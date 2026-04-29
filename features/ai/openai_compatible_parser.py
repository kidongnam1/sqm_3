"""Text-first OpenAI-compatible document parser adapters.

These adapters support Groq, OpenRouter, Ollama, and LM Studio as fallback
providers. They do not replace the coordinate/Gemini vision path; they are used
after text extraction when a free/local model can still recover structured data.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from types import SimpleNamespace
from typing import Any

logger = logging.getLogger(__name__)

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


def _simple(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _simple(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_simple(v) for v in value]
    return value


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError as exc:
                logger.debug("Suppressed: fallback JSON decode failed: %s", exc)
    return {}


def _extract_pdf_text(pdf_path: str, max_chars: int = 18000) -> str:
    if not HAS_PYMUPDF:
        raise RuntimeError("PyMuPDF 미설치: text fallback provider 사용 불가")
    doc = fitz.open(pdf_path)
    try:
        chunks = []
        for page in doc:
            chunks.append(page.get_text("text") or "")
            if sum(len(c) for c in chunks) >= max_chars:
                break
        text = "\n".join(chunks).strip()
        if not text:
            raise RuntimeError("PDF 텍스트 추출 결과가 비어 있습니다")
        return text[:max_chars]
    finally:
        doc.close()


def _prompt(doc_type: str, gemini_hint: str, text: str) -> str:
    schemas = {
        "invoice": (
            '{"sap_no":"","invoice_no":"","bl_no":"","product_code":"",'
            '"product":"","quantity_mt":0,"net_weight_kg":0,"gross_weight_kg":0,'
            '"package_count":0,"package_type":"","vessel":"","origin":"",'
            '"destination":"","lot_numbers":[]}'
        ),
        "bl": (
            '{"bl_no":"","booking_no":"","sap_no":"","vessel":"","voyage":"",'
            '"port_of_loading":"","port_of_discharge":"","shipper":"",'
            '"consignee":"","total_containers":0,"total_weight_kg":0,'
            '"shipped_on_board_date":"","carrier_id":"",'
            '"containers":[{"container_no":"","seal_no":"","weight_kg":0}]}'
        ),
        "do": (
            '{"do_no":"","bl_no":"","vessel":"","voyage":"","port_of_loading":"",'
            '"port_of_discharge":"","shipper":"","consignee":"","total_weight_kg":0,'
            '"arrival_date":"","issue_date":"",'
            '"containers":[{"container_no":"","seal_no":"","size_type":"",'
            '"free_time":"","return_place":""}]}'
        ),
        "packing_list": (
            '{"folio":"","product":"","packing":"","code":"","vessel":"",'
            '"customer":"","destination":"","total_net_weight_kg":0,'
            '"total_gross_weight_kg":0,'
            '"lots":[{"list_no":0,"container_no":"","lot_no":"","lot_sqm":"",'
            '"mxbg":10,"net_weight_kg":0,"gross_weight_kg":0,'
            '"del_no":"","al_no":""}]}'
        ),
    }
    schema = schemas[doc_type]
    return (
        "You are a shipping document parser for SQM Inventory.\n"
        "Return ONLY valid JSON matching this schema. Do not invent values.\n"
        "Normalize dates to YYYY-MM-DD and weights to kg.\n\n"
        f"Schema:\n{schema}\n\n"
        f"Context hint:\n{gemini_hint or ''}\n\n"
        f"PDF text:\n{text}"
    )


class OpenAICompatibleTextParser:
    """Minimal chat-completions adapter for free/local fallback models."""

    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: int = 45,
    ):
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def parse_invoice(self, pdf_path: str, gemini_hint: str = ""):
        return self._parse("invoice", pdf_path, gemini_hint)

    def parse_bl(self, pdf_path: str, gemini_hint: str = ""):
        return self._parse("bl", pdf_path, gemini_hint)

    def parse_do(self, pdf_path: str, gemini_hint: str = ""):
        return self._parse("do", pdf_path, gemini_hint)

    def parse_packing_list(self, pdf_path: str, gemini_hint: str = ""):
        return self._parse("packing_list", pdf_path, gemini_hint)

    def _parse(self, doc_type: str, pdf_path: str, gemini_hint: str):
        text = _extract_pdf_text(pdf_path)
        prompt = _prompt(doc_type, gemini_hint, text)
        raw_text = self._chat(prompt)
        data = _extract_json(raw_text)
        if not data:
            raise RuntimeError(f"{self.provider_name} JSON 응답 없음")
        data["raw_response"] = raw_text
        data["error_message"] = ""
        return _simple(data)

    def _chat(self, prompt: str) -> str:
        if "localhost:11434" in self.base_url or self.base_url.endswith(":11434"):
            return self._chat_ollama(prompt)
        return self._chat_openai_compatible(prompt)

    def _chat_openai_compatible(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 4096,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return self._post_json(url, payload, headers)

    def _chat_ollama(self, prompt: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0},
        }
        text = self._post_json(url, payload, {"Content-Type": "application/json"})
        data = _extract_json(text)
        if "message" in data and isinstance(data["message"], dict):
            return str(data["message"].get("content", ""))
        return text

    def _post_json(self, url: str, payload: dict, headers: dict) -> str:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.provider_name} HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self.provider_name} 연결 실패: {exc}") from exc

        data = json.loads(raw)
        if "choices" in data:
            return str(data["choices"][0]["message"].get("content", ""))
        if "message" in data and isinstance(data["message"], dict):
            return json.dumps(data, ensure_ascii=False)
        return raw

