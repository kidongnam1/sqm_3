# tests/conftest.py
# SQM v8.6.5 — pytest 공통 설정
# 역할: Gemini API Key 없는 환경(CI/Linux)에서 integration 마커 테스트 자동 skip
# 작성: 2026-04-30 Ruby

import os
import configparser
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _detect_gemini_key() -> bool:
    """Gemini API Key 존재 여부를 2가지 경로로 확인한다."""
    # 1순위: 환경 변수 (CI 파이프라인 표준 방식)
    if os.environ.get("GEMINI_API_KEY", "").strip():
        return True
    # 2순위: settings.ini (사장님 PC 방식)
    ini_path = ROOT / "settings.ini"
    if ini_path.exists():
        cfg = configparser.ConfigParser()
        cfg.read(ini_path, encoding="utf-8")
        for section in cfg.sections():
            key = cfg.get(section, "gemini_api_key", fallback="").strip()
            if key and key not in ("", "YOUR_API_KEY_HERE", "None", "none"):
                return True
    return False


# 모듈 로드 시 1회 평가 → 빠름
_GEMINI_AVAILABLE = _detect_gemini_key()


def pytest_collection_modifyitems(config, items):
    """
    @pytest.mark.integration 테스트를 Gemini Key 없는 환경에서 자동 skip.
    수동으로 실행하려면: pytest -m integration --run-integration
    """
    if _GEMINI_AVAILABLE:
        return  # 키 있으면 아무것도 안 함

    skip_marker = pytest.mark.skip(
        reason="Gemini API Key 없음 — GEMINI_API_KEY 환경변수 또는 settings.ini 설정 필요"
    )
    for item in items:
        if item.get_closest_marker("integration"):
            item.add_marker(skip_marker)
