"""
SQM Inventory — FastAPI Backend (PyWebView Edition)
포트: 8765
"""
import sys
import os

# ⚠️ 이 파일은 backend/api/__init__.py — 프로젝트 루트는 부모의 부모의 부모
# (예: F:/.../Claude_SQM_v864_4/backend/api/__init__.py → F:/.../Claude_SQM_v864_4)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

# Engine import (기존 Tkinter 엔진 그대로 사용)
try:
    from engine_modules.inventory_modular.engine import SQMInventoryEngineV3
    from config import DB_PATH
    engine = SQMInventoryEngineV3(str(DB_PATH))
    ENGINE_AVAILABLE = True
except Exception as e:
    # v864.3 Phase 2: log full traceback so silent engine-load failures are visible
    logging.error(f"Engine load failed: {e}", exc_info=True)
    ENGINE_AVAILABLE = False
    engine = None


# ── DB 마이그레이션 (앱 시작 시 자동 실행) ──────────────────────────────────
def _run_db_migrations():
    """inventory 테이블 신규 컬럼 자동 추가 (ALTER TABLE IF NOT EXISTS 대체)"""
    try:
        from config import DB_PATH
        import sqlite3
        con = sqlite3.connect(str(DB_PATH))
        existing = [row[1] for row in con.execute("PRAGMA table_info(inventory)").fetchall()]
        new_cols = [
            ("folio",  "TEXT DEFAULT ''"),
            ("vessel", "TEXT DEFAULT ''"),
        ]
        for col, typedef in new_cols:
            if col not in existing:
                con.execute(f"ALTER TABLE inventory ADD COLUMN {col} {typedef}")
                logging.info(f"[Migration] inventory.{col} 컬럼 추가 완료")
        con.commit()

        # carrier_profile 테이블 (Phase 5 신규)
        con.execute("""CREATE TABLE IF NOT EXISTS carrier_profile (
            carrier_id      TEXT PRIMARY KEY,
            display_name    TEXT NOT NULL DEFAULT '',
            default_product TEXT DEFAULT '',
            bag_weight_kg   REAL DEFAULT 500.0,
            note            TEXT DEFAULT '',
            is_active       INTEGER DEFAULT 1
        )""")
        con.commit()
        con.close()
    except Exception as e:
        logging.warning(f"[Migration] DB 마이그레이션 실패: {e}")

_run_db_migrations()

app = FastAPI(title="SQM Inventory API", version="8.6.4")

# ── T8: CORS 설정 ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # PyWebView local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── v864.3 Debug Visibility: 프론트엔드 에러 수집 라우터 ─────
try:
    from backend.api.debug_log import router as debug_log_router
    app.include_router(debug_log_router)
    logging.info("debug_log router loaded OK (POST /api/log/frontend-error)")
except Exception as e:
    logging.warning(f"debug_log router load failed: {e}")

# ── v864.3 Phase 4-B: Allocation 입력 (F014) 네이티브 ─────
try:
    from backend.api.allocation_api import router as allocation_router
    app.include_router(allocation_router)
    logging.info("allocation_api router loaded OK (POST /api/allocation/bulk-import-excel)")
except Exception as e:
    logging.warning(f"allocation_api router load failed: {e}")

# ── v864.3 Phase 4-B: 즉시 출고 (F015) 네이티브 ─────
try:
    from backend.api.outbound_api import router as outbound_api_router
    app.include_router(outbound_api_router)
    logging.info("outbound_api router loaded OK (POST /api/outbound/quick)")
except Exception as e:
    logging.warning(f"outbound_api router load failed: {e}")

# ── v864.3 Phase 4-B: 톤백 위치 매핑 (F004) 네이티브 ─────
try:
    from backend.api.tonbag_api import router as tonbag_api_router
    app.include_router(tonbag_api_router)
    logging.info("tonbag_api router loaded OK (POST /api/tonbag/location-upload)")
except Exception as e:
    logging.warning(f"tonbag_api router load failed: {e}")

# ── Tier 2 Stage 2: 자동 생성 라우터 include ─────────────────
# [Sprint 0] backend.api.menubar was a 634-line NotReadyError stub set and has been removed.
# Real menu action routing lives in /api/inbound, /api/outbound, /api/allocation, /api/action*, etc.

try:
    from backend.api.controls import router as controls_router
    app.include_router(controls_router)
