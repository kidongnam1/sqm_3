# tests/test_container.py
# SQM v865 -- 컨테이너 번호 + 문서 파싱 유틸리티 단위 테스트
# 실행: pytest tests/test_container.py -v
# 수정: 2026-04-28 -- Box / normalize_date / strip_doc_no 테스트 추가

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import re
from utils.container_utils import (
    normalize_container_no,
    check_container_no,
    extract_container_nos,
    Box,
    strip_doc_no,
    normalize_date,
    normalize_spaces,
    extract_box,
    diagnose_box,
)


# ============================================================
# 1. normalize_container_no  (기존 5개)
# ============================================================
class TestNormalize:
    def test_space_removed(self):
        assert normalize_container_no('HAMU 2354538') == 'HAMU2354538'

    def test_lowercase_to_upper(self):
        assert normalize_container_no('hamu2354538') == 'HAMU2354538'

    def test_hyphen_removed(self):
        assert normalize_container_no('HAMU-2354538') == 'HAMU2354538'

    def test_invalid_returns_empty(self):
        assert normalize_container_no('ABC123') == ''
        assert normalize_container_no('') == ''
        assert normalize_container_no(None) == ''

    def test_already_clean(self):
        assert normalize_container_no('MSMU5531984') == 'MSMU5531984'


# ============================================================
# 2. check_container_no -- ISO 6346  (기존 5개)
# ============================================================
class TestCheckDigit:
    def test_valid_msmu(self):
        assert check_container_no('MSMU5531984') is True

    def test_valid_uetu(self):
        assert check_container_no('UETU6117887') is True

    def test_valid_with_space(self):
        assert check_container_no('MSMU 5531984') is True

    def test_wrong_check_digit(self):
        assert check_container_no('MSMU5531985') is False

    def test_invalid_format(self):
        assert check_container_no('ABC123') is False
        assert check_container_no('') is False


# ============================================================
# 3. extract_container_nos  (기존 6개)
# ============================================================
class TestExtract:
    def test_single(self):
        assert extract_container_nos('MSMU5531984 입고') == ['MSMU5531984']

    def test_multiple(self):
        result = extract_container_nos('MSMU5531984 UETU6117887')
        assert 'MSMU5531984' in result
        assert 'UETU6117887' in result
        assert len(result) == 2

    def test_space_split_hapag(self):
        assert extract_container_nos('HAMU 2354538 입고') == ['HAMU2354538']

    def test_dedup(self):
        result = extract_container_nos('MSMU5531984 / MSMU5531984')
        assert result.count('MSMU5531984') == 1

    def test_empty_text(self):
        assert extract_container_nos('') == []
        assert extract_container_nos(None) == []

    def test_no_bl_number_confusion(self):
        result = extract_container_nos('BL: MEDUW9018104')
        assert isinstance(result, list)


# ============================================================
# 4. Box -- % 좌표 데이터클래스  (신규 5개)
# ============================================================
class TestBox:
    def test_to_pixels_a4_full_page(self):
        box = Box(x0=0.0, y0=0.0, x1=100.0, y1=100.0)
        x0, y0, x1, y1 = box.to_pixels(595, 842)
        assert x0 == pytest.approx(0.0)
        assert y1 == pytest.approx(842.0)

    def test_to_pixels_letter_hapag(self):
        box = Box(x0=62.3, y0=11.1, x1=81.2, y1=12.8)
        x0, y0, x1, y1 = box.to_pixels(612, 792)
        assert x0 == pytest.approx(612 * 0.623, rel=1e-3)
        assert y0 == pytest.approx(792 * 0.111, rel=1e-3)
        assert x1 == pytest.approx(612 * 0.812, rel=1e-3)
        assert y1 == pytest.approx(792 * 0.128, rel=1e-3)

    def test_different_page_sizes_give_different_pixels(self):
        box = Box(x0=50.0, y0=50.0, x1=50.0, y1=50.0)
        px_a4     = box.to_pixels(595, 842)
        px_letter = box.to_pixels(612, 792)
        assert px_a4[0]     == pytest.approx(297.5)
        assert px_letter[0] == pytest.approx(306.0)

    def test_from_tuple(self):
        box = Box.from_tuple((10.0, 20.0, 90.0, 80.0))
        assert box.x0 == 10.0 and box.y0 == 20.0
        assert box.x1 == 90.0 and box.y1 == 80.0

    def test_immutable(self):
        box = Box(x0=10.0, y0=10.0, x1=90.0, y1=90.0)
        with pytest.raises(Exception):
            box.x0 = 0.0  # type: ignore


# ============================================================
# 5. strip_doc_no -- BL/DO 번호 정규화  (신규 5개)
# ============================================================
class TestStripDocNo:
    def test_space_removed(self):
        assert strip_doc_no('MEDUW 9018104') == 'MEDUW9018104'

    def test_dot_removed(self):
        assert strip_doc_no('HLC.SCL260148627') == 'HLCSCL260148627'

    def test_lowercase_to_upper(self):
        assert strip_doc_no('meduw9018104') == 'MEDUW9018104'

    def test_already_clean(self):
        assert strip_doc_no('HLCUSCL260148627') == 'HLCUSCL260148627'

    def test_empty(self):
        assert strip_doc_no('') == ''
        assert strip_doc_no(None) == ''


