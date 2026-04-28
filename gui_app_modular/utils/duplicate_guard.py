"""
전역 중복 점검 유틸리티.

- 앱 전체 테이블을 순회하면서 식별 키 중복을 빠르게 탐지
- 오탐 방지를 위해 업무상 고유성이 강한 키만 검사
"""

from __future__ import annotations

import logging
from typing import Dict, List, Sequence, Tuple

logger = logging.getLogger(__name__)


_KEY_RULES: Dict[str, List[Tuple[str, ...]]] = {
    "inventory": [("lot_no",)],
    "inventory_tonbag": [("tonbag_uid",), ("uid",), ("lot_no", "sub_lt")],
    "shipment": [("sap_no",)],
    # allocation_plan은 LOT 중복이 정상적으로 발생할 수 있어(톤백/단계 분할),
    # 파일/배치 라인 기준 키만 점검한다.
    "allocation_plan": [
        ("source_fingerprint", "line_no"),
        ("import_batch_id", "line_no"),
    ],
    # stock_movement는 이력 테이블 — 동일 lot_no에 여러 이벤트(입고/출고/반품)가
    # 정상적으로 존재하므로 중복 검사 대상에서 제외한다.
    "stock_movement": [],
    # sold_table, picking_table도 동일 lot_no 다중 행이 정상
    "sold_table": [],
    "picking_table": [],
}

_GENERIC_KEYS: List[Tuple[str, ...]] = [
    ("tonbag_uid",),
    ("uid",),
    ("lot_no", "sub_lt"),
    ("lot_no",),
]


def _get_tables(db) -> List[str]:
    rows = db.fetchall(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """
    )
    return [str(r["name"] if isinstance(r, dict) else r[0]) for r in rows]


def _get_columns(db, table_name: str) -> List[str]:
    rows = db.fetchall(f"PRAGMA table_info('{table_name}')")
    cols: List[str] = []
    for row in rows:
        col = row["name"] if isinstance(row, dict) else row[1]
        cols.append(str(col))
    return cols


def _build_duplicate_query(table_name: str, key_cols: Sequence[str]) -> str:
    key_expr = ", ".join(key_cols)
    non_empty = " AND ".join([f"TRIM(COALESCE({c}, '')) != ''" for c in key_cols])
    return f"""
        SELECT {key_expr}, COUNT(*) AS cnt
        FROM {table_name}
        WHERE {non_empty}
        GROUP BY {key_expr}
        HAVING COUNT(*) > 1
        LIMIT 5
    """


def scan_duplicate_keys(db) -> List[str]:
    findings: List[str] = []
    for table in _get_tables(db):
        cols = set(_get_columns(db, table))
        rules = _KEY_RULES.get(table, _GENERIC_KEYS)
        for key_cols in rules:
            if not all(c in cols for c in key_cols):
                continue
            try:
                rows = db.fetchall(_build_duplicate_query(table, key_cols))
            except Exception as e:
                logger.debug(f"[dup-guard] query skip {table}/{key_cols}: {e}")
                continue
            for row in rows:
                values = [str(row[c] if isinstance(row, dict) else "") for c in key_cols]
                cnt = int(row["cnt"] if isinstance(row, dict) else row[-1])
                key_text = "+".join(key_cols)
                val_text = " | ".join(values)
                findings.append(f"{table} [{key_text}] 중복 {cnt}건: {val_text}")
    return findings
