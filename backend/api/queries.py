"""
SQM v8.6.6 — SQL 직접 조회 엔드포인트
Phase 4-A Group 3: F009, F023, F025, F031, F034, F037, F038, F046, F047, F055

엔진(Tkinter GUI) 우회 → DB 직접 쿼리
모든 응답: ok_response(data=...) 표준 포맷
"""
import os
import sqlite3
import logging
from fastapi import APIRouter
from backend.common.errors import ok_response, err_response

router = APIRouter(prefix="/api/q", tags=["queries"])
logger = logging.getLogger(__name__)


# ── DB 경로 헬퍼 ────────────────────────────────────────────────
def _db() -> sqlite3.Connection:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    db_path = os.path.join(root, "data", "db", "sqm_inventory.db")
    con = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=3000")
    return con


def _rows_to_list(rows) -> list:
    """sqlite3.Row 목록을 dict 목록으로 변환"""
    return [dict(r) for r in rows]


# ── F009: 입고 현황 조회 ────────────────────────────────────────
@router.get("/inbound-status", summary="📋 입고 현황 조회 (F009)")
def get_inbound_status(limit: int = 200):
    """inventory 테이블 — 입고일자 내림차순"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT
                id, lot_no, lot_sqm, sap_no, bl_no,
                product, net_weight, current_weight, tonbag_count,
                status, inbound_date, arrival_date, warehouse,
                vessel, created_at
            FROM inventory
            ORDER BY inbound_date DESC, created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "columns": ["lot_no", "lot_sqm", "sap_no", "bl_no", "product",
                        "net_weight", "current_weight", "tonbag_count",
                        "status", "inbound_date", "arrival_date", "warehouse", "vessel"]
        })
    except Exception as e:
        logger.error("inbound-status error: %s", e)
        return err_response(str(e))


# ── F023: 승인 이력 조회 ────────────────────────────────────────
@router.get("/approval-history", summary="📜 승인 이력 조회 (F023)")
def get_approval_history(limit: int = 200):
    """allocation_approval + allocation_plan JOIN — 승인/반려 이력"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT
                aa.id,
                aa.allocation_plan_id,
                aa.status,
                aa.actor,
                aa.reason,
                aa.created_at,
                ap.lot_no,
                ap.customer,
                ap.sale_ref,
                ap.qty_mt,
                ap.outbound_date
            FROM allocation_approval aa
            LEFT JOIN allocation_plan ap ON aa.allocation_plan_id = ap.id
            ORDER BY aa.created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "columns": ["id", "allocation_plan_id", "status", "actor",
                        "reason", "created_at", "lot_no", "customer",
                        "sale_ref", "qty_mt", "outbound_date"]
        })
    except Exception as e:
        logger.error("approval-history error: %s", e)
        return err_response(str(e))


# ── F025 / F037: 출고 현황 조회 ─────────────────────────────────
@router.get("/outbound-status", summary="📋 출고 현황 조회 (F025/F037)")
def get_outbound_status(limit: int = 200):
    """stock_movement WHERE movement_type='OUTBOUND' — 출고 이력"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT
                id, lot_no, movement_type, qty_kg,
                customer, from_location, to_location,
                COALESCE(movement_date, created_at) AS movement_date,
                source_type, source_file, actor, remarks, created_at
            FROM stock_movement
            WHERE movement_type = 'OUTBOUND'
            ORDER BY COALESCE(movement_date, created_at) DESC
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "columns": ["lot_no", "movement_type", "qty_kg", "customer",
                        "from_location", "to_location", "movement_date",
                        "source_type", "actor", "remarks"]
        })
    except Exception as e:
        logger.error("outbound-status error: %s", e)
        return err_response(str(e))


# F037 alias (재고 탭에서도 같은 endpoint 사용)
@router.get("/outbound-status-inv", summary="📋 출고 현황 (재고 탭) (F037)")
def get_outbound_status_inv(limit: int = 200):
    """F037: F025와 동일 데이터, 재고 탭 진입점"""
    return get_outbound_status(limit=limit)


# ── F031: 백업 목록 ─────────────────────────────────────────────
@router.get("/backup-list", summary="📋 백업 목록 (F031)")
def get_backup_list():
    """backup/ 폴더 파일 목록 (최신순)"""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(here))
        backup_dir = os.path.join(root, "backup")

        if not os.path.isdir(backup_dir):
            return ok_response(data={"items": [], "total": 0,
                                     "backup_dir": backup_dir,
                                     "note": "backup 폴더 없음"})

        files = []
        for fname in os.listdir(backup_dir):
            if fname.endswith(".db") or fname.endswith(".zip"):
                fpath = os.path.join(backup_dir, fname)
                stat = os.stat(fpath)
                files.append({
                    "filename": fname,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": stat.st_mtime,
                    "path": fpath
                })
        files.sort(key=lambda x: x["modified"], reverse=True)
        return ok_response(data={
            "items": files,
            "total": len(files),
            "backup_dir": backup_dir
        })
    except Exception as e:
        logger.error("backup-list error: %s", e)
        return err_response(str(e))


# ── F034: 감사 로그 조회 ─────────────────────────────────────────
@router.get("/audit-log", summary="📋 감사 로그 조회 (F034)")
def get_audit_log(limit: int = 200):
    """audit_log 테이블 — 최신순"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT id, event_type, event_data, batch_id,
                   tonbag_id, user_note, created_by, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "columns": ["id", "event_type", "event_data", "batch_id",
                        "tonbag_id", "user_note", "created_by", "created_at"]
        })
    except Exception as e:
        logger.error("audit-log error: %s", e)
        return err_response(str(e))


