# -*- coding: utf-8 -*-
"""
AI fallback parser normalization for inbound documents.

This module is intentionally a thin adapter:
coordinate parsers remain the primary path, while Gemini/OpenAI results are
normalized back into the same document_models classes used by coordinate parsing.
"""
from __future__ import annotations

import json
import logging
import os
import re
import inspect
from datetime import datetime
from typing import Any, Iterable, Optional

from ..document_models import (
    BLData,
    ContainerInfo,
    DOData,
    FreeTimeInfo,
    InvoiceData,
    LOTInfo,
    PackingListData,
    PackingListRow,
    ShipmentDocuments,
)

logger = logging.getLogger(__name__)


SUPPORTED_AI_CARRIERS = {"MAERSK", "MSC", "HAPAG", "ONE"}

_CARRIER_HINTS = {
    "MAERSK": {
        "BL": (
            "MAERSK BL/Waybill. B/L No may equal Booking No. "
            "Use the value near 'B/L No.'; do not use container numbers."
        ),
        "DO": (
            "MAERSK D/O. Extract D/O No, B/L No, vessel, voyage, arrival date, "
            "container list, Free Time date, and return yard per container."
        ),
    },
    "MSC": {
        "BL": (
            "MSC Sea Waybill. BL No usually starts with MEDU or MSCU. "
            "Do not confuse rider-page container numbers with BL No."
        ),
        "DO": (
            "MSC D/O. BL No starts with MEDU/MSCU. Arrival date can be in the "
            "For Local Use section. Extract return deadline/free time per container."
        ),
    },
    "HAPAG": {
        "BL": (
            "HAPAG-Lloyd Sea Waybill. BL/SWB No usually starts with HLCU. "
            "Use SWB-No./Sea Waybill number, not booking or container numbers."
        ),
        "DO": (
            "HAPAG-Lloyd D/O. Extract HLCU BL No, D/O No, vessel/voyage, "
            "arrival date, containers, free time date, and return yard."
        ),
    },
    "ONE": {
        "BL": (
            "ONE Sea Waybill. BL No usually starts with ONEY. "
            "Use SEA WAYBILL NO. and keep vessel/voyage separate."
        ),
        "DO": (
            "ONE e-D/O. BL No usually starts with ONEY. Extract split-letter "
            "tokens carefully, plus demurrage/free-time dates per container."
        ),
    },
}


def normalize_carrier_id(carrier_id: str = "") -> str:
    c = str(carrier_id or "").upper().strip().replace(" ", "_").replace("-", "_")
    aliases = {
        "MAEU": "MAERSK",
        "MERSK": "MAERSK",
        "MEDU": "MSC",
        "MSCU": "MSC",
        "HLCU": "HAPAG",
        "HAPAG_LLOYD": "HAPAG",
        "ONEU": "ONE",
        "ONEY": "ONE",
    }
    return aliases.get(c, c)


def build_ai_hint(doc_type: str, carrier_id: str = "", partial: Any = None) -> str:
    """Build a short, sanitized hint for Gemini/OpenAI parsers."""
    doc_type = str(doc_type or "").upper()
    carrier = normalize_carrier_id(carrier_id)
    parts = [
        "AI fallback mode: coordinate parsing already ran first.",
        "Return values must match SQM Inventory internal fields.",
        "Do not invent missing values; leave unknown values blank.",
        "Normalize dates to YYYY-MM-DD and weights to kg.",
    ]
    if carrier:
        parts.append(f"Selected carrier: {carrier}.")
        parts.append(_CARRIER_HINTS.get(carrier, {}).get(doc_type, ""))
    p = _partial_summary(partial)
    if p:
        parts.append("Coordinate partial result follows. Trust valid values unless the PDF clearly contradicts them.")
        parts.append(p)
        parts.append("Fill missing fields first; if you correct a partial value, make the corrected value explicit in JSON.")
    hint = "\n".join(x for x in parts if x)
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", hint)[:1200]


def _partial_summary(obj: Any) -> str:
    if not obj:
        return ""
    fields = (
        "sap_no", "invoice_no", "folio", "bl_no", "do_no", "vessel", "voyage",
        "voyage_no", "port_of_loading", "port_of_discharge", "quantity_mt",
        "net_weight_kg", "gross_weight_kg", "total_net_weight_kg",
        "total_gross_weight_kg", "total_lots", "total_containers",
    )
    data = {}
    for f in fields:
        if hasattr(obj, f):
            v = getattr(obj, f)
            if v not in (None, "", 0, 0.0, []):
                data[f] = str(v)
    if hasattr(obj, "lots"):
        lots = list(getattr(obj, "lots") or [])
        if lots:
            data["lots_count"] = str(len(lots))
            data["first_lot"] = str(getattr(lots[0], "lot_no", lots[0]))
    if hasattr(obj, "containers"):
        conts = list(getattr(obj, "containers") or [])
        if conts:
            data["containers_count"] = str(len(conts))
            data["first_container"] = str(getattr(conts[0], "container_no", conts[0]))
    if not data:
        return ""
    return json.dumps(data, ensure_ascii=False)


def _clean_text(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("\xa0", " ")).strip(" ,;:")


