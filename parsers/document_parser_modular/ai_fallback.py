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


# ── Multi-provider helper utilities ───────────────────────────────────────────

def _is_transient_error(exc: Exception) -> bool:
    """503 / 429 / quota errors → True (fallback to next provider)."""
    msg = str(exc).lower()
    for kw in ("503", "429", "quota", "overloaded", "rate limit",
               "resource_exhausted", "too many requests", "unavailable"):
        if kw in msg:
            return True
    return False


def _load_ext_api_key(provider: str) -> str:
    """Load OpenAI key: env OPENAI_API_KEY → core.config → settings.ini [OpenAI]."""
    provider = provider.lower()
    if provider != "openai":
        return ""
    env_val = os.environ.get("OPENAI_API_KEY", "")
    if env_val:
        return env_val
    try:
        import core.config as cc
        return getattr(cc, "OPENAI_API_KEY", "") or ""
    except Exception:
        pass
    try:
        import configparser, pathlib
        ini = pathlib.Path(__file__).resolve().parents[3] / "settings.ini"
        if ini.exists():
            cp = configparser.ConfigParser()
            cp.read(ini, encoding="utf-8")
            if cp.has_section("OpenAI"):
                return cp.get("OpenAI", "api_key", fallback="")
    except Exception:
        pass
    return ""


