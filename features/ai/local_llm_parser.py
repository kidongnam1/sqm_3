"""Local LLM fallback provider factories for Ollama and LM Studio."""
from __future__ import annotations

from features.ai.openai_compatible_parser import OpenAICompatibleTextParser


def create_ollama_parser(
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5:14b",
    *,
    auto_start: bool = True,
):
    from features.ai.ollama_manager import (
        check_ollama_server,
        find_ollama_cli,
        has_ollama_model,
        start_ollama_server,
    )

    if not find_ollama_cli():
        raise RuntimeError("[Ollama] CLI not installed - skipping local provider")
    if not check_ollama_server(base_url):
        if not auto_start or not start_ollama_server():
            raise RuntimeError("[Ollama] server not running - skipping local provider")
    if not has_ollama_model(model, base_url):
        raise RuntimeError(f"[Ollama] model {model} not found - skipping local provider")
    return OpenAICompatibleTextParser(
        provider_name="ollama",
        base_url=base_url,
        model=model,
    )


def create_lmstudio_parser(
    base_url: str = "http://localhost:1234/v1",
    model: str = "local-model",
):
    return OpenAICompatibleTextParser(
        provider_name="lmstudio",
        base_url=base_url,
        model=model,
    )
