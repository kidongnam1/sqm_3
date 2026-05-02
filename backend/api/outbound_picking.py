# -*- coding: utf-8 -*-
"""
Picking List 파서 API
POST /api/outbound/picking  — PDF 업로드 → 파싱 결과 JSON 반환
"""
import logging
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/outbound", tags=["outbound"])


def _get_owner():
    """Gemini API owner 인스턴스 반환. 키 없으면 None."""
    try:
        from features.ai.gemini_parser import GeminiDocumentParser
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            # settings.ini fallback
            try:
                import configparser, pathlib
                cfg = configparser.ConfigParser()
                cfg.read(str(pathlib.Path(__file__).parents[2] / "settings.ini"), encoding="utf-8")
                key = cfg.get("AI", "gemini_api_key", fallback="")
            except Exception:
                pass
        if key:
            return GeminiDocumentParser(key)
    except Exception as e:
        logger.debug("[PICKING] owner 생성 실패: %s", e)
    return None


@router.post("/picking")
async def parse_picking_list(file: UploadFile = File(...)):
    """
    Picking List PDF 업로드 → 파싱 결과 반환.

    텍스트 PDF: 좌표 기반 파싱 (빠름, 오프라인)
    이미지 PDF: Gemini Vision 파싱 (API 키 필요)
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF 파일만 업로드 가능합니다")

    tmp_path = None
    try:
        # 임시 파일 저장
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # 파서 실행
        from parsers.document_parser_modular.picking_mixin import PickingListParserMixin
        parser = PickingListParserMixin()
        owner = _get_owner()
        result = parser.parse_picking_list_auto(tmp_path, owner=owner)

        if not result.success and result.errors:
            raise HTTPException(422, detail={
                "ok": False,
                "errors": result.errors,
                "warnings": result.warnings,
            })

        return {
            "ok": True,
            "filename": file.filename,
            "pdf_type": PickingListParserMixin._detect_pdf_type(tmp_path),
            "meta": {
                "outbound_id":       result.meta.outbound_id,
                "sales_order":       result.meta.sales_order,
                "customer_ref":      result.meta.picking_no,
                "plan_loading_date": result.meta.plan_loading_date,
                "cutoff_date":       result.meta.cutoff_date,
                "delivery_terms":    result.meta.delivery_terms,
                "containers":        result.meta.containers,
                "port_loading":      result.meta.port_loading,
                "port_discharge":    result.meta.port_discharge,
                "contact_person":    result.meta.contact_person,
                "contact_email":     result.meta.contact_email,
                "bag_weight_kg":     result.meta.bag_weight_kg or 500,
            },
            "summary": result.summary,
            "tonbag": [
                {
                    "lot_no":    t.lot_no,
                    "weight_kg": t.weight_kg,
                    "unit":      t.unit,
                    "storage":   t.storage,
                }
                for t in result.tonbag
            ],
            "sample": [
                {
                    "lot_no":    s.lot_no,
                    "weight_kg": s.weight_kg,
                    "unit":      s.unit,
                    "storage":   s.storage,
                }
                for s in result.sample
            ],
            "warnings": result.warnings,
            "errors":   result.errors,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[PICKING] 파싱 예외: %s", e)
        raise HTTPException(500, f"파싱 중 오류: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
