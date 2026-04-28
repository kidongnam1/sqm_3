# -*- coding: utf-8 -*-
from __future__ import annotations

TONBAG_NO_WIDTH = 3
SAMPLE_TONBAG_NO = "S00"

def normalize_tonbag_no(value, is_sample: bool = False) -> str:
    if is_sample:
        return SAMPLE_TONBAG_NO
    s = str(value or '').strip().upper()
    if s in {'S0','S00'}:
        return SAMPLE_TONBAG_NO
    return s.zfill(TONBAG_NO_WIDTH) if s.isdigit() else s

def build_tonbag_uid(lot_no: str, tonbag_no: str, is_sample: bool = False) -> str:
    tn = normalize_tonbag_no(tonbag_no, is_sample=is_sample)
    return f"{str(lot_no).strip()}-{tn}"
