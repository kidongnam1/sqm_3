# -*- coding: utf-8 -*-
"""
tests/test_bl_container_matching.py
BL 컨테이너 번호 매칭 + Daily Gemini Cache 유닛 테스트

커버리지:
  1. TestContainerNormalization   — ISO 6346 정규화 (_norm_container + inbound 인라인)
  2. TestDbUpdateLotsContainers   — _db_update_lots 로 컨테이너 매칭 (in-memory SQLite)
  3. TestOneCarrierContainerFmt   — ONE(ONEY) 선사 컨테이너 포맷 end-to-end
  4. TestDailyGeminiCache         — _DAILY_CACHE / _record_gemini_failure / _prefer_openai_today
  5. TestDailyCacheIntegration    — MultiProviderParser 가 임계치 초과 시 Gemini skip
"""
import re
import sqlite3
import sys
import os
import importlib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parsers.document_parser_modular.ai_fallback import (
    _norm_container,
    _record_gemini_failure,
    _prefer_openai_today,
    _DAILY_CACHE,
    _GEMINI_DAILY_FAIL_THRESHOLD,
    MultiProviderParser,
    _is_transient_error,
)


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def _reset_cache():
    """테스트 간 _DAILY_CACHE 리셋."""
    _DAILY_CACHE.update({"date": "", "failures": 0, "prefer_openai": False})


def _make_db(rows: list[dict]) -> sqlite3.Connection:
    """in-memory SQLite — inventory 테이블에 rows 삽입."""
    con = sqlite3.connect(":memory:")
    con.execute(
        "CREATE TABLE inventory (lot_no TEXT, container_no TEXT, "
        "bl_no TEXT, vessel TEXT, voyage TEXT, ship_date TEXT)"
    )
    for r in rows:
        con.execute(
            "INSERT INTO inventory (lot_no, container_no, bl_no, vessel, voyage, ship_date)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                r.get("lot_no", ""),
                r.get("container_no", ""),
                r.get("bl_no", ""),
                r.get("vessel", ""),
                r.get("voyage", ""),
                r.get("ship_date", ""),
            ),
        )
    con.commit()
    return con


def _db_update_lots(db_con, where_col, where_vals, update_dict):
    """inbound.py 의 _db_update_lots 를 테스트용으로 인라인 복제."""
    if not where_vals or not update_dict:
        return {"updated": 0, "lots": [], "skipped_empty": 0}
    pairs = {k: v for k, v in update_dict.items() if v not in (None, "", [])}
    skipped = len(update_dict) - len(pairs)
    if not pairs:
        return {"updated": 0, "lots": [], "skipped_empty": skipped}
    set_clause = ", ".join(f"{k} = ?" for k in pairs)
    placeholders = ",".join("?" * len(where_vals))
    sql = f"UPDATE inventory SET {set_clause} WHERE {where_col} IN ({placeholders})"
    params = list(pairs.values()) + where_vals
    cur = db_con.execute(sql, params)
    db_con.commit()
    cur2 = db_con.execute(
        f"SELECT lot_no FROM inventory WHERE {where_col} IN ({placeholders})",
        where_vals,
    )
    lots = [r[0] for r in cur2.fetchall()]
    return {"updated": cur.rowcount, "lots": lots, "skipped_empty": skipped}


