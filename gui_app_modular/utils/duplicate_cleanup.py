# -*- coding: utf-8 -*-
"""duplicate_cleanup.py - 중복 데이터 정리 유틸 (운영 안전용)

⚠️ 기본 정책(루비안)
- 자동 삭제는 '명확한 식별키' 중복만 대상으로 한다.
- allocation_plan 의 (source_fingerprint, line_no) / (import_batch_id, line_no) 중복은
  '같은 파일 라인이 여러 번 적재'된 경우가 많아 정리 대상이 된다.
- 항상 '가장 먼저 들어온 1건(rowid 최소)'만 남기고 나머지를 제거한다.

사용 예(엔진 db 객체가 있을 때):
    from gui_app_modular.utils.duplicate_cleanup import cleanup_allocation_plan_duplicates
    result = cleanup_allocation_plan_duplicates(engine.db)
"""

from __future__ import annotations

from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

def _table_has_columns(db, table: str, cols: Tuple[str, ...]) -> bool:
    try:
        rows = db.fetchall(f"PRAGMA table_info('{table}')")
        existing = { (r['name'] if isinstance(r, dict) else r[1]) for r in rows }
        return all(c in existing for c in cols)
    except Exception:
        return False

def cleanup_duplicates_keep_first(db, table: str, key_cols: Tuple[str, ...]) -> int:
    """key_cols로 그룹핑하여 rowid 최소 1건만 남기고 나머지 삭제. 삭제 건수 반환."""
    if not _table_has_columns(db, table, key_cols):
        return 0
    key_expr = ", ".join(key_cols)
    non_empty = " AND ".join([f"TRIM(COALESCE({c}, '')) != ''" for c in key_cols])

    # 삭제 대상 rowid를 먼저 뽑아서 삭제 (안전/가시성)
    sql_ids = f"""
        SELECT rowid
        FROM {table}
        WHERE {non_empty}
          AND rowid NOT IN (
              SELECT MIN(rowid)
              FROM {table}
              WHERE {non_empty}
              GROUP BY {key_expr}
          )
    """
    rows = db.fetchall(sql_ids)
    ids = [ (r['rowid'] if isinstance(r, dict) else r[0]) for r in rows ]
    if not ids:
        return 0

    # chunk delete
    deleted = 0
    for i in range(0, len(ids), 500):
        chunk = ids[i:i+500]
        placeholders = ",".join(["?"]*len(chunk))
        db.execute(f"DELETE FROM {table} WHERE rowid IN ({placeholders})", chunk)
        deleted += len(chunk)
    return deleted

def cleanup_allocation_plan_duplicates(db) -> Dict[str, int]:
    """allocation_plan 중복 정리. 삭제 수를 rule별로 반환."""
    results: Dict[str, int] = {}
    if not _table_has_columns(db, "allocation_plan", ("source_fingerprint", "line_no")):
        return results

    # (source_fingerprint, line_no)
    n1 = cleanup_duplicates_keep_first(db, "allocation_plan", ("source_fingerprint", "line_no"))
    results["allocation_plan[source_fingerprint+line_no]"] = n1

    # (import_batch_id, line_no) - 있으면
    if _table_has_columns(db, "allocation_plan", ("import_batch_id", "line_no")):
        n2 = cleanup_duplicates_keep_first(db, "allocation_plan", ("import_batch_id", "line_no"))
        results["allocation_plan[import_batch_id+line_no]"] = n2

    if any(results.values()):
        try:
            db.commit()
        except Exception:
            logger.debug("[SUPPRESSED] exception in duplicate_cleanup.py")  # noqa
    return results
