"""
SQM Inventory Engine - Tonbag Mixin
===================================

v2.9.91 - Extracted from inventory.py

Tonbag (Sub LOT) management functions
"""

from engine_modules.constants import STATUS_AVAILABLE, STATUS_PICKED
import logging
import sqlite3
from datetime import date
from typing import Dict

logger = logging.getLogger(__name__)


class TonbagMixin:
    """
    Tonbag management mixin
    
    Methods for tonbag CRUD, location updates, and status queries
    """

    # NOTE: get_tonbags, get_sublots → QueryMixin으로 이관 완료 (v3.8.4 데드코드 정리)

    def get_tonbag_summary(self, lot_no: str) -> Dict:
        """
        Get tonbag summary for a LOT
        
        Args:
            lot_no: LOT number
            
        Returns:
            Summary dict with counts and weights
        """
        query = """
            SELECT 
                COUNT(*) as total_count,
                SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) as available_count,
                SUM(CASE WHEN status = 'PICKED' THEN 1 ELSE 0 END) as picked_count,
                SUM(CASE WHEN status = 'SAMPLE' THEN 1 ELSE 0 END) as sample_count,
                SUM(weight) as total_weight,
                SUM(CASE WHEN status = 'AVAILABLE' THEN weight ELSE 0 END) as available_weight,
                SUM(CASE WHEN status = 'PICKED' THEN weight ELSE 0 END) as picked_weight
            FROM inventory_tonbag
            WHERE lot_no = ?
        """

        row = self.db.fetchone(query, (lot_no,))

        if row:
            return {
                'lot_no': lot_no,
                'total_count': row['total_count'] or 0,
                'available_count': row['available_count'] or 0,
                'picked_count': row['picked_count'] or 0,
                'sample_count': row['sample_count'] or 0,
                'total_weight': row['total_weight'] or 0,
                'available_weight': row['available_weight'] or 0,
                'picked_weight': row['picked_weight'] or 0
            }

        return {
            'lot_no': lot_no,
            'total_count': 0,
            'available_count': 0,
            'picked_count': 0,
            'sample_count': 0,
            'total_weight': 0,
            'available_weight': 0,
            'picked_weight': 0
        }

    def get_all_sublots_summary(self) -> Dict:
        """
        Get summary of all sublots
        
        Returns:
            Summary dict
        """
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) as available,
                SUM(CASE WHEN status = 'PICKED' THEN 1 ELSE 0 END) as picked,
                SUM(weight) as total_weight,
                SUM(CASE WHEN status = 'AVAILABLE' THEN weight ELSE 0 END) as available_weight
            FROM inventory_tonbag
        """

        row = self.db.fetchone(query)

        if row:
            return {
                'total': row['total'] or 0,
                'available': row['available'] or 0,
                'picked': row['picked'] or 0,
                'total_weight_kg': row['total_weight'] or 0,
                'available_weight_kg': row['available_weight'] or 0
            }

        return {'total': 0, 'available': 0, 'picked': 0,
                'total_weight_kg': 0, 'available_weight_kg': 0}

    def get_all_tonbags_summary(self) -> Dict:
        """Alias for get_all_sublots_summary"""
        return self.get_all_sublots_summary()

    # ─── 이동 허용 상태 (v6.6.0 하드스톱 §5) ───
    _MOVE_BLOCKED_STATUSES = frozenset({
        'PICKED', 'SOLD', 'DEPLETED', 'SHIPPED',
        'OUTBOUND',   # v9.0: 출고완료 톤백 위치변경 차단 (감사 추적 혼란 방지)
    })
    # 사유 코드 화이트리스트 (§7)
    VALID_MOVE_REASONS = frozenset({
        'RELOCATE',       # 일반 재배치
        'RACK_REPAIR',    # 랙 수리
        'INVENTORY_AUDIT',# 재고 실사
        'PICKING_OPT',    # 피킹 최적화
        'RETURN_PUTAWAY', # 반품 적치
        'CORRECTION',     # 위치 보정
        'OTHER',          # 기타 (note 필수)
    })

    def update_tonbag_location(self, lot_no: str, sub_lt: int,
                               location: str,
                               source: str = 'MANUAL',
                               reason_code: str = 'RELOCATE',
                               operator: str = 'system',
                               note: str = '') -> Dict:
        """
        단건 톤백 위치 변경 — v6.6.0: 하드스톱 7개 + 사유코드 강제.

        하드스톱:
          ①  톤백 미존재
          ②  이동 금지 상태 (PICKED/SOLD/DEPLETED/SHIPPED)
          ③  동일 위치 이동 (경고 → 차단)
          ④  to_location 형식 오류
          ⑤  Capacity=1 위반 (to_location에 다른 AVAILABLE/RESERVED 톤백 있음)
          ⑥  reason_code 누락/오류
          ⑦  OTHER 사유인데 note 없음
        """
        from datetime import datetime

        result = {
            'success': False,
            'error': None,
            'from_location': None,
            'to_location': None,
        }

        try:
            # ─── §5-①: 톤백 존재 확인 ───
            existing = self.db.fetchone(
                "SELECT lot_no, sub_lt, location, weight, status, "
                "COALESCE(is_sample,0) AS is_sample "
                "FROM inventory_tonbag WHERE lot_no = ? AND sub_lt = ?",
                (lot_no, sub_lt)
            )
            if not existing:
                result['error'] = f"[HARD-STOP①] 톤백 없음: {lot_no}-{sub_lt}"
                return result

            from_loc  = (existing.get('location') or '').strip()
            to_loc    = (location or '').strip().upper()
            tb_weight = existing.get('weight') or 0
            cur_status = (existing.get('status') or '').strip().upper()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # ─── §5-②: 이동 금지 상태 ───
            if cur_status in self._MOVE_BLOCKED_STATUSES:
                result['error'] = (
                    f"[HARD-STOP②] 이동 금지 상태: {cur_status} "
                    f"(AVAILABLE/RESERVED만 이동 가능)"
                )
                return result

            # ─── ① v6.8.0 SAMPLE_MOVE_FORBIDDEN ───
            # 샘플 톤백(1kg)은 위치 이동 금지
            # 샘플은 입고 위치에 고정 보관이 원칙 (SQM 불변 조건)
            _is_sample_mv = int(existing.get('is_sample') or 0)
            if _is_sample_mv == 1:
                result['error'] = (
                    f"[HARD-STOP SAMPLE_MOVE_FORBIDDEN] "
                    f"샘플 톤백은 이동 불가: {lot_no}-{sub_lt} (is_sample=1)"
                )
                return result

            # ─── §5-③: 동일 위치 ───
            if from_loc and from_loc.upper() == to_loc:
                result['error'] = f"[HARD-STOP③] 현재 위치와 동일: {to_loc}"
                return result

            # ─── §5-④: to_location 형식 ───
            if to_loc:
                from engine_modules.constants import validate_location_format  # v8.6.4 이동
                ok, msg = validate_location_format(to_loc)
                if not ok:
                    result['error'] = f"[HARD-STOP④] 위치 형식 오류: {msg}"
                    return result

            # ─── §5-⑤: Capacity=1 위반 ───
            occupant = self.db.fetchone(
                """SELECT lot_no, sub_lt FROM inventory_tonbag
                   WHERE UPPER(COALESCE(location,'')) = ?
                     AND lot_no != ? AND sub_lt != ?
                     AND status NOT IN ('SOLD','DEPLETED','SHIPPED')
                   LIMIT 1""",
                (to_loc, lot_no, sub_lt)
            )
            if occupant:
                o_lot = occupant.get('lot_no', '?')
                o_sub = occupant.get('sub_lt', '?')
                result['error'] = (
                    f"[HARD-STOP⑤] Capacity=1 위반: {to_loc}에 "
                    f"LOT {o_lot}/톤백 {o_sub} 점유 중"
                )
                return result

            # ─── §7-⑥: 사유코드 강제 ───
            rc = (reason_code or '').strip().upper()
            if not rc or rc not in self.VALID_MOVE_REASONS:
                result['error'] = (
                    f"[HARD-STOP⑥] 사유코드 필수: {list(self.VALID_MOVE_REASONS)}"
                )
                return result

            # ─── §7-⑦: OTHER → note 필수 ───
            if rc == 'OTHER' and not (note or '').strip():
                result['error'] = "[HARD-STOP⑦] 기타(OTHER) 사유 선택 시 비고를 입력하세요."
                return result

            # ─── DB 업데이트 (All-or-Nothing) ───
            with self.db.transaction():
                self.db.execute("""
                    UPDATE inventory_tonbag
                    SET location           = ?,
                        location_updated_at = ?,
                        updated_at         = ?
                    WHERE lot_no = ? AND sub_lt = ?
                """, (to_loc, now, now, lot_no, sub_lt))

                # ⑥ stock_movement 단일 이력 (location_move_log 폐지)
                if from_loc != to_loc:
                    self.db.execute("""
                        INSERT INTO stock_movement
                        (lot_no, sub_lt, movement_type, qty_kg,
                         from_location, to_location,
                         reason_code, operator, remarks, created_at)
                        VALUES (?, ?, 'RELOCATE', ?, ?, ?, ?, ?, ?, ?)
                    """, (lot_no, sub_lt, tb_weight,
                          from_loc, to_loc,
                          rc, operator,
                          (note or f"source={source}"), now))

            result['success']       = True
            result['from_location'] = from_loc
            result['to_location']   = to_loc
            logger.info(
                f"[MOVE] {lot_no}-{sub_lt} [{from_loc}]→[{to_loc}] "
                f"reason={rc} op={operator}"
            )

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            result['error'] = str(e)
            logger.error(f"Location update error: {e}")

        return result


    # ═══════════════════════════════════════════════════════════════
    # ⑤ 대량 이동 워크플로: PENDING → Supervisor 승인 → 반영
    # ═══════════════════════════════════════════════════════════════

    def submit_batch_move(self, validated_items: list, reason_code: str = 'RELOCATE',
                          operator: str = 'system', note: str = '') -> dict:
        """
        대량 이동 요청 제출 — PENDING 상태로 저장 (즉시 반영 없음).

        Args:
            validated_items: validate_and_match() 결과 matched 리스트
            reason_code:      이동 사유 코드 (VALID_MOVE_REASONS)
            operator:         요청자
            note:             비고

        Returns:
            {'success': bool, 'batch_id': str, 'error': str|None}
        """
        import uuid, json
        from datetime import datetime

        result = {'success': False, 'batch_id': None, 'error': None}

        if not validated_items:
            result['error'] = "이동 항목이 없습니다."
            return result

        rc = (reason_code or 'RELOCATE').strip().upper()
        if rc not in self.VALID_MOVE_REASONS:
            result['error'] = f"[HARD-STOP⑥] 사유코드 오류: {rc}"
            return result
        if rc == 'OTHER' and not (note or '').strip():
            result['error'] = "[HARD-STOP⑦] OTHER 사유 시 비고 필수."
            return result

        batch_id = f"MB-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            self.db.execute("""
                INSERT INTO move_batch
                (batch_id, status, total_count, reason_code,
                 submitted_by, submitted_at, items_json, note)
                VALUES (?, 'PENDING', ?, ?, ?, ?, ?, ?)
            """, (batch_id, len(validated_items), rc,
                  operator, now,
                  json.dumps(validated_items, ensure_ascii=False),
                  note or ''))

            result['success']  = True
            result['batch_id'] = batch_id
            logger.info(f"[MOVE-BATCH] 제출 batch_id={batch_id} "
                        f"items={len(validated_items)} op={operator}")
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"[MOVE-BATCH] 제출 실패: {e}")

        return result

    def approve_batch_move(self, batch_id: str,
                           approver: str = 'supervisor') -> dict:
        """
        Supervisor 승인 → All-or-Nothing 일괄 반영.

        Args:
            batch_id:  submit_batch_move()가 반환한 batch_id
            approver:  승인자

        Returns:
            {'success': bool, 'applied': int, 'skipped': int,
             'errors': list, 'error': str|None}
        """
        import json
        from datetime import datetime

        result = {
            'success': False, 'applied': 0,
            'skipped': 0, 'errors': [], 'error': None,
        }

        try:
            batch = self.db.fetchone(
                "SELECT * FROM move_batch WHERE batch_id = ?", (batch_id,))
        except Exception as e:
            result['error'] = f"move_batch 조회 실패: {e}"
            return result

        if not batch:
            result['error'] = f"배치 없음: {batch_id}"
            return result

        status = (batch.get('status') or '').upper()
        if status != 'PENDING':
            result['error'] = f"승인 불가 상태: {status} (PENDING만 승인 가능)"
            return result

        items = []
        try:
            items = json.loads(batch.get('items_json') or '[]')
        except Exception:
            result['error'] = "items_json 파싱 오류"
            return result

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        reason_code = batch.get('reason_code', 'RELOCATE')

        # All-or-Nothing: 먼저 전체 pre-check
        pre_errors = []
        for item in items:
            lot_no = item.get('lot_no', '')
            sub_lt = item.get('sub_lt')
            to_loc = (item.get('to_location') or item.get('location') or '').strip().upper()

            tb = self.db.fetchone(
                "SELECT status, location FROM inventory_tonbag "
                "WHERE lot_no=? AND sub_lt=?", (lot_no, sub_lt))
            if not tb:
                pre_errors.append(f"톤백 없음: {lot_no}-{sub_lt}")
                continue
            cur_st = (tb.get('status') or '').upper()
            if cur_st in self._MOVE_BLOCKED_STATUSES:
                pre_errors.append(f"이동 금지 상태 {lot_no}-{sub_lt}: {cur_st}")

        if pre_errors:
            result['error'] = "Pre-check 실패 — 전체 롤백: " + " / ".join(pre_errors)
            self.db.execute(
                "UPDATE move_batch SET status='REJECTED', "
                "rejected_by=?, rejected_at=?, reject_reason=? "
                "WHERE batch_id=?",
                (approver, now, result['error'], batch_id))
            return result

        # All-or-Nothing 반영
        try:
            with self.db.transaction():
                for item in items:
                    lot_no = item.get('lot_no', '')
                    sub_lt = item.get('sub_lt')
                    to_loc = (item.get('to_location') or item.get('location') or '').strip().upper()
                    tb_weight = item.get('weight', 0)
                    from_loc  = (item.get('from_location') or item.get('db_current_location') or '').strip()

                    self.db.execute("""
                        UPDATE inventory_tonbag
                        SET location=?, location_updated_at=?, updated_at=?
                        WHERE lot_no=? AND sub_lt=?
                    """, (to_loc, now, now, lot_no, sub_lt))

                    if from_loc.upper() != to_loc:
                        self.db.execute("""
                            INSERT INTO stock_movement
                            (lot_no, sub_lt, movement_type, qty_kg,
                             from_location, to_location,
                             reason_code, operator, remarks, created_at)
                            VALUES (?,?,'RELOCATE',?,?,?,?,?,?,?)
                        """, (lot_no, sub_lt, tb_weight,
                              from_loc, to_loc,
                              reason_code, approver,
                              f"batch={batch_id}", now))
                        result['applied'] += 1
                    else:
                        result['skipped'] += 1

                self.db.execute(
                    "UPDATE move_batch SET status='APPROVED', "
                    "approved_by=?, approved_at=? WHERE batch_id=?",
                    (approver, now, batch_id))

            result['success'] = True
            logger.info(f"[MOVE-BATCH] 승인 batch_id={batch_id} "
                        f"applied={result['applied']} skipped={result['skipped']}")
        except Exception as e:
            result['error'] = f"배치 반영 실패 (롤백): {e}"
            logger.error(f"[MOVE-BATCH] 승인 실패: {e}")

        return result

    def reject_batch_move(self, batch_id: str, rejector: str = 'supervisor',
                          reason: str = '') -> dict:
        """대량 이동 요청 반려."""
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            batch = self.db.fetchone(
                "SELECT status FROM move_batch WHERE batch_id=?", (batch_id,))
            if not batch or batch.get('status') != 'PENDING':
                return {'success': False,
                        'error': f"반려 불가: {batch.get('status') if batch else '없음'}"}
            self.db.execute(
                "UPDATE move_batch SET status='REJECTED', "
                "rejected_by=?, rejected_at=?, reject_reason=? "
                "WHERE batch_id=?",
                (rejector, now, reason, batch_id))
            logger.info(f"[MOVE-BATCH] 반려 batch_id={batch_id} by={rejector}")
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_pending_batch_moves(self) -> list:
        """PENDING 상태 대량 이동 요청 목록 반환."""
        try:
            rows = self.db.fetchall(
                "SELECT batch_id, total_count, reason_code, submitted_by, "
                "submitted_at, note "
                "FROM move_batch WHERE status='PENDING' "
                "ORDER BY submitted_at DESC")
            return rows or []
        except Exception:
            return []

    def update_tonbag_status(self, lot_no: str, sub_lt: int,
                             status: str, picked_to: str = None,
                             pick_ref: str = None) -> Dict:
        """
        Update tonbag status (v6.0.7+: PICKED 전환은 AVAILABLE/RESERVED만 허용)
        
        Args:
            lot_no: LOT number
            sub_lt: Sub LOT number
            status: New status (AVAILABLE, PICKED, SAMPLE 등)
            picked_to: Customer name (for PICKED status)
            pick_ref: Sale reference (for PICKED status)
            
        Returns:
            Result dict (success, error)
        """
        result = {'success': False, 'error': None}

        try:
            # v6.0.7+ 상태 전이 화이트리스트: PICKED로의 전환은 AVAILABLE/RESERVED에서만 허용
            new_status = (status or '').strip().upper()
            if new_status == STATUS_PICKED:
                row = self.db.fetchone(
                    "SELECT status FROM inventory_tonbag WHERE lot_no = ? AND sub_lt = ?",
                    (lot_no, sub_lt)
                )
                if row:
                    cur = (row.get('status') or '').strip().upper()
                    if cur not in ('AVAILABLE', 'RESERVED'):
                        result['error'] = f"상태 전이 불가: 현재 {cur} → PICKED (AVAILABLE/RESERVED만 허용)"
                        logger.warning("update_tonbag_status 차단: %s-%s %s → PICKED", lot_no, sub_lt, cur)
                        return result
                else:
                    result['error'] = f"톤백 없음: {lot_no}-{sub_lt}"
                    return result

            update_fields = ["status = ?"]
            params = [status]

            if status == STATUS_PICKED:
                update_fields.append("outbound_date = ?")
                params.append(date.today())

                if picked_to:
                    update_fields.append("picked_to = ?")
                    params.append(picked_to)

                if pick_ref:
                    update_fields.append("pick_ref = ?")
                    params.append(pick_ref)

            elif status == STATUS_AVAILABLE:
                # Clear outbound info when returning to available
                update_fields.extend([
                    "outbound_date = NULL",
                    "picked_to = NULL",
                    "pick_ref = NULL"
                ])

            params.extend([lot_no, sub_lt])

            query = f"""
                UPDATE inventory_tonbag 
                SET {', '.join(update_fields)}
                WHERE lot_no = ? AND sub_lt = ?
            """

            self.db.execute(query, tuple(params))
            result['success'] = True

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            result['error'] = str(e)
            logger.error(f"Status update error: {e}")

        return result

    def create_tonbags_for_lot(self, lot_no: str, count: int,
                               weight_per_bag: float,
                               inbound_date: date = None) -> Dict:
        """
        Create tonbags for a LOT
        
        Args:
            lot_no: LOT number
            count: Number of tonbags to create
            weight_per_bag: Weight per tonbag (kg)
            inbound_date: Inbound date
            
        Returns:
            Result dict
        """
        result = {
            'success': False,
            'created': 0,
            'error': None
        }

        if inbound_date is None:
            inbound_date = date.today()

        try:
            # Get current max sub_lt for this lot
            row = self.db.fetchone(
                "SELECT MAX(sub_lt) as max_sub FROM inventory_tonbag WHERE lot_no = ?",
                (lot_no,)
            )
            start_sub = (row['max_sub'] or 0) + 1

            # v7.7.0: 개별 INSERT → executemany (N+1 → 1회 처리)
            _new_tb_rows = [
                (lot_no, start_sub + i, weight_per_bag, inbound_date)
                for i in range(count)
            ]
            self.db.executemany("""
                INSERT INTO inventory_tonbag
                (lot_no, sub_lt, weight, status, inbound_date)
                VALUES (?, ?, ?, 'AVAILABLE', ?)
            """, _new_tb_rows)
            result['created'] += count

            result['success'] = True
            logger.info(f"Created {count} tonbags for {lot_no}")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            result['error'] = str(e)
            logger.error(f"Create tonbags error: {e}")

        return result

    def delete_tonbag(self, lot_no: str, sub_lt: int) -> Dict:
        """
        Delete a tonbag (only if AVAILABLE)
        
        Args:
            lot_no: LOT number
            sub_lt: Sub LOT number
            
        Returns:
            Result dict
        """
        result = {'success': False, 'error': None}

        try:
            # Check status
            existing = self.db.fetchone(
                "SELECT status FROM inventory_tonbag WHERE lot_no = ? AND sub_lt = ?",
                (lot_no, sub_lt)
            )

            if not existing:
                result['error'] = "Tonbag not found"
                return result

            if existing['status'] != STATUS_AVAILABLE:
                result['error'] = f"Cannot delete tonbag with status: {existing['status']}"
                return result

            self.db.execute(
                "DELETE FROM inventory_tonbag WHERE lot_no = ? AND sub_lt = ?",
                (lot_no, sub_lt)
            )

            result['success'] = True
            logger.info(f"Deleted tonbag: {lot_no}-{sub_lt}")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            result['error'] = str(e)
            logger.error(f"Delete tonbag error: {e}")

        return result
