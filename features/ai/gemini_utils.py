"""
SQM 재고관리 - Gemini API 공통 유틸리티 (v3.6.9)
==================================================

모든 Gemini API 호출의 공통 기능:
- Client 싱글턴 (앱당 1개 인스턴스)
- 타임아웃 지원 (기본 30초)
- 에러별 안내 메시지
- 모델명 중앙 관리
"""

import concurrent.futures
import logging
import os
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# 싱글턴 Client
# ═══════════════════════════════════════════════════════════════════════

_client_lock = threading.Lock()
_client_instance = None
_client_api_key = None


def get_gemini_client(api_key: str = None):
    """
    Gemini Client 싱글턴 반환
    
    동일 API 키에 대해 Client를 재사용합니다.
    API 키가 변경되면 새 Client를 생성합니다.
    
    Args:
        api_key: Gemini API 키 (없으면 config/환경변수에서 로드)
    
    Returns:
        genai.Client 또는 None
    """
    global _client_instance, _client_api_key

    if not api_key:
        api_key = _get_api_key()

    if not api_key:
        return None

    with _client_lock:
        if _client_instance is not None and _client_api_key == api_key:
            return _client_instance

        try:
            from google import genai
            _client_instance = genai.Client(api_key=api_key)
            _client_api_key = api_key
            logger.info("Gemini Client 생성 완료")
            return _client_instance
        except ImportError:
            logger.warning("google-genai 패키지 미설치: pip install google-genai")
            return None
        except (ImportError, ModuleNotFoundError) as e:
            logger.error(f"Gemini Client 생성 실패: {e}")
            return None


def reset_gemini_client():
    """Client 싱글턴 초기화 (API 키 변경 시 호출)"""
    global _client_instance, _client_api_key
    with _client_lock:
        _client_instance = None
        _client_api_key = None
        logger.info("Gemini Client 초기화됨")


def _get_api_key() -> str:
    """API 키 로드 (환경변수 → config → settings.ini 순)"""
    # 1. 환경변수
    key = os.environ.get('GEMINI_API_KEY', '')
    if key and not key.startswith('your-'):
        return key

    # 2. config.py
    try:
        from core.config import GEMINI_API_KEY
        if GEMINI_API_KEY and not GEMINI_API_KEY.startswith('your-'):
            return GEMINI_API_KEY
    except ImportError as _e:
        logger.debug(f"Suppressed: {_e}")

    return ''


# ═══════════════════════════════════════════════════════════════════════
# 모델명 중앙 관리
# ═══════════════════════════════════════════════════════════════════════

def get_model_name() -> str:
    """현재 설정된 Gemini 모델명 반환"""
    try:
        from core.config import GEMINI_MODEL
        if GEMINI_MODEL:
            return GEMINI_MODEL
    except ImportError as _e:
        logger.debug(f"Suppressed: {_e}")
    return "gemini-2.5-flash"


# ═══════════════════════════════════════════════════════════════════════
# 타임아웃 지원 API 호출
# ═══════════════════════════════════════════════════════════════════════

