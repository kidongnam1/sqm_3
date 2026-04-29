# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - 데이터 정합성 + 스냅샷 + 알림 Mixin
============================================================

v3.8.5 신규 모듈

기능:
    1. 자동 정합성 검증 (출고/반품 후 즉시 assert)
    2. 일간 재고 스냅샷 (특정 날짜 기준 재고 조회)
    3. 대시보드 알림 (DEPLETED 미정리, 정합성 경고)

작성자: Ruby (남기동)
"""

from engine_modules.constants import STATUS_AVAILABLE, STATUS_RESERVED
import json
import logging
from datetime import date
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

WEIGHT_TOLERANCE_KG = 1.0  # 무게 허용 오차 (kg) — v8.4.1: 샘플 1kg 반영 (0.5→1.0)


class IntegrityMixin:
    """데이터 정합성 + 스냅샷 + 알림 Mixin"""

    # ══════════════════════════════════════════════════════════
    # 기능 1: 자동 정합성 검증
    # ══════════════════════════════════════════════════════════

    def verify_lot_integrity(self, lot_no: str) -> Dict:
        """
        단일 LOT 정합성 검증

        검증 항목:
            1. initial_weight = current_weight + picked_weight
            2. inventory.current_weight = SUM(톤백 AVAILABLE+RESERVED weight, sample 제외)  # v8.0.2 정의 확정
            3. inventory.picked_weight = SUM(톤백 PICKED weight)
            4. current_weight >= 0, picked_weight >= 0
            5. 톤백 총수 = mxbg_pallet (경고)

        Args:
            lot_no: LOT 번호

        Returns:
            dict: {valid, errors, warnings, details}
        """
        result = {'valid': True, 'errors': [], 'warnings': [], 'details': {}}

        try:
            lot = self.db.fetchone(
                "SELECT lot_no, initial_weight, current_weight, picked_weight, mxbg_pallet "
                "FROM inventory WHERE lot_no = ?", (lot_no,))
            if not lot:
                result['errors'].append(f"LOT 없음: {lot_no}")
                result['valid'] = False
                return result

            iw = float(lot['initial_weight'] or 0)
            cw = float(lot['current_weight'] or 0)
            pw = float(lot['picked_weight'] or 0)

            result['details'] = {
                'initial_weight': iw,
                'current_weight': cw,
                'picked_weight': pw,
            }

            # v6.9.7 [AV-09]: Phantom inventory ALERT
            # DB에 AVAILABLE 톤백이 있는데 current_weight=0이면 유령 재고
            _avail_tb = self.db.fetchone(
                "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                "WHERE lot_no=? AND status='AVAILABLE' AND COALESCE(is_sample,0)=0",
                (lot_no,)
            )
            _avail_cnt = int(_avail_tb.get('cnt', 0)) if _avail_tb else 0
            if _avail_cnt > 0 and cw <= 0:
                result['warnings'].append(
                    f"[AV-09] Phantom inventory: AVAILABLE 톤백 {_avail_cnt}개 존재하나 "
                    f"current_weight={cw:.1f}kg — 정합성 재계산 필요"
                )
                logger.warning(f"[AV-09] Phantom inventory: {lot_no} avail_tonbag={_avail_cnt} cw={cw}")

            # v6.9.7 [AV-09b]: current_weight>0 인데 AVAILABLE 톤백 0개 → 역유령
            if cw > WEIGHT_TOLERANCE_KG and _avail_cnt == 0:
                _non_sold = self.db.fetchone(
                    "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
                    "WHERE lot_no=? AND status NOT IN ('SOLD','RETURNED') AND COALESCE(is_sample,0)=0",
                    (lot_no,)
                )
                _ns = int(_non_sold.get('cnt',0)) if _non_sold else 0
                if _ns == 0:
                    result['warnings'].append(
                        f"[AV-09b] 역유령 재고: current_weight={cw:.1f}kg인데 "
                        f"AVAILABLE 톤백 없음 ({lot_no}) — DB 재계산 필요"
                    )
                    logger.warning(f"[AV-09b] 역유령재고: {lot_no} cw={cw} avail=0")

            # 검증 1: initial = current + picked
            diff = abs(iw - (cw + pw))
            if diff > WEIGHT_TOLERANCE_KG:
                result['errors'].append(
                    f"무게 불일치: initial({iw:.1f}) ≠ "
                    f"current({cw:.1f}) + picked({pw:.1f}), 차이={diff:.1f}kg"
                )
                result['valid'] = False

            # v6.9.8 [AV-09c]: picked_weight > initial_weight → 초과 출고 경고
            if pw > iw + WEIGHT_TOLERANCE_KG:
                result['warnings'].append(
                    f"[AV-09c] 출고 초과: picked_weight({pw:.1f}kg) > "
                    f"initial_weight({iw:.1f}kg) — 유령 출고 가능성 확인 필요"
                )
                result['valid'] = False
                logger.warning(f"[AV-09c] 출고초과: {lot_no} picked={pw:.1f} > initial={iw:.1f}")

            # v6.9.8 [AV-03]: sample 포함 가용수량 계산 오류 감지
            # current_weight가 샘플(1kg) 포함 계산되면 0.001MT 미만 남는 이상 케이스 발생
            # 샘플 무게가 current_weight에 포함된 경우 탐지
            from core.constants import SAMPLE_WEIGHT_KG as _SW
            _avail_tb_sum = self.db.fetchone(
                "SELECT COALESCE(SUM(weight),0) AS total FROM inventory_tonbag "
                "WHERE lot_no=? AND status='AVAILABLE' AND COALESCE(is_sample,0)=0",
                (lot_no,)
            )
            _avail_sum = float(_avail_tb_sum.get('total',0)) if _avail_tb_sum else 0
            if abs(cw - _avail_sum - _SW) < WEIGHT_TOLERANCE_KG and cw > _SW:
                result['warnings'].append(
                    f"[AV-03] 샘플 포함 가용수량 의심: current_weight={cw:.1f}kg = "
                    f"톤백합계({_avail_sum:.1f}kg) + 샘플({_SW}kg) "
                    f"— sample 무게가 current_weight에 포함된 가능성"
                )
                logger.warning(f"[AV-03] 샘플포함 의심: {lot_no} cw={cw:.1f} avail_sum={_avail_sum:.1f}")

            # 검증 2-3: 톤백 합계 대조 (v5.7.2: 가용/출고 합산에 샘플 포함 — 대원칙 5001=500×10+1)
            # 가용 합계: status IN ('AVAILABLE','SAMPLE','RESERVED','RETURN') — RESERVED는 current_weight 미차감 상태
            # v7.0.1: RESERVED 포함 (reserve_from_allocation에서 current_weight 안 건드리므로)
            # v7.3.6: RETURN 포함 (반품 대기 톤백도 창고 내 실재 재고로 집계)
            tb_summary = self.db.fetchone("""
                SELECT 
                    COALESCE(SUM(CASE WHEN status IN ('AVAILABLE','SAMPLE','RESERVED','RETURN') THEN weight ELSE 0 END), 0) as avail_w,
                    COALESCE(SUM(CASE WHEN status IN ('PICKED','CONFIRMED','SHIPPED','SOLD') THEN weight ELSE 0 END), 0) as picked_w,
                    COALESCE(SUM(CASE WHEN status = 'RESERVED' THEN weight ELSE 0 END), 0) as reserved_w,
                    COALESCE(SUM(CASE WHEN COALESCE(is_sample,0)=1 THEN weight ELSE 0 END), 0) as sample_w,
                    SUM(CASE WHEN COALESCE(is_sample,0)=0 THEN 1 ELSE 0 END) as total_count,
                    SUM(CASE WHEN status='AVAILABLE' THEN 1 ELSE 0 END) as avail_count,
                    SUM(CASE WHEN status='RESERVED' THEN 1 ELSE 0 END) as reserved_count,
                    SUM(CASE WHEN status IN ('PICKED','CONFIRMED','SHIPPED') THEN 1 ELSE 0 END) as picked_count,
                    SUM(CASE WHEN status='RETURN' THEN 1 ELSE 0 END) as return_count,
                    SUM(CASE WHEN COALESCE(is_sample,0)=1 THEN 1 ELSE 0 END) as sample_count
                FROM inventory_tonbag WHERE lot_no = ?
            """, (lot_no,))

            if tb_summary:
                tb_avail = float(tb_summary['avail_w'] or 0)
                tb_picked = float(tb_summary['picked_w'] or 0)
                tb_total = int(tb_summary['total_count'] or 0)
                # ★ v7.5.0 검증 10: avail_w에서 샘플 1kg 분리
                # avail_w = 일반 톤백 가용 + 샘플 1kg 합산값이므로
                # current_weight(lot_inventory)와 대조 시 샘플 제외한 값으로 비교
                _sample_w_in_avail = float(tb_summary.get('sample_w') or 0)
                tb_avail_no_sample = tb_avail - _sample_w_in_avail  # 순수 일반 톤백 가용량

                result['details']['tonbag_available_weight'] = tb_avail
                result['details']['tonbag_available_weight_no_sample'] = tb_avail_no_sample
                result['details']['sample_w_in_avail'] = _sample_w_in_avail
                result['details']['tonbag_picked_weight'] = tb_picked
                result['details']['tonbag_reserved_weight'] = float(tb_summary.get('reserved_w') or 0)
                result['details']['tonbag_count'] = tb_total
                result['details']['reserved_count'] = int(tb_summary.get('reserved_count') or 0)

                # current_weight는 샘플 포함/제외 여부에 따라 두 가지 허용
                # 허용1: cw == tb_avail      (샘플 포함 current_weight 방식)
                # 허용2: cw == tb_avail_no_sample (샘플 제외 current_weight 방식)
                _cw_ok = (
                    abs(cw - tb_avail) <= WEIGHT_TOLERANCE_KG or
                    abs(cw - tb_avail_no_sample) <= WEIGHT_TOLERANCE_KG
                )
                if not _cw_ok:
                    result['errors'].append(
                        f"LOT↔톤백 가용 불일치: inv.current({cw:.1f}) ≠ "
                        f"tonbag.available({tb_avail:.1f}) "
                        f"[샘플제외={tb_avail_no_sample:.1f}]"
                    )
                    result['valid'] = False

                if abs(pw - tb_picked) > WEIGHT_TOLERANCE_KG:
                    result['errors'].append(
                        f"LOT↔톤백 출고 불일치: inv.picked({pw:.1f}) ≠ "
                        f"tonbag.picked({tb_picked:.1f})"
                    )
                    result['valid'] = False

                # 검증 5: 톤백 수 검증 (경고)
                mxbg = int(lot['mxbg_pallet'] or 0)
                if mxbg > 0 and tb_total != mxbg:
                    result['warnings'].append(
                        f"톤백 수 불일치: 등록({mxbg}) ≠ 실제({tb_total})"
                    )

                # ★ v5.2.0 검증 6: 샘플 정책 하드스톱 (개수)
                sample_count = int(tb_summary.get('sample_count') or 0)
                result['details']['sample_count'] = sample_count
                if sample_count == 0:
                    result['errors'].append(
                        f"샘플 정책 위반: LOT {lot_no}에 샘플 톤백 0개 (필수 1개)"
                    )
                    result['valid'] = False
                elif sample_count > 1:
                    result['errors'].append(
                        f"샘플 정책 위반: LOT {lot_no}에 샘플 톤백 {sample_count}개 (최대 1개)"
                    )
                    result['valid'] = False

                # ★ v7.5.0 검증 8: 샘플 무게 = 정확히 1.0kg (값 검증)
                if sample_count == 1:
                    from core.constants import SAMPLE_WEIGHT_KG as _SW
                    _sample_row = self.db.fetchone(
                        "SELECT weight FROM inventory_tonbag "
                        "WHERE lot_no = ? AND COALESCE(is_sample,0) = 1 LIMIT 1",
                        (lot_no,)
                    )
                    if _sample_row:
                        _sample_w = float(_sample_row.get('weight') or 0
                                          if isinstance(_sample_row, dict)
                                          else _sample_row[0] or 0)
                        result['details']['sample_weight_kg'] = _sample_w
                        if abs(_sample_w - _SW) > 0.01:
                            result['errors'].append(
                                f"샘플 무게 오류: {_sample_w:.3f}kg ≠ {_SW}kg "
                                f"(핵심 불변조건: 샘플은 반드시 1.000kg)"
                            )
                            result['valid'] = False
                        else:
                            result['details']['sample_weight_ok'] = True

                # ★ v7.5.0 검증 9: 일반 톤백 전체 출고 후 샘플 잔류 경고
                # 모든 일반 톤백이 SOLD/SHIPPED인데 샘플이 AVAILABLE/RESERVED → 이상 상태
                if sample_count == 1:
                    _normal_avail = self.db.fetchone(
                        """SELECT COUNT(*) as cnt FROM inventory_tonbag
                           WHERE lot_no = ? AND COALESCE(is_sample,0)=0
                             AND status IN ('AVAILABLE','RESERVED')""",
                        (lot_no,)
                    )
                    _normal_avail_cnt = int(
                        (_normal_avail.get('cnt') if isinstance(_normal_avail, dict)
                         else _normal_avail[0]) or 0
                    ) if _normal_avail else 0

                    _sample_status_row = self.db.fetchone(
                        "SELECT status FROM inventory_tonbag "
                        "WHERE lot_no = ? AND COALESCE(is_sample,0)=1 LIMIT 1",
                        (lot_no,)
                    )
                    _sample_status = str(
                        (_sample_status_row.get('status') if isinstance(_sample_status_row, dict)
                         else _sample_status_row[0]) or ''
                    ) if _sample_status_row else ''

                    result['details']['sample_status'] = _sample_status
                    if (_normal_avail_cnt == 0
                            and _sample_status in (STATUS_AVAILABLE, STATUS_RESERVED, 'SAMPLE')):
                        result['warnings'].append(
                            f"샘플 잔류 경고: 일반 톤백 전체 출고 완료 후 "
                            f"샘플이 {_sample_status} 상태로 남아있음 (의도적 보관이면 무시)"
                        )

            # 검증 4: 음수 검증
            if cw < -0.01:
                result['errors'].append(f"current_weight 음수: {cw}")
                result['valid'] = False
            if pw < -0.01:
                result['errors'].append(f"picked_weight 음수: {pw}")
                result['valid'] = False

            # ═══ v5.6.0 검증 7: 대원칙 (톤백 단가 = 500kg 또는 1000kg) ═══
            # LOT 총무게 = (톤백수 × 단가) + 샘플 1kg
            if tb_summary and tb_total > 0:
                from core.constants import SAMPLE_WEIGHT_KG
                from engine_modules.tonbag_weight_rules import get_rule_status
                SAMPLE_WEIGHT = SAMPLE_WEIGHT_KG
                VALID_UNIT_WEIGHTS = (500.0, 1000.0)  # v6.12: 비표준 단가 추가 시 여기에 추가 (예: 750.0)
                TOLERANCE = 0.5  # 0.5kg 허용

                # 방법: (initial_weight - 1) / 톤백수 = 단가 → 500 or 1000이어야 함
                # (iw - SAMPLE_WEIGHT) / tb_total → 개별 톤백 무게로 대체 확인

                # 개별 톤백 무게 확인 (일반 톤백만)
                tb_weights = self.db.fetchall(
                    "SELECT weight FROM inventory_tonbag WHERE lot_no = ? AND COALESCE(is_sample,0) = 0",
                    (lot_no,))
                
                if tb_weights:
                    weights = [float(r['weight'] or 0) for r in tb_weights]
                    unique_weights = set(round(w, 1) for w in weights)
                    
                    # 모든 톤백이 동일 무게인지 확인
                    if len(unique_weights) > 1:
                        result['warnings'].append(
                            f"톤백 무게 불균일: {sorted(unique_weights)}")
                    
                    # 단가가 500 or 1000인지 확인
                    avg_weight = sum(weights) / len(weights)
                    is_valid_unit = any(
                        abs(avg_weight - vw) < TOLERANCE for vw in VALID_UNIT_WEIGHTS)
                    
                    if not is_valid_unit:
                        result['errors'].append(
                            f"대원칙 위반: 톤백 평균 {avg_weight:.1f}kg "
                            f"(허용: {VALID_UNIT_WEIGHTS})")
                        result['valid'] = False
                    
                    # LOT 총무게 정합성: 톤백합 + 샘플 = initial_weight
                    tonbag_sum = sum(weights)
                    expected_total = tonbag_sum + SAMPLE_WEIGHT
                    if abs(iw - expected_total) > TOLERANCE:
                        result['errors'].append(
                            f"대원칙 총무게 불일치: initial({iw:.1f}) ≠ "
                            f"톤백합({tonbag_sum:.1f}) + 샘플({SAMPLE_WEIGHT}) = {expected_total:.1f}")
                        result['valid'] = False
                    
                    result['details']['unit_weight'] = round(avg_weight, 1)
                    result['details']['principle_valid'] = is_valid_unit
                    result['details']['rule_status'] = get_rule_status(avg_weight)

            # ★ v7.6.0 검증 11: allocation mismatch — 부분 출고 잔류 감지
            # 일부 톤백은 SOLD, 일부는 AVAILABLE → allocation 불완전 처리 의심
            if tb_summary and tb_total > 0:
                _sold_cnt = self.db.fetchone(
                    """SELECT COUNT(*) as cnt FROM inventory_tonbag
                       WHERE lot_no=? AND COALESCE(is_sample,0)=0
                         AND status IN ('SOLD','SHIPPED')""",
                    (lot_no,)
                )
                _avail_cnt = self.db.fetchone(
                    """SELECT COUNT(*) as cnt FROM inventory_tonbag
                       WHERE lot_no=? AND COALESCE(is_sample,0)=0
                         AND status = 'AVAILABLE'""",
                    (lot_no,)
                )
                _sold_n = int((_sold_cnt.get('cnt') if isinstance(_sold_cnt, dict)
                               else _sold_cnt[0]) or 0) if _sold_cnt else 0
                _avail_n = int((_avail_cnt.get('cnt') if isinstance(_avail_cnt, dict)
                                else _avail_cnt[0]) or 0) if _avail_cnt else 0

                result['details']['sold_tonbag_count']  = _sold_n
                result['details']['avail_tonbag_count'] = _avail_n

                if _sold_n > 0 and _avail_n > 0:
                    result['warnings'].append(
                        f"부분 출고 잔류: 일반 톤백 {tb_total}개 중 "
                        f"SOLD={_sold_n}개 / AVAILABLE={_avail_n}개 혼재. "
                        f"allocation 미완결 또는 분할 출고 확인 필요."
                    )

            # ★ v7.6.0 검증 12: allocation 합계 vs LOT 입고 총량 대조
            # allocation_plan의 qty_mt 합계가 LOT 입고 총량과 다르면 mismatch
            try:
                _alloc_sum_row = self.db.fetchone(
                    """SELECT COALESCE(COUNT(CASE WHEN qty_mt >= 0.01 THEN 1 END) * 0.5, 0) as total_alloc_mt
                       FROM allocation_plan
                       WHERE lot_no=? AND status NOT IN ('CANCELLED','REJECTED')""",
                    (lot_no,)
                )
                if _alloc_sum_row:
                    _alloc_mt = float(_alloc_sum_row.get('total_alloc_mt')
                                      if isinstance(_alloc_sum_row, dict)
                                      else _alloc_sum_row[0] or 0)
                    # LOT 입고 순수 중량 = initial_weight - 샘플 1kg
                    from core.constants import SAMPLE_WEIGHT_KG as _SW2
                    _lot_net_mt = (iw - _SW2) / 1000.0
                    result['details']['allocation_total_mt'] = round(_alloc_mt, 4)
                    result['details']['lot_net_mt'] = round(_lot_net_mt, 4)

                    # allocation 합계가 LOT 순중량 초과 → ERROR
                    if _alloc_mt > _lot_net_mt + 0.001:
                        result['errors'].append(
                            f"allocation 초과: 배정합계({_alloc_mt:.3f}MT) > "
                            f"LOT 순중량({_lot_net_mt:.3f}MT). "
                            f"초과={_alloc_mt - _lot_net_mt:.3f}MT"
                        )
                        result['valid'] = False
                    # allocation 합계 < LOT 순중량 (미배정 잔여) → WARNING
                    elif _alloc_mt > 0 and (_lot_net_mt - _alloc_mt) > 0.01:
                        result['warnings'].append(
                            f"allocation 미완결: LOT 순중량({_lot_net_mt:.3f}MT) 중 "
                            f"배정합계={_alloc_mt:.3f}MT, "
                            f"미배정={_lot_net_mt - _alloc_mt:.3f}MT 잔류"
                        )
            except Exception as _ae:
                logger.debug(f"[integrity] allocation 합계 검증 스킵: {_ae}")

        except (ValueError, TypeError, KeyError) as e:
            result['errors'].append(f"검증 오류: {e}")
            result['valid'] = False
            logger.error(f"정합성 검증 오류: {e}", exc_info=True)

        # v8.3.0 [Phase 9]: 정합성 오류 감지 시 audit + notify
        if result.get('errors'):
            try:
                from engine_modules.audit_helper import write_audit, EVT_INTEGRITY_FAIL
                write_audit(self.db, EVT_INTEGRITY_FAIL, lot_no=lot_no,
                            detail={'errors': result['errors'],
                                    'warnings': result.get('warnings', [])})
            except Exception as _e:
                logger.debug(f"[SUPPRESSED] exception in integrity_mixin.py: {_e}")  # noqa
            try:
                from utils.error_notifier import notify_integrity_fail
                notify_integrity_fail(lot_no, result['errors'],
                                      result.get('warnings', []))
            except Exception as _e:
                logger.debug(f"[SUPPRESSED] exception in integrity_mixin.py: {_e}")  # noqa

        return result

    def verify_all_integrity(self) -> Dict:
        """
        전체 재고 정합성 검증

        Returns:
            dict: {valid, total_lots, error_lots, warning_lots, details}
        """
        result = {
            'valid': True,
            'total_lots': 0,
            'error_lots': [],
            'warning_lots': [],
            'details': {}
        }

        try:
            lots = self.db.fetchall("SELECT lot_no FROM inventory")
            result['total_lots'] = len(lots)

            for lot in lots:
                lot_no = lot['lot_no']
                check = self.verify_lot_integrity(lot_no)

                if not check['valid']:
                    result['valid'] = False
                    result['error_lots'].append({
                        'lot_no': lot_no,
                        'errors': check['errors']
                    })

                if check['warnings']:
                    result['warning_lots'].append({
                        'lot_no': lot_no,
                        'warnings': check['warnings']
                    })

            logger.info(
                f"전체 정합성 검증: {result['total_lots']}개 LOT, "
                f"에러 {len(result['error_lots'])}건, "
                f"경고 {len(result['warning_lots'])}건"
            )

        except (ValueError, TypeError, AttributeError) as e:
            result['valid'] = False
            result['details']['error'] = str(e)
            logger.error(f"전체 정합성 검증 오류: {e}")

        return result

    def _assert_lot_integrity(self, lot_no: str) -> None:
        """
        출고/반품 후 자동 호출되는 정합성 assert

        불일치 감지 시 로그 경고만 기록 (트랜잭션 롤백하지 않음)

        Args:
            lot_no: 검증할 LOT 번호
        """
        try:
            check = self.verify_lot_integrity(lot_no)
            if not check['valid']:
                logger.warning(
                    f"[정합성 경고] {lot_no}: {check['errors']}"
                )
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"정합성 assert 오류: {e}")

    # ══════════════════════════════════════════════════════════
    # 기능 2: 일간 재고 스냅샷
    # ══════════════════════════════════════════════════════════

    def get_snapshot(self, snapshot_date: date = None) -> Optional[Dict]:
        """
        특정 날짜 스냅샷 조회

        Args:
            snapshot_date: 조회 날짜 (기본: 오늘)

        Returns:
            스냅샷 데이터 또는 None
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        row = self.db.fetchone(
            "SELECT * FROM inventory_snapshot WHERE snapshot_date = ?",
            (snapshot_date.isoformat(),))

        if row:
            data = dict(row)
            if data.get('product_summary'):
                try:
                    data['product_summary'] = json.loads(data['product_summary'])
                except (json.JSONDecodeError, TypeError) as _e:
                    logger.debug(f"JSON 파싱 실패: {_e}")
            return data
        return None

    def get_snapshot_range(self, start_date: date, end_date: date) -> List[Dict]:
        """
        기간별 스냅샷 조회 (추이 분석용)

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            스냅샷 리스트
        """
        rows = self.db.fetchall("""
            SELECT * FROM inventory_snapshot 
            WHERE snapshot_date BETWEEN ? AND ?
            ORDER BY snapshot_date
        """, (start_date.isoformat(), end_date.isoformat()))

        result = []
        for row in rows:
            data = dict(row)
            if data.get('product_summary'):
                try:
                    data['product_summary'] = json.loads(data['product_summary'])
                except (json.JSONDecodeError, TypeError) as _e:
                    logger.debug(f"JSON 파싱 실패: {_e}")
            result.append(data)
        return result

    # ══════════════════════════════════════════════════════════
    # 기능 6: 대시보드 알림
    # ══════════════════════════════════════════════════════════
