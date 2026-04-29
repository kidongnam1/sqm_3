# -*- coding: utf-8 -*-
"""
carrier_templates/generic.py — SQM v8.0.6 PATCH
================================================
Generic fallback 템플릿

설계 원칙:
  - 선사 템플릿이 없거나 모두 실패 시 마지막 fallback으로 사용
  - BL/DO 기본 구조만 정의, 정확도보다 안정성 우선

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations
from typing import Any, Dict, List


_GENERIC_BL_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "GENERIC_BL_V1",
        "doc_type": "BL",
        "priority": 1,
        "title_keywords": ["B/L", "BILL OF LADING", "WAYBILL", "SEA WAYBILL"],
        "match_rules": {
            "required_any": [],
            "exclude_any": [],
        },
        "field_rules": {
            "bl_no": {
                "label_aliases": [
                    "B/L No.", "B/L NO.", "Bill of Lading No.",
                    "SEA WAYBILL No.", "Waybill No.",
                ],
                "type": "text",
                "required": True,
            },
            "vessel": {
                "label_aliases": ["Vessel", "Ocean Vessel"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No.", "Voyage"],
                "type": "text",
            },
            "shipper": {
                "label_aliases": ["Shipper"],
                "type": "block_text",
            },
            "consignee": {
                "label_aliases": ["Consignee"],
                "type": "block_text",
            },
            "port_of_discharge": {
                "label_aliases": ["Port of Discharge"],
                "type": "text",
            },
            "container_table": {
                "anchor_keywords": ["Container", "Weight", "KGS", "CBM"],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["Gross Weight", "GROSS WEIGHT"],
                "type": "number",
            },
        },
        "preview_fields": [
            "bl_no",
            "vessel",
            "voyage_no",
            "port_of_discharge",
            "first_container_no",
            "gross_weight_total",
        ],
        "normalizers": {
            "bl_no": "strip_upper",
            "vessel": "strip_upper",
            "voyage_no": "strip_upper",
            "port_of_discharge": "strip_upper",
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
        },
        "gemini_hint": "",
    },
]

_GENERIC_DO_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "GENERIC_DO_V1",
        "doc_type": "DO",
        "priority": 1,
        "title_keywords": ["D/O", "DELIVERY ORDER", "D/O No.", "발급확인서"],
        "match_rules": {
            "required_any": [],
            "exclude_any": [],
        },
        "field_rules": {
            "do_no": {
                "label_aliases": ["D/O No.", "DO No.", "Delivery Order No."],
                "type": "text",
                "required": True,
            },
            "bl_no": {
                "label_aliases": ["B/L No.", "BL No."],
                "type": "text",
            },
            "ocean_vessel": {
                "label_aliases": ["Ocean Vessel", "Vessel"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No."],
                "type": "text",
            },
            "consignee": {
                "label_aliases": ["Consignee"],
                "type": "block_text",
            },
            "container_table": {
                "anchor_keywords": ["Container", "Seal", "Weight"],
                "type": "table",
            },
            "free_time_table": {
                "anchor_keywords": ["FREE TIME", "Free Time", "반납", "Return"],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["Gross Weight", "Total Weight"],
                "type": "number",
            },
        },
        "preview_fields": [
            "do_no",
            "bl_no",
            "ocean_vessel",
            "voyage_no",
            "consignee",
            "first_container_no",
            "gross_weight_total",
        ],
        "normalizers": {
            "do_no": "strip",
            "bl_no": "strip_upper",
            "ocean_vessel": "strip_upper",
            "voyage_no": "strip_upper",
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
        },
        "gemini_hint": "",
    },
]

GENERIC_TEMPLATE_FAMILY: Dict[str, Any] = {
    "family_id": "TEMPLATE_999_GENERIC",
    "carrier": "GENERIC",
    "carrier_name": "Generic Fallback",
    "priority": 1,
    "aliases": ["GENERIC"],
    "match_rules": {
        "required_any": [],
        "exclude_any": [],
        "score_rules": [],
    },
    "subtemplates": {
        "BL": _GENERIC_BL_SUBTEMPLATES,
        "DO": _GENERIC_DO_SUBTEMPLATES,
    },
}


def get_generic_template_family() -> Dict[str, Any]:
    return GENERIC_TEMPLATE_FAMILY