def _digits(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s:
        return 0.0
    try:
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            parts = s.split(",")
            if len(parts) == 2 and len(parts[1]) <= 3:
                s = s.replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "." in s:
            parts = s.split(".")
            if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
                s = s.replace(".", "")
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _to_kg(v: Any) -> float:
    n = _to_float(v)
    if 0 < n < 100:
        return n * 1000.0
    return n


def _to_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (ValueError, TypeError):
        d = _digits(v)
        return int(d) if d else default


def _norm_bl(v: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(v or "").upper())


def _norm_container(v: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(v or "").upper().replace("O", "0"))

def _parse_date(v) -> str:
    """날짜 문자열을 YYYY-MM-DD로 정규화. 실패 시 원본 반환."""
    if not v:
        return ""
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y",
                "%d-%m-%Y", "%Y%m%d", "%d %b %Y", "%d %B %Y"):
        try:
            return __import__('datetime').datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s



def _unique(values: Iterable[Any]) -> list[str]:
    out = []
    seen = set()
    for raw in values or []:
        v = _clean_text(raw)
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _copy_if_empty(dst: Any, src: Any, fields: Iterable[str]) -> None:
    if not dst or not src:
        return
    for f in fields:
        if not hasattr(dst, f) or not hasattr(src, f):
            continue
        cur = getattr(dst, f)
        new = getattr(src, f)
        if cur in (None, "", 0, 0.0, []):
                setattr(dst, f, new)


def _invoke_parser_method(parser: Any, method_name: str, pdf_path: str, gemini_hint: str):
    """Call provider parser while respecting older method signatures."""
    method = getattr(parser, method_name)
    try:
        sig = inspect.signature(method)
        params = list(sig.parameters.values())
        accepts_args = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
        accepts_hint = accepts_args or len(params) >= 2 or "gemini_hint" in sig.parameters
    except (TypeError, ValueError):
        accepts_hint = True
    if accepts_hint:
        return method(pdf_path, gemini_hint)
    return method(pdf_path)


# ── Multi-provider helper utilities ───────────────────────────────────────────

def _is_transient_error(exc: Exception) -> bool:
    """503 / 429 / quota errors → True (fallback to next provider)."""
    msg = str(exc).lower()
    for kw in ("503", "429", "quota", "overloaded", "rate limit",
               "resource_exhausted", "too many requests", "unavailable"):
        if kw in msg:
            return True
    return False



# ── Daily provider cache ──────────────────────────────────────────────────────
# Gemini 가 하루 N회 초과 실패하면 당일은 OpenAI를 1순위로 자동 승격.
# 메모리 캐시(프로세스 재시작 시 리셋)이므로 DB 의존 없음.

_DAILY_CACHE: dict = {"date": "", "failures": 0, "prefer_openai": False}
_GEMINI_DAILY_FAIL_THRESHOLD = 3   # 이 횟수 초과 시 당일 OpenAI 우선


def _record_gemini_failure() -> None:
    """Gemini transient 오류 발생 시 호출. 임계치 초과 시 prefer_openai=True."""
    from datetime import date as _date
    today = str(_date.today())
    if _DAILY_CACHE["date"] != today:
        _DAILY_CACHE.update({"date": today, "failures": 0, "prefer_openai": False})
    _DAILY_CACHE["failures"] += 1
    if _DAILY_CACHE["failures"] > _GEMINI_DAILY_FAIL_THRESHOLD:
        if not _DAILY_CACHE["prefer_openai"]:
            logger.warning(
                "[DailyCache] Gemini 당일 %d회 실패 → 오늘은 다음 provider 1순위로 전환",
                _DAILY_CACHE["failures"],
            )
        _DAILY_CACHE["prefer_openai"] = True


def _prefer_openai_today() -> bool:
    """당일 임계치 초과 여부. 날짜가 바뀌면 자동 리셋."""
    from datetime import date as _date
    if _DAILY_CACHE["date"] != str(_date.today()):
        _DAILY_CACHE.update({"date": str(_date.today()), "failures": 0, "prefer_openai": False})
    return _DAILY_CACHE["prefer_openai"]


def _load_ext_api_key(provider: str) -> str:
    """Load API key for any provider: ENV -> core.config -> settings.ini.
    Supported: openai, paid_openai, groq, openrouter.
    ENV: OPENAI_API_KEY | GROQ_API_KEY | OPENROUTER_API_KEY
    INI: [OpenAI] | [Groq] | [OpenRouter]  key=api_key
    """
    _ENV_MAP = {
        "openai": "OPENAI_API_KEY", "paid_openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY",
    }
    _CONFIG_ATTR = {
        "openai": "OPENAI_API_KEY", "paid_openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY",
    }
    _INI_SECTION = {
        "openai": "OpenAI", "paid_openai": "OpenAI",
        "groq": "Groq", "openrouter": "OpenRouter",
    }
    provider = provider.lower()
    if provider not in _ENV_MAP:
        return ""
    env_val = os.environ.get(_ENV_MAP[provider], "")
    if env_val:
        return env_val
    try:
        import core.config as cc
        return getattr(cc, _CONFIG_ATTR[provider], "") or ""
    except Exception:
        pass
    try:
        import configparser, pathlib
        ini = pathlib.Path(__file__).resolve().parents[3] / "settings.ini"
        if ini.exists():
            cp = configparser.ConfigParser()
            cp.read(ini, encoding="utf-8")
            section = _INI_SECTION[provider]
            if cp.has_section(section):
                return cp.get(section, "api_key", fallback="")
    except Exception:
        pass
    return ""


class _SimpleRaw:
    """Wrap a dict as attribute-accessible object (duck-types GeminiDocumentParser result)."""
    def __init__(self, d: dict):
        for k, v in (d or {}).items():
            if k == "ai_compare_report":
                pass
            elif isinstance(v, dict):
                v = _SimpleRaw(v)
            elif isinstance(v, list):
                v = [_SimpleRaw(x) if isinstance(x, dict) else x for x in v]
            setattr(self, k, v)
    def __getattr__(self, item):
        return None


