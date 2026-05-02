# -*- coding: utf-8 -*-
"""Stage 2 tonbag weight rules.

기존 SQM 로직을 공식 규칙으로 모듈화한다.
공식:
    tonbag_weight = (lot_total_weight_kg - sample_weight_kg) / mxbg_pallet
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_WEIGHT_KG = 1.0

@dataclass(frozen=True)
class TonbagWeightRuleResult:
    tonbag_weight_kg: float
    sample_weight_kg: float
    mxbg_pallet: int
    rule_status: str


def calculate_tonbag_weight(lot_total_weight_kg: float, mxbg_pallet: int, sample_weight_kg: float = DEFAULT_SAMPLE_WEIGHT_KG) -> float:
    try:
        _mx = int(float(str(mxbg_pallet).replace(',', '').strip() or 0))
    except (ValueError, TypeError):
        _mx = 0
    if _mx <= 0:
        return 0.0
    _lot = float(str(lot_total_weight_kg).replace(',', '').strip() or 0)
    _smp = float(sample_weight_kg)
    return (_lot - _smp) / _mx


def get_rule_status(weight_kg: float) -> str:
    # 운영 해석: 500은 확정, 1000은 pending_confirmation.
    if abs(float(weight_kg) - 500.0) < 0.5:
        return 'confirmed'
    if abs(float(weight_kg) - 1000.0) < 0.5:
        return 'pending_confirmation'
    return 'unknown'


def build_rule_result(
    lot_total_weight_kg: float,
    mxbg_pallet: int,
    sample_weight_kg: float = DEFAULT_SAMPLE_WEIGHT_KG,
    expected_per_bag: int | None = None,  # v9.1: 참고용만, 계산값이 항상 우선
) -> TonbagWeightRuleResult:
    """v9.1 대원칙 (기동님 확정):

    톤백 개수  = Packing List MXBG 값
    톤백 1개 무게 = (LOT 전체 무게 - 1kg 샘플) / MXBG

    이 공식이 LOT 선택(500kg/1000kg)에 무관하게 항상 정확함.
    expected_per_bag(템플릿 단가)은 더 이상 실제 계산에 사용하지 않음.
    계산값 vs 템플릿값 비교 로그만 남기고 계산값을 그대로 사용.
    """
    # 핵심 계산: (전체 무게 - 샘플 1kg) / MXBG
    w = calculate_tonbag_weight(lot_total_weight_kg, mxbg_pallet, sample_weight_kg)
    status = get_rule_status(w)

    # 템플릿 단가가 있으면 참고용 로그만 (덮어쓰기 금지)
    if expected_per_bag is not None:
        try:
            expected = float(expected_per_bag)
            diff_pct = abs(w - expected) / max(expected, 1) * 100
            if diff_pct > 5:
                # 편차 있어도 계산값 우선 — 로그만 남김
                status = f'mxbg_calc_{int(w)}kg(tpl={int(expected)}kg)'
        except (TypeError, ValueError):
            logger.debug("[SUPPRESSED] exception in tonbag_weight_rules.py")  # noqa

    return TonbagWeightRuleResult(
        tonbag_weight_kg=w,
        sample_weight_kg=sample_weight_kg,
        mxbg_pallet=mxbg_pallet,
        rule_status=status,
    )
