"""
SQM v5.5.5 — 공용 유틸리티 (Single Source of Truth)
=====================================================
safe_float, safe_str, normalize_column_name, normalize_lot, norm_* 정규화 함수.
매칭 실패/중복 방지를 위해 *_raw 보존 + *_std 표준키 적용.

사용법:
    from utils.common import safe_float, normalize_lot, norm_tonbag_no_std, norm_bl_no
"""

import logging
import re
from datetime import datetime
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 톤백번호 표준 폭 (0 패딩)
TONBAG_NO_STD_WIDTH = 3


def safe_float(value: Any, default: float = 0.0) -> float:
    """안전한 실수 변환 (쉼표, 공백, 하이픈 처리)"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace(',', '').replace(' ', '').strip()
        if not cleaned or cleaned == '-':
            return default
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = '') -> str:
    """안전한 문자열 변환"""
    if value is None:
        return default
    try:
        result = str(value).strip()
        return result if result else default
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """안전한 정수 변환"""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        if isinstance(value, float):
            return int(value)
        cleaned = str(value).replace(',', '').replace(' ', '').strip()
        if not cleaned or cleaned == '-':
            return default
        if '.' in cleaned:
            return int(float(cleaned))
        return int(cleaned)
    except (ValueError, TypeError):
        return default


def normalize_column_name(name: str) -> str:
    """컬럼명 정규화: 소문자, 공백→언더스코어, 특수문자 제거"""
    if not name:
        return ''
    result = str(name).strip().lower()
    result = result.replace(' ', '_').replace('-', '_')
    result = re.sub(r'[^a-z0-9_]', '', result)
    result = re.sub(r'_+', '_', result).strip('_')
    return result


def normalize_lot(val: Any) -> Optional[str]:
    """
    LOT 값 정규화 (엑셀 1125110452.0 등 → "1125110452").
    비교·DB 조회 시 동일 LOT로 인식되도록 문자열로 통일.
    """
    if val is None:
        return None
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        import math
        if math.isnan(val) or math.isinf(val):
            return None
        if val == int(val):
            return str(int(val))
        s = str(val).rstrip('0').rstrip('.')
        return s if s else None
    s = str(val).strip().replace(',', '')
    if not s:
        return None
    m = re.fullmatch(r'(\d+)\.0+', s)
    if m:
        return m.group(1)
    return s


# --- 정규화 함수 (매칭/중복 방지: trim + 표준키) ---

def norm_str(x: Any) -> Optional[str]:
    """기본 문자열 정규화: strip, 빈 문자열이면 None."""
    if x is None:
        return None
    s = str(x).strip()
    return s if s else None


def norm_upper(x: Any) -> Optional[str]:
    """대문자 통일 (BL, 컨테이너, 코드 등)."""
    s = norm_str(x)
    return s.upper() if s else None


def norm_digits_only(x: Any) -> Optional[str]:
    """숫자만 추출 (BL NO, SAP NO 표준키용)."""
    s = norm_str(x)
    if not s:
        return None
    # Excel float 문자열 보정: 2200033057.0 / MAEU258468669.00 -> 접미 .0 제거
    s_compact = s.replace(',', '')
    m = re.fullmatch(r'([A-Za-z]*\d+)\.0+', s_compact)
    if m:
        s = m.group(1)
    else:
        s = s_compact
    d = re.sub(r'\D+', '', s)
    return d if d else None


def norm_tonbag_no_std(raw: Any, width: int = TONBAG_NO_STD_WIDTH, is_sample: bool = False) -> Tuple[Optional[str], int]:
    """
    톤백번호 표준화: 좌측 0 패딩 유지, 내부 sub_lt 정수 반환.
    입력: 1, "001", " 001 " -> 표준문자열 "001", sub_lt 1.
    샘플이면 ("S00", 0).
    Returns:
        (tonbag_no_std: str | None, sub_lt: int)
    """
    if is_sample:
        return 'S00', 0
    s = norm_str(raw)
    if not s:
        return None, 0
    s_upper = s.upper()
    if s_upper.startswith('S') and len(s_upper) <= 4:
        return 'S00', 0
    if re.fullmatch(r'\d+', s):
        n = int(s)
        return s.zfill(width), n
    return None, 0


def norm_bl_no(x: Any) -> Optional[str]:
    """BL NO 표준화 (DB 저장용).

    v9.0: MAEU263764814 형식 지원
    - 영문+숫자 조합(예: MAEU263764814, MSCU1234567): 원문(upper) 보존
    - 순수 숫자/소수표기(예: 263764814, 263764814.0): 숫자만 표준화
    """
    s_up = norm_upper(x)
    if not s_up:
        return None
    if re.search(r'[A-Z]', s_up):
        return s_up
    return norm_digits_only(x) or s_up


def norm_bl_no_for_query(x: Any) -> Optional[str]:
    """BL NO WHERE 조회용 정규화 (v9.0).

    DB에 MAEU263764814 또는 263764814 중 어느 형식이든 조회 가능하도록 정규화.

    MAEU263764814 → 263764814   (영문 2~4자 + 순수숫자 → 숫자만)
    263764814     → 263764814   (순수숫자 → 그대로)
    MSCU1234567   → 1234567     (영문4 + 순수숫자7 → 숫자만)
    MEDUFP963996  → MEDUFP963996 (영문+숫자 혼합 → 원문 유지)
    """
    s_up = norm_upper(x)
    if not s_up:
        return None
    # 영문 2~4자 + 순수숫자(6~15자) 조합만 숫자 추출
    m = re.match(r'^[A-Z]{2,4}(\d{6,15})$', s_up)
    if m:
        return m.group(1)
    # 순수 숫자
    if re.match(r'^\d{6,}$', s_up):
        return s_up
    # 영문+숫자 혼합(MEDUFP963996 등) → 원문 그대로 반환
    # (숫자 추출 시 일부만 잘릴 수 있으므로 원문 보존)
    return s_up


def norm_sap_no(x: Any) -> Optional[str]:
    """SAP NO 표준키: 숫자만 또는 원문 trim."""
    return norm_digits_only(x) or norm_str(x)


def norm_container_no(x: Any) -> Optional[str]:
    """컨테이너번호: upper + 공백/하이픈 제거 (FFAU4840178)."""
    s = norm_upper(x)
    if not s:
        return None
    return s.replace(' ', '').replace('-', '')


def norm_sale_ref(x: Any) -> Optional[str]:
    """SALE REF / ORDER NO: upper + trim + 연속 공백 1개."""
    s = norm_str(x)
    if not s:
        return None
    s = s.upper()
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def norm_location(x: Any) -> Optional[str]:
    """로케이션: upper, 공백/언더스코어 정리. (예: A-01-02)"""
    s = norm_upper(x)
    if not s:
        return None
    s = re.sub(r'[\s_]+', '', s)
    return s


def norm_date_any(x: Any) -> Optional[str]:
    """다양한 날짜 포맷 -> ISO YYYY-MM-DD. 실패 시 None."""
    s = norm_str(x)
    if not s:
        return None
    if hasattr(x, 'strftime'):
        return x.strftime('%Y-%m-%d')
    for fmt in ('%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d', '%y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S', '%d-%m-%Y'):
        for part in (s, s[:10]):
            try:
                dt = datetime.strptime(part, fmt)
                return dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError) as _e:
                logger.debug(f"[SUPPRESSED] exception in common.py: {_e}")  # noqa
    return None
