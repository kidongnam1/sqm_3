# -*- coding: utf-8 -*-
"""
SQM 재고관리 - 커스텀 메뉴바 (v3.0)
===================================

ttkbootstrap 기반 메뉴바
- 간격/패딩 조절 가능
- 테마 통합
- 컴팩트한 UI
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import sqlite3
import tkinter as tk
from ..utils.ui_constants import is_dark, CustomMessageBox, ThemeColors
try:
    from ..menu_registry import FILE_MENU_AI_TOOLS_ITEMS  # noqa: F401
except ImportError:
    FILE_MENU_AI_TOOLS_ITEMS = []  # fallback
from typing import Dict, Callable
from utils.ui_debug import log_ui_event, safe_widget_bg  # v5.3.6

logger = logging.getLogger(__name__)


class CustomMenuBar:
    """
    ttkbootstrap 기반 커스텀 메뉴바
    
    tk.Menu 대신 ttk.Frame + Menubutton 사용
    """
    
    # 메뉴 스타일 설정 (v4.0.8: 가시성 대폭 개선)
    MENU_FONT = ('맑은 고딕', 13, 'bold')
    MENU_PADX = 16
    MENU_PADY = 7
    DROPDOWN_FONT = ('맑은 고딕', 11)
    
    # v4.0.8 / v8.7.0 Phase2: 메뉴바 색상 — ThemeColors 단일 소스 (메뉴바는 다크 스타일)
    MENUBAR_BG = None  # __init__에서 ThemeColors로 설정
    MENUBAR_FG = None
    MENUBAR_HOVER_BG = None
    MENUBAR_ACTIVE_BG = None
    DROPDOWN_BG = None
    DROPDOWN_FG = None
    DROPDOWN_ACTIVE_BG = None
    DROPDOWN_ACTIVE_FG = None
    
    def __init__(self, parent, app):
        """
        Args:
            parent: 부모 위젯 (root)
            app: SQMInventoryApp 인스턴스
        """
        from ..utils.constants import tk, ttk, X
        
        self.parent = parent
        self.app = app
        self.tk = tk
        self.ttk = ttk

        # v8.7.0 Phase2: ThemeColors 단일 소스 (메뉴바 다크, 드롭다운은 테마 따름)
        _dark_bar = True
        _dark_dd = ThemeColors.is_dark_theme(getattr(app, 'current_theme', 'darkly'))
        self.MENUBAR_BG = ThemeColors.get('statusbar_bg', _dark_bar)
        self.MENUBAR_FG = ThemeColors.get('statusbar_fg', _dark_bar)
        self.MENUBAR_HOVER_BG = ThemeColors.get('bg_hover', _dark_bar)
        self.MENUBAR_ACTIVE_BG = ThemeColors.get('info', _dark_bar)
        self.DROPDOWN_BG = ThemeColors.get('bg_card', _dark_dd)
        self.DROPDOWN_FG = ThemeColors.get('text_primary', _dark_dd)
        self.DROPDOWN_ACTIVE_BG = ThemeColors.get('info', _dark_dd)
        self.DROPDOWN_ACTIVE_FG = ThemeColors.get('badge_text', _dark_dd)
        
        # v4.0.8: 메뉴바 프레임 — 진한 배경, 충분한 높이
        self.menubar_frame = tk.Frame(parent, bg=self.MENUBAR_BG, pady=3, padx=6)
        self.menubar_frame.pack(fill=X, side='top')
        
        # 메뉴바를 맨 위로 올리기 (lift)
        self.menubar_frame.lift()
        
        # 메뉴 버튼들 저장
        self.menu_buttons: Dict[str, ttk.Menubutton] = {}
        self.menus: Dict[str, tk.Menu] = {}
        
        # 메뉴 구성
        self._create_menus()

    def _get_return_doc_review_pending_count(self, days: int = 30) -> int:
        """최근 N일 반품 문서점검 대기건(RETURN_DOC_REVIEW) 개수."""
        try:
            row = self.app.engine.db.fetchone(
                """
                SELECT COUNT(*) AS cnt
                FROM stock_movement
                WHERE movement_type = 'RETURN_DOC_REVIEW'
                  AND DATE(created_at) >= DATE('now', ?)
                """,
                (f"-{int(days)} days",),
            )
            if not row:
                return 0
            return int((row.get('cnt') if isinstance(row, dict) else row[0]) or 0)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError, TypeError, KeyError, AttributeError) as e:
            logger.debug(f"[custom_menubar] 반품 문서점검 카운트 조회 오류: {e}")
            return 0

    @staticmethod
    def _format_return_review_badge(count: int) -> str:
        """
        반품 문서점검 메뉴 배지 문자열.
        - 0건: 표시 없음
        - 1~4건: 🟡 [N]
        - 5건 이상: 🔴 [N]
        """
        if count <= 0:
            return ""
        icon = "🔴" if count >= 5 else "🟡"
        return f" {icon} [{count}]"
    
    def _get_first_child(self):
        """첫 번째 자식 위젯 반환 (더 이상 사용 안 함)"""
        children = self.parent.winfo_children()
        return children[0] if children else None
    
    def _create_menus(self) -> None:
        """v4.1.4: 메뉴 재구성 — v6.0.2: 탑레벨 출고 먼저(Picking List 노출)"""
        self._create_outbound_menu()
        self._create_file_menu()
        self._create_report_menu()
        self._create_tools_menu()
        self._create_features_menu()
        self._create_view_menu()
        self._create_help_menu()
        self._create_product_menu()

    def _create_outbound_menu(self) -> None:
        """탑레벨 📤 출고 메뉴 — menu_registry 기반 (Picking List 등 반드시 포함, 예외 시에도 항목 표시)"""
        outbound_menu = self._add_menu("📤 출고")
        try:
            from ..menu_registry import FILE_MENU_OUTBOUND_ITEMS
        except Exception as e:
            logger.debug("menu_registry 로드 실패, 출고 메뉴 기본 항목만 표시: %s", e)
            FILE_MENU_OUTBOUND_ITEMS = []

        for entry in FILE_MENU_OUTBOUND_ITEMS:
            if entry is None:
                self._add_separator(outbound_menu)
                continue
            label, method_name = entry[0], entry[1]
            optional = entry[2] if len(entry) > 2 else False
            if optional and (not hasattr(self.app, method_name) or not callable(getattr(self.app, method_name))):
                continue
            callback = getattr(self.app, method_name, None)
            if not callable(callback):
                callback = lambda l=label: CustomMessageBox.showinfo(
                    self.parent, "출고", f"'{l}' 기능을 불러오는 중입니다.\n앱을 재시작해 보세요."
                )
            try:
                self._add_command(outbound_menu, label, callback)
            except Exception as e:
                logger.debug("출고 메뉴 항목 추가 스킵 %s: %s", label, e)

    def _create_file_menu(self) -> None:
        """1. 📁 파일 메뉴 (입고는 menu_registry, 출고는 탑레벨로 분리)"""
        from ..menu_registry import (
            FILE_MENU_INBOUND_ITEMS,
            FILE_MENU_INBOUND_RETURN_SUB_ITEMS,
            FILE_MENU_EXPORT_ITEMS,
            FILE_MENU_BACKUP_ITEMS,
        )
        
        # =====================================================
        # 1. 파일 메뉴 (v6.0.2: 출고는 탑레벨 📤 출고 메뉴로 이동)
        # =====================================================
        file_menu = self._add_menu("📁 파일")
        
        # 입고 — menu_registry 기반
        inbound_sub = self._add_submenu(file_menu, "📥 입고 (Ctrl+I)")
        for entry in FILE_MENU_INBOUND_ITEMS:
            if entry is None:
                self._add_separator(inbound_sub)
                continue
            label, method_name = entry[0], entry[1]
            optional = entry[2] if len(entry) > 2 else False
            callback = getattr(self.app, method_name, None)
            if method_name == "_show_return_dialog":
                pending = self._get_return_doc_review_pending_count(30)
                badge = self._format_return_review_badge(pending)
                return_sub = self._add_submenu(inbound_sub, f"{label}{badge}")
                if callable(callback):
                    for sub_label, mode in FILE_MENU_INBOUND_RETURN_SUB_ITEMS:
                        self._add_command(return_sub, sub_label, lambda md=mode, fn=callback: fn(md))
                else:
                    self._add_command(return_sub, "📝 소량 반품 (1~2건)", self._show_return_safe)
                continue
            if optional and not callable(callback):
                continue
            if callable(callback):
                self._add_command(inbound_sub, label, callback)
        self._add_separator(inbound_sub)
        
        self._add_separator(file_menu)
        
        # 내보내기
        export_sub = self._add_submenu(file_menu, "💾 내보내기 (Ctrl+E)")
        for label, option in FILE_MENU_EXPORT_ITEMS:
            self._add_command(export_sub, label, lambda op=option: self.app._on_export_click(op))
        
        self._add_separator(file_menu)
        
        # 백업 (v3.8.4: 자동 백업 추가)
        backup_sub = self._add_submenu(file_menu, "🔐 백업 (Ctrl+B)")
        for label, method_name in FILE_MENU_BACKUP_ITEMS:
            callback = getattr(self.app, method_name, None)
            if callable(callback):
                self._add_command(backup_sub, label, callback)
        self._add_separator(backup_sub)
        self._add_command(backup_sub, "⏰ 자동 백업 설정", self.app._show_auto_backup_settings)
        
        self._add_separator(file_menu)
        
        # 도구 (v8.1.5: PDF 변환은 🔧 도구 메뉴 단일화 — 파일 메뉴 내 중복 제거)
        tools_sub = self._add_submenu(file_menu, "🔧 도구")
        self._add_command(tools_sub, "📷 문서 변환 (OCR/PDF)", self._show_doc_convert_safe)
        self._add_separator(tools_sub)
        self._add_command(tools_sub, "🩺 데이터 정합성 검사", self._show_integrity_check_safe)
        
        self._add_separator(file_menu)
        
        # 최근 파일
        self.recent_menu = self._add_submenu(file_menu, "📂 최근 파일")
        self._update_recent_files()
        
        self._add_separator(file_menu)
        self._add_command(file_menu, "종료", self.parent.quit)

    def _create_report_menu(self) -> None:
        """보고서 메뉴 — menu_registry.MENU_REPORT_ITEMS 단일 소스 (v8.1.4)"""
        report_menu = self._add_menu("📝 보고서")
        try:
            from ..menu_registry import MENU_REPORT_ITEMS
            for entry in MENU_REPORT_ITEMS:
                if entry is None:
                    self._add_separator(report_menu)
                    continue
                label = entry[0]
                method_name = entry[1]
                optional = entry[2] if len(entry) > 2 else False
                cb = getattr(self.app, method_name, None)
                if optional and not callable(cb):
                    continue
                if callable(cb):
                    self._add_command(report_menu, label, cb)
        except Exception as e:
            logger.warning(f"[UI] 보고서 메뉴 registry 로드 실패, 폴백: {e}")
            self._add_command(report_menu, "📄 거래 명세서", self.app._generate_invoice_pdf)
            self._add_separator(report_menu)
            self._add_command(report_menu, "📦 재고 현황 보고서", self.app._generate_inventory_pdf_report)
        
    def _create_tools_menu(self) -> None:
        """2. 🔧 도구 메뉴"""
        from ..utils.constants import (
            HAS_GEMINI, HAS_DB_PROTECTION, HAS_FEATURES
        )
        # =====================================================
        # 2. 도구 메뉴
        # =====================================================
        tools_menu = self._add_menu("🔧 도구")
        
        # v5.9.0: 컨테이너 구분 → 필터바 초기화 옆으로 이동 (변수만 초기화)
        if not hasattr(self.app, '_container_suffix_var'):
            self.app._container_suffix_var = self.tk.BooleanVar(value=True)
        
        # 📦 제품 마스터 관리
        self._add_command(tools_menu, "📦 제품 마스터 관리", self.app._show_product_master)
        self._add_command(tools_menu, "📊 제품별 재고 현황", self.app._show_product_inventory_report)
        if hasattr(self.app, "_show_lot_allocation_audit_dialog"):
            self._add_command(
                tools_menu, "📊 LOT Allocation·톤백 현황", self.app._show_lot_allocation_audit_dialog
            )
        self._add_separator(tools_menu)
        # D/O 후속 연결 (입고 후 D/O 나중에 도착 시 LOT에 도착일/Free Time 보충)
        self._add_command(tools_menu, "📋 D/O 후속 연결", self.app._on_do_update)
        self._add_separator(tools_menu)
        
        # PDF/이미지 변환
        pdf_sub = self._add_submenu(tools_menu, "📄 PDF/이미지 변환")
        self._add_command(pdf_sub, "→ Excel", self.app._convert_pdf_to_excel)
        self._add_command(pdf_sub, "→ Word", self.app._convert_pdf_to_word)
        self._add_separator(pdf_sub)
        self._add_command(pdf_sub, "📁 일괄 변환", self.app._batch_convert_pdf_excel)
        self._add_command(pdf_sub, "🔍 분석", self.app._analyze_pdf)
        
        # v3.8.4: 문서 변환 (OCR)
        self._add_command(tools_menu, "📷 문서 변환 (OCR/PDF)", self._show_doc_convert_safe)
        
        # PDF 보고서 (거래 명세서는 상단 보고서 메뉴로 이동)
        report_sub = self._add_submenu(tools_menu, "📋 PDF 보고서")
        self._add_command(report_sub, "📦 재고 현황 보고서", self.app._generate_inventory_pdf_report)
        self._add_command(report_sub, "📈 입출고 내역", self.app._generate_transaction_pdf)
        self._add_command(report_sub, "📤 출고 확인서", self.app._generate_outbound_confirm_pdf)
        self._add_command(report_sub, "🔖 LOT 상세", self.app._generate_lot_detail_pdf)
        report_sub.add_separator()
        self._add_command(report_sub, "📊 일일 현황 PDF", self.app._generate_daily_pdf_v398)
        self._add_command(report_sub, "📅 월간 실적 PDF", self.app._generate_monthly_pdf_v398)
        
        self._add_separator(tools_menu)
        
        # v3.8.4: 정합성 리포트
        self._add_command(tools_menu, "🩺 데이터 정합성 검사", self._show_integrity_check_safe)
        
        self._add_separator(tools_menu)
        
        # v4.1.2: Gemini AI — 항상 표시 (API 키 없으면 설정 안내)
        # v6.4.0: 선사 BL 등록 도구 추가
        api_sub = self._add_submenu(tools_menu, "🤖 Gemini AI")
        if HAS_GEMINI:
            self.app._gemini_var = self.tk.BooleanVar(value=getattr(self.app, 'use_gemini', False))
            self._add_checkbutton(api_sub, "API 사용", self.app._gemini_var, self.app._toggle_gemini)
            self._add_separator(api_sub)
        # BL 선사 도구 (v6.4.0 registry 기반, optional)
        for _lbl, _mth, *_ in FILE_MENU_AI_TOOLS_ITEMS:
            self._add_command(
                api_sub, _lbl,
                getattr(self.app, _mth, None) or
                (lambda m=_mth: self._safe_call(m) if hasattr(self, '_safe_call') else None)
            )
        self._add_separator(api_sub)
        self._add_command(api_sub, "💬 AI 채팅", self.app._open_ai_chat)
        self._add_command(api_sub, "⚙️ API 설정", self.app._show_api_settings)
        self._add_command(api_sub, "🔬 API 테스트", self.app._test_gemini_api_connection)
        self._add_separator(tools_menu)
        
        # DB 보호 (조건부)
        if HAS_DB_PROTECTION:
            db_sub = self._add_submenu(tools_menu, "🛡️ DB 보호")
            self._add_command(db_sub, "🔍 무결성 검증", self.app._verify_db_integrity)
            self._add_command(db_sub, "📋 작업 로그", self.app._show_action_log)
            self._add_command(db_sub, "💾 로그 내보내기", self.app._export_action_log)
            self._add_separator(db_sub)
            self._add_command(db_sub, "🔄 체크섬 갱신", self.app._update_checksum)
            self._add_separator(tools_menu)
        
        self._add_command(tools_menu, "🔍 DB 검사", self.app._on_integrity_check)
        self._add_command(tools_menu, "🔧 DB 최적화", self.app._on_optimize_db)
        self._add_separator(tools_menu)
        self._add_command(tools_menu, "📋 로그 정리", self.app._on_cleanup_logs)
        self._add_command(tools_menu, "ℹ️  DB 정보", self.app._show_db_info)
        self._add_separator(tools_menu)
        if hasattr(self.app, '_is_developer_mode_enabled') and self.app._is_developer_mode_enabled():
            self._add_command(tools_menu, "🗑️ 테스트 DB 초기화 (데이터 삭제)", self.app._show_test_db_reset_popup)
        
        # 고급 기능 (조건부)
        if HAS_FEATURES:
            self._add_separator(tools_menu)
            adv_sub = self._add_submenu(tools_menu, "✨ 고급")
            self._add_command(adv_sub, "🔬 입고 검증", self.app._dry_run_inbound)
            self._add_command(adv_sub, "🔬 출고 검증", self.app._dry_run_outbound)
            self._add_separator(adv_sub)
            self._add_command(adv_sub, "🩺 전체 진단", self.app._run_self_test)
            self._add_command(adv_sub, "🧪 단위 테스트", self.app._open_test_runner)
        
    def _create_features_menu(self) -> None:
        """v8.1.5: 🚀 v2.7 메뉴 — features_v2 미사용으로 완전 비활성화 (함수 유지, 실제 메뉴 생성 안 함)"""
        # features_v2.py 가 존재하지 않으므로 HAS_FEATURES_V2=False → 메뉴 불필요
        # 기동님 확인 2026-03-23: 현재 UI에서 미사용 메뉴이므로 제거 확정
        pass

    def _create_view_menu(self) -> None:
        """👁️ 보기 메뉴 — 위젯 참조(tab_xxx) 방식으로 교체 (v8.1.5)
        
        [수정 이유] notebook.select(숫자) 방식은 탭이 숨김/추가되면 인덱스가
        밀려 엉뚱한 탭이 선택되는 버그 발생. → self.app.tab_xxx 위젯 직접 참조로 고정.
        """
        view_menu = self._add_menu("👁️ View")
        self._add_command(view_menu, "🔄 Refresh (F5)", self.app._refresh_inventory)
        self._add_separator(view_menu)

        # v8.1.7: 위젯 참조 방식 — optional=True 이면 탭 미존재 시 항목 생략
        def _go(tab_attr: str):
            """위젯 참조로 탭 이동 — 인덱스 오동작 버그 방지"""
            tab = getattr(self.app, tab_attr, None)
            if tab and self.app.notebook.winfo_exists():
                try:
                    self.app.notebook.select(tab)
                except Exception as e:
                    logger.warning(f'[UI] custom_menubar: {e}')
        def _add_tab_cmd(label: str, tab_attr: str, optional: bool = False):
            if optional and not getattr(self.app, tab_attr, None):
                return
            self._add_command(view_menu, label, lambda a=tab_attr: _go(a))

        # 사이드바 워크플로우 탭
        _add_tab_cmd("📦 Inventory",   "tab_inventory")
        _add_tab_cmd("📋 Allocation",  "tab_allocation")
        _add_tab_cmd("🚛 Picked",      "tab_picked")
        _add_tab_cmd("📤 Outbound",    "tab_sold")
        _add_tab_cmd("🔄 Return",      "tab_return")
        _add_tab_cmd("🔀 Move",        "tab_move")
        self._add_separator(view_menu)
        # 메뉴 전용 탭
        _add_tab_cmd("📊 Dashboard",   "tab_dashboard")
        _add_tab_cmd("📝 Log",         "tab_log")
        _add_tab_cmd("📷 Scan",        "tab_scan", optional=True)
        self._add_separator(view_menu)
        self._add_command(view_menu, "🎨 Theme", self.app._show_theme_selector)
        
    def _create_help_menu(self) -> None:
        """도움말 메뉴 — menu_registry.MENU_HELP_ITEMS 단일 소스 (v8.1.4)"""
        help_menu = self._add_menu("❓ 도움말")
        try:
            from ..menu_registry import MENU_HELP_ITEMS
            for entry in MENU_HELP_ITEMS:
                if entry is None:
                    self._add_separator(help_menu)
                    continue
                label = entry[0]
                method_name = entry[1]
                optional = entry[2] if len(entry) > 2 else False
                # app 또는 self(CustomMenuBar)에서 메서드 검색
                cb = getattr(self.app, method_name, None) or getattr(self, method_name, None)
                if optional and not callable(cb):
                    continue
                if callable(cb):
                    self._add_command(help_menu, label, cb)
        except Exception as e:
            logger.warning(f"[UI] 도움말 메뉴 registry 로드 실패, 폴백: {e}")
            self._add_command(help_menu, "📖 사용법", self.app._show_help)
            self._add_command(help_menu, "📝 버전 정보", self.app._show_about)
        
    def _create_product_menu(self) -> None:
        """6. 📦 품목 메뉴"""
        # =====================================================
        # 6. 품목관리 메뉴 (v4.1.2)
        # =====================================================
        product_menu = self._add_menu("📦 품목")
        self._add_command(product_menu, "📋 품목별 재고 요약", self.app._show_product_summary)
        self._add_command(product_menu, "🔍 품목별 LOT 조회", self.app._show_product_lot_lookup)
        self._add_separator(product_menu)
        self._add_command(product_menu, "📊 품목별 입출고 현황", self.app._show_product_movement)
    # --------------------------
    # v5.3.5: Light theme menu bg reset fix (Menubutton/Menu)
    # --------------------------
    def _restore_menubar_colors(self):
        """Force restore menubar frame + buttons to configured colors."""
        try:
            if self.menubar_frame and self.menubar_frame.winfo_exists():
                self.menubar_frame.config(bg=self.MENUBAR_BG)
        except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")
        for _label, _btn in list(self.menu_buttons.items()):
            try:
                if not _btn or (hasattr(_btn,'winfo_exists') and not _btn.winfo_exists()):
                    continue
                active = getattr(_btn, '_menu_active', False)
                _btn.config(bg=(self.MENUBAR_ACTIVE_BG if active else self.MENUBAR_BG))
            except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")
        try:
            self.parent.update_idletasks()
        except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")

        # v5.3.6: anomaly logging (light theme bg reset)
        try:
            exp = getattr(self, 'MENUBAR_BG', None)
            cur = safe_widget_bg(getattr(self, 'menubar_frame', None))
            if exp and cur and cur != exp:
                log_ui_event('UI_BG_ANOMALY_MENUBAR', {'expected': exp, 'current': cur})
        except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")

    def refresh_theme_colors(self) -> None:
        """v5.7: 테마 변경 시 메뉴바·드롭다운 색상 캐시 갱신 후 위젯에 재적용 (글씨/배경 동기화)"""
        try:
            _dark_bar = True
            _theme = getattr(self.app, 'current_theme', 'darkly')
            _dark_dd = ThemeColors.is_dark_theme(_theme)
            self.MENUBAR_BG = ThemeColors.get('statusbar_bg', _dark_bar)
            self.MENUBAR_FG = ThemeColors.get('statusbar_fg', _dark_bar)
            self.MENUBAR_HOVER_BG = ThemeColors.get('bg_hover', _dark_bar)
            self.MENUBAR_ACTIVE_BG = ThemeColors.get('info', _dark_bar)
            self.DROPDOWN_BG = ThemeColors.get('bg_card', _dark_dd)
            self.DROPDOWN_FG = ThemeColors.get('text_primary', _dark_dd)
            self.DROPDOWN_ACTIVE_BG = ThemeColors.get('info', _dark_dd)
            self.DROPDOWN_ACTIVE_FG = ThemeColors.get('badge_text', _dark_dd)
            self._restore_menubar_colors()
            for _menu in (self.menus or {}).values():
                try:
                    if _menu and getattr(_menu, 'winfo_exists', lambda: True) and _menu.winfo_exists():
                        _menu.config(
                            bg=self.DROPDOWN_BG,
                            fg=self.DROPDOWN_FG,
                            activebackground=self.DROPDOWN_ACTIVE_BG,
                            activeforeground=self.DROPDOWN_ACTIVE_FG,
                        )
                except (ValueError, TypeError, AttributeError, self.tk.TclError) as _e:
                    logger.debug(f"메뉴 색상 갱신 무시: {_e}")
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"refresh_theme_colors 무시: {e}")

    def _schedule_restore_menubar(self):
        """Restore multiple times to beat Windows/Tk internal refresh timing."""
        try:
            self.parent.after_idle(self._restore_menubar_colors)
            for ms in (50, 200, 500, 1000):
                self.parent.after(ms, self._restore_menubar_colors)
        except (ValueError, TypeError, AttributeError, tk.TclError):
            try:
                self._restore_menubar_colors()
            except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")


    
    def _add_menu(self, label: str) -> 'tk.Menu':
        """v4.0.8: 고대비 메뉴 버튼 — 진한 남색 배경 + 흰 텍스트 + 호버 효과"""
        from ..utils.constants import LEFT
        
        # 드롭다운 메뉴 생성 (밝은 배경)
        menu = self.tk.Menu(self.parent, tearoff=0, font=self.DROPDOWN_FONT,
                            bg=self.DROPDOWN_BG, fg=self.DROPDOWN_FG,
                            activebackground=self.DROPDOWN_ACTIVE_BG,
                            activeforeground=self.DROPDOWN_ACTIVE_FG,
                            relief='flat', bd=1)
        
        # v4.0.8: tk.Menubutton (진한 배경 + 흰 글자)
        btn = self.tk.Menubutton(
            self.menubar_frame,
            text=f"  {label}  ",
            font=self.MENU_FONT,
            bg=self.MENUBAR_BG,
            fg=self.MENUBAR_FG,
            activebackground=self.MENUBAR_ACTIVE_BG,
            activeforeground=self.MENUBAR_FG,
            relief='flat',
            bd=0,
            padx=self.MENU_PADX,
            pady=self.MENU_PADY,
            menu=menu,
        )
        btn.pack(side=LEFT)
        btn._menu_active = False  # v5.3.5

        try:
            from ..utils.menu_tab_tooltips import menubar_top_tooltip
            from ..utils.ui_constants import apply_tooltip
            _mb_tip = menubar_top_tooltip(label.strip())
            if _mb_tip:
                apply_tooltip(btn, _mb_tip)
        except Exception as e:
            logger.debug("menubutton tooltip: %s", e)

        # 호버 효과 (v5.0.9: 안전한 색상 복구)
        def on_enter(e):
            try:
                if getattr(btn, '_menu_active', False):
                    return
                btn.config(bg=self.MENUBAR_HOVER_BG)
            except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
                logger.debug(f"[custom_menubar] 무시: {_e}")
        def on_leave(e):
            try:
                if getattr(btn, '_menu_active', False):
                    return
                btn.config(bg=self.MENUBAR_BG)
            except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
                logger.debug(f"[custom_menubar] 무시: {_e}")
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)

        # v5.3.5: menu open/close tracking
        def _on_menu_click(e):
            try:
                # mark active right before posting
                btn._menu_active = True
                btn.config(bg=self.MENUBAR_ACTIVE_BG)
            except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")
            # schedule restore to beat any internal refresh
            self._schedule_restore_menubar()

        def _on_menu_unmap(e=None):
            try:
                btn._menu_active = False
            except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")
            self._schedule_restore_menubar()

        try:
            btn.bind('<Button-1>', _on_menu_click, add='+')
            menu.bind('<Unmap>', _on_menu_unmap, add='+')
        except (ValueError, TypeError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")

        
        # 저장
        self.menu_buttons[label] = btn
        self.menus[label] = menu
        
        return menu
    
    def _add_command(self, menu: 'tk.Menu', label: str, command: Callable) -> None:
        """메뉴 항목 추가 (v3.6.9: 넉넉한 간격)"""
        menu.add_command(
            label=f"  {label}",
            command=command,
            font=self.DROPDOWN_FONT,
            hidemargin=False,
        )
    
    def _add_header(self, menu: 'tk.Menu', label: str) -> None:
        """비활성 헤더 라벨 (구분 제목용)"""
        menu.add_command(
            label=label,
            state='disabled',
            font=('맑은 고딕', 13, 'bold'),
        )
    
    def _add_submenu(self, parent_menu: 'tk.Menu', label: str) -> 'tk.Menu':
        """서브메뉴 추가 (v4.0.8: 색상 통일)"""
        submenu = self.tk.Menu(parent_menu, tearoff=0, font=self.DROPDOWN_FONT,
                               bg=self.DROPDOWN_BG, fg=self.DROPDOWN_FG,
                               activebackground=self.DROPDOWN_ACTIVE_BG,
                               activeforeground=self.DROPDOWN_ACTIVE_FG)
        parent_menu.add_cascade(label=label, menu=submenu, font=self.DROPDOWN_FONT)
        return submenu
    
    def _add_separator(self, menu: 'tk.Menu') -> None:
        """구분선 추가"""
        menu.add_separator()
    
    def _add_checkbutton(self, menu: 'tk.Menu', label: str, 
                         variable: 'tk.BooleanVar', command: Callable) -> None:
        """체크박스 메뉴 항목 추가"""
        menu.add_checkbutton(
            label=label,
            variable=variable,
            command=command,
            font=self.DROPDOWN_FONT,
        )
    
    def _show_status_guide(self) -> None:
        """v4.0.8: STATUS 상태값 안내 팝업"""
        from ..utils.constants import tk
        
        guide = create_themed_toplevel(self.parent)
        guide.title("📊 STATUS 상태값 안내")
        guide.geometry("620x520")
        guide.transient(self.parent)
        guide.grab_set()
        
        # 제목
        tk.Label(guide, text="📊 SQM 재고 STATUS 상태값 안내",
                 font=('맑은 고딕', 16, 'bold'), fg=ThemeColors.get('text_primary')).pack(pady=(15, 5))
        tk.Label(guide, text="재고(LOT) 및 톤백에 사용되는 상태값 목록",
                 font=('맑은 고딕', 11), fg=ThemeColors.get('text_secondary')).pack(pady=(0, 10))
        
        # 상태값 프레임
        content = tk.Frame(guide, padx=20, pady=10)
        content.pack(fill='both', expand=True)
        
        _gd = is_dark()
        _sec = ThemeColors.get('text_secondary', _gd)
        _pri = ThemeColors.get('text_primary', _gd)
        statuses = [
            ('✅ 판매가능', '판매가능', ThemeColors.get('badge_db', _gd), ThemeColors.get('available', _gd),
             '출고 가능한 정상 재고. 입고 완료 후 기본 상태.'),
            ('📤 판매화물 결정', '판매화물 결정', ThemeColors.get('statusbar_icon_warn', _gd), ThemeColors.get('picked', _gd),
             '판매 배정 완료. 아직 선적 전.'),
            ('✔️ 출고 확정', '출고 확정', ThemeColors.get('info', _gd), ThemeColors.get('tree_select_bg', _gd),
             '출고 확정됨. 판매화물 결정 → 출고 확정 전환 후 선적 대기.'),
            ('🚢 선적 완료', '선적 완료', ThemeColors.get('info', _gd), ThemeColors.get('shipped', _gd),
             '실제 출하(선적) 완료. 창고에서 나간 상태.'),
            ('❌ 소진', '소진', ThemeColors.get('text_secondary', _gd), ThemeColors.get('bg_secondary', _gd),
             '해당 LOT/톤백의 재고가 모두 소진됨. 0 kg.'),
            ('🔒 판매배정', '판매배정', ThemeColors.get('statusbar_icon_warn', _gd), ThemeColors.get('reserved', _gd),
             '특정 고객/주문에 배정된 재고. 다른 출고에 사용 불가.'),
            ('🧪 샘플', '샘플', ThemeColors.get('success', _gd), ThemeColors.get('available', _gd),
             '샘플 톤백(1kg). 정규 재고와 별도 관리.'),
        ]
        
        for i, (icon_label, ko_name, fg_color, bg_color, desc) in enumerate(statuses):
            row = tk.Frame(content, bg=bg_color, padx=10, pady=6, relief='groove', bd=1)
            row.pack(fill='x', pady=3)
            
            tk.Label(row, text=icon_label, font=('맑은 고딕', 13, 'bold'),
                     bg=bg_color, fg=fg_color, width=18, anchor='w').pack(side='left')
            tk.Label(row, text=f"({ko_name})", font=('맑은 고딕', 11),
                     bg=bg_color, fg=_sec, width=8).pack(side='left')
            tk.Label(row, text=desc, font=('맑은 고딕', 10),
                     bg=bg_color, fg=_pri, anchor='w', wraplength=300).pack(side='left', padx=(10, 0))
        
        # 닫기 버튼
        tk.Button(guide, text="닫기", command=guide.destroy,
                  font=('맑은 고딕', 11), padx=20, pady=5).pack(pady=15)
    
    def _show_backup_guide(self) -> None:
        """v4.1.2: DB 백업/복구 가이드 팝업"""
        from ..utils.constants import tk
        
        guide = create_themed_toplevel(self.parent)
        guide.title("💾 DB 백업/복구 가이드")
        guide.geometry("650x580")
        guide.transient(self.parent)
        guide.grab_set()
        
        tk.Label(guide, text="💾 DB 백업 및 복구 가이드",
                 font=('맑은 고딕', 16, 'bold'), fg=ThemeColors.get('text_primary')).pack(pady=(15, 10))
        
        text = tk.Text(guide, font=('맑은 고딕', 11), wrap='word', padx=15, pady=10)
        text.pack(fill='both', expand=True, padx=10)
        
        content = """📁 DB 파일 위치
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 파일명: data/db/sqm_inventory.db
• 백업폴더: data/db/backups/
• WAL 파일: sqm_inventory.db-wal (함께 백업 필요)