# ── F038: 재고 추이 차트 ────────────────────────────────────────
@router.get("/inventory-trend", summary="📊 재고 추이 차트 (F038)")
def get_inventory_trend():
    """inventory_snapshot — 날짜별 재고 추이 (차트용 JSON)"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT
                snapshot_date,
                total_lots,
                total_tonbags,
                ROUND(total_weight_kg / 1000.0, 2) AS total_weight_mt,
                ROUND(available_weight_kg / 1000.0, 2) AS available_weight_mt,
                ROUND(picked_weight_kg / 1000.0, 2) AS picked_weight_mt,
                product_summary,
                created_at
            FROM inventory_snapshot
            ORDER BY snapshot_date ASC
        """).fetchall()
        con.close()
        items = _rows_to_list(rows)
        # 차트용 series 데이터 생성
        labels = [r["snapshot_date"] for r in items]
        total_mt = [r["total_weight_mt"] for r in items]
        available_mt = [r["available_weight_mt"] for r in items]
        picked_mt = [r["picked_weight_mt"] for r in items]
        return ok_response(data={
            "items": items,
            "total": len(items),
            "chart": {
                "labels": labels,
                "series": {
                    "total_mt": total_mt,
                    "available_mt": available_mt,
                    "picked_mt": picked_mt,
                }
            }
        })
    except Exception as e:
        logger.error("inventory-trend error: %s", e)
        return err_response(str(e))


