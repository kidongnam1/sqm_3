# -*- coding: utf-8 -*-
"""
backend/api/template_ai_api.py
================================
AI 기반 선사 템플릿 자동 생성 API

POST /api/inbound/templates/generate-from-docs
  - BL PDF + D/O PDF 업로드 → Gemini AI 분석 → 템플릿 데이터 반환
  - 저장은 기존 POST /api/inbound/templates 재사용

Author: Ruby (2026-05-04)
"""
from __future__ import annotations
import json, logging, os, re, tempfile
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbound/templates", tags=["template-ai"])

# ── Gemini 템플릿 추출 프롬프트 ──────────────────────────────────────────────
_EXTRACT_PROMPT = """You are analyzing a shipping transport document (Bill of Lading or Delivery Order)
for a Korean logistics company.

Analyze the document image carefully and extract carrier template information.

Return ONLY a valid JSON object — no markdown fences, no explanation, just raw JSON:
{
  "carrier_id": "SHORT_CAPS_CODE",
  "carrier_name": "Full Carrier Company Name",
  "bl_format": "LETTER_PREFIX",
  "bl_no_example": "actual BL or reference number found in document",
  "doc_type": "BL or DO",
  "aliases": ["list", "of", "carrier", "identifiers", "visible", "in", "document"],
  "gemini_hint_bl": "【선사명 BL 전용】BL No: 위치설명 (예시번호). 컨테이너: 형식설명. (한국어로 작성)",
  "gemini_hint_do": "【선사명 D/O 전용】D/O No: 위치설명. BL No: 위치설명. (한국어로 작성)",
  "gemini_hint_packing": "선사명 패킹리스트: 포대수량, 순중량(kg), 총중량(kg) 추출 방법. (한국어로 작성)",
  "port_of_loading": "loading port city name if visible",
  "port_of_discharge": "discharge port city name if visible"
}

Rules:
- carrier_id: short ALL-CAPS code (e.g. MAERSK, MSC, ONE, HAPAG, EVERGREEN, CMACGM, HMM, YANGMING, ZIM)
- bl_format: alphabetic prefix of the BL number only (e.g. if BL is MAEU123456789, format is MAEU)
- aliases: include company name, SCAC code, and any other identifiers visible in the document
- gemini_hint_bl and gemini_hint_do: Korean language instructions describing WHERE to find key fields
- If document is D/O (Delivery Order / 화물인도지시서), set doc_type to "DO"
- If document is BL (Bill of Lading / 선하증권), set doc_type to "BL"
"""