def call_gemini_safe(
    client,
    model_name: str,
    contents,
    timeout: int = 30,
    temperature: float = 0.1,
    max_output_tokens: int = 4096
) -> Optional[Any]:
    """
    타임아웃 + 에러 핸들링이 포함된 Gemini API 호출
    
    Args:
        client: genai.Client 인스턴스
        model_name: 모델명 (예: "gemini-2.5-flash")
        contents: 프롬프트 (str, list, 또는 Content 객체)
        timeout: 타임아웃 초 (기본 30)
        temperature: 생성 온도 (기본 0.1)
        max_output_tokens: 최대 출력 토큰 (기본 4096)
    
    Returns:
        response 객체 또는 None (실패 시)
    
    Raises:
        TimeoutError: 타임아웃 초과
        ConnectionError: 네트워크 오류
        PermissionError: API 키 오류 (401)
        RuntimeError: 할당량 초과 (429)
    """
    if not client:
        raise ValueError("Gemini Client가 None입니다")

    def _api_call():
        return client.models.generate_content(
            model=model_name,
            contents=contents
        )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_api_call)
            try:
                result = future.result(timeout=timeout)
                return result
            except concurrent.futures.TimeoutError:
                logger.error(f"Gemini API 타임아웃 ({timeout}초)")
                raise TimeoutError(
                    f"Gemini API 응답 시간 초과 ({timeout}초)\n"
                    f"네트워크 상태를 확인하거나 타임아웃을 늘려주세요."
                )
    except TimeoutError:
        raise  # 그대로 전파
    except (ValueError, TypeError, AttributeError) as e:
        error_msg = str(e).lower()

        # 에러별 구체적 안내
        if '401' in error_msg or 'unauthorized' in error_msg or 'invalid api key' in error_msg:
            raise PermissionError(
                "API 키가 유효하지 않습니다.\n"
                "settings.ini의 api_key를 확인하세요.\n"
                "https://aistudio.google.com/apikey 에서 새 키를 발급받을 수 있습니다."
            )
        elif '429' in error_msg or 'rate limit' in error_msg or 'quota' in error_msg:
            raise RuntimeError(
                "API 호출 한도를 초과했습니다.\n"
                "잠시 후 다시 시도하거나, Google AI Studio에서 할당량을 확인하세요."
            )
        elif '503' in error_msg or 'unavailable' in error_msg:
            raise ConnectionError(
                "Gemini API 서비스가 일시적으로 불가합니다.\n"
                "잠시 후 다시 시도해주세요."
            )
        elif '404' in error_msg or 'not found' in error_msg:
            raise ValueError(
                f"모델 '{model_name}'을 찾을 수 없습니다.\n"
                f"settings.ini의 model 설정을 확인하세요."
            )
        else:
            raise


# ═══════════════════════════════════════════════════════════════════════
# 제품명 매핑 (공통)
# ═══════════════════════════════════════════════════════════════════════

PRODUCT_MAPPING = {
    # 리튬카보네이트
    "리튬카보네이트": "LITHIUM CARBONATE",
    "리튬 카보네이트": "LITHIUM CARBONATE",
    "탄산리튬": "LITHIUM CARBONATE",
    "lithium carbonate": "LITHIUM CARBONATE",
    "lc": "LITHIUM CARBONATE",

    # 리튬하이드록사이드
    "리튬하이드록사이드": "LITHIUM HYDROXIDE",
    "리튬 하이드록사이드": "LITHIUM HYDROXIDE",
    "수산화리튬": "LITHIUM HYDROXIDE",
    "lithium hydroxide": "LITHIUM HYDROXIDE",
    "lh": "LITHIUM HYDROXIDE",

    # 리튬클로라이드
    "리튬클로라이드": "LITHIUM CHLORIDE",
    "리튬 클로라이드": "LITHIUM CHLORIDE",
    "염화리튬": "LITHIUM CHLORIDE",
    "lithium chloride": "LITHIUM CHLORIDE",
    "lcl": "LITHIUM CHLORIDE",

    # 포타슘클로라이드
    "포타슘클로라이드": "POTASSIUM CHLORIDE",
    "포타슘 클로라이드": "POTASSIUM CHLORIDE",
    "염화칼륨": "POTASSIUM CHLORIDE",
    "potassium chloride": "POTASSIUM CHLORIDE",
    "kcl": "POTASSIUM CHLORIDE",

    # 소듐나이트레이트
    "소듐나이트레이트": "SODIUM NITRATE",
    "소듐 나이트레이트": "SODIUM NITRATE",
    "질산나트륨": "SODIUM NITRATE",
    "sodium nitrate": "SODIUM NITRATE",
    "sn": "SODIUM NITRATE",
}


def normalize_product_name(name: str) -> str:
    """제품명 정규화 (한글/약어 → DB 표준명)"""
    if not name:
        return ''
    return PRODUCT_MAPPING.get(name.strip().lower(), name.strip().upper())
