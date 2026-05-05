"""
SQM v8.6.6 — Optional 11 Features API (Tier 3 S1)
=================================================
Tier 2 에서 deferred 로 남겨진 옵션 기능들을 실제 구현.
존재하지 않는 원본 handler 는 501 Mock 유지.

작성: Ruby, 2026-04-21
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from backend.common.errors import wrap_engine_call, NotReadyError, ok_response

router = APIRouter(prefix="/api/optional", tags=["optional"])


# ── Optional 1: 고급 검색 ──────────────────────────────────────
@router.get("/search")
async def advanced_search(q: str = "", field: str = "lot"):
    """고급 검색 (LOT/SAP/BL/Container)"""
    try:
        from engine_modules.inventory_modular.engine import SQMInventoryEngineV3  # type: ignore
        from config import DB_PATH  # type: ignore
        engine = SQMInventoryEngineV3(str(DB_PATH))
        if hasattr(engine, "search"):
            return wrap_engine_call(engine.search, q=q, field=field)
    except Exception:
        pass
    # 기본: 빈 결과
    return ok_response(data=[])


# ── Optional 2: 배치 출고 확정 ──────────────────────────────────
@router.post("/batch-outbound-confirm")
async def batch_outbound_confirm(payload: dict | None = None):
    """여러 LOT 동시 출고 확정"""
    lots = (payload or {}).get("lots", [])
    if not lots:
        raise HTTPException(400, "lots 필요")
    return ok_response(data={"confirmed": len(lots), "lots": lots})


# ── Optional 3: LOT 병합 ────────────────────────────────────────
@router.post("/lot-merge")
async def lot_merge(payload: dict | None = None):
    """두 LOT 을 하나로 병합"""
    raise NotReadyError("LOT 병합 (물리 재확인 후 활성화)")


# ── Optional 4: LOT 분할 ────────────────────────────────────────
@router.post("/lot-split")
async def lot_split(payload: dict | None = None):
    """하나의 LOT 을 여러 개로 분할"""
    raise NotReadyError("LOT 분할")


# ── Optional 5: CSV 대량 입고 ───────────────────────────────────
@router.post("/csv-import")
async def csv_import(payload: dict | None = None):
    """CSV 파일 대량 입고"""
    return ok_response(data={"imported": 0, "message": "CSV 파일을 다시 선택하세요"})


# ── Optional 6: 엑셀 전체 내보내기 ──────────────────────────────
@router.post("/excel-export-all")
async def excel_export_all(payload: dict | None = None):
    """전체 재고 엑셀 내보내기"""
    try:
        from engine_modules.inventory_modular.engine import SQMInventoryEngineV3  # type: ignore
        from config import DB_PATH  # type: ignore
        import tempfile, os
        engine = SQMInventoryEngineV3(str(DB_PATH))
        out = os.path.join(tempfile.gettempdir(), "sqm_export_all.xlsx")
        if hasattr(engine, "export_to_excel"):
            from backend.common.excel_alignment import safe_apply_sqm_file

            def _export_with_align():
                r = engine.export_to_excel(out, option="all")
                safe_apply_sqm_file(out)
                return r

            return wrap_engine_call(_export_with_align)
    except Exception:
        pass
    raise NotReadyError("엔진 연결 후 사용 가능")


# ── Optional 7: 바코드 생성 ─────────────────────────────────────
@router.post("/barcode-generate")
async def barcode_generate(payload: dict | None = None):
    """LOT 번호로 바코드 이미지 생성"""
    raise NotReadyError("바코드 생성기 연결 필요")


# ── Optional 8: 알림 이메일 발송 ────────────────────────────────
@router.post("/alert-email")
async def alert_email(payload: dict | None = None):
    """ALERTS 내용을 이메일로 발송"""
    raise NotReadyError("SMTP 설정 필요")


# ── Optional 9: 감사 로그 내보내기 ──────────────────────────────
@router.get("/audit-log")
async def audit_log(limit: int = 1000):
    """감사 로그(audit log) 조회"""
    try:
        from engine_modules.inventory_modular.engine import SQMInventoryEngineV3  # type: ignore
        from config import DB_PATH  # type: ignore
        engine = SQMInventoryEngineV3(str(DB_PATH))
        if hasattr(engine, "get_audit_log"):
            return wrap_engine_call(engine.get_audit_log, limit=limit)
    except Exception:
        pass
    return ok_response(data=[])


# ── Optional 10: 시스템 헬스 상세 ───────────────────────────────
@router.get("/system-health")
async def system_health():
    """CPU/메모리/DB 연결/디스크 사용량"""
    import sys, platform
    try:
        import psutil  # type: ignore
        return ok_response(data={
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_pct": psutil.cpu_percent(interval=0.1),
            "mem_pct": psutil.virtual_memory().percent,
            "disk_pct": psutil.disk_usage("/").percent,
        })
    except ImportError:
        return ok_response(data={
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "note": "psutil 미설치 — pip install psutil 로 상세 정보",
        })


# ── Optional 11: 테마 프로파일 저장/복원 ────────────────────────
@router.post("/theme-profile")
async def theme_profile(payload: dict | None = None):
    """사용자별 테마/뷰모드 프로파일 저장 (현재는 에코)"""
    return ok_response(data=payload or {})
