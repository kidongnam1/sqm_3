# -*- coding: utf-8 -*-
"""
SQM Inventory - Theme Mixin
===========================

v3.6.0 - UI 통일성 적용
- 다이얼로그 크기 표준화
- 간격 표준화
- 중앙 배치
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import os
import json
import logging
from ..utils.ui_constants import CustomMessageBox
from pathlib import Path

logger = logging.getLogger(__name__)


class ThemeMixin:
    """
    Theme management mixin
    
    Mixed into SQMInventoryApp class
    """
    
    # Available themes
    LIGHT_THEMES = ['cosmo', 'litera', 'minty', 'lumen', 'sandstone', 'yeti', 'pulse', 'united', 'morph', 'journal', 'simplex', 'cerculean']
    DARK_THEMES = ['darkly', 'cyborg', 'superhero', 'solar', 'vapor']
    

    def _load_theme_preference(self) -> str:
        """Load theme preference (RUBI: 단일 다크 기본 + 숨김 오버라이드)

        우선순위:
          1) 환경변수 SQM_THEME (숨김)
          2) setting.ini [UI] theme (숨김/관리자)
          3) theme_preference.json (레거시 호환)
          4) 기본값: cosmo (밝은 테마, v8.1.5)
        """
        # 1) ENV override (hidden switch)
        try:
            env_theme = (os.environ.get("SQM_THEME", "") or "").strip()
            if env_theme:
                return env_theme
        except Exception:
            logger.debug("[THEME-FAIL] file=exception in theme_mixin.py reason=theme_apply_error")  # noqa

        # 2) setting.ini override (hidden/admin)
        try:
            import configparser
            ini = configparser.ConfigParser()
            ini_path = Path(__file__).parent.parent.parent / "setting.ini"
            if ini_path.exists():
                ini.read(str(ini_path), encoding="utf-8")
                ini_theme = (ini.get("UI", "theme", fallback="") or "").strip()
                if ini_theme:
                    return ini_theme
        except Exception:
            logger.debug("[THEME-FAIL] file=exception in theme_mixin.py reason=theme_apply_error")  # noqa

        # 3) legacy preference file
        try:
            pref_file = Path(__file__).parent.parent.parent / "theme_preference.json"
            if pref_file.exists():
                with open(pref_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    legacy = (data.get('theme', '') or '').strip()
                    if legacy:
                        return legacy
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Load theme preference error: {e}")

        # 4) default: v8.5.6 darkly (dark professional) theme
        return 'darkly'

    
    def _save_theme_preference(self, theme_name: str) -> None:
        """Save theme preference to file"""
        try:
            pref_file = Path(__file__).parent.parent.parent / "theme_preference.json"
            
            with open(pref_file, 'w', encoding='utf-8') as f:
                json.dump({'theme': theme_name}, f)
            
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Save theme preference error: {e}")
    
    def _change_theme(self, theme_name: str) -> None:
        """Change application theme — 근본 해결: 전역 스타일·메뉴바·트리 일괄 갱신"""
        from ..utils.constants import HAS_TTKBOOTSTRAP
        
        if not HAS_TTKBOOTSTRAP:
            CustomMessageBox.showinfo(self.root, "Info", "Theme change requires ttkbootstrap")
            return
        
        try:
            if hasattr(self.root, 'style'):
                try:
                    self.root.style.theme_use(theme_name)
                    from ..utils.ui_constants import set_global_theme as _sgt_tm
                    _sgt_tm(theme_name)  # v9.0: 전역 동기화 / v8.2.4: import 수정
                except Exception as _te:
                    # Python 3.14 + ttkbootstrap: Duplicate element 등 무시
                    logger.debug(f"theme_use 무시 (호환성): {_te}")
            
            self.current_theme = theme_name
            self._save_theme_preference(theme_name)
            
            # 1) 전역 가독성 스타일 재적용 (Treeview/Notebook 등 글씨·배경 동기화)
            try:
                from ..utils.ui_constants import ReadableStyle, apply_contrast_scrollbar_style, ThemeColors
                ReadableStyle.apply(self.root, theme_name)
                apply_contrast_scrollbar_style(self.root, theme_name)

                # [v6.3.3] 루트 배경 강제 (안전장치)
                is_dark = ThemeColors.is_dark_theme(theme_name)
                bg_color = ThemeColors.get('bg_primary', is_dark)
                try:
                    self.root.configure(background=bg_color)
                except Exception:
                    logger.debug("[THEME-FAIL] file=exception in theme_mixin.py reason=theme_apply_error")  # noqa

            except (ImportError, Exception) as e:
                logger.debug(f"ReadableStyle 재적용 무시: {e}")
            
            # 2) v8.0.5 NAVY-ORANGE: 테마 전환 시 즉시 적용 (깜빡임 방지)
            try:
                from fixes.global_tree_style import apply_global_tree_style
                from fixes.theme_colorful_override import apply_colorful_overrides
                is_dark_now = ThemeColors.is_dark_theme(theme_name)
                apply_global_tree_style(self.root, is_dark_now)
                apply_colorful_overrides(self)
            except Exception as _nc:
                logger.debug(f"navy-orange 즉시 적용 무시: {_nc}")

            # 트리뷰 태그·그리드 스타일 + 메뉴바 색상 갱신
            self._update_theme_colors()

            # v9.1: tc() 기반 tk 위젯 전체 색상 갱신 (하드코딩 색상 덮어씀)
            try:
                from ..utils.theme_refresh import apply_tc_theme_to_all
                apply_tc_theme_to_all(self)
            except Exception as _tc_e:
                logger.debug(f"apply_tc_theme_to_all 무시: {_tc_e}")
            # 메인 노트북 하단 중복 탭줄 재발 방지
            try:
                if hasattr(self, '_enforce_main_notebook_hidden_tabs'):
                    self._enforce_main_notebook_hidden_tabs()
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"메인 노트북 숨김 재적용 무시: {_e}")
            
            # 3) 메뉴바가 테마 색상 캐시를 쓰면 재적용 (글씨/배경 동기화)
            try:
                if hasattr(self, 'custom_menubar') and getattr(self.custom_menubar, 'refresh_theme_colors', None):
                    self.custom_menubar.refresh_theme_colors()
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"메뉴바 테마 갱신 무시: {_e}")
            
            # 4) 재고·톤백 트리 리프레시로 화면에 새 색상 반영
            try:
                self._safe_refresh()
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"탭 리프레시 무시: {_e}")

            # v8.6.4: 테마 전환 시 대시보드 카드 색상 즉시 동기화
            try:
                if hasattr(self, '_refresh_dashboard'):
                    self.root.after(200, self._refresh_dashboard)
                elif hasattr(self, '_refresh_dashboard_cards'):
                    self.root.after(200, self._refresh_dashboard_cards)
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"대시보드 색상 동기화 무시: {_e}")
            
            # v6.1.1: 50ms 후 2차 적용 (간헐적 타이밍 이슈 보험)
            try:
                self.root.update_idletasks()
                self.root.after(50, self._update_theme_colors)
                if hasattr(self, '_enforce_main_notebook_hidden_tabs'):
                    self.root.after(60, self._enforce_main_notebook_hidden_tabs)
            except Exception as _e:
                logger.debug(f"2차 적용 무시: {_e}")
            
            self._log(f"Theme changed: {theme_name}")

            # v7.3.0: 툴바 빠른 버튼 색상 동기화
            try:
                if hasattr(self, '_refresh_toolbar_colors'):
                    self._refresh_toolbar_colors()
            except (ValueError, TypeError, AttributeError) as _e:
                logger.debug(f"toolbar color sync 무시: {_e}")
            
            # v8.6.4: 모든 테마 리프레시 완료 후 컬러풀 UI 최종 복원
            def _final_colorful_restore():
                try:
                    # 메뉴바 컬러 복원
                    for btn in getattr(self, '_all_menu_btns', []):
                        _mc = getattr(btn, '_menu_color', None)
                        if _mc:
                            btn.config(fg=_mc)
                    # 사이드바 아이콘 컬러 복원
                    _TAB_CLR = {
                        'inventory':'#4ade80','allocation':'#facc15',
                        'picked':'#a78bfa','sold':'#38bdf8',
                        'return_tab':'#f87171','move':'#22d3ee',
                        'dashboard':'#00e676','log':'#94a3b8','scan':'#fb923c',
                    }
                    for k, w in getattr(self, '_sidebar_wrappers', {}).items():
                        if not getattr(w, '_active', False) and hasattr(w, '_icon'):
                            w._icon.config(fg=_TAB_CLR.get(k, '#94a3b8'))
                    # v8.7.0 [FIX G-1.4]: '_reapply_dashboard_card_colors' 메서드 부재 → 첫 분기 항상 실패.
                    #   실제 동작은 else 분기(카드 딕셔너리 순회)에서 수행 중이었음. 첫 분기 제거.
                    # 카드 색상 복원
                    if hasattr(self, '_dashboard_cards'):
                        for _c in self._dashboard_cards.values():
                            _clr = getattr(_c, 'color', '#fff')
                            if hasattr(_c, 'value_label'):
                                _c.value_label.config(fg=_clr)
                            if hasattr(_c, 'title_label'):
                                _c.title_label.config(fg=_clr)
                except Exception as _fe:
                    logger.debug(f"[v8.6.4] 컬러 복원 무시: {_fe}")
            self.root.after(500, _final_colorful_restore)
            self.root.after(1500, _final_colorful_restore)

        except Exception as e:
            logger.debug(f"Theme change non-critical: {e}")

    def _update_theme_colors(self) -> None:
        """v6.1.1: 테마 변경 시 전체 위젯 자동 스캔 + 일괄 갱신 (실패 시 fallback)"""
        try:
            from ..utils.theme_refresh import refresh_all_widgets_for_theme
            stats = refresh_all_widgets_for_theme(self)
            logger.debug(f"[v6.2.3] _update_theme_colors: {stats}")
        except (ImportError, Exception) as e:
            logger.debug(f"theme_refresh 실패, fallback 사용: {e}")
            self._update_theme_colors_fallback()

    def _update_theme_colors_fallback(self) -> None:
        """v6.1.1: theme_refresh 사용 불가 시 기존 방식으로 최소 갱신"""
        from ..utils.ui_constants import ThemeColors
        from tkinter import ttk as _ttk_mod

        is_dark = ThemeColors.is_dark_theme(self.current_theme)
        p = ThemeColors.get_palette(is_dark)
        fg = p['text_primary']
        bg = p['bg_card']
        bg_sec = p['bg_secondary']
        try:
            _st = _ttk_mod.Style()
            for sn in ('Treeview', 'Inv.Treeview', 'Tb.Treeview', 'Cargo.Treeview'):
                try:
                    _st.configure(sn, foreground=fg, background=bg, fieldbackground=bg)
                    _st.map(sn, foreground=[('selected', p['tree_select_fg']), ('!selected', fg)], background=[('selected', p['tree_select_bg'])])
                    # 재고 탭 Inv.Treeview: 본문과 동일 bg_card — 헤더/데이터 영역 배경 통일 (v8.1.4 flat 유지)
                    if sn == 'Inv.Treeview':
                        _st.configure(
                            f"{sn}.Heading",
                            foreground=fg, background=bg, relief='flat', borderwidth=0,
                            anchor='center',
                        )
                    else:
                        _st.configure(
                            f"{sn}.Heading",
                            foreground=fg, background=bg_sec, anchor='center',
                        )
                except Exception as _te:
                    logger.debug(f"[테마] Treeview 스타일 적용 실패 ({sn}): {_te}")
        except Exception as _e:
            logger.debug(f"fallback 전역 스타일 갱신 무시: {_e}")

        if hasattr(self, 'tree_inventory'):
            ThemeColors.configure_tags(self.tree_inventory, is_dark)
            try:
                from ..utils.table_styler import TableStyler
                TableStyler.update_grid_style_for_theme(self.tree_inventory, is_dark)
            except (ImportError, Exception):
                logger.debug("[THEME-FAIL] file=exception in theme_mixin.py reason=theme_apply_error")  # noqa
        if hasattr(self, 'tree_sublot'):
            ThemeColors.configure_tags(self.tree_sublot, is_dark)
            try:
                from ..utils.table_styler import TableStyler
                TableStyler.update_grid_style_for_theme(self.tree_sublot, is_dark)
            except (ImportError, Exception):
                logger.debug("[THEME-FAIL] file=exception in theme_mixin.py reason=theme_apply_error")  # noqa
        try:
            if hasattr(self, '_refresh_toolbar_theme'):
                self._refresh_toolbar_theme()
        except (ValueError, TypeError, AttributeError):
            logger.debug("[THEME-FAIL] file=exception in theme_mixin.py reason=theme_apply_error")  # noqa
    
    def _show_theme_selector(self) -> None:
        """Show theme selection dialog"""
        from ..utils.constants import tk, ttk, HAS_TTKBOOTSTRAP, BOTH, X, LEFT, RIGHT, END
        from ..utils.ui_constants import Spacing, FontScale, center_dialog, setup_dialog_geometry_persistence
        
        if not HAS_TTKBOOTSTRAP:

            CustomMessageBox.showinfo(self.root, "Info", "Theme selection requires ttkbootstrap")
            return
        
        # === UI 통일성: 폰트 스케일 ===
        try:
            dpi = self.root.winfo_fpixels('1i')
        except (ImportError, ModuleNotFoundError):
            dpi = 96
        fonts = FontScale(dpi)
        
        # === UI 통일성: 다이얼로그 크기 표준화 (medium) ===
        dialog = create_themed_toplevel(self.root)
        dialog.title("Select Theme")
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "theme_select_dialog", self.root, "medium")
        
        # === UI 통일성: 간격 표준화 ===
        # Current theme
        ttk.Label(dialog, text=f"Current: {self.current_theme}",
                  font=fonts.heading(bold=True)).pack(pady=Spacing.SM)
        
        # Notebook for light/dark themes
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=BOTH, expand=True, padx=Spacing.SM, pady=Spacing.XS)
        
        # Light themes tab
        light_frame = ttk.Frame(notebook, padding=Spacing.XS)
        notebook.add(light_frame, text="Light Themes")
        
        light_listbox = tk.Listbox(light_frame, height=15, font=fonts.body())
        light_listbox.pack(fill=BOTH, expand=True, padx=Spacing.XS, pady=Spacing.XS)
        
        for theme in self.LIGHT_THEMES:
            light_listbox.insert(END, theme)
            if theme == self.current_theme:
                light_listbox.selection_set(light_listbox.size() - 1)
        
        # Dark themes tab
        dark_frame = ttk.Frame(notebook, padding=Spacing.XS)
        notebook.add(dark_frame, text="Dark Themes")
        
        dark_listbox = tk.Listbox(dark_frame, height=15, font=fonts.body())
        dark_listbox.pack(fill=BOTH, expand=True, padx=Spacing.XS, pady=Spacing.XS)
        
        for theme in self.DARK_THEMES:
            dark_listbox.insert(END, theme)
            if theme == self.current_theme:
                dark_listbox.selection_set(dark_listbox.size() - 1)
        
        # Preview function
        def preview_theme(event=None):
            # Get selected theme
            current_tab = notebook.index(notebook.select())
            
            if current_tab == 0:  # Light
                selection = light_listbox.curselection()
                if selection:
                    theme = light_listbox.get(selection[0])
                    self._change_theme(theme)
            else:  # Dark
                selection = dark_listbox.curselection()
                if selection:
                    theme = dark_listbox.get(selection[0])
                    self._change_theme(theme)
        
        light_listbox.bind('<<ListboxSelect>>', preview_theme)
        dark_listbox.bind('<<ListboxSelect>>', preview_theme)
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=X, padx=Spacing.SM, pady=Spacing.SM)
        
        ttk.Button(btn_frame, text="Apply", command=dialog.destroy, width=10).pack(
            side=RIGHT, padx=Spacing.XS
        )
        ttk.Button(btn_frame, text="Reset to Default", width=15,
                   command=lambda: self._change_theme('darkly')).pack(side=LEFT, padx=Spacing.XS)
        
        # === UI 통일성: 중앙 배치 ===
        center_dialog(dialog, self.root)
        
        # ESC로 닫기
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def _toggle_dark_mode_theme(self) -> None:
        """Toggle between light and dark mode"""
        if self.current_theme in self.DARK_THEMES:
            # Switch to light
            self._change_theme('litera')
        else:
            # Switch to dark
            self._change_theme('darkly')
