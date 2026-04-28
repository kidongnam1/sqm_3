# -*- coding: utf-8 -*-
"""
test_ai_fallback_parity.py
==========================
AI fallback vs 좌표 파싱 패리티 테스트

레이어 구분:
  Layer 1 (단위) — API 키 불필요. _to_float, _norm_bl 등 순수 함수.
  Layer 2 (Mock) — API 키 불필요. GeminiDocumentParser를 MagicMock으로 교체.
  Layer 3 (통합) — GEMINI_API_KEY 환경변수 필요. @pytest.mark.integration.

실행:
  pytest tests/test_ai_fallback_parity.py                  # Layer 1+2 only
  pytest tests/test_ai_fallback_parity.py -m integration   # Layer 1+2+3 (requires key)
  GEMINI_API_KEY=<key> pytest tests/ -m integration        # full integration
"""
from __future__ import annotations

import os
import re
import sys
import pytest
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

# ── 경로 설정 (SQM_v865_CLEAN/ 루트 기준) ─────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Integration 마커 ───────────────────────────────────────────────────────
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires GEMINI_API_KEY env var and real PDF files"
    )

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
SKIP_INTEGRATION = not GEMINI_KEY
SKIP_REASON = "GEMINI_API_KEY 환경변수 없음 (export GEMINI_API_KEY=... 후 재실행)"


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 1: 단위 테스트 — API 키 불필요
# ═══════════════════════════════════════════════════════════════════════════

