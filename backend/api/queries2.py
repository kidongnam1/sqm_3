"""
SQM v864.3 — Phase 4-B SQL 조회 엔드포인트
queries2.py: report-daily, report-monthly, recent-files,
             return-stats, outbound-confirm-list, detail-outbound

모든 응답: ok_response(data=...) 표준 포맷
"""
import os
import sqlite3
import logging
from datetime import date, datetime
from fastapi import APIRouter, Query as QP
from backend.common.errors import ok_response, err_response

router = APIRouter(prefix="/api/q2", tags=["queries2"])
logger = logging.getLogger(__name__)


# ── DB 경로 헬퍼 ─────────────────────────────────────────────────
def _db() -> sqlite3.Connection:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    db_path = os.path.join(root, "data", "db", "sqm_inventory.db")
    con = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=3000")
    return con


def _rows(rows) -> list:
    return [dict(r) for r in rows]


# ── 일일 보고서 ──────────────────────────────────────────────────
@router.get("/report-daily", summary="📅 일일 보고서 (F049)")
def get_report_daily(target_date: str = QP(None, description="YYYY-MM-DD, 기본 오늘")):
    """오늘(또는 지정일) 입출고 현황 요약"""
    try:
        d = target_date or date.today().isoformat()
        con = _db()

        # 입고 건수/중량
        inbound = con.execute("""
            SELECT COUNT(*) AS cnt,
                   ROUND(SUM(qty_kg)/1000.0, 3) AS total_mt
            FROM stock_movement
            WHERE movement_type='INBOUND'
              AND DATE(COALESCE(movement_date, created_at)) = ?
        """, (d,)).fetchone()

        # 출고 건수/중량
        outbound = con.execute("""
            SELECT COUNT(*) AS cnt,
                   ROUND(SUM(qty_kg)/1000.0, 3) AS total_mt
            FROM stock_movement
            WHERE movement_type='OUTBOUND'
              AND DATE(COALESCE(movement_date, created_at)) = ?
        """, (d,)).fetchone()

        # 재고 현황 스냅샷 (오늘 기준 직접 집계)
        inv_snap = con.execute("""
            SELECT
                COUNT(*) AS total_lots,
                SUM(CASE WHEN status='AVAILABLE' THEN 1 ELSE 0 END) AS available,
                SUM(CASE WHEN status='RESERVED'  THEN 1 ELSE 0 END) AS reserved,
                SUM(CASE WHEN status='PICKED'    THEN 1 ELSE 0 END) AS picked,
                ROUND(SUM(current_weight)/1000.0, 3) AS current_mt
            FROM inventory
        """).fetchone()

        # 당일 이동 상세 (최대 50건)
        movements = con.execute("""
            SELECT lot_no, movement_type,
                   ROUND(qty_kg/1000.0,3) AS qty_mt,
                   customer, actor,
                   COALESCE(movement_date, created_at) AS ts
            FROM stock_movement
            WHERE DATE(COALESCE(movement_date, created_at)) = ?
            ORDER BY COALESCE(movement_date, created_at) DESC
            LIMIT 50
        """, (d,)).fetchall()
        con.close()

        return ok_response(data={
            "report_date": d,
            "inbound":  {"count": inbound["cnt"] or 0,  "total_mt": inbound["total_mt"]  or 0},
            "outbound": {"count": outbound["cnt"] or 0, "total_mt": outbound["total_mt"] or 0},
            "inventory_snapshot": dict(inv_snap) if inv_snap else {},
            "movements": _rows(movements),
        })
    except Exception as e:
        logger.error("report-daily error: %s", e)
        return err_response(str(e))


