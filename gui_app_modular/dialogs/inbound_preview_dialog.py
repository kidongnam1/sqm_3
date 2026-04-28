"""
SQM v6.12.1 — 수동입고 미리보기 편집 다이얼로그
================================================
엑셀 수동입고 시 DB 반영 전 미리보기 + 셀 편집 기능.
Addon-C(PDF 입고 미리보기 편집)와 동일한 인라인 편집 패턴.
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
import logging
import tkinter as tk
from tkinter import ttk
from tkinter.constants import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y

logger = logging.getLogger(__name__)

try:
    from gui_app_modular.utils.custom_messagebox import CustomMessageBox
    from gui_app_modular.utils.ui_constants import (
        DialogSize, apply_modal_window_options, center_dialog,
        setup_dialog_geometry_persistence,
    )
except ImportError:
    DialogSize = None
    center_dialog = None
    apply_modal_window_options = None
    CustomMessageBox = None
    setup_dialog_geometry_persistence = None

try:
    from gui_app_modular.utils.theme_colors import ThemeColors
except ImportError:
    ThemeColors = None


class ManualInboundPreviewDialog:
    """
    수동입고 미리보기 + 편집 다이얼로그.

    Args:
        parent: 부모 윈도우
        rows_valid: [(excel_row_num, packing_dict), ...]
        on_confirm: 확인 시 콜백 — 편집된 rows_valid를 인자로 받음
        current_theme: 현재 테마
    """

    # 편집 가능한 컬럼
    EDITABLE_COLS = ('lot_no', 'sap_no', 'bl_no', 'net_weight', 'mxbg_pallet',
                     'product', 'container_no', 'warehouse')
    DISPLAY_COLS = ('no', 'lot_no', 'sap_no', 'bl_no', 'net_weight',
                    'mxbg_pallet', 'product', 'container_no', 'warehouse')
    HEADERS = ('#', 'LOT NO', 'SAP NO', 'B/L NO', '순중량(kg)',
               '톤백수', '제품명', '컨테이너', '창고')
    WIDTHS = (35, 100, 80, 100, 80, 50, 120, 90, 60)

    def __init__(self, parent, rows_valid: list, on_confirm=None,
                 current_theme: str = 'darkly'):
        self.parent = parent
        self.rows_valid = rows_valid  # [(row_num, packing_dict), ...]
        self.on_confirm = on_confirm
        self.confirmed = False
        self._editing_item = None

        dark_mode = is_dark() if ThemeColors else False
        bg = ThemeColors.get('bg_card', is_dark()) if ThemeColors else '#FFFFFF'
        fg = ThemeColors.get('text_primary', is_dark()) if ThemeColors else '#000000'

        self.popup = create_themed_toplevel(parent)
        self.popup.title(f"📝 수동입고 미리보기 ({len(rows_valid)}건)")
        self.popup.transient(parent)
        self.popup.grab_set()
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(self.popup, "inbound_preview_dialog", parent, "large")
        elif DialogSize:
            self.popup.geometry(DialogSize.get_geometry(parent, 'large'))
            if apply_modal_window_options:
                apply_modal_window_options(self.popup)
            if center_dialog:
                center_dialog(self.popup, parent)
        else:
            self.popup.geometry("1000x550")
        self.popup.configure(bg=bg)

        # ═══ 안내 ═══
        info = tk.Frame(self.popup, bg=bg, pady=5)
        info.pack(fill=X, padx=10)
        tk.Label(info,
                 text=f"총 {len(rows_valid)}건 | 셀 더블클릭으로 편집 가능 | 편집 후 [DB 반영]",
                 font=('맑은 고딕', 10), bg=bg, fg=fg).pack(anchor='w')

        # ═══ Treeview ═══
        tree_frame = tk.Frame(self.popup, bg=bg)
        tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(
            tree_frame, columns=self.DISPLAY_COLS, show='headings', height=18
        )
        # v8.6.4: 파싱 결과 수동 편집 활성화 (더블클릭 + Ctrl+C/V)
        self.tree._enable_global_editable = True
        for cid, hdr, w in zip(self.DISPLAY_COLS, self.HEADERS, self.WIDTHS):
            self.tree.heading(cid, text=hdr, anchor='center')
            anchor = 'e' if cid in ('net_weight', 'mxbg_pallet') else 'center'
            self.tree.column(cid, width=w, anchor=anchor)

        sb = tk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        sb_x = tk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=sb_x.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side=RIGHT, fill=Y)
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 데이터 로드
        for idx, (rnum, p) in enumerate(rows_valid):
            self.tree.insert('', END, iid=str(idx), values=(
                idx + 1,
                p.get('lot_no', ''),
                p.get('sap_no', ''),
                p.get('bl_no', ''),
                f"{p.get('net_weight', 0):,.0f}",
                p.get('mxbg_pallet', 10),
                p.get('product', ''),
                p.get('container_no', ''),
                p.get('warehouse', '광양'),
            ))

        # 더블클릭 편집 바인딩
        self.tree.bind('<Double-1>', self._on_cell_edit)

        # v8.1.5: 합계 Footer
        from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter
        self._inbound_footer = TreeviewTotalFooter(
            self.popup, self.tree,
            ['net_weight', 'mxbg_pallet'],
            column_display_names={'net_weight': '순중량(kg)', 'mxbg_pallet': '톤백수'}
        )
        self._inbound_footer.pack(fill=X, padx=10)
        self._inbound_footer.update_totals()

        # ═══ 하단 버튼 ═══
        btn_bar = tk.Frame(self.popup, bg=bg, pady=8)
        btn_bar.pack(fill=X, padx=10)

        ttk.Button(btn_bar, text="취소", command=self.popup.destroy).pack(side=RIGHT, padx=5)
        ttk.Button(btn_bar, text="✅ DB 반영", command=self._on_submit).pack(side=RIGHT, padx=5)

        # 요약
        total_kg = sum(p.get('net_weight', 0) for _, p in rows_valid)
        total_tb = sum(p.get('mxbg_pallet', 0) for _, p in rows_valid)
        tk.Label(btn_bar,
                 text=f"합계: {total_kg:,.0f} kg | 톤백 {total_tb:,}개",
                 font=('맑은 고딕', 10), bg=bg, fg=fg).pack(side=LEFT)

        self.popup.wait_window()

    def _on_cell_edit(self, event):
        """셀 더블클릭 → 인라인 Entry 편집."""
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col_id = self.tree.identify_column(event.x)  # '#1', '#2', ...
        col_idx = int(col_id.replace('#', '')) - 1
        if col_idx < 0 or col_idx >= len(self.DISPLAY_COLS):
            return
        col_name = self.DISPLAY_COLS[col_idx]
        if col_name not in self.EDITABLE_COLS:
            return

        item = self.tree.identify_row(event.y)
        if not item:
            return

        # 기존 편집 중이면 저장
        self._finish_editing()

        bbox = self.tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox

        current_val = self.tree.set(item, col_name)

        entry = tk.Entry(self.tree, font=('맑은 고딕', 10))
        entry.insert(0, current_val.replace(',', ''))  # 숫자 콤마 제거
        entry.select_range(0, 'end')
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()

        self._editing_item = (item, col_name, entry)
        entry.bind('<Return>', lambda e: self._finish_editing())
        entry.bind('<Escape>', lambda e: self._cancel_editing())
        entry.bind('<FocusOut>', lambda e: self._finish_editing())

    def _finish_editing(self):
        """편집 완료 → Treeview + rows_valid 업데이트."""
        if not self._editing_item:
            return
        item, col_name, entry = self._editing_item
        new_val = entry.get().strip()
        entry.destroy()
        self._editing_item = None

        idx = int(item)
        rnum, packing = self.rows_valid[idx]

        # 타입별 변환
        if col_name in ('net_weight',):
            try:
                new_val_num = float(new_val.replace(',', ''))
                packing[col_name] = new_val_num
                self.tree.set(item, col_name, f"{new_val_num:,.0f}")
            except ValueError:
                return  # 잘못된 값 → 무시
        elif col_name in ('mxbg_pallet',):
            try:
                new_val_int = int(float(new_val.replace(',', '')))
                packing[col_name] = new_val_int
                self.tree.set(item, col_name, str(new_val_int))
            except ValueError:
                return
        else:
            packing[col_name] = new_val
            self.tree.set(item, col_name, new_val)

    def _cancel_editing(self):
        """편집 취소."""
        if self._editing_item:
            self._editing_item[2].destroy()
            self._editing_item = None

    def _on_submit(self):
        """DB 반영 확인."""
        self._finish_editing()
        self.confirmed = True
        self.popup.destroy()
        if self.on_confirm:
            self.on_confirm(self.rows_valid)
