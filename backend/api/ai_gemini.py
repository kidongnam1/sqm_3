"""
Gemini AI API — v8.6.6 신규 (1차 작업)
=========================================
v8.6.6의 검증된 features/ai/gemini_utils.py를 thin wrapper로 노출.

엔드포인트:
- GET  /api/ai/settings    → 현재 키/모델/사용여부 조회 (키는 마스킹)
- POST /api/ai/settings    → API 키 저장 (keyring 우선, ini fallback)
- POST /api/ai/toggle      → 사용 ON/OFF
- GET  /api/ai/test        → API 연결 테스트 (간단한 핑)
"""
import logging
import os
import configparser
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["AI"])


# ── Schemas ────────────────────────────────────────────────────
class ApiKeyPayload(BaseModel):
    api_key: str
    model: str = ""  # 선택


class TogglePayload(BaseModel):
    enabled: bool


# ── Helpers ────────────────────────────────────────────────────
def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _fresh_api_key():
    """
    매번 호출 시 환경변수 → keyring → settings.ini 순으로 직접 읽기.
    Python 모듈 캐시 우회 (백엔드 재시작 없이 새 키 인식).
    Returns: (key, source, model)
    """
    # 1. 환경변수
    key = (os.environ.get("GEMINI_API_KEY", "") or "").strip()
    model_env = (os.environ.get("GEMINI_MODEL", "") or "").strip()
    if key and not key.startswith("your-"):
        return key, "ENV", model_env or "gemini-2.5-flash"

    # 2. keyring
    try:
        import keyring
        kr_key = keyring.get_password("SQM_Inventory", "GEMINI_API_KEY")
        if kr_key and kr_key.strip():
            return kr_key.strip(), "KEYRING", model_env or "gemini-2.5-flash"
    except Exception as _e:
        logger.debug(f"keyring 조회 suppressed: {_e}")

    # 3. settings.ini 직접 읽기
    try:
        from config import SETTINGS_FILE
        if SETTINGS_FILE.exists():
            cfg = configparser.ConfigParser()
            cfg.read(SETTINGS_FILE, encoding="utf-8")
            ini_key = (cfg.get("Gemini", "api_key", fallback="") or "").strip()
            ini_model = (cfg.get("Gemini", "model", fallback="") or "").strip()
            if ini_key and not ini_key.startswith("your-") and not ini_key.startswith("# "):
                return ini_key, "INI", ini_model or model_env or "gemini-2.5-flash"
    except Exception as _e:
        logger.debug(f"ini 조회 suppressed: {_e}")

    return "", "NONE", model_env or "gemini-2.5-flash"


# ── 설정 조회 ──────────────────────────────────────────────────
@router.get("/settings", summary="🔐 Gemini API 설정 조회")
def get_settings():
    try:
        # 매번 fresh 읽기 (백엔드 재시작 없이도 변경 반영)
        key, source, model = _fresh_api_key()
        try:
            from config import USE_GEMINI_DEFAULT
            enabled = bool(USE_GEMINI_DEFAULT)
        except Exception:
            enabled = True
        return {
            "success": True,
            "api_key_masked": _mask_key(key),
            "has_key": bool(key),
            "model": model,
            "enabled": enabled,
            "key_source": source,  # ENV / KEYRING / INI / NONE
        }
    except Exception as e:
        logger.exception("get_settings error")
        raise HTTPException(500, f"설정 조회 실패: {e}")


