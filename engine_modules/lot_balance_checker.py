# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class LotBalanceResult:
    ok: bool
    lot_no: str
    expected_weight: float
    actual_weight: float
    diff: float
    message: str


def check_lot_weight_balance(lot_no: str, expected_weight: float, tonbag_weight_sum: float, tolerance_kg: float = 0.5) -> LotBalanceResult:
    diff = abs(float(expected_weight or 0) - float(tonbag_weight_sum or 0))
    ok = diff <= tolerance_kg
    return LotBalanceResult(
        ok=ok,
        lot_no=str(lot_no),
        expected_weight=float(expected_weight or 0),
        actual_weight=float(tonbag_weight_sum or 0),
        diff=diff,
        message=(f'LOT 무게 정상: {lot_no}' if ok else f'LOT 무게 불일치: {lot_no}, diff={diff:.3f}kg')
    )
