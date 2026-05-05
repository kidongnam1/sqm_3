# -*- coding: utf-8 -*-
"""
SQM v866 — 재고조정 API
POST /api/inventory/adjust/parse    : 자연어 입력 파싱 (DB 수정 없음)
POST /api/inventory/adjust/execute  : 파싱 결과 실행 (DB + 엑셀 수정)
"""
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventory/adjust", tags=["inventory-adjust"])

# ─── 프로젝트 루트 sys.path 보장 ────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ─── DB 경로 헬퍼 ───────────────────────────────────────────────────────────
def _db_path() -> str:
    env = os.environ.get("SQM_TEST_DB_PATH")
    if env and os.path.exists(env):
        return env
    return os.path.join(_ROOT, "data", "db", "sqm_inventory.db")


def _make_sqm_db():
    """SQMDatabase 인스턴스 반환 (adjust_parser/executor가 요구하는 fetchone/fetchall 인터페이스)."""
    from engine_modules.database import SQMDatabase
    return SQMDatabase(db_path=_db_path())


def _excel_path() -> Optional[str]:
    """프로젝트 data 폴더에서 최신 재고관리 엑셀 파일 경로 반환. 없으면 None."""
    try:
        from engine_modules.inventory_modular.adjust_executor import find_latest_excel
        data_dir = os.path.join(_ROOT, "data")
        path = find_latest_excel(data_dir)
        if path:
            logger.info("[AdjustAPI] 엑셀 파일 발견: %s", path)
        else:
            logger.info("[AdjustAPI] 엑셀 파일 없음 — 엑셀 수정 스킵")
        return path
    except Exception as exc:
        logger.warning("[AdjustAPI] 엑셀 경로 탐색 실패 (무시): %s", exc)
        return None


# ─── Pydantic 모델 ───────────────────────────────────────────────────────────

# ─── 단순 상태변경 요청 모델 ────────────────────────────────────────────────
class SimpleActionRequest(BaseModel):
    lot_no: str
    action: str          # e.g. 'return_to_available'
    operator: Optional[str] = "Nam Ki-dong"


@router.post("")
def simple_action(req: SimpleActionRequest):
    """
    단순 액션 처리 (return_to_available 등)
    POST /api/inventory/adjust  { lot_no, action }
    """
    import sqlite3
    from datetime import datetime

    if req.action == "return_to_available":
        try:
            conn = sqlite3.connect(_db_path())
            conn.row_factory = sqlite3.Row
            now = datetime.now().isoformat(sep=" ", timespec="seconds")
            # LOT 전체 RETURN 톤백 → AVAILABLE
            updated = conn.execute(
                """UPDATE inventory_tonbag SET status='AVAILABLE', updated_at=?
                   WHERE lot_no=? AND status='RETURN'""",
                (now, req.lot_no)
            ).rowcount
            # LOT 헤더 상태도 AVAILABLE로
            conn.execute(
                """UPDATE inventory SET status='AVAILABLE', updated_at=?
                   WHERE lot_no=? AND status='RETURN'""",
                (now, req.lot_no)
            )
            conn.commit()
            conn.close()
            logger.info("[SimpleAction] %s return_to_available: %d tonbags updated", req.lot_no, updated)
            return {"ok": True, "updated_tonbags": updated, "lot_no": req.lot_no}
        except Exception as exc:
            logger.error("[SimpleAction] return_to_available 오류: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


class ParseRequest(BaseModel):
    text: str


class AdjustItemIn(BaseModel):
    lot_no: str
    new_count: int
    reason_code: Optional[str] = "OTHER"
    reason_text: Optional[str] = ""


class ExecuteRequest(BaseModel):
    items: List[AdjustItemIn]
    operator: Optional[str] = "Nam Ki-dong"


# ─── 엔드포인트 ──────────────────────────────────────────────────────────────

@router.post("/parse")
def parse_adjust(req: ParseRequest):
    """
    자연어 재고조정 요청을 파싱합니다.
    DB를 조회하여 LOT 번호를 검증하고 delta를 계산하지만 DB를 수정하지 않습니다.

    입력:  { "text": "1126012309 LOT 2포대 파손됐어" }
    출력:  { "items": [...], "ambiguous": [], "error": null }
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 필드가 비어 있습니다.")

    try:
        from engine_modules.inventory_modular.adjust_parser import parse_adjust_request

        db = _make_sqm_db()
        try:
            result = parse_adjust_request(text, db)
        finally:
            try:
                db.close_all()
            except Exception:
                pass

        items_out: List[Dict[str, Any]] = []
        for item in result.items:
            items_out.append({
                "lot_no":      item.lot_no,
                "new_count":   item.new_count,
                "delta":       item.delta,
                "reason_code": item.reason_code,
                "reason_text": item.reason_text,
                "confidence":  item.confidence,
            })

        return {
            "items":     items_out,
            "ambiguous": result.ambiguous,
            "error":     result.error,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[AdjustAPI /parse] 오류: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"파싱 중 오류 발생: {exc}")


@router.post("/execute")
def execute_adjust(req: ExecuteRequest):
    """
    재고조정 항목을 DB 및 엑셀에 반영합니다.
    각 LOT은 독립 트랜잭션 — 일부 실패해도 나머지는 계속 진행합니다.

    입력:  { "items": [{lot_no, new_count, reason_code, reason_text}], "operator": "..." }
    출력:  { "success": [...], "skipped": [...], "failed": [...], "log_ids": [...] }
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="items 목록이 비어 있습니다.")

    try:
        from engine_modules.inventory_modular.adjust_executor import execute_adjustment

        items_dict: List[Dict[str, Any]] = [
            {
                "lot_no":      it.lot_no,
                "new_count":   it.new_count,
                "reason_code": it.reason_code or "OTHER",
                "reason_text": it.reason_text or "",
            }
            for it in req.items
        ]

        operator = (req.operator or "Nam Ki-dong").strip() or "Nam Ki-dong"
        excel_path = _excel_path()

        db = _make_sqm_db()
        try:
            result = execute_adjustment(
                items=items_dict,
                db=db,
                excel_path=excel_path,
                operator=operator,
            )
        finally:
            try:
                db.close_all()
            except Exception:
                pass

        return {
            "success":  result.success,
            "skipped":  result.skipped,
            "failed":   result.failed,
            "log_ids":  result.log_ids,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[AdjustAPI /execute] 오류: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"재고조정 실행 중 오류 발생: {exc}")
