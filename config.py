"""
SQM 재고관리 시스템 - 설정 모듈
================================

v3.6.0: Docstring 보강

모듈 개요:
    시스템 전역 설정을 관리합니다. 경로, 데이터베이스, API, UI, 
    로깅 등 모든 설정이 이 모듈에서 정의됩니다.

주요 설정:
    - DB_TYPE: 데이터베이스 유형 ('sqlite' 또는 'postgresql')
    - DB_PATH: SQLite 데이터베이스 파일 경로
    - PG_*: PostgreSQL 연결 설정
    - GEMINI_API_KEY: Gemini API 키
    - UI_THEME: ttkbootstrap 테마

주요 함수:
    - validate_api_key(): API 키 유효성 검사
    - validate_api_key_with_gui(): GUI 경고창 포함 검증
    - safe_file_backup(): 안전한 파일 백업
    - smart_path_recovery(): 경로 자동 복구
    - sql_*(): SQL 호환 함수들

사용 예시:
    >>> from config import DB_PATH, DB_TYPE, GEMINI_API_KEY
    >>> 
    >>> # API 키 검증
    >>> valid, error = validate_api_key()
    >>> 
    >>> # 안전한 백업
    >>> success, path = safe_file_backup('data.db')
    >>> 
    >>> # SQL 호환 함수
    >>> query = f"SELECT {sql_group_concat('lot_no')} FROM inventory"

환경변수:
    - SQM_DB_TYPE: 데이터베이스 유형 (기본: sqlite)
    - SQM_PG_HOST: PostgreSQL 호스트
    - SQM_PG_PORT: PostgreSQL 포트
    - SQM_PG_DATABASE: PostgreSQL 데이터베이스명
    - SQM_PG_USER: PostgreSQL 사용자
    - SQM_PG_PASSWORD: PostgreSQL 비밀번호
    - GEMINI_API_KEY: Gemini API 키

작성자: Ruby (남기동)
버전: v3.6.0
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# =============================================================================
# 프로젝트 정보 (★ v2.5.4: 버전 단일화)
# =============================================================================

try:
    from version import APP_NAME, APP_NAME_EN, __version__
except ImportError:
    __version__ = "0.0.0"  # S2-3: version.py 누락 시 fallback
    import logging as _vlog
    _vlog.getLogger(__name__).warning("[버전] version.py 로드 실패 → fallback 0.0.0")
    APP_NAME = "SQM 재고관리 시스템"
    APP_NAME_EN = "SQM Inventory Management System"

APP_VERSION = __version__  # 하위 호환성 유지

# =============================================================================
# 경로 설정
# =============================================================================

# 기본 디렉토리 (실행 파일 위치 기준)
BASE_DIR = Path(__file__).parent.absolute()

# 데이터 디렉토리
DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR / "db"
OUTPUT_DIR = BASE_DIR / "output"
BACKUP_DIR = BASE_DIR / "backup"
LOG_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

# 디렉토리 자동 생성
for dir_path in [DATA_DIR, DB_DIR, OUTPUT_DIR, BACKUP_DIR, LOG_DIR, TEMP_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 데이터베이스 설정
# =============================================================================

# ★★★ v3.6.0: PostgreSQL 지원 (기본값: SQLite) ★★★
# DB_TYPE: 'sqlite' 또는 'postgresql'
DB_TYPE = os.environ.get('SQM_DB_TYPE', 'sqlite')  # 기본값: sqlite (나중에 postgresql 전환 용이)

# SQLite 설정 (DB_TYPE='sqlite' 일 때 사용)
DB_PATH = DB_DIR / "sqm_inventory.db"
DB_TIMEOUT = 30.0  # 초
DB_WAL_MODE = True  # WAL 모드 활성화

# v8.1.5: Picking List 자재코드 상수
PICKING_MAIN_MATERIAL_CODE   = "30000008"   # 리튬카보네이트 본품
PICKING_SAMPLE_MATERIAL_CODE = "30000010"   # 리튬카보네이트 샘플
PICKING_DEFAULT_CONTAINERS   = 15           # 컨테이너 수 기본값

# Export 경로
EXPORT_DIR = OUTPUT_DIR

# PostgreSQL 설정 (DB_TYPE='postgresql' 일 때 사용)
PG_HOST = os.environ.get('SQM_PG_HOST', 'localhost')
PG_PORT = int(os.environ.get('SQM_PG_PORT', '5432'))
PG_DATABASE = os.environ.get('SQM_PG_DATABASE', 'sqm_inventory')
PG_USER = os.environ.get('SQM_PG_USER', 'postgres')
PG_PASSWORD = os.environ.get('SQM_PG_PASSWORD', 'postgres')

# PostgreSQL 연결 풀 설정
PG_MIN_CONNECTIONS = int(os.environ.get('SQM_PG_MIN_CONN', '2'))
PG_MAX_CONNECTIONS = int(os.environ.get('SQM_PG_MAX_CONN', '10'))

def get_pg_connection_string():
    """PostgreSQL 연결 문자열 반환"""
    return f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"

def get_db_info():
    """현재 DB 설정 정보 반환"""
    if DB_TYPE == 'postgresql':
        return {
            'type': 'PostgreSQL',
            'host': PG_HOST,
            'port': PG_PORT,
            'database': PG_DATABASE,
            'user': PG_USER,
        }
    else:
        return {
            'type': 'SQLite',
            'path': str(DB_PATH),
        }

# =============================================================================
# 백업 설정 (개선 #1)
# =============================================================================

BACKUP_ENABLED = True
BACKUP_MAX_COUNT = 5  # 최대 백업 파일 수
BACKUP_BEFORE_IMPORT = True  # 가져오기 전 자동 백업
BACKUP_BEFORE_DELETE = True  # 삭제 전 자동 백업
BACKUP_INTERVAL_HOURS = 24  # 최소 백업 간격 (시간)

# =============================================================================
# API 설정 (v2.8.0: 환경변수 우선, settings.ini 폴백)
# =============================================================================

import configparser

# settings.ini 파일 경로
SETTINGS_FILE = BASE_DIR / "settings.ini"

def _load_settings():
    """
    settings.ini 파일에서 설정 읽기
    
    ★★★ v3.9.7: 보안 강화 ★★★
    1. 환경변수 우선 (GEMINI_API_KEY)
    2. keyring (OS 자격증명 관리자) 2순위
    3. settings.ini는 폴백용 + 자동 마이그레이션
    """
    config = configparser.ConfigParser()

    # 기본값
    defaults = {
        'api_key': '',
        'model': 'gemini-2.5-flash',
        'use_gemini': 'true',
        'theme': 'darkly',
        'openai_api_key': '',
        'openai_model': 'gpt-4o',
        'save_raw_gemini_response': False,   # v5.5.2: 디버깅 시 Gemini 원문을 logs/에 저장 (ON/OFF)
        'disable_openai_fallback': False,     # v5.5.2: True면 OpenAI 폴백 비활성 (Gemini-only)
    }

    # ★★★ 1순위: 환경변수 ★★★
    env_api_key = os.environ.get('GEMINI_API_KEY', '')
    env_model = os.environ.get('GEMINI_MODEL', '')
    os.environ.get('SQM_DB_PATH', '')
    env_openai_key = os.environ.get('OPENAI_API_KEY', '')
    env_openai_model = os.environ.get('OPENAI_MODEL', '')
    env_save_raw = os.environ.get('SQM_SAVE_RAW_GEMINI_RESPONSE', '')

    result = defaults.copy()

    if env_api_key:
        result['api_key'] = env_api_key
        result['api_key_source'] = 'ENV'

    if env_model:
        result['model'] = env_model

    if env_openai_key:
        result['openai_api_key'] = env_openai_key
    if env_openai_model:
        result['openai_model'] = env_openai_model
    if env_save_raw and str(env_save_raw).strip().lower() in ('1', 'true', 'yes'):
        result['save_raw_gemini_response'] = True

    # ★★★ 2순위: keyring (OS 자격증명 관리자) ★★★
    if not result.get('api_key'):
        try:
            import keyring
            kr_key = keyring.get_password('SQM_Inventory', 'GEMINI_API_KEY')
            if kr_key:
                result['api_key'] = kr_key
                result['api_key_source'] = 'KEYRING'
        except (ImportError, Exception) as e:
            logger.debug(f"Suppressed: keyring 미설치 또는 오류 — 건너뜀: {e}")

    if SETTINGS_FILE.exists():
        try:
            config.read(SETTINGS_FILE, encoding='utf-8')

            # ★★★ 3순위: ini 파일 (+ 자동 마이그레이션) ★★★
            if not result.get('api_key') or result.get('api_key_source') is None:
                ini_key = config.get('Gemini', 'api_key', fallback='')
                if ini_key and not ini_key.startswith('your-'):
                    result['api_key'] = ini_key
                    result['api_key_source'] = 'INI'
                    logger.debug("⚠️ [보안경고] API 키가 settings.ini에 평문 저장되어 있습니다!")
                    logger.debug("   자동으로 OS 자격증명에 이관을 시도합니다...")
                    # v3.9.7: keyring으로 자동 이관 시도
                    _migrate_api_key_to_keyring(ini_key, config)

            result['model'] = config.get('Gemini', 'model', fallback=result['model'])
            result['use_gemini'] = config.getboolean('Parser', 'use_gemini', fallback=True)
            result['theme'] = config.get('UI', 'theme', fallback=defaults['theme'])
            if config.has_section('OpenAI'):
                result['openai_api_key'] = config.get('OpenAI', 'api_key', fallback=result.get('openai_api_key', ''))
                result['openai_model'] = config.get('OpenAI', 'model', fallback=result.get('openai_model', 'gpt-4o'))
            if config.has_section('Debug'):
                result['save_raw_gemini_response'] = config.getboolean('Debug', 'save_raw_gemini_response', fallback=result.get('save_raw_gemini_response', False))
            if config.has_section('Parser'):
                result['disable_openai_fallback'] = config.getboolean('Parser', 'disable_openai_fallback', fallback=result.get('disable_openai_fallback', False))

        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"⚠️ settings.ini 읽기 오류: {e}")

    return result


def _migrate_api_key_to_keyring(api_key: str, config: configparser.ConfigParser) -> bool:
    """v3.9.7: API 키를 settings.ini → keyring(OS 자격증명)으로 이관"""
    try:
        import keyring
        keyring.set_password('SQM_Inventory', 'GEMINI_API_KEY', api_key)

        # ini에서 키 제거 (주석으로 대체)
        config.set('Gemini', 'api_key', '# MIGRATED_TO_KEYRING')
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            config.write(f)

        logger.debug("   ✅ API 키가 OS 자격증명 관리자로 안전하게 이관되었습니다.")
        return True
    except ImportError:
        logger.debug("   ℹ️ keyring 미설치. pip install keyring 으로 설치하면 자동 이관됩니다.")
        return False
    except (OSError, IOError, PermissionError) as e:
        logger.info(f"   ⚠️ keyring 이관 실패: {e}")
        return False


def save_api_key_secure(api_key: str) -> str:
    """v3.9.7: API 키를 가장 안전한 방법으로 저장 (GUI에서 호출)"""
    # 1순위: keyring
    try:
        import keyring
        keyring.set_password('SQM_Inventory', 'GEMINI_API_KEY', api_key)
        return 'KEYRING'
    except (ImportError, Exception) as _e:
        logger.debug(f"Suppressed: {_e}")

    # 2순위: 환경변수 안내
    # (실제 환경변수 설정은 사용자가 해야 하므로 ini에 저장)
    try:
        config = configparser.ConfigParser()
        if SETTINGS_FILE.exists():
            config.read(SETTINGS_FILE, encoding='utf-8')
        if not config.has_section('Gemini'):
            config.add_section('Gemini')
        config.set('Gemini', 'api_key', api_key)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            config.write(f)
        return 'INI'
    except (OSError, IOError, PermissionError):
        return 'FAILED'


def save_gemini_model(model: str) -> bool:
    """Gemini 모델을 settings.ini [Gemini] model에 저장. 다음 실행부터 적용."""
    if not model or not model.strip():
        return False
    try:
        config = configparser.ConfigParser()
        if SETTINGS_FILE.exists():
            config.read(SETTINGS_FILE, encoding='utf-8')
        if not config.has_section('Gemini'):
            config.add_section('Gemini')
        config.set('Gemini', 'model', model.strip())
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            config.write(f)
        return True
    except (OSError, IOError, PermissionError):
        return False


# 설정 로드
_settings = _load_settings()

# Gemini API 설정
GEMINI_API_KEY = _settings['api_key']
GEMINI_MODEL = _settings['model']
USE_GEMINI_DEFAULT = _settings.get('use_gemini', True)
API_KEY_SOURCE = _settings.get('api_key_source', 'NONE')  # v2.8.0: 키 출처 추적

# OpenAI API 설정 (Gemini 실패 시 폴백용, 선택)
OPENAI_API_KEY = _settings.get('openai_api_key', '')
OPENAI_MODEL = _settings.get('openai_model', 'gpt-4o')

# v5.5.2: 디버깅/정책 옵션
SAVE_RAW_GEMINI_RESPONSE = _settings.get('save_raw_gemini_response', False)  # True면 logs/raw_pl_response.txt 등 저장
DISABLE_OPENAI_FALLBACK = _settings.get('disable_openai_fallback', False)    # True면 Gemini만 사용

# API 키 검증
def validate_api_key():
    """API 키 유효성 검사"""
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith('your-'):
        return False, "GEMINI_API_KEY가 설정되지 않았습니다. 환경변수 또는 settings.ini를 확인하세요."
    return True, ""

def get_api_key_warning():
    """v2.8.0: API 키 보안 경고 메시지 반환"""
    if API_KEY_SOURCE == 'INI':
        return ("⚠️ API 키가 settings.ini에 평문 저장됨\n"
                "환경변수 GEMINI_API_KEY 사용을 권장합니다.")
    return None


def get_settings():
    """설정 딕셔너리 반환 (GUI/파서용). gemini_api_key 등 키 제공."""
    return {
        'api_key': _settings.get('api_key', ''),
        'gemini_api_key': _settings.get('api_key', ''),
        'model': _settings.get('model', 'gemini-2.5-flash'),
        'use_gemini': _settings.get('use_gemini', True),
        'openai_api_key': _settings.get('openai_api_key', ''),
        'openai_model': _settings.get('openai_model', 'gpt-4o'),
    }

# =============================================================================
# UI 설정
# =============================================================================

UI_THEME = "darkly"  # v8.5.6: 다크 프로페셔널 테마 통일
UI_DARK_MODE = True
WINDOW_SIZE = "1200x800"
WINDOW_MIN_SIZE = (900, 600)

# =============================================================================
# 비즈니스 설정
# =============================================================================

# 제품 코드
PRODUCT_CODES = {
    "MIC9000": "LITHIUM CARBONATE 99.5%",
    "MIC9100": "LITHIUM CARBONATE 99.5% BG",
    "LC": "LITHIUM CARBONATE",
    "LH": "LITHIUM HYDROXIDE",
}

# 포장 단위
PACKING_UNITS = {
    "MX500": "MX 500 Kg (In Wooden Pallet)",
    "MX1000": "MX 1000 Kg (In Wooden Pallet)",
}

# 입력 검증 설정 (개선 #3)
VALIDATION = {
    'LOT_NO_MIN_LENGTH': 5,
    'LOT_NO_MAX_LENGTH': 20,
    'LOT_NO_PATTERN': r'^\d{8,11}$',  # 8~11자리 숫자 (OCR 오독 허용)
    'WEIGHT_MIN': 0,
    'WEIGHT_MAX': 50000,  # 50톤
    'SAP_NO_PATTERN': r'^\d{10}$',  # SAP No는 정확히 10자리 유지
}

# =============================================================================
# 로깅 설정 (P2: config_logging에서 구현, 하위 호환 re-export)
# =============================================================================
from config_logging import (
    setup_logging,
)

# =============================================================================
# 설정 유효성 검사
# =============================================================================

def validate_config():
    """
    전체 설정 유효성 검사

    Returns:
        (success, errors): 성공 여부 및 오류 목록
    """
    errors = []

    # 디렉토리 확인
    for dir_name, dir_path in [
        ('DATA_DIR', DATA_DIR),
        ('DB_DIR', DB_DIR),
        ('LOG_DIR', LOG_DIR),
    ]:
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except (ConnectionError, TimeoutError, ValueError) as e:
                errors.append(f"{dir_name} 생성 실패: {e}")

    # API 키 확인
    api_valid, api_error = validate_api_key()
    if not api_valid:
        errors.append(api_error)

    return len(errors) == 0, errors


# =============================================================================
# v3.6.0: API 키 GUI 검증 (안정성 강화)
# =============================================================================

def validate_api_key_with_gui(parent=None):
    """
    v3.6.0: GUI 실행 전 API 키 검증 및 경고창 표시
    
    Args:
        parent: 부모 윈도우 (None이면 루트 생성)
    
    Returns:
        bool: 계속 실행 여부 (True: 진행, False: 중단)
    """
    api_valid, api_error = validate_api_key()

    if not api_valid:
        try:
            import tkinter as tk

            from gui_app_modular.utils.custom_messagebox import CustomMessageBox

            # 임시 루트 윈도우 (숨김)
            if parent is None:
                temp_root = tk.Tk()
                temp_root.withdraw()

            CustomMessageBox.warning(None,
                "⚠️ API 설정 필요",
                "Gemini API 키가 설정되지 않았습니다.\n\n"
                "PDF 파싱 기능을 사용하려면:\n"
                "1. 메뉴 > 도구 > Gemini > 설정\n"
                "2. 또는 환경변수 GEMINI_API_KEY 설정\n\n"
                "API 키 없이도 기본 기능은 사용 가능합니다."
            )

            if parent is None:
                temp_root.destroy()

        except (RuntimeError, ValueError):
            logger.info(f"⚠️ API 키 미설정: {api_error}")

    return True  # 실행은 허용 (경고만 표시)


# =============================================================================
# 파일/경로 유틸 (P2: utils.file_utils에서 구현, 하위 호환 re-export)
# =============================================================================


# =============================================================================
# v5.7.8: SQL 호환 함수 — config_sql에서 구현, 하위 호환용 래퍼 (출고/리포트 참조)
# =============================================================================
from config_sql import (
    sql_auto_increment as _sql_auto_increment_impl,
)
from config_sql import (
    sql_date_format as _sql_date_format_impl,
)
from config_sql import (
    sql_group_concat as _sql_group_concat_impl,
)


def sql_group_concat(column: str, separator: str = ',') -> str:
    """DB 타입에 따른 문자열 집계. SQLite: GROUP_CONCAT, PostgreSQL: STRING_AGG"""
    return _sql_group_concat_impl(DB_TYPE, column, separator)


def sql_date_format(column: str, format_str: str) -> str:
    """DB 타입에 따른 날짜 포맷. SQLite: strftime, PostgreSQL: to_char"""
    return _sql_date_format_impl(DB_TYPE, column, format_str)


def sql_auto_increment() -> str:
    """자동 증가 컬럼 타입. SQLite: INTEGER PRIMARY KEY AUTOINCREMENT, PG: SERIAL PRIMARY KEY"""
    return _sql_auto_increment_impl(DB_TYPE)


# 모듈 로드 시 로깅 초기화
_logger = setup_logging()


# =============================================================================
# 출고(Outbound) 모드 설정 (★ v6.3.3: 랜덤출고/스캔즉시확정 기본)
# =============================================================================
# 리오님 운영 정책:
# - STEP1~3: TONBAG 미지정(사전 예약/선정/상태변경 금지)
# - STEP4: UID 스캔 = 즉시 확정(출고) + 원장 기록
#
# 기존 방식(예정 UID 대조 + PICKED→SOLD)은 옵션으로만 유지 가능
OUTBOUND_MODE = os.environ.get("SQM_OUTBOUND_MODE", "random_scan_confirm")
# 허용오차: ±0.1% (0.001)
OUTBOUND_WEIGHT_TOL_PCT = float(os.environ.get("SQM_OUTBOUND_WEIGHT_TOL_PCT", "0.001"))
# Undo: 최근 1건(관리자 전용) — 기능은 엔진에만 제공(연결은 UI 패치에서)
OUTBOUND_UNDO_LIMIT = int(os.environ.get("SQM_OUTBOUND_UNDO_LIMIT", "1"))