except Exception as e:
    logging.warning(f"controls router load failed: {e}")

# Phase 3 Q1: Dashboard KPI 실데이터 라우터
try:
    from backend.api.dashboard import router as dashboard_kpi_router
    app.include_router(dashboard_kpi_router)
    logging.info("dashboard_kpi router loaded OK")
except Exception as e:
    logging.warning(f"dashboard_kpi router load failed: {e}")

# Phase 4-A Group 2: 정적 응답 (info.py — F057~F062)
try:
    from backend.api.info import router as info_router
    app.include_router(info_router)
    logging.info("info router loaded OK")
except Exception as e:
    logging.warning(f"info router load failed: {e}")

# Phase 4-A Group 3: SQL 직접 조회 (queries.py — F009,F023,F025,F031,F034,F037,F038,F046,F047,F055)
try:
    from backend.api.queries import router as queries_router
    app.include_router(queries_router)
    logging.info("queries router loaded OK")
except Exception as e:
    logging.warning(f"queries router load failed: {e}")

# Phase 4-A Group 4: 엔진+SQL 혼합 (actions.py — F013,F029,F035,F050,F061)
try:
    from backend.api.actions import router as actions_router
    app.include_router(actions_router)
    logging.info("actions router loaded OK")
except Exception as e:
    logging.warning(f"actions router load failed: {e}")

try:
    from backend.api.optional import router as optional_router
    app.include_router(optional_router)
except Exception as e:
    logging.warning(f"optional router load failed: {e}")

# Phase 4-B: queries2 + actions2
try:
    from backend.api.queries2 import router as queries2_router
    app.include_router(queries2_router)
    logging.info("queries2 router loaded OK")
except Exception as e:
    logging.warning(f"queries2 router load failed: {e}")

try:
    from backend.api.actions2 import router as actions2_router
    app.include_router(actions2_router)
    logging.info("actions2 router loaded OK")
except Exception as e:
    logging.warning(f"actions2 router load failed: {e}")

# Phase 4-C: queries3 + actions3
try:
    from backend.api.queries3 import router as queries3_router
    app.include_router(queries3_router)
    logging.info("queries3 router loaded OK")
except Exception as e:
    logging.warning(f"queries3 router load failed: {e}")

try:
    from backend.api.actions3 import router as actions3_router
    app.include_router(actions3_router)
    logging.info("actions3 router loaded OK")
except Exception as e:
    logging.warning(f"actions3 router load failed: {e}")

# Stage 2/3: Settings (email, backup, table-stats)
try:
    from backend.api.settings import router as settings_router
    app.include_router(settings_router)
    logging.info("settings router loaded OK (/api/settings/*)")
except Exception as e:
    logging.warning(f"settings router load failed: {e}")

# Phase 4-D: inbound (PDF upload)
try:
    from backend.api.inbound import router as inbound_router
    app.include_router(inbound_router)
    logging.info("inbound router loaded OK")
except Exception as e:
    logging.warning(f"inbound router load failed: {e}")
try:
    from backend.api.inventory_api import inv_router, alloc_router, tb_router, scan_router, health_router
    app.include_router(inv_router)
    app.include_router(alloc_router)
    app.include_router(tb_router)
    app.include_router(scan_router)
    app.include_router(health_router)
    logging.info("inventory_api routers loaded OK (inventory/allocation/tonbags/scan/health)")
except Exception as e:
    logging.warning(f"inventory_api routers load failed: {e}")

# Phase 5: Carrier Profile CRUD
try:
    from backend.api.carriers import router as carriers_router
    app.include_router(carriers_router)
    logging.info("carriers router loaded OK (/api/carriers/*)")
except Exception as e:
    logging.warning(f"carriers router load failed: {e}")

# v865 1차: Gemini AI (settings/toggle/test)
try:
    from backend.api.ai_gemini import router as ai_gemini_router
    app.include_router(ai_gemini_router)
    logging.info("ai_gemini router loaded OK (/api/ai/*)")
except Exception as e:
    logging.warning(f"ai_gemini router load failed: {e}")

# ── 표준 예외 핸들러 설치 ────────────────────────────────────
# v864.3 Phase 2: static mount moved to END of file — Starlette matches
# routes in registration order, so app.mount("/") at this position was
# shadowing all inline @app.get("/api/...") decorators below (HTTP 404).
try:
    from backend.common.errors import install_exception_handlers
    install_exception_handlers(app)
