"""
SQM v6.12 Stage3 — 바코드 스캔 대조 엔진
==========================================
출고 확정 전 현장 스캔 UID와 시스템 출고 예정 UID를 대조.
불일치 시 Hard Stop.

작성자: Ruby
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Set, Tuple
from core.outbound_scan_validation_patch import is_scannable_status

logger = logging.getLogger(__name__)

_INVISIBLE_CHARS = '\ufeff\u200b\u200c\u200d\u00a0\u2060'


def _clean_uid(raw: str) -> str:
    if not raw:
        return ''
    cleaned = str(raw).strip()
    for ch in _INVISIBLE_CHARS:
        cleaned = cleaned.replace(ch, '')
    return cleaned.replace('\r', '').replace('\n', '').strip()


def _normalize_sublt(value) -> str:
    s = str(value).strip()
    try:
        return str(int(s))
    except (ValueError, TypeError):
        return s


class BarcodeScanEngine:
    """바코드 스캔 대조 + uid_verify_history 관리"""

    def __init__(self, db, engine=None):
        self.db     = db
        self._engine = engine  # v8.0.2 [P2]: crud_mixin 중앙함수 위임용
        self._ensure_table()
        self._ensure_swap_table()
        self._ensure_outbound_scan_table()

    # ---------------------------------------------------------------------
    # Phase 3 (RUBI) — Random Outbound: Scan = Immediate Confirm(OUT)
    #   - STEP1~3: TONBAG 상태 변경 금지 (Phase 2)
    #   - STEP4: UID 스캔 순간에만 SOLD(=OUT) 확정
    #   - Target 체크는 allocation_plan.qty_mt(중량) 기반
    # ---------------------------------------------------------------------

    def _ensure_outbound_scan_table(self) -> None:
        """스캔 확정 로그 테이블(best-effort). 없으면 생성만 하고 실패는 무시."""
        try:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS outbound_scan_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tonbag_id INTEGER,
                    tonbag_uid TEXT,
                    lot_no TEXT,
                    sale_ref TEXT,
                    customer TEXT,
                    weight_kg REAL,
                    source_file TEXT,
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    undone INTEGER DEFAULT 0,
                    undone_at TEXT
                )
                """
            )
            try:
                self.db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_out_scan_uid ON outbound_scan_log(tonbag_uid)"
                )
                self.db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_out_scan_lot ON outbound_scan_log(lot_no)"
                )
                self.db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_out_scan_at ON outbound_scan_log(created_at DESC)"
                )
            except Exception:
                logger.debug("[SUPPRESSED] exception in barcode_scan_engine.py")  # noqa
        except Exception as e:
            logger.debug(f"outbound_scan_log 테이블 생성 스킵: {e}")

    def _recalc_inventory_lot_weights(self, lot_no: str, now: str = None, reason: str = 'P2_SCAN') -> None:
        """v8.0.2 [P2 wrapper]: crud_mixin._recalc_current_weight() 위임.
        GPT 정정본 권장: 계산 본체는 crud_mixin 1개, 이 함수는 위임만 수행.
        engine 미주입 시 직접 SQL로 폴백 (하위호환 유지).
        """
        lot_no = str(lot_no or '').strip()
        if not lot_no:
            return

        # 1순위: engine._recalc_current_weight() 위임 (crud_mixin 본체)
        if self._engine and hasattr(self._engine, '_recalc_current_weight'):
            try:
                self._engine._recalc_current_weight(lot_no, reason=reason)
                logger.debug(f"[{reason}][wrapper→crud] LOT={lot_no}")
                return
            except Exception as _e:
                logger.debug(f"[{reason}] crud 위임 실패 → 직접 계산 폴백: {_e}")

        # 2순위: 직접 SQL 폴백 (engine 미주입 환경 하위호환)
        now = now or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            row_avail = self.db.fetchone(
                "SELECT COALESCE(SUM(weight),0) AS avail_kg "
                "FROM inventory_tonbag WHERE lot_no=? "
                "AND status IN ('AVAILABLE','RESERVED') AND COALESCE(is_sample,0)=0",
                (lot_no,)
            )
            avail_kg = float(row_avail.get('avail_kg', 0) if isinstance(row_avail, dict) else (row_avail[0] or 0))
            row_picked = self.db.fetchone(
                "SELECT COALESCE(SUM(weight),0) AS picked_kg "
                "FROM inventory_tonbag WHERE lot_no=? "
                "AND status='PICKED' AND COALESCE(is_sample,0)=0",
                (lot_no,)
            )
            picked_kg = float(row_picked.get('picked_kg', 0) if isinstance(row_picked, dict) else (row_picked[0] or 0))
            self.db.execute(
                "UPDATE inventory SET current_weight=?, picked_weight=?, updated_at=? WHERE lot_no=?",
                (avail_kg, picked_kg, now, lot_no)
            )
            logger.debug(f"[{reason}][fallback] LOT={lot_no} current={avail_kg:.0f}kg picked={picked_kg:.0f}kg")
        except Exception as e:
            logger.debug(f"[{reason}] recalc_lot={lot_no} failed: {e}")

    def _pick_target_row_for_lot(self, lot_no: str, sale_ref: str = None) -> Dict:
        """allocation_plan에서 LOT 목표(중량) 조회. sale_ref가 있으면 우선 적용."""
        lot_no = str(lot_no or '').strip()
        if not lot_no:
            return {}
        try:
            # Phase2에서는 tonbag_id가 NULL(톤백 미지정)일 수 있음.
            # status 값은 버전마다 다르므로, "취소/실행완료"만 제외하는 관대한 기준 사용.
            where = "lot_no = ? AND COALESCE(status,'') NOT IN ('CANCELLED','EXECUTED','REJECTED')"
            params = [lot_no]
            if sale_ref:
                where += " AND COALESCE(sale_ref,'') = ?"
                params.append(str(sale_ref).strip())
            row = self.db.fetchone(
                f"SELECT lot_no, customer, sale_ref, SUM(COALESCE(qty_mt,0)) AS qty_mt_sum, COUNT(*) AS row_cnt "
                f"FROM allocation_plan WHERE {where}",
                tuple(params),
            )
            if not row:
                return {}
            if isinstance(row, dict):
                return row
            # tuple fallback
            return {
                "lot_no": lot_no,
                "customer": "",
                "sale_ref": sale_ref or "",
                "qty_mt_sum": float(row[3] or 0),
                "row_cnt": int(row[4] or 0),
            }
        except Exception as e:
            logger.debug(f"allocation_plan 목표 조회 실패: {e}")
            return {}

    def _get_confirmed_weight_kg(self, lot_no: str, sale_ref: str = None) -> float:
        try:
            where = "lot_no = ? AND undone = 0"
            params = [str(lot_no).strip()]
            if sale_ref:
                where += " AND COALESCE(sale_ref,'') = ?"
                params.append(str(sale_ref).strip())
            row = self.db.fetchone(
                f"SELECT SUM(COALESCE(weight_kg,0)) AS s FROM outbound_scan_log WHERE {where}",
                tuple(params),
            )
            if not row:
                return 0.0
            return float(row.get('s', 0) if isinstance(row, dict) else (row[0] or 0))
        except Exception:
            return 0.0

    def _is_gate1_passed(self, sale_ref: str = None, lot_no: str = None) -> bool:
        """Gate-1 통과 여부 확인. process_state 컬럼이 없으면 하위 호환을 위해 True."""
        try:
            cols = {str(r.get('name','')).strip().lower() for r in (self.db.fetchall('PRAGMA table_info(allocation_plan)') or [])}
            if 'process_state' not in cols:
                return True
            where = ["status <> 'CANCELLED'"]
            params = []
            if sale_ref:
                where.append("COALESCE(sale_ref,'') = ?")
                params.append(str(sale_ref).strip())
            if lot_no:
                where.append("lot_no = ?")
                params.append(str(lot_no).strip())
            where.append("COALESCE(process_state,'') IN ('GATE1_PASSED','SCAN_CONFIRMED')")
            row = self.db.fetchone(
                f"SELECT 1 AS ok FROM allocation_plan WHERE {' AND '.join(where)} LIMIT 1",
                tuple(params),
            )
            return bool(row)
        except Exception:
            return True

    def _is_uid_already_confirmed(self, uid: str) -> bool:
        uid = _clean_uid(uid)
        if not uid:
            return False
        try:
            row = self.db.fetchone(
                "SELECT id FROM outbound_scan_log WHERE tonbag_uid = ? AND undone = 0 LIMIT 1",
                (uid,),
            )
            return bool(row)
        except Exception:
            return False

    def _confirm_one_uid_random(self, uid: str, sale_ref: str = None, source_file: str = "") -> Dict:
        """(Phase3) UID 1건 스캔 → 즉시 SOLD(=OUT) 확정."""
        uid = _clean_uid(uid)
        if not uid:
            return {"ok": False, "uid": uid, "reason": "EMPTY"}

        if self._is_uid_already_confirmed(uid):
            return {"ok": False, "uid": uid, "reason": "DUPLICATE_CONFIRMED"}

        # tonbag 조회 (STEP4 확정 전 AVAILABLE/RESERVED 상태를 허용)
        # v7.1.1 [SAMPLE-SCAN-1]: is_sample=1(샘플) 톤백은 조회 자체를 분리하여 HARD-STOP
        row = self.db.fetchone(
            "SELECT id, lot_no, sub_lt, tonbag_no, weight, tonbag_uid, status, "
            "COALESCE(is_sample, 0) AS is_sample "
            "FROM inventory_tonbag "
            "WHERE (tonbag_uid = ? OR COALESCE(tonbag_no,'') = ? OR CAST(sub_lt AS TEXT) = ? OR CAST(sub_lt AS TEXT) = ?) "
            "LIMIT 1",
            (uid, uid, uid, _normalize_sublt(uid)),
        )
        if not row:
            return {"ok": False, "uid": uid, "reason": "UID_NOT_FOUND"}

        # v7.1.1 [SAMPLE-SCAN-1]: 샘플 톤백(sub_lt=0 또는 is_sample=1) 스캔 → HARD-STOP
        # 샘플은 재고에는 존재하지만 절대 출고 대상이 아님 (SQM 핵심 불변 조건)
        if int(row.get('is_sample') or 0) == 1 or int(row.get('sub_lt') or -1) == 0:
            logger.warning(
                f"[SAMPLE-SCAN-1] 샘플 스캔 차단: uid={uid} "
                f"lot_no={row.get('lot_no','')} sub_lt={row.get('sub_lt','')} "
                f"— 샘플 톤백은 출고 불가"
            )
            return {
                "ok": False,
                "uid": uid,
                "reason": "SAMPLE_SCAN_BLOCKED",
                "message": (
                    f"[SAMPLE-SCAN-1] 샘플 톤백 스캔 차단: {uid} "
                    f"(sub_lt={row.get('sub_lt','')}) — 샘플은 출고 대상이 아닙니다."
                ),
                "lot_no": str(row.get('lot_no', '')),
            }

        lot_no = str(row.get('lot_no', '')).strip()
        if not lot_no:
            return {"ok": False, "uid": uid, "reason": "LOT_EMPTY"}

        status_chk = is_scannable_status(row.get('status', ''))
        if not status_chk.success:
            return {
                "ok": False,
                "uid": uid,
                "reason": status_chk.code,
                "message": status_chk.message,
                "lot_no": lot_no,
            }

        if sale_ref and not self._is_gate1_passed(sale_ref=sale_ref, lot_no=lot_no):
            return {"ok": False, "uid": uid, "reason": "GATE1_NOT_PASSED", "lot_no": lot_no}

        target = self._pick_target_row_for_lot(lot_no, sale_ref=sale_ref)
        target_mt = float(target.get('qty_mt_sum', 0) or 0)
        target_kg = target_mt * 1000.0
        if target_kg <= 0:
            return {"ok": False, "uid": uid, "reason": "LOT_SCAN_BLOCKED", "lot_no": lot_no}

        weight_kg = float(row.get('weight', 0) or 0)
        confirmed_kg = self._get_confirmed_weight_kg(lot_no, sale_ref=sale_ref)
        # 0.1% 또는 최소 1kg 허용 오차
        tolerance_kg = max(1.0, target_kg * 0.001)
        if confirmed_kg + weight_kg > target_kg + tolerance_kg:
            return {
                "ok": False,
                "uid": uid,
                "reason": "TARGET_EXCEEDED",
                "lot_no": lot_no,
                "target_kg": target_kg,
                "confirmed_kg": confirmed_kg,
                "this_kg": weight_kg,
            }

        customer = str(target.get('customer', '') or '').strip()
        eff_sale_ref = (str(sale_ref).strip() if sale_ref else str(target.get('sale_ref', '') or '').strip())

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 확정 처리: inventory_tonbag → SOLD (레거시 호환)
        self.db.execute(
            "UPDATE inventory_tonbag SET status='OUTBOUND', outbound_date=?, picked_to=?, sale_ref=?, updated_at=? WHERE id=?",
            (now, customer, eff_sale_ref, now, row['id']),
        )
        # 로그 기록
        self.db.execute(
            "INSERT INTO outbound_scan_log (tonbag_id, tonbag_uid, lot_no, sale_ref, customer, weight_kg, source_file) "
            "VALUES (?,?,?,?,?,?,?)",
            (row['id'], uid, lot_no, eff_sale_ref, customer, weight_kg, source_file or ''),
        )
        # 재고 이동 이력(있으면)
        try:
            self.db.execute(
                "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                "VALUES (?,'SOLD',?,?,?)",
                (lot_no, weight_kg, f"phase4_scan_confirm uid={uid}", now),
            )
        except Exception:
            logger.debug("[SUPPRESSED] exception in barcode_scan_engine.py")  # noqa
        # allocation_plan 업무 상태 갱신
        try:
            cols = {str(r.get('name','')).strip().lower() for r in (self.db.fetchall('PRAGMA table_info(allocation_plan)') or [])}
            # v6.5.4: 화이트리스트 컬럼만 SET 허용 (SQL 인젝션 방지)
            _ALLOWED_SET_COLS = {'process_state', 'updated_at'}
            sets = []
            params = []
            if 'process_state' in cols and 'process_state' in _ALLOWED_SET_COLS:
                sets.append("process_state = ?")
                params.append('SCAN_CONFIRMED')
            if 'updated_at' in cols and 'updated_at' in _ALLOWED_SET_COLS:
                sets.append("updated_at = ?")
                params.append(now)
            if sets:
                q = f"UPDATE allocation_plan SET {', '.join(sets)} WHERE lot_no = ?"
                params.append(lot_no)
                if eff_sale_ref:
                    q += " AND COALESCE(sale_ref,'') = ?"
                    params.append(eff_sale_ref)
                self.db.execute(q, tuple(params))
            # target 충족 시 EXECUTED로 종결
            if eff_sale_ref:
                new_confirmed_kg = confirmed_kg + weight_kg
                if target_kg > 0 and new_confirmed_kg >= (target_kg - tolerance_kg):
                    self.db.execute(
                        "UPDATE allocation_plan SET status='EXECUTED' WHERE lot_no = ? AND COALESCE(sale_ref,'') = ? AND status <> 'CANCELLED'",
                        (lot_no, eff_sale_ref),
                    )
        except Exception:
            logger.debug("[SUPPRESSED] exception in barcode_scan_engine.py")  # noqa

        return {
            "ok": True,
            "uid": uid,
            "tonbag_id": row['id'],
            "lot_no": lot_no,
            "sale_ref": eff_sale_ref,
            "customer": customer,
            "weight_kg": weight_kg,
        }

    def process_barcode_scan_confirm_out(self, scanned_codes_or_file, sale_ref: str = None) -> Dict:
        """(Phase3) 스캔 파일/리스트 → 즉시 확정(OUT=SOLD)."""
        scanned_codes = (
            self.read_scan_file(scanned_codes_or_file)
            if isinstance(scanned_codes_or_file, str)
            else list(scanned_codes_or_file or [])
        )
        # UID 정리 + 중복 하드스톱
        seen, duplicates, uniq = set(), [], []
        for raw in scanned_codes:
            u = _clean_uid(raw)
            if not u:
                continue
            if u in seen:
                duplicates.append(u)
            else:
                seen.add(u)
                uniq.append(u)

        if duplicates:
            return {
                "success": False,
                "confirmed": 0,
                "duplicates": sorted(set(duplicates)),
                "errors": [f"중복 UID 스캔: {len(set(duplicates))}개"],
            }

        ok_rows, fails = [], []
        # 트랜잭션으로 원자성 확보 (All-or-Nothing)
        with self.db.transaction("IMMEDIATE"):
            for u in uniq:
                res = self._confirm_one_uid_random(u, sale_ref=sale_ref, source_file="barcode_scan")
                if res.get("ok"):
                    ok_rows.append(res)
                else:
                    fails.append(res)
            if fails:
                # 실패가 1건이라도 있으면 롤백 유도
                raise RuntimeError(json.dumps({"phase3_fail": fails}, ensure_ascii=False))

        # v7.1.1 [SCAN-COMPLETE-1]: 출고 완료 검증
        # PICKED 개수와 실제 확정(SOLD) 개수 비교 → 불일치 시 warnings 기록
        sc1_warnings = []
        try:
            if sale_ref:
                _picked_q = self.db.fetchone(
                    "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                    "WHERE status='PICKED' AND COALESCE(sale_ref,'')=? "
                    "AND COALESCE(is_sample,0)=0",
                    (str(sale_ref).strip(),)
                )
            else:
                _picked_q = self.db.fetchone(
                    "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                    "WHERE status='PICKED' AND COALESCE(is_sample,0)=0"
                )
            _remaining_picked = int((_picked_q.get('cnt') if isinstance(_picked_q, dict) else _picked_q[0]) or 0)                 if _picked_q else 0
            _confirmed_cnt = len(ok_rows)
            if _remaining_picked > 0:
                _iw = (
                    f"[SCAN-COMPLETE-1] 미확정 PICKED 잔여: "
                    f"PICKED 잔여={_remaining_picked}개 "
                    f"(확정={_confirmed_cnt}개) "
                    f"— 스캔 누락 또는 추가 스캔 필요"
                )
                sc1_warnings.append(_iw)
                logger.warning(_iw)
        except Exception as _sc1e:
            logger.debug(f"[SCAN-COMPLETE-1] 검증 스킵: {_sc1e}")

        _result = {
            "success": True,
            "confirmed": len(ok_rows),
            "rows": ok_rows,
        }
        if sc1_warnings:
            _result["warnings"] = sc1_warnings
        return _result


    def confirm_one_uid_live(self, uid: str, sale_ref: str = None, source: str = "live_scan") -> Dict:
        """(Phase4) 실시간 스캔 1건 확정.
        - Enter 입력(USB 스캐너 키보드 입력)용
        - 실패 시 예외를 던지지 않고 dict로 반환
        """
        try:
            with self.db.transaction("IMMEDIATE"):
                res = self._confirm_one_uid_random(uid, sale_ref=sale_ref, source_file=source)
                if not res.get("ok"):
                    return {"success": False, **res}
            return {"success": True, **res}
        except Exception as e:
            return {"success": False, "uid": _clean_uid(uid), "reason": "EXCEPTION", "message": str(e)}

    def export_scan_confirm_report_csv(self, rows: List[Dict], output_dir: str, prefix: str = "OUTBOUND_SCAN") -> str:
        """(Phase4) 스캔 확정 결과를 CSV로 저장하고 파일 경로를 반환."""
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception:
            logger.debug("[SUPPRESSED] exception in barcode_scan_engine.py")  # noqa
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_dir, f"{prefix}_{ts}.csv")
        fields = ["sale_ref", "customer", "lot_no", "tonbag_id", "uid", "weight_kg"]
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                for r in rows or []:
                    if not isinstance(r, dict):
                        continue
                    w.writerow({
                        "sale_ref": r.get("sale_ref", ""),
                        "customer": r.get("customer", ""),
                        "lot_no": r.get("lot_no", ""),
                        "tonbag_id": r.get("tonbag_id", ""),
                        "uid": r.get("uid", ""),
                        "weight_kg": r.get("weight_kg", ""),
                    })
            return path
        except Exception as e:
            logger.debug(f"CSV 리포트 저장 실패: {e}")
            return ""

    def undo_last_scan_confirm(self, sale_ref: str = None) -> Dict:
        """(Phase3) 최근 스캔 확정 1건 Undo (관리자용)."""
        try:
            where = "undone = 0"
            params = []
            if sale_ref:
                where += " AND COALESCE(sale_ref,'') = ?"
                params.append(str(sale_ref).strip())
            row = self.db.fetchone(
                f"SELECT id, tonbag_id, tonbag_uid, lot_no, weight_kg FROM outbound_scan_log "
                f"WHERE {where} ORDER BY id DESC LIMIT 1",
                tuple(params),
            )
            if not row:
                return {"success": False, "message": "Undo 대상 스캔 로그가 없습니다."}

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with self.db.transaction("IMMEDIATE"):
                self.db.execute(
                    "UPDATE outbound_scan_log SET undone = 1, undone_at = ? WHERE id = ?",
                    (now, row['id']),
                )
                # tonbag 상태 복구: AVAILABLE 로 복귀 (Phase2 기본)
                self.db.execute(
                    "UPDATE inventory_tonbag SET status='AVAILABLE', updated_at=? WHERE id=?",
                    (now, row['tonbag_id']),
                )
                try:
                    self.db.execute(
                        "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                        "VALUES (?,'UNDO_SOLD',?,?,?)",
                        (row.get('lot_no', ''), float(row.get('weight_kg', 0) or 0), f"undo uid={row.get('tonbag_uid','')}", now),
                    )
                except Exception:
                    logger.debug("[SUPPRESSED] exception in barcode_scan_engine.py")  # noqa
            return {"success": True, "message": "최근 스캔 확정 1건을 되돌렸습니다.", "uid": row.get('tonbag_uid','')}
        except Exception as e:
            return {"success": False, "message": f"Undo 실패: {e}"}

    def _ensure_table(self):
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS uid_verify_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    outbound_ref    TEXT,
                    sale_ref        TEXT,
                    verify_result   TEXT NOT NULL,
                    expected_count  INTEGER,
                    scanned_count   INTEGER,
                    missing_uids    TEXT,
                    extra_uids      TEXT,
                    duplicate_uids  TEXT,
                    scan_file_name  TEXT,
                    verified_at     TEXT DEFAULT (datetime('now'))
                )
            """)
            try:
                self.db.execute("ALTER TABLE uid_verify_history ADD COLUMN sale_ref TEXT")
            except Exception as _ae:
                # 컬럼 이미 존재 시 정상 (sqlite3.OperationalError: duplicate column)
                logging.getLogger(__name__).debug(f"[바코드] sale_ref 컬럼 추가 스킵: {_ae}")
            try:
                self.db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_verify_history_ref "
                    "ON uid_verify_history(outbound_ref)"
                )
                self.db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_verify_history_at "
                    "ON uid_verify_history(verified_at DESC)"
                )
                self.db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_verify_history_sale "
                    "ON uid_verify_history(sale_ref)"
                )
            except Exception as _ie:
                logging.getLogger(__name__).debug(f"[바코드] sale_ref 인덱스 생성 스킵: {_ie}")
        except Exception as e:
            logger.debug(f"uid_verify_history 테이블 생성 스킵: {e}")

    def _ensure_swap_table(self):
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS uid_swap_history (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no              TEXT NOT NULL,
                    expected_tonbag_id  INTEGER,
                    expected_uid        TEXT,
                    scanned_tonbag_id   INTEGER,
                    scanned_uid         TEXT,
                    reason              TEXT,
                    created_at          TEXT DEFAULT (datetime('now'))
                )
            """)
        except Exception as e:
            logger.debug(f"uid_swap_history 테이블 생성 스킵: {e}")

    def _uid_to_lot_map(self, uids: List[str]) -> Dict[str, str]:
        if not uids:
            return {}
        uniq = [u for u in dict.fromkeys([str(x).strip() for x in uids if str(x).strip()])]
        if not uniq:
            return {}
        try:
            placeholders = ",".join("?" * len(uniq))
            rows = self.db.fetchall(
                f"SELECT tonbag_uid, lot_no FROM inventory_tonbag WHERE tonbag_uid IN ({placeholders})",
                tuple(uniq),
            )
            out = {}
            for r in rows or []:
                uid = str(r.get("tonbag_uid", "")).strip()
                lot = str(r.get("lot_no", "")).strip()
                if uid and lot:
                    out[uid] = lot
            return out
        except Exception as e:
            logger.debug(f"UID→LOT 매핑 조회 실패: {e}")
            return {}

    def read_scan_file(self, file_path: str) -> List[str]:
        def _clean_lines(lines: List[str]) -> List[str]:
            cleaned = []
            for line in lines:
                uid = _clean_uid(line)
                if not uid:
                    continue
                # 헤더 라인(UID/BARCODE 등) 자동 제외
                u = uid.upper()
                if u in ('UID', 'BARCODE', 'TONBAG_UID', 'SUB_LT'):
                    continue
                cleaned.append(uid)
            return cleaned

        ext = file_path.lower().rsplit('.', 1)[-1] if '.' in file_path else ''
        if ext == 'txt':
            encodings = ('utf-8-sig', 'utf-8', 'cp949', 'euc-kr', 'latin-1')
            for enc in encodings:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        lines = _clean_lines([line for line in f])
                    if lines:
                        return lines
                except (UnicodeDecodeError, UnicodeError) as _e:
                    logger.debug(f"[SUPPRESSED] exception in barcode_scan_engine.py: {_e}")  # noqa
            return []
        elif ext == 'csv':
            import pandas as pd
            encodings = ('utf-8-sig', 'utf-8', 'cp949', 'euc-kr', 'latin-1')
            for enc in encodings:
                try:
                    df = pd.read_csv(file_path, header=None, dtype=str, encoding=enc)
                    values = df.iloc[:, 0].dropna().tolist()
                    lines = _clean_lines(values)
                    if lines:
                        return lines
                except (UnicodeDecodeError, UnicodeError) as _e:
                    logger.debug(f"[SUPPRESSED] exception in barcode_scan_engine.py: {_e}")  # noqa
                except Exception as _e:
                    logger.debug(f"[SUPPRESSED] exception in barcode_scan_engine.py: {_e}")  # noqa
            return []
        elif ext in ('xlsx', 'xls'):
            import pandas as pd
            df = pd.read_excel(file_path, header=None, dtype=str)
            values = df.iloc[:, 0].dropna().tolist()
            return _clean_lines(values)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: .{ext}")

    def _build_picked_maps(self, sale_ref: str = None) -> Tuple[List[Dict], Dict[str, Dict], Dict[str, Dict]]:
        query = (
            "SELECT id, lot_no, sub_lt, weight, tonbag_uid, picked_to, sale_ref "
            "FROM inventory_tonbag WHERE status = 'PICKED'"
        )
        params = []
        if sale_ref:
            query += " AND sale_ref = ?"
            params.append(sale_ref)
        rows = self.db.fetchall(query, tuple(params)) or []
        uid_map, sublt_map = {}, {}
        for r in rows:
            uid = _clean_uid(r.get('tonbag_uid', ''))
            if uid:
                uid_map[uid] = r
            sub_lt_raw = str(r.get('sub_lt', '')).strip()
            if sub_lt_raw:
                sublt_map[sub_lt_raw] = r
                sublt_map[_normalize_sublt(sub_lt_raw)] = r
        return rows, uid_map, sublt_map

    def verify_outbound_scan(self, expected_uids: Set[str], scanned_uids_raw: List[str],
                              outbound_ref: str = '', scan_file_name: str = '', sale_ref: str = '') -> Dict:
        picked_rows, uid_map, sublt_map = self._build_picked_maps(sale_ref=sale_ref or None)
        # expected_uids가 넘어오면 호출자 기준(expected_uids) 우선, 없으면 DB PICKED fallback
        use_db_expected = not bool(expected_uids) and bool(picked_rows)
        expected_ids = {int(r['id']) for r in picked_rows} if use_db_expected else set()

        seen_codes, duplicates = set(), []
        matched_ids = set()
        extra_codes = []
        for raw in scanned_uids_raw:
            code = _clean_uid(raw)
            if not code:
                continue
            if code in seen_codes:
                duplicates.append(code)
                continue
            seen_codes.add(code)
            if use_db_expected:
                row = uid_map.get(code) or sublt_map.get(code) or sublt_map.get(_normalize_sublt(code))
                if row:
                    matched_ids.add(int(row['id']))
                else:
                    extra_codes.append(code)
            else:
                # DB PICKED가 없으면 호출자 expected_uids로 fallback 검증 (테스트/레거시 호환)
                pass

        if use_db_expected:
            missing_rows = [r for r in picked_rows if int(r['id']) not in matched_ids]
            missing = sorted([
                _clean_uid(r.get('tonbag_uid') or '') or str(r.get('sub_lt', ''))
                for r in missing_rows
            ])
            extra = sorted(set(extra_codes))
            expected_count = len(expected_ids)
        else:
            expected_clean = {_clean_uid(u) for u in (expected_uids or set()) if _clean_uid(u)}
            expected_norm = {_normalize_sublt(u) for u in expected_clean}
            scanned_norm = {_normalize_sublt(s) for s in seen_codes}
            missing = sorted([u for u in expected_clean if _normalize_sublt(u) not in scanned_norm])
            extra = sorted([s for s in seen_codes if _normalize_sublt(s) not in expected_norm])
            expected_count = len(expected_clean)
        duplicates = sorted(set(duplicates))
        # 중복은 경고로만 취급 (PASS 유지)
        passed = (not missing) and (not extra)
        pass_swap = False
        swap_lots = []
        if (not duplicates) and missing and extra:
            miss_map = self._uid_to_lot_map(missing)
            extra_map = self._uid_to_lot_map(extra)
            if len(miss_map) == len(missing) and len(extra_map) == len(extra):
                miss_cnt_by_lot = {}
                extra_cnt_by_lot = {}
                for uid in missing:
                    lot = miss_map.get(uid, '')
                    miss_cnt_by_lot[lot] = miss_cnt_by_lot.get(lot, 0) + 1
                for uid in extra:
                    lot = extra_map.get(uid, '')
                    extra_cnt_by_lot[lot] = extra_cnt_by_lot.get(lot, 0) + 1
                # LOT 내부 스왑 조건: 각 LOT에서 extra <= missing
                lot_ok = True
                for lot, ec in extra_cnt_by_lot.items():
                    if not lot or ec > miss_cnt_by_lot.get(lot, 0):
                        lot_ok = False
                        break
                if lot_ok:
                    pass_swap = True
                    swap_lots = sorted(extra_cnt_by_lot.keys())

        result = {
            'result': 'PASS' if passed else ('PASS_SWAP' if pass_swap else 'FAIL'),
            'missing': missing, 'extra': extra, 'duplicates': duplicates,
            'expected_count': expected_count, 'scanned_count': len(scanned_uids_raw),
            'scanned_unique_count': len(seen_codes),
            'swap_lots': swap_lots,
        }
        if passed:
            if duplicates:
                result['message'] = (
                    f"✅ UID 대조 통과 ({expected_count}개 일치, "
                    f"중복 {len(duplicates)}개 경고)"
                )
            else:
                result['message'] = f"✅ UID 대조 통과 ({expected_count}개 일치)"
        elif pass_swap:
            result['message'] = (
                f"⚠️ UID 대조 조건부 통과(PASS_SWAP): "
                f"같은 LOT 내부 스왑으로 진행 가능 (LOT {len(swap_lots)}개)"
            )
        else:
            parts = []
            if missing: parts.append(f"누락 {len(missing)}개")
            if extra: parts.append(f"초과 {len(extra)}개")
            if duplicates: parts.append(f"중복 {len(duplicates)}개")
            result['message'] = f"❌ UID 대조 실패: {', '.join(parts)}"

        try:
            self.db.execute("""
                INSERT INTO uid_verify_history
                (outbound_ref, sale_ref, verify_result, expected_count, scanned_count,
                 missing_uids, extra_uids, duplicate_uids, scan_file_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (outbound_ref, sale_ref, result['result'], result['expected_count'],
                  result['scanned_count'],
                  json.dumps(missing, ensure_ascii=False) if missing else None,
                  json.dumps(extra, ensure_ascii=False) if extra else None,
                  json.dumps(duplicates, ensure_ascii=False) if duplicates else None,
                  scan_file_name))
        except Exception as e:
            logger.warning(f"uid_verify_history 기록 실패: {e}")
        return result

    def get_picked_uids(self, lot_no: str = None, sale_ref: str = None) -> Set[str]:
        query = "SELECT tonbag_uid FROM inventory_tonbag WHERE status = 'PICKED' AND tonbag_uid IS NOT NULL"
        params = []
        if lot_no:
            query += " AND lot_no = ?"
            params.append(lot_no)
        if sale_ref:
            query += " AND sale_ref = ?"
            params.append(sale_ref)
        rows = self.db.fetchall(query, tuple(params))
        return {_clean_uid(r['tonbag_uid']) for r in rows if r.get('tonbag_uid') and _clean_uid(r['tonbag_uid'])}

    def get_picked_sale_refs(self) -> List[str]:
        try:
            rows = self.db.fetchall(
                "SELECT DISTINCT sale_ref FROM inventory_tonbag "
                "WHERE status='PICKED' AND sale_ref IS NOT NULL AND sale_ref != '' "
                "ORDER BY sale_ref"
            ) or []
            return [str(r.get('sale_ref', '')).strip() for r in rows if str(r.get('sale_ref', '')).strip()]
        except Exception:
            return []

    def get_lot_mode_reserved_count(self) -> int:
        """LOT 단위 예약(tonbag_id 미지정) 잔여 건수."""
        try:
            row = self.db.fetchone(
                "SELECT COUNT(*) AS cnt FROM allocation_plan WHERE status='RESERVED' AND tonbag_id IS NULL"
            )
            return int(row.get('cnt', 0) if isinstance(row, dict) else (row[0] if row else 0))
        except Exception:
            return 0


    # ══ v8.6.4: process_barcode_scan_for_lot_mode 서브메서드 ══

    def _scan_validate_tonbag_uid(self, uid: str, current_lot_no: str,
                                   result: dict):
        """v8.6.4: 스캔 UID 유효성 검증 (scan 분해 1/3). None=오류."""
        import sqlite3 as _sq
        if not uid:
            result.setdefault("errors",[]).append("[SD-01] UID 없음")
            return None
        try:
            tb = self.db.fetchone(
                "SELECT * FROM inventory_tonbag WHERE tonbag_uid=?", (uid,))
        except (_sq.OperationalError, OSError) as _e:
            logger.debug(f"[SUPPRESSED] barcode_scan_engine.py: {_e}")  # noqa
            return None
        if not tb:
            result.setdefault("errors",[]).append(f"[SD-02] UID 미발견: {uid}")
            return None
        tb = dict(tb) if not isinstance(tb, dict) else tb
        if tb.get("status") in ("OUTBOUND","SOLD"):
            result.setdefault("errors",[]).append(f"[SD-03][ALREADY_SOLD] {uid}")
            return None
        if current_lot_no and tb.get("lot_no") != current_lot_no:
            result.setdefault("errors",[]).append(
                f"[SD-04][LOT_MISMATCH] 스캔={tb.get('lot_no')} 현재={current_lot_no}")
            return None
        return tb

    def _scan_recalc_lot_weight(self, lot_nos: list) -> None:
        """v8.6.4: LOT current_weight 일괄 재계산 (scan 분해 2/3)."""
        import sqlite3 as _sq
        for lot_no in set(lot_nos or []):
            try:
                self.db.execute(
                    """UPDATE inventory
                       SET current_weight=(
                           SELECT COALESCE(SUM(weight),0)
                           FROM inventory_tonbag
                           WHERE lot_no=? AND status='AVAILABLE'
                             AND COALESCE(is_sample,0)=0
                       ), updated_at=datetime('now')
                       WHERE lot_no=?""",
                    (lot_no, lot_no))
            except (_sq.OperationalError, OSError) as _e:
                logger.debug(f"[SUPPRESSED] barcode_scan_engine.py: {_e}")  # noqa

    def process_barcode_scan_for_lot_mode(
        self, file_path: str, target_lot_no: str = None
    ) -> Dict:
        """
        LOT 단위 예약 모드 전용 스캔 처리. (v6.3.4 RUBI 개선)

        변경사항:
        - RESERVED → PICKED → SOLD 3단계 정상 처리 (기존: RESERVED → SOLD 직접 건너뜀)
        - allocation_plan.export_type 을 picking_table / sold_table 에 전달
        - export_type='반송' 건은 result['bangsong_lots'] 에 따로 수집 → 세관 신고 Excel 트리거

        v6.9.4 추가:
          - target_lot_no 파라미터: 현재 출고 중인 LOT 지정
          - 오스캔 HARD-STOP: 스캔 UID의 lot_no ≠ target_lot_no → WRONG_LOT_SCAN

        flow:
          scan UID → inventory_tonbag 조회
              → [v6.9.4] LOT 불일치 → HARD-STOP (WRONG_LOT_SCAN)
              → allocation_plan(RESERVED, tonbag_id IS NULL, lot_no 일치) 1건 매칭
              → tonbag: RESERVED→PICKED (picked_date), allocation_plan: tonbag_id 확정
              → tonbag: PICKED→SOLD   (sold_date),  allocation_plan: EXECUTED
              → picking_table INSERT, sold_table INSERT, stock_movement INSERT
        """
        scanned_codes = self.read_scan_file(file_path)
        seen = set()
        duplicates = []
        uniq_codes = []
        for code in scanned_codes:
            c = _clean_uid(code)
            if not c:
                continue
            if c in seen:
                duplicates.append(c)
            else:
                seen.add(c)
                uniq_codes.append(c)

        if duplicates:
            return {
                'success': False,
                'sold': 0,
                'not_found': [],
                'no_plan': [],
                'duplicates': sorted(set(duplicates)),
                'remaining_lot_reserved': self.get_lot_mode_reserved_count(),
                'errors': [f"중복 UID 스캔: {len(set(duplicates))}개"],
            }

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sold_count = 0
        not_found = []
        no_plan = []
        bangsong_lots = []   # v6.3.4 RUBI: 반송 건 수집
        sd08_warnings = []   # v6.9.7 [SD-08]: warehouse mismatch

        with self.db.transaction("IMMEDIATE"):
            for code in uniq_codes:
                # v6.9.5 [SD-10]: SOLD 상태 재출고 명확한 에러 분리
                # 기존: status 조건 불일치 → not_found 에 묶여 에러 불명확
                # 개선: SOLD 상태 먼저 확인 → 명확한 ALREADY_SOLD 에러
                _sold_check = self.db.fetchone(
                    "SELECT id, tonbag_uid, lot_no, status, weight, location FROM inventory_tonbag "
                    "WHERE (tonbag_uid = ? OR CAST(sub_lt AS TEXT) = ?) "
                    "AND status = 'SOLD'",
                    (code, code),
                )
                if _sold_check:
                    _sold_err = (
                        f"[SD-10] 이미 출고된 톤백 재스캔 차단: "
                        f"{_sold_check.get('tonbag_uid','?')} "
                        f"(LOT={_sold_check.get('lot_no','?')}, status=SOLD) "
                        f"— 이중 출고 방지"
                    )
                    logger.error(_sold_err)
                    return {
                        'success': False,
                        'sold': 0,
                        'not_found': [],
                        'no_plan': [],
                        'duplicates': [],
                        'wrong_lot': [],
                        'already_sold': [code],
                        'errors': [_sold_err],
                    }

                row = self.db.fetchone(
                    "SELECT id, lot_no, sub_lt, weight, tonbag_uid, status, location FROM inventory_tonbag "
                    "WHERE (tonbag_uid = ? OR CAST(sub_lt AS TEXT) = ?) "
                    "AND status IN ('AVAILABLE','RESERVED','PICKED')",
                    (code, code),
                )
                if not row:
                    # v6.9.8 [SD-05]: lot_no 없는 스캔 명확 에러 분리
                    # UID 형식: LOT-NNN (예: 1125072147-001)
                    # '-'로 split 시 lot 부분 없으면 SD-05
                    _code_parts = code.split('-')
                    _has_lot = len(_code_parts) >= 2 and _code_parts[0].isdigit()
                    if not _has_lot:
                        logger.warning(
                            f"[SD-05][INVALID_UID] lot_no 식별 불가 UID: '{code}' "
                            f"— 바코드 형식 확인 (예: 1125072147-001)"
                        )
                    else:
                        logger.warning(f"[SD-05] AVAILABLE 재고 없음: '{code}'")
                    not_found.append(code)
                    continue

                lot_no = row.get('lot_no', '')
                tb_id  = row['id']
                tb_weight = row.get('weight') or 0

                # v6.9.4 [WRONG_LOT_SCAN]: 오스캔 HARD-STOP
                # 현재 출고 중인 LOT과 스캔된 tonbag의 LOT이 다르면 즉시 차단
                if target_lot_no and lot_no != str(target_lot_no).strip():
                    return {
                        'success': False,
                        'sold': 0,
                        'not_found': [],
                        'no_plan': [],
                        'duplicates': [],
                        'wrong_lot': [{
                            'scanned_uid': code,
                            'scanned_lot': lot_no,
                            'target_lot': target_lot_no,
                        }],
                        'errors': [
                            f"[WRONG_LOT_SCAN] 오스캔 차단: "
                            f"스캔={code} (LOT {lot_no}) ≠ "
                            f"현재 출고 LOT {target_lot_no} "
                            f"— 올바른 화물을 스캔하세요"
                        ],
                    }

                plan = self.db.fetchone(
                    "SELECT id, customer, sale_ref, export_type, outbound_date "
                    "FROM allocation_plan "
                    "WHERE status='RESERVED' AND tonbag_id IS NULL AND lot_no=? "
                    "ORDER BY id ASC LIMIT 1",
                    (lot_no,),
                )
                if not plan:
                    no_plan.append(code)
                    continue

                plan_id     = plan['id']
                customer    = plan.get('customer', '')
                sale_ref    = plan.get('sale_ref', '')
                export_type = str(plan.get('export_type') or '').strip()   # v6.3.4 RUBI

                # v6.9.7 [SD-08]: 출고 스캔 시 location mismatch WARNING
                # 스캔된 톤백의 location과 inventory(LOT)의 warehouse 비교
                # inventory_tonbag에는 warehouse 컬럼 없음 → location 기준 체크
                _tb_loc = str(row.get('location') or '').strip()
                _inv_row = self.db.fetchone(
                    "SELECT warehouse, location FROM inventory WHERE lot_no=?", (lot_no,)
                )
                _inv_loc = str(_inv_row.get('location') or '') if _inv_row else ''
                if _tb_loc and _inv_loc and _tb_loc != _inv_loc:
                    _sd08_warn = (
                        f"[SD-08] 위치 불일치 경고: "
                        f"스캔 UID={code} location='{_tb_loc}' ≠ "
                        f"LOT {lot_no} location='{_inv_loc}' "
                        f"— 화물 위치 확인 필요"
                    )
                    logger.warning(_sd08_warn)
                    sd08_warnings.append(_sd08_warn)

                # v6.9.8 [PK-08]: double pick 차단 — 이미 PICKED 상태 재스캔
                if str(row.get('status','')) == 'PICKED':
                    _pk08_err = (
                        f"[PK-08][DOUBLE_PICK] 이중 피킹 차단: "
                        f"UID={code} LOT {lot_no} sub_lt={row.get('sub_lt','?')} "
                        f"이미 PICKED 상태 — 동일 화물 중복 스캔 불가"
                    )
                    logger.error(_pk08_err)
                    duplicates.append(code)
                    continue

                # v6.9.8 [SD-03]: sale_ref mismatch 스캔 차단
                # allocation_plan의 sale_ref와 기존 tonbag.sale_ref가 다르면 경고
                _plan_sale_ref = str(plan.get('sale_ref') or '').strip()
                _tb_sale_ref   = str(row.get('sale_ref') or '').strip()
                if _plan_sale_ref and _tb_sale_ref and _plan_sale_ref != _tb_sale_ref:
                    _sd03_warn = (
                        f"[SD-03] sale_ref 불일치 경고: "
                        f"UID={code} tonbag.sale_ref='{_tb_sale_ref}' ≠ "
                        f"plan.sale_ref='{_plan_sale_ref}' "
                        f"— 화물/출고 계획 확인 필요"
                    )
                    logger.warning(_sd03_warn)
                    sd08_warnings.append(_sd03_warn)  # sd08_warnings 재사용 (scan warnings)

                # v6.9.8 [SD-09]: outbound_date 만료 스캔 차단
                # allocation_plan.outbound_date가 오늘보다 이전이면 경고
                _plan_out_date = str(plan.get('outbound_date') or '').strip()
                if _plan_out_date:
                    try:
                        from datetime import date as _date_cls, datetime as _dt_cls
                        _out_d = _dt_cls.strptime(_plan_out_date[:10], '%Y-%m-%d').date()
                        _today = _date_cls.today()
                        if _out_d < _today:
                            _sd09_warn = (
                                f"[SD-09] 출고예정일 만료 경고: "
                                f"UID={code} plan outbound_date={_plan_out_date} "
                                f"(오늘 {_today} 기준 {(_today-_out_d).days}일 초과) "
                                f"— 출고 계획 재확인 필요"
                            )
                            logger.warning(_sd09_warn)
                            sd08_warnings.append(_sd09_warn)
                    except (ValueError, TypeError):
                        logger.debug("[SUPPRESSED] exception in barcode_scan_engine.py")  # noqa

                # ── STEP 1: RESERVED → PICKED ─────────────────────────
                self.db.execute(
                    "UPDATE inventory_tonbag "
                    "SET status='PICKED', picked_date=?, updated_at=? WHERE id=?",
                    (now, now, tb_id),
                )
                # allocation_plan: tonbag_id 확정 (tonbag_id IS NULL 해소)
                self.db.execute(
                    "UPDATE allocation_plan SET tonbag_id=?, sub_lt=? WHERE id=?",
                    (tb_id, row.get('sub_lt'), plan_id),
                )
                try:
                    self.db.execute(
                        "INSERT INTO picking_table "
                        "(lot_no, tonbag_id, sub_lt, tonbag_uid, customer, qty_kg, "
                        " status, picking_date, created_by, remark) "
                        "VALUES (?,?,?,?,?,?,'ACTIVE',?,'barcode_lot_mode',?)",
                        (
                            lot_no, tb_id, row.get('sub_lt', 0),
                            row.get('tonbag_uid') or code,
                            customer, tb_weight, now,
                            f"lot_mode plan_id={plan_id} export_type={export_type}",
                        ),
                    )
                except Exception as e:
                    logger.debug(f"picking_table insert skipped (lot_mode): {e}")

                # ── STEP 2: PICKED → SOLD ──────────────────────────────
                self.db.execute(
                    "UPDATE inventory_tonbag "
                    "SET status='OUTBOUND', outbound_date=?, picked_to=?, sale_ref=?, updated_at=? WHERE id=?",
                    (now, customer, sale_ref, now, tb_id),
                )
                self.db.execute(
                    "UPDATE allocation_plan SET status='EXECUTED', executed_at=? WHERE id=?",
                    (now, plan_id),
                )
                try:
                    self.db.execute(
                        "INSERT INTO sold_table "
                        "(lot_no, tonbag_id, sub_lt, tonbag_uid, sold_qty_kg, sold_date, status, created_by) "
                        "VALUES (?,?,?,?,?,?,'OUTBOUND','barcode_lot_mode')",
                        (
                            lot_no, tb_id,
                            row.get('sub_lt', 0),
                            row.get('tonbag_uid') or code,
                            tb_weight, now,
                        ),
                    )
                except Exception as e:
                    logger.debug(f"sold_table insert skipped in lot_mode scan: {e}")

                self.db.execute(
                    "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                    "VALUES (?,'SOLD',?,?,?)",
                    (
                        lot_no, tb_weight,
                        f"barcode_lot_mode uid={code}, plan_id={plan_id}, export_type={export_type}",
                        now,
                    ),
                )

                # v6.3.4 RUBI: 반송 건 수집
                if export_type == '반송' and lot_no not in bangsong_lots:
                    bangsong_lots.append(lot_no)

                sold_count += 1

            # v7.9.9 [C-3]: STEP2 후 inventory.current_weight + LOT status 재계산
            # 기존: inventory_tonbag만 OUTBOUND로 변경 → inventory.current_weight 미갱신
            # 수정: 스캔된 LOT들 일괄 재계산 (트랜잭션 밖에서 처리)
            processed_lots = list({r.get('lot_no') for r in [
                self.db.fetchone(
                    "SELECT lot_no FROM inventory_tonbag WHERE (tonbag_uid=? OR CAST(sub_lt AS TEXT)=?)",
                    (code, code)
                ) for code in uniq_codes
            ] if r})
            for _lot in processed_lots:
                self._recalc_inventory_lot_weights(_lot, now=now, reason='P2_SCAN_BATCH')
            try:
                self.db.conn.commit()
            except Exception:
                logger.debug("[SUPPRESSED] exception in barcode_scan_engine.py")  # noqa

        return {
            'success': sold_count > 0,
            'sold': sold_count,
            'not_found': not_found,
            'no_plan': no_plan,
            'duplicates': sorted(set(duplicates)),
            'remaining_lot_reserved': self.get_lot_mode_reserved_count(),
            'bangsong_lots': bangsong_lots,   # v6.3.4 RUBI: 반송 LOT 목록
            'sd08_warnings': sd08_warnings,  # v6.9.7 [SD-08]
        }


        """
        LOT 단위 예약 모드 전용 스캔 처리.
        - allocation_plan(RESERVED, tonbag_id IS NULL)의 LOT 계획 1건을 스캔 UID 1건과 매칭
        - 매칭된 톤백은 SOLD 전환
        """


    def process_barcode_scan_to_sold(self, scanned_codes_or_file, sale_ref: str = None) -> Dict:
        scanned_codes = (
            self.read_scan_file(scanned_codes_or_file)
            if isinstance(scanned_codes_or_file, str)
            else list(scanned_codes_or_file or [])
        )
        # 중복 스캔은 하드스톱
        seen = set()
        duplicates = []
        uniq_codes = []
        for code in scanned_codes:
            c = str(code).strip()
            if not c:
                continue
            if c in seen:
                duplicates.append(c)
            else:
                seen.add(c)
                uniq_codes.append(c)
        dup_set = sorted(set(duplicates))

        sold_count, not_found, swap_count = 0, [], 0
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        scanned_set = set(uniq_codes)

        with self.db.transaction("IMMEDIATE"):
            for code in uniq_codes:
                code = code.strip()
                if not code: continue
                row = self.db.fetchone(
                    "SELECT id, lot_no, sub_lt, weight, tonbag_uid FROM inventory_tonbag "
                    "WHERE (tonbag_uid = ? OR CAST(sub_lt AS TEXT) = ? OR CAST(sub_lt AS TEXT) = ?) "
                    "AND status = 'PICKED' "
                    + ("AND sale_ref = ?" if sale_ref else ""),
                    ((code, code, _normalize_sublt(code), sale_ref) if sale_ref else (code, code, _normalize_sublt(code))))
                if row:
                    self.db.execute(
                        "UPDATE inventory_tonbag SET status='OUTBOUND', outbound_date=?, updated_at=? "
                        "WHERE id=? AND status='PICKED'",
                        (now, now, row['id'])
                    )
                    try:
                        self.db.execute(
                            "INSERT INTO sold_table (lot_no, tonbag_id, sub_lt, tonbag_uid, sold_qty_kg, sold_date, status, created_by) VALUES (?,?,?,?,?,?,'SOLD','barcode_scan')",
                            (row['lot_no'], row['id'], row['sub_lt'], row.get('tonbag_uid') or '', row.get('weight') or 0, now))
                    except Exception as e:
                        logger.debug(f"sold_table insert skipped in barcode scan: {e}")
                    try:
                        self.db.execute("UPDATE picking_table SET status='SOLD', sold_date=? WHERE tonbag_id=? AND status='ACTIVE'", (now, row['id']))
                    except Exception as e:
                        logger.debug(f"picking_table status update skipped in barcode scan: {e}")
                    self.db.execute(
                        "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) VALUES (?,'SOLD',?,?,?)",
                        (row['lot_no'], row.get('weight') or 0, f"barcode_scan uid={code}", now))
                    sold_count += 1
                else:
                    scanned_row = self.db.fetchone(
                        "SELECT id, lot_no, sub_lt, weight, tonbag_uid, picked_to, sale_ref, status "
                        "FROM inventory_tonbag "
                        "WHERE (tonbag_uid = ? OR CAST(sub_lt AS TEXT) = ? OR CAST(sub_lt AS TEXT) = ?) "
                        "AND status IN ('AVAILABLE','RESERVED')",
                        (code, code, _normalize_sublt(code)),
                    )
                    if not scanned_row:
                        not_found.append(code)
                        continue

                    lot_no = scanned_row.get('lot_no', '')
                    picked_row = self.db.fetchone(
                        "SELECT id, lot_no, sub_lt, weight, tonbag_uid, picked_to, sale_ref "
                        "FROM inventory_tonbag "
                        "WHERE lot_no = ? AND status = 'PICKED' "
                        + ("AND sale_ref = ? " if sale_ref else "")
                        + "AND COALESCE(tonbag_uid,'') <> '' AND tonbag_uid NOT IN ({}) "
                        "ORDER BY sub_lt ASC LIMIT 1".format(",".join("?" * len(scanned_set))),
                        ((lot_no, sale_ref, *tuple(scanned_set)) if sale_ref and scanned_set else
                         (lot_no, sale_ref) if sale_ref and not scanned_set else
                         (lot_no, *tuple(scanned_set))),
                    ) if scanned_set else self.db.fetchone(
                        "SELECT id, lot_no, sub_lt, weight, tonbag_uid, picked_to, sale_ref "
                        "FROM inventory_tonbag WHERE lot_no = ? AND status = 'PICKED' "
                        + ("AND sale_ref = ? " if sale_ref else "")
                        + "ORDER BY sub_lt ASC LIMIT 1",
                        ((lot_no, sale_ref) if sale_ref else (lot_no,)),
                    )

                    if not picked_row:
                        not_found.append(code)
                        continue

                    # LOT 내부 swap: 기존 PICKED는 RESERVED로 복귀, 실제 스캔 톤백은 SOLD 처리
                    self.db.execute(
                        "UPDATE inventory_tonbag SET status='RESERVED', picked_date=NULL, outbound_date=NULL, updated_at=? "
                        "WHERE id=?",
                        (now, picked_row['id']),
                    )
                    self.db.execute(
                        "UPDATE inventory_tonbag SET status='OUTBOUND', outbound_date=?, picked_to=?, sale_ref=?, updated_at=? "
                        "WHERE id=?",
                        (now, picked_row.get('picked_to', ''), picked_row.get('sale_ref', ''), now, scanned_row['id']),
                    )
                    self.db.execute(
                        "INSERT INTO uid_swap_history "
                        "(lot_no, expected_tonbag_id, expected_uid, scanned_tonbag_id, scanned_uid, reason, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            lot_no,
                            picked_row.get('id'),
                            picked_row.get('tonbag_uid', ''),
                            scanned_row.get('id'),
                            scanned_row.get('tonbag_uid', '') or code,
                            'PASS_SWAP lot_internal',
                            now,
                        ),
                    )
                    try:
                        self.db.execute(
                            "INSERT INTO sold_table "
                            "(lot_no, tonbag_id, sub_lt, tonbag_uid, sold_qty_kg, sold_date, status, created_by) "
                            "VALUES (?,?,?,?,?,?,'SOLD','barcode_scan_swap')",
                            (
                                lot_no, scanned_row['id'], scanned_row.get('sub_lt', 0),
                                scanned_row.get('tonbag_uid') or code, scanned_row.get('weight') or 0, now
                            ),
                        )
                    except Exception as e:
                        logger.debug(f"sold_table insert skipped in barcode swap: {e}")
                    self.db.execute(
                        "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                        "VALUES (?,'SOLD',?,?,?)",
                        (
                            lot_no,
                            scanned_row.get('weight') or 0,
                            f"barcode_scan PASS_SWAP scanned={code}, expected_uid={picked_row.get('tonbag_uid','')}",
                            now,
                        ),
                    )
                    sold_count += 1
                    swap_count += 1

        remaining_query = "SELECT COUNT(*) AS cnt FROM inventory_tonbag WHERE status='PICKED'"
        remaining_params = ()
        if sale_ref:
            remaining_query += " AND sale_ref = ?"
            remaining_params = (sale_ref,)
        remaining = self.db.fetchone(remaining_query, remaining_params)
        remaining_cnt = (remaining['cnt'] if isinstance(remaining, dict) else remaining[0]) if remaining else 0

        return {
            'success': True,
            'sold': sold_count,
            'swap_count': swap_count,
            'not_found': not_found,
            'duplicates': dup_set,
            'remaining_picked': remaining_cnt,
        }

    def process_barcode_scan_to_sold_from_file(self, file_path: str, sale_ref: str = None) -> Dict:
        """레거시 호환용: 파일 경로 기반 호출."""
        return self.process_barcode_scan_to_sold(file_path, sale_ref=sale_ref)

    def get_picked_full_info(self, sale_ref: str = None) -> List[Dict]:
        """PICKED 톤백 상세 정보 반환 (검증 미리보기용)."""
        query = (
            "SELECT id, lot_no, sub_lt, weight, tonbag_uid, sale_ref, "
            "picked_to, picked_date, location "
            "FROM inventory_tonbag WHERE status='PICKED'"
        )
        params = []
        if sale_ref:
            query += " AND sale_ref = ?"
            params.append(sale_ref)
        query += " ORDER BY lot_no, sub_lt"
        try:
            return self.db.fetchall(query, tuple(params)) or []
        except Exception:
            return []

    def get_verify_history(self, limit: int = 50) -> List[Dict]:
        try:
            return self.db.fetchall("SELECT * FROM uid_verify_history ORDER BY verified_at DESC LIMIT ?", (limit,))
        except Exception:
            return []
