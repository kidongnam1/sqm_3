"""
SQM v864.3 — Dashboard KPI 실데이터 엔드포인트
Phase 3 Q1: GET /api/dashboard/kpi

SQL 집계 — DB 직접 접근 (engine 없이도 동작)
컬럼 확인: stock_movement.qty_kg / movement_date(nullable) / created_at
           inventory.status / inventory_tonbag.location+status
"""
import sqlite3
import os
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-kpi"])

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


def _get_db_path() -> str:
    """config.py 의존 없이 프로젝트 루트 기준 DB 경로 반환."""
    here = os.path.dirname(os.path.abspath(__file__))          # backend/api/
    project_root = os.path.dirname(os.path.dirname(here))      # Claude_SQM_v864_4/
    return os.path.join(project_root, "data", "db", "sqm_inventory.db")


def _run_kpi_queries(db_path: str) -> dict:
    """
    KPI 집계 SQL 4종 실행.
    movement_date 가 NULL 인 레코드는 created_at 으로 대체 (COALESCE).
    """
    con = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=3000")
    try:
        cur = con.cursor()

        # ① 오늘 입고량 (MT)
        cur.execute("""
            SELECT COALESCE(SUM(qty_kg), 0) / 1000.0
            FROM stock_movement
            WHERE movement_type = 'INBOUND'
              AND DATE(COALESCE(movement_date, created_at), 'localtime')
                  = DATE('now', 'localtime')
        """)
        today_inbound_mt = round(float(cur.fetchone()[0] or 0.0), 3)

        # ② 오늘 출고량 (MT)
        cur.execute("""
            SELECT COALESCE(SUM(qty_kg), 0) / 1000.0
            FROM stock_movement
            WHERE movement_type = 'OUTBOUND'
              AND DATE(COALESCE(movement_date, created_at), 'localtime')
                  = DATE('now', 'localtime')
        """)
        today_outbound_mt = round(float(cur.fetchone()[0] or 0.0), 3)

        # ③ 현재 재고 LOT 수 (출고/반품/판매 완료 제외)
        cur.execute("""
            SELECT COUNT(DISTINCT lot_no)
            FROM inventory
            WHERE status NOT IN ('SOLD', 'RETURNED', 'OUTBOUND')
        """)
        current_stock_lots = int(cur.fetchone()[0] or 0)

        # ④ 위치 미배정 톤백 수 (출고/판매 제외, location 없음)
        cur.execute("""
            SELECT COUNT(*)
            FROM inventory_tonbag
            WHERE (location IS NULL OR TRIM(location) = '')
              AND status NOT IN ('SOLD', 'RETURNED', 'OUTBOUND')
        """)
        unassigned_locations = int(cur.fetchone()[0] or 0)

        return {
            "today_inbound_mt":     today_inbound_mt,
            "today_outbound_mt":    today_outbound_mt,
            "current_stock_lots":   current_stock_lots,
            "unassigned_locations": unassigned_locations,
        }
    finally:
        con.close()


