import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features.ai.ai_fallback_policy import (
    AiFallbackSettings,
    build_provider_policy,
    can_use_paid_provider,
)


def test_default_policy_disables_paid_provider():
    settings = AiFallbackSettings(
        free_fallback_enabled=True,
        local_ai_enabled=True,
        paid_ai_enabled=False,
        require_paid_confirm=True,
        provider_order=("gemini", "paid_openai"),
    )

    policies = build_provider_policy(settings)
    paid = [item for item in policies if item.name == "paid_openai"][0]

    assert paid.enabled is False
    assert paid.requires_user_confirm is True
    assert can_use_paid_provider(settings, user_confirmed=True) is False


def test_paid_provider_requires_confirmation_when_enabled():
    settings = AiFallbackSettings(
        paid_ai_enabled=True,
        require_paid_confirm=True,
        provider_order=("paid_openai",),
    )

    assert can_use_paid_provider(settings, user_confirmed=False) is False
    assert can_use_paid_provider(settings, user_confirmed=True) is True


def test_free_and_local_providers_are_enabled_by_default():
    settings = AiFallbackSettings(provider_order=("gemini", "groq", "ollama"))

    enabled = [item.name for item in build_provider_policy(settings) if item.enabled]

    assert enabled == ["gemini", "groq", "ollama"]
