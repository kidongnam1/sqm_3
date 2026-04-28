# -*- coding: utf-8 -*-
from gui_app_modular.utils.ui_constants import tc
from .utils.custom_messagebox import CustomMessageBox
"""
SQM Inventory - Main Application Class
======================================

v2.9.91 - Modular GUI Application

This module combines all mixins and tabs to create the main application.
"""

import os
import sqlite3
import sys
import logging
import tkinter as tk                       # v7.9.9: 전역 import (NameError 방지)
import tkinter.ttk as ttk                  # v7.9.9: 전역 import
from tkinter.constants import BOTH, YES, TOP, X, Y
from pathlib import Path
from typing import Optional
import configparser  # v5.3.3

# Setup logging
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class SQMInventoryApp:
    """
    Main SQM Inventory Application
    
    Combines all GUI components through mixins:
    - MenuMixin: Menu bar setup
    - ToolbarMixin: Toolbar buttons
    - RefreshMixin: Data refresh functions
    - WindowMixin: Window management
    - ValidationMixin: Data validation
    - KeyBindingsMixin: Keyboard shortcuts
    - ContextMenuMixin: Right-click menus
    - FeaturesV2Mixin: Extended features (v2.7+)
    """
    
    def __init__(self, root=None, db_path: Optional[str] = None):
        """
        Initialize application
        
        Args:
            root: Tkinter root window (created if None)
            db_path: Database path (uses default if None)
        """
        # Import GUI libraries
        from .utils.constants import tk, ttk, HAS_TTKBOOTSTRAP
        
        # Create or use provided root
        if root is None:
            if HAS_TTKBOOTSTRAP:
                import ttkbootstrap as ttk_bs
                theme = self._load_theme_preference()
                # ★ v6.3.2-v5: ttkbootstrap primary 색상 소스 수정
                # Window 생성 전에 STANDARD_THEMES를 수정하면
                # 모든 위젯에 자동으로 새 색상이 적용됨
                try:
                    from ttkbootstrap.themes.standard import STANDARD_THEMES
                    _gy_colors = {
                        'primary':   '#10B981',   # 딥 에메랄드 (세련된 녹색)
                        'secondary': '#64748b',   # 슬레이트
                        'success':   '#10b981',   # 에메랄드
                        'info':      '#0ea5e9',   # 스카이 블루
                        'warning':   '#f59e0b',   # 앰버
                        'danger':    '#ef4444',   # 레드
                        'light':     '#cbd5e1',
                        'dark':      '#0f172a',   # 딥 네이비
                        'bg':        '#0b1120',   # 딥 네이비 블랙
                        'fg':        '#e2e8f0',   # 밝은 슬레이트
                        'selectbg':  '#1d4ed8',   # 다크 블루
                        'selectfg':  '#ffffff',
                        'border':    '#1e3a5f',   # 네이비 보더
                        'inputfg':   '#ffffff',
                        'inputbg':   '#111827',   # 네이비 입력 배경
                        'active':    '#1e293b',   # 네이비 액티브
                    }
                    if theme in STANDARD_THEMES:
                        STANDARD_THEMES[theme]['colors'].update(_gy_colors)
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).debug(f"Theme color override: {_e}")
                self.root = ttk_bs.Window(themename=theme)
            else:
                self.root = tk.Tk()
        else:
            self.root = root
        
        # v8.6.4: 타이틀바에 버전 표시 (윗줄 이동)
        try:
            from version import __version__, APP_NAME
            self.root.title(f"📦 {APP_NAME}  v{__version__}")
        except ImportError:
            self.root.title("📦 SQM 재고관리 시스템  v8.6.4")
        
        # Store references
        self.tk = tk
        self.ttk = ttk
        self.db_path = db_path
        
        # Initialize state variables
        # v8.1.8 BUG-THEME: _load_theme_preference()로 읽은 theme을 직접 전달
        # Style().theme_use()는 Window 생성 직후 'default'를 반환할 수 있어
        # _GLOBAL_IS_DARK가 잘못 설정되는 레이스 컨디션이 있었음
        _boot_theme = theme if root is None else None
        self._init_state(boot_theme=_boot_theme)
        
        # v8.6.4: 메인 윈도우 숨기고 스플래시(모래시계+타이머) 표시
        self.root.withdraw()
        self._show_loading_splash()

        # v3.6.5: 가독성 스타일 적용 (테마 인식)
        try:
            from .utils.ui_constants import ReadableStyle, apply_contrast_scrollbar_style, init_ui_system
            init_ui_system(self.root)
            ReadableStyle.apply(self.root, self.current_theme)
            apply_contrast_scrollbar_style(self.root, self.current_theme)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.debug(f"ReadableStyle init: {e}")
        
        # v4.19.1: 전역 Treeview 스타일 — line 217의 after(800) 호출로 통합됨
        
        # Initialize engine
        self._update_splash('엔진 초기화...')
        self._init_engine()
        
        # v5.0.3: 시작 시 DB 검증 및 자동 복구
        # v8.7.1 [VISIBILITY]: 성공/실패 모두 가시화, sqlite3 예외 포함, exc_info 보존
        try:
            from utils.backup_validator import AutoRecovery

            backup_dir = os.path.join('data', 'db', 'backups')
            _db_used = self.db_path or 'data/db/sqm_inventory.db'
            auto_recovery = AutoRecovery(_db_used, backup_dir)

            recovered, message = auto_recovery.check_and_recover()

            if recovered:
                logger.warning(f"🔧 [AUTO-RECOVERY] 자동 복구 실행됨: {message}")
                # 복구 후 엔진 재초기화
                logger.info("[AUTO-RECOVERY] 엔진 재초기화 시작 (db=%s)", _db_used)
                self._init_engine()
                logger.info("[AUTO-RECOVERY] 엔진 재초기화 완료")
            else:
                # v8.7.1: 복구 불필요도 명시 로깅 (과거엔 무로그 → '건너뛴건지 실패인지' 불명)
                logger.info("[AUTO-RECOVERY] DB 정상 (복구 불필요): %s", message or _db_used)
        except ImportError:
            logger.debug("[AUTO-RECOVERY] 모듈 없음 (선택 기능, 무시)")
        except (ValueError, TypeError, KeyError, AttributeError, OSError,
                sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            # v8.7.1: sqlite3 예외 추가 (DB 손상/락 상황 포착), exc_info 로 스택 보존
            logger.error("[AUTO-RECOVERY] 자동 복구 오류: %s", e, exc_info=True)
        
        # Setup UI
        # v8.1.8 BUG-THEME: 탭/위젯 생성 직전 set_global_theme 재확인
        # tc() 함수가 위젯 생성 시점에 _GLOBAL_IS_DARK를 읽으므로
        # _setup_ui 진입 전에 반드시 올바른 테마가 설정되어 있어야 함
        try:
            from .utils.ui_constants import set_global_theme as _sgt
            _sgt(getattr(self, 'current_theme', 'darkly'))
        except Exception as e:
            logger.warning(f'[UI] main_app: {e}')
        self._update_splash('화면 구성 중...')
        self._setup_ui()
        # 전역 자동 툴팁: 메뉴/팝업/버튼에 120자 이내 안내 자동 부착
        try:
            from .utils.auto_tooltip import install_global_auto_tooltips
            install_global_auto_tooltips(self.root)
            logger.info("✅ 전역 자동 툴팁 적용 완료")
        except ImportError as e:
            logger.debug(f"전역 자동 툴팁 로딩 실패 (무시): {e}")
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning(f"전역 자동 툴팁 적용 실패: {e}")

        # v6.2.3: 전역 Editable Treeview 바인딩 (Ctrl+C/X/V, Delete, 더블클릭 편집)
        try:
            from .utils.global_editable_tree import install_global_editable_tree
            install_global_editable_tree(self.root)
            logger.info("✅ 전역 Editable Treeview 적용 완료")
        except ImportError as e:
            logger.debug(f"전역 Editable Treeview 로딩 실패 (무시): {e}")
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning(f"전역 Editable Treeview 적용 실패: {e}")

        # 전역 순번 열: 모든 표(Treeview)에 '순번' 자동 표시
        try:
            from .utils.global_row_number_tree import install_global_row_number_tree
            install_global_row_number_tree(self.root)
            logger.info("✅ 전역 순번 열 적용 완료")
        except (ImportError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning(f"전역 순번 열 적용 실패: {e}")
        
        # Load data
        self._update_splash('데이터 로딩...')
        self._load_initial_data()
        
        # v5.0.0: 모든 Treeview에 통일 스타일 자동 적용
        try:
            from fixes.auto_style_applier import apply_styles_to_all_trees
            # UI 생성 완료 후 실행 (after 사용)
            self.root.after(1000, lambda: apply_styles_to_all_trees(self.root))
            # v8.0.5 NAVY-ORANGE: after 타이머 제거 → 단발 적용 (깜빡임 원인 제거)
            try:
                from fixes.theme_colorful_override import apply_colorful_overrides
                from fixes.global_tree_style import apply_global_tree_style
                _is_dark = getattr(self, 'current_theme', 'litera').lower() in (
                    'darkly', 'cyborg', 'superhero', 'solar', 'vapor')
                self.root.after(800, lambda: [
                    apply_global_tree_style(self.root, _is_dark),
                    apply_colorful_overrides(self),
                ])
            except ImportError as _ie:
                # P1-1: ImportError를 ERROR 레벨로 기록 (침묵 억제 제거)
                logger.error(f"[MainApp] 테마 스타일 모듈 로드 실패: {_ie}")
                self._init_state_valid = getattr(self, '_init_state_valid', True)  # 비치명적 — 앱 계속 동작
            logger.info("✅ v5.0.0: 자동 스타일 적용 예약 완료")
        except ImportError as e:
            logger.debug(f"자동 스타일 적용기 로딩 실패 (무시): {e}")
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.warning(f"자동 스타일 적용 예약 실패: {e}")
        
        logger.info("SQM Inventory App initialized")
        # v8.5.9: 시작 속도 최적화 — health check를 UI 표시 후 지연 실행
        self.root.after(500, self._startup_health_check)
        # v8.6.4: 초기화 완료 → 스플래시 제거 + 메인 윈도우 표시
        self._hide_loading_splash()
        self._ensure_resources_templates()   # v6.3.3 RUBI

    def _ensure_resources_templates(self) -> None:
        """
        v6.3.3 RUBI: resources/templates/ 폴더 자동 생성.

        Allocation 양식 미리보기 다이얼로그(AllocationTemplateDialog)가
        이 폴더에서 Song/Woo 양식 파일을 읽습니다.
        폴더가 없으면 실행 파일 기준 경로에 자동 생성합니다.

        배치 방법:
            resources/templates/allocation_template_song.xlsx  ← Song 양식
            resources/templates/allocation_template_woo.xlsx   ← Woo  양식
        """
        import os
        from pathlib import Path

        # SQM 실행 파일 기준 경로 (gui_app_modular 상위 = 프로젝트 루트)
        try:
            base = Path(__file__).parent.parent
        except Exception:
            base = Path(os.getcwd())

        templates_dir = base / 'resources' / 'templates'
        try:
            templates_dir.mkdir(parents=True, exist_ok=True)
            # README 파일 생성 (최초 1회)
            readme = templates_dir / 'README.txt'
            if not readme.exists():
                readme.write_text(
                    "SQM Allocation 양식 템플릿 폴더\n"
                    "================================\n\n"
                    "이 폴더에 아래 파일을 배치하면 '📄 Allocation 양식 미리보기' 메뉴에서\n"
                    "실제 양식 파일을 미리보기 및 다운로드할 수 있습니다.\n\n"
                    "  allocation_template_song.xlsx  : Song 양식 (250MT 기준)\n"
                    "  allocation_template_woo.xlsx   : Woo  양식 (550MT 기준)\n\n"
                    "파일이 없으면 내장 샘플 데이터로 대신 표시됩니다.\n",
                    encoding='utf-8',
                )
            logger.info(f"[v6.3.3] resources/templates 폴더 준비: {templates_dir}")
        except OSError as e:
            logger.warning(f"[v6.3.3] resources/templates 폴더 생성 실패 (무시): {e}")
    
    def _init_state(self, boot_theme: str = None) -> None:
        """Initialize application state variables.
        
        v8.1.8 BUG-THEME 수정:
          boot_theme 파라미터로 _load_theme_preference() 결과를 직접 받아
          Style().theme_use() 레이스 컨디션 없이 set_global_theme() 호출.
        """
        # Selection state
        self.selected_tonbags = set()
        self.selected_search_items = set()
        
        # Sort state
        self._sort_column = None
        self._sort_reverse = False
        
        # Feature flags
        self.use_gemini = False
        self.gemini_required_warning_shown = False
        self._is_fullscreen = False
        
        # Filter presets
        self.filter_presets = {}
        
        # Recent files
        self.recent_files = []
        
        # Theme — v8.1.8: boot_theme 우선 사용 → 레이스 컨디션 차단
        # v8.2.4 BUG-FIX: set_global_theme import 누락 수정
        from .utils.ui_constants import set_global_theme as _set_global_theme
        try:
            if boot_theme:
                # Window 생성 전에 읽은 테마를 그대로 사용 (가장 안전)
                self.current_theme = boot_theme
                _set_global_theme(boot_theme)
            else:
                # root가 외부에서 주입된 경우 → Style().theme_use() 폴백
                from tkinter import ttk as _ttk_detect
                detected = _ttk_detect.Style().theme_use() or ''
                # 'default' 또는 빈 값이면 theme_preference.json 재시도
                if not detected or detected == 'default':
                    detected = self._load_theme_preference()
                self.current_theme = detected
                _set_global_theme(detected)
        except Exception:
            self.current_theme = 'darkly'
            _set_global_theme('darkly')
        
        # v3.0: UI 운영 헬퍼 초기화
        self.ui_helper = None  # _setup_ui에서 초기화

        # 전역 중복 검사 가드
        self._dup_guard_last_signature = ""
        self._dup_guard_interval_ms = 60000
    
    def _init_engine(self) -> None:
        """Initialize database engine

        v8.7.1 [VISIBILITY]: 엔진 로딩 경로/클래스명 명시 로깅.
        - primary: engine_modules.inventory.SQMInventoryEngine (SQMInventoryEngineV3 facade)
        - fallback: engine.Engine (legacy)
        - none: self.engine=None (UI는 부분 기능만 동작)
        """
        try:
            from engine_modules.inventory import SQMInventoryEngine

            self.engine = SQMInventoryEngine(db_path=self.db_path)
            logger.info(
                "[ENGINE] primary loaded: %s (db=%s)",
                type(self.engine).__name__, self.db_path,
            )

        except ImportError as e:
            logger.warning(
                "[ENGINE] primary import failed, trying fallback: %s", e, exc_info=True,
            )
            # Try alternate import (legacy)
            try:
                from engine import Engine
                self.engine = Engine(db_path=self.db_path)
                logger.warning(
                    "[ENGINE] fallback loaded (legacy): %s (db=%s)",
                    type(self.engine).__name__, self.db_path,
                )
            except ImportError as e2:
                logger.error(
                    "[ENGINE] no engine module found (primary+fallback both failed): %s",
                    e2, exc_info=True,
                )
                self.engine = None
    
    def _setup_ui(self) -> None:
        """Setup main UI components"""
        from .utils.constants import ttk, BOTH, YES
        
        # Load window configuration
        self._load_window_config()
        
        # v3.8.4: 통합 메뉴바 (메인메뉴+액션+탭을 1줄로)
        self._setup_toolbar()
        # v5.4.1: 시작 직후 1회 툴바/드롭다운 팔레트 재동기화(화이트 모드 변색 방지)
        try:
            self._refresh_toolbar_theme()
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as _e:
            logger.debug(f"Suppressed: {_e}")
        
        # v5.0.6: main_frame 생성 (StatusBar를 위해 필요)
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=BOTH, expand=YES, padx=0, pady=5)

        # v8.6.4: 사이드바 너비 확대 + 콘텐츠 여백
        self._sidebar_frame = tk.Frame(self.main_frame, width=72, bg=tc('bg_secondary'))
        self._sidebar_frame.pack(side='left', fill='y', padx=(4, 0))
        self._sidebar_frame.pack_propagate(False)

        self._content_frame = ttk.Frame(self.main_frame)
        self._content_frame.pack(side='left', fill=BOTH, expand=YES, padx=(8, 8))

        # v8.6.5 PERF-2: dirty flag 시스템 초기화
        if hasattr(self, '_init_dirty_tabs'):
            self._init_dirty_tabs()

        # Setup main notebook (tabs) — 콘텐츠 영역에 배치
        self.notebook = ttk.Notebook(self._content_frame)
        self.notebook.pack(fill=BOTH, expand=YES)
        
        # v3.8.4: notebook 탭 헤더 숨김 (toolbar에 탭 버튼 있음)
        self._enforce_main_notebook_hidden_tabs()
        
        # ── v8.1.7: 사이드바 재고 워크플로우 7탭 + 보조 탭 3개 ─────────────
        # 사이드바: Inventory / Allocation / Picked / Outbound / Return / Move
        # 메뉴 전용 (사이드바 미표시): Dashboard / Log / Scan
        self.tab_inventory   = ttk.Frame(self.notebook)   # Inventory (재고 전체)
        self.tab_allocation  = ttk.Frame(self.notebook)   # Allocation (배정)
        self.tab_picked      = ttk.Frame(self.notebook)   # Picked (피킹)
        self.tab_sold        = ttk.Frame(self.notebook)   # Outbound (출고)
        self.tab_return      = ttk.Frame(self.notebook)   # Return (반품) — 신규 독립 탭
        self.tab_move        = ttk.Frame(self.notebook)   # Move (이동) — v8.1.7 신규
        self.tab_dashboard   = ttk.Frame(self.notebook)   # Dashboard — 메뉴 전용
        self.tab_log         = ttk.Frame(self.notebook)   # Log — 메뉴 전용
        self.tab_scan        = ttk.Frame(self.notebook)   # Scan — 메뉴 전용

        # 호환성 alias
        self.tab_available          = self.tab_inventory
        self.tab_search             = self.tab_inventory
        self.tab_summary            = self.tab_dashboard
        self.tab_cargo_overview     = self.tab_return    # cargo_overview → Return 탭
        self.tab_outbound_scheduled = self.tab_sold
        self.tab_tonbag             = self.tab_inventory
        self.tab_pivot              = ttk.Frame(self.notebook)  # 호환성 (미사용)

        # notebook 등록 — 워크플로우 순서 + 메뉴 전용
        self.notebook.add(self.tab_inventory,  text="  📦 Inventory  ")
        self.notebook.add(self.tab_allocation, text="  📋 Allocation  ")
        self.notebook.add(self.tab_picked,     text="  🚛 Picked  ")
        self.notebook.add(self.tab_sold,       text="  📤 Outbound  ")
        self.notebook.add(self.tab_return,     text="  🔄 Return  ")
        self.notebook.add(self.tab_move,       text="  🔀 Move  ")
        self.notebook.add(self.tab_dashboard,  text="  📊 Dashboard  ")
        self.notebook.add(self.tab_log,        text="  📝 Log  ")
        self.notebook.add(self.tab_scan,       text="  📷 Scan  ")

        # v7.9.9 [SIDEBAR]: 사이드바 탭 버튼 빌드 (main_frame 생성 후 호출)
        if hasattr(self, '_sidebar_frame'):
            self._build_sidebar_tab_buttons()
            self._tab_index_map = {
                'inventory': 0, 'allocation': 1, 'picked': 2, 'sold': 3,
                'return_tab': 4, 'move': 5,
                'dashboard': 6, 'log': 7, 'scan': 8,
            }
            self._active_tab_key = 'dashboard'  # v8.6.3: 초기 활성 탭 대시보드
            self._highlight_active_tab()

        # Setup individual tabs
        for tab_name, setup_fn in [
            ('Inventory',  self._setup_inventory_tab),
            ('Allocation', self._setup_allocation_tab),
            ('Picked',     self._setup_picked_tab),
            ('Outbound',   self._setup_sold_tab),
            ('Return',     self._setup_return_tab),      # v8.1.7: Return 탭
            ('Move',       self._setup_move_tab),        # v8.1.7: Move 탭 신규
            ('Dashboard',  self._setup_dashboard_tab),
            ('Log',        self._setup_log_tab),
            ('Scan',       self._setup_scan_tab),
        ]:
            try:
                setup_fn()
            except (AttributeError, RuntimeError) as e:
                logger.error(f"탭 초기화 실패 [{tab_name}]: {e}")
                import traceback
                traceback.print_exc()
        
        # v8.7.0 [FIX G-1.1]: '_setup_summary_tab_content' 메서드는 코드베이스에 정의 없음.
        #   v3.8.8에서 "검색 탭 팝업화"로 요약 탭이 제거되었고 관련 초기화 훅도 dead.
        #   hasattr 가드로 조용히 스킵되던 3줄 완전 제거 (의미 없는 dead hook).


        # v8.6.3: 시작 시 첫 탭 → 대시보드
        # after(0): 이벤트 루프 시작 직후 실행 → 다른 초기화가 덮어쓰는 것 방지
        def _set_dashboard_tab():
            try:
                self.notebook.select(self.tab_dashboard)
                self._active_tab_key = 'dashboard'
                if hasattr(self, '_highlight_active_tab'):
                    self._highlight_active_tab()
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"[초기탭] {type(_e).__name__}: {_e}")

        def _refresh_dashboard_safe():
            try:
                if hasattr(self, '_refresh_dashboard') and callable(self._refresh_dashboard):
                    self._refresh_dashboard()
            except (AttributeError, RuntimeError) as _e:
                logger.debug(f"[대시보드새로고침] {_e}")

        self.root.after(0,   _set_dashboard_tab)       # 즉시: 탭 선택
        self.root.after(800, _refresh_dashboard_safe)  # 0.8초 후: 데이터 로드
        
        # v3.8.4: notebook 탭 변경 시 툴바 탭 버튼 연동
        def _on_notebook_tab_changed(event):
            try:
                idx = self.notebook.index(self.notebook.select())
                # 0=inventory, 1=allocation, 2=picked, 3=sold, 4=return, 5=move, 6=dashboard, 7=log, 8=scan
                idx_to_key = {0: 'inventory', 1: 'allocation', 2: 'picked', 3: 'sold', 4: 'return_tab', 5: 'move', 6: 'dashboard', 7: 'log', 8: 'scan'}
                key = idx_to_key.get(idx)
                if key and hasattr(self, '_active_tab_key'):
                    self._active_tab_key = key
                    self._highlight_active_tab()
                
                # 탭 전환 시 자동 새로고침
                if key == 'inventory' and hasattr(self, '_refresh_inventory'):
                    self._refresh_inventory()
                elif key == 'allocation' and hasattr(self, '_refresh_allocation'):
                    self._refresh_allocation()
                elif key == 'picked' and hasattr(self, '_refresh_picked'):
                    self._refresh_picked()
                elif key == 'sold' and hasattr(self, '_refresh_sold'):
                    self._refresh_sold()
                elif key == 'return_tab' and hasattr(self, '_refresh_cargo_overview'):
                    self._refresh_cargo_overview()
                elif key == 'dashboard':
                    if hasattr(self, '_refresh_dashboard') and callable(self._refresh_dashboard):
                        self._refresh_dashboard()
                    elif hasattr(self, '_refresh_summary'):
                        self._refresh_summary()
                
                # v3.9.4: 탭 전환 시 상태바 + 하단 통계 갱신
                if hasattr(self, '_update_statusbar_summary'):
                    self._update_statusbar_summary()
                
                # v3.8.8: 탭 전환 시 전용 툴바 활성화/비활성화
                self._toggle_tab_toolbars(key)
                # v8.6.5 PERF-2: dirty 탭 전환 시 새로고침
                if hasattr(self, '_refresh_dirty_current_tab'):
                    self._refresh_dirty_current_tab()
            except (AttributeError, RuntimeError) as _e:
                logger.debug(f"{type(_e).__name__}: {_e}")
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"main_app: {_e}")
        
        self.notebook.bind('<<NotebookTabChanged>>', _on_notebook_tab_changed)
        
        # v3.6.5: 인프라 초기화 개별 예외 처리
        for infra_name, infra_fn in [
            ('StatusBar', self._setup_status_bar),
            ('KeyBindings', self._setup_keybindings),
            ('ContextMenus', self._setup_context_menus),
            ('WindowBindings', self._setup_window_bindings),
            ('DragDrop', self._setup_drag_drop),
            ('UIHelper', self._setup_ui_helper),
        ]:
            try:
                infra_fn()
            except (ValueError, TypeError, AttributeError) as e:
                logger.error(f"초기화 실패 [{infra_name}]: {e}")

    def _enforce_main_notebook_hidden_tabs(self) -> None:
        """메인 노트북 탭 헤더를 항상 숨김(중복 줄 표시 방지).

        v8.7.2 [FIX]: Tab 레이아웃을 비우고 Notebook 레이아웃을 client 전용으로
        명시적으로 정의해 탭 전환 시 콘텐츠가 정상 스위칭되도록 보장.
        """
        try:
            style = self.ttk.Style()
            # Tab 헤더 레이아웃 제거 (전역 TNotebook.Tab 건드리지 않음)
            style.layout('MainHidden.TNotebook.Tab', [])
            # Notebook 레이아웃을 client 영역만 갖도록 명시
            # (기본 TNotebook이 이미 Notebook.client만 갖지만, 명시적으로 지정해 안정성 확보)
            style.layout('MainHidden.TNotebook', [
                ('Notebook.client', {'sticky': 'nswe'}),
            ])
            if hasattr(self, 'notebook') and self.notebook:
                self.notebook.configure(style='MainHidden.TNotebook')
        except (RuntimeError, ValueError, AttributeError) as _e:
            logger.debug(f"_enforce_main_notebook_hidden_tabs: {_e}")
    
    def _setup_ui_helper(self) -> None:
        """v3.0: UI 운영 헬퍼 초기화"""
        try:
            from .utils.ui_ops_helper import UIOperationsHelper
            
            # 상태바에서 진행률 바와 레이블 가져오기
            progressbar = getattr(self, 'progress_bar', None)
            progress_label = getattr(self, 'status_label', None)
            
            # UI 헬퍼 초기화
            self.ui_helper = UIOperationsHelper(
                self.root, 
                progressbar=progressbar,
                progress_label=progress_label
            )
            
            # 미완료 작업 확인 (앱 시작 시)
            self.root.after(1000, self._check_work_recovery)
            
            # v8.5.9: 시작 속도 최적화 — 무거운 작업을 UI 표시 후 지연 실행
            # 테마 렌더링 → 통계 → 백업 순서로 점진적 로드
            self.root.after(800, self._force_initial_theme_refresh)
            self.root.after(2500, self._startup_stats_refresh)
            self.root.after(4000, self._start_auto_backup_safe)
            
            logger.info("[v3.0] UI 운영 헬퍼 초기화 완료")
            
        except ImportError as e:
            logger.warning(f"[v3.0] UI 헬퍼 로드 실패: {e}")
            self.ui_helper = None
    
    def _check_work_recovery(self) -> None:
        """미완료 작업 복구 확인"""
        if not self.ui_helper:
            return
    
    def _startup_health_check(self) -> None:
        """v7.9.3: 시작 시 버전·DB 상태 자동 확인 로그.

        v8.7.1 [VISIBILITY]: 최상위 예외 wrapper를 debug → error + exc_info 로 격상.
        부팅 시 DB/무결성 확인 실패가 조용히 사라지던 문제 해결.
        """
        try:
            from version import __version__
            logger.info(f"[STARTUP] SQM v{__version__} 시작")
        except ImportError as _ve:
            logger.warning("[STARTUP] version.py import 실패: %s", _ve)
        try:
            engine = getattr(self, 'engine', None)
            if not engine:
                logger.warning("[STARTUP] engine 없음 — DB 확인 불가")
                return
            db = getattr(engine, 'db', None)
            if not db:
                logger.warning("[STARTUP] DB 연결 없음")
                return
            # LOT 수 / 총 중량 확인
            row = db.fetchone(
                "SELECT COUNT(*) as lots, COALESCE(SUM(current_weight),0) as kg "
                "FROM inventory WHERE status='AVAILABLE'"
            )
            if row:
                lots = row.get('lots', 0) if isinstance(row, dict) else row[0]
                kg   = row.get('kg',   0) if isinstance(row, dict) else row[1]
                logger.info(f"[STARTUP] AVAILABLE LOT: {lots}개, {kg:,.0f}kg")
            # 정합성 확인
            int_row = db.fetchone(
                "SELECT COUNT(*) as cnt FROM inventory_tonbag "
                "WHERE status NOT IN ('AVAILABLE','RESERVED','PICKED','SOLD',"
                "'RETURNED','DEPLETED','SAMPLE','CANCELLED','SHIPPED')"
            )
            if int_row:
                bad = int_row.get('cnt',0) if isinstance(int_row, dict) else int_row[0]
                if bad > 0:
                    logger.warning(f"[STARTUP] 비정상 상태 톤백 {bad}개 감지 — 정합성 검사 권장")
                else:
                    logger.info("[STARTUP] 톤백 상태 정합성 OK")
            # 미처리 중복 stock_movement 확인
            dup_row = db.fetchone(
                "SELECT COUNT(*) as cnt FROM ("
                "  SELECT lot_no FROM stock_movement "
                "  WHERE movement_type='INBOUND' GROUP BY lot_no HAVING COUNT(*)>1"
                ")"
            )
            if dup_row:
                dup_cnt = dup_row.get('cnt',0) if isinstance(dup_row, dict) else dup_row[0]
                if dup_cnt > 0:
                    logger.warning(f"[STARTUP] stock_movement 중복 LOT {dup_cnt}건 감지")
            logger.info("[STARTUP] 시작 상태 확인 완료")

            # v8.0.0 [P1]: orphan allocation 자동 정리
            # 비정상 종료 후 STAGED/PENDING_APPROVAL 상태 영구 잔존 방지
            try:
                if hasattr(engine, 'run_allocation_cleanup'):
                    _cleanup = engine.run_allocation_cleanup(days_old=7)
                    _orphan  = _cleanup.get('orphan_cancelled', 0)
                    _expired = _cleanup.get('expired_rejected', 0)
                    if _orphan > 0 or _expired > 0:
                        logger.warning(
                            f"[STARTUP][P1] Allocation 정리 완료 — "
                            f"orphan 취소: {_orphan}건, 만료 rejected: {_expired}건"
                        )
                    else:
                        logger.info("[STARTUP][P1] Allocation orphan 없음 (정상)")
            except Exception as _ce:
                logger.debug(f"[STARTUP][P1] Allocation 정리 스킵: {_ce}")

            # v8.0.5 [INTEGRITY-AUTO]: 시작 시 재고 무결성 자동 검사
            try:
                if hasattr(engine, 'run_integrity_check'):
                    _ic = engine.run_integrity_check(dry_run=True, auto_fix=False)
                    _issues = _ic.get('issues', []) if isinstance(_ic, dict) else []
                    if _issues:
                        logger.warning(
                            f"[STARTUP][INTEGRITY] 재고 무결성 이슈 {len(_issues)}건 감지 — "                            f"관리자 메뉴 > DB 정합성 확인 권장"
                        )
                    else:
                        logger.info("[STARTUP][INTEGRITY] 재고 무결성 OK")
            except Exception as _ie:
                logger.debug(f"[STARTUP][INTEGRITY] 자동 검사 스킵: {_ie}")

        except Exception as e:
            # v8.7.1 [VISIBILITY]: debug → error 로 격상 + exc_info 전체 스택 보존
            logger.error(
                "[STARTUP] 상태 확인 실패 — 부팅은 계속, DB/엔진 점검 필요: %s",
                e, exc_info=True,
            )

    def _startup_stats_refresh(self) -> None:
        """v3.9.4: 앱 시작 시 통계 자동 갱신 (하단바 + 상태바)"""
        try:
            # 재고리스트 새로고침 → 하단 통계 자동 채움
            if hasattr(self, '_refresh_inventory'):
                self._refresh_inventory()
            # 상태바 요약
            if hasattr(self, '_update_statusbar_summary'):
                self._update_statusbar_summary()
            logger.info("[v3.9.4] 시작 시 통계 자동 갱신 완료")
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"startup_stats_refresh: {e}")
    
    def _start_auto_backup_safe(self) -> None:
        """v3.8.4: 자동 백업 안전 시작"""
        try:
            if hasattr(self, '_start_auto_backup'):
                self._start_auto_backup()
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"자동 백업 시작 오류: {e}")
        
        def on_recover(work):
            """복구 콜백"""
            self._log(f"작업 복구: {work.work_type} (진행률: {work.progress:.0%})")
            # 작업 유형에 따른 복구 로직
            if work.work_type == "INBOUND":
                self._log("입고 작업 복구 시도")
            elif work.work_type == "OUTBOUND":
                self._log("출고 작업 복구 시도")
            else:
                self._log(f"기타 작업 복구: {work.work_type}")
        
        def on_discard():
            """무시 콜백"""
            self._log("미완료 작업 무시됨")
        
        try:
            self.ui_helper.check_recovery(on_recover, on_discard)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"작업 복구 확인 실패: {e}")
    
    def _load_initial_data(self) -> None:
        """Load initial data into UI.

        v8.5.9: 시작 속도 최적화 — 정합성 검사·스냅샷을 UI 표시 후 지연 실행.
        재고/톤백 테이블만 즉시 로드하여 화면이 빨리 뜨도록 함.
        """
        try:
            self._refresh_inventory()
            self._refresh_tonbag()
            if hasattr(self, '_refresh_summary'):
                self._refresh_summary()
            self._log("Data loaded")

            # 무거운 작업은 UI 표시 후 지연 실행
            self.root.after(1500, self._startup_integrity_check)
            self.root.after(1800, self._save_startup_snapshot)
            self.root.after(2000, self._start_duplicate_guard)
        except (AttributeError, RuntimeError) as e:
            logger.error(f"Initial data load error: {e}")
            self._log(f"X Data load error: {e}")

    def _start_duplicate_guard(self) -> None:
        """전역 중복 검사 자동 루프 시작."""
        try:
            self.root.after(2500, self._run_duplicate_guard_once)
            # ③ v6.7.1: Allocation 고아/만료 자동 정리 (시작 3초 후)
            self.root.after(3000, self._run_allocation_cleanup_once)
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"duplicate guard start skip: {e}")

    def _run_allocation_cleanup_once(self) -> None:
        """③ v6.7.1: 앱 시작 시 Allocation 고아/만료 레코드 자동 정리 (1회)."""
        try:
            if not hasattr(self, 'engine') or not self.engine:
                return
            if not hasattr(self.engine, 'run_allocation_cleanup'):
                return
            r = self.engine.run_allocation_cleanup(days_old=7)
            orphan = r.get('orphan_cancelled', 0)
            expired = r.get('expired_rejected', 0)
            if orphan or expired:
                logger.info(
                    f"[Allocation 정리] 고아취소={orphan}건 / 만료반려={expired}건"
                )
        except Exception as e:
            logger.debug(f"[Allocation 정리] 스킵: {e}")

    def _run_duplicate_guard_once(self) -> None:
        """전역 식별 키 중복 검사 1회 실행 후 재예약."""
        try:
            if not self.engine or not hasattr(self.engine, "db"):
                return
            from .utils.duplicate_guard import scan_duplicate_keys

            findings = scan_duplicate_keys(self.engine.db)
            signature = "\n".join(findings)
            if findings:
                if signature == self._dup_guard_last_signature:
                    # 동일 결과 반복 — 로그/상태바 재출력 생략 (60초 타이머 스팸 방지)
                    return
                self._set_status(f"⚠️ 중복 감지 {len(findings)}건")
                self._log("⚠️ 전역 중복 검사 결과:")
                for line in findings[:10]:
                    self._log(f"   - {line}")
                if len(findings) > 10:
                    self._log(f"   ... 외 {len(findings) - 10}건")
                # v6.3.5: 기본은 팝업 생략(논블로킹), SQM_DUP_POPUP=1 일 때만 모달 표시
                _dup_popup = (os.environ.get("SQM_DUP_POPUP", "").strip() == "1")
                if _dup_popup:
                    popup_lines = findings[:5]
                    popup_msg = "중복 데이터가 감지되었습니다.\n\n"
                    popup_msg += "\n".join([f"• {x}" for x in popup_lines])
                    if len(findings) > 5:
                        popup_msg += f"\n\n... 외 {len(findings) - 5}건"
                    CustomMessageBox.showwarning(
                        self.root,
                        "중복 데이터 경고",
                        popup_msg
                    )
                else:
                    self._log("⚠️ 중복 데이터 경고: 팝업은 생략했습니다. (SQM_DUP_POPUP=1 이면 팝업 표시)")
                self._dup_guard_last_signature = signature
            else:
                self._dup_guard_last_signature = ""
        except (ImportError, ModuleNotFoundError, ValueError, TypeError, AttributeError) as e:
            logger.debug(f"duplicate guard run skip: {e}")
        finally:
            try:
                # P1-4: root 생존 여부 확인 후 재예약 (메모리 누수 방지)
                if self.root and self.root.winfo_exists():
                    self.root.after(self._dup_guard_interval_ms, self._run_duplicate_guard_once)
                else:
                    logger.info("[DupGuard] root 종료됨 — 타이머 루프 중단")
            except (ValueError, TypeError, AttributeError) as e:
                logger.debug(f"duplicate guard reschedule skip: {e}")

    def _save_startup_snapshot(self) -> None:
        """v7.5.0: 앱 시작 시 일별 스냅샷 저장 + 최근 7일 누락 보완"""
        try:
            from core.validators import InventoryValidator
            from datetime import date, timedelta
            validator = InventoryValidator(db=self.engine.db)

            # ① 오늘 스냅샷 저장
            result = validator.save_daily_snapshot()
            if result.get('success'):
                logger.info(
                    f"[스냅샷] {result['date']}: "
                    f"{result['total_lots']}개 LOT, "
                    f"{result['total_weight_kg']:,.0f}kg"
                )

            # ② 최근 7일 누락 스냅샷 자동 보완 (v7.5.0 신규)
            today = date.today()
            for days_ago in range(1, 8):
                missing_date = (today - timedelta(days=days_ago)).isoformat()
                existing = self.engine.db.fetchone(
                    "SELECT id FROM inventory_snapshot WHERE snapshot_date = ?",
                    (missing_date,)
                )
                if not existing:
                    # 해당 날짜 데이터가 없으면 현재 스냅샷으로 백필
                    try:
                        self.engine.db.execute(
                            """INSERT OR IGNORE INTO inventory_snapshot
                               (snapshot_date, total_lots, total_tonbags,
                                total_weight_kg, available_weight_kg,
                                picked_weight_kg, product_summary)
                               SELECT ?, total_lots, total_tonbags,
                                      total_weight_kg, available_weight_kg,
                                      picked_weight_kg, product_summary
                               FROM inventory_snapshot
                               WHERE snapshot_date = ?""",
                            (missing_date, result.get('date', today.isoformat()))
                        )
                        self.engine.db.commit()
                        logger.debug(f"[스냅샷] 누락 보완: {missing_date}")
                    except Exception as _be:
                        logger.debug(f"[스냅샷] 백필 실패({missing_date}): {_be}")

        except (OSError, RuntimeError) as e:
            logger.debug(f"스냅샷 저장 실패 (무시): {e}")

    def _startup_integrity_check(self) -> None:
        """v3.8.4: 시작 시 데이터 정합성 검사. 경고/에러 시 발생 위치·작업을 로그에 명시."""
        _where, _what = "시작 시 정합성 검사", "데이터 정합성 검사"
        try:
            if not self.engine or not hasattr(self.engine, 'db'):
                return

            from core.validators import InventoryValidator
            validator = InventoryValidator(db=self.engine.db)
            result = validator.check_data_integrity()

            issues = []
            if result.errors:
                for e in result.errors:
                    issues.append(f"🔴 {e}")
                    self._log(f"🔴 정합성 오류: {e}", level="error", where=_where, what=_what)
            if result.warnings:
                for w in result.warnings:
                    issues.append(f"🟡 {w}")
                    self._log(f"🟡 정합성 경고: {w}", level="warning", where=_where, what=_what)

            if issues:
                from .utils.custom_messagebox import CustomMessageBox
                msg = "시작 시 데이터 정합성 검사 결과:\n\n"
                msg += "\n".join(issues[:10])
                if len(issues) > 10:
                    msg += f"\n\n... 외 {len(issues) - 10}건"

                if result.errors:
                    msg += "\n\n[설정/도구 → 정합성 복구]에서 자동 수정할 수 있습니다."
                    CustomMessageBox.showwarning(self.root, "⚠️ 정합성 검사", msg)
                else:
                    self._log("경미한 경고 발견 (위 항목 참고).", level="warning", where=_where, what=_what)
            else:
                self._log("데이터 정합성 검사 통과", level="info", where=_where, what=_what)

        except (ImportError, ModuleNotFoundError) as e:
            logger.debug(f"정합성 검사 스킵: {e}")
    
    def mainloop(self, *args, **kwargs) -> None:
        """ttk/Tk 루트는 self.root — 실행 스크립트에서 app.mainloop() 호환용."""
        if hasattr(self, "root") and self.root is not None:
            self.root.mainloop(*args, **kwargs)
            return
        raise RuntimeError("root 창이 초기화되지 않아 mainloop를 실행할 수 없습니다.")

    # ─── v8.6.4: 시작 스플래시 윈도우 (모래시계 + 타이머) ─────────────
    def _show_loading_splash(self) -> None:
        """별도 스플래시 윈도우로 로딩 표시.
        메인 윈도우는 withdraw 상태로 초기화 → 깜빡임 완전 차단.
        _update_splash()로 초기화 단계마다 갱신하여 스플래시가 살아있도록 유지.
        """
        import time as _time
        try:
            _is_dark = getattr(self, 'current_theme', 'darkly').lower() in (
                'darkly', 'cyborg', 'superhero', 'solar', 'vapor')
            bg = '#0b1120' if _is_dark else '#f8fafc'
            fg = '#94a3b8' if _is_dark else '#64748b'
            accent = '#10B981' if _is_dark else '#059669'

            splash = tk.Toplevel(self.root)
            splash.title('SQM Loading...')
            splash.configure(bg=bg)
            splash.attributes('-topmost', True)
            splash.resizable(False, False)

            # 화면 중앙 배치 (300x200)
            sw, sh = 300, 200
            x = (splash.winfo_screenwidth() - sw) // 2
            y = (splash.winfo_screenheight() - sh) // 2
            splash.geometry(f'{sw}x{sh}+{x}+{y}')

            # 테두리 효과
            border_frame = tk.Frame(splash, bg=accent, padx=1, pady=1)
            border_frame.pack(fill='both', expand=True)
            inner = tk.Frame(border_frame, bg=bg)
            inner.pack(fill='both', expand=True)

            # 모래시계 아이콘
            self._splash_icon_label = tk.Label(
                inner, text='\u29D6', font=('Segoe UI', 40), fg=accent, bg=bg)
            self._splash_icon_label.pack(pady=(20, 0))

            # 상태 텍스트 (단계별 갱신됨)
            self._splash_status_var = tk.StringVar(value='시스템 준비 중...')
            tk.Label(
                inner, textvariable=self._splash_status_var,
                font=('맑은 고딕', 11), fg=fg, bg=bg).pack(pady=(10, 0))

            # 경과 타이머
            self._splash_timer_var = tk.StringVar(value='0.0s')
            tk.Label(
                inner, textvariable=self._splash_timer_var,
                font=('Consolas', 10), fg=fg, bg=bg).pack(pady=(4, 0))

            self._splash_window = splash
            self._splash_start_time = _time.perf_counter()
            self._splash_anim_idx = 0
            self._splash_anim_chars = ['\u29D6', '\u29D7']  # ⧖ ⧗
            self._splash_accent = accent

            # 첫 렌더링 강제
            splash.update_idletasks()
            splash.update()
            splash.lift()
            splash.focus_force()
        except Exception as e:
            logger.debug(f"[v8.6.4] 스플래시 표시 실패 (무시): {e}")

    def _update_splash(self, status: str = '') -> None:
        """스플래시 상태 텍스트 + 타이머 + 아이콘 갱신.
        __init__ 도중 호출하여 스플래시가 얼지 않도록 유지.
        """
        import time as _time
        try:
            if not hasattr(self, '_splash_window') or self._splash_window is None:
                return
            # 상태 텍스트
            if status:
                self._splash_status_var.set(status)
            # 타이머
            elapsed = _time.perf_counter() - self._splash_start_time
            self._splash_timer_var.set(f'{elapsed:.1f}s')
            # 모래시계 토글
            self._splash_anim_idx = (self._splash_anim_idx + 1) % 2
            self._splash_icon_label.config(
                text=self._splash_anim_chars[self._splash_anim_idx])
            # 화면 갱신
            self._splash_window.update_idletasks()
            self._splash_window.update()
        except Exception as _e:
            logger.debug(f"[splash] 업데이트 예외 무시: {_e}")

    def _hide_loading_splash(self) -> None:
        """스플래시 제거 + 메인 윈도우 표시."""
        import time as _time
        try:
            # 최종 경과 시간 로그
            elapsed = 0.0
            if hasattr(self, '_splash_start_time'):
                elapsed = _time.perf_counter() - self._splash_start_time
            # 스플래시 닫기
            if hasattr(self, '_splash_window') and self._splash_window:
                self._splash_window.destroy()
                self._splash_window = None
            # 메인 윈도우 표시
            self.root.deiconify()
            logger.info(f"[v8.6.4] 스플래시 제거 → 메인 윈도우 표시 ({elapsed:.1f}s)")
        except Exception as e:
            # 실패해도 메인 윈도우는 반드시 표시
            try:
                self.root.deiconify()
            except Exception as _e2:
                logger.debug(f"[splash] deiconify 실패: {_e2}")
            logger.debug(f"[v8.6.4] 스플래시 제거 실패 (무시): {e}")

    def _force_initial_theme_refresh(self) -> None:
        """v8.4.1 [BUG-A]: 앱 시작 시 모든 탭을 1회 순회하여 위젯 렌더링 강제.
        테마/스크롤바/Footer가 시작 시 안 보이는 레이스컨디션 해결.
        """
        try:
            nb = getattr(self, 'notebook', None)
            if not nb:
                return
            # 현재 활성 탭 저장
            current = nb.select()
            # 모든 탭을 빠르게 1회 순회 (위젯 렌더링 강제)
            for tab_id in nb.tabs():
                try:
                    nb.select(tab_id)
                    nb.update_idletasks()
                except Exception as e:
                    logger.warning(f'[UI] main_app: {e}')
            # 원래 탭으로 복귀
            if current:
                nb.select(current)
            # 테마 재적용 (색상 갱신)
            try:
                from gui_app_modular.utils.theme_refresh import apply_tc_theme_to_all
                apply_tc_theme_to_all(self)
            except Exception as _te:
                logger.debug(f"[BUG-A] 테마 재적용 스킵: {_te}")
            # 사이드바 활성 표시 갱신
            if hasattr(self, '_highlight_active_tab'):
                self._highlight_active_tab()
            # v8.6.4: 메뉴바 컬러 복원 (apply_tc_theme_to_all 이후)
            for btn in getattr(self, '_all_menu_btns', []):
                _mc = getattr(btn, '_menu_color', None)
                if _mc:
                    try: btn.config(fg=_mc)
                    except Exception as e: logger.debug(f"[UI] 메뉴바 컬러 복원 스킵: {e}")
            logger.info("[v8.4.1] 초기 테마/탭 렌더링 강제 완료")
        except Exception as e:
            logger.debug(f"[BUG-A] _force_initial_theme_refresh 스킵: {e}")
    
    def run(self) -> None:
        """Start the application main loop"""
        self._log("Application started")
        self.mainloop()
    
    def _toggle_tab_toolbars(self, active_tab: str) -> None:
        """v3.8.8: 탭 전환 시 해당 탭 전용 툴바만 표시
        
        각 탭이 초기화될 때 self._tab_toolbars dict에 등록하면,
        탭 전환 시 자동으로 show/hide 처리됨.
        
        등록 예: self._tab_toolbars['tonbag'] = [action_bar_widget]
        """
        if not hasattr(self, '_tab_toolbars'):
            return
        
        try:
            for tab_key, widgets in self._tab_toolbars.items():
                for w in widgets:
                    try:
                        if tab_key == active_tab:
                            # 활성 탭의 툴바 표시
                            if not w.winfo_ismapped():
                                w.pack(fill='x')
                        else:
                            # 비활성 탭의 툴바 숨김
                            if w.winfo_ismapped():
                                w.pack_forget()
                    except (RuntimeError, ValueError) as _e:
                        logger.debug(f"{type(_e).__name__}: {_e}")
        except (RuntimeError, ValueError) as _e:
            logger.debug(f"{type(_e).__name__}: {_e}")
        except (RuntimeError, ValueError) as _e:
            logger.debug(f"_toggle_tab_toolbars: {_e}")
    
    # =========================================================================
    # Placeholder methods - These are implemented by mixins
    # =========================================================================
    
    def _log_fallback(self, message: str, level: str = 'info') -> None:
        """Log message - fallback when LogTabMixin not available"""
        logger.debug(f"[{level.upper()}] {message}")
    
    def _set_status_fallback(self, message: str) -> None:
        """Set status bar - fallback when StatusBarMixin not available"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
    
    def _run_background(self, work_fn, on_success=None, on_error=None) -> None:
        """v3.6.5: Background task runner (동기 fallback)
        
        gui/mixins/base_mixin에 비동기 구현이 있지만
        gui_app_modular에서는 간단한 동기 실행으로 대체
        """
        try:
            result = work_fn()
            if on_success:
                on_success(result)
        except (RuntimeError, ValueError) as e:
            logger.error(f"Background task error: {e}")
            if on_error:
                on_error(e)
            elif hasattr(self, '_log'):
                self._log(f"❌ 작업 오류: {e}")
    
    # v3.6.5: _load_theme_preference 제거 (theme_mixin.py에서 정의)
    # MRO 충돌 방지


# Import and mix in all mixin classes
from .mixins import (
    MenuMixin,
    RefreshMixin,
    FeaturesV2Mixin,
    WindowMixin,
    ValidationMixin,
    KeyBindingsMixin,
    ContextMenuMixin,
    ToolbarMixin,
    StatusBarMixin,
    DatabaseMixin,
    DragDropMixin,
    ThemeMixin,
    AdvancedFeaturesMixin,
)

from .tabs import (
    AllocationLotOverviewMixin,
    AllocationTabMixin,
    CargoOverviewTabMixin,
    DashboardTabMixin,
    InventoryTabMixin,
    LogTabMixin,
    MoveTabMixin,
    OutboundScheduledTabMixin,
    PickedTabMixin,
    ReturnTabMixin,
    SoldTabMixin,
    ScanTabMixin,
    SummaryTabMixin,
    TonbagTabMixin,
)
# v5.5.3 P8: PivotLogicMixin 제거 (죽은 코드)
from .tabs.dashboard_data_mixin import DashboardDataMixin

from .handlers import (
    ImportHandlersMixin,
    OutboundHandlersMixin,
    BackupHandlersMixin,
    PDFHandlersMixin,
    ExportHandlersMixin,
    InboundProcessorMixin,
    StatusImportHandlersMixin,
    SimpleOutboundHandlerMixin,
)
from .handlers.pdf_report_handler import PDFReportMixin
from .handlers.inbound_update_mixin import InboundUpdateMixin
from .handlers.outbound_template_mixin import OutboundTemplateMixin
from .handlers.product_handlers import ProductManagementMixin
from .handlers.simple_excel_outbound import SimpleExcelOutboundMixin

from .dialogs import (
    LotAllocationAuditMixin,
    LotDetailDialogMixin,
    SettingsDialogMixin,
    InfoDialogsMixin,
    OutboundPreviewDialogMixin,
)


# Create combined application class with all mixins
class SQMInventoryAppFull(
    SQMInventoryApp,
    # Mixins
    MenuMixin,
    RefreshMixin,
    FeaturesV2Mixin,
    WindowMixin,
    ValidationMixin,
    KeyBindingsMixin,
    ContextMenuMixin,
    ToolbarMixin,
    StatusBarMixin,
    DatabaseMixin,
    DragDropMixin,
    ThemeMixin,
    AdvancedFeaturesMixin,
    # Tabs
    CargoOverviewTabMixin,
    ReturnTabMixin,
    MoveTabMixin,
    AllocationLotOverviewMixin,
    AllocationTabMixin,
    DashboardTabMixin,
    DashboardDataMixin,
    InventoryTabMixin,
    OutboundScheduledTabMixin,
    PickedTabMixin,
    SoldTabMixin,
    ScanTabMixin,
    TonbagTabMixin,
    LogTabMixin,
    SummaryTabMixin,
    # Handlers
    ImportHandlersMixin,
    OutboundHandlersMixin,
    BackupHandlersMixin,
    PDFHandlersMixin,
    ExportHandlersMixin,
    InboundProcessorMixin,
    InboundUpdateMixin,
    StatusImportHandlersMixin,
    SimpleOutboundHandlerMixin,
    OutboundTemplateMixin,
    PDFReportMixin,
    ProductManagementMixin,
    SimpleExcelOutboundMixin,
    # Dialogs
    LotAllocationAuditMixin,
    LotDetailDialogMixin,
    SettingsDialogMixin,
    InfoDialogsMixin,
    OutboundPreviewDialogMixin,
):
    """
    Full SQM Inventory Application with all features
    
    This class combines the base application with all mixins
    to provide the complete functionality.
    """

    def _safe_progress(self, value: int, message: str = '', detail: str = ''):
        """안전한 진행률 업데이트 (어디서든 호출 가능)"""
        try:
            if hasattr(self, 'progress_bar'):
                self.progress_bar['value'] = value
            if message:
                self._log(message)
            if hasattr(self, '_set_status') and (detail or message):
                self._set_status(detail or message)
            if hasattr(self, 'root'):
                self.root.update_idletasks()
        except (AttributeError, RuntimeError) as _e:
            logger.debug(f"{type(_e).__name__}: {_e}")
        except (ValueError, TypeError, AttributeError) as _e:
            logger.debug(f"main_app: {_e}")

    def _update_progress(self, value: int, message: str = '', detail: str = ''):
        """호환성 래퍼"""
        self._safe_progress(value, message, detail)
    
    def _run_integrity_check(self) -> None:
        """
        데이터 정합성 검사 실행
        
        v4.19.1: 정합성 검사 에러 수정
        메뉴: 설정 및 도구 → 데이터 정합성 검사
        """
        try:
            from utils.integrity_check import run_integrity_check
            from .utils.constants import tk
            
            # 검사 실행
            report = run_integrity_check(self.engine.db)
            
            # 결과 다이얼로그
            if report.is_valid:
                tk.CustomMessageBox.info(None, 
                    "✅ 정합성 검사 완료",
                    f"모든 데이터가 정상입니다!\n\n"
                    f"검사 LOT 수: {report.total_lots}개\n"
                    f"정상: {report.valid_lots}개\n"
                    f"경고: {report.warning_lots}개"
                )
            else:
                error_msg = "\n".join([
                    f"- {err['lot_no']}: {err['message']}"
                    for err in report.errors[:5]
                ])
                
                tk.CustomMessageBox.warning(None, 
                    "⚠️ 정합성 문제 발견",
                    f"일부 데이터에 문제가 있습니다.\n\n"
                    f"오류 LOT: {len(report.errors)}개\n\n"
                    f"{error_msg}\n\n"
                    f"전체 보고서는 로그를 확인하세요."
                )
        
        except ImportError as e:
            from .utils.constants import tk
            tk.CustomMessageBox.error(None, 
                "기능 로딩 실패",
                f"정합성 검사 모듈을 불러올 수 없습니다.\n\n{e}"
            )
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            logger.exception("정합성 검사 실패")
            from .utils.constants import tk
            tk.CustomMessageBox.error(None,
                "검사 실행 실패",
                f"정합성 검사 중 오류가 발생했습니다.\n\n{e}"
            )

    # ══════════════════════════════════════════════════════════════════════
    # v8.7.0 [FIX CRIT-1]: 아래 메서드들은 이전 버전에서 실수로 `if __name__ == '__main__':`
    # 블록 내부에 들여쓰기되어 있어 런타임에 클래스에 바인딩되지 않고 dead code 상태였음.
    # 메뉴(도구 > 제품 마스터, 제품별 재고 리포트, DB 마이그레이션 등)가 조용히 실패.
    # 클래스 본체로 복귀시킴.
    # ══════════════════════════════════════════════════════════════════════

    # --------------------------
    # v5.3.1: Manual DB Migration (v5.3.0)
    # --------------------------
    def _on_run_v530_migration(self):
        """Manual migration trigger: v5.3.0 audit columns + mapping history."""
        try:
            # engine may expose migration mixin via self.engine.db or similar; best-effort call
            mig = None
            if hasattr(self, "engine") and hasattr(self.engine, "db_migration"):
                mig = self.engine.db_migration
            elif hasattr(self, "engine") and hasattr(self.engine, "db"):
                mig = getattr(self.engine.db, "migration", None)
            elif hasattr(self, "engine"):
                mig = getattr(self.engine, "migration", None)

            if mig is None and hasattr(self, "engine"):
                # fallback: try attribute name
                mig = getattr(self.engine, "db_migration_mixin", None)

            if mig is None:
                raise RuntimeError("Migration runner not found on engine.")
            if hasattr(mig, "run_v530_migration_manual"):
                mig.run_v530_migration_manual()
            else:
                raise RuntimeError("run_v530_migration_manual() not found.")
            CustomMessageBox.info(None, "DB Migration", "v5.3.0 migration completed successfully.")
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            CustomMessageBox.error(None, "DB Migration (HARD STOP)", f"Migration failed: {e}")

    # --------------------------
    # v5.3.3: Menu Theme Fix (white theme background issue) - best effort
    # --------------------------
    def _read_ui_settings(self):
        base = os.getcwd()
        cfg = configparser.ConfigParser()
        try:
            cfg.read(os.path.join(base, 'settings.ini'), encoding='utf-8')
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as _e:
            logger.debug(f"Suppressed: {_e}")
        menu_fix = cfg.getint('ui', 'menu_fix_enabled', fallback=1)
        return {"menu_fix_enabled": menu_fix}

    def _show_product_inventory_report(self):
        """도구 > 제품별 재고 현황 리포트."""
        try:
            from .dialogs.product_inventory_report import show_product_inventory_report
            show_product_inventory_report(self)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                from tkinter import messagebox
                messagebox.showerror("오류", f"제품별 리포트 열기 실패:\n{e}")
            except Exception:
                logger.debug("[SUPPRESSED] exception in main_app.py")  # noqa

    # v6.2.7: 제품 마스터 관리
    def _show_product_master(self):
        """도구 > 제품 마스터 관리 다이얼로그."""
        try:
            from .dialogs.product_master_dialog import show_product_master_dialog
            show_product_master_dialog(self)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                from tkinter import messagebox
                messagebox.showerror("오류", f"제품 마스터 열기 실패:\n{e}")
            except Exception:
                logger.debug("[SUPPRESSED] exception in main_app.py")  # noqa


def main():
    """GUI 전용 진입 (부트스트랩 없음). 정식 실행은 run.py 또는 python -m gui_app_modular 사용."""
    import argparse

    parser = argparse.ArgumentParser(description='SQM Inventory Management System')
    parser.add_argument('--db', type=str, help='Database path')
    parser.add_argument('--theme', type=str, default='darkly', help='UI theme (default: darkly)')
    args = parser.parse_args()

    app = SQMInventoryAppFull(db_path=args.db)
    app.run()


# 개발/테스트용: 이 파일 직접 실행 시 환경 점검·MAC Guard·자동 백업 생략
if __name__ == '__main__':
    main()