# ── 스냅샷 생성 API ──────────────────────────────────────────────
@router.post("/create-snapshot", summary="📸 오늘 재고 스냅샷 생성/갱신")
def create_today_snapshot(force: bool = False):
    """
    오늘 날짜 기준 inventory_snapshot 생성 또는 갱신.
    - force=False: 오늘 스냅샷이 이미 있으면 skip
    - force=True : 있어도 덮어씀
    v864.2: validators.py save_today_snapshot() 이식
    """
    import json
    from datetime import date as _date
    today = _date.today().isoformat()
    try:
        con = _db()
        existing = con.execute(
            "SELECT id FROM inventory_snapshot WHERE snapshot_date=?", (today,)
        ).fetchone()
        if existing and not force:
            con.close()
            return ok_response(
                data={"created": False, "date": today, "reason": "already_exists"},
                message=f"{today} 스냅샷 이미 존재 (force=True로 덮어쓰기 가능)"
            )
        # inventory 집계
        stats = con.execute("""
            SELECT
                COUNT(*) AS total_lots,
                COALESCE(SUM(current_weight), 0)   AS total_weight,
                COALESCE(SUM(CASE WHEN status NOT IN ('DEPLETED','OUTBOUND') THEN current_weight ELSE 0 END), 0) AS avail_weight,
                COALESCE(SUM(picked_weight), 0)     AS picked_weight
            FROM inventory
        """).fetchone()
        tonbag_cnt = con.execute(
            "SELECT COUNT(*) FROM inventory_tonbag WHERE COALESCE(is_sample,0)=0"
        ).fetchone()[0]
        product_rows = con.execute("""
            SELECT product, COUNT(*) AS lots, SUM(current_weight) AS weight
            FROM inventory GROUP BY product
        """).fetchall()
        product_summary = json.dumps(
            [{"product": r[0], "lots": r[1], "weight_kg": r[2]} for r in product_rows],
            ensure_ascii=False
        )
        total_lots   = stats[0] if stats else 0
        total_weight = stats[1] if stats else 0
        avail_weight = stats[2] if stats else 0
        picked_weight= stats[3] if stats else 0
        if existing:
            con.execute("""
                UPDATE inventory_snapshot SET
                    total_lots=?, total_tonbags=?,
                    total_weight_kg=?, available_weight_kg=?,
                    picked_weight_kg=?, product_summary=?,
                    created_at=datetime('now')
                WHERE snapshot_date=?
            """, (total_lots, tonbag_cnt, total_weight,
                  avail_weight, picked_weight, product_summary, today))
        else:
            con.execute("""
                INSERT INTO inventory_snapshot
                    (snapshot_date, total_lots, total_tonbags, total_weight_kg,
                     available_weight_kg, picked_weight_kg, product_summary)
                VALUES (?,?,?,?,?,?,?)
            """, (today, total_lots, tonbag_cnt, total_weight,
                  avail_weight, picked_weight, product_summary))
        con.commit()
        con.close()
        logger.info(f"[snapshot] {today} 생성 완료 — lots={total_lots}, {total_weight:.1f}kg")
        return ok_response(
            data={"created": True, "date": today,
                  "total_lots": total_lots, "total_tonbags": tonbag_cnt,
                  "total_weight_kg": round(total_weight, 1),
                  "available_weight_kg": round(avail_weight, 1)},
            message=f"{today} 스냅샷 생성 완료"
        )
    except Exception as e:
        logger.error("create-snapshot error: %s", e, exc_info=True)
        return err_response(str(e))


# ── F046: 재고 현황 보고서 ──────────────────────────────────────
@router.get("/inventory-report", summary="📦 재고 현황 보고서 (F046)")
def get_inventory_report():
    """inventory GROUP BY product — 제품별 집계 보고서"""
    try:
        con = _db()
        # 제품별 집계
        summary = con.execute("""
            SELECT
                product,
                COUNT(*)                            AS lot_count,
                SUM(tonbag_count)                   AS tonbag_count,
                ROUND(SUM(net_weight) / 1000.0, 3)  AS total_net_mt,
                ROUND(SUM(current_weight) / 1000.0, 3) AS current_mt,
                GROUP_CONCAT(DISTINCT status)       AS statuses
            FROM inventory
            GROUP BY product
            ORDER BY current_mt DESC
        """).fetchall()
        # 상태별 집계
        status_cnt = con.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM inventory
            GROUP BY status
            ORDER BY cnt DESC
        """).fetchall()
        # 전체 합계
        totals = con.execute("""
            SELECT
                COUNT(*)                              AS total_lots,
                SUM(tonbag_count)                     AS total_tonbags,
                ROUND(SUM(net_weight) / 1000.0, 3)    AS total_net_mt,
                ROUND(SUM(current_weight) / 1000.0, 3) AS total_current_mt
            FROM inventory
        """).fetchone()
        con.close()
        return ok_response(data={
            "summary": _rows_to_list(summary),
            "status_breakdown": _rows_to_list(status_cnt),
            "totals": dict(totals) if totals else {},
        })
    except Exception as e:
        logger.error("inventory-report error: %s", e)
        return err_response(str(e))


# ── F047: 입출고 내역 ───────────────────────────────────────────
@router.get("/movement-history", summary="📈 입출고 내역 (F047)")
def get_movement_history(limit: int = 300):
    """stock_movement 전체 이력 (입고+출고 통합)"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT
                id, lot_no, movement_type, qty_kg,
                ROUND(qty_kg / 1000.0, 3) AS qty_mt,
                customer, from_location, to_location,
                COALESCE(movement_date, created_at) AS movement_date,
                source_type, actor, remarks
            FROM stock_movement
            ORDER BY COALESCE(movement_date, created_at) DESC
            LIMIT ?
        """, (limit,)).fetchall()
        # 타입별 집계
        stats = con.execute("""
            SELECT movement_type, COUNT(*) AS cnt,
                   ROUND(SUM(qty_kg) / 1000.0, 3) AS total_mt
            FROM stock_movement
            GROUP BY movement_type
        """).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "stats": _rows_to_list(stats),
            "columns": ["lot_no", "movement_type", "qty_kg", "qty_mt",
                        "customer", "movement_date", "source_type", "actor", "remarks"]
        })
    except Exception as e:
        logger.error("movement-history error: %s", e)
        return err_response(str(e))


# ── Picked List: 피킹 완료 목록 ─────────────────────────────────
@router.get("/picked-list", summary="📋 피킹 완료 목록 (picking_table)")
def get_picked_list(limit: int = 500):
    """picking_table — ACTIVE 상태 피킹 건을 lot_no+picking_no 기준 GROUP BY 집계"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT
                lot_no,
                customer,
                picking_no,
                COUNT(*)                       AS tonbag_count,
                SUM(COALESCE(qty_kg, 0))       AS total_kg,
                MIN(picking_date)              AS picking_date
            FROM picking_table
            WHERE status = 'ACTIVE'
            GROUP BY lot_no, picking_no
            ORDER BY picking_date DESC, lot_no
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "columns": ["lot_no", "customer", "picking_no",
                        "tonbag_count", "total_kg", "picking_date"]
        })
    except Exception as e:
        logger.error("picked-list error: %s", e)
        return err_response(str(e))


