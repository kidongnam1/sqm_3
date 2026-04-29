# -*- coding: utf-8 -*-
"""
features/parsers/candidate_scorer.py — SQM v8.0.6 PATCH
=========================================================
다중 템플릿 후보 preview 품질 점수 계산

점수 기준:
  - 필수 필드(required) 추출 성공: +25
  - 중요 필드(important) 추출 성공: +10
  - 형식 정상: +3 per field
  - 빈 필드: -4 ~ -20
  - 형식 오류: -10

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional


_REQUIRED: Dict[str, List[str]] = {
    "BL": ["bl_no", "vessel", "first_container_no"],
    "DO": ["do_no", "bl_no", "first_container_no"],
}

_IMPORTANT: Dict[str, List[str]] = {
    "BL": ["booking_no", "voyage_no", "gross_weight_total", "port_of_discharge", "ship_date"],
    "DO": ["ocean_vessel", "voyage_no", "gross_weight_total", "first_free_time", "first_return_yard"],
}


def _validate(field: str, value: Optional[str]) -> str:
    """필드 형식 검사 → "ok" | "empty" | "invalid_*" """
    if not value or str(value).strip() in ("", "None", "NOT_FOUND"):
        return "empty"
    v = str(value).strip()
    if field in {"gross_weight_total", "measurement_total"}:
        try:
            float(v.replace(",", ""))
            return "ok"
        except ValueError:
            return "invalid_number"
    if field in {"first_free_time", "ship_date"}:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            return "ok"
        return "invalid_date"
    if field == "first_container_no":
        if re.match(r"^[A-Z]{4}\d{7}$", v.upper()):
            return "ok"
        return "invalid_format"
    return "ok"


def score_preview_result(preview_data: Dict[str, str], doc_type: str) -> int:
    """
    preview dict의 품질 점수 계산.
    doc_type: "BL" | "DO"
    """
    if not preview_data:
        return -100

    # 오류 있으면 즉시 감점
    err = preview_data.get("error_message", "")
    if err:
        return -100

    score = 0
    validation: Dict[str, str] = {}

    all_fields = set(
        _REQUIRED.get(doc_type, []) + _IMPORTANT.get(doc_type, [])
    )
    for field in all_fields:
        val = preview_data.get(field)
        validation[field] = _validate(field, val)

    for field in _REQUIRED.get(doc_type, []):
        state = validation.get(field, "empty")
        if state == "ok":
            score += 25
        elif state != "empty":
            score += 5
        else:
            score -= 20

    for field in _IMPORTANT.get(doc_type, []):
        state = validation.get(field, "empty")
        if state == "ok":
            score += 10
        elif state != "empty":
            score += 3
        else:
            score -= 5

    for state in validation.values():
        if state == "ok":
            score += 3
        elif state == "empty":
            score -= 4
        elif state in {"invalid_number", "invalid_date", "invalid_format"}:
            score -= 10

    return score
