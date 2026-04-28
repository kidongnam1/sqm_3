"""test_ollama_manager.py — OllamaStatus helpers + router integration."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features.ai import ollama_manager
from parsers.document_parser_modular import ai_fallback
from features.ai.ai_fallback_policy import AiProviderPolicy


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


# ── ollama_manager unit tests (unchanged) ────────────────────────────────────

def test_cli_missing_status(monkeypatch):
    monkeypatch.setattr(ollama_manager.shutil, "which", lambda name: None)
    monkeypatch.setattr(ollama_manager.Path, "exists", lambda self: False)

    status = ollama_manager.get_ollama_status()

    assert status.installed is False
    assert status.server_running is False
    assert status.model_available is False


def test_health_check_false_on_url_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(ollama_manager.urllib.request, "urlopen", _raise)

    assert ollama_manager.check_ollama_server() is False


def test_list_models_parses_api_tags(monkeypatch):
    monkeypatch.setattr(
        ollama_manager.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse({
            "models": [{"name": "qwen2.5:14b"}, {"name": "llama3.1:8b"}]
        }),
    )

    assert ollama_manager.list_ollama_models() == ["qwen2.5:14b", "llama3.1:8b"]
    assert ollama_manager.has_ollama_model("qwen2.5:14b") is True


# ── router integration ────────────────────────────────────────────────────────

def test_router_skips_ollama_and_does_not_call_paid_without_policy(monkeypatch):
    """Ollama transient fail + paid_openai disabled -> RuntimeError, paid never called."""
    router = ai_fallback.MultiProviderParserV2(openai_key="paid-key")
    called = {"paid": False}

    policies = [
        AiProviderPolicy("ollama", True, False, True, False),
        AiProviderPolicy("paid_openai", False, True, False, True),  # disabled
    ]
    monkeypatch.setattr(
        "features.ai.ai_fallback_policy.build_provider_policy",
        lambda **kw: policies,
    )

    def _spy_build(self, pname):
        if pname == "ollama":
            raise RuntimeError("Ollama server unavailable")
        called["paid"] = True
        return ai_fallback._SimpleRaw({"sap_no": "2200034590"})

    monkeypatch.setattr(ai_fallback.MultiProviderParserV2, "_build_parser", _spy_build)

    try:
        router.parse_invoice("dummy.pdf")
    except RuntimeError:
        pass

    assert called["paid"] is False
