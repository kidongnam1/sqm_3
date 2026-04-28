# -*- coding: utf-8 -*-
"""
carrier_templates/mersk.py — SQM v8.0.6 PATCH
==============================================
MERSK(Maersk) 선사 템플릿 1 정의

설계 원칙:
  - BL/DO 서브템플릿을 분리하여 각각의 키워드/필드/프리뷰 기준 제공
  - 템플릿은 "강제 파싱 규칙"이 아닌 "초기 추천 힌트"로 사용
  - 기존 GeminiDocumentParser(parse_bl/parse_do)와 결합 시
    gemini_hint 또는 carrier_template_hint 인자로 전달

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations
from typing import Any, Dict, List


# ─────────────────────────────────────────────────────────────────
# BL 서브템플릿 목록 (우선순위 순)
# ─────────────────────────────────────────────────────────────────
_MERSK_BL_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "MERSK_BL_V1",
        "doc_type": "BL",
        "priority": 100,
        "title_keywords": [
            "NON-NEGOTIABLE WAYBILL",
            "B/L No.",
            "SCAC MAEU",
            "MAERSK BILL OF LADING",
        ],
        "match_rules": {
            "required_any": [
                "NON-NEGOTIABLE WAYBILL",
                "B/L No.",
                "SCAC MAEU",
            ],
            "exclude_any": [
                "D/O 발급확인서",
                "D/O No.",
                "DELIVERY ORDER",
            ],
        },
        "field_rules": {
            "bl_no": {
                "label_aliases": ["B/L No.", "B/L NO.", "B/L:"],
                "type": "text",
                "required": True,
            },
            "booking_no": {
                "label_aliases": ["Booking No."],
                "type": "text",
            },
            "vessel": {
                "label_aliases": ["Vessel"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No."],
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
            "notify_party": {
                "label_aliases": ["Notify Party"],
                "type": "block_text",
            },
            "port_of_loading": {
                "label_aliases": ["Port of Loading"],
                "type": "text",
            },
            "port_of_discharge": {
                "label_aliases": ["Port of Discharge"],
                "type": "text",
            },
            "container_table": {
                "anchor_keywords": [
                    "Container No./Seal No.",
                    "Weight",
                    "Measurement",
                    "KGS",
                    "CBM",
                ],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["KG GROSS WEIGHT", "GROSS WEIGHT"],
                "type": "number",
            },
        },
        "preview_fields": [
            "bl_no",
            "booking_no",
            "vessel",
            "voyage_no",
            "port_of_discharge",
            "shipper",
            "consignee",
            "first_container_no",
            "gross_weight_total",
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
        # Gemini 프롬프트 추가 힌트 (기존 bl_carrier_registry 호환)
        "gemini_hint": (
            "【Maersk BL/Waybill 전용】\n"
            "BL No: 1페이지 우상단 'B/L No.' 라벨 오른쪽 (예: 263764814)\n"
            "Booking No: BL No와 같은 숫자일 수 있음(정상)\n"
            "컨테이너: XXXX0000000 형식(4자리+7숫자)\n"
            "선적일: SHIPPED ON BOARD 또는 ON BOARD DATE 근처"
        ),
    },
    {
        "template_id": "MERSK_WAYBILL_V1",
        "doc_type": "BL",
        "priority": 90,
        "title_keywords": [
            "WAYBILL",
            "SCAC MAEU",
            "MAERSK",
        ],
        "match_rules": {
            "required_any": [
                "WAYBILL",
                "MAEU",
            ],
            "exclude_any": [
                "D/O 발급확인서",
                "DELIVERY ORDER",
            ],
        },
        "field_rules": {
            "bl_no": {
                "label_aliases": ["B/L No.", "Waybill No.", "B/L:"],
                "type": "text",
                "required": True,
            },
            "booking_no": {
                "label_aliases": ["Booking No."],
                "type": "text",
            },
            "vessel": {
                "label_aliases": ["Vessel"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No."],
                "type": "text",
            },
            "container_table": {
                "anchor_keywords": ["Container", "KGS", "CBM"],
                "type": "table",
            },
        },
        "preview_fields": [
            "bl_no",
            "booking_no",
            "vessel",
            "voyage_no",
            "first_container_no",
        ],
        "normalizers": {
            "bl_no": "strip_upper",
            "booking_no": "strip",
            "vessel": "strip_upper",
            "voyage_no": "strip_upper",
            "first_container_no": "container_no_upper",
        },
        "gemini_hint": (
            "【Maersk Waybill 전용】\n"
            "BL No: 'B/L No.' 또는 'Waybill No.' 라벨 오른쪽\n"
            "컨테이너: XXXX0000000 형식"
        ),
    },
]

# ─────────────────────────────────────────────────────────────────
# DO 서브템플릿 목록
# ─────────────────────────────────────────────────────────────────
_MERSK_DO_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "MERSK_DO_V1",
        "doc_type": "DO",
        "priority": 100,
        "title_keywords": [
            "D/O 발급확인서",
            "D/O No.",
            "B/L No.",
            "MAERSK LINE",
        ],
        "match_rules": {
            "required_any": [
                "D/O 발급확인서",
                "D/O No.",
            ],
            "exclude_any": [
                "NON-NEGOTIABLE WAYBILL",
                "SCAC MAEU",
            ],
        },
        "field_rules": {
            "do_no": {
                "label_aliases": ["D/O No.", "DO No."],
                "type": "text",
                "required": True,
            },
            "bl_no": {
                "label_aliases": ["B/L No.", "BL No."],
                "type": "text",
                "required": True,
            },
            "ocean_vessel": {
                "label_aliases": ["Ocean Vessel"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No."],
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
            "port_of_loading": {
                "label_aliases": ["Port of Loading"],
                "type": "text",
            },
            "port_of_discharge": {
                "label_aliases": ["Port of Discharge"],
                "type": "text",
            },
            "container_table": {
                "anchor_keywords": [
                    "Container No.",
                    "Seal No.",
                    "Gross Weight(KGS)",
                    "Measurment(CBM)",
                ],
                "type": "table",
            },
            "free_time_table": {
                "anchor_keywords": [
                    "FREE TIME",
                    "Free_Time",
                    "반납지",
                    "반납일수",
                ],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["Gross Weight(KGS)"],
                "type": "number",
            },
            "measurement_total": {
                "label_aliases": ["Measurment(CBM)", "Measurement(CBM)"],
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
            "first_free_time",
            "first_return_yard",
        ],
        "normalizers": {
            "do_no": "strip",
            "bl_no": "strip_upper",
            "ocean_vessel": "strip_upper",
            "voyage_no": "strip_upper",
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
            "measurement_total": "number_only",
            "first_free_time": "date_yyyy_mm_dd",
            "first_return_yard": "strip_upper",
        },
        "gemini_hint": (
            "【Maersk D/O 발급확인서 전용】\n"
            "D/O No: 상단 'D/O No.' 라벨 오른쪽\n"
            "B/L No: 'B/L No.' 라벨 오른쪽 (MAEU로 시작)\n"
            "컨테이너: 중앙 표 'Container No.' 열\n"
            "Free Time: 하단 표 'Free_Time' 열 (YYYY-MM-DD)\n"
            "반납지: 'KRKWY' 등 코드"
        ),
    },
]

# ─────────────────────────────────────────────────────────────────
# MERSK 템플릿 Family (Template 1)
# ─────────────────────────────────────────────────────────────────
MERSK_TEMPLATE_FAMILY: Dict[str, Any] = {
    "family_id": "TEMPLATE_1_MERSK",
    "carrier": "MAERSK",
    "carrier_name": "Maersk",
    "priority": 100,
    "aliases": [
        "MERSK",
        "MAERSK",
        "MAERSK LINE",
        "MAEU",
        "MAERSK A/S",
    ],
    "match_rules": {
        "required_any": [
            "MAERSK",
            "MAEU",
            "MAERSK LINE",
        ],
        "exclude_any": [
            "MSC",
            "MEDITERRANEAN SHIPPING COMPANY",
            "CMA CGM",
            "HMM",
            "HYUNDAI MERCHANT MARINE",
            "ONE",
            "OCEAN NETWORK EXPRESS",
        ],
        "score_rules": [
            {"contains": "MAERSK", "score": 30},
            {"contains": "MAERSK LINE", "score": 35},
            {"contains": "MAEU", "score": 25},
            {"contains": "SCAC MAEU", "score": 25},
            {"contains": "NON-NEGOTIABLE WAYBILL", "score": 20},
            {"contains": "D/O 발급확인서", "score": 20},
            {"contains": "D/O NO.", "score": 15},
            {"contains": "B/L NO.", "score": 10},
        ],
    },
    "subtemplates": {
        "BL": _MERSK_BL_SUBTEMPLATES,
        "DO": _MERSK_DO_SUBTEMPLATES,
    },
}


def get_mersk_template_family() -> Dict[str, Any]:
    """MERSK 템플릿 Family 반환 (template_registry 등록용)"""
    return MERSK_TEMPLATE_FAMILY
