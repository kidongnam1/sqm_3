"""
refresh_excel_api.py — Excel STATUS 갱신 API

POST /api/inventory/refresh-excel-status
  → allocation_plan DB 기준으로 _int.xlsx INVENTORY 시트 STATUS 컬럼 갱신
  → RESERVED=노란, SOLD=빨강, AVAILABLE=초록

작성일: 2026-05-03
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


class RefreshResult(BaseModel):
    success: bool
    updated: int
    reserved: int
    sold: int
    available: int
    excel_path: str
    message: str


@router.post("/refresh-excel-status", response_model=RefreshResult)
async def refresh_excel_status():
    """DB allocation_plan 기준으로 _int.xlsx STATUS 컬럼을 갱신합니다."""
    try:
        # 프로젝트 루트 탐색
        here = Path(__file__).resolve()
        project_root = here.parent.parent.parent  # backend/api/ → backend/ → root

        # scripts 모듈 경로 추가
        import sys
        scripts_dir = str(project_root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        from refresh_excel_status import refresh, _find_db, _find_excel

        db_path    = _find_db(project_root)
        excel_path = _find_excel(project_root)

        logger.info("[refresh_excel] DB=%s Excel=%s", db_path, excel_path)

        stats = refresh(excel_path, db_path, dry_run=False)

        msg = (
            f"✅ Excel STATUS 갱신 완료 — "
            f"변경 {stats['updated']}행 "
            f"(RESERVED: {stats['reserved']}, SOLD: {stats['sold']}, AVAILABLE: {stats['available']})"
        )
        logger.info(msg)

        return RefreshResult(
            success=True,
            updated=stats["updated"],
            reserved=stats["reserved"],
            sold=stats["sold"],
            available=stats["available"],
            excel_path=str(Path(excel_path).name),
            message=msg,
        )

    except FileNotFoundError as exc:
        logger.warning("[refresh_excel] 파일 없음: %s", exc)
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("[refresh_excel] 오류: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Excel 갱신 오류: {exc}")
