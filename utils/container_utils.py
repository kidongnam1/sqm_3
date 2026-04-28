# utils/container_utils.py
# SQM v865 — 컨테이너 번호 + 문서 파싱 유틸리티
# 작성: Ruby (Senior Software Architect) / 2026-04-28
# 수정: 2026-04-28 — Box, normalize_date, strip_doc_no 추가 (GPT 코드 참고)
#
# 공개 API:
#   [컨테이너]
#   normalize_container_no(raw)    -> 정규화 (공백·하이픈 제거, 대문자)
#   check_container_no(number)     -> ISO 6346 체크 디지트 검증
#   extract_container_nos(text)    -> 자유 텍스트에서 전체 추출
#
#   [좌표]
#   Box(x0, y0, x1, y1)           -> % 좌표 컨테이너 (선사별 페이지 크기 자동 대응)
#
#   [문서 번호]
#   strip_doc_no(raw)              -> BL/DO 번호 정규화 (알파뉴메릭만)
#
#   [날짜]
#   normalize_date(raw)            -> 다양한 날짜 형식 -> YYYY-MM-DD
#
#   [텍스트 정제]
#   normalize_spaces(text)         -> 전각 공백 포함 연속 공백 -> 단일 스페이스
#
#   [박스 추출]
#   extract_box(words, W, H, ...)   -> % 좌표 박스 추출 + 자동 fallback + 진단 로그
#   diagnose_box(words, W, H, ...)  -> 좌표 실패 시 근방 단어 반환 (개발/튜닝용)
#
# 사용법:
#   from utils.container_utils import (
#       normalize_container_no, check_container_no, extract_container_nos,
#       Box, strip_doc_no, normalize_date, normalize_spaces,
#   )

import re
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================
# 1. Box -- % 좌표 데이터클래스  (GPT 코드 Box.to_rect 참고)
# ============================================================
@dataclass(frozen=True)
class Box:
    """
    PDF 영역을 페이지 크기 대비 % 좌표로 저장하는 불변 객체.

    선사별 페이지 크기가 달라도 동일한 % 좌표를 사용.
      - HAPAG BL : Letter (612 x 792 pt)
      - MSC / ONE / MAERSK : A4  (595 x 842 pt)

    Examples:
      box = Box(x0=60.0, y0=10.0, x1=85.0, y1=13.0)
      rect_args = box.to_pixels(612, 792)   # HAPAG Letter
      rect_args = box.to_pixels(595, 842)   # A4

      # PyMuPDF 사용 시:
      import fitz
      clip = fitz.Rect(*box.to_pixels(page.rect.width, page.rect.height))
    """
    x0: float   # % of page width  (left)
    y0: float   # % of page height (top)
    x1: float   # % of page width  (right)
    y1: float   # % of page height (bottom)

    def to_pixels(self, page_width: float, page_height: float) -> tuple:
        """
        % 좌표 -> 픽셀 좌표 4-튜플.
        반환값을 fitz.Rect(*box.to_pixels(w, h)) 로 바로 사용 가능.
        """
        return (
            page_width  * self.x0 / 100.0,
            page_height * self.y0 / 100.0,
            page_width  * self.x1 / 100.0,
            page_height * self.y1 / 100.0,
        )

    @classmethod
    def from_tuple(cls, t: tuple) -> "Box":
        """기존 (x0, y0, x1, y1) 튜플에서 Box 생성 (하위 호환)."""
        return cls(*t)

    def __repr__(self) -> str:
        return (f"Box(x0={self.x0:.1f}%, y0={self.y0:.1f}%, "
                f"x1={self.x1:.1f}%, y1={self.y1:.1f}%)")


# ============================================================
# normalize_spaces -- 텍스트 공백 정제  (GPT extract_lines_in_box 참고)
# ============================================================
def normalize_spaces(text: str) -> str:
    """
    연속 공백·탭·전각 공백(\u00a0)을 단일 스페이스로 압축하고 앞뒤 제거.

    PDF get_text() 추출 시 끼어드는 \u00a0(non-breaking space)와
    탭 문자도 정리한다. extract_lines_in_box() 전처리로 사용.

    Examples:
      'A\u00a0B'       -> 'A B'
      '  hello  world  ' -> 'hello world'
      'A\tB'           -> 'A B'
    """
    return re.sub(r"[ \t\u00a0]+", " ", str(text or "").replace("\r", "\n")).strip()

