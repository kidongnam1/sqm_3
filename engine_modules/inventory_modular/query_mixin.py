# ============================================================
# SQM Query Mixin 원칙 (v8.0.5 확정 — 2026-03-16)
# ------------------------------------------------------------
# Query and dashboard must use the same state interpretation
# as central recalc:
#   current_weight = AVAILABLE + RESERVED (sample 제외)
#   picked_weight  = PICKED (sample 제외)
#   출고이력 조회  = PICKED/SOLD/SHIPPED/OUTBOUND 포함
#   OUTBOUND       = current_weight 계산에서 제외
# SOLD는 통계/이력 전용 (핵심 재고 상태 아님)
# ============================================================

"""
SQM 재고관리 시스템 - 조회 기능 Mixin (v3.6.0)
================================================
실제 DB 테이블: inventory, inventory_tonbag, stock_movement, shipment
"""
from engine_modules.constants import STATUS_AVAILABLE, STATUS_RESERVED
import logging
import sqlite3
from typing import Dict, List

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Dict:
    """DB Row → dict 변환"""
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except (TypeError, ValueError):
        if hasattr(row, 'keys'):
            return {k: row[k] for k in row.keys()}
        return {}


def _rows_to_dicts(rows) -> List[Dict]:
    """DB Row 리스트 → dict 리스트 변환"""
    if not rows:
        return []
    return [_row_to_dict(r) for r in rows]


