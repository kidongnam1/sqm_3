"""
test_sample_parity.py
=====================
샘플 포대(is_sample=1) 정합성 검증
  - sample_bags  : inventory_api 반환값 vs DB 직접 카운트
  - sample_weight_mt: inventory_api 반환값 vs DB 직접 합산
  - 샘플 무게는 일반 재고 무게(current_weight)와 별도 추적되는지 확인

2026-05-04 Ruby — Phase 5+ 정합성 확장
"""
import pytest
import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'db', 'sqm_inventory.db'
)

SAMPLE_STATUSES = ('AVAILABLE', 'RESERVED', 'PICKED', 'RETURN')


@pytest.fixture(scope="module")
def db():
    if not os.path.exists(DB_PATH):
        pytest.skip("DB 파일 없음 — 실데이터 필요")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def get_lots_with_samples(db):
    """is_sample=1 포대가 1개 이상 있는 LOT 목록"""
    rows = db.execute(
        "SELECT DISTINCT lot_no FROM inventory_tonbag "
        "WHERE COALESCE(is_sample,0)=1 AND status IN ('AVAILABLE','RESERVED','PICKED','RETURN')"
    ).fetchall()
    return [r['lot_no'] for r in rows]


def db_sample_bags(db, lot_no):
    """DB에서 직접 샘플 포대 수 계산"""
    row = db.execute(
        "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
        "WHERE lot_no=? AND COALESCE(is_sample,0)=1 "
        "  AND status IN ('AVAILABLE','RESERVED','PICKED','RETURN')",
        (lot_no,)
    ).fetchone()
    return int(row['cnt']) if row else 0


def db_sample_weight_mt(db, lot_no):
    """DB에서 직접 샘플 무게 합산 (MT)"""
    row = db.execute(
        "SELECT COALESCE(SUM(weight),0) AS total_kg FROM inventory_tonbag "
        "WHERE lot_no=? AND COALESCE(is_sample,0)=1 "
        "  AND status IN ('AVAILABLE','RESERVED','PICKED','RETURN')",
        (lot_no,)
    ).fetchone()
    total_kg = float(row['total_kg']) if row else 0.0
    return round(total_kg / 1000.0, 3)