🔧 수동 백업 방법
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 📁 파일 메뉴 → 🔐 백업 → 💾 백업 생성
2. 단축키: Ctrl+B
3. 백업 파일명: SQM_backup_YYYYMMDD_HHMMSS.db

⏰ 자동 백업 설정
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 📁 파일 메뉴 → 🔐 백업 → ⏰ 자동 백업 설정
2. 매 30분/1시간/3시간 간격 선택
3. 프로그램 실행 중 자동으로 백업 생성

🔄 복구 방법
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 📁 파일 메뉴 → 🔐 백업 → 🔄 복원
2. 백업 파일 선택 → 현재 DB를 선택한 백업으로 교체
3. 프로그램 자동 재시작

🌐 공유폴더(서버) 환경
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• DB 파일을 네트워크 공유폴더에 두면 여러 PC에서 접근 가능
• 주의: SQLite는 동시 쓰기에 제한이 있으므로 1명만 쓰기 권장
• WAL 모드 → DELETE 모드 자동 전환 (네트워크 안정성)
• 설정: config.ini에서 db_path를 공유폴더 경로로 변경

⚠️ 주의사항
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• DB 파일 복사 시 .db + .db-wal + .db-shm 3개 파일 모두 복사
• 프로그램 실행 중에는 DB 파일 직접 이동/삭제 금지
• 정기적으로 🔍 DB 검사 실행 권장
"""
        text.insert('1.0', content)
        text.config(state='disabled')
        
        tk.Button(guide, text="닫기", command=guide.destroy,
                  font=('맑은 고딕', 11), padx=20, pady=5).pack(pady=10)
    
    def _show_return_safe(self) -> None:
        """반품 처리 (안전한 호출)"""

        
        if hasattr(self.app, '_show_return_dialog'):
            self.app._show_return_dialog()
        else:
            CustomMessageBox.showinfo(self.parent, "반품", "반품 기능을 사용하려면 EntryPoint 모듈이 필요합니다.")
    
    def _show_doc_convert_safe(self) -> None:
        """v3.8.4: 문서 변환 (안전한 호출)"""
        if hasattr(self.app, '_show_document_convert_dialog'):
            self.app._show_document_convert_dialog()
        else:
            CustomMessageBox.showinfo(self.parent, "문서 변환", "문서 변환 기능이 로드되지 않았습니다.")
    
    def _show_integrity_check_safe(self) -> None:
        """v3.8.4: 데이터 정합성 검사 실행"""
        try:
            from utils.integrity_check import IntegrityChecker
            if hasattr(self.app, 'engine') and hasattr(self.app.engine, 'db'):
                checker = IntegrityChecker(self.app.engine.db)
                report = checker.run_all()
                text = checker.print_report(report)
                saved = checker.save_report(report)
                
                # 결과 표시
                from ..utils.constants import tk
                result_win = create_themed_toplevel(self.parent)
                result_win.title("🩺 데이터 정합성 검사 결과")
                result_win.geometry("650x500")
                
                txt = tk.Text(result_win, wrap='word', font=('Consolas', 10))
                txt.pack(fill='both', expand=True, padx=10, pady=10)
                txt.insert('1.0', text)
                txt.config(state='disabled')
                
                CustomMessageBox.showinfo(self.parent, "검사 완료",
                    f"정합성 점수: {report.score}/100\n"
                    f"리포트 저장: {saved}")
            else:
                CustomMessageBox.showwarning(self.parent, "검사 불가", "DB 엔진이 초기화되지 않았습니다.")
        except (ImportError, ModuleNotFoundError) as e:
            CustomMessageBox.showerror(self.parent, "검사 오류", f"정합성 검사 오류:\n{e}")
    
    def _update_recent_files(self) -> None:
        """최근 파일 메뉴 업데이트"""
        if hasattr(self.app, '_update_recent_files_menu'):
            # 기존 메서드가 recent_menu를 사용하므로 참조 설정
            self.app.recent_menu = self.recent_menu
            self.app._update_recent_files_menu()
    
    def get_recent_menu(self) -> 'tk.Menu':
        """최근 파일 메뉴 반환"""
        return self.recent_menu


class CustomMenuBarMixin:
    """
    커스텀 메뉴바 Mixin
    
    MenuMixin 대신 사용
    """
    
    def _setup_custom_menu(self) -> None:
        """커스텀 메뉴바 설정"""
        try:
            self.custom_menubar = CustomMenuBar(self.root, self)
            self.recent_menu = self.custom_menubar.get_recent_menu()
            logger.info("커스텀 메뉴바 초기화 완료")
        except (AttributeError, RuntimeError) as e:
            logger.error(f"커스텀 메뉴바 초기화 실패: {e}")
            # 폴백: 기존 메뉴 사용
            self._setup_menu_fallback()
    
    def _setup_menu_fallback(self) -> None:
        """폴백: 기존 tk.Menu 사용"""
        from ..utils.constants import tk
        
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 최소한의 메뉴만 생성
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="파일", menu=file_menu)
        file_menu.add_command(label="입고", command=self._on_pdf_inbound)
        file_menu.add_command(label="출고 Allocation", command=self._on_allocation_input_unified)
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self.root.quit)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도움말", menu=help_menu)
        help_menu.add_command(label="정보", command=self._show_about)