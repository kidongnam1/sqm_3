# -*- coding: utf-8 -*-
"""
carrier_templates/one.py — SQM v866
====================================
ONE (Ocean Network Express) 선사 템플릿

[수정이력]
  2026-05-04  Ruby  SQM v866 신규 생성
"""
from __future__ import annotations
from typing import Any, Dict, List

_ONE_BL_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "ONE_BL_V1",
        "doc_type": "BL",
        "priority": 100,
        "title_keywords": [
            "OCEAN BILL OF LADING",
            "BILL OF LADING",
            "OCEAN NETWORK EXPRESS",
            "ONE",
            "ONEU",
        ],
        "match_rules": {
            "required_any": [
                "OCEAN NETWORK EXPRESS",
                "ONEU",
                "ONEY",
            ],
            "exclude_any": [
                "MAERSK", "MSC", "HAPAG", "HMM",
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
                "label_aliases": ["Booking No.", "Booking Number"],
                "type": "text",
            },
            "vessel": {
                "label_aliases": ["Ocean Vessel", "Vessel", "Vessel Name"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No.", "Voy No.", "VOY"],
                "type": "text",
            },
            "port_of_loading": {
                "label_aliases": ["Port of Loading", "POL"],
                "type": "text",
            },
            "port_of_discharge": {
                "label_aliases": ["Port of Discharge", "POD"],
                "type": "text",
            },
            "container_table": {
                "anchor_keywords": ["Container No.", "Seal No.", "KGS", "CBM"],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["Gross Weight", "GROSS WEIGHT", "Total Gross Weight"],
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
            "【ONE (Ocean Network Express) BL 전용】\n"
            "BL No: \'B/L No.\' 라벨 옆 — ONEU로 시작하는 7자리 숫자 (예: ONEU1234567)\n"
            "Booking No: BL No와 동일한 경우 많음(정상)\n"
            "선사 SCAC 코드: ONEY\n"
            "컨테이너: XXXX0000000 형식(4자리+7숫자)\n"
            "주의: \'OCEAN NETWORK EXPRESS\' 텍스트로 선사 확인"
        ),
    },
]

_ONE_DO_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "ONE_DO_V1",
        "doc_type": "DO",
        "priority": 100,
        "title_keywords": [
            "D/O 발급확인서", "DELIVERY ORDER", "D/O No.",
            "OCEAN NETWORK EXPRESS", "ONE",
        ],
        "match_rules": {
            "required_any": ["D/O 발급확인서", "D/O No.", "DELIVERY ORDER"],
            "exclude_any": ["NON-NEGOTIABLE WAYBILL", "MAERSK", "MSC", "HAPAG"],
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
                "label_aliases": ["Ocean Vessel", "Vessel"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No.", "Voy"],
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
            "【ONE D/O 발급확인서 전용】\n"
            "D/O No: 상단 \'D/O No.\' 라벨 옆\n"
            "B/L No: \'B/L No.\' 라벨 옆 (ONEU로 시작)\n"
            "Free Time: 하단 표 \'Free Time\' 열 (YYYY-MM-DD)\n"
            "반납지: 항구 코드 (예: KRKWY, KRPUS)"
        ),
    },
]

ONE_TEMPLATE_FAMILY: Dict[str, Any] = {
    "family_id": "TEMPLATE_3_ONE",
    "carrier": "ONE",
    "carrier_name": "Ocean Network Express",
    "priority": 90,
    "aliases": ["ONE", "ONEU", "ONEY", "OCEAN NETWORK EXPRESS", "ONE LINE"],
    "match_rules": {
        "required_any": ["OCEAN NETWORK EXPRESS", "ONEU", "ONEY"],
        "exclude_any": ["MAERSK", "MSC", "HAPAG", "HMM", "CMA CGM"],
        "score_rules": [
            {"contains": "OCEAN NETWORK EXPRESS", "score": 35},
            {"contains": "ONEU", "score": 25},
            {"contains": "ONEY", "score": 20},
        ],
    },
    "subtemplates": {
        "BL": _ONE_BL_SUBTEMPLATES,
        "DO": _ONE_DO_SUBTEMPLATES,
    },
}

def get_one_template_family() -> Dict[str, Any]:
    return ONE_TEMPLATE_FAMILY