_COMPARE_FIELDS = {
    "parse_invoice": (
        "sap_no", "invoice_no", "bl_no", "product_code", "product",
        "quantity_mt", "net_weight_kg", "gross_weight_kg", "vessel",
        "origin", "destination", "lot_numbers",
    ),
    "parse_bl": (
        "bl_no", "booking_no", "sap_no", "vessel", "voyage",
        "port_of_loading", "port_of_discharge", "total_containers",
        "total_weight_kg", "shipped_on_board_date", "containers",
    ),
    "parse_do": (
        "do_no", "bl_no", "vessel", "voyage", "port_of_loading",
        "port_of_discharge", "total_weight_kg", "arrival_date",
        "issue_date", "containers",
    ),
    "parse_packing_list": (
        "folio", "product", "packing", "code", "vessel", "customer",
        "destination", "total_net_weight_kg", "total_gross_weight_kg",
        "lots",
    ),
}


def _plain_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _plain_value(v) for k, v in value.items()}
    data = {}
    for key, val in vars(value).items() if hasattr(value, "__dict__") else []:
        if key.startswith("_") or key in {"raw_response", "error_message"}:
            continue
        data[key] = _plain_value(val)
    return data if data else str(value)


def _compare_token(value: Any) -> str:
    plain = _plain_value(value)
    if plain in (None, "", [], {}, 0, 0.0):
        return ""
    if isinstance(plain, (list, dict)):
        return json.dumps(plain, ensure_ascii=False, sort_keys=True)
    return re.sub(r"\s+", " ", str(plain)).strip().upper()


def _has_value(value: Any) -> bool:
    return _compare_token(value) != ""


def _merge_compare_results(method_name: str, free_raw: Any, paid_raw: Any,
                           free_provider: str, paid_provider: str) -> Any:
    fields = _COMPARE_FIELDS.get(method_name, ())
    merged = {}
    agreed = []
    conflicts = []
    free_only = []
    paid_only = []

    for field in fields:
        free_value = getattr(free_raw, field, None)
        paid_value = getattr(paid_raw, field, None)
        free_token = _compare_token(free_value)
        paid_token = _compare_token(paid_value)
        if free_token and paid_token and free_token == paid_token:
            merged[field] = _plain_value(free_value)
            agreed.append(field)
        elif free_token and paid_token:
            # Keep free/provider-order result, but mark the field for review.
            merged[field] = _plain_value(free_value)
            conflicts.append({
                "field": field,
                "free": _plain_value(free_value),
                "paid": _plain_value(paid_value),
            })
        elif free_token:
            merged[field] = _plain_value(free_value)
            free_only.append(field)
        elif paid_token:
            merged[field] = _plain_value(paid_value)
            paid_only.append(field)

    for raw in (free_raw, paid_raw):
        if not raw:
            continue
        for key, value in vars(raw).items() if hasattr(raw, "__dict__") else []:
            if key.startswith("_") or key in merged:
                continue
            if _has_value(value):
                merged[key] = _plain_value(value)

    report = {
        "mode": "free_paid_compare",
        "free_provider": free_provider,
        "paid_provider": paid_provider,
        "agreed_fields": agreed,
        "free_only_fields": free_only,
        "paid_only_fields": paid_only,
        "conflicts": conflicts,
        "requires_review": bool(conflicts or free_only or paid_only),
    }
    merged["ai_compare_report"] = report
    merged["raw_response"] = json.dumps(report, ensure_ascii=False)
    if conflicts:
        conflict_names = ", ".join(item["field"] for item in conflicts)
        merged["error_message"] = f"AI 무료/유료 비교 불일치: {conflict_names}"
    else:
        merged["error_message"] = ""
    return _SimpleRaw(merged)


def _attach_compare_warning(raw: Any, warning: str) -> Any:
    try:
        existing = getattr(raw, "error_message", "") or ""
        setattr(raw, "error_message", f"{existing}; {warning}".strip("; "))
    except Exception:
        logger.debug("Suppressed: compare warning attach failed")
    return raw