def api_sample_values(db, lot_no):
    """inventory_api 와 동일한 서브쿼리로 sample_bags, sample_weight_mt 계산"""
    row = db.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM inventory_tonbag t
             WHERE t.lot_no=i.lot_no AND t.is_sample=1
               AND t.status IN ('AVAILABLE','RESERVED','PICKED','RETURN')
            ) AS sample_bags,
            ROUND((SELECT COALESCE(SUM(t.weight),0) FROM inventory_tonbag t
             WHERE t.lot_no=i.lot_no AND t.is_sample=1
               AND t.status IN ('AVAILABLE','RESERVED','PICKED','RETURN')
            ) / 1000.0, 3) AS sample_weight_mt
        FROM inventory i
        WHERE i.lot_no=?
        """,
        (lot_no,)
    ).fetchone()
    if not row:
        return None, None
    return int(row['sample_bags']), float(row['sample_weight_mt'])


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

def test_db_has_inventory_tonbag_table(db):
    """inventory_tonbag 테이블 존재 + is_sample 컬럼 존재"""
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert 'inventory_tonbag' in tables, "inventory_tonbag 테이블 없음"

    cols = [r[1] for r in db.execute(
        "PRAGMA table_info(inventory_tonbag)"
    ).fetchall()]
    assert 'is_sample' in cols, "is_sample 컬럼 없음"


def test_sample_bags_count_matches_db(db):
    """
    sample_bags (API 서브쿼리) == DB 직접 COUNT
    샘플 포대가 있는 모든 LOT 검증
    """
    lots = get_lots_with_samples(db)
    if not lots:
        pytest.skip("샘플 포대 데이터 없음 (실데이터 입력 후 재실행)")

    errors = []
    for lot_no in lots:
        api_bags, _ = api_sample_values(db, lot_no)
        db_bags = db_sample_bags(db, lot_no)
        if api_bags != db_bags:
            errors.append(f"LOT {lot_no}: API={api_bags} vs DB={db_bags}")

    assert not errors, f"sample_bags 불일치 {len(errors)}건:\n" + "\n".join(errors)


def test_sample_weight_matches_db(db):
    """
    sample_weight_mt (API 서브쿼리) == DB 직접 SUM/1000.0
    허용 오차: 0.001 MT (부동소수점 반올림)
    """
    lots = get_lots_with_samples(db)
    if not lots:
        pytest.skip("샘플 포대 데이터 없음 (실데이터 입력 후 재실행)")

    errors = []
    TOLERANCE = 0.001
    for lot_no in lots:
        _, api_mt = api_sample_values(db, lot_no)
        db_mt = db_sample_weight_mt(db, lot_no)
        if abs((api_mt or 0.0) - db_mt) > TOLERANCE:
            errors.append(
                f"LOT {lot_no}: API={api_mt} MT vs DB={db_mt} MT (diff={abs(api_mt-db_mt):.4f})"
            )

    assert not errors, f"sample_weight_mt 불일치 {len(errors)}건:\n" + "\n".join(errors)


def test_sample_weight_not_exceeds_lot_weight(db):
    """
    샘플 무게는 LOT 전체 무게를 초과할 수 없음
    sample_weight_mt <= initial_weight / 1000.0
    """
    lots = get_lots_with_samples(db)
    if not lots:
        pytest.skip("샘플 포대 데이터 없음")

    errors = []
    for lot_no in lots:
        row = db.execute(
            "SELECT initial_weight FROM inventory WHERE lot_no=?", (lot_no,)
        ).fetchone()
        if not row:
            continue
        initial_mt = float(row['initial_weight'] or 0) / 1000.0
        sample_mt = db_sample_weight_mt(db, lot_no)
        if sample_mt > initial_mt + 0.001:
            errors.append(
                f"LOT {lot_no}: sample={sample_mt} MT > initial={initial_mt} MT"
            )

    assert not errors, f"샘플 무게 초과 {len(errors)}건:\n" + "\n".join(errors)


def test_normal_avail_excludes_sample(db):
    """
    일반 AVAILABLE 포대 수 = is_sample=0 AND status=AVAILABLE
    샘플 포대가 일반 재고 카운트에 포함되면 안 됨
    """
    lots = get_lots_with_samples(db)
    if not lots:
        pytest.skip("샘플 포대 데이터 없음")

    errors = []
    for lot_no in lots:
        # 일반 AVAIL (is_sample=0)
        normal = db.execute(
            "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
            "WHERE lot_no=? AND COALESCE(is_sample,0)=0 AND status='AVAILABLE'",
            (lot_no,)
        ).fetchone()
        # 전체 AVAIL (is_sample 구분 없이)
        total = db.execute(
            "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
            "WHERE lot_no=? AND status='AVAILABLE'",
            (lot_no,)
        ).fetchone()
        sample_avail = db.execute(
            "SELECT COUNT(*) AS cnt FROM inventory_tonbag "
            "WHERE lot_no=? AND COALESCE(is_sample,0)=1 AND status='AVAILABLE'",
            (lot_no,)
        ).fetchone()

        n_cnt = int(normal['cnt']) if normal else 0
        t_cnt = int(total['cnt']) if total else 0
        s_cnt = int(sample_avail['cnt']) if sample_avail else 0

        # n_cnt + s_cnt == t_cnt 이어야 함
        if n_cnt + s_cnt != t_cnt:
            errors.append(
                f"LOT {lot_no}: normal({n_cnt}) + sample({s_cnt}) != total({t_cnt})"
            )

    assert not errors, f"일반/샘플 AVAIL 분리 오류 {len(errors)}건:\n" + "\n".join(errors)


def test_sample_bags_positive_weight(db):
    """
    샘플 포대는 반드시 weight > 0 이어야 함 (0kg 샘플 포대는 데이터 오류)
    """
    rows = db.execute(
        "SELECT lot_no, sub_lt, weight FROM inventory_tonbag "
        "WHERE COALESCE(is_sample,0)=1 "
        "  AND status IN ('AVAILABLE','RESERVED','PICKED','RETURN') "
        "  AND (weight IS NULL OR weight <= 0)"
    ).fetchall()

    if rows:
        msgs = [f"  LOT={r['lot_no']} sub_lt={r['sub_lt']} weight={r['weight']}" for r in rows[:10]]
        pytest.fail(f"weight=0 또는 NULL 샘플 포대 {len(rows)}건:\n" + "\n".join(msgs))
