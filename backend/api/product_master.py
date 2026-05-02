"""
제품 마스터 CRUD v2 — v864-2 Tk(GUI) 기준 필드까지 확장.

기존 웹 필드(product_name, sap_no, spec, unit, remarks) 유지 +
원본 Tk 필드(code, full_name, korean_name, tonbag_support,
             is_default, is_active, sort_order) 추가.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.common.errors import ok_response, err_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/product-master", tags=["product-master"])

# ──────────────────────────────────────────────────────────────────────────────
# 기본 제품 8종 (v864-2 Tk 원본과 동일)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_PRODUCTS = [
    {"code": "NSH", "product_name": "NSH",     "full_name": "Nickel Sulfate Hexahydrate",    "korean_name": "황산니켈",           "tonbag_support": 1, "sort_order": 1},
    {"code": "LCA", "product_name": "LCA",     "full_name": "Lithium Carbonate Anhydrous",   "korean_name": "탄산리튬",           "tonbag_support": 1, "sort_order": 2},
    {"code": "CSH", "product_name": "CSH",     "full_name": "Cobalt Sulfate Heptahydrate",   "korean_name": "황산코발트",         "tonbag_support": 1, "sort_order": 3},
    {"code": "NCM", "product_name": "NCM",     "full_name": "Nickel Cobalt Manganese",       "korean_name": "니켈코발트망간",     "tonbag_support": 1, "sort_order": 4},
    {"code": "NCA", "product_name": "NCA",     "full_name": "Nickel Cobalt Aluminum",        "korean_name": "니켈코발트알루미늄", "tonbag_support": 1, "sort_order": 5},
    {"code": "LFP", "product_name": "LFP",     "full_name": "Lithium Iron Phosphate",        "korean_name": "리튬인산철",         "tonbag_support": 1, "sort_order": 6},
    {"code": "LMO", "product_name": "LMO",     "full_name": "Lithium Manganese Oxide",       "korean_name": "리튬망간산화물",     "tonbag_support": 1, "sort_order": 7},
    {"code": "LCO", "product_name": "LCO",     "full_name": "Lithium Cobalt Oxide",          "korean_name": "리튬코발트산화물",   "tonbag_support": 1, "sort_order": 8},
]


# ──────────────────────────────────────────────────────────────────────────────
# DB 헬퍼
# ──────────────────────────────────────────────────────────────────────────────
def _db_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, "data", "db", "sqm_inventory.db")


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(), timeout=5, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=3000")
    return con


def _row(r: sqlite3.Row) -> dict[str, Any]:
    return dict(r)


def _migrate(con: sqlite3.Connection) -> None:
    """기존 product_master 테이블에 v2 컬럼 추가 (없을 때만)."""
    new_cols = [
        ("code",            "TEXT DEFAULT ''"),
        ("full_name",       "TEXT DEFAULT ''"),
        ("korean_name",     "TEXT DEFAULT ''"),
        ("tonbag_support",  "INTEGER DEFAULT 0"),
        ("is_default",      "INTEGER DEFAULT 0"),
        ("is_active",       "INTEGER DEFAULT 1"),
        ("sort_order",      "INTEGER DEFAULT 0"),
    ]
    existing = {row[1] for row in con.execute("PRAGMA table_info(product_master)").fetchall()}
    for col, typedef in new_cols:
        if col not in existing:
            try:
                con.execute(f"ALTER TABLE product_master ADD COLUMN {col} {typedef}")
                logger.info("product_master: added column %s", col)
            except Exception as exc:
                logger.debug("ALTER TABLE skip (%s): %s", col, exc)
    con.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic 모델
# ──────────────────────────────────────────────────────────────────────────────
class ProductPayload(BaseModel):
    product_name:   str = Field("", max_length=256)
    code:           str = Field("", max_length=16)
    full_name:      str = Field("", max_length=256)
    korean_name:    str = Field("", max_length=256)
    sap_no:         str = ""
    spec:           str = ""
    unit:           str = ""
    remarks:        str = ""
    tonbag_support: int = 0
    is_active:      int = 1
    sort_order:     int = 0


# ──────────────────────────────────────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/list")
def list_products():
    try:
        con = _db()
        _migrate(con)
        rows = con.execute(
            """SELECT id, code, product_name, full_name, korean_name,
                      sap_no, spec, unit, remarks,
                      tonbag_support, is_default, is_active, sort_order,
                      created_at, updated_at
               FROM product_master
               ORDER BY sort_order, code COLLATE NOCASE, product_name COLLATE NOCASE"""
        ).fetchall()
        con.close()
        items = [_row(r) for r in rows]
        return ok_response(data={"items": items, "total": len(items)})
    except Exception as e:
        logger.error("product-master list: %s", e)
        return err_response(str(e))


@router.post("/create")
def create_product(payload: ProductPayload):
    name = (payload.product_name or payload.full_name or payload.code).strip()
    if not name:
        return err_response("product_name(또는 code/full_name) 필수")
    code = payload.code.strip().upper()
    try:
        con = _db()
        _migrate(con)
        # code 중복 검사
        if code and con.execute("SELECT 1 FROM product_master WHERE code=?", (code,)).fetchone():
            con.close()
            return err_response(f"이미 존재하는 코드: {code}")
        con.execute(
            """INSERT INTO product_master
               (code, product_name, full_name, korean_name,
                sap_no, spec, unit, remarks,
                tonbag_support, is_default, is_active, sort_order,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,0,?,?, datetime('now'), datetime('now'))""",
            (code, name,
             payload.full_name.strip(), payload.korean_name.strip(),
             payload.sap_no.strip(), payload.spec.strip(),
             payload.unit.strip(), payload.remarks.strip(),
             int(bool(payload.tonbag_support)),
             int(bool(payload.is_active)),
             payload.sort_order),
        )
        con.commit()
        rid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.close()
        return ok_response(data={"id": rid}, message=f"등록: {name}")
    except sqlite3.IntegrityError:
        return err_response(f"이미 존재하는 제품명: {name}")
    except Exception as e:
        logger.error("product-master create: %s", e)
        return err_response(str(e))


@router.put("/{row_id}")
def update_product(row_id: int, payload: ProductPayload):
    name = (payload.product_name or payload.full_name or payload.code).strip()
    if not name:
        return err_response("product_name(또는 code/full_name) 필수")
    code = payload.code.strip().upper()
    try:
        con = _db()
        _migrate(con)
        # code 중복 검사 (자기 자신 제외)
        if code:
            dup = con.execute(
                "SELECT 1 FROM product_master WHERE code=? AND id!=?", (code, row_id)
            ).fetchone()
            if dup:
                con.close()
                return err_response(f"코드 중복: {code}")
        cur = con.execute(
            """UPDATE product_master
               SET code=?, product_name=?, full_name=?, korean_name=?,
                   sap_no=?, spec=?, unit=?, remarks=?,
                   tonbag_support=?, is_active=?, sort_order=?,
                   updated_at=datetime('now')
               WHERE id=?""",
            (code, name,
             payload.full_name.strip(), payload.korean_name.strip(),
             payload.sap_no.strip(), payload.spec.strip(),
             payload.unit.strip(), payload.remarks.strip(),
             int(bool(payload.tonbag_support)),
             int(bool(payload.is_active)),
             payload.sort_order, row_id),
        )
        if cur.rowcount == 0:
            con.close()
            return err_response(f"id={row_id} 없음")
        con.commit()
        con.close()
        return ok_response(message=f"수정: {name}")
    except sqlite3.IntegrityError:
        return err_response(f"제품명 중복: {name}")
    except Exception as e:
        logger.error("product-master update: %s", e)
        return err_response(str(e))


@router.delete("/{row_id}")
def delete_product(row_id: int):
    try:
        con = _db()
        _migrate(con)
        row = con.execute(
            "SELECT is_default, code FROM product_master WHERE id=?", (row_id,)
        ).fetchone()
        if not row:
            con.close()
            return err_response(f"id={row_id} 없음")
        if row["is_default"]:
            con.close()
            return err_response(f"기본 제품({row['code']})은 삭제할 수 없습니다. 비활성화를 사용하세요.")
        # 소프트 삭제 (is_active=0) 대신 하드 삭제 — 사용자 제품만 허용
        con.execute("DELETE FROM product_master WHERE id=?", (row_id,))
        con.commit()
        con.close()
        return ok_response(message="삭제 완료")
    except Exception as e:
        logger.error("product-master delete: %s", e)
        return err_response(str(e))


@router.post("/deactivate/{row_id}")
def deactivate_product(row_id: int):
    """기본 제품 포함 모든 제품을 비활성화 (is_active=0)."""
    try:
        con = _db()
        _migrate(con)
        cur = con.execute(
            "UPDATE product_master SET is_active=0, updated_at=datetime('now') WHERE id=?",
            (row_id,)
        )
        if cur.rowcount == 0:
            con.close()
            return err_response(f"id={row_id} 없음")
        con.commit()
        con.close()
        return ok_response(message="비활성화 완료")
    except Exception as e:
        logger.error("product-master deactivate: %s", e)
        return err_response(str(e))


@router.post("/sync-defaults")
def sync_defaults():
    """기본 제품 8종을 code 기준으로 없으면 삽입 (is_default=1)."""
    try:
        con = _db()
        _migrate(con)
        inserted = 0
        for p in DEFAULT_PRODUCTS:
            exists = con.execute(
                "SELECT 1 FROM product_master WHERE code=?", (p["code"],)
            ).fetchone()
            if not exists:
                con.execute(
                    """INSERT INTO product_master
                       (code, product_name, full_name, korean_name,
                        tonbag_support, is_default, is_active, sort_order,
                        created_at, updated_at)
                       VALUES (?,?,?,?,?,1,1,?, datetime('now'), datetime('now'))""",
                    (p["code"], p["product_name"], p["full_name"],
                     p["korean_name"], p["tonbag_support"], p["sort_order"]),
                )
                inserted += 1
        con.commit()
        total = con.execute("SELECT COUNT(*) FROM product_master WHERE is_default=1").fetchone()[0]
        con.close()
        return ok_response(
            data={"inserted": inserted, "default_total": total},
            message=f"기본 제품 {inserted}건 추가 (기본 제품 합계 {total}건)"
        )
    except Exception as e:
        logger.error("product-master sync-defaults: %s", e)
        return err_response(str(e))


@router.post("/sync-from-inventory")
def sync_from_inventory():
    """inventory에 등장한 DISTINCT product를 마스터에 없으면 추가."""
    try:
        con = _db()
        _migrate(con)
        before = con.execute("SELECT COUNT(*) FROM product_master").fetchone()[0]
        # product_name 기준 중복 방지 (UNIQUE 제약이 없으므로 수동 처리)
        inv_products = con.execute(
            "SELECT DISTINCT TRIM(product) AS p FROM inventory WHERE product IS NOT NULL AND LENGTH(TRIM(product)) > 0"
        ).fetchall()
        added = 0
        for row in inv_products:
            pname = row["p"]
            exists = con.execute(
                "SELECT 1 FROM product_master WHERE product_name=?", (pname,)
            ).fetchone()
            if not exists:
                con.execute(
                    """INSERT INTO product_master
                       (product_name, full_name, is_default, is_active, sort_order,
                        created_at, updated_at)
                       VALUES (?,?,0,1,100, datetime('now'), datetime('now'))""",
                    (pname, pname),
                )
                added += 1
        con.commit()
        after = con.execute("SELECT COUNT(*) FROM product_master").fetchone()[0]
        con.close()
        return ok_response(
            data={"inserted": added, "total": after},
            message=f"신규 {added}건 반영 (전체 {after}건)"
        )
    except Exception as e:
        logger.error("product-master sync: %s", e)
        return err_response(str(e))
