# -*- coding: utf-8 -*-
"""
features/ai/multi_template_registry.py — SQM v8.0.6 PATCH
==========================================================
다중 템플릿 후보 엔진 레지스트리

설계 원칙:
  - 기존 bl_carrier_registry.py는 유지 (BL No 정규식 추출 전용)
  - 이 파일은 BL/DO preview 단계에서 후보 템플릿을 선택하는 새 계층
  - 기존 GeminiDocumentParser(parse_bl/parse_do)와 조합 사용

연결 방식:
  template_hint = get_candidate_templates(...)[0]["template_hint"]
  gemini_hint   = template_hint.get("gemini_hint", "")
  # → gemini_parser.parse_bl(pdf_path, gemini_hint=gemini_hint)

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from features.ai.carrier_templates.mersk import get_mersk_template_family
from features.ai.carrier_templates.msc import get_msc_template_family
from features.ai.carrier_templates.hmm_cmacgm import (
    get_hmm_template_family,
    get_cma_cgm_template_family,
)
from features.ai.carrier_templates.generic import get_generic_template_family

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# 등록된 템플릿 Family 목록 (우선순위 높은 것부터)
# ─────────────────────────────────────────────────────────────────
_TEMPLATE_FAMILIES: List[Dict[str, Any]] = [
    get_mersk_template_family(),   # Template 1: MERSK
    get_msc_template_family(),     # Template 2: MSC
    get_hmm_template_family(),     # Template 3: HMM
    get_cma_cgm_template_family(), # Template 4: CMA CGM
    get_generic_template_family(), # Template 999: Generic fallback
]


# ─────────────────────────────────────────────────────────────────
# 내부 유틸
# ─────────────────────────────────────────────────────────────────
def _su(text: str) -> str:
    """safe upper"""
    return (text or "").upper()


def _contains_any(src_u: str, items: List[str]) -> bool:
    return any(item.upper() in src_u for item in (items or []))


def _calc_family_score(family: Dict[str, Any], text: str, filename: str) -> int:
    src_u = _su(f"{filename}\n{text}")
    score = int(family.get("priority", 0))
    rules = family.get("match_rules", {})

    if _contains_any(src_u, rules.get("exclude_any", [])):
        return -9999

    for token in rules.get("required_any", []):
        if token.upper() in src_u:
            score += 20

    for rule in rules.get("score_rules", []):
        token = str(rule.get("contains", "")).upper()
        if token and token in src_u:
            score += int(rule.get("score", 0))

    return score


def _calc_subtemplate_score(sub: Dict[str, Any], text: str, filename: str) -> int:
    src_u = _su(f"{filename}\n{text}")
    score = int(sub.get("priority", 0))
    rules = sub.get("match_rules", {})

    if _contains_any(src_u, rules.get("exclude_any", [])):
        return -9999

    for token in rules.get("required_any", []):
        if token.upper() in src_u:
            score += 25

    for token in sub.get("title_keywords", []):
        if token.upper() in src_u:
            score += 10

    return score


# ─────────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────────
def guess_doc_type(first_page_text: str, filename: str) -> Optional[str]:
    """파일명+1페이지 텍스트로 문서유형(BL/DO) 추정"""
    src_u = _su(f"{filename}\n{first_page_text}")
    do_score = sum(1 for t in ["D/O", "DELIVERY ORDER", "D/O 발급확인서", "DO NO."] if t in src_u)
    bl_score = sum(1 for t in ["B/L", "BILL OF LADING", "WAYBILL", "SEA WAYBILL", "B/L NO."] if t in src_u)
    if do_score == 0 and bl_score == 0:
        return None
    return "DO" if do_score > bl_score else "BL"


def guess_carrier(first_page_text: str, filename: str) -> Optional[str]:
    """v8.7.0 [POLICY]: 자동 선사 추정 비활성화 — 호출부는 사용자 입력(db_carrier_id) 우선 사용.

    정책: "철저히 사용자 입력하는 베이스" — 파일명/텍스트 기반 자동 추정 금지.
    호출부가 carrier를 명시적으로 넘기지 않으면 None을 반환하여 GENERIC 경로로 빠지게 함.

    (기존 별칭 매칭 로직은 주석 처리 — 필요 시 복구 가능)
    """
    _ = (first_page_text, filename)  # 파라미터 유지(시그니처 호환)
    return None


def get_candidate_templates(
    first_page_text: str,
    filename: str,
    doc_type: Optional[str] = None,
    carrier: Optional[str] = None,
    max_candidates: int = 3,
) -> List[Dict[str, Any]]:
    """
    후보 템플릿 목록 반환 (점수 내림차순).

    반환 형식 (1건):
    {
        "family_id": ...,
        "carrier": ...,
        "doc_type": ...,
        "template_id": ...,
        "match_score": ...,
        "template_hint": {... subtemplate dict ...},
    }
    """
    resolved_doc_type = doc_type or guess_doc_type(first_page_text, filename)
    resolved_carrier = carrier or guess_carrier(first_page_text, filename)

    candidates: List[Tuple[int, Dict[str, Any]]] = []

    for family in _TEMPLATE_FAMILIES:
        fam_carrier = str(family.get("carrier", ""))
        # 선사가 특정됐으면 해당 선사 + generic만 시도
        if resolved_carrier and fam_carrier not in (resolved_carrier, "GENERIC"):
            continue

        fam_score = _calc_family_score(family, first_page_text, filename)
        if fam_score < -1000:
            continue

        subtemplates: Dict[str, List] = family.get("subtemplates", {})

        def _try_subtypes(sub_list: List, inferred_doc_type: str) -> None:
            for sub in sub_list:
                sub_score = _calc_subtemplate_score(sub, first_page_text, filename)
                if sub_score < -1000:
                    continue
                total = fam_score + sub_score
                candidates.append((
                    total,
                    {
                        "family_id": family["family_id"],
                        "carrier": fam_carrier,
                        "doc_type": inferred_doc_type,
                        "template_id": sub["template_id"],
                        "match_score": total,
                        "template_hint": sub,
                    },
                ))

        if resolved_doc_type:
            _try_subtypes(subtemplates.get(resolved_doc_type, []), resolved_doc_type)
        else:
            for dt, sub_list in subtemplates.items():
                _try_subtypes(sub_list, dt)

    candidates.sort(key=lambda x: x[0], reverse=True)

    # 중복 template_id 제거
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for _, cand in candidates:
        tid = cand["template_id"]
        if tid in seen:
            continue
        seen.add(tid)
        deduped.append(cand)
        if len(deduped) >= max_candidates:
            break

    # 후보가 없으면 generic fallback 강제 추가
    if not deduped and resolved_doc_type:
        generic = next(
            (f for f in _TEMPLATE_FAMILIES if f.get("carrier") == "GENERIC"), None
        )
        if generic:
            for sub in generic.get("subtemplates", {}).get(resolved_doc_type, []):
                deduped.append({
                    "family_id": generic["family_id"],
                    "carrier": "GENERIC",
                    "doc_type": resolved_doc_type,
                    "template_id": sub["template_id"],
                    "match_score": 0,
                    "template_hint": sub,
                })
                break

    for i, cand in enumerate(deduped):
        logger.info(
            "[MultiRegistry] 후보%d: template_id=%s carrier=%s doc_type=%s score=%s",
            i + 1,
            cand["template_id"],
            cand["carrier"],
            cand["doc_type"],
            cand["match_score"],
        )

    return deduped


def get_best_gemini_hint(
    first_page_text: str,
    filename: str,
    doc_type: Optional[str] = None,
    carrier: Optional[str] = None,
) -> str:
    """
    기존 GeminiDocumentParser.parse_bl(gemini_hint=...) 연결용.
    1순위 후보 템플릿의 gemini_hint 문자열 반환.
    """
    candidates = get_candidate_templates(
        first_page_text, filename, doc_type=doc_type, carrier=carrier, max_candidates=1
    )
    if candidates:
        return candidates[0]["template_hint"].get("gemini_hint", "")
    return ""
