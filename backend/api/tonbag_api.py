# -*- coding: utf-8 -*-
"""
SQM v864.3 — Tonbag API (Phase 4-B)
POST /api/tonbag/location-upload : 톤백 위치 Excel 업로드 (F004)
engine.update_tonbag_location(lot_no, sub_lt, location) 반복 호출
"""
import logging
import os
import tempfile
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tonbag", tags=["tonbag"])


# 톤백 위치 Excel 컬럼 별칭
_LOC_COLUMN_MAP = {
    "lot_no":   ["lot_no", "lot", "lot no", "lot번호", "로트"],
    "sub_lt":   ["sub_lt", "sublt", "sub", "sublot", "톤백번호", "톤백no", "tonbag_no"],
    "location": ["location", "loc", "위치", "창고위치", "warehouse_location"],
    "reason":   ["reason", "reason_code", "사유", "사유코드"],
    "note":     ["note", "비고", "remark", "memo"],
}


def _match_columns(df_columns) -> dict:
    result = {}
    lowered = {str(c).strip().lower(): c for c in df_columns}
    for std_key, aliases in _LOC_COLUMN_MAP.items():
        for alias in aliases:
            a = alias.strip().lower()
            if a in lowered:
                result[std_key] = lowered[a]
                break
    return result


def _clean(v: Any) -> Any:
    try:
        import math
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    return v


@router.post("/location-upload", summary="📍 톤백 위치 매핑 — Excel 업로드 (F004)")
async def location_upload(file: UploadFile = File(...)):
    """
    Excel 각 행: (lot_no, sub_lt, location, [reason], [note])
    engine.update_tonbag_location() 반복 호출. 행별 성공/실패 독립.
    """
    if not file.filename:
        raise HTTPException(400, "파일명 없음")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        raise HTTPException(400, f"Excel 파일만 지원 (.xlsx/.xls). 받은 파일: {file.filename}")

    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(500, "pandas 미설치")

    try:
        from backend.api import engine, ENGINE_AVAILABLE
    except Exception as e:
        raise HTTPException(500, f"엔진 로드 실패: {e}")
    if not ENGINE_AVAILABLE or engine is None or not hasattr(engine, "update_tonbag_location"):
        raise HTTPException(500, "엔진 update_tonbag_location 메서드 없음")

    tmp_path = None
    try:
        content = await file.read()
        if not content:
            raise HTTPException(400, "빈 파일")
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        df = None
        header_used = None
        for header_row in (0, 1, 2):
            try:
                candidate = pd.read_excel(tmp_path, header=header_row)
                if candidate.empty:
                    continue
                matched = _match_columns(candidate.columns)
                if "lot_no" in matched and "sub_lt" in matched and "location" in matched:
                    df = candidate
                    header_used = header_row
                    break
            except Exception:
                continue
        if df is None or df.empty:
            raise HTTPException(400, "필수 컬럼 없음 (lot_no + sub_lt + location)")

        col_map = _match_columns(df.columns)
        success_count = 0
        fail_count = 0
        errors = []

        for idx, row in df.iterrows():
            data = {k: _clean(row[c]) for k, c in col_map.items()}
            lot_no = data.get("lot_no")
            sub_lt = data.get("sub_lt")
            location = data.get("location")
            reason = data.get("reason") or "RELOCATE"
            note = data.get("note") or ""

            if not lot_no or not sub_lt or not location:
                fail_count += 1
                errors.append({"row": int(idx) + 2, "reason": "lot_no/sub_lt/location 누락"})
                continue
            try:
                sub_lt_int = int(sub_lt)
            except Exception:
                fail_count += 1
                errors.append({"row": int(idx) + 2, "reason": f"sub_lt 정수 변환 실패: {sub_lt}"})
                continue

            try:
                result = engine.update_tonbag_location(
                    lot_no=str(lot_no).strip(),
                    sub_lt=sub_lt_int,
                    location=str(location).strip(),
                    source="EXCEL_UPLOAD",
                    reason_code=str(reason).strip().upper() if reason else "RELOCATE",
                    operator="web_ui",
                    note=str(note),
                )
                if result.get("success"):
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append({
                        "row": int(idx) + 2,
                        "lot_no": str(lot_no),
                        "sub_lt": sub_lt_int,
                        "reason": result.get("error") or "unknown",
                    })
            except Exception as e:
                fail_count += 1
                errors.append({
                    "row": int(idx) + 2,
                    "lot_no": str(lot_no),
                    "reason": f"exception: {e}",
                })

        logger.info(f"[location-upload] 완료: 성공 {success_count} / 실패 {fail_count}")
        return {
            "ok": True,
            "data": {
                "filename": file.filename,
                "total": int(len(df)),
                "success_count": success_count,
                "fail_count": fail_count,
                "header_row": header_used,
                "matched_columns": list(col_map.keys()),
                "errors": errors[:50],
            },
            "message": f"{success_count}건 위치 변경 / {fail_count}건 실패",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[location-upload] 에러: {e}")
        raise HTTPException(500, f"Internal error: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
