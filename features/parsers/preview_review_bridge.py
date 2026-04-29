# -*- coding: utf-8 -*-
"""사전 검수 브리지 유틸
- 파일명/본문 힌트 기반 문서유형 추정
- 문서별 대표 1행(대표 레코드) 생성
- PreParseReviewDialog 입력 데이터 생성
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gui_app_modular.dialogs.preparse_review_dialog import ReviewItem, PreviewField


def detect_doc_type_from_name(file_name: str) -> tuple[str, str]:
    name = (file_name or "").upper()
    rules = [
        ("BL", ["B/L", "BL", "BILL OF LADING"]),
        ("PL", ["PACKING", "P/L", "PL"]),
        ("FA", ["INVOICE", "FINAL INVOICE", "FA"]),
        ("DO", ["DELIVERY ORDER", "D/O", " DO "]),
    ]
    for doc_type, keys in rules:
        for key in keys:
            if key in name:
                return doc_type, f"파일명 키워드 감지: {key}"
    return "OTHER", "파일명 기준 명확한 유형 미검출"


def build_review_item_for_document(file_path: str, preview_payload: dict[str, Any] | None = None) -> ReviewItem:
    file_name = Path(file_path).name
    auto_doc_type, detect_reason = detect_doc_type_from_name(file_name)
    preview_payload = preview_payload or {}
    fields = []
    for key, value in preview_payload.items():
        fields.append(
            PreviewField(
                key=key,
                label=key,
                value=value,
                field_type=_guess_field_type(key, value),
                required=key.upper() in {"LOT_NO", "QTY", "NET_WEIGHT", "BL_NO", "CONTAINER_NO"},
            )
        )
    if not fields:
        fields = [
            PreviewField("LOT_NO", "LOT_NO", "", "string", True),
            PreviewField("QTY", "QTY", "", "float", False),
            PreviewField("UNIT", "UNIT", "", "enum", False, ["KG", "MT"]),
        ]
    return ReviewItem(
        file_path=file_path,
        file_name=file_name,
        auto_doc_type=auto_doc_type,
        user_doc_type=auto_doc_type,
        detect_reason=detect_reason,
        preview_fields=fields,
        preview_status="대기",
    )


def _guess_field_type(key: str, value: Any) -> str:
    key_u = (key or "").upper()
    if key_u.endswith("DATE"):
        return "date"
    if key_u in {"QTY", "NET_WEIGHT", "GROSS_WEIGHT", "QTY_MT", "QTY_KG"}:
        return "float"
    if key_u in {"BAG_QTY", "TONBAG_COUNT"}:
        return "int"
    if key_u == "UNIT":
        return "enum"
    return "string"
