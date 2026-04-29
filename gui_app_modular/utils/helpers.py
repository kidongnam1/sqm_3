"""
SQM Inventory - Helper Functions
================================

v2.9.91 - Common utility functions

Date parsing, format conversion, file operations

날짜 처리: date 객체 필요 → safe_date_to_date (이 모듈)
          문자열 필요 → safe_utils.safe_date_str
"""

import logging
import os
import re
from datetime import date, datetime
from typing import Any, Optional

from core.types import (  # noqa: F401 (re-export)
    normalize_column_name, # noqa: F401
    safe_float,           # noqa: F401
    safe_int,             # noqa: F401
    safe_str,             # noqa: F401
)

logger = logging.getLogger(__name__)
# Ruby v2: re-export __all__ (pyflakes 호환)
__all__ = ['normalize_column_name', 'safe_float', 'safe_int', 'safe_str',
           'find_column', 'format_number', 'format_weight']


def safe_date(value: Any, default: Optional[date] = None) -> Optional[date]:
    """
    Safe date conversion → date 객체 반환.
    문자열이 필요하면: from gui_app_modular.utils.safe_utils import safe_date_str

    Supports formats:
    - datetime object
    - date object
    - "YYYY-MM-DD"
    - "YYYYMMDD"
    - "DD/MM/YYYY"
    - "MM/DD/YYYY"
    
    Args:
        value: Value to convert
        default: Default if conversion fails
        
    Returns:
        Date object or default
    """
    if value is None:
        return default or date.today()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if hasattr(value, 'date'):  # pandas Timestamp
        return value.date()

    # String parsing
    value_str = str(value).strip()

    # Try common formats
    formats = [
        '%Y-%m-%d',
        '%Y%m%d',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%Y.%m.%d',
        '%d.%m.%Y',
        '%Y/%m/%d',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue

    return default or date.today()


# 용도별 별칭 (DEBUGGING_RISK_OVERVIEW: safe_date 용도별 정리)
safe_date_to_date = safe_date  # 날짜 객체 필요 시. 문자열 필요 시 safe_utils.safe_date_str


# P1: format_* / find_column 단일 소스
from .formatters import find_column, format_number, format_weight  # noqa: F401


def validate_lot_no(lot_no: str) -> bool:
    """LOT 번호 검증. 단일 소스: engine_modules.validators.validate_lot_no"""
    from core.validators import validate_lot_no as _validate_lot_no
    ok, _ = _validate_lot_no(lot_no)
    return ok


def validate_sap_no(sap_no: str) -> bool:
    """SAP NO 검증. 단일 소스: engine_modules.validators.validate_sap_no"""
    from core.validators import validate_sap_no as _validate_sap_no
    ok, _ = _validate_sap_no(sap_no)
    return ok


def get_file_extension(file_path: str) -> str:
    """
    Get file extension (lowercase, without dot)
    
    Args:
        file_path: File path
        
    Returns:
        Extension (e.g., 'xlsx', 'pdf')
    """
    if not file_path:
        return ""

    _, ext = os.path.splitext(file_path)
    return ext.lower().lstrip('.')


def ensure_directory(dir_path: str) -> bool:
    """
    Ensure directory exists
    
    Args:
        dir_path: Directory path
        
    Returns:
        True if directory exists or was created
    """
    if not dir_path:
        return False

    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except OSError as e:
        logger.error(f"Failed to create directory {dir_path}: {e}")
        return False


def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate string to maximum length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if not text:
        return ""

    text = str(text)
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def clean_lot_no(value: Any) -> str:
    """
    Clean and normalize LOT number
    
    Handles:
    - Float values (removes .0)
    - String with decimals
    - Leading/trailing whitespace
    
    Args:
        value: Raw LOT value
        
    Returns:
        Cleaned LOT number string
    """
    if value is None:
        return ""

    # Handle numeric types
    if isinstance(value, (int, float)):
        return str(int(value))

    # Handle strings
    value_str = str(value).strip()

    # Remove decimal part if present
    if '.' in value_str:
        value_str = value_str.split('.')[0]

    return value_str


def parse_weight_string(value: str) -> float:
    """
    Parse weight from string
    
    Handles:
    - "1,234.56"
    - "1234.56 kg"
    - "1.234 MT"
    
    Args:
        value: Weight string
        
    Returns:
        Weight in kg
    """
    if not value:
        return 0.0

    value_str = str(value).strip().upper()

    # Check for MT unit
    is_mt = 'MT' in value_str

    # Remove non-numeric characters except . and ,
    cleaned = re.sub(r'[^\d.,]', '', value_str)

    # Handle comma as thousands separator
    if ',' in cleaned and '.' in cleaned:
        # Assume format: 1,234.56
        cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        # Assume format: 1234,56 (European)
        cleaned = cleaned.replace(',', '.')

    try:
        weight = float(cleaned)
        if is_mt:
            weight *= 1000  # Convert to kg
        return weight
    except ValueError:
        return 0.0