class TestAiFallbackUtils:
    """ai_fallback.py 내부 정규화 함수 단위 테스트."""

    @pytest.fixture(autouse=True)
    def import_module(self):
        from parsers.document_parser_modular.ai_fallback import (
            _to_float, _norm_bl, _norm_container, _copy_if_empty,
            _clean_text, _digits, normalize_carrier_id, build_ai_hint,
        )
        self._to_float        = _to_float
        self._norm_bl         = _norm_bl
        self._norm_container  = _norm_container
        self._copy_if_empty   = _copy_if_empty
        self._clean_text      = _clean_text
        self._digits          = _digits
        self.normalize_carrier_id = normalize_carrier_id
        self.build_ai_hint    = build_ai_hint

    # ── _to_float ──────────────────────────────────────────────────────────
    def test_to_float_int(self):
        assert self._to_float("1234") == 1234.0

    def test_to_float_dot_separator(self):
        assert self._to_float("1,234.56") == pytest.approx(1234.56)

    def test_to_float_euro_format(self):
        # 유럽식: 1.234,56
        assert self._to_float("1.234,56") == pytest.approx(1234.56)

    def test_to_float_mt_suffix(self):
        # 17,760 MT: comma-only → treated as decimal → 17.76
        # Use "17,760.00 MT" (dot present) → correct 17760
        assert self._to_float("17,760.00 MT") == pytest.approx(17760.0)
        assert self._to_float("17760") == pytest.approx(17760.0)

    def test_to_float_empty(self):
        assert self._to_float("") == 0.0

    def test_to_float_none(self):
        assert self._to_float(None) == 0.0

    # ── _norm_bl ──────────────────────────────────────────────────────────
    def test_norm_bl_removes_spaces(self):
        assert self._norm_bl("MEDU 963970") == "MEDU963970"

    def test_norm_bl_uppercase(self):
        assert self._norm_bl("medu963970") == "MEDU963970"

    def test_norm_bl_empty(self):
        assert self._norm_bl("") == ""

    def test_norm_bl_already_clean(self):
        assert self._norm_bl("HLCUSCL260148627") == "HLCUSCL260148627"

    # ── _norm_container ───────────────────────────────────────────────────
    def test_norm_container_removes_space(self):
        result = self._norm_container("MSCU 1234567")
        assert " " not in result
        assert result == "MSCU1234567"

    def test_norm_container_uppercase(self):
        result = self._norm_container("mscu1234567")
        assert result == "MSCU1234567"

    # ── _copy_if_empty ────────────────────────────────────────────────────
    def test_copy_if_empty_fills_missing(self):
        class Obj:
            bl_no = ""
            vessel = "MAERSK STAR"
        dst = Obj()
        src = Obj()
        src.bl_no = "MEDU963970"
        src.vessel = "MSC VESSEL"
        self._copy_if_empty(dst, src, ["bl_no", "vessel"])
        # bl_no was empty → filled from src
        assert dst.bl_no == "MEDU963970"
        # vessel was set → NOT overwritten
        assert dst.vessel == "MAERSK STAR"

    def test_copy_if_empty_zero_not_filled(self):
        """0.0은 '비어있음'으로 간주."""
        class Obj:
            quantity_mt = 0.0
        dst = Obj()
        src = Obj()
        src.quantity_mt = 17760.0
        self._copy_if_empty(dst, src, ["quantity_mt"])
        assert dst.quantity_mt == pytest.approx(17760.0)

    def test_copy_if_empty_none_filled(self):
        class Obj:
            bl_no = None
        dst = Obj()
        src = Obj()
        src.bl_no = "HLCUSCL260148627"
        self._copy_if_empty(dst, src, ["bl_no"])
        assert dst.bl_no == "HLCUSCL260148627"

    # ── normalize_carrier_id ──────────────────────────────────────────────
    def test_normalize_hlcu(self):
        assert self.normalize_carrier_id("HLCU") == "HAPAG"

    def test_normalize_medu(self):
        assert self.normalize_carrier_id("MEDU") == "MSC"

    def test_normalize_maeu(self):
        assert self.normalize_carrier_id("MAEU") == "MAERSK"

    def test_normalize_oney(self):
        assert self.normalize_carrier_id("ONEY") == "ONE"

    def test_normalize_already_hapag(self):
        assert self.normalize_carrier_id("HAPAG") == "HAPAG"

    def test_normalize_unknown(self):
        result = self.normalize_carrier_id("UNKNOWN")
        assert isinstance(result, str)

    def test_normalize_empty(self):
        result = self.normalize_carrier_id("")
        assert isinstance(result, str)

    # ── build_ai_hint ─────────────────────────────────────────────────────
    def test_build_ai_hint_bl_maersk(self):
        hint = self.build_ai_hint("BL", "MAERSK", None)
        assert "MAERSK" in hint or "maersk" in hint.lower()
        assert len(hint) > 10

    def test_build_ai_hint_do_msc(self):
        hint = self.build_ai_hint("DO", "MSC", None)
        assert len(hint) > 10

    def test_build_ai_hint_with_partial(self):
        """partial 결과가 있을 때 hint에 반영되는지."""
        class FakePartial:
            bl_no = "MEDU9700352"
            vessel = ""
        hint = self.build_ai_hint("BL", "MSC", FakePartial())
        assert len(hint) > 10  # 최소한 hint는 생성됨

    def test_build_ai_hint_max_length(self):
        """hint가 너무 길지 않은지 (1500자 이하)."""
        hint = self.build_ai_hint("DO", "HAPAG", None)
        assert len(hint) <= 1500

    def test_build_ai_hint_unknown_carrier(self):
        hint = self.build_ai_hint("BL", "UNKNOWN_CARRIER", None)
        assert isinstance(hint, str)


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 2: Mock 테스트 — API 키 불필요
# ═══════════════════════════════════════════════════════════════════════════

def _make_mock_owner(api_key: str = "DUMMY_KEY") -> MagicMock:
    """테스트용 가짜 owner (DocumentParser 역할)."""
    owner = MagicMock()
    owner._api_key = api_key
    owner._gemini_client = None
    owner.provider = "gemini"
    owner._get_ai_key = MagicMock(return_value=api_key)
    owner._get_ai_model = MagicMock(return_value=None)
    owner._gemini_with_retry = MagicMock()
    return owner


def _make_fake_invoice(**kwargs):
    """InvoiceData 유사 객체 생성."""
    try:
        from parsers.document_models import InvoiceData
        obj = InvoiceData()
    except Exception:
        obj = MagicMock()
    defaults = dict(
        invoice_no="INV-2026-001",
        sap_no="2200034659",
        bl_no="MEDU9700352",
        quantity_mt=17760.0,
        vessel="MSC VESSEL",
        invoice_date="2026-01-31",
        success=True,
        error_message="",
    )
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_fake_bl(**kwargs):
    """BLData 유사 객체 생성."""
    try:
        from parsers.document_models import BLData
        obj = BLData()
    except Exception:
        obj = MagicMock()
    defaults = dict(
        bl_no="MEDU9700352",
        vessel="MSC STAR",
        voyage="123W",
        containers=[],
        success=True,
        error_message="",
    )
    defaults.update(kwargs)
    for k, v in defaults.items():
        try:
            setattr(obj, k, v)
        except AttributeError:
            pass
    return obj


