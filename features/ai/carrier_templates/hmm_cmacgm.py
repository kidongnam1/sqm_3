# -*- coding: utf-8 -*-
"""
carrier_templates/hmm_cmacgm.py — SQM v8.0.6 PATCH
====================================================
Template 3: HMM (Hyundai Merchant Marine)
Template 4: CMA CGM

설계 원칙:
  - 실제 샘플 미확보 → 기존 bl_carrier_registry.py 패턴 기반 보수적 설계
  - BL No 정규식은 기존 bl_carrier_registry 재사용 (detect_pattern 호환)
  - DO는 generic 기반 (샘플 미확보)
  - 실제 샘플 수신 후 V2로 정밀화 예정

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations
from typing import Any, Dict, List


# ══════════════════════════════════════════════════════════════════
# Template 3: HMM (Hyundai Merchant Marine)
# ══════════════════════════════════════════════════════════════════

_HMM_BL_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "HMM_BL_V1",
        "doc_type": "BL",
        "priority": 100,
        "title_keywords": [
            "HYUNDAI MERCHANT MARINE",
            "HMM",
            "HMM CO., LTD",
            "BILL OF LADING",
        ],
        "match_rules": {
            "required_any": [
                "HYUNDAI MERCHANT MARINE",
                "HMM CO., LTD",
            ],
            "exclude_any": [
                "MAERSK", "MAEU",
                "MEDITERRANEAN SHIPPING",
                "CMA CGM",
                "ONE", "OCEAN NETWORK",
            ],
        },
        "field_rules": {
            "bl_no": {
                "label_aliases": [
                    "B/L No.", "B/L NO.", "Bill of Lading No.",
                    "B/L NUMBER",
                ],
                "type": "text",
                "required": True,
            },
            "booking_no": {
                "label_aliases": ["Booking No.", "Booking Number"],
                "type": "text",
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
            "booking_no",
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
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
        },
        "gemini_hint": (
            "【HMM (Hyundai Merchant Marine) Bill of Lading 전용 규칙】\n"
            "BL No 위치: 1페이지 상단 'B/L No.' 또는 'Bill of Lading No.' 라벨 근처\n"
            "형식 예시: HBKM1234567 (알파벳+숫자 혼합)\n"
            "컨테이너: XXXX0000000 형식 (4자리+7숫자)\n"
            "⚠️ 실제 HMM BL 샘플 기반이 아니므로 파싱 후 반드시 확인하세요."
        ),
        # 기존 bl_carrier_registry 호환
        "_bl_extract_pattern": (
            r"B(?:/L|ILL OF LADING)\s*(?:No\.?|NUMBER|:)\s*([A-Z0-9]{6,20})"
        ),
        "_bl_page_scope": "page0",
        "_bl_format_hint": "HBKM1234567",
    },
]

_HMM_DO_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "HMM_DO_V1",
        "doc_type": "DO",
        "priority": 70,
        "title_keywords": ["HMM", "HYUNDAI", "D/O", "DELIVERY ORDER"],
        "match_rules": {
            "required_any": ["HYUNDAI MERCHANT MARINE", "HMM"],
            "exclude_any": ["MAERSK", "MSC", "CMA CGM"],
        },
        "field_rules": {
            "do_no": {
                "label_aliases": ["D/O No.", "DO No.", "Delivery Order No."],
                "type": "text",
                "required": True,
            },
            "bl_no": {
                "label_aliases": ["B/L No."],
                "type": "text",
            },
            "ocean_vessel": {
                "label_aliases": ["Vessel", "Ocean Vessel"],
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
                "anchor_keywords": ["Container", "Weight"],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["Gross Weight"],
                "type": "number",
            },
        },
        "preview_fields": [
            "do_no", "bl_no", "ocean_vessel", "voyage_no",
            "consignee", "first_container_no", "gross_weight_total",
        ],
        "normalizers": {
            "do_no": "strip",
            "bl_no": "strip_upper",
            "ocean_vessel": "strip_upper",
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
        },
        "gemini_hint": (
            "【HMM D/O 전용 (샘플 미확보 — 검수 필수)】\n"
            "⚠️ HMM DO 실제 샘플 기반이 아닙니다. 파싱 후 반드시 수동 검수하세요."
        ),
    },
]

HMM_TEMPLATE_FAMILY: Dict[str, Any] = {
    "family_id": "TEMPLATE_3_HMM",
    "carrier": "HMM",
    "carrier_name": "Hyundai Merchant Marine",
    "priority": 90,
    "aliases": [
        "HMM",
        "HYUNDAI MERCHANT MARINE",
        "HMM CO., LTD",
    ],
    "match_rules": {
        "required_any": [
            "HYUNDAI MERCHANT MARINE",
            "HMM CO., LTD",
        ],
        "exclude_any": [
            "MAERSK", "MAEU", "MEDITERRANEAN SHIPPING",
            "CMA CGM", "ONE", "OCEAN NETWORK EXPRESS",
        ],
        "score_rules": [
            {"contains": "HYUNDAI MERCHANT MARINE", "score": 40},
            {"contains": "HMM CO., LTD", "score": 30},
            {"contains": "HMM", "score": 15},
            {"contains": "B/L NO.", "score": 10},
        ],
    },
    "subtemplates": {
        "BL": _HMM_BL_SUBTEMPLATES,
        "DO": _HMM_DO_SUBTEMPLATES,
    },
}


# ══════════════════════════════════════════════════════════════════
# Template 4: CMA CGM
# ══════════════════════════════════════════════════════════════════

_CMA_BL_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "CMA_CGM_BL_V1",
        "doc_type": "BL",
        "priority": 100,
        "title_keywords": [
            "CMA CGM",
            "COMPAGNIE GENERALE MARITIME",
            "CMA CGM S.A.",
            "BILL OF LADING",
        ],
        "match_rules": {
            "required_any": [
                "CMA CGM",
                "COMPAGNIE GENERALE MARITIME",
            ],
            "exclude_any": [
                "MAERSK", "MAEU",
                "MEDITERRANEAN SHIPPING",
                "HMM", "HYUNDAI",
                "ONE", "OCEAN NETWORK",
            ],
        },
        "field_rules": {
            "bl_no": {
                "label_aliases": [
                    "B/L No.", "B/L NO.", "Bill of Lading No.",
                    "Waybill No.",
                ],
                "type": "text",
                "required": True,
            },
            "booking_no": {
                "label_aliases": ["Booking No.", "Booking Reference"],
                "type": "text",
            },
            "vessel": {
                "label_aliases": ["Vessel", "Ocean Vessel", "Pre-Carriage By"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No.", "Voyage"],
                "type": "text",
            },
            "shipper": {
                "label_aliases": ["Shipper", "Exporter"],
                "type": "block_text",
            },
            "consignee": {
                "label_aliases": ["Consignee"],
                "type": "block_text",
            },
            "port_of_discharge": {
                "label_aliases": ["Port of Discharge", "Place of Delivery"],
                "type": "text",
            },
            "container_table": {
                "anchor_keywords": ["Container No.", "Seal No.", "KGS", "CBM"],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["Gross Weight", "GROSS WEIGHT"],
                "type": "number",
            },
        },
        "preview_fields": [
            "bl_no",
            "booking_no",
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
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
        },
        "gemini_hint": (
            "【CMA CGM Bill of Lading 전용 규칙】\n"
            "BL No 위치: 1페이지 상단 'B/L No.' 라벨 근처\n"
            "형식 예시: CMDUXXXXXXXXX (알파벳+숫자 혼합)\n"
            "컨테이너: XXXX0000000 형식 (4자리+7숫자)\n"
            "⚠️ 실제 CMA CGM BL 샘플 기반이 아니므로 파싱 후 반드시 확인하세요."
        ),
        "_bl_extract_pattern": (
            r"B(?:/L|ILL OF LADING)\s*(?:No\.?|:)\s*([A-Z0-9]{6,20})"
        ),
        "_bl_page_scope": "page0",
        "_bl_format_hint": "CMDUXXXXXXXXX",
    },
]

_CMA_DO_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "CMA_CGM_DO_V1",
        "doc_type": "DO",
        "priority": 70,
        "title_keywords": ["CMA CGM", "D/O", "DELIVERY ORDER"],
        "match_rules": {
            "required_any": ["CMA CGM", "COMPAGNIE GENERALE MARITIME"],
            "exclude_any": ["MAERSK", "MSC", "HMM"],
        },
        "field_rules": {
            "do_no": {
                "label_aliases": ["D/O No.", "Delivery Order No."],
                "type": "text",
                "required": True,
            },
            "bl_no": {
                "label_aliases": ["B/L No."],
                "type": "text",
            },
            "ocean_vessel": {
                "label_aliases": ["Vessel", "Ocean Vessel"],
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
                "anchor_keywords": ["Container", "Weight"],
                "type": "table",
            },
            "gross_weight_total": {
                "label_aliases": ["Gross Weight"],
                "type": "number",
            },
        },
        "preview_fields": [
            "do_no", "bl_no", "ocean_vessel", "voyage_no",
            "consignee", "first_container_no", "gross_weight_total",
        ],
        "normalizers": {
            "do_no": "strip",
            "bl_no": "strip_upper",
            "ocean_vessel": "strip_upper",
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
        },
        "gemini_hint": (
            "【CMA CGM D/O 전용 (샘플 미확보 — 검수 필수)】\n"
            "⚠️ CMA CGM DO 실제 샘플 기반이 아닙니다. 파싱 후 반드시 수동 검수하세요."
        ),
    },
]

CMA_CGM_TEMPLATE_FAMILY: Dict[str, Any] = {
    "family_id": "TEMPLATE_4_CMA_CGM",
    "carrier": "CMA_CGM",
    "carrier_name": "CMA CGM",
    "priority": 90,
    "aliases": [
        "CMA CGM",
        "CMA_CGM",
        "COMPAGNIE GENERALE MARITIME",
        "CMA CGM S.A.",
    ],
    "match_rules": {
        "required_any": [
            "CMA CGM",
            "COMPAGNIE GENERALE MARITIME",
        ],
        "exclude_any": [
            "MAERSK", "MAEU", "MEDITERRANEAN SHIPPING",
            "HMM", "HYUNDAI",
            "ONE", "OCEAN NETWORK EXPRESS",
        ],
        "score_rules": [
            {"contains": "CMA CGM", "score": 35},
            {"contains": "COMPAGNIE GENERALE MARITIME", "score": 40},
            {"contains": "CMA CGM S.A.", "score": 30},
            {"contains": "CMDU", "score": 20},
            {"contains": "B/L NO.", "score": 10},
        ],
    },
    "subtemplates": {
        "BL": _CMA_BL_SUBTEMPLATES,
        "DO": _CMA_DO_SUBTEMPLATES,
    },
}


# ──────────────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────────────
def get_hmm_template_family() -> Dict[str, Any]:
    """HMM 템플릿 Family 반환"""
    return HMM_TEMPLATE_FAMILY


def get_cma_cgm_template_family() -> Dict[str, Any]:
    """CMA CGM 템플릿 Family 반환"""
    return CMA_CGM_TEMPLATE_FAMILY
