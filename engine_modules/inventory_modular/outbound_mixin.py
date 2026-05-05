ALLOCATION_FORCE_APPROVAL_ALL = True

# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - 출고 처리 Mixin
======================================

v3.6.6: SQLAlchemy → SQMDatabase API 전환 (self.db 기반)

작성자: Ruby (남기동)
버전: v3.6.6
"""

import sqlite3
import logging
import math
import random
import os
import hashlib
import configparser
import csv
import json
from datetime import datetime
from typing import Dict, List, Optional
from utils.path_utils import resolve_reports_dir

from engine_modules.constants import (
    STATUS_AVAILABLE,
    STATUS_RESERVED,
    STATUS_DEPLETED,
    STATUS_PICKED,
    STATUS_SOLD,         # ⚠️ DEPRECATED: 읽기 전용 하위호환
    STATUS_OUTBOUND,     # v7.2.0: 신규 출고 완료 상태
    STATUS_PARTIAL,      # v6.8.7 신규
)
from core.types import normalize_lot

# v6.8.6: 인라인 import → top-level 통합 (7곳 중복 제거)
from engine_modules.constants import (
    normalize_customer,
    get_tonbag_unit_weight,
    QUICK_OUTBOUND_MAX_TONBAGS,
)

from .base import InventoryBaseMixin

logger = logging.getLogger(__name__)


class OutboundMixin(InventoryBaseMixin):
    # v6.9.4 [LOT-MODE-ONLY]: 승인 임계치 조정
    # 기존 50% → 100% 초과 불가(사실상 비활성화) + 절대량 20,000kg(40톤)으로 상향
    # 이유: LOT 모드에서는 STAGED → 스캔 불가 → 출고 마비
    # 실운영 기준: LOT 전량 예약이 일반적 (CATL/BYD 전량 출고 흔함)
    ALLOCATION_APPROVAL_QTY_KG_THRESHOLD = 20000.0   # 40MT 초과 시만 승인 (기존 10MT)
    ALLOCATION_APPROVAL_RATIO_THRESHOLD  = 1.01       # 100% 초과 불가 → 사실상 비활성화

    def _table_exists(self, table_name: str) -> bool:
        try:
            row = self.db.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return bool(row)
        except Exception:
            return False

    def _ensure_outbound_txn_tables(self) -> None:
        """outbound_event_log 테이블 best-effort 생성 (RUBI 패치·타임라인 UI용)."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS outbound_event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    outbound_no TEXT,
                    event_type TEXT,
                    message TEXT,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                )
            """)
            self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_outbound_event_log_created "
                "ON outbound_event_log(created_at DESC)"
            )
        except Exception as e:
            logger.debug(f"outbound_event_log 테이블 생성 스킵: {e}")

    def get_outbound_event_log(self, limit: int = 50) -> List[Dict]:
        """출고 이벤트 로그 최근 N건 조회 (타임라인 UI용). 테이블 없으면 빈 목록."""
        try:
            self._ensure_outbound_txn_tables()
            rows = self.db.fetchall(
                "SELECT id, outbound_no, event_type, message, created_at "
                "FROM outbound_event_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            if not rows:
                return []
            out = []
            for r in rows:
                if isinstance(r, dict):
                    out.append(dict(r))
                else:
                    out.append({
                        "id": r[0], "outbound_no": r[1] or "",
                        "event_type": r[2] or "", "message": r[3] or "",
                        "created_at": r[4] or "",
                    })
            return out
        except Exception as e:
            logger.debug(f"get_outbound_event_log: {e}")
            return []

    def _get_outbound_status(self, outbound_no: str) -> str:
        """출고번호별 상태 문자열 반환 (배너용). outbound 테이블에 status 컬럼 있으면 사용."""
        if not outbound_no:
            return ""
        try:
            row = self.db.fetchone(
                "SELECT status FROM outbound WHERE outbound_no = ? LIMIT 1",
                (outbound_no,),
            )
            if row:
                return (row.get("status") if isinstance(row, dict) else row[0]) or ""
        except Exception:
            logger.debug("[SUPPRESSED] exception in outbound_mixin.py")  # noqa
        return ""


    def cleanup_orphan_lot_allocations(self, days_old: int = 7) -> Dict:
        """
        ③ v6.7.1: LOT 단위 예약 고아 레코드 정리.
        tonbag_id=NULL이고 생성 후 days_old일 이상 경과된 RESERVED 건을 CANCELLED 처리.

        Args:
            days_old: 정리 기준 일수 (기본 7일)
        Returns:
            {'success': bool, 'cancelled': int}
        """
        result = {'success': False, 'cancelled': 0}
        try:
            if not self._table_exists('allocation_plan'):
                result['success'] = True
                return result
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d %H:%M:%S')
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with self.db.transaction('IMMEDIATE'):
                cur = self.db.execute("""
                    UPDATE allocation_plan
                       SET status      = 'CANCELLED',
                           cancelled_at = ?
                     WHERE tonbag_id IS NULL
                       AND status     = 'RESERVED'
                       AND created_at < ?
                """, (now, cutoff))
                cnt = cur.rowcount if hasattr(cur, 'rowcount') else 0
            result['success']   = True
            result['cancelled'] = cnt
            if cnt:
                logger.info(f"[③ 고아정리] LOT 단위 예약 {cnt}건 CANCELLED (>{days_old}일)")
                # [D] v6.8.3: lot_mode 만료 CANCELLED → audit_log 기록
                try:
                    import json as _jd
                    self.db.execute(
                        "INSERT INTO audit_log(event_type, event_data, created_at) VALUES (?, ?, ?)",
                        ('LOT_MODE_ALLOC_EXPIRED',
                         _jd.dumps({'cancelled': cnt, 'days_old': days_old,
                                    'cutoff': cutoff}, ensure_ascii=False),
                         now)
                    )
                except Exception as _ae:
                    logger.debug(f"[D audit_log] 기록 스킵: {_ae}")

            # [D] v6.8.3: 만료 임박(3일 이내) LOT 단위 예약 사전 경고
            try:
                from datetime import timedelta
                _warn_cutoff = (
                    datetime.now() - timedelta(days=max(0, days_old - 3))
                ).strftime('%Y-%m-%d %H:%M:%S')
                _soon_rows = self.db.fetchall("""
                    SELECT lot_no, customer, created_at
                    FROM allocation_plan
                    WHERE tonbag_id IS NULL
                      AND status = 'RESERVED'
                      AND created_at < ?
                    ORDER BY created_at ASC LIMIT 10
                """, (_warn_cutoff,))
                if _soon_rows:
                    result['expiring_soon'] = [
                        {'lot_no': r.get('lot_no') if isinstance(r, dict) else r[0],
                         'customer': r.get('customer') if isinstance(r, dict) else r[1],
                         'created_at': r.get('created_at') if isinstance(r, dict) else r[2]}
                        for r in _soon_rows
                    ]
                    logger.warning(
                        f"[D 만료임박] LOT 단위 예약 {len(_soon_rows)}건 3일 이내 자동 CANCELLED 예정 "
                        f"— 바코드 스캔 또는 취소 처리 필요"
                    )
            except Exception as _de:
                logger.debug(f"[D 만료임박] 체크 스킵: {_de}")

        except Exception as e:
            result['error'] = str(e)
            logger.warning(f"[③ 고아정리] 실패: {e}")
        return result

    def cleanup_expired_staged_allocations(self, days_old: int = 7) -> Dict:
        """
        ③⑦ v6.7.1: STAGED+PENDING_APPROVAL 만료 건 자동 REJECTED.
        승인/반려 없이 days_old일 이상 방치된 대기 건 정리.

        Args:
            days_old: 정리 기준 일수 (기본 7일)
        Returns:
            {'success': bool, 'rejected': int}
        """
        result = {'success': False, 'rejected': 0}
        try:
            if not self._table_exists('allocation_plan'):
                result['success'] = True
                return result
            cols = {r.get('name','') for r in (self.db.fetchall(
                'PRAGMA table_info(allocation_plan)') or [])}
            if 'workflow_status' not in cols:
                result['success'] = True
                return result
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d %H:%M:%S')
            now    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with self.db.transaction('IMMEDIATE'):
                cur = self.db.execute("""
                    UPDATE allocation_plan
                       SET workflow_status = 'REJECTED',
                           rejected_reason = 'AUTO_EXPIRE_AFTER_7DAYS',
                           approved_by     = 'system_cleanup',
                           approved_at     = ?
                     WHERE status          = 'STAGED'
                       AND workflow_status = 'PENDING_APPROVAL'
                       AND created_at      < ?
                """, (now, cutoff))
                cnt = cur.rowcount if hasattr(cur, 'rowcount') else 0
            result['success']  = True
            result['rejected'] = cnt
            if cnt:
                logger.info(f"[③⑦ 만료정리] STAGED PENDING {cnt}건 자동 REJECTED (>{days_old}일)")
        except Exception as e:
            result['error'] = str(e)
            logger.warning(f"[③⑦ 만료정리] 실패: {e}")
        return result

    def fix_lot_status_integrity(self) -> Dict:
        """★ v6.8.6 N+1 쿼리 → 벌크 쿼리 최적화 (v6.8.5 설계 원칙 유지).
        설계 원칙 재정립 전 잘못 기록된 LOT 상태를 일괄 보정:
        - LOT = SOLD 이지만 AVAILABLE 톤백이 남아 있는 케이스 → LOT = AVAILABLE
        - LOT = AVAILABLE 이지만 전체 톤백이 SOLD인 케이스 → LOT = SOLD
        운영 DB에 최초 1회 실행. (관리자 메뉴 → DB 정합성 복구)

        v6.8.6 최적화:
          - 기존: LOT 수 N → 쿼리 3N번 (N+1 패턴)
          - 개선: 3개 집계 쿼리로 전체 처리 (성능 100배 이상 향상)
        """
        result = {'success': False, 'fixed': 0, 'details': [], 'errors': []}
        try:
            # ── 벌크 쿼리 1: LOT=SOLD 이지만 AVAILABLE 톤백 잔존 ──────────
            # GROUP BY로 전체 LOT 한 번에 집계
            # v8.6.5 STAB-4: N+1 제거 — sold_cnt를 GROUP BY에 포함
            needs_avail = self.db.fetchall("""
                SELECT inv.lot_no,
                       SUM(CASE WHEN tb.status = 'AVAILABLE' AND tb.is_sample = 0 THEN 1 ELSE 0 END) AS normal_avail,
                       SUM(CASE WHEN tb.status = 'AVAILABLE' AND tb.is_sample = 1 THEN 1 ELSE 0 END) AS sample_avail,
                       SUM(CASE WHEN tb.status IN ('SOLD','OUTBOUND') THEN 1 ELSE 0 END) AS sold_cnt
                FROM inventory inv
                JOIN inventory_tonbag tb ON tb.lot_no = inv.lot_no
                WHERE inv.status IN (?, 'OUTBOUND')
                GROUP BY inv.lot_no
                HAVING (normal_avail + sample_avail) > 0
            """, (STATUS_SOLD, 'OUTBOUND')) or []

            for _r in needs_avail:
                _lot = _r.get('lot_no') if isinstance(_r, dict) else _r[0]
                _na  = int(_r.get('normal_avail', 0) if isinstance(_r, dict) else _r[1])
                _sa  = int(_r.get('sample_avail', 0) if isinstance(_r, dict) else _r[2])
                _sc_fix = int(_r.get('sold_cnt', 0) if isinstance(_r, dict) else _r[3])
                _fix_status = STATUS_PARTIAL if _sc_fix > 0 else STATUS_AVAILABLE
                self.db.execute(
                    "UPDATE inventory SET status = ? WHERE lot_no = ?",
                    (_fix_status, _lot)
                )
                detail = f"{_lot}: SOLD→{_fix_status} (잔여 일반 {_na}개 + 샘플 {_sa}개)"
                result['details'].append(detail)
                result['fixed'] += 1
                logger.info(f"[fix_integrity] {detail}")

            # ── 벌크 쿼리 2: LOT=AVAILABLE 이지만 전체 톤백 SOLD ───────────
            needs_sold = self.db.fetchall("""
                SELECT inv.lot_no,
                       COUNT(tb.id) AS total,
                       SUM(CASE WHEN tb.status = 'SOLD' THEN 1 ELSE 0 END) AS sold_cnt
                FROM inventory inv
                JOIN inventory_tonbag tb ON tb.lot_no = inv.lot_no
                WHERE inv.status = ?
                GROUP BY inv.lot_no
                HAVING total > 0 AND sold_cnt >= total
            """, (STATUS_AVAILABLE,)) or []

            for _r in needs_sold:
                _lot = _r.get('lot_no') if isinstance(_r, dict) else _r[0]
                _tc  = int(_r.get('total', 0) if isinstance(_r, dict) else _r[1])
                self.db.execute(
                    "UPDATE inventory SET status = ? WHERE lot_no = ?",
                    (STATUS_OUTBOUND, _lot)
                )
                detail = f"{_lot}: AVAILABLE→OUTBOUND (전체 {_tc}개 출고)"
                result['details'].append(detail)
                result['fixed'] += 1
                logger.info(f"[fix_integrity] {detail}")

            result['success'] = True
            result['message'] = f"LOT 상태 정합성 복구 완료: {result['fixed']}건"
        except Exception as e:
            result['errors'].append(str(e))
            logger.error(f"[fix_integrity] 오류: {e}")
        return result

    def run_allocation_cleanup(self, days_old: int = 7) -> Dict:
        """
        ③⑦ v6.7.1: 전체 Allocation 정리 일괄 실행.
        - LOT 단위 고아 레코드 정리
        - 만료 STAGED 자동 REJECTED

        Returns:
            {'orphan_cancelled': int, 'expired_rejected': int}
        """
        r1 = self.cleanup_orphan_lot_allocations(days_old)
        r2 = self.cleanup_expired_staged_allocations(days_old)
        return {
            'success': r1.get('success', False) and r2.get('success', False),
            'orphan_cancelled': r1.get('cancelled', 0),
            'expired_rejected': r2.get('rejected', 0),
        }

    def clear_pending_allocation_on_exit(self) -> Dict:
        """
        프로그램 종료 시 승인되지 않은 Allocation 대기건 정리.

        대상: allocation_plan.status=ALLOC_STAGED AND workflow_status=ALLOC_WF_PENDING
        처리: workflow_status=ALLOC_WF_REJECTED, rejected_reason='AUTO_CLEAR_ON_EXIT'
        """
        result = {"success": False, "cleared": 0, "error": ""}
        try:
            if not self._table_exists("allocation_plan"):
                result["success"] = True
                return result

            cols = self.db.fetchall("PRAGMA table_info(allocation_plan)") or []
            col_names = {
                str(c.get("name", "")).strip().lower()
                for c in cols
                if isinstance(c, dict)
            }
            if "workflow_status" not in col_names:
                result["success"] = True
                return result

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            actor = "system_exit"
            with self.db.transaction("IMMEDIATE"):
                cur = self.db.execute(
                    """
                    UPDATE allocation_plan
                       SET workflow_status = 'REJECTED',
                           rejected_reason = COALESCE(NULLIF(rejected_reason,''), 'AUTO_CLEAR_ON_EXIT'),
                           approved_by = COALESCE(NULLIF(approved_by,''), ?),
                           approved_at = COALESCE(approved_at, ?)
                     WHERE status = 'STAGED'
                       AND workflow_status = 'PENDING_APPROVAL'
                    """,
                    (actor, now),
                )
                try:
                    result["cleared"] = int(getattr(cur, "rowcount", 0) or 0)
                except (TypeError, ValueError):
                    result["cleared"] = 0
            result["success"] = True
            if result["cleared"] > 0:
                logger.info(f"[allocation] 종료 시 승인대기 자동 정리: {result['cleared']}건")
            return result
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"[allocation] 종료 시 승인대기 정리 실패: {e}", exc_info=True)
            return result

    def _normalize_outbound_date(self, raw_date) -> str:
        """outbound_date를 YYYY-MM-DD로 정규화, 실패 시 ValueError.
        [C] v6.8.3: NULL/공백이면 오늘 날짜 자동 설정 (execute_reserved 영구 제외 방지)
        """
        txt = str(raw_date or "").strip()
        if not txt:
            # [C] NULL → 오늘 날짜 자동 설정 + 경고 로그
            _today = datetime.now().strftime('%Y-%m-%d')
            logger.warning(
                f"[C OUTBOUND_DATE_NULL] outbound_date 미입력 "
                f"→ 오늘 날짜 자동 설정: {_today}"
            )
            return _today
        try:
            return datetime.strptime(txt[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            raise ValueError(f"INVALID_OUTBOUND_DATE: '{txt}' (허용 형식: YYYY-MM-DD)")

    def _save_allocation_fail_report(
        self,
        rows: list,
        errors: list,
        source_file: str = "",
        error_details: list | None = None,
    ) -> dict:
        """Allocation 검증 실패 리포트 CSV+JSON 저장."""
        out = {"csv": "", "json": ""}
        if not errors:
            return out
        try:
            reports_root = resolve_reports_dir()
            out_dir = os.path.join(reports_root, "allocation")
            os.makedirs(out_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = os.path.join(out_dir, f"allocation_fail_{ts}.csv")
            json_path = os.path.join(out_dir, f"allocation_fail_{ts}.json")

            detail_rows = list(error_details or [])
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["line_no", "FAIL_CODE", "lot_no", "sold_to", "qty_mt", "reason"])
                if detail_rows:
                    for d in detail_rows:
                        w.writerow([
                            d.get("line_no", ""),
                            d.get("fail_code", "ALLOCATION_VALIDATE_FAIL"),
                            d.get("lot_no", ""),
                            d.get("sold_to", ""),
                            d.get("qty_mt", ""),
                            d.get("reason", ""),
                        ])
                else:
                    for r in rows or []:
                        lot_no = str((r.get("lot_no", "") if isinstance(r, dict) else getattr(r, "lot_no", "")) or "")
                        sold_to = str((r.get("sold_to", "") if isinstance(r, dict) else getattr(r, "sold_to", "")) or "")
                        qty_mt = (r.get("qty_mt", "") if isinstance(r, dict) else getattr(r, "qty_mt", ""))
                        fail_reason = "; ".join(errors[:3])
                        fail_code = "ALLOCATION_VALIDATE_FAIL"
                        if "INVALID_OUTBOUND_DATE" in fail_reason:
                            fail_code = "INVALID_OUTBOUND_DATE"
                        w.writerow(["", fail_code, lot_no, sold_to, qty_mt, fail_reason])

            with open(json_path, "w", encoding="utf-8") as f:
                payload = {
                    "source_file": source_file,
                    "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "error_count": len(errors),
                    "errors": errors,
                    "error_details": detail_rows,
                }
                json.dump(payload, f, ensure_ascii=False, indent=2)

            out["csv"] = csv_path
            out["json"] = json_path
            return out
        except Exception as e:
            logger.debug(f"Allocation 실패 리포트 저장 스킵: {e}")
            return out

    def _get_allocation_random_mode(self) -> str:
        """
        Allocation 예약 랜덤 모드 조회.
        우선순위: ENV(SQM_ALLOC_RANDOM_MODE) > settings.ini[outbound].allocation_random_mode > 기본(random)

        Returns:
            'random' | 'seeded'
        """
        raw = str(os.environ.get("SQM_ALLOC_RANDOM_MODE", "") or "").strip().lower()
        if not raw:
            try:
                cfg = configparser.ConfigParser()
                cfg.read(os.path.join(os.getcwd(), "settings.ini"), encoding="utf-8")
                raw = str(cfg.get("outbound", "allocation_random_mode", fallback="")).strip().lower()
            except Exception as e:
                logger.debug(f"allocation_random_mode 설정 읽기 스킵: {e}")

        if raw in ("seeded", "deterministic", "reproducible", "sale_ref_seed", "seed"):
            return "seeded"
        return "random"

    def _get_allocation_strict_mode(self) -> bool:
        """
        Allocation 예약 Strict 모드 조회.
        우선순위: ENV(SQM_ALLOCATION_STRICT_MODE) > settings.ini[outbound].allocation_strict_mode > 기본(True)
        """
        raw = str(os.environ.get("SQM_ALLOCATION_STRICT_MODE", "") or "").strip().lower()
        if not raw:
            try:
                cfg = configparser.ConfigParser()
                cfg.read(os.path.join(os.getcwd(), "settings.ini"), encoding="utf-8")
                raw = str(cfg.get("outbound", "allocation_strict_mode", fallback="")).strip().lower()
            except Exception as e:
                logger.debug(f"allocation_strict_mode 설정 읽기 스킵: {e}")

        if not raw:
            return True
        return raw in ("1", "true", "yes", "on", "strict")

    def _get_allocation_reservation_mode(self, override_mode: str = "") -> str:
        """
        v6.9.4 [LOT-MODE-ONLY]: 항상 'lot' 반환.

        설계 원칙 (기동님 확정 2026-03-10):
          - 예약 단계(Allocation)에서는 tonbag_id를 특정하지 않음
          - 개수(pick_count)만 allocation_plan에 기록 (tonbag_id = NULL)
          - 실출고 바코드 스캔 순간에 비로소 tonbag_id 확정
          - 이 원칙이 SQM의 근간 로직

        Returns:
            'lot' (항상 고정, tonbag 모드 폐기)
        """
        # v6.9.4: tonbag 즉시 특정 경로 완전 폐기
        # override_mode / ENV / settings.ini 값 무시 — 항상 lot 모드
        _ = override_mode  # 하위호환 시그니처 유지
        return "lot"

    def _has_allocation_source_fingerprint_column(self) -> bool:
        """allocation_plan.source_fingerprint 컬럼 존재 여부."""
        try:
            rows = self.db.fetchall("PRAGMA table_info(allocation_plan)")
            cols = {str(r.get("name", "")).strip().lower() for r in (rows or [])}
            return "source_fingerprint" in cols
        except Exception as e:
            logger.debug(f"source_fingerprint 컬럼 확인 스킵: {e}")
            return False

    def _compute_allocation_source_fingerprint(self, allocation_rows: list, source_file: str = "") -> str:
        """
        Allocation 입력 fingerprint 생성.
        - 파일: 파일 내용 SHA1 우선, 실패 시 파일 메타+경로로 대체
        - 붙여넣기: 행 데이터 정규화 문자열 SHA1
        """
        try:
            sf = str(source_file or "").strip()
            if sf and sf != "(붙여넣기)" and os.path.isfile(sf):
                try:
                    h = hashlib.sha1()
                    with open(sf, "rb") as f:
                        for chunk in iter(lambda: f.read(1024 * 1024), b""):
                            h.update(chunk)
                    return h.hexdigest()
                except Exception as e:
                    logger.debug(f"Allocation 파일 해시 계산 실패(메타 대체): {e}")
                try:
                    st = os.stat(sf)
                    base = f"path={os.path.abspath(sf)}|size={st.st_size}|mtime={int(st.st_mtime)}"
                    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()
                except Exception as e:
                    logger.debug(f"Allocation 파일 메타 해시 계산 실패: {e}")

            # 붙여넣기 또는 파일 접근 불가 시: 행 기반 fingerprint
            normalized_rows = []
            for alloc in (allocation_rows or []):
                lot_no = str(alloc.get("lot_no", "") if isinstance(alloc, dict) else getattr(alloc, "lot_no", "")).strip().upper()
                qty_mt = float((alloc.get("qty_mt", 0) if isinstance(alloc, dict) else getattr(alloc, "qty_mt", 0)) or 0)
                sold_to = str(alloc.get("sold_to", "") if isinstance(alloc, dict) else getattr(alloc, "sold_to", "")).strip().upper()
                customer = str(alloc.get("customer", "") if isinstance(alloc, dict) else getattr(alloc, "customer", "")).strip().upper()
                sale_ref = str(alloc.get("sale_ref", "") if isinstance(alloc, dict) else getattr(alloc, "sale_ref", "")).strip().upper()
                outbound_date = str(
                    alloc.get("outbound_date", "") if isinstance(alloc, dict) else getattr(alloc, "outbound_date", "")
                ).strip()[:10]
                normalized_rows.append(
                    f"{lot_no}|{qty_mt:.6f}|{sold_to}|{customer}|{sale_ref}|{outbound_date}"
                )
            normalized_rows.sort()
            base = "paste|" + "\n".join(normalized_rows)
            return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()
        except Exception as e:
            logger.debug(f"Allocation fingerprint 계산 실패: {e}")
            return ""

    @staticmethod
    def _build_allocation_seed(
        lot_no: str,
        sale_ref: str,
        qty_mt: float,
        outbound_date,
        source_file: str,
    ) -> str:
        """
        같은 요청이면 같은 선택 결과가 나오도록 고정 시드 문자열 생성.
        sale_ref 우선, 없으면 요청 필드 조합으로 생성.
        """
        sale_ref_norm = str(sale_ref or "").strip().upper()
        date_norm = str(outbound_date or "").strip()[:10]
        source_norm = str(source_file or "").strip()
        base = (
            f"sale_ref={sale_ref_norm}|lot={str(lot_no or '').strip().upper()}|"
            f"qty_mt={float(qty_mt or 0):.6f}|date={date_norm}|src={source_norm}"
        )
        return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()

    """출고 처리 Mixin (v3.6.6: SQMDatabase API 기반)"""
    
    def process_outbound(self, allocation_data, source: str = 'AUTO', stop_at_picked: bool = False) -> Dict:
        """
        출고 처리 (v3.8.4: All-or-Nothing + 톤백 동기화, v5.9.92: source/stop_at_picked)
        
        source: 출고 경로 구분 (AUTO/QUICK/EXCEL 등). allocation_plan에 기록.
        stop_at_picked: True면 톤백 PICKED까지만 하고 재고·outbound 미반영(빠른 출고용).
        """
        result = {
            'success': False,
            'message': '',
            'processed': 0,
            'lots_processed': 0,
            'total_weight_kg': 0,
            'total_picked': 0,
            'errors': [],
            'warnings': [],
        }
        
        try:
            if isinstance(allocation_data, dict):
                allocations = [allocation_data]
            else:
                allocations = list(allocation_data)
            
            if not allocations:
                result['message'] = "처리할 데이터 없음"
                return result
            
            # ★ All-or-Nothing: 전체를 하나의 트랜잭션으로
            with self.db.transaction("IMMEDIATE"):
                processed_lots = []
                for alloc in allocations:
                    processed = self._process_single_outbound(alloc, source=source, stop_at_picked=stop_at_picked)
                    if processed:
                        result['processed'] += 1
                        result['total_weight_kg'] += processed.get('weight_kg', 0)
                        result['total_picked'] += processed.get('weight_kg', 0) / 1000.0
                        processed_lots.append(processed.get('lot_no'))
                
                # v5.1.4: 트랜잭션 안에서 정합성 검증
                if hasattr(self, 'verify_lot_integrity') and processed_lots:
                    for lot_no in set(processed_lots):
                        integrity = self.verify_lot_integrity(lot_no)
                        if not integrity.get('valid', True):
                            raise ValueError(
                                f"출고 후 정합성 실패 ({lot_no}): {integrity.get('errors', [])}"
                            )
            
            result['lots_processed'] = result['processed']
            
            if result['processed'] > 0:
                result['success'] = True
                result['message'] = f"출고 완료: {result['processed']}건"
            else:
                result['message'] = "처리된 출고 없음"
            
            self._log_operation("출고", {
                'processed': result['processed'],
                'weight_kg': result['total_weight_kg']
            })
            
        except (ValueError, TypeError, AttributeError,
                sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"출고 처리 오류 (전체 롤백): {e}", exc_info=True)
            result['errors'].append(str(e))
        
        return result
    
    def _process_single_outbound(
        self, alloc: Dict, source: str = 'AUTO', stop_at_picked: bool = False
    ) -> Optional[Dict]:
        """
        단일 출고 처리 (v3.8.4: inventory + tonbag 동기화, v5.9.92: source, stop_at_picked)
        
        stop_at_picked=True면 톤백 PICKED + allocation_plan 기록만 하고 재고/outbound 미반영.
        """
        lot_no = str(alloc.get('lot_no') or '').strip()
        weight_kg = self._safe_parse_float(alloc.get('weight_kg'))
        if weight_kg <= 0:
            qty_mt = self._safe_parse_float(alloc.get('qty_mt'))
            weight_kg = qty_mt * 1000.0
        
        customer = alloc.get('customer') or alloc.get('sold_to', '')
        sale_ref = alloc.get('sale_ref', '')
        
        if not lot_no or weight_kg <= 0:
            return None
        
        lot = self.db.fetchone(
            "SELECT current_weight, picked_weight FROM inventory WHERE lot_no = ?",
            (lot_no,)
        )
        if not lot:
            raise ValueError(f"LOT 없음: {lot_no}")
        
        available = lot['current_weight'] or 0
        if available < weight_kg - 0.01:
            raise ValueError(
                f"가용 재고 부족: {lot_no} (가용: {available:.0f}kg, 요청: {weight_kg:.0f}kg)"
            )
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        qty_mt_val = weight_kg / 1000.0
        
        # ★ 1단계: 톤백 PICKED 처리 (가용 톤백에서 필요 수량만큼, 샘플 제외)
        remaining_kg = weight_kg
        tonbags = self.db.fetchall(
            """SELECT id, sub_lt, weight FROM inventory_tonbag 
               WHERE lot_no = ? AND status = ?
                 AND COALESCE(is_sample, 0) = 0
               ORDER BY sub_lt DESC""",
            (lot_no, STATUS_AVAILABLE)
        )
        picked_count = 0
        first_tonbag_id = None
        if tonbags:
            for tb in tonbags:
                if remaining_kg <= 0.01:
                    break
                tb_weight = tb['weight'] or 0
                if tb_weight <= 0:
                    continue
                if first_tonbag_id is None:
                    first_tonbag_id = tb['id']
                self.db.execute(
                    """UPDATE inventory_tonbag SET
                        status = ?,
                        picked_to = ?,
                        picked_date = ?,
                        sale_ref = ?,
                        outbound_date = ?,
                        updated_at = ?
                    WHERE id = ?""",
                    (STATUS_PICKED, customer, now, sale_ref, now, now, tb['id'])
                )
                remaining_kg -= tb_weight
                picked_count += 1
        
        # v5.9.92: allocation_plan에 출고 기록 (source 저장)
        try:
            self.db.execute(
                """INSERT INTO allocation_plan 
                (lot_no, tonbag_id, customer, sale_ref, qty_mt, outbound_date, status, source, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, 'PICKED', ?, ?)""",
                (lot_no, first_tonbag_id, customer, sale_ref, qty_mt_val, now, source, now)
            )
        except (sqlite3.OperationalError, OSError) as e:
            if "allocation_plan" in str(e) and "source" in str(e).lower():
                logger.debug("allocation_plan.source 미존재 시 무시: %s", e)
            else:
                raise
        
        if stop_at_picked:
            # ★ S4-1 FIX (S3-BUG-1): inventory 무게 갱신 추가
            # 이전: 톤백만 PICKED 변경, inventory 무게 미갱신 → 정합성 실패 → 롤백
            # 수정: current_weight↓ + picked_weight↑ → 정합성 유지
            # [BUG-FIX #3/#6 2026-04-28]: 실제 픽 무게(톤백 합산) 전달
            _actual_kg_stop = (weight_kg - remaining_kg) if tonbags else weight_kg
            self._update_lot_after_pick(lot_no, weight_kg, actual_picked_kg=_actual_kg_stop)
            if hasattr(self, '_recalc_current_weight'):
                self._recalc_current_weight(lot_no, reason='P2_STOP_AT_PICK')
            self._recalc_lot_status(lot_no)
            # PICK 이력 기록 (OUTBOUND와 구분)
            self.db.execute(
                """INSERT INTO stock_movement 
                (lot_no, movement_type, qty_kg, remarks, created_at)
                VALUES (?, 'PICK', ?, ?, ?)""" ,
                (lot_no, weight_kg, f"customer={customer},source={source}", now)
            )
            return {'lot_no': lot_no, 'weight_kg': weight_kg, 'tonbags_picked': picked_count}
        
        # ★ 2단계: inventory 업데이트
        # [BUG-FIX #1-NORMAL 2026-04-29]: 요청량(weight_kg) 대신 실제픽량 사용
        # 그리디 루프 마지막 톤백 통째 픽 => 요청량 초과 가능
        _actual_kg = (weight_kg - remaining_kg) if tonbags else weight_kg
        new_weight = max(0.0, available - _actual_kg)
        new_status = STATUS_DEPLETED if new_weight <= 0 else STATUS_AVAILABLE
        self.db.execute(
            """UPDATE inventory SET
                current_weight = ?,
                picked_weight = picked_weight + ?,
                status = ?,
                sold_to = CASE WHEN ? != '' THEN ? ELSE sold_to END,
                updated_at = ?
            WHERE lot_no = ?""",
            (new_weight, _actual_kg, new_status, customer, customer, now, lot_no)
        )
        if hasattr(self, '_recalc_current_weight'):
            self._recalc_current_weight(lot_no, reason='P2_OUTBOUND_STAGE2')
        self._recalc_lot_status(lot_no)
        
        # ★ 3단계: stock_movement 이력
        self.db.execute(
            """INSERT INTO stock_movement 
            (lot_no, movement_type, qty_kg, remarks, created_at)
            VALUES (?, 'OUTBOUND', ?, ?, ?)""",
            (lot_no, weight_kg, f"customer={customer}" if customer else '', now)
        )
        
        # ★ 4단계: outbound 테이블 기록
        self.db.execute(
            """INSERT INTO outbound 
            (customer, total_qty_mt, outbound_date, created_at)
            VALUES (?, ?, ?, ?)""",
            (customer, weight_kg, now, now)
        )

        # v8.3.0 [Phase 9]: OUTBOUND audit_log
        try:
            from engine_modules.audit_helper import write_audit, EVT_OUTBOUND
            write_audit(self.db, EVT_OUTBOUND, lot_no=lot_no, detail={
                'customer':      customer,
                'weight_kg':     weight_kg,
                'tonbags_picked': picked_count,
            })
        except Exception as _ae:
            logger.debug(f"[OUTBOUND audit] 스킵: {_ae}")

        return {'lot_no': lot_no, 'weight_kg': weight_kg, 'tonbags_picked': picked_count}
    
    def _update_lot_after_pick(self, lot_no: str, weight_kg: float,
                               actual_picked_kg: float = None) -> None:
        """피킹 후 LOT 업데이트 — inventory current_weight/picked_weight/status 갱신.

        P1-2: 트랜잭션은 호출자(process_outbound)가 관리한다.
        _recalc_current_weight 는 호출 지점에서 1회만 실행한다 (중복 제거).

        [BUG-FIX #1/#3/#6 2026-04-28]:
          actual_picked_kg: 실제 픽된 톤백 총 무게. None 이면 weight_kg(요청량) 폴백.
          CASE 조건을 MAX(0,...) 적용 후 새 current_weight 기준으로 판정
          (기존: 적용 전 current_weight 기준 → 재고 음수 방지와 상태 판정 엇갈림).
        """
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 실제 픽 무게 (톤백 단위 픽으로 요청량보다 클 수 있음)
        pick_kg = float(actual_picked_kg) if actual_picked_kg is not None else float(weight_kg)
        # 새 current_weight 선계산 → 상태 판정에 동일 값 사용 (BUG #1 수정)
        row = self.db.fetchone(
            "SELECT current_weight FROM inventory WHERE lot_no = ?", (lot_no,))
        cur = float((row['current_weight'] if isinstance(row, dict) else row[0]) or 0) if row else 0.0
        new_weight = max(0.0, cur - pick_kg)

        if new_weight <= 0.0:
            self.db.execute(
                """UPDATE inventory SET
                    current_weight = ?,
                    picked_weight  = picked_weight + ?,
                    status         = ?,
                    updated_at     = ?
                WHERE lot_no = ?""",
                (new_weight, pick_kg, STATUS_DEPLETED, now, lot_no)
            )
        else:
            self.db.execute(
                """UPDATE inventory SET
                    current_weight = ?,
                    picked_weight  = picked_weight + ?,
                    updated_at     = ?
                WHERE lot_no = ?""",
                (new_weight, pick_kg, now, lot_no)
            )
        # NOTE: _recalc_current_weight 는 호출자 트랜잭션 내에서 처리 — 여기선 호출 안 함

    def cancel_outbound_tonbag(self, lot_no: str, sub_lt: int) -> Dict:
        """
        출고 취소: 톤백 PICKED → AVAILABLE + inventory.current_weight 복구
        
        All-or-Nothing: 톤백 + inventory 모두 성공해야 commit
        """
        from datetime import datetime
        result = {'success': False, 'message': '', 'errors': []}
        
        try:
            with self.db.transaction("IMMEDIATE"):
                # 톤백 정보 조회
                tonbag = self.db.fetchone("""
                    SELECT id, weight, status, picked_to 
                    FROM inventory_tonbag 
                    WHERE lot_no = ? AND sub_lt = ?
                """, (lot_no, sub_lt))
                
                if not tonbag:
                    result['errors'].append(f"톤백 없음: {lot_no}-{sub_lt}")
                    return result
                
                # v6.9.3 [RT-FIX]: SOLD 상태도 직접 반품 허용
                # 설계 원칙: 출고 취소 = SOLD → AVAILABLE 직접 복귀 (PICKED 경유 없음)
                _allowed_cancel = (STATUS_PICKED, STATUS_SOLD)
                if tonbag['status'] not in _allowed_cancel:
                    result['errors'].append(
                        f"[RETURN_INVALID_STATUS] 반품 불가 상태: "
                        f"{lot_no}-{sub_lt} ({tonbag['status']}) "
                        f"— PICKED 또는 SOLD 상태만 반품 가능"
                    )
                    return result
                
                weight = tonbag['weight'] or 0
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 1. 톤백: PICKED → AVAILABLE
                self.db.execute("""
                    UPDATE inventory_tonbag SET
                        status = ?,
                        picked_to = NULL,
                        picked_date = NULL,
                        pick_ref = NULL,
                        outbound_date = NULL,
                        updated_at = ?
                    WHERE lot_no = ? AND sub_lt = ?
                """, (STATUS_AVAILABLE, now, lot_no, sub_lt))

                # 2. inventory: current_weight 복구
                self.db.execute("""
                    UPDATE inventory SET
                        current_weight = current_weight + ?,
                        picked_weight = MAX(0, picked_weight - ?),
                        updated_at = ?
                    WHERE lot_no = ?
                """, (weight, weight, now, lot_no))

                # v7.2.0 [RT-FIX]: OUTBOUND/SOLD 상태 반품 시 sold_table / picking_table 정리
                was_sold = tonbag['status'] in (STATUS_OUTBOUND, STATUS_SOLD, 'SHIPPED', 'CONFIRMED')
                if was_sold:
                    try:
                        self.db.execute(
                            "UPDATE sold_table SET status='RETURNED', sold_date=? "
                            "WHERE lot_no=? AND sub_lt=? AND status IN ('ACTIVE','SOLD','CONFIRMED')",
                            (now, lot_no, sub_lt)
                        )
                    except Exception:
                        logger.debug("[SUPPRESSED] exception in outbound_mixin.py")  # noqa
                    try:
                        self.db.execute(
                            "UPDATE picking_table SET status='RETURNED', sold_date=? "
                            "WHERE lot_no=? AND sub_lt=? AND status IN ('ACTIVE','SOLD','CONFIRMED')",
                            (now, lot_no, sub_lt)
                        )
                    except Exception:
                        logger.debug("[SUPPRESSED] exception in outbound_mixin.py")  # noqa
                    try:
                        self.db.execute(
                            "UPDATE allocation_plan SET status='CANCELLED', cancelled_at=? "
                            "WHERE lot_no=? AND sub_lt=? AND status IN ('EXECUTED','RESERVED','STAGED')",
                            (now, lot_no, sub_lt)
                        )
                    except Exception:
                        logger.debug("[SUPPRESSED] exception in outbound_mixin.py")  # noqa
                
                # 3. inventory summary/status 재계산
                if hasattr(self, '_recalc_current_weight'):
                    self._recalc_current_weight(lot_no, reason='P2_CANCEL_OUTBOUND_TONBAG')
                self._recalc_lot_status(lot_no)
                
                # 4. stock_movement 이력 (B3 FIX: 필수 기록)
                self.db.execute("""
                    INSERT INTO stock_movement 
                    (lot_no, movement_type, qty_kg, remarks, created_at)
                    VALUES (?, 'CANCEL_OUTBOUND', ?, ?, ?)
                """, (lot_no, weight, f"customer={tonbag['picked_to'] or ''}", now))
                
                result['success'] = True
                result['message'] = f"출고 취소 완료: {lot_no}-{sub_lt} ({weight:.0f}kg)"
                logger.info(result['message'])
            
            # v7.1.0 [CANCEL-INTEGRITY-1]: 취소 후 verify_lot_integrity 강화
            # 기존 _assert_lot_integrity → verify_lot_integrity로 교체
            # 경고 발생 시 result['warnings']에 기록 (중단 아님)
            if result['success']:
                try:
                    if hasattr(self, 'verify_lot_integrity'):
                        _integ = self.verify_lot_integrity(lot_no)
                        if not _integ.get('valid', True):
                            _iw = (
                                f"[CANCEL-INTEGRITY-1] 취소 후 정합성 경고: {lot_no} "
                                f"— {'; '.join(_integ.get('errors', []))[:100]} "
                                f"(재고 복구 완료, DB 재계산 권장)"
                            )
                            result.setdefault('warnings', []).append(_iw)
                            logger.warning(_iw)
                        else:
                            logger.info(f"[CANCEL-INTEGRITY-1] 정합성 OK: {lot_no}")
                    elif hasattr(self, '_assert_lot_integrity'):
                        self._assert_lot_integrity(lot_no)
                except Exception as _ie:
                    logger.debug(f"[CANCEL-INTEGRITY-1] 스킵: {_ie}")
                
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            result['errors'].append(str(e))
            logger.error(f"출고 취소 오류: {e}")
        
        return result

    def cancel_outbound_bulk(self, items: list) -> Dict:
        """
        일괄 출고 취소 (All-or-Nothing)
        items: [{'lot_no': '...', 'sub_lt': 1}, ...]
        """
        from datetime import datetime
        result = {'success': False, 'cancelled': 0, 'errors': []}
        
        try:
            with self.db.transaction("IMMEDIATE"):
                touched_lots = set()
                # v8.2.0 N+1 최적화: 루프 전 tonbag 일괄 pre-fetch
                # P1-7: 배치 조회 실패(예외) 시에만 N+1 폴백, 빈 결과는 유효한 정답
                _keys = [
                    (str(it.get('lot_no') or '').strip(), it.get('sub_lt'))
                    for it in items
                ]
                _placeholders = ','.join('(?,?)' for _ in _keys)
                _params = [v for k in _keys for v in k]
                _batch_failed = False
                _tb_rows = []
                if _placeholders:
                    try:
                        _tb_rows = self.db.fetchall(
                            f"SELECT lot_no, sub_lt, weight, status, picked_to "
                            f"FROM inventory_tonbag "
                            f"WHERE status = ? AND (lot_no, sub_lt) IN ({_placeholders})",
                            tuple([STATUS_PICKED] + _params)
                        ) or []
                    except Exception as _be:
                        # SQLite 구버전 row-value IN 미지원 시에만 N+1 폴백
                        logger.debug(f"[cancel_outbound_bulk] 배치 조회 실패 → N+1 폴백: {_be}")
                        _batch_failed = True

                if _batch_failed:
                    # N+1 폴백: 배치 쿼리 문법 오류(구버전 SQLite) 시에만 진입
                    for _k_lot, _k_sub in _keys:
                        _r = self.db.fetchone(
                            "SELECT lot_no, sub_lt, weight, status, picked_to "
                            "FROM inventory_tonbag "
                            "WHERE lot_no=? AND sub_lt=? AND status=?",
                            (_k_lot, _k_sub, STATUS_PICKED)
                        )
                        if _r:
                            _tb_rows.append(_r)
                _tonbag_cache = {
                    (str(r.get('lot_no') if isinstance(r, dict) else r[0]),
                     r.get('sub_lt') if isinstance(r, dict) else r[1]): r
                    for r in (_tb_rows or [])
                }

                for item in items:
                    lot_no = str(item.get('lot_no') or '').strip()
                    sub_lt = item.get('sub_lt')

                    tonbag = _tonbag_cache.get((lot_no, sub_lt))
                    if not tonbag:
                        raise ValueError(f"취소 불가: {lot_no}-{sub_lt}")

                    weight = (tonbag.get('weight') if isinstance(tonbag, dict)
                              else tonbag[2]) or 0
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.db.execute("""
                        UPDATE inventory_tonbag SET
                            status = ?, picked_to = NULL, picked_date = NULL,
                            pick_ref = NULL, outbound_date = NULL, updated_at = ?
                        WHERE lot_no = ? AND sub_lt = ?
                    """, (STATUS_AVAILABLE, now, lot_no, sub_lt))
                    
                    self.db.execute("""
                        UPDATE inventory SET
                            current_weight = current_weight + ?,
                            picked_weight = MAX(0, picked_weight - ?),
                            updated_at = ?
                        WHERE lot_no = ?
                    """, (weight, weight, now, lot_no))
                    
                    # stock_movement 이력 기록 (v3.8.4 bugfix)
                    self.db.execute("""
                        INSERT INTO stock_movement 
                        (lot_no, movement_type, qty_kg, remarks, created_at)
                        VALUES (?, 'CANCEL_OUTBOUND', ?, ?, ?)
                    """, (lot_no, weight, f"bulk_cancel customer={tonbag['picked_to'] or ''}", now))
                    
                    result['cancelled'] += 1
                    if lot_no:
                        touched_lots.add(lot_no)
                
                # 모든 관련 LOT status 재계산
                for lot_no in touched_lots:
                    self._recalc_lot_status(lot_no)
                    # v8.0.3 [P2]: bulk 취소 후 중앙 재계산
                    if hasattr(self, '_recalc_current_weight'):
                        self._recalc_current_weight(lot_no, reason='P2_CANCEL_OUTBOUND_BULK')
                
                result['success'] = True
                result['message'] = f"일괄 취소 완료: {result['cancelled']}건"
                
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            result['errors'].append(str(e))
            logger.error(f"일괄 출고 취소 오류: {e}")
        
        return result

    def _recalc_lot_status(self, lot_no: str) -> None:
        """LOT status 재계산 — v7.2.0: OUTBOUND 통합 + RETURN 상태 추가
        ★ 설계 원칙 (기동님 확정)
        판정 우선순위:
         1) AVAILABLE 톤백 1개라도 있고 OUTBOUND/SOLD 없음 → LOT = AVAILABLE
         2) AVAILABLE + OUTBOUND/SOLD 혼재                  → LOT = PARTIAL
         3) 전체 톤백이 모두 OUTBOUND/SOLD                  → LOT = OUTBOUND (신규)
         4) AVAILABLE 없고 RETURN 있음                      → LOT = RETURN (신규)
         5) AVAILABLE 없고 PICKED 있음                      → LOT = PICKED
         6) AVAILABLE 없고 RESERVED 있음                    → LOT = RESERVED
         7) 톤백 없거나 무게 0                              → DEPLETED
        """
        lot = self.db.fetchone(
            "SELECT current_weight, initial_weight FROM inventory WHERE lot_no = ?",
            (lot_no,)
        )
        if not lot:
            return

        # 단일 쿼리로 상태별 COUNT 집계 (v6.8.6: 기존 2회→1회)
        try:
            _cnt_rows = self.db.fetchall(
                "SELECT status, COUNT(*) AS cnt "
                "FROM inventory_tonbag WHERE lot_no = ? GROUP BY status",
                (lot_no,)
            )
            _cnt_map = {}
            _total_cnt = 0
            for _r in (_cnt_rows or []):
                _st = str(_r.get('status','') if isinstance(_r, dict) else _r[0]).strip().upper()
                _c  = int(_r.get('cnt', 0) if isinstance(_r, dict) else _r[1])
                _cnt_map[_st] = _c
                _total_cnt += _c
        except Exception:
            _cnt_map = {}
            _total_cnt = 0

        _avail_cnt    = _cnt_map.get(STATUS_AVAILABLE, 0)
        _reserved_cnt = _cnt_map.get(STATUS_RESERVED,  0)
        _picked_cnt   = _cnt_map.get(STATUS_PICKED,    0)
        _return_cnt   = _cnt_map.get('RETURN',         0)
        # v7.2.0: OUTBOUND + SOLD(하위호환) 통합 집계
        _outbound_cnt = (_cnt_map.get(STATUS_OUTBOUND, 0)
                         + _cnt_map.get(STATUS_SOLD, 0)
                         + _cnt_map.get('SHIPPED', 0)
                         + _cnt_map.get('CONFIRMED', 0))

        # ★ v7.2.0: OUTBOUND 통합 판정
        #  1) AVAILABLE 존재 + OUTBOUND 없음       → AVAILABLE
        #  2) AVAILABLE + OUTBOUND 혼재            → PARTIAL
        #  3) 전량 OUTBOUND/SOLD                   → OUTBOUND
        #  4) RETURN 존재 (반품 대기)              → RETURN
        #  5) PICKED 존재                          → PICKED
        #  6) RESERVED 존재                        → RESERVED
        #  7) 기타                                 → DEPLETED
        if _avail_cnt > 0 and _outbound_cnt == 0:
            new_status = STATUS_AVAILABLE
        elif _avail_cnt > 0 and _outbound_cnt > 0:
            new_status = STATUS_PARTIAL
        elif _total_cnt > 0 and _outbound_cnt >= _total_cnt:
            new_status = STATUS_OUTBOUND  # v7.2.0: SOLD 대신 OUTBOUND
        elif _return_cnt > 0:
            new_status = 'RETURN'         # v7.2.0: 반품 대기
        elif _picked_cnt > 0:
            new_status = STATUS_PICKED
        elif _reserved_cnt > 0:
            new_status = STATUS_RESERVED
        else:
            cw = lot.get('current_weight') or 0
            new_status = STATUS_DEPLETED if cw <= 0 else STATUS_AVAILABLE

        self.db.execute(
            "UPDATE inventory SET status = ? WHERE lot_no = ?",
            (new_status, lot_no)
        )


    # ═══════════════════════════════════════════════════════
    # v5.9.3: Allocation 기반 예약/실행/확정
    # ═══════════════════════════════════════════════════════

    def _allocation_risk_flags(self, qty_kg: float, available_kg: float) -> list[str]:
        flags = []
        if qty_kg >= self.ALLOCATION_APPROVAL_QTY_KG_THRESHOLD:
            flags.append("LARGE_VOLUME")
        if available_kg > 0 and qty_kg >= available_kg * self.ALLOCATION_APPROVAL_RATIO_THRESHOLD:
            flags.append("OVER_50PCT")
        return flags

    def _allocation_requires_approval(self, qty_kg: float, available_kg: float) -> bool:
        return len(self._allocation_risk_flags(qty_kg, available_kg)) > 0

    def _ra_build_result_template(self, allocation_rows: list, reservation_mode: str) -> dict:
        """v8.6.2 [SRP]: reserve_from_allocation 결과 dict 초기화 템플릿.

        예약 결과의 단일 진실 공급원 — 키 추가 시 여기만 수정.
        """
        return {
            'success': False,
            'reserved': 0,
            'pending_approval': 0,
            'errors': [],
            'error_details': [],
            'plan_ids': [],
            'requested_rows': len(allocation_rows),
            'reservation_mode': reservation_mode or 'tonbag',
        }

    def _ra_get_alloc_plan_cols(self) -> set:
        """v8.6.2 [SRP]: allocation_plan 테이블 컬럼 집합 조회.

        has_* 플래그 계산의 단일 소스.
        DB 조회 실패 시 빈 set 반환 (fallback 안전).
        """
        try:
            rows = self.db.fetchall("PRAGMA table_info(allocation_plan)")
            return {str(r.get("name", "")).strip().lower() for r in (rows or [])}
        except Exception as e:
            logger.debug(f"[_ra_get_alloc_plan_cols] 컬럼 조회 스킵: {e}")
            return set()

    # ── v8.6.4 [SRP] reserve_from_allocation 서브메서드 ────────────────

    @staticmethod
    def _ra_alloc_val(alloc, key, default=None):
        """AllocationRow(dataclass) 또는 dict 모두 지원하는 값 접근 헬퍼."""
        if isinstance(alloc, dict):
            return alloc.get(key, default)
        return getattr(alloc, key, default)

    def _ra_insert_plan_row(self, payload: dict, alloc_plan_cols: set) -> int:
        """allocation_plan 테이블에 행 삽입, 생성된 row id 반환."""
        cols, vals = [], []
        for k, v in payload.items():
            if k in alloc_plan_cols:
                cols.append(k)
                vals.append(v)
        if not cols:
            raise ValueError("allocation_plan insert 컬럼 없음")
        placeholders = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO allocation_plan ({', '.join(cols)}) VALUES ({placeholders})"
        self.db.execute(sql, tuple(vals))
        row = self.db.fetchone("SELECT last_insert_rowid() AS rid")
        return int(row.get("rid", 0) if isinstance(row, dict) else (row[0] if row else 0))

    def _ra_build_plan_payload(self, *, lot_no, customer, sale_ref, qty_mt,
                               outbound_date, status, source_label, now,
                               source_file, source_fingerprint,
                               alloc_plan_cols, import_batch_id, line_no,
                               export_type_val='', sc_rcvd_val=None,
                               tonbag_id=None, sub_lt=None,
                               workflow_status=None, risk_flags_txt=None):
        """v8.6.4 [SRP]: 3가지 경로(승인대기/LOT/톤백) 공통 payload 생성.

        기존 3회 반복 payload 구성 → 단일 메서드로 통합.
        """
        cols = alloc_plan_cols
        payload = {
            "lot_no": lot_no,
            "tonbag_id": tonbag_id,
            "sub_lt": sub_lt,
            "customer": customer,
            "sale_ref": sale_ref,
            "qty_mt": qty_mt,
            "outbound_date": outbound_date,
            "status": status,
            "source_file": source_file,
            "source_fingerprint": source_fingerprint if "source_fingerprint" in cols else "",
            "created_at": now,
        }
        if "source" in cols:
            payload["source"] = source_label
        if "import_batch_id" in cols and import_batch_id:
            payload["import_batch_id"] = import_batch_id
        if "line_no" in cols and line_no is not None:
            payload["line_no"] = line_no
        if "gate_status" in cols:
            payload["gate_status"] = "PASS"
        if "fail_code" in cols:
            payload["fail_code"] = ""
        if "fail_reason" in cols:
            payload["fail_reason"] = ""
        if "validated_at" in cols:
            payload["validated_at"] = now
        if "workflow_status" in cols and workflow_status:
            payload["workflow_status"] = workflow_status
        if "risk_flags" in cols and risk_flags_txt is not None:
            payload["risk_flags"] = risk_flags_txt
        if "approved_by" in cols and workflow_status:
            payload["approved_by"] = ""
        if "approved_at" in cols and workflow_status:
            payload["approved_at"] = None
        if "rejected_reason" in cols and workflow_status:
            payload["rejected_reason"] = ""
        if "export_type" in cols:
            payload["export_type"] = export_type_val
        if "sc_rcvd" in cols:
            payload["sc_rcvd"] = sc_rcvd_val
        return payload

    def _ra_parse_allocation_line(self, alloc, _alloc_val_fn):
        """Allocation 행 1줄을 파싱하여 dict로 반환. 정규화 포함."""
        lot_no = (normalize_lot(_alloc_val_fn(alloc, 'lot_no')) or '').strip()
        _raw_customer = str(_alloc_val_fn(alloc, 'sold_to') or _alloc_val_fn(alloc, 'customer') or '').strip()
        try:
            customer = normalize_customer(_raw_customer)
        except Exception:
            customer = _raw_customer
        sale_ref = str(_alloc_val_fn(alloc, 'sale_ref') or '').strip()
        qty_mt = float(_alloc_val_fn(alloc, 'qty_mt') or 0)
        outbound_date = _alloc_val_fn(alloc, 'outbound_date')
        sublot_count = int(_alloc_val_fn(alloc, 'sublot_count') or _alloc_val_fn(alloc, 'tonbag_count') or 0)
        is_sample_req = bool(_alloc_val_fn(alloc, 'is_sample', False))
        export_type_val = str(_alloc_val_fn(alloc, 'export_type') or '').strip()
        _sc = _alloc_val_fn(alloc, 'sc_rcvd')
        sc_rcvd_val = str(_sc) if _sc else None
        _unit_val = str(_alloc_val_fn(alloc, 'unit') or '').strip().upper()
        return {
            'lot_no': lot_no, 'customer': customer, '_raw_customer': _raw_customer,
            'sale_ref': sale_ref, 'qty_mt': qty_mt, 'outbound_date': outbound_date,
            'sublot_count': sublot_count, 'is_sample_req': is_sample_req,
            'export_type_val': export_type_val, 'sc_rcvd_val': sc_rcvd_val,
            'unit_val': _unit_val,
        }

    def _ra_validate_line_inputs(self, ctx: dict, line_no: int, result: dict, _build_error_detail) -> str:
        """행 입력 유효성 검증. 에러 시 에러 코드 문자열 반환, 통과 시 '' 반환."""
        lot_no = ctx['lot_no']
        customer = ctx['customer']
        qty_mt = ctx['qty_mt']
        sale_ref = ctx['sale_ref']

        if not lot_no:
            msg = "LOT 번호 누락"
            result['errors'].append(msg)
            _build_error_detail(line_no, "INVALID_LOT", msg, lot_no, customer, qty_mt)
            return "INVALID_LOT"
        if qty_mt == 0:
            msg = (f"[AL-09][ZERO_QTY] LOT {lot_no}: qty_mt=0 "
                   f"(빈 행 또는 수량 미입력 — 엑셀 확인 필요)")
            logger.error(msg)
            result['errors'].append(msg)
            _build_error_detail(line_no, "ZERO_QTY", msg, lot_no, customer, qty_mt)
            return "ZERO_QTY"
        if qty_mt < 0:
            msg = (f"[INVALID_QTY] LOT {lot_no}: qty_mt={qty_mt} "
                   f"(음수는 예약 불가 — 양수값 입력 필요)")
            logger.warning(msg)
            result['errors'].append(msg)
            _build_error_detail(line_no, "INVALID_QTY", msg, lot_no, customer, qty_mt)
            return "INVALID_QTY"
        if not customer:
            msg = (f"[INVALID_CUSTOMER] LOT {lot_no}: customer/sold_to가 비어 있음 "
                   f"(고객사 지정 필수)")
            logger.warning(msg)
            result['errors'].append(msg)
            _build_error_detail(line_no, "INVALID_CUSTOMER", msg, lot_no, customer, qty_mt)
            return "INVALID_CUSTOMER"
        if not sale_ref:
            msg = (f"[WARN_SALE_REF] LOT {lot_no}: sale_ref 미입력 "
                   f"(판매참조번호 없이 예약 진행)")
            logger.warning(msg)
            result.setdefault('warnings', []).append(msg)
        if ctx['unit_val'] and ctx['unit_val'] not in ('', 'KG'):
            msg = (f"[UNIT_MISMATCH] 허용되지 않은 단위: '{ctx['unit_val']}' "
                   f"(lot={lot_no}, line={line_no}) — KG만 허용")
            logger.warning(msg)
            result['errors'].append(msg)
            _build_error_detail(line_no, "UNIT_MISMATCH", msg, lot_no, customer, qty_mt)
            return "UNIT_MISMATCH"
        return ""

    def _ra_check_alloc_conflict(self, ctx: dict, line_no: int, result: dict, _build_error_detail) -> bool:
        """동일 (lot_no, customer, sale_ref, outbound_date) 활성 상태 충돌 체크. 충돌 시 True."""
        lot_no = ctx['lot_no']
        customer = ctx['customer']
        sale_ref = ctx['sale_ref']
        outbound_date = ctx['outbound_date']
        qty_mt = ctx['qty_mt']
        # [BUG-FIX #2-CAPACITY 2026-04-29]: LOT 가용 재고 초과 배정 차단
        try:
            _lot_row = self.db.fetchone(
                "SELECT current_weight FROM inventory WHERE lot_no = ?",
                (lot_no,)
            )
            if _lot_row:
                _cur_w = float((_lot_row.get('current_weight') if isinstance(_lot_row, dict)
                               else _lot_row[0]) or 0)
                _active_alloc_row = self.db.fetchone(
                    """SELECT COALESCE(SUM(qty_mt),0) AS total_mt FROM allocation_plan
                       WHERE lot_no = ? AND status IN ('STAGED','RESERVED','PENDING_APPROVAL')""",
                    (lot_no,)
                )
                _active_kg = float((_active_alloc_row.get('total_mt') if isinstance(_active_alloc_row, dict)
                                   else (_active_alloc_row[0] if _active_alloc_row else 0)) or 0) * 1000
                _req_kg = float(qty_mt or 0) * 1000
                if _active_kg + _req_kg > _cur_w + 0.01:
                    msg = (
                        f"[LOT_CAPACITY_EXCEEDED] LOT 가용재고 초과: {lot_no} "
                        f"현재가용={_cur_w:.0f}kg, 기활성배정={_active_kg:.0f}kg, "
                        f"신규요청={_req_kg:.0f}kg (합계={_active_kg+_req_kg:.0f}kg > 가용)"
                    )
                    logger.warning(msg)
                    result['errors'].append(msg)
                    _build_error_detail(line_no, "LOT_CAPACITY_EXCEEDED", msg, lot_no, customer, qty_mt)
                    return True
        except Exception as _cap_e:
            logger.debug(f"[LOT_CAPACITY] 용량 체크 스킵 (DB 오류): {_cap_e}")
        try:
            _conflict_statuses = "('STAGED','RESERVED','PENDING_APPROVAL')"
            _conflict_row = self.db.fetchone(
                f"""SELECT id FROM allocation_plan
                   WHERE lot_no = ? AND customer = ? AND sale_ref = ?
                     AND status IN {_conflict_statuses}
                     AND (outbound_date = ? OR (outbound_date IS NULL AND ? IS NULL))
                   LIMIT 1""",
                (lot_no, customer, sale_ref, outbound_date, outbound_date)
            )
            if _conflict_row:
                _conflict_id = _conflict_row.get('id', '?') if isinstance(_conflict_row, dict) else _conflict_row[0]
                msg = (f"[ALLOC_CONFLICT] 중복 행 차단: lot={lot_no} "
                       f"customer={customer} sale_ref={sale_ref} "
                       f"outbound_date={outbound_date} "
                       f"(기존 plan_id={_conflict_id})")
                logger.warning(msg)
                result['errors'].append(msg)
                _build_error_detail(line_no, "ALLOC_CONFLICT", msg, lot_no, customer, qty_mt)
                return True
        except Exception as _ce:
            logger.debug(f"[ALLOC_CONFLICT] 충돌 체크 스킵 (DB 오류): {_ce}")
        return False

    def _ra_check_lot_dup(self, ctx: dict, line_no: int, result: dict,
                          _build_error_detail, _batch_processed_lots: set) -> bool:
        """LOT 단위 sale_ref 중복 체크. 중복 시 True."""
        sale_ref = ctx['sale_ref']
        lot_no = ctx['lot_no']
        qty_mt = ctx['qty_mt']
        customer = ctx['customer']
        if not sale_ref:
            return False
        try:
            _lot_key = (sale_ref, lot_no)
            if _lot_key not in _batch_processed_lots:
                _lot_dup = self.db.fetchone(
                    """SELECT id FROM allocation_plan
                       WHERE sale_ref = ? AND lot_no = ?
                         AND tonbag_id IS NULL
                         AND status IN ('RESERVED','PENDING_APPROVAL')
                       LIMIT 1""",
                    (sale_ref, lot_no)
                )
                if _lot_dup:
                    _dup_id = _lot_dup.get('id','?') if isinstance(_lot_dup, dict) else _lot_dup[0]
                    msg = (
                        f"[LOT_MODE_DUP] LOT 단위 예약 중복: sale_ref={sale_ref} "
                        f"lot={lot_no} plan_id={_dup_id} — 이전 배정이 남아있음 (전체 초기화 후 재시도)"
                    )
                    logger.warning(msg)
                    result['errors'].append(msg)
                    _build_error_detail(line_no, "LOT_MODE_DUP", msg, lot_no, customer, qty_mt)
                    return True
        except Exception as _ge:
            logger.debug(f"[LOT_MODE_DUP 중복체크] 스킵: {_ge}")
        return False

    def _ra_resolve_pick_count(self, ctx: dict, tonbags: list, weight_kg: float,
                               _unit_w: float, result: dict) -> int:
        """요청 수량에서 pick_count(배정 톤백 수) 계산."""
        lot_no = ctx['lot_no']
        sublot_count = ctx['sublot_count']
        is_sample_req = ctx['is_sample_req']
        qty_mt = ctx['qty_mt']

        if sublot_count > 0:
            pick_count = sublot_count
            if not is_sample_req and _unit_w > 0 and qty_mt > 0:
                _calc_count = max(1, math.ceil((qty_mt * 1000) / _unit_w))
                if abs(_calc_count - sublot_count) > 1:
                    _b_warn = (
                        f"[TONBAG_COUNT_MISMATCH] {lot_no}: "
                        f"입력 sublot_count={sublot_count}개 "
                        f"vs qty_mt={qty_mt}MT÷{_unit_w}kg=계산{_calc_count}개 "
                        f"— sublot_count 우선 사용"
                    )
                    logger.warning(_b_warn)
                    result.setdefault('warnings', []).append(_b_warn)
        else:
            if is_sample_req:
                pick_count = 1
            elif _unit_w <= 0:
                _b_warn = (
                    f"[UNIT_WEIGHT_UNKNOWN] {lot_no}: "
                    f"톤백 단가 조회 실패(0kg) → 500kg 기본값 사용"
                )
                logger.warning(_b_warn)
                result.setdefault('warnings', []).append(_b_warn)
                _unit_w = 500.0
                pick_count = max(1, math.ceil(weight_kg / _unit_w))
            else:
                pick_count = max(1, math.ceil(weight_kg / _unit_w))
            logger.debug(
                f"[B pick_count] {lot_no}: "
                f"qty_mt={qty_mt}→weight_kg={weight_kg}÷unit_w={_unit_w}"
                f"=pick_count={pick_count}"
            )
        return pick_count

    def _ra_record_reservation_result(self, lot_no: str, reserved_in_lot: int,
                                       reserved_kg: float, selected_sub_lts: list,
                                       seed_hash: str, customer: str, sale_ref: str,
                                       effective_mode: str, allocation_random_mode: str,
                                       is_sample_req: bool, now: str,
                                       _batch_processed_lots: set, result: dict):
        """예약 결과 기록: stock_movement + audit_log + 배치 추적."""
        result['reserved'] += reserved_in_lot
        if reserved_in_lot > 0 and sale_ref:
            _batch_processed_lots.add((sale_ref, lot_no))
        if reserved_in_lot > 0 and effective_mode != "lot":
            self._recalc_lot_status(lot_no)
        if reserved_in_lot > 0:
            self.db.execute(
                "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                "VALUES (?, 'RESERVED', ?, ?, ?)",
                (
                    lot_no,
                    reserved_kg,
                    f"allocation(mode:{effective_mode}, rand:{allocation_random_mode}), tonbags={reserved_in_lot}, "
                    f"sub_lt={','.join(selected_sub_lts) if selected_sub_lts else '-'}, "
                    f"customer={customer}, seed={seed_hash[:8] if seed_hash else '-'}",
                    now,
                ),
            )
            try:
                from engine_modules.audit_helper import write_audit, EVT_RESERVED
                write_audit(self.db, EVT_RESERVED, lot_no=lot_no, detail={
                    'customer':    customer,
                    'tonbags':     reserved_in_lot,
                    'weight_kg':   reserved_kg,
                    'sale_ref':    sale_ref,
                    'mode':        effective_mode,
                })
            except Exception as _ae:
                logger.debug(f"[RESERVED audit] 스킵: {_ae}")
        logger.info(
            f"[reserve-{effective_mode}] {lot_no}: {reserved_in_lot}개 RESERVED "
            f"(rand={allocation_random_mode}, seed={seed_hash[:8] if seed_hash else '-'}, "
            f"sample={is_sample_req}, sub_lt={selected_sub_lts}) -> {customer}"
        )

    def _ra_log_random_selection(self, lot_no: str, sale_ref: str, customer: str,
                                  allocation_random_mode: str, seed_hash: str,
                                  tonbags: list, selected: list, reserved_in_lot: int, now: str):
        """랜덤 선택 이력 audit_log 저장."""
        try:
            _all_uids = [str(tb.get('tonbag_uid') or tb.get('sub_lt','')) for tb in tonbags]
            _sel_uids = [str(tb.get('tonbag_uid') or tb.get('sub_lt','')) for tb in (selected or [])]
            _excl_uids = [u for u in _all_uids if u not in _sel_uids]
            _g7_payload = json.dumps({
                "event":              "ALLOC_RANDOM_LOG",
                "lot_no":             lot_no,
                "sale_ref":           sale_ref,
                "customer":           customer,
                "random_mode":        allocation_random_mode,
                "random_seed":        seed_hash if seed_hash else None,
                "candidate_bag_count": len(_all_uids),
                "candidate_bag_list": _all_uids,
                "selected_bag_count": len(_sel_uids),
                "selected_bag_list":  _sel_uids,
                "excluded_bag_count": len(_excl_uids),
                "excluded_bag_list":  _excl_uids,
                "excluded_reason":    "not_selected_by_random_shuffle",
                "pick_count":         reserved_in_lot,
                "selection_timestamp": now,
            }, ensure_ascii=False)
            self.db.execute(
                "INSERT INTO audit_log(event_type, event_data, created_at) VALUES (?,?,?)",
                ("ALLOC_RANDOM_LOG", _g7_payload, now),
            )
            logger.debug(f"[G7-RANDOM-LOG] {lot_no} 랜덤 선택 로그 저장: "
                         f"후보={len(_all_uids)} 선택={len(_sel_uids)} 제외={len(_excl_uids)}")
        except Exception as _g7e:
            logger.debug(f"[G7-RANDOM-LOG] 로그 저장 스킵: {_g7e}")

    def _ra_check_duplicate_file(self, source_file, source_fingerprint, has_source_fp_col, result):
        """v8.6.4 [SRP]: 중복 Allocation 파일 감지 (fingerprint 우선, basename 폴백)."""
        if not source_fingerprint:
            return
        try:
            fname = os.path.basename(source_file) if source_file and source_file != '(붙여넣기)' else '(붙여넣기)'
            if has_source_fp_col:
                dup = self.db.fetchone(
                    """SELECT COUNT(*) AS cnt FROM allocation_plan
                       WHERE status = 'RESERVED' AND source_fingerprint = ?""",
                    (source_fingerprint,))
            else:
                dup = self.db.fetchone(
                    """SELECT COUNT(*) AS cnt FROM allocation_plan
                       WHERE status = 'RESERVED' AND source_file LIKE ?""",
                    (f"%{fname}",))
            dup_cnt = dup.get('cnt', 0) if isinstance(dup, dict) else (dup[0] if dup else 0)
            if dup_cnt > 0:
                result['duplicate_file'] = True
                result['duplicate_count'] = int(dup_cnt)
                result['duplicate_file_name'] = fname
                result['duplicate_source_fingerprint'] = source_fingerprint
        except Exception as e:
            logger.debug(f"중복 Allocation 파일 감지 실패: {e}")

    def _ra_g5_batch_validate(self, allocation_rows, result):
        """v8.6.4 [SRP]: [G5-MXBG] 배치 내 동일 LOT 합산 + 기존 RESERVED 초과 사전 검증.

        Returns True if G5 hard-stop (전체 배치 차단), False otherwise.
        """
        _av = self._ra_alloc_val
        _batch_lot_qty: dict = {}
        for _ba in (allocation_rows or []):
            _bln = (normalize_lot(_av(_ba, 'lot_no')) or '').strip()
            _bqt = float(_av(_ba, 'qty_mt') or 0)
            if _bln:
                _batch_lot_qty[_bln] = _batch_lot_qty.get(_bln, 0.0) + _bqt

        _g5_lot_list = [k for k, v in _batch_lot_qty.items() if v > 0]
        if not _g5_lot_list:
            return False

        _g5_ph = ",".join("?" * len(_g5_lot_list))
        _g5_total_rows = self.db.fetchall(
            f"SELECT lot_no, COALESCE(SUM(weight),0) AS total_kg "
            f"FROM inventory_tonbag "
            f"WHERE lot_no IN ({_g5_ph}) "
            f"AND status NOT IN ('SOLD','RETURNED','DEPLETED') "
            f"GROUP BY lot_no", _g5_lot_list)
        _g5_total_map = {
            (r.get('lot_no') if isinstance(r, dict) else r[0]):
            float(r.get('total_kg') if isinstance(r, dict) else r[1])
            for r in (_g5_total_rows or [])
        }
        _g5_already_rows = self.db.fetchall(
            f"SELECT lot_no, COALESCE(SUM(qty_mt * 1000), 0) AS already_kg "
            f"FROM allocation_plan "
            f"WHERE lot_no IN ({_g5_ph}) "
            f"AND status IN ('RESERVED','STAGED','PENDING_APPROVAL') "
            f"AND qty_mt >= 0.01 "
            f"GROUP BY lot_no", _g5_lot_list)
        _g5_already_map = {
            (r.get('lot_no') if isinstance(r, dict) else r[0]):
            float(r.get('already_kg') if isinstance(r, dict) else r[1])
            for r in (_g5_already_rows or [])
        }

        _g5_errors = []
        for _bln, _bqt_sum in _batch_lot_qty.items():
            if _bqt_sum <= 0:
                continue
            _bqt_kg = _bqt_sum * 1000.0
            _btotal_kg = _g5_total_map.get(_bln, 0.0)
            _balready_kg = _g5_already_map.get(_bln, 0.0)
            if _btotal_kg > 0 and (_balready_kg + _bqt_kg) > _btotal_kg + 0.5:
                _bremain_kg = max(0.0, _btotal_kg - _balready_kg)
                _g5_msg = (
                    f"[G5-MXBG-EXCEED] {_bln}: "
                    f"기존예약 {_balready_kg:.0f}kg + 이번배치 {_bqt_kg:.0f}kg"
                    f" > MXBG총량 {_btotal_kg:.0f}kg"
                    f" (잔여 배정 가능: {_bremain_kg:.0f}kg)")
                logger.error(_g5_msg)
                _g5_errors.append(_g5_msg)
                result['errors'].append(_g5_msg)

        if _g5_errors:
            result['success'] = False
            result['errors'].insert(0,
                f"[G5-HARD-STOP] 배치 내 LOT 중복 초과 {len(_g5_errors)}건 — 전체 배치 차단")
            logger.error(f"[G5-HARD-STOP] {len(_g5_errors)}건 배치 차단")
            return True
        return False

    def _ra_pre_dup_warnings(self, allocation_rows, result):
        """v8.6.4 [SRP]: [PRE-DUP] 기존 예약 LOT 사전 중복 감지 (경고만, 처리는 계속)."""
        _av = self._ra_alloc_val
        try:
            _batch_sale_refs = set()
            for _ba in (allocation_rows or []):
                _bsr = str(_av(_ba, 'sale_ref') or '').strip()
                _bqt = float(_av(_ba, 'qty_mt') or 0)
                if _bsr and _bqt >= 0.01:
                    _batch_sale_refs.add(_bsr)
            for _bsr in _batch_sale_refs:
                _already = self.db.fetchall(
                    "SELECT DISTINCT lot_no FROM allocation_plan "
                    "WHERE sale_ref=? AND status IN ('RESERVED','PENDING_APPROVAL','STAGED')",
                    (_bsr,))
                _already_lots = {
                    str(r.get('lot_no') if isinstance(r, dict) else r[0]).strip()
                    for r in (_already or []) if r}
                if _already_lots:
                    _batch_main_lots = {
                        (normalize_lot(_av(_ba, 'lot_no')) or '').strip()
                        for _ba in (allocation_rows or [])
                        if float(_av(_ba, 'qty_mt') or 0) >= 0.01}
                    _overlap = _already_lots & _batch_main_lots
                    if _overlap:
                        _msg = (
                            f"[PRE-DUP] sale_ref={_bsr}: "
                            f"이미 예약된 LOT {len(_overlap)}개 포함 — "
                            f"{sorted(_overlap)[:5]}{'...' if len(_overlap)>5 else ''} "
                            f"(LOT_MODE_DUP으로 스킵됩니다)")
                        logger.warning(_msg)
                        result.setdefault('warnings', []).append(_msg)
        except Exception as _pde:
            logger.debug(f"[PRE-DUP] 사전 중복 감지 스킵: {_pde}")

    def _ra_finalize_result(self, result, allocation_rows, source_file, has_alloc_batch_table):
        """v8.6.4 [SRP]: [Phase 3] 결과 집계 + import_batch 통계 + fail report."""
        if result['reserved'] == 0 and result['errors']:
            all_dup = all("중복 배정" in err or "이미 예약/출고됨" in err
                          for err in result['errors'])
            if all_dup:
                result['errors'].append(
                    "⚠️ 모든 LOT이 이미 예약 상태입니다.\n"
                    "• 다시 예약: [예약 취소] 후 재시도\n"
                    "• 기존 예약 진행: [출고 실행]")

        if has_alloc_batch_table and result.get("import_batch_id"):
            try:
                failed_lines = len(result.get("error_details", []))
                passed_lines = max(0, len(allocation_rows or []) - failed_lines)
                self.db.execute(
                    "UPDATE allocation_import_batch SET passed_lines=?, failed_lines=? WHERE id=?",
                    (passed_lines, failed_lines, result.get("import_batch_id")))
            except Exception as e:
                logger.debug(f"allocation_import_batch 집계 업데이트 스킵: {e}")

        if result.get("errors"):
            report_paths = self._save_allocation_fail_report(
                allocation_rows, result.get("errors", []),
                source_file=source_file,
                error_details=result.get("error_details", []))
            if report_paths.get("csv") or report_paths.get("json"):
                result["fail_report"] = report_paths
                if has_alloc_batch_table and result.get("import_batch_id"):
                    try:
                        self.db.execute(
                            "UPDATE allocation_import_batch SET report_csv_path=?, report_json_path=? WHERE id=?",
                            (report_paths.get("csv", ""),
                             report_paths.get("json", ""),
                             result.get("import_batch_id")))
                    except Exception as e:
                        logger.debug(f"allocation_import_batch 리포트 경로 업데이트 스킵: {e}")

    # ── reserve_from_allocation 헬퍼 (Phase 4-C 추출) ─────────────────

    def _ra_validate_lot_availability(
        self, lot_no: str, qty_mt: float, is_sample_req: bool,
        customer: str, line_no: int,
        result: dict, strict_errors: list,
        _build_error_detail,  # callable
    ) -> tuple:
        """
        LOT 헤더 미존재 체크 + G2 MXBG 초과 체크 + LOT 상태 체크.
        Returns (ok: bool, inv_status: str).
        ok=False means caller should `continue` the loop.
        """
        # [A] LOT 헤더 미존재 체크
        _inv_hdr = self.db.fetchone(
            "SELECT lot_no, status, product FROM inventory WHERE lot_no = ? LIMIT 1",
            (lot_no,)
        )
        if not _inv_hdr:
            msg = (
                f"[LOT_NOT_FOUND] {lot_no}: "
                f"재고 테이블에 LOT 없음 — 입고 처리 후 다시 시도하세요 "
                f"(Allocation 파일의 LOT 번호 오타 여부도 확인)"
            )
            logger.error(msg)
            result['errors'].append(msg)
            strict_errors.append(msg)
            _build_error_detail(line_no, "LOT_NOT_FOUND", msg, lot_no, customer, qty_mt)
            return False, ''
        _inv_status = str(_inv_hdr.get('status') or '').strip().upper()

        # [G2-MXBG-FIX] 총 cargo 초과 체크
        if qty_mt > 0:
            _g2_total_row = self.db.fetchone(
                "SELECT COALESCE(SUM(weight),0) AS total_kg "
                "FROM inventory_tonbag "
                "WHERE lot_no=? "
                "AND status NOT IN ('SOLD','RETURNED','DEPLETED')",
                (lot_no,)
            )
            _g2_total_kg = float(
                (_g2_total_row.get('total_kg') if isinstance(_g2_total_row, dict) else _g2_total_row[0])
                if _g2_total_row else 0
            )
            _g2_already_row = self.db.fetchone(
                "SELECT COALESCE(SUM(qty_mt * 1000), 0) AS already_kg "
                "FROM allocation_plan "
                "WHERE lot_no=? "
                "AND status IN ('RESERVED','STAGED','PENDING_APPROVAL') "
                "AND qty_mt >= 0.01",
                (lot_no,)
            )
            _g2_already_kg = float(
                (_g2_already_row.get('already_kg') if isinstance(_g2_already_row, dict) else _g2_already_row[0])
                if _g2_already_row else 0
            )
            _g2_req_kg = qty_mt * 1000.0
            if _g2_total_kg > 0 and (_g2_already_kg + _g2_req_kg) > _g2_total_kg + 0.5:
                _g2_remain_kg = max(0.0, _g2_total_kg - _g2_already_kg)
                _g2_msg = (
                    f"[G2-MXBG-EXCEED] {lot_no}: "
                    f"기존예약 {_g2_already_kg:.0f}kg + 이번요청 {_g2_req_kg:.0f}kg"
                    f" > MXBG총량 {_g2_total_kg:.0f}kg"
                    f" (잔여 배정 가능: {_g2_remain_kg:.0f}kg)"
                )
                logger.error(_g2_msg)
                result['errors'].append(_g2_msg)
                strict_errors.append(_g2_msg)
                _build_error_detail(line_no, "G2_CARGO_EXCEED", _g2_msg, lot_no, customer, qty_mt)
                return False, _inv_status

        # LOT 상태 체크
        if _inv_status not in ('AVAILABLE', 'RESERVED', 'PARTIAL'):
            msg = (
                f"[LOT_STATUS_MISMATCH] {lot_no}: "
                f"현재 LOT 상태={_inv_status} "
                f"(AVAILABLE/RESERVED/PARTIAL만 Allocation 가능)"
            )
            logger.warning(msg)
            result['errors'].append(msg)
            strict_errors.append(msg)
            _build_error_detail(line_no, "LOT_STATUS_MISMATCH", msg, lot_no, customer, qty_mt)
            return False, _inv_status

        return True, _inv_status

    def _ra_fetch_tonbag_pool(
        self, lot_no: str, is_sample_req: bool,
        customer: str, qty_mt: float, line_no: int,
        result: dict, strict_errors: list,
        _build_error_detail,  # callable
    ):
        """
        AVAILABLE 톤백 조회 + 위치 미배정 경고 + 톤백 없음 진단.
        Returns tonbag list, or None if caller should `continue`.
        """
        if is_sample_req:
            tonbags = self.db.fetchall(
                """SELECT id, sub_lt, weight,
                   COALESCE(location,'') AS location
                   FROM inventory_tonbag
                   WHERE lot_no = ? AND status = ?
                     AND COALESCE(is_sample, 0) = 1""",
                (lot_no, STATUS_AVAILABLE)
            )
        else:
            tonbags = self.db.fetchall(
                """SELECT id, sub_lt, weight,
                   COALESCE(location,'') AS location
                   FROM inventory_tonbag
                   WHERE lot_no = ? AND status = ?
                     AND COALESCE(is_sample, 0) = 0""",
                (lot_no, STATUS_AVAILABLE)
            )

        # [P2] 위치 미배정 톤백 경고
        if tonbags and not is_sample_req:
            _no_loc = [tb for tb in tonbags
                       if not str(tb.get('location') or '').strip()]
            if _no_loc:
                _loc_warn = (
                    f"[LOCATION_NOT_ASSIGNED] {lot_no}: "
                    f"{len(_no_loc)}개 톤백 위치 미배정 "
                    f"— [재고관리→위치배정] 후 출고 진행 권장"
                )
                logger.warning(_loc_warn)
                result.setdefault('warnings', []).append(_loc_warn)

        if not tonbags:
            # 원인 구분: DB에 LOT 없음 vs 톤백이 이미 예약/출고됨
            exists = self.db.fetchone(
                "SELECT 1 FROM inventory_tonbag WHERE lot_no = ? LIMIT 1",
                (lot_no,)
            )
            if not exists:
                msg = f"가용 톤백 없음: {lot_no} (LOT 미등록 → 입고 먼저 반영)"
                result['errors'].append(msg)
                strict_errors.append(msg)
                _build_error_detail(line_no, "LOT_NOT_IN_DB", msg, lot_no, customer, qty_mt)
            else:
                status_rows = self.db.fetchall(
                    "SELECT status, COUNT(*) AS cnt FROM inventory_tonbag WHERE lot_no = ? GROUP BY status",
                    (lot_no,)
                )
                status_summary = ", ".join(
                    f"{r.get('status', 'UNKNOWN')}={r.get('cnt', 0)}" for r in (status_rows or [])
                ) or "상태 집계 없음"
                avail_row = self.db.fetchone(
                    "SELECT COUNT(*) AS cnt FROM inventory_tonbag WHERE lot_no = ? AND status = ?",
                    (lot_no, STATUS_AVAILABLE)
                )
                avail_sample_row = self.db.fetchone(
                    "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                    "WHERE lot_no = ? AND status = ? AND COALESCE(is_sample, 0) = 1",
                    (lot_no, STATUS_AVAILABLE)
                )
                avail_normal_row = self.db.fetchone(
                    "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                    "WHERE lot_no = ? AND status = ? AND COALESCE(is_sample, 0) = 0",
                    (lot_no, STATUS_AVAILABLE)
                )
                avail_cnt = (avail_row.get('cnt') if isinstance(avail_row, dict) else avail_row[0]) if avail_row else 0
                avail_sample_cnt = (avail_sample_row.get('cnt') if isinstance(avail_sample_row, dict) else avail_sample_row[0]) if avail_sample_row else 0
                avail_normal_cnt = (avail_normal_row.get('cnt') if isinstance(avail_normal_row, dict) else avail_normal_row[0]) if avail_normal_row else 0
                if avail_cnt > 0:
                    req_type = "샘플(1kg)" if is_sample_req else "일반(비샘플)"
                    extra_reason = (
                        f"판매가능 톤백 {avail_cnt}개 "
                        f"(일반 {avail_normal_cnt}개 / 샘플 {avail_sample_cnt}개, 요청유형={req_type})"
                    )
                else:
                    extra_reason = "판매가능 톤백 0개"
                msg = (
                    f"가용 톤백 없음: {lot_no} (중복 배정 | {extra_reason} | 상태: {status_summary} | 조치: [예약 취소] 후 재시도)"
                )
                result['errors'].append(msg)
                strict_errors.append(msg)
                _build_error_detail(line_no, "NO_AVAILABLE_TONBAG", msg, lot_no, customer, qty_mt)
            return None

        return tonbags

    def _ra_execute_lot_reservation(
        self, ctx: dict, tonbags: list, pick_count: int,
        need_approval: bool, has_workflow_status_col: bool,
        effective_mode: str, allocation_random_mode: str,
        plan_line_counter: int, result: dict,
        _insert_plan,  # callable
        _common_kw: dict,
    ) -> tuple:
        """
        STAGED path + LOT mode + TONBAG mode 예약 실행.
        Returns (reserved_in_lot, reserved_kg, selected_sub_lts, seed_hash, plan_line_counter, selected).
        """
        lot_no = ctx['lot_no']
        sale_ref = ctx['sale_ref']
        qty_mt = ctx['qty_mt']
        outbound_date = _common_kw['outbound_date']
        source_file = _common_kw['source_file']
        weight_kg = ctx.get('_weight_kg', qty_mt * 1000.0)
        available_kg = sum(float(tb.get('weight') or 0) for tb in tonbags)
        risk_flags = ctx.get('_risk_flags', [])

        reserved_in_lot = 0
        reserved_kg = 0.0
        seed_hash = ""
        selected_sub_lts = []
        selected = []

        # 대량/위험 건은 STAGED + PENDING_APPROVAL로 적재
        if need_approval and has_workflow_status_col:
            qty_mt_each = (qty_mt / pick_count) if pick_count > 0 else qty_mt
            risk_txt = "|".join(risk_flags)
            for _ in range(pick_count):
                plan_line_counter += 1
                payload = self._ra_build_plan_payload(
                    qty_mt=qty_mt_each, status="STAGED",
                    source_label="APPROVAL_QUEUE",
                    line_no=plan_line_counter,
                    workflow_status="PENDING_APPROVAL",
                    risk_flags_txt=risk_txt,
                    **_common_kw)
                _insert_plan(payload)
                result['pending_approval'] += 1
            logger.info(
                f"[reserve-stage] {lot_no}: 승인대기 {pick_count}건 적재 "
                f"(qty_kg={weight_kg:.0f}, avail_kg={available_kg:.0f}, risk={risk_flags})")
            return reserved_in_lot, reserved_kg, selected_sub_lts, seed_hash, plan_line_counter, selected

        if effective_mode == "lot":
            # v9.2 [LOT-MODE-FIX]: 1행 INSERT (pick_count 반복 → UNIQUE 위반 수정)
            # lot 모드는 tonbag_id=NULL 1행으로 전체 qty_mt 기록.
            # pick_count는 결과 카운트에만 반영 (실출고 시 바코드 스캔으로 tonbag 특정).
            plan_line_counter += 1
            payload = self._ra_build_plan_payload(
                qty_mt=qty_mt, status="RESERVED",
                source_label="LOT", line_no=plan_line_counter,
                **_common_kw)
            _insert_plan(payload)
            reserved_in_lot = pick_count  # tonbag 개수 반영
            reserved_kg = sum(float(tb.get('weight') or 0) for tb in tonbags[:pick_count])
            # v9.3 [LOT-MODE-RESERVED]: inventory_tonbag.status → RESERVED (즉시 반영)
            _lot_selected = tonbags[:pick_count]
            _now = _common_kw['now']
            _customer = _common_kw['customer']
            _sale_ref_kw = _common_kw['sale_ref']
            _upd_lot_rows = [
                (STATUS_RESERVED, _customer, _sale_ref_kw, _now, tb['id'])
                for tb in _lot_selected
            ]
            if _upd_lot_rows:
                self.db.executemany(
                    """UPDATE inventory_tonbag SET
                        status = ?, picked_to = ?, sale_ref = ?, updated_at = ?
                    WHERE id = ?""", _upd_lot_rows)
            selected_sub_lts = [str(tb.get('sub_lt', '')) for tb in _lot_selected]
            self._recalc_lot_status(lot_no)
        else:
            # 톤백 단위 예약
            pool = list(tonbags)
            if allocation_random_mode == "seeded":
                seed_hash = self._build_allocation_seed(
                    lot_no=lot_no, sale_ref=sale_ref, qty_mt=qty_mt,
                    outbound_date=outbound_date, source_file=source_file)
                rng = random.Random(seed_hash)
                rng.shuffle(pool)
            else:
                random.shuffle(pool)
            selected = pool[:pick_count]
            selected_sub_lts = [str(tb.get('sub_lt', '')) for tb in selected]

            now = _common_kw['now']
            customer = _common_kw['customer']
            sale_ref_kw = _common_kw['sale_ref']
            _upd_rows = [
                (STATUS_RESERVED, customer, sale_ref_kw, now, tb['id'])
                for tb in selected]
            self.db.executemany(
                """UPDATE inventory_tonbag SET
                    status = ?, picked_to = ?, sale_ref = ?, updated_at = ?
                WHERE id = ?""", _upd_rows)
            qty_mt_each_tb = (qty_mt / pick_count) if pick_count > 0 else qty_mt
            for tb in selected:
                plan_line_counter += 1
                payload = self._ra_build_plan_payload(
                    qty_mt=qty_mt_each_tb, status="RESERVED",
                    source_label="TONBAG", line_no=plan_line_counter,
                    tonbag_id=tb["id"], sub_lt=tb["sub_lt"],
                    **_common_kw)
                _insert_plan(payload)
                reserved_in_lot += 1
                reserved_kg += float(tb.get('weight') or 0)

        return reserved_in_lot, reserved_kg, selected_sub_lts, seed_hash, plan_line_counter, selected

    # ── reserve_from_allocation 메인 ──────────────────────────────────

    def reserve_from_allocation(self, allocation_rows: list, source_file: str = '', reservation_mode: str = '') -> Dict:
        """
        Allocation 엑셀에서 파싱된 데이터로 톤백 예약 (AVAILABLE → RESERVED).
        allocation_plan 테이블에 계획 기록 + 톤백 상태 변경.

        v9.1 구조:
          [Phase 1] import_batch 생성 (보조)
          [Phase 2] 메인 트랜잭션 — All-or-Nothing 보호 (with self.db.transaction)
            [P2-1] G5 사전 검증  [P2-2] 사전 중복 경고  [P2-3] LOT별 루프
          [Phase 3] 결과 집계

        All-or-Nothing: Phase 2 에러 시 전체 자동 롤백. Phase 1/3은 보조.

        Args:
            allocation_rows: AllocationRow 또는 dict 리스트
            source_file: 원본 파일명

        Returns:
            {'success': bool, 'reserved': int, 'errors': [], 'plan_ids': []}
        """
        # v8.6.2 [SRP]: result 초기화 → _ra_build_result_template()
        result = self._ra_build_result_template(allocation_rows, reservation_mode)

        _alloc_val = self._ra_alloc_val  # v8.6.4 [SRP]: static method 참조

        # [RUBI-PHASE2] 랜덤출고 정책:
        strict_mode = self._get_allocation_strict_mode()
        allocation_random_mode = self._get_allocation_random_mode()
        effective_mode = self._get_allocation_reservation_mode(reservation_mode)
        result['reservation_mode'] = effective_mode
        has_alloc_batch_table = self._table_exists("allocation_import_batch")
        has_source_fp_col = self._has_allocation_source_fingerprint_column()
        source_fingerprint = self._compute_allocation_source_fingerprint(allocation_rows, source_file)
        # v8.6.2 [SRP]: col 조회 → _ra_get_alloc_plan_cols()
        alloc_plan_cols = self._ra_get_alloc_plan_cols()
        has_workflow_status_col = "workflow_status" in alloc_plan_cols

        def _build_error_detail(line_no: int, fail_code: str, reason: str, lot_no: str, sold_to: str, qty_mt):
            result['error_details'].append({
                "line_no": line_no, "fail_code": fail_code, "reason": reason,
                "lot_no": lot_no, "sold_to": sold_to, "qty_mt": qty_mt,
            })

        def _insert_plan(payload: dict):
            """v8.6.4: 서브메서드 위임 + plan_ids 추적."""
            rid = self._ra_insert_plan_row(payload, alloc_plan_cols)
            if rid:
                result["plan_ids"].append(rid)
            return rid

        # v8.6.4 [SRP]: 중복 Allocation 파일 감지 → 서브메서드
        self._ra_check_duplicate_file(source_file, source_fingerprint, has_source_fp_col, result)

        # ══ [Phase 1] import_batch 생성 (보조, 실패해도 계속) ════════
        import_batch_id = None
        if has_alloc_batch_table:
            try:
                now_batch = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.db.execute(
                    """INSERT INTO allocation_import_batch
                       (source_file, total_lines, passed_lines, failed_lines, imported_at)
                       VALUES (?, ?, 0, 0, ?)""",
                    (source_file or '(붙여넣기)', len(allocation_rows or []), now_batch)
                )
                row = self.db.fetchone("SELECT last_insert_rowid() AS rid")
                import_batch_id = int(row.get("rid", 0) if isinstance(row, dict) else (row[0] if row else 0))
                result["import_batch_id"] = import_batch_id
            except Exception as e:
                logger.debug(f"allocation_import_batch 생성 스킵: {e}")

        # ══ [Phase 2] 메인 트랜잭션 (All-or-Nothing 보호) ════════════
        try:
            with self.db.transaction("IMMEDIATE"):
                strict_errors = []
                plan_line_counter = 0

                # v8.6.4 [SRP]: G5 사전 검증 → 서브메서드
                if self._ra_g5_batch_validate(allocation_rows, result):
                    return result  # G5 HARD-STOP

                # v8.6.4 [SRP]: PRE-DUP 사전 중복 경고 → 서브메서드
                self._ra_pre_dup_warnings(allocation_rows, result)

                # ── [Phase 2-3] LOT별 예약 루프 ────────────────────
                _batch_processed_lots = set()
                for line_no, alloc in enumerate(allocation_rows, start=1):
                    # 행 파싱
                    ctx = self._ra_parse_allocation_line(alloc, _alloc_val)
                    lot_no = ctx['lot_no']
                    customer = ctx['customer']
                    sale_ref = ctx['sale_ref']
                    qty_mt = ctx['qty_mt']
                    outbound_date = ctx['outbound_date']
                    sublot_count = ctx['sublot_count']
                    is_sample_req = ctx['is_sample_req']
                    export_type_val = ctx['export_type_val']
                    sc_rcvd_val = ctx['sc_rcvd_val']

                    if ctx['_raw_customer'] != customer and ctx['_raw_customer']:
                        logger.debug(f"[E normalize_customer] '{ctx['_raw_customer']}' → '{customer}'")

                    # Gate A: 입력 유효성 검증
                    _val_err = self._ra_validate_line_inputs(ctx, line_no, result, _build_error_detail)
                    if _val_err:
                        if _val_err in ('INVALID_LOT',):
                            strict_errors.append(result['errors'][-1])
                        continue

                    # Gate: Allocation Row 충돌 차단
                    if self._ra_check_alloc_conflict(ctx, line_no, result, _build_error_detail):
                        continue

                    # Gate B: LOT+sale_ref 중복 차단
                    if self._ra_check_lot_dup(ctx, line_no, result, _build_error_detail, _batch_processed_lots):
                        continue

                    # [A+G2+C2] LOT 가용성 검증 (헤더/MXBG/상태)
                    _lot_ok, _inv_status = self._ra_validate_lot_availability(
                        lot_no, qty_mt, is_sample_req,
                        customer, line_no,
                        result, strict_errors, _build_error_detail
                    )
                    if not _lot_ok:
                        continue

                    # v6.12 Addon-G: DB에서 실제 톤백 단가 조회 (500/1000kg 동적 대응)
# [v6.8.6 top-level import로 이동]                     from engine_modules.constants import STATUS_PICKED, STATUS_RESERVED, STATUS_SOLD, get_tonbag_unit_weight
                    _unit_w = get_tonbag_unit_weight(self.db, lot_no)
                    weight_kg = qty_mt * 1000 if qty_mt > 0 else sublot_count * _unit_w

                    # [P2] AVAILABLE 톤백 조회 + 위치경고 + 없음 진단
                    tonbags = self._ra_fetch_tonbag_pool(
                        lot_no, is_sample_req,
                        customer, qty_mt, line_no,
                        result, strict_errors, _build_error_detail
                    )
                    if tonbags is None:
                        continue

                    # [B] qty_mt → 톤백 개수 변환 검증
                    pick_count = self._ra_resolve_pick_count(ctx, tonbags, weight_kg, _unit_w, result)
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    try:
                        ob_date_str = self._normalize_outbound_date(outbound_date)
                    except ValueError as ve:
                        msg = str(ve)
                        result['errors'].append(msg)
                        strict_errors.append(msg)
                        _build_error_detail(line_no, "INVALID_OUTBOUND_DATE", msg, lot_no, customer, qty_mt)
                        continue

                    if len(tonbags) < pick_count:
                        # v6.9.3 [AL-FIX-5]: 가용 초과 → HARD-STOP (oversell 원천 차단)
                        # PENDING_APPROVAL로 넘기지 않고 즉시 차단
                        msg = (
                            f"[QTY_EXCEEDS_AVAILABLE] {lot_no}: "
                            f"요청 {pick_count}개 > 가용 {len(tonbags)}개 "
                            f"— oversell 방지 HARD-STOP "
                            f"(Allocation 수정 또는 추가 입고 후 재시도)"
                        )
                        result['errors'].append(msg)
                        strict_errors.append(msg)
                        _build_error_detail(line_no, "QTY_EXCEEDS_AVAILABLE", msg, lot_no, customer, qty_mt)
                        continue

                    reserved_in_lot = 0
                    reserved_kg = 0.0
                    seed_hash = ""
                    selected_sub_lts = []
                    selected = []
                    available_kg = sum(float(tb.get('weight') or 0) for tb in tonbags)

                    # v6.9.3 [AL-10-FIX]: STAGED 경로에서도 실질 가용 수량 체크
                    # AVAILABLE 톤백 수 - 이미 STAGED/PENDING 계획된 수 = 실질 가용
                    # v8.5.9: 샘플 요청은 전용 is_sample=1 행에서 배정하므로 STAGED 체크 스킵
                    if not is_sample_req:
                        try:
                            _staged_cnt_row = self.db.fetchone(
                                """SELECT COUNT(*) AS cnt FROM allocation_plan
                                   WHERE lot_no=? AND status IN ('STAGED','RESERVED','PENDING_APPROVAL')
                                     AND tonbag_id IS NULL AND qty_mt >= 0.01""",
                                (lot_no,)
                            )
                            _staged_cnt = int((_staged_cnt_row.get('cnt') if isinstance(_staged_cnt_row, dict)
                                               else _staged_cnt_row[0]) if _staged_cnt_row else 0)
                            _real_avail = len(tonbags) - _staged_cnt
                            if _real_avail < pick_count:
                                msg = (
                                    f"[QTY_EXCEEDS_AVAILABLE] {lot_no}: "
                                    f"요청 {pick_count}개 > 실질가용 {_real_avail}개 "
                                    f"(AVAILABLE={len(tonbags)}, 이미STAGED={_staged_cnt}) "
                                    f"— oversell 방지 HARD-STOP"
                                )
                                result['errors'].append(msg)
                                strict_errors.append(msg)
                                _build_error_detail(line_no, "QTY_EXCEEDS_AVAILABLE", msg, lot_no, customer, qty_mt)
                                continue
                        except Exception as _ae:
                            logger.debug(f"[AL-10-FIX] 실질가용 체크 스킵: {_ae}")

                    # v6.9.0 [C4]: True or 제거 — 실제 승인 필요 여부 판정
                    need_approval = self._allocation_requires_approval(weight_kg, available_kg)
                    risk_flags = self._allocation_risk_flags(weight_kg, available_kg)

                    # v8.6.4 [SRP]: payload 공통 kwargs
                    _common_kw = dict(
                        lot_no=lot_no, customer=customer, sale_ref=sale_ref,
                        outbound_date=ob_date_str, now=now,
                        source_file=source_file, source_fingerprint=source_fingerprint,
                        alloc_plan_cols=alloc_plan_cols, import_batch_id=import_batch_id,
                        export_type_val=export_type_val, sc_rcvd_val=sc_rcvd_val,
                    )

                    # [Phase 4-C] 예약 실행 (STAGED / LOT / TONBAG)
                    ctx['_weight_kg'] = weight_kg
                    ctx['_risk_flags'] = risk_flags
                    (reserved_in_lot, reserved_kg, selected_sub_lts, seed_hash,
                     plan_line_counter, selected) = self._ra_execute_lot_reservation(
                        ctx, tonbags, pick_count,
                        need_approval, has_workflow_status_col,
                        effective_mode, allocation_random_mode,
                        plan_line_counter, result,
                        _insert_plan, _common_kw,
                    )
                    # STAGED 경로는 예약 없이 pending만 추가 → 다음 행으로
                    if need_approval and has_workflow_status_col:
                        continue

                    # 예약 결과 기록: movement + audit + 배치 추적
                    self._ra_record_reservation_result(
                        lot_no, reserved_in_lot, reserved_kg, selected_sub_lts,
                        seed_hash, customer, sale_ref, effective_mode,
                        allocation_random_mode, is_sample_req, now,
                        _batch_processed_lots, result)

                    # 랜덤 선택 이력 로그
                    self._ra_log_random_selection(
                        lot_no, sale_ref, customer, allocation_random_mode,
                        seed_hash, tonbags, selected, reserved_in_lot, now)

                if strict_mode and strict_errors:
                    raise ValueError(
                        "[STRICT] Allocation 예약 중단: " + " | ".join(strict_errors[:10])
                    )

            result['success'] = (result['reserved'] > 0) or (result.get('pending_approval', 0) > 0)
            if result['success']:
                if effective_mode == "lot":
                    result['message'] = f"예약 완료(LOT 단위): {result['reserved']}개 계획"
                else:
                    result['message'] = f"예약 완료: {result['reserved']}개 톤백"
            if result.get('pending_approval', 0) > 0:
                staged_msg = f"승인대기 적재: {result.get('pending_approval', 0)}건"
                if result.get('message'):
                    result['message'] += f" / {staged_msg}"
                else:
                    result['message'] = staged_msg

        except (ValueError, TypeError, sqlite3.Error) as e:
            logger.error(f"Allocation 예약 오류 (전체 롤백): {e}", exc_info=True)
            result['reserved'] = 0
            result['errors'].append(str(e))

        # v8.6.4 [SRP]: Phase 3 결과 집계 → 서브메서드
        self._ra_finalize_result(result, allocation_rows, source_file, has_alloc_batch_table)

        return result

    def apply_approved_allocation_reservations(self, limit: int = 0) -> Dict:
        """
        승인 완료(STAGED + APPROVED) 건을 실제 RESERVED로 반영.
        """
        result = {"success": False, "applied": 0, "errors": []}
        try:
            alloc_plan_cols = set()
            rows = self.db.fetchall("PRAGMA table_info(allocation_plan)")
            alloc_plan_cols = {str(r.get("name", "")).strip().lower() for r in (rows or [])}
            if "workflow_status" not in alloc_plan_cols:
                # ⑤ v6.7.1: 자동 마이그레이션 — 컬럼 없으면 즉시 추가 후 재시도
                logger.warning("[⑤] workflow_status 컬럼 없음 → 자동 마이그레이션 실행")
                try:
                    self.db.execute(
                        "ALTER TABLE allocation_plan "
                        "ADD COLUMN workflow_status TEXT DEFAULT 'APPROVED'"
                    )
                    self.db.execute(
                        "ALTER TABLE allocation_plan "
                        "ADD COLUMN rejected_reason TEXT"
                    )
                    self.db.execute(
                        "ALTER TABLE allocation_plan "
                        "ADD COLUMN approved_by TEXT"
                    )
                    self.db.execute(
                        "ALTER TABLE allocation_plan "
                        "ADD COLUMN approved_at TEXT"
                    )
                    # 컬럼 재조회
                    rows2 = self.db.fetchall("PRAGMA table_info(allocation_plan)")
                    alloc_plan_cols = {str(r.get("name","")).strip().lower()
                                       for r in (rows2 or [])}
                    if "workflow_status" not in alloc_plan_cols:
                        result["errors"].append(
                            "workflow_status 자동 마이그레이션 실패 — 수동 확인 필요")
                        return result
                    logger.info("[⑤] workflow_status 자동 마이그레이션 완료")
                except Exception as _e:
                    result["errors"].append(
                        f"workflow_status 마이그레이션 오류: {_e}")
                    return result
            has_risk_flags_col = "risk_flags" in alloc_plan_cols
            has_source_col = "source" in alloc_plan_cols
            has_approved_by_col = "approved_by" in alloc_plan_cols
            has_approved_at_col = "approved_at" in alloc_plan_cols

            # [C] v6.7.8: SQL 상수 리터럴로 교체 — ALLOC_STAGED/ALLOC_WF_APPROVED는
            # Python 변수이므로 SQL 문자열 안에 직접 쓰면 구문 오류 발생
            q = (
                "SELECT id, lot_no, customer, sale_ref, qty_mt, outbound_date, COALESCE(risk_flags, '') AS risk_flags "
                "FROM allocation_plan "
                "WHERE status='STAGED' AND workflow_status='APPROVED' "
                "ORDER BY created_at ASC, id ASC"
            )
            if limit and int(limit) > 0:
                q += f" LIMIT {int(limit)}"
            staged_rows = self.db.fetchall(q) or []
            if not staged_rows:
                result["errors"].append("반영할 승인 완료(STAGED/APPROVED) 건이 없습니다.")
                return result

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            actor = os.environ.get("USERNAME", "") or os.environ.get("USER", "") or "system"
            with self.db.transaction("IMMEDIATE"):
                for r in staged_rows:
                    plan_id = int(r.get("id", 0))
                    lot_no = str(r.get("lot_no", "")).strip()
                    customer = str(r.get("customer", "")).strip()
                    str(r.get("sale_ref", "")).strip()
                    qty_mt = float(r.get("qty_mt", 0) or 0)
                    _ = qty_mt <= 0.01 + 1e-9  # is_sample_req: 향후 샘플 필터링 예약
                    # [RUBI-PHASE2] 승인 완료 건은 TONBAG를 예약하지 않고 'LOT Target(대기)'로만 반영합니다.
                    # 실제 TONBAG 확정은 출고 스캔(UID) 순간에만 발생합니다.
                    # 최소 안전장치: LOT에 판매가능(AVAILABLE) 톤백이 1개도 없으면 승인 반영을 막습니다.
                    try:
                        cnt_row = self.db.fetchone(
                            "SELECT COUNT(*) AS cnt FROM inventory_tonbag WHERE lot_no=? AND status=?",
                            (lot_no, STATUS_AVAILABLE),
                        )
                        avail_cnt = int(cnt_row.get("cnt", 0) if isinstance(cnt_row, dict) else (cnt_row[0] if cnt_row else 0))
                    except Exception:
                        avail_cnt = 0
                    if avail_cnt <= 0:
                        result["errors"].append(f"미반영: {lot_no} 판매가능 톤백 없음 (plan_id={plan_id})")
                        continue

                    # allocation_plan만 상태 전환 (tonbag_id/sub_lt는 NULL 유지)
                    self.db.execute(
                        """UPDATE allocation_plan
                           SET status='RESERVED',
                               tonbag_id=NULL,
                               sub_lt=NULL,
                               workflow_status=ALLOC_WF_APPLIED
                           WHERE id=? AND status=ALLOC_STAGED AND workflow_status=ALLOC_WF_APPROVED""",
                        (plan_id,),
                    )
                    result["applied"] += 1
                    try:
                        details = {
                            "plan_id": plan_id,
                            "workflow": "APPROVED_TO_RESERVED",
                            "risk_flags": r.get("risk_flags", "") if has_risk_flags_col else "",
                        }
                        self.db.execute(
                            """INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at, source, actor, details_json)
                               VALUES (?, 'RESERVED', ?, ?, ?, ?, ?, ?)""",
                            (
                                lot_no,
                                float((qty_mt or 0) * 1000.0),
                                f"approved allocation apply, customer={customer}",
                                now,
                                "APPROVAL_APPLY" if has_source_col else None,
                                actor if has_approved_by_col else None,
                                json.dumps(details, ensure_ascii=False) if has_approved_at_col else None,
                            ),
                        )
                    except Exception as e:
                        logger.debug(f"stock_movement 기록 스킵: {e}")
                    self._recalc_lot_status(lot_no)

            result["success"] = result["applied"] > 0
            if not result["success"] and not result["errors"]:
                result["errors"].append("반영된 건이 없습니다.")
            return result
        except (sqlite3.Error, ValueError, TypeError) as e:
            logger.error(f"승인분 예약 반영 오류: {e}", exc_info=True)
            result["errors"].append(str(e))
            return result

    # ── execute_reserved 헬퍼 ─────────────────────────────────

    def _er_load_reserved_plans(self, lot_no: str = None, target_date: str = None) -> list:
        """RESERVED 상태 allocation_plan 조회."""
        query = """SELECT ap.id, ap.lot_no, ap.tonbag_id, ap.sub_lt,
                          ap.customer, ap.sale_ref, ap.outbound_date
                   FROM allocation_plan ap
                   WHERE ap.status = 'RESERVED'"""
        params = []
        if lot_no:
            query += " AND ap.lot_no = ?"
            params.append(lot_no)
        if target_date:
            query += " AND ap.outbound_date <= ?"
            params.append(target_date)
        return self.db.fetchall(query, tuple(params))

    def _er_warn_stale_plans(self, plans: list, result: dict):
        """outbound_date 30일 초과 만료 예약 경고."""
        if not plans:
            return
        try:
            from datetime import timedelta
            _h_threshold = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            _stale = [
                p for p in plans
                if p.get('outbound_date') and str(p.get('outbound_date','')) < _h_threshold
            ]
            if _stale:
                _stale_lots = list({p.get('lot_no','') for p in _stale})[:5]
                _h_warn = (
                    f"[STALE_RESERVATION] 출고일 30일 초과 예약 {len(_stale)}건 포함 "
                    f"— LOT: {', '.join(_stale_lots)} "
                    f"/ 담당자 확인 권장"
                )
                logger.warning(_h_warn)
                result.setdefault('warnings', []).append(_h_warn)
        except Exception as _he:
            logger.debug(f"[ER_STALE_WARN] 스킵: {_he}")

    def _er_validate_tonbag(self, plan: dict, result: dict):
        """톤백 상태/무게 검증. (tb_dict, tb_weight, tonbag_uid) 반환, 실패 시 None."""
        tb_id = plan['tonbag_id']
        p_lot = plan['lot_no']

        tb = self.db.fetchone(
            "SELECT weight, status, tonbag_uid, "
            "COALESCE(is_sample, 0) AS is_sample FROM inventory_tonbag WHERE id = ?",
            (tb_id,)
        )
        if not tb or tb['status'] != STATUS_RESERVED:
            result['errors'].append(f"톤백 {tb_id} 상태 불일치")
            return None

        _is_sample_tb = int(tb.get('is_sample') or 0)
        tb_weight = tb['weight'] or 0

        if tb_weight <= 0:
            _k_warn = (
                f"[ZERO_WEIGHT_TONBAG] 톤백 {tb_id} (lot={p_lot}) "
                f"무게=0kg — 입고 데이터 오류, PICKED 스킵 "
                f"(재고관리→무게 수정 후 재시도)"
            )
            logger.warning(_k_warn)
            result['errors'].append(_k_warn)
            return None

        if _is_sample_tb and tb_weight > 1.01:
            _warn = (f"[SAMPLE_WEIGHT_WARN] 샘플 톤백 {tb_id} (lot={p_lot}) "
                     f"무게={tb_weight}kg > 1kg — 이상값, PICKED 스킵")
            logger.warning(_warn)
            result['errors'].append(_warn)
            return None

        tonbag_uid = (tb.get('tonbag_uid') or '').strip() or None
        return {'tb': tb, 'weight': tb_weight, 'uid': tonbag_uid}

    def _er_apply_pick_transition(self, plan: dict, tb_weight: float, now: str):
        """톤백 RESERVED→PICKED 전환 + inventory weight 갱신 + plan EXECUTED."""
        tb_id = plan['tonbag_id']
        p_lot = plan['lot_no']

        # 톤백 상태 전환
        self.db.execute(
            """UPDATE inventory_tonbag SET
                status = ?, picked_date = ?, outbound_date = ?, updated_at = ?
            WHERE id = ?""",
            (STATUS_PICKED, now, plan['outbound_date'] or now, now, tb_id)
        )
        # inventory weight 갱신
        self.db.execute(
            """UPDATE inventory SET
                current_weight = MAX(0, current_weight - ?),
                picked_weight = picked_weight + ?,
                updated_at = ?
            WHERE lot_no = ?""",
            (tb_weight, tb_weight, now, p_lot)
        )
        if hasattr(self, '_recalc_current_weight'):
            self._recalc_current_weight(p_lot, reason='P2_RESERVED_TO_PICKED')
        # plan 상태 갱신
        self.db.execute(
            """UPDATE allocation_plan SET status = 'PICKED', executed_at = ?
            WHERE id = ?""",
            (now, plan['id'])
        )

    def _er_record_pick_movement(self, plan: dict, tb_weight: float, now: str):
        """stock_movement에 PICKED_MOVE 이력 INSERT."""
        self.db.execute(
            """INSERT INTO stock_movement
            (lot_no, movement_type, qty_kg, remarks, created_at)
            VALUES (?, 'PICKED_MOVE', ?, ?, ?)""",
            (plan['lot_no'], tb_weight,
             f"RESERVED→PICKED, customer={plan['customer']}, sale_ref={plan['sale_ref']}", now)
        )

    def _er_insert_picking_row(self, plan: dict, tb_weight: float, tonbag_uid, now: str, result: dict) -> bool:
        """picking_table에 PICKED 이력 INSERT. 중복 시 False 반환 (해당 톤백 스킵)."""
        try:
            self.db.execute(
                """INSERT INTO picking_table
                (lot_no, tonbag_id, sub_lt, tonbag_uid, customer, qty_kg, status, picking_date, created_by, remark)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, 'system', ?)""",
                (plan['lot_no'], plan['tonbag_id'], plan['sub_lt'], tonbag_uid,
                 plan.get('customer') or '', tb_weight, now,
                 f"plan_id={plan['id']}, sale_ref={plan.get('sale_ref', '')}")
            )
        except sqlite3.OperationalError as e:
            _oe_msg = str(e).lower()
            if "no such table" in _oe_msg:
                pass
            elif "unique" in _oe_msg:
                _h3_msg = (
                    f"[PICKING_DUPLICATE] 중복 피킹 차단: "
                    f"tonbag_id={plan['tonbag_id']}, lot={plan['lot_no']} — "
                    f"이미 picking_table에 존재합니다"
                )
                logger.warning(_h3_msg)
                result['errors'].append(_h3_msg)
                return False
            else:
                # NOTE: picking_table INSERT 실패 — 운영 중요도 높을 수 있으므로 경고 로깅
                logger.warning(
                    f"[ER_PICKING] INSERT 실패: tonbag_id={plan['tonbag_id']}, "
                    f"lot={plan['lot_no']}, error={e}"
                )
        return True

    # ── execute_reserved 메인 ────────────────────────────────

    def execute_reserved(self, lot_no: str = None, target_date: str = None) -> Dict:
        """
        RESERVED 톤백을 PICKED로 전환 (출고 실행).
        lot_no 지정 시 해당 LOT만, target_date 지정 시 해당 날짜 이하만 실행.

        Returns:
            {'success': bool, 'executed': int, 'errors': []}
        """
        result = {'success': False, 'executed': 0, 'errors': []}

        try:
            # 1) RESERVED plans 로드
            plans = self._er_load_reserved_plans(lot_no, target_date)

            # 2) 만료 예약 경고
            self._er_warn_stale_plans(plans, result)

            # 3) 예약 없음 처리
            if not plans:
                lot_mode_cnt = 0
                try:
                    row = self.db.fetchone(
                        "SELECT COUNT(*) AS cnt FROM allocation_plan WHERE status='RESERVED' AND tonbag_id IS NULL"
                    )
                    lot_mode_cnt = int(row.get('cnt', 0) if isinstance(row, dict) else (row[0] if row else 0))
                except Exception:
                    lot_mode_cnt = 0
                if lot_mode_cnt > 0:
                    result['message'] = (
                        f"실행할 톤백 예약 건 없음 (LOT 단위 예약 {lot_mode_cnt}건 대기 중: 바코드 스캔으로 확정하세요)"
                    )
                else:
                    result['message'] = "실행할 예약 건 없음"
                return result

            # 4) 트랜잭션: plan별 RESERVED→PICKED 전환
            with self.db.transaction("IMMEDIATE"):
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                processed_lots = set()

                for plan in plans:
                    p_lot = plan['lot_no']
                    tb_id = plan['tonbag_id']

                    # LOT 모드: tonbag_id=NULL → 바코드 스캔 대기
                    if tb_id is None:
                        logger.debug(
                            f"[LOT-MODE] {p_lot} plan_id={plan['id']} "
                            f"tonbag_id=NULL → 바코드 스캔 대기 (execute_reserved 스킵)"
                        )
                        result['executed'] += 1
                        processed_lots.add(p_lot)
                        continue

                    # 톤백 검증
                    validated = self._er_validate_tonbag(plan, result)
                    if not validated:
                        continue

                    # 상태 전환 + weight 갱신 + plan EXECUTED
                    self._er_apply_pick_transition(plan, validated['weight'], now)

                    # movement 이력
                    self._er_record_pick_movement(plan, validated['weight'], now)

                    # picking_table INSERT (중복 시 스킵)
                    if not self._er_insert_picking_row(plan, validated['weight'], validated['uid'], now, result):
                        continue

                    processed_lots.add(p_lot)
                    result['executed'] += 1

                for pl in processed_lots:
                    self._recalc_lot_status(pl)

            result['success'] = result['executed'] > 0
            result['message'] = f"출고 실행 완료: {result['executed']}건"

        except (ValueError, TypeError, sqlite3.Error) as e:
            logger.error(f"출고 실행 오류 (전체 롤백): {e}", exc_info=True)
            result['errors'].append(str(e))

        return result


    # ══════════════════════════════════════════════════════════════════════
    # v8.6.4: confirm_outbound + gate1_verify_picking 분해 — 서브메서드 4개
    # ══════════════════════════════════════════════════════════════════════

    def _co_check_double_sold(self, tonbag_id) -> bool:
        """v8.6.4: 이중 SOLD 차단 (confirm_outbound 분해 1/4).

        sold_table에 동일 tonbag_id가 이미 존재하면 True (이중 차단).
        """
        import sqlite3 as _sq
        if not tonbag_id:
            return False
        try:
            row = self.db.fetchone(
                "SELECT id FROM sold_table WHERE tonbag_id=? AND status IN ('OUTBOUND','SOLD')",
                (tonbag_id,)
            )
            return bool(row)
        except (_sq.OperationalError, OSError):
            return False

    def _co_verify_weight_conservation(self, lot_no: str) -> dict:
        """v8.6.4: 출고 확정 후 무게 보존 법칙 사후검증 (confirm_outbound 분해 2/4).

        initial_weight == current_weight + picked_weight (±1.0kg 허용)
        Returns: {'ok': bool, 'diff': float, 'msg': str}
        """
        import sqlite3 as _sq
        try:
            row = self.db.fetchone(
                """SELECT i.initial_weight,
                          COALESCE(SUM(CASE WHEN t.status='AVAILABLE' THEN t.weight ELSE 0 END),0) AS avail,
                          COALESCE(SUM(CASE WHEN t.status='PICKED'    THEN t.weight ELSE 0 END),0) AS picked,
                          COALESCE(SUM(CASE WHEN t.status IN ('OUTBOUND','SOLD')
                                           THEN t.weight ELSE 0 END),0) AS outb
                   FROM inventory i
                   LEFT JOIN inventory_tonbag t ON t.lot_no=i.lot_no AND COALESCE(t.is_sample,0)=0
                   WHERE i.lot_no=?
                   GROUP BY i.lot_no""",
                (lot_no,)
            )
            if not row:
                return {'ok': True, 'diff': 0.0, 'msg': ''}
            r = dict(row) if not isinstance(row, dict) else row
            initial = float(r.get('initial_weight') or 0)
            actual  = float(r.get('avail',0)) + float(r.get('picked',0)) + float(r.get('outb',0))
            diff    = abs(initial - actual)
            ok      = diff <= 1.0
            msg     = ('' if ok else
                       f"[LOT_TOTAL_MISMATCH] {lot_no}: initial={initial:.1f} actual={actual:.1f} diff={diff:.1f}kg")
            return {'ok': ok, 'diff': diff, 'msg': msg}
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[confirm] 무게 검증 스킵: {e}")
            return {'ok': True, 'diff': 0.0, 'msg': ''}

    def _g1_aggregate_picking_qty(self, picking_rows: list) -> dict:
        """v8.6.4: 피킹 LOT별 요청 수량 집계 (gate1_verify_picking 분해 3/4).

        Returns: {lot_no: {'qty_mt': float, 'bag_count': int}}
        """
        from collections import defaultdict
        agg = defaultdict(lambda: {'qty_mt': 0.0, 'bag_count': 0})
        for r in picking_rows:
            lot = str(r.get('lot_no') or '').strip()
            if not lot:
                continue
            qty = float(r.get('qty_mt') or r.get('weight_kg', 0) / 1000.0)
            agg[lot]['qty_mt']    += qty
            agg[lot]['bag_count'] += int(r.get('bag_count') or 1)
        return dict(agg)

    def _g1_cancel_excess_allocation(self, lot_no: str,
                                      excess_mt: float) -> int:
        """v8.6.4: Picking < RESERVED 초과분 allocation_plan CANCELLED (gate1_verify_picking 분해 4/4).

        최신 순으로 초과분만 CANCELLED.
        Returns: cancelled 건수
        """
        import sqlite3 as _sq
        import math
        if excess_mt <= 0:
            return 0
        excess_bags = math.ceil(excess_mt / 0.5)
        try:
            candidates = self.db.fetchall(
                """SELECT id FROM allocation_plan
                   WHERE lot_no=? AND status='RESERVED'
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (lot_no, excess_bags)
            )
            if not candidates:
                return 0
            ids = tuple(
                (r.get('id') if isinstance(r, dict) else r[0])
                for r in candidates
            )
            placeholders = ','.join(['?'] * len(ids))
            self.db.execute(
                f"UPDATE allocation_plan SET status='CANCELLED' WHERE id IN ({placeholders})",
                ids
            )
            logger.info(f"[Gate1] {lot_no} 초과 allocation {len(ids)}건 CANCELLED")
            return len(ids)
        except (_sq.OperationalError, OSError) as e:
            logger.warning(f"[Gate1] allocation CANCELLED 실패 {lot_no}: {e}")
            return 0

    # ── confirm_outbound 헬퍼 ──────────────────────────────────

    def _co_load_picked_tonbags(self, lot_no: str = None) -> list:
        """PICKED 상태 톤백 조회. lot_no 지정 시 해당 LOT만."""
        query = """SELECT id, lot_no, sub_lt, weight, tonbag_uid FROM inventory_tonbag
                   WHERE status = ?"""
        params = [STATUS_PICKED]
        if lot_no:
            query += " AND lot_no = ?"
            params.append(lot_no)
        return self.db.fetchall(query, tuple(params))

    def _co_guard_against_double_outbound(self, tonbags: list, result: dict) -> bool:
        """이중 출고 차단. 이미 sold_table에 존재하면 True(차단) 반환."""
        _tb_ids = [tb['id'] for tb in tonbags]
        if not _tb_ids:
            return False
        try:
            _ph = ','.join('?' * len(_tb_ids))
            _already_sold = self.db.fetchall(
                f"SELECT tonbag_id FROM sold_table WHERE tonbag_id IN ({_ph})",
                tuple(_tb_ids)
            )
            if _already_sold:
                _dup_ids = [str(r.get('tonbag_id') if isinstance(r, dict) else r[0])
                           for r in _already_sold]
                _f_msg = (
                    f"[DOUBLE_OUTBOUND_BLOCKED] 이미 출고된 톤백 {len(_dup_ids)}개 중복 확정 시도: "
                    f"tonbag_ids={', '.join(_dup_ids)} — 출고 확정 차단"
                )
                logger.error(_f_msg)
                result['errors'].append(_f_msg)
                return True
        except Exception as _fe:
            logger.error(f"[DOUBLE_OUTBOUND_CHECK] safety guard 실패 — 출고 차단: {_fe}")
            result['errors'].append(f"이중 출고 체크 실패: {_fe}")
            return True
        return False

    def _co_validate_customer_sale_ref(self, tonbags: list, result: dict) -> bool:
        """sale_ref/customer 혼재 검증. 혼재 시 True(차단) 반환."""
        _tb_ids = [tb['id'] for tb in tonbags]
        if not _tb_ids:
            return False
        _sale_ref_set = set()
        _customer_set = set()
        try:
            _ph = ','.join('?' * len(_tb_ids))
            _plans = self.db.fetchall(
                f"SELECT tonbag_id, sale_ref, customer FROM allocation_plan "
                f"WHERE tonbag_id IN ({_ph}) "
                f"GROUP BY tonbag_id HAVING id = MAX(id)",
                tuple(_tb_ids)
            )
            for _plan in (_plans or []):
                _sr = str(_plan.get('sale_ref') or '').strip()
                _cu_raw = str(_plan.get('customer') or '').strip()
                try:
                    _cu = normalize_customer(_cu_raw)
                except Exception:
                    _cu = _cu_raw
                if _sr: _sale_ref_set.add(_sr)
                if _cu: _customer_set.add(_cu)
        except Exception as _h2e:
            logger.debug(f"[CO_VALIDATE] sale_ref/customer 혼재체크 스킵: {_h2e}")

        if len(_customer_set) > 1:
            _warn = (f"[CONFIRM_WARN] PICKED 톤백에 복수 고객 혼재: "
                     f"{', '.join(sorted(_customer_set))} — 출고 확정을 중단합니다.")
            logger.warning(_warn)
            result['errors'].append(_warn)
            return True
        if len(_sale_ref_set) > 1:
            _warn = (f"[CONFIRM_WARN] PICKED 톤백에 복수 sale_ref 혼재: "
                     f"{', '.join(sorted(_sale_ref_set))} — 출고 확정을 중단합니다.")
            logger.warning(_warn)
            result['errors'].append(_warn)
            return True
        return False

    def _co_build_sold_row_payload(self, tb: dict, now: str) -> tuple:
        """sold_table INSERT용 페이로드 구성. (columns, values) 반환."""
        tb_id = tb['id']
        uid_val = (tb.get('tonbag_uid') or '').strip() or ''
        if not uid_val:
            uid_val = str(tb.get('sub_lt') or tb_id)

        # picking_id 조회
        try:
            pick_row = self.db.fetchone(
                "SELECT id FROM picking_table WHERE tonbag_id = ? ORDER BY id DESC LIMIT 1",
                (tb_id,)
            )
            picking_id = pick_row['id'] if pick_row else None
        except sqlite3.OperationalError:
            picking_id = None

        # inventory 정보
        _inv_row = self.db.fetchone(
            "SELECT sap_no, bl_no, product_code, product, gross_weight, net_weight, "
            "mxbg_pallet, sold_to, sale_ref FROM inventory WHERE lot_no = ?",
            (tb['lot_no'],)
        )
        _inv = dict(_inv_row) if _inv_row else {}

        # picking_table 정보
        _pick_info = self.db.fetchone(
            "SELECT sales_order_no, picking_no, customer, outbound_id FROM picking_table "
            "WHERE tonbag_id = ? ORDER BY id DESC LIMIT 1",
            (tb_id,)
        )
        _pi = dict(_pick_info) if _pick_info else {}

        # allocation_plan 정보 (fallback)
        _alloc_info = self.db.fetchone(
            "SELECT customer, sale_ref FROM allocation_plan "
            "WHERE tonbag_id = ? ORDER BY id DESC LIMIT 1",
            (tb_id,)
        )
        _al = dict(_alloc_info) if _alloc_info else {}

        # GW 계산
        _is_sample = tb.get('is_sample', 0) or (1 if tb.get('sub_lt', -1) == 0 else 0)
        _tb_gw_kg = 0.0
        if _is_sample:
            _tb_gw_kg = (tb.get('weight') or 0) * 1.025
        elif _inv.get('mxbg_pallet') and _inv.get('gross_weight'):
            _tb_gw_kg = float(_inv['gross_weight']) / int(_inv['mxbg_pallet'])

        _customer = (_pi.get('customer') or _al.get('customer')
                    or _inv.get('sold_to') or '')
        _sold_qty_kg = tb.get('weight') or 0
        _sold_qty_mt = round(_sold_qty_kg / 1000.0, 6) if _sold_qty_kg else 0
        _sku = _inv.get('product_code') or ''
        if _is_sample and _sku and 'Sample' not in _sku:
            _sku = f"{_sku} Sample"

        return (
            tb['lot_no'], tb_id, tb.get('sub_lt', 0), uid_val, picking_id,
            _sold_qty_kg, _sold_qty_mt, _tb_gw_kg, now,
            _inv.get('sap_no', ''), _inv.get('bl_no', ''),
            _customer, _sku,
            _pi.get('sales_order_no', ''), _pi.get('picking_no', ''),
            now[:10],
            1 if not _is_sample else 1,
            1 if _is_sample else 0
        )

    def _co_insert_sold_row(self, tb: dict, now: str):
        """sold_table에 출고 이력 1건 INSERT."""
        try:
            values = self._co_build_sold_row_payload(tb, now)
            self.db.execute(
                """INSERT INTO sold_table
                (lot_no, tonbag_id, sub_lt, tonbag_uid, picking_id,
                 sold_qty_kg, sold_qty_mt, gross_weight_kg, sold_date, status, created_by,
                 sap_no, bl_no, customer, sku, sales_order_no, picking_no,
                 delivery_date, ct_plt, is_sample)
                VALUES (?, ?, ?, ?, ?,
                        ?, ?, ?, ?, 'OUTBOUND', 'system',
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?)""",
                values
            )
        except sqlite3.OperationalError as e:
            # NOTE: sold_table 미존재 시 무시, 그 외는 로깅
            if "no such table" not in str(e).lower():
                logger.warning(
                    f"[CO_INSERT_SOLD] sold_table 기록 실패: tonbag_id={tb['id']}, "
                    f"lot_no={tb.get('lot_no')}, error={e}"
                )

    def _co_insert_outbound_movement(self, tb: dict, now: str):
        """stock_movement에 OUTBOUND 이력 INSERT."""
        self.db.execute(
            "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
            "VALUES (?, 'OUTBOUND', ?, ?, ?)",
            (tb['lot_no'], tb.get('weight', 0),
             f"confirm_outbound, sub_lt={tb.get('sub_lt', 0)}", now))

    def _co_run_post_checks(self, touched_lots: set, result: dict):
        """출고 확정 후 LOT_TOTAL_MISMATCH + SAMPLE_POLICY 사후검증."""
        if not touched_lots:
            return
        try:
            _post_errors = []
            _inv_rows = self.db.fetchall(
                "SELECT lot_no, initial_weight, current_weight, picked_weight "
                "FROM inventory WHERE lot_no IN (%s)" %
                ','.join('?' * len(touched_lots)),
                tuple(touched_lots)
            )
            for _r in (_inv_rows or []):
                _iw = float(_r.get('initial_weight') or 0)
                _cw = float(_r.get('current_weight') or 0)
                _pw = float(_r.get('picked_weight') or 0)
                if abs(_iw - (_cw + _pw)) > 0.01:
                    _msg = (
                        f"[LOT_TOTAL_MISMATCH] {_r.get('lot_no')}: "
                        f"initial={_iw}kg ≠ current({_cw})+picked({_pw})={_cw+_pw}kg"
                    )
                    logger.error(_msg)
                    _post_errors.append(_msg)

            _sample_rows = self.db.fetchall(
                "SELECT lot_no, COUNT(*) AS cnt FROM inventory_tonbag "
                "WHERE is_sample=1 AND lot_no IN (%s) GROUP BY lot_no" %
                ','.join('?' * len(touched_lots)),
                tuple(touched_lots)
            )
            for _sr in (_sample_rows or []):
                _cnt = int(_sr.get('cnt') or 0)
                if _cnt != 1:
                    _msg = (
                        f"[SAMPLE_POLICY_BROKEN] {_sr.get('lot_no')}: "
                        f"샘플 {_cnt}개 (정책: 1개)"
                    )
                    logger.error(_msg)
                    _post_errors.append(_msg)

            if _post_errors:
                result['post_check_errors'] = _post_errors
                result['message'] += f" ⚠ 사후검증 {len(_post_errors)}건 오류"
            else:
                logger.info("[POST_OUTBOUND] LOT_TOTAL + SAMPLE_POLICY 검증 통과")
        except Exception as _pe:
            logger.debug(f"[POST_OUTBOUND] 사후검증 스킵: {_pe}")

    # ── confirm_outbound 메인 ────────────────────────────────

    def confirm_outbound(self, lot_no: str = None, force_all: bool = False) -> Dict:
        """
        PICKED → OUTBOUND 확정 (SOLD는 레거시 호환 표현).

        Args:
            lot_no: 특정 LOT 지정. None이면 전체 (force_all=True 필수)
            force_all: lot_no=None 전체 확정 시 반드시 True로 명시

        Returns:
            {'success': bool, 'confirmed': int}
        """
        result = {'success': False, 'confirmed': 0, 'errors': []}

        # [H1] lot_no=None 전체 확정 — force_all=True 없으면 hard-stop
        if not lot_no and not force_all:
            _h1_msg = (
                "[CONFIRM_ALL_BLOCKED] lot_no 미지정 전체 확정은 "
                "force_all=True 명시 필수 — 실수 호출 차단"
            )
            logger.error(_h1_msg)
            result['errors'].append(_h1_msg)
            return result

        if not lot_no and force_all:
            logger.warning(
                "[CONFIRM_ALL_WARNING] lot_no 미지정 — 전체 PICKED 톤백 일괄 확정 모드 "
                "(force_all=True 명시 확인됨)"
            )
            result.setdefault('warnings', []).append("전체 PICKED 톤백 일괄 확정 모드")

        try:
            # 1) PICKED 톤백 로드
            tonbags = self._co_load_picked_tonbags(lot_no)
            if not tonbags:
                result['message'] = "확정할 톤백 없음"
                return result

            # 2) 이중 출고 차단
            if self._co_guard_against_double_outbound(tonbags, result):
                return result

            # 3) sale_ref/customer 혼재 검증
            if self._co_validate_customer_sale_ref(tonbags, result):
                return result

            # 4) 트랜잭션: 상태변경 + sold_table + movement + lot 재계산
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with self.db.transaction("IMMEDIATE"):
                touched_lots = set()
                # 톤백 STATUS 일괄 OUTBOUND 전환
                _upd_rows = [
                    (STATUS_OUTBOUND, now, now, tb['id']) for tb in tonbags
                ]
                self.db.executemany(
                    "UPDATE inventory_tonbag SET status = ?, outbound_date = ?, updated_at = ? WHERE id = ?",
                    _upd_rows
                )
                for tb in tonbags:
                    self._co_insert_sold_row(tb, now)
                    self._co_insert_outbound_movement(tb, now)
                    result['confirmed'] += 1
                    if tb.get('lot_no'):
                        touched_lots.add(tb['lot_no'])
                for lot in touched_lots:
                    self._recalc_lot_status(lot)

            result['success'] = result['confirmed'] > 0
            result['message'] = f"출고 확정: {result['confirmed']}건 OUTBOUND"

            # 5) 출고 확정 후 touched_lots 전체 재계산
            for _ln in touched_lots:
                if hasattr(self, '_recalc_current_weight'):
                    self._recalc_current_weight(_ln, reason='P2_CONFIRM_OUTBOUND')

            # 6) 사후검증: LOT_TOTAL_MISMATCH + SAMPLE_POLICY
            self._co_run_post_checks(touched_lots, result)

        except (ValueError, TypeError, sqlite3.Error) as e:
            logger.error(f"출고 확정 오류: {e}")
            result['errors'].append(str(e))

        return result

    def gate1_verify_picking(
        self,
        picking_result,
        picking_no: str = '',
    ) -> dict:
        """
        Gate-1: 피킹리스트 LOT ↔ allocation_plan RESERVED LOT 교차검증.

        v6.12.1 강화:
        - LOT 존재 여부 대조 (기존)
        - 톤백 수/무게 대조 (신규): 피킹 요청 수량 vs RESERVED 수량
        - 결과 상세 리포트 생성
        """
        result = {
            'passed': False,
            'requires_approval': False,
            'fail_code': '',
            'picking_lots': set(),
            'reserved_lots': set(),
            'only_in_picking': set(),
            'only_in_reserved': set(),
            'matched_lots': set(),
            'qty_mismatches': [],       # v6.12.1: 수량 불일치 상세
            'lot_details': [],          # v6.12.1: LOT별 상세 비교
            'error_report': '',
        }
        try:
            # --- 피킹 LOT 추출 ---
            if hasattr(picking_result, 'tonbag'):
                picking_lots = {getattr(item, 'lot_no', str(item.get('lot_no', '')))
                                for item in picking_result.tonbag}
            elif isinstance(picking_result, dict) and 'items' in picking_result:
                picking_lots = {item['lot_no'] for item in picking_result['items']
                                if item.get('lot_no')}
            else:
                picking_lots = set()

            result['picking_lots'] = picking_lots
            if not picking_lots:
                result['error_report'] = 'Gate-1 실패: 피킹 LOT 없음'
                return result

            # --- 피킹 LOT별 요청 수량 집계 ---
            picking_qty = {}  # {lot_no: {'qty_kg': float, 'tonbag_count': int}}
            if hasattr(picking_result, 'tonbag'):
                for item in picking_result.tonbag:
                    lot = getattr(item, 'lot_no', '')
                    kg = getattr(item, 'qty_kg', 0) or getattr(item, 'weight_kg', 0) or 0
                    if lot:
                        if lot not in picking_qty:
                            picking_qty[lot] = {'qty_kg': 0, 'tonbag_count': 0}
                        picking_qty[lot]['qty_kg'] += float(kg)
                        picking_qty[lot]['tonbag_count'] += 1
            elif isinstance(picking_result, dict):
                for item in picking_result.get('items', []):
                    lot = item.get('lot_no', '')
                    kg = float(item.get('qty_kg', 0) or 0)
                    if lot:
                        if lot not in picking_qty:
                            picking_qty[lot] = {'qty_kg': 0, 'tonbag_count': 0}
                        picking_qty[lot]['qty_kg'] += kg
                        picking_qty[lot]['tonbag_count'] += 1

            # --- DB 대조 ---
            placeholders = ','.join('?' * len(picking_lots))
            rows = self.db.fetchall(
                f"""SELECT DISTINCT lot_no FROM allocation_plan
                    WHERE status = 'RESERVED' AND lot_no IN ({placeholders})""",
                tuple(picking_lots)
            )
            reserved_in_db = {r['lot_no'] for r in rows}
            all_reserved = self.db.fetchall(
                "SELECT DISTINCT lot_no FROM allocation_plan WHERE status = 'RESERVED'"
            )
            all_reserved_lots = {r['lot_no'] for r in all_reserved}
            result['reserved_lots'] = all_reserved_lots

            only_in_picking = picking_lots - reserved_in_db
            only_in_reserved = all_reserved_lots - picking_lots
            matched = picking_lots & reserved_in_db
            result['only_in_picking'] = only_in_picking
            result['only_in_reserved'] = only_in_reserved
            result['matched_lots'] = matched

            # --- v6.9.1 [FIX-1]: Picking Qty > Available TONBAG 검증 ---
            # oversell 방지 핵심 검증
            avail_short = []
            for lot_no in sorted(picking_lots):
                pk = picking_qty.get(lot_no, {})
                pk_count = pk.get('tonbag_count', 0)
                if pk_count == 0:
                    continue
                avail_row = self.db.fetchone(
                    "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                    "WHERE lot_no=? AND status='AVAILABLE' AND COALESCE(is_sample,0)=0",
                    (lot_no,)
                )
                avail_cnt = int((avail_row.get('cnt') if isinstance(avail_row, dict)
                                 else (avail_row[0] if avail_row else 0)) or 0)
                if pk_count > avail_cnt:
                    avail_short.append(
                        f"LOT {lot_no}: 피킹요청 {pk_count}개 > AVAILABLE {avail_cnt}개 "
                        f"(oversell 위험)"
                    )
            result['avail_short'] = avail_short

            # --- v6.9.1 [FIX-2]: only_in_picking HARD-STOP 강화 ---
            # RESERVED 없는 LOT가 피킹에 있으면 requires_approval 없이 즉시 차단

            qty_mismatches = []
            lot_details = []
            for lot_no in sorted(matched):
                # DB에서 RESERVED 톤백 수/총 무게 조회
                # v6.9.6 [PK-10-FIX]: LOT 모드(tonbag_id=NULL) JOIN 버그 수정
                # 기존: JOIN inventory_tonbag → tonbag_id=NULL 시 항상 0,0 반환
                # 수정: tonbag_id NULL 여부 분기 → LOT 모드는 qty_mt 합산으로 계산
                _lot_mode_chk = self.db.fetchone(
                    "SELECT COUNT(*) AS cnt FROM allocation_plan "
                    "WHERE lot_no=? AND status='RESERVED' AND tonbag_id IS NULL",
                    (lot_no,)
                )
                _is_lot_mode = int(_lot_mode_chk.get('cnt', 0) if _lot_mode_chk else 0) > 0

                if _is_lot_mode:
                    # LOT 모드: qty_mt 직접 합산 (v8.6.0: COUNT*500 하드코딩 제거)
                    # → SUM(qty_mt*1000)으로 500/1000kg 톤백 모두 정확히 처리
                    db_row = self.db.fetchone(
                        """SELECT COUNT(*) AS plan_count,
                                  COALESCE(SUM(CASE WHEN qty_mt >= 0.01 THEN qty_mt * 1000 ELSE 0 END), 0) AS total_kg
                           FROM allocation_plan
                           WHERE lot_no = ? AND status = 'RESERVED'""",
                        (lot_no,)
                    )
                    db_count = db_row['plan_count'] if db_row else 0
                    db_kg = float(db_row['total_kg']) if db_row else 0
                else:
                    # TONBAG 모드 (구버전 호환): inventory_tonbag JOIN
                    db_row = self.db.fetchone(
                        """SELECT COUNT(*) AS tb_count,
                                  COALESCE(SUM(t.weight), 0) AS total_kg
                           FROM allocation_plan ap
                           JOIN inventory_tonbag t ON t.id = ap.tonbag_id
                           WHERE ap.lot_no = ? AND ap.status = 'RESERVED'""",
                        (lot_no,)
                    )
                    db_count = db_row['tb_count'] if db_row else 0
                    db_kg = float(db_row['total_kg']) if db_row else 0

                pk = picking_qty.get(lot_no, {'qty_kg': 0, 'tonbag_count': 0})
                pk_kg = pk['qty_kg']
                pk_count = pk['tonbag_count']

                detail = {
                    'lot_no': lot_no,
                    'picking_kg': pk_kg,
                    'picking_count': pk_count,
                    'reserved_kg': db_kg,
                    'reserved_count': db_count,
                    'kg_match': abs(pk_kg - db_kg) < 1.0,
                    'count_match': pk_count == 0 or pk_count == db_count,
                }
                lot_details.append(detail)

                if not detail['kg_match']:
                    qty_mismatches.append(
                        f"LOT {lot_no}: 피킹 {pk_kg:,.0f}kg vs RESERVED {db_kg:,.0f}kg "
                        f"(차이: {abs(pk_kg - db_kg):,.0f}kg)"
                    )

            result['qty_mismatches'] = qty_mismatches
            result['lot_details'] = lot_details

            # --- 리포트 생성 ---
            lines = [
                '=' * 60,
                f'[Gate-1 교차검증] {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                f'피킹리스트: {picking_no}',
                f'피킹 LOT: {len(picking_lots)}개 | RESERVED: {len(all_reserved_lots)}개 | 매칭: {len(matched)}개',
                '',
            ]

            # LOT 존재 불일치
            if only_in_picking:
                lines.append(f'❌ 피킹에만 있고 RESERVED 없는 LOT ({len(only_in_picking)}개):')
                for lot in sorted(only_in_picking)[:10]:
                    lines.append(f'   - {lot}')
                if len(only_in_picking) > 10:
                    lines.append(f'   ... 외 {len(only_in_picking)-10}개')
                lines.append('')

            if only_in_reserved:
                lines.append(f'⚠️ RESERVED에만 있고 피킹 없는 LOT ({len(only_in_reserved)}개):')
                for lot in sorted(only_in_reserved)[:10]:
                    lines.append(f'   - {lot}')
                lines.append('')

            # v6.12.1: 수량 불일치
            if qty_mismatches:
                lines.append(f'⚠️ 수량 불일치 ({len(qty_mismatches)}건):')
                for m in qty_mismatches[:10]:
                    lines.append(f'   - {m}')
                if len(qty_mismatches) > 10:
                    lines.append(f'   ... 외 {len(qty_mismatches)-10}건')
                lines.append('')

            # 매칭 LOT 요약
            if lot_details:
                ok_count = sum(1 for d in lot_details if d['kg_match'])
                lines.append(f'📊 매칭 LOT 수량 검증: {ok_count}/{len(lot_details)} 일치')
                lines.append('')

            # 최종 판정
            if only_in_picking:
                # v6.9.1 [FIX-2]: RESERVED 없는 LOT → 즉시 HARD-STOP (승인 불가)
                result['passed'] = False
                result['requires_approval'] = False
                result['fail_code'] = 'LOT_NOT_RESERVED'
                lines.append(f'🚫 Gate-1 HARD-STOP — RESERVED 없는 LOT {len(only_in_picking)}개')
                lines.append('   allocation_plan 확인 후 재시도하세요')
            elif avail_short:
                # v6.9.1 [FIX-1]: AVAILABLE 부족 → HARD-STOP
                result['passed'] = False
                result['requires_approval'] = False
                result['fail_code'] = 'AVAIL_INSUFFICIENT'
                lines.append(f'🚫 Gate-1 HARD-STOP — AVAILABLE 부족 (oversell 위험) {len(avail_short)}건')
                for s in avail_short[:5]:
                    lines.append(f'   - {s}')
            elif qty_mismatches:
                # v6.9.6 [PK-10 AUTO-REPAIR]: Picking < RESERVED → 초과 예약 자동 CANCELLED
                # Picking > RESERVED → HARD STOP (과피킹)
                auto_repaired = []
                hard_stop_lots = []
                for d in lot_details:
                    if not d['kg_match']:
                        pk_kg = d['picking_kg']
                        db_kg = d['reserved_kg']
                        lot_no_d = d['lot_no']
                        if pk_kg < db_kg:
                            # Picking < RESERVED → 초과분 allocation_plan CANCELLED
                            # 초과 건수 계산 (MT 기준 역산)
                            _excess_kg = db_kg - pk_kg
                            _unit_mt = self.db.fetchone(
                                "SELECT qty_mt FROM allocation_plan "
                                "WHERE lot_no=? AND status='RESERVED' "
                                "ORDER BY id DESC LIMIT 1",
                                (lot_no_d,)
                            )
                            _unit = float(_unit_mt.get('qty_mt', 0.5)) if _unit_mt else 0.5
                            _cancel_count = max(1, round(_excess_kg / (_unit * 1000)))
                            # 초과 plan CANCELLED (최신 순)
                            _excess_plans = self.db.fetchall(
                                "SELECT id FROM allocation_plan "
                                "WHERE lot_no=? AND status='RESERVED' "
                                "ORDER BY id DESC LIMIT ?",
                                (lot_no_d, _cancel_count)
                            )
                            for _ep in _excess_plans:
                                try:
                                    from datetime import datetime as _dt
                                    self.db.execute(
                                        "UPDATE allocation_plan "
                                        "SET status='CANCELLED', "
                                        "cancelled_at=? "
                                        "WHERE id=?",
                                        (_dt.now().strftime('%Y-%m-%d %H:%M:%S'), _ep['id'])
                                    )
                                except Exception as _ce:
                                    logger.warning(f"[PK-10 AUTO-REPAIR] CANCEL 실패: {_ce}")
                            auto_repaired.append(
                                f"LOT {lot_no_d}: 피킹 {pk_kg:,.0f}kg < RESERVED {db_kg:,.0f}kg "
                                f"→ 초과 {_cancel_count}건 자동 취소"
                            )
                            logger.info(
                                f"[PK-10 AUTO-REPAIR] {lot_no_d}: "
                                f"초과예약 {_cancel_count}건 CANCELLED "
                                f"(picking={pk_kg:.0f}kg < reserved={db_kg:.0f}kg)"
                            )
                        elif pk_kg > db_kg:
                            # Picking > RESERVED → HARD STOP
                            hard_stop_lots.append(
                                f"LOT {lot_no_d}: 피킹 {pk_kg:,.0f}kg > RESERVED {db_kg:,.0f}kg "
                                f"(과피킹 — 추가 Allocation 필요)"
                            )

                if hard_stop_lots:
                    result['passed'] = False
                    result['requires_approval'] = False
                    result['fail_code'] = 'OVER_PICKING'
                    lines.append(f'🚫 Gate-1 HARD-STOP — 과피킹 {len(hard_stop_lots)}건 (RESERVED 초과)')
                    for h in hard_stop_lots[:5]:
                        lines.append(f'   - {h}')
                    result['auto_repaired'] = auto_repaired
                elif auto_repaired:
                    lines.append(f'🔧 Gate-1 AUTO-REPAIR — 초과 예약 {len(auto_repaired)}건 자동 취소')
                    for ar in auto_repaired[:5]:
                        lines.append(f'   ✅ {ar}')
                    result['passed'] = True
                    result['auto_repaired'] = auto_repaired
                    result['fail_code'] = ''
                else:
                    lines.append('⚠️ Gate-1 승인 필요 — LOT 매칭 OK, 수량 불일치 있음')
                    lines.append('   관리자 승인 후 진행할 수 있습니다')
                    result['passed'] = False
                    result['requires_approval'] = True
                    result['fail_code'] = 'QTY_MISMATCH'
            else:
                lines.append('✅ Gate-1 완전 통과 — LOT 매칭 + 수량 검증 모두 OK')
                result['passed'] = True

            lines.append('=' * 60)
            result['error_report'] = '\n'.join(lines)
            logger.info('[Gate-1] passed=%s, matched=%s, missing=%s, qty_mismatch=%s',
                        result['passed'], len(matched), len(only_in_picking), len(qty_mismatches))
        except (sqlite3.Error, AttributeError) as e:
            result['error_report'] = f'Gate-1 DB 오류: {e}'
            logger.error(f'[Gate-1] 오류: {e}', exc_info=True)
        return result

    @staticmethod
    # DEAD CODE REMOVED v8.6.4: _gate1_to_json()
    # 사유: 전체 코드베이스에서 호출 없음 (2026-03-28 감사)
    # 원본 15줄 제거

    def gate1_apply_picking_result(
        self,
        sale_ref: str,
        picking_result,
        picking_no: str = '',
        sales_order: str = '',
        allow_qty_mismatch: bool = False,
        approval_reason: str = '',
    ) -> dict:
        """Gate-1 결과를 저장하고 STEP4 스캔 대기 상태로만 전환한다.
        STEP3에서는 inventory_tonbag.status를 변경하지 않는다.
        """
        result = {'success': False, 'executed': 0, 'gate1': {}, 'errors': []}
        gate1 = self.gate1_verify_picking(picking_result, picking_no)
        result['gate1'] = gate1
        if gate1.get('requires_approval') and not allow_qty_mismatch:
            result['errors'].append('Gate-1 승인 필요: 수량 불일치(QTY_MISMATCH)')
            return result
        if not gate1.get('passed'):
            if gate1.get('requires_approval') and allow_qty_mismatch:
                pass
            else:
                result['errors'].append(gate1.get('error_report', 'Gate-1 실패'))
                return result
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            cols = {str(r.get('name','')).strip().lower() for r in (self.db.fetchall('PRAGMA table_info(allocation_plan)') or [])}
            has_process_state = 'process_state' in cols
            has_gate1_checked_at = 'gate1_checked_at' in cols
            has_gate1_json_path = 'gate1_json_path' in cols
            has_gate1_report_path = 'gate1_report_path' in cols
            has_gate1_requires_approval = 'gate1_requires_approval' in cols
            has_gate1_approved_by = 'gate1_approved_by' in cols
            has_qc_status = 'qc_status' in cols
            has_qc_reason = 'qc_reason' in cols
            gate1_json_path = ''
            gate1_report_path = ''
            try:
                gate1_json_path = self._save_gate1_result_json(gate1, picking_no) if hasattr(self, '_save_gate1_result_json') else ''
            except Exception:
                gate1_json_path = ''
            try:
                gate1_report_path = self._save_gate1_report(gate1, picking_no) if hasattr(self, '_save_gate1_report') else ''
            except Exception:
                gate1_report_path = ''
            with self.db.transaction('IMMEDIATE'):
                if gate1.get('requires_approval') and allow_qty_mismatch:
                    try:
                        self.db.execute(
                            "INSERT INTO audit_log(event_type, event_data, created_at) VALUES (?, ?, ?)",
                            ('OUTBOUND_QTY_MISMATCH_APPROVED', json.dumps({
                                'picking_no': picking_no, 'sales_order': sales_order,
                                'fail_code': gate1.get('fail_code', 'QTY_MISMATCH'),
                                'approval_reason': approval_reason or ''
                            }, ensure_ascii=False), now),
                        )
                    except Exception:
                        logger.debug("[SUPPRESSED] exception in outbound_mixin.py")  # noqa
                matched_lots = list(gate1.get('matched_lots', []))
                # [M] v6.8.4: matched_lots 빈값 → 명시적 오류
                if not matched_lots:
                    _m_err = (
                        "[GATE1_NO_MATCH] Gate-1 통과했으나 매칭 LOT 없음 "
                        "— 피킹리스트 LOT 번호 확인"
                    )
                    logger.error(_m_err)
                    result['errors'].append(_m_err)
                    return result
                for lot_no in matched_lots:
                    sets = []
                    vals = []
                    if has_process_state:
                        sets.append("process_state = ?")
                        vals.append('GATE1_PASSED')
                    if has_gate1_checked_at:
                        sets.append("gate1_checked_at = ?")
                        vals.append(now)
                    if has_gate1_json_path:
                        sets.append("gate1_json_path = ?")
                        vals.append(gate1_json_path)
                    if has_gate1_report_path:
                        sets.append("gate1_report_path = ?")
                        vals.append(gate1_report_path)
                    if has_gate1_requires_approval:
                        sets.append("gate1_requires_approval = ?")
                        vals.append(1 if gate1.get('requires_approval') else 0)
                    if has_gate1_approved_by:
                        sets.append("gate1_approved_by = ?")
                        vals.append((os.environ.get('USERNAME', '') or os.environ.get('USER', '') or 'system') if allow_qty_mismatch else '')
                    if has_qc_status:
                        sets.append("qc_status = ?")
                        vals.append('OK' if gate1.get('passed') else 'WARN')
                    if has_qc_reason:
                        sets.append("qc_reason = ?")
                        vals.append(gate1.get('fail_code', '') or '')
                    if sets:
                        vals.extend([lot_no, 'RESERVED'])
                        self.db.execute(
                            f"UPDATE allocation_plan SET {', '.join(sets)} WHERE lot_no = ? AND status = ?",
                            tuple(vals),
                        )
                # ── v6.9.2 [FIX-5]: 부분 출고 — 초과 RESERVED 톤백 AVAILABLE 복귀 ──
                # 예) Alloc=10, Pick=8 → 2개를 allocation_plan 취소 + tonbag AVAILABLE 복귀
                reverted_total = 0
                for d in gate1.get('lot_details', []):
                    lot = d.get('lot_no', '')
                    pk_cnt = int(d.get('picking_count') or 0)
                    rv_cnt = int(d.get('reserved_count') or 0)
                    if lot and pk_cnt > 0 and rv_cnt > pk_cnt:
                        excess = rv_cnt - pk_cnt
                        # FIFO 기준 초과분 allocation_plan 조회 (created_at 내림차순 = 최신 것부터 취소)
                        excess_plans = self.db.fetchall(
                            """SELECT ap.id, ap.tonbag_id
                               FROM allocation_plan ap
                               JOIN inventory_tonbag tb ON tb.id = ap.tonbag_id
                               WHERE ap.lot_no = ? AND ap.status = 'RESERVED'
                               ORDER BY tb.sub_lt DESC
                               LIMIT ?""",
                            (lot, excess)
                        )
                        for ep in (excess_plans or []):
                            try:
                                self.db.execute(
                                    "UPDATE allocation_plan SET status='CANCELLED', "
                                    "cancelled_at=? WHERE id=?",
                                    (now, ep['id'])
                                )
                                self.db.execute(
                                    "UPDATE inventory_tonbag SET status='AVAILABLE', "
                                    "updated_at=? WHERE id=?",
                                    (now, ep['tonbag_id'])
                                )
                                reverted_total += 1
                            except Exception as _rv_e:
                                logger.warning(f"[v6.9.2] 초과 RESERVED 복귀 실패 {ep}: {_rv_e}")
                        if reverted_total:
                            self._recalc_lot_status(lot)
                            logger.info(
                                f"[v6.9.2] 부분 출고 복귀: LOT {lot} "
                                f"RESERVED {rv_cnt}개 중 {excess}개 → AVAILABLE"
                            )

                result['reverted_to_available'] = reverted_total
                result['success'] = len(matched_lots) > 0
                result['executed'] = len(matched_lots)
                result['json_path'] = gate1_json_path
                result['report_path'] = gate1_report_path
                result['message'] = (
                    f'Gate-1 검증 완료: {len(matched_lots)}개 LOT / STEP4 스캔 대기'
                    + (f' / 초과 예약 {reverted_total}개 → AVAILABLE 복귀' if reverted_total else '')
                )
        except Exception as e:
            logger.error(f'[gate1_apply_picking_result] 오류: {e}', exc_info=True)
            result['errors'].append(str(e))
        return result

    def execute_from_picking(
        self,
        picking_result,
        picking_no: str = '',
        sales_order: str = '',
        allow_qty_mismatch: bool = False,
        approval_reason: str = '',
    ) -> dict:
        """하위 호환용 래퍼. STEP3에서는 Gate-1 결과 저장만 수행한다."""
        return self.gate1_apply_picking_result(
            sale_ref=sales_order or picking_no,
            picking_result=picking_result,
            picking_no=picking_no,
            sales_order=sales_order,
            allow_qty_mismatch=allow_qty_mismatch,
            approval_reason=approval_reason,
        )

    def cancel_reservation(
        self,
        lot_no: str = None,
        plan_id: int = None,
        plan_ids: list = None,
        sale_ref: str = None,   # v7.7.1: sale_ref 일괄 취소 지원
        include_picked: bool = False,   # v8.6.5: PICKED 상태도 취소
        include_outbound: bool = False,  # v8.6.5: OUTBOUND 상태도 취소
    ) -> Dict:
        """
        RESERVED 예약 취소 → AVAILABLE 복원.
        plan_ids: 여러 건 일괄 취소 시 [id, ...] 전달.
        sale_ref: 판매참조번호 기준 일괄 취소 (v7.7.1).
        include_picked: True면 PICKED/EXECUTED 상태도 취소 (v8.6.5).
        include_outbound: True면 OUTBOUND/SOLD 상태도 취소 (v8.6.5).

        Returns:
            {'success': bool, 'cancelled': int}
        """
        result = {'success': False, 'cancelled': 0, 'errors': []}

        # v6.9.3 [CR-FIX-1]: plan_ids=[] HARD-STOP
        # 빈 리스트 전달 시 조건 없이 전체 취소되는 위험 차단
        if plan_ids is not None:
            if not isinstance(plan_ids, (list, tuple)) or len(plan_ids) == 0:
                result['message'] = "취소할 배정(plan_ids)이 비어 있습니다."
                result['errors'].append("[EMPTY_PLAN_IDS] plan_ids=[] — 취소 대상 없음 (HARD-STOP)")
                return result

        # v6.9.3 [CR-FIX-1]: 모든 파라미터 None → 실수 전체 취소 방지
        if plan_ids is None and plan_id is None and lot_no is None and not sale_ref:
            result['message'] = "취소할 예약 없음"
            result['errors'].append("[NO_CANCEL_TARGET] lot_no/plan_id/plan_ids/sale_ref 중 하나는 반드시 지정 필요")
            return result

        # v8.6.5: 취소 대상 상태 범위 확장
        cancel_statuses = ['RESERVED', 'PENDING_APPROVAL', 'STAGED']
        if include_picked:
            cancel_statuses.extend(['PICKED', 'EXECUTED'])
        if include_outbound:
            cancel_statuses.extend(['OUTBOUND', 'SOLD', 'SHIPPED', 'CONFIRMED'])
        status_ph = ','.join('?' * len(cancel_statuses))
        query = f"SELECT id, lot_no, tonbag_id, status FROM allocation_plan WHERE status IN ({status_ph})"
        params = list(cancel_statuses)
        if plan_ids:
            query += " AND id IN (" + ",".join("?" * len(plan_ids)) + ")"
            params.extend(plan_ids)
        else:
            if lot_no:
                query += " AND lot_no = ?"
                params.append(lot_no)
            if plan_id is not None:
                query += " AND id = ?"
                params.append(plan_id)
            # v7.7.1: sale_ref 기준 일괄 취소
            if sale_ref:
                query += " AND sale_ref = ?"
                params.append(str(sale_ref).strip())

        try:
            plans = self.db.fetchall(query, tuple(params))
            if not plans:
                result['message'] = "취소할 예약 없음"
                return result

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # v8.6.5: 상태 흐름 역방향 매핑 (직전 상태로 복원)
            # AVAILABLE → RESERVED → PICKED → OUTBOUND
            _PREV_STATUS_TONBAG = {
                'RESERVED': STATUS_AVAILABLE,
                'PENDING_APPROVAL': STATUS_AVAILABLE,
                'STAGED': STATUS_AVAILABLE,
                'PICKED': 'RESERVED',
                'EXECUTED': 'RESERVED',
                'OUTBOUND': STATUS_PICKED,
                'SOLD': STATUS_PICKED,
                'SHIPPED': STATUS_PICKED,
                'CONFIRMED': STATUS_PICKED,
            }
            _PREV_STATUS_PLAN = {
                'RESERVED': 'CANCELLED',
                'PENDING_APPROVAL': 'CANCELLED',
                'STAGED': 'CANCELLED',
                'PICKED': 'RESERVED',
                'EXECUTED': 'RESERVED',
                'OUTBOUND': 'PICKED',
                'SOLD': 'PICKED',
                'SHIPPED': 'PICKED',
                'CONFIRMED': 'PICKED',
            }

            with self.db.transaction("IMMEDIATE"):
                touched_lots = set()
                for plan in plans:
                    _tb_id = plan.get('tonbag_id') if isinstance(plan, dict) else plan[2]
                    _plan_id = plan.get('id') if isinstance(plan, dict) else plan[0]
                    _lot = plan.get('lot_no', '') if isinstance(plan, dict) else plan[1]
                    _cur_status = plan.get('status', 'RESERVED') if isinstance(plan, dict) else plan[3]

                    # 직전 상태 결정
                    _prev_tb = _PREV_STATUS_TONBAG.get(_cur_status, STATUS_AVAILABLE)
                    _prev_plan = _PREV_STATUS_PLAN.get(_cur_status, 'CANCELLED')

                    # 톤백 상태 → 직전 단계로 복원
                    if _tb_id:
                        if _prev_tb == STATUS_AVAILABLE:
                            # RESERVED → AVAILABLE: sale_ref/picked_to 초기화
                            self.db.execute(
                                """UPDATE inventory_tonbag SET
                                    status = ?, picked_to = NULL, sale_ref = NULL, updated_at = ?
                                WHERE id = ?""",
                                (_prev_tb, now, _tb_id))
                        elif _prev_tb == 'RESERVED':
                            # PICKED → RESERVED: outbound_date 초기화, picked_to 유지
                            self.db.execute(
                                """UPDATE inventory_tonbag SET
                                    status = ?, outbound_date = NULL, updated_at = ?
                                WHERE id = ?""",
                                (_prev_tb, now, _tb_id))
                        elif _prev_tb == STATUS_PICKED:
                            # OUTBOUND → PICKED: outbound_date 초기화
                            self.db.execute(
                                """UPDATE inventory_tonbag SET
                                    status = ?, outbound_date = NULL, updated_at = ?
                                WHERE id = ?""",
                                (_prev_tb, now, _tb_id))
                    else:
                        # LOT 모드: lot_no 기준 톤백 → 직전 상태
                        if _lot:
                            if _prev_tb == STATUS_AVAILABLE:
                                self.db.execute(
                                    """UPDATE inventory_tonbag SET
                                        status = ?, picked_to = NULL, sale_ref = NULL, updated_at = ?
                                    WHERE lot_no = ? AND status = ?""",
                                    (_prev_tb, now, _lot, _cur_status))
                            else:
                                self.db.execute(
                                    """UPDATE inventory_tonbag SET
                                        status = ?, outbound_date = NULL, updated_at = ?
                                    WHERE lot_no = ? AND status = ?""",
                                    (_prev_tb, now, _lot, _cur_status))

                    # OUTBOUND/SOLD → PICKED 복원 시: sold_table RETURNED 처리
                    if _cur_status in ('OUTBOUND', 'SOLD', 'SHIPPED', 'CONFIRMED') and _lot:
                        self.db.execute(
                            "UPDATE sold_table SET status='RETURNED' "
                            "WHERE lot_no=? AND status IN ('OUTBOUND','SOLD')",
                            (_lot,))

                    # allocation_plan → 직전 상태로 복원
                    self.db.execute(
                        """UPDATE allocation_plan SET status = ?, cancelled_at = ?
                        WHERE id = ?""",
                        (_prev_plan, now, _plan_id))
                    result['cancelled'] += 1

                    # stock_movement 이력
                    _mv_type = f"REVERT_{_cur_status}_TO_{_prev_tb}"
                    self.db.execute(
                        "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                        "VALUES (?, ?, 0, ?, ?)",
                        (_lot, _mv_type, f"plan_id={_plan_id} {_cur_status}→{_prev_plan}", now))
                    if _lot:
                        touched_lots.add(_lot)
                for lot_no in touched_lots:
                    self._recalc_lot_status(lot_no)
                    # v8.0.3 [P2]: RESERVED→AVAILABLE 후 current_weight 재계산
                    if hasattr(self, '_recalc_current_weight'):
                        self._recalc_current_weight(lot_no, reason='P2_CANCEL_RESERVATION')

            # v9.0 [AUDIT]: 수동 예약 취소 audit_log 기록
            if result.get('cancelled', 0) > 0:
                try:
                    import json as _json
                    self.db.execute(
                        "INSERT INTO audit_log(event_type, event_data, created_at) VALUES (?, ?, ?)",
                        (
                            'CANCEL_RESERVATION',
                            _json.dumps({
                                'cancelled': result['cancelled'],
                                'lot_no': lot_no,
                                'plan_id': plan_id,
                                'plan_ids': plan_ids,
                                'sale_ref': sale_ref,
                            }, ensure_ascii=False),
                            now
                        )
                    )
                    logger.debug("[cancel_reservation] audit_log 기록 완료: %d건", result['cancelled'])
                except Exception as _ae:
                    logger.debug("[cancel_reservation] audit_log 기록 실패(무시): %s", _ae)

            result['success'] = result['cancelled'] > 0
            result['message'] = f"예약 취소: {result['cancelled']}건"

        except (ValueError, TypeError, sqlite3.Error) as e:
            logger.error(f"예약 취소 오류: {e}")
            result['errors'].append(str(e))

        return result

    def revert_picked_to_reserved(self, lot_no: str = None) -> Dict:
        """
        판매화물 결정 취소: PICKED → 판매 배정(RESERVED)으로 되돌림.
        allocation_plan EXECUTED → RESERVED, inventory_tonbag PICKED → RESERVED.
        """
        result = {'success': False, 'reverted': 0, 'errors': []}
        query = """SELECT id, lot_no, tonbag_id FROM allocation_plan WHERE status IN ('EXECUTED','PICKED')"""
        params = [] if not lot_no else [lot_no]
        if lot_no:
            query += " AND lot_no = ?"
        try:
            rows = self.db.fetchall(query, tuple(params))
            if not rows:
                result['message'] = "되돌릴 판매화물 결정(EXECUTED) 건이 없습니다."
                return result
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with self.db.transaction("IMMEDIATE"):
                for r in rows:
                    tb_weight_row = self.db.fetchone(
                        "SELECT weight FROM inventory_tonbag WHERE id = ?", (r['tonbag_id'],)
                    )
                    _tb_w = float((tb_weight_row.get('weight') if isinstance(tb_weight_row, dict) else (tb_weight_row[0] if tb_weight_row else 0)) or 0)

                    self.db.execute(
                        """UPDATE allocation_plan SET status = 'RESERVED', executed_at = NULL WHERE id = ?""",
                        (r['id'],)
                    )
                    self.db.execute(
                        """UPDATE inventory_tonbag SET status = ?, picked_date = NULL, updated_at = ?
                           WHERE id = ?""",
                        (STATUS_RESERVED, now, r['tonbag_id'])
                    )
                    # v6.9.0 [C3]: current_weight 복구 — PICKED 전환 시 차감했던 무게 복원
                    if _tb_w > 0 and r.get('lot_no'):
                        self.db.execute(
                            """UPDATE inventory
                               SET current_weight = current_weight + ?,
                                   picked_weight  = MAX(0, picked_weight - ?),
                                   updated_at     = ?
                               WHERE lot_no = ?""",
                            (_tb_w, _tb_w, now, r['lot_no'])
                        )
                    result['reverted'] += 1
                    # v6.12.1: stock_movement 'REVERT_PICKED' 이력
                    self.db.execute(
                        "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                        "VALUES (?, 'REVERT_PICKED', ?, ?, ?)",
                        (r['lot_no'], _tb_w, f"plan_id={r['id']}, PICKED→RESERVED", now))
                    if hasattr(self, '_recalc_current_weight'):
                        self._recalc_current_weight(r['lot_no'], reason='P2_REVERT_PICKED_TO_RESERVED')
                    self._recalc_lot_status(r['lot_no'])
            result['success'] = True
            result['message'] = f"판매화물 결정 취소: {result['reverted']}건 → 판매 배정(RESERVED)"
        except (sqlite3.Error, ValueError, TypeError) as e:
            logger.error(f"revert_picked_to_reserved 오류: {e}")
            result['errors'].append(str(e))
        return result

    def revert_sold_to_picked(self, lot_no: str = None) -> Dict:
        """
        출고 취소: SOLD → AVAILABLE 직접 복귀.
        ★ v6.8.5 설계 원칙: 출고 취소 후 바로 AVAILABLE 복귀
        (PICKED 경유 없음 — 재출고 시 Allocation 재업로드 또는 즉시 가용)
        sold_table 해당 행 삭제, allocation_plan EXECUTED → CANCELLED,
        inventory current_weight 복구.
        """
        result = {'success': False, 'reverted': 0, 'errors': []}
        query = """SELECT id, lot_no, weight FROM inventory_tonbag WHERE status IN (?, ?)"""
        params = [STATUS_OUTBOUND, STATUS_SOLD]
        if lot_no:
            query += " AND lot_no = ?"
            params.append(lot_no)
        try:
            tonbags = self.db.fetchall(query, tuple(params))
            if not tonbags:
                result['message'] = "되돌릴 출고(SOLD) 톤백이 없습니다."
                return result
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with self.db.transaction("IMMEDIATE"):
                touched_lots = set()
                for tb in tonbags:
                    tb_id = tb['id']
                    # ★ v6.8.5: SOLD → AVAILABLE 직접 복귀
                    # 출고 취소 후 PICKED를 거치지 않고 바로 가용 상태로
                    _tb_w = float(tb.get('weight') or 0)
                    self.db.execute(
                        """UPDATE inventory_tonbag
                           SET status = ?, outbound_date = NULL,
                               picked_date = NULL, updated_at = ?
                           WHERE id = ?""",
                        (STATUS_AVAILABLE, now, tb_id)
                    )
                    # sold_table 삭제
                    try:
                        self.db.execute("DELETE FROM sold_table WHERE tonbag_id = ?", (tb_id,))
                    except sqlite3.OperationalError:
                        logger.debug("[SUPPRESSED] exception in outbound_mixin.py")  # noqa
                    # allocation_plan EXECUTED → ALLOC_CANCELLED
                    # v6.9.0 [M2]: cancelled_at 컬럼 존재 여부 안전 처리
                    try:
                        try:
                            _alloc_cols = {str(r.get('name','')).lower()
                                           for r in (self.db.fetchall("PRAGMA table_info(allocation_plan)") or [])}
                        except Exception:
                            _alloc_cols = set()
                        if 'cancelled_at' in _alloc_cols:
                            self.db.execute(
                                """UPDATE allocation_plan
                                   SET status = 'CANCELLED',
                                       cancelled_at = ?
                                   WHERE tonbag_id = ?
                                     AND status = 'EXECUTED'""",
                                (now, tb_id)
                            )
                        else:
                            self.db.execute(
                                """UPDATE allocation_plan
                                   SET status = 'CANCELLED'
                                   WHERE tonbag_id = ?
                                     AND status = 'EXECUTED'""",
                                (tb_id,)
                            )
                        logger.debug(
                            f"[I] allocation_plan EXECUTED→ALLOC_CANCELLED: "
                            f"tonbag_id={tb_id}"
                        )
                    except Exception as _ie:
                        logger.warning(f"[I allocation_plan CANCEL] 실패 tonbag_id={tb_id}: {_ie}")
                    # inventory 무게 복구 — picked_weight 차감, current_weight 복원
                    if _tb_w > 0 and tb.get('lot_no'):
                        try:
                            self.db.execute(
                                """UPDATE inventory
                                   SET current_weight = current_weight + ?,
                                       picked_weight  = MAX(0, picked_weight - ?),
                                       updated_at     = ?
                                   WHERE lot_no = ?""",
                                (_tb_w, _tb_w, now, tb['lot_no'])
                            )
                        except Exception as _iw:
                            logger.warning(f"[I inventory 무게복구] 실패: {_iw}")
                    result['reverted'] += 1
                    # stock_movement 'REVERT_SOLD' 이력
                    self.db.execute(
                        "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                        "VALUES (?, 'REVERT_SOLD', ?, ?, ?)",
                        (tb.get('lot_no', ''), _tb_w,
                         f"tonbag_id={tb_id}, SOLD→AVAILABLE", now))
                    if tb.get('lot_no'):
                        touched_lots.add(tb['lot_no'])
                for lot in touched_lots:
                    self._recalc_lot_status(lot)
            result['success'] = True
            result['message'] = f"출고 취소: {result['reverted']}건 → 가용(AVAILABLE) 복귀"
            # v8.0.3 [P2]: revert 후 touched_lots 재계산
            for _ln in touched_lots:
                if hasattr(self, '_recalc_current_weight'):
                    self._recalc_current_weight(_ln, reason='P2_REVERT_SOLD_TO_PICKED')
        except (sqlite3.Error, ValueError, TypeError) as e:
            logger.error(f"revert_sold_to_picked 오류: {e}")
            result['errors'].append(str(e))
        return result

    # ═══════════════════════════════════════════════════════
    # v6.2.4 Stage4: 빠른 출고 (Quick Outbound) — 성능 개선판
    # ═══════════════════════════════════════════════════════

    def quick_outbound(self, lot_no: str, count: int, customer: str,
                        reason: str = '', operator: str = '') -> Dict:
        """
        빠른 출고: Allocation 없이 소량 즉시 출고.
        최대 QUICK_OUTBOUND_MAX_TONBAGS개, AVAILABLE → PICKED 직접 전환.
        """
        import uuid
