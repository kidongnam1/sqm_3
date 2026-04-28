"""
v864.3 Debug Visibility — 프론트엔드 에러 수집 엔드포인트

프론트에서 window.onerror / unhandledrejection / console.error 가 발생하면
main_webview.py 의 JS 브리지가 POST /api/log/frontend-error 로 전송.
여기서 받아 파이썬 로그에 기록 → sqm_debug.log 에 모든 프론트 에러가 백엔드 로그와 함께 남음.
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/log", tags=["debug"])
log = logging.getLogger("frontend")


@router.post("/frontend-error")
async def frontend_error(request: Request):
    """프론트엔드 에러를 수집하여 파이썬 로그에 기록.

    기대 payload (main_webview.py JS 브리지 기준):
        {
          "kind": "error" | "unhandledrejection" | "console.error",
          "message": str,
          "source": str,  # optional
          "line": int,    # optional
          "col": int,     # optional
          "stack": str,   # optional
          "url": str,
          "ua": str
        }
    """
    try:
        payload = await request.json()
    except Exception as e:
        log.error(f"[FE] payload parse failed: {e}")
        return JSONResponse({"ok": False, "detail": "bad_json"}, status_code=400)

    kind = str(payload.get("kind", "?"))
    message = str(payload.get("message", ""))
    source = str(payload.get("source", ""))
    line = payload.get("line", 0)
    col = payload.get("col", 0)
    stack = str(payload.get("stack", ""))
    url = str(payload.get("url", ""))

    header = f"[FE-{kind}] {message}"
    if source:
        header += f"  @ {source}:{line}:{col}"
    if url:
        header += f"  (page={url})"

    if kind == "console.error":
        log.warning(header)
    else:
        # error / unhandledrejection 은 ERROR 레벨
        if stack:
            log.error(header + "\nSTACK:\n" + stack)
        else:
            log.error(header)

    return {"ok": True}


@router.get("/ping")
async def ping():
    """디버그 라우터 살아있는지 확인용"""
    return {"ok": True, "router": "debug_log"}