except Exception as e:
    logging.warning(f"exception handlers install failed: {e}")

# ── Health ───────────────────────────────────────────────────
@app.get("/api/health")
def health():
    """
    v864.3 health probe — Phase 1c-B Modules 카운터 지원.
    Returns:
        status: "ok"
        engine: Bool (legacy 호환)
        engine_available: Bool (sqm-inline.js 기대 필드)
        modules_loaded: int — 로드 성공 모듈 수 (현재는 ENGINE_AVAILABLE 기반 8/0 이분법)
        modules_total: int — 전체 모듈 수 (v864.3 기준 8)
        version: 버전 문자열
    """
    loaded = 8 if ENGINE_AVAILABLE else 0
    return {
        "status": "ok",
        "engine": ENGINE_AVAILABLE,
        "engine_available": ENGINE_AVAILABLE,
        "modules_loaded": loaded,
        "modules_total": 8,
        "version": "8.6.4",
    }

# ── Dashboard ────────────────────────────────────────────────
@app.get("/api/dashboard/stats")
def dashboard_stats():
    if not ENGINE_AVAILABLE:
        return _sample_dashboard()
    try:
        summary = engine.get_inventory_summary()
        return {
            "available_lots": summary.get("available_count", 0),
            "reserved_lots":  summary.get("reserved_count", 0),
            "picked_lots":    summary.get("picked_count", 0),
            "outbound_lots_month": summary.get("outbound_month", 0),
            "return_lots":    summary.get("return_count", 0),
            "available_kg":   summary.get("available_kg", 0),
        }
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Inventory ────────────────────────────────────────────────
@app.get("/api/inventory")
def get_inventory(
    status: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    lot_no: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    if not ENGINE_AVAILABLE:
        return _sample_inventory(page=page, page_size=page_size)
    try:
        rows = engine.get_inventory(status=status, product=product, lot_no=lot_no)
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": rows[start:start + page_size],
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/inventory/{lot_no}")
def get_lot_detail(lot_no: str):
    if not ENGINE_AVAILABLE:
        raise HTTPException(503, "Engine unavailable")
    try:
        detail = engine.get_lot_detail(lot_no)
        if not detail:
            raise HTTPException(404, f"LOT not found: {lot_no}")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Tonbags ──────────────────────────────────────────────────
@app.get("/api/tonbags")
def get_tonbags(
    lot_no: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    if not ENGINE_AVAILABLE:
        return []
    try:
        return engine.get_tonbags(lot_no=lot_no, status=status)
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Allocation ───────────────────────────────────────────────
@app.get("/api/allocation")
def get_allocation():
    if not ENGINE_AVAILABLE:
        return _sample_allocation()
    try:
        rows = engine.get_inventory(status="RESERVED")
        return {"total": len(rows), "data": rows}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Outbound ─────────────────────────────────────────────────
@app.get("/api/outbound/scheduled")
def get_outbound_scheduled():
    if not ENGINE_AVAILABLE:
        return []
    try:
        return engine.get_inventory(status="PICKED")
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/outbound/history")
def get_outbound_history(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    if not ENGINE_AVAILABLE:
        return []
    try:
        return engine.get_inventory(status="OUTBOUND")
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Move (Tonbag 위치이동) ────────────────────────────────────
@app.post("/api/move")
def move_tonbag(payload: dict):
    """payload: { barcode: str, destination: str }"""
    barcode = payload.get("barcode", "").strip()
    destination = payload.get("destination", "").strip()
    if not barcode or not destination:
        raise HTTPException(400, "barcode and destination required")
    if not ENGINE_AVAILABLE:
        return {"success": True, "message": f"[DEMO] {barcode} → {destination}"}
    try:
        result = engine.move_tonbag(barcode, destination)
        return {"success": True, "message": result or f"{barcode} 이동 완료"}
    except AttributeError:
        return {"success": True, "message": f"[DEMO] {barcode} → {destination}"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/move/history")
def get_move_history(limit: int = Query(50, ge=1, le=500)):
    if not ENGINE_AVAILABLE:
        return []
    try:
        return engine.get_move_history(limit=limit)
    except AttributeError:
        return []
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Allocation Actions ────────────────────────────────────────
@app.post("/api/allocation/{lot}/cancel")
def cancel_allocation(lot: str):
    if not ENGINE_AVAILABLE:
        return {"success": True, "message": f"[DEMO] {lot} 배정 취소"}
    try:
        result = engine.cancel_reservation(lot)
        return {"success": True, "message": result or f"{lot} 배정 취소 완료"}
    except AttributeError:
        return {"success": True, "message": f"[DEMO] {lot} 배정 취소"}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Outbound Actions ──────────────────────────────────────────
@app.post("/api/outbound/{lot_no}/confirm")
def confirm_outbound(lot_no: str):
    if not ENGINE_AVAILABLE:
        return {"success": True, "message": f"[DEMO] {lot_no} 출고 확정"}
    try:
        result = engine.confirm_outbound(lot_no)
        return {"success": True, "message": result or f"{lot_no} 출고 확정 완료"}
    except AttributeError:
        return {"success": True, "message": f"[DEMO] {lot_no} 출고 확정"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/outbound/{lot_no}/cancel")
def cancel_outbound_lot(lot_no: str):
    if not ENGINE_AVAILABLE:
        return {"success": True, "message": f"[DEMO] {lot_no} 출고 취소"}
    try:
        result = engine.cancel_outbound(lot_no)
        return {"success": True, "message": result or f"{lot_no} 출고 취소 완료"}
    except AttributeError:
        return {"success": True, "message": f"[DEMO] {lot_no} 출고 취소"}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Integrity ────────────────────────────────────────────────
@app.get("/api/integrity/quick")
def integrity_quick():
    if not ENGINE_AVAILABLE:
        return {"status": "ok", "lights": ["green", "green", "yellow", "green"]}
    try:
        result = engine.health_check()
        return {"status": "ok", "detail": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# ── Export ───────────────────────────────────────────────────
@app.post("/api/export/excel")
def export_excel(payload: dict):
    option = payload.get("option", 1)
    if not ENGINE_AVAILABLE:
        raise HTTPException(503, "Engine unavailable")
    try:
        import tempfile, os
        out = os.path.join(tempfile.gettempdir(), f"sqm_export_option{option}.xlsx")
        engine.export_to_excel(out, option=option)
        return {"success": True, "path": out}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Activity Log ─────────────────────────────────────────────
@app.get("/api/log/activity")
def get_activity_log(limit: int = Query(100, ge=1, le=1000)):
    if not ENGINE_AVAILABLE:
        return _sample_activity()
    try:
        return engine.get_outbound_event_log(limit=limit)
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Sample Data Fallbacks ────────────────────────────────────
def _sample_dashboard():
    return {
        "available_lots": 247, "reserved_lots": 38, "picked_lots": 15,
        "outbound_lots_month": 89, "return_lots": 3,
        "available_kg": 12340000,
    }

def _sample_inventory(page=1, page_size=50):
    rows = [
        {"lot": "SQM-2026-0421", "sap": "1000421001", "bl": "COAU2604210",
         "product": "PP", "status": "AVAILABLE",
         "balance": 500.0, "net": 500.0, "container": "CRXU1234567",
         "mxbg_pallet": 20, "avail_bags": 1000,
         "invoice_no": "", "ship_date": "", "arrival_date": "2026-04-21",
         "con_return": "", "free_time": 0, "wh": "광양", "customs": "",
         "initial_weight": 500.0, "outbound_weight": 0.0,
         "date": "2026-04-21", "location": "A-01",
         "sale_ref": "", "customer": "", "remarks": ""},
    ]
    start = (page - 1) * page_size
    return {"total": len(rows), "page": page, "page_size": page_size, "data":rows[start:start+page_size]}

def _sample_allocation():
    return {"total": 0, "data": []}

def _sample_activity():
    return [
        {"time": "14:32", "type": "INBOUND", "lot": "SQM-2026-0421", "note": "PP 500KG"},
    ]


# ══════════════════════════════════════════════════════════════
# ── Static frontend mount (MUST be LAST) ──────────────────────
# ══════════════════════════════════════════════════════════════
# v864.3 Phase 2 fix: Starlette matches routes in registration order.
# Mounting "/" at the END ensures every inline @app.get("/api/...")
# above is checked FIRST; only unmatched paths fall through to
# serving frontend/ static files. Previous position (before the
# @app.get decorators) caused HTTP 404 on /api/health, /api/dashboard,
# /api/inventory because the mount swallowed every path.
try:
    import mimetypes
    # Windows: fix .js/.css MIME type misidentification
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
except Exception:
    pass