class _SimpleRaw:
    """Wrap a dict as attribute-accessible object (duck-types GeminiDocumentParser result)."""
    def __init__(self, d: dict):
        for k, v in d.items():
            setattr(self, k, v)
    def __getattr__(self, item):
        return None



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
        try:
            gp = self._gemini()
            return gp.parse_invoice(pdf_path, gemini_hint=gemini_hint), "gemini"
        except Exception as e:
            if not _is_transient_error(e):
                raise
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
        try:
            gp = self._gemini()
            return gp.parse_bl(pdf_path, gemini_hint=gemini_hint), "gemini"
        except Exception as e:
            if not _is_transient_error(e):
                raise
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
        try:
            gp = self._gemini()
            return gp.parse_do(pdf_path, gemini_hint=gemini_hint), "gemini"
        except Exception as e:
            if not _is_transient_error(e):
                raise
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
        try:
            gp = self._gemini()
            return gp.parse_packing_list(pdf_path, gemini_hint=gemini_hint), "gemini"
        except Exception as e:
            if not _is_transient_error(e):
                raise
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


    if not gemini_key and not openai_key:
        raise RuntimeError("AI API Key가 없습니다. GEMINI_API_KEY 또는 OPENAI_API_KEY 환경변수를 설정하세요.")

    mpp = MultiProviderParser(gemini_key, openai_key)
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
    result.bl_no = _norm_bl(getattr(raw, "bl_no", ""))
    result.booking_no = _norm_bl(getattr(raw, "booking_no", "")) or result.bl_no
    result.sap_no = _digits(getattr(raw, "sap_no", ""))
    result.vessel = _clean_text(getattr(raw, "vessel", ""))
    result.voyage = _clean_text(getattr(raw, "voyage", ""))
    result.port_of_loading = _clean_text(getattr(raw, "port_of_loading", ""))
    result.port_of_discharge = _clean_text(getattr(raw, "port_of_discharge", ""))
    result.shipper_name = _clean_text(getattr(raw, "shipper", ""))
    result.consignee_name = _clean_text(getattr(raw, "consignee", ""))
    result.total_containers = _to_int(getattr(raw, "total_containers", 0))
    result.gross_weight_kg = _to_kg(getattr(raw, "total_weight_kg", 0))
    result.total_weight = result.gross_weight_kg
    result.shipped_on_board_date = _clean_text(
        getattr(raw, "shipped_on_board_date", "") or getattr(raw, "ship_date", "") or getattr(raw, "shipped_date", "")
    )
    result.ship_date = result.shipped_on_board_date
    result.carrier_id = carrier or normalize_carrier_id(getattr(raw, "carrier_id", ""))
    result.carrier_name = _clean_text(getattr(raw, "carrier_name", "")) or result.carrier_id
    result.bl_equals_booking_no = bool(getattr(raw, "bl_equals_booking_no", False))
    result.raw_response = getattr(raw, "raw_response", "") or ""
    result.error_message = getattr(raw, "error_message", "") or ""

    for c in getattr(raw, "containers", []) or []:
        ci = ContainerInfo()
        ci.container_no = _norm_container(getattr(c, "container_no", ""))
        ci.seal_no = _clean_text(getattr(c, "seal_no", ""))
        ci.weight_kg = _to_kg(getattr(c, "weight_kg", 0))
        if ci.container_no:
            result.containers.append(ci)

    _copy_if_empty(result, partial, (
        "bl_no", "booking_no", "sap_no", "vessel", "voyage",
        "port_of_loading", "port_of_discharge", "gross_weight_kg",
        "total_containers", "carrier_id", "carrier_name",
    ))
    if not result.containers and partial and hasattr(partial, "containers"):
        result.containers = list(getattr(partial, "containers") or [])
    if not result.total_containers:
        result.total_containers = len(result.containers)
    result.success = bool(result.bl_no)
    logger.info("[AI-FALLBACK] BL %s carrier=%s success=%s bl=%s", used_provider, result.carrier_id, result.success, result.bl_no)
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
    result.carrier_id = carrier
    result.do_no = _clean_text(getattr(raw, "do_no", ""))
    result.bl_no = _norm_bl(getattr(raw, "bl_no", "") or getattr(raw, "bl_no_full", ""))
    result.vessel = _clean_text(getattr(raw, "vessel", ""))
    result.voyage = _clean_text(getattr(raw, "voyage", ""))
    result.port_of_loading = _clean_text(getattr(raw, "port_of_loading", ""))
    result.port_of_discharge = _clean_text(getattr(raw, "port_of_discharge", ""))
    result.shipper = _clean_text(getattr(raw, "shipper", ""))
    result.consignee = _clean_text(getattr(raw, "consignee", ""))
    result.gross_weight_kg = _to_kg(getattr(raw, "total_weight_kg", 0))
    result.arrival_date = _clean_text(getattr(raw, "arrival_date", ""))
    result.issue_date = _clean_text(getattr(raw, "issue_date", ""))
    result.raw_response = getattr(raw, "raw_response", "") or ""
    result.error_message = getattr(raw, "error_message", "") or ""

    result.free_time_info = []
    for c in getattr(raw, "containers", []) or []:
        ci = ContainerInfo()
        ci.container_no = _norm_container(getattr(c, "container_no", ""))
        ci.seal_no = _clean_text(getattr(c, "seal_no", ""))
        ci.size_type = _clean_text(getattr(c, "size_type", ""))
        if ci.container_no:
            result.containers.append(ci)
        ft_date = _clean_text(getattr(c, "free_time", ""))
        return_place = _clean_text(getattr(c, "return_place", ""))
        if ci.container_no or ft_date or return_place:
            result.free_time_info.append(FreeTimeInfo(
                container_no=ci.container_no,
                free_time_date=ft_date,
                return_location=return_place,
                storage_free_days=0,
            ))

    _copy_if_empty(result, partial, (
        "do_no", "bl_no", "vessel", "voyage", "port_of_loading",
        "port_of_discharge", "gross_weight_kg", "arrival_date", "issue_date",
    ))
    if not result.containers and partial and hasattr(partial, "containers"):
        result.containers = list(getattr(partial, "containers") or [])
    if not result.free_time_info and partial and hasattr(partial, "free_time_info"):
        result.free_time_info = list(getattr(partial, "free_time_info") or [])
    result.success = bool(result.bl_no or result.do_no)
    logger.info("[AI-FALLBACK] DO %s carrier=%s success=%s bl=%s do=%s", used_provider, carrier, result.success, result.bl_no, result.do_no)
    result._ai_provider = used_provider
    return result


