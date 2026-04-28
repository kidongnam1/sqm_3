# -*- coding: utf-8 -*-
"""
sort_utils.py — v7.0.0 [REFACTOR-1]
Treeview 컬럼 정렬 유틸리티 (4탭 중복 sort_key 중앙화)

기존: 각 탭(cargo/inventory/tonbag/outbound_scheduled)에 동일 로직 중복 정의
개선: 단일 소스로 통합 → 유지보수성 향상

Usage:
    from gui_app_modular.utils.sort_utils import make_sort_key
    sort_key = make_sort_key(col, numeric_cols)
    items.sort(key=sort_key, reverse=reverse)
"""


def make_sort_key(col: str, numeric_cols: list):
    """
    Treeview 컬럼 정렬용 key 함수 생성.

    Args:
        col:          현재 정렬 중인 컬럼 ID
        numeric_cols: 숫자로 정렬할 컬럼 ID 목록

    Returns:
        정렬 key 함수 (lambda or named function)
    """
    if col in numeric_cols:
        def _numeric_key(x):
            try:
                return float(str(x[0]).replace(',', ''))
            except (ValueError, TypeError):
                return 0.0
        return _numeric_key
    else:
        return lambda x: (str(x[0]) or '').lower()