# [v6.8.6 top-level import로 이동]         from engine_modules.constants import QUICK_OUTBOUND_MAX_TONBAGS
        result = {
            'success': False, 'picked_count': 0,
            'total_weight_kg': 0, 'errors': []
        }

        if count > QUICK_OUTBOUND_MAX_TONBAGS:
            result['errors'].append(f"빠른 출고 최대 {QUICK_OUTBOUND_MAX_TONBAGS}개 (요청: {count}개)")
            return result
        customer = (customer or '').strip()
        if not customer:
            result['errors'].append("고객명 필수")
            return result
        lot_no = str(lot_no).strip()
        if not lot_no:
            result['errors'].append("LOT 번호 필요")
            return result

        try:
            with self.db.transaction("IMMEDIATE"):
                tonbags = self.db.fetchall(
                    """SELECT id, sub_lt, weight, tonbag_uid FROM inventory_tonbag
                       WHERE lot_no = ? AND status = ? AND COALESCE(is_sample,0) = 0
                       ORDER BY sub_lt DESC LIMIT ?""",
                    (lot_no, STATUS_AVAILABLE, count))

                if len(tonbags) < count:
                    raise ValueError(f"가용 톤백 부족: {len(tonbags)}개 (요청: {count}개)")

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                quick_ref = f"QUICK-{now.replace(' ', '_').replace(':', '')}-{uuid.uuid4().hex[:6]}"
                total_weight = 0.0

                for tb in tonbags:
                    tb_w = tb['weight'] or 0
                    # AVAILABLE → PICKED 직접
                    self.db.execute(
                        """UPDATE inventory_tonbag
                           SET status = ?, picked_to = ?, sale_ref = ?,
                               picked_date = ?, outbound_date = ?, updated_at = ?
                           WHERE id = ?""",
                        (STATUS_PICKED, customer, quick_ref, now, now, now, tb['id']))

                    # allocation_plan EXECUTED 직접 적재
                    try:
                        self.db.execute(
                            """INSERT INTO allocation_plan
                               (lot_no, tonbag_id, sub_lt, customer, sale_ref,
                                qty_mt, status, source, source_file, executed_at, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, 'EXECUTED', 'QUICK', ?, ?, ?)""",
                            (lot_no, tb['id'], tb['sub_lt'], customer, quick_ref,
                             tb_w / 1000.0, f"reason={reason}, op={operator}", now, now))
                    except (sqlite3.OperationalError, OSError) as e:
                        if "source" in str(e).lower():
                            self.db.execute(
                                """INSERT INTO allocation_plan
                                   (lot_no, tonbag_id, sub_lt, customer, sale_ref,
                                    qty_mt, status, source_file, executed_at, created_at)
                                   VALUES (?, ?, ?, ?, ?, ?, 'EXECUTED', ?, ?, ?)""",
                                (lot_no, tb['id'], tb['sub_lt'], customer, quick_ref,
                                 tb_w / 1000.0, f"QUICK:reason={reason}:op={operator}", now, now))
                        else:
                            raise
                    # picking_table
                    try:
                        self.db.execute(
                            """INSERT INTO picking_table
                            (lot_no, tonbag_id, sub_lt, tonbag_uid, customer, qty_kg, status, picking_date, created_by, remark)
                            VALUES (?,?,?,?,?,?,'ACTIVE',?,'system',?)""",
                            (lot_no, tb['id'], tb['sub_lt'], tb.get('tonbag_uid') or '', customer, tb_w, now,
                             f"QUICK: {reason}, op={operator}"))
                    except Exception as e:
                        logger.debug(f"picking_table INSERT skipped in quick outbound: {e}")
                    total_weight += tb_w
                    result['picked_count'] += 1

                # v8.0.0 [P2]: inventory 중앙 재계산 함수로 교체
                if hasattr(self, '_recalc_current_weight'):
                    self._recalc_current_weight(lot_no, reason='QUICK_OUTBOUND_PICK')
                else:
                    self.db.execute(
                        "UPDATE inventory SET current_weight=MAX(0,current_weight-?), picked_weight=picked_weight+?, updated_at=? WHERE lot_no=?",
                        (total_weight, total_weight, now, lot_no))
                # stock_movement
                self.db.execute(
                    "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) VALUES (?,'QUICK_OUTBOUND',?,?,?)",
                    (
                        lot_no,
                        total_weight,
                        f"customer={customer}, reason={reason}, op={operator}, count={count}, ref={quick_ref}",
                        now,
                    ))

                self._recalc_lot_status(lot_no)
                if hasattr(self, 'verify_lot_integrity'):
                    integrity = self.verify_lot_integrity(lot_no)
                    if not integrity.get('valid', True):
                        err_list = integrity.get('errors', [])
                        err_msg = "; ".join(str(e) for e in err_list[:3])
                        raise ValueError(f"빠른 출고 정합성 실패 ({lot_no}): {err_msg}")

                result['success'] = True
                result['total_weight_kg'] = total_weight
                result['quick_ref'] = quick_ref
                result['message'] = f"빠른 출고: {result['picked_count']}개 → PICKED ({total_weight:,.0f}kg)"
                logger.info(result['message'])

        except (ValueError, TypeError) as e:
            result['errors'].append(str(e))
            logger.error(f"빠른 출고 검증 오류: {e}", exc_info=True)
        except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
            result['errors'].append(f"DB 오류: {e}")
            logger.error(f"빠른 출고 DB 오류: {e}", exc_info=True)
        except Exception as e:
            result['errors'].append(f"예기치 않은 오류: {e}")
            logger.error(f"빠른 출고 미예상 오류: {e}", exc_info=True)
        return result

    # =========================================================================
    # v7.0.0: _preflight_alloc_cols — allocation_plan 테이블 컬럼 존재 검사
    # =========================================================================
    @staticmethod
    # DEAD CODE REMOVED v8.6.4: _rfa_build_error_detail()
    # 사유: 전체 코드베이스에서 호출 없음 (2026-03-28 감사)
    # 원본 31줄 제거

    # ── RETURN_AS_REINBOUND: 입고 다이얼로그 재활용 모드 ──────────────────────
    def open_inbound_dialog_for_return(
        self,
        outbound_id: str,
        lot_no: str,
        customer: str,
        return_reason: str = '반품',
        operator_id: str = 'SYSTEM',
    ) -> dict:
        """
        반품 처리 시 기존 입고 다이얼로그를 mode='return'으로 재활용.

        RETURN_AS_REINBOUND 정책:
          1. Rack Scan  → 새 위치 스캔 (입고 프로세스와 동일)
          2. Tonbag Scan → 톤백 UID 확인 (입고 프로세스와 동일)
          3. ReturnReinboundEngine.process() 호출

        Args:
            outbound_id:   원출고 ID
            lot_no:        반품 LOT 번호
            customer:      고객사 명
            return_reason: 반품 사유
            operator_id:   작업자 ID

        Returns:
            {'ok': bool, 'return_id': str, 'new_location': str, 'error': str}

        Note:
            [v7.0.0 완료] GUI 통합은 ReturnReinboundDialog 로 완성됨.
            - inventory_tab._return_from_context() → ReturnReinboundDialog 직접 호출
            - tonbag_tab._on_tonbag_return()       → ReturnReinboundDialog 직접 호출
            - OneStopInboundDialog mode='return' 분기는 불필요 (ReturnReinboundDialog로 대체)
            이 메서드는 GUI 없는 환경(테스트/CLI)용 엔진 직접 호출 경로로 유지됨.
        """
        # GUI 없는 환경(테스트/CLI)에서는 엔진 직접 호출
        try:
            from engine_modules.return_reinbound_engine import (
                ReturnReinboundEngine,
            )
            # new_location은 GUI에서 PDA 스캔으로 받아옴
            # 테스트 환경에서는 자동 생성
            new_location = getattr(self, '_test_return_location', 'B-01-01-01')

            engine = ReturnReinboundEngine(self.conn if hasattr(self, 'conn') else None)
            if engine.conn is None:
                return {'ok': False, 'error': 'DB 연결 없음'}

            result = engine.process(
                outbound_id=outbound_id,
                lot_no=lot_no,
                new_location=new_location,
                operator_id=operator_id,
                reason=return_reason,
            )
            return {
                'ok':          result.ok,
                'return_id':   result.return_id,
                'new_location': result.new_location,
                'error':       result.error,
            }
        except ImportError:
            return {'ok': False, 'error': 'ReturnReinboundEngine import 실패'}

    def _preflight_alloc_cols(self) -> dict:
        """allocation_plan 테이블 컬럼 존재 여부 사전 검사.
        v8.2.2: dead code 제거 후 테스트 의존성으로 복구.
        반환: {cols: set, has_source: bool, has_line_no: bool,
               has_export_type: bool, has_workflow_status: bool, has_fail_code: bool}
        """
        try:
            rows = self.db.fetchall(
                "PRAGMA table_info(allocation_plan)"
            ) or []
            cols = set(
                (r.get('name') if isinstance(r, dict) else r[1])
                for r in rows
            )
            return {
                'cols':               cols,
                'has_source':         'source'          in cols,
                'has_line_no':        'line_no'         in cols,
                'has_export_type':    'export_type'     in cols,
                'has_workflow_status':'workflow_status' in cols,
                'has_fail_code':      'fail_code'       in cols,
            }
        except Exception as e:
            logger.debug(f"_preflight_alloc_cols 오류: {e}")
            return {
                'cols': set(),
                'has_source': False, 'has_line_no': False,
                'has_export_type': False, 'has_workflow_status': False,
                'has_fail_code': False,
            }