class MultiProviderParser:
    """Gemini (1st) → OpenAI (2nd) 2-provider fallback router."""

    def __init__(self, gemini_key: str = "", openai_key: str = ""):
        self._gemini_key = gemini_key
        self._openai_key = openai_key

    # ── internal helpers ──────────────────────────────────────────────────────

    def _gemini(self):
        if not self._gemini_key:
            raise RuntimeError("GEMINI_API_KEY 없음")
        from features.ai.gemini_parser import GeminiDocumentParser
        return GeminiDocumentParser(self._gemini_key)

    def _openai(self):
        if not self._openai_key:
            raise RuntimeError("OPENAI_API_KEY 없음")
        return None  # openai_parser functions are called directly

    # ── public parse methods ──────────────────────────────────────────────────

    def parse_invoice(self, pdf_path: str, gemini_hint: str = ""):
        # 1st: Gemini
        if not _prefer_openai_today():
            try:
                gp = self._gemini()
                return gp.parse_invoice(pdf_path, gemini_hint=gemini_hint), "gemini"
            except Exception as e:
                if not _is_transient_error(e):
                    raise
                _record_gemini_failure()
                logger.warning("[MultiProvider] Gemini 일시 오류 → OpenAI 시도: %s", e)

        # 2nd: OpenAI
        try:
            if not self._openai_key:
                raise RuntimeError("OPENAI_API_KEY 없음")
            from features.ai.openai_parser import try_parse_invoice
            raw = try_parse_invoice(pdf_path, self._openai_key)
            return (_SimpleRaw(raw) if isinstance(raw, dict) else raw), "openai"
        except Exception as e:
            if not _is_transient_error(e):
                raise
            logger.warning("[MultiProvider] OpenAI 일시 오류 — 재시도 불가: %s", e)

        raise RuntimeError("Gemini/OpenAI 모두 일시 오류. 잠시 후 재시도하세요.")

    def parse_bl(self, pdf_path: str, gemini_hint: str = ""):
        if not _prefer_openai_today():
            try:
                gp = self._gemini()
                return gp.parse_bl(pdf_path, gemini_hint=gemini_hint), "gemini"
            except Exception as e:
                if not _is_transient_error(e):
                    raise
                _record_gemini_failure()
                logger.warning("[MultiProvider] Gemini BL 일시 오류 → OpenAI 시도: %s", e)

        try:
            if not self._openai_key:
                raise RuntimeError("OPENAI_API_KEY 없음")
            from features.ai.openai_parser import try_parse_bl
            raw = try_parse_bl(pdf_path, self._openai_key)
            return (_SimpleRaw(raw) if isinstance(raw, dict) else raw), "openai"
        except Exception as e:
            if not _is_transient_error(e):
                raise
            logger.warning("[MultiProvider] OpenAI BL 일시 오류 — 재시도 불가: %s", e)

        raise RuntimeError("Gemini/OpenAI 모두 일시 오류. 잠시 후 재시도하세요.")

    def parse_do(self, pdf_path: str, gemini_hint: str = ""):
        if not _prefer_openai_today():
            try:
                gp = self._gemini()
                return gp.parse_do(pdf_path, gemini_hint=gemini_hint), "gemini"
            except Exception as e:
                if not _is_transient_error(e):
                    raise
                _record_gemini_failure()
                logger.warning("[MultiProvider] Gemini DO 일시 오류 → OpenAI 시도: %s", e)

        try:
            if not self._openai_key:
                raise RuntimeError("OPENAI_API_KEY 없음")
            from features.ai.openai_parser import try_parse_do
            raw = try_parse_do(pdf_path, self._openai_key)
            return (_SimpleRaw(raw) if isinstance(raw, dict) else raw), "openai"
        except Exception as e:
            if not _is_transient_error(e):
                raise
            logger.warning("[MultiProvider] OpenAI DO 일시 오류 — 재시도 불가: %s", e)

        raise RuntimeError("Gemini/OpenAI 모두 일시 오류. 잠시 후 재시도하세요.")

    def parse_packing_list(self, pdf_path: str, gemini_hint: str = ""):
        if not _prefer_openai_today():
            try:
                gp = self._gemini()
                return gp.parse_packing_list(pdf_path, gemini_hint=gemini_hint), "gemini"
            except Exception as e:
                if not _is_transient_error(e):
                    raise
                _record_gemini_failure()
                logger.warning("[MultiProvider] Gemini PL 일시 오류 → OpenAI 시도: %s", e)

        try:
            if not self._openai_key:
                raise RuntimeError("OPENAI_API_KEY 없음")
            from features.ai.openai_parser import try_parse_packing_list
            raw = try_parse_packing_list(pdf_path, self._openai_key)
            return (_SimpleRaw(raw) if isinstance(raw, dict) else raw), "openai"
        except Exception as e:
            if not _is_transient_error(e):
                raise
            logger.warning("[MultiProvider] OpenAI PL 일시 오류 — 재시도 불가: %s", e)

        raise RuntimeError("Gemini/OpenAI 모두 일시 오류. 잠시 후 재시도하세요.")