def _pdf_to_images(pdf_path: str, dpi: int = 150) -> list[bytes]:
    """PDF → PNG bytes 리스트 (최대 2페이지)"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        images = []
        for i, page in enumerate(doc):
            if i >= 2:  # 최대 2페이지만 (첫 페이지가 핵심)
                break
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            images.append(pix.tobytes("png"))
        doc.close()
        return images
    except Exception as e:
        logger.warning(f"PDF→이미지 변환 실패: {e}")
        return []


def _call_gemini_vision(image_bytes_list: list[bytes], prompt: str) -> Optional[str]:
    """Gemini Vision API 호출 → 텍스트 응답"""
    try:
        from features.ai.gemini_utils import get_gemini_client, get_model_name, call_gemini_safe
        client = get_gemini_client()
        model  = get_model_name()

        try:
            from google.genai import types as _gt
            parts = []
            for img_bytes in image_bytes_list:
                parts.append(_gt.Part.from_bytes(data=img_bytes, mime_type="image/png"))
            parts.append(_gt.Part.from_text(prompt))
            contents = parts
        except ImportError:
            # 구버전 호환
            contents = [prompt] + [img for img in image_bytes_list]

        resp = call_gemini_safe(client, model, contents, timeout=45)
        if resp is None:
            return None
        return resp.text if hasattr(resp, "text") else str(resp)
    except Exception as e:
        logger.error(f"Gemini Vision 호출 실패: {e}")
        return None


def _parse_gemini_json(raw: str) -> dict:
    """Gemini 응답에서 JSON 추출 (마크다운 펜스 제거)"""
    if not raw:
        return {}
    # ```json ... ``` 또는 ``` ... ``` 제거
    text = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    # JSON 블록 탐색
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _merge_doc_results(bl_data: dict, do_data: dict) -> dict:
    """BL 분석 결과 + D/O 분석 결과 병합"""
    merged = dict(bl_data)
    # D/O에서 do_hint만 덮어쓰기
    if do_data.get("gemini_hint_do"):
        merged["gemini_hint_do"] = do_data["gemini_hint_do"]
    # aliases 합치기
    aliases = list(bl_data.get("aliases", []))
    for a in do_data.get("aliases", []):
        if a not in aliases:
            aliases.append(a)
    merged["aliases"] = aliases
    return merged


# ── 엔드포인트 ────────────────────────────────────────────────────────────────
@router.post("/generate-from-docs", summary="🤖 AI 선사 템플릿 자동 생성 (PDF 업로드)")
async def generate_template_from_docs(
    bl_file: Optional[UploadFile] = File(None,  description="BL(선하증권) PDF"),
    do_file: Optional[UploadFile] = File(None,  description="D/O(화물인도지시서) PDF (선택)"),
):
    """
    BL / D/O PDF를 Gemini AI로 분석하여 선사 템플릿 데이터를 자동 추출합니다.
    저장은 프론트에서 POST /api/inbound/templates 를 별도 호출.
    """
    if not bl_file and not do_file:
        raise HTTPException(400, "BL 또는 D/O PDF 파일을 하나 이상 업로드하세요")

    tmp_paths = []
    try:
        results = {}

        for label, upload in [("BL", bl_file), ("DO", do_file)]:
            if not upload:
                continue
            if not (upload.filename or "").lower().endswith(".pdf"):
                raise HTTPException(400, f"{label} 파일은 PDF만 지원합니다")

            content = await upload.read()
            if not content:
                raise HTTPException(400, f"{label} 파일이 비어 있습니다")

            tf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tf.write(content)
            tf.close()
            tmp_paths.append(tf.name)

            images = _pdf_to_images(tf.name)
            if not images:
                raise HTTPException(500, f"{label} PDF를 이미지로 변환할 수 없습니다 (PyMuPDF 필요)")

            raw = _call_gemini_vision(images, _EXTRACT_PROMPT)
            if not raw:
                raise HTTPException(500, f"Gemini AI 분석 실패 — API 키 또는 네트워크 확인")

            parsed = _parse_gemini_json(raw)
            if not parsed.get("carrier_id"):
                raise HTTPException(422, f"{label} 문서에서 선사 정보를 추출하지 못했습니다.\n"
                                         "선명하게 인쇄된 BL 원본 PDF를 사용하세요.")
            results[label] = parsed
            logger.info(f"[template-ai] {label} 분석 완료: carrier={parsed.get('carrier_id')}")

        # BL 우선, DO는 hint 보강용
        final = results.get("BL") or results.get("DO")
        if "BL" in results and "DO" in results:
            final = _merge_doc_results(results["BL"], results["DO"])

        # 템플릿명 자동 제안
        cid   = final.get("carrier_id", "선사미상")
        cname = final.get("carrier_name", cid)
        final["suggested_name_500"]  = f"{cid} — 리튬카보네이트 500 kg"
        final["suggested_name_1000"] = f"{cid} — 리튬카보네이트 1,000 kg"
        final["product_hint_default"] = "리튬카보네이트 500kg/포대"

        return {
            "ok": True,
            "preview": final,
            "message": f"✅ {cname} 선사 템플릿 분석 완료 — 아래 내용 확인 후 저장하세요"
        }

    finally:
        for p in tmp_paths:
            try:
                os.unlink(p)
            except Exception:
                pass