# ============================================================
# 6. normalize_date -- 날짜 정규화  (신규 10개)
# ============================================================
class TestNormalizeDate:
    def test_dmy_text_hapag_msc(self):
        assert normalize_date('16 JUN 2025') == '2025-06-16'

    def test_dmy_text_single_digit_day(self):
        assert normalize_date('6 JUN 2025') == '2025-06-06'

    def test_ymd_dash_iso(self):
        assert normalize_date('2025-06-16') == '2025-06-16'

    def test_dmy_slash(self):
        assert normalize_date('16/06/2025') == '2025-06-16'

    def test_ymd_dot(self):
        assert normalize_date('2025.06.16') == '2025-06-16'

    def test_dmy_dot(self):
        assert normalize_date('16.06.2025') == '2025-06-16'

    def test_ymd_compact(self):
        assert normalize_date('20250616') == '2025-06-16'

    def test_invalid_returns_empty(self):
        assert normalize_date('') == ''
        assert normalize_date(None) == ''
        assert normalize_date('not-a-date') == ''

    def test_invalid_month_name(self):
        assert normalize_date('16 XXX 2025') == ''

    def test_custom_out_fmt(self):
        assert normalize_date('16 JUN 2025', out_fmt='%d/%m/%Y') == '16/06/2025'

# ============================================================
# 7. normalize_spaces -- 공백 정제  (신규 4개)
# ============================================================
class TestNormalizeSpaces:
    def test_nbsp_removed(self):
        assert normalize_spaces('A B') == 'A B'

    def test_multiple_spaces(self):
        assert normalize_spaces('  hello  world  ') == 'hello world'

    def test_tab_removed(self):
        assert normalize_spaces('A	B') == 'A B'

    def test_empty(self):
        assert normalize_spaces('') == ''
        assert normalize_spaces(None) == ''

# ============================================================
# 8. extract_box -- fallback + validator + diagnose  (신규 7개)
# ============================================================
def _make_words(*items):
    """헬퍼: (text, x0_pct, top_pct) 리스트 → words dict 리스트 (W=H=100 기준)"""
    return [
        {"text": t, "x0": float(x), "top": float(y),
         "x1": float(x + 5), "bottom": float(y + 2)}
        for t, x, y in items
    ]


class TestExtractBox:
    def test_basic_space_join(self):
        words = _make_words(("HELLO", 10, 5), ("WORLD", 20, 5))
        assert extract_box(words, 100, 100, 5, 30, 3, 7) == "HELLO WORLD"

    def test_nospace_join(self):
        words = _make_words(("HEL", 10, 5), ("LO", 15, 5))
        assert extract_box(words, 100, 100, 5, 30, 3, 7, join="") == "HELLO"

    def test_sort_top_then_x(self):
        # y=10%(SECOND) 가 먼저 정의돼도 y=5%(FIRST) 가 앞에 와야 함
        words = _make_words(("SECOND", 10, 10), ("FIRST", 10, 5))
        assert extract_box(words, 100, 100, 5, 30, 3, 12) == "FIRST SECOND"

    def test_fallback_expands_y(self):
        # 단어가 y=8.5% — 원래 범위(y=3~7%)엔 없고 fallback(±2% → 1~9%)엔 잡힘
        words = _make_words(("TARGET", 10, 8.5))
        result = extract_box(words, 100, 100, 5, 30, 3, 7, fallback_margin=2.0)
        assert result == "TARGET"

    def test_no_fallback_when_margin_zero(self):
        words = _make_words(("TARGET", 10, 8.5))
        assert extract_box(words, 100, 100, 5, 30, 3, 7, fallback_margin=0) == ""

    def test_validator_rejects_noise_uses_fallback(self):
        # y=5% 에는 노이즈("NOISE"), y=8%에 숫자("MSC123") — validator 숫자 필수
        words = _make_words(("NOISE", 10, 5), ("MSC123", 10, 8))
        validator = lambda s: bool(re.search(r"\d", s))
        result = extract_box(words, 100, 100, 5, 30, 3, 6,
                             fallback_margin=3.0, validator=validator, field="test_bl")
        assert "MSC123" in result

    def test_total_miss_returns_empty(self):
        words = _make_words(("FAR", 90, 90))
        assert extract_box(words, 100, 100, 5, 30, 3, 7, fallback_margin=2.0) == ""


# ============================================================
# 9. diagnose_box -- 진단 헬퍼  (신규 3개)
# ============================================================
class TestDiagnoseBox:
    def test_returns_word_in_range(self):
        words = [{"text": "BL", "x0": 60.0, "top": 7.5, "x1": 65.0, "bottom": 8.0}]
        hits = diagnose_box(words, 100, 100, x1=55, x2=80, y_center=7.5, radius=3.0)
        assert len(hits) == 1
        assert hits[0]["text"] == "BL"
        assert hits[0]["y_pct"] == pytest.approx(7.5)

    def test_excludes_far_word(self):
        words = [{"text": "FAR", "x0": 60.0, "top": 20.0, "x1": 65.0, "bottom": 21.0}]
        hits = diagnose_box(words, 100, 100, x1=55, x2=80, y_center=7.5, radius=3.0)
        assert hits == []

    def test_sorted_by_y_then_x(self):
        words = _make_words(("B", 65, 8), ("A", 60, 5))
        hits = diagnose_box(words, 100, 100, x1=55, x2=80, y_center=6.5, radius=5.0)
        assert [h["text"] for h in hits] == ["A", "B"]
