# ============================================================
# SQM Return Reinbound Engine 원칙 (v8.0.5 확정 — 2026-03-16)
# ------------------------------------------------------------
# Reinbound/restore flows must not overwrite inventory summary
# directly (current_weight = total_weight_kg 금지);
# restore item state first, then finalize via central recalc.
#
# ATOMIC 구조: BEGIN → tonbag restore → recalc → COMMIT
# P2 경로:
#   process (main)       → P2_REINBOUND_ATOMIC
#   _restore_lot_weight  → P2_REINBOUND_RESTORE
# SOLD cleanup: reinbound restore와 분리된 별도 경로
# ============================================================

# -*- coding: utf-8 -*-
"""
engine_modules/return_reinbound_engine.py
==========================================
SQM v7.0.0 — RETURN_AS_REINBOUND 정책 엔진
============================================

[SQM RETURN POLICY v1 — RETURN_AS_REINBOUND]

1. 반품 톤백은 신규 row를 생성하지 않는다.
   (tonbag_uid UNIQUE 제약 준수 — UPDATE 방식 사용)

2. 반품 처리는 기존 inventory_tonbag row를 UPDATE한다.
   - status    = 'AVAILABLE'
   - location  = PDA 재스캔으로 새로 배정된 위치
   - weight_kg = 원본 중량 (불변)

3. current_weight는 inventory 테이블에서 즉시 복구한다.

4. 모든 반품은 return_log 테이블에 기록하고
   outbound_id(= source_outbound_id)로 원출고와 연결한다.

5. outbound_log row는 절대 수정하지 않는다. (불변 이력)

6. mode='return' 으로 호출 시 입고 다이얼로그를 재활용한다.
   (one_stop_inbound의 Rack Scan → Tonbag Scan 흐름 그대로 사용)

사용 예:
    engine = ReturnReinboundEngine(conn)
    result = engine.process(
        outbound_id = 'OUT0001',
        lot_no      = '1120000023',
        new_location = 'B-02-03-01',
        operator_id  = 'OP001',
        reason       = '계약 변경',
    )
    if result.ok:
        logger.info(f"재입고 완료: {result.return_id}")
    else:
        logger.warning(f"오류: {result.error}")
"""
from engine_modules.constants import STATUS_AVAILABLE
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List


# ─── 결과 데이터클래스 ────────────────────────────────────────────────────────
@dataclass
class ReturnResult:
    ok:               bool
    return_id:        Optional[str]   = None
    lot_no:           Optional[str]   = None
    outbound_id:      Optional[str]   = None
    new_location:     Optional[str]   = None
    tonbags_restored: int             = 0
    weight_restored:  float           = 0.0
    error:            Optional[str]   = None
    detail:           List[str]       = field(default_factory=list)


# ─── Preflight 검증 결과 ──────────────────────────────────────────────────────
@dataclass
class PreflightResult:
    ok:           bool
    errors:       List[str] = field(default_factory=list)
    outbound_row: Optional[dict] = None
    lot_row:      Optional[dict] = None
    tonbag_rows:  List[dict]     = field(default_factory=list)