# ============================================================
# 7. extract_box -- % 좌표 박스 추출 + 자동 fallback  (신규)
# ============================================================
def extract_box(
    words: list,
    W: float,
    H: float,
    x1: float,
    x2: float,
    y1: float,
    y2: float,
    *,
    join: str = " ",
    fallback_margin: float = 2.0,
    validator=None,
    field: str = "",
) -> str:
    """
    % 좌표 박스에서 단어 추출. 1차 실패 시 y축을 fallback_margin만큼 자동 확장 재시도.

    Args:
        words:           [{"text":str, "x0":px, "top":px, ...}, ...]  (페이지 px 단위)
        W, H:            페이지 너비·높이 (px)
        x1, x2, y1, y2: 추출 영역 (% of page)
        join:            단어 연결 문자 (" " = 기본, "" = nospace)
        fallback_margin: 1차 실패 시 y축 ± 확장 폭 (%, 0이면 fallback 없음)
        validator:       callable(str) -> bool — False 반환 시 빈 결과로 취급
        field:           진단 로그에 표시할 필드명 (예: "msc_bl_no")

    Returns:
        추출된 텍스트. 완전 실패 시 "" 반환.

    Examples:
        # 기본 사용 (space join, fallback ±2%)
        text = extract_box(words, W, H, 57.0, 80.0, 7.0, 8.0, field="bl_no")

        # nospace (문자 단위 분리 PDF)
        text = extract_box(words, W, H, 54.0, 75.0, 11.0, 12.5, join="", field="one_bl")

        # validator: BL 번호 패턴 검증 후 fallback
        import re as _re
        bl_pat = _re.compile(r"(MEDU|MSCU)[A-Z0-9]{6,10}")
        text = extract_box(words, W, H, 57, 80, 7, 8,
                           validator=lambda s: bool(bl_pat.search(s)),
                           field="msc_bl_no")
    """
    def _extract(ay1: float, ay2: float) -> str:
        hits = sorted(
            [w for w in words
             if x1 <= w["x0"] / W * 100 <= x2
             and ay1 <= w["top"] / H * 100 <= ay2],
            key=lambda t: (t["top"], t["x0"]),
        )
        return join.join(t["text"] for t in hits).strip()

    result = _extract(y1, y2)

    if result and (validator is None or validator(result)):
        return result

    # 1차 실패 or validator 불통과 → y 범위 확장 fallback
    if fallback_margin > 0:
        fb_result = _extract(y1 - fallback_margin, y2 + fallback_margin)
        if fb_result and (validator is None or validator(fb_result)):
            logger.warning(
                "[extract_box] %s fallback ±%.1f%% 성공: y=%.1f~%.1f%% → %r",
                field or "?", fallback_margin,
                y1 - fallback_margin, y2 + fallback_margin, fb_result,
            )
            return fb_result

    # 완전 실패 → 진단 로그 (x 범위 내 가장 가까운 단어 5개 출력)
    if not result:
        nearby = sorted(
            [w for w in words if x1 <= w["x0"] / W * 100 <= x2],
            key=lambda t: t["top"],
        )
        if nearby:
            logger.debug(
                "[extract_box] %s 빈결과 — x=%.0f~%.0f%% 근방 단어 top5: %s",
                field or "?", x1, x2,
                [(f"y={round(w['top']/H*100,1)}%", w["text"]) for w in nearby[:5]],
            )
    return result


# ============================================================
# 8. diagnose_box -- 좌표 진단 헬퍼 (개발/튜닝용)
# ============================================================
def diagnose_box(
    words: list,
    W: float,
    H: float,
    x1: float,
    x2: float,
    y_center: float,
    radius: float = 5.0,
) -> list:
    """
    파싱 실패 시 진단용 — x 범위 내에서 y_center ± radius% 안의 단어를 반환.

    반환값 각 항목: {"text": str, "x_pct": float, "y_pct": float}

    사용법:
        hits = diagnose_box(words, W, H, x1=57, x2=80, y_center=7.5, radius=5)
        for h in hits:
            print(f"  x={h['x_pct']:.1f}%  y={h['y_pct']:.1f}%  {h['text']\!r}")

    좌표 조정 가이드:
        1. extract_box() 가 빈 결과 반환
        2. diagnose_box() 로 실제 단어 위치 확인
        3. 출력된 y_pct 값으로 CARRIER_COORD_TABLE 또는 by_xy() 좌표 수정
    """
    return [
        {
            "text": w["text"],
            "x_pct": round(w["x0"] / W * 100, 1),
            "y_pct": round(w["top"] / H * 100, 1),
        }
        for w in sorted(words, key=lambda t: (t["top"], t["x0"]))
        if x1 <= w["x0"] / W * 100 <= x2
        and (y_center - radius) <= w["top"] / H * 100 <= (y_center + radius)
    ]



# ============================================================
# 2. strip_doc_no -- BL/DO 번호 정규화  (GPT compact_alnum 참고)
# ============================================================
def strip_doc_no(raw: str) -> str:
    """
    BL/DO 번호에서 공백·특수문자를 제거하고 알파뉴메릭 대문자만 반환.

    OCR 스캔 PDF에서 번호에 끼어드는 공백·점·줄바꿈 제거용.

    Examples:
      'MEDUW 9018104'   -> 'MEDUW9018104'
      'HLC.SCL260148627' -> 'HLCSCL260148627'
      'meduw9018104'    -> 'MEDUW9018104'
      ''                 -> ''
    """
    return re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())


