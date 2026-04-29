"""
SQM GUI - 포맷/컬럼 유틸 단일 소스 (P1)
=========================================
format_number, format_weight, format_weight_mt, format_weight_kg, find_column
"""

from typing import Optional


def format_number(value: float, decimals: int = 2, use_comma: bool = True) -> str:
    """숫자 포맷 (천 단위 구분, 소수 자리)."""
    try:
        if use_comma:
            return f"{value:,.{decimals}f}"
        return f"{value:.{decimals}f}"
    except (ValueError, TypeError, AttributeError):
        return str(value)


def format_weight_kg(kg_value: float) -> str:
    """kg 포맷 (정수 콤마)."""
    return f"{kg_value:,.0f} kg"


def format_weight_mt(kg_value: float) -> str:
    """kg → MT 변환 포맷."""
    mt = kg_value / 1000
    return f"{mt:,.2f} MT"


def format_weight(weight_kg: float, unit: str = 'MT') -> str:
    """무게 포맷 (unit: 'MT', 'kg', 'auto')."""
    if unit == 'MT':
        return f"{weight_kg / 1000:.3f} MT"
    if unit == 'kg':
        return f"{weight_kg:,.0f} kg"
    # auto
    if weight_kg >= 1000:
        return f"{weight_kg / 1000:.3f} MT"
    return f"{weight_kg:.1f} kg"


def find_column(
    df_columns: list,
    candidates: list,
    default: Optional[str] = None
) -> Optional[str]:
    """DataFrame 컬럼에서 후보 이름 찾기 (대소문자 무시)."""
    df_cols_lower = {str(c).lower().strip(): c for c in df_columns}
    for candidate in candidates:
        key = str(candidate).lower().strip()
        if key in df_cols_lower:
            return df_cols_lower[key]
    return default