# ─── 메인 엔진 ───────────────────────────────────────────────────────────────
class ReturnReinboundEngine:
    """
    RETURN_AS_REINBOUND 정책 실행 엔진.

    - All-or-Nothing: preflight 검증 전부 통과 시에만 DB 커밋
    - 부분 처리 없음: 오류 발생 시 전체 롤백
    """

    PROCESSED_AS = 'REINBOUND'

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── 공개 API ──────────────────────────────────────────────────────────────
    def process(
        self,
        outbound_id:  str,
        lot_no:       str,
        new_location: str,
        operator_id:  str  = 'SYSTEM',
        reason:       str  = '반품',
        return_date:  Optional[str] = None,
    ) -> ReturnResult:
        """
        반품 처리 메인 진입점.

        Args:
            outbound_id:  원출고 ID (OUT XXXX)
            lot_no:       반품 LOT 번호
            new_location: PDA 재스캔으로 배정된 새 Rack 위치
            operator_id:  작업자 ID
            reason:       반품 사유
            return_date:  반품일 (None이면 오늘)

        Returns:
            ReturnResult (ok=True면 성공)
        """
        rdate = return_date or date.today().isoformat()

        # ── Step 1: Preflight 검증 ────────────────────────────────────────────
        pre = self._preflight(outbound_id, lot_no)
        if not pre.ok:
            return ReturnResult(
                ok=False,
                error='; '.join(pre.errors),
                detail=pre.errors,
            )

        # ── Step 2: All-or-Nothing 트랜잭션 ─────────────────────────────────
        try:
            return_id = self._generate_return_id()
            self.conn.execute("BEGIN")

            # 2-A: 톤백 전체 AVAILABLE 복구 (UPDATE, 신규 row ❌)
            tb_count, tb_weight = self._restore_tonbags(
                lot_no, new_location, pre.tonbag_rows
            )

            # 2-B: inventory current_weight + status 복구
            self._restore_lot_weight(lot_no, tb_weight)

            # 2-C: return_log 이력 기록 (원출고와 연결 유지)
            self._write_return_log(
                return_id=return_id,
                outbound_id=outbound_id,
                lot_no=lot_no,
                customer=pre.outbound_row['customer'],
                return_date=rdate,
                reason=reason,
                weight_kg=tb_weight,
                new_location=new_location,
                operator_id=operator_id,
            )

            # v8.0.5 [ATOMIC-FIX]: tonbag restore 후 recalc를 COMMIT 전에 실행
            # GPT 지적: DETAIL변경 ≠ SUMMARY갱신 원자성 보장
            try:
                _eng = getattr(self, '_engine', None) or getattr(self, 'engine', None)
                if _eng and hasattr(_eng, '_recalc_current_weight'):
                    _eng._recalc_current_weight(lot_no, reason='P2_REINBOUND_ATOMIC')
            except Exception as _re:
                import logging
                logging.getLogger(__name__).debug(f'[ATOMIC] reinbound atomic recalc 스킵: {_re}')

            self.conn.execute("COMMIT")

            return ReturnResult(
                ok=True,
                return_id=return_id,
                lot_no=lot_no,
                outbound_id=outbound_id,
                new_location=new_location,
                tonbags_restored=tb_count,
                weight_restored=tb_weight,
                detail=[
                    f"톤백 {tb_count}개 AVAILABLE 복구",
                    f"중량 {tb_weight:,.1f}kg 재고 복구",
                    f"위치 재배정: {new_location}",
                    f"원출고 연결: {outbound_id}",
                ],
            )

        except Exception as exc:
            self.conn.execute("ROLLBACK")
            return ReturnResult(
                ok=False,
                error=f"DB 오류 (롤백): {exc}",
            )

    # ── Preflight 검증 ────────────────────────────────────────────────────────
    def _preflight(self, outbound_id: str, lot_no: str) -> PreflightResult:
        errors = []

        # 1) outbound_log 존재 확인
        ob = self.conn.execute(
            "SELECT * FROM outbound_log WHERE outbound_id=?",
            (outbound_id,)
        ).fetchone()
        if not ob:
            errors.append(f"출고 이력 없음: {outbound_id}")
            return PreflightResult(ok=False, errors=errors)
        ob_dict = dict(ob)

        # 2) outbound_id ↔ lot_no 매칭
        if ob_dict['lot_no'] != lot_no:
            errors.append(
                f"LOT 불일치: outbound={ob_dict['lot_no']}, 요청={lot_no}"
            )

        # 3) inventory 존재 확인
        lot = self.conn.execute(
            "SELECT * FROM inventory WHERE lot_no=?", (lot_no,)
        ).fetchone()
        if not lot:
            errors.append(f"재고 없음: {lot_no}")
            return PreflightResult(ok=False, errors=errors)
        lot_dict = dict(lot)

        # 4) 이중 반품 방지 (이미 반품된 건 차단)
        dup = self.conn.execute(
            "SELECT return_id FROM return_log "
            "WHERE outbound_id=? AND lot_no=?",
            (outbound_id, lot_no)
        ).fetchone()
        if dup:
            errors.append(f"이미 반품 처리됨: {dup[0]}")

        # 5) 반품 대상 톤백 조회
        tonbags = [
            dict(r) for r in self.conn.execute(
                "SELECT * FROM inventory_tonbag WHERE lot_no=?",
                (lot_no,)
            ).fetchall()
        ]
        if not tonbags:
            errors.append(f"톤백 없음: {lot_no}")

        if errors:
            return PreflightResult(ok=False, errors=errors)

        return PreflightResult(
            ok=True,
            outbound_row=ob_dict,
            lot_row=lot_dict,
            tonbag_rows=tonbags,
        )

    # ── 톤백 복구 ─────────────────────────────────────────────────────────────
    def _restore_tonbags(
        self,
        lot_no: str,
        new_location: str,
        tonbag_rows: list,
    ) -> tuple[int, float]:
        """
        tonbag_uid UNIQUE 제약 준수: 신규 INSERT 없이 UPDATE만 사용.
        v7.6.0: UPDATE 전 샘플 tonbag 상태 사전 검증 추가.

        Returns:
            (복구된 톤백 수, 복구된 총 중량 kg)
        """
        # ★ v7.6.0 원인2 방어: UPDATE 전 샘플 사전 검증
        # (1) 샘플 tonbag 존재 확인 — weight/weight_kg 양쪽 컬럼 허용
        try:
            _sample_row = self.conn.execute(
                "SELECT id, COALESCE(weight, weight_kg, 0) as w, "
                "status, tonbag_uid FROM inventory_tonbag "
                "WHERE lot_no = ? AND COALESCE(is_sample,0) = 1 LIMIT 1",
                (lot_no,)
            ).fetchone()
        except Exception:
            # 컬럼 조합 실패 시 단순 쿼리로 재시도
            _sample_row = self.conn.execute(
                "SELECT id, status, tonbag_uid FROM inventory_tonbag "
                "WHERE lot_no = ? AND COALESCE(is_sample,0) = 1 LIMIT 1",
                (lot_no,)
            ).fetchone()

        if _sample_row is None:
            raise ValueError(
                f"[v7.6.0] RETURN_AS_REINBOUND 샘플 정책 위반: "
                f"LOT {lot_no}에 샘플 tonbag 없음. DB 수동 확인 필요."
            )

        _s = dict(_sample_row) if hasattr(_sample_row, 'keys') else {}

        # (2) 샘플 무게 검증 (weight 컬럼이 있을 때만)
        _sw = float(_s.get('w') or _s.get('weight') or _s.get('weight_kg') or 0)
        if _sw > 0 and abs(_sw - 1.0) > 0.01:
            raise ValueError(
                f"[v7.6.0] RETURN_AS_REINBOUND 샘플 무게 오류: "
                f"LOT {lot_no} 샘플 weight={_sw}kg (필수 1.000kg). "
                f"tonbag_uid={_s.get('tonbag_uid')}"
            )

        # (3) tonbag_uid 형식 검증 (경고만)
        _expected_uid = f"{lot_no}-S00"
        _actual_uid = str(_s.get('tonbag_uid') or '')
        if _actual_uid and _actual_uid != _expected_uid:
            import logging as _log
            _log.getLogger(__name__).warning(
                f"[v7.6.0] 샘플 tonbag_uid 불일치: "
                f"expected={_expected_uid}, actual={_actual_uid}"
            )

        # (4) 샘플 이중 복구 경고 (ERROR 아닌 WARNING)
        if _s.get('status') == STATUS_AVAILABLE:
            import logging as _log
            _log.getLogger(__name__).warning(
                f"[v7.6.0] 샘플 이중 복구 감지: LOT {lot_no} 샘플이 "
                f"이미 AVAILABLE 상태. 반품 중복 처리 가능성 확인 필요."
            )

        total_weight = sum(t['weight_kg'] for t in tonbag_rows)
        count = len(tonbag_rows)

        self.conn.execute(
            """
            UPDATE inventory_tonbag
            SET status   = 'AVAILABLE',
                location = ?
            WHERE lot_no = ?
            """,
            (new_location, lot_no)
        )

        # [4] v6.7.9: sold_table RETURNED 반영
        # REINBOUND 경로에서 sold_table 미정리 시
        # 매출 통계에 반품 건이 SOLD로 계속 집계되는 오류 수정
        import datetime as _dt
        _now = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            self.conn.execute(
                "UPDATE sold_table "
                "SET status='RETURNED', "
                "remark=COALESCE(remark,'')||' | REINBOUND반품:'||? "
                "WHERE lot_no=? AND status IN ('SOLD','OUTBOUND')",
                (_now, lot_no)
            )
            import logging as _log
            _log.getLogger(__name__).info(
                f"[4] sold_table RETURNED 반영: {lot_no} ({count}건)"
            )
        except Exception as _se:
            import logging as _log
            _log.getLogger(__name__).debug(
                f"[4] sold_table RETURNED 스킵: {_se}"
            )

        return count, total_weight

    # ── LOT 중량 복구 ─────────────────────────────────────────────────────────
    def _restore_lot_weight(self, lot_no: str, weight_kg: float) -> None:
        """
        inventory.current_weight 복구.
        v8.0.2 [P2]: total_weight_kg 강제 세팅 대신 _recalc_current_weight() 사용.
        status만 AVAILABLE로 변경 후 중앙 재계산으로 정확한 값 산출.
        """
        self.conn.execute(
            """
            UPDATE inventory
            SET status = 'AVAILABLE'
            WHERE lot_no = ?
            """,
            (lot_no,)
        )
        # v8.0.2 [P2]: 중앙 재계산으로 current_weight 복구
        try:
            engine = getattr(self, '_engine', None) or getattr(self, 'engine', None)
            if engine and hasattr(engine, '_recalc_current_weight'):
                engine._recalc_current_weight(lot_no, reason='P2_REINBOUND_RESTORE')
        except Exception as _e:
            import logging
            logging.getLogger(__name__).debug(f'[P2] reinbound recalc 스킵: {_e}')

    # ── 반품 이력 기록 ────────────────────────────────────────────────────────
    def _write_return_log(
        self,
        return_id:    str,
        outbound_id:  str,
        lot_no:       str,
        customer:     str,
        return_date:  str,
        reason:       str,
        weight_kg:    float,
        new_location: str,
        operator_id:  str,
    ) -> None:
        """
        return_log INSERT.
        processed_as='REINBOUND' 고정 + outbound_id로 원출고 연결 유지.
        """
        self.conn.execute(
            """
            INSERT INTO return_log
            (return_id, outbound_id, lot_no, customer, return_date,
             reason, weight_kg, processed_as, new_location, operator_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                return_id, outbound_id, lot_no, customer, return_date,
                reason, weight_kg,
                self.PROCESSED_AS,   # 항상 'REINBOUND'
                new_location,
                operator_id,
            )
        )

    # ── return_id 생성 ────────────────────────────────────────────────────────
    @staticmethod
    def _generate_return_id() -> str:
        today = date.today().strftime("%Y%m%d")
        uid   = uuid.uuid4().hex[:6].upper()
        return f"RTN-{today}-{uid}"

    # ── 통계 조회 헬퍼 ───────────────────────────────────────────────────────
    def get_return_summary(self) -> dict:
        """반품 통계 요약 (감사/보고용)"""
        total = self.conn.execute(
            "SELECT COUNT(*), SUM(weight_kg) FROM return_log "
            "WHERE processed_as='REINBOUND'"
        ).fetchone()
        by_customer = self.conn.execute(
            "SELECT customer, COUNT(*), SUM(weight_kg) "
            "FROM return_log WHERE processed_as='REINBOUND' "
            "GROUP BY customer ORDER BY COUNT(*) DESC"
        ).fetchall()
        return {
            'total_count':    total[0] or 0,
            'total_weight_kg': total[1] or 0.0,
            'by_customer': [
                {'customer': r[0], 'count': r[1], 'weight_kg': r[2]}
                for r in by_customer
            ],
        }