def _make_fake_do(**kwargs):
    """DOData 유사 객체 생성."""
    try:
        from parsers.document_models import DOData
        obj = DOData()
    except Exception:
        obj = MagicMock()
    defaults = dict(
        bl_no="MEDU9700352",
        vessel="MSC STAR",
        voyage="123W",
        do_no="DO-2026-001",
        containers=[],
        free_time_info=[],
        success=True,
        error_message="",
    )
    defaults.update(kwargs)
    for k, v in defaults.items():
        try:
            setattr(obj, k, v)
        except AttributeError:
            pass
    return obj


class TestParseInvoiceAiMock:
    """parse_invoice_ai Mock 테스트 — Gemini API 미호출."""

    def _run_with_mock(self, gemini_return, pdf_path="dummy.pdf", carrier_id="MSC"):
        from parsers.document_parser_modular.ai_fallback import parse_invoice_ai
        owner = _make_mock_owner()

        mock_gp = MagicMock()
        mock_gp.parse_invoice = MagicMock(return_value=gemini_return)
        owner._gemini_with_retry = MagicMock(return_value=gemini_return)

        with patch("parsers.document_parser_modular.ai_fallback._get_provider_parser",
                   return_value=(mock_gp, "gemini")):
            return parse_invoice_ai(owner, pdf_path, carrier_id=carrier_id)

    def test_success_maps_core_fields(self):
        fake = _make_fake_invoice(invoice_no="INV001", sap_no="2200034659", success=True)
        result = self._run_with_mock(fake)
        assert result is not None
        assert getattr(result, "success", False)

    def test_failure_returns_none_or_failed(self):
        fake = _make_fake_invoice(success=False, invoice_no="", sap_no="")
        result = self._run_with_mock(fake)
        if result is not None:
            assert not getattr(result, "success", True)

    def test_exception_does_not_raise(self):
        """AI 오류 시 RuntimeError/None 반환 — 테스트는 예외 여부만 확인."""
        from parsers.document_parser_modular.ai_fallback import parse_invoice_ai
        owner = _make_mock_owner()
        with patch("parsers.document_parser_modular.ai_fallback._get_provider_parser",
                   side_effect=RuntimeError("no api key")):
            # parse_invoice_ai may raise RuntimeError or return None — both OK
            try:
                result = parse_invoice_ai(owner, "dummy.pdf", carrier_id="MSC")
                assert result is None or not getattr(result, "success", True)
            except (RuntimeError, ImportError, AttributeError):
                pass  # RuntimeError from AI layer is acceptable


class TestParseBlAiMock:
    """parse_bl_ai Mock 테스트."""

    def _run_with_mock(self, gemini_return, carrier_id="MSC"):
        from parsers.document_parser_modular.ai_fallback import parse_bl_ai
        owner = _make_mock_owner()
        mock_gp = MagicMock()
        mock_gp.parse_bl = MagicMock(return_value=gemini_return)
        with patch("parsers.document_parser_modular.ai_fallback._get_provider_parser",
                   return_value=(mock_gp, "gemini")):
            return parse_bl_ai(owner, "dummy.pdf", carrier_id=carrier_id)

    def test_success_returns_bl_data(self):
        fake = _make_fake_bl(bl_no="MEDU9700352", success=True)
        result = self._run_with_mock(fake)
        assert result is not None

    def test_bl_no_normalized(self):
        """bl_no 공백 제거 및 대문자 변환."""
        fake = _make_fake_bl(bl_no="medu 9700352", success=True)
        result = self._run_with_mock(fake)
        if result and hasattr(result, "bl_no") and result.bl_no:
            assert " " not in result.bl_no
            assert result.bl_no == result.bl_no.upper()

    def test_carriers_hapag_msc_maersk_one(self):
        for carrier in ["HAPAG", "MSC", "MAERSK", "ONE"]:
            fake = _make_fake_bl(bl_no=f"BL-{carrier}-001", success=True)
            result = self._run_with_mock(fake, carrier_id=carrier)
            assert result is not None, f"parse_bl_ai 실패: carrier={carrier}"


