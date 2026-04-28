"""test_ai_fallback_router.py — MultiProviderParserV2 routing logic tests."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.document_parser_modular import ai_fallback
from features.ai.ai_fallback_policy import AiProviderPolicy


# ── helpers ───────────────────────────────────────────────────────────────────

def _policy(name, enabled, is_paid=False, is_local=False):
    return AiProviderPolicy(
        name=name,
        enabled=enabled,
        is_paid=is_paid,
        is_local=is_local,
        requires_user_confirm=False,
    )


class _RaiseOn:
    """Parser that raises the given exception on any parse_* call."""
    def __init__(self, exc):
        self._exc = exc

    def parse_invoice(self, pdf_path, gemini_hint=""):
        raise self._exc

    def parse_bl(self, pdf_path, gemini_hint=""):
        raise self._exc


class _ReturnOk:
    """Parser that returns a fixed SimpleRaw result."""
    def __init__(self, sap_no="2200034590"):
        self._sap_no = sap_no

    def parse_invoice(self, pdf_path, gemini_hint=""):
        return ai_fallback._SimpleRaw({"sap_no": self._sap_no})

    def parse_bl(self, pdf_path, gemini_hint=""):
        return ai_fallback._SimpleRaw({"bl_no": "TESTBL001"})


# ── tests ─────────────────────────────────────────────────────────────────────

def test_router_moves_from_gemini_503_to_free_provider(monkeypatch):
    """Gemini 503 (transient) -> router falls through to Groq and succeeds."""
    router = ai_fallback.MultiProviderParserV2(
        gemini_key="gemini-key",
        groq_key="groq-key",
    )

    policies = [_policy("gemini", True), _policy("groq", True)]
    monkeypatch.setattr(
        "features.ai.ai_fallback_policy.build_provider_policy",
        lambda **kw: policies,
    )

    parsers = {
        "gemini": _RaiseOn(RuntimeError("503 UNAVAILABLE")),
        "groq": _ReturnOk("2200034590"),
    }
    monkeypatch.setattr(
        ai_fallback.MultiProviderParserV2,
        "_build_parser",
        lambda self, pname: parsers[pname],
    )

    raw, provider = router.parse_invoice("dummy.pdf")

    assert provider == "groq"
    assert raw.sap_no == "2200034590"


def test_router_skips_disabled_paid_provider(monkeypatch):
    """paid_openai disabled in policy -> _build_parser never called, raises RuntimeError."""
    router = ai_fallback.MultiProviderParserV2(openai_key="paid-key")
    called = {"paid": False}

    monkeypatch.setattr(
        "features.ai.ai_fallback_policy.build_provider_policy",
        lambda **kw: [_policy("paid_openai", False, is_paid=True)],
    )

    def _spy_build(self, pname):
        called["paid"] = True
        return _ReturnOk()

    monkeypatch.setattr(ai_fallback.MultiProviderParserV2, "_build_parser", _spy_build)

    with pytest.raises(RuntimeError):
        router.parse_invoice("dummy.pdf")

    assert called["paid"] is False


def test_router_allows_enabled_paid_provider(monkeypatch):
    """paid_openai enabled in policy -> router succeeds and returns provider name."""
    router = ai_fallback.MultiProviderParserV2(openai_key="paid-key")

    monkeypatch.setattr(
        "features.ai.ai_fallback_policy.build_provider_policy",
        lambda **kw: [_policy("paid_openai", True, is_paid=True)],
    )
    monkeypatch.setattr(
        ai_fallback.MultiProviderParserV2,
        "_build_parser",
        lambda self, pname: _ReturnOk("2200034590"),
    )

    raw, provider = router.parse_invoice("dummy.pdf")

    assert provider == "paid_openai"
    assert raw.sap_no == "2200034590"