# ── Sold List: 출고 완료 목록 ───────────────────────────────────
@router.get("/sold-list", summary="📋 출고 완료 목록 (sold_table)")
def get_sold_list(limit: int = 500):
    """sold_table — SOLD/OUTBOUND/CONFIRMED 상태를 lot_no+sales_order_no 기준 GROUP BY 집계"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT
                s.lot_no,
                s.customer,
                s.sales_order_no,
                COUNT(*)                             AS tonbag_count,
                SUM(COALESCE(s.sold_qty_kg, 0))      AS total_kg,
                MAX(s.sold_date)                     AS sold_date
            FROM sold_table s
            WHERE s.status IN ('SOLD', 'OUTBOUND', 'CONFIRMED')
            GROUP BY s.lot_no, s.sales_order_no
            ORDER BY s.sold_date DESC, s.lot_no
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "columns": ["lot_no", "customer", "sales_order_no",
                        "tonbag_count", "total_kg", "sold_date"]
        })
    except Exception as e:
        logger.error("sold-list error: %s", e)
        return err_response(str(e))


# ── F055: 제품별 재고 현황 ──────────────────────────────────────
@router.get("/product-inventory", summary="📊 제품별 재고 현황 (F055)")
def get_product_inventory():
    """inventory + inventory_tonbag JOIN — 제품별 톤백 상세"""
    try:
        con = _db()
        # 제품별 LOT + 톤백 요약
        rows = con.execute("""
            SELECT
                i.product,
                i.lot_no,
                i.lot_sqm,
                i.sap_no,
                i.bl_no,
                i.status                               AS lot_status,
                i.net_weight,
                i.current_weight,
                i.tonbag_count,
                i.inbound_date,
                i.warehouse,
                COUNT(t.id)                            AS tb_count,
                SUM(CASE WHEN t.status='AVAILABLE'  THEN 1 ELSE 0 END) AS tb_available,
                SUM(CASE WHEN t.status='RESERVED'   THEN 1 ELSE 0 END) AS tb_reserved,
                SUM(CASE WHEN t.status='PICKED'     THEN 1 ELSE 0 END) AS tb_picked,
                ROUND(SUM(t.weight) / 1000.0, 3)      AS tb_weight_mt
            FROM inventory i
            LEFT JOIN inventory_tonbag t ON t.inventory_id = i.id
            GROUP BY i.id
            ORDER BY i.product, i.inbound_date DESC
        """).fetchall()
        # 제품별 재고 합계
        product_totals = con.execute("""
            SELECT
                i.product,
                COUNT(DISTINCT i.id)                   AS lot_count,
                SUM(i.tonbag_count)                    AS declared_tonbags,
                COUNT(t.id)                            AS actual_tonbags,
                ROUND(SUM(i.current_weight) / 1000.0, 3) AS current_mt
            FROM inventory i
            LEFT JOIN inventory_tonbag t ON t.inventory_id = i.id
            GROUP BY i.product
            ORDER BY current_mt DESC
        """).fetchall()
        con.close()
        return ok_response(data={
            "lots": _rows_to_list(rows),
            "product_totals": _rows_to_list(product_totals),
            "total_lots": len(rows),
        })
    except Exception as e:
        logger.error("product-inventory error: %s", e)
        return err_response(str(e))


# ── Allocation Summary: LOT별 요약 (2단 구조 상단) ─────────────────
@router.get("/allocation-summary", summary="📋 배정 LOT 요약 (Allocation 2단 구조)")
def get_allocation_summary():
    """allocation_plan GROUP BY lot_no — LOT별 요약 (v864.2 동일 2단 구조)"""
    try:
        con = _db()
        # v9.3 [ALLOC-SUMMARY-JOIN]: inventory JOIN → SAP NO/PRODUCT/WH 채움
        #         status 필터 제거 → RESERVED/PICKED/SOLD 모두 반환
        rows = con.execute("""
            SELECT ap.lot_no,
                   ap.customer,
                   SUM(COALESCE(ap.qty_mt, 0))                     AS total_mt,
                   COUNT(*)                                         AS tonbag_count,
                   COALESCE(date(ap.outbound_date), '0000-00-00')   AS plan_date,
                   MAX(ap.sale_ref)                                  AS sale_ref,
                   MAX(ap.outbound_date)                             AS outbound_date,
                   MAX(ap.status)                                    AS status,
                   i.sap_no,
                   i.product,
                   COALESCE(i.warehouse, 'GY')                      AS warehouse
            FROM allocation_plan ap
            LEFT JOIN inventory i ON ap.lot_no = i.lot_no
            WHERE ap.status NOT IN ('CANCELLED')
            GROUP BY ap.lot_no, COALESCE(date(ap.outbound_date), '0000-00-00'),
                     i.sap_no, i.product, i.warehouse
            ORDER BY ap.status, ap.lot_no, plan_date
        """).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "columns": ["lot_no", "customer", "total_mt", "tonbag_count", "plan_date", "sale_ref", "outbound_date", "status", "sap_no", "product", "warehouse"]
        })
    except Exception as e:
        logger.error("allocation-summary error: %s", e)
        return err_response(str(e))


# ── Allocation Detail: 특정 LOT의 톤백 상세 (2단 구조 하단) ────────
@router.get("/allocation-detail/{lot_no}", summary="📋 배정 LOT 상세 톤백 목록")
def get_allocation_detail(lot_no: str, plan_date: str = ""):
    """allocation_plan WHERE lot_no — 개별 톤백 상세 (펼침 영역)"""
    try:
        con = _db()
        if plan_date and plan_date != "0000-00-00":
            rows = con.execute("""
                SELECT ap.lot_no,
                       ap.tonbag_no,
                       ap.customer,
                       COALESCE(ap.qty_mt, 0)                         AS qty_mt,
                       ap.sale_ref,
                       ap.status,
                       ap.created_at
                FROM allocation_plan ap
                WHERE ap.lot_no = ?
                  AND ap.status = 'RESERVED'
                  AND COALESCE(date(ap.outbound_date), '0000-00-00') = ?
                ORDER BY ap.tonbag_no
            """, (lot_no, plan_date)).fetchall()
        else:
            rows = con.execute("""
                SELECT ap.lot_no,
                       ap.tonbag_no,
                       ap.customer,
                       COALESCE(ap.qty_mt, 0)                         AS qty_mt,
                       ap.sale_ref,
                       ap.status,
                       ap.created_at
                FROM allocation_plan ap
                WHERE ap.lot_no = ?
                  AND ap.status = 'RESERVED'
                ORDER BY ap.tonbag_no
            """, (lot_no,)).fetchall()
        con.close()
        return ok_response(data={
            "items": _rows_to_list(rows),
            "total": len(rows),
            "columns": ["lot_no", "tonbag_no", "customer", "qty_mt",
                         "sale_ref", "status", "created_at"]
        })
    except Exception as e:
        logger.error("allocation-detail error: %s", e)
        return err_response(str(e))


# ==============================================================
# Stage 2: 최근 입고 LOT + 톤백 상세 (modal용)
# ==============================================================
@router.get("/recent-inbound-lots", summary="📦 최근 입고 LOT 목록 (Stage 2)")
def get_recent_inbound_lots(limit: int = 50):
    """최근 입고된 LOT 목록 — InboundCancelModal 드롭다운용"""
    try:
        con = _db()
        rows = con.execute("""
            SELECT lot_no, product, net_weight, warehouse, status, inbound_date, created_at
            FROM inventory
            WHERE status NOT IN ('CANCELLED', 'FULLY_OUTBOUND')
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        con.close()
        return ok_response(data={"items": _rows_to_list(rows), "total": len(rows)})
    except Exception as e:
        logger.error("recent-inbound-lots error: %s", e)
        return err_response(str(e))


