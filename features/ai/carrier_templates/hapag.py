# -*- coding: utf-8 -*-
"""
carrier_templates/hapag.py — SQM v866
======================================
Hapag-Lloyd 선사 템플릿

[수정이력]
  2026-05-04  Ruby  SQM v866 신규 생성
"""
from __future__ import annotations
from typing import Any, Dict, List

_HAPAG_BL_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "HAPAG_BL_V1",
        "doc_type": "BL",
        "priority": 100,
        "title_keywords": [
            "BILL OF LADING",
            "HAPAG-LLOYD",
            "HAPAG LLOYD",
            "HLCU",
        ],
        "match_rules": {
            "required_any": ["HAPAG-LLOYD", "HAPAG LLOYD", "HLCU", "HLCUX"],
            "exclude_any": [
                "MAERSK", "MSC", "ONE", "HMM",
                "CMA CGM", "D/O 발급확인서",
            ],
        },
        "field_rules": {
            "bl_no": {
                "label_aliases": ["B/L No.", "B/L NO.", "BL No.", "Bill of Lading No."],
                "type": "text",
                "required": True,
            },
            "booking_no": {
                "label_aliases": ["Booking No.", "Booking Ref."],
                "type": "text",
            },
            "vessel": {
                "label_aliases": ["Vessel", "Ocean Vessel", "Pre-Carriage By"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No.", "Voy.", "VOY"],
                "type": "text",
            },
            "port_of_loading": {
                "label_aliases": ["Port of Loading", "Place of Receipt"],
                "type": "text",
            },
            "port_of_discharge": {
                "label_aliases": ["Port of Discharge", "Place of Delivery"],
                "type": "text",
            },
            "container_table": {
                "anchor_keywords": [
                    "Container No.", "Seal No.", "KGS", "CBM", "Gross Weight",
                ],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["Gross Weight", "GROSS WEIGHT", "Total Weight"],
                "type": "number",
            },
        },
        "preview_fields": [
            "bl_no", "booking_no", "vessel", "voyage_no",
            "port_of_discharge", "first_container_no", "gross_weight_total",
        ],
        "normalizers": {
            "bl_no": "strip_upper",
            "booking_no": "strip",
            "vessel": "strip_upper",
            "voyage_no": "strip_upper",
            "port_of_discharge": "strip_upper",
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
        },
        "gemini_hint": (
            "【Hapag-Lloyd BL 전용】\n"
            "BL No: \'B/L No.\' 라벨 옆 — HLCU로 시작 (예: HLCU1234567890)\n"
            "SCAC 코드: HLCU 또는 HLCUX\n"
            "컨테이너: XXXX0000000 형식(4자리+7숫자)\n"
            "주의: \'HAPAG-LLOYD\' 또는 \'Hapag-Lloyd AG\' 텍스트로 선사 확인\n"
            "선적일: \'Shipped on Board\' 또는 \'Date of Issue\' 근처"
        ),
    },
]

_HAPAG_DO_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "HAPAG_DO_V1",
        "doc_type": "DO",
        "priority": 100,
        "title_keywords": [
            "D/O 발급확인서", "DELIVERY ORDER", "D/O No.",
            "HAPAG-LLOYD", "HAPAG LLOYD",
        ],
        "match_rules": {
            "required_any": ["D/O 발급확인서", "D/O No.", "DELIVERY ORDER"],
            "exclude_any": ["NON-NEGOTIABLE WAYBILL", "MAERSK", "MSC", "ONE"],
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
                "required": True,
            },
            "vessel": {
                "label_aliases": ["Vessel", "Ocean Vessel"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No.", "Voy."],
                "type": "text",
            },
            "container_table": {
                "anchor_keywords": ["Container No.", "Seal No.", "KGS", "CBM"],
                "type": "table",
            },
            "free_time_table": {
                "anchor_keywords": ["FREE TIME", "Free Time", "반납일수", "반납지"],
                "type": "table",
            },
        },
        "preview_fields": [
            "do_no", "bl_no", "vessel", "voyage_no",
            "first_container_no", "first_free_time", "first_return_yard",
        ],
        "normalizers": {
            "do_no": "strip",
            "bl_no": "strip_upper",
            "vessel": "strip_upper",
            "voyage_no": "strip_upper",
            "first_container_no": "container_no_upper",
            "first_free_time": "date_yyyy_mm_dd",
            "first_return_yard": "strip_upper",
        },
        "gemini_hint": (
            "【Hapag-Lloyd D/O 발급확인서 전용】\n"
            "D/O No: 상단 \'D/O No.\' 라벨 옆\n"
            "B/L No: \'B/L No.\' 라벨 옆 (HLCU로 시작)\n"
            "Free Time: 하단 표 \'Free Time\' 열 (YYYY-MM-DD)\n"
            "반납지: 항구 코드 (예: KRKWY, KRPUS)"
        ),
    },
]

HAPAG_TEMPLATE_FAMILY: Dict[str, Any] = {
    "family_id": "TEMPLATE_4_HAPAG",
    "carrier": "HAPAG",
    "carrier_name": "Hapag-Lloyd",
    "priority": 85,
    "aliases": [
        "HAPAG", "HAPAG-LLOYD", "HAPAG LLOYD",
        "HLCU", "HLCUX", "Hapag-Lloyd AG",
    ],
    "match_rules": {
        "required_any": ["HAPAG-LLOYD", "HAPAG LLOYD", "HLCU", "HLCUX"],
        "exclude_any": ["MAERSK", "MSC", "ONE", "HMM", "CMA CGM"],
        "score_rules": [
            {"contains": "HAPAG-LLOYD", "score": 35},
            {"contains": "HAPAG LLOYD", "score": 30},
            {"contains": "HLCU", "score": 25},
            {"contains": "HLCUX", "score": 25},
        ],
    },
    "subtemplates": {
        "BL": _HAPAG_BL_SUBTEMPLATES,
        "DO": _HAPAG_DO_SUBTEMPLATES,
    },
}

def get_hapag_template_family() -> Dict[str, Any]:
    return HAPAG_TEMPLATE_FAMILY
