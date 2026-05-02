import sqlite3, os, logging
from fastapi import APIRouter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrity", tags=["integrity"])


def _db_path():
    env = os.environ.get("SQM_TEST_DB_PATH")
    if env and os.path.exists(env): return env
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(root, "data", "db", "sqm_inventory.db")
    if not os.path.exists(p):
        b = os.path.join(root, "backup", "sqm_backup_20260421_232322.db")
        if os.path.exists(b): return b
    return p


def _db():
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/check")
async def integrity_check():
    try:
        conn = _db()
        total = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        rows = conn.execute(
            "SELECT lot_no, initial_weight, current_weight, picked_weight, "
            "ABS(initial_weight - (current_weight + picked_weight)) AS diff "
            "FROM inventory "
            "WHERE ABS(initial_weight - (current_weight + picked_weight)) > 1.0"
        ).fetchall()
        conn.close()
        error_list = [dict(r) for r in rows]
        return dict(
            success=True,
            message="정합성 검사 완료",
            data=dict(
                total=total,
                ok=total - len(error_list),
                error=len(error_list),
                details=error_list,
            )
        )
    except Exception as e:
        log.error("integrity_check error: %s", e)
        return dict(success=False, message=str(e), data=None)
