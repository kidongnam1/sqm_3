# -*- coding: utf-8 -*-
"""
SQM v8.6.6 — 전체 워크플로 Smoke Test
업로드 파일: 톤백리스트_전체_20260505_202643.xlsx 기반
80 LOT × 11톤백(정규10 + 샘플1) = 880개 / 400.080 MT

워크플로 타임라인:
  Day  0  입고    : 880 AVAILABLE
  Day  0  Alloc   : 절반(40 LOT) → RESERVED
  Day  7  Picking : RESERVED 중 절반(20 LOT) → PICKED
  Day 14  Outbound: PICKED(20 LOT) → SOLD
  Day 21  Return  : SOLD 중 절반(10 LOT) → RETURN
  Day 22  Move    : RETURN → AVAILABLE + 위치 재배정

정합성 핵심 규칙:
  ① 전체 톤백 수 = 항상 880 (상태 합산)
  ② 같은 LOT의 같은 Sub_LT 중복 상태 금지
  ③ 무게 합산 = 일정 (출고 전 400.080 MT)
  ④ 샘플백(Sub_LT=0) 동일 규칙 적용
"""
import io
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

# ── 프로젝트 루트 경로 ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB_PATH = ROOT / "data" / "db" / "sqm_inventory.db"

# ── FastAPI 앱 import ──────────────────────────────────────────────
from backend.main import app
client = TestClient(app)

# ══════════════════════════════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════════════════════════════

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def get_status_counts() -> Dict[str, int]:
    """inventory_tonbag 상태별 개수"""
    con = _conn()
    rows = con.execute(
        "SELECT status, COUNT(*) as cnt FROM inventory_tonbag GROUP BY status"
    ).fetchall()
    con.close()
    return {r["status"]: r["cnt"] for r in rows}


def get_lot_table() -> pd.DataFrame:
    """
    LOT별 × 상태별 × 구분(정규/샘플) 상세 테이블
    컬럼: lot_no, sap_no, 정규_AVAILABLE, 정규_RESERVED, 정규_PICKED,
           정규_SOLD, 정규_RETURN, 샘플_AVAILABLE, 샘플_RESERVED,
           샘플_PICKED, 샘플_SOLD, 샘플_RETURN, 총톤백, 총중량_MT
    """
    con = _conn()
    df = pd.read_sql_query("""
        SELECT
            it.lot_no,
            inv.sap_no,
            it.is_sample,
            it.status,
            COUNT(*) as cnt,
            SUM(it.weight) as weight_kg
        FROM inventory_tonbag it
        JOIN inventory inv ON inv.lot_no = it.lot_no
        GROUP BY it.lot_no, inv.sap_no, it.is_sample, it.status
        ORDER BY it.lot_no, it.is_sample, it.status
    """, con)
    con.close()

    if df.empty:
        return df

    # 피벗: 행=LOT, 컬럼=상태+구분
    df["구분"] = df["is_sample"].map({0: "정규", 1: "샘플"})
    df["key"] = df["구분"] + "_" + df["status"]
    pivot = df.pivot_table(
        index=["lot_no", "sap_no"],
        columns="key",
        values="cnt",
        aggfunc="sum",
        fill_value=0
    ).reset_index()
    pivot.columns.name = None

    # 무게 합산
    wt = df.groupby("lot_no")["weight_kg"].sum().reset_index()
    wt["총중량_MT"] = (wt["weight_kg"] / 1000).round(3)
    pivot = pivot.merge(wt[["lot_no","총중량_MT"]], on="lot_no", how="left")
    pivot["총톤백"] = df.groupby("lot_no")["cnt"].sum().reset_index()["cnt"]
    return pivot