def _accepts_do_hint(gp: Any) -> bool:
    # Current GeminiDocumentParser.parse_do does not accept gemini_hint in older builds.
    try:
        import inspect
        return "gemini_hint" in inspect.signature(gp.parse_do).parameters
    except Exception:
        return False


def _sap_from_filename(pdf_path: str) -> str:
    m = re.search(r"(22\d{8})", os.path.basename(str(pdf_path or "")))
    return m.group(1) if m else ""


def parse_inbound_4docs(owner: Any, *, fa_path: str = None, pl_path: str = None,
                        bl_path: str = None, do_path: str = None,
                        carrier_id: str = "") -> ShipmentDocuments:
    """
    Parse FA/PL/BL/DO with coordinate-first parser methods.

    The owner is normally DocumentParserV3. Its parser methods already run the
    coordinate path first; this helper supplies the selected carrier to BL/DO and
    attaches cross-check results when available.
    """
    carrier = normalize_carrier_id(carrier_id)
    if carrier and carrier not in SUPPORTED_AI_CARRIERS:
        logger.warning("[AI-FALLBACK] carrier=%s is not in validated 4-carrier set %s",
                       carrier, sorted(SUPPORTED_AI_CARRIERS))

    docs = ShipmentDocuments()

    if fa_path:
        docs.invoice = owner.parse_invoice(fa_path)
    if pl_path:
        docs.packing_list = owner.parse_packing_list(pl_path)
    if bl_path:
        try:
            docs.bl = owner.parse_bl(bl_path, carrier_id=carrier)
        except TypeError:
            docs.bl = owner.parse_bl(bl_path)
    if do_path:
        old_carrier = getattr(owner, "_last_carrier_id", "")
        try:
            if carrier:
                owner._last_carrier_id = carrier
            docs.do = owner.parse_do(do_path)
        finally:
            try:
                owner._last_carrier_id = old_carrier
            except Exception:
                pass

    try:
        from ..cross_check_engine import cross_check_documents
        cross = cross_check_documents(
            invoice=docs.invoice,
            packing_list=docs.packing_list,
            bl=docs.bl,
            do=docs.do,
        )
        docs.cross_check_result = cross
        if not getattr(cross, "is_clean", True):
            docs.validation_errors.extend(str(item) for item in getattr(cross, "items", []) or [])
    except Exception as exc:
        logger.debug("[AI-FALLBACK] cross_check skipped: %s", exc)

    docs.sap_no = (
        getattr(docs.invoice, "sap_no", "") or
        getattr(docs.packing_list, "sap_no", "") or
        getattr(docs.bl, "sap_no", "")
    )
    docs.bl_no = (
        getattr(docs.invoice, "bl_no", "") or
        getattr(docs.bl, "bl_no", "") or
        getattr(docs.do, "bl_no", "")
    )
    docs.folio = getattr(docs.packing_list, "folio", "") or ""
    docs.do_no = getattr(docs.do, "do_no", "") or ""
    docs.vessel = (
        getattr(docs.invoice, "vessel", "") or
        getattr(docs.packing_list, "vessel", "") or
        getattr(docs.bl, "vessel", "") or
        getattr(docs.do, "vessel", "")
    )
    docs.net_weight_kg = (
        getattr(docs.invoice, "net_weight_kg", 0) or
        getattr(docs.packing_list, "total_net_weight_kg", 0) or
        getattr(docs.bl, "net_weight_kg", 0)
    )
    docs.gross_weight_kg = (
        getattr(docs.invoice, "gross_weight_kg", 0) or
        getattr(docs.packing_list, "total_gross_weight_kg", 0) or
        getattr(docs.bl, "gross_weight_kg", 0) or
        getattr(docs.do, "gross_weight_kg", 0)
    )
    return docs