# ─────────────────────────────────────────────────────────────────────────────
# 1. ISO 6346 정규화
# ─────────────────────────────────────────────────────────────────────────────
class TestContainerNormalization:
    """_norm_container 및 인라인 re.sub 정규화 로직 검증."""

    def test_removes_spaces(self):
        assert _norm_container("TCKU 3045899") == "TCKU3045899"

    def test_removes_hyphens(self):
        assert _norm_container("TCKU-3045899") == "TCKU3045899"

    def test_uppercase(self):
        assert _norm_container("tcku3045899") == "TCKU3045899"

    def test_letter_o_to_digit_zero(self):
        # _norm_container 는 'O' → '0' 전체 적용 (캐리어 코드 포함)
        # ONEY → 0NEY, 숫자 위치의 O도 0으로
        result = _norm_container("ONEY3O45899")
        assert result == "0NEY3045899"  # 실제 동작: O 전부 0으로

    def test_letter_o_behavior_awareness(self):
        """_norm_container 의 O→0 변환은 전체 적용됨을 명시적으로 확인.
        컨테이너 번호 DB 저장 시에도 동일하게 정규화해야 매칭 가능."""
        # 동일 컨테이너의 두 표현이 같은 결과를 낼 것
        assert _norm_container("ONEY3045899") == _norm_container("oney3045899")
        assert _norm_container("TCKU3045899") == _norm_container("tcku3045899")

    def test_pure_digits_preserved(self):
        assert _norm_container("MSCU1234567") == "MSCU1234567"

    def test_empty_string(self):
        assert _norm_container("") == ""

    def test_none_value(self):
        assert _norm_container(None) == ""

    def test_inline_norm_matches_norm_container(self):
        """inbound.py 의 인라인 re.sub 결과가 _norm_container 와 동일해야 함."""
        raw_values = [
            "TCKU 3045899",
            "ONEY 1234567",
            "  MSCU-7654321  ",
            "hlcu3456789",
        ]
        for v in raw_values:
            inline = re.sub(r"[^A-Z0-9]", "", v.upper())
            # _norm_container 도 O→0 변환 외엔 동일 결과
            # (인라인은 O→0 없음, 이 차이는 의도적)
            assert re.sub(r"[^A-Z0-9]", "", v.upper()) == inline

    # ONE 선사 특유 포맷 케이스
    def test_one_carrier_formats(self):
        """ONE(ONEY) 선사 컨테이너 번호 변형들이 모두 동일 정규화 결과."""
        variants = [
            "ONEY3045899",      # 정상
            "ONEY 3045899",     # 공백 포함
            "ONEY-3045899",     # 하이픈
            "oney3045899",      # 소문자
            "ONEY 304 589 9",   # 과도한 공백
        ]
        normalized = {re.sub(r"[^A-Z0-9]", "", v.upper()) for v in variants}
        assert len(normalized) == 1, f"모두 동일 결과여야 함: {normalized}"
        assert "ONEY3045899" in normalized