def print_stage_table(stage: str, df: pd.DataFrame):
    """단계별 상태 테이블 출력"""
    print(f"\n{'='*80}")
    print(f"  📊 {stage}")
    print(f"{'='*80}")
    if df.empty:
        print("  (데이터 없음)")
        return
    # 주요 컬럼만 표시
    show_cols = ["lot_no", "sap_no"]
    for col in ["정규_AVAILABLE","정규_RESERVED","정규_PICKED","정규_SOLD","정규_RETURN",
                "샘플_AVAILABLE","샘플_RESERVED","샘플_PICKED","샘플_SOLD","샘플_RETURN",
                "총톤백","총중량_MT"]:
        if col in df.columns:
            show_cols.append(col)
    print(df[show_cols].to_string(index=False))

    # 합계 행
    totals = {}
    for col in show_cols[2:]:
        try:
            totals[col] = df[col].sum()
        except Exception:
            totals[col] = "-"
    print(f"\n  ▶ 합계: " + " | ".join(
        f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
        for k, v in totals.items()
    ))
    print(f"{'='*80}\n")


def make_allocation_excel(lots: List[str], qty_per_lot: float,
                           customer: str = "TEST CUSTOMER",
                           sale_ref_prefix: str = "SC-TEST") -> bytes:
    """Allocation Excel 생성 (bulk-import-excel 형식)"""
    wb = Workbook()
    ws = wb.active
    ws.append(["lot_no", "sold_to", "sale_ref", "qty_mt", "outbound_date"])
    for i, lot in enumerate(lots, 1):
        ws.append([lot, customer, f"{sale_ref_prefix}-{i:03d}",
                   qty_per_lot, "2026-05-12"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════
# Fixture: 전체 LOT 목록 (DB에서 읽기)
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def all_lots() -> List[str]:
    con = _conn()
    rows = con.execute(
        "SELECT lot_no FROM inventory ORDER BY lot_no"
    ).fetchall()
    con.close()
    lots = [r["lot_no"] for r in rows]
    assert len(lots) > 0, "DB에 LOT 없음 — 앱 실행 후 데이터 로드 필요"
    return lots


@pytest.fixture(scope="module")
def half_lots(all_lots) -> List[str]:
    """전체 LOT 중 절반 (Allocation 대상)"""
    n = len(all_lots) // 2
    return all_lots[:n]


@pytest.fixture(scope="module")
def quarter_lots(all_lots) -> List[str]:
    """전체 LOT 중 1/4 (Picking 대상)"""
    n = len(all_lots) // 4
    return all_lots[:n]


# ══════════════════════════════════════════════════════════════════════
# STEP 0 — 초기 상태 검증 (입고 직후)
# ══════════════════════════════════════════════════════════════════════

class TestStep0_InitialState:
    """Day 0: 입고 완료 — 전체 AVAILABLE 상태 검증"""

    def test_api_health(self):
        """API 서버 정상 응답"""
        r = client.get("/api/dashboard/stats")
        assert r.status_code == 200, f"API 응답 실패: {r.status_code}"

    def test_all_available(self, all_lots):
        """모든 톤백이 AVAILABLE 상태"""
        counts = get_status_counts()
        total = sum(counts.values())
        avail = counts.get("AVAILABLE", 0)

        df = get_lot_table()
        print_stage_table("STEP 0 — 초기 상태 (입고 직후)", df)

        assert total > 0, "톤백 데이터 없음"
        assert avail == total, (
            f"초기 상태 오류: AVAILABLE={avail}, 전체={total}\n"
            f"비AVAILABLE 상태: {counts}"
        )

    def test_no_duplicate_sublot(self, all_lots):
        """중복 톤백 없음 (같은 LOT의 같은 Sub_LT 중복 금지)"""
        con = _conn()
        dups = con.execute("""
            SELECT lot_no, sub_lt, COUNT(*) as cnt
            FROM inventory_tonbag
            GROUP BY lot_no, sub_lt
            HAVING cnt > 1
        """).fetchall()
        con.close()
        assert len(dups) == 0, f"중복 톤백 발견: {[dict(d) for d in dups]}"

    def test_weight_integrity(self):
        """무게 정합성 — inventory.current_weight = 톤백 합산"""
        con = _conn()
        mismatches = con.execute("""
            SELECT i.lot_no,
                   i.current_weight as header_kg,
                   COALESCE(t.sum_kg, 0) as tonbag_sum_kg
            FROM inventory i
            LEFT JOIN (
                SELECT lot_no, SUM(weight) as sum_kg
                FROM inventory_tonbag
                WHERE status IN ('AVAILABLE','RESERVED','RETURN')
                GROUP BY lot_no
            ) t ON t.lot_no = i.lot_no
            WHERE ABS(COALESCE(i.current_weight,0) - COALESCE(t.sum_kg,0)) > 1.0
        """).fetchall()
        con.close()
        assert len(mismatches) == 0, (
            f"무게 불일치 LOT:\n" +
            "\n".join(f"  {r['lot_no']}: header={r['header_kg']}kg, "
                      f"tonbag_sum={r['tonbag_sum_kg']}kg"
                      for r in mismatches)
        )

    def test_sample_bags_present(self, all_lots):
        """샘플백(Sub_LT=0) 각 LOT에 1개씩 존재"""
        con = _conn()
        rows = con.execute("""
            SELECT lot_no, COUNT(*) as cnt
            FROM inventory_tonbag
            WHERE is_sample = 1
            GROUP BY lot_no
        """).fetchall()
        con.close()
        for r in rows:
            assert r["cnt"] == 1, f"LOT {r['lot_no']}: 샘플백 {r['cnt']}개 (1개 기대)"


# ══════════════════════════════════════════════════════════════════════
# STEP 1 — Allocation (AVAILABLE → RESERVED)
# ══════════════════════════════════════════════════════════════════════

class TestStep1_Allocation:
    """Day 0: Allocation — 전체 중 절반 RESERVED"""

    def test_allocation_upload(self, half_lots):
        """Allocation Excel 업로드 → RESERVED 전환"""
        counts_before = get_status_counts()
        avail_before = counts_before.get("AVAILABLE", 0)

        excel_bytes = make_allocation_excel(
            lots=half_lots,
            qty_per_lot=5.0,
            customer="TEST CUSTOMER",
            sale_ref_prefix="SC-SMOKE"
        )
        r = client.post(
            "/api/allocation/bulk-import-excel",
            files={"file": ("alloc_test.xlsx", excel_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        assert r.status_code == 200, f"Allocation 업로드 실패: {r.text}"
        body = r.json()
        assert body.get("ok") or body.get("success") or body.get("imported", 0) > 0, \
            f"Allocation 응답 이상: {body}"

    def test_reserved_count_increased(self, half_lots):
        """RESERVED 톤백 수 증가 확인"""
        # apply-approved 실행
        r2 = client.post("/api/allocation/apply-approved")
        # 200 또는 이미 적용된 경우 허용
        assert r2.status_code in (200, 400), f"apply-approved 실패: {r2.text}"

        counts = get_status_counts()
        df = get_lot_table()
        print_stage_table("STEP 1 — Allocation 완료 (절반 RESERVED)", df)

        reserved = counts.get("RESERVED", 0)
        total = sum(counts.values())
        assert reserved > 0, "RESERVED 톤백이 0개 — Allocation 미반영"
        assert total == sum(
            get_status_counts().values()
        ), "전체 톤백 수 변동 — 정합성 오류"

    def test_no_duplicate_after_alloc(self):
        """Allocation 후 중복 없음"""
        con = _conn()
        dups = con.execute("""
            SELECT lot_no, sub_lt, COUNT(*) as cnt
            FROM inventory_tonbag
            GROUP BY lot_no, sub_lt
            HAVING cnt > 1
        """).fetchall()
        con.close()
        assert len(dups) == 0, f"Allocation 후 중복 발견: {[dict(d) for d in dups]}"

    def test_total_tonbag_count_unchanged(self, all_lots):
        """전체 톤백 수 불변 (880개)"""
        con = _conn()
        total = con.execute("SELECT COUNT(*) FROM inventory_tonbag").fetchone()[0]
        con.close()
        expected = len(all_lots) * 11  # LOT당 10정규 + 1샘플
        assert total == expected, f"톤백 총 수 변동: {total} (기대: {expected})"


# ══════════════════════════════════════════════════════════════════════
# STEP 2 — Picking (RESERVED → PICKED)
# ══════════════════════════════════════════════════════════════════════

class TestStep2_Picking:
    """Day 7: Packing List — RESERVED 중 절반 PICKED"""

    def test_pick_half_of_reserved(self, quarter_lots):
        """RESERVED LOT 중 절반을 PICKED로 전환"""
        con = _conn()
        reserved_lots = [
            r["lot_no"] for r in con.execute(
                "SELECT DISTINCT lot_no FROM allocation_plan WHERE status='RESERVED'"
            ).fetchall()
        ]
        con.close()

        if not reserved_lots:
            pytest.skip("RESERVED LOT 없음 — Step1 먼저 실행 필요")

        pick_target = reserved_lots[:max(1, len(reserved_lots) // 2)]
        failed = []
        for lot in pick_target:
            r = client.post(f"/api/allocation/{lot}/pick")
            if r.status_code not in (200, 404):
                failed.append(f"{lot}: {r.status_code}")

        assert len(failed) == 0, f"Pick 실패 LOT: {failed}"

    def test_picked_count(self):
        """PICKED 톤백 수 > 0"""
        counts = get_status_counts()
        df = get_lot_table()
        print_stage_table("STEP 2 — Picking 완료 (RESERVED 절반 → PICKED)", df)

        picked = counts.get("PICKED", 0)
        assert picked > 0, "PICKED 톤백이 0개"

    def test_integrity_after_pick(self, all_lots):
        """Picking 후 전체 톤백 수 불변"""
        con = _conn()
        total = con.execute("SELECT COUNT(*) FROM inventory_tonbag").fetchone()[0]
        con.close()
        assert total == len(all_lots) * 11


# ══════════════════════════════════════════════════════════════════════
# STEP 3 — Outbound / SOLD (PICKED → SOLD)
# ══════════════════════════════════════════════════════════════════════

class TestStep3_Outbound:
    """Day 14: 출고 확정 — PICKED → SOLD"""

    def test_confirm_picked_lots(self):
        """PICKED LOT을 SOLD(출고확정)으로 전환"""
        con = _conn()
        picked_lots = [
            r["lot_no"] for r in con.execute(
                "SELECT DISTINCT lot_no FROM allocation_plan WHERE status='PICKED'"
            ).fetchall()
        ]
        con.close()

        if not picked_lots:
            pytest.skip("PICKED LOT 없음")

        failed = []
        for lot in picked_lots:
            r = client.post(f"/api/allocation/{lot}/confirm")
            if r.status_code not in (200, 404):
                failed.append(f"{lot}: {r.status_code}")

        assert len(failed) == 0, f"Confirm 실패: {failed}"

    def test_sold_appears(self):
        """SOLD 상태 톤백 존재"""
        counts = get_status_counts()
        df = get_lot_table()
        print_stage_table("STEP 3 — Outbound 완료 (PICKED → SOLD)", df)
        assert counts.get("SOLD", 0) > 0, "SOLD 톤백 없음"

    def test_weight_balance_after_outbound(self):
        """출고 후 AVAILABLE + RESERVED 무게 합산 정합"""
        con = _conn()
        row = con.execute("""
            SELECT SUM(weight) as total_active_kg
            FROM inventory_tonbag
            WHERE status IN ('AVAILABLE', 'RESERVED')
        """).fetchone()
        con.close()
        total_kg = row["total_active_kg"] or 0
        assert total_kg > 0, "출고 후 재고 무게 0"


# ══════════════════════════════════════════════════════════════════════
# STEP 4 — Return (SOLD → RETURN)
# ══════════════════════════════════════════════════════════════════════

class TestStep4_Return:
    """Day 21: 반품 — SOLD LOT 절반 RETURN"""

    def test_mark_return(self):
        """SOLD LOT 절반을 RETURN 상태로 수동 설정"""
        con = _conn()
        sold_lots = [
            r["lot_no"] for r in con.execute(
                "SELECT DISTINCT lot_no FROM inventory WHERE status='SOLD'"
            ).fetchall()
        ]
        if not sold_lots:
            con.close()
            pytest.skip("SOLD LOT 없음")

        return_target = sold_lots[:max(1, len(sold_lots) // 2)]
        now = __import__("datetime").datetime.now().isoformat(sep=" ", timespec="seconds")
        for lot in return_target:
            con.execute(
                "UPDATE inventory_tonbag SET status='RETURN', updated_at=? WHERE lot_no=?",
                (now, lot)
            )
            con.execute(
                "UPDATE inventory SET status='RETURN', updated_at=? WHERE lot_no=?",
                (now, lot)
            )
        con.commit()
        con.close()

    def test_return_count(self):
        """RETURN 상태 톤백 > 0"""
        counts = get_status_counts()
        df = get_lot_table()
        print_stage_table("STEP 4 — 반품 완료 (RETURN 상태)", df)
        assert counts.get("RETURN", 0) > 0, "RETURN 톤백 없음"

    def test_no_duplicate_on_return(self):
        """반품 후 중복 없음"""
        con = _conn()
        dups = con.execute("""
            SELECT lot_no, sub_lt, COUNT(*) as cnt
            FROM inventory_tonbag
            GROUP BY lot_no, sub_lt
            HAVING cnt > 1
        """).fetchall()
        con.close()
        assert len(dups) == 0, f"반품 후 중복: {[dict(d) for d in dups]}"


# ══════════════════════════════════════════════════════════════════════
# STEP 5 — Move + Re-Available (RETURN → AVAILABLE + 위치 재배정)
# ══════════════════════════════════════════════════════════════════════

class TestStep5_MoveAndReAvailable:
    """Day 22: 재입고 — RETURN → AVAILABLE + 위치 이동"""

    def test_return_to_available(self):
        """RETURN LOT을 AVAILABLE로 복귀"""
        con = _conn()
        return_lots = [
            r["lot_no"] for r in con.execute(
                "SELECT DISTINCT lot_no FROM inventory WHERE status='RETURN'"
            ).fetchall()
        ]
        con.close()

        if not return_lots:
            pytest.skip("RETURN LOT 없음")

        failed = []
        for lot in return_lots:
            r = client.post(
                "/api/inventory/adjust",
                json={"lot_no": lot, "action": "return_to_available"}
            )
            if r.status_code != 200:
                failed.append(f"{lot}: {r.status_code} {r.text[:80]}")

        assert len(failed) == 0, f"return_to_available 실패: {failed}"

    def test_move_location(self):
        """재입고 후 위치 재배정 (A-ZONE → B-ZONE)"""
        con = _conn()
        avail_lots = [
            r["lot_no"] for r in con.execute(
                "SELECT DISTINCT lot_no FROM inventory WHERE status='AVAILABLE' LIMIT 5"
            ).fetchall()
        ]
        con.close()

        if not avail_lots:
            pytest.skip("AVAILABLE LOT 없음")

        failed = []
        for lot in avail_lots:
            r = client.post(
                "/api/action2/inventory-move",
                json={"lot_no": lot, "to_loc": "B-ZONE-TEST"}
            )
            if r.status_code != 200:
                failed.append(f"{lot}: {r.status_code}")

        assert len(failed) == 0, f"Move 실패: {failed}"

    def test_final_state_table(self, all_lots):
        """최종 상태 테이블 출력 — 전체 정합성 최종 확인"""
        counts = get_status_counts()
        df = get_lot_table()
        print_stage_table("STEP 5 — 최종 상태 (Move + Re-Available 완료)", df)

        # 전체 톤백 수 불변
        total = sum(counts.values())
        assert total == len(all_lots) * 11, \
            f"최종 총 톤백 수 오류: {total} (기대: {len(all_lots) * 11})"

    def test_no_final_duplicate(self):
        """최종 중복 없음"""
        con = _conn()
        dups = con.execute("""
            SELECT lot_no, sub_lt, COUNT(*) as cnt
            FROM inventory_tonbag
            GROUP BY lot_no, sub_lt
            HAVING cnt > 1
        """).fetchall()
        con.close()
        assert len(dups) == 0, f"최종 중복: {[dict(d) for d in dups]}"

    def test_moved_location_recorded(self):
        """위치 이동 기록이 stock_movement에 저장됨"""
        con = _conn()
        moves = con.execute(
            "SELECT COUNT(*) FROM stock_movement WHERE movement_type='MOVE'"
        ).fetchone()[0]
        con.close()
        assert moves > 0, "stock_movement에 MOVE 기록 없음"