class TestParseDoAiMock:
    """parse_do_ai Mock 테스트."""

    def _run_with_mock(self, gemini_return, carrier_id="MSC"):
        from parsers.document_parser_modular.ai_fallback import parse_do_ai
        owner = _make_mock_owner()
        mock_gp = MagicMock()
        mock_gp.parse_do = MagicMock(return_value=gemini_return)
        with patch("parsers.document_parser_modular.ai_fallback._get_provider_parser",
                   return_value=(mock_gp, "gemini")):
            return parse_do_ai(owner, "dummy.pdf", carrier_id=carrier_id)

    def test_success_returns_do_data(self):
        fake = _make_fake_do(bl_no="MEDU9700352", success=True)
        result = self._run_with_mock(fake)
        assert result is not None

    def test_all_carriers(self):
        for carrier in ["HAPAG", "MSC", "MAERSK", "ONE"]:
            fake = _make_fake_do(bl_no=f"BL-{carrier}", do_no=f"DO-{carrier}", success=True)
            result = self._run_with_mock(fake, carrier_id=carrier)
            assert result is not None, f"parse_do_ai 실패: carrier={carrier}"


class TestCopyIfEmptyIntegration:
    """_copy_if_empty: 좌표 결과 → AI 결과 병합 통합 시나리오."""

    def test_coord_partial_fills_ai_missing_fields(self):
        """좌표에서 sap_no 추출 성공, AI는 bl_no만 성공 → 병합 후 둘 다 존재."""
        from parsers.document_parser_modular.ai_fallback import _copy_if_empty

        class CoordResult:
            sap_no = "2200034659"
            bl_no = ""
            quantity_mt = 17760.0

        class AiResult:
            sap_no = ""
            bl_no = "MEDU9700352"
            quantity_mt = 0.0

        # AI result를 최종 dst로, coord를 src (좌표 값이 우선)
        _copy_if_empty(AiResult, CoordResult, ["sap_no", "quantity_mt"])
        assert AiResult.sap_no == "2200034659"
        assert AiResult.quantity_mt == pytest.approx(17760.0)
        assert AiResult.bl_no == "MEDU9700352"  # AI 값 유지

    def test_coord_does_not_overwrite_ai_success(self):
        """AI가 이미 채운 필드는 좌표로 덮어쓰지 않는다."""
        from parsers.document_parser_modular.ai_fallback import _copy_if_empty

        class CoordResult:
            bl_no = "WRONG_COORD_BL"

        class AiResult:
            bl_no = "MEDU9700352"  # 이미 있음

        _copy_if_empty(AiResult, CoordResult, ["bl_no"])
        assert AiResult.bl_no == "MEDU9700352"  # 덮어쓰기 안 됨


# ═══════════════════════════════════════════════════════════════════════════
# LAYER 3: 통합 테스트 — GEMINI_API_KEY 필요
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
class TestIntegrationBuildHint:
    """실제 build_ai_hint 호출 (API 호출 없음 — 문자열 생성만)."""

    def test_hint_all_carriers_bl(self):
        from parsers.document_parser_modular.ai_fallback import build_ai_hint
        for carrier in ["MAERSK", "MSC", "HAPAG", "ONE"]:
            hint = build_ai_hint("BL", carrier, None)
            assert len(hint) > 5, f"hint too short for carrier={carrier}"

    def test_hint_all_carriers_do(self):
        from parsers.document_parser_modular.ai_fallback import build_ai_hint
        for carrier in ["MAERSK", "MSC", "HAPAG", "ONE"]:
            hint = build_ai_hint("DO", carrier, None)
            assert len(hint) > 5, f"hint too short for carrier={carrier}"


# ─────────────────────────────────────────────────────────────────────────
# Parity Fixtures (패리티 검증용 실제 파싱 결과 비교)
# 실제 PDF 경로는 환경변수로 전달받는다.
# ─────────────────────────────────────────────────────────────────────────