class MultiProviderParserV2:
    """6-provider fallback: Gemini->Groq->OpenRouter->Ollama->LMStudio->PaidOpenAI.

    Policy: features/ai/ai_fallback_policy.py (settings.ini [AI] section)
    Daily cache: Gemini failures > threshold -> skip Gemini for today
    """

    def __init__(self, *, gemini_key="", openai_key="", groq_key="",
                 openrouter_key="", ollama_base_url="http://localhost:11434",
                 ollama_model="qwen2.5:14b",
                 lmstudio_base_url="http://localhost:1234/v1",
                 lmstudio_model="local-model"):
        self._gemini_key = gemini_key
        self._openai_key = openai_key
        self._groq_key = groq_key
        self._openrouter_key = openrouter_key
        self._ollama_base_url = ollama_base_url
        self._ollama_model = ollama_model
        self._lmstudio_base_url = lmstudio_base_url
        self._lmstudio_model = lmstudio_model

    def _build_parser(self, provider):
        if provider == "gemini":
            if not self._gemini_key:
                raise RuntimeError("GEMINI_API_KEY 없음")
            from features.ai.gemini_parser import GeminiDocumentParser
            return GeminiDocumentParser(self._gemini_key)
        if provider == "groq":
            if not self._groq_key:
                raise RuntimeError("GROQ_API_KEY 없음 — groq 건너뜀")
            from features.ai.groq_parser import create_groq_parser
            return create_groq_parser(self._groq_key)
        if provider == "openrouter":
            if not self._openrouter_key:
                raise RuntimeError("OPENROUTER_API_KEY 없음 — openrouter 건너뜀")
            from features.ai.openrouter_parser import create_openrouter_parser
            return create_openrouter_parser(self._openrouter_key)
        if provider == "ollama":
            from features.ai.local_llm_parser import create_ollama_parser
            return create_ollama_parser(self._ollama_base_url, self._ollama_model)
        if provider == "lmstudio":
            from features.ai.local_llm_parser import create_lmstudio_parser
            return create_lmstudio_parser(self._lmstudio_base_url, self._lmstudio_model)
        if provider == "paid_openai":
            if not self._openai_key:
                raise RuntimeError("OPENAI_API_KEY 없음 — paid_openai 건너뜀")
            from features.ai.openai_compatible_parser import OpenAICompatibleTextParser
            return OpenAICompatibleTextParser(
                provider_name="paid_openai",
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                api_key=self._openai_key,
            )
        raise RuntimeError(f"알 수 없는 provider: {provider}")

    def _parse_with_providers(self, method_name, pdf_path, gemini_hint):
        """Try each enabled provider in policy order. Returns (result, provider_name)."""
        from features.ai.ai_fallback_policy import build_provider_policy, load_ai_fallback_settings
        settings = load_ai_fallback_settings()
        policies = build_provider_policy(settings=settings)
        has_free_policy = any((not p.is_paid) and p.enabled for p in policies)
        if settings.compare_free_paid_enabled and self._openai_key and has_free_policy:
            return self._parse_compare_free_paid(method_name, pdf_path, gemini_hint, policies)

        last_err = RuntimeError("사용 가능한 provider 없음")
        for policy in policies:
            if not policy.enabled:
                logger.debug("[V2] %s disabled by policy", policy.name)
                continue
            if policy.name == "gemini" and _prefer_openai_today():
                logger.info("[V2] Gemini 당일 임계치 초과 — 다음 provider")
                continue
            try:
                parser = self._build_parser(policy.name)
                result = _invoke_parser_method(parser, method_name, pdf_path, gemini_hint)
                if isinstance(result, tuple):
                    result = result[0]
                logger.info("[V2] %s success via %s", method_name, policy.name)
                return result, policy.name
            except Exception as e:
                if policy.name == "gemini" and _is_transient_error(e):
                    _record_gemini_failure()
                if not _is_transient_error(e):
                    logger.warning("[V2] %s non-transient from %s: %s",
                                   method_name, policy.name, e)
                    raise
                logger.warning("[V2] %s transient from %s -> next: %s",
                               method_name, policy.name, e)
                last_err = e
        raise RuntimeError(f"모든 provider 실패: {last_err}")

    def _call_provider(self, provider_name: str, method_name: str, pdf_path: str, gemini_hint: str):
        parser = self._build_parser(provider_name)
        result = _invoke_parser_method(parser, method_name, pdf_path, gemini_hint)
        if isinstance(result, tuple):
            result = result[0]
        return result

    def _try_free_chain(self, method_name: str, pdf_path: str, gemini_hint: str, policies):
        last_err = RuntimeError("사용 가능한 무료/로컬 provider 없음")
        for policy in policies:
            if policy.is_paid or not policy.enabled:
                continue
            if policy.name == "gemini" and _prefer_openai_today():
                logger.info("[COMPARE] Gemini 당일 임계치 초과 — 다음 무료 provider")
                continue
            try:
                result = self._call_provider(policy.name, method_name, pdf_path, gemini_hint)
                return result, policy.name
            except Exception as exc:
                if policy.name == "gemini" and _is_transient_error(exc):
                    _record_gemini_failure()
                last_err = exc
                logger.warning("[COMPARE] free provider %s failed: %s", policy.name, exc)
                continue
        raise RuntimeError(f"무료/로컬 provider 실패: {last_err}")

    def _try_paid_provider(self, method_name: str, pdf_path: str, gemini_hint: str):
        result = self._call_provider("paid_openai", method_name, pdf_path, gemini_hint)
        return result, "paid_openai"

    def _parse_compare_free_paid(self, method_name: str, pdf_path: str, gemini_hint: str, policies):
        """Run one free/local provider and paid OpenAI, then compare field-by-field."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as pool:
            free_future = pool.submit(self._try_free_chain, method_name, pdf_path, gemini_hint, policies)
            paid_future = pool.submit(self._try_paid_provider, method_name, pdf_path, gemini_hint)
            free_result = free_error = paid_result = paid_error = None
            try:
                free_result = free_future.result()
            except Exception as exc:
                free_error = exc
            try:
                paid_result = paid_future.result()
            except Exception as exc:
                paid_error = exc

        if free_result and paid_result:
            free_raw, free_provider = free_result
            paid_raw, paid_provider = paid_result
            merged = _merge_compare_results(
                method_name, free_raw, paid_raw, free_provider, paid_provider
            )
            logger.info("[COMPARE] %s free=%s paid=%s complete",
                        method_name, free_provider, paid_provider)
            return merged, f"compare:{free_provider}+{paid_provider}"

        if free_result:
            free_raw, free_provider = free_result
            warning = f"유료 AI 비교 실패: {paid_error}"
            logger.warning("[COMPARE] paid provider failed; using free result: %s", paid_error)
            return _attach_compare_warning(free_raw, warning), free_provider

        if paid_result:
            paid_raw, paid_provider = paid_result
            warning = f"무료/로컬 AI 비교 실패: {free_error}"
            logger.warning("[COMPARE] free providers failed; using paid result: %s", free_error)
            return _attach_compare_warning(paid_raw, warning), paid_provider

        raise RuntimeError(f"무료/유료 AI 비교 모두 실패: free={free_error}; paid={paid_error}")

    def parse_invoice(self, pdf_path, gemini_hint=""):
        return self._parse_with_providers("parse_invoice", pdf_path, gemini_hint)

    def parse_bl(self, pdf_path, gemini_hint=""):
        return self._parse_with_providers("parse_bl", pdf_path, gemini_hint)

    def parse_do(self, pdf_path, gemini_hint=""):
        return self._parse_with_providers("parse_do", pdf_path, gemini_hint)

    def parse_packing_list(self, pdf_path, gemini_hint=""):
        return self._parse_with_providers("parse_packing_list", pdf_path, gemini_hint)


def _get_provider_parser(owner: Any, provider: Optional[str] = None):
    """Return a MultiProviderParser loaded with all available API keys."""
    # Gemini key (1st priority)
    gemini_key = ""
    try:
        gemini_key = owner._get_ai_key("gemini")
    except Exception:
        gemini_key = getattr(owner, "_ai_api_key", "") or getattr(owner, "gemini_api_key", "")
    if not gemini_key:
        try:
            import core.config as cc
            gemini_key = getattr(cc, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        except Exception:
            gemini_key = os.environ.get("GEMINI_API_KEY", "")

    # OpenAI key (2nd priority)
    openai_key = _load_ext_api_key("openai")


    groq_key = _load_ext_api_key("groq")
    openrouter_key = _load_ext_api_key("openrouter")

    if not gemini_key and not openai_key and not groq_key:
        raise RuntimeError(
            "AI API Key가 없습니다. "
            "GEMINI_API_KEY, OPENAI_API_KEY, 또는 GROQ_API_KEY 를 설정하세요."
        )

    mpp = MultiProviderParserV2(
        gemini_key=gemini_key,
        openai_key=openai_key,
        groq_key=groq_key,
        openrouter_key=openrouter_key,
    )
    return mpp, "multi"


def parse_invoice_ai(owner: Any, pdf_path: str, *, partial: Any = None,
                     carrier_id: str = "", provider: Optional[str] = None) -> InvoiceData:
    gp, used_provider = _get_provider_parser(owner, provider)
    hint = build_ai_hint("FA", carrier_id, partial)
    raw, used_provider = gp.parse_invoice(pdf_path, gemini_hint=hint)

    result = InvoiceData()
    result.source_file = pdf_path
    result.parsed_at = datetime.now()
    result.sap_no = _digits(getattr(raw, "sap_no", ""))
    result.invoice_no = _digits(getattr(raw, "invoice_no", ""))
    result.salar_invoice_no = result.invoice_no
    result.bl_no = _norm_bl(getattr(raw, "bl_no", ""))
    result.customer_name = "SOQUIMICH LLC"
    result.product_code = _clean_text(getattr(raw, "product_code", "")) or "MIC9000.00"
    result.product_name = _clean_text(getattr(raw, "product", ""))
    result.quantity_mt = _to_float(getattr(raw, "quantity_mt", 0))
    result.unit_price = _to_float(getattr(raw, "unit_price", 0))
    result.total_amount = _to_float(getattr(raw, "total_amount", 0))
    result.currency = _clean_text(getattr(raw, "currency", "")) or "USD"
    result.incoterm = _clean_text(getattr(raw, "incoterm", ""))
    result.origin = _clean_text(getattr(raw, "origin", ""))
    result.destination = _clean_text(getattr(raw, "destination", ""))
    result.vessel = _clean_text(getattr(raw, "vessel", ""))
    result.net_weight_kg = _to_kg(getattr(raw, "net_weight_kg", 0))
    result.gross_weight_kg = _to_kg(getattr(raw, "gross_weight_kg", 0))
    result.package_count = _to_int(getattr(raw, "package_count", 0))
    result.package_type = _clean_text(getattr(raw, "package_type", ""))
    result.lot_numbers = _unique(getattr(raw, "lot_numbers", []) or [])
    result.raw_response = getattr(raw, "raw_response", "") or ""
    result.error_message = getattr(raw, "error_message", "") or ""
    result._ai_compare_report = getattr(raw, "ai_compare_report", None)

    _copy_if_empty(result, partial, (
        "sap_no", "invoice_no", "salar_invoice_no", "bl_no", "product_code",
        "product_name", "quantity_mt", "net_weight_kg", "gross_weight_kg",
        "package_count", "package_type", "vessel", "origin", "destination",
    ))
    if not result.lot_numbers and partial and hasattr(partial, "lot_numbers"):
        result.lot_numbers = list(getattr(partial, "lot_numbers") or [])
    result.success = bool(result.sap_no and result.invoice_no)
    logger.info("[AI-FALLBACK] FA %s success=%s sap=%s lots=%s", used_provider, result.success, result.sap_no, len(result.lot_numbers))
    result._ai_provider = used_provider
    return result


def parse_packing_list_ai(owner: Any, pdf_path: str, *, partial: Any = None,
                          carrier_id: str = "", bag_weight_kg: int = None,
                          provider: Optional[str] = None) -> PackingListData:
    gp, used_provider = _get_provider_parser(owner, provider)
    hint = build_ai_hint("PL", carrier_id, partial)
    raw, used_provider = gp.parse_packing_list(pdf_path, gemini_hint=hint)

    result = PackingListData()
    result.source_file = pdf_path
    result.parsed_at = datetime.now()
    result.folio = _digits(getattr(raw, "folio", ""))
    result.sap_no = _sap_from_filename(pdf_path)
    result.product = _clean_text(getattr(raw, "product", ""))
    result.packing = _clean_text(getattr(raw, "packing", ""))
    result.code = _clean_text(getattr(raw, "code", ""))
    result.vessel = _clean_text(getattr(raw, "vessel", ""))
    result.customer = _clean_text(getattr(raw, "customer", ""))
    result.destination = _clean_text(getattr(raw, "destination", ""))
    result.bag_weight_kg = bag_weight_kg
    result.raw_response = getattr(raw, "raw_response", "") or ""
    result.error_message = getattr(raw, "error_message", "") or ""
    result._ai_compare_report = getattr(raw, "ai_compare_report", None)

    for item in getattr(raw, "lots", []) or []:
        lot = LOTInfo(
            list_no=_to_int(getattr(item, "list_no", 0)),
            container_no=_clean_text(getattr(item, "container_no", "")),
            lot_no=_digits(getattr(item, "lot_no", "")),
            lot_sqm=_digits(getattr(item, "lot_sqm", "")),
            mxbg_pallet=_to_int(getattr(item, "mxbg", 10), default=10),
            plastic_jars=1,
            net_weight_kg=_to_kg(getattr(item, "net_weight_kg", 0)),
            gross_weight_kg=_to_kg(getattr(item, "gross_weight_kg", 0)),
            del_no=_digits(getattr(item, "del_no", "")),
            al_no=_digits(getattr(item, "al_no", "")),
        )
        result.lots.append(lot)
        result.rows.append(PackingListRow(
            list_no=lot.list_no,
            container=lot.container_no,
            lot_no=lot.lot_no,
            lot_sqm=lot.lot_sqm,
            mxbg_pallet=lot.mxbg_pallet,
            plastic_jars=lot.plastic_jars,
            net_weight=lot.net_weight_kg,
            gross_weight=lot.gross_weight_kg,
            del_no=lot.del_no,
            al_no=lot.al_no,
        ))

    _copy_if_empty(result, partial, ("folio", "sap_no", "product", "packing", "code", "vessel", "customer", "destination"))
    if not result.lots and partial and hasattr(partial, "lots"):
        result.lots = list(getattr(partial, "lots") or [])
        result.rows = list(getattr(partial, "rows", []) or [])

    result.total_lots = len(result.lots)
    result.total_net_weight_kg = _to_kg(getattr(raw, "total_net_weight_kg", 0)) or sum(l.net_weight_kg for l in result.lots)
    result.total_gross_weight_kg = _to_kg(getattr(raw, "total_gross_weight_kg", 0)) or sum(l.gross_weight_kg for l in result.lots)
    result.total_maxibag = sum(l.mxbg_pallet for l in result.lots)
    result.total_plastic_jars = sum(l.plastic_jars for l in result.lots)
    result.containers = sorted({l.container_no for l in result.lots if l.container_no})
    result.success = bool(result.lots)
    logger.info("[AI-FALLBACK] PL %s success=%s lots=%s", used_provider, result.success, result.total_lots)
    result._ai_provider = used_provider
    return result


def parse_bl_ai(owner: Any, pdf_path: str, *, partial: Any = None,
                carrier_id: str = "", provider: Optional[str] = None) -> BLData:
    carrier = normalize_carrier_id(carrier_id)
    gp, used_provider = _get_provider_parser(owner, provider)
    hint = build_ai_hint("BL", carrier, partial)
    raw, used_provider = gp.parse_bl(pdf_path, gemini_hint=hint)

    result = BLData()
    result.source_file = pdf_path
    result.parsed_at = datetime.now()
    result.bl_no           = _norm_bl(getattr(raw, "bl_no", ""))
    result.booking_no      = _norm_bl(getattr(raw, "booking_no", ""))
    result.scac            = _clean_text(getattr(raw, "scac", ""))
    result.svc_contract    = _clean_text(getattr(raw, "svc_contract", ""))
    result.sap_no          = _clean_text(getattr(raw, "sap_no", ""))
    result.shipper_name    = _clean_text(getattr(raw, "shipper_name", "") or
                                          getattr(raw, "shipper", ""))
    result.consignee_name  = _clean_text(getattr(raw, "consignee_name", "") or
                                          getattr(raw, "consignee", ""))
    result.notify_party    = _clean_text(getattr(raw, "notify_party", ""))
    result.vessel          = _clean_text(getattr(raw, "vessel", ""))
    result.voyage          = _clean_text(getattr(raw, "voyage", ""))
    result.port_of_loading    = _clean_text(getattr(raw, "port_of_loading", ""))
    result.port_of_discharge  = _clean_text(getattr(raw, "port_of_discharge", ""))
    result.place_of_receipt   = _clean_text(getattr(raw, "place_of_receipt", ""))
    result.place_of_delivery  = _clean_text(getattr(raw, "place_of_delivery", ""))
    result.shipped_on_board_date = _parse_date(getattr(raw, "shipped_on_board_date", None))
    result.ship_date       = _parse_date(getattr(raw, "ship_date", None))
    result.issue_date      = _parse_date(getattr(raw, "issue_date", None))
    result.place_of_issue  = _clean_text(getattr(raw, "place_of_issue", ""))
    result.product_name    = _clean_text(getattr(raw, "product_name", "") or
                                          getattr(raw, "product", ""))
    result.total_containers = _to_int(getattr(raw, "total_containers", 0))
    result.total_packages   = _to_int(getattr(raw, "total_packages", 0))
    result.net_weight_kg    = _to_kg(getattr(raw, "total_weight_kg", 0) or
                                      getattr(raw, "net_weight_kg", 0))
    result.gross_weight_kg  = _to_kg(getattr(raw, "gross_weight_kg", 0))
    result.freight_terms    = _clean_text(getattr(raw, "freight_terms", ""))
    result.carrier_id       = carrier_id
    result.raw_response     = getattr(raw, "raw_response", "") or ""
    result.error_message    = getattr(raw, "error_message", "") or ""
    result._ai_compare_report = getattr(raw, "ai_compare_report", None)

    # 컨테이너 목록
    for item in getattr(raw, "containers", []) or []:
        try:
            from parsers.document_models import ContainerInfo
            result.containers.append(ContainerInfo(
                container_no=_clean_text(getattr(item, "container_no", "")),
                seal_no=_clean_text(getattr(item, "seal_no", "")),
                packages=_to_int(getattr(item, "packages", 0)),
                weight_kg=_to_kg(getattr(item, "weight_kg", 0)),
                cbm=float(getattr(item, "cbm", 0) or 0),
            ))
        except Exception:
            logger.debug("[AI-FALLBACK] BL container item 변환 실패")

    _copy_if_empty(result, partial, (
        "bl_no", "booking_no", "vessel", "voyage",
        "port_of_loading", "port_of_discharge", "sap_no",
    ))

    result.success = bool(result.bl_no)
    logger.info("[AI-FALLBACK] BL %s success=%s bl=%s",
                used_provider, result.success, result.bl_no)
    result._ai_provider = used_provider
    return result


def parse_do_ai(owner: Any, pdf_path: str, *, partial: Any = None,
                carrier_id: str = "", provider: Optional[str] = None) -> DOData:
    carrier = normalize_carrier_id(carrier_id)
    gp, used_provider = _get_provider_parser(owner, provider)
    hint = build_ai_hint("DO", carrier, partial)
    raw, used_provider = gp.parse_do(pdf_path, gemini_hint=hint)

    result = DOData()
    result.source_file = pdf_path
    result.parsed_at = datetime.now()
    result.do_no             = _clean_text(getattr(raw, "do_no", ""))
    result.bl_no             = _norm_bl(getattr(raw, "bl_no", ""))
    result.sap_no            = _clean_text(getattr(raw, "sap_no", ""))
    result.shipper           = _clean_text(getattr(raw, "shipper", "") or
                                            getattr(raw, "shipper_name", ""))
    result.consignee         = _clean_text(getattr(raw, "consignee", "") or
                                            getattr(raw, "consignee_name", ""))
    result.notify_party      = _clean_text(getattr(raw, "notify_party", ""))
    result.vessel            = _clean_text(getattr(raw, "vessel", ""))
    result.voyage            = _clean_text(getattr(raw, "voyage", ""))
    result.port_of_loading   = _clean_text(getattr(raw, "port_of_loading", ""))
    result.port_of_discharge = _clean_text(getattr(raw, "port_of_discharge", ""))
    result.final_destination = _clean_text(getattr(raw, "final_destination", "") or
                                            getattr(raw, "destination", ""))
    result.arrival_date      = _parse_date(getattr(raw, "arrival_date", None))
    result.issue_date        = _parse_date(getattr(raw, "issue_date", None))
    result.stock_date        = _parse_date(getattr(raw, "stock_date", None))
    result.description       = _clean_text(getattr(raw, "description", ""))
    result.gross_weight_kg   = _to_kg(getattr(raw, "total_weight_kg", 0) or
                                       getattr(raw, "gross_weight_kg", 0))
    result.total_packages    = _to_int(getattr(raw, "total_packages", 0))
    result.warehouse_code    = _clean_text(getattr(raw, "warehouse_code", ""))
    result.warehouse_name    = _clean_text(getattr(raw, "warehouse_name", "") or
                                            getattr(raw, "warehouse", ""))
    result.mrn               = _clean_text(getattr(raw, "mrn", ""))
    result.msn               = _clean_text(getattr(raw, "msn", ""))
    result.raw_response      = getattr(raw, "raw_response", "") or ""
    result.error_message     = getattr(raw, "error_message", "") or ""
    result._ai_compare_report = getattr(raw, "ai_compare_report", None)

    # 컨테이너 목록
    for item in getattr(raw, "containers", []) or []:
        try:
            from parsers.document_models import ContainerInfo
            result.containers.append(ContainerInfo(
                container_no=_clean_text(getattr(item, "container_no", "")),
                seal_no=_clean_text(getattr(item, "seal_no", "")),
                packages=_to_int(getattr(item, "packages", 0)),
                weight_kg=_to_kg(getattr(item, "weight_kg", 0) or
                                  getattr(item, "gross_weight_kg", 0)),
                cbm=float(getattr(item, "cbm", 0) or 0),
                free_time_date=_parse_date(getattr(item, "free_time_date", None)),
                return_yard=_clean_text(getattr(item, "return_yard", "") or
                                         getattr(item, "return_location", "")),
            ))
        except Exception:
            logger.debug("[AI-FALLBACK] DO container item 변환 실패")

    _copy_if_empty(result, partial, (
        "do_no", "bl_no", "vessel", "voyage",
        "port_of_loading", "port_of_discharge", "sap_no",
    ))

    result.success = bool(result.do_no or result.bl_no)
    logger.info("[AI-FALLBACK] DO %s success=%s do=%s",
                used_provider, result.success, result.do_no)
    result._ai_provider = used_provider
    return result