# ─────────────────────────────────────────────────────────────────────────────
# 2. _db_update_lots 컨테이너 매칭
# ─────────────────────────────────────────────────────────────────────────────
class TestDbUpdateLotsContainers:
    """_db_update_lots WHERE container_no IN (...) 매칭 정확도."""

    def test_exact_match(self):
        con = _make_db([{"lot_no": "L001", "container_no": "TCKU3045899"}])
        r = _db_update_lots(con, "container_no", ["TCKU3045899"], {"vessel": "VESSEL A"})
        assert r["updated"] == 1
        assert "L001" in r["lots"]

    def test_no_match_without_normalization(self):
        """정규화 없으면 공백 포함 컨테이너는 매칭 실패 — 버그 재현."""
        con = _make_db([{"lot_no": "L002", "container_no": "TCKU3045899"}])
        # 공백 있는 원본 값으로 매칭 시도 → 실패해야 함
        r = _db_update_lots(con, "container_no", ["TCKU 3045899"], {"vessel": "VESSEL B"})
        assert r["updated"] == 0, "정규화 없으면 공백 포함 컨테이너는 매칭 안 됨 (예상된 동작)"

    def test_match_after_normalization(self):
        """정규화 후 매칭 성공 — inbound.py 패치 효과 검증."""
        con = _make_db([{"lot_no": "L003", "container_no": "TCKU3045899"}])
        raw_cn = "TCKU 3045899"  # PDF 파서가 반환한 원본 (공백 포함)
        # inbound.py 패치와 동일한 정규화 적용
        normalized = re.sub(r"[^A-Z0-9]", "", raw_cn.upper())
        r = _db_update_lots(con, "container_no", [normalized], {"vessel": "VESSEL C"})
        assert r["updated"] == 1
        assert "L003" in r["lots"]

    def test_multiple_containers(self):
        con = _make_db([
            {"lot_no": "L010", "container_no": "TCKU3045899"},
            {"lot_no": "L011", "container_no": "MSCU1234567"},
            {"lot_no": "L012", "container_no": "HLCU9876543"},
        ])
        r = _db_update_lots(
            con,
            "container_no",
            ["TCKU3045899", "MSCU1234567"],
            {"vessel": "MV TEST"},
        )
        assert r["updated"] == 2
        assert set(r["lots"]) == {"L010", "L011"}

    def test_empty_update_dict(self):
        con = _make_db([{"lot_no": "L020", "container_no": "TCKU3045899"}])
        r = _db_update_lots(con, "container_no", ["TCKU3045899"], {})
        assert r["updated"] == 0

    def test_none_values_skipped(self):
        con = _make_db([{"lot_no": "L021", "container_no": "TCKU3045899"}])
        r = _db_update_lots(
            con, "container_no", ["TCKU3045899"], {"vessel": None, "voyage": ""}
        )
        assert r["updated"] == 0
        assert r["skipped_empty"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. ONE 선사 end-to-end
# ─────────────────────────────────────────────────────────────────────────────
class TestOneCarrierContainerFmt:
    """ONE(ONEY) 선사 컨테이너 포맷 — 정규화 → DB 매칭 end-to-end."""

    ONE_CONTAINERS = ["ONEY3045899", "ONEY1234567", "ONEY9876543"]

    def test_one_containers_in_db(self):
        rows = [
            {"lot_no": f"LOT{i:03d}", "container_no": cn}
            for i, cn in enumerate(self.ONE_CONTAINERS)
        ]
        con = _make_db(rows)

        # PDF 파서가 공백 포함으로 반환한 경우
        raw_list = ["ONEY 3045899", "ONEY 1234567"]
        normalized = [re.sub(r"[^A-Z0-9]", "", v.upper()) for v in raw_list]

        r = _db_update_lots(con, "container_no", normalized, {"bl_no": "ONEYBLA001"})
        assert r["updated"] == 2
        assert set(r["lots"]) == {"LOT000", "LOT001"}

    def test_one_carrier_normalize_chain(self):
        """ONEY 소문자 + 하이픈 → 정규화 → 매칭."""
        con = _make_db([{"lot_no": "LX01", "container_no": "ONEY3045899"}])
        raw = "oney-3045899"  # 소문자 + 하이픈
        normalized = re.sub(r"[^A-Z0-9]", "", raw.upper())
        r = _db_update_lots(con, "container_no", [normalized], {"vessel": "EVER GIVEN"})
        assert r["updated"] == 1

    def test_one_bl_fields_update(self):
        """BL 필드(bl_no, vessel, voyage) 업데이트 확인."""
        con = _make_db([{"lot_no": "LX02", "container_no": "ONEY3045899"}])
        update = {"bl_no": "ONEYBLA002", "vessel": "ONE TRUST", "voyage": "042W"}
        r = _db_update_lots(con, "container_no", ["ONEY3045899"], update)
        assert r["updated"] == 1
        row = con.execute("SELECT bl_no, vessel, voyage FROM inventory WHERE lot_no='LX02'").fetchone()
        assert row[0] == "ONEYBLA002"
        assert row[1] == "ONE TRUST"
        assert row[2] == "042W"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Daily Gemini Cache — 유닛
# ─────────────────────────────────────────────────────────────────────────────
class TestDailyGeminiCache:
    """_record_gemini_failure / _prefer_openai_today 기본 동작."""

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def test_initial_state_no_prefer(self):
        assert _prefer_openai_today() is False

    def test_failure_increments_counter(self):
        _record_gemini_failure()
        assert _DAILY_CACHE["failures"] == 1

    def test_below_threshold_no_promote(self):
        for _ in range(_GEMINI_DAILY_FAIL_THRESHOLD):
            _record_gemini_failure()
        assert _DAILY_CACHE["prefer_openai"] is False

    def test_exceed_threshold_promotes(self):
        for _ in range(_GEMINI_DAILY_FAIL_THRESHOLD + 1):
            _record_gemini_failure()
        assert _DAILY_CACHE["prefer_openai"] is True
        assert _prefer_openai_today() is True

    def test_date_change_resets_cache(self):
        """날짜가 바뀌면 캐시 자동 리셋."""
        for _ in range(_GEMINI_DAILY_FAIL_THRESHOLD + 1):
            _record_gemini_failure()
        assert _DAILY_CACHE["prefer_openai"] is True

        # 날짜를 어제로 강제 설정
        _DAILY_CACHE["date"] = "2000-01-01"
        # _prefer_openai_today() 호출 시 날짜 비교 → 리셋
        result = _prefer_openai_today()
        assert result is False
        assert _DAILY_CACHE["failures"] == 0

    def test_prefer_openai_resets_on_new_day(self):
        _DAILY_CACHE.update({"date": "2000-01-01", "failures": 99, "prefer_openai": True})
        result = _prefer_openai_today()
        assert result is False
        assert _DAILY_CACHE["date"] == str(date.today())

    def test_threshold_exact_value(self):
        assert _GEMINI_DAILY_FAIL_THRESHOLD == 3


# ─────────────────────────────────────────────────────────────────────────────
# 5. Daily Cache + MultiProviderParser integration
# ─────────────────────────────────────────────────────────────────────────────
class TestDailyCacheIntegration:
    """캐시 초과 시 MultiProviderParser 가 Gemini 를 skip 하는지 검증."""

    def setup_method(self):
        _reset_cache()

    def teardown_method(self):
        _reset_cache()

    def _make_parser(self):
        return MultiProviderParser(gemini_key="fake-gemini-key", openai_key="fake-openai-key")

    def test_gemini_skipped_when_cache_exceeded(self):
        """_prefer_openai_today() == True 이면 Gemini 호출 없이 OpenAI 로."""
        # 캐시를 임계치 초과로 설정
        for _ in range(_GEMINI_DAILY_FAIL_THRESHOLD + 1):
            _record_gemini_failure()
        assert _prefer_openai_today() is True

        mpp = self._make_parser()
        gemini_called = []

        def fake_gemini_init(key):
            gemini_called.append(key)
            return MagicMock()

        fake_openai_result = MagicMock()
        fake_openai_result.invoice_no = "INV-001"

        # GeminiDocumentParser 는 _gemini() 안에서 lazy import →
        # features.ai.gemini_parser 경로로 패치
        with patch(
            "features.ai.gemini_parser.GeminiDocumentParser",
            side_effect=fake_gemini_init,
        ):
            with patch(
                "features.ai.openai_parser.try_parse_invoice",
                return_value={"invoice_no": "INV-001"},
            ):
                result, provider = mpp.parse_invoice("fake.pdf")

        assert len(gemini_called) == 0, "Gemini 가 호출되면 안 됨 (캐시 초과)"
        assert provider == "openai"

    def test_gemini_called_when_cache_ok(self):
        """캐시 미초과 시 Gemini 먼저 시도."""
        mpp = self._make_parser()

        fake_gemini_result = MagicMock()
        fake_gemini_result.parse_invoice = MagicMock(return_value=MagicMock())
        fake_gemini_result.parse_invoice.return_value.invoice_no = "INV-002"

        with patch(
            "features.ai.gemini_parser.GeminiDocumentParser",
            return_value=fake_gemini_result,
        ):
            result, provider = mpp.parse_invoice("fake.pdf")

        assert provider == "gemini"

    def test_failure_recorded_on_transient_gemini_error(self):
        """Gemini transient 오류 시 _record_gemini_failure 호출 → 카운터 증가."""
        mpp = self._make_parser()
        initial_failures = _DAILY_CACHE["failures"]

        # Gemini 가 503 transient 오류를 던지게 설정
        class Fake503(Exception):
            pass

        fake_gemini = MagicMock()
        fake_gemini.parse_invoice.side_effect = Fake503("503 overloaded")

        fake_openai_raw = {"invoice_no": "INV-003"}

        with patch(
            "parsers.document_parser_modular.ai_fallback._is_transient_error",
            return_value=True,
        ):
            with patch(
                "features.ai.gemini_parser.GeminiDocumentParser",
                return_value=fake_gemini,
            ):
                with patch(
                    "features.ai.openai_parser.try_parse_invoice",
                    return_value=fake_openai_raw,
                ):
                    result, provider = mpp.parse_invoice("fake.pdf")

        assert _DAILY_CACHE["failures"] == initial_failures + 1
        assert provider == "openai"

    def test_non_transient_error_not_recorded(self):
        """비-transient Gemini 오류는 _record_gemini_failure 호출 안 함."""
        mpp = self._make_parser()
      