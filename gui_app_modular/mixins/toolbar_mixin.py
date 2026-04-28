# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════
# 🎨 색상 사용 원칙 (v3.8.0 — 절대 준수)
# ══════════════════════════════════════════════════════════════
# ✅ 올바른 방법: tc() 함수 사용 (라이트/다크 자동 전환)
#     from gui_app_modular.utils.ui_constants import tc
#     label.config(fg=tc('text_primary'), bg=tc('bg_primary'))
#     entry.config(fg=tc('text_primary'), bg=tc('bg_entry'))
#     frame.config(bg=tc('bg_secondary'))
#
# ❌ 금지: 하드코딩 색상 사용
#     label.config(fg=tc('text_primary'))         # 다크 배경에서 안 보임
#     label.config(fg=tc('text_primary'))         # 라이트 배경에서 안 보임
#     label.config(bg=tc('bg_primary'))       # 라이트 모드에서 검은 배경
#
# 📋 주요 tc() 키:
#     text_primary   — 일반 텍스트 (라이트: #2c3e50  다크: #FF8C00)
#     text_secondary — 보조 텍스트
#     text_muted     — 비활성 텍스트 (gray 대체)
#     bg_primary     — 기본 배경
#     bg_secondary   — 보조 배경
#     bg_card        — 카드/패널 배경
#     bg_entry       — 입력창 배경
#     success        — 성공 (녹색 계열)
#     warning        — 경고 (주황 계열)
#     danger         — 오류 (빨간 계열)
#     info           — 정보 (파란 계열)
# ══════════════════════════════════════════════════════════════

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
from ..utils.custom_messagebox import CustomMessageBox
"""
SQM v3.8.4 — 통합 메뉴바
=========================
순서: [입고▼] [출고▼] [보고서▼] [🔍검색] │ [파일▼] [설정/도구▼] [도움말▼]
      ← 업무 메뉴 (좌측) →              │  ← 시스템 메뉴 (우측) →
+ 탭 전환 버튼 (균등 배치)
+ 자동 2줄 전환
"""
import sqlite3
import logging
import tkinter as tk
from tkinter import ttk
from ..utils.ui_constants import is_dark, ThemeColors, Spacing, FontScale, FontStyle, get_font_scale, DialogSize, center_dialog, apply_modal_window_options
from utils.ui_debug import log_ui_event, safe_widget_bg  # v5.3.6

logger = logging.getLogger(__name__)

FONT_CANDIDATES = ['NanumSquare', 'NanumSquareRound', '나눔스퀘어', 'Malgun Gothic', '맑은 고딕']


def _pick_font(root) -> str:
    import tkinter.font as tkfont
    available = tkfont.families()
    for f in FONT_CANDIDATES:
        if f in available:
            return f
    return '맑은 고딕'


