# -*- coding: utf-8 -*-
"""
carrier_templates/msc.py — SQM v8.0.6 PATCH
=============================================
MSC(Mediterranean Shipping Company) 선사 템플릿 2 정의

설계 원칙:
  - 기존 bl_carrier_registry.py의 MSC CarrierTemplate 설정과 호환
  - BL = Sea Waybill 구조 (RIDER PAGE 주의)
  - DO는 샘플 미확보 상태 → generic 규칙 적용 후 수동 검수 권장

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations
from typing import Any, Dict, List


# ─────────────────────────────────────────────────────────────────
# BL 서브템플릿 목록 (우선순위 순)
# ─────────────────────────────────────────────────────────────────
_MSC_BL_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "MSC_BL_V1",
        "doc_type": "BL",
        "priority": 100,
        "title_keywords": [
            "MEDITERRANEAN SHIPPING COMPANY",
            "SEA WAYBILL No.",
            "MSC CHILE",
            "MSC ",
        ],
        "match_rules": {
            "required_any": [
                "MEDITERRANEAN SHIPPING COMPANY",
                "SEA WAYBILL No.",
            ],
            "exclude_any": [
                "MAERSK",
                "MAEU",
                "D/O 발급확인서",
                "DELIVERY ORDER",
            ],
        },
        "field_rules": {
            "bl_no": {
                # MSC: 1페이지 첫 줄 끝에 위치 (예: MEDUFP963996)
                "label_aliases": ["SEA WAYBILL No.", "B/L No.", "SEA WAYBILL NUMBER"],
                "type": "text",
                "required": True,
                # MSC는 BL No가 라벨 오른쪽이 아닌 같은 줄 끝에 있음
                "extract_rule": "same_line_end",
            },
            "booking_no": {
                "label_aliases": ["Booking No.", "Booking Number"],
                "type": "text",
            },
            "vessel": {
                "label_aliases": ["Vessel", "Ocean Vessel", "Vessel Name"],
                "type": "text",
            },
            "voyage_no": {
                "label_aliases": ["Voyage No.", "Voyage"],
                "type": "text",
            },
            "shipper": {
                "label_aliases": ["Shipper", "Shipper/Exporter"],
                "type": "block_text",
            },
            "consignee": {
                "label_aliases": ["Consignee"],
                "type": "block_text",
            },
            "notify_party": {
                "label_aliases": ["Notify Party", "Notify Address"],
                "type": "block_text",
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
                # ★ MSC 주의: Rider Page(2~3페이지)의 컨테이너 번호가 BL No로 오탐될 수 있음
                "anchor_keywords": [
                    "Container No",
                    "Seal No",
                    "KGS",
                    "CBM",
                    "ML-CL",
                ],
                "type": "table",
                "page_scope": "page0",  # 1페이지만 사용 (Rider Page 제외)
            },
            "gross_weight_total": {
                "label_aliases": ["Total Gross Weight", "GROSS WEIGHT"],
                "type": "number",
            },
            "sap_no": {
                # MSC SAP는 Rider Page(2~3페이지)에 위치
                "label_aliases": ["SAP", "SAP NO", "SAP No."],
                "type": "text",
                "page_scope": "page1_to_2",
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
            "sap_no",
        ],
        "normalizers": {
            "bl_no": "strip_upper",
            "booking_no": "strip",
            "vessel": "strip_upper",
            "voyage_no": "strip_upper",
            "port_of_discharge": "strip_upper",
            "first_container_no": "container_no_upper",
            "gross_weight_total": "number_only",
            "sap_no": "strip",
        },
        "gemini_hint": (
            "【MSC Sea Waybill 전용 규칙】\n"
            "BL No 위치: 1페이지 상단 맨 첫 번째 줄 끝에 있습니다.\n"
            "형식 예시: MEDUFP963996 (MEDU로 시작하는 알파벳+숫자 혼합)\n"
            "⚠️ 주의: Rider Page(2~3페이지)에 컨테이너 번호(MSNU..., TCLU...)가 있는데 "
            "이것은 BL No가 아닙니다. 절대 혼동하지 마세요.\n"
            "⚠️ SAP NO는 Rider Page(2~3페이지)에 있음\n"
            "⚠️ 'SEA WAYBILL No.'가 여러 번 등장하면 반드시 1페이지 것만 사용하세요."
        ),
        # 기존 bl_carrier_registry 호환 플래그
        "_bl_page_scope": "page0",
        "_sap_page_hint": "page1_to_2",
        "_bl_extract_pattern": (
            r"MEDITERRANEAN SHIPPING COMPANY.*?SEA WAYBILL No\.\s+(\w{6,20})"
        ),
        "_bl_format_hint": "MEDUFP963996",
    },
]

# ─────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────
# DO 서브템플릿 목록 (MSC DO — v8.2.4: 실제 샘플 3종 기반 업데이트)
# MEDUFP963988 / MEDUFP963996 / MEDUFP963970 분석 결과 반영
# ─────────────────────────────────────────────────────────────────
_MSC_DO_SUBTEMPLATES: List[Dict[str, Any]] = [
    {
        "template_id": "MSC_DO_V2",
        "doc_type": "DO",
        "priority": 100,   # v8.2.4: 실제 샘플 확보 → priority 상향
        "title_keywords": [
            "화물인도지시서",
            "D/O No.",
            "MEDITERRANEAN SHIPPING",
            "MSC",
            "MEDU",
        ],
        "match_rules": {
            "required_any": [
                "화물인도지시서",
                "MEDITERRANEAN SHIPPING",
                "MSC",
            ],
            "exclude_any": [
                "SEA WAYBILL No.",
                "MAERSK",
                "NON-NEGOTIABLE",
            ],
        },
        "field_rules": {
            # D/O 번호: 예) 26032314BIQL / 260323140MBF / 26032314Y6OD
            "do_no": {
                "label_aliases": ["D/O No.", "DO No.", "D/O NO."],
                "type": "text",
                "required": True,
            },
            # B/L 번호: MEDU로 시작하는 알파숫자 혼합
            "bl_no": {
                "label_aliases": ["Sea Waybill No.", "SEA WAYBILL No.", "B/L No."],
                "type": "text",
                "required": True,
                "pattern": r"(?:MEDU|MSCU)[A-Z0-9]{6,10}",
            },
            # 선박명
            "ocean_vessel": {
                "label_aliases": ["Ocean Vessel", "Vessel", "선박명"],
                "type": "text",
            },
            # 항차
            "voyage_no": {
                "label_aliases": ["Voyage No.", "Voyage"],
                "type": "text",
            },
            # 수하인
            "consignee": {
                "label_aliases": ["Consignee", "수하인"],
                "type": "block_text",
            },
            # 선적항
            "port_of_loading": {
                "label_aliases": ["Port of Loading", "선적항"],
                "type": "text",
            },
            # 양하항
            "port_of_discharge": {
                "label_aliases": ["Port of Discharge", "양하항"],
                "type": "text",
            },
            # 입항일: (For Local Use) 섹션 — "선박 입항일" 아래 (MRN/MSN 사이에 위치)
            "arrival_date": {
                "label_aliases": ["선박 입항일", "입항일", "Arrival Date"],
                "type": "date",
                "section": "for_local_use",  # 하단 (For Local Use) 섹션
                "note": "MRN/MSN 라벨 사이에 위치 — 5줄 후에 나타남",
            },
            # 발행일
            "issue_date": {
                "label_aliases": ["발행일", "Issue Date"],
                "type": "date",
                "section": "for_local_use",
            },
            # MRN / MSN (한국 세관 신고번호)
            "mrn": {
                "label_aliases": ["MRN", "MRN/MSN"],
                "type": "text",
                "pattern": r"\d{2}MSCU\d{4}[A-Z]",
            },
            "msn": {
                "label_aliases": ["MSN"],
                "type": "text",
                "pattern": r"\d{4}",
            },
            # 컨테이너 표 (중앙)
            "container_table": {
                "anchor_keywords": [
                    "Container No.", "Container No", "컨테이너번호",
                    "Seal No.", "Seal No", "씰번호",
                    "Gross Weight", "중량",
                ],
                "type": "table",
            },
            # 반납기한 표 (하단)
            "free_time_table": {
                "anchor_keywords": [
                    "반납기한", "반납일", "FREE TIME",
                    "Return Deadline", "CY Return",
                ],
                "type": "table",
            },
            # 총 중량
            "gross_weight_total": {
                "label_aliases": [
                    "Gross Weight(KGS)", "Gross Weight", "총중량", "TOTAL"
                ],
                "type": "number",
            },
            # 창고 코드 (광양항서부컨테이너터미널 등)
            "warehouse_name": {
                "label_aliases": ["창고", "CY", "반납지", "Return Yard"],
                "type": "text",
            },
        },
        "preview_fields": [
            "do_no",
            "bl_no",
            "ocean_vessel",
            "voyage_no",
            "consignee",
            "arrival_date",
            "issue_date",
            "first_container_no",
            "gross_weight_total",
            "first_free_time",
            "mrn",
            "msn",
        ],
        "normalizers": {
            "do_no":               "strip",
            "bl_no":               "strip_upper",
            "ocean_vessel":        "strip_upper",
            "voyage_no":           "strip_upper",
            "first_container_no":  "container_no_upper",
            "gross_weight_total":  "number_only",
            "first_free_time":     "date_yyyy_mm_dd",
            "arrival_date":        "date_yyyy_mm_dd",
            "issue_date":          "date_yyyy_mm_dd",
        },
        "gemini_hint": (
            "【MSC D/O 화물인도지시서 전용 — 실제 샘플 3종 기반】\n"
            "\n"
            "■ D/O No 위치: 상단 'D/O No.' 라벨 바로 오른쪽\n"
            "  예시: 26032314BIQL / 260323140MBF / 26032314Y6OD\n"
            "\n"
            "■ B/L No (Sea Waybill No): MEDU로 시작하는 알파숫자 혼합\n"
            "  예시: MEDUFP963988 / MEDUFP963996 / MEDUFP963970\n"
            "  ⚠️ 컨테이너 번호(MSNU, TCLU 등 4글자+7숫자)와 혼동 금지!\n"
            "\n"
            "■ 선박 입항일 위치: 문서 하단 '(For Local Use)' 섹션\n"
            "  구조: 선박 입항일 → (빈줄) → 3. → MRN → / → MSN → [날짜]\n"
            "  ⚠️ 날짜는 '선박 입항일' 라벨에서 5~7줄 아래에 있음!\n"
            "  예시: 2026-03-21\n"
            "\n"
            "■ 발행일: '선박 입항일' 아래 '2.' 다음 줄\n"
            "  예시: 2026-03-23\n"
            "\n"
            "■ MRN/MSN: '3.' 다음 줄에 슬래시(/) 구분\n"
            "  예시: 26MSCU3082I / 0001\n"
            "\n"
            "■ 컨테이너 번호: [A-Z]{4}\\d{7} 형식 (예: MSCU1234567)\n"
            "■ 씰 번호: ML-CL로 시작 (예: ML-CL1234567)\n"
            "■ 반납기한: 2026-04-04 형식 (컨테이너마다 동일)\n"
            "■ 총중량: 123,150 KGS (6개 컨테이너 합계)\n"
            "\n"
            "★ 반드시 arrival_date(선박 입항일)를 추출하세요. NOT_FOUND 금지!"
        ),
    },
]

# ─────────────────────────────────────────────────────────────────
# MSC 템플릿 Family (Template 2)
# ─────────────────────────────────────────────────────────────────
MSC_TEMPLATE_FAMILY: Dict[str, Any] = {
    "family_id": "TEMPLATE_2_MSC",
    "carrier": "MSC",
    "carrier_name": "Mediterranean Shipping Company",
    "priority": 100,
    "aliases": [
        "MSC",
        "MEDITERRANEAN SHIPPING COMPANY",
        "MEDITERRANEAN SHIPPING",
        "MSC CHILE",
    ],
    "match_rules": {
        "required_any": [
            "MEDITERRANEAN SHIPPING COMPANY",
            "SEA WAYBILL No.",
            "MSC CHILE",
        ],
        "exclude_any": [
            "MAERSK",
            "MAEU",
            "MAERSK LINE",
            "CMA CGM",
            "HMM",
            "ONE",
        ],
        "score_rules": [
            {"contains": "MEDITERRANEAN SHIPPING COMPANY", "score": 40},
            {"contains": "SEA WAYBILL No.", "score": 30},
            {"contains": "MSC CHILE", "score": 20},
            {"contains": "MSC ", "score": 15},
            {"contains": "MEDUFP", "score": 25},
            {"contains": "MEDU", "score": 20},
            {"contains": "B/L NO.", "score": 10},
        ],
    },
    "subtemplates": {
        "BL": _MSC_BL_SUBTEMPLATES,
        "DO": _MSC_DO_SUBTEMPLATES,
    },
}


def get_msc_template_family() -> Dict[str, Any]:
    """MSC 템플릿 Family 반환 (template_registry 등록용)"""
    return MSC_TEMPLATE_FAMILY
