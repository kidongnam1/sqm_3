"""
SQM v8.6.6 - FastAPI common error module
=========================================
- ApiError: 프로젝트 표준 예외
- wrap_engine_call: 엔진 호출 래퍼 (HTTP 로 예외 승격)
- install_exception_handlers: 앱 레벨 핸들러 등록

Phase 2 Step 3 (2026-04-21):
  NotReadyError: HTTP 501 -> HTTP 200 + body.ok=false
  이유: DevTools Console 은 4xx/5xx 를 빨간색으로 칠해서
        의도된 "준비 중" 안내도 실제 에러처럼 보임.
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("sqm.api")


# ========== Response Formatters ==========
def ok_response(data: Any = None, message: str | None = None) -> dict:
    """표준 성공 응답 포맷"""
    return {"ok": True, "data": data, "error": None, "message": message}


def err_response(error: str, detail: Any = None) -> dict:
    """표준 에러 응답 포맷 (JSON body 용)"""
    return {"ok": False, "data": None, "error": error, "detail": detail}


# ========== Exception Classes ==========
class ApiError(Exception):
    """프로젝트 표준 예외 (HTTP status + 메시지)"""

    def __init__(self, code: int, message: str, detail: Any = None):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotReadyError(ApiError):
    """
    아직 구현되지 않은 기능.
    Phase 2 Step 3: HTTP 200 + body.ok=false + detail.code=NOT_READY.
    프론트: body.ok===false && detail?.code==='NOT_READY' -> info toast.
    """

    def __init__(self, feature: str = ""):
        super().__init__(
            200,
            f"NotReady{' - ' + feature if feature else ''}",
            detail={"code": "NOT_READY", "feature": feature},
        )


# ========== Engine Call Wrapper ==========
def wrap_engine_call(fn: Callable, *args, **kwargs) -> dict:
    """
    Tkinter 핸들러를 HTTP 응답으로 승격하는 표준 래퍼.
    - NotImplementedError -> HTTP 200 + body.ok=false (soft-fail)
    - FileNotFoundError -> HTTP 404
    - PermissionError -> HTTP 403
    - ValueError / TypeError -> HTTP 400
    - Exception -> HTTP 500
        """
    try:
        result = fn(*args, **kwargs)
        return ok_response(data=result)
    except NotImplementedError:
        return err_response("기능 준비 중", code="NOT_READY")
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ========== App-Level Exception Handlers ==========
def install_exception_handlers(app: FastAPI) -> None:
    """
    FastAPI 앱에 표준 예외 핸들러 등록.
    ApiError / NotReadyError → JSON 응답으로 변환.
    """

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        # NotReadyError (code=200) → ok=false body
        if exc.code == 200:
            return JSONResponse(
                status_code=200,
                content={"ok": False, "data": None, "error": exc.message, "detail": exc.detail},
            )
        return JSONResponse(
            status_code=exc.code,
            content={"ok": False, "data": None, "error": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        log.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "data": None, "error": str(exc), "detail": None},
        )
