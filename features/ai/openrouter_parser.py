"""OpenRouter fallback provider factory."""
from __future__ import annotations

from features.ai.openai_compatible_parser import OpenAICompatibleTextParser


def create_openrouter_parser(
    api_key: str,
    model: str = "meta-llama/llama-3.1-8b-instruct:free",
):
    return OpenAICompatibleTextParser(
        provider_name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        model=model,
        api_key=api_key,
    )

