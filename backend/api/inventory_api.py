"""
SQM v8.6.6 - Inventory / Allocation / Tonbag / Scan endpoints
GET  /api/inventory          사이드바 Inventory 탭 데이터
GET  /api/allocation         사이드바 Allocation 탭 데이터
GET  /api/tonbags            톤백 리스트
POST /api/scan/process       바코드 스캔 처리
GET  /api/health             시스템 헬스체크
"""
import sqlite3, os, sys, logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Query as QP, HTTPException, Body
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

# ─── 헬퍼 ────────────────────────────────────────────────────────────
def _db_path() -> str:
    # 테스트 모드: 환경변수 SQM_TEST_DB_PATH 우선 사용
    env_path = os.environ.get("SQM_TEST_DB_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main_path = os.path.join(root, "data", "db", "sqm_inventory.db")
    # 메인 DB가 없거나 백업 fallback 사용 (테스트 환경 보호)
    if not os.path.exists(main_path):
        backup = os.path.join(root, "backup", "sqm_backup_20260421_232322.db")
        if os.path.exists(backup):
            return backup
    return main_path

def _db() -> sqlite3.Connection:
    db = sqlite3.connect(_db_path(), timeout=10)
    db.row_factory = sqlite3.Row
    return db

def _rows(cur) -> list:
    return [dict(r) for r in cur.fetchall()]

# ─── 라우터 ──────────────────────────────────────────────────────────
inv_router  = APIRouter(prefix="/api/inventory",  tags=["inventory"])
alloc_router = APIRouter(prefix="/api/allocation", tags=["allocation"])
tb_router   = APIRouter(prefix="/api/tonbags",    tags=["tonbags"])
scan_router = APIRouter(prefix="/api/scan",       tags=["scan"])
health_router = APIRouter(prefix="/api",           tags=["health"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/inventory   — Inventory 탭 메인 데이터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@inv_router.get("")
def get_inventory(
    status: Optional[str] = QP(None),
    product: Optional[str] = QP(None),
    lot_no:  Optional[str] = QP(None),
    limit:   int = QP(200),
):
    try:
        db = _db()
        c  = db.cursor()
        sql = """
            SELECT
                i.lot_no        AS lot,
                i.sap_no        AS sap,
                i.bl_no         AS bl,
                i.product,
                i.status,
                ROUND(i.current_weight / 1000.0, 3) AS balance,
                ROUND(i.net_weight / 1000.0, 3)     AS net,
                i.container_no  AS container,
                i.mxbg_pallet,
                (SELECT COUNT(*) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.status = 'AVAILABLE' AND t.is_sample = 0
                ) AS avail_bags,
                -- v9.4: 톤백 레벨 상태별 무게 (MT)
                ROUND((SELECT COALESCE(SUM(t.weight),0) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.status = 'AVAILABLE' AND t.is_sample = 0
                ) / 1000.0, 3) AS avail_mt,
                ROUND((SELECT COALESCE(SUM(t.weight),0) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.status = 'RESERVED' AND t.is_sample = 0
                ) / 1000.0, 3) AS reserved_mt,
                ROUND((SELECT COALESCE(SUM(t.weight),0) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.status = 'PICKED' AND t.is_sample = 0
                ) / 1000.0, 3) AS picked_mt,
                (SELECT COUNT(*) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.status = 'AVAILABLE' AND t.is_sample = 0
                ) AS tb_avail,
                (SELECT COUNT(*) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.status = 'RESERVED' AND t.is_sample = 0
                ) AS tb_reserved,
                (SELECT COUNT(*) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.status = 'PICKED' AND t.is_sample = 0
                ) AS tb_picked,
                (SELECT COUNT(*) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.is_sample = 0
                ) AS total_bags,
                (SELECT COUNT(*) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.status IN ('SOLD','OUTBOUND','CONFIRMED','SHIPPED') AND t.is_sample = 0
                ) AS tb_sold,
                (SELECT COUNT(*) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.is_sample = 1
                   AND t.status IN ('AVAILABLE','RESERVED','PICKED','RETURN')
                ) AS sample_bags,
                ROUND((SELECT COALESCE(SUM(t.weight),0) FROM inventory_tonbag t
                 WHERE t.lot_no = i.lot_no AND t.is_sample = 1
                   AND t.status IN ('AVAILABLE','RESERVED','PICKED','RETURN')
                ) / 1000.0, 3) AS sample_weight_mt,
                i.salar_invoice_no AS invoice_no,
                i.ship_date,
                i.arrival_date,
                i.con_return,
                i.free_time,
                i.warehouse     AS wh,
                i.customs,
                ROUND(i.initial_weight / 1000.0, 3) AS initial_weight,
                ROUND((i.initial_weight - i.current_weight) / 1000.0, 3) AS outbound_weight,
                i.inbound_date  AS date,
                i.location,
                i.sale_ref,
                i.sold_to       AS customer,
                i.remarks,
                i.lot_sqm,
                i.product_code,
                i.vessel,
                i.voyage
            FROM inventory i
            WHERE 1=1
        """
        params = []
        if status:
            sql += " AND i.status = ?"
            params.append(status)
        if product:
            sql += " AND i.product LIKE ?"
            params.append(f"%{product}%")
        if lot_no:
            sql += " AND i.lot_no LIKE ?"
            params.append(f"%{lot_no}%")
        sql += " ORDER BY i.inbound_date DESC LIMIT ?"
        params.append(limit)
        rows = _rows(c.execute(sql, params))
        db.close()
        return rows
    except Exception as e:
        log.error(f"GET /api/inventory error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/inventory/{lot}/cancel  — 배정 취소
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@inv_router.post("/{lot_no}/cancel")
def cancel_inventory(lot_no: str):
    try:
        db = _db()
        db.execute(
            "UPDATE inventory SET status='STOCK', sale_ref=NULL, sold_to=NULL WHERE lot_no=?",
            (lot_no,)
        )
        db.commit(); db.close()
        return {"success": True, "message": f"{lot_no} 배정 취소 완료"}
    except Exception as e:
        log.error(f"cancel error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/allocation  — Allocation 탭 메인 데이터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@alloc_router.get("")
def get_allocation(
    status:  Optional[str] = QP(None),
    customer: Optional[str] = QP(None),
    limit:   int = QP(200),
):
    try:
        db = _db()
        c  = db.cursor()
        # allocation_plan 테이블 우선, 없으면 inventory SOLD 기준
        plan_count = c.execute("SELECT COUNT(*) FROM allocation_plan").fetchone()[0]
        if plan_count > 0:
            sql = """
                SELECT
                    ap.lot_no           AS lot,
                    i.product,
                    ap.customer,
                    ap.sale_ref,
                    ROUND(ap.qty_mt, 3) AS balance,
                    ap.outbound_date    AS ship_date,
                    ap.status,
                    ap.picking_no,
                    ap.workflow_status
                FROM allocation_plan ap
                LEFT JOIN inventory i ON i.lot_no = ap.lot_no
                WHERE 1=1
            """
            params = []
            if status:
                sql += " AND ap.status = ?"
                params.append(status)
            if customer:
                sql += " AND ap.customer LIKE ?"
                params.append(f"%{customer}%")
            sql += " ORDER BY ap.created_at DESC LIMIT ?"
            params.append(limit)
        else:
            # allocation_plan 비어있으면 inventory의 SOLD/RESERVED 기준
            sql = """
                SELECT
                    i.lot_no        AS lot,
                    i.product,
                    i.sold_to       AS customer,
                    i.sale_ref,
                    ROUND(i.current_weight/1000.0, 3) AS balance,
                    NULL            AS ship_date,
                    i.status,
                    NULL            AS picking_no,
                    NULL            AS workflow_status
                FROM inventory i
                WHERE i.status IN ('SOLD','RESERVED','PICKING','PICKED')
            """
            params = []
            if customer:
                sql += " AND i.sold_to LIKE ?"
                params.append(f"%{customer}%")
            sql += " ORDER BY i.inbound_date DESC LIMIT ?"
            params.append(limit)

        rows = _rows(c.execute(sql, params))
        db.close()
        return rows
    except Exception as e:
        log.error(f"GET /api/allocation error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/allocation/{lot}/cancel  — 배정 취소
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@alloc_router.post("/{lot_no}/cancel")
def cancel_allocation(lot_no: str):
    try:
        db = _db()
        db.execute(
            "UPDATE allocation_plan SET status='CANCELLED', cancelled_at=datetime('now') WHERE lot_no=?",
            (lot_no,)
        )
        db.commit(); db.close()
        return {"success": True, "message": f"{lot_no} 배정 취소"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [Sprint 1-1-D] PATCH /api/allocation/{lot_no} — 행 필드 업데이트
# v864-2 AllocationDialog 인라인 편집 워크플로우 포팅
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_ALLOC_EDITABLE_FIELDS = {
    "customer", "sale_ref", "qty_mt", "outbound_date", "status",
}


@alloc_router.patch("/{lot_no}")
def update_allocation(lot_no: str, updates: Dict[str, Any] = Body(...)):
    """
    allocation_plan 행의 허용된 필드를 업데이트.
    Body: {field_name: value, ...}

    허용 필드: customer, sale_ref, qty_mt, outbound_date, status
    (lot_no/sap_no/product 는 외래키·조인 영향으로 편집 불허)
    """
    fields = {k: v for k, v in (updates or {}).items() if k in _ALLOC_EDITABLE_FIELDS}
    if not fields:
        raise HTTPException(
            400,
            f"허용된 필드 없음. 편집 가능: {sorted(_ALLOC_EDITABLE_FIELDS)}"
        )
    # qty_mt 는 numeric 강제
    if "qty_mt" in fields:
        try:
            fields["qty_mt"] = float(fields["qty_mt"])
        except (TypeError, ValueError):
            raise HTTPException(400, "qty_mt 는 숫자여야 합니다")
    sets = ", ".join(f"{k}=?" for k in fields.keys())
    values = list(fields.values()) + [lot_no]
    try:
        db = _db()
        cursor = db.execute(
            f"UPDATE allocation_plan SET {sets}, updated_at=datetime('now') WHERE lot_no=?",
            values
        )
        if cursor.rowcount == 0:
            db.close()
            raise HTTPException(404, f"allocation_plan 에서 {lot_no} 찾지 못함")
        db.commit(); db.close()
        return {"success": True, "lot_no": lot_no, "updated_fields": list(fields.keys())}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"PATCH /api/allocation/{lot_no} error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [Sprint 1-1-E] POST /api/allocation/{lot_no}/pick — RESERVED → PICKED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@alloc_router.post("/{lot_no}/pick")
def pick_allocation(lot_no: str):
    """배정 → 출고 실행 (RESERVED → PICKED)."""
    try:
        db = _db()
        cursor = db.execute(
            """UPDATE allocation_plan
               SET status='PICKED', picked_at=datetime('now')
               WHERE lot_no=? AND status='RESERVED'""",
            (lot_no,)
        )
        changes = cursor.rowcount
        db.commit(); db.close()
        if changes == 0:
            raise HTTPException(404, f"{lot_no}: RESERVED 상태가 아니거나 존재하지 않음")
        return {"success": True, "lot_no": lot_no, "message": f"{lot_no} → PICKED"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"POST /api/allocation/{lot_no}/pick error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [Sprint 1-1-E] POST /api/allocation/{lot_no}/confirm — PICKED → SOLD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@alloc_router.post("/{lot_no}/confirm")
def confirm_allocation(lot_no: str):
    """출고 확정 (PICKED → SOLD)."""
    try:
        db = _db()
        cursor = db.execute(
            """UPDATE allocation_plan
               SET status='SOLD', confirmed_at=datetime('now')
               WHERE lot_no=? AND status='PICKED'""",
            (lot_no,)
        )
        changes = cursor.rowcount
        # inventory 테이블 상태도 SOLD 로
        db.execute(
            "UPDATE inventory SET status='SOLD' WHERE lot_no=?",
            (lot_no,)
        )
        db.commit(); db.close()
        if changes == 0:
            raise HTTPException(404, f"{lot_no}: PICKED 상태가 아니거나 존재하지 않음")
        return {"success": True, "lot_no": lot_no, "message": f"{lot_no} → SOLD"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"POST /api/allocation/{lot_no}/confirm error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [Sprint 1-1-E] POST /api/allocation/{lot_no}/reset — LOT 배정 초기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@alloc_router.post("/{lot_no}/reset")
def reset_allocation(lot_no: str):
    """
    LOT 배정 완전 초기화.
    - allocation_plan 에서 해당 lot_no 행 DELETE
    - inventory 테이블 status 를 AVAILABLE 로 원복 (SOLD 가 아닌 경우만)
    """
    try:
        db = _db()
        # inventory status 가 이미 SOLD 면 보호 (출고 완료된 건 reset 불가)
        row = db.execute("SELECT status FROM inventory WHERE lot_no=?", (lot_no,)).fetchone()
        if row and row[0] == "SOLD":
            raise HTTPException(409, f"{lot_no}: SOLD 상태는 reset 불가 (반품으로 처리하세요)")
        del_cur = db.execute("DELETE FROM allocation_plan WHERE lot_no=?", (lot_no,))
        deleted = del_cur.rowcount
        db.execute(
            "UPDATE inventory SET status='AVAILABLE', sold_to=NULL, sale_ref=NULL WHERE lot_no=? AND status!='SOLD'",
            (lot_no,)
        )
        db.commit(); db.close()
        if deleted == 0:
            return {"success": True, "lot_no": lot_no, "message": f"{lot_no}: 배정 기록 없음 (inventory만 초기화)"}
        return {"success": True, "lot_no": lot_no, "message": f"{lot_no} 배정 완전 초기화 ({deleted}건 삭제)"}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"POST /api/allocation/{lot_no}/reset error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/tonbags     — 톤백 리스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@tb_router.get("")
def get_tonbags(
    lot_no:  Optional[str] = QP(None),
    status:  Optional[str] = QP(None),
    limit:   int = QP(300),
):
    try:
        db = _db()
        c  = db.cursor()
        sql = """
            SELECT
                t.sub_lt,
                t.lot_no,
                t.sap_no,
                t.bl_no,
                t.inbound_date,
                ROUND(t.weight / 1000.0, 3) AS weight,
                t.status,
                t.location,
                t.picked_to     AS container,
                i.product,
                t.tonbag_uid,
                t.tonbag_no,
                COALESCE(t.is_sample, 0) AS is_sample
            FROM inventory_tonbag t
            LEFT JOIN inventory i ON i.lot_no = t.lot_no
            WHERE 1=1
        """
        params = []
        if lot_no:
            sql += " AND t.lot_no LIKE ?"
            params.append(f"%{lot_no}%")
        if status:
            sql += " AND t.status = ?"
            params.append(status)
        sql += " ORDER BY t.inbound_date DESC, t.sub_lt LIMIT ?"
        params.append(limit)
        rows = _rows(c.execute(sql, params))
        db.close()
        return rows
    except Exception as e:
        log.error(f"GET /api/tonbags error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/scan/process  — 바코드 스캔 처리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@scan_router.post("/process")
def scan_process(payload: dict):
    barcode = (payload.get("barcode") or "").strip()
    action  = (payload.get("action") or "lookup").strip()
    if not barcode:
        raise HTTPException(400, "barcode is required")
    try:
        db = _db()
        c  = db.cursor()
        # sub_lt 또는 tonbag_uid로 조회
        row = c.execute("""
            SELECT t.*, i.product, i.status AS lot_status
            FROM inventory_tonbag t
            LEFT JOIN inventory i ON i.lot_no = t.lot_no
            WHERE t.sub_lt = ? OR t.tonbag_uid = ?
        """, (barcode, barcode)).fetchone()

        if not row:
            db.close()
            return {"success": False, "message": f"바코드를 찾을 수 없음: {barcode}"}

        r = dict(row)
        if action == "lookup":
            db.close()
            return {
                "success": True,
                "message": f"LOT {r.get('lot_no')} / {r.get('sub_lt')} — 위치: {r.get('location','-')}",
                "data": r
            }
        elif action == "outbound":
            db.execute(
                "UPDATE inventory_tonbag SET status='PICKED', picked_date=date('now') WHERE sub_lt=?",
                (barcode,)
            )
            db.commit()
            db.close()
            return {"success": True, "message": f"{barcode} 출고 처리 완료", "data": r}
        else:
            db.close()
            return {"success": True, "message": f"{barcode} 조회 완료", "data": r}
    except Exception as e:
        log.error(f"scan process error: {e}")
        raise HTTPException(500, str(e))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POST /api/scan/bulk-upload  — 바코드 스캔 결과 CSV/Excel 업로드 (Stage 3)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from fastapi import UploadFile, File as FileField
import io, pathlib as _pathlib

@scan_router.post("/bulk-upload")
async def scan_bulk_upload(file: UploadFile = FileField(...), action: str = "lookup"):
    """
    CSV/Excel 파일 업로드 → tonbag_uid / sub_lt 일괄 조회.
    action=lookup: 조회만 / action=outbound|return|pick|available: 상태 전환
    """
    try:
        content = await file.read()
        ext = _pathlib.Path(file.filename or "upload.csv").suffix.lower()
        try:
            import pandas as pd
        except ImportError:
            return {"ok": False, "message": "pandas not installed"}
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(content), header=0, dtype=str)
        else:
            try:
                df = pd.read_csv(io.StringIO(content.decode("utf-8")), header=0, dtype=str)
            except Exception:
                df = pd.read_csv(io.StringIO(content.decode("cp949", errors="replace")), header=0, dtype=str)
        df.columns = [str(c).strip().lower() for c in df.columns]
        uid_col = None
        for cand in ["tonbag_uid", "uid", "sub_lt", "barcode", "scan_id", df.columns[0]]:
            if cand in df.columns:
                uid_col = cand
                break
        if uid_col is None:
            return {"ok": False, "message": "인식 가능한 UID 컬럼 없음 (tonbag_uid / sub_lt / barcode)"}
        uids = df[uid_col].dropna().str.strip().unique().tolist()
        if not uids:
            return {"ok": False, "message": "유효한 UID 없음"}
        db = _db()
        results = []
        for uid in uids:
            row = db.execute("""
                SELECT t.id, t.sub_lt, t.lot_no, t.tonbag_uid, t.status,
                       t.weight, t.location, i.product, i.warehouse
                FROM inventory_tonbag t
                LEFT JOIN inventory i ON i.lot_no = t.lot_no
                WHERE t.tonbag_uid = ? OR t.sub_lt = ?
                LIMIT 1
            """, (uid, uid)).fetchone()
            if row:
                r = dict(row)
                r["input_uid"] = uid
                r["matched"] = True
                if action != "lookup":
                    STATUS_TRANS = {
                        "outbound": ("PICKED", "OUTBOUND"),
                        "return": ("OUTBOUND", "RETURN"),
                        "pick": ("AVAILABLE", "PICKED"),
                        "available": (None, "AVAILABLE"),
                    }
                    trans = STATUS_TRANS.get(action.lower())
                    if trans:
                        src, dst = trans
                        if src is None or r.get("status") == src:
                            db.execute("UPDATE inventory_tonbag SET status=? WHERE id=?", (dst, r["id"]))
                            r["status_changed"] = f"{src or '*'} -> {dst}"
                r["weight"] = float(r.get("weight") or 0)
            else:
                r = {"input_uid": uid, "matched": False, "lot_no": None, "status": None, "weight": 0}
            results.append(r)
        db.commit()
        db.close()
        matched = sum(1 for r in results if r.get("matched"))
        not_matched = len(results) - matched
        return {"ok": True, "message": f"처리 완료: {matched} 매칭 / {not_matched} 미매칭",
                "results": results, "matched_count": matched, "not_matched_count": not_matched, "action": action}
    except HTTPException:
        raise
    except Exception as e:
        log.exception("scan bulk-upload error: %s", e)
        return {"ok": False, "message": str(e)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/health       — 헬스체크
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@health_router.get("/health")
def health_check():
    try:
        db = _db()
        c  = db.cursor()
        lots  = c.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        tbags = c.execute("SELECT COUNT(*) FROM inventory_tonbag").fetchone()[0]
        db.close()
        return {
            "status": "ok",
            "lots": lots,
            "tonbags": tbags,
            "engine_count": lots
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "engine_count": 0}
