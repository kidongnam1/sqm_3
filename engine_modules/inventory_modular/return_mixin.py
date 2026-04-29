# ============================================================
# SQM Return Mixin 원칙 (v8.0.5 확정 — 2026-03-16)
# ------------------------------------------------------------
# Return and recovery flows must restore item state first
# and must not repair inventory summary directly;
# lot totals must be finalized only by central recalc.
#
# 핵심 함수:
#   return_single_tonbag → P2_RETURN_SINGLE_TONBAG
#   bulk_return_by_lot   → P2_RETURN (각 lot)
#   finalize_return_to_available → IMMEDIATE 트랜잭션
#
# 상태 복귀 순서: tonbag RETURN → finalize → AVAILABLE
# ============================================================

"""
SQM Inventory Engine - Return Mixin
===================================

v2.9.91 - Extracted from inventory.py

Return (반품) processing functions
"""

from engine_modules.constants import (
    STATUS_AVAILABLE, STATUS_RESERVED, STATUS_PICKED,
    STATUS_RETURN, STATUS_SOLD,
    # 'OUTBOUND': SQL 문자열 'OUTBOUND' 직접 사용 (하위호환)
)  # v7.5.0: 하드코딩 상수 중앙화
import json
import logging
import sqlite3
from datetime import date, datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class ReturnMixin:
    """
    Return processing mixin
    
    Methods for processing returns (PICKED -> AVAILABLE)
    """

    def get_returnable_tonbags(self, lot_no: str = None) -> List[Dict]:
        """
        Get tonbags that can be returned.
        
        Args:
            lot_no: Optional filter by LOT number
            
        Returns:
            List of returnable tonbags
        """
        query = """
            SELECT 
                t.lot_no, t.sub_lt, t.weight, t.location,
                t.status, t.outbound_date, t.picked_to, t.sale_ref,
                i.sap_no, i.bl_no, i.product
            FROM inventory_tonbag t
            LEFT JOIN inventory i ON t.lot_no = i.lot_no
            WHERE t.status IN ('PICKED', 'CONFIRMED', 'SHIPPED', 'SOLD', 'RESERVED')
        """
        params = []

        if lot_no:
            query += " AND t.lot_no = ?"
            params.append(lot_no)

        query += " ORDER BY t.lot_no, t.sub_lt"

        return self.db.fetchall(query, tuple(params))

    def get_return_history(self, lot_no: str = None, limit: int = 100) -> List[Dict]:
        """
        Get return history
        
        Args:
            lot_no: Optional filter by LOT number
            limit: Maximum records to return
            
        Returns:
            List of return records
        """
        query = """
            SELECT 
                r.id, r.lot_no, r.sub_lt, r.return_date,
                r.original_customer, r.original_sale_ref,
                r.reason, r.remark, r.created_at,
                i.sap_no, i.product
            FROM return_history r
            LEFT JOIN inventory i ON r.lot_no = i.lot_no
            WHERE 1=1
        """
        params = []

        if lot_no:
            query += " AND r.lot_no = ?"
            params.append(lot_no)

        query += f" ORDER BY r.created_at DESC LIMIT {limit}"

        return self.db.fetchall(query, tuple(params))


    # ══════════════════════════════════════════════════════════════════════
    # v8.6.4: process_return 분해 — 서브메서드 3개
    # ══════════════════════════════════════════════════════════════════════

    def _ret_validate_sample_hard_stop(self, tonbag: dict, result: dict) -> bool:
        """v8.6.4: 샘플 반품 Hard Stop (process_return 분해 1/3).

        샘플(is_sample=1 or sub_lt=0)은 일반 반품 흐름과 완전 분리.
        Returns False → 반품 중단.
        """
        is_sample = int(tonbag.get('is_sample') or 0)
        sub_lt    = tonbag.get('sub_lt')
        if is_sample or sub_lt == 0:
            msg = (f"[T9][SAMPLE_RETURN] 샘플 톤백은 일반 반품 불가 "
                   f"(sub_lt={sub_lt}, is_sample={is_sample}). "
                   f"샘플 반품은 별도 처리 필요.")
            logger.warning(msg)
            result.setdefault('errors', []).append(msg)
            return False
        return True

    def _ret_cancel_allocation_plan(self, lot_no: str, sub_lt,
                                    tonbag_id) -> int:
        """v8.6.4: 반품 시 allocation_plan EXECUTED→CANCELLED 정리
        (process_return 분해 2/3).

        Returns:
            cancelled 행 수
        """
        import sqlite3 as _sq
        cancelled = 0
        try:
            # LOT 모드(sub_lt=NULL) + 톤백 모드(sub_lt 지정) 모두 처리
            for where, params in [
                ("lot_no=? AND sub_lt=? AND status='EXECUTED'",
                 (lot_no, sub_lt)),
                ("lot_no=? AND sub_lt IS NULL AND status='EXECUTED'",
                 (lot_no,)),
                ("lot_no=? AND tonbag_id=? AND status='EXECUTED'",
                 (lot_no, tonbag_id)),
            ]:
                r = self.db.execute(
                    f"UPDATE allocation_plan SET status='CANCELLED' WHERE {where}",
                    params
                )
                if hasattr(r, 'rowcount'):
                    cancelled += (r.rowcount or 0)
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[반품] allocation_plan CANCELLED 스킵: {e}")
        if cancelled:
            logger.info(f"[반품] {lot_no} allocation_plan {cancelled}건 CANCELLED")
        return cancelled

    def _ret_restore_inventory_weight(self, lot_no: str,
                                       weight_kg: float) -> None:
        """v8.6.4: PICKED/SOLD 반품 시 inventory current_weight 복구
        (process_return 분해 3/3).
        """
        import sqlite3 as _sq
        try:
            self.db.execute(
                """UPDATE inventory
                   SET current_weight = COALESCE(current_weight, 0) + ?,
                       updated_at = datetime('now')
                   WHERE lot_no = ?""",
                (weight_kg, lot_no)
            )
            logger.debug(f"[반품] inventory current_weight +{weight_kg}kg ({lot_no})")
        except (_sq.OperationalError, OSError) as e:
            logger.warning(f"[반품] current_weight 복구 실패 {lot_no}: {e}")

    def process_return(self, return_data: list,
                       source_type: str = '', source_file: str = '') -> Dict:
        """
        반품 처리 (v5.1.5: 정합성 게이트 + stock_movement 이력 + picked_date 초기화)
        
        Args:
            return_data: List of return items
                [{'lot_no': '...', 'sub_lt': 1, 'reason': '...', 'remark': '...'}, ...]
            source_type: 반품 출처 ('RETURN_SINGLE', 'RETURN_EXCEL', 'RETURN_PASTE')
            source_file: 원본 파일명 (감사 추적용)
            
        Returns:
            Processing result dict
        """
        result = {
            'success': False,
            'returned': 0,
            'skipped': 0,
            'errors': [],
            'details': [],
            'integrity': {},  # v5.1.5: LOT별 정합성 결과
        }

        if not return_data:
            result['errors'].append("No return data provided")
            return result

        try:
            with self.db.transaction("IMMEDIATE"):
                # v8.2.0 N+1 최적화: tonbag 일괄 pre-fetch
                _valid_items = [
                    (str(it.get('lot_no') or '').strip(), it.get('sub_lt'))
                    for it in return_data
                    if str(it.get('lot_no') or '').strip() and it.get('sub_lt') is not None
                ]
                _tb_cache = {}
                if _valid_items:
                    _all_lots_r = list(set(k[0] for k in _valid_items))
                    _ph_r = ','.join('?' * len(_all_lots_r))
                    _tb_rows_r = self.db.fetchall(
                        f"SELECT lot_no, sub_lt, weight, status, picked_to, sale_ref, is_sample "
                        f"FROM inventory_tonbag WHERE lot_no IN ({_ph_r})",
                        tuple(_all_lots_r)
                    ) or []
                    _tb_cache = {
                        (r.get('lot_no') if isinstance(r, dict) else r[0],
                         r.get('sub_lt')  if isinstance(r, dict) else r[1]): r
                        for r in _tb_rows_r
                    }

                for item in return_data:
                    lot_no = str(item.get('lot_no') or '').strip()
                    sub_lt = item.get('sub_lt')
                    reason = item.get('reason', '')
                    remark = item.get('remark', '')

                    if not lot_no or sub_lt is None:
                        result['errors'].append(f"Invalid item: {item}")
                        result['skipped'] += 1
                        continue

                    # cache에서 tonbag 조회 (N+1 제거)
                    tonbag = _tb_cache.get((lot_no, sub_lt))
                    if tonbag is None:
                        # fallback: 캐시 미스 시 개별 조회
                        tonbag = self.db.fetchone("""
                            SELECT lot_no, sub_lt, weight, status, picked_to, sale_ref, is_sample 
                            FROM inventory_tonbag 
                            WHERE lot_no = ? AND sub_lt = ?
                        """, (lot_no, sub_lt))

                    if not tonbag:
                        result['errors'].append(f"Tonbag not found: {lot_no}-{sub_lt}")
                        result['skipped'] += 1
                        continue

                    # v6.12.1: sqlite3.Row → dict 변환 (.get() 호환)
                    if not isinstance(tonbag, dict):
                        tonbag = dict(tonbag)

                    # v7.1.3 [T9-SAMPLE-RETURN-BLOCK]: 샘플 톤백 반품 Hard Stop
                    # 샘플(is_sample=1 또는 sub_lt=0)은 일반 반품 흐름과 완전 분리
                    # bulk_return_by_lot: is_sample=0 WHERE 조건으로 이미 제외
                    # process_return 단일건: 명시적 Hard Stop 추가 (T9 보강)
                    if tonbag.get('is_sample') or tonbag.get('sub_lt') == 0:
                        msg = (
                            f"[T9][SAMPLE_RETURN_BLOCKED] 샘플 톤백 반품 차단: "
                            f"{lot_no}-{sub_lt} (is_sample=1 또는 sub_lt=0) "
                            f"— 샘플은 재고 포함 고정 정책, 반품 불가"
                        )
                        logger.error(msg)
                        result['errors'].append(msg)
                        result.setdefault('fail_codes', []).append('SAMPLE_RETURN_BLOCKED')
                        result['skipped'] += 1
                        continue

                    # v6.9.7 [RT-06]: RETURN_DUPLICATE — 이중 반품 명확한 차단
                    if tonbag['status'] == STATUS_AVAILABLE:
                        msg = (
                            f"[RT-06][RETURN_DUPLICATE] 이중 반품 차단: "
                            f"{lot_no}-{sub_lt} 이미 재고 복구됨 (status=AVAILABLE) "
                            f"— 동일 화물 중복 반품 불가"
                        )
                        logger.error(msg)
                        result['errors'].append(msg)
                        result.setdefault('fail_codes', []).append('RETURN_DUPLICATE')
                        result['skipped'] += 1
                        continue

                    # v6.9.7 [RT-10]: CANCELLED 예약 후 반품 시도 차단
                    # allocation_plan이 CANCELLED인데 tonbag이 RESERVED 상태면 정합성 오류
                    if tonbag['status'] == STATUS_RESERVED:
                        # LOT 모드(sub_lt=NULL) 포함 CANCELLED 체크
                        _cancelled_plan = self.db.fetchone(
                            "SELECT COUNT(*) AS cnt FROM allocation_plan "
                            "WHERE lot_no=? AND status='CANCELLED' "
                            "AND (sub_lt=? OR sub_lt IS NULL)",
                            (lot_no, sub_lt)
                        )
                        _cp_cnt = int(_cancelled_plan.get('cnt', 0)) if _cancelled_plan else 0
                        if _cp_cnt > 0:
                            msg = (
                                f"[RT-10][RETURN_AFTER_CANCEL] 취소 후 반품 시도 차단: "
                                f"{lot_no}-{sub_lt} allocation_plan=CANCELLED인데 "
                                f"tonbag=RESERVED (정합성 오류 — cancel_reservation 먼저 실행)"
                            )
                            logger.error(msg)
                            result['errors'].append(msg)
                            result.setdefault('fail_codes', []).append('RETURN_AFTER_CANCEL')
                            result['skipped'] += 1
                            continue

                    if tonbag['status'] not in ('PICKED', 'CONFIRMED', 'SHIPPED', 'OUTBOUND', 'SOLD', 'RESERVED'):
                        # v7.2.0: OUTBOUND 추가 (구 SOLD 포함)
                        _rt05_msg = (
                            f"[RT-05][RETURN_INVALID_STATUS] 반품 불가 상태: "
                            f"{tonbag['status']} ({lot_no}-{sub_lt}) "
                            f"— 반품 가능 상태: PICKED/OUTBOUND/SOLD/SHIPPED/CONFIRMED/RESERVED"
                        )
                        result['errors'].append(_rt05_msg)
                        result.setdefault('fail_codes', []).append('RETURN_INVALID_STATUS')
                        logger.error(_rt05_msg)
                        result['skipped'] += 1
                        continue

                    tb_weight = float(tonbag['weight'] or 0)

                    # Save return history
                    self.db.execute("""
                        INSERT INTO return_history 
                        (lot_no, sub_lt, return_date, original_customer, 
                         original_sale_ref, reason, remark, weight_kg)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lot_no, sub_lt, date.today(),
                        tonbag['picked_to'], tonbag.get('sale_ref', ''),
                        reason, remark, tb_weight
                    ))

                    # v5.1.5: stock_movement 이력 추가 (반품)
                    # v6.12.1: source_type, source_file 추가
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    _src = source_type or 'RETURN_SINGLE'
                    self.db.execute("""
                        INSERT INTO stock_movement 
                        (lot_no, movement_type, qty_kg, remarks, source_type, source_file, created_at)
                        VALUES (?, 'RETURN', ?, ?, ?, ?, ?)
                    """, (lot_no, tb_weight,
                          f"sub_lt={sub_lt}, customer={tonbag.get('picked_to','')}, reason={reason}",
                          _src, source_file or '', now))

                    was_reserved = tonbag['status'] == STATUS_RESERVED
                    was_status = tonbag['status']  # v6.0.1: 반품 전 상태 보존

                    # v7.2.0: 반품 시 AVAILABLE 직접복귀 → RETURN 상태 경유
                    # location 지정 후 finalize_return_to_available() 호출로 AVAILABLE 전환
                    self.db.execute("""
                        UPDATE inventory_tonbag 
                        SET status = 'RETURN',
                            outbound_date = NULL,
                            picked_date = NULL,
                            picked_to = NULL,
                            sale_ref = NULL,
                            updated_at = ?
                        WHERE lot_no = ? AND sub_lt = ?
                    """, (now, lot_no, sub_lt))

                    # v5.9.3: RESERVED였으면 allocation_plan도 CANCELLED 처리
                    if was_reserved:
                        try:
                            self.db.execute("""
                                UPDATE allocation_plan SET status = 'CANCELLED', cancelled_at = ?
                                WHERE lot_no = ? AND sub_lt = ? AND status = 'RESERVED'
                            """, (now, lot_no, sub_lt))
                        except (sqlite3.OperationalError, ValueError, TypeError) as _e:
                            logger.debug(f"Suppressed: {_e}")
                    else:
                        # PICKED/SOLD: inventory current_weight 복구
                        self.db.execute("""
                            UPDATE inventory 
                            SET current_weight = current_weight + ?,
                                picked_weight = MAX(0, picked_weight - ?),
                                updated_at = ?
                            WHERE lot_no = ?
                        """, (tb_weight, tb_weight, now, lot_no))

                    # v8.0.3: was_reserved 조건 제거 → 항상 재계산 (RESERVED→RETURN도 포함)
                    if hasattr(self, '_recalc_current_weight'):
                        self._recalc_current_weight(lot_no, reason='P2_RETURN_SINGLE_TONBAG')

                    # [3] v6.7.9: PICKED/SOLD 반품 시 allocation_plan EXECUTED → CANCELLED
                    # RESERVED 외 상태 반품 시에도 allocation_plan 잔존 레코드 정리
                    # 미정리 시 재출고 시 ALLOC_CONFLICT 오류 발생
                    # v9.1: OUTBOUND 추가 (신규 write 기준)
                    if was_status in (STATUS_PICKED, STATUS_SOLD, 'OUTBOUND'):
                        try:
                            self.db.execute(
                                "UPDATE allocation_plan "
                                "SET status='CANCELLED', cancelled_at=? "
                                "WHERE lot_no=? AND sub_lt=? "
                                "AND status IN ('EXECUTED','RESERVED','STAGED')",
                                (now, lot_no, sub_lt)
                            )
                            logger.info(
                                f"[3] allocation_plan CANCELLED: {lot_no}-{sub_lt} "
                                f"(반품 사유: {reason})"
                            )
                        except (sqlite3.OperationalError, ValueError, TypeError) as _ae:
                            logger.debug(f"[3] allocation_plan 정리 스킵: {_ae}")

                    # v6.0.1/v9.1: picking_table RETURNED (OUTBOUND 추가)
                    if was_status in (STATUS_PICKED, STATUS_SOLD, 'OUTBOUND'):
                        try:
                            self.db.execute(
                                "UPDATE picking_table SET status='RETURNED', sold_date=? "
                                "WHERE lot_no=? AND sub_lt=? AND status IN ('ACTIVE','SOLD')",
                                (now, lot_no, sub_lt))
                        except (sqlite3.OperationalError, ValueError, TypeError) as _pe:
                            logger.debug(f"[v6.0.1] picking_table RETURNED 스킵: {_pe}")
                    # v6.0.1/v9.1: sold_table RETURNED (OUTBOUND 포함)
                    if was_status in (STATUS_SOLD, 'OUTBOUND'):
                        try:
                            self.db.execute(
                                "UPDATE sold_table SET status='RETURNED', "
                                "remark=COALESCE(remark,'')||? "
                                "WHERE lot_no=? AND sub_lt=? AND status IN ('SOLD','OUTBOUND')",
                                (f" | 반품:{now} 사유:{reason}", lot_no, sub_lt))
                        except (sqlite3.OperationalError, ValueError, TypeError) as _se:
                            logger.debug(f"[v6.0.1] sold_table RETURNED 스킵: {_se}")
                    # v6.2.2: 반품 후 문서 연계 점검용 감사 이력
                    self._log_return_doc_review_audit(
                        lot_no=lot_no,
                        sub_lt=sub_lt,
                        reason=reason,
                        source_type=_src,
                        source_file=source_file,
                    )

                    result['returned'] += 1
                    result['details'].append({
                        'lot_no': lot_no,
                        'sub_lt': sub_lt,
                        'weight': tb_weight,
                        'original_customer': tonbag.get('picked_to', '')
                    })
                    # v8.3.0 [Phase 9]: RETURN audit_log
                    try:
                        from engine_modules.audit_helper import write_audit, EVT_RETURN
                        write_audit(self.db, EVT_RETURN, lot_no=lot_no, detail={
                            'sub_lt': sub_lt,
                            'weight_kg': tb_weight,
                            'original_customer': tonbag.get('picked_to', ''),
                            'reason': item.get('reason', ''),
                        })
                    except Exception as _ae:
                        logger.debug(f"[RETURN audit] 스킵: {_ae}")
                    logger.info(f"Returned: {lot_no}-{sub_lt} ({tb_weight:.0f}kg)")

                # v7.6.0 [RT-09]: N+1 쿼리 → 단일 IN 쿼리로 통합 (성능 개선)
                # 반품된 톤백 위치 일괄 조회
                _details_with_sub = [
                    d for d in result.get('details', []) if 'sub_lt' in d
                ]
                if _details_with_sub:
                    _lot_sub_pairs = [(d['lot_no'], d['sub_lt']) for d in _details_with_sub]
                    _placeholders = ','.join(['(?,?)'] * len(_lot_sub_pairs))
                    _flat_params = [v for pair in _lot_sub_pairs for v in pair]
                    try:
                        _loc_rows = self.db.fetchall(
                            f"SELECT lot_no, sub_lt, location FROM inventory_tonbag "
                            f"WHERE (lot_no, sub_lt) IN ({_placeholders})",
                            _flat_params
                        )
                        _loc_map = {
                            (r['lot_no'], r['sub_lt']): str(r.get('location') or '').strip()
                            for r in (_loc_rows or [])
                        }
                    except Exception:
                        # SQLite IN 튜플 미지원 시 폴백
                        _loc_map = {}
                    for _ret_d in _details_with_sub:
                        _loc_val = _loc_map.get((_ret_d['lot_no'], _ret_d['sub_lt']), '')
                        if not _loc_val:
                            _rt09_warn = (
                                f"[RT-09] 반품 후 재입고 위치 미지정: "
                                f"LOT {_ret_d['lot_no']}-sub_lt={_ret_d.get('sub_lt','?')} "
                                f"— 재고관리→위치 설정 권장"
                            )
                            logger.warning(_rt09_warn)
                            result.setdefault('warnings', []).append(_rt09_warn)

                # v5.2.0: 반품된 모든 LOT의 status 재계산 (래퍼 제거 → 직접 호출)
                returned_lots = set(d['lot_no'] for d in result['details'])
                for rlt in returned_lots:
                    self._recalc_lot_status(rlt)
                    logger.info(f"LOT status 재계산(반품): {rlt}")

                # v5.1.5: 정합성 검증 (트랜잭션 안에서)
                if hasattr(self, 'verify_lot_integrity') and returned_lots:
                    for rlt in returned_lots:
                        integrity = self.verify_lot_integrity(rlt)
                        result['integrity'][rlt] = integrity
                        if not integrity.get('valid', True):
                            raise ValueError(
                                f"반품 후 정합성 실패 ({rlt}): {integrity.get('errors', [])}"
                            )

                result['success'] = result['returned'] > 0

        except (ValueError, TypeError, AttributeError,
                sqlite3.OperationalError, sqlite3.IntegrityError) as e:
            result['errors'].append(f"Return processing error: {e}")
            logger.exception("Return processing error")

        return result

    def _log_return_doc_review_audit(
        self, lot_no: str, sub_lt: int, reason: str = "",
        source_type: str = "", source_file: str = ""
    ) -> None:
        """
        반품 시점의 문서 연계 정보 스냅샷을 stock_movement에 기록.
        - 자동 문서 수정은 하지 않고, 점검 필요 근거를 남긴다.
        """
        try:
            inv = self.db.fetchone(
                "SELECT sap_no, bl_no, salar_invoice_no FROM inventory WHERE lot_no = ? LIMIT 1",
                (lot_no,),
            ) or {}
            sold = self.db.fetchone(
                """
                SELECT id, picking_no, sales_order_no, sap_no, bl_no, customer, sold_date
                FROM sold_table
                WHERE lot_no = ? AND sub_lt = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (lot_no, sub_lt),
            ) or {}
            pick = self.db.fetchone(
                """
                SELECT id, picking_no, sales_order_no, outbound_id, customer, sold_date
                FROM picking_table
                WHERE lot_no = ? AND sub_lt = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (lot_no, sub_lt),
            ) or {}

            details = {
                "lot_no": lot_no,
                "sub_lt": int(sub_lt) if sub_lt is not None else None,
                "reason": reason or "",
                "inventory": {
                    "sap_no": str(inv.get("sap_no", "") or ""),
                    "bl_no": str(inv.get("bl_no", "") or ""),
                    "invoice_no": str(inv.get("salar_invoice_no", "") or ""),
                },
                "sold_table": {
                    "id": sold.get("id"),
                    "picking_no": str(sold.get("picking_no", "") or ""),
                    "sales_order_no": str(sold.get("sales_order_no", "") or ""),
                    "sap_no": str(sold.get("sap_no", "") or ""),
                    "bl_no": str(sold.get("bl_no", "") or ""),
                    "customer": str(sold.get("customer", "") or ""),
                    "sold_date": str(sold.get("sold_date", "") or ""),
                },
                "picking_table": {
                    "id": pick.get("id"),
                    "picking_no": str(pick.get("picking_no", "") or ""),
                    "sales_order_no": str(pick.get("sales_order_no", "") or ""),
                    "outbound_id": str(pick.get("outbound_id", "") or ""),
                    "customer": str(pick.get("customer", "") or ""),
                    "sold_date": str(pick.get("sold_date", "") or ""),
                },
                "action_required": "Review D/O, Invoice, B/L linkage after return",
            }
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            movement_type = 'RETURN_DOC_REVIEW'
            remarks = f"return doc linkage review required: lot={lot_no}, sub_lt={sub_lt}"
            ref_id = sold.get("id") or pick.get("id")
            ref_table = "sold_table" if sold.get("id") else ("picking_table" if pick.get("id") else "inventory")
            self.db.execute(
                """
                INSERT INTO stock_movement
                (lot_no, movement_type, qty_kg, remarks, source_type, source_file, ref_table, ref_id, details_json, created_at)
                VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lot_no, movement_type, remarks, source_type or 'RETURN_SINGLE', source_file or '',
                    ref_table, ref_id, json.dumps(details, ensure_ascii=False), now,
                ),
            )
        except (sqlite3.OperationalError, ValueError, TypeError, KeyError, AttributeError) as e:
            logger.debug(f"[return-doc-audit] 스킵: {e}")

    # ── v7.0.0: RETURN_AS_REINBOUND 정책 진입점 ──────────────────────────────
    def process_return_reinbound(
        self,
        outbound_id: str,
        lot_no: str,
        new_location: str,
        operator_id: str = 'SYSTEM',
        reason: str = '반품',
        return_date: str = None,
    ) -> Dict:
        """
        RETURN_AS_REINBOUND 정책 기반 반품 처리 (v7.0.0).

        기존 process_return() 의 복잡한 상태 전이를 대체하는 단순화된 진입점.

        처리 흐름:
          1. ReturnReinboundEngine.process() 호출
          2. tonbag_uid UNIQUE 제약 준수 — UPDATE 방식, 신규 row 금지
          3. outbound_log 불변 — 절대 수정하지 않음
          4. return_log에 원출고 연결 이력 기록

        Args:
            outbound_id:  원출고 ID (OUT…)
            lot_no:       반품 LOT 번호
            new_location: PDA 재스캔으로 배정된 새 Rack 위치
            operator_id:  작업자 ID (기본 'SYSTEM')
            reason:       반품 사유
            return_date:  반품일 (None 이면 오늘)

        Returns:
            {
              'success': bool,
              'return_id': str | None,
              'lot_no': str,
              'new_location': str,
              'tonbags_restored': int,
              'weight_restored': float,
              'error': str | None,
            }
        """
        try:
            from engine_modules.return_reinbound_engine import ReturnReinboundEngine
        except ImportError as e:
            logger.error(f"[v7.0.0] ReturnReinboundEngine import 실패: {e}")
            return {
                'success': False, 'return_id': None,
                'lot_no': lot_no, 'new_location': new_location,
                'tonbags_restored': 0, 'weight_restored': 0.0,
                'error': f'엔진 import 실패: {e}',
            }

        # DB 연결 어댑터 (return_mixin의 self.db → sqlite3.Connection)
        raw_conn = getattr(self.db, '_conn', None) or getattr(self.db, 'conn', None)
        if raw_conn is None:
            # database.py Database 객체에서 내부 연결 추출 시도
            try:
                raw_conn = self.db._get_connection()
            except AttributeError:
                raw_conn = self.db

        engine = ReturnReinboundEngine(raw_conn)
        result = engine.process(
            outbound_id=outbound_id,
            lot_no=lot_no,
            new_location=new_location,
            operator_id=operator_id,
            reason=reason,
            return_date=return_date,
        )

        if result.ok:
            logger.info(
                f"[v7.0.0] RETURN_AS_REINBOUND 완료 "
                f"return_id={result.return_id} lot={lot_no} "
                f"위치={new_location} 톤백={result.tonbags_restored}개"
            )
        else:
            logger.error(f"[v7.0.0] RETURN_AS_REINBOUND 실패: {result.error}")

        return {
            'success':          result.ok,
            'return_id':        result.return_id,
            'lot_no':           result.lot_no,
            'new_location':     result.new_location,
            'tonbags_restored': result.tonbags_restored,
            'weight_restored':  result.weight_restored,
            'error':            result.error,
        }

    def return_single_tonbag(self, lot_no: str, sub_lt: int,
                             reason: str = None, remark: str = None) -> Dict:
        """
        Return a single tonbag
        
        Args:
            lot_no: LOT number
            sub_lt: Sub LOT number
            reason: Return reason
            remark: Additional remarks
            
        Returns:
            Result dict
        """
        return self.process_return([{
            'lot_no': lot_no,
            'sub_lt': sub_lt,
            'reason': reason or '',
            'remark': remark or ''
        }])

    def bulk_return_by_lot(self, lot_no: str, reason: str = None) -> Dict:
        """
        Return all returnable tonbags for a LOT.
        v7.1.0 [BULK-RETURN-1]: RESERVED 상태 반품 시 경고 추가
          - SOLD/PICKED 이외의 RESERVED 톤백 반품은 예외적 케이스
          - 운영자 확인 유도를 위해 result['warnings'] 기록

        Args:
            lot_no: LOT number
            reason: Return reason

        Returns:
            Result dict with 'warnings' key for RESERVED tonbag returns
        """
        # Get all returnable tonbags for this lot
        picked = self.db.fetchall("""
            SELECT lot_no, sub_lt, status FROM inventory_tonbag
            WHERE lot_no = ? AND status IN ('PICKED', 'CONFIRMED', 'SHIPPED', 'SOLD', 'RESERVED')
              AND COALESCE(is_sample, 0) = 0
        """, (lot_no,))

        if not picked:
            return {
                'success': False,
                'returned': 0,
                'errors': [f"반품 가능한 톤백 없음: LOT {lot_no}"],
                'warnings': []
            }

        # v7.1.0 [BULK-RETURN-1]: RESERVED 상태 반품 경고
        reserved_subs = [
            row['sub_lt'] for row in picked
            if str(row.get('status', '')) == STATUS_RESERVED
        ]
        pre_warnings = []
        if reserved_subs:
            _warn = (
                f"[BULK-RETURN-1] LOT {lot_no}: RESERVED 상태 톤백 {len(reserved_subs)}개 "
                f"(sub_lt: {reserved_subs}) 반품 포함 — 미출고 상태 반품 여부 확인 필요. "
                f"의도된 경우 계속 진행 가능합니다."
            )
            pre_warnings.append(_warn)
            logger.warning(_warn)

        return_data = [
            {'lot_no': row['lot_no'], 'sub_lt': row['sub_lt'], 'reason': reason or ''}
            for row in picked
        ]

        result = self.process_return(
            return_data,
            source_type='RETURN_BULK',
            source_file=''
        )
        # 경고 병합
        if pre_warnings:
            result.setdefault('warnings', [])
            result['warnings'] = pre_warnings + result.get('warnings', [])
        return result

    def get_return_statistics(self, start_date: str = '', end_date: str = '',
                              lot_no: str = '') -> Dict:
        """
        v7.1.0: 반품 사유 통계 리포트.
        RETURN_AS_REINBOUND(return_log) + 레거시(return_history) UNION 통합 쿼리.

        Args:
            start_date: 시작일 (YYYY-MM-DD, 빈값=전체)
            end_date:   종료일 (YYYY-MM-DD, 빈값=전체)
            lot_no:     LOT 필터 (빈값=전체)

        Returns:
            {
                'total_count': int,
                'total_weight_kg': float,
                'by_reason': [{'reason': str, 'count': int, 'weight_kg': float}, ...],
                'by_lot': [{'lot_no': str, 'count': int, 'weight_kg': float, 'reasons': str}, ...],
                'by_month': [{'month': str, 'count': int, 'weight_kg': float}, ...],
                'top_customers': [{'customer': str, 'count': int}, ...],
            }
        """
        result = {
            'total_count': 0,
            'total_weight_kg': 0.0,
            'by_reason': [],
            'by_lot': [],
            'by_month': [],
            'top_customers': [],
        }

        # ── UNION CTE: return_log(v7.0.0) + return_history(레거시) 통합 뷰 ──
        # return_log: return_id, lot_no, customer, return_date, reason, weight_kg
        # return_history: id, lot_no, original_customer, return_date, reason, weight_kg
        UNION_CTE = """
            WITH combined AS (
                SELECT
                    lot_no,
                    COALESCE(customer, '미기재')       AS customer,
                    COALESCE(return_date, '')           AS return_date,
                    COALESCE(reason, '미기재')          AS reason,
                    COALESCE(weight_kg, 0)              AS weight_kg
                FROM return_log
                UNION ALL
                SELECT
                    lot_no,
                    COALESCE(original_customer, '미기재') AS customer,
                    COALESCE(return_date, '')             AS return_date,
                    COALESCE(reason, '미기재')            AS reason,
                    COALESCE(weight_kg, 0)                AS weight_kg
                FROM return_history
            )
        """

        try:
            # WHERE 조건 구성 (CTE 내 컬럼명 기준)
            where_parts = ['1=1']
            params: list = []
            if start_date:
                where_parts.append("return_date >= ?")
                params.append(start_date)
            if end_date:
                where_parts.append("return_date <= ?")
                params.append(end_date)
            if lot_no:
                where_parts.append("lot_no = ?")
                params.append(lot_no)
            where = ' AND '.join(where_parts)
            p = tuple(params)

            # ① 전체 합계
            row = self.db.fetchone(
                f"{UNION_CTE} SELECT COUNT(*) AS cnt, "
                f"COALESCE(SUM(weight_kg), 0) AS total "
                f"FROM combined WHERE {where}", p)
            if row:
                result['total_count'] = row['cnt'] if isinstance(row, dict) else row[0]
                result['total_weight_kg'] = float(
                    row['total'] if isinstance(row, dict) else row[1])

            # ② 사유별 집계
            rows = self.db.fetchall(
                f"""{UNION_CTE}
                SELECT reason,
                       COUNT(*) AS cnt,
                       COALESCE(SUM(weight_kg), 0) AS total
                FROM combined WHERE {where}
                GROUP BY reason
                ORDER BY cnt DESC""", p)
            result['by_reason'] = [
                {'reason': r['reason'] if isinstance(r, dict) else r[0],
                 'count': r['cnt'] if isinstance(r, dict) else r[1],
                 'weight_kg': float(r['total'] if isinstance(r, dict) else r[2])}
                for r in rows
            ]

            # ③ LOT별 집계
            rows = self.db.fetchall(
                f"""{UNION_CTE}
                SELECT lot_no,
                       COUNT(*) AS cnt,
                       COALESCE(SUM(weight_kg), 0) AS total,
                       GROUP_CONCAT(DISTINCT reason) AS reasons
                FROM combined WHERE {where}
                GROUP BY lot_no
                ORDER BY cnt DESC LIMIT 50""", p)
            result['by_lot'] = [
                {'lot_no': r['lot_no'] if isinstance(r, dict) else r[0],
                 'count': r['cnt'] if isinstance(r, dict) else r[1],
                 'weight_kg': float(r['total'] if isinstance(r, dict) else r[2]),
                 'reasons': (r['reasons'] if isinstance(r, dict) else r[3]) or ''}
                for r in rows
            ]

            # ④ 월별 추이
            rows = self.db.fetchall(
                f"""{UNION_CTE}
                SELECT SUBSTR(return_date, 1, 7) AS month,
                       COUNT(*) AS cnt,
                       COALESCE(SUM(weight_kg), 0) AS total
                FROM combined WHERE {where}
                GROUP BY SUBSTR(return_date, 1, 7)
                ORDER BY month""", p)
            result['by_month'] = [
                {'month': (r['month'] if isinstance(r, dict) else r[0]) or '?',
                 'count': r['cnt'] if isinstance(r, dict) else r[1],
                 'weight_kg': float(r['total'] if isinstance(r, dict) else r[2])}
                for r in rows
            ]

            # ⑤ 고객별 반품 건수 Top 10
            rows = self.db.fetchall(
                f"""{UNION_CTE}
                SELECT customer,
                       COUNT(*) AS cnt
                FROM combined WHERE {where}
                GROUP BY customer
                ORDER BY cnt DESC LIMIT 10""", p)
            result['top_customers'] = [
                {'customer': r['customer'] if isinstance(r, dict) else r[0],
                 'count': r['cnt'] if isinstance(r, dict) else r[1]}
                for r in rows
            ]

        except (sqlite3.OperationalError, ValueError, TypeError,
                AttributeError, KeyError) as e:
            logger.error(f"[get_return_statistics v7.1.0] 오류: {e}", exc_info=True)

        return result

    # ═══════════════════════════════════════════════════════
    # v7.2.0 [RETURN-FINALIZE]: RETURN → AVAILABLE 전환
    # ═══════════════════════════════════════════════════════

    def finalize_return_to_available(
        self,
        lot_no: str,
        sub_lt: int,
        location: str = None,
    ) -> Dict:
        """반품 대기(RETURN) 톤백을 location 지정 후 AVAILABLE로 전환한다.

        Args:
            lot_no:   LOT 번호
            sub_lt:   톤백 sub_lt
            location: 배치할 랙 위치 (없으면 기존 location 유지)

        Returns:
            {'success': bool, 'message': str}
        """
        result = {'success': False, 'message': ''}
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 대상 톤백 조회
            tb = self.db.fetchone(
                "SELECT id, status, location, weight FROM inventory_tonbag "
                "WHERE lot_no = ? AND sub_lt = ?",
                (lot_no, sub_lt)
            )
            if not tb:
                result['message'] = f'톤백 없음: {lot_no}-{sub_lt}'
                return result

            if tb.get('status') != STATUS_RETURN:
                result['message'] = (
                    f"RETURN 상태가 아님 (현재: {tb.get('status')}) — "
                    f"finalize_return_to_available 호출 불가"
                )
                return result

            tb_id        = tb['id'] if isinstance(tb, dict) else tb[0]
            tb_weight    = float(tb.get('weight') or 0)
            new_location = location or (tb.get('location') or '')

            # v9.1: 모든 변경을 하나의 트랜잭션으로 묶음 (버그3 수정)
            # inventory_tonbag + stock_movement 만 처리
            # current_weight 복구는 하지 않음 (버그2 수정)
            # → process_return() 에서 이미 PICKED/SOLD/OUTBOUND 시 복구됨
            # → _recalc_current_weight() 가 실제 tonbag 상태 기반으로 재계산
            with self.db.transaction('IMMEDIATE'):
                # RETURN → AVAILABLE 전환
                self.db.execute(
                    "UPDATE inventory_tonbag "
                    "SET status = 'AVAILABLE', location = ?, updated_at = ? "
                    "WHERE id = ?",
                    (new_location, now, tb_id)
                )
                # stock_movement 이력 (위치 복귀 기록)
                self.db.execute(
                    "INSERT INTO stock_movement "
                    "(lot_no, movement_type, qty_kg, remarks, created_at) "
                    "VALUES (?, 'RETURN_TO_AVAILABLE', ?, ?, ?)",
                    (lot_no, tb_weight,
                     f"sub_lt={sub_lt}, location={new_location}", now)
                )

            # P2 재계산 (실제 tonbag 상태 기반으로 current_weight 재산출)
            if hasattr(self, '_recalc_current_weight'):
                self._recalc_current_weight(lot_no, reason='P2_RETURN_TO_AVAILABLE')
            if hasattr(self, '_recalc_lot_status'):
                self._recalc_lot_status(lot_no)

            result['success'] = True
            result['message'] = (
                f"[RETURN→AVAILABLE] {lot_no}-{sub_lt} 복귀 완료 "
                f"(location={new_location or '미지정'})"
            )
            logger.info(result['message'])

        except Exception as e:
            result['message'] = f'finalize_return_to_available 오류: {e}'
            logger.error(result['message'], exc_info=True)

        return result

    # ═══════════════════════════════════════════════════════════════════
    # v8.1.7: Move 이력 조회 메서드 (tonbag_move_log 기반)
    # ═══════════════════════════════════════════════════════════════════

    def get_move_history(self, status: str = None, lot_no: str = None,
                         limit: int = 500) -> List[Dict]:
        """
        톤백 위치 이동 이력 조회 (tonbag_move_log 테이블).

        Args:
            status:  필터 상태 ('PENDING', 'APPROVED', 'COMPLETED', 'REJECTED', None=전체)
            lot_no:  LOT 필터 (None=전체)
            limit:   최대 반환 건수

        Returns:
            List of dict — tonbag_move_log 행 목록
        """
        try:
            query = """
                SELECT
                    m.id, m.lot_no, m.sub_lt, m.tonbag_no,
                    m.from_location, m.to_location,
                    m.move_date, m.status, m.approver,
                    m.operator, m.remark, m.source_type,
                    m.created_at,
                    i.product, i.sap_no
                FROM tonbag_move_log m
                LEFT JOIN inventory i ON m.lot_no = i.lot_no
                WHERE 1=1
            """
            params: list = []
            if status:
                query += " AND m.status = ?"
                params.append(status)
            if lot_no:
                query += " AND m.lot_no = ?"
                params.append(lot_no)
            query += f" ORDER BY m.created_at DESC LIMIT {int(limit)}"
            return self.db.fetchall(query, tuple(params)) or []
        except Exception as _e:
            import logging
            logging.getLogger(__name__).debug(f"[get_move_history] {_e}")
            return []

    def record_move(self, lot_no: str, sub_lt: int, to_location: str,
                    from_location: str = '', tonbag_no: str = '',
                    move_date: str = '', status: str = 'COMPLETED',
                    approver: str = '', operator: str = 'system',
                    remark: str = '', source_type: str = 'MANUAL',
                    source_file: str = '') -> Dict:
        """
        톤백 위치 이동 이력 기록 (tonbag_move_log INSERT).

        Returns:
            {'success': bool, 'id': int, 'message': str}
        """
        result = {'success': False, 'id': None, 'message': ''}
        try:
            from datetime import datetime
            move_date = move_date or datetime.now().strftime('%Y-%m-%d')
            self.db.execute("""
                INSERT INTO tonbag_move_log
                    (lot_no, sub_lt, tonbag_no, from_location, to_location,
                     move_date, status, approver, operator, remark,
                     source_type, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (lot_no, sub_lt, tonbag_no, from_location, to_location,
                  move_date, status, approver, operator, remark,
                  source_type, source_file))
            result['success'] = True
            result['message'] = (
                f"[MOVE] {lot_no}-{sub_lt} {from_location or '?'} → {to_location}"
            )
            import logging
            logging.getLogger(__name__).info(result['message'])
        except Exception as _e:
            result['message'] = f"record_move 오류: {_e}"
            import logging
            logging.getLogger(__name__).error(result['message'])
        return result