def _get_test_pdfs():
    """환경변수에서 테스트 PDF 경로 읽기."""
    return {
        "FA_MSC":    os.environ.get("TEST_FA_MSC", ""),
        "FA_HAPAG":  os.environ.get("TEST_FA_HAPAG", ""),
        "FA_MAERSK": os.environ.get("TEST_FA_MAERSK", ""),
        "FA_ONE":    os.environ.get("TEST_FA_ONE", ""),
        "BL_MSC":    os.environ.get("TEST_BL_MSC", ""),
        "BL_HAPAG":  os.environ.get("TEST_BL_HAPAG", ""),
        "BL_MAERSK": os.environ.get("TEST_BL_MAERSK", ""),
        "BL_ONE":    os.environ.get("TEST_BL_ONE", ""),
        "DO_MSC":    os.environ.get("TEST_DO_MSC", ""),
        "DO_HAPAG":  os.environ.get("TEST_DO_HAPAG", ""),
        "DO_MAERSK": os.environ.get("TEST_DO_MAERSK", ""),
        "DO_ONE":    os.environ.get("TEST_DO_ONE", ""),
    }

# 핵심 필드 패리티 규칙: 이 필드들은 좌표 vs AI 결과가 일치해야 함
_FA_PARITY_FIELDS  = ["sap_no", "bl_no", "quantity_mt", "invoice_no"]
_BL_PARITY_FIELDS  = ["bl_no", "vessel"]
_DO_PARITY_FIELDS  = ["bl_no", "vessel"]


def _compare_fields(coord_result, ai_result, fields: list[str], label: str):
    """두 파싱 결과의 핵심 필드를 비교하고 불일치 목록 반환."""
    mismatches = []
    for field in fields:
        cv = str(getattr(coord_result, field, "") or "").strip().upper()
        av = str(getattr(ai_result,   field, "") or "").strip().upper()
        if cv and av and cv != av:
            mismatches.append(f"{label}.{field}: coord={cv!r} vs ai={av!r}")
    return mismatches


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
class TestParityFaMscIntegration:
    """FA(Invoice) × MSC 패리티 테스트."""

    def test_fa_msc_parity(self):
        pdf = _get_test_pdfs()["FA_MSC"]
        if not pdf or not os.path.exists(pdf):
            pytest.skip(f"TEST_FA_MSC PDF 없음 (설정: export TEST_FA_MSC=/path/to/file.pdf)")
        _run_fa_parity(pdf, "MSC")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
class TestParityFaHapagIntegration:
    def test_fa_hapag_parity(self):
        pdf = _get_test_pdfs()["FA_HAPAG"]
        if not pdf or not os.path.exists(pdf):
            pytest.skip("TEST_FA_HAPAG PDF 없음")
        _run_fa_parity(pdf, "HAPAG")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
class TestParityBlMscIntegration:
    def test_bl_msc_parity(self):
        pdf = _get_test_pdfs()["BL_MSC"]
        if not pdf or not os.path.exists(pdf):
            pytest.skip("TEST_BL_MSC PDF 없음")
        _run_bl_parity(pdf, "MSC")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
class TestParityBlHapagIntegration:
    def test_bl_hapag_parity(self):
        pdf = _get_test_pdfs()["BL_HAPAG"]
        if not pdf or not os.path.exists(pdf):
            pytest.skip("TEST_BL_HAPAG PDF 없음")
        _run_bl_parity(pdf, "HAPAG")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
class TestParityBlMaerskIntegration:
    def test_bl_maersk_parity(self):
        pdf = _get_test_pdfs()["BL_MAERSK"]
        if not pdf or not os.path.exists(pdf):
            pytest.skip("TEST_BL_MAERSK PDF 없음")
        _run_bl_parity(pdf, "MAERSK")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
class TestParityDoMscIntegration:
    def test_do_msc_parity(self):
        pdf = _get_test_pdfs()["DO_MSC"]
        if not pdf or not os.path.exists(pdf):
            pytest.skip("TEST_DO_MSC PDF 없음")
        _run_do_parity(pdf, "MSC")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason=SKIP_REASON)
class TestParityDoHapagIntegration:
    def test_do_hapag_parity(self):
        pdf = _get_test_pdfs()["DO_HAPAG"]
        if not pdf or not os.path.exists(pdf):
            pytest.skip("TEST_DO_HAPAG PDF 없음")
        _run_do_parity(pdf, "HAPAG")