# ── API 키 저장 ────────────────────────────────────────────────
@router.post("/settings", summary="🔐 Gemini API 키 저장")
def save_settings(payload: ApiKeyPayload):
    if not payload.api_key or not payload.api_key.strip():
        raise HTTPException(400, "API 키가 비어있습니다")
    try:
        from config import save_api_key_secure, save_gemini_model
        source = save_api_key_secure(payload.api_key.strip())
        if source == "FAILED":
            raise HTTPException(500, "API 키 저장 실패")
        if payload.model and payload.model.strip():
            save_gemini_model(payload.model.strip())
        # Gemini Client 싱글턴 리셋 (다음 호출 시 새 키로 재생성)
        try:
            from features.ai.gemini_utils import reset_gemini_client
            reset_gemini_client()
        except Exception as _e:
            logger.debug(f"reset_gemini_client suppressed: {_e}")
        return {
            "success": True,
            "message": f"API 키가 {source}에 저장되었습니다. 다음 실행부터 적용됩니다.",
            "source": source,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("save_settings error")
        raise HTTPException(500, f"저장 실패: {e}")


# ── 사용 토글 ──────────────────────────────────────────────────
@router.post("/toggle", summary="🔀 Gemini AI 사용 ON/OFF")
def toggle_ai(payload: TogglePayload):
    try:
        import configparser
        from config import SETTINGS_FILE
        config = configparser.ConfigParser()
        if SETTINGS_FILE.exists():
            config.read(SETTINGS_FILE, encoding="utf-8")
        if not config.has_section("Gemini"):
            config.add_section("Gemini")
        config.set("Gemini", "use_gemini", "true" if payload.enabled else "false")
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            config.write(f)
        return {
            "success": True,
            "enabled": payload.enabled,
            "message": f"Gemini AI 사용을 {'켰습니다' if payload.enabled else '껐습니다'}. 다음 실행부터 적용됩니다.",
        }
    except Exception as e:
        logger.exception("toggle_ai error")
        raise HTTPException(500, f"토글 실패: {e}")


# ── API 연결 테스트 ────────────────────────────────────────────
@router.get("/test", summary="🧪 Gemini API 연결 테스트")
def test_connection():
    """
    짧은 핑 프롬프트를 보내 키/모델/네트워크가 정상인지 검증.
    매번 fresh 키 읽기 + Client 강제 재생성 (캐시 무시).
    """
    # 1. fresh 키 읽기 (백엔드 캐시 우회)
    key, source, model = _fresh_api_key()
    if not key:
        return {
            "success": False,
            "ok": False,
            "message": "❌ API 키를 찾을 수 없음 (환경변수 GEMINI_API_KEY, keyring, settings.ini 모두 비어있음)",
            "source": "NONE",
        }

    # 2. google-genai 패키지 확인
    try:
        from google import genai
    except ImportError:
        return {
            "success": False,
            "ok": False,
            "message": "❌ google-genai 패키지 미설치. pip install google-genai",
            "source": source,
        }

    # 3. Client 강제 재생성 (캐시 무시)
    try:
        from features.ai.gemini_utils import reset_gemini_client, call_gemini_safe
        reset_gemini_client()
        client = genai.Client(api_key=key)
    except Exception as e:
        return {
            "success": False,
            "ok": False,
            "message": f"❌ Client 생성 실패: {e}",
            "source": source,
        }

    # 4. 핑 호출
    try:
        resp = call_gemini_safe(
            client=client,
            model_name=model,
            contents="ping",
            timeout=15,
            temperature=0.0,
            max_output_tokens=16,
        )
        text = ""
        try:
            text = (resp.text or "").strip() if resp else ""
        except Exception:
            text = ""
        return {
            "success": True,
            "ok": True,
            "model": model,
            "source": source,
            "key_masked": _mask_key(key),
            "reply": text or "(응답 비어있음)",
            "message": f"✅ {model} 연결 성공 (키 출처: {source})",
        }
    except TimeoutError:
        return {"success": False, "ok": False, "source": source, "message": "⏱ 타임아웃 (15초 초과)"}
    except PermissionError:
        return {"success": False, "ok": False, "source": source, "message": f"🔐 API 키 인증 실패 (401) — 키 출처: {source}, 마스킹: {_mask_key(key)}"}
    except RuntimeError as e:
        return {"success": False, "ok": False, "source": source, "message": f"⚠️ 할당량/런타임 에러: {e}"}
    except Exception as e:
        logger.exception("test_connection error")
        return {"success": False, "ok": False, "source": source, "message": f"❌ 연결 실패: {e}"}