@router.get("/kpi")
def get_dashboard_kpi():
    """
    Phase 3 Q1 — Dashboard KPI 실데이터 (5초 폴링용)

    Response:
        ok: bool
        data:
            today_inbound_mt:    float  (MT, 오늘 입고)
            today_outbound_mt:   float  (MT, 오늘 출고)
            current_stock_lots:  int    (현재 재고 LOT 수)
            unassigned_locations: int   (위치 미배정 톤백 수)
            updated_at:          str    (KST ISO 8601)
    """
    now_str = datetime.now(KST).isoformat(timespec="seconds")

    try:
        db_path = _get_db_path()
        kpi = _run_kpi_queries(db_path)
        return {
            "ok": True,
            "data": {**kpi, "updated_at": now_str},
        }
    except Exception as exc:
        logger.error("[dashboard/kpi] 집계 실패: %s", exc, exc_info=True)
        return {
            "ok": False,
            "data": {
                "today_inbound_mt":     0.0,
                "today_outbound_mt":    0.0,
                "current_stock_lots":   0,
                "unassigned_locations": 0,
                "updated_at":           now_str,
            },
            "error": str(exc),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/dashboard/stats  — 대시보드 통계 패널
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/stats")
def get_dashboard_stats():
    """
    Dashboard 통계 — 5단계 상태 요약 + 제품x상태 매트릭스 + 정합성 검증.

    v864.2 대응: dashboard_data_mixin._get_status_four_phase_stats()
                + dashboard_data_mixin._get_integrity_summary()
    """
    try:
        db_path = _get_db_path()
        db = sqlite3.connect(db_path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=3000")
        c = db.cursor()

        # ── 기본 통계 (기존 호환) ──
        total_lots  = c.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        total_tbags = c.execute("SELECT COUNT(*) FROM inventory_tonbag").fetchone()[0]
        stock_lots  = c.execute("SELECT COUNT(*) FROM inventory WHERE status='AVAILABLE'").fetchone()[0]
        sold_lots   = c.execute("SELECT COUNT(*) FROM inventory WHERE status IN ('SOLD','RESERVED','PICKED')").fetchone()[0]
        total_wt    = c.execute("SELECT COALESCE(SUM(current_weight),0) FROM inventory").fetchone()[0]
        avail_wt    = c.execute("SELECT COALESCE(SUM(current_weight),0) FROM inventory WHERE status='AVAILABLE'").fetchone()[0]

        # ── 상태 요약 (inventory_tonbag 기준) — 일반 + 샘플 분리 ──
        status_rows = c.execute("""
            SELECT
                CASE
                    WHEN status IN ('OUTBOUND', 'SOLD', 'SHIPPED', 'CONFIRMED') THEN 'outbound'
                    WHEN status = 'AVAILABLE' THEN 'available'
                    WHEN status = 'RESERVED'  THEN 'reserved'
                    WHEN status = 'PICKED'    THEN 'picked'
                    WHEN status = 'RETURN'    THEN 'return'
                    ELSE 'other'
                END AS grp,
                COALESCE(is_sample, 0)       AS is_sample,
                COUNT(DISTINCT lot_no)        AS lots,
                COUNT(*)                      AS tonbags,
                COALESCE(SUM(weight), 0)      AS weight_kg
            FROM inventory_tonbag
            GROUP BY grp, is_sample
        """).fetchall()

        status_summary = {}
        for grp_name in ('available', 'reserved', 'picked', 'outbound', 'return'):
            status_summary[grp_name] = {
                "lots": 0, "tonbags": 0, "weight_kg": 0.0,
                "normal_bags": 0, "normal_kg": 0.0,
                "sample_bags": 0, "sample_kg": 0.0,
            }
        for row in status_rows:
            grp, is_sample, lots, tonbags, weight_kg = row
            if grp not in status_summary:
                continue
            s = status_summary[grp]
            s["lots"]     += lots
            s["tonbags"]  += tonbags
            s["weight_kg"] = round(s["weight_kg"] + float(weight_kg), 1)
            if is_sample:
                s["sample_bags"] += tonbags
                s["sample_kg"]    = round(s["sample_kg"] + float(weight_kg), 1)
            else:
                s["normal_bags"] += tonbags
                s["normal_kg"]    = round(s["normal_kg"] + float(weight_kg), 1)
        for grp_name in status_summary:
            s = status_summary[grp_name]
            s["weight_kg"] = round(s["weight_kg"], 1)

        # ── 제품x상태 매트릭스 (제품별 톤백 수량) ──
        matrix_rows = c.execute("""
            SELECT
                COALESCE(i.product, '(미지정)') AS product,
                SUM(CASE WHEN tb.status = 'AVAILABLE' THEN 1 ELSE 0 END) AS available,
                SUM(CASE WHEN tb.status = 'RESERVED'  THEN 1 ELSE 0 END) AS reserved,
                SUM(CASE WHEN tb.status = 'PICKED'    THEN 1 ELSE 0 END) AS picked,
                SUM(CASE WHEN tb.status IN ('OUTBOUND','SOLD','SHIPPED','CONFIRMED') THEN 1 ELSE 0 END) AS outbound,
                SUM(CASE WHEN tb.status = 'RETURN'    THEN 1 ELSE 0 END) AS return_cnt,
                COUNT(*) AS total
            FROM inventory_tonbag tb
            LEFT JOIN inventory i ON tb.lot_no = i.lot_no
            GROUP BY COALESCE(i.product, '(미지정)')
            ORDER BY COALESCE(i.product, '(미지정)')
        """).fetchall()

        product_matrix = []
        for row in matrix_rows:
            product_matrix.append({
                "product":   row[0],
                "available": row[1],
                "reserved":  row[2],
                "picked":    row[3],
                "outbound":  row[4],
                "return":    row[5],
                "total":     row[6],
            })

        # ── 정합성 요약 (총입고 = 현재재고 + 출고누계) ──
        # 샘플 톤백도 inventory.initial_weight에 포함되므로 전체를 샘플 포함 기준으로 통일한다.
        # stock_movement INBOUND는 기존 데이터에 샘플 포함/제외 이력이 섞일 수 있어 기준값으로 쓰지 않는다.
        total_inbound_kg = c.execute("""
            SELECT COALESCE(SUM(initial_weight), 0) FROM inventory
        """).fetchone()[0]

        # 현재 재고 중량 (샘플 포함: AVAILABLE + RESERVED + PICKED + RETURN)
        current_stock_kg = c.execute("""
            SELECT COALESCE(SUM(weight), 0) FROM inventory_tonbag
            WHERE status IN ('AVAILABLE', 'RESERVED', 'PICKED', 'RETURN')
        """).fetchone()[0]

        # 출고 누계 중량 (샘플 포함: OUTBOUND + SOLD 상태 톤백)
        outbound_total_kg = c.execute("""
            SELECT COALESCE(SUM(weight), 0) FROM inventory_tonbag
            WHERE status IN ('OUTBOUND', 'SOLD', 'SHIPPED', 'CONFIRMED')
        """).fetchone()[0]

        diff_kg = round(float(total_inbound_kg) - float(current_stock_kg) - float(outbound_total_kg), 1)
        integrity = {
            "total_inbound_kg":  round(float(total_inbound_kg), 1),
            "current_stock_kg":  round(float(current_stock_kg), 1),
            "outbound_total_kg": round(float(outbound_total_kg), 1),
            "diff_kg":           diff_kg,
            "ok":                abs(diff_kg) <= 1.0,
        }

        # LOT 행 기준 합계 (엑셀 «LOT 재고현황» 순중량/현재중량 합과 동일 — 샘플은 보통 순중량−현재중량 차이로 반영)
        _nw_sum, _cw_sum = c.execute(
            """
            SELECT COALESCE(SUM(net_weight), 0), COALESCE(SUM(current_weight), 0)
            FROM inventory
            """
        ).fetchone()
        _nw_sum = float(_nw_sum or 0)
        _cw_sum = float(_cw_sum or 0)
        _sample_tb = c.execute(
            """
            SELECT COALESCE(SUM(weight), 0) FROM inventory_tonbag
            WHERE COALESCE(is_sample, 0) = 1
              AND status IN ('AVAILABLE', 'RESERVED', 'PICKED', 'RETURN')
            """
        ).fetchone()[0]
        lot_weight_summary = {
            "sum_net_weight_kg": round(_nw_sum, 1),
            "sum_current_weight_kg": round(_cw_sum, 1),
            "gap_net_minus_current_kg": round(_nw_sum - _cw_sum, 1),
            "sum_net_mt": round(_nw_sum / 1000.0, 3),
            "sum_current_mt": round(_cw_sum / 1000.0, 3),
            "sample_tonbags_in_stock_kg": round(float(_sample_tb or 0), 1),
        }

        db.close()

        return {
            # 기존 호환 필드
            "total_lots":      total_lots,
            "total_tbags":     total_tbags,
            "stock_lots":      stock_lots,
            "sold_lots":       sold_lots,
            "total_weight_mt": round(total_wt / 1000.0, 2),
            "available_mt":    round(avail_wt / 1000.0, 2),
            # 신규: 5단계 상태 요약
            "status_summary":  status_summary,
            # 신규: 제품x상태 매트릭스
            "product_matrix":  product_matrix,
            # 신규: 정합성 검증
            "integrity":       integrity,
            # LOT 목록/엑셀과 동일한 중량 합계 (순중량 vs 현재중량·샘플 톤백)
            "lot_weight_summary": lot_weight_summary,
        }
    except Exception as e:
        logger.error("[dashboard/stats] 집계 실패: %s", e, exc_info=True)
        return {"error": str(e)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GET /api/dashboard/alerts — ALERTS 패널
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/alerts")
def get_dashboard_alerts():
    try:
        db_path = _get_db_path()
        db = sqlite3.connect(db_path, timeout=10)
        c  = db.cursor()
        alerts = []
        # 프리타임 만료 임박 LOT
        ft_rows = c.execute("""
            SELECT i.lot_no, i.container_no, fi.free_time_date
            FROM freetime_info fi
            JOIN inventory i ON i.lot_no = fi.lot_no
            WHERE fi.free_time_date IS NOT NULL
              AND date(fi.free_time_date) <= date('now', '+7 days')
              AND i.status NOT IN ('RETURNED','CANCELLED')
            LIMIT 5
        """).fetchall()
        for r in ft_rows:
            alerts.append({
                "type": "warning",
                "message": f"FREE TIME 임박: LOT {r[0]} / {r[1]} ({r[2]})",
                "level": "WARNING"
            })
        # 위치 미배정 톤백
        no_loc = c.execute("""
            SELECT COUNT(*) FROM inventory_tonbag
            WHERE (location IS NULL OR location='') AND status='AVAILABLE'
        """).fetchone()[0]
        if no_loc > 0:
            alerts.append({
                "type": "info",
                "message": f"위치 미배정 톤백 {no_loc}개 있음",
                "level": "INFO"
            })
        # 최근 감사로그 에러
        err_rows = c.execute("""
            SELECT event_type, event_data FROM audit_log
            WHERE event_type LIKE '%ERROR%' OR event_type LIKE '%FAIL%'
            ORDER BY created_at DESC LIMIT 3
        """).fetchall()
        for r in err_rows:
            alerts.append({
                "type": "error",
                "message": f"[{r[0]}] {str(r[1])[:80]}",
                "level": "ERROR"
            })
        db.close()
        if not alerts:
            alerts.append({"type": "ok", "message": "정상 — 경고 없음", "level": "OK"})
        return alerts
    except Exception as e:
        return [{"type": "error", "message": str(e), "level": "ERROR"}]
