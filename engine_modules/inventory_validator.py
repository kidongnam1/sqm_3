# -*- coding: utf-8 -*-
"""Stage 4 inventory integrity helpers for SQM.

핵심 역할
- Rack capacity(20) 검증
- Warehouse capacity(A/B 각 3500) 검증
- System total capacity(7000) 검증
- LOT / TONBAG / LOCATION 기본 무결성 검증
"""
from __future__ import annotations
from dataclasses import dataclass

RACK_CAPACITY = 20
WAREHOUSE_CAPACITY = {"A": 3500, "B": 3500}
SYSTEM_CAPACITY = 7000

@dataclass
class ValidationResult:
    ok: bool
    code: str
    message: str


def check_rack_capacity(current_count: int, incoming_count: int = 0, rack_capacity: int = RACK_CAPACITY) -> ValidationResult:
    total = int(current_count or 0) + int(incoming_count or 0)
    if total > rack_capacity:
        return ValidationResult(False, 'ERROR_RACK_CAPACITY_EXCEEDED', f'Rack capacity 초과: {total}/{rack_capacity}')
    return ValidationResult(True, 'RACK_CAPACITY_OK', f'Rack capacity 정상: {total}/{rack_capacity}')


def check_warehouse_capacity(warehouse_code: str, current_count: int, incoming_count: int = 0) -> ValidationResult:
    wh = str(warehouse_code or '').strip().upper()
    cap = WAREHOUSE_CAPACITY.get(wh, 0)
    total = int(current_count or 0) + int(incoming_count or 0)
    if cap and total > cap:
        return ValidationResult(False, 'ERROR_WAREHOUSE_CAPACITY_EXCEEDED', f'{wh}동 capacity 초과: {total}/{cap}')
    return ValidationResult(True, 'WAREHOUSE_CAPACITY_OK', f'{wh}동 capacity 정상: {total}/{cap}')


def check_system_capacity(current_count: int, incoming_count: int = 0) -> ValidationResult:
    total = int(current_count or 0) + int(incoming_count or 0)
    if total > SYSTEM_CAPACITY:
        return ValidationResult(False, 'ERROR_SYSTEM_CAPACITY_EXCEEDED', f'System capacity 초과: {total}/{SYSTEM_CAPACITY}')
    return ValidationResult(True, 'SYSTEM_CAPACITY_OK', f'System capacity 정상: {total}/{SYSTEM_CAPACITY}')


def validate_location_code(location_code: str) -> ValidationResult:
    code = str(location_code or '').strip().upper()
    # A-03-05-02 형식
    import re
    if re.fullmatch(r'[A-Z]-\d{2}-\d{2}-\d{2}', code):
        return ValidationResult(True, 'LOCATION_CODE_OK', f'Location 형식 정상: {code}')
    return ValidationResult(False, 'ERROR_INVALID_LOCATION', f'Location 형식 오류: {code}')