class QueryMixin:
    """재고 조회 Mixin - 실제 DB 스키마 기반"""

    # ══════════════════════════════════════════════════════════
    # inventory 테이블 조회
    # ══════════════════════════════════════════════════════════
    def get_inventory(self, status: str = None, product: str = None,
                      lot_no: str = None) -> List[Dict]:
        """재고 목록 조회 (v3.9.4: 18열 전체 포함, v5.9.9: 컬럼 누락 시 폴백)"""
        query_full = """
            SELECT id, lot_no, sap_no, bl_no, product, product_code,
                   container_no, lot_sqm,
                   sold_to, warehouse, status, location, vessel,
                   initial_weight, current_weight, picked_weight,
                   net_weight, gross_weight, mxbg_pallet,
                   salar_invoice_no, ship_date, arrival_date, con_return, free_time,
                   customs,
                   stock_date, inbound_date, created_at, updated_at
            FROM inventory WHERE 1=1
        """
        query_fallback = """
            SELECT id, lot_no, sap_no, bl_no, product, product_code,
                   container_no, lot_sqm,
                   sold_to, warehouse, status, '' AS location, vessel,
                   initial_weight, current_weight, picked_weight,
                   net_weight, gross_weight, mxbg_pallet,
                   salar_invoice_no, ship_date, arrival_date, con_return, free_time,
                   '' AS customs,
                   stock_date, '' AS inbound_date, created_at, updated_at
            FROM inventory WHERE 1=1
        """
        for query in (query_full, query_fallback):
            try:
                q = query
                params = []
                if status:
                    q += " AND status = ?"
                    params.append(status)
                if product:
                    q += " AND product LIKE ?"
                    params.append(f"%{product}%")
                if lot_no:
                    q += " AND lot_no LIKE ?"
                    params.append(f"%{lot_no}%")
                q += " ORDER BY COALESCE(arrival_date, created_at) DESC, lot_no"
                rows = self.db.fetchall(q, tuple(params))
                from engine_modules.tonbag_compat import normalize_all_rows
                return normalize_all_rows(_rows_to_dicts(rows))
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                if "no such column" in str(e).lower() and query == query_full:
                    logger.debug(f"재고 조회 폴백 (컬럼 누락): {e}")
                    continue
                logger.error(f"재고 조회 오류: {e}")
                return []
        return []

    def get_all_inventory(self) -> List[Dict]:
        """전체 재고 조회 (inventory_tab 호환)"""
        return self.get_inventory()

    def get_inventory_outbound_scheduled(self, status: str = None, product: str = None,
                                          lot_no: str = None) -> List[Dict]:
        """
        출고 예정 테이블 — 재고 리스트에서 Allocation(예약) 삭감 반영.
        정의: 출고 예정 = 재고리스트 - allocation_plan(RESERVED)
        - 행 개수: 재고리스트와 동일(LOT 단위).
        - Balance(Kg) = current_weight - allocated_kg → sum(Balance) = sum(재고 현재고) - sum(예약 Kg).
        """
        base = self.get_inventory(status=status, product=product, lot_no=lot_no)
        if not base:
            return []
        try:
            # allocation_plan 없으면 allocation 반영 없이 기본 재고 반환
            try:
                alloc_rows = self.db.fetchall("""
                SELECT ap.lot_no,
                       COUNT(*) AS allocated_count,
                       COALESCE(SUM(
                           CASE
                               WHEN ap.tonbag_id IS NOT NULL AND t.id IS NOT NULL
                               THEN COALESCE(t.weight, 0)
                               ELSE COALESCE(ap.qty_mt, 0) * 1000.0
                           END
                       ), 0) AS allocated_kg
                FROM allocation_plan ap
                LEFT JOIN inventory_tonbag t ON ap.tonbag_id = t.id
                WHERE ap.status = 'RESERVED'
                  AND COALESCE(t.is_sample, 0) = 0
                GROUP BY ap.lot_no
            """)
            except sqlite3.OperationalError as _e:
                if 'allocation_plan' in str(_e).lower():
                    alloc_rows = []
                else:
                    raise
            alloc_map = {r['lot_no']: r for r in alloc_rows} if alloc_rows else {}

            result = []
            for item in base:
                lot = str(item.get('lot_no', '')).strip()
                curr = float(item.get('current_weight', 0) or 0)
                alloc = alloc_map.get(lot, {})
                alloc_kg = float(alloc.get('allocated_kg', 0) or 0)
                alloc_cnt = int(alloc.get('allocated_count', 0) or 0)
                after = max(0.0, curr - alloc_kg)
                row = dict(item)
                row['allocated_kg'] = alloc_kg
                row['allocated_count'] = alloc_cnt
                row['current_weight_after_allocation'] = after
                result.append(row)
            return result
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"출고 예정 조회 오류: {e}")
            return base

    def get_lot_outbound_history(self, lot_no: str) -> List[Dict]:
        """
        LOT별 출고 이력 — 톤백·샘플의 출고/예약 이력 (여러 번에 걸친 출고 포함).
        PICKED, SOLD, SHIPPED, RESERVED 상태 톤백을 날짜순 정렬.
        """
        try:
            try:
                rows = self.db.fetchall("""
                    SELECT t.id, t.sub_lt, t.weight, t.status AS tonbag_status,
                           t.is_sample, t.picked_to, t.picked_date, t.outbound_date,
                           ap.customer AS alloc_customer, ap.outbound_date AS alloc_outbound_date
                    FROM inventory_tonbag t
                    LEFT JOIN allocation_plan ap ON ap.tonbag_id = t.id AND ap.status IN ('RESERVED','EXECUTED')
                    WHERE t.lot_no = ? AND t.status IN ('PICKED','SOLD','SHIPPED','OUTBOUND','RESERVED')
                    ORDER BY COALESCE(t.outbound_date, t.picked_date, ap.outbound_date, '') DESC,
                             t.sub_lt
                """, (lot_no,))
            except sqlite3.OperationalError as _e:
                if 'allocation_plan' in str(_e).lower():
                    rows = self.db.fetchall("""
                        SELECT id, sub_lt, weight, status AS tonbag_status,
                               is_sample, picked_to, picked_date, outbound_date,
                               picked_to AS alloc_customer, outbound_date AS alloc_outbound_date
                        FROM inventory_tonbag
                        WHERE lot_no = ? AND status IN ('PICKED','SOLD','SHIPPED','OUTBOUND','RESERVED')
                        ORDER BY COALESCE(outbound_date, picked_date, '') DESC, sub_lt
                    """, (lot_no,))
                else:
                    raise
            out = []
            for r in rows:
                d = dict(r)
                d['customer'] = d.get('picked_to') or d.get('alloc_customer') or ''
                d['out_date'] = d.get('outbound_date') or d.get('picked_date') or d.get('alloc_outbound_date') or ''
                out.append(d)
            return out
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"출고 이력 조회 오류: {e}")
            return []

    def get_all_tonbag_outbound_status(self) -> List[Dict]:
        """
        전체 LOT에 대한 톤백 예정/이력 — RESERVED, PICKED, SOLD, SHIPPED 톤백 전부.
        톤백포함 뷰용.
        """
        try:
            try:
                rows = self.db.fetchall("""
                    SELECT t.lot_no, t.id, t.sub_lt, t.weight, t.status AS tonbag_status,
                           t.is_sample, t.picked_to, t.picked_date, t.outbound_date,
                           ap.customer AS alloc_customer, ap.outbound_date AS alloc_outbound_date
                    FROM inventory_tonbag t
                    LEFT JOIN allocation_plan ap ON ap.tonbag_id = t.id AND ap.status IN ('RESERVED','EXECUTED')
                    WHERE t.status IN ('PICKED','SOLD','SHIPPED','OUTBOUND','RESERVED')
                    ORDER BY t.lot_no, COALESCE(t.outbound_date, t.picked_date, ap.outbound_date, '') DESC, t.sub_lt
                """)
            except sqlite3.OperationalError as _e:
                if 'allocation_plan' in str(_e).lower():
                    rows = self.db.fetchall("""
                        SELECT lot_no, id, sub_lt, weight, status AS tonbag_status,
                               is_sample, picked_to, picked_date, outbound_date,
                               picked_to AS alloc_customer, outbound_date AS alloc_outbound_date
                        FROM inventory_tonbag
                        WHERE status IN ('PICKED','SOLD','SHIPPED','OUTBOUND','RESERVED')
                        ORDER BY lot_no, COALESCE(outbound_date, picked_date, '') DESC, sub_lt
                    """)
                else:
                    raise
            out = []
            for r in rows:
                d = dict(r)
                d['customer'] = d.get('picked_to') or d.get('alloc_customer') or ''
                d['out_date'] = d.get('outbound_date') or d.get('picked_date') or d.get('alloc_outbound_date') or ''
                out.append(d)
            return out
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"전체 톤백 출고 현황 조회 오류: {e}")
            return []

    def get_lot_detail(self, lot_no: str) -> Dict:
        """LOT 상세 조회"""
        try:
            row = self.db.fetchone(
                "SELECT * FROM inventory WHERE lot_no = ?", (lot_no,))
            if not row:
                return {'error': f'LOT not found: {lot_no}'}
            lot_data = _row_to_dict(row)
            lot_data['tonbags'] = self.get_tonbags(lot_no=lot_no)
            return lot_data
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"LOT 상세 조회 오류: {e}")
            return {'error': str(e)}

    def get_lot_items(self, lot_no: str) -> List[Dict]:
        """LOT 항목 조회 (톤백 목록)"""
        return self.get_tonbags(lot_no=lot_no)

    # ══════════════════════════════════════════════════════════
    # inventory_tonbag 테이블 조회
    # ══════════════════════════════════════════════════════════

    def get_all_tonbags(self) -> List[Dict]:
        """전체 톤백 조회 (tonbag_tab 호환)"""
        return self.get_tonbags()

    def get_tonbags_with_inventory(self) -> List[Dict]:
        """v3.9.0: 톤백 + 재고(LOT) 정보 JOIN 조회
        v5.9.9: i.customs 등 컬럼 누락 시 폴백
        
        톤백리스트 탭용 — 재고리스트 18열 + TONBAG NO + LOCATION = 20열
        """
        query_full = """
            SELECT 
                i.lot_no, i.sap_no, i.bl_no, i.container_no,
                i.product, i.mxbg_pallet, 
                t.sub_lt AS tonbag_no,
                t.tonbag_uid,
                t.location,
                t.is_sample,
                i.net_weight, i.salar_invoice_no,
                i.ship_date, i.arrival_date,
                i.con_return, i.free_time, i.warehouse,
                t.status AS tonbag_status,
                i.customs,
                i.current_weight, i.initial_weight,
                t.weight AS tonbag_weight,
                t.weight AS tonbag_initial_weight,
                CASE WHEN t.status IN ('PICKED','SOLD','SHIPPED','OUTBOUND','DEPLETED') THEN 0 ELSE t.weight END AS tonbag_current_weight,
                t.picked_date, t.picked_to
            FROM inventory_tonbag t
            LEFT JOIN inventory i ON t.lot_no = i.lot_no
            ORDER BY i.lot_no, t.sub_lt
        """
        query_fallback = """
            SELECT 
                i.lot_no, i.sap_no, i.bl_no, i.container_no,
                i.product, i.mxbg_pallet, 
                t.sub_lt AS tonbag_no,
                t.tonbag_uid,
                t.location,
                t.is_sample,
                i.net_weight, i.salar_invoice_no,
                i.ship_date, i.arrival_date,
                i.con_return, i.free_time, i.warehouse,
                t.status AS tonbag_status,
                '' AS customs,
                i.current_weight, i.initial_weight,
                t.weight AS tonbag_weight,
                t.weight AS tonbag_initial_weight,
                CASE WHEN t.status IN ('PICKED','SOLD','SHIPPED','OUTBOUND','DEPLETED') THEN 0 ELSE t.weight END AS tonbag_current_weight,
                t.picked_date, t.picked_to
            FROM inventory_tonbag t
            LEFT JOIN inventory i ON t.lot_no = i.lot_no
            ORDER BY i.lot_no, t.sub_lt
        """
        for query in (query_full, query_fallback):
            try:
                rows = self.db.fetchall(query)
                from engine_modules.tonbag_compat import normalize_rows
                return normalize_rows(_rows_to_dicts(rows))
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                if "no such column" in str(e).lower() and query == query_full:
                    logger.debug(f"톤백+재고 JOIN 폴백 (컬럼 누락): {e}")
                    continue
                logger.error(f"톤백+재고 JOIN 조회 오류: {e}", exc_info=True)
                return []
        return []

    def get_tonbags(self, lot_no: str = None, status: str = None) -> List[Dict]:
        """v5.5.3 P5: 톤백 조회 (17열 전체 + normalize_rows)"""
        try:
            query = """
                SELECT id, inventory_id, lot_no, sub_lt, sap_no, bl_no,
                       weight, status, location, picked_to, pick_ref,
                       inbound_date, picked_date, outbound_date,
                       remarks, created_at, updated_at
                FROM inventory_tonbag WHERE 1=1
            """
            params = []
            if lot_no:
                query += " AND lot_no = ?"
                params.append(lot_no)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY lot_no, sub_lt"
            rows = self.db.fetchall(query, tuple(params))
            from engine_modules.tonbag_compat import normalize_rows
            return normalize_rows(_rows_to_dicts(rows))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"톤백 조회 오류: {e}")
            return []

    # v5.1.0: 하위 호환 래퍼
    def get_sublots(self, lot_no: str = None, status: str = None) -> List[Dict]:
        """[Deprecated] get_tonbags()로 대체. 하위 호환용."""
        return self.get_tonbags(lot_no=lot_no, status=status)

    # ══════════════════════════════════════════════════════════
    # 요약/집계
    # ══════════════════════════════════════════════════════════
    def get_inventory_summary(self) -> Dict:
        """재고 요약 조회"""
        try:
            query = """
                SELECT
                    COUNT(*) as total_lots,
                    COALESCE(SUM(initial_weight), 0) as total_weight_kg,
                    COALESCE(SUM(current_weight), 0) as available_weight_kg,
                    COALESCE(SUM(picked_weight), 0) as picked_weight_kg,
                    COALESCE(SUM(COALESCE(initial_weight,0) - COALESCE(current_weight,0) - COALESCE(picked_weight,0)), 0) as sold_weight_kg,
                    COALESCE(SUM(mxbg_pallet), 0) as total_bags
                FROM inventory
            """
            row = self.db.fetchone(query)
            if not row:
                return {}
            data = _row_to_dict(row)
            for key in ['total_weight_kg', 'available_weight_kg',
                        'picked_weight_kg', 'sold_weight_kg']:
                data[key.replace('_kg', '_mt')] = (data.get(key) or 0) / 1000
            return data
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"재고 요약 조회 오류: {e}")
            return {}

    def get_inventory_by_product(self) -> List[Dict]:
        """제품별 재고 조회"""
        try:
            query = """
                SELECT product,
                       COUNT(*) as lot_count,
                       COALESCE(SUM(initial_weight), 0) as total_kg,
                       COALESCE(SUM(current_weight), 0) as available_kg,
                       COALESCE(SUM(mxbg_pallet), 0) as bag_count
                FROM inventory
                GROUP BY product ORDER BY product
            """
            rows = self.db.fetchall(query)
            return _rows_to_dicts(rows)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"제품별 재고 조회 오류: {e}")
            return []

    def get_inventory_by_customer(self) -> List[Dict]:
        """고객별 재고 조회 (톤백 기준)"""
        try:
            query = """
                SELECT COALESCE(picked_to, '미배정') as customer,
                       COUNT(DISTINCT lot_no) as lot_count,
                       COALESCE(SUM(weight), 0) as total_kg,
                       COUNT(*) as bag_count
                FROM inventory_tonbag
                WHERE status IN ('PICKED', 'OUTBOUND')
                GROUP BY picked_to ORDER BY total_kg DESC
            """
            rows = self.db.fetchall(query)
            return _rows_to_dicts(rows)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"고객별 재고 조회 오류: {e}")
            return []

    def get_cargo_overview_counts(self, scope: str = 'all') -> Dict:
        """총괄 화물 상태별 LOT 개수 (콤보 표시용).
        scope='all': 총 입고 기준 (전체 inventory, 출고 포함).
        scope='current': 현재 재고 기준 (전체=판매가능+판매배정+판매화물 결정, 출고 제외).
        """
        try:
            if scope == 'current':
                # 현재 재고: 톤백 중 AVAILABLE/RESERVED/PICKED가 하나라도 있는 LOT 수
                cur = self.db.fetchone("""
                    SELECT COUNT(DISTINCT lot_no) AS c FROM inventory_tonbag
                    WHERE status IN ('AVAILABLE','SAMPLE','RESERVED','PICKED')
                """)
                cnt_total = cur.get('c', 0) if isinstance(cur, dict) else (cur[0] if cur else 0)
            else:
                total = self.db.fetchone("SELECT COUNT(*) AS c FROM inventory")
                cnt_total = total.get('c', 0) if isinstance(total, dict) else (total[0] if total else 0)
            # AVAILABLE: RESERVED/PICKED/SOLD 톤백이 하나도 없는 LOT
            avail = self.db.fetchone("""
                SELECT COUNT(DISTINCT i.lot_no) AS c FROM inventory i
                WHERE NOT EXISTS (
                    SELECT 1 FROM inventory_tonbag t
                    WHERE t.lot_no = i.lot_no AND t.status IN ('RESERVED','PICKED','SOLD','SHIPPED','DEPLETED')
                )
                AND EXISTS (SELECT 1 FROM inventory_tonbag t2 WHERE t2.lot_no = i.lot_no)
            """)
            cnt_avail = avail.get('c', 0) if isinstance(avail, dict) else (avail[0] if avail else 0)
            # ★ v8.1.5 BUG-10: LOT 모드(tonbag_id=NULL) + 톤백 모드 모두 포함
            try:
                res = self.db.fetchone("""
                    SELECT COUNT(DISTINCT lot_no) AS c FROM (
                        SELECT lot_no FROM allocation_plan
                        WHERE status = 'RESERVED'
                        UNION
                        SELECT lot_no FROM inventory_tonbag
                        WHERE status = 'RESERVED'
                          AND COALESCE(is_sample, 0) = 0
                    )
                """)
                cnt_reserved = res.get('c', 0) if isinstance(res, dict) else (res[0] if res else 0)
            except sqlite3.OperationalError:
                fb = self.db.fetchone(
                    "SELECT COUNT(DISTINCT lot_no) AS c FROM inventory_tonbag WHERE status = 'RESERVED'"
                )
                cnt_reserved = fb.get('c', 0) if isinstance(fb, dict) else (fb[0] if fb else 0)
            picked = self.db.fetchone("SELECT COUNT(DISTINCT lot_no) AS c FROM inventory_tonbag WHERE status = 'PICKED'")
            cnt_picked = picked.get('c', 0) if isinstance(picked, dict) else (picked[0] if picked else 0)
            sold = self.db.fetchone("SELECT COUNT(DISTINCT lot_no) AS c FROM inventory_tonbag WHERE status IN ('SOLD','OUTBOUND')")
            cnt_sold = sold.get('c', 0) if isinstance(sold, dict) else (sold[0] if sold else 0)
            if scope == 'current':
                cnt_sold = 0  # 현재 재고 기준에서는 출고 개수 미표시
            return {'total': cnt_total, 'AVAILABLE': cnt_avail, 'RESERVED': cnt_reserved, 'PICKED': cnt_picked, 'SOLD': cnt_sold}
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.debug(f"총괄 화물 개수 조회: {e}")
            return {'total': 0, 'AVAILABLE': 0, 'RESERVED': 0, 'PICKED': 0, 'SOLD': 0}

    def get_cargo_overview_lots(self, status_filter: str = None, scope: str = 'all') -> List[Dict]:
        """
        총괄 화물 리스트용 — 상태별 LOT 목록.
        scope='all': 총 입고 기준. scope='current': 현재 재고 기준(전체=판매가능+판매배정+판매화물 결정, 출고 제외).
        - 전체: scope=all → 모든 inventory; scope=current → AVAILABLE/RESERVED/PICKED가 하나라도 있는 LOT.
        - AVAILABLE(판매가능): 톤백이 모두 AVAILABLE/SAMPLE인 LOT만 (RESERVED/PICKED/SOLD 없음).
        - RESERVED(판매배정): allocation_plan(RESERVED)에 포함된 LOT만.
        - PICKED(판매화물 결정): 톤백 중 PICKED가 있는 LOT만.
        - SOLD(출고): 톤백 중 SOLD가 있는 LOT만 (scope=all만).
        """
        if not status_filter or status_filter in ('전체', 'ALL', ''):
            if scope == 'current':
                lot_nos = self.db.fetchall("""
                    SELECT DISTINCT lot_no FROM inventory_tonbag
                    WHERE status IN ('AVAILABLE','SAMPLE','RESERVED','PICKED')
                """)
                if not lot_nos:
                    return []
                placeholders = ','.join('?' * len(lot_nos))
                lot_list = [r.get('lot_no') if isinstance(r, dict) else r[0] for r in lot_nos]
                q = f"SELECT id, lot_no, sap_no, bl_no, product, product_code, container_no, lot_sqm, sold_to, warehouse, status, location, vessel, initial_weight, current_weight, picked_weight, net_weight, gross_weight, mxbg_pallet, salar_invoice_no, ship_date, arrival_date, con_return, free_time, customs, stock_date, inbound_date, created_at, updated_at FROM inventory WHERE lot_no IN ({placeholders}) ORDER BY COALESCE(arrival_date, created_at) DESC, lot_no"
                try:
                    rows = self.db.fetchall(q, tuple(lot_list))
                except sqlite3.OperationalError as e:
                    if "no such column" in str(e).lower():
                        q_fb = f"SELECT id, lot_no, sap_no, bl_no, product, product_code, container_no, lot_sqm, sold_to, warehouse, status, '' AS location, vessel, initial_weight, current_weight, picked_weight, net_weight, gross_weight, mxbg_pallet, salar_invoice_no, ship_date, arrival_date, con_return, free_time, '' AS customs, stock_date, '' AS inbound_date, created_at, updated_at FROM inventory WHERE lot_no IN ({placeholders}) ORDER BY COALESCE(arrival_date, created_at) DESC, lot_no"
                        rows = self.db.fetchall(q_fb, tuple(lot_list))
                    else:
                        raise
                from engine_modules.tonbag_compat import normalize_all_rows
                return normalize_all_rows(_rows_to_dicts(rows))
            return self.get_inventory()
        try:
            status = str(status_filter).strip().upper()
            if status == STATUS_AVAILABLE:
                # 판매가능: RESERVED/PICKED/SOLD 톤백이 하나도 없는 LOT
                lot_nos = self.db.fetchall("""
                    SELECT DISTINCT i.lot_no FROM inventory i
                    WHERE NOT EXISTS (
                        SELECT 1 FROM inventory_tonbag t
                        WHERE t.lot_no = i.lot_no AND t.status IN ('RESERVED','PICKED','SOLD','SHIPPED','DEPLETED')
                    )
                    AND EXISTS (SELECT 1 FROM inventory_tonbag t2 WHERE t2.lot_no = i.lot_no)
                """)
            elif status == STATUS_RESERVED:
                # 판매배정: allocation_plan(RESERVED) lot (tonbag_id NULL 포함) ∪ 톤백 RESERVED(레거시)
                try:
                    lot_nos = self.db.fetchall("""
                        SELECT lot_no FROM (
                            SELECT DISTINCT ap.lot_no AS lot_no
                            FROM allocation_plan ap
                            LEFT JOIN inventory_tonbag tb ON ap.tonbag_id = tb.id
                            WHERE ap.status = 'RESERVED'
                              AND COALESCE(tb.is_sample, 0) = 0
                              AND TRIM(COALESCE(ap.lot_no, '')) != ''
                            UNION
                            SELECT DISTINCT t.lot_no AS lot_no
                            FROM inventory_tonbag t
                            WHERE t.status = 'RESERVED'
                              AND COALESCE(t.is_sample, 0) = 0
                              AND TRIM(COALESCE(t.lot_no, '')) != ''
                        ) u
                        ORDER BY lot_no
                    """)
                except sqlite3.OperationalError as _e:
                    if 'allocation_plan' in str(_e).lower():
                        lot_nos = []
                    else:
                        raise
                if not lot_nos:
                    lot_nos = self.db.fetchall(
                        "SELECT DISTINCT lot_no FROM inventory_tonbag WHERE status = 'RESERVED'"
                    )
            elif status in ('PICKED', 'SOLD', 'SHIPPED', 'DEPLETED'):
                lot_nos = self.db.fetchall("""
                    SELECT DISTINCT lot_no FROM inventory_tonbag
                    WHERE status = ?
                """, (status,))
            else:
                return self.get_inventory()
            if not lot_nos:
                return []
            placeholders = ','.join('?' * len(lot_nos))
            lot_list = [r.get('lot_no') if isinstance(r, dict) else r[0] for r in lot_nos]
            q = f"""
                SELECT id, lot_no, sap_no, bl_no, product, product_code,
                       container_no, lot_sqm, sold_to, warehouse, status, location, vessel,
                       initial_weight, current_weight, picked_weight,
                       net_weight, gross_weight, mxbg_pallet,
                       salar_invoice_no, ship_date, arrival_date, con_return, free_time,
                       customs, stock_date, inbound_date, created_at, updated_at
                FROM inventory
                WHERE lot_no IN ({placeholders})
                ORDER BY COALESCE(arrival_date, created_at) DESC, lot_no
            """
            try:
                rows = self.db.fetchall(q, tuple(lot_list))
            except sqlite3.OperationalError as e:
                if "no such column" in str(e).lower():
                    q_fb = f"""
                        SELECT id, lot_no, sap_no, bl_no, product, product_code,
                               container_no, lot_sqm, sold_to, warehouse, status, '' AS location, vessel,
                               initial_weight, current_weight, picked_weight,
                               net_weight, gross_weight, mxbg_pallet,
                               salar_invoice_no, ship_date, arrival_date, con_return, free_time,
                               '' AS customs, stock_date, '' AS inbound_date, created_at, updated_at
                        FROM inventory
                        WHERE lot_no IN ({placeholders})
                        ORDER BY COALESCE(arrival_date, created_at) DESC, lot_no
                    """
                    rows = self.db.fetchall(q_fb, tuple(lot_list))
                else:
                    raise
            from engine_modules.tonbag_compat import normalize_all_rows
            return normalize_all_rows(_rows_to_dicts(rows))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"총괄 화물 조회 오류: {e}")
            return []

    def search_lots(self, keyword: str = None, **filters) -> List[Dict]:
        """LOT 검색"""
        try:
            query = "SELECT * FROM inventory WHERE 1=1"
            params = []
            if keyword:
                query += """
                    AND (lot_no LIKE ? OR bl_no LIKE ?
                         OR product LIKE ? OR sap_no LIKE ?)
                """
                kw = f"%{keyword}%"
                params.extend([kw, kw, kw, kw])
            safe_columns = {
                'status', 'product', 'bl_no', 'sap_no',
                'warehouse', 'sold_to', 'container_no'
            }
            for key, value in filters.items():
                if value and key in safe_columns:
                    query += f" AND {key} = ?"
                    params.append(value)
            query += " ORDER BY COALESCE(arrival_date, created_at) DESC LIMIT 100"
            rows = self.db.fetchall(query, tuple(params))
            return _rows_to_dicts(rows)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"LOT 검색 오류: {e}")
            return []


    # ═══════════════════════════════════════════════════════════
    # v8.2.0 Phase 3: 자주 반복되는 쿼리 공통 메서드 (N+1 방지)
    # ═══════════════════════════════════════════════════════════

    def count_tonbags(self, status: str = None, lot_no: str = None,
                      is_sample: int = None) -> int:
        """inventory_tonbag 행 수 카운트 — WHERE 조건 선택적 적용.
        21곳에서 반복되던 COUNT 쿼리 단일화.
        """
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if lot_no:
            conditions.append("lot_no = ?")
            params.append(lot_no)
        if is_sample is not None:
            conditions.append("COALESCE(is_sample, 0) = ?")
            params.append(is_sample)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        try:
            row = self.db.fetchone(
                f"SELECT COUNT(*) AS cnt FROM inventory_tonbag {where}",
                tuple(params)
            )
            return int((row.get('cnt') if isinstance(row, dict) else row[0]) or 0) if row else 0
        except Exception as e:
            logger.debug(f"count_tonbags 오류: {e}")
            return 0

    def count_tonbags_by_status(self, lot_no: str) -> dict:
        """LOT별 상태별 톤백 수 한 번에 조회 (N+1 방지용 배치 버전).
        반환: {'AVAILABLE': N, 'RESERVED': N, 'PICKED': N, 'OUTBOUND': N, ...}
        """
        try:
            rows = self.db.fetchall(
                "SELECT status, COUNT(*) AS cnt FROM inventory_tonbag "
                "WHERE lot_no = ? AND COALESCE(is_sample, 0) = 0 GROUP BY status",
                (lot_no,)
            ) or []
            return {
                (r.get('status') if isinstance(r, dict) else r[0]):
                int(r.get('cnt') if isinstance(r, dict) else r[1] or 0)
                for r in rows
            }
        except Exception as e:
            logger.debug(f"count_tonbags_by_status 오류: {e}")
            return {}

    def get_inventory_map(self, lot_nos: list, cols: str = '*') -> dict:
        """lot_no 목록으로 inventory 행 일괄 조회 → dict 반환 (N+1 방지).
        반환: {lot_no: row_dict}
        """
        if not lot_nos:
            return {}
        try:
            ph = ','.join('?' * len(lot_nos))
            rows = self.db.fetchall(
                f"SELECT {cols} FROM inventory WHERE lot_no IN ({ph})",
                tuple(lot_nos)
            ) or []
            return {
                (r.get('lot_no') if isinstance(r, dict) else r[0]): r
                for r in rows
            }
        except Exception as e:
            logger.debug(f"get_inventory_map 오류: {e}")
            return {}

    def get_tonbag_map(self, lot_nos: list, status_filter: list = None) -> dict:
        """lot_no 목록으로 inventory_tonbag 일괄 조회 → {(lot_no, sub_lt): row} dict.
        N+1 쿼리 방지용 배치 조회.
        """
        if not lot_nos:
            return {}
        try:
            ph = ','.join('?' * len(lot_nos))
            params = list(lot_nos)
            where_extra = ""
            if status_filter:
                sph = ','.join('?' * len(status_filter))
                where_extra = f" AND status IN ({sph})"
                params.extend(status_filter)
            rows = self.db.fetchall(
                f"SELECT * FROM inventory_tonbag "
                f"WHERE lot_no IN ({ph}){where_extra}",
                tuple(params)
            ) or []
            return {
                (r.get('lot_no') if isinstance(r, dict) else r[0],
                 r.get('sub_lt')  if isinstance(r, dict) else r[1]): r
                for r in rows
            }
        except Exception as e:
            logger.debug(f"get_tonbag_map 오류: {e}")
            return {}
