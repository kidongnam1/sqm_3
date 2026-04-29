"""
GUI 부트스트랩 (P2 단일 소스)
============================

ttkbootstrap/tkinter 로드, GUI 상수·설정·폴백.
실제 구현은 여기; constants.py는 하위 호환 re-export.
"""

import logging
from pathlib import Path

# 모듈 로거
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# GUI 라이브러리 로드
# ═══════════════════════════════════════════════════════════════

try:
    import tkinter as tk

    import ttkbootstrap as ttk
    from ttkbootstrap import Style, Window
    from ttkbootstrap.scrolled import ScrolledFrame
    from ttkbootstrap.tableview import Tableview
    from ttkbootstrap.tooltip import ToolTip

    # v3.6.5: ttkbootstrap 전용 위젯 (안전 import)
    try:
        from ttkbootstrap.widgets import DateEntry, Floodgauge
        # [v7.3.2] Meter: Python 3.14 + ttkbootstrap 호환 문제로 비활성화
        # (테마 변경 시 ValueError: unknown color specifier: '')
        Meter = None
    except ImportError:
        Meter = None
        DateEntry = None
        Floodgauge = None

    # ttkbootstrap에 LabelFrame이 없으면 tkinter.ttk에서 가져옴
    if not hasattr(ttk, 'LabelFrame'):
        from tkinter.ttk import LabelFrame
        ttk.LabelFrame = LabelFrame

    # tkinter 상수 (ttkbootstrap에서 재정의되지 않으므로 직접 정의)
    LEFT = tk.LEFT
    RIGHT = tk.RIGHT
    TOP = tk.TOP
    BOTTOM = tk.BOTTOM
    BOTH = tk.BOTH
    X = tk.X
    Y = tk.Y
    YES = True
    NO = False
    VERTICAL = tk.VERTICAL
    HORIZONTAL = tk.HORIZONTAL
    END = tk.END
    WORD = tk.WORD
    DISABLED = tk.DISABLED
    NORMAL = tk.NORMAL
    SUNKEN = tk.SUNKEN
    RAISED = tk.RAISED
    FLAT = tk.FLAT
    GROOVE = tk.GROOVE
    RIDGE = tk.RIDGE
    W = tk.W
    E = tk.E
    N = tk.N
    S = tk.S
    NW = tk.NW
    NE = tk.NE
    SW = tk.SW
    SE = tk.SE
    CENTER = tk.CENTER
    Menu = tk.Menu

    HAS_TTKBOOTSTRAP = True
    HAS_TOOLTIP = True
    HAS_METER = Meter is not None
    HAS_DATEENTRY = DateEntry is not None
    HAS_FLOODGAUGE = Floodgauge is not None
    logger.info("✅ ttkbootstrap 로드됨")
except ImportError:
    import tkinter as tk
    from tkinter import ttk
    HAS_TTKBOOTSTRAP = False
    HAS_TOOLTIP = False
    HAS_METER = False
    HAS_DATEENTRY = False
    HAS_FLOODGAUGE = False
    ToolTip = None
    Meter = None
    DateEntry = None
    Floodgauge = None
    ScrolledFrame = None
    Tableview = None

    # ttkbootstrap 상수 폴백 정의
    LEFT = tk.LEFT
    RIGHT = tk.RIGHT
    TOP = tk.TOP
    BOTTOM = tk.BOTTOM
    BOTH = tk.BOTH
    X = tk.X
    Y = tk.Y
    YES = True
    NO = False
    VERTICAL = tk.VERTICAL
    HORIZONTAL = tk.HORIZONTAL
    END = tk.END
    WORD = tk.WORD
    DISABLED = tk.DISABLED
    NORMAL = tk.NORMAL
    SUNKEN = tk.SUNKEN
    RAISED = tk.RAISED
    FLAT = tk.FLAT
    GROOVE = tk.GROOVE
    RIDGE = tk.RIDGE
    W = tk.W
    E = tk.E
    N = tk.N
    S = tk.S
    NW = tk.NW
    NE = tk.NE
    SW = tk.SW
    SE = tk.SE
    CENTER = tk.CENTER
    Menu = tk.Menu

    Window = tk.Tk
    Style = None
    ScrolledFrame = None
    Tableview = None

    logger.warning("⚠️ ttkbootstrap 미설치 - 기본 UI 사용")

# ═══════════════════════════════════════════════════════════════
# pandas
# ═══════════════════════════════════════════════════════════════

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None
    logger.warning("⚠️ pandas 미설치")

# ═══════════════════════════════════════════════════════════════
# 설정 파일 경로
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent.parent
WINDOW_CONFIG_FILE = BASE_DIR / "window_config.json"
THEME_CONFIG_FILE = BASE_DIR / "theme_preference.json"
RECENT_FILES_FILE = BASE_DIR / "recent_files.json"

# ═══════════════════════════════════════════════════════════════
# 버전 정보
# ═══════════════════════════════════════════════════════════════

try:
    from version import APP_NAME, __version__
except ImportError:
    __version__ = "0.0.0"  # S2-3: version.py 누락 시 fallback
    import logging as _vlog
    _vlog.getLogger(__name__).warning("[버전] version.py 로드 실패 → fallback 0.0.0")
    APP_NAME = "SQM 재고관리 시스템"

# ═══════════════════════════════════════════════════════════════
# 선택적 모듈 플래그
# ═══════════════════════════════════════════════════════════════

# Column Aliases
try:
    from column_aliases import COLUMN_ALIASES, ColumnMapper
    HAS_COLUMN_ALIASES = True
except ImportError:
    ColumnMapper = None
    COLUMN_ALIASES = {}
    HAS_COLUMN_ALIASES = False

# Validators
try:
    from validators import DataValidator
    HAS_VALIDATOR = True
except ImportError:
    HAS_VALIDATOR = False
    DataValidator = None

# DB Protection
try:
    from db_protection import ActionLogger, DBProtection
    HAS_DB_PROTECTION = True
except ImportError:
    HAS_DB_PROTECTION = False
    DBProtection = None
    ActionLogger = None

# Error Handler
try:
    from error_handler import ErrorDialog, add_tooltip, safe_execute
    HAS_ERROR_HANDLER = True
except ImportError:
    HAS_ERROR_HANDLER = False
    ErrorDialog = None
    safe_execute = lambda f: f
    add_tooltip = lambda w, t: None

# Preflight
try:
    from engine_modules.preflight import PreflightError, PreflightValidator
    HAS_PREFLIGHT = True
except ImportError:
    HAS_PREFLIGHT = False
    PreflightValidator = None
    PreflightError = None

# Features
try:
    from features import FeatureManager
    HAS_FEATURES = True
except ImportError:
    HAS_FEATURES = False
    FeatureManager = None

# Features V2
try:
    from features_v2 import FeaturesV2Manager
    HAS_FEATURES_V2 = True
except ImportError:
    HAS_FEATURES_V2 = False
    FeaturesV2Manager = None

# Comprehensive Backup
try:
    from comprehensive_backup import ComprehensiveBackupSystem
    HAS_COMPREHENSIVE_BACKUP = True
except ImportError:
    HAS_COMPREHENSIVE_BACKUP = False
    ComprehensiveBackupSystem = None

# Upload Guard
try:
    from upload_guard import UploadGuard
    HAS_UPLOAD_GUARD = True
except ImportError:
    HAS_UPLOAD_GUARD = False
    UploadGuard = None

# Document Parser V3 (v8.5.6: V2 래퍼 삭제 → V3 직접 import)
try:
    from parsers.document_parser_modular import DocumentParserV3 as DocumentParserV2
    HAS_PARSER_V2 = True
except ImportError:
    HAS_PARSER_V2 = False
    DocumentParserV2 = None

# PDF Parser (Legacy)
try:
    from parsers.pdf_parser import PDFParser, parse_pdf
except ImportError:
    try:
        from parsers import PDFParser, parse_pdf
    except ImportError:
        PDFParser = None
        parse_pdf = None

# Gemini API
try:
    from core.config import GEMINI_API_KEY
    HAS_GEMINI = bool(GEMINI_API_KEY and GEMINI_API_KEY != 'your-api-key-here')
except ImportError:
    HAS_GEMINI = False
    GEMINI_API_KEY = None

# Progress Dialog
try:
    from improvements import ProgressInfo, TkProgressDialog
    HAS_PROGRESS = True
except ImportError:
    HAS_PROGRESS = False
    TkProgressDialog = None
    ProgressInfo = None

# ═══════════════════════════════════════════════════════════════
# UI 상수
# ═══════════════════════════════════════════════════════════════

# 기본 창 크기
DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 900
MIN_WINDOW_WIDTH = 1000
MIN_WINDOW_HEIGHT = 700

# 기본 테마
DEFAULT_THEME = "darkly"  # v8.1.3: 프로페셔널 다크 테마 통일
DARK_THEMES = ["darkly", "superhero", "cyborg", "vapor", "solar"]
LIGHT_THEMES = ["cosmo", "darkly", "journal", "litera", "lumen", "minty", "pulse", "sandstone", "united", "yeti"]

# 상태 코드
STATUS_AVAILABLE = "AVAILABLE"
STATUS_RESERVED = "RESERVED"
STATUS_PICKED = "PICKED"
STATUS_SHIPPED = "SHIPPED"

# 색상
COLORS = {
    'success': '#28a745',
    'warning': '#ffc107',
    'danger': '#dc3545',
    'info': '#17a2b8',
    'primary': '#007bff',
}

# 최근 파일 최대 개수
MAX_RECENT_FILES = 10

# 캐시 만료 시간 (초)
CACHE_EXPIRE_SECONDS = 300

# ═══════════════════════════════════════════════════════════════
# SQM 비즈니스 기본값 — core.constants 단일 소스 (re-export만, 로컬 정의 없음)
# ═══════════════════════════════════════════════════════════════
DEFAULT_PRODUCT = 'LITHIUM CARBONATE'
WEIGHT_TOLERANCE_KG = 0.5  # 무게 허용 오차 (kg)