# ── 월간 보고서 ──────────────────────────────────────────────────
@router.get("/report-monthly", summary="📆 월간 보고서 (F048)")
def get_report_monthly(year: int = QP(None), month: int = QP(None)):
    """지정 월(기본 이번 달) 입출고 집계 + 주차별 세분화"""
    try:
        today = date.today()
        y = year  or today.year
        m = month or today.month
        prefix = f"{y:04d}-{m:02d}"

        con = _db()

        # 월간 입출고 유형별 집계
        summary = con.execute("""
            SELECT movement_type,
                   COUNT(*) AS cnt,
                   ROUND(SUM(qty_kg)/1000.0, 3) AS total_mt
            FROM stock_movement
            WHERE strftime('%Y-%m', COALESCE(movement_date, created_at)) = ?
            GROUP BY movement_type
            ORDER BY cnt DESC
        """, (prefix,)).fetchall()

        # 일별 입출고 (차트용)
        daily = con.execute("""
            SELECT DATE(COALESCE(movement_date, created_at)) AS day,
                   movement_type,
                   COUNT(*) AS cnt,
                   ROUND(SUM(qty_kg)/1000.0, 3) AS total_mt
            FROM stock_movement
            WHERE strftime('%Y-%m', COALESCE(movement_date, created_at)) = ?
            GROUP BY day, movement_type
            ORDER BY day ASC
        """, (prefix,)).fetchall()

        # 제품별 월간 입고
        by_product = con.execute("""
            SELECT i.product,
                   COUNT(DISTINCT sm.lot_no) AS lot_cnt,
                   ROUND(SUM(sm.qty_kg)/1000.0, 3) AS total_mt
            FROM stock_movement sm
            JOIN inventory i ON i.lot_no = sm.lot_no
            WHERE sm.movement_type='INBOUND'
              AND strftime('%Y-%m', COALESCE(sm.movement_date, sm.created_at)) = ?
            GROUP BY i.product
            ORDER BY total_mt DESC
        """, (prefix,)).fetchall()

        # 당월 말 재고 잔량
        inv_snap = con.execute("""
            SELECT COUNT(*) AS total_lots,
                   ROUND(SUM(current_weight)/1000.0, 3) AS current_mt
            FROM inventory
        """).fetchone()
        con.close()

        return ok_response(data={
            "year": y, "month": m,
            "period": prefix,
            "summary": _rows(summary),
            "daily_chart": _rows(daily),
            "by_product": _rows(by_product),
            "inventory_snapshot": dict(inv_snap) if inv_snap else {},
        })
    except Exception as e:
        logger.error("report-monthly error: %s", e)
        return err_response(str(e))