@router.get("/tonbag-detail", summary="🎒 특정 LOT 톤백 상세 목록 (Stage 2)")
def get_tonbag_detail(lot_no: str = ""):
    """특정 LOT의 톤백 목록 — LotAllocationAuditModal 2단 표"""
    try:
        con = _db()
        if lot_no:
            rows = con.execute("""
                SELECT t.id, t.sub_lt, t.lot_no, t.weight, t.status, t.location,
                       t.tonbag_uid, t.inbound_date, t.picked_to, t.picked_date
                FROM inventory_tonbag t
                WHERE t.lot_no = ?
                ORDER BY t.sub_lt
            """, (lot_no,)).fetchall()
        else:
            rows = []
        con.close()
        return ok_response(data={"items": _rows_to_list(rows), "total": len(rows)})
    except Exception as e:
        logger.error("tonbag-detail error: %s", e)
        return err_response(str(e))


@router.get("/outbound-history", summary="📦 출고 이력 목록 (Stage 2)")
def get_outbound_history(limit: int = 100, lot_no: str = "", date_from: str = "", date_to: str = ""):
    """출고 이력 목록"""
    try:
        con = _db()
        params = []
        where_parts = []
        if lot_no:
            where_parts.append("i.lot_no LIKE ?")
            params.append(f"%{lot_no}%")
        if date_from:
            where_parts.append("sm.created_at >= ?")
            params.append(date_from)
        if date_to:
            where_parts.append("sm.created_at <= ?")
            params.append(date_to + " 23:59:59")
        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        rows = con.execute(f"""
            SELECT sm.id, sm.lot_no, i.product, sm.qty_kg,
                   ROUND(sm.qty_kg/1000.0,3) AS qty_mt,
                   sm.customer, sm.actor, sm.remarks,
                   COALESCE(sm.movement_date, sm.created_at) AS outbound_dt,
                   sm.from_location, sm.to_location, i.warehouse
            FROM stock_movement sm
            LEFT JOIN inventory i ON i.lot_no = sm.lot_no
            {where}
            {'WHERE' if not where_parts else 'AND'} sm.movement_type = 'OUTBOUND'
            ORDER BY sm.created_at DESC
            LIMIT ?
        """.replace("WHERE AND", "WHERE").replace("AND AND", "AND"), params + [limit]).fetchall()
        con.close()
        return ok_response(data={"items": _rows_to_list(rows), "total": len(rows)})
    except Exception as e:
        logger.error("outbound-history error: %s", e)
        return err_response(str(e))


