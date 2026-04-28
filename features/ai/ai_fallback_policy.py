"""AI fallback provider policy for SQM document parsing.

Default policy is free/local first. Paid providers are skipped unless the
caller explicitly approves the current parsing attempt.
"""
from __future__ import annotations

import configparser
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER_ORDER = (
    "gemini",
    "groq",
    "openrouter",
    "ollama",
    "lmstudio",
    "paid_openai",
)

PAID_PROVIDERS = {"paid_openai", "openai", "anthropic"}
LOCAL_PROVIDERS = {"ollama", "lmstudio"}
FREE_REMOTE_PROVIDERS = {"gemini", "groq", "openrouter"}


@dataclass(frozen=True)
class AiProviderPolicy:
    name: str
    enabled: bool
    is_paid: bool
    is_local: bool
    requires_user_confirm: bool


@dataclass(frozen=True)
class AiFallbackSettings:
    free_fallback_enabled: bool = True
    local_ai_enabled: bool = True
    paid_ai_enabled: bool = False
    require_paid_confirm: bool = True
    provider_order: tuple[str, ...] = DEFAULT_PROVIDER_ORDER


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _settings_file() -> Path:
    try:
        from config import SETTINGS_FILE
        return Path(SETTINGS_FILE)
    except Exception as exc:
        logger.debug("Suppressed: settings file lookup failed: %s", exc)
    return Path(__file__).resolve().parents[2] / "settings.ini"


def load_ai_fallback_settings() -> AiFallbackSettings:
    """Load AI fallback settings from ENV and settings.ini."""
    values = {
        "free_fallback_enabled": True,
        "local_ai_enabled": True,
        "paid_ai_enabled": False,
        "require_paid_confirm": True,
        "provider_order": ",".join(DEFAULT_PROVIDER_ORDER),
    }

    ini = _settings_file()
    if ini.exists():
        parser = configparser.ConfigParser()
        try:
            parser.read(ini, encoding="utf-8")
            if parser.has_section("AI"):
                for key in values:
                    values[key] = parser.get("AI", key, fallback=str(values[key]))
            if parser.has_section("OpenAI"):
                openai_enabled = parser.getboolean("OpenAI", "enabled", fallback=False)
                if openai_enabled:
                    values["paid_ai_enabled"] = True
        except (configparser.Error, OSError, UnicodeDecodeError) as exc:
            logger.debug("Suppressed: AI settings read failed: %s", exc)

    env_map = {
        "SQM_AI_FREE_FALLBACK": "free_fallback_enabled",
        "SQM_AI_LOCAL_ENABLED": "local_ai_enabled",
        "SQM_AI_PAID_ENABLED": "paid_ai_enabled",
        "SQM_AI_REQUIRE_PAID_CONFIRM": "require_paid_confirm",
        "SQM_AI_PROVIDER_ORDER": "provider_order",
    }
    for env_key, setting_key in env_map.items():
        if env_key in os.environ:
            values[setting_key] = os.environ.get(env_key, values[setting_key])

    order = tuple(
        item.strip().lower()
        for item in str(values["provider_order"]).split(",")
        if item.strip()
    ) or DEFAULT_PROVIDER_ORDER

    return AiFallbackSettings(
        free_fallback_enabled=_as_bool(values["free_fallback_enabled"], True),
        local_ai_enabled=_as_bool(values["local_ai_enabled"], True),
        paid_ai_enabled=_as_bool(values["paid_ai_enabled"], False),
        require_paid_confirm=_as_bool(values["require_paid_confirm"], True),
        provider_order=order,
    )


def build_provider_policy(
    settings: AiFallbackSettings | None = None,
    *,
    user_confirmed_paid: bool = False,
) -> list[AiProviderPolicy]:
    settings = settings or load_ai_fallback_settings()
    policies: list[AiProviderPolicy] = []
    for name in settings.provider_order:
        normalized = "paid_openai" if name == "openai" else name
        is_paid = normalized in PAID_PROVIDERS
        is_local = normalized in LOCAL_PROVIDERS
        if is_paid:
            enabled = can_use_paid_provider(settings, user_confirmed_paid)
        elif is_local:
            enabled = settings.local_ai_enabled
        else:
            enabled = settings.free_fallback_enabled
        policies.append(AiProviderPolicy(
            name=normalized,
            enabled=enabled,
            is_paid=is_paid,
            is_local=is_local,
            requires_user_confirm=is_paid and settings.require_paid_confirm,
        ))
    return policies


def can_use_paid_provider(
    settings: AiFallbackSettings | None = None,
    user_confirmed: bool = False,
) -> bool:
    settings = settings or load_ai_fallback_settings()
    if not settings.paid_ai_enabled:
        return False
    return user_confirmed or not settings.require_paid_confirm

