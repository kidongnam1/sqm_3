"""
총괄 화물 리스트 탭 — 상태별 화물만 표시 (전체/판매가능/판매배정/판매화물 결정/출고)
- 판매배정 = 고객 Allocation(RESERVED) 테이블에 있는 LOT만
- 판매가능 = RESERVED/PICKED/SOLD 없는 LOT만
"""
from engine_modules.constants import STATUS_AVAILABLE, STATUS_PICKED, STATUS_RESERVED, STATUS_SOLD
import logging

from ..utils.constants import BOTH, LEFT, YES, X, ttk
from ..utils.ui_constants import is_dark, Spacing, ThemeColors, get_status_display

logger = logging.getLogger(__name__)

# 재고 탭과 동일 컬럼 정의 (정렬 헤더 라벨용)
CARGO_OVERVIEW_COLUMNS = [
    ('row_num',          'No.',           50, 'center', True),
    ('lot_no',           'LOT NO',       130, 'center', True),
    ('sap_no',           'SAP NO',       120, 'center', True),
    ('bl_no',            'BL NO',        140, 'center', True),
    ('product',          'PRODUCT',      170, 'w',      True),
    ('status',           'STATUS',        95, 'center', True),
    ('current_weight',   'Balance(Kg)',  105, 'e',      True),
    ('net_weight',       'NET(Kg)',      105, 'e',      True),
    ('container_no',     'CONTAINER',    135, 'center', True),
    ('mxbg_pallet',      'MXBG',          70, 'center', True),
    ('avail_bags',       'Avail',          65, 'e',      True),
    ('salar_invoice_no', 'INVOICE NO',   110, 'center', True),
    ('ship_date',        'SHIP DATE',     95, 'center', True),
    ('arrival_date',     'ARRIVAL',       95, 'center', True),
    ('con_return',       'CON RETURN',    95, 'center', True),
    ('free_time',        'FREE TIME',     80, 'center', True),
    ('warehouse',        'WH',            85, 'w',      True),
    ('customs',          'CUSTOMS',       90, 'center', True),
    ('initial_weight',   'Inbound(Kg)',  105, 'e',      True),
    ('outbound_weight',  'Outbound(Kg)', 105, 'e',      True),
]

STATUS_FILTER_MAP = {
    '전체': None,
    '판매가능': STATUS_AVAILABLE,
    '판매배정': STATUS_RESERVED,
    '판매화물 결정': STATUS_PICKED,
    '출고': STATUS_SOLD,
}


def _cargo_status_from_combo_value(raw: str):
    """콤보 표시값(예: '판매배정 (3)')에서 DB 상태값(예: RESERVED) 추출. 전체면 None."""
    if not (raw and raw.strip()):
        return None
    raw = raw.strip()
    label = raw.split(" (")[0].strip() if " (" in raw else raw
    return STATUS_FILTER_MAP.get(label)


def _cargo_date_in_range(row: dict, date_from: str, date_to: str) -> bool:
    """행의 arrival_date / stock_date / ship_date가 기간 안에 있으면 True.
    v8.1.8: parse_date_range 적용 — 둘 다 비면 전체 기간(True).
    """
    # 공통 유틸로 정규화 — 빈 문자열이면 None 반환
    try:
        from gui_app_modular.utils.tree_enhancements import parse_date_range
        d_from_n, d_to_n = parse_date_range(date_from or '', date_to or '')
    except Exception:
        d_from_n, d_to_n = None, None

    # 둘 다 없으면 전체 기간
    if not d_from_n and not d_to_n:
        return True

    d_str = (row.get('arrival_date') or row.get('stock_date') or
             row.get('ship_date') or '').strip()[:10]
    if not d_str:
        return True
    try:
        from datetime import datetime
        d = datetime.strptime(d_str, '%Y-%m-%d').date()
        if d_from_n:
            f = datetime.strptime(d_from_n, '%Y-%m-%d').date()
            if d < f:
                return False
        if d_to_n:
            t = datetime.strptime(d_to_n, '%Y-%m-%d').date()
            if d > t:
                return False
        return True
    except (ValueError, TypeError):
        return True


def _sync_cargo_combo_to_values(var, cur_val: str, new_values: list) -> None:
    """콤보 values 갱신 후 선택 라벨 유지: 같은 라벨의 새 항목(새 개수)으로 var 설정."""
    if not cur_val or not new_values:
        return
    label = cur_val.split(" (")[0].strip() if " (" in cur_val else cur_val
    for v in new_values:
        if v.strip().startswith(label + " ("):
            var.set(v)
            return


