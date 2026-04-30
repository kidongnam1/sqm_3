"""
SQM v5.8.6.B — 날짜 유틸리티 (Single Source of Truth)
======================================================
normalize_date(), 정규식 폴백, Free Time 계산을 한 곳에 모음.

변경 이력:
    v5.8.6.B (2026-02-17): 신규 생성 — 문서 1(v2.5.3)의 검증된 로직 이식

사용법:
    from utils.date_utils import normalize_date, extract_ship_date, extract_arrival_date
    from utils.date_utils import calculate_free_time_status
"""

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 1. normalize_date() — 6가지 날짜 형식 → date 객체
# ═══════════════════════════════════════════════════════════════

# 영문 월 매핑
_MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
    'JANUARY': 1, 'FEBRUARY': 2, 'MARCH': 3, 'APRIL': 4,
    'JUNE': 6, 'JULY': 7, 'AUGUST': 8, 'SEPTEMBER': 9,
    'OCTOBER': 10, 'NOVEMBER': 11, 'DECEMBER': 12,
}


def normalize_date(date_str: Any) -> Optional[date]:
    """
    다양한 날짜 형식을 date 객체로 변환.

    지원 형식:
        1) YYYY-MM-DD (ISO)       → 2025-10-17
        2) YYYY/MM/DD             → 2025/10/17
        3) YYYY.MM.DD             → 2025.10.17
        4) DD/MM/YYYY (유럽식)    → 17/10/2025
        5) 영문월: SEP 15, 2025 / 15 SEP 2025 / September 15, 2025
        6) 한글: 2025년 10월 17일

    Args:
        date_str: 날짜 문자열 (str, date, None 허용)

    Returns:
        date 객체 또는 None
    """
    if date_str is None:
        return None

    # 이미 date 객체이면 그대로
    if isinstance(date_str, date) and not isinstance(date_str, datetime):
        return date_str
    if isinstance(date_str, datetime):
        return date_str.date()

    s = str(date_str).strip()

    # NOT_FOUND, 빈 문자열, None 문자열 처리
    if not s or s in ('NOT_FOUND', 'None', 'null', 'N/A', '-', ''):
        return None

    # 앞쪽 10글자만 (시간 부분 제거)
    s = s[:20]

    # 1) ISO: YYYY-MM-DD
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError as e:
            logger.debug(f"Suppressed: {e}")

    # 1b) Compact ISO: YYYYMMDD
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError as e:
            logger.debug(f"Suppressed: {e}")

    # 2) YYYY/MM/DD
    m = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError as e:
            logger.debug(f"Suppressed: {e}")

    # 3) YYYY.MM.DD
    m = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError as e:
            logger.debug(f"Suppressed: {e}")

    # 4) DD/MM/YYYY 또는 DD-MM-YYYY (유럽식)
    m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return date(y, mo, d)
            except ValueError as e:
                logger.debug(f"Suppressed: {e}")

    # 4b) DD-Mon-YYYY (하이픈 + 영문월)
    # 예: 29-Jan-2026, 15-FEB-2025, 03-DECEMBER-2025
    # 4b') DD.Mon.YYYY (점 구분 + 영문월) — HAPAG BL ship_date 형식
    # 예: 26.FEB.2026
    m = re.match(r'^(\d{1,2})[.\-]([A-Za-z]+)[.\-](\d{4})$', s)
    if m:
        d = int(m.group(1))
        mon = m.group(2).upper()
        y = int(m.group(3))
        if mon in _MONTH_MAP:
            try:
                return date(y, _MONTH_MAP[mon], d)
            except ValueError as e:
                logger.debug(f"Suppressed: {e}")

    # 5) 영문월: "SEP 15, 2025" / "15 SEP 2025" / "September 15, 2025"
    s_upper = s.upper().replace(',', '')
    # "MON DD YYYY" 또는 "MONTH DD YYYY"
    m = re.match(r'^([A-Z]+)\s+(\d{1,2})\s+(\d{4})$', s_upper)
    if m and m.group(1) in _MONTH_MAP:
        try:
            return date(int(m.group(3)), _MONTH_MAP[m.group(1)], int(m.group(2)))
        except ValueError as e:
            logger.debug(f"Suppressed: {e}")
    # "DD MON YYYY" 또는 "DD MONTH YYYY"
    m = re.match(r'^(\d{1,2})\s+([A-Z]+)\s+(\d{4})$', s_upper)
    if m and m.group(2) in _MONTH_MAP:
        try:
            return date(int(m.group(3)), _MONTH_MAP[m.group(2)], int(m.group(1)))
        except ValueError as e:
            logger.debug(f"Suppressed: {e}")

    # 6) 한글: "2025년 10월 17일"
    m = re.match(r'^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일?', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError as e:
            logger.debug(f"Suppressed: {e}")

    logger.debug(f"[date_utils] normalize_date 실패: '{date_str}'")
    return None


# ═══════════════════════════════════════════════════════════════
# 2. 정규식 패턴 사전 — 문서 1(v2.5.3)에서 검증된 패턴
# ═══════════════════════════════════════════════════════════════

_BL_SHIP_DATE_PATTERNS = [
    # "SHIPPED ON BOARD DATE: 2025-09-15"
    r'SHIPPED\s*ON\s*BOARD\s*(?:DATE)?\s*[:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    # "ON BOARD DATE"
    r'ON\s*BOARD\s*DATE\s*[:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    # "LADEN ON BOARD"
    r'LADEN\s*ON\s*BOARD\s*[:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    # "DATE OF SHIPMENT"
    r'DATE\s*OF\s*SHIPMENT\s*[:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    # 유럽식 DD/MM/YYYY
    r'SHIPPED\s*ON\s*BOARD.*?(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
    # 영문월: "15 SEP 2025"
    r'SHIPPED\s*ON\s*BOARD.*?(\d{1,2}\s+[A-Z]{3}\s+\d{4})',
    # 영문월: "SEP 15, 2025"
    r'SHIPPED\s*ON\s*BOARD.*?([A-Z]{3}\s+\d{1,2},?\s+\d{4})',
]

_DO_ARRIVAL_DATE_PATTERNS = [
    # "선박 입항일" 다음 줄의 날짜 (가장 정확)
    r'선박\s*입항일(?:[\s\S]{1,60}?)(\d{4}-\d{1,2}-\d{1,2})',  # v8.2.4: MRN/MSN 사이 날짜도 포함
    # "입항일: 2025-10-17"
    r'입항일?\s*[:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    # 영문 라벨
    r'(?:ARRIVAL|입항)\s*(?:DATE|일)?\s*[:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    r'ETA\s*(?:BUSAN)?\s*[:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    r'ATA\s*[:\s]*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})',
    # 유럽식
    r'입항일?\s*[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
]


# ═══════════════════════════════════════════════════════════════
# 3. 하이브리드 추출 함수
# ═══════════════════════════════════════════════════════════════

def extract_ship_date(gemini_data: dict, pdf_text: str = '') -> Tuple[Optional[date], str, bool]:
    """
    B/L에서 선적일(Ship Date) 추출 — Gemini 우선, 정규식 폴백.

    Args:
        gemini_data: Gemini 파싱 결과 (dict 또는 객체의 __dict__)
        pdf_text: PDF에서 추출한 텍스트 (정규식 폴백용)

    Returns:
        (ship_date, source, estimated)
        - ship_date: date 객체 또는 None
        - source: 'gemini' | 'regex' | 'none'
        - estimated: True면 추정값
    """
    # dict가 아니면 변환
    if not isinstance(gemini_data, dict):
        gemini_data = getattr(gemini_data, '__dict__', {})

    # ── 1차: Gemini 결과 확인 (3개 키 순차) ──
    ship_str = (gemini_data.get('shipped_on_board_date') or
                gemini_data.get('shipped_date') or
                gemini_data.get('ship_date') or '')

    parsed = normalize_date(ship_str)
    if parsed:
        logger.info(f"[BL] Ship Date: {parsed} [Gemini]")
        return (parsed, 'gemini', False)

    # ── 2차: 정규식 폴백 (pdf_text 필요) ──
    if pdf_text:
        for pattern in _BL_SHIP_DATE_PATTERNS:
            match = re.search(pattern, pdf_text, re.IGNORECASE | re.DOTALL)
            if match:
                parsed = normalize_date(match.group(1))
                if parsed:
                    logger.warning(f"[BL] Ship Date: {parsed} [정규식 폴백 ⚠️]")
                    return (parsed, 'regex', True)

    # Ship Date는 일부 B/L에서 부재 가능(업무 진행 가능)하므로 ERROR 대신 WARNING으로 기록
    logger.warning("[BL] Ship Date: 찾지 못함 (선택 필드)")
    return (None, 'none', False)


def extract_arrival_date(gemini_data: dict, pdf_text: str = '') -> Tuple[Optional[date], str, bool]:
    """
    D/O에서 입항일(Arrival Date) 추출 — Gemini 우선, 정규식 폴백, all_dates 추정.

    Args:
        gemini_data: Gemini 파싱 결과
        pdf_text: PDF에서 추출한 텍스트 (정규식 폴백용)

    Returns:
        (arrival_date, source, estimated)
    """
    if not isinstance(gemini_data, dict):
        gemini_data = getattr(gemini_data, '__dict__', {})

    # ── 1차: Gemini 결과 확인 (다중 키) ──
    arrival_str = (gemini_data.get('arrival_date') or
                   gemini_data.get('eta_date') or
                   gemini_data.get('eta') or
                   gemini_data.get('vessel_arrival') or
                   gemini_data.get('eta_busan') or '')

    parsed = normalize_date(arrival_str)
    if parsed:
        logger.info(f"[DO] Arrival Date: {parsed} [Gemini]")
        return (parsed, 'gemini', False)

    # ── 2차: 정규식 폴백 ──
    if pdf_text:
        for pattern in _DO_ARRIVAL_DATE_PATTERNS:
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                parsed = normalize_date(match.group(1))
                if parsed:
                    logger.warning(f"[DO] Arrival Date: {parsed} [정규식 폴백 ⚠️]")
                    return (parsed, 'regex', True)

    # ── 3차: all_dates_found에서 추정 ──
    all_dates = gemini_data.get('all_dates_found', [])
    issue_date_str = gemini_data.get('issue_date', '')
    if all_dates:
        candidates = []
        for d_str in all_dates:
            if d_str == issue_date_str:
                continue  # 발행일 제외
            p = normalize_date(d_str)
            if p:
                candidates.append(p)
        if candidates:
            earliest = min(candidates)
            logger.warning(f"[DO] Arrival Date: {earliest} [all_dates 추정 🟡]")
            return (earliest, 'estimated', True)

    # Arrival Date는 문서 품질/형식에 따라 누락될 수 있어 WARNING으로 기록
    logger.warning("[DO] Arrival Date: 찾지 못함 (수동 입력 가능)")
    return (None, 'none', False)


# ═══════════════════════════════════════════════════════════════
# 4. Free Time 계산 — 문서 1(v2.5.3)에서 이식
# ═══════════════════════════════════════════════════════════════

def calculate_free_time_status(arrival_date: date, free_days: int = 14) -> Dict[str, Any]:
    """
    arrival_date 기준 Free Time 상태 계산.

    Args:
        arrival_date: 입항일 (date 객체)
        free_days: 무료 보관 일수 (기본 14일)

    Returns:
        dict: {status, color, free_time_end, remaining_days, message}
    """
    today = date.today()
    free_time_end = arrival_date + timedelta(days=free_days)
    remaining = (free_time_end - today).days

    if remaining <= 0:
        return {
            'status': 'EXPIRED', 'color': 'red',
            'free_time_end': str(free_time_end),
            'remaining_days': remaining,
            'message': f'⛔ 무료기간 {abs(remaining)}일 초과!'
        }
    elif remaining <= 3:
        return {
            'status': 'URGENT', 'color': 'red',
            'free_time_end': str(free_time_end),
            'remaining_days': remaining,
            'message': f'🔴 긴급! {remaining}일 남음'
        }
    elif remaining <= 7:
        return {
            'status': 'WARNING', 'color': 'orange',
            'free_time_end': str(free_time_end),
            'remaining_days': remaining,
            'message': f'🟡 주의: {remaining}일 남음'
        }
    else:
        return {
            'status': 'NORMAL', 'color': 'green',
            'free_time_end': str(free_time_end),
            'remaining_days': remaining,
            'message': f'🟢 정상: {remaining}일 남음'
        }


# ═══════════════════════════════════════════════════════════════
# 5. PDF 텍스트 추출 헬퍼
# ═══════════════════════════════════════════════════════════════

def normalize_date_str(date_str: Any) -> Optional[str]:
    """Normalize a supported date value to YYYY-MM-DD."""
    parsed = normalize_date(date_str)
    return parsed.isoformat() if parsed else None


def calculate_free_days(arrival_date: Any, return_date: Any) -> Optional[int]:
    """
    Calculate DO free time days from arrival date and container return date.

    Returns None when either date cannot be parsed. Negative results are clamped
    to 0 so invalid OCR ordering does not create negative free-time values.
    """
    arrival = normalize_date(arrival_date)
    returned = normalize_date(return_date)
    if not arrival or not returned:
        return None
    return max(0, (returned - arrival).days)


def extract_pdf_text(pdf_path: str, max_pages: int = 5) -> str:
    """
    PDF에서 텍스트 추출 (정규식 폴백용).
    PyMuPDF(fitz) 사용. 이미지 PDF면 빈 문자열 반환.
    """
    try:
        from core.pdf_engine import open_pdf
        doc = open_pdf(pdf_path)
        texts = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            texts.append(page.get_text())
        doc.close()
        return '\n'.join(texts)
    except ImportError:
        logger.debug("[date_utils] PyMuPDF 미설치 — 정규식 폴백 불가")
        return ''
    except Exception as e:
        logger.debug(f"[date_utils] PDF 텍스트 추출 실패: {e}")
        return ''
