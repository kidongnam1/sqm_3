"""
SQM v5.5.3 — Treeview 향상: 줄무늬, 필터, 합계
=================================================
v5.5.3 patch_03: tk→ttk 전환으로 테마 자동 대응

재고 리스트 / 톤백 리스트에 공통 적용:
- 줄무늬 행 (striped rows)
- 헤더 필터 Combobox
- 하단 합계 바
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import calendar
import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from .ui_constants import ThemeColors, apply_modal_window_options, is_dark

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# v8.1.5: 기간 필터 공통 유틸
# ═══════════════════════════════════════════════════════
_PERIOD_TRACE_REGISTERED: set = set()  # (id(from_var), id(to_var)) 중복 방지


def row_reference_date_ymd(row: Optional[dict]) -> str:
    """LOT/톤백 행의 조회 기준일 YYYYMMDD (없으면 '').
    입항일 → 입고일(stock_date) → 선적일 → 생성일 순."""
    if not row:
        return ''
    for key in ('arrival_date', 'stock_date', 'ship_date', 'created_at'):
        raw = str(row.get(key, '') or '').strip()[:10]
        if raw:
            return raw.replace('-', '')
    return ''


def bind_period_vars_debounced(
    parent_widget,
    date_from_var,
    date_to_var,
    on_filter,
    delay_ms: int = 350,
    entry_widgets: tuple = (),
):
    """기간 StringVar 변경 시 디바운스 새로고침 연결.
    같은 (from_var, to_var) 조합에는 trace를 한 번만 등록."""
    _timer = [None]

    def _schedule(*_args):
        if _timer[0]:
            try:
                parent_widget.after_cancel(_timer[0])
            except Exception as e:
                logger.warning(f'[UI] tree_enhancements: {e}')
        _timer[0] = parent_widget.after(delay_ms, _fire)

    def _fire():
        _timer[0] = None
        try:
            on_filter()
        except Exception as e:
            logger.debug(f"period debounce fire: {e}")

    key = (id(date_from_var), id(date_to_var))
    if key not in _PERIOD_TRACE_REGISTERED:
        for sv in (date_from_var, date_to_var):
            if sv is None:
                continue
            try:
                sv.trace_add('write', lambda *_: _schedule())
            except Exception as e:
                logger.debug(f"trace_add period: {e}")
        _PERIOD_TRACE_REGISTERED.add(key)

    for w in entry_widgets:
        if w is None:
            continue
        try:
            w.bind('<FocusOut>', lambda e: _schedule())
            w.bind('<Return>', lambda e: _schedule())
        except Exception as e:
            logger.warning(f'[UI] tree_enhancements: {e}')
def _parse_date_for_calendar(value: Optional[str]) -> date:
    """기간 입력값(YYYY-MM-DD 등)을 date로. 실패 시 오늘."""
    if not value or not str(value).strip():
        return date.today()
    try:
        s = str(value).strip()
        if len(s) >= 10:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        return date.today()
    except (ValueError, TypeError) as e:
        logger.debug(f"Suppressed: {e}")
        return date.today()


def show_date_calendar(parent, initial_value: Optional[str], on_choose: Callable[[str], None]) -> None:
    """v8.6.3: 세련된 캘린더 팝업.

    개선 사항:
      - 연도/월 직접 선택 Combobox 추가
      - 오늘 날짜 하이라이트
      - 토(파란색) / 일(빨간색) 색상 구분
      - 오늘 버튼, 닫기 버튼
      - 창 크기 고정, 부모 위치 추적
    """
    import tkinter as tk
    from tkinter import ttk
    from datetime import date as _date_cls

    _today = _date_cls.today()
    d = _parse_date_for_calendar(initial_value)
    year, month = d.year, d.month

    win = create_themed_toplevel(parent)
    win.title("날짜 선택")
    win.resizable(False, False)
    win.transient(parent)
    win.grab_set()
    apply_modal_window_options(win)

    _is_dark = True
    try:
        from gui_app_modular.utils.theme_utils import is_dark as _is_dark_fn
        _is_dark = _is_dark_fn()
    except Exception as _e:
        logger.debug(f"[tree_enhancements] 다크모드 감지 실패: {_e}")

    # 색상 팔레트
    BG       = '#1E293B' if _is_dark else '#F8FAFC'
    BG_NAV   = '#0F172A' if _is_dark else '#E2E8F0'
    FG       = '#F1F5F9' if _is_dark else '#1E293B'
    FG_MUTED = '#64748B' if _is_dark else '#94A3B8'
    ACCENT   = '#22D3EE'    # Cyan-400
    TODAY_BG = '#0E7490'    # Cyan-700
    SAT_FG   = '#60A5FA'    # Blue-400
    SUN_FG   = '#F87171'    # Red-400
    BTN_BG   = '#334155' if _is_dark else '#E2E8F0'
    BTN_HOV  = '#475569' if _is_dark else '#CBD5E1'
    SEL_BG   = '#22D3EE'
    SEL_FG   = '#0F172A'

    win.configure(bg=BG)

    # ── 상단 네비게이션 ──────────────────────────────────
    nav = tk.Frame(win, bg=BG_NAV, pady=8)
    nav.pack(fill=tk.X)

    def _prev_month():
        nonlocal year, month
        month -= 1
        if month < 1: year -= 1; month = 12
        _year_var.set(str(year)); _month_var.set(f"{month:02d}")
        _render()

    def _next_month():
        nonlocal year, month
        month += 1
        if month > 12: year += 1; month = 1
        _year_var.set(str(year)); _month_var.set(f"{month:02d}")
        _render()

    def _prev_year():
        nonlocal year
        year -= 1
        _year_var.set(str(year)); _render()

    def _next_year():
        nonlocal year
        year += 1
        _year_var.set(str(year)); _render()

    # 연도/월 Combobox
    _year_var  = tk.StringVar(value=str(year))
    _month_var = tk.StringVar(value=f"{month:02d}")
    year_list  = [str(y) for y in range(_today.year - 5, _today.year + 6)]
    month_list = [f"{m:02d}" for m in range(1, 13)]

    tk.Button(nav, text="«", bg=BG_NAV, fg=FG, bd=0, font=("맑은 고딕",10,"bold"),
              command=_prev_year, cursor="hand2").pack(side=tk.LEFT, padx=(8,2))
    tk.Button(nav, text="‹", bg=BG_NAV, fg=FG, bd=0, font=("맑은 고딕",11,"bold"),
              command=_prev_month, cursor="hand2").pack(side=tk.LEFT, padx=2)

    _y_cb = ttk.Combobox(nav, textvariable=_year_var, values=year_list,
                         width=6, state='readonly', font=("맑은 고딕",9))
    _y_cb.pack(side=tk.LEFT, padx=4)
    tk.Label(nav, text="년", bg=BG_NAV, fg=FG, font=("맑은 고딕",9)).pack(side=tk.LEFT)

    _m_cb = ttk.Combobox(nav, textvariable=_month_var, values=month_list,
                         width=4, state='readonly', font=("맑은 고딕",9))
    _m_cb.pack(side=tk.LEFT, padx=4)
    tk.Label(nav, text="월", bg=BG_NAV, fg=FG, font=("맑은 고딕",9)).pack(side=tk.LEFT)

    tk.Button(nav, text="›", bg=BG_NAV, fg=FG, bd=0, font=("맑은 고딕",11,"bold"),
              command=_next_month, cursor="hand2").pack(side=tk.LEFT, padx=2)
    tk.Button(nav, text="»", bg=BG_NAV, fg=FG, bd=0, font=("맑은 고딕",10,"bold"),
              command=_next_year, cursor="hand2").pack(side=tk.LEFT, padx=(2,8))

    def _on_year_select(e=None):
        nonlocal year
        try: year = int(_year_var.get()); _render()
        except (ValueError, TypeError): pass  # 비정상 입력 무시
    def _on_month_select(e=None):
        nonlocal month
        try: month = int(_month_var.get()); _render()
        except (ValueError, TypeError): pass  # 비정상 입력 무시
    _y_cb.bind('<<ComboboxSelected>>', _on_year_select)
    _m_cb.bind('<<ComboboxSelected>>', _on_month_select)

    # ── 요일 헤더 ────────────────────────────────────────
    hdr = tk.Frame(win, bg=BG)
    hdr.pack(fill=tk.X, padx=8, pady=(6,2))
    DAY_NAMES = ["일", "월", "화", "수", "목", "금", "토"]
    DAY_FG    = [SUN_FG, FG, FG, FG, FG, FG, SAT_FG]
    for i, (dn, df) in enumerate(zip(DAY_NAMES, DAY_FG)):
        tk.Label(hdr, text=dn, fg=df, bg=BG, font=("맑은 고딕",9,"bold"),
                 width=4).grid(row=0, column=i, padx=1)

    # ── 날짜 그리드 ──────────────────────────────────────
    body = tk.Frame(win, bg=BG)
    body.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

    def _render():
        for w in body.winfo_children():
            w.destroy()
        cal_obj = calendar.Calendar(calendar.SUNDAY)
        weeks = cal_obj.monthdayscalendar(year, month)
        for r, week in enumerate(weeks):
            for c_idx, day in enumerate(week):
                if day == 0:
                    tk.Label(body, text="", bg=BG, width=4).grid(row=r, column=c_idx, padx=1, pady=2)
                    continue
                is_today   = (year == _today.year and month == _today.month and day == _today.day)
                is_sunday  = (c_idx == 0)
                is_saturday= (c_idx == 6)
                _fg = SUN_FG if is_sunday else (SAT_FG if is_saturday else FG)
                _bg = TODAY_BG if is_today else BTN_BG
                _font = ("맑은 고딕", 9, "bold") if is_today else ("맑은 고딕", 9)
                btn = tk.Button(
                    body, text=str(day), width=4, bg=_bg, fg=_fg,
                    font=_font, bd=0, relief='flat', cursor='hand2',
                    activebackground=SEL_BG, activeforeground=SEL_FG,
                    command=lambda y=year, m=month, d=day: _on_day(y, m, d)
                )
                btn.grid(row=r, column=c_idx, padx=1, pady=2)
                def _on_enter(e, b=btn, bg=_bg): b.config(bg=BTN_HOV)
                def _on_leave(e, b=btn, bg=_bg): b.config(bg=bg)
                btn.bind("<Enter>", _on_enter)
                btn.bind("<Leave>", _on_leave)

    def _on_day(y: int, m: int, day: int):
        ymd = f"{y:04d}-{m:02d}-{day:02d}"
        try: on_choose(ymd)
        except Exception as e: logger.debug("날짜 선택 콜백 오류: %s", e)
        win.destroy()

    # ── 하단: 오늘 버튼 + 닫기 ──────────────────────────
    footer = tk.Frame(win, bg=BG_NAV, pady=6)
    footer.pack(fill=tk.X)

    def _goto_today():
        nonlocal year, month
        year, month = _today.year, _today.month
        _year_var.set(str(year)); _month_var.set(f"{month:02d}")
        _render()

    tk.Button(footer, text="오늘", bg=ACCENT, fg='#0F172A',
              font=("맑은 고딕",9,"bold"), bd=0, padx=12, pady=3,
              cursor='hand2', command=lambda: _on_day(_today.year, _today.month, _today.day)
              ).pack(side=tk.LEFT, padx=8)
    tk.Button(footer, text="이 달로", bg=BTN_BG, fg=FG,
              font=("맑은 고딕",9), bd=0, padx=10, pady=3,
              cursor='hand2', command=_goto_today
              ).pack(side=tk.LEFT, padx=2)
    tk.Button(footer, text="✕ 닫기", bg=BTN_BG, fg=FG_MUTED,
              font=("맑은 고딕",9), bd=0, padx=10, pady=3,
              cursor='hand2', command=win.destroy
              ).pack(side=tk.RIGHT, padx=8)

    _render()

    win.update_idletasks()
    # 부모 위치 기준으로 표시
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        win.geometry(f"+{px+20}+{py+40}")
    except Exception as _e:
        logger.debug(f"[tree_enhancements] 윈도우 위치 설정 실패: {_e}")
    try: win.focus_set()
    except Exception as e: logger.debug(f"Suppressed: {e}")


def apply_striped_rows(tree, is_dark: bool = False) -> None:
    """
    Treeview에 줄무늬 행 적용 (홀수/짝수 교대 배경)

    v5.5.3 patch_03: ThemeColors 참조로 테마 자동 대응
    """
    even_bg = ThemeColors.get('bg_card', is_dark)
    odd_bg  = ThemeColors.get('bg_secondary', is_dark) if not is_dark else '#1a2d42'
    # v9.0: foreground 명시 추가 (다크 테마 텍스트 가시성)
    row_fg  = ThemeColors.get('text_primary', is_dark)

    tree.tag_configure('even_row', background=even_bg, foreground=row_fg)
    tree.tag_configure('odd_row',  background=odd_bg,  foreground=row_fg)

    for idx, item_id in enumerate(tree.get_children('')):
        tag = 'even_row' if idx % 2 == 0 else 'odd_row'
        existing_tags = list(tree.item(item_id, 'tags') or ())
        existing_tags = [t for t in existing_tags if t not in ('even_row', 'odd_row')]
        existing_tags.append(tag)
        tree.item(item_id, tags=tuple(existing_tags))


class HeaderFilterBar:
    """
    Treeview 위에 컬럼별 필터 Combobox 바

    v5.5.3 patch_03: ttk 위젯 사용 → 테마 자동 대응
    
    Usage:
        filter_bar = HeaderFilterBar(parent, tree, columns, on_filter_callback)
        filter_bar.pack(fill='x')
    """

    def __init__(self, parent, tree, filter_columns: List[Tuple[str, str, int]],
                 on_filter: Callable, is_dark: bool = False,
                 date_from_var=None, date_to_var=None,
                 container_suffix_var=None, on_container_suffix_toggle=None):
        """
        Args:
            parent: 부모 위젯
            tree: Treeview 위젯
            filter_columns: [(col_id, label, width), ...]
            on_filter: 필터 변경 시 콜백
            is_dark: 하위 호환 (사용하지 않음, ttk가 자동 처리)
            date_from_var: (선택) 기간 시작일 StringVar — 있으면 STATUS와 초기화 사이에 기간 입력 추가
            date_to_var: (선택) 기간 종료일 StringVar
            container_suffix_var: (선택) 컨테이너 접미사 표시 BooleanVar
            on_container_suffix_toggle: (선택) 접미사 토글 콜백
        """
        import tkinter as tk
        from tkinter import ttk

        self.tree = tree
        self.on_filter = on_filter
        self.filter_vars = {}
        self.filter_combos = {}
        self._date_from_var = date_from_var
        self._date_to_var = date_to_var

        # ttk.Frame — 테마 색상 자동 적용
        self.frame = ttk.Frame(parent, padding=(5, 2))

        # "필터:" 라벨 (ttk)
        _lbl_filter = ttk.Label(self.frame, text="🔽 필터:",
                                font=('맑은 고딕', 10, 'bold'))
        _lbl_filter.pack(side='left', padx=(0, 8))
        self._apply_tooltip_safe(_lbl_filter, "컬럼별 조건을 선택하면 목록이 자동으로 필터됩니다. 빈 조건은 적용되지 않습니다.")

        for col_id, label, width in filter_columns:
            _lbl = ttk.Label(self.frame, text=f"{label}:", font=('맑은 고딕', 10))
            _lbl.pack(side='left', padx=(0, 2))
            self._apply_tooltip_safe(_lbl, self._get_column_tooltip(col_id, label))

            var = tk.StringVar(value="전체")
            combo = ttk.Combobox(self.frame, textvariable=var,
                                 values=["전체"], state="readonly",
                                 width=max(width // 10, 8))
            combo.pack(side='left', padx=(0, 8))
            combo.bind('<<ComboboxSelected>>', lambda e: self.on_filter())
            self._apply_tooltip_safe(combo, f"{label} 값으로 목록 필터. '전체'는 조건 없음.")

            self.filter_vars[col_id] = var
            self.filter_combos[col_id] = combo

        # v5.7.5: 기간(날짜 범위) — STATUS와 초기화 사이 한 줄에 배치 + 클릭 시 캘린더
        if date_from_var is not None and date_to_var is not None:
            _lbl_period = ttk.Label(self.frame, text="조회 기간 ", font=('맑은 고딕', 10))
            _lbl_period.pack(side='left', padx=(8, 2))
            self._apply_tooltip_safe(_lbl_period, "입력한 기간(시작일~종료일) 안의 데이터만 표시. 비우면 기간 조건 없음. 형식: YYYY-MM-DD")
            _e_from = ttk.Entry(self.frame, textvariable=date_from_var, width=12)
            _e_from.pack(side='left', padx=2)
            self._apply_tooltip_safe(_e_from, "시작일 (YYYY-MM-DD). 클릭하면 캘린더에서 선택. 비우면 제한 없음.")
            _btn_cal_from = ttk.Button(self.frame, text="📅", width=5,
                                       command=lambda: show_date_calendar(
                                           self.frame.winfo_toplevel(),
                                           date_from_var.get(),
                                           lambda ymd: (date_from_var.set(ymd), self.on_filter())))
            _btn_cal_from.pack(side='left', padx=(2, 4))
            self._apply_tooltip_safe(_btn_cal_from, "캘린더에서 시작일 선택")
            ttk.Label(self.frame, text=" ~ ").pack(side='left')
            _e_to = ttk.Entry(self.frame, textvariable=date_to_var, width=12)
            _e_to.pack(side='left', padx=2)
            self._apply_tooltip_safe(_e_to, "종료일 (YYYY-MM-DD). 클릭하면 캘린더에서 선택. 비우면 제한 없음.")
            _btn_cal_to = ttk.Button(self.frame, text="📅", width=5,
                                     command=lambda: show_date_calendar(
                                         self.frame.winfo_toplevel(),
                                         date_to_var.get(),
                                         lambda ymd: (date_to_var.set(ymd), self.on_filter())))
            _btn_cal_to.pack(side='left', padx=(2, 4))
            self._apply_tooltip_safe(_btn_cal_to, "캘린더에서 종료일 선택")
            # v8.1.8: 플레이스홀더 연결
            attach_date_placeholder(_e_from, date_from_var)
            attach_date_placeholder(_e_to,   date_to_var)
            # 입력란 클릭 시에도 캘린더 열기
            def _open_cal_from(_e=None):
                show_date_calendar(
                    self.frame.winfo_toplevel(),
                    date_from_var.get(),
                    lambda ymd: (date_from_var.set(ymd), self.on_filter()))
            def _open_cal_to(_e=None):
                show_date_calendar(
                    self.frame.winfo_toplevel(),
                    date_to_var.get(),
                    lambda ymd: (date_to_var.set(ymd), self.on_filter()))
            _e_from.bind('<Button-1>', _open_cal_from)
            _e_to.bind('<Button-1>', _open_cal_to)
            for _w in (_e_from, _e_to):
                _w.bind('<FocusOut>', lambda e: self.on_filter())
                _w.bind('<Return>', lambda e: self.on_filter())

        # 초기화 버튼
        _btn_reset = ttk.Button(self.frame, text="✖ 초기화", width=8,
                                command=self._reset_filters)
        _btn_reset.pack(side='left', padx=5)
        self._apply_tooltip_safe(_btn_reset, "모든 필터(컬럼 조건·기간)를 '전체'/비움으로 되돌리고 목록을 다시 불러옵니다.")

        # 컨테이너 접미사(-1,-2) 표시 체크박스
        if container_suffix_var is not None:
            _cb_suffix = ttk.Checkbutton(
                self.frame, text="📦 컨테이너 구분(-1,-2)",
                variable=container_suffix_var,
                command=on_container_suffix_toggle,
            )
            _cb_suffix.pack(side='left', padx=(10, 0))
            self._apply_tooltip_safe(_cb_suffix, "CONTAINER 열의 -1, -2 접미사 표시/숨김")

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def _reset_filters(self):
        for var in self.filter_vars.values():
            var.set("전체")
        if getattr(self, '_date_from_var', None) is not None:
            self._date_from_var.set("")
        if getattr(self, '_date_to_var', None) is not None:
            self._date_to_var.set("")
        self.on_filter()

    def _apply_tooltip_safe(self, widget, text: str) -> None:
        """툴팁 적용 (ui_constants.apply_tooltip 있으면 사용, 없으면 무시)"""
        try:
            from .ui_constants import apply_tooltip
            apply_tooltip(widget, text)
        except Exception as e:
            logger.debug(f"Suppressed: {e}")

    def _get_column_tooltip(self, col_id: str, label: str) -> str:
        """컬럼별 툴팁 문구"""
        _tips = {
            'lot_no': 'LOT 번호로 필터. 해당 LOT만 표시.',
            'sap_no': 'SAP 번호로 필터.',
            'bl_no': 'B/L 번호로 필터.',
            'container_no': '컨테이너 번호로 필터.',
            'product': '제품명으로 필터.',
            'status': '전체 / 판매가능 / 판매배정 / 판매화물 결정 / 출고 중 선택. 옆 숫자는 해당 개수.',
            'tonbag_status': '전체 / 판매가능 / 판매배정 / 판매화물 결정 / 출고 중 선택. 옆 숫자는 해당 톤백 개수.',
            'avail_bags': 'Avail = 현재 판매가능 톤백 개수. 출고 시 감소, 반품 시 증가.',
        }
        return _tips.get(col_id, f"{label} 값으로 목록을 제한합니다.")

    def get_filters(self) -> dict:
        """현재 필터 값 → {'col_id': 'value', ...}. '전체'는 제외."""
        result = {}
        for col_id, var in self.filter_vars.items():
            val = var.get()
            if val and val != "전체":
                result[col_id] = val
        return result

    def update_filter_values(self, col_id: str, values: List[str]) -> None:
        """특정 컬럼의 필터 드롭다운 값 업데이트"""
        if col_id in self.filter_combos:
            seen = set()
            str_vals = []
            for v in values:
                if v is None:
                    continue
                v_str = str(v).strip()
                if v_str and v_str not in seen:
                    seen.add(v_str)
                    str_vals.append(v_str)
            all_values = ["전체"] + sorted(str_vals)
            self.filter_combos[col_id]['values'] = all_values


class HeaderSortFilterRow:
    """
    차트(트리) 헤더 열마다 정렬(오름/내림) + 리스트 목록 상자(콤보)를 넣은 한 줄.
    상단 필터 메뉴 없이, 헤더에 통합.

    - 각 열: 컬럼명 + 정렬 표시(▲/▼) + 콤보(전체/값 목록)
    - 헤더 클릭 시 정렬, 콤보 선택 시 필터 적용
    - get_filters(), update_filter_values(), filter_vars, filter_combos — HeaderFilterBar와 호환
    """

    def __init__(self, parent, tree, columns: List[Tuple[str, str, int]],
                 on_filter: Callable, on_sort: Callable[[str], None],
                 is_dark: bool = False,
                 date_from_var=None, date_to_var=None,
                 container_suffix_var=None, on_container_suffix_toggle=None,
                 show_opt_row: bool = True,
                 opt_row_side: str = "below"):
        """
        Args:
            parent: 부모 위젯
            tree: Treeview (컬럼 폭 참조용)
            columns: [(col_id, label, width), ...] — 필터/정렬할 컬럼들
            on_filter: 필터 변경 시 콜백
            on_sort: 헤더 클릭 시 콜백 on_sort(col_id)
            date_from_var, date_to_var, container_suffix_var, on_container_suffix_toggle: 선택
            show_opt_row: False면 기간/초기화 행 미표시 (헤더 열+목록상자만)
            opt_row_side: "below"=필터 다음 줄, "right"=필터 줄 오른쪽(기간·초기화)
        """
        import tkinter as tk
        from tkinter import ttk

        self.tree = tree
        self.on_filter = on_filter
        self.on_sort = on_sort
        self.filter_vars = {}
        self.filter_combos = {}
        self._sort_labels = {}
        self._sort_column = None
        self._sort_reverse = False
        self._date_from_var = date_from_var
        self._date_to_var = date_to_var

        self.frame = ttk.Frame(parent, padding=(2, 2))
        _opt_right = (opt_row_side or "below").lower() == "right"
        if _opt_right:
            self._filter_row = ttk.Frame(self.frame)
            self._filter_row.pack(fill=tk.X)
            cell_parent = self._filter_row
            self._cells_frame = ttk.Frame(cell_parent)
            self._cells_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        else:
            self._filter_row = None
            self._cells_frame = ttk.Frame(self.frame)
            self._cells_frame.pack(fill=tk.X)

        # 필터 그룹 간 여백(픽셀) — 라벨·▲·콤보는 붙이고, 그룹(탭) 사이는 넓게
        _cell_pad_between = 26
        _cell_pad_first_left = 2

        for idx, (col_id, label, width) in enumerate(columns):
            cell = ttk.Frame(self._cells_frame)
            if idx == 0:
                cell.pack(side=tk.LEFT, fill=tk.Y, padx=(_cell_pad_first_left, _cell_pad_between))
            else:
                cell.pack(side=tk.LEFT, fill=tk.Y, padx=(0, _cell_pad_between))

            # 컬럼명 + 클릭 시 정렬
            lbl = ttk.Label(cell, text=label, font=('맑은 고딕', 10, 'bold'))
            lbl.pack(side=tk.LEFT, padx=(0, 0))
            lbl.bind('<Button-1>', lambda e, c=col_id: self._on_header_click(c))
            try:
                from .ui_constants import apply_tooltip
                apply_tooltip(lbl, "클릭: 오름차순/내림차순 정렬")
            except Exception:
                logger.debug("[SUPPRESSED] exception in tree_enhancements.py")  # noqa

            sort_lbl = ttk.Label(cell, text="", font=('맑은 고딕', 10), width=2)
            sort_lbl.pack(side=tk.LEFT, padx=(0, 0))
            sort_lbl.bind('<Button-1>', lambda e, c=col_id: self._on_header_click(c))
            self._sort_labels[col_id] = sort_lbl

            # 콤보 width=문자 단위. 트리 컬럼 픽셀(width)과 무관하게 //5(과대) 대신
            # LOT/SAP 등 10~12자·제품명은 상한 18자까지.
            _combo_w = min(max(width // 11, 11), 18)
            var = tk.StringVar(value="전체")
            combo = ttk.Combobox(
                cell, textvariable=var, values=["전체"], state="readonly",
                width=_combo_w,
            )
            combo.pack(side=tk.LEFT, padx=(0, 0))
            combo.bind('<<ComboboxSelected>>', lambda e: self.on_filter())
            self.filter_vars[col_id] = var
            self.filter_combos[col_id] = combo
            try:
                from .ui_constants import apply_tooltip
                apply_tooltip(combo, f"목록에서 선택해 {label} 필터")
            except Exception:
                logger.debug("[SUPPRESSED] exception in tree_enhancements.py")  # noqa

        # 하위호환: lot_combo, sap_combo 등 별칭
        self.lot_combo = self.filter_combos.get('lot_no')
        self.sap_combo = self.filter_combos.get('sap_no')
        self.bl_combo = self.filter_combos.get('bl_no')
        self.container_combo = self.filter_combos.get('container_no')
        self.product_combo = self.filter_combos.get('product')

        # 기간·컨테이너 구분 (선택) — show_opt_row=False면 미표시
        _opt_parent = self._filter_row if _opt_right else self.frame
        self._opt_frame = ttk.Frame(_opt_parent)
        if show_opt_row:
            if _opt_right:
                self._opt_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 4), pady=(0, 2))
            else:
                self._opt_frame.pack(fill=tk.X, pady=(4, 0))
        if show_opt_row and date_from_var is not None and date_to_var is not None:
            ttk.Label(self._opt_frame, text="조회 기간 ").pack(side=tk.LEFT, padx=(0, 2))
            ttk.Entry(self._opt_frame, textvariable=date_from_var, width=14).pack(side=tk.LEFT, padx=(2, 4))
            _btn_cal_from = ttk.Button(self._opt_frame, text="📅", width=5,
                command=lambda: show_date_calendar(
                    self.frame.winfo_toplevel(), date_from_var.get(),
                    lambda ymd: (date_from_var.set(ymd), self.on_filter())))
            _btn_cal_from.pack(side=tk.LEFT, padx=(2, 6))
            ttk.Label(self._opt_frame, text=" ~ ").pack(side=tk.LEFT, padx=(2, 2))
            ttk.Entry(self._opt_frame, textvariable=date_to_var, width=14).pack(side=tk.LEFT, padx=(2, 4))
            _btn_cal_to = ttk.Button(self._opt_frame, text="📅", width=5,
                command=lambda: show_date_calendar(
                    self.frame.winfo_toplevel(), date_to_var.get(),
                    lambda ymd: (date_to_var.set(ymd), self.on_filter())))
            _btn_cal_to.pack(side=tk.LEFT, padx=(2, 8))
        if show_opt_row and container_suffix_var is not None and on_container_suffix_toggle is not None:
            ttk.Checkbutton(
                self._opt_frame, text="📦 컨테이너 구분(-1,-2)",
                variable=container_suffix_var, command=on_container_suffix_toggle
            ).pack(side=tk.LEFT, padx=(0, 6))
        if show_opt_row:
            ttk.Button(self._opt_frame, text="✖ 초기화", width=8, command=self._reset_filters).pack(side=tk.LEFT, padx=(4, 0))

    def _on_header_click(self, col_id: str) -> None:
        prev = self._sort_column
        self._sort_column = col_id
        self._sort_reverse = not self._sort_reverse if prev == col_id else False
        self._update_sort_indicators()
        if self.on_sort:
            self.on_sort(col_id)

    def _update_sort_indicators(self) -> None:
        for cid, lbl in self._sort_labels.items():
            if cid == self._sort_column:
                lbl.config(text="▼" if self._sort_reverse else "▲")
            else:
                lbl.config(text="")

    def set_sort(self, col_id: str, reverse: bool) -> None:
        """외부에서 정렬 상태 동기화 시 호출."""
        self._sort_column = col_id
        self._sort_reverse = bool(reverse)
        self._update_sort_indicators()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()

    def _reset_filters(self) -> None:
        for var in self.filter_vars.values():
            var.set("전체")
        if getattr(self, '_date_from_var', None) is not None:
            self._date_from_var.set("")
        if getattr(self, '_date_to_var', None) is not None:
            self._date_to_var.set("")
        self.on_filter()

    def get_filters(self) -> dict:
        result = {}
        for col_id, var in self.filter_vars.items():
            val = var.get()
            if val and val != "전체":
                result[col_id] = val
        return result

    def update_filter_values(self, col_id: str, values: List[str]) -> None:
        if col_id not in self.filter_combos:
            return
        seen = set()
        str_vals = []
        for v in values:
            if v is None:
                continue
            v_str = str(v).strip()
            if v_str and v_str not in seen:
                seen.add(v_str)
                str_vals.append(v_str)
        self.filter_combos[col_id]['values'] = ["전체"] + sorted(str_vals)


class FooterTotalBar:
    """
    Treeview 하단 합계 바

    v5.5.3 patch_03: ttk 위젯 사용 → 테마 자동 대응.
    숫자 강조는 bold체로 표현 (배경색 대신).
    
    Usage:
        footer = FooterTotalBar(parent)
        footer.pack(fill='x')
        footer.update({'net_kg': 100000, 'balance_kg': 95000, 'rows': 200})
    """

    def __init__(self, parent, is_dark: bool = False):
        """
        Args:
            parent: 부모 위젯
            is_dark: 하위 호환 (사용하지 않음, ttk가 자동 처리)
        """
        from tkinter import ttk

        self.frame = ttk.Frame(parent, padding=(5, 4))
        self._labels = {}

        fields = [
            ('rows', '📊 행수:', '0'),
            ('net_kg', '📦 NET(Kg):', '0'),
            ('balance_kg', '💰 Balance(Kg):', '0'),
        ]

        for key, label_text, default in fields:
            ttk.Label(self.frame, text=label_text,
                      font=('맑은 고딕', 11, 'bold')).pack(side='left', padx=(10, 2))
            lbl = ttk.Label(self.frame, text=default,
                            font=('맑은 고딕', 12, 'bold'))
            lbl.pack(side='left', padx=(0, 15))
            self._labels[key] = lbl

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def update(self, data: dict) -> None:
        """합계 업데이트. data keys: rows, net_kg, balance_kg"""
        for key, lbl in self._labels.items():
            val = data.get(key, 0)
            if isinstance(val, (int, float)):
                lbl.config(text=f"{val:,.0f}")
            else:
                lbl.config(text=str(val))


def _safe_float(val) -> float:
    """문자열에서 숫자만 추출해 float으로. 콤마·공백 제거."""
    if val is None:
        return 0.0
    s = str(val).strip().replace(",", "").replace(" ", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


class TreeviewTotalFooter:
    """
    Treeview 하단 총합 바 — 합계 가능한 숫자 컬럼만 하단에 표시.
    v8.1.8: 폰트 13pt + 강조색 + 상단 구분선으로 시인성 개선.

    Usage:
        footer = TreeviewTotalFooter(parent, tree, summable_column_ids=['current_weight','net_weight',...])
        footer.pack(fill='x')
        # 데이터 로드 후
        footer.update_totals()
    """

    def __init__(self, parent, tree, summable_column_ids: List[str],
                 column_display_names: Optional[dict] = None,
                 column_formats: Optional[Dict[str, str]] = None):
        """
        Args:
            parent: 부모 위젯 (tree와 형제로 pack될 frame)
            tree: ttk.Treeview
            summable_column_ids: 합계할 컬럼 id 목록 (tree의 columns와 동일한 id)
            column_display_names: {col_id: "표시명"} — 없으면 tree.heading(col_id) 사용
            column_formats: {col_id: "포맷"} — 합계 표시 포맷 (예: {'qty_mt': ',.3f'}). 없으면 ',.0f'
        """
        import tkinter as tk

        self.tree = tree
        self.summable_column_ids = [c for c in summable_column_ids if c]
        self.column_display_names = column_display_names or {}
        self.column_formats = column_formats or {}

        _d = is_dark()
        # v8.1.8: 배경을 약간 다르게 — footer 영역 시각적 분리
        _bg     = ThemeColors.get('statusbar_bg', _d)   # 사이드바와 같은 진한 배경
        # 눈에 띄는 강조색: 다크=주황(#FF8C00), 라이트=딥블루(#1a56db)
        _accent = '#00E5A0' if _d else '#0369a1'  # v8.1.9: 기동님 승인 색상
        # 구분선 색
        _border = '#00E5A0' if _d else '#0369a1'

        # 상단 구분선 (2px 강조색 바)
        self.frame = tk.Frame(parent, bg=_bg, highlightthickness=0)
        tk.Frame(self.frame, bg=_border, height=2).pack(fill='x', side='top')

        # 내용 영역
        _inner = tk.Frame(self.frame, bg=_bg, padx=10, pady=5)
        _inner.pack(fill='x', side='top')

        # 좌측 아이콘 라벨
        tk.Label(
            _inner, text='Σ', bg=_bg, fg=_accent,
            font=('맑은 고딕', 14, 'bold'),
        ).pack(side='left', padx=(0, 8))

        # 합계 텍스트 라벨 — 13pt bold, 강조색
        self._label_var = tk.Label(
            _inner,
            text='',
            font=('맑은 고딕', 13, 'bold'),
            bg=_bg,
            fg=_accent,
            anchor='w',
        )
        self._label_var.pack(side='left', fill='x', expand=True)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def update_totals(self) -> None:
        """Tree 내용을 읽어 건수 + 합계 가능 컬럼 합산 후 하단 라벨 갱신. 필터 적용된 행만 반영."""
        if not self._label_var:
            return
        children = self.tree.get_children('')
        count = len(children)
        parts = [f'건수: {count:,}']
        if not self.summable_column_ids:
            self._label_var.config(text='   |   '.join(parts))
            return
        cols = list(self.tree['columns'])
        if not cols:
            self._label_var.config(text='   |   '.join(parts))
            return
        col_index = {c: i for i, c in enumerate(cols)}
        sums = {c: 0.0 for c in self.summable_column_ids if c in col_index}
        for item_id in children:
            try:
                vals = self.tree.item(item_id, 'values')
                if not vals:
                    continue
                for c in sums:
                    idx = col_index[c]
                    if idx < len(vals):
                        sums[c] += _safe_float(vals[idx])
            except (TypeError, IndexError, Exception):
                continue
        for c in self.summable_column_ids:
            if c not in sums:
                continue
            name = self.column_display_names.get(c) or (
                self.tree.heading(c, 'text') if c in cols else c)
            fmt = self.column_formats.get(c, ',.0f')
            parts.append(f'{name}: {sums[c]:{fmt}}')
        self._label_var.config(text='   |   '.join(parts))


# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# v8.6.3: 공통 날짜 범위 입력 바 — 모든 탭/다이얼로그 표준 UI
# 사용: frame, from_var, to_var = make_date_range_bar(parent, on_apply)
# ══════════════════════════════════════════════════════════════════════
def make_date_range_bar(
    parent,
    on_apply_callback,
    label_from: str = "시작일",
    label_to:   str = "종료일",
    default_from: str = "",
    default_to:   str = "",
    show_clear:   bool = True,
) -> tuple:
    """v8.6.3: 표준 날짜 범위 입력 바 생성.

    모든 날짜 기간 입력 메뉴에서 동일한 UI/UX 보장:
      [시작일] 📅  ~  [종료일] 📅  [조회]  [초기화]

    - 📅 버튼 클릭 → 캘린더 팝업
    - YYYY-MM-DD 직접 타이핑 가능
    - 빈값 = 전체 기간 (제한 없음)
    - 오늘 날짜 초기값 설정 가능

    Args:
        parent:            부모 위젯
        on_apply_callback: 조회 버튼 클릭 시 호출 (인자 없음)
        label_from/to:     시작/종료 라벨 텍스트
        default_from/to:   초기값 ('' = 비워두기, 'today' = 오늘 날짜)
        show_clear:        초기화 버튼 표시 여부

    Returns:
        (frame, from_var, to_var)
    """
    import tkinter as tk
    from tkinter import ttk
    from datetime import date as _date

    def _resolve_default(val: str) -> str:
        if val == 'today':
            return _date.today().strftime('%Y-%m-%d')
        return val or ''

    from_var = tk.StringVar(value=_resolve_default(default_from))
    to_var   = tk.StringVar(value=_resolve_default(default_to))

    frame = ttk.Frame(parent)

    # ── 시작일 ──
    ttk.Label(frame, text=f"{label_from}:").pack(side=tk.LEFT, padx=(0, 2))
    e_from = ttk.Entry(frame, textvariable=from_var, width=11)
    e_from.pack(side=tk.LEFT, padx=(0, 1))
    attach_date_placeholder(e_from, from_var)

    # 📅 캘린더 버튼 (시작일)
    def _open_from():
        show_date_calendar(
            frame,
            from_var.get() or _date.today().strftime('%Y-%m-%d'),
            lambda ymd: (from_var.set(ymd), on_apply_callback()),
        )
    ttk.Button(frame, text="📅", width=3, command=_open_from).pack(side=tk.LEFT, padx=(0, 6))

    ttk.Label(frame, text="~").pack(side=tk.LEFT, padx=4)

    # ── 종료일 ──
    ttk.Label(frame, text=f"{label_to}:").pack(side=tk.LEFT, padx=(6, 2))
    e_to = ttk.Entry(frame, textvariable=to_var, width=11)
    e_to.pack(side=tk.LEFT, padx=(0, 1))
    attach_date_placeholder(e_to, to_var)

    # 📅 캘린더 버튼 (종료일)
    def _open_to():
        show_date_calendar(
            frame,
            to_var.get() or _date.today().strftime('%Y-%m-%d'),
            lambda ymd: (to_var.set(ymd), on_apply_callback()),
        )
    ttk.Button(frame, text="📅", width=3, command=_open_to).pack(side=tk.LEFT, padx=(0, 6))

    # ── 조회 버튼 ──
    ttk.Button(frame, text="🔍 조회", width=7,
               command=on_apply_callback).pack(side=tk.LEFT, padx=4)

    # ── 초기화 버튼 ──
    if show_clear:
        def _clear():
            from_var.set('')
            to_var.set('')
            on_apply_callback()
        ttk.Button(frame, text="✕ 초기화", width=7, command=_clear).pack(side=tk.LEFT, padx=2)

    # Enter 키 조회 연결
    e_from.bind('<Return>', lambda _: on_apply_callback())
    e_to.bind('<Return>',   lambda _: on_apply_callback())

    return frame, from_var, to_var

# v8.1.8: 공통 기간 필터 유틸 — DateRangeFilter
# ══════════════════════════════════════════════════════════════════════
import re as _re

def parse_date_range(from_str: str, to_str: str):
    """
    기간 입력값 정규화.

    규칙:
      - 둘 다 빈 문자열  → (None, None)  → 전체 기간 조회
      - from만 있음      → (from, None)  → from 이후 전체
      - to만 있음        → (None, to)    → to 이전 전체
      - 둘 다 있음       → (from, to)    → 해당 기간만

    반환: (date_from: str|None, date_to: str|None)
      - 값이 있으면 'YYYY-MM-DD' 형식 보장
      - 파싱 실패 시 None 반환 (전체 조회 유지)
    """
    def _normalize(s: str):
        if not s:
            return None
        s = s.strip().replace('/', '-').replace('.', '-')
        # YYYYMMDD → YYYY-MM-DD
        if _re.match(r'^\d{8}$', s):
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        # YYYY-MM-DD 확인
        if _re.match(r'^\d{4}-\d{2}-\d{2}$', s):
            return s
        # YYYY-M-D → YYYY-MM-DD
        m = _re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', s)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return None  # 파싱 실패 → None (전체 조회)

    return _normalize(from_str), _normalize(to_str)


def build_date_sql(
    date_col: str,
    from_str: str,
    to_str: str,
    include_null: bool = False,
) -> tuple:
    """
    기간 필터 SQL 조각 + 파라미터 반환.

    Args:
        date_col:     DB 컬럼명. 예: 's.sold_date', 'i.stock_date'
        from_str:     시작일 문자열 (빈 문자열 허용)
        to_str:       종료일 문자열 (빈 문자열 허용)
        include_null: True → 날짜 NULL 행도 포함 (OR ... IS NULL)

    Returns:
        (sql_fragment: str, params: list)
        - sql_fragment가 빈 문자열이면 조건 없음 (전체 기간)

    사용 예:
        sql_frag, params = build_date_sql('s.sold_date', date_from, date_to)
        if sql_frag:
            base_sql += f' AND {sql_frag}'
            base_params.extend(params)
    """
    d_from, d_to = parse_date_range(from_str, to_str)

    parts = []
    params = []

    if d_from:
        null_part = f" OR {date_col} IS NULL" if include_null else ""
        parts.append(f"({date_col} >= ?{null_part})")
        params.append(d_from)

    if d_to:
        # 종료일은 해당 날 23:59:59까지 포함
        d_to_end = d_to + ' 23:59:59'
        null_part = f" OR {date_col} IS NULL" if include_null else ""
        parts.append(f"({date_col} <= ?{null_part})")
        params.append(d_to_end)

    sql_fragment = " AND ".join(parts)
    return sql_fragment, params


def apply_date_filter_to_rows(
    rows: list,
    date_key: str,
    from_str: str,
    to_str: str,
) -> list:
    """
    이미 가져온 row 목록을 파이썬에서 기간 필터링.
    (SQL 쿼리 수정이 어려운 경우 사용)

    Args:
        rows:      dict 목록
        date_key:  행에서 날짜를 꺼낼 키 이름
        from_str:  시작일 문자열
        to_str:    종료일 문자열

    Returns:
        필터링된 rows. 둘 다 비어있으면 원본 그대로 반환.
    """
    from datetime import date as _date, datetime as _datetime

    d_from, d_to = parse_date_range(from_str, to_str)

    # 둘 다 없으면 전체 반환 (핵심 원칙)
    if not d_from and not d_to:
        return rows

    def _to_date(val):
        if not val:
            return None
        if isinstance(val, _date):
            return val
        s = str(val).strip()[:10]
        try:
            return _datetime.strptime(s, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    from_d = _to_date(d_from)
    to_d   = _to_date(d_to)

    result = []
    for row in rows:
        val = row.get(date_key) if isinstance(row, dict) else None
        row_d = _to_date(val)
        if row_d is None:
            # 날짜 없는 행은 기간 입력이 있어도 포함
            result.append(row)
            continue
        if from_d and row_d < from_d:
            continue
        if to_d and row_d > to_d:
            continue
        result.append(row)
    return result


# ══════════════════════════════════════════════════════════════════════
# v8.1.8: 공통 기간 필터 유틸 — parse_date_range / build_date_sql
#          / apply_date_filter_to_rows
# ══════════════════════════════════════════════════════════════════════
import re as _re_dt


def parse_date_range(from_str: str, to_str: str):
    """
    기간 입력값 정규화.

    핵심 원칙:
      둘 다 빈 문자열 → (None, None) → 전체 기간 조회 (조건 없음)
      from 만 입력    → (from, None) → from 이후 전체
      to 만 입력      → (None, to)   → to 이전 전체
      둘 다 입력      → (from, to)   → 해당 기간만

    반환: (date_from: str|None, date_to: str|None) — 'YYYY-MM-DD' 보장
    파싱 실패한 값은 None 처리 (전체 조회 유지, 오류 표시 없음)
    """
    def _norm(s: str):
        if not s:
            return None
        s = s.strip().replace('/', '-').replace('.', '-')
        if _re_dt.match(r'^\d{8}$', s):          # YYYYMMDD
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        if _re_dt.match(r'^\d{4}-\d{2}-\d{2}$', s):
            return s
        m = _re_dt.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', s)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return None

    return _norm(from_str), _norm(to_str)


def build_date_sql(date_col: str, from_str: str, to_str: str,
                   include_null: bool = False) -> tuple:
    """
    기간 필터 SQL 조각 + 파라미터 반환.

    Args:
        date_col:     DB 컬럼명. 예: 's.sold_date'
        from_str:     시작일 문자열 (빈 문자열 허용)
        to_str:       종료일 문자열 (빈 문자열 허용)
        include_null: True → NULL 날짜 행도 포함

    Returns:
        (sql_fragment: str, params: list)
        sql_fragment 가 빈 문자열 → 조건 없음 (전체 기간)

    사용법:
        frag, p = build_date_sql('s.sold_date', date_from, date_to)
        if frag:
            sql += f' AND {frag}'
            params.extend(p)
    """
    d_from, d_to = parse_date_range(from_str, to_str)
    parts, params = [], []

    if d_from:
        np = f" OR {date_col} IS NULL" if include_null else ""
        parts.append(f"({date_col} >= ?{np})")
        params.append(d_from)

    if d_to:
        np = f" OR {date_col} IS NULL" if include_null else ""
        parts.append(f"({date_col} <= ?{np})")
        params.append(d_to + ' 23:59:59')

    return " AND ".join(parts), params


def apply_date_filter_to_rows(rows: list, date_key: str,
                              from_str: str, to_str: str) -> list:
    """
    파이썬 레벨 기간 필터링 (SQL 수정 불가한 경우 사용).

    핵심 원칙: 둘 다 빈 문자열이면 원본 그대로 반환 (전체 기간).
    날짜 파싱 실패한 행은 항상 포함.
    """
    from datetime import date as _date, datetime as _dt_cls

    d_from, d_to = parse_date_range(from_str, to_str)
    if not d_from and not d_to:           # 기간 미입력 → 전체 반환
        return rows

    def _to_date(val):
        if not val:
            return None
        if isinstance(val, _date):
            return val
        try:
            return _dt_cls.strptime(str(val).strip()[:10], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    from_d = _to_date(d_from)
    to_d   = _to_date(d_to)
    result = []
    for row in rows:
        rv = row.get(date_key) if isinstance(row, dict) else None
        rd = _to_date(rv)
        if rd is None:          # 날짜 없는 행은 항상 포함
            result.append(row)
            continue
        if from_d and rd < from_d:
            continue
        if to_d and rd > to_d:
            continue
        result.append(row)
    return result


# ══════════════════════════════════════════════════════════════════════
# v8.1.8: 날짜 Entry 플레이스홀더 유틸
# ══════════════════════════════════════════════════════════════════════

def attach_date_placeholder(entry_widget, string_var,
                             placeholder: str = 'YYYY-MM-DD',
                             placeholder_fg: str = '#aaaaaa',
                             normal_fg: str = None) -> None:
    """
    tkinter Entry에 날짜 플레이스홀더 동작 연결.

    동작:
      - StringVar 값이 비어있으면 → Entry 배경에 회색 힌트 텍스트 표시
      - 사용자가 클릭(포커스인)하면 → 힌트 텍스트 제거 + 정상 색상
      - 포커스를 잃으면(포커스아웃) → 비어있으면 다시 힌트 표시
      - 실제 StringVar 값은 절대 오염하지 않음 (힌트는 보여주기만)

    Args:
        entry_widget:   ttk.Entry 또는 tk.Entry 위젯
        string_var:     연결된 tk.StringVar
        placeholder:    힌트 텍스트 (기본: 'YYYY-MM-DD')
        placeholder_fg: 힌트 텍스트 색상
        normal_fg:      입력 시 텍스트 색상 (None이면 위젯 기본색 유지)
    """
    import tkinter as _tk

    # 정상 fg 색상 결정
    try:
        _normal_fg = normal_fg or entry_widget.cget('foreground') or '#000000'
    except Exception:
        _normal_fg = normal_fg or '#000000'

    _is_showing_placeholder = [False]

    def _show_placeholder():
        """StringVar가 비어있으면 플레이스홀더 표시."""
        if string_var.get().strip() == '':
            try:
                entry_widget.config(foreground=placeholder_fg)
                # StringVar를 오염하지 않고 직접 위젯에 텍스트 삽입
                entry_widget.delete(0, 'end')
                entry_widget.insert(0, placeholder)
            except Exception as e:
                logger.warning(f'[UI] tree_enhancements: {e}')
            _is_showing_placeholder[0] = True
        else:
            _is_showing_placeholder[0] = False

    def _on_focus_in(event=None):
        """포커스 받으면 플레이스홀더 제거."""
        if _is_showing_placeholder[0]:
            try:
                entry_widget.delete(0, 'end')
                entry_widget.config(foreground=_normal_fg)
            except Exception as e:
                logger.warning(f'[UI] tree_enhancements: {e}')
            _is_showing_placeholder[0] = False

    def _on_focus_out(event=None):
        """포커스 잃으면 빈 경우 플레이스홀더 복원."""
        current = entry_widget.get().strip()
        if current == '' or current == placeholder:
            string_var.set('')          # StringVar 깨끗하게 유지
            _show_placeholder()
        else:
            try:
                entry_widget.config(foreground=_normal_fg)
            except Exception as e:
                logger.warning(f'[UI] tree_enhancements: {e}')
            _is_showing_placeholder[0] = False

    entry_widget.bind('<FocusIn>',  _on_focus_in,  add='+')
    entry_widget.bind('<FocusOut>', _on_focus_out, add='+')

    # 초기 상태: 비어있으면 즉시 플레이스홀더 표시
    _show_placeholder()
