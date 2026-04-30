from datetime import date

from utils.date_utils import calculate_free_days, normalize_date, normalize_date_str


def test_normalize_date_compact_yyyymmdd():
    assert normalize_date("20260424") == date(2026, 4, 24)
    assert normalize_date_str("20260424") == "2026-04-24"


def test_calculate_free_days_from_do_dates():
    assert calculate_free_days("2026-04-11", "20260424") == 13
    assert calculate_free_days("11-APR-2026", "24/04/2026") == 13
    assert calculate_free_days("2026.4.11", "2026.4.24") == 13


def test_calculate_free_days_clamps_negative_ocr_ordering():
    assert calculate_free_days("2026-04-24", "2026-04-11") == 0


def test_calculate_free_days_returns_none_for_unparseable_dates():
    assert calculate_free_days("not-a-date", "20260424") is None
    assert calculate_free_days("2026-04-11", "") is None
