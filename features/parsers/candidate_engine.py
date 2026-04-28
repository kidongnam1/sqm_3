# -*- coding: utf-8 -*-
"""
features/parsers/candidate_engine.py — SQM v8.0.6 PATCH
=========================================================
다중 템플릿 후보 엔진

역할:
  - 후보 템플릿별로 GeminiDocumentParser preview를 시도
  - 각 결과의 품질 점수(candidate_scorer)를 비교
  - 최고 점수 후보를 선택하여 반환

사용 예시:
  from features.parsers.candidate_engine import run_candidate_preview

  result = run_candidate_preview(
      pdf_path=pdf_path,
      filename=os.path.basename(pdf_path),
      first_page_text=first_page_text,
      gemini_parser=parser,          # GeminiDocumentParser 인스턴스
      user_doc_type="BL",
  )
  best = result["best"]
  if best:
      gemini_hint = best["gemini_hint"]
      full_result = parser.parse_bl(pdf_path, gemini_hint=gemini_hint)

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from features.ai.multi_template_registry import get_candidate_templates
from features.parsers.candidate_scorer import score_preview_result

logger = logging.getLogger(__name__)


def run_candidate_preview(
    pdf_path: str,
    filename: str,
    first_page_text: str,
    gemini_parser: Any,                     # GeminiDocumentParser 인스턴스
    user_doc_type: Optional[str] = None,
    user_carrier: Optional[str] = None,
    max_candidates: int = 3,
) -> Dict[str, Any]:
    """
    후보 템플릿별 preview 실행 후 최고 품질 후보 반환.

    반환 구조:
    {
        "ok": bool,
        "message": str,
        "candidates": [
            {
                "candidate_rank": int,
                "template_id": str,
                "carrier": str,
                "doc_type": str,
                "match_score": int,
                "quality_score": int,
                "gemini_hint": str,
                "preview_data": dict,   # BLResult/DOResult 주요 필드
                "raw_result": object,   # BLResult or DOResult
            }, ...
        ],
        "best": {위 구조 중 quality_score 최고 항목} | None,
    }
    """
    candidates = get_candidate_templates(
        first_page_text=first_page_text,
        filename=filename,
        doc_type=user_doc_type,
        carrier=user_carrier,
        max_candidates=max_candidates,
    )

    if not candidates:
        logger.warning("[CandidateEngine] 후보 템플릿 없음: %s", filename)
        return {
            "ok": False,
            "message": "후보 템플릿을 찾지 못했습니다.",
            "candidates": [],
            "best": None,
        }

    results: List[Dict[str, Any]] = []

    for rank, cand in enumerate(candidates, start=1):
        doc_type = cand["doc_type"]
        hint = cand["template_hint"]
        gemini_hint = hint.get("gemini_hint", "")
        template_id = cand["template_id"]

        logger.info(
            "[CandidateEngine] preview 시도 rank=%d template_id=%s doc_type=%s",
            rank, template_id, doc_type,
        )

        try:
            if doc_type == "BL":
                raw = gemini_parser.parse_bl(pdf_path, gemini_hint=gemini_hint)
                preview_data = _bl_result_to_dict(raw)
            elif doc_type == "DO":
                raw = gemini_parser.parse_do(pdf_path)
                preview_data = _do_result_to_dict(raw)
            else:
                logger.warning("[CandidateEngine] 미지원 doc_type=%s", doc_type)
                continue

            quality = score_preview_result(preview_data, doc_type)

            enriched = {
                "candidate_rank": rank,
                "template_id": template_id,
                "family_id": cand["family_id"],
                "carrier": cand["carrier"],
                "doc_type": doc_type,
                "match_score": cand["match_score"],
                "quality_score": quality,
                "gemini_hint": gemini_hint,
                "preview_data": preview_data,
                "raw_result": raw,
            }
            results.append(enriched)

            logger.info(
                "[CandidateEngine] preview 완료 template_id=%s quality=%d",
                template_id, quality,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[CandidateEngine] preview 실패 template_id=%s: %s",
                template_id, exc,
            )
            results.append({
                "candidate_rank": rank,
                "template_id": template_id,
                "family_id": cand["family_id"],
                "carrier": cand["carrier"],
                "doc_type": doc_type,
                "match_score": cand["match_score"],
                "quality_score": -100,
                "gemini_hint": gemini_hint,
                "preview_data": {},
                "raw_result": None,
                "error": str(exc),
            })

    # quality_score 내림차순 정렬
    results.sort(key=lambda x: (x.get("quality_score", -100), x.get("match_score", 0)), reverse=True)

    best = results[0] if results else None
    if best:
        logger.info(
            "[CandidateEngine] 최종 선택: template_id=%s quality=%d",
            best["template_id"], best["quality_score"],
        )

    return {
        "ok": bool(best and best.get("quality_score", -100) > -100),
        "message": "후보 preview 완료",
        "candidates": results,
        "best": best,
    }


# ─────────────────────────────────────────────────────────────────
# BLResult / DOResult → dict 변환 (점수 계산용)
# ─────────────────────────────────────────────────────────────────
def _bl_result_to_dict(raw: Any) -> Dict[str, Any]:
    """BLResult 객체 → 점수 계산용 dict"""
    if raw is None:
        return {}
    try:
        containers = getattr(raw, "containers", []) or []
        first_container = containers[0].get("container_no", "") if containers else ""
        return {
            "bl_no": getattr(raw, "bl_no", ""),
            "booking_no": getattr(raw, "booking_no", ""),
            "vessel": getattr(raw, "vessel", ""),
            "voyage_no": getattr(raw, "voyage", ""),
            "port_of_discharge": getattr(raw, "port_of_discharge", ""),
            "shipper": getattr(raw, "shipper", ""),
            "consignee": getattr(raw, "consignee", ""),
            "first_container_no": first_container,
            "gross_weight_total": str(getattr(raw, "total_weight_kg", "") or ""),
            "total_containers": str(getattr(raw, "total_containers", "") or ""),
            "ship_date": getattr(raw, "shipped_on_board_date", ""),
            "carrier_id": getattr(raw, "carrier_id", ""),
            "error_message": getattr(raw, "error_message", ""),
        }
    except Exception:
        return {}


def _do_result_to_dict(raw: Any) -> Dict[str, Any]:
    """DOResult 객체 → 점수 계산용 dict"""
    if raw is None:
        return {}
    try:
        containers = getattr(raw, "containers", []) or []
        first_con = containers[0] if containers else {}
        return {
            "do_no": getattr(raw, "do_no", ""),
            "bl_no": getattr(raw, "bl_no", ""),
            "ocean_vessel": getattr(raw, "vessel", ""),
            "voyage_no": getattr(raw, "voyage", ""),
            "consignee": getattr(raw, "consignee", ""),
            "first_container_no": first_con.get("container_no", "") if isinstance(first_con, dict) else "",
            "gross_weight_total": str(getattr(raw, "total_gross_weight", "") or ""),
            "first_free_time": first_con.get("free_time", "") if isinstance(first_con, dict) else "",
            "first_return_yard": first_con.get("return_yard", "") if isinstance(first_con, dict) else "",
            "error_message": getattr(raw, "error_message", ""),
        }
    except Exception:
        return {}
