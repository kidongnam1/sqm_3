"""
SQM Inventory - Context Menu Mixin
==================================

v2.9.91 - Extracted from gui_app.py

Right-click context menus for treeviews
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
from engine_modules.constants import STATUS_AVAILABLE
import logging
import sqlite3

from ..utils.ui_constants import (
    STATUS_DISPLAY_TO_DB,
    CustomMessageBox,
    apply_modal_window_options,
    get_status_display,
    setup_dialog_geometry_persistence,
)

logger = logging.getLogger(__name__)


class ContextMenuMixin:
    """
    Context menu mixin
    
    Mixed into SQMInventoryApp class
    """

    def _setup_context_menus(self) -> None:
        """Setup context menus for all treeviews"""
        # Inventory treeview context menu
        if hasattr(self, 'tree_inventory'):
            self._setup_inventory_context_menu()

        # Tonbag treeview context menu
        if hasattr(self, 'tree_sublot'):
            self._setup_tonbag_context_menu()

        # Search treeview context menu
        if hasattr(self, 'tree_search'):
            self._setup_search_context_menu()

        # v7.0: Generic context menus for new tabs (Allocation, Picked, Sold)
        for tree_attr in [
            'tree_allocation', 'tree_allocation_detail',
            'tree_picked', 'tree_picked_detail',
            'tree_sold', 'tree_sold_detail',
            # 'tree_inventory', # Specific menu exists
            # 'tree_cargo_overview' # Specific menu exists in CargoOverviewTabMixin
        ]:
            tree = getattr(self, tree_attr, None)
            if tree:
                self._setup_generic_context_menu(tree)

    def _setup_generic_context_menu(self, tree) -> None:
        """Setup generic context menu (Copy/Export/Paste) for a treeview"""
        from ..utils.constants import Menu

        menu = Menu(self.root, tearoff=0)
        menu.add_command(label="📋 선택 영역 복사 (Copy)", command=lambda: self._copy_selection_to_clipboard(tree))
        menu.add_command(label="📥 선택 영역 Excel 저장", command=lambda: self._export_selection_to_excel(tree))
        menu.add_separator()
        menu.add_command(label="📋 붙여넣기 (Paste)", command=lambda: self._paste_to_tree_placeholder(tree))

        def show_menu(event):
            item = tree.identify_row(event.y)
            if item:
                # If item is not in selection, select it (unless Ctrl/Shift is held - hard to detect here, standard behavior is select)
                # But for right click, usually we want to keep selection if the clicked item is IN selection.
                if item not in tree.selection():
                    tree.selection_set(item)
            menu.post(event.x_root, event.y_root)

        tree.bind('<Button-3>', show_menu)

    def _copy_selection_to_clipboard(self, tree) -> None:
        """Copy selected rows to clipboard (Excel compatible TSV)"""
        selection = tree.selection()
        if not selection:
            return

        # Get column headers
        columns = tree['columns']
        headers = [tree.heading(col, 'text') for col in columns]

        lines = []
        # Add headers
        lines.append('\t'.join(headers))

        # Add data
        for item_id in selection:
            values = tree.item(item_id, 'values')
            lines.append('\t'.join(str(v) for v in values))

        text = '\n'.join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._log(f"📋 {len(selection)}행 클립보드 복사 완료")

    def _export_selection_to_excel(self, tree) -> None:
        """Export selected rows to Excel"""
        from datetime import datetime

        from ..utils.constants import HAS_PANDAS, filedialog, pd

        if not HAS_PANDAS:
            CustomMessageBox.showwarning(self.root, "기능 제한", "pandas 모듈이 없어 Excel 저장이 불가능합니다.")
            return

        selection = tree.selection()
        if not selection:
            CustomMessageBox.showwarning(self.root, "선택 필요", "내보낼 행을 선택하세요.")
            return

        # Get column headers and data
        columns = tree['columns']
        headers = [tree.heading(col, 'text') for col in columns]

        data = []
        for item_id in selection:
            values = tree.item(item_id, 'values')
            row_dict = {h: v for h, v in zip(headers, values)}
            data.append(row_dict)

        df = pd.DataFrame(data)

        filename = f"Export_Selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension='.xlsx',
            filetypes=[('Excel', '*.xlsx'), ('All', '*.*')],
            initialfile=filename
        )
        if path:
            try:
                df.to_excel(path, index=False)
                self._log(f"✅ 선택 영역 Excel 저장: {path}")
                CustomMessageBox.showinfo(self.root, "저장 완료", f"{len(data)}행 저장되었습니다.")
            except Exception as e:
                CustomMessageBox.showerror(self.root, "저장 실패", f"오류: {e}")

    def _paste_to_tree_placeholder(self, tree) -> None:
        """Paste placeholder"""
        # If there is a global paste handler, try to use it
        if hasattr(self, '_on_paste_table'):
             # Ask user if they want to open Paste Dialog
             if CustomMessageBox.askyesno(self.root, "데이터 붙여넣기", "데이터 붙여넣기 창을 여시겠습니까?"):
                 self._on_paste_table()
             return

        CustomMessageBox.showinfo(self.root, "알림", "이 테이블은 직접 붙여넣기를 지원하지 않습니다.\n[데이터 붙여넣기] 메뉴를 이용하세요.")

    def _setup_inventory_context_menu(self) -> None:
        """Setup inventory treeview context menu"""
        from ..utils.constants import Menu

        self.inventory_menu = Menu(self.root, tearoff=0)
        self.inventory_menu.add_command(label="📋 View Details", command=self._view_lot_details)
        self.inventory_menu.add_command(label="🎒 View Tonbags", command=self._view_lot_tonbags)
        self.inventory_menu.add_command(label="📅 LOT 히스토리", command=self._show_lot_history_timeline)
        self.inventory_menu.add_separator()
        self.inventory_menu.add_command(label="✏️ Edit LOT", command=self._edit_lot)
        self.inventory_menu.add_command(label="🗑️ Delete LOT", command=self._delete_lot)
        self.inventory_menu.add_separator()
        self.inventory_menu.add_command(label="📥 Export Selected (DB Full)", command=self._export_selected_lots)
        self.inventory_menu.add_command(label="📥 선택 영역 Excel 저장 (보이는 대로)", command=lambda: self._export_selection_to_excel(self.tree_inventory))
        self.inventory_menu.add_command(label="📋 Copy to Clipboard", command=lambda: self._copy_treeview_selection(self.tree_inventory))

        self.tree_inventory.bind('<Button-3>', self._show_inventory_context_menu)

    def _show_inventory_context_menu(self, event) -> None:
        """Show inventory context menu"""
        # Select row under cursor
        item = self.tree_inventory.identify_row(event.y)
        if item:
            self.tree_inventory.selection_set(item)
            self.inventory_menu.post(event.x_root, event.y_root)

    def _view_lot_details(self) -> None:
        """View LOT details from context menu"""
        selection = self.tree_inventory.selection()
        if not selection:
            return

        values = self.tree_inventory.item(selection[0], 'values')
        if values:
            lot_no = values[0]
            # v3.6.2: _show_lot_detail → _show_lot_detail_popup (정확한 메서드명)
            if hasattr(self, '_show_lot_detail_popup'):
                self._show_lot_detail_popup(str(lot_no))
            else:
                logger.warning(f"LOT 상세 팝업 미구현: {lot_no}")

    def _view_lot_tonbags(self) -> None:
        """View LOT tonbags from context menu"""
        selection = self.tree_inventory.selection()
        if not selection:
            return

        values = self.tree_inventory.item(selection[0], 'values')
        if values:
            lot_no = values[0]
            # v7.0: AVAILABLE 탭으로 이동 후 톤백 보기 (기존 tonbag 탭 → 인덱스 변경)
            if hasattr(self, 'tonbag_search_var'):
                self.tonbag_search_var.set(lot_no)
            if hasattr(self, 'notebook'):
                tab = getattr(self, 'tab_inventory', None)
                if tab:
                    self.notebook.select(tab)  # AVAILABLE (inventory) 탭 — v8.1.6
            if hasattr(self, '_inv_view_switch_var') and getattr(self, '_inv_view_switch_var', None):
                self._inv_view_switch_var.set('tonbag')

    def _edit_lot(self) -> None:
        """Edit LOT from context menu"""
        from ..utils.constants import BOTH, W, X, tk, ttk

        selection = self.tree_inventory.selection()
        if not selection:
            return

        values = self.tree_inventory.item(selection[0], 'values')
        if not values:
            return

        lot_no = values[0]

        # Get current LOT data
        lot_data = self.engine.db.fetchone(
            "SELECT * FROM inventory WHERE lot_no = ?",
            (lot_no,)
        )

        if not lot_data:
            CustomMessageBox.showerror(self.root, "Error", f"LOT not found: {lot_no}")
            return

        # Create edit dialog
        dialog = create_themed_toplevel(self.root)
        dialog.title(f"Edit LOT: {lot_no}")
        apply_modal_window_options(dialog)
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "context_edit_lot_dialog", self.root, "medium")

        # Form frame
        form_frame = ttk.Frame(dialog, padding=10)
        form_frame.pack(fill=BOTH, expand=True)

        # Fields
        fields = {}
        editable_fields = [
            ('sap_no', 'SAP NO'),
            ('bl_no', 'B/L NO'),
            ('product', 'Product'),
            ('container_no', 'Container'),
            ('sold_to', 'Sold To'),
            ('sale_ref', 'Sale Ref'),
            ('warehouse', 'Warehouse'),
            ('remark', 'Remark'),
        ]

        for i, (field, label) in enumerate(editable_fields):
            ttk.Label(form_frame, text=f"{label}:").grid(row=i, column=0, sticky=W, pady=3)
            var = tk.StringVar(value=lot_data.get(field, '') or '')
            entry = ttk.Entry(form_frame, textvariable=var, width=35)
            entry.grid(row=i, column=1, pady=3, padx=5)
            fields[field] = var

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=X, pady=10, padx=10)

        def save_changes():
            try:
                # v7.5.0: 화이트리스트 검증 — SQL 인젝션 방지
                ALLOWED_EDIT_FIELDS = {
                    'sap_no', 'bl_no', 'product', 'container_no',
                    'sold_to', 'sale_ref', 'warehouse', 'remark'
                }
                updates = {
                    field: var.get().strip()
                    for field, var in fields.items()
                    if field in ALLOWED_EDIT_FIELDS
                }
                if not updates:
                    return

                # Build update query (화이트리스트 통과 필드만 사용)
                set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [lot_no]

                self.engine.db.execute(
                    f"UPDATE inventory SET {set_clause} WHERE lot_no = ?",
                    values
                )

                self._log(f"LOT updated: {lot_no}")
                CustomMessageBox.showinfo(self.root, "Success", f"LOT {lot_no} updated")
                dialog.destroy()
                self._safe_refresh()
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                CustomMessageBox.showerror(self.root, "Error", f"Update failed: {e}")

        ttk.Button(btn_frame, text="Save", command=save_changes).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def _delete_lot(self) -> None:
        """Delete LOT from context menu"""


        selection = self.tree_inventory.selection()
        if not selection:
            return

        values = self.tree_inventory.item(selection[0], 'values')
        if not values:
            return

        lot_no = values[0]

        if not CustomMessageBox.askyesno(self.root, "Confirm Delete",
            f"Delete LOT {lot_no}?\n\n"
            f"This will also delete all associated tonbags.\n"
            f"This action cannot be undone."):
            return

        try:
            with self.engine.db.transaction():
                # Delete tonbags first
                self.engine.db.execute(
                    "DELETE FROM inventory_tonbag WHERE lot_no = ?",
                    (lot_no,)
                )
                # Delete LOT
                self.engine.db.execute(
                    "DELETE FROM inventory WHERE lot_no = ?",
                    (lot_no,)
                )

            self._log(f"LOT deleted: {lot_no}")
            CustomMessageBox.showinfo(self.root, "Success", f"LOT {lot_no} deleted")
            self._safe_refresh()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            CustomMessageBox.showerror(self.root, "Error", f"Delete failed: {e}")

    def _export_selected_lots(self) -> None:
        """Export selected LOTs to Excel"""
        from ..utils.constants import HAS_PANDAS, filedialog, pd

        if not HAS_PANDAS:
            CustomMessageBox.showerror(self.root, "Error", "pandas not installed")
            return

        selection = self.tree_inventory.selection()
        if not selection:
            CustomMessageBox.showwarning(self.root, "Warning", "Select LOTs to export")
            return

        # Collect selected LOT numbers
        lot_numbers = []
        for item_id in selection:
            values = self.tree_inventory.item(item_id, 'values')
            if values:
                lot_numbers.append(values[0])

        if not lot_numbers:
            return

        # Get file path
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"selected_lots_{len(lot_numbers)}.xlsx"
        )

        if not file_path:
            return

        try:
            from ..utils.excel_file_helper import get_unique_excel_path
            file_path = get_unique_excel_path(file_path)
            # Get full data for selected LOTs
            placeholders = ','.join(['?'] * len(lot_numbers))
            lots = self.engine.db.fetchall(
                f"SELECT * FROM inventory WHERE lot_no IN ({placeholders})",
                lot_numbers
            )

            df = pd.DataFrame(lots)
            df.to_excel(file_path, index=False)

            self._log(f"Exported {len(lot_numbers)} LOTs to {file_path}")
            CustomMessageBox.showinfo(self.root, "Success", f"Exported {len(lot_numbers)} LOTs")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            CustomMessageBox.showerror(self.root, "Error", f"Export failed: {e}")

    def _setup_tonbag_context_menu(self) -> None:
        """Setup tonbag treeview context menu"""
        from ..utils.constants import Menu

        self.tonbag_menu = Menu(self.root, tearoff=0)
        self.tonbag_menu.add_command(label="Select for Outbound", command=self._select_tonbag_for_outbound)
        self.tonbag_menu.add_command(label="Deselect", command=self._deselect_tonbag)
        self.tonbag_menu.add_separator()
        self.tonbag_menu.add_command(label="Edit Tonbag", command=self._edit_tonbag)
        self.tonbag_menu.add_command(label="Change Status", command=self._change_tonbag_status)
        self.tonbag_menu.add_separator()
        self.tonbag_menu.add_command(label="Copy to Clipboard", command=lambda: self._copy_treeview_selection(self.tree_sublot))

        self.tree_sublot.bind('<Button-3>', self._show_tonbag_context_menu)

    def _show_tonbag_context_menu(self, event) -> None:
        """Show tonbag context menu"""
        item = self.tree_sublot.identify_row(event.y)
        if item:
            self.tree_sublot.selection_set(item)
            self.tonbag_menu.post(event.x_root, event.y_root)

    def _select_tonbag_for_outbound(self) -> None:
        """Select tonbag for outbound"""
        selection = self.tree_sublot.selection()
        if not selection:
            return

        if not hasattr(self, 'selected_tonbags'):
            self.selected_tonbags = set()

        for item_id in selection:
            values = self.tree_sublot.item(item_id, 'values')
            # 톤백 트리는 상태를 한글로 표시 → DB 비교 시 역매핑 또는 한글 직접 비교
            status_display = values[6] if len(values) > 6 else ''
            if values and (status_display == '판매가능' or STATUS_DISPLAY_TO_DB.get(status_display) == 'AVAILABLE'):
                self.selected_tonbags.add(item_id)

        self._set_status(f"Selected tonbags: {len(self.selected_tonbags)}")

    def _deselect_tonbag(self) -> None:
        """Deselect tonbag"""
        selection = self.tree_sublot.selection()
        if not selection:
            return

        if hasattr(self, 'selected_tonbags'):
            for item_id in selection:
                self.selected_tonbags.discard(item_id)

        self._set_status(f"Selected tonbags: {len(getattr(self, 'selected_tonbags', []))}")

    def _edit_tonbag(self) -> None:
        """Edit tonbag from context menu"""

        CustomMessageBox.showinfo(self.root, "Info", "Tonbag edit feature - coming soon")

    def _change_tonbag_status(self) -> None:
        """톤백 상태 변경 (v6.0.4 2단계: 한글 표시·저장 시 DB값 변환)"""
        from ..utils.constants import tk, ttk

        selection = self.tree_sublot.selection()
        if not selection:
            return

        values = self.tree_sublot.item(selection[0], 'values')
        if not values:
            return

        lot_no = values[1]   # lot_no column (0=row_num, 1=lot_no)
        sub_lt_display = values[2]   # tonbag_no_print (표시: 1, 2, S0 등)
        try:
            sub_lt_int = 0 if str(sub_lt_display).strip().upper().startswith('S') or str(sub_lt_display).strip() in ('', '0') else int(float(str(sub_lt_display)))
        except (ValueError, TypeError):
            sub_lt_int = 0
        current_status_display = values[6] if len(values) > 6 else ''  # 한글 상태명

        # 콤보 옵션: 한글 표시 (DB 저장 시 역매핑)
        status_options = ['판매가능', '판매배정', '판매화물 결정', '출고', '소진', '선적', '반품']

        dialog = create_themed_toplevel(self.root)
        dialog.title("상태 변경")
        apply_modal_window_options(dialog)
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "context_status_change_dialog", self.root, "small")

        ttk.Label(dialog, text=f"LOT: {lot_no}, 톤백: {sub_lt_display}").pack(pady=10)
        ttk.Label(dialog, text=f"현재: {current_status_display}").pack()

        status_var = tk.StringVar(value=current_status_display if current_status_display in status_options else status_options[0])
        combo = ttk.Combobox(dialog, textvariable=status_var, values=status_options, state='readonly')
        combo.pack(pady=10)

        def save_status():
            new_display = status_var.get().strip()
            new_status = STATUS_DISPLAY_TO_DB.get(new_display)
            if not new_status:
                CustomMessageBox.showwarning(self.root, "상태", "선택한 상태를 DB 값으로 변환할 수 없습니다.")
                return
            try:
                self.engine.db.execute(
                    "UPDATE inventory_tonbag SET status = ? WHERE lot_no = ? AND sub_lt = ?",
                    (new_status, lot_no, sub_lt_int)
                )
                self._log(f"톤백 상태 변경: {lot_no}-{sub_lt_display} → {new_display}")
                dialog.destroy()
                self._refresh_tonbag()
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                CustomMessageBox.showerror(self.root, "오류", f"상태 변경 실패: {e}")

        ttk.Button(dialog, text="저장", command=save_status).pack(pady=10)

    def _setup_search_context_menu(self) -> None:
        """Setup search treeview context menu"""
        from ..utils.constants import Menu

        self.search_menu = Menu(self.root, tearoff=0)
        self.search_menu.add_command(label="Add to Report", command=self._add_to_search_report)
        self.search_menu.add_command(label="View LOT Details", command=self._view_search_lot_details)
        self.search_menu.add_separator()
        self.search_menu.add_command(label="Copy to Clipboard", command=lambda: self._copy_treeview_selection(self.tree_search))

        self.tree_search.bind('<Button-3>', self._show_search_context_menu)

    def _show_search_context_menu(self, event) -> None:
        """Show search context menu"""
        item = self.tree_search.identify_row(event.y)
        if item:
            self.tree_search.selection_set(item)
            self.search_menu.post(event.x_root, event.y_root)

    def _add_to_search_report(self) -> None:
        """Add search result to report"""
        selection = self.tree_search.selection()
        if not selection:
            return

        if not hasattr(self, 'selected_search_items'):
            self.selected_search_items = set()

        for item_id in selection:
            self.selected_search_items.add(item_id)

        self._set_status(f"Report items: {len(self.selected_search_items)}")

    def _view_search_lot_details(self) -> None:
        """View LOT details from search result"""
        selection = self.tree_search.selection()
        if not selection:
            return

        values = self.tree_search.item(selection[0], 'values')
        if values and len(values) > 3:
            lot_no = values[3]  # lot_no column
            # v3.6.2: _show_lot_detail → _show_lot_detail_popup
            if hasattr(self, '_show_lot_detail_popup'):
                self._show_lot_detail_popup(str(lot_no))
            else:
                logger.warning(f"LOT 상세 팝업 미구현: {lot_no}")

    def _show_lot_history_timeline(self) -> None:
        """v3.9.5: LOT 히스토리 타임라인 (입고→출고 추적 뷰)"""
        from ..utils.constants import BOTH, LEFT, RIGHT, VERTICAL, YES, W, X, Y, tk, ttk
        from ..utils.ui_constants import CustomMessageBox, ThemeColors

        selection = self.tree_inventory.selection()
        if not selection:
            return

        values = self.tree_inventory.item(selection[0], 'values')
        if not values:
            return
        lot_no = str(values[1])

        try:
            lot = self.engine.get_lot_detail(lot_no)
            if lot.get('error'):
                CustomMessageBox.showwarning(self.root, "경고", f"LOT 조회 실패: {lot.get('error')}")
                return
        except (ValueError, TypeError, AttributeError) as e:
            CustomMessageBox.showwarning(self.root, "경고", f"LOT 조회 오류: {e}")
            return

        dialog = create_themed_toplevel(self.root)
        dialog.title(f"📅 LOT 히스토리 — {lot_no}")
        apply_modal_window_options(dialog)
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "context_lot_history_dialog", self.root, "medium")

        _is_dark = is_dark()
        _bg = ThemeColors.get('bg_card', _is_dark)
        _fg = ThemeColors.get('text_primary', _is_dark)
        _accent = ThemeColors.get('statusbar_progress', _is_dark)
        _green = ThemeColors.get('badge_db', _is_dark)
        _orange = ThemeColors.get('statusbar_icon_warn', _is_dark)
        _red = ThemeColors.get('statusbar_icon_err', _is_dark)

        dialog.configure(bg=_bg)

        # 헤더
        header = tk.Frame(dialog, bg=_accent, pady=10)
        header.pack(fill=X)
        _header_fg = ThemeColors.get('badge_text', _is_dark)
        tk.Label(header, text="📅 LOT 히스토리 타임라인",
                 bg=_accent, fg=_header_fg, font=('맑은 고딕', 14, 'bold')).pack()
        tk.Label(header, text=f"LOT: {lot_no} | SAP: {lot.get('sap_no', '')} | {lot.get('product', '')}",
                 bg=_accent, fg=_header_fg, font=('맑은 고딕', 10)).pack()

        # 타임라인
        canvas_frame = tk.Frame(dialog, bg=_bg)
        canvas_frame.pack(fill=BOTH, expand=YES, padx=10, pady=5)

        canvas = tk.Canvas(canvas_frame, bg=_bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient=VERTICAL, command=canvas.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = tk.Frame(canvas, bg=_bg)
        canvas.create_window((0, 0), window=inner, anchor='nw')

        events = []

        if lot.get('ship_date'):
            events.append(('🚢', lot['ship_date'], '선적 (Ship)',
                          f"선박: {lot.get('vessel', '')} | BL: {lot.get('bl_no', '')}", _accent))

        if lot.get('arrival_date'):
            events.append(('📥', lot['arrival_date'], '입항/입고 (Arrival)',
                          f"창고: {lot.get('warehouse', '')} | NET: {float(lot.get('net_weight', 0) or 0):,.0f}kg | MXBG: {lot.get('mxbg_pallet', '')}",
                          _green))

        if lot.get('free_time') and lot.get('arrival_date'):
            try:
                from datetime import datetime, timedelta
                arr = datetime.strptime(lot['arrival_date'], '%Y-%m-%d')
                ft_days = int(lot['free_time'])
                ft_date = (arr + timedelta(days=ft_days)).strftime('%Y-%m-%d')
                events.append(('⏰', ft_date, f'Free Time 만료 ({ft_days}일)',
                              f"컨테이너: {lot.get('container_no', '')}", _orange))
            except (ValueError, TypeError) as _e:
                logger.debug(f'Suppressed (ValueError, TypeError): {_e}')

        tonbags = lot.get('tonbags', [])
        for tb in tonbags:
            if tb.get('picked_date'):
                events.append(('📤', tb['picked_date'],
                              f"톤백 #{tb.get('sub_lt', '?')} 판매화물 결정",
                              f"출고처: {tb.get('picked_to', '')} | {float(tb.get('weight', 0) or 0):,.1f}kg",
                              _orange))
            if tb.get('outbound_date'):
                events.append(('✅', tb['outbound_date'],
                              f"톤백 #{tb.get('sub_lt', '?')} 선적 완료",
                              "최종 출고 확정", _green))

        status = lot.get('status', STATUS_AVAILABLE)
        status_colors = {'AVAILABLE': _green, 'PICKED': _orange,
                        'DEPLETED': _red, 'SHIPPED': _accent}
        status_display = get_status_display(status) or status
        events.append(('📌', '현재', f'현재 상태: {status_display}',
                       f"잔량: {float(lot.get('current_weight', 0) or 0):,.0f}kg / {float(lot.get('initial_weight', 0) or 0):,.0f}kg",
                       status_colors.get(status, _fg)))

        events.sort(key=lambda x: x[1] if x[1] != '현재' else 'zzzz')

        for idx, (icon, date, title, detail, color) in enumerate(events):
            row = tk.Frame(inner, bg=_bg, pady=8)
            row.pack(fill=X, padx=10)

            tk.Label(row, text=date, bg=_bg, fg=color,
                     font=('맑은 고딕', 10, 'bold'), width=12, anchor='e').pack(side=LEFT, padx=(0, 10))

            dot = tk.Canvas(row, width=20, height=20, bg=_bg, highlightthickness=0)
            dot.create_oval(4, 4, 16, 16, fill=color, outline=color)
            dot.pack(side=LEFT, padx=5)

            content = tk.Frame(row, bg=_bg)
            content.pack(side=LEFT, fill=X, expand=YES)
            tk.Label(content, text=f"{icon} {title}", bg=_bg, fg=_fg,
                     font=('맑은 고딕', 11, 'bold'), anchor=W).pack(anchor=W)
            tk.Label(content, text=detail, bg=_bg, fg=ThemeColors.get('text_muted', _is_dark),
                     font=('맑은 고딕', 10), anchor=W).pack(anchor=W)

            if idx < len(events) - 1:
                tk.Frame(inner, bg=color, height=1).pack(fill=X, padx=50)

        # 진행률
        pf = tk.Frame(dialog, bg=_bg, pady=10)
        pf.pack(fill=X, padx=20)

        init_w = float(lot.get('initial_weight', 0) or 0)
        curr_w = float(lot.get('current_weight', 0) or 0)
        pct = ((init_w - curr_w) / init_w * 100) if init_w > 0 else 0

        tk.Label(pf, text=f"출고 진행률: {pct:.1f}%", bg=_bg, fg=_fg,
                 font=('맑은 고딕', 11, 'bold')).pack(anchor=W)

        bar = tk.Canvas(pf, height=20, bg=ThemeColors.get('chart_grid'), highlightthickness=0)
        bar.pack(fill=X, pady=5)
        bar.update_idletasks()
        bw = bar.winfo_width() or 700
        fill_w = max(int(bw * pct / 100), 0)
        bar_c = _green if pct < 50 else (_orange if pct < 90 else _red)
        bar.create_rectangle(0, 0, fill_w, 20, fill=bar_c, outline='')

        tk.Label(pf, text=f"입고: {init_w:,.0f}kg | 출고: {init_w-curr_w:,.0f}kg | 잔량: {curr_w:,.0f}kg",
                 bg=_bg, fg=ThemeColors.get('text_muted', _is_dark), font=('맑은 고딕', 10)).pack(anchor=W)

        ttk.Button(dialog, text="닫기", command=dialog.destroy).pack(pady=10)

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox('all'))
        dialog.bind('<Escape>', lambda e: dialog.destroy())
