# -*- coding: utf-8 -*-
"""
SQM v4.0.1 — 대시보드 데이터/차트 Mixin
==========================================

dashboard_tab.py에서 분리:
- 알림 수집
- 통계 조회
- 차트 그리기 (바차트)
- 자동 갱신
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)


class DashboardDataMixin:
    """대시보드 데이터 수집 및 차트 Mixin"""

    def _get_return_doc_review_pending_count(self, days: int = 30) -> int:
        """
        반품 후 문서 연계 점검 필요 건수 집계.
        RETURN_DOC_REVIEW movement를 기준으로 최근 N일 건수를 조회한다.
        """
        try:
            row = self.engine.db.fetchone(
                """
                SELECT COUNT(*) AS cnt
                FROM stock_movement
                WHERE movement_type = 'RETURN_DOC_REVIEW'
                  AND DATE(created_at) >= DATE('now', ?)
                """,
                (f"-{int(days)} days",),
            )
            return int((row.get('cnt') if isinstance(row, dict) else row[0]) or 0) if row else 0
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError, TypeError, KeyError, OSError) as e:
            logger.debug(f"반품 문서점검 대기건 조회 오류: {e}")
            return 0

    def _collect_alerts(self) -> List[Dict]:
        """알림 수집"""
        alerts = []
        
        try:
            # 1. 재고 부족 알림
            low_stock = self._get_low_stock_lots()
            for lot in low_stock[:5]:
                alerts.append({
                    'icon': '📉',
                    'message': (
                        f"{lot['lot_no']}: 재고 부족 ({lot['weight']:.0f} kg) "
                        f"— 기준치(1,000 kg) 미달, 추가 발주 또는 입고 일정 확인 필요"
                    ),
                    'severity': 'warning',
                    'lot_no': lot['lot_no']
                })
            
            # 2. 장기 체류 LOT 경고 — 삭제됨 (사장님 지시)
            # 3. 톤백 무결성 경고
            integrity_issues = self._check_tonbag_integrity_quick()
            if integrity_issues > 0:
                alerts.append({
                    'icon': '🔧',
                    'message': (
                        f"톤백 무결성 이슈 {integrity_issues}건 "
                        f"— inventory.current_weight ≠ inventory_tonbag 합산 불일치 LOT 감지. "
                        f"[재고관리 → 정합성 검사]에서 LOT별 수동 확인 및 보정 필요"
                    ),
                    'severity': 'error'
                })

            # 4. v6.12.1: 반품 알림 — LOT N회 이상 반품 시 경고
            try:
                from engine_modules.constants import RETURN_ALERT_THRESHOLD
                _threshold = RETURN_ALERT_THRESHOLD
            except ImportError:
                _threshold = 3
            try:
                repeat_lots = self.engine.db.fetchall(f"""
                    WITH combined AS (
                        SELECT lot_no FROM return_log
                        UNION ALL
                        SELECT lot_no FROM return_history
                    )
                    SELECT lot_no, COUNT(*) AS cnt
                    FROM combined
                    GROUP BY lot_no
                    HAVING COUNT(*) >= {_threshold}
                    ORDER BY cnt DESC LIMIT 5
                """)
                for rl in (repeat_lots or []):
                    _lot = rl['lot_no'] if isinstance(rl, dict) else rl[0]
                    _cnt = rl['cnt'] if isinstance(rl, dict) else rl[1]
                    alerts.append({
                        'icon': '🔄',
                        'message': f"{_lot}: 반품 {_cnt}회 — 품질 점검 필요",
                        'severity': 'warning',
                        'lot_no': _lot
                    })
            except Exception as _re:
                logger.debug(f"반품 알림 수집 오류: {_re}")

            # 5. 반품 후 문서 연계 점검 대기 알림
            pending_review = self._get_return_doc_review_pending_count(30)
            if pending_review > 0:
                alerts.append({
                    'icon': '📄',
                    'message': f"반품 문서점검 대기 {pending_review}건 (최근 30일)",
                    'severity': 'error' if pending_review >= 5 else 'warning'
                })

            # v8.3.0 [Phase 11]: Allocation 승인 대기 배지
            try:
                _ap_row = self.engine.db.fetchone("""
                    SELECT COUNT(*) AS cnt
                    FROM allocation_plan
                    WHERE status='STAGED'
                      AND workflow_status='PENDING_APPROVAL'
                """)
                _ap_cnt = (
                    _ap_row.get('cnt', 0) if isinstance(_ap_row, dict)
                    else (_ap_row[0] if _ap_row else 0)
                )
                if _ap_cnt and _ap_cnt > 0:
                    alerts.append({
                        'icon': '✅',
                        'message': (
                            f"Allocation 승인 대기 {_ap_cnt}건 "
                            f"— STAGED 상태로 결재 미완료. "
                            f"[출고 → ✅ 승인 대기] 탭에서 승인 또는 반려 처리 필요"
                        ),
                        'severity': 'warning',
                    })
            except Exception as _ape:
                logger.debug(f"[승인대기 배지] {_ape}")

            # ★ v7.6.0 — 6. Free Time 만료 임박 알림 (D-3 이내)
            try:
                from datetime import date, timedelta
                _today = date.today()
                _d3 = (_today + timedelta(days=3)).isoformat()
                _ft_rows = self.engine.db.fetchall("""
                    SELECT lot_no, container_no, con_return, free_time
                    FROM inventory
                    WHERE con_return IS NOT NULL
                      AND con_return != ''
                      AND con_return <= ?
                      AND status NOT IN ('OUTBOUND','SOLD','DEPLETED')
                    ORDER BY con_return ASC
                    LIMIT 5
                """, (_d3,))
                for _fr in (_ft_rows or []):
                    _lot = _fr['lot_no'] if isinstance(_fr, dict) else _fr[0]
                    _con = _fr['con_return'] if isinstance(_fr, dict) else _fr[2]
                    alerts.append({
                        'icon': '⏰',
                        'message': (
                            f"{_lot}: 컨테이너 반납 D-3 이내 ({_con}) "
                            f"— 기한 초과 시 Demurrage(체선료) 발생, 즉시 반납 또는 연장 협의 필요"
                        ),
                        'severity': 'error',
                        'lot_no': _lot
                    })
            except Exception as _de:
                logger.debug(f"[D 만료임박 알림] {_de}")

            # ★ v7.7.0 — 7. 부분 출고 잔류 감지 (검증 11)
            try:
                _partial_rows = self.engine.db.fetchall("""
                    SELECT lot_no,
                           SUM(CASE WHEN status='SOLD'      AND COALESCE(is_sample,0)=0 THEN 1 ELSE 0 END) AS sold_n,
                           SUM(CASE WHEN status='AVAILABLE' AND COALESCE(is_sample,0)=0 THEN 1 ELSE 0 END) AS avail_n
                    FROM inventory_tonbag
                    GROUP BY lot_no
                    HAVING sold_n > 0 AND avail_n > 0
                    ORDER BY lot_no
                    LIMIT 5
                """)
                for _pr in (_partial_rows or []):
                    _lot   = _pr['lot_no'] if isinstance(_pr, dict) else _pr[0]
                    _sold  = _pr['sold_n']  if isinstance(_pr, dict) else _pr[1]
                    _avail = _pr['avail_n'] if isinstance(_pr, dict) else _pr[2]
                    alerts.append({
                        'icon': '⚠️',
                        'message': (f"{_lot}: 부분 출고 잔류 "
                                    f"(SOLD={_sold} / AVAILABLE={_avail}) — allocation 확인"),
                        'severity': 'warning',
                        'lot_no': _lot,
                    })
            except Exception as _p7e:
                logger.debug(f"[v7.7.0] 부분 출고 잔류 알림 오류: {_p7e}")

            # ★ v7.7.0 — 7. allocation 초과 감지 (검증 12 ERROR)
            try:
                _alloc_err_rows = self.engine.db.fetchall("""
                    SELECT ap.lot_no,
                           ROUND(SUM(ap.qty_mt), 3)             AS alloc_mt,
                           ROUND((iv.initial_weight - 1.0)/1000.0, 3) AS net_mt
                    FROM allocation_plan ap
                    JOIN inventory iv ON iv.lot_no = ap.lot_no
                    WHERE ap.status NOT IN ('CANCELLED', 'REJECTED')
                    GROUP BY ap.lot_no
                    HAVING alloc_mt > net_mt + 0.001
                    ORDER BY ap.lot_no
                    LIMIT 5
                """)
                for _ar in (_alloc_err_rows or []):
                    _lot      = _ar['lot_no']  if isinstance(_ar, dict) else _ar[0]
                    _alloc_mt = _ar['alloc_mt'] if isinstance(_ar, dict) else _ar[1]
                    _net_mt   = _ar['net_mt']   if isinstance(_ar, dict) else _ar[2]
                    alerts.append({
                        'icon': '🔴',
                        'message': (f"{_lot}: allocation 초과 "
                                    f"({_alloc_mt:.3f}MT > 순중량 {_net_mt:.3f}MT)"),
                        'severity': 'error',
                        'lot_no': _lot,
                    })
            except Exception as _a7e:
                logger.debug(f"[v7.7.0] allocation 초과 알림 오류: {_a7e}")

            # [D] v6.8.3: lot_mode 예약 만료 임박 알림 (3일 이내)
            try:
                from datetime import datetime, timedelta
                _d_cutoff = (
                    datetime.now() - timedelta(days=4)
                ).strftime('%Y-%m-%d %H:%M:%S')
                _expiring = self.engine.db.fetchall("""
                    SELECT lot_no, customer, created_at
                    FROM allocation_plan
                    WHERE tonbag_id IS NULL
                      AND status = 'RESERVED'
                      AND created_at < ?
                    ORDER BY created_at ASC LIMIT 5
                """, (_d_cutoff,))
                if _expiring:
                    _exp_cnt = len(_expiring)
                    _exp_lot = (_expiring[0].get('lot_no') if isinstance(_expiring[0], dict)
                                else _expiring[0][0])
                    alerts.append({
                        'icon': '⏰',
                        'message': (
                            f"LOT 단위 예약 만료 임박 {_exp_cnt}건 (3일 이내 자동 취소) "
                            f"— 대표: {_exp_lot} / 바코드 스캔 필요"
                        ),
                        'severity': 'warning',
                        'lot_no': _exp_lot,
                    })
            except Exception as _de:
                logger.debug(f"[D 만료임박 알림] {_de}")

            # ② v6.8.2: 위치 미배정 알림 — 입고 후 배치가 안 된 톤백 자동 감지
            try:
                _ul_data = self._get_unassigned_location_data()
                _ul_total = _ul_data.get('total', 0)
                if _ul_total > 0:
                    _ul_lots = _ul_data.get('lot_count', 0)
                    alerts.append({
                        'icon': '📍',
                        'message': (
                            f"위치 미배정 톤백 {_ul_total}개 ({_ul_lots} LOT) "
                            f"— 입고 후 창고 행·열·단 위치가 미지정 상태. "
                            f"재고 실사 및 위치 추적 불가 — [재고관리 → 위치배정] 즉시 처리 필요"
                        ),
                        'severity': 'error' if _ul_total >= 10 else 'warning',
                    })
            except Exception as _ule:
                logger.debug(f"[② 위치미배정 알림] {_ule}")

            # ★ v8.2.4 — 파싱 실패율 경고 (최근 7일 실패율 30% 초과 시)
            try:
                if hasattr(self.engine, 'get_parsing_stats'):
                    _ps = self.engine.get_parsing_stats(days=7)
                    if _ps.get('total', 0) >= 3 and _ps.get('success_rate', 100) < 70:
                        _fail_cnt = _ps.get('fail', 0)
                        _rate     = _ps.get('success_rate', 0)
                        alerts.append({
                            'icon': '📄',
                            'message': (
                                f"파싱 실패율 높음: 최근 7일 {_fail_cnt}건 실패 "
                                f"(성공률 {_rate}%) — Gemini 설정 확인"
                            ),
                            'severity': 'warning',
                        })
            except Exception as _pe:
                logger.debug(f"[파싱 실패율 알림] {_pe}")

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"알림 수집 오류: {e}")

        return alerts


    def _get_status_four_phase_stats(self) -> Dict:
        """
        v7.3.0: 5단계 현황 (AVAILABLE/RESERVED/PICKED/OUTBOUND+SOLD/RETURN) — 대시보드 카드용.
        inventory_tonbag 기준 건수·중량 집계.
        v8.1.7: RESERVED 표시 — LOT 모드(allocation_plan, tonbag_id NULL) 반영.
          reserved_lot_cnt / reserved_tonbag_cnt / reserved_kg(계획 MT+고아 톤백)
        """
        _empty = {
            'available_cnt': 0, 'reserved_cnt': 0, 'reserved_lot_cnt': 0,
            'reserved_tonbag_cnt': 0, 'picked_cnt': 0,
            'outbound_cnt': 0, 'sold_cnt': 0, 'return_cnt': 0, 'total_cnt': 0,
            'available_kg': 0, 'reserved_kg': 0, 'picked_kg': 0,
            'outbound_kg': 0, 'sold_kg': 0, 'return_kg': 0, 'total_kg': 0,
        }
        try:
            row = self.engine.db.fetchone("""
                SELECT
                    SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) AS available_cnt,
                    SUM(CASE WHEN status = 'RESERVED'  THEN 1 ELSE 0 END) AS reserved_tonbag_cnt,
                    SUM(CASE WHEN status = 'PICKED'    THEN 1 ELSE 0 END) AS picked_cnt,
                    SUM(CASE WHEN status IN ('OUTBOUND','SOLD') THEN 1 ELSE 0 END) AS outbound_cnt,
                    SUM(CASE WHEN status = 'SOLD'      THEN 1 ELSE 0 END) AS sold_cnt,
                    SUM(CASE WHEN status = 'RETURN'    THEN 1 ELSE 0 END) AS return_cnt,
                    COUNT(*) AS total_cnt,
                    COALESCE(SUM(CASE WHEN status = 'AVAILABLE' THEN weight ELSE 0 END), 0) AS available_kg,
                    COALESCE(SUM(CASE WHEN status = 'PICKED'    THEN weight ELSE 0 END), 0) AS picked_kg,
                    COALESCE(SUM(CASE WHEN status IN ('OUTBOUND','SOLD') THEN weight ELSE 0 END), 0) AS outbound_kg,
                    COALESCE(SUM(CASE WHEN status = 'SOLD'      THEN weight ELSE 0 END), 0) AS sold_kg,
                    COALESCE(SUM(CASE WHEN status = 'RETURN'    THEN weight ELSE 0 END), 0) AS return_kg,
                    COALESCE(SUM(weight), 0) AS total_kg,
                    SUM(CASE WHEN status='AVAILABLE' AND COALESCE(is_sample,0)=0 THEN 1 ELSE 0 END) AS avail_tb_cnt,
                    SUM(CASE WHEN status='AVAILABLE' AND COALESCE(is_sample,0)=1 THEN 1 ELSE 0 END) AS avail_samp_cnt,
                    SUM(CASE WHEN status='PICKED'    AND COALESCE(is_sample,0)=0 THEN 1 ELSE 0 END) AS picked_tb_cnt,
                    SUM(CASE WHEN status='PICKED'    AND COALESCE(is_sample,0)=1 THEN 1 ELSE 0 END) AS picked_samp_cnt,
                    SUM(CASE WHEN status IN ('OUTBOUND','SOLD') AND COALESCE(is_sample,0)=0 THEN 1 ELSE 0 END) AS out_tb_cnt,
                    SUM(CASE WHEN status IN ('OUTBOUND','SOLD') AND COALESCE(is_sample,0)=1 THEN 1 ELSE 0 END) AS out_samp_cnt,
                    SUM(CASE WHEN status='RETURN'    AND COALESCE(is_sample,0)=0 THEN 1 ELSE 0 END) AS ret_tb_cnt,
                    SUM(CASE WHEN status='RETURN'    AND COALESCE(is_sample,0)=1 THEN 1 ELSE 0 END) AS ret_samp_cnt
                FROM inventory_tonbag
            """, use_cache=True, cache_ttl=30)
            if not row:
                return dict(_empty)

            reserved_lot_cnt = 0
            reserved_kg = 0.0
            try:
                r2 = self.engine.db.fetchone("""
                    SELECT
                        (SELECT COUNT(*) FROM (
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
                        )) AS reserved_lot_cnt,
                        (SELECT COALESCE(SUM(ap.qty_mt), 0) * 1000.0
                         FROM allocation_plan ap
                         LEFT JOIN inventory_tonbag tb ON ap.tonbag_id = tb.id
                         WHERE ap.status = 'RESERVED'
                           AND COALESCE(tb.is_sample, 0) = 0) AS kg_plan,
                        (SELECT COALESCE(SUM(t.weight), 0)
                         FROM inventory_tonbag t
                         WHERE t.status = 'RESERVED'
                           AND COALESCE(t.is_sample, 0) = 0
                           AND NOT EXISTS (
                             SELECT 1 FROM allocation_plan ap
                             WHERE ap.tonbag_id = t.id AND ap.status = 'RESERVED'
                           )) AS kg_orphan_tb
                """, use_cache=True, cache_ttl=30)
                if r2:
                    reserved_lot_cnt = int(r2.get('reserved_lot_cnt') or 0)
                    kg_plan = float(r2.get('kg_plan') or 0)
                    kg_orphan = float(r2.get('kg_orphan_tb') or 0)
                    reserved_kg = kg_plan + kg_orphan
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError, ValueError, TypeError) as e:
                logger.debug(f"RESERVED(allocation_plan) 통계 보조 쿼리: {e}")

            rtb = int(row.get('reserved_tonbag_cnt') or 0)
            return {
                'available_cnt': row['available_cnt'] or 0,
                'reserved_cnt': reserved_lot_cnt,
                'reserved_lot_cnt': reserved_lot_cnt,
                'reserved_tonbag_cnt': rtb,
                'picked_cnt': row['picked_cnt'] or 0,
                'outbound_cnt': row['outbound_cnt'] or 0,
                'sold_cnt': row['sold_cnt'] or 0,
                'return_cnt': row['return_cnt'] or 0,
                'total_cnt': row['total_cnt'] or 0,
                'available_kg': row['available_kg'] or 0,
                'reserved_kg': reserved_kg,
                'picked_kg': row['picked_kg'] or 0,
                'outbound_kg': row['outbound_kg'] or 0,
                'sold_kg': row['sold_kg'] or 0,
                'return_kg': row['return_kg'] or 0,
                'total_kg': row['total_kg'] or 0,
                # v8.1.5: 톤백/샘플 구분 신규 키
                'avail_tb_cnt':    int(row.get('avail_tb_cnt',  0) or 0),
                'avail_samp_cnt':  int(row.get('avail_samp_cnt',0) or 0),
                'picked_tb_cnt':   int(row.get('picked_tb_cnt', 0) or 0),
                'picked_samp_cnt': int(row.get('picked_samp_cnt',0) or 0),
                'out_tb_cnt':      int(row.get('out_tb_cnt',    0) or 0),
                'out_samp_cnt':    int(row.get('out_samp_cnt',  0) or 0),
                'ret_tb_cnt':      int(row.get('ret_tb_cnt',    0) or 0),
                'ret_samp_cnt':    int(row.get('ret_samp_cnt',  0) or 0),
            }
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.debug(f"5단계 통계 오류: {e}")
            return dict(_empty)

    def _get_product_tonbag_sample_breakdown(self) -> List[Dict]:
        """
        v4.1.8: 제품별 톤백/샘플 구분 통계
        
        변경사항:
        - 샘플 제품명: [SAMPLE] → _sample 형식으로 변경
        - lot_count 변수 NameError 버그 수정
        """
        try:
            rows = self.engine.db.fetchall("""
                SELECT
                    i.product,
                    COALESCE(t.is_sample, 0) AS is_sample,
                    COUNT(DISTINCT i.lot_no) AS lot_count,
                    SUM(CASE WHEN t.status='AVAILABLE' THEN t.weight ELSE 0 END) AS tonbag_kg,
                    SUM(CASE WHEN t.status='AVAILABLE' THEN 1 ELSE 0 END) AS tonbag_cnt,
                    COALESCE(SUM(CASE WHEN t.status='AVAILABLE' THEN t.weight ELSE 0 END), 0) AS total_kg,
                    SUM(CASE WHEN t.status='AVAILABLE' THEN 1 ELSE 0 END) AS total_cnt
                FROM inventory i
                LEFT JOIN inventory_tonbag t ON i.lot_no = t.lot_no
                GROUP BY i.product, COALESCE(t.is_sample, 0)
                ORDER BY i.product, COALESCE(t.is_sample, 0) DESC
            """)
            result = []
            for r in rows:
                product = r['product'] or 'Unknown'
                is_sample = r['is_sample'] or 0
                r_lot_count = r['lot_count'] or 0  # ✅ v4.1.8: NameError 방지
                
                # ✅ v4.1.8: 샘플 제품명 표기 개선
                if is_sample:
                    if product and not str(product).endswith('_sample'):
                        product = f"{product}_sample"
                    r_lot_count = 0  # 샘플은 LOT 수 0으로 표시
                
                tb_kg = r['tonbag_kg'] or 0
                tb_cnt = r['tonbag_cnt'] or 0
                
                # 샘플 행: tonbag=0, sample=전부 / 일반 행: tonbag=전부, sample=0
                if is_sample:
                    result.append({
                        'product': product, 
                        'lot_count': r_lot_count,  # ✅ 수정
                        'tonbag_kg': 0, 'tonbag_cnt': 0,
                        'sample_kg': tb_kg, 'sample_cnt': tb_cnt,
                        'total_kg': r['total_kg'] or 0, 'total_cnt': r['total_cnt'] or 0,
                    })
                else:
                    result.append({
                        'product': product, 
                        'lot_count': r_lot_count,  # ✅ 수정
                        'tonbag_kg': tb_kg, 'tonbag_cnt': tb_cnt,
                        'sample_kg': 0, 'sample_cnt': 0,
                        'total_kg': r['total_kg'] or 0, 'total_cnt': r['total_cnt'] or 0,
                    })
            return result
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.debug(f"제품별 톤백/샘플 통계 오류: {e}")
            return []


    def _get_low_stock_lots(self, threshold: float = 1000) -> List[Dict]:
        """재고 부족 LOT 조회"""
        try:
            cursor = None
            conn = self.engine.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT lot_no, current_weight 
                FROM inventory 
                WHERE status = 'AVAILABLE' AND current_weight > 0 AND current_weight < ?
                ORDER BY current_weight ASC
                LIMIT 10
            ''', (threshold,))
            
            return [{'lot_no': row[0], 'weight': row[1]} for row in cursor.fetchall()]
            
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"재고 부족 조회 오류: {e}")
            return []
    
        finally:
            if cursor:
                try:
                    cursor.close()
                except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                    logger.debug(f"{type(_e).__name__}: {_e}")
                except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                    logger.debug(f"dashboard_tab: {_e}")
    def _check_tonbag_integrity_quick(self) -> int:
        """톤백 무결성 빠른 검사"""
        try:
            cursor = None
            conn = self.engine.get_connection()
            cursor = conn.cursor()
            
            # current_weight != SUM(AVAILABLE tonbag) 인 LOT 수
            cursor.execute('''
                SELECT COUNT(*) FROM (
                    SELECT i.lot_no
                    FROM inventory i
                    LEFT JOIN (
                        SELECT lot_no, COALESCE(SUM(weight), 0) as tonbag_sum
                        FROM inventory_tonbag
                        WHERE status = 'AVAILABLE'
                        GROUP BY lot_no
                    ) t ON i.lot_no = t.lot_no
                    WHERE ABS(i.current_weight - COALESCE(t.tonbag_sum, 0)) > 0.01
                      AND i.status = 'AVAILABLE'
                )
            ''')
            
            return cursor.fetchone()[0] or 0
            
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"무결성 검사 오류: {e}")
            return 0
    
        finally:
            if cursor:
                try:
                    cursor.close()
                except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                    logger.debug(f"{type(_e).__name__}: {_e}")
                except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                    logger.debug(f"dashboard_tab: {_e}")
    
    # =========================================================
    # 빠른 액션 핸들러
    # =========================================================
    
    def _quick_pdf_inbound(self) -> None:
        """빠른 PDF 입고"""
        if hasattr(self, '_handle_pdf_import'):
            self._handle_pdf_import()
        else:
            self._log("PDF 입고 기능 준비 중...")
    
    def _quick_outbound(self) -> None:
        """빠른 출고 — v8.1.6: 위젯 참조(tab_allocation)로 판매배정 탭 이동."""
        tab = getattr(self, 'tab_allocation', None)
        if tab and hasattr(self, 'notebook'):
            try:
                self.notebook.select(tab)
            except Exception as e:
                logger.warning(f'[UI] dashboard_data_mixin: {e}')
    def _quick_search(self) -> None:
        """빠른 검색 — v8.1.6: 위젯 참조(tab_inventory)로 판매가능 탭 이동."""
        tab = getattr(self, 'tab_inventory', None)
        if tab and hasattr(self, 'notebook'):
            try:
                self.notebook.select(tab)
            except Exception as e:
                logger.warning(f'[UI] dashboard_data_mixin: {e}')
    def _quick_report(self) -> None:
        """빠른 보고서"""
        if hasattr(self, '_generate_summary_report'):
            self._generate_summary_report()
    
    def _quick_backup(self) -> None:
        """빠른 백업"""
        if hasattr(self, '_handle_backup'):
            self._handle_backup()
        else:
            self._log("백업 기능 준비 중...")
    
    def _on_alert_double_click(self, event) -> None:
        """알림 더블클릭 시 해당 LOT로 이동"""
        selection = self.alert_listbox.curselection()
        if not selection:
            return
        
        text = self.alert_listbox.get(selection[0])

        # 반품 문서점검 대기 알림은 반품 통계 화면으로 이동
        if "반품 문서점검 대기" in text and hasattr(self, "_show_return_statistics"):
            self._show_return_statistics()
            return

        # LOT 번호 추출 시도
        # 예: "📉 LOT-001: 재고 부족 (500kg)"
        if ':' in text:
            lot_part = text.split(':')[0]
            lot_no = lot_part.split()[-1] if lot_part else None
            
            if lot_no and hasattr(self, '_search_lot'):
                self._search_lot(lot_no)
    
    # =========================================================
    # 자동 새로고침
    # =========================================================
    
    def _start_auto_refresh(self) -> None:
        """자동 새로고침 시작"""
        if self.auto_refresh_var.get():
            try:
                self._refresh_dashboard()
            except (ValueError, TypeError, KeyError) as _e:
                logger.debug(f"{type(_e).__name__}: {_e}")
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"Auto-refresh error: {_e}")
            # v3.6.2: 에러 발생해도 타이머는 계속 동작
            self._auto_refresh_job = self.root.after(30000, self._start_auto_refresh)
    
    def _toggle_auto_refresh(self) -> None:
        """자동 새로고침 토글"""
        if self.auto_refresh_var.get():
            self._start_auto_refresh()
        else:
            if self._auto_refresh_job:
                self.root.after_cancel(self._auto_refresh_job)
                self._auto_refresh_job = None
    
    def _stop_auto_refresh(self) -> None:
        """자동 새로고침 중지"""
        if self._auto_refresh_job:
            self.root.after_cancel(self._auto_refresh_job)
            self._auto_refresh_job = None
    
    # =========================================================
    # 차트 (v3.6.0 추가)
    # =========================================================
    
    def _refresh_dashboard_chart(self) -> None:
        """입출고 추이 차트 새로고침"""
        if not hasattr(self, 'chart_canvas'):
            return
        
        try:
            # 캔버스 초기화
            self.chart_canvas.delete('all')
            
            # 캔버스 크기
            self.chart_canvas.update_idletasks()
            width = self.chart_canvas.winfo_width() or 250
            height = self.chart_canvas.winfo_height() or 180
            
            # 여백
            margin_left = 50
            margin_right = 20
            margin_top = 20
            margin_bottom = 40
            
            chart_width = width - margin_left - margin_right
            chart_height = height - margin_top - margin_bottom
            
            # 최근 7일 데이터 가져오기
            data = self._get_weekly_io_data()
            
            if not data:
                # 데이터 없음 표시
                self.chart_canvas.create_text(
                    width // 2, height // 2,
                    text="데이터 없음",
                    fill='#999',
                    font=('맑은 고딕', 13)
                )
                return
            
            # 최대값 계산
            max_value = max(
                max(d.get('inbound', 0) for d in data),
                max(d.get('outbound', 0) for d in data),
                1  # 0 방지
            )
            
            # 막대 너비
            bar_width = chart_width // (len(data) * 3)
            gap = bar_width // 2
            
            # Y축 그리드
            for i in range(5):
                y = margin_top + (chart_height * i // 4)
                self.chart_canvas.create_line(
                    margin_left, y, width - margin_right, y,
                    fill='#eee', dash=(2, 2)
                )
                # Y축 레이블
                value = max_value * (4 - i) // 4
                self.chart_canvas.create_text(
                    margin_left - 5, y,
                    text=f"{value/1000:.0f}t",
                    anchor='e',
                    fill='#999',
                    font=('', 13)
                )
            
            # 막대 그래프
            for i, day_data in enumerate(data):
                x_base = margin_left + (i * (bar_width * 3 + gap))
                
                inbound = day_data.get('inbound', 0)
                outbound = day_data.get('outbound', 0)
                date_str = day_data.get('date', '')[-5:]  # MM-DD
                
                # 입고 막대 (녹색)
                in_height = (inbound / max_value) * chart_height if max_value > 0 else 0
                self.chart_canvas.create_rectangle(
                    x_base, margin_top + chart_height - in_height,
                    x_base + bar_width, margin_top + chart_height,
                    fill='#27ae60', outline='#1e8449'
                )
                
                # 출고 막대 (주황)
                out_height = (outbound / max_value) * chart_height if max_value > 0 else 0
                self.chart_canvas.create_rectangle(
                    x_base + bar_width + 2, margin_top + chart_height - out_height,
                    x_base + bar_width * 2 + 2, margin_top + chart_height,
                    fill='#e67e22', outline='#d35400'
                )
                
                # X축 레이블 (날짜)
                self.chart_canvas.create_text(
                    x_base + bar_width, margin_top + chart_height + 15,
                    text=date_str,
                    fill='#666',
                    font=('', 13)
                )
            
        except (AttributeError, RuntimeError) as e:
            logger.error(f"차트 새로고침 오류: {e}")
    
    def _get_weekly_io_data(self) -> List[Dict]:
        """최근 7일 입출고 데이터 조회
        v8.2.0 N+1 → 2쿼리(GROUP BY)로 최적화: 14쿼리 → 2쿼리.
        """
        try:
            db = self.engine.db
            # 입고: 날짜별 GROUP BY — 쿼리 1회
            inbound_rows = db.fetchall("""
                SELECT DATE(arrival_date) AS d,
                       COALESCE(SUM(initial_weight), 0) AS kg
                FROM inventory
                WHERE DATE(arrival_date) >= DATE('now', '-6 days')
                GROUP BY DATE(arrival_date)
            """) or []
            inbound_map = {
                (r.get('d') if isinstance(r, dict) else r[0]):
                float(r.get('kg') if isinstance(r, dict) else r[1] or 0)
                for r in inbound_rows
            }
            # 출고: 날짜별 GROUP BY — 쿼리 1회
            outbound_rows = db.fetchall("""
                SELECT DATE(created_at) AS d,
                       COALESCE(SUM(qty_kg), 0) AS kg
                FROM stock_movement
                WHERE movement_type = 'OUTBOUND'
                  AND DATE(created_at) >= DATE('now', '-6 days')
                GROUP BY DATE(created_at)
            """) or []
            outbound_map = {
                (r.get('d') if isinstance(r, dict) else r[0]):
                float(r.get('kg') if isinstance(r, dict) else r[1] or 0)
                for r in outbound_rows
            }
            result = []
            for i in range(6, -1, -1):
                date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                result.append({
                    'date':     date,
                    'inbound':  inbound_map.get(date, 0),
                    'outbound': outbound_map.get(date, 0),
                })
            return result
            
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"주간 데이터 조회 오류: {e}")
            return []

        finally:
            if cursor:
                try:
                    cursor.close()
                except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                    logger.debug(f"{type(_e).__name__}: {_e}")
                except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                    logger.debug(f"dashboard_tab: {_e}")

    # =========================================================
    # v6.12.1: 반품률 대시보드 위젯
    # =========================================================


    # =========================================================
    # v6.7.2: 스캔 실패율 KPI
    # =========================================================

    def _get_scan_fail_rate_data(self) -> dict:
        """
        v6.7.2: 스캔 실패율 데이터.
        stock_movement의 SCAN_FAIL + audit_log 기반 집계.
        데이터 없으면 graceful N/A 반환.
        """
        result = {
            'total_scans': 0, 'fail_scans': 0,
            'fail_rate': 0.0, 'period_days': 30,
        }
        try:
            db = self.engine.db

            # 전체 스캔 (OUTBOUND 이동 = 출고 스캔)
            row = db.fetchone("""
                SELECT COUNT(*) AS cnt
                FROM stock_movement
                WHERE movement_type IN ('OUTBOUND','SOLD','PICKED')
                  AND created_at >= date('now', '-30 days')
            """)
            total = int(row['cnt'] if isinstance(row, dict) else (row[0] if row else 0))

            # SCAN_FAIL 이벤트 (audit_log 우선, stock_movement 보조)
            fail = 0
            try:
                r2 = db.fetchone("""
                    SELECT COUNT(*) AS cnt FROM audit_log
                    WHERE event_type LIKE '%SCAN_FAIL%'
                      AND created_at >= date('now', '-30 days')
                """)
                fail = int(r2['cnt'] if isinstance(r2, dict) else (r2[0] if r2 else 0))
            except Exception:
                logger.debug("[SUPPRESSED] exception in dashboard_data_mixin.py")  # noqa
            if fail == 0:
                try:
                    r3 = db.fetchone("""
                        SELECT COUNT(*) AS cnt FROM stock_movement
                        WHERE movement_type = 'SCAN_FAIL'
                          AND created_at >= date('now', '-30 days')
                    """)
                    fail = int(r3['cnt'] if isinstance(r3, dict) else (r3[0] if r3 else 0))
                except Exception:
                    logger.debug("[SUPPRESSED] exception in dashboard_data_mixin.py")  # noqa

            result['total_scans'] = total
            result['fail_scans']  = fail
            result['fail_rate']   = (fail / total * 100) if total > 0 else 0.0
        except Exception as e:
            logger.debug(f"[scan_fail_rate] {e}")
        return result

    def _refresh_dashboard_scan_fail(self) -> None:
        """v6.7.2: 스캔 실패율 카드 갱신."""
        if not hasattr(self, '_scan_fail_text'):
            return
        d = self._get_scan_fail_rate_data()
        rate    = d['fail_rate']
        total   = d['total_scans']
        fail    = d['fail_scans']
        period  = d['period_days']

        if total == 0:
            body = "최근 30일 스캔 데이터 없음"
            color = 'gray'
        else:
            color = '#e74c3c' if rate >= 5 else ('#e67e22' if rate >= 2 else '#27ae60')
            body = "\n".join([
                "실패율: {:.1f}%".format(rate),
                "전체: {:,}건  실패: {:,}건".format(total, fail),
                "기간: 최근 {}일".format(period),
            ])

        try:
            self._scan_fail_text.config(state='normal')
            self._scan_fail_text.delete('1.0', 'end')
            self._scan_fail_text.insert('end', body)
            self._scan_fail_text.config(
                state='disabled',
                fg=color
            )
        except Exception as e:
            logger.debug(f"[scan_fail_ui] {e}")

    # =========================================================
    # v6.7.3: LOT 평균 재고기간 KPI
    # =========================================================

    def _get_avg_lot_days_data(self) -> dict:
        """
        v6.7.3: LOT 평균 재고기간.
        입고일(arrival_date / stock_date) ~ 출고일(sold 이동) 기준.
        AVAILABLE LOT은 오늘 기준 현재 체류일 표시.
        """
        result = {
            'avg_days_sold': 0.0,
            'avg_days_available': 0.0,
            'max_days': 0,
            'long_lot': '',
            'available_lots': 0,
        }
        try:
            db = self.engine.db

            # 출고 완료 LOT 평균 재고기간
            row = db.fetchone("""
                SELECT AVG(julianday(sm.created_at) -
                           julianday(COALESCE(inv.stock_date, inv.arrival_date, inv.created_at))) AS avg_d
                FROM inventory inv
                JOIN stock_movement sm ON sm.lot_no = inv.lot_no
                WHERE sm.movement_type IN ('SOLD','OUTBOUND')
                  AND COALESCE(inv.stock_date, inv.arrival_date) IS NOT NULL
                  AND sm.created_at >= date('now', '-180 days')
            """)
            if row:
                v = row['avg_d'] if isinstance(row, dict) else row[0]
                result['avg_days_sold'] = round(float(v or 0), 1)

            # 현재 AVAILABLE LOT 체류일 평균 + 최장 LOT
            row2 = db.fetchone("""
                SELECT AVG(julianday('now') -
                           julianday(COALESCE(stock_date, arrival_date, created_at))) AS avg_d,
                       MAX(julianday('now') -
                           julianday(COALESCE(stock_date, arrival_date, created_at))) AS max_d,
                       COUNT(*) AS cnt
                FROM inventory
                WHERE status = 'AVAILABLE'
                  AND COALESCE(stock_date, arrival_date) IS NOT NULL
            """)
            if row2:
                avg2 = row2['avg_d'] if isinstance(row2, dict) else row2[0]
                max2 = row2['max_d'] if isinstance(row2, dict) else row2[1]
                cnt2 = row2['cnt']  if isinstance(row2, dict) else row2[2]
                result['avg_days_available'] = round(float(avg2 or 0), 1)
                result['max_days']           = int(float(max2 or 0))
                result['available_lots']     = int(cnt2 or 0)

            # 가장 오래 체류 중인 LOT
            row3 = db.fetchone("""
                SELECT lot_no,
                       CAST(julianday('now') -
                            julianday(COALESCE(stock_date, arrival_date, created_at)) AS INTEGER) AS days
                FROM inventory
                WHERE status = 'AVAILABLE'
                  AND COALESCE(stock_date, arrival_date) IS NOT NULL
                ORDER BY days DESC LIMIT 1
            """)
            if row3:
                lot  = row3['lot_no'] if isinstance(row3, dict) else row3[0]
                days = row3['days']   if isinstance(row3, dict) else row3[1]
                result['long_lot'] = f"{lot} ({days}일)"
        except Exception as e:
            logger.debug(f"[avg_lot_days] {e}")
        return result

    def _refresh_dashboard_avg_lot_days(self) -> None:
        """v6.7.3: LOT 평균 재고기간 카드 갱신."""
        if not hasattr(self, '_avg_lot_days_text'):
            return
        d = self._get_avg_lot_days_data()

        avg_s = d['avg_days_sold']
        avg_a = d['avg_days_available']
        max_d = d['max_days']
        long  = d['long_lot']
        cnt   = d['available_lots']

        if cnt == 0 and avg_s == 0:
            body  = "재고기간 데이터 없음"
            color = 'gray'
        else:
            color = ('#e74c3c' if max_d >= 180
                     else '#e67e22' if max_d >= 90
                     else '#27ae60')
            body = "\n".join([
                "입고→출고 평균: {}일".format(int(avg_s)),
                "현 재고 평균:  {}일 ({}LOT)".format(int(avg_a), cnt),
                "최장 체류: {}".format(long or '-'),
            ])
        try:
            self._avg_lot_days_text.config(state='normal')
            self._avg_lot_days_text.delete('1.0', 'end')
            self._avg_lot_days_text.insert('end', body)
            self._avg_lot_days_text.config(state='disabled', fg=color)
        except Exception as e:
            logger.debug(f"[avg_lot_days_ui] {e}")

    # =========================================================
    # [P1] v6.8.1: 위치 미배정 톤백 KPI
    # =========================================================

    def _get_unassigned_location_data(self) -> dict:
        """입고 후 location=NULL/공백인 AVAILABLE 톤백 집계."""
        result = {'total': 0, 'lots': [], 'lot_count': 0}
        try:
            db = self.engine.db
            row = db.fetchone("""
                SELECT COUNT(*) AS cnt
                FROM inventory_tonbag
                WHERE status = 'AVAILABLE'
                  AND COALESCE(is_sample, 0) = 0
                  AND (location IS NULL OR TRIM(location) = '')
            """)
            total = int((row['cnt'] if isinstance(row, dict) else row[0]) or 0) if row else 0
            result['total'] = total
            if total > 0:
                rows = db.fetchall("""
                    SELECT lot_no, COUNT(*) AS cnt
                    FROM inventory_tonbag
                    WHERE status = 'AVAILABLE'
                      AND COALESCE(is_sample, 0) = 0
                      AND (location IS NULL OR TRIM(location) = '')
                    GROUP BY lot_no ORDER BY cnt DESC LIMIT 5
                """)
                result['lots'] = [
                    (r['lot_no'] if isinstance(r, dict) else r[0],
                     int(r['cnt']  if isinstance(r, dict) else r[1]))
                    for r in (rows or [])
                ]
                result['lot_count'] = len(result['lots'])
        except Exception as e:
            logger.debug(f"[unassigned_loc] {e}")
        return result

    def _navigate_to_unassigned_location(self, event=None) -> None:
        """① v6.8.2: 위치 미배정 KPI 카드 클릭 → 판매가능 탭 이동
        search_var에 '위치미배정' 키워드 설정하여 필터 적용.
        v8.1.6: 위젯 참조(tab_inventory)로 교체.
        """
        try:
            # 판매가능 탭으로 전환 — 위젯 참조 방식
            tab = getattr(self, 'tab_inventory', None)
            if tab and hasattr(self, 'notebook'):
                self.notebook.select(tab)
            # 위치 미배정 필터 적용 — inventory_tab의 search_var 활용
            # _unassigned_loc_filter 플래그로 inventory_tab 측에서 감지
            if hasattr(self, '_unassigned_loc_filter_var'):
                self._unassigned_loc_filter_var.set(True)
            elif hasattr(self, 'search_var'):
                self.search_var.set('')  # 기존 검색 초기화
            # 재고 탭 갱신 트리거
            if hasattr(self, '_refresh_inventory'):
                self._refresh_inventory()
            logger.info("[① 드릴다운] 위치 미배정 → 판매가능 탭 이동")
        except Exception as e:
            logger.debug(f"[드릴다운] {e}")

    def _refresh_dashboard_unassigned_location(self) -> None:
        """[P1] v6.8.1: 위치 미배정 톤백 KPI 카드 갱신."""
        if not hasattr(self, '_unassigned_loc_text'):
            return
        d = self._get_unassigned_location_data()
        total = d['total']
        if total == 0:
            body  = "✅ 위치 미배정 없음"
            color = '#27ae60'
        else:
            lines = [f"⚠ 클릭하여 목록 보기 → {total}개 미배정"]
            for lot_no, cnt in d['lots'][:3]:
                lines.append(f"  {lot_no}: {cnt}개")
            if d['lot_count'] > 3:
                lines.append(f"  … 외 {d['lot_count']-3} LOT")
            body  = "\n".join(lines)
            color = '#e74c3c' if total >= 10 else '#e67e22'
        try:
            self._unassigned_loc_text.config(state='normal')
            self._unassigned_loc_text.delete('1.0', 'end')
            self._unassigned_loc_text.insert('end', body)
            self._unassigned_loc_text.config(state='disabled', fg=color)
            # ① 드릴다운 클릭 바인딩 (최초 1회)
            if not getattr(self, '_unassigned_drilldown_bound', False):
                self._unassigned_loc_text.bind('<Button-1>',
                    self._navigate_to_unassigned_location)
                self._unassigned_loc_text.config(cursor='hand2')
                self._unassigned_drilldown_bound = True
        except Exception as e:
            logger.debug(f"[unassigned_loc_ui] {e}")

    def _get_return_rate_data(self) -> Dict:
        """반품률 데이터 수집 (최근 30일 기준)."""
        result = {
            'return_count': 0,
            'outbound_count': 0,
            'return_rate': 0.0,
            'return_weight_kg': 0.0,
            'top_reasons': [],
        }
        try:
            # v7.1.0: return_log(REINBOUND) + return_history(레거시) UNION
            row = self.engine.db.fetchone("""
                WITH combined AS (
                    SELECT weight_kg, return_date, reason FROM return_log
                    UNION ALL
                    SELECT weight_kg, return_date, reason FROM return_history
                )
                SELECT COUNT(*) AS cnt, COALESCE(SUM(weight_kg), 0) AS total
                FROM combined
                WHERE return_date >= date('now', '-30 days')
            """)
            if row:
                result['return_count'] = row['cnt'] if isinstance(row, dict) else row[0]
                result['return_weight_kg'] = float(row['total'] if isinstance(row, dict) else row[1])

            row2 = self.engine.db.fetchone("""
                SELECT COUNT(*) AS cnt FROM stock_movement
                WHERE movement_type IN ('PICKED', 'SOLD', 'OUTBOUND')
                AND created_at >= date('now', '-30 days')
            """)
            if row2:
                result['outbound_count'] = row2['cnt'] if isinstance(row2, dict) else row2[0]

            total_out = result['outbound_count'] or 1
            result['return_rate'] = result['return_count'] / total_out * 100

            rows = self.engine.db.fetchall("""
                WITH combined AS (
                    SELECT reason, return_date FROM return_log
                    UNION ALL
                    SELECT reason, return_date FROM return_history
                )
                SELECT COALESCE(reason, '미기재') AS reason, COUNT(*) AS cnt
                FROM combined
                WHERE return_date >= date('now', '-30 days')
                GROUP BY COALESCE(reason, '미기재')
                ORDER BY cnt DESC LIMIT 3
            """)
            result['top_reasons'] = [
                {'reason': r['reason'] if isinstance(r, dict) else r[0],
                 'count': r['cnt'] if isinstance(r, dict) else r[1]}
                for r in rows
            ]
        except Exception as e:
            logger.debug(f"[return_rate] data error: {e}")
        return result

    def _refresh_dashboard_return_rate(self) -> None:
        """반품률 위젯 새로고침."""
        if not hasattr(self, '_return_info_text'):
            return
        try:
            data = self._get_return_rate_data()
            lines = [
                "📊 최근 30일 반품 현황",
                "",
                f"  반품: {data['return_count']}건 ({data['return_weight_kg']:,.0f}kg)",
                f"  출고: {data['outbound_count']}건",
            ]
            rate = data['return_rate']
            rate_icon = '🟢' if rate < 3 else ('🟡' if rate < 10 else '🔴')
            lines.append(f"  반품률: {rate_icon} {rate:.1f}%")
            pending_review = self._get_return_doc_review_pending_count(30)
            review_icon = '🟢' if pending_review == 0 else ('🟡' if pending_review < 5 else '🔴')
            lines.append(f"  문서점검 대기: {review_icon} {pending_review}건")
            lines.append("")
            if data['top_reasons']:
                lines.append("  상위 사유:")
                for r in data['top_reasons']:
                    lines.append(f"    • {r['reason']} ({r['count']}건)")

            self._return_info_text.config(state='normal')
            self._return_info_text.delete('1.0', 'end')
            self._return_info_text.insert('1.0', '\n'.join(lines))
            self._return_info_text.config(state='disabled')
        except Exception as e:
            logger.debug(f"[return_rate] widget error: {e}")

    # ══════════════════════════════════════════════════════════
    # v7.0.1: 위치별 재고 현황 (구역 통계)
    # ══════════════════════════════════════════════════════════

    def _get_location_zone_stats(self) -> Dict:
        """
        구역별 톤백 수량/중량 통계
        
        위치 형식: G5-01-02-03 → 첫 파트(G5)가 구역
        
        Returns:
            {
                'zones': [{'zone': 'A', 'count': 50, 'weight': 25000}, ...],
                'no_location': {'count': 10, 'weight': 5000},
                'total_locations': 150,
                'total_zones': 5
            }
        """
        try:
            # 구역별 집계 (위치 첫 파트 = 구역)
            rows = self.engine.db.fetchall("""
                SELECT 
                    CASE 
                        WHEN location IS NULL OR location = '' THEN '(미지정)'
                        WHEN INSTR(location, '-') > 0 THEN SUBSTR(location, 1, INSTR(location, '-') - 1)
                        ELSE location
                    END AS zone,
                    COUNT(*) AS count,
                    SUM(weight) AS total_weight
                FROM inventory_tonbag
                WHERE status = 'AVAILABLE'
                  AND COALESCE(is_sample, 0) = 0
                GROUP BY zone
                ORDER BY zone
            """)
            
            zones = []
            no_location = {'count': 0, 'weight': 0}
            
            for row in rows:
                zone = row['zone'] or '(미지정)'
                count = row['count'] or 0
                weight = row['total_weight'] or 0
                
                if zone == '(미지정)':
                    no_location = {'count': count, 'weight': weight}
                else:
                    zones.append({
                        'zone': zone,
                        'count': count,
                        'weight': weight
                    })
            
            return {
                'zones': sorted(zones, key=lambda x: x['zone']),
                'no_location': no_location,
                'total_locations': sum(z['count'] for z in zones),
                'total_zones': len(zones)
            }
            
        except Exception as e:
            logger.debug(f"location zone stats error: {e}")
            return {'zones': [], 'no_location': {'count': 0, 'weight': 0},
                    'total_locations': 0, 'total_zones': 0}

    # ═══════════════════════════════════════════════════════════════
    # v7.3.8 — 정합성 패널 데이터
    # ═══════════════════════════════════════════════════════════════

    def _get_integrity_summary(self) -> dict:
        """입고(SUM initial_weight) = 현재재고 톤백합 + 출고누계 톤백합 — 웹 /api/dashboard/stats 와 동일.

        샘플 톤백(is_sample=1) 무게는 현재재고·출고 집계에 포함한다.
        LOT 순중량·현재중량 합계는 엑셀 LOT 목록과 동일한 참고용 필드로 제공한다.
        """
        try:
            db = self.engine.db

            def _fv(r, key=None, idx=0):
                if r is None:
                    return None
                if isinstance(r, dict):
                    if key is not None:
                        return r.get(key)
                    vals = list(r.values())
                    return vals[idx] if idx < len(vals) else None
                try:
                    return r[idx]
                except (IndexError, TypeError):
                    return None

            # 총입고 기준 — inventory.initial_weight (웹 정합성 total_inbound_kg)
            r_init = db.fetchone(
                "SELECT COALESCE(SUM(initial_weight), 0) AS kg FROM inventory"
            )
            initial_kg = float(_fv(r_init, "kg") or 0)

            # 현재 재고 중량 — 샘플 톤백 포함 (웹 current_stock_kg)
            r_cur = db.fetchone(
                "SELECT COUNT(*) AS cnt, COALESCE(SUM(weight), 0) AS kg "
                "FROM inventory_tonbag "
                "WHERE status IN ('AVAILABLE','RESERVED','PICKED','RETURN')"
            )
            cur_cnt = int(_fv(r_cur, "cnt") or 0)
            cur_kg = float(_fv(r_cur, "kg") or 0)

            # 출고 누계 — 샘플 포함 (웹 outbound_total_kg; 상태 목록 동일)
            r_out = db.fetchone(
                "SELECT COUNT(*) AS cnt, COALESCE(SUM(weight), 0) AS kg "
                "FROM inventory_tonbag "
                "WHERE status IN ('OUTBOUND','SOLD','SHIPPED','CONFIRMED')"
            )
            out_cnt = int(_fv(r_out, "cnt") or 0)
            out_kg = float(_fv(r_out, "kg") or 0)

            r_lot = db.fetchone(
                "SELECT COUNT(DISTINCT lot_no) AS cnt FROM inventory WHERE status != 'DEPLETED'"
            )
            lot_cnt = int(_fv(r_lot, "cnt") or 0)

            diff_kg = round(initial_kg - cur_kg - out_kg, 1)
            ok = abs(diff_kg) <= 1.0

            # 표시용: 샘플 톤백 건수 (참고)
            r_cur_samp = db.fetchone(
                "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                "WHERE status IN ('AVAILABLE','RESERVED','PICKED','RETURN') "
                "AND COALESCE(is_sample,0)=1"
            )
            cur_samp_cnt = int(_fv(r_cur_samp, "cnt") or 0)
            r_out_samp = db.fetchone(
                "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                "WHERE status IN ('OUTBOUND','SOLD','SHIPPED','CONFIRMED') "
                "AND COALESCE(is_sample,0)=1"
            )
            out_samp_cnt = int(_fv(r_out_samp, "cnt") or 0)
            r_samp_total = db.fetchone(
                "SELECT COUNT(*) AS cnt FROM inventory_tonbag WHERE COALESCE(is_sample,0)=1"
            )
            total_samp_cnt = int(_fv(r_samp_total, "cnt") or 0)

            # LOT 행 순중량·현재중량 (웹 lot_weight_summary)
            r_nw = db.fetchone(
                "SELECT COALESCE(SUM(net_weight), 0) AS sn, "
                "COALESCE(SUM(current_weight), 0) AS sc FROM inventory"
            )
            sum_net = float(_fv(r_nw, "sn") or 0)
            sum_cur_inv = float(_fv(r_nw, "sc") or 0)
            r_samp_tb = db.fetchone(
                "SELECT COALESCE(SUM(weight), 0) AS kg FROM inventory_tonbag "
                "WHERE COALESCE(is_sample, 0) = 1 "
                "AND status IN ('AVAILABLE','RESERVED','PICKED','RETURN')"
            )
            samp_tb_kg = float(_fv(r_samp_tb, "kg") or 0)

            return {
                'total_kg': initial_kg,
                'total_cnt': lot_cnt,
                'total_samp_cnt': total_samp_cnt,
                'cur_kg': cur_kg,
                'cur_cnt': cur_cnt,
                'cur_samp_cnt': cur_samp_cnt,
                'out_kg': out_kg,
                'out_cnt': out_cnt,
                'out_samp_cnt': out_samp_cnt,
                'lot_cnt': lot_cnt,
                'diff_kg': diff_kg,
                'ok': ok,
                'sum_net_weight_kg': round(sum_net, 1),
                'sum_current_weight_kg': round(sum_cur_inv, 1),
                'gap_net_minus_current_kg': round(sum_net - sum_cur_inv, 1),
                'sample_tonbags_in_stock_kg': round(samp_tb_kg, 1),
            }
        except Exception as e:
            logger.debug(f"정합성 집계 오류: {e}")
            return {
                'total_cnt': 0, 'total_kg': 0, 'total_samp_cnt': 0,
                'cur_cnt': 0,   'cur_kg': 0,   'cur_samp_cnt': 0,
                'out_cnt': 0,   'out_kg': 0,   'out_samp_cnt': 0,
                'lot_cnt': 0,   'diff_kg': 0,  'ok': True,
                'sum_net_weight_kg': 0, 'sum_current_weight_kg': 0,
                'gap_net_minus_current_kg': 0, 'sample_tonbags_in_stock_kg': 0,
            }

    def _get_integrity_mismatch_lots(self) -> list:
        """정합성 불일치 LOT 목록 (드릴다운용)."""
        try:
            rows = self.engine.db.fetchall("""
                SELECT i.lot_no,
                       i.initial_weight,
                       i.current_weight,
                       COALESCE(SUM(CASE WHEN t.status IN ('OUTBOUND','SOLD')
                                         THEN t.weight ELSE 0 END),0) AS out_kg,
                       COALESCE(SUM(CASE WHEN t.status IN ('AVAILABLE','RESERVED','PICKED','RETURN')
                                         AND COALESCE(t.is_sample,0)=0
                                         THEN t.weight ELSE 0 END),0) AS cur_kg
                FROM inventory i
                JOIN inventory_tonbag t ON t.lot_no = i.lot_no
                WHERE COALESCE(t.is_sample,0)=0
                GROUP BY i.lot_no, i.initial_weight, i.current_weight
                HAVING ABS(COALESCE(i.initial_weight,0) - cur_kg - out_kg) > 1.0
                ORDER BY ABS(COALESCE(i.initial_weight,0) - cur_kg - out_kg) DESC
                LIMIT 20
            """)
            return [dict(r) for r in (rows or [])]
        except Exception as e:
            logger.debug(f"불일치 LOT 조회 오류: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════
    # v7.3.8 — 기간별 입고 추이 데이터
    # ═══════════════════════════════════════════════════════════════

    def _get_period_inbound_trend(self, months: int = 3) -> list:
        """v7.5.0: 월별 입고 LOT수 + 중량 추이.
        우선: inventory_snapshot / 없으면: inventory 직접 집계."""
        try:
            # ① inventory_snapshot 기반 (빠름)
            snap_rows = self.engine.db.fetchall(f"""
                SELECT strftime('%Y-%m', snapshot_date) AS ym,
                       MAX(total_lots)      AS lot_cnt,
                       MAX(total_weight_kg) AS kg
                FROM inventory_snapshot
                WHERE snapshot_date >= date('now', '-{months} months')
                GROUP BY ym
                ORDER BY ym
            """)
            if snap_rows and len(snap_rows) >= 1:
                return [dict(r) for r in snap_rows]

            # ② 스냅샷 없으면 inventory 직접 집계 (폴백)
            rows = self.engine.db.fetchall(f"""
                SELECT strftime('%Y-%m', COALESCE(arrival_date, created_at)) AS ym,
                       COUNT(DISTINCT lot_no) AS lot_cnt,
                       COALESCE(SUM(initial_weight), 0) AS kg
                FROM inventory
                WHERE COALESCE(arrival_date, created_at) >= date('now', '-{months} months')
                GROUP BY ym
                ORDER BY ym
            """)
            return [dict(r) for r in (rows or [])]
        except Exception as e:
            logger.debug(f"기간 추이 오류: {e}")
            return []

    def _get_customer_breakdown(self) -> list:
        """고객사별 LOT수 + 중량 (sold_to 기준)."""
        try:
            rows = self.engine.db.fetchall("""
                SELECT COALESCE(NULLIF(sold_to,''), '(미입력)') AS customer,
                       COUNT(DISTINCT lot_no) AS lot_cnt,
                       COALESCE(SUM(initial_weight), 0) AS kg
                FROM inventory
                GROUP BY customer
                ORDER BY kg DESC
                LIMIT 10
            """)
            return [dict(r) for r in (rows or [])]
        except Exception as e:
            logger.debug(f"고객사 집계 오류: {e}")
            return []