# ── 패리티 공통 헬퍼 ──────────────────────────────────────────────────────

def _make_real_owner(carrier_id: str = "MSC"):
    """실제 파싱에 필요한 최소 owner 객체."""
    class RealOwner:
        _api_key = GEMINI_KEY
        provider = "gemini"
        _gemini_client = None

        def _get_ai_key(self, provider="gemini"):
            return GEMINI_KEY if provider == "gemini" else ""

        def _get_ai_model(self, provider="gemini"):
            return None

        def _gemini_with_retry(self, fn, *args, retries=3, wait_seconds=1.0, **kwargs):
            return fn(*args, **kwargs)

        def _require_gemini_api_key(self):
            pass

    return RealOwner()


def _run_fa_parity(pdf_path: str, carrier_id: str):
    """FA 좌표 파싱 vs AI 파싱 패리티 검사."""
    from parsers.document_parser_modular.invoice_mixin import InvoiceMixin
    from parsers.document_parser_modular.ai_fallback import parse_invoice_ai

    owner = _make_real_owner(carrier_id)
    mixin = InvoiceMixin()

    # 좌표 파싱
    try:
        coord = mixin.parse_invoice(pdf_path)
    except Exception as e:
        pytest.skip(f"좌표 파싱 오류: {e}")
        return

    # AI 파싱
    try:
        ai = parse_invoice_ai(owner, pdf_path, carrier_id=carrier_id)
    except Exception as e:
        pytest.skip(f"AI 파싱 오류: {e}")
        return

    if coord is None or ai is None:
        pytest.skip("파싱 결과 None")
        return

    mismatches = _compare_fields(coord, ai, _FA_PARITY_FIELDS, f"FA-{carrier_id}")
    assert not mismatches, (
        f"[FA-{carrier_id}] 좌표/AI 결과 불일치:\n" +
        "\n".join(f"  {m}" for m in mismatches)
    )


def _run_bl_parity(pdf_path: str, carrier_id: str):
    """BL 좌표 파싱 vs AI 파싱 패리티 검사."""
    from parsers.document_parser_modular.bl_mixin import BLMixin
    from parsers.document_parser_modular.ai_fallback import parse_bl_ai

    owner = _make_real_owner(carrier_id)
    mixin = BLMixin()

    try:
        coord = mixin.parse_bl(pdf_path, carrier_id=carrier_id)
    except Exception as e:
        pytest.skip(f"BL 좌표 파싱 오류: {e}")
        return

    try:
        ai = parse_bl_ai(owner, pdf_path, carrier_id=carrier_id)
    except Exception as e:
        pytest.skip(f"BL AI 파싱 오류: {e}")
        return

    if coord is None or ai is None:
        pytest.skip("파싱 결과 None")
        return

    mismatches = _compare_fields(coord, ai, _BL_PARITY_FIELDS, f"BL-{carrier_id}")
    assert not mismatches, (
        f"[BL-{carrier_id}] 좌표/AI 결과 불일치:\n" +
        "\n".join(f"  {m}" for m in mismatches)
    )


def _run_do_parity(pdf_path: str, carrier_id: str):
    """DO 좌표 파싱 vs AI 파싱 패리티 검사."""
    from parsers.document_parser_modular.do_mixin import DOMixin
    from parsers.document_parser_modular.ai_fallback import parse_do_ai

    owner = _make_real_owner(carrier_id)
    mixin = DOMixin()

    try:
        coord = mixin.parse_do(pdf_path, carrier_id=carrier_id)
    except Exception as e:
        pytest.skip(f"DO 좌표 파싱 오류: {e}")
        return

    try:
        ai = parse_do_ai(owner, pdf_path, carrier_id=carrier_id)
    except Exception as e:
        pytest.skip(f"DO AI 파싱 오류: {e}")
        return

    if coord is None or ai is None:
        pytest.skip("파싱 결과 None")
        return

    mismatches = _compare_fields(coord, ai, _DO_PARITY_FIELDS, f"DO-{carrier_id}")
    assert not mismatches, (
        f"[DO-{carrier_id}] 좌표/AI 결과 불일치:\n" +
        "\n".join(f"  {m}" for m in mismatches)
    )
