"""Groq fallback provider factory."""
from __future__ import annotations

from features.ai.openai_compatible_parser import OpenAICompatibleTextParser


def create_groq_parser(api_key: str, model: str = "llama-3.3-70b-versatile"):
    return OpenAICompatibleTextParser(
        provider_name="groq",
        base_url="https://api.groq.com/openai/v1",
        model=model,
        api_key=api_key,
    )