class ToolbarMixin:
    """v3.8.4: 통합 메뉴바 (ThemeColors 단일 소스, Phase5: 메뉴 헬퍼·미니멀)"""

    def _get_return_doc_review_pending_count(self, days: int = 30) -> int:
        """최근 N일 반품 문서점검 대기건(RETURN_DOC_REVIEW) 개수."""
        try:
            row = self.engine.db.fetchone(
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
            logger.debug(f"반품 문서점검 카운트 조회 오류: {e}")
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

    def _load_toolbar_colors(self) -> None:
        """ThemeColors 단일 소스 — 툴바는 항상 다크 스타일 (Phase2/5)"""
        try:
            import ttkbootstrap as ttk_bs
            sc = ttk_bs.Style().colors
            _dark = True
            self._tb_bg = ThemeColors.get('statusbar_bg', _dark)
            self._tb_sep = ThemeColors.get('border', _dark)
            self._tb_fg_normal = ThemeColors.get('text_secondary', _dark)
            self._tb_fg_active = ThemeColors.get('statusbar_fg', _dark)
            self._tb_fg_hover = ThemeColors.get('text_primary', _dark)
            self._tb_hover_bg = ThemeColors.get('bg_hover', _dark)
            self._tb_underline_color = str(sc.info) if getattr(sc, 'info', None) else ThemeColors.get('info', _dark)
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError):
            _dark = True
            self._tb_bg = ThemeColors.get('statusbar_bg', _dark)
            self._tb_sep = ThemeColors.get('border', _dark)
            self._tb_fg_normal = ThemeColors.get('text_secondary', _dark)
            self._tb_fg_active = ThemeColors.get('statusbar_fg', _dark)
            self._tb_fg_hover = ThemeColors.get('text_primary', _dark)
            self._tb_hover_bg = ThemeColors.get('bg_hover', _dark)
            self._tb_underline_color = ThemeColors.get('info', _dark)

    def _setup_toolbar(self) -> None:
        self._toolbar_font = _pick_font(self.root)
        self._tb_font_scale = get_font_scale() or FontScale()
        logger.info(f"[v3.8.4] 폰트: {self._toolbar_font}")

        # ThemeColors에서 동적 로드
        self._load_toolbar_colors()

        # 컨테이너 서픽스 변수 초기화
        self._container_suffix_var = tk.BooleanVar(value=True)

        self._toolbar_container = tk.Frame(self.root)
        self._toolbar_container.pack(fill='x')

        # Row1: 메뉴 버튼 (Phase3: Spacing 8px 그리드)
        self._row1 = tk.Frame(self._toolbar_container, bg=self._tb_bg, pady=Spacing.XS)
        self._row1.pack(fill='x')
        
        # Row1: 오른쪽 액션(새로고침/버전 배지)
        self._right_actions = tk.Frame(self._row1, bg=self._tb_bg)
        self._right_actions.pack(side='right', padx=Spacing.MD)
        self._build_refresh_button(self._right_actions)
        self._build_quick_theme_buttons(self._right_actions)  # v7.3.0: 🌙☀ 빠른 전환

        # v8.6.4: 버전 배지 → 타이틀바로 이동 (우측 공간 확보)
        # v7.9.9 [SIDEBAR]: Row2 탭버튼 제거 — 사이드바로 이전
        self._row2 = tk.Frame(self._toolbar_container, bg=self._tb_bg, pady=0)
        self._row2.pack(fill='x')
        self._row2_visible = False  # Row2 사용 안 함

        # v8.6.4: 컬러 액션 버튼 바 (v8.3.4 스타일 복원)
        try:
            self._build_action_button_bar()
        except Exception as _ab:
            logger.debug(f"액션 버튼 바 스킵: {_ab}")

        # v3.8.9: 메뉴 버튼 — 왼쪽 정렬, 최대 너비 제한
        self._menu_frame = tk.Frame(self._row1, bg=self._tb_bg)
        self._menu_frame.pack(side='left', fill='x')

        # === 7개 메뉴 버튼 (균등) ===
        self._all_menu_btns = []
        self._all_dropdown_menus = []  # v5.4.1: theme refresh 대상 tk.Menu들
        self._build_all_menus()

        # v7.9.9 [SIDEBAR]: _sec_tabs는 더미 Frame (하위호환 유지)
        self._sec_tabs = tk.Frame(self._row2, bg=self._tb_bg)
        # 탭 버튼은 _build_sidebar_tab_buttons()에서 사이드바에 생성
        # main_app._setup_tabs() 이후 호출됨

        # v3.8.9: overflow 체크 비활성화 (탭은 항상 row2에 고정)
        # self.root.bind('<Configure>', self._check_toolbar_overflow)
        # v7.0: 4단계 탭 순서 — AVAILABLE(0), ALLOCATION(1), PICKED(2), SOLD(3), 대시보드(4), 로그(5)
        # 4개 메인 + 총괄 재고 리스트 + 통계 + 로그
        self._tab_index_map = {'inventory': 0, 'allocation': 1, 'picked': 2, 'sold': 3, 'cargo_overview': 4, 'dashboard': 5, 'log': 6}
        self._active_tab_key = 'inventory'


    def _build_action_button_bar(self) -> None:
        """v8.6.4: v8.3.4 스타일 컬러 버튼 바 — 다크/라이트 자동 대응.

        이미지 2번(v8.3.4) 기준:
          PDF입고(초록) / 즉시출고(파랑) / 반품(회색) /
          재고조회(파랑) / 정합성(청록) / 백업(회색) / 설정(회색)
        """
        from gui_app_modular.utils.ui_constants import tc
        _dk = is_dark()

        # 버튼 바 프레임
        self._action_bar = tk.Frame(
            self._toolbar_container,
            bg=tc('bg_secondary'),
            pady=3, padx=6,
        )
        self._action_bar.pack(fill='x')

        # 버튼 정의: (label, method, bg_key, hover_key)
        BTN_DEFS = [
            ("📄 PDF 입고",   "_on_pdf_inbound",          '#22c55e', '#16a34a'),
            ("🚀 즉시 출고",  "_on_s1_onestop_outbound",  '#3b82f6', '#2563eb'),
            ("🔄 반품",       "_show_return_dialog",       '#64748b', '#475569'),
            ("📊 재고 조회",  "_bulk_import_inventory",    '#0ea5e9', '#0284c7'),
            (None, None, None, None),  # 구분선
            ("🔍 정합성",     "_run_integrity_check",      '#06b6d4', '#0891b2'),
            # v8.7.0 [FIX CRIT-2]: 핸들러명 불일치 수정
            #   _on_backup_db → _on_backup_click (backup_handlers.py:34 실제 존재)
            #   _show_settings_dialog → _show_api_settings (settings_dialog.py:34 실제 존재)
            ("💾 백업",       "_on_backup_click",          '#64748b', '#475569'),
            ("⚙️ 설정",       "_show_api_settings",        '#64748b', '#475569'),
        ]

        for item in BTN_DEFS:
            label, method, bg_color, hover_color = item
            if label is None:
                # 구분선
                sep = tk.Frame(self._action_bar, bg=tc('border'), width=1)
                sep.pack(side='left', fill='y', padx=6, pady=2)
                continue

            btn = tk.Label(
                self._action_bar,
                text=label,
                bg=bg_color,
                fg=tc('text_on_dark'),  # v8.6.4
                font=('맑은 고딕', 10, 'bold'),
                padx=12, pady=4,
                cursor='hand2',
                relief='flat',
            )
            btn.pack(side='left', padx=(0, 3), pady=1)

            # 클릭 바인딩
            btn.bind('<Button-1>',
                     lambda e, m=method: self._safe_call(m))
            # 호버 효과
            btn.bind('<Enter>',
                     lambda e, b=btn, hc=hover_color: b.config(bg=hc))
            btn.bind('<Leave>',
                     lambda e, b=btn, bc=bg_color: b.config(bg=bc))

        # 참조 저장 (테마 갱신용)
        self._action_bar_buttons = [
            c for c in self._action_bar.winfo_children()
            if isinstance(c, tk.Label)
        ]

    def _refresh_action_bar_colors(self) -> None:
        """v8.6.4: 테마 전환 시 액션 버튼 바 배경 갱신."""
        try:
            from gui_app_modular.utils.ui_constants import tc
            if hasattr(self, '_action_bar') and self._action_bar.winfo_exists():
                self._action_bar.config(bg=tc('bg_secondary'))
        except Exception as _e:
            logger.debug(f"action_bar 색상 갱신 스킵: {_e}")

    # ═══════════════════════════════════════════════════════
    # 메뉴 생성 헬퍼 (v3.8.4: 항목 간격 확대)
    # ═══════════════════════════════════════════════════════

    def _create_menu(self, parent=None) -> 'tk.Menu':
        """간격 넓은 팝업 메뉴 생성 (v3.8.4)"""
        # v5.4.1: 드롭다운 메뉴 색상(라이트/다크) 강제 고정 — Windows tk_popup 리셋 방지
        dark_mode = is_dark()
        # D/O 후속 연결 등 하위 메뉴는 배경 대비가 확실한 고대비 색상으로 고정한다.
        menu_bg = '#101827' if dark_mode else '#ffffff'
        menu_fg = '#f8fafc' if dark_mode else '#111827'
        menu_abg = '#2f80ed' if dark_mode else '#0f6ecb'
        menu_afg = '#ffffff'
        menu_dis = '#cbd5e1' if dark_mode else '#334155'
        f = self._toolbar_font
        p = parent or self.root
        _menu_font = self._tb_font_scale.get_font(FontStyle.SUBTITLE)
        m = tk.Menu(p, tearoff=0, font=(f, _menu_font[1]),
                    activeborderwidth=3,
                    borderwidth=3,
                    relief='flat',
                    background=menu_bg, foreground=menu_fg,
                    activebackground=menu_abg, activeforeground=menu_afg,
                    disabledforeground=menu_dis)
        # v5.4.1: 일부 Windows/Tk 조합에서 초기 옵션이 덮이는 케이스 대비
        try:
            m.config(bg=menu_bg, fg=menu_fg, activebackground=menu_abg, activeforeground=menu_afg,
                     disabledforeground=menu_dis)
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")
        return m

    def _add_menu_items(self, menu: 'tk.Menu', items: list) -> None:
        """Phase5: (label, command) 또는 None(구분선) 리스트로 메뉴 일괄 구성"""
        for item in items:
            if item is None:
                menu.add_separator()
            else:
                label, cmd = item[0], item[1]
                menu.add_command(label=f"  {label}" if not str(label).startswith('  ') else label, command=cmd)

    # ═══════════════════════════════════════════════════════
    # 7개 메뉴 버튼 (균등 배치)
    # ═══════════════════════════════════════════════════════

    def _build_all_menus(self) -> None:
        """7개 드롭다운 메뉴 (밑줄 스타일) + 툴팁"""
        from ..utils.menu_tab_tooltips import clip_tooltip as _menu_bar_tip_clip
        # v8.6.4: 메뉴별 컬러
        menus = [
            ('📁 파일 ▼',      self._build_file_menu,
             '파일 메뉴: 데이터베이스 열기/저장/백업, 설정 파일, 최근 파일, 종료 등 파일 관련 기능',
             None),
            ('📥 입고 ▼',      self._build_inbound_menu,
             '입고 메뉴: 원스톱 입고(PDF/엑셀), 로케이션 업로드, 입고 이력 조회 등 입고 처리 기능',
             '#4ade80'),
            ('📤 출고 ▼',      self._build_outbound_menu,
             '출고 메뉴: 선택 출고, 출고 템플릿, 출고 이력, 반품(재입고) 등 출고·반품 관련 기능',
             '#facc15'),
            ('📊 재고 ▼',      self._build_report_menu,
             '재고 메뉴: 재고 현황·통계, 대시보드, LOT/톤백 조회, 엑셀 내보내기 등 재고 조회·보고 기능',
             '#38bdf8'),
            ('📝 보고서 ▼',    self._build_customer_report_menu,
             '보고서 메뉴: 고객별·기간별 보고서, PDF/엑셀 출력 등 보고서 생성·출력 기능',
             '#a78bfa'),
            ('🔧 설정/도구 ▼', self._build_settings_menu,
             '설정/도구 메뉴: API 키·테마 설정, 데이터 검증, 마이그레이션, 개발자 도구 등',
             '#94a3b8'),
            ('❓ 도움말 ▼',    self._build_help_menu,
             '도움말 메뉴: 단축키, 사용 안내, 정보·버전, 로그 보기 등',
             None),
        ]

        for item in menus:
            text = item[0]
            builder = item[1]
            tooltip = item[2] if len(item) > 2 else ""
            menu_color = item[3] if len(item) > 3 else None
            _btn_fg = menu_color or self._tb_fg_normal
            _btn_font = self._tb_font_scale.heading()
            btn = tk.Label(self._menu_frame, text=text,
                          font=_btn_font,
                          bg=self._tb_bg, fg=_btn_fg,
                          anchor='center', justify='center',
                          padx=Spacing.MD, pady=Spacing.SM, cursor='hand2')
            btn._tc_skip = True
            btn._menu_color = menu_color
            btn.pack(side='left', padx=Spacing.MD)

            underline = tk.Frame(btn, height=2, bg=self._tb_underline_color)
            btn._underline = underline
            btn._menu_active = False

            menu = builder()
            try:
                self._all_dropdown_menus.append(menu)
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")
            btn.bind('<Button-1>', lambda e, m=menu, b=btn: self._show_menu(m, b))

            def make_enter(button):
                def on_enter(e):
                    if not button._menu_active:
                        button.config(fg='#ffffff', bg=self._tb_hover_bg)
                return on_enter

            def make_leave(button):
                def on_leave(e):
                    if not button._menu_active:
                        _orig = getattr(button, '_menu_color', None) or self._tb_fg_normal
                        button.config(fg=_orig, bg=self._tb_bg)
                return on_leave

            btn.bind('<Enter>', make_enter(btn))
            btn.bind('<Leave>', make_leave(btn))
            self._all_menu_btns.append(btn)
            if tooltip:
                self._attach_tooltip(btn, _menu_bar_tip_clip(tooltip))

        # v5.7.5: 검색 버튼 UI 제거 (메뉴 끝 검색 버튼 삭제)


    def _build_refresh_button(self, parent) -> None:
        """메인 화면 새로고침 버튼 (F5)"""
        try:
            btn = tk.Label(
                parent, text='🔄 새로고침',
                font=self._tb_font_scale.body(bold=True),
                bg=self._tb_bg, fg=self._tb_fg_normal,
                anchor='center', justify='center',
                padx=Spacing.SM, pady=Spacing.XS, cursor='hand2'
            )
            btn.pack(side='left')
            btn.bind('<Button-1>', lambda e: self._refresh_all_data())
            btn.bind('<Enter>', lambda e: btn.config(fg=self._tb_fg_hover))
            btn.bind('<Leave>', lambda e: btn.config(fg=self._tb_fg_normal))
            self._refresh_btn = btn
            from ..utils.menu_tab_tooltips import clip_tooltip as _rf_tip
            self._attach_tooltip(btn, _rf_tip("전체 탭 새로고침 (F5)"))
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"refresh button: {_e}")

    def _build_quick_theme_buttons(self, parent) -> None:
        """v7.3.0: 🌙 다크 / ☀ 라이트 빠른 전환 버튼 (툴바 우측)"""
        try:
            sep = tk.Label(parent, text=" │ ", bg=self._tb_bg, fg=self._tb_fg_normal,
                           font=self._tb_font_scale.body())
            sep.pack(side='left')

            for icon, label, theme in [("🌙", "Dark", "darkly"), ("☀", "Light", "litera")]:  # v8.6.4 수정
                btn = tk.Label(
                    parent, text=f"{icon} {label}",
                    font=self._tb_font_scale.body(bold=True),
                    bg=self._tb_bg, fg=self._tb_fg_normal,
                    anchor='center', padx=Spacing.XS, pady=Spacing.XS, cursor='hand2'
                )
                btn.pack(side='left', padx=2)
                btn.bind('<Button-1>', lambda e, th=theme: self._change_theme(th))
                btn.bind('<Enter>', lambda e, b=btn: b.config(fg=self._tb_fg_hover))
                btn.bind('<Leave>', lambda e, b=btn: b.config(fg=self._tb_fg_normal))
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"quick theme buttons: {_e}")

    def _refresh_toolbar_colors(self) -> None:
        """v8.6.4: 테마 전환 시 툴바 전체 배경·전경색 동기화"""
        try:
            self._load_toolbar_colors()
            for widget in [self._toolbar_container, self._row1, self._row2,
                           self._right_actions]:
                if widget and widget.winfo_exists():
                    widget.config(bg=self._tb_bg)
            for child in self._row1.winfo_children():
                try:
                    _orig_color = getattr(child, '_menu_color', None)
                    child.config(bg=self._tb_bg, fg=_orig_color or self._tb_fg_normal)
                except (tk.TclError, AttributeError):
                    logger.debug("[SUPPRESSED] exception in toolbar_mixin.py")  # noqa
            # v8.6.4: 액션 버튼 바 배경 갱신
            self._refresh_action_bar_colors()
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"toolbar color refresh: {_e}")

    def _build_inbound_menu(self) -> 'tk.Menu':
        """v6.0.6 3단계: 입고 드롭다운 — menu_registry 기반 (custom_menubar·네이티브 메뉴와 동일 항목)"""
        m = self._create_menu()
        try:
            from ..menu_registry import FILE_MENU_INBOUND_ITEMS, FILE_MENU_INBOUND_RETURN_SUB_ITEMS
            for entry in FILE_MENU_INBOUND_ITEMS:
                if entry is None:
                    m.add_separator()
                    continue
                label, method_name = entry[0], entry[1]
                optional = entry[2] if len(entry) > 2 else False
                if optional and not callable(getattr(self, method_name, None)):
                    continue
                if method_name == "_show_return_dialog":
                    m.add_separator()
                    return_sub = self._create_menu()
                    _show_return = getattr(self, "_show_return_dialog", None)
                    if callable(_show_return):
                        for sub_label, mode in FILE_MENU_INBOUND_RETURN_SUB_ITEMS:
                            return_sub.add_command(label=f"  {sub_label}", command=lambda md=mode: _show_return(md))
                    pending = self._get_return_doc_review_pending_count(30)
                    badge = self._format_return_review_badge(pending)
                    m.add_cascade(label=f"  {label}{badge}", menu=return_sub)
                else:
                    m.add_command(label=f"  {label}", command=lambda mn=method_name: self._safe_call(mn))
        except Exception as _e2:  # v6.4.0: ImportError → Exception
            import logging as _lg2
            _lg2.getLogger(__name__).warning(f"[toolbar] 입고 메뉴 registry 로드 실패 → fallback: {_e2}")
            self._add_menu_items(m, [
                ('📄 PDF 스캔 입고',          lambda: self._safe_call('_on_pdf_inbound')),
                ('📊 엑셀 파일 수동 입고',    lambda: self._safe_call('_bulk_import_inventory_simple')),
                ('📂 반품 입고 (Excel)',       lambda: self._safe_call('_on_return_inbound_upload')),
                ('📦 제품명 테이블 관리',         lambda: self._safe_call('_show_product_master')),  # v6.7.3
                None,
            ])
            return_sub = self._create_menu()
            _show_return = getattr(self, "_show_return_dialog", None)
            if callable(_show_return):
                return_sub.add_command(label="  📝 소량 반품 (1~2건)", command=lambda: _show_return(0))
                return_sub.add_command(label="  📂 다량 반품 (Excel)", command=lambda: _show_return(1))
            pending = self._get_return_doc_review_pending_count(30)
            badge = self._format_return_review_badge(pending)
            m.add_cascade(label=f"  🔄 반품 (재입고){badge}", menu=return_sub)
        return m

    def _build_outbound_menu(self) -> 'tk.Menu':
        """v6.0.2: 출고 드롭다운 — menu_registry 기반
        v6.4.0: except Exception으로 확장 (ImportError 외 오류도 안전 처리)
        """
        m = self._create_menu()
        items = []
        try:
            from ..menu_registry import FILE_MENU_OUTBOUND_ITEMS
            for entry in FILE_MENU_OUTBOUND_ITEMS:
                if entry is None:
                    items.append(None)
                    continue
                label, method_name = entry[0], entry[1]
                optional = entry[2] if len(entry) > 2 else False
                if optional and not callable(getattr(self, method_name, None)):
                    continue
                items.append((label, lambda mn=method_name: self._safe_call(mn)))
            self._add_menu_items(m, items)
        except Exception as _e:  # v6.4.0: ImportError → Exception
            import logging as _lg
            _lg.getLogger(__name__).warning(
                f"[toolbar] 출고 메뉴 registry 로드 실패 → fallback: {_e}"
            )
            self._add_menu_items(m, [
                ('📋 Allocation 입력 (파일 / 붙여넣기)', lambda: self._safe_call('_on_allocation_input_unified')),
                ('📋 Picking List 업로드 (PDF)', lambda: self._safe_call('_on_picking_list_upload')),
                (None, None),
                ('📤 빠른 출고 (붙여넣기)', lambda: self._safe_call('_on_quick_outbound_paste')),
                ('🚀 S1 원스톱 출고', lambda: self._safe_call('_on_s1_onestop_outbound')),
            ])
        return m

    def _build_report_menu(self) -> 'tk.Menu':
        """재고 메뉴 — menu_registry.MENU_STOCK_ITEMS 단일 소스 (v8.1.4)"""
        m = self._create_menu()
        try:
            from ..menu_registry import MENU_STOCK_ITEMS
            for entry in MENU_STOCK_ITEMS:
                if entry is None:
                    m.add_separator()
                    continue
                label = entry[0]
                method_name = entry[1]
                optional = entry[2] if len(entry) > 2 else False
                kwargs = entry[3] if len(entry) > 3 else {}
                if optional and not callable(getattr(self, method_name, None)):
                    continue
                if kwargs:
                    m.add_command(
                        label=f"  {label}",
                        command=lambda mn=method_name, kw=kwargs: getattr(self, mn)(**kw)
                    )
                else:
                    m.add_command(
                        label=f"  {label}",
                        command=lambda mn=method_name: self._safe_call(mn)
                    )
        except Exception as e:
            logger.warning(f"[UI] 재고 메뉴 registry 로드 실패, 폴백: {e}")
            self._add_menu_items(m, [
                ('📊 LOT 리스트 Excel',  lambda: self._on_export_click(option=3)),
                ('🎒 톤백리스트 Excel',  lambda: self._on_export_click(option=4)),
            ])
        return m

    def _build_customer_report_menu(self) -> 'tk.Menu':
        """보고서 메뉴 — menu_registry.MENU_REPORT_ITEMS 단일 소스 (v8.1.4)"""
        m = self._create_menu()
        try:
            from ..menu_registry import MENU_REPORT_ITEMS
            for entry in MENU_REPORT_ITEMS:
                if entry is None:
                    m.add_separator()
                    continue
                label = entry[0]
                method_name = entry[1]
                optional = entry[2] if len(entry) > 2 else False
                if optional and not callable(getattr(self, method_name, None)):
                    continue
                m.add_command(
                    label=f"  {label}",
                    command=lambda mn=method_name: self._safe_call(mn)
                )
        except Exception as e:
            logger.warning(f"[UI] 보고서 메뉴 registry 로드 실패, 폴백: {e}")
            self._add_menu_items(m, [
                ('📄 거래명세서 생성', lambda: self._safe_call('_generate_outbound_invoice')),
            ])
        return m

    def _build_file_menu(self) -> 'tk.Menu':
        m = self._create_menu()
        from ..menu_registry import FILE_MENU_EXPORT_ITEMS, FILE_MENU_BACKUP_ITEMS
        exp = self._create_menu(m)
        for label, option in FILE_MENU_EXPORT_ITEMS:
            exp.add_command(label=f"  {label}", command=lambda op=option: self._on_export_click(option=op))
        m.add_cascade(label="  💾 내보내기", menu=exp)
        m.add_separator()
        bak = self._create_menu(m)
        for label, method_name in FILE_MENU_BACKUP_ITEMS:
            bak.add_command(label=f"  {label}", command=lambda mn=method_name: self._safe_call(mn))
        bak.add_command(label="  ⏰ 자동 백업 설정", command=lambda: self._safe_call('_show_auto_backup_settings'))
        m.add_cascade(label="  🔐 백업", menu=bak)
        m.add_separator()
        # v5.5.3: Gemini API (설정/도구에서 이동)
        # v6.4.0: BL 선사 도구 서브메뉴
        try:
            from ..menu_registry import FILE_MENU_AI_TOOLS_ITEMS as _ai_items
            _bl_sub = self._create_menu(m)
            for _entry in _ai_items:
                if _entry is None:
                    _bl_sub.add_separator()
                    continue
                _lbl, _mth = _entry[0], _entry[1]
                _bl_sub.add_command(
                    label=f"  {_lbl}",
                    command=lambda mn=_mth: self._safe_call(mn)
                )
            m.add_cascade(label="  🚢 BL 선사 도구", menu=_bl_sub)
            m.add_separator()
        except Exception as e:
            logger.warning(f"[UI] BL 선사 도구 메뉴 생성 실패: {e}")
        try:
            from ..utils.constants import HAS_GEMINI
            if HAS_GEMINI:
                if not hasattr(self, '_gemini_var'):
                    self._gemini_var = tk.BooleanVar(value=getattr(self, 'use_gemini', False))
                api_sub = self._create_menu(m)
                api_sub.add_checkbutton(
                    label="  API 사용",
                    variable=self._gemini_var,
                    command=lambda: self._safe_call('_toggle_gemini')
                )
                api_sub.add_separator()
                api_sub.add_command(label="  💬 AI 채팅", command=lambda: self._safe_call('_open_ai_chat'))
                api_sub.add_command(label="  ⚙️ API 설정", command=lambda: self._safe_call('_show_api_settings'))
                api_sub.add_command(label="  🔬 API 테스트", command=lambda: self._safe_call('_test_gemini_api_connection'))
                m.add_cascade(label="  🤖 Gemini AI", menu=api_sub)
            else:
                api_sub = self._create_menu(m)
                api_sub.add_command(label="  ⚙️ API 설정", command=lambda: self._safe_call('_show_api_settings'))
                api_sub.add_command(label="  🔬 API 테스트", command=lambda: self._safe_call('_test_gemini_api_connection'))
                m.add_cascade(label="  🤖 Gemini AI", menu=api_sub)
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"toolbar_mixin: Gemini 메뉴 추가 스킵: {_e}")
        # v5.5.3: PDF 변환 (설정/도구에서 이동)
        pdf_sub = self._create_menu(m)
        pdf_sub.add_command(label="  → Excel", command=lambda: self._safe_call('_convert_pdf_to_excel'))
        pdf_sub.add_command(label="  → Word", command=lambda: self._safe_call('_convert_pdf_to_word'))
        pdf_sub.add_separator()
        pdf_sub.add_command(label="  📁 일괄 변환", command=lambda: self._safe_call('_batch_convert_pdf_excel'))
        pdf_sub.add_command(label="  🔍 분석", command=lambda: self._safe_call('_analyze_pdf'))
        m.add_cascade(label="  📄 PDF/이미지 변환", menu=pdf_sub)
        m.add_separator()
        m.add_command(label="  ❌ 종료", command=self.root.quit)
        return m

    def _build_settings_menu(self) -> 'tk.Menu':
        m = self._create_menu()
        # 화면
        m.add_command(label="━━ 🖥️ 화면 ━━", state='disabled', font=self._tb_font_scale.heading())
        m.add_command(label="  🔄 새로고침 (F5)", command=self._refresh_all_data)
        m.add_separator()
        # v7.9.9 [창 크기]: 저장 / 초기화
        m.add_command(label="  💾 현재 창 크기 저장",
                      command=self._on_save_window_size)
        m.add_command(label="  ↩️  기본 창 크기로 초기화 (1500×900)",
                      command=self._on_reset_window_size)
        m.add_separator()
        # 테마
        theme = self._create_menu(m)
        theme.add_command(label="━━ ☀️ Light ━━", state='disabled', font=self._tb_font_scale.heading())
        for t in ['darkly', 'cosmo', 'litera', 'minty', 'journal', 'yeti', 'morph']:
            theme.add_command(label=f"  ☀️ {t.capitalize()}", command=lambda th=t: self._change_theme(th))
        theme.add_separator()
        theme.add_command(label="━━ 🌙 Dark ━━", state='disabled', font=self._tb_font_scale.heading())
        for t in ['darkly', 'cyborg', 'superhero', 'solar', 'vapor']:
            theme.add_command(label=f"  🌙 {t.capitalize()}", command=lambda th=t: self._change_theme(th))
        m.add_cascade(label="  🎨 테마 선택", menu=theme)
        # 글꼴 크기
        fsize = self._create_menu(m)
        fsize.add_command(label="  작게 (11pt)", command=lambda: self._change_font_size(11))
        fsize.add_command(label="  보통 (13pt)", command=lambda: self._change_font_size(13))
        fsize.add_command(label="  크게 (16pt)", command=lambda: self._change_font_size(16))
        m.add_cascade(label="  🔤 글꼴 크기", menu=fsize)
        m.add_separator()
        # 도구
        m.add_command(label="━━ 🔧 도구 ━━", state='disabled', font=self._tb_font_scale.heading())
        if not hasattr(self, '_dev_mode_var'):
            _dev_on = self._is_developer_mode_enabled() if hasattr(self, '_is_developer_mode_enabled') else False
            self._dev_mode_var = tk.BooleanVar(value=_dev_on)
        m.add_checkbutton(
            label="  🧪 개발자 모드",
            variable=self._dev_mode_var,
            command=self._on_toggle_developer_mode
        )
        # v5.9.0: 컨테이너 구분 옵션은 필터바 초기화 옆으로 이동
        # v3.8.4: 대시보드 자동 갱신
        if not hasattr(self, '_auto_refresh_var'):
            self._auto_refresh_var = tk.BooleanVar(value=False)
        m.add_checkbutton(
            label="  🔄 대시보드 자동 갱신 (30초)",
            variable=self._auto_refresh_var,
            command=self._on_auto_refresh_toggle
        )
        # v3.8.4: 정합성 검사
        m.add_command(
            label="  🔍 정합성 검사/복구",
            command=self._on_integrity_check
        )
        m.add_command(
            label="  🧪 운영 DB 스키마 점검(1회)",
            command=self._on_operational_schema_check_once
        )
        if hasattr(self, "_show_lot_allocation_audit_dialog"):
            m.add_command(
                label="  📊 LOT Allocation·톤백 현황",
                command=self._show_lot_allocation_audit_dialog,
            )
        # v5.5.3: Gemini API → 📁 파일 메뉴로 이동
        m.add_separator()
        # v5.5.3: PDF 변환 → 📁 파일 메뉴로 이동
        m.add_command(label="  🩺 데이터 정합성 검사", command=lambda: self._safe_call('_run_integrity_check'))
        m.add_separator()
        if hasattr(self, '_is_developer_mode_enabled') and self._is_developer_mode_enabled():
            m.add_command(label="  🗑️ 테스트 DB 초기화 (데이터 삭제)", command=lambda: self._safe_call('_show_test_db_reset_popup'))
        return m


    def _on_save_window_size(self) -> None:
        """v7.9.9: 현재 창 크기/위치를 window_config.json에 즉시 저장."""
        try:
            if hasattr(self, '_save_window_config'):
                self._save_window_config()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            from .custom_messagebox import CustomMessageBox
            CustomMessageBox.showinfo(
                self.root, "창 크기 저장",
                f"✅ 현재 창 크기가 저장되었습니다.\n\n크기: {w} × {h} px"
            )
        except Exception as _e:
            logger.debug(f"[창 크기 저장] {_e}")

    def _on_reset_window_size(self) -> None:
        """v7.9.9: 창 크기를 기본값 1500×900으로 초기화."""
        try:
            self.root.geometry("1500x900")
            # 화면 중앙 배치
            self.root.update_idletasks()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = (sw - 1500) // 2
            y = (sh - 900) // 2
            self.root.geometry(f"1500x900+{x}+{y}")
            if hasattr(self, '_save_window_config'):
                self._save_window_config()
            from .custom_messagebox import CustomMessageBox
            CustomMessageBox.showinfo(
                self.root, "창 크기 초기화",
                "✅ 창 크기가 기본값(1500×900)으로 초기화되었습니다.\n화면 중앙에 배치되었습니다."
            )
        except Exception as _e:
            logger.debug(f"[창 크기 초기화] {_e}")

    def _on_toggle_developer_mode(self) -> None:
        enabled = bool(getattr(self, '_dev_mode_var', None) and self._dev_mode_var.get())
        ok = self._set_developer_mode_enabled(enabled) if hasattr(self, '_set_developer_mode_enabled') else False
        if not ok:
            CustomMessageBox.showerror(self.root, "개발자 모드", "설정을 저장하지 못했습니다.")
            return
        state_txt = "ON" if enabled else "OFF"
        self._log(f"개발자 모드 변경: {state_txt}")
        CustomMessageBox.showinfo(
            self.root,
            "개발자 모드",
            f"개발자 모드가 {state_txt}로 저장되었습니다.\n메뉴 반영을 위해 앱을 다시 열어주세요."
        )

    def _build_help_menu(self) -> 'tk.Menu':
        """도움말 메뉴 — menu_registry.MENU_HELP_ITEMS 단일 소스 (v8.1.4)"""
        m = self._create_menu()
        try:
            from ..menu_registry import MENU_HELP_ITEMS
            for entry in MENU_HELP_ITEMS:
                if entry is None:
                    m.add_separator()
                    continue
                label = entry[0]
                method_name = entry[1]
                optional = entry[2] if len(entry) > 2 else False
                if optional and not callable(getattr(self, method_name, None)):
                    continue
                # 버전 정보에 현재 버전 추가
                display_label = label
                if method_name == '_show_about':
                    try:
                        from version import __version__
                        display_label = f"{label} (v{__version__})"
                    except ImportError:
                        pass
                m.add_command(
                    label=f"  {display_label}",
                    command=lambda mn=method_name: self._safe_call(mn)
                )
        except Exception as e:
            logger.warning(f"[UI] 도움말 메뉴 registry 로드 실패, 폴백: {e}")
            self._add_menu_items(m, [
                ('📖 사용법', lambda: self._safe_call('_show_help')),
                ('📝 버전 정보', lambda: self._safe_call('_show_about')),
            ])
        return m

    # ═══════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════
    # v7.9.9 [SIDEBAR] 탭 버튼 — 왼쪽 사이드바
    # ═══════════════════════════════════════════════════════

    def _build_sidebar_tab_buttons(self) -> None:
        """v7.9.9 [SIDEBAR]: 아이콘 + 텍스트 표시, 메뉴 간격 확대."""
        sidebar = getattr(self, '_sidebar_frame', None)
        if not sidebar:
            self._build_tab_buttons()
            return

        SIDEBAR_BG  = tc('bg_secondary')
        ACTIVE_BG   = tc('bg_secondary')
        HOVER_BG    = tc('bg_secondary')
        ICON_FG     = tc('text_muted')
        ACTIVE_FG   = tc('text_primary')
        ACTIVE_BAR  = tc('border_focus')
        TEXT_FG     = tc('text_muted')
        TEXT_ACTIVE = tc('text_primary')

        # v8.6.4: 사이드바 탭별 컬러
        TAB_COLORS = {
            'inventory':  '#4ade80', 'allocation': '#facc15',
            'picked':     '#a78bfa', 'sold':       '#38bdf8',
            'return_tab': '#f87171', 'move':       '#22d3ee',
            'dashboard':  '#00e676', 'log':        '#94a3b8',
            'scan':       '#fb923c',
        }

        tab_defs = [
            ('inventory',   '📦', 'Inventory',
             'Full LOT list. Filter · search · double-click for detail.'),
            ('allocation',  '📋', 'Allocation',
             'Reserved LOTs. View all allocation assignments.'),
            ('picked',      '🚛', 'Picked',
             'Picked LOTs awaiting outbound confirmation.'),
            ('sold',        '📤', 'Outbound',
             'Confirmed outbound LOTs (OUTBOUND status).'),
            ('return_tab',  '🔄', 'Return',
             'Return & re-inbound management.'),
            ('move',        '🔀', 'Move',
             'Tonbag location move & transfer management.'),
            # v8.4.1 [K]: 사이드바 추가 — 기존 메뉴 전용 탭
            ('dashboard',   '📊', 'Dashboard',
             'KPI cards, integrity signal, product summary.'),
            ('log',         '📝', 'Log',
             'Operation log & audit trail.'),
            ('scan',        '📷', 'Scan',
             'Barcode scan history & real-time tracking.'),
        ]

        import tkinter as _tk
        self._tab_buttons      = {}
        self._sidebar_wrappers = {}
        self._sidebar_labels   = {}

        # 상단 여백
        _tk.Frame(sidebar, bg=SIDEBAR_BG, height=10).pack(fill='x')

        from ..utils.menu_tab_tooltips import clip_tooltip as _tip_clip

        for key, icon, label, tip in tab_defs:
            # v8.4.1 [K]: Dashboard 앞에 구분선 삽입
            if key == 'dashboard':
                _sep = _tk.Frame(sidebar, bg=SIDEBAR_BG, height=2)
                _sep.pack(fill='x', padx=10, pady=4)
                _tk.Frame(_sep, bg=tc('border'), height=1).pack(fill='x')

            # 외부 wrapper
            wrapper = _tk.Frame(sidebar, bg=SIDEBAR_BG, cursor='hand2')
            wrapper.pack(fill='x', pady=8)

            # 왼쪽 활성 인디케이터 바
            bar = _tk.Frame(wrapper, width=3, bg=SIDEBAR_BG)
            bar.pack(side='left', fill='y')
            wrapper._bar = bar

            # 내부 컨테이너 (아이콘+텍스트 수직 배치)
            inner = _tk.Frame(wrapper, bg=SIDEBAR_BG, cursor='hand2')
            inner.pack(side='left', fill='x', expand=True, padx=4, pady=6)

            # 아이콘
            _tab_color = TAB_COLORS.get(key, ICON_FG)
            icon_lbl = _tk.Label(inner, text=icon,
                                 font=('Segoe UI Emoji', 18),
                                 bg=SIDEBAR_BG, fg=_tab_color,
                                 cursor='hand2')
            icon_lbl._tc_skip = True
            icon_lbl.pack()

            text_lbl = _tk.Label(inner, text=label,
                                 font=('맑은 고딕', 10),
                                 bg=SIDEBAR_BG, fg=TEXT_FG,
                                 justify='center', cursor='hand2')
            text_lbl._tc_skip = True
            text_lbl.pack()

            wrapper._icon   = icon_lbl
            wrapper._text   = text_lbl
            wrapper._inner  = inner
            wrapper._bg     = SIDEBAR_BG
            wrapper._active = False

            def make_handlers(w, i_lbl, t_lbl, tab_key):
                _icon_color = TAB_COLORS.get(tab_key, ICON_FG)
                def on_enter(e):
                    if not w._active:
                        for wgt in (w, w._inner, i_lbl, t_lbl):
                            wgt.config(bg=HOVER_BG)
                        i_lbl.config(fg=ACTIVE_FG)
                        t_lbl.config(fg=ACTIVE_FG)
                def on_leave(e):
                    if not w._active:
                        for wgt in (w, w._inner, i_lbl, t_lbl):
                            wgt.config(bg=SIDEBAR_BG)
                        i_lbl.config(fg=_icon_color)
                        t_lbl.config(fg=TEXT_FG)
                return on_enter, on_leave

            on_enter, on_leave = make_handlers(wrapper, icon_lbl, text_lbl, key)

            for widget in (wrapper, inner, icon_lbl, text_lbl):
                widget.bind('<Enter>', on_enter)
                widget.bind('<Leave>', on_leave)
                widget.bind('<Button-1>', lambda e, k=key: self._switch_tab(k))

            self._tab_buttons[key]      = icon_lbl
            self._sidebar_wrappers[key] = wrapper
            self._sidebar_labels[key]   = text_lbl
            self._attach_tooltip(wrapper, _tip_clip(tip))

        # 하단 구분선
        _tk.Frame(sidebar, bg=tc('bg_secondary'), height=1).pack(fill='x', pady=8)

        # v7.9.9 [Q3]: 사이드바 하단 고정 버튼
        # 빈 공간 채우기 (버튼들을 맨 아래로 밀기)
        _spacer = _tk.Frame(sidebar, bg=SIDEBAR_BG)
        _spacer.pack(fill='both', expand=True)

        _tk.Frame(sidebar, bg=tc('bg_secondary'), height=1).pack(fill='x')

        # 🌙☀ 테마 전환 버튼
        def _toggle_theme_from_sidebar():
            try:
                current = getattr(self, 'current_theme', 'darkly')
                from gui_app_modular.utils.constants import DARK_THEMES, LIGHT_THEMES
                is_dark = current in DARK_THEMES if hasattr(__import__('gui_app_modular.utils.constants', fromlist=['DARK_THEMES']), 'DARK_THEMES') else 'dark' in current.lower()
                next_theme = 'darkly' if not is_dark else 'darkly'
                if hasattr(self, '_apply_theme'):
                    self._apply_theme(next_theme)
                elif hasattr(self, 'apply_theme'):
                    self.apply_theme(next_theme)
            except Exception as _te:
                logger.debug(f"[SIDEBAR] theme toggle: {_te}")

        theme_btn = _tk.Label(sidebar, text='🌙', font=('Segoe UI Emoji', 14),
                              bg=SIDEBAR_BG, fg=ICON_FG,
                              width=4, pady=8, cursor='hand2')
        theme_btn.pack(fill='x')
        theme_btn.bind('<Button-1>', lambda e: _toggle_theme_from_sidebar())
        theme_btn.bind('<Enter>', lambda e: theme_btn.config(bg=HOVER_BG, fg=ACTIVE_FG))
        theme_btn.bind('<Leave>', lambda e: theme_btn.config(bg=SIDEBAR_BG, fg=ICON_FG))
        self._attach_tooltip(theme_btn, _tip_clip('테마 전환(밝음/어두움).'))

        # ⚙ 설정 버튼
        def _open_settings_from_sidebar():
            try:
                # v8.7.0 [FIX CRIT-3]: _show_settings_dialog는 정의되지 않았음.
                #   실제 설정 진입점은 SettingsDialogMixin._show_api_settings.
                if hasattr(self, '_on_settings'):
                    self._on_settings()
                elif hasattr(self, '_show_api_settings'):
                    self._show_api_settings()
                elif hasattr(self, '_show_settings_dialog'):
                    self._show_settings_dialog()
            except Exception as _se:
                logger.debug(f"[SIDEBAR] settings: {_se}")

        settings_btn = _tk.Label(sidebar, text='⚙', font=('Segoe UI Emoji', 14),
                                 bg=SIDEBAR_BG, fg=ICON_FG,
                                 width=4, pady=8, cursor='hand2')
        settings_btn.pack(fill='x')
        settings_btn.bind('<Button-1>', lambda e: _open_settings_from_sidebar())
        settings_btn.bind('<Enter>', lambda e: settings_btn.config(bg=HOVER_BG, fg=ACTIVE_FG))
        settings_btn.bind('<Leave>', lambda e: settings_btn.config(bg=SIDEBAR_BG, fg=ICON_FG))
        self._attach_tooltip(settings_btn, _tip_clip('설정·환경 옵션 열기.'))

        _tk.Frame(sidebar, bg=SIDEBAR_BG, height=6).pack(fill='x')

    def _highlight_active_tab(self) -> None:
        """v8.6.4 [SIDEBAR]: 활성 탭 = 밝은 흰색, 비활성 = 탭 고유 컬러."""
        SIDEBAR_BG   = tc('bg_secondary')
        ACTIVE_BG    = tc('bg_secondary')
        ACTIVE_BAR   = tc('border_focus')
        INACTIVE_BAR = SIDEBAR_BG
        ACTIVE_FG    = tc('text_primary')
        TEXT_FG      = tc('text_muted')
        TEXT_ACTIVE  = tc('text_primary')

        TAB_COLORS = {
            'inventory':  '#4ade80', 'allocation': '#facc15',
            'picked':     '#a78bfa', 'sold':       '#38bdf8',
            'return_tab': '#f87171', 'move':       '#22d3ee',
            'dashboard':  '#00e676', 'log':        '#94a3b8',
            'scan':       '#fb923c',
        }

        wrappers = getattr(self, '_sidebar_wrappers', {})
        labels   = getattr(self, '_sidebar_labels',   {})
        for key, wrapper in wrappers.items():
            is_active = (key == self._active_tab_key)
            bg      = ACTIVE_BG  if is_active else SIDEBAR_BG
            bar_c   = ACTIVE_BAR if is_active else INACTIVE_BAR
            _tab_clr = TAB_COLORS.get(key, TEXT_FG)
            icon_fg = ACTIVE_FG if is_active else _tab_clr
            text_fg = TEXT_ACTIVE if is_active else TEXT_FG
            wrapper.config(bg=bg)
            wrapper._icon.config(bg=bg, fg=icon_fg)
            wrapper._bar.config(bg=bar_c)
            wrapper._active = is_active
            if hasattr(wrapper, '_inner'):
                wrapper._inner.config(bg=bg)
            lbl = labels.get(key)
            if lbl:
                try:
                    lbl.config(bg=bg, fg=text_fg)
                except Exception:
                    logger.debug("[SUPPRESSED] exception in toolbar_mixin.py")  # noqa


    # 탭 버튼 (균등 배치)
    # ═══════════════════════════════════════════════════════

    def _build_tab_buttons(self) -> None:
        """v5.5.3 patch_01: 탭 버튼 — 밑줄+텍스트 스타일 (메뉴와 통일)"""
        _ = self._toolbar_font  # toolbar_font reserved
        # 4개 메인(한글) + 총괄 재고 리스트 + 통계 + 로그
        tab_defs = [
            ('inventory', '📦 판매가능',
             'LOT 리스트(판매가능). 필터·검색 후 더블클릭 시 LOT 상세·톤백. [전체 톤백 펼치기]로 해당 상태 톤백 일괄 표시.'),
            ('allocation', '📋 판매배정',
             'LOT 리스트(판매배정). [전체 배정 보기]로 톤백 일괄 표시.'),
            ('picked', '🚛 판매화물 결정',
             'LOT 리스트(판매화물 결정). [전체 피킹 보기].'),
            ('sold', '✅ 출고',
             'LOT/톤백 리스트(출고 완료). [전체 판매 보기].'),
            ('cargo_overview', '📋 총괄 재고 리스트',
             '상태별 화물 한눈에 (전체/판매가능/판매배정/판매화물 결정/출고).'),
            ('dashboard', '📊 대시보드',
             '4단계 현황, 알림, 최근 7일 차트 등.'),
            ('log', '📝 로그',
             '시스템·작업 로그. 오류 추적·동작 확인.'),
            ('scan', '📷 스캔',
             '바코드 스캔 기반 출고·반품·재입고 처리.'),
        ]
        self._tab_buttons = {}
        # v5.7.5: 탭은 상단 메뉴보다 작게 (Phase3: FontScale.small + Spacing)
        _tab_font = self._tb_font_scale.small()
        from ..utils.menu_tab_tooltips import clip_tooltip as _tab_tip_clip
        for key, text, tip in tab_defs:
            wrapper = tk.Frame(self._sec_tabs, bg=self._tb_bg)
            wrapper.pack(side='left', padx=Spacing.XS)

            btn = tk.Label(wrapper, text=text, font=_tab_font,
                          bg=self._tb_bg, fg=self._tb_fg_normal,
                          anchor='center', justify='center',
                          padx=Spacing.SM, pady=Spacing.XS, cursor='hand2')
            btn.pack()

            # 밑줄 (비활성 시 숨김)
            underline = tk.Frame(wrapper, height=2, bg=self._tb_underline_color)
            btn._underline = underline
            btn._wrapper = wrapper

            btn.bind('<Button-1>', lambda e, k=key: self._switch_tab(k))
            btn.bind('<Enter>', lambda e, b=btn, k=key: self._tab_hover_enter(b, k))
            btn.bind('<Leave>', lambda e, b=btn, k=key: self._tab_hover_leave(b, k))
            if tip:
                self._attach_tooltip(btn, _tab_tip_clip(tip))
            self._tab_buttons[key] = btn

    # ═══════════════════════════════════════════════════════
    # 자동 2줄 전환
    # ═══════════════════════════════════════════════════════

    def _check_toolbar_overflow(self, event=None) -> None:
        try:
            self.root.update_idletasks()

            win_w = self.root.winfo_width()
            need_w = self._menu_frame.winfo_reqwidth() + self._sec_tabs.winfo_reqwidth() + 60
            if need_w > win_w and not self._row2_visible:
                self._sec_tabs.pack_forget()
                self._sec_tabs.pack(in_=self._row2, fill='x', expand=True, padx=Spacing.SM)
                self._row2.pack(fill='x')
                self._row2_visible = True
            elif need_w <= win_w and self._row2_visible:
                self._sec_tabs.pack_forget()
                self._row2.pack_forget()
                self._sec_tabs.pack(in_=self._row1, fill='x', expand=True, padx=Spacing.SM, pady=(Spacing.XS, 0))
                self._row2_visible = False
        except (RuntimeError, ValueError) as _e:
            logger.debug(f"{type(_e).__name__}: {_e}")
        except (RuntimeError, ValueError) as _e:
            logger.debug(f"toolbar_mixin: {_e}")

    # ═══════════════════════════════════════════════════════
    # 탭 전환
    # ═══════════════════════════════════════════════════════

    def _switch_tab(self, tab_key: str):
        """사이드바 탭 전환 — v8.1.7: 위젯 참조 방식 (인덱스 오동작 버그 제거)."""
        # tab_key → tab_xxx 위젯 매핑
        _key_to_attr = {
            'inventory':  'tab_inventory',
            'allocation': 'tab_allocation',
            'picked':     'tab_picked',
            'sold':       'tab_sold',
            'return_tab': 'tab_return',
            'move':       'tab_move',
            'dashboard':  'tab_dashboard',
            'log':        'tab_log',
            'scan':       'tab_scan',
        }
        attr = _key_to_attr.get(tab_key)
        tab = getattr(self, attr, None) if attr else None
        if tab is None or not hasattr(self, 'notebook'):
            return
        try:
            self.notebook.select(tab)
            self._active_tab_key = tab_key
            self._highlight_active_tab()
            # v8.7.2 [FIX]: Windows에서 탭 전환 후 이전 탭 내용이 잔류하는 렌더링 버그 방지
            self.notebook.update_idletasks()
        except (ValueError, TypeError, AttributeError) as _e:
            logger.debug(f"[_switch_tab] {tab_key}: {_e}")

    def _tab_hover_enter(self, btn, key: str) -> None:
        """v5.5.3 patch_01: 호버 — 텍스트 색상만 변경"""
        if key != self._active_tab_key:
            btn.config(fg=self._tb_fg_hover)

    def _tab_hover_leave(self, btn, key: str) -> None:
        """v5.5.3 patch_01: 호버 해제"""
        if key != self._active_tab_key:
            btn.config(fg=self._tb_fg_normal)

    # ═══════════════════════════════════════════════════════
    # 🔍 검색 팝업
    # ═══════════════════════════════════════════════════════

    def _show_search_popup(self) -> None:
        """v3.8.9: 검색 팝업 — DB 데이터 로드 + LOT 리스트 필터링"""
        _ = self._toolbar_font  # toolbar_font reserved
        popup = create_themed_toplevel(self.root)
        popup.title("🔍 검색")
        popup.geometry(DialogSize.get_geometry(self.root, 'medium'))
        apply_modal_window_options(popup)
        popup.transient(self.root)
        popup.grab_set()
        center_dialog(popup, self.root)

        main = tk.Frame(popup, padx=Spacing.LG, pady=Spacing.MD)
        main.pack(fill='both', expand=True)

        # v3.8.9: 검색 필터용 안정적 StringVar (팝업 닫혀도 유지)
        if not hasattr(self, '_search_filter_vars'):
            self._search_filter_vars = {
                'sap_no': tk.StringVar(self.root, value='전체'),
                'bl_no': tk.StringVar(self.root, value='전체'),
                'lot_no': tk.StringVar(self.root, value='전체'),
                'status': tk.StringVar(self.root, value='전체'),
                'date_from': tk.StringVar(self.root, value=''),
                'date_to': tk.StringVar(self.root, value=''),
            }
        
        svars = self._search_filter_vars
        _lab_font = self._tb_font_scale.heading()
        _body_font = self._tb_font_scale.body()

        # 콤보박스: SAP NO, BL NO, LOT NO (Phase3: Spacing + FontScale)
        combos = {}
        for row_idx, (field, label) in enumerate([
            ('sap_no', 'SAP NO'), ('bl_no', 'BL NO'), ('lot_no', 'LOT NO')
        ]):
            tk.Label(main, text=label, font=_lab_font, anchor='w'
                     ).grid(row=row_idx, column=0, sticky='w', pady=Spacing.SM)
            cb = ttk.Combobox(main, textvariable=svars[field],
                              state='readonly', width=28, font=_body_font)
            cb.grid(row=row_idx, column=1, sticky='ew', padx=(Spacing.SM, 0), pady=Spacing.SM)
            combos[field] = cb
            
            # v3.8.9: DB에서 값 로드
            # v5.6.0: SQL 인젝션 방지 — 화이트리스트 검증
            ALLOWED_FIELDS = {'sap_no', 'bl_no', 'lot_no', 'status', 'product', 'warehouse'}
            try:
                if field not in ALLOWED_FIELDS:
                    logger.warning(f"허용되지 않은 필드: {field}")
                    continue
                rows = self.engine.db.fetchall(
                    f"SELECT DISTINCT {field} FROM inventory "
                    f"WHERE {field} IS NOT NULL AND {field} != '' "
                    f"ORDER BY {field} ASC"
                )
                vals = ['전체']
                for r in rows:
                    v = r.get(field, '') if isinstance(r, dict) else (r[0] if r else '')
                    if v:
                        vals.append(str(v))
                cb['values'] = vals
                logger.debug(f"검색 팝업 [{field}]: {len(vals)-1}개 로드")
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                logger.debug(f"{type(_e).__name__}: {_e}")
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                logger.debug(f"검색 팝업 [{field}] 로드 실패: {_e}")
                cb['values'] = ['전체']

        # v8.6.3: 공통 날짜 범위 바 통일 적용
        tk.Label(main, text='Arrival Date', font=_lab_font, anchor='w'
                 ).grid(row=3, column=0, sticky='w', pady=Spacing.SM)
        df = tk.Frame(main)
        df.grid(row=3, column=1, sticky='ew', padx=(Spacing.SM, 0), pady=Spacing.SM)
        try:
            from gui_app_modular.utils.tree_enhancements import make_date_range_bar
            _db, _sv_f, _sv_t = make_date_range_bar(
                df, lambda: None, label_from='', label_to='', show_clear=True)
            _db.pack(side='left')
            svars['date_from'] = _sv_f
            svars['date_to']   = _sv_t
        except Exception:
            _is_dark = is_dark()
            tk.Entry(df, textvariable=svars['date_from'], width=12, font=_body_font).pack(side='left')
            tk.Label(df, text=' ~ ', font=_body_font).pack(side='left')
            tk.Entry(df, textvariable=svars['date_to'], width=12, font=_body_font).pack(side='left')

        # 상태
        tk.Label(main, text='상태', font=_lab_font, anchor='w'
                 ).grid(row=4, column=0, sticky='w', pady=Spacing.SM)
        ttk.Combobox(main, textvariable=svars['status'],
                     values=['전체', 'AVAILABLE', 'PICKED', 'SHIPPED', 'DEPLETED'],
                     state='readonly', width=28, font=_body_font
                     ).grid(row=4, column=1, sticky='ew', padx=(Spacing.SM, 0), pady=Spacing.SM)

        main.columnconfigure(1, weight=1)

        def do_search():
            """검색 실행 → LOT 리스트 필터링"""
            # _inv_search_combos를 StringVar 기반으로 설정
            self._inv_search_combos = {}
            for field in ('sap_no', 'bl_no', 'lot_no'):
                self._inv_search_combos[field] = (svars[field], None)
            
            # Date, Status 반영
            if hasattr(self, '_date_from_var'):
                self._date_from_var.set(svars['date_from'].get())
            if hasattr(self, '_date_to_var'):
                self._date_to_var.set(svars['date_to'].get())
            if hasattr(self, 'status_var'):
                self.status_var.set(svars['status'].get())
            
            # AVAILABLE(LOT 리스트) 탭으로 이동 + 새로고침
            try:
                self.notebook.select(self.tab_inventory)
            except (AttributeError, RuntimeError) as _e:
                logger.debug(f"{type(_e).__name__}: {_e}")
            if hasattr(self, '_refresh_inventory'):
                self._refresh_inventory()
            popup.destroy()

        def do_reset():
            """초기화"""
            for key in svars:
                if key in ('date_from', 'date_to'):
                    svars[key].set('')
                else:
                    svars[key].set('전체')

        # v3.8.9: 버튼 크기 통일 (Phase3: Spacing + FontScale)
        _btn_font = self._tb_font_scale.body(bold=True)
        _btn_w = 12
        bf = tk.Frame(main)
        bf.grid(row=5, column=0, columnspan=2, pady=(Spacing.LG, 0))
        _popup_dark = is_dark()
        _btn_fg = ThemeColors.get('badge_text', _popup_dark)
        tk.Button(bf, text='🔍 검색', font=_btn_font, bg=ThemeColors.get('statusbar_progress', is_dark()), fg=_btn_fg,
                 bd=0, width=_btn_w, pady=Spacing.SM, cursor='hand2',
                 command=do_search).pack(side='left', padx=Spacing.SM)
        tk.Button(bf, text='🔄 초기화', font=_btn_font, bg=ThemeColors.get('btn_neutral', _popup_dark), fg=_btn_fg,
                 bd=0, width=_btn_w, pady=Spacing.SM, cursor='hand2',
                 command=do_reset).pack(side='left', padx=Spacing.SM)

        popup.bind('<Escape>', lambda e: popup.destroy())
        popup.bind('<Return>', lambda e: do_search())

    # ═══════════════════════════════════════════════════════
    # 컨테이너 서픽스
    # ═══════════════════════════════════════════════════════

    def _on_container_suffix_toggle(self) -> None:
        """컨테이너 -1, -2 서픽스 표시 토글 — 재고/톤백 테이블의 CONTAINER 열 표시를 갱신합니다."""
        show = self._container_suffix_var.get()
        self._log(f"📦 컨테이너 구분: {'ON' if show else 'OFF'}")
        self._safe_refresh()
    def _format_container_no(self, container_no: str) -> str:
        """컨테이너 번호 표시: _container_suffix_var가 꺼져 있으면 끝의 -1, -2 접미사를 제거합니다."""
        if not container_no:
            return ''
        if not getattr(self, '_container_suffix_var', None):
            return str(container_no)
        if not self._container_suffix_var.get():
            s = str(container_no).strip()
            if '-' in s:
                parts = s.rsplit('-', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    return parts[0].strip()
        return str(container_no)

    def _on_auto_refresh_toggle(self) -> None:
        """v3.8.4: 대시보드 자동 갱신 30초 토글"""
        enabled = self._auto_refresh_var.get()
        self._log(f"🔄 자동 갱신: {'ON (30초)' if enabled else 'OFF'}")
        if enabled:
            self._schedule_auto_refresh()
        
    def _schedule_auto_refresh(self) -> None:
        """30초 타이머로 대시보드 갱신 + DB 변경 감지 (v3.8.4)"""
        if not getattr(self, '_auto_refresh_var', None):
            return
        if not self._auto_refresh_var.get():
            return
        try:
            # DB 파일 변경 감지
            db_changed = self._check_db_modified()
            if db_changed:
                if hasattr(self, '_refresh_inventory'):
                    self._refresh_inventory()
                if hasattr(self, '_refresh_tonbag'):
                    self._refresh_tonbag()
                self._log("🔄 DB 변경 감지 → 자동 새로고침")
            
            if hasattr(self, '_refresh_dashboard'):
                self._refresh_dashboard()
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"자동 갱신 오류: {e}")
        # 30초 후 재호출
        if hasattr(self, 'root'):
            self.root.after(30000, self._schedule_auto_refresh)

    def _check_db_modified(self) -> bool:
        """v3.8.4: DB 파일 수정 시간 비교"""
        import os
        try:
            db_path = getattr(self, 'db_path', None)
            if not db_path or not os.path.exists(db_path):
                return False
            
            mtime = os.path.getmtime(db_path)
            last = getattr(self, '_last_db_mtime', 0)
            
            if mtime > last:
                self._last_db_mtime = mtime
                return last > 0  # 최초 실행 시는 False
            return False
        except (OSError, IOError, PermissionError):
            return False

    def _on_fix_lot_status_integrity(self) -> None:
        """v6.8.5: LOT 상태 정합성 복구 (최초 1회)"""
        from ..utils.custom_messagebox import CustomMessageBox
        ans = CustomMessageBox.askyesno(
            self,
            "LOT 상태 정합성 복구",
            "LOT 상태를 톤백 기준으로 일괄 보정합니다.\n\n"
            "• LOT=SOLD 이지만 AVAILABLE 톤백 잔존 → AVAILABLE\n"
            "• LOT=AVAILABLE 이지만 전체 SOLD → SOLD\n\n"
            "계속하시겠습니까?"
        )
        if not ans:
            return
        try:
            result = self.engine.fix_lot_status_integrity()
            if result.get('success'):
                _cnt = result.get('fixed', 0)
                _details = '\n'.join(result.get('details', [])[:20])
                msg = f"복구 완료: {_cnt}건\n\n{_details}" if _cnt else "정합성 이상 없음"
                CustomMessageBox.info(self, title="복구 완료", message=msg)
            else:
                CustomMessageBox.error(
                    self, title="오류",
                    message='\n'.join(result.get('errors', ['알 수 없는 오류']))
                )
        except Exception as e:
            CustomMessageBox.error(self, title="오류", message=str(e))

    def _on_integrity_check(self) -> None:
        """v3.8.7: 정합성 검사 + 18열 데이터 누락 진단"""
        from ..utils.custom_messagebox import CustomMessageBox
        try:
            from core.validators import InventoryValidator
            validator = InventoryValidator(db=self.engine.db)
            
            # 1. 기존 정합성 검사
            result = validator.check_data_integrity()
            issues = []
            if result.errors:
                for e in result.errors:
                    issues.append(f"🔴 {e}")
            if result.warnings:
                for w in result.warnings:
                    issues.append(f"🟡 {w}")
            
            # 2. v3.8.7: 18열 데이터 누락 진단
            total_cnt = self.engine.db.fetchone("SELECT COUNT(*) AS cnt FROM inventory")
            total = (total_cnt['cnt'] if total_cnt else 0) if total_cnt else 0
            
            if total > 0:
                key_cols = [
                    ('lot_no', 'LOT NO'), ('sap_no', 'SAP NO'), ('bl_no', 'BL NO'),
                    ('container_no', 'CONTAINER'), ('product', 'PRODUCT'),
                    ('product_code', 'CODE'), ('lot_sqm', 'LOT SQM'),
                    ('mxbg_pallet', 'MXBG'), ('net_weight', 'NET(Kg)'),
                    ('gross_weight', 'GROSS(Kg)'), ('salar_invoice_no', 'INVOICE NO'),
                    ('ship_date', 'SHIP DATE'), ('arrival_date', 'ARRIVAL'),
                    ('free_time', 'FREE TIME'), ('warehouse', 'WH'),
                    ('status', 'STATUS'), ('current_weight', 'Balance'),
                    ('initial_weight', '입고량'),
                ]
                
                issues.append("")
                issues.append("━━━ 18열 데이터 완성도 ━━━")
                
                for col_db, col_label in key_cols:
                    # v5.6.0: 화이트리스트 검증 (key_cols는 하드코딩이지만 안전장치)
                    ALLOWED_COLS = {k for k, _ in key_cols}
                    if col_db not in ALLOWED_COLS:
                        continue
                    try:
                        filled_row = self.engine.db.fetchone(
                            f"SELECT COUNT(*) AS cnt FROM inventory "
                            f"WHERE {col_db} IS NOT NULL AND {col_db} != '' AND {col_db} != 0"
                        )
                        filled = (filled_row['cnt'] if filled_row else 0) if filled_row else 0
                        empty = total - filled
                        pct = filled / total * 100
                        
                        if empty > 0:
                            icon = '🔴' if pct < 50 else ('🟡' if pct < 80 else '🟢')
                            issues.append(f"{icon} {col_label:12s}: {filled}/{total} ({pct:.0f}%) — {empty}개 누락")
                        else:
                            issues.append(f"✅ {col_label:12s}: {total}/{total} (100%)")
                    except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError):
                        issues.append(f"⚪ {col_label:12s}: 확인 불가")
            
            if not issues:
                CustomMessageBox.showinfo(self.root, "✅ 정합성 검사", "모든 데이터가 정상입니다.")
                return
            
            msg = "\n".join(issues[:30])
            if len(issues) > 30:
                msg += f"\n... 외 {len(issues) - 30}건"
            
            # 복구 질문
            if result.errors or result.warnings:
                if CustomMessageBox.askyesno(self.root, "⚠️ 정합성 검사 + 18열 진단",
                    f"{msg}\n\n자동 복구를 실행할까요?"):
                    
                    fix_result = validator.fix_data_integrity(dry_run=False)
                    fixes = fix_result.get('fixes', [])
                    if fixes:
                        self._log(f"✅ 정합성 복구: {len(fixes)}건")
                        CustomMessageBox.showinfo(self.root, "복구 완료",
                            f"복구 완료: {len(fixes)}건\n\n" + "\n".join(fixes[:10]))
                        self._refresh_inventory()
                    else:
                        CustomMessageBox.showinfo(self.root, "복구", "복구할 항목이 없습니다.")
            else:
                CustomMessageBox.showinfo(self.root, "📊 18열 데이터 진단", msg)
                
        except (RuntimeError, ValueError) as e:
            CustomMessageBox.showerror(self.root, "오류", f"정합성 검사 오류:\n{e}")

    def _on_operational_schema_check_once(self) -> None:
        """운영 DB 기준 스키마 점검(1회) — Allocation 원장화 필수 항목 확인."""
        try:
            db = getattr(getattr(self, "engine", None), "db", None)
            if db is None:
                CustomMessageBox.showwarning(self.root, "스키마 점검", "DB 연결이 없어 점검할 수 없습니다.")
                return

            def _table_exists(name: str) -> bool:
                row = db.fetchone(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (name,)
                )
                return bool(row)

            def _index_exists(name: str) -> bool:
                row = db.fetchone(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                    (name,)
                )
                return bool(row)

            def _cols(name: str) -> set:
                rows = db.fetchall(f"PRAGMA table_info({name})") or []
                return {str(r.get("name", "")).strip().lower() for r in rows}

            checks = []
            checks.append(("table:allocation_import_batch", _table_exists("allocation_import_batch")))
            checks.append(("table:lot_reservation", _table_exists("lot_reservation")))

            sm_cols = _cols("stock_movement")
            ap_cols = _cols("allocation_plan")
            req_sm = {"ref_table", "ref_id", "source", "actor", "details_json"}
            req_ap = {"import_batch_id", "line_no", "gate_status", "fail_code", "fail_reason", "validated_at"}
            checks.append(("stock_movement.ref_trace_cols", req_sm.issubset(sm_cols)))
            checks.append(("allocation_plan.gate_cols", req_ap.issubset(ap_cols)))
            checks.append(("index:ux_alloc_line", _index_exists("ux_alloc_line")))
            checks.append(("index:idx_stock_mv_ref", _index_exists("idx_stock_mv_ref")))

            ok_count = sum(1 for _, ok in checks if ok)
            ng = [name for name, ok in checks if not ok]
            lines = [
                f"[운영 DB 스키마 점검 결과] {ok_count}/{len(checks)} 통과",
                "",
            ]
            for name, ok in checks:
                lines.append(f"{'✅' if ok else '❌'} {name}")
            if ng:
                lines += [
                    "",
                    "누락 항목이 있어도 앱 재시작 시 마이그레이션으로 자동 보정될 수 있습니다.",
                    "재시작 후 다시 점검해도 동일하면 알려주세요.",
                ]
                CustomMessageBox.showwarning(self.root, "운영 DB 스키마 점검", "\n".join(lines))
            else:
                CustomMessageBox.showinfo(self.root, "운영 DB 스키마 점검", "\n".join(lines))
        except Exception as e:
            logger.error(f"운영 DB 스키마 점검 오류: {e}", exc_info=True)
            CustomMessageBox.showerror(self.root, "스키마 점검 오류", str(e))

    # ═══════════════════════════════════════════════════════
    # 유틸리티
    # ═══════════════════════════════════════════════════════
    def _restore_toolbar_chain_bg(self):
        """v5.3.5: restore toolbar/menu parent frame chain bg to theme bg.
        Fix for Windows light theme where tk_popup/grab_release refresh resets bg.
        """
        for name in ('_toolbar', '_row0', '_row1', '_menu_frame', '_row2', '_sec_tabs'):
            try:
                w = getattr(self, name, None)
                if w and w.winfo_exists():
                    w.config(bg=self._tb_bg)
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")



    
    def _refresh_toolbar_theme(self) -> None:
        """v5.4.0: Apply current ThemeColors palette to existing toolbar widgets.
        Fix: light theme switching leaving toolbar colors stale or mismatched.
        """
        try:
            self._load_toolbar_colors()
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")

        # restore container chain bg first
        try:
            self._restore_toolbar_chain_bg()
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")

        for w in (getattr(self, '_toolbar_container', None), getattr(self, '_row1', None),
                  getattr(self, '_row2', None), getattr(self, '_menu_frame', None),
                  getattr(self, '_sec_tabs', None)):
            try:
                if w and w.winfo_exists():
                    w.config(bg=self._tb_bg)
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")

        # v5.5.3 patch_01: 모든 메뉴 버튼 동일 스타일 적용
        for b in getattr(self, '_all_menu_btns', []):
            try:
                if not b.winfo_exists():
                    continue
                b.config(bg=self._tb_bg,
                         fg=self._tb_fg_active if getattr(b, '_menu_active', False) else self._tb_fg_normal)
                # 밑줄 색상도 테마에 맞게 갱신
                if hasattr(b, '_underline') and b._underline.winfo_exists():
                    b._underline.config(bg=self._tb_underline_color)
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")


        # v5.4.1: 드롭다운 tk.Menu 팔레트도 테마에 맞게 재동기화(화이트 모드 검정 변색 방지)
        try:
            dark_mode = is_dark()
            # D/O 후속 연결 등 하위 메뉴는 배경 대비가 확실한 고대비 색상으로 고정한다.
            menu_bg = '#101827' if dark_mode else '#ffffff'
            menu_fg = '#f8fafc' if dark_mode else '#111827'
            menu_abg = '#2f80ed' if dark_mode else '#0f6ecb'
            menu_afg = '#ffffff'
            menu_dis = '#cbd5e1' if dark_mode else '#334155'
            for m in getattr(self, '_all_dropdown_menus', []):
                try:
                    if m and m.winfo_exists():
                        m.config(bg=menu_bg, fg=menu_fg, activebackground=menu_abg, activeforeground=menu_afg, disabledforeground=menu_dis)
                except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                    logger.debug(f"Suppressed: {_e}")
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")

        # v5.5.3 patch_01: 탭 버튼도 테마 갱신
        try:
            if hasattr(self, '_tab_buttons'):
                self._highlight_active_tab()
                # v7.9.9 [SIDEBAR]: 사이드바는 고정 색상 — wrapper bg 변경 불필요
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")

        # v5.5.3 patch_02: 검색 버튼 밑줄 색상 갱신 (폴백 tk.Label용)
        try:
            sb = getattr(self, '_search_btn', None)
            if sb and sb.winfo_exists() and isinstance(sb, tk.Label):
                sb.config(fg=self._tb_underline_color,
                          highlightbackground=self._tb_underline_color)
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
            logger.debug(f"Suppressed: {_e}")

        try:
            self.root.after_idle(lambda: self.root.update_idletasks())
        except (ValueError, TypeError, KeyError, AttributeError, tk.TclError):
            try:
                self.root.update_idletasks()
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")

    def _show_menu(self, menu, btn) -> None:
        """
        v5.0.9: tk_popup + after()로 확실한 색상 복구
        
        Windows White 테마에서 tk_popup() 후 grab_release() 시
        tkinter가 내부적으로 위젯 배경을 시스템 기본색으로 리셋하는 문제.
        after()로 지연 복구 + 부모 프레임 배경까지 재설정으로 100% 해결.
        """
        # 모든 버튼 비활성
        for b in self._all_menu_btns:
            b._menu_active = False
            try:
                b.config(fg=self._tb_fg_normal)
                if hasattr(b, '_underline'):
                    b._underline.pack_forget()
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"Suppressed: {_e}")

        # 현재 버튼만 활성 (밑줄 + 흰색 텍스트)
        btn._menu_active = True
        btn.config(fg=self._tb_fg_active)
        if hasattr(btn, '_underline'):
            btn._underline.place(relx=0, rely=1.0, relwidth=1.0, anchor='sw')
        
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        
        def _restore_all_buttons():
            """모든 버튼 + 부모 프레임 색상 강제 복구"""
            try:
                # v5.3.6: capture before state for anomaly logging
                _before = {
                    'tb_bg': getattr(self, '_tb_bg', None),
                    'menu_frame_bg': safe_widget_bg(getattr(self, '_menu_frame', None)),
                    'row1_bg': safe_widget_bg(getattr(self, '_row1', None)),
                }

                # v5.3.5: 상위 체인까지 통째로 bg 복구
                self._restore_toolbar_chain_bg()
                # 부모 프레임 배경도 재설정 (White 테마 핵심!)
                if hasattr(self, '_menu_frame') and self._menu_frame.winfo_exists():
                    self._menu_frame.config(bg=self._tb_bg)
                if hasattr(self, '_row1') and self._row1.winfo_exists():
                    self._row1.config(bg=self._tb_bg)
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"[toolbar_mixin] 무시: {_e}")
            
            for b in self._all_menu_btns:
                b._menu_active = False
                try:
                    if not b.winfo_exists():
                        continue
                    # v5.5.3 patch_01: 텍스트 색상만 복구 (배경 변경 없음)
                    mx = b.winfo_pointerx() - b.winfo_rootx()
                    my = b.winfo_pointery() - b.winfo_rooty()
                    is_hover = (0 <= mx <= b.winfo_width() and
                               0 <= my <= b.winfo_height())
                    b.config(fg=self._tb_fg_hover if is_hover else self._tb_fg_normal)
                    if hasattr(b, '_underline'):
                        b._underline.pack_forget()
                except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                    logger.debug(f"Suppressed: {_e}")
            
            # 강제 화면 갱신 (White 테마에서 필수)
            try:
                self.root.update_idletasks()

                # v5.3.6: detect light theme bg reset and log once per restore call
                _after = {
                    'menu_frame_bg': safe_widget_bg(getattr(self, '_menu_frame', None)),
                    'row1_bg': safe_widget_bg(getattr(self, '_row1', None)),
                }
                try:
                    exp = getattr(self, '_tb_bg', None)
                    if exp and (_after.get('menu_frame_bg') not in (None, exp) or _after.get('row1_bg') not in (None, exp)):
                        log_ui_event('UI_BG_ANOMALY_TOOLBAR', {
                            'expected': exp,
                            'before': _before,
                            'after': _after,
                        })
                except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                    logger.debug(f"Suppressed: {_e}")
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"[toolbar_mixin] 무시: {_e}")
        
        try:
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError) as _e:
                logger.debug(f"[toolbar_mixin] 무시: {_e}")
            
            btn._menu_active = False
            
            # v5.3.5: after_idle 1회 + after()로 지연 복구 (50/200/500/1000ms)
            # White 테마에서 tkinter 내부 갱신이 느릴 수 있으므로 4회 보장
            try:
                self.root.after_idle(_restore_all_buttons)
                self.root.after(50, _restore_all_buttons)
                self.root.after(200, _restore_all_buttons)
                self.root.after(500, _restore_all_buttons)
                self.root.after(1000, _restore_all_buttons)
            except (ValueError, TypeError, KeyError, AttributeError, tk.TclError):
                _restore_all_buttons()
    
    def _safe_call(self, method_name: str):
        """메서드 안전 호출 (v8.4.1: self.app fallback 추가).
        - 메서드 미정의: 경고 메시지 표시
        - 메서드 실행 중 예외: 에러 로그 + 오류 메시지 표시
        """
        fn = getattr(self, method_name, None)
        # v8.4.1 [BUG-H]: ToolbarMixin.self에 없으면 self.app에서 탐색
        if not fn or not callable(fn):
            _app = getattr(self, 'app', None)
            if _app:
                fn = getattr(_app, method_name, None)
        if fn and callable(fn):
            try:
                fn()
            except Exception as _e:
                logger.error(f"[_safe_call] {method_name} 실행 오류: {_e}", exc_info=True)
                try:
                    CustomMessageBox.showerror(
                        getattr(self, 'root', None),
                        "실행 오류",
                        f"'{method_name}' 실행 중 오류 발생:\n{_e}"
                    )
                except Exception as e:
                    logger.warning(f'[UI] toolbar_mixin: {e}')
        else:
            logger.warning(f"[_safe_call] 메서드 미정의: {method_name}")
            try:
                CustomMessageBox.showwarning(
                    getattr(self, 'root', None),
                    "기능 준비 중",
                    f"'{method_name}' 기능은 아직 구현되지 않았습니다."
                )
            except Exception as _e:
                logger.debug(f"[_safe_call] 경고창 표시 실패: {_e}")

    def _attach_tooltip(self, widget, text: str):
        """v8.7.0 [UX]: 11시 방향 멀리 + 3초 자동숨김 + 클릭숨김 통일."""
        tip_win = None
        after_id = None
        hide_id = None
        def show():
            nonlocal tip_win, hide_id
            if tip_win:
                return
            tip_win = tk.Toplevel(widget)
            tip_win.wm_overrideredirect(True)
            _tip_dark = is_dark()
            tk.Label(tip_win, text=text, justify='left',
                     background=ThemeColors.get('bg_card', _tip_dark),
                     foreground=ThemeColors.get('text_primary', _tip_dark),
                     relief='solid', borderwidth=1,
                     font=self._tb_font_scale.body(),
                     padx=Spacing.SM, pady=Spacing.SM,
                     wraplength=520).pack()
            # 11시 방향 멀리 배치
            try:
                tip_win.update_idletasks()
                tw = tip_win.winfo_reqwidth()
                th = tip_win.winfo_reqheight()
                wx = widget.winfo_rootx()
                wy = widget.winfo_rooty()
                sw = widget.winfo_screenwidth()
                sh = widget.winfo_screenheight()
                x = wx - tw - 30
                y = wy - th - 20
                if x < 0:
                    x = max(0, wx - tw + 24)
                if y < 0:
                    y = wy + widget.winfo_height() + 8
                if x + tw > sw:
                    x = sw - tw - 2
                if y + th > sh:
                    y = sh - th - 2
                tip_win.wm_geometry(f"+{x}+{y}")
            except Exception as _pe:
                logger.debug(f"toolbar tooltip geometry: {_pe}")
            # 3초 자동 숨김
            try:
                hide_id = widget.after(3000, lambda: cancel(None))
            except Exception as _se:
                logger.debug(f"toolbar tooltip schedule: {_se}")
        def schedule(e):
            nonlocal after_id
            cancel(e)
            after_id = widget.after(400, show)
        def cancel(e):
            nonlocal tip_win, after_id, hide_id
            if after_id:
                try:
                    widget.after_cancel(after_id)
                except Exception as _e:
                    logger.debug("[tooltip] after_cancel(show) 실패: %s", _e)
                after_id = None
            if hide_id:
                try:
                    widget.after_cancel(hide_id)
                except Exception as _e:
                    logger.debug("[tooltip] after_cancel(hide) 실패: %s", _e)
                hide_id = None
            if tip_win:
                try:
                    tip_win.destroy()
                except Exception as _e:
                    logger.debug("[tooltip] tip_win.destroy 실패: %s", _e)
                tip_win = None
        widget.bind('<Enter>', schedule, add='+')
        widget.bind('<Leave>', cancel, add='+')
        widget.bind('<Button-1>', cancel, add='+')
        widget.bind('<Button-3>', cancel, add='+')

    def _refresh_all_data(self) -> None:
        try:
            for fn in ['_refresh_inventory', '_refresh_allocation', '_refresh_picked', '_refresh_sold', '_refresh_cargo_overview', '_refresh_dashboard']:
                if hasattr(self, fn): getattr(self, fn)()
            self._log("🔄 전체 새로고침 완료")
        except (RuntimeError, OSError) as e:
            logger.error(f"새로고침: {e}")

    def _on_sales_order_upload(self) -> None:
        """📊 Sales Order 업로드 → 처리 결과 즉시 요약 표시 (v9.1 E2).

        처리 완료 후:
          ✅ SOLD / ⚠️ PENDING / ❌ 오류 수량 팝업 표시
          PENDING 목록 상세 표시
        """
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        from features.parsers.sales_order_engine import SalesOrderEngine

        file_path = fd.askopenfilename(
            title="Sales Order 파일 선택",
            filetypes=[("Excel 파일", "*.xlsx *.xls"), ("All", "*.*")],
            parent=self,
        )
        if not file_path:
            return

        try:
            engine = SalesOrderEngine(db=self.db)
            result = engine.process(file_path)
        except Exception as e:
            mb.showerror("오류", f"Sales Order 처리 중 오류:\n{e}", parent=self)
            return

        so_no     = result.get("sales_order_no") or "?"
        sold      = result.get("sold", 0)
        pending   = result.get("pending", 0)
        remaining = result.get("remaining_picked", 0)
        warnings  = result.get("warnings", [])
        skipped   = result.get("skipped", [])
        success   = result.get("success", False)
        elapsed   = result.get("elapsed_ms", 0)

        # ── E2: 결과 요약 팝업 ─────────────────────────────────
        lines = [
            f"Sales Order: {so_no}",
            "",
            f"  ✅  SOLD      : {sold:3d}개",
            f"  ⚠️  PENDING   : {pending:3d}개",
            f"  🔄  잔여 PICKED: {remaining:3d}개",
            f"  ⏱  처리 시간 : {elapsed}ms",
        ]

        if pending > 0:
            lines.append("")
            lines.append("⚠️ PENDING 상세 (picking_table 미매칭):")
            for sk in (skipped or [])[:10]:
                lot = sk.get("lot_no", "?")
                pk  = sk.get("picking_no", "?")
                reason = sk.get("reason", "")[:40]
                lines.append(f"  • LOT {lot}  PK:{pk}  {reason}")
            if len(skipped or []) > 10:
                lines.append(f"  ... 외 {len(skipped)-10}건")

        if warnings:
            lines.append("")
            lines.append("📋 경고:")
            for w in warnings[:5]:
                lines.append(f"  {w[:60]}")

        summary = "\n".join(lines)
        if success and pending == 0:
            mb.showinfo(f"SO #{so_no} 완료", summary, parent=self)
        elif success and pending > 0:
            mb.showwarning(f"SO #{so_no} — PENDING {pending}건", summary, parent=self)
        else:
            mb.showerror(f"SO #{so_no} 실패", summary, parent=self)

        # 탭 새로고침
        if hasattr(self, "refresh_bus_deferred"):
            self.refresh_bus_deferred(reason="so_upload")
        logger.info(f"[SO_UPLOAD] SO#{so_no} SOLD={sold} PENDING={pending}")

    def _on_dn_cross_check(self) -> None:
        """🔍 DN 교차검증 — 고객 Sales Order / DN vs SQM DB (v8.6.4).

        고객이 보내온 DN/Sales Order Excel을 SQM 출고 DB와 비교.
        LOT 목록 / 수량 / 납기일 / 고객명 자동 검증.
        """
        try:
            from gui_app_modular.dialogs.dn_cross_check_dialog import show_dn_check_dialog
            show_dn_check_dialog(self, self.db)
        except ImportError as e:
            import tkinter.messagebox as _mb
            _mb.showerror("오류", f"DN 교차검증 모듈 로드 실패:\n{e}", parent=self)
        except Exception as e:
            import tkinter.messagebox as _mb
            _mb.showerror("DN 교차검증 오류", str(e), parent=self)



    def _change_font_size(self, size: int):
        try:
            import tkinter.font as tkfont
            for name in ["TkDefaultFont", "TkTextFont"]:
                tkfont.nametofont(name).configure(size=size)
            self._log(f"🔤 글꼴 크기: {size}pt")
        except (RuntimeError, ValueError) as e:
            logger.error(f"글꼴 크기: {e}")
