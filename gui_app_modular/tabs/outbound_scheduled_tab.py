# -*- coding: utf-8 -*-
"""
SQM v5.9.6 — 출고 예정 탭
==========================
재고 리스트에서 Allocation(예약) 삭감 반영한 테이블.
Balance(Kg) = current_weight - allocated_kg
LOT 클릭 시 출고/톤백·샘플 이력 팝업 (Excel/PDF 출력 가능)
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from engine_modules.constants import STATUS_RESERVED
import tkinter as tk
from tkinter import filedialog
from tkinter import END, X
from ..utils.ui_constants import is_dark, ThemeColors, Spacing, apply_modal_window_options, get_status_display, setup_dialog_geometry_persistence
import logging
from ..utils.tree_enhancements import TreeviewTotalFooter

logger = logging.getLogger(__name__)

# 출고 예정 컬럼 (재고리스트 + 예약)
OUTBOUND_SCHEDULED_COLUMNS = [
    ('row_num',            'No.',            50, 'center', True),
    ('lot_no',             'LOT NO',        130, 'center', True),
    ('sap_no',             'SAP NO',        120, 'center', True),
    ('bl_no',              'BL NO',         140, 'center', True),
    ('product',            'PRODUCT',       170, 'w',      True),
    ('status',             'STATUS',         95, 'center', True),
    ('current_weight_after_allocation', 'Balance(Kg)', 105, 'e', True),
    ('allocated_kg',       '예약(Kg)',       95, 'e', True),
    ('allocated_count',    '예약(개)',       70, 'e', True),
    ('net_weight',         'NET(Kg)',        105, 'e', True),
    ('container_no',       'CONTAINER',     135, 'center', True),
    ('ship_date',          'SHIP DATE',      95, 'center', True),
    ('arrival_date',       'ARRIVAL',        95, 'center', True),
    ('warehouse',          'WH',             85, 'w',      True),
    ('initial_weight',     'Inbound(Kg)',   105, 'e',      True),
]


try:
    from ..utils.sort_utils import make_sort_key
except ImportError:
    def make_sort_key(col, numeric_cols):
        def _k(item):
            v = item[0]
            try:
                return (0, float(v)) if col in numeric_cols else (0, str(v).lower())
            except Exception:
                return (1, str(v))
        return _k


class OutboundScheduledTabMixin:
    """출고 예정 탭 Mixin — Allocation 삭감 반영"""

    def _setup_outbound_scheduled_tab(self) -> None:
        """출고 예정 탭 설정"""
        from ..utils.constants import ttk, VERTICAL, BOTH, YES, LEFT, RIGHT, X

        is_dark()

        # 버튼 바
        btn_frame = ttk.Frame(self.tab_outbound_scheduled)
        btn_frame.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        ttk.Button(btn_frame, text="📥 Excel 내보내기",
                   command=lambda: self._on_export_outbound_scheduled()).pack(side=LEFT, padx=Spacing.XS)
        ttk.Button(btn_frame, text="🔄 새로고침",
                   command=self._refresh_outbound_scheduled).pack(side=LEFT, padx=Spacing.XS)
        ttk.Button(btn_frame, text="📦 톤백포함",
                   command=self._show_tonbag_included_popup).pack(side=LEFT, padx=Spacing.XS)

        # v6.2.7: 제품 필터 콤보박스
        ttk.Label(btn_frame, text="  제품:").pack(side=LEFT, padx=(Spacing.SM, 0))
        self._ob_product_filter_var = getattr(self, '_tk_module', __import__('tkinter')).StringVar(value='전체')
        self._ob_product_filter = ttk.Combobox(
            btn_frame, textvariable=self._ob_product_filter_var,
            state='readonly', width=20
        )
        self._ob_product_filter['values'] = ['전체']
        self._ob_product_filter.pack(side=LEFT, padx=Spacing.XS)
        self._ob_product_filter.bind('<<ComboboxSelected>>', lambda e: self._refresh_outbound_scheduled())

        # v6.3.5: 출고번호(outbound_no) 선택(최근) + 상태 배너 (단일 트랜잭션 고정)
        ttk.Label(btn_frame, text="  출고번호:").pack(side=LEFT, padx=(Spacing.SM, 0))
        self._ob_outbound_no_var = tk.StringVar(value="(자동)")
        self._ob_outbound_no_combo = ttk.Combobox(
            btn_frame, textvariable=self._ob_outbound_no_var,
            state='readonly', width=18
        )
        self._ob_outbound_no_combo['values'] = ['(자동)']
        self._ob_outbound_no_combo.current(0)
        self._ob_outbound_no_combo.pack(side=LEFT, padx=Spacing.XS)
        # v8.7.0 [FIX C-3]: _on_select_outbound_no 정의 없음 — hasattr 방어 후 bind
        self._ob_outbound_no_combo.bind(
            '<<ComboboxSelected>>',
            lambda e: self._on_select_outbound_no() if hasattr(self, '_on_select_outbound_no') else None
        )

        self._ob_outbound_banner_var = tk.StringVar(value="출고번호: -  |  상태: -")
        self._ob_outbound_banner = ttk.Label(btn_frame, textvariable=self._ob_outbound_banner_var)
        self._ob_outbound_banner.pack(side=RIGHT, padx=(Spacing.SM, 0))

        # v5.9.7: 스플릿 패널 (마스터-상세)
        from ..utils.split_panel import MasterDetailSplitPanel
        self._ob_split_panel = MasterDetailSplitPanel(
            self.tab_outbound_scheduled,
            detail_title="📋 판매 배정 이력 (선택 LOT)",
            master_weight=3,
            detail_weight=1
        )
        self._ob_split_panel.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)

        # 합계 바 (하단): 출고 예정 = 재고리스트 − Allocation → 개수·총합 일치
        self._ob_footer_frame = ttk.Frame(self.tab_outbound_scheduled)
        self._ob_footer_frame.pack(fill=X, padx=Spacing.XS, pady=(Spacing.XS, 0))
        self._ob_footer_label = ttk.Label(
            self._ob_footer_frame,
            text="LOT 0건 | Balance(Kg) 합계: 0 | 예약(Kg) 합계: 0 | 예약(개) 합계: 0  (출고 예정 = 재고리스트 − 판매 배정)"
        )
        self._ob_footer_label.pack(anchor="w")

        # 마스터 영역: 트리뷰
        tree_frame = ttk.Frame(self._ob_split_panel.get_master_container())
        tree_frame.pack(fill=BOTH, expand=YES)

        all_cols = [c[0] for c in OUTBOUND_SCHEDULED_COLUMNS]
        self.tree_outbound_scheduled = ttk.Treeview(
            tree_frame, columns=all_cols, show="headings", height=20,
            selectmode='extended'
        )
        self._ob_sort_column = None
        self._ob_sort_reverse = False
        for col_id, label, width, anchor, _ in OUTBOUND_SCHEDULED_COLUMNS:
            self.tree_outbound_scheduled.heading(
                col_id, text=label, anchor='center',
                command=lambda c=col_id: self._sort_outbound_scheduled_tree(c)
            )
            self.tree_outbound_scheduled.column(col_id, width=width, anchor=anchor)

        v_scroll = tk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree_outbound_scheduled.yview)
        h_scroll = tk.Scrollbar(tree_frame, orient='horizontal', command=self.tree_outbound_scheduled.xview)
        self.tree_outbound_scheduled.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree_outbound_scheduled.pack(side=LEFT, fill=BOTH, expand=YES)
        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill=X)

        self.tree_outbound_scheduled.bind('<Double-1>', self._on_outbound_scheduled_lot_click)
        self.tree_outbound_scheduled.bind('<<TreeviewSelect>>', self._on_outbound_scheduled_selection_change)

        # v8.1.5: 합계 Footer
        self._ob_scheduled_footer = TreeviewTotalFooter(
            self._ob_split_panel.get_master_container(), self.tree_outbound_scheduled,
            ['current_weight_after_allocation', 'allocated_kg', 'allocated_count', 'net_weight', 'initial_weight'],
            column_display_names={
                'current_weight_after_allocation': 'Balance(Kg)',
                'allocated_kg': '예약(Kg)',
                'allocated_count': '예약(개)',
                'net_weight': 'NET(Kg)',
                'initial_weight': 'Inbound(Kg)',
            }
        )
        self._ob_scheduled_footer.pack(fill=X)

        # v5.9.7: 상세 패널 — Allocation 이력
        self._setup_ob_allocation_detail_panel()

        self._refresh_outbound_scheduled()

    def _setup_ob_allocation_detail_panel(self) -> None:
        """출고예정 탭 상세 패널: Allocation 이력"""
        from ..utils.constants import ttk, VERTICAL, BOTH, LEFT, X
        detail_container = self._ob_split_panel.get_detail_container()
        # 톤백포함 버튼 (전체 LOT 톤백 예정 현황 팝업)
        ob_detail_bar = ttk.Frame(detail_container)
        ob_detail_bar.pack(fill=X, pady=(0, Spacing.XS))
        ttk.Button(ob_detail_bar, text="📦 톤백포함 (전체 LOT)", command=self._show_tonbag_included_popup).pack(side=LEFT, padx=Spacing.XS)
        cols = ('no', 'sub_lt', 'weight', 'type', 'status', 'customer', 'out_date')
        # v8.1.5: tree + scrollbar를 wrapper frame에 배치
        tree_wrapper = ttk.Frame(detail_container)
        tree_wrapper.pack(fill=BOTH, expand=True)
        self._ob_alloc_detail_tree = ttk.Treeview(
            tree_wrapper, columns=cols, show='headings', height=8
        )
        for cid, txt, w in [
            ('no', 'No.', 45), ('sub_lt', '톤백#', 70), ('weight', '중량(kg)', 90),
            ('type', '구분', 70), ('status', '상태', 90), ('customer', '출고처', 120),
            ('out_date', '출고/예정일', 100),
        ]:
            self._ob_alloc_detail_tree.heading(cid, text=txt, anchor='center')
            self._ob_alloc_detail_tree.column(cid, width=w)
        sb = tk.Scrollbar(tree_wrapper, orient=VERTICAL, command=self._ob_alloc_detail_tree.yview)
        self._ob_alloc_detail_tree.configure(yscrollcommand=sb.set)
        self._ob_alloc_detail_tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side='right', fill='y')
        # v8.1.5: 합계 Footer
        self._ob_detail_footer = TreeviewTotalFooter(
            detail_container, self._ob_alloc_detail_tree,
            ['weight'],
            column_display_names={'weight': '중량(kg)'}
        )
        self._ob_detail_footer.pack(fill=X)

    def _on_outbound_scheduled_selection_change(self, event) -> None:
        """출고예정 선택 변경 → Allocation 이력 상세 패널 갱신"""
        sel = self.tree_outbound_scheduled.selection()
        if not sel or not hasattr(self, '_ob_alloc_detail_tree'):
            return
        item = self.tree_outbound_scheduled.item(sel[0])
        vals = item.get('values', [])
        if len(vals) < 2:
            return
        lot_no = str(vals[1]).strip()
        if not lot_no:
            return
        self._ob_alloc_detail_tree.delete(*self._ob_alloc_detail_tree.get_children())
        self._ob_split_panel.set_detail_title(f"📋 판매 배정 이력 — {lot_no}")
        try:
            history = self.engine.get_lot_outbound_history(lot_no)
            for idx, row in enumerate(history or [], 1):
                st = str(row.get('tonbag_status', '')).strip()
                is_sample = row.get('is_sample') or 0
                tb_type = '🧪 샘플' if is_sample else '📦 정규'
                sub_lt = row.get('sub_lt', 0) or (0 if is_sample else '')
                weight = float(row.get('weight', 0) or 0)
                customer = str(row.get('customer', '')).strip()
                out_date = str(row.get('out_date', ''))[:10] if row.get('out_date') else ''
                status_txt = ('🔒 ' if st == STATUS_RESERVED else '') + (get_status_display(st) or st)
                self._ob_alloc_detail_tree.insert('', END, values=(
                    idx, sub_lt, f"{weight:,.0f}", tb_type, status_txt, customer, out_date))
        except Exception as e:
            logger.debug(f"Allocation 이력 로드: {e}")
        if hasattr(self, '_ob_detail_footer'):
            self._ob_detail_footer.update_totals()

    def _on_outbound_scheduled_lot_click(self, event) -> None:
        """LOT 더블클릭 → 출고 이력 팝업"""
        sel = self.tree_outbound_scheduled.selection()
        if not sel:
            return
        item = self.tree_outbound_scheduled.item(sel[0])
        vals = item.get('values', [])
        if len(vals) < 2:
            return
        lot_no = str(vals[1]).strip()
        if lot_no:
            self._show_lot_outbound_history_popup(lot_no)

    def _show_tonbag_included_popup(self) -> None:
        """톤백포함 — 전체 LOT에 대한 톤백 예정/이력 (RESERVED, PICKED, SOLD, SHIPPED)"""
        from ..utils.constants import ttk, BOTH, LEFT, END, X
        try:
            rows = self.engine.get_all_tonbag_outbound_status()
        except Exception as e:
            logger.debug(f"톤백포함 조회: {e}")
            rows = []
        popup = create_themed_toplevel(self.root)
        popup.title("📦 톤백포함 — 전체 LOT 톤백 예정/이력")
        apply_modal_window_options(popup)
        popup.transient(self.root)
        setup_dialog_geometry_persistence(popup, "tonbag_outbound_status_popup", self.root, "large")
        dark_mode = is_dark()
        bg = ThemeColors.get('bg_card', is_dark)
        fg = ThemeColors.get('text_primary', is_dark)
        popup.configure(bg=bg)
        header = tk.Frame(popup, bg=bg, padx=15, pady=10)
        header.pack(fill=X)
        tk.Label(header, text=f"전체 LOT 톤백 예정/이력 — {len(rows)}건",
                 font=('맑은 고딕', 12, 'bold'), bg=bg, fg=fg).pack(anchor='w')
        tk.Label(header, text="판매배정·판매화물 결정·출고·선적 상태 톤백 (LOT별 정렬)",
                 font=('맑은 고딕', 10), bg=bg, fg=ThemeColors.get('text_secondary', is_dark)).pack(anchor='w')
        cols = ('lot_no', 'sub_lt', 'weight', 'type', 'status', 'customer', 'out_date')
        tree = ttk.Treeview(popup, columns=cols, show='headings', height=20)
        for cid, txt, w in [
            ('lot_no', 'LOT NO', 120), ('sub_lt', '톤백#', 60), ('weight', '중량(kg)', 90),
            ('type', '구분', 70), ('status', '상태', 90), ('customer', '출고처', 120),
            ('out_date', '출고/예정일', 100),
        ]:
            tree.heading(cid, text=txt, anchor='center')
            tree.column(cid, width=w)
        sb = tk.Scrollbar(popup, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True, padx=Spacing.XS, pady=Spacing.XS)
        sb.pack(side='right', fill='y', pady=Spacing.XS)
        for idx, row in enumerate(rows, 1):
            st = str(row.get('tonbag_status', '')).strip()
            is_sample = row.get('is_sample') or 0
            tb_type = '🧪 샘플' if is_sample else '📦 정규'
            sub_lt = row.get('sub_lt', 0) or (0 if is_sample else '')
            weight = float(row.get('weight', 0) or 0)
            customer = str(row.get('customer', '')).strip()
            out_date = str(row.get('out_date', ''))[:10] if row.get('out_date') else ''
            status_txt = ('🔒 ' if st == STATUS_RESERVED else '') + (get_status_display(st) or st)
            tree.insert('', END, values=(
                str(row.get('lot_no', '')), sub_lt, f"{weight:,.0f}", tb_type, status_txt, customer, out_date))
        if not rows:
            tree.insert('', END, values=('', '데이터 없음', '', '', '', '', ''))
        ttk.Button(popup, text="닫기", command=popup.destroy).pack(pady=Spacing.XS)
        popup.bind('<Escape>', lambda e: popup.destroy())

    def _refresh_outbound_scheduled(self) -> None:
        """출고 예정 테이블 새로고침"""
        if not hasattr(self, 'tree_outbound_scheduled'):
            return
        self._update_outbound_banner()
        self.tree_outbound_scheduled.delete(*self.tree_outbound_scheduled.get_children())

        # v6.2.7: 제품 필터 콤보 갱신
        try:
            from gui_app_modular.dialogs.product_master_helper import get_product_choices
            product_choices = ['전체'] + get_product_choices(self.engine.db, include_code=False)
            if hasattr(self, '_ob_product_filter'):
                current = self._ob_product_filter_var.get()
                self._ob_product_filter['values'] = product_choices
                if current not in product_choices:
                    self._ob_product_filter_var.set('전체')
        except Exception:
            logger.debug("[SUPPRESSED] exception in outbound_scheduled_tab.py")  # noqa

        try:
            data = self.engine.get_inventory_outbound_scheduled()

            # v6.2.7: 제품 필터 적용
            product_filter = getattr(self, '_ob_product_filter_var', None)
            if product_filter and product_filter.get() != '전체':
                selected_product = product_filter.get().upper()
                data = [d for d in data 
                        if selected_product in str(d.get('product', '')).upper()]

            total_balance_kg = 0.0
            total_alloc_kg = 0.0
            total_alloc_count = 0
            for idx, item in enumerate(data, 1):
                lot_no = str(item.get('lot_no', ''))
                balance = float(item.get('current_weight_after_allocation', 0) or 0)
                alloc_kg = float(item.get('allocated_kg', 0) or 0)
                alloc_cnt = int(item.get('allocated_count', 0) or 0)
                total_balance_kg += balance
                total_alloc_kg += alloc_kg
                total_alloc_count += alloc_cnt
                vals = [
                    str(idx),
                    lot_no,
                    str(item.get('sap_no', '')),
                    str(item.get('bl_no', '')),
                    str(item.get('product', '')),
                    str(item.get('status', '')),
                    f"{balance:,.0f}",
                    f"{alloc_kg:,.0f}",
                    str(alloc_cnt),
                    f"{float(item.get('net_weight', 0) or 0):,.0f}",
                    str(item.get('container_no', '')),
                    str(item.get('ship_date', ''))[:10] if item.get('ship_date') else '',
                    str(item.get('arrival_date', ''))[:10] if item.get('arrival_date') else '',
                    str(item.get('warehouse', '')),
                    f"{float(item.get('initial_weight', 0) or 0):,.0f}",
                ]
                self.tree_outbound_scheduled.insert('', 'end', values=vals)
            # 합계 바 갱신 (출고 예정 = 재고 - Allocation → 개수·총합 일치)
            if hasattr(self, '_ob_footer_label'):
                self._ob_footer_label.config(
                    text=f"LOT {len(data)}건 | Balance(Kg) 합계: {total_balance_kg:,.0f} | "
                         f"예약(Kg) 합계: {total_alloc_kg:,.0f} | 예약(개) 합계: {total_alloc_count}  "
                         f"(출고 예정 = 재고리스트 − 판매 배정)"
                )
            if hasattr(self, '_ob_scheduled_footer'):
                self._ob_scheduled_footer.update_totals()
        except Exception as e:
            logger.error(f"출고 예정 새로고침 오류: {e}")
            if hasattr(self, '_log'):
                self._log(f"⚠️ 출고 예정 조회 오류: {e}")
            if hasattr(self, '_ob_footer_label'):
                self._ob_footer_label.config(text="LOT 0건 | 조회 오류  (출고 예정 = 재고리스트 − 판매 배정)")

    def _sort_outbound_scheduled_tree(self, col: str) -> None:
        """출고 예정 트리 헤더 클릭 시 오름차순/내림차순 정렬"""
        tree = self.tree_outbound_scheduled
        if self._ob_sort_column == col:
            self._ob_sort_reverse = not self._ob_sort_reverse
        else:
            self._ob_sort_column = col
            self._ob_sort_reverse = False
        items = [(tree.set(item, col), item) for item in tree.get_children('')]
        numeric_cols = ['row_num', 'current_weight_after_allocation', 'allocated_kg', 'allocated_count',
                       'net_weight', 'initial_weight']
        if col in numeric_cols:
            sort_key = make_sort_key(col, numeric_cols)  # v7.0.0 [REFACTOR-1]
        items.sort(key=sort_key, reverse=self._ob_sort_reverse)
        for idx, (_, item) in enumerate(items):
            tree.move(item, '', idx)
        arrow = " ▼" if self._ob_sort_reverse else " ▲"
        for c_id, c_label, _, _, _ in OUTBOUND_SCHEDULED_COLUMNS:
            tree.heading(
                c_id,
                text=f"{c_label}{arrow}" if c_id == col else c_label,
                anchor='center',
            )

    def _on_export_outbound_scheduled(self) -> None:
        """출고 예정 테이블 Excel 내보내기 (같은 이름 있으면 _1, _2 ... 로 저장)"""
        from tkinter import filedialog
        from ..utils.ui_constants import CustomMessageBox
        from ..utils.excel_file_helper import get_unique_excel_path
        path = filedialog.asksaveasfilename(
            parent=getattr(self, "root", None),
            defaultextension='.xlsx',
            filetypes=[('Excel', '*.xlsx')],
            initialfile=f"출고예정_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        )
        if not path:
            return
        path = get_unique_excel_path(path)
        try:
            self._export_outbound_scheduled_excel(path)
            CustomMessageBox.showinfo(self.root, "완료", f"저장 완료:\n{path}")
        except Exception as e:
            logger.debug(f"출고 예정 Excel 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", str(e))

    def _show_lot_outbound_history_popup(self, lot_no: str) -> None:
        """LOT 출고 이력 팝업 — 톤백·샘플 출고/예약 이력 (Excel/PDF 출력)"""
        from ..utils.constants import ttk, VERTICAL, BOTH, LEFT, END
        from ..utils.ui_constants import apply_tooltip

        history = self.engine.get_lot_outbound_history(lot_no)
        lot_info = self.engine.db.fetchone("SELECT product, sap_no FROM inventory WHERE lot_no = ?", (lot_no,))
        product = (lot_info.get('product', '-') or '-') if lot_info else '-'

        popup = create_themed_toplevel(self.root)
        popup.title(f"출고 이력 — {lot_no}")
        apply_modal_window_options(popup)
        popup.transient(self.root)
        setup_dialog_geometry_persistence(popup, "lot_outbound_history_popup", self.root, "large")

        dark_mode = is_dark()
        bg = ThemeColors.get('bg_card', is_dark)
        fg = ThemeColors.get('text_primary', is_dark)
        popup.configure(bg=bg)

        # 헤더
        header = tk.Frame(popup, bg=bg, padx=15, pady=10)
        header.pack(fill=X)
        tk.Label(header, text=f"📦 {lot_no}  |  {product}",
                 font=('맑은 고딕', 14, 'bold'), bg=bg, fg=fg).pack(anchor='w')
        tk.Label(header, text="출고된 톤백·샘플 이력 (여러 번에 걸친 출고 포함)",
                 font=('맑은 고딕', 10), bg=bg, fg=ThemeColors.get('text_secondary', is_dark)).pack(anchor='w')

        # 테이블
        cols = ('no', 'sub_lt', 'weight', 'type', 'status', 'customer', 'out_date')
        tree = ttk.Treeview(popup, columns=cols, show='headings', height=14)
        for cid, txt, w in [
            ('no', 'No.', 45), ('sub_lt', '톤백#', 70), ('weight', '중량(kg)', 90),
            ('type', '구분', 70), ('status', '상태', 90), ('customer', '출고처', 120),
            ('out_date', '출고/예정일', 100),
        ]:
            tree.heading(cid, text=txt, anchor='center')
            tree.column(cid, width=w)

        sb = tk.Scrollbar(popup, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True, padx=Spacing.XS, pady=Spacing.XS)
        sb.pack(side='right', fill='y', pady=Spacing.XS)

        for idx, row in enumerate(history, 1):
            st = str(row.get('tonbag_status', '')).strip()
            is_sample = row.get('is_sample') or 0
            tb_type = '🧪 샘플' if is_sample else '📦 정규'
            sub_lt = row.get('sub_lt', 0) or (0 if is_sample else '')
            weight = float(row.get('weight', 0) or 0)
            customer = str(row.get('customer', '')).strip()
            out_date = str(row.get('out_date', ''))[:10] if row.get('out_date') else ''
            status_txt = ('🔒 ' if st == STATUS_RESERVED else '') + (get_status_display(st) or st)
            tree.insert('', END, values=(idx, sub_lt, f"{weight:,.0f}", tb_type, status_txt, customer, out_date))

        if not history:
            tree.insert('', END, values=('', '이력 없음', '', '', '', '', ''))

        # 버튼: Excel, PDF, 닫기
        btn_bar = tk.Frame(popup, bg=bg, pady=8)
        btn_bar.pack(fill=X, padx=10)

        def _export_excel():
            from ..utils.excel_file_helper import get_unique_excel_path
            path = filedialog.asksaveasfilename(
                parent=getattr(self, "root", None),
                defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx')],
                initialfile=f"출고이력_{lot_no}.xlsx"
            )
            if path:
                path = get_unique_excel_path(path)
                try:
                    self._export_lot_outbound_history_excel(lot_no, path, history)
                    from ..utils.ui_constants import CustomMessageBox
                    CustomMessageBox.showinfo(self.root, "완료", f"저장 완료:\n{path}")
                except Exception as e:
                    logger.debug(f"Excel 저장 오류: {e}")
                    from ..utils.ui_constants import CustomMessageBox
                    CustomMessageBox.showerror(self.root, "오류", str(e))

        def _export_pdf():
            try:
                self._export_lot_outbound_history_pdf(lot_no, history)
            except Exception as e:
                logger.debug(f"PDF 저장 오류: {e}")
                from ..utils.ui_constants import CustomMessageBox
                CustomMessageBox.showerror(self.root, "오류", str(e))

        ttk.Button(btn_bar, text="📊 Excel 저장", command=_export_excel).pack(side=LEFT, padx=5)
        ttk.Button(btn_bar, text="📋 PDF 저장", command=_export_pdf).pack(side=LEFT, padx=5)
        ttk.Button(btn_bar, text="닫기", command=popup.destroy).pack(side='right', padx=5)

        apply_tooltip(btn_bar.winfo_children()[0], "출고 이력을 Excel 파일로 저장")
        apply_tooltip(btn_bar.winfo_children()[1], "출고 이력을 PDF 파일로 저장")

        popup.bind('<Escape>', lambda e: popup.destroy())

    def _export_outbound_scheduled_excel(self, output_path: str) -> None:
        """출고 예정 테이블 Excel 저장"""
        import pandas as pd
        data = self.engine.get_inventory_outbound_scheduled()
        if not data:
            pd.DataFrame().to_excel(output_path, index=False)
            return
        rows = []
        for idx, item in enumerate(data, 1):
            rows.append({
                'No.': idx, 'LOT NO': item.get('lot_no'), 'SAP NO': item.get('sap_no'),
                'BL NO': item.get('bl_no'), 'PRODUCT': item.get('product'), 'STATUS': item.get('status'),
                'Balance(Kg)': item.get('current_weight_after_allocation', 0),
                '예약(Kg)': item.get('allocated_kg', 0), '예약(개)': item.get('allocated_count', 0),
                'NET(Kg)': item.get('net_weight'), 'CONTAINER': item.get('container_no'),
                'SHIP DATE': item.get('ship_date'), 'ARRIVAL': item.get('arrival_date'),
                'WH': item.get('warehouse'), 'Inbound(Kg)': item.get('initial_weight'),
            })
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(output_path, engine='openpyxl') as w:
            df.to_excel(w, sheet_name='출고예정', index=False, startrow=2)
            ws = w.sheets['출고예정']
            ws['A1'] = f"SQM 출고 예정 — {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}"
            ws.merge_cells('A1:O1')

    def _export_lot_outbound_history_excel(self, lot_no: str, output_path: str,
                                            history: list) -> None:
        """LOT 출고 이력 Excel 저장"""
        import pandas as pd
        import re
        rows = []
        for idx, row in enumerate(history, 1):
            st_raw = str(row.get('tonbag_status', '')).strip()
            st = get_status_display(st_raw) or st_raw
            is_sample = row.get('is_sample') or 0
            tb_type = '샘플' if is_sample else '정규'
            rows.append({
                'No.': idx, '톤백#': row.get('sub_lt'), '중량(kg)': row.get('weight'),
                '구분': tb_type, '상태': st, '출고처': row.get('customer', ''),
                '출고/예정일': str(row.get('out_date', ''))[:10],
            })
        df = pd.DataFrame(rows)
        sheet_name = re.sub(r'[\\/:*?\[\]]', '_', f'출고이력_{lot_no}')[:31]
        with pd.ExcelWriter(output_path, engine='openpyxl') as w:
            df.to_excel(w, sheet_name=sheet_name, index=False, startrow=2)
            ws = w.sheets[sheet_name]
            ws['A1'] = f"LOT 출고 이력 — {lot_no}"
            ws.merge_cells('A1:G1')

    def _export_lot_outbound_history_pdf(self, lot_no: str, history: list) -> None:
        """LOT 출고 이력 PDF 저장"""
        from tkinter import filedialog
        from ..utils.ui_constants import CustomMessageBox

        path = filedialog.asksaveasfilename(
            parent=getattr(self, "root", None),
            defaultextension='.pdf',
            filetypes=[('PDF', '*.pdf')],
            initialfile=f"출고이력_{lot_no}.pdf"
        )
        if not path:
            return
        try:
            from ..utils.pdf_report_gen import generate_lot_outbound_history_pdf
            fp = generate_lot_outbound_history_pdf(self.engine, lot_no, history, path)
            if fp:
                CustomMessageBox.showinfo(self.root, "완료", f"저장 완료:\n{fp}")
        except Exception as e:
            logger.debug(f"출고 이력 PDF: {e}")
            CustomMessageBox.showerror(self.root, "오류", str(e))



    def _update_outbound_banner(self) -> None:
        """현재 engine.current_outbound_no와 상태를 출고 예정 탭 상단에 표시."""
        try:
            eng = getattr(self, 'engine', None)
            outbound_no = getattr(eng, 'current_outbound_no', '') if eng else ''
            status = ''
            if eng and outbound_no and hasattr(eng, '_get_outbound_status'):
                try:
                    status = eng._get_outbound_status(outbound_no) or ''
                except Exception:
                    status = ''
            txt = f"출고번호: {outbound_no or '-'}  |  상태: {status or '-'}"
            if hasattr(self, '_ob_outbound_banner_var'):
                self._ob_outbound_banner_var.set(txt)
        except Exception:
            return