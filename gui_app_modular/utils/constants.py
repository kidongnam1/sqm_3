"""
GUI 상수 re-export — v7.3.1 완전판
===================================
gui_bootstrap에서 정의된 모든 tkinter 상수 + 기능 플래그를
명시적으로 re-export. 어느 폴더에서 실행해도 독립 동작 보장.
filedialog는 tkinter에서 직접 import (gui_bootstrap 미포함).
"""

# ── 경로/로깅/설정 ─────────────────────────────────────────────
from .gui_bootstrap import (
    Path, logger,
    BASE_DIR, WINDOW_CONFIG_FILE, THEME_CONFIG_FILE,
    RECENT_FILES_FILE, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    DEFAULT_THEME, DARK_THEMES, LIGHT_THEMES,
    MAX_RECENT_FILES, CACHE_EXPIRE_SECONDS,
    DEFAULT_PRODUCT, WEIGHT_TOLERANCE_KG,
    APP_NAME, __version__,
)

# ── 상태 상수 ──────────────────────────────────────────────────
from .gui_bootstrap import (
    STATUS_AVAILABLE, STATUS_RESERVED, STATUS_PICKED, STATUS_SHIPPED,
    COLORS,
)

# ── tkinter / ttkbootstrap 위젯 ────────────────────────────────
from .gui_bootstrap import tk, ttk

# ── tkinter 레이아웃 상수 ──────────────────────────────────────
from .gui_bootstrap import (
    LEFT, RIGHT, TOP, BOTTOM,
    BOTH, X, Y,
    YES, NO,
    VERTICAL, HORIZONTAL,
    END, WORD,
    DISABLED, NORMAL,
    SUNKEN, RAISED, FLAT, GROOVE, RIDGE,
    W, E, N, S,
    NW, NE, SW, SE,
    CENTER,
    Menu,
)

# ── filedialog (tkinter 직접 import) ───────────────────────────
try:
    from tkinter import filedialog
except ImportError:
    filedialog = None  # tkinter 미설치 환경 안전 처리

# ── ttkbootstrap 기능 플래그 ───────────────────────────────────
from .gui_bootstrap import (
    HAS_TTKBOOTSTRAP, HAS_TOOLTIP,
    HAS_METER, HAS_DATEENTRY, HAS_FLOODGAUGE,
)

# ── 선택적 위젯 (없으면 None) ──────────────────────────────────
from .gui_bootstrap import Meter, DateEntry, Floodgauge

# ── 선택적 라이브러리 ──────────────────────────────────────────
from .gui_bootstrap import (
    HAS_PANDAS, pd,
    HAS_GEMINI, GEMINI_API_KEY,
    HAS_FEATURES_V2,
    HAS_COLUMN_ALIASES, ColumnMapper,
)

__all__ = [
    # 경로/로깅
    'Path', 'logger', 'BASE_DIR', 'WINDOW_CONFIG_FILE', 'THEME_CONFIG_FILE',
    'RECENT_FILES_FILE', 'DEFAULT_WINDOW_WIDTH', 'DEFAULT_WINDOW_HEIGHT',
    'MIN_WINDOW_WIDTH', 'MIN_WINDOW_HEIGHT', 'DEFAULT_THEME',
    'DARK_THEMES', 'LIGHT_THEMES', 'MAX_RECENT_FILES', 'CACHE_EXPIRE_SECONDS',
    'DEFAULT_PRODUCT', 'WEIGHT_TOLERANCE_KG', 'APP_NAME', '__version__',
    # 상태
    'STATUS_AVAILABLE', 'STATUS_RESERVED', 'STATUS_PICKED', 'STATUS_SHIPPED', 'COLORS',
    # 위젯
    'tk', 'ttk', 'filedialog', 'Menu',
    # 레이아웃
    'LEFT', 'RIGHT', 'TOP', 'BOTTOM', 'BOTH', 'X', 'Y', 'YES', 'NO',
    'VERTICAL', 'HORIZONTAL', 'END', 'WORD',
    'DISABLED', 'NORMAL', 'SUNKEN', 'RAISED', 'FLAT', 'GROOVE', 'RIDGE',
    'W', 'E', 'N', 'S', 'NW', 'NE', 'SW', 'SE', 'CENTER',
    # 플래그
    'HAS_TTKBOOTSTRAP', 'HAS_TOOLTIP', 'HAS_METER', 'HAS_DATEENTRY', 'HAS_FLOODGAUGE',
    # 선택 위젯
    'Meter', 'DateEntry', 'Floodgauge',
    # 선택 라이브러리
    'HAS_PANDAS', 'pd', 'HAS_GEMINI', 'GEMINI_API_KEY',
    'HAS_FEATURES_V2', 'HAS_COLUMN_ALIASES', 'ColumnMapper',
]