try:
    from ..utils.sort_utils import make_sort_key
except ImportError:
    def make_sort_key(col, numeric_cols):
        def _key(item):
            v = item[0]
            if col in numeric_cols:
                try: return (0, float(v))
                except Exception: return (1, str(v))
            return (0, str(v).lower())
        return _key


class CargoOverviewTabMixin:
    """총괄 화물 리스트 탭 — 상태 필터로 해당 화물만 표시"""

    def _setup_cargo_overview_tab(self) -> None:
        import tkinter as tk

        from ..utils.constants import VERTICAL
        from ..utils.tree_enhancements import TreeviewTotalFooter, apply_striped_rows
        from ..utils.ui_constants import apply_tooltip

        _is_dark = is_dark()
        frame = self.tab_cargo_overview

        # 탭 헤더 (v7.6.0 심플화)
        try:
            from ..utils.ui_constants import make_tab_header
            make_tab_header(frame, "📋 총괄 재고 리스트",
                            status_color='#8b5cf6', is_dark=_is_dark)
        except Exception:
            logger.debug("[SUPPRESSED] exception in cargo_overview_tab.py")  # noqa

        # 상단: 기준 (총 입고 / 현재 재고) + 상태 필터
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.SM))
        ttk.Label(filter_frame, text="기준:", font=('맑은 고딕', 10, 'bold')).pack(side=LEFT, padx=(0, Spacing.XS))
        self._cargo_scope_var = tk.StringVar(value="all")
        ttk.Radiobutton(filter_frame, text="총 입고 기준", variable=self._cargo_scope_var, value="all",
                        command=self._on_cargo_scope_change).pack(side=LEFT, padx=(0, Spacing.SM))
        ttk.Radiobutton(filter_frame, text="현재 재고 기준", variable=self._cargo_scope_var, value="current",
                        command=self._on_cargo_scope_change).pack(side=LEFT, padx=(0, Spacing.SM))
        apply_tooltip(filter_frame.winfo_children()[-1], "현재 재고 기준: 전체=판매가능+판매배정+판매화물 결정(출고 제외)")
        ttk.Label(filter_frame, text="  상태:", font=('맑은 고딕', 10, 'bold')).pack(side=LEFT, padx=(Spacing.SM, Spacing.XS))
        self._cargo_status_var = tk.StringVar(value="전체 (0)")
        self._cargo_status_combo = ttk.Combobox(
            filter_frame, textvariable=self._cargo_status_var,
            values=["전체 (0)", "판매가능 (0)", "판매배정 (0)", "판매화물 결정 (0)", "출고 (0)"],
            state="readonly", width=20
        )
        self._cargo_status_combo.pack(side=LEFT, padx=(0, Spacing.SM))
        self._cargo_status_combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_cargo_overview())
        apply_tooltip(self._cargo_status_combo, "해당 상태의 화물만 표시. 현재 재고 기준에서는 출고 옵션 없음.")

        # v8.6.3: 공통 날짜 범위 바 통일 적용
        try:
            from ..utils.tree_enhancements import make_date_range_bar, bind_period_vars_debounced
            _date_bar, self._cargo_date_from_var, self._cargo_date_to_var = \
                make_date_range_bar(filter_frame, self._refresh_cargo_overview)
            _date_bar.pack(side=LEFT, padx=(Spacing.SM, 0))
            bind_period_vars_debounced(
                frame, self._cargo_date_from_var, self._cargo_date_to_var,
                self._refresh_cargo_overview, delay_ms=350,
            )
        except Exception as _e:
            logger.warning(f'[UI] cargo_overview make_date_range_bar: {_e}')
            self._cargo_date_from_var = tk.StringVar()
            self._cargo_date_to_var   = tk.StringVar()

        ttk.Button(filter_frame, text="🔄 새로고침", command=self._refresh_cargo_overview).pack(side=LEFT, padx=Spacing.SM)
        apply_tooltip(filter_frame.winfo_children()[-1], "목록 다시 불러오기")

        # 트리뷰
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)
        all_col_ids = [c[0] for c in CARGO_OVERVIEW_COLUMNS]
        import tkinter.font as tkfont
        _style = ttk.Style()
        _font = tkfont.Font(family='맑은 고딕', size=11)
        _head_font = tkfont.Font(family='맑은 고딕', size=11, weight='bold')
        _row_h = _font.metrics('linespace') + 6
        _tv_bg = ThemeColors.get('bg_card', _is_dark)
        _tv_fg = ThemeColors.get('text_primary', _is_dark)
        _tv_head_bg = ThemeColors.get('bg_secondary', _is_dark)
        _tv_head_fg = ThemeColors.get('text_primary', _is_dark)
        _style.configure('Cargo.Treeview', font=_font, rowheight=_row_h, background=_tv_bg, foreground=_tv_fg, fieldbackground=_tv_bg)
        _style.configure(
            'Cargo.Treeview.Heading',
            font=_head_font, background=_tv_head_bg, foreground=_tv_head_fg,
            anchor='center',
        )
        # v6.1.1: 선택/비선택 행 foreground 명시 (테마 가시성)
        _style.map('Cargo.Treeview',
                   background=[('selected', ThemeColors.get('tree_select_bg', _is_dark))],
                   foreground=[
                       ('selected', ThemeColors.get('tree_select_fg', _is_dark)),
                       ('!selected', _tv_fg),
                   ])

        self.tree_cargo_overview = ttk.Treeview(
            tree_frame, columns=all_col_ids, show="headings", height=22,
            selectmode='extended', style='Cargo.Treeview'
        )
        self._cargo_sort_column = None
        self._cargo_sort_reverse = False
        for col_id, label, width, anchor, _ in CARGO_OVERVIEW_COLUMNS:
            self.tree_cargo_overview.heading(
                col_id, text=label, anchor='center',
                command=lambda c=col_id: self._sort_cargo_treeview(c)
            )
            self.tree_cargo_overview.column(col_id, width=width, anchor=anchor, stretch=True)
        scroll = tk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree_cargo_overview.yview)
        scroll_x = tk.Scrollbar(tree_frame, orient='horizontal', command=self.tree_cargo_overview.xview)
        self.tree_cargo_overview.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        self.tree_cargo_overview.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll.pack(side=tk.RIGHT, fill='y')
        scroll_x.pack(side=tk.BOTTOM, fill='x')
        apply_striped_rows(self.tree_cargo_overview, _is_dark)
        ThemeColors.configure_tags(self.tree_cargo_overview, _is_dark)

        # 하단 합계
        summable = ['current_weight', 'net_weight', 'initial_weight', 'outbound_weight']
        self._cargo_footer = TreeviewTotalFooter(
            frame, self.tree_cargo_overview, summable,
            column_display_names={c[0]: c[1] for c in CARGO_OVERVIEW_COLUMNS}
        )
        self._cargo_footer.pack(fill=X)
        self._cargo_header_filter = {}
        self._cargo_detached = []
        self.tree_cargo_overview.bind('<Button-3>', self._on_cargo_tree_right_click)
        self._refresh_cargo_overview()

    def _sort_cargo_treeview(self, col: str) -> None:
        """총괄 화물 트리 헤더 클릭 시 오름차순/내림차순 정렬"""
        tree = self.tree_cargo_overview
        if self._cargo_sort_column == col:
            self._cargo_sort_reverse = not self._cargo_sort_reverse
        else:
            self._cargo_sort_column = col
            self._cargo_sort_reverse = False
        items = [(tree.set(item, col), item) for item in tree.get_children('')]
        numeric_cols = ['net_weight', 'current_weight', 'initial_weight', 'mxbg_pallet', 'free_time', 'row_num']
        sort_key = make_sort_key(col, numeric_cols)  # v7.0.0 [REFACTOR-1]
        items.sort(key=sort_key, reverse=self._cargo_sort_reverse)
        for idx, (_, item) in enumerate(items):
            tree.move(item, '', idx)
        arrow = " ▼" if self._cargo_sort_reverse else " ▲"
        for c_id, c_label, _, _, _ in CARGO_OVERVIEW_COLUMNS:
            tree.heading(
                c_id,
                text=f"{c_label}{arrow}" if c_id == col else c_label,
                anchor='center',
            )

    def _on_cargo_tree_right_click(self, event) -> None:
        """총괄 화물 트리 우클릭 → 컨텍스트 메뉴 (LOT 복사, 새로고침)"""
        import tkinter as tk
        item_id = self.tree_cargo_overview.identify_row(event.y)
        if not item_id:
            return
        self.tree_cargo_overview.selection_set(item_id)
        values = self.tree_cargo_overview.item(item_id, 'values')
        if not values:
            return
        cols = [c[0] for c in CARGO_OVERVIEW_COLUMNS]
        lot_no = ''
        if 'lot_no' in cols and len(values) > cols.index('lot_no'):
            lot_no = str(values[cols.index('lot_no')]).strip()
        menu = tk.Menu(self.root, tearoff=0)
        if lot_no:
            menu.add_command(label=f"📋 LOT 복사: {lot_no}", command=lambda: self._copy_cargo_lot(lot_no))
            menu.add_separator()
            if hasattr(self, '_show_lot_detail_popup'):
                menu.add_command(label="📊 LOT 상세", command=lambda: self._show_lot_detail_popup(lot_no))
                menu.add_separator()

        # v7.0: 공통 기능 추가 (선택 영역 복사/저장)
        if hasattr(self, '_copy_selection_to_clipboard'):
            menu.add_command(label="📋 선택 영역 복사 (Copy)", command=lambda: self._copy_selection_to_clipboard(self.tree_cargo_overview))
        if hasattr(self, '_export_selection_to_excel'):
            menu.add_command(label="📥 선택 영역 Excel 저장", command=lambda: self._export_selection_to_excel(self.tree_cargo_overview))
        menu.add_separator()

        menu.add_command(label="🔄 새로고침", command=self._refresh_cargo_overview)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_cargo_lot(self, text: str) -> None:
        """클립보드에 LOT 번호 복사"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        if hasattr(self, '_log'):
            self._log(f"📋 클립보드 복사: {text}")

    def _on_cargo_scope_change(self) -> None:
        """총 입고 기준 ↔ 현재 재고 기준 전환 시 상태 콤보 옵션 갱신 후 새로고침"""
        self._refresh_cargo_overview()

    def _refresh_cargo_overview(self) -> None:
        """총괄 화물 리스트 새로고침 — 상태별 해당 화물만"""
        if not getattr(self, 'tree_cargo_overview', None):
            return
        for item in self.tree_cargo_overview.get_children(''):
            self.tree_cargo_overview.delete(item)
        raw = (self._cargo_status_var.get() or '').strip()
        status_filter = _cargo_status_from_combo_value(raw)
        scope = getattr(self, '_cargo_scope_var', None) and self._cargo_scope_var.get() or 'all'
        try:
            rows = self.engine.get_cargo_overview_lots(status_filter, scope=scope)
        except Exception as e:
            logger.debug(f"총괄 화물 조회: {e}")
            rows = []
        # 기간 필터 적용 (날짜에 따라 테이블/하단 합계 연동)
        date_from = getattr(self, '_cargo_date_from_var', None) and self._cargo_date_from_var.get() or ''
        date_to = getattr(self, '_cargo_date_to_var', None) and self._cargo_date_to_var.get() or ''
        if date_from or date_to:
            rows = [r for r in rows if _cargo_date_in_range(r, date_from, date_to)]
        # 상태별 개수로 콤보 values 갱신 (현재 재고 기준이면 출고 제외)
        try:
            counts = self.engine.get_cargo_overview_counts(scope=scope)
            cnt_total = counts.get('total', 0)
            cnt_avail = counts.get('AVAILABLE', 0)
            cnt_reserved = counts.get('RESERVED', 0)
            cnt_picked = counts.get('PICKED', 0)
            cnt_sold = counts.get('SOLD', 0)
        except Exception:
            cnt_total = cnt_avail = cnt_reserved = cnt_picked = cnt_sold = 0
        if scope == 'current':
            new_values = [
                f"전체 ({cnt_total})", f"판매가능 ({cnt_avail})", f"판매배정 ({cnt_reserved})",
                f"판매화물 결정 ({cnt_picked})",
            ]
            self._cargo_status_combo['values'] = new_values
            cur_val = (self._cargo_status_var.get() or '').strip()
            if cur_val and '출고' in cur_val:
                self._cargo_status_var.set(f"전체 ({cnt_total})")
            else:
                _sync_cargo_combo_to_values(self._cargo_status_var, cur_val, new_values)
        else:
            new_values = [
                f"전체 ({cnt_total})", f"판매가능 ({cnt_avail})", f"판매배정 ({cnt_reserved})",
                f"판매화물 결정 ({cnt_picked})", f"출고 ({cnt_sold})",
            ]
            self._cargo_status_combo['values'] = new_values
            _sync_cargo_combo_to_values(self._cargo_status_var, (self._cargo_status_var.get() or '').strip(), new_values)
        # Avail 컬럼: N+1 방지 — LOT별 AVAILABLE 톤백 수 일괄 조회
        try:
            avail_rows = self.engine.db.fetchall(
                "SELECT lot_no, COUNT(*) as cnt FROM inventory_tonbag "
                "WHERE status = 'AVAILABLE' AND COALESCE(is_sample,0) = 0 GROUP BY lot_no"
            )
            avail_map = {str(r.get('lot_no', '')): r.get('cnt', 0) for r in (avail_rows or [])}
        except Exception as e:
            logger.debug(f"Avail 일괄 조회: {e}")
            avail_map = {}
        # 행 채우기 (재고 탭과 동일 포맷). 태그는 필터 상태 기준
        for row_num, item in enumerate(rows, 1):
            lot_no = str(item.get('lot_no', ''))
            status = status_filter or item.get('status', STATUS_AVAILABLE)
            vals = []
            for col_id, _, _, _, _ in CARGO_OVERVIEW_COLUMNS:
                if col_id == 'row_num':
                    vals.append(str(row_num))
                elif col_id == 'outbound_weight':
                    try:
                        iw = float(item.get('initial_weight', 0) or 0)
                        cw = float(item.get('current_weight', 0) or 0)
                        ow = iw - cw
                        vals.append(f"{ow:,.0f}" if ow > 0 else '0')
                    except (ValueError, TypeError):
                        vals.append('0')
                elif col_id == 'avail_bags':
                    vals.append(str(avail_map.get(lot_no, 0)))
                elif col_id == 'status':
                    # 총괄 리스트 상태(콤보)에 따라 리스트 안 STATUS 컬럼도 동일하게 표시
                    if status_filter is not None:
                        display_status = get_status_display(status_filter)
                    else:
                        display_status = get_status_display(status) or status
                    vals.append(display_status)
                elif col_id in ('net_weight', 'current_weight', 'initial_weight'):
                    v = item.get(col_id, 0)
                    try:
                        vals.append(f"{float(v):,.0f}" if v else '0')
                    except (ValueError, TypeError):
                        vals.append(str(v) if v else '0')
                elif col_id in ('mxbg_pallet', 'free_time'):
                    v = item.get(col_id, '')
                    try:
                        vals.append(f"{int(float(v)):,}" if v else '')
                    except (ValueError, TypeError):
                        vals.append(str(v) if v else '')
                else:
                    v = item.get(col_id, '')
                    vals.append(str(v) if v is not None else '')
            tag = status.lower() if status in ('AVAILABLE', 'PICKED', 'RESERVED', 'SHIPPED', 'DEPLETED') else ''
            row_idx = len(self.tree_cargo_overview.get_children(''))
            tags = [tag] if tag else []
            if row_idx % 2 == 1 and not tag:
                tags.append('stripe')
            self.tree_cargo_overview.insert('', 'end', values=vals, tags=tuple(tags))
        _is_dark = is_dark()
        ThemeColors.configure_tags(self.tree_cargo_overview, _is_dark)
        if hasattr(self, '_cargo_footer') and self._cargo_footer:
            self._cargo_footer.update_totals()


# ═══════════════════════════════════════════════════════════════════
# v8.1.7: Return 탭 셋업 — Return / 반품 재입고 관리
# ═══════════════════════════════════════════════════════════════════
class ReturnTabMixin:
    """🔄 Return 탭 — 반품 재입고 관리 (v8.1.7 신규)."""

    def _setup_return_tab(self) -> None:
        """Return 탭 UI 초기화."""
        import tkinter as tk
        from ..utils.ui_constants import Spacing, ThemeColors, is_dark, apply_tooltip

        frame = self.tab_return
        # ── 헤더 ──────────────────────────────────────────────
        hdr = tk.Frame(frame)
        hdr.pack(fill='x', padx=Spacing.LG, pady=(Spacing.MD, 0))
        tk.Label(hdr, text="🔄 Return Management",
                 font=('맑은 고딕', 14, 'bold')).pack(side='left')

        # ── 버튼 바 ───────────────────────────────────────────
        btn_bar = tk.Frame(frame)
        btn_bar.pack(fill='x', padx=Spacing.LG, pady=Spacing.SM)

        from tkinter import ttk as _ttk
        _ttk.Button(btn_bar, text="📂 Return Inbound (Excel)",
                    command=lambda: self._on_return_inbound_upload()
                    if hasattr(self, '_on_return_inbound_upload') else None
                    ).pack(side='left', padx=(0, Spacing.Tab.BTN_GAP))
        _ttk.Button(btn_bar, text="🔄 Return (Re-inbound)",
                    command=lambda: self._show_return_dialog(1)
                    if hasattr(self, '_show_return_dialog') else None
                    ).pack(side='left', padx=(0, Spacing.Tab.BTN_GAP))
        _ttk.Button(btn_bar, text="📊 Return Statistics",
                    command=lambda: self._show_return_statistics()
                    if hasattr(self, '_show_return_statistics') else None
                    ).pack(side='left', padx=(0, Spacing.Tab.BTN_GAP))
        _ttk.Button(btn_bar, text="🔄 Refresh",
                    command=lambda: self._refresh_return_tab()
                    ).pack(side='right')

        # ── 요약 카드 ─────────────────────────────────────────
        card_frame = tk.Frame(frame)
        card_frame.pack(fill='x', padx=Spacing.LG, pady=(0, Spacing.SM))
        self._return_summary_labels = {}
        for col_key, col_title in [
            ('total',    'Total Returns'),
            ('pending',  'Pending Review'),
            ('complete', 'Completed'),
        ]:
            card = tk.Frame(card_frame, relief='solid', bd=1)
            card.pack(side='left', fill='x', expand=True, padx=Spacing.Tab.BTN_GAP)
            tk.Label(card, text=col_title, font=('맑은 고딕', 10)).pack(pady=(Spacing.XS, 0))
            lbl = tk.Label(card, text='—', font=('맑은 고딕', 18, 'bold'))
            lbl.pack(pady=(0, Spacing.XS))
            self._return_summary_labels[col_key] = lbl

        # ── 트리뷰 ────────────────────────────────────────────
        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill='both', expand=True, padx=Spacing.LG, pady=(0, Spacing.MD))
        cols = ('lot_no', 'product', 'return_date', 'qty_kg', 'reason', 'status')
        self.tree_return = _ttk.Treeview(tree_frame, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H)
        hdrs = [('LOT NO', 120), ('Product', 150), ('Return Date', 100),
                ('Qty (kg)', 90), ('Reason', 180), ('Status', 90)]
        for col, (heading, width) in zip(cols, hdrs):
            self.tree_return.heading(col, text=heading)
            self.tree_return.column(col, width=width, anchor='center')
        vsb = _ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree_return.yview)
        self.tree_return.configure(yscrollcommand=vsb.set)
        self.tree_return.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def _refresh_return_tab(self) -> None:
        """Return 탭 데이터 새로고침 — return_history 테이블 컬럼 기반."""
        try:
            if not hasattr(self, 'tree_return'):
                return
            self.tree_return.delete(*self.tree_return.get_children())

            rows = []
            if hasattr(self, 'engine') and hasattr(self.engine, 'get_return_history'):
                rows = self.engine.get_return_history(limit=500) or []

            for r in rows:
                # return_history 컬럼: lot_no, sub_lt, return_date,
                #   original_customer, original_sale_ref, reason, remark,
                #   weight_kg, sap_no, product (LEFT JOIN inventory)
                product = r.get('product') or r.get('sap_no') or ''
                qty_kg  = r.get('weight_kg', '')
                if qty_kg:
                    try:
                        qty_kg = f"{float(qty_kg):,.1f}"
                    except (ValueError, TypeError) as e:
                        logger.debug(f"[UI] weight format skipped: {qty_kg!r}: {e}")
                status = '완료' if r.get('return_date') else '대기'
                self.tree_return.insert('', 'end', values=(
                    r.get('lot_no', ''),
                    product,
                    r.get('return_date', ''),
                    qty_kg,
                    r.get('reason', ''),
                    status,
                ))

            # 요약 카드 업데이트
            if hasattr(self, '_return_summary_labels'):
                total    = len(rows)
                complete = sum(1 for r in rows if r.get('return_date'))
                pending  = total - complete
                self._return_summary_labels['total'].config(text=str(total))
                self._return_summary_labels['pending'].config(text=str(pending))
                self._return_summary_labels['complete'].config(text=str(complete))

        except Exception as _e:
            import logging
            logging.getLogger(__name__).debug(f"[ReturnTab] refresh: {_e}")
