"""
보고서 양식 파일 저장소 — `data/report_templates/` 업로드·목록·삭제.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from backend.common.errors import ok_response, err_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/report-templates", tags=["report-templates"])

_ALLOWED_EXT = (".xlsx", ".xls", ".pdf", ".docx", ".csv", ".html")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9가-힣._\- \(\)]{1,200}$")


def _templates_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    d = os.path.join(root, "data", "report_templates")
    os.makedirs(d, exist_ok=True)
    return d


def _validate_filename(name: str) -> str:
    base = os.path.basename(name.strip())
    if not base or ".." in base:
        raise HTTPException(400, "잘못된 파일명")
    if not _SAFE_NAME.match(base):
        raise HTTPException(400, "허용되지 않는 문자가 포함된 파일명")
    low = base.lower()
    if not any(low.endswith(ext) for ext in _ALLOWED_EXT):
        raise HTTPException(400, f"허용 확장자: {', '.join(_ALLOWED_EXT)}")
    return base


@router.get("/list")
def list_templates():
    try:
        d = _templates_dir()
        items = []
        for fn in sorted(os.listdir(d)):
            path = os.path.join(d, fn)
            if not os.path.isfile(path):
                continue
            try:
                st = os.stat(path)
                items.append({
                    "name": fn,
                    "size_bytes": st.st_size,
                    "modified_at": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })
            except OSError as e:
                logger.debug("list_templates skip %s: %s", fn, e)
        return ok_response(data={"items": items, "total": len(items), "directory": d})
    except Exception as e:
        logger.error("report-templates list: %s", e)
        return err_response(str(e))


@router.post("/upload")
async def upload_template(file: UploadFile = File(...)):
    try:
        raw = file.filename or ""
        safe = _validate_filename(raw)
        dest = os.path.join(_templates_dir(), safe)
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(400, "파일 크기 50MB 초과")
        with open(dest, "wb") as f:
            f.write(content)
        return ok_response(data={"name": safe, "size_bytes": len(content)}, message=f"저장: {safe}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("report-templates upload: %s", e)
        return err_response(str(e))


@router.delete("/file")
def delete_template(name: str = Query(..., min_length=1, max_length=220)):
    try:
        safe = _validate_filename(name)
        path = os.path.join(_templates_dir(), safe)
        if not os.path.isfile(path):
            return err_response(f"파일 없음: {safe}")
        os.remove(path)
        return ok_response(message=f"삭제: {safe}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("report-templates delete: %s", e)
        return err_response(str(e))
