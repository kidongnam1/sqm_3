# -*- coding: utf-8 -*-
"""피킹리스트 첫 행 검수 보조 유틸"""
from __future__ import annotations

from typing import Any


def extract_first_picking_row(doc: dict[str, Any]) -> dict[str, Any]:
    items = doc.get("items", []) or []
    if not items:
        return {
            "LOT_NO": "",
            "QTY": "",
            "UNIT": "",
            "LOCATION": "",
            "IS_SAMPLE": "",
        }
    row = items[0]
    return {
        "LOT_NO": row.get("lot_no", ""),
        "QTY": row.get("qty_kg", row.get("qty_mt", "")),
        "UNIT": row.get("unit", ""),
        "LOCATION": row.get("storage_location", ""),
        "IS_SAMPLE": "Y" if row.get("is_sample") else "",
    }


def build_picking_mapping_profile(doc: dict[str, Any]) -> dict[str, str]:
    return {
        "column_1": "LOT_NO",
        "column_2": "QTY",
        "column_3": "UNIT",
        "column_4": "LOCATION",
        "column_5": "IS_SAMPLE",
    }