# ============================================================
# 3. normalize_date -- 날짜 정규화  (GPT normalize_date 참고)
# ============================================================
_MONTH_MAP: dict = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_DATE_PATTERNS = [
    (re.compile(r"(\d{1,2})\s+([A-Z]{3})\s+(\d{4})"), "dmy_text"),
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), "ymd_dash"),
    (re.compile(r"(\d{2})/(\d{2})/(\d{4})"), "dmy_slash"),
    (re.compile(r"(\d{4})\.(\d{2})\.(\d{2})"), "ymd_dot"),
    (re.compile(r"(\d{2})\.(\d{2})\.(\d{4})"), "dmy_dot"),
    (re.compile(r"^(\d{4})(\d{2})(\d{2})$"), "ymd_compact"),
]


def normalize_date(raw: str, out_fmt: str = "%Y-%m-%d") -> str:
    """
    다양한 날짜 표기를 YYYY-MM-DD(기본)로 통일.

    지원 형식:
      '16 JUN 2025'  -> '2025-06-16'  (HAPAG DO, MSC DO)
      '2025-06-16'   -> '2025-06-16'
      '16/06/2025'   -> '2025-06-16'
      '2025.06.16'   -> '2025-06-16'
      '16.06.2025'   -> '2025-06-16'
      '20250616'     -> '2025-06-16'

    Returns:
      YYYY-MM-DD 형식 문자열, 파싱 실패 시 빈 문자열 반환.
    """
    if not raw:
        return ""
    s = str(raw).strip().upper()

    for pat, fmt_key in _DATE_PATTERNS:
        m = pat.search(s)
        if not m:
            continue
        try:
            if fmt_key == "dmy_text":
                d, mon_str, y = int(m.group(1)), m.group(2), int(m.group(3))
                month = _MONTH_MAP.get(mon_str)
                if not month:
                    continue
                dt = datetime(y, month, d)
            elif fmt_key == "ymd_dash":
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            elif fmt_key == "dmy_slash":
                dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            elif fmt_key in ("ymd_dot", "ymd_compact"):
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            elif fmt_key == "dmy_dot":
                dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            else:
                continue
            return dt.strftime(out_fmt)
        except (ValueError, TypeError):
            continue

    logger.debug("[normalize_date] 파싱 실패: %r", raw)
    return ""


# ============================================================
# ISO 6346 문자->수치 테이블
# A=10, B=12, C=13 ... Z=38  (11의 배수인 11,22,33은 건너뜀)
# ============================================================
_LETTER_VAL: dict = {
    c: v for c, v in zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        [10, 12, 13, 14, 15, 16, 17, 18, 19, 20,
         21, 23, 24, 25, 26, 27, 28, 29, 30, 31,
         32, 34, 35, 36, 37, 38]
    )
}

_CT_RE = re.compile(r"[A-Z]{4}\s?\d{7}")


# ============================================================
# 4. normalize_container_no
# ============================================================
def normalize_container_no(raw: str) -> str:
    """
    컨테이너 번호를 표준 형식으로 정규화.

    처리:
      - 소문자 -> 대문자
      - 공백·하이픈·밑줄 제거
      - 형식 불일치 시 빈 문자열 반환

    Examples:
      'HAMU 2354538'  -> 'HAMU2354538'
      'hamu2354538'   -> 'HAMU2354538'
      'HAMU-2354538'  -> 'HAMU2354538'
      'ABC123'        -> ''  (형식 불일치)
    """
    cleaned = re.sub(r"[\s\-_]", "", str(raw or "").upper())
    if re.fullmatch(r"[A-Z]{4}\d{7}", cleaned):
        return cleaned
    return ""


# ============================================================
# 5. check_container_no
# ============================================================
def check_container_no(number: str) -> bool:
    """
    ISO 6346 체크 디지트 검증.

    컨테이너 번호 11자리 (예: HAMU2354538):
      - 앞 10자리로 가중합 계산
      - 11로 나눈 나머지 -> 10이면 0으로 처리
      - 계산값이 마지막 자리(체크 디지트)와 같아야 정상

    Returns:
      True  -> 체크 디지트 일치 (정상)
      False -> 불일치 (OCR 오류·타이핑 실수 가능성)
    """
    s = normalize_container_no(number)
    if not s:
        return False

    total = 0
    for i, ch in enumerate(s[:10]):
        val = _LETTER_VAL[ch] if ch.isalpha() else int(ch)
        total += val * (2 ** i)

    expected = (total % 11) % 10
    actual   = int(s[10])
    ok = (expected == actual)

    if not ok:
        logger.debug("[container] 체크 디지트 불일치: %s (계산=%d, 실제=%d)",
                     s, expected, actual)
    return ok


# ============================================================
# 6. extract_container_nos
# ============================================================
def extract_container_nos(text: str) -> list:
    """
    자유 텍스트에서 컨테이너 번호 전체 추출.

    - 공백 포함 형식 허용 ('HAMU 2354538')
    - 정규화 후 중복 제거 (삽입 순서 유지)

    Returns:
      ['HAMU2354538', 'HAMU2410117', ...]
    """
    seen: dict = {}
    for raw in _CT_RE.findall(str(text or "").upper()):
        normed = normalize_container_no(raw)
        if normed and normed not in seen:
            seen[normed] = None
    return list(seen.keys())
