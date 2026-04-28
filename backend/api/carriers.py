"""
carriers.py — Carrier Profile CRUD API
GET    /api/carriers           → 전체 목록 (is_active=1)
GET    /api/carriers/{id}      → 단일 조회
POST   /api/carriers           → 신규 등록
PUT    /api/carriers/{id}      → 수정
DELETE /api/carriers/{id}      → 소프트 삭제 (is_active=0)
"""
import sqlite3
import logging
from fastapi import APIRouter, HTTPException
from backend.common.errors import ok_response

router = APIRouter(prefix="/api/carriers", tags=["carriers"])

# ── DB 연결 헬퍼 ─────────────────────────────────────────────────
def _get_con():
    from config import DB_PATH
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


# ── Row → dict ──────────────────────────────────────────────────
def _row(row) -> dict:
    return {
        "carrier_id":      row["carrier_id"],
        "display_name":    row["display_name"],
        "default_product": row["default_product"],
        "bag_weight_kg":   row["bag_weight_kg"],
        "note":            row["note"],
        "is_active":       bool(row["is_active"]),
    }


# ── GET /api/carriers ─────────────────────────────────────────────
@router.get("")
def list_carriers():
    """활성 선사 프로파일 목록 반환"""
    try:
        con = _get_con()
        rows = con.execute(
            "SELECT * FROM carrier_profile WHERE is_active=1 ORDER BY carrier_id"
        ).fetchall()
        con.close()
        return {"data": [_row(r) for r in rows]}
    except Exception as e:
        logging.error(f"[carriers] list failed: {e}")
        raise HTTPException(500, str(e))


# ── GET /api/carriers/{carrier_id} ───────────────────────────────
@router.get("/{carrier_id}")
def get_carrier(carrier_id: str):
    """단일 선사 프로파일 조회"""
    try:
        con = _get_con()
        row = con.execute(
            "SELECT * FROM carrier_profile WHERE carrier_id=?",
            (carrier_id,)
        ).fetchone()
        con.close()
        if not row:
            raise HTTPException(404, f"선사 프로파일 없음: {carrier_id}")
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[carriers] get {carrier_id} failed: {e}")
        raise HTTPException(500, str(e))


# ── POST /api/carriers ────────────────────────────────────────────
@router.post("")
def create_carrier(payload: dict):
    """
    신규 선사 프로파일 등록
    필수: carrier_id, display_name
    선택: default_product, bag_weight_kg, note
    """
    carrier_id = (payload.get("carrier_id") or "").strip()
    display_name = (payload.get("display_name") or "").strip()
    if not carrier_id:
        raise HTTPException(400, "carrier_id 필수")
    if not display_name:
        raise HTTPException(400, "display_name 필수")

    default_product = (payload.get("default_product") or "").strip()
    bag_weight_kg = float(payload.get("bag_weight_kg") or 500.0)
    note = (payload.get("note") or "").strip()

    try:
        con = _get_con()
        # 중복 확인 (소프트 삭제 포함)
        existing = con.execute(
            "SELECT is_active FROM carrier_profile WHERE carrier_id=?",
            (carrier_id,)
        ).fetchone()
        if existing:
            if existing["is_active"]:
                con.close()
                raise HTTPException(409, f"이미 존재하는 carrier_id: {carrier_id}")
            else:
                # 소프트 삭제된 항목 → 재활성화 + 업데이트
                con.execute(
                    """UPDATE carrier_profile SET
                       display_name=?, default_product=?, bag_weight_kg=?, note=?, is_active=1
                       WHERE carrier_id=?""",
                    (display_name, default_product, bag_weight_kg, note, carrier_id)
                )
        else:
            con.execute(
                """INSERT INTO carrier_profile
                   (carrier_id, display_name, default_product, bag_weight_kg, note, is_active)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (carrier_id, display_name, default_product, bag_weight_kg, note)
            )
        con.commit()
        con.close()
        return ok_response(f"{carrier_id} 등록 완료")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[carriers] create {carrier_id} failed: {e}")
        raise HTTPException(500, str(e))


# ── PUT /api/carriers/{carrier_id} ───────────────────────────────
@router.put("/{carrier_id}")
def update_carrier(carrier_id: str, payload: dict):
    """선사 프로파일 수정 (부분 업데이트 지원)"""
    try:
        con = _get_con()
        row = con.execute(
            "SELECT * FROM carrier_profile WHERE carrier_id=? AND is_active=1",
            (carrier_id,)
        ).fetchone()
        if not row:
            con.close()
            raise HTTPException(404, f"선사 프로파일 없음: {carrier_id}")

        # 전달된 필드만 업데이트 (없으면 기존 값 유지)
        display_name    = (payload.get("display_name")    or row["display_name"]).strip()
        default_product = (payload.get("default_product") or row["default_product"]).strip()
        bag_weight_kg   = float(payload.get("bag_weight_kg") or row["bag_weight_kg"])
        note            = (payload.get("note")            if "note" in payload else row["note"] or "").strip()

        con.execute(
            """UPDATE carrier_profile SET
               display_name=?, default_product=?, bag_weight_kg=?, note=?
               WHERE carrier_id=?""",
            (display_name, default_product, bag_weight_kg, note, carrier_id)
        )
        con.commit()
        con.close()
        return ok_response(f"{carrier_id} 수정 완료")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[carriers] update {carrier_id} failed: {e}")
        raise HTTPException(500, str(e))


# ── DELETE /api/carriers/{carrier_id} ────────────────────────────
@router.delete("/{carrier_id}")
def delete_carrier(carrier_id: str):
    """선사 프로파일 소프트 삭제 (is_active=0)"""
    try:
        con = _get_con()
        row = con.execute(
            "SELECT carrier_id FROM carrier_profile WHERE carrier_id=? AND is_active=1",
            (carrier_id,)
        ).fetchone()
        if not row:
            con.close()
            raise HTTPException(404, f"선사 프로파일 없음: {carrier_id}")

        con.execute(
            "UPDATE carrier_profile SET is_active=0 WHERE carrier_id=?",
            (carrier_id,)
        )
        con.commit()
        con.close()
        return ok_response(f"{carrier_id} 삭제 완료")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[carriers] delete {carrier_id} failed: {e}")
        raise HTTPException(500, str(e))