@router.get("/global-search", summary="🔍 전역 검색 (Stage 2)")
def global_search(q: str = "", limit: int = 50):
    """전역 검색 — inventory / inventory_tonbag 통합 검색"""
    if not q or len(q.strip()) < 2:
        return ok_response(data={"items": [], "total": 0, "query": q})
    try:
        con = _db()
        term = f"%{q.strip()}%"
        rows = con.execute("""
            SELECT 'LOT' AS type, lot_no AS id, lot_no, product, status,
                   net_weight AS weight, warehouse, inbound_date AS date
            FROM inventory
            WHERE lot_no LIKE ? OR product LIKE ? OR bl_no LIKE ? OR sap_no LIKE ?
            UNION ALL
            SELECT 'TONBAG', sub_lt, lot_no, NULL, status,
                   weight, location, inbound_date
            FROM inventory_tonbag
            WHERE sub_lt LIKE ? OR tonbag_uid LIKE ? OR location LIKE ?
            ORDER BY date DESC
            LIMIT ?
        """, (term, term, term, term, term, term, term, limit)).fetchall()
        con.close()
        return ok_response(data={"items": _rows_to_list(rows), "total": len(rows), "query": q})
    except Exception as e:
        logger.error("global-search error: %s", e)
        return err_response(str(e))
