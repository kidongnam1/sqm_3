import sqlite3, os, logging, datetime
from fastapi import APIRouter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scan", tags=["scan"])


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


@router.post("/lookup")
async def scan_lookup(payload: dict):
    uid = (payload.get("uid") or payload.get("barcode") or "").strip()
    if not uid:
        return dict(success=False, message="uid 또는 barcode 필드 필요", data=None)
    try:
        conn = _db()
        row = conn.execute(
            "SELECT t.id, t.sub_lt, t.lot_no, t.sap_no, t.bl_no, "
            "t.tonbag_uid, t.tonbag_no, t.status, "
            "t.weight, t.location, t.inbound_date, t.picked_to AS container, "
            "i.product, i.status AS lot_status, i.warehouse "
            "FROM inventory_tonbag t "
            "LEFT JOIN inventory i ON i.lot_no = t.lot_no "
            "WHERE t.tonbag_uid = ? OR t.sub_lt = ? LIMIT 1",
            (uid, uid)
        ).fetchone()
        conn.close()
        if not row:
            return dict(success=False, message="바코드 없음: " + uid, data=None)
        data = dict(row)
        data["weight"] = float(data.get("weight") or 0)
        return dict(success=True,
                    message="LOT " + str(data.get("lot_no")) + " — " + str(data.get("status")),
                    data=data)
    except Exception as e:
        log.error("scan_lookup error: %s", e)
        return dict(success=False, message=str(e), data=None)


@router.post("/confirm_outbound")
async def scan_confirm_outbound(payload: dict):
    uid = (payload.get("uid") or payload.get("barcode") or "").strip()
    if not uid:
        return dict(success=False, message="uid 또는 barcode 필드 필요", data=None)
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id, sub_lt, lot_no, status FROM inventory_tonbag "
            "WHERE (tonbag_uid = ? OR sub_lt = ?) AND status = ? LIMIT 1",
            (uid, uid, "PICKED")
        ).fetchone()
        if not row:
            conn.close()
            return dict(success=False, message=uid + ": PICKED 상태 톤백 없음", data=None)
        r = dict(row)
        today = datetime.date.today().isoformat()
        conn.execute(
            "UPDATE inventory_tonbag SET status=?, sold_date=? WHERE id=?",
            ("SOLD", today, r["id"])
        )
        remaining = conn.execute(
            "SELECT COUNT(*) FROM inventory_tonbag "
            "WHERE lot_no=? AND status NOT IN (?,?,?,?)",
            (r["lot_no"], "SOLD", "OUTBOUND", "CONFIRMED", "SHIPPED")
        ).fetchone()[0]
        if remaining == 0:
            conn.execute("UPDATE inventory SET status=? WHERE lot_no=?", ("SOLD", r["lot_no"]))
        conn.commit()
        conn.close()
        return dict(success=True,
                    message=uid + " -> SOLD (LOT: " + str(r["lot_no"]) + ")",
                    data=dict(sub_lt=r["sub_lt"], lot_no=r["lot_no"], status="SOLD"))
    except Exception as e:
        log.error("scan_confirm_outbound error: %s", e)
        return dict(success=False, message=str(e), data=None)


@router.post("/return")
async def scan_return(payload: dict):
    uid = (payload.get("uid") or payload.get("barcode") or "").strip()
    reason = (payload.get("reason") or "").strip()
    if not uid:
        return dict(success=False, message="uid 또는 barcode 필드 필요", data=None)
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id, sub_lt, lot_no, status FROM inventory_tonbag "
            "WHERE (tonbag_uid = ? OR sub_lt = ?) AND status IN (?,?,?) LIMIT 1",
            (uid, uid, "OUTBOUND", "PICKED", "SOLD")
        ).fetchone()
        if not row:
            conn.close()
            return dict(success=False, message=uid + ": OUTBOUND/PICKED/SOLD 상태 없음", data=None)
        r = dict(row)
        prev = r["status"]
        today = datetime.date.today().isoformat()
        conn.execute(
            "UPDATE inventory_tonbag SET status=?, return_date=?, return_reason=? WHERE id=?",
            ("RETURN", today, reason, r["id"])
        )
        conn.commit()
        conn.close()
        return dict(success=True,
                    message=uid + ": " + prev + " -> RETURN (" + (reason or "없음") + ")",
                    data=dict(sub_lt=r["sub_lt"], lot_no=r["lot_no"], status="RETURN"))
    except Exception as e:
        log.error("scan_return error: %s", e)
        return dict(success=False, message=str(e), data=None)


@router.put("/move")
async def scan_move(payload: dict):
    uid = (payload.get("uid") or payload.get("barcode") or "").strip()
    to_loc = (payload.get("to_location") or payload.get("location") or "").strip()
    if not uid or not to_loc:
        return dict(success=False, message="uid/barcode 와 to_location 필드 필요", data=None)
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id, sub_lt, lot_no, location, status FROM inventory_tonbag "
            "WHERE tonbag_uid = ? OR sub_lt = ? LIMIT 1",
            (uid, uid)
        ).fetchone()
        if not row:
            conn.close()
            return dict(success=False, message="바코드 없음: " + uid, data=None)
        r = dict(row)
        prev = r.get("location") or "-"
        conn.execute("UPDATE inventory_tonbag SET location=? WHERE id=?", (to_loc, r["id"]))
        conn.commit()
        conn.close()
        return dict(success=True,
                    message=uid + ": " + prev + " -> " + to_loc + " 위치 변경 완료",
                    data=dict(sub_lt=r["sub_lt"], lot_no=r["lot_no"],
                              from_location=prev, to_location=to_loc, status=r["status"]))
    except Exception as e:
        log.error("scan_move error: %s", e)
        return dict(success=False, message=str(e), data=None)