# ── 최근 파일 (최근 입고 LOT 목록) ─────────────────────────────
@router.get("/recent-files", summary="📂 최근 파일/입고 (F063)")
def get_recent_files(limit: int = QP(20, ge=1, le=100)):
    """최근 입고된 LOT 목록 — 파일 메뉴 '최근 파일' 용"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT lot_no, lot_sqm, sap_no, bl_no, product,
                   net_weight, current_weight, tonbag_count,
                   status, inbound_date, warehouse, created_at
            FROM inventory
            ORDER BY created_at DESC, inbound_date DESC
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows(rows),
            "total": len(rows),
            "note": "최근 입고 LOT 목록 (최신순)",
        })
    except Exception as e:
        logger.error("recent-files error: %s", e)
        return err_response(str(e))


# ── 반품 사유 통계 ───────────────────────────────────────────────
@router.get("/return-stats", summary="📊 반품 사유 통계 (F008)")
def get_return_stats():
    """return_history 테이블 — 사유별 반품 집계"""
    try:
        con = _db()
        # 사유별 집계
        by_reason = con.execute("""
            SELECT COALESCE(reason, '미분류') AS reason,
                   COUNT(*) AS cnt,
                   ROUND(SUM(weight_kg)/1000.0, 3) AS total_mt
            FROM return_history
            GROUP BY reason
            ORDER BY cnt DESC
        """).fetchall()

        # 월별 추이
        monthly = con.execute("""
            SELECT strftime('%Y-%m', return_date) AS month,
                   COUNT(*) AS cnt,
                   ROUND(SUM(weight_kg)/1000.0, 3) AS total_mt
            FROM return_history
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """).fetchall()

        # 전체 요약
        total = con.execute("""
            SELECT COUNT(*) AS cnt,
                   ROUND(SUM(weight_kg)/1000.0, 3) AS total_mt
            FROM return_history
        """).fetchone()
        con.close()

        return ok_response(data={
            "by_reason": _rows(by_reason),
            "monthly_trend": _rows(monthly),
            "total": dict(total) if total else {"cnt": 0, "total_mt": 0},
            "note": "반품 이력이 없으면 빈 결과" if not by_reason else "",
        })
    except Exception as e:
        logger.error("return-stats error: %s", e)
        return err_response(str(e))


# ── 출고 확정 대기 목록 ─────────────────────────────────────────
@router.get("/outbound-confirm-list", summary="✅ 출고 확정 대기 목록 (F022)")
def get_outbound_confirm_list():
    """PICKED 상태 LOT — 출고 확정 대상"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT i.lot_no, i.lot_sqm, i.sap_no, i.bl_no,
                   i.product, i.current_weight, i.tonbag_count,
                   i.status, i.sold_to, i.sale_ref,
                   i.warehouse, i.inbound_date,
                   COUNT(t.id) AS picked_tonbags,
                   ROUND(SUM(t.weight)/1000.0, 3) AS picked_mt
            FROM inventory i
            LEFT JOIN inventory_tonbag t ON t.inventory_id=i.id
                AND t.status='PICKED'
            WHERE i.status IN ('PICKED','RESERVED')
            GROUP BY i.id
            ORDER BY i.updated_at DESC
        """).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows(rows),
            "total": len(rows),
            "columns": ["lot_no", "product", "current_weight", "tonbag_count",
                        "status", "sold_to", "sale_ref", "picked_mt"],
        })
    except Exception as e:
        logger.error("outbound-confirm-list error: %s", e)
        return err_response(str(e))


# ── Detail of Outbound 보고서 ──────────────────────────────────
@router.get("/detail-outbound", summary="📦 Detail of Outbound (F040)")
def get_detail_outbound(limit: int = QP(200)):
    """출고 상세 보고서 — stock_movement OUTBOUND + inventory JOIN"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT
                sm.id, sm.lot_no,
                i.lot_sqm, i.sap_no, i.bl_no,
                i.product,
                sm.qty_kg,
                ROUND(sm.qty_kg/1000.0, 3) AS qty_mt,
                sm.customer,
                sm.from_location, sm.to_location,
                COALESCE(sm.movement_date, sm.created_at) AS outbound_dt,
                sm.actor, sm.remarks,
                i.sale_ref, i.sold_to,
                i.vessel, i.warehouse
            FROM stock_movement sm
            LEFT JOIN inventory i ON i.lot_no = sm.lot_no
            WHERE sm.movement_type = 'OUTBOUND'
            ORDER BY COALESCE(sm.movement_date, sm.created_at) DESC
            LIMIT ?
        """, (limit,)).fetchall()

        # 제품별 소계
        subtotals = con.execute("""
            SELECT i.product,
                   COUNT(*) AS cnt,
                   ROUND(SUM(sm.qty_kg)/1000.0, 3) AS total_mt
            FROM stock_movement sm
            LEFT JOIN inventory i ON i.lot_no = sm.lot_no
            WHERE sm.movement_type='OUTBOUND'
            GROUP BY i.product
            ORDER BY total_mt DESC
        """).fetchall()
        con.close()

        return ok_response(data={
            "items": _rows(rows),
            "total": len(rows),
            "subtotals_by_product": _rows(subtotals),
            "columns": ["lot_no", "lot_sqm", "sap_no", "product", "qty_mt",
                        "customer", "outbound_dt", "sale_ref", "vessel"],
        })
    except Exception as e:
        logger.error("detail-outbound error: %s", e)
        return err_response(str(e))


# ── 반품 이력 목록 ────────────────────────────────────────────────
@router.get("/return-list", summary="↩️ 반품 이력 목록 (Stage 3)")
def get_return_list(limit: int = 200, reason: str = "", date_from: str = "", date_to: str = ""):
    """return_history 테이블 전체 목록 + inventory에서 LOT 정보 JOIN"""
    try:
        con = _db()
        params = []
        where_parts = []
        if reason:
            where_parts.append("r.reason = ?")
            params.append(reason)
        if date_from:
            where_parts.append("r.return_date >= ?")
            params.append(date_from)
        if date_to:
            where_parts.append("r.return_date <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        rows = con.execute(f"""
            SELECT r.id, r.lot_no, r.sub_lt,
                   r.reason, r.remark AS memo, r.return_date, r.created_at,
                   ROUND(r.weight_kg / 1000.0, 3) AS weight_mt,
                   i.product, i.bl_no, i.warehouse, i.status AS inv_status
            FROM return_history r
            LEFT JOIN inventory i ON i.lot_no = r.lot_no
            {where}
            ORDER BY r.created_at DESC
            LIMIT ?
        """, params + [limit]).fetchall()
        reasons = [r[0] for r in con.execute(
            "SELECT DISTINCT reason FROM return_history WHERE reason IS NOT NULL ORDER BY reason"
        ).fetchall()]
        con.close()
        return ok_response(data={"items": _rows(rows), "total": len(rows), "reasons": reasons})
    except Exception as e:
        logger.error("return-list error: %s", e)
        return err_response(str(e))
