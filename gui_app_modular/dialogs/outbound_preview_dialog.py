"""
SQM Inventory - Outbound Preview Dialog
=======================================

v3.6.0 - UI 통일성 적용
- 다이얼로그 크기 표준화 (DialogSize)
- 컬럼 너비 표준화 (ColumnWidth)
- 간격 표준화 (Spacing)
- 테마 색상 대응 (ThemeColors)
- 폰트 스케일링 (FontScale)
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
from typing import Dict, List

from ..utils.ui_constants import (
    CustomMessageBox,
)

logger = logging.getLogger(__name__)



# v9.0: Treeview 테마 헬퍼
def _apply_tv_theme(tree, parent=None, **kw):
    try:
        from gui_app_modular.utils.ui_constants import apply_treeview_theme
        apply_treeview_theme(tree, parent=parent)
    except Exception:
        logger.debug("[SUPPRESSED] exception in outbound_preview_dialog.py")  # noqa

class OutboundPreviewDialogMixin:
    """
    Outbound preview dialog mixin
    
    Mixed into SQMInventoryApp class
    """

    def _show_outbound_preview(self, outbound_data: List[Dict], callback=None) -> None:
        """Show outbound preview before execution"""
        from ..utils.constants import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y, tk, ttk
        from ..utils.ui_constants import (
            ColumnWidth,
            FontScale,
            Spacing,
            ThemeColors,
            setup_dialog_geometry_persistence,
        )

        # === UI 통일성: 폰트 스케일 ===
        try:
            dpi = self.root.winfo_fpixels('1i')
        except (ImportError, ModuleNotFoundError):
            dpi = 96
        fonts = FontScale(dpi)

        # === UI 통일성: 테마 감지 ===
        # v9.1: is_dark() 전역 함수로 통일
        from gui_app_modular.utils.ui_constants import is_dark as _is_dark_fn
        is_dark = _is_dark_fn()

        # === UI 통일성: 다이얼로그 크기 표준화 + 직전 크기 복원 ===
        dialog = create_themed_toplevel(self.root)
        dialog.title("Outbound Preview")
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "outbound_preview_dialog", self.root, "large")

        # === UI 통일성: 간격 표준화 ===
        # Summary frame
        summary_frame = ttk.LabelFrame(dialog, text="Summary")
        summary_frame.pack(fill=X, padx=Spacing.SM, pady=Spacing.SM)

        total_qty = sum(item.get('qty_mt', 0) or item.get('qty_kg', 0)/1000 for item in outbound_data)
        lot_count = len(set(item.get('lot_no', '') for item in outbound_data))

        ttk.Label(summary_frame, text=f"Total Items: {len(outbound_data)}",
                  font=fonts.body()).pack(side=LEFT, padx=Spacing.MD, pady=Spacing.XS)
        ttk.Label(summary_frame, text=f"LOT Count: {lot_count}",
                  font=fonts.body()).pack(side=LEFT, padx=Spacing.MD, pady=Spacing.XS)
        ttk.Label(summary_frame, text=f"Total Quantity: {total_qty:.3f} MT",
                  font=fonts.body(bold=True)).pack(side=LEFT, padx=Spacing.MD, pady=Spacing.XS)

        # Detail frame
        detail_frame = ttk.LabelFrame(dialog, text="Outbound Items")
        detail_frame.pack(fill=BOTH, expand=True, padx=Spacing.SM, pady=Spacing.XS)

        # Treeview
        columns = ("lot_no", "sap_no", "product", "qty_mt", "customer", "sale_ref", "status")
        tree = ttk.Treeview(detail_frame, columns=columns, show="headings", height=15)

        # === UI 통일성: 컬럼 너비 표준화 ===
        column_headers = [
            ("lot_no", "LOT NO"),
            ("sap_no", "SAP NO"),
            ("product", "Product"),
            ("qty_mt", "Qty (MT)"),
            ("customer", "Customer"),
            ("sale_ref", "Sale Ref"),
            ("status", "Status"),
        ]

        column_mapping = {'qty_mt': 'weight', 'sale_ref': 'bl_no'}

        for col, text in column_headers:
            mapped = column_mapping.get(col, col)
            width = ColumnWidth.get(mapped)
            anchor = ColumnWidth.get_anchor(mapped)
            tree.heading(col, text=text, anchor='center')
            tree.column(col, width=width, anchor=anchor)

        scrollbar = tk.Scrollbar(detail_frame, orient=VERTICAL, command=tree.yview)
        scrollbar_x = tk.Scrollbar(detail_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=scrollbar_x.set)

        tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Validate and populate
        errors = []
        warnings = []

        for idx, item in enumerate(outbound_data):
            lot_no = item.get('lot_no', '')
            sap_no = item.get('sap_no', '')
            product = item.get('product', '')
            qty_mt = item.get('qty_mt', 0) or (item.get('qty_kg', 0) / 1000)
            customer = item.get('customer', '') or item.get('sold_to', '')
            sale_ref = item.get('sale_ref', '')

            # Check LOT exists
            lot_data = self.engine.db.fetchone(
                "SELECT lot_no, product_code, current_weight FROM inventory WHERE lot_no = ?",
                (lot_no,)
            )

            status = "OK"
            tag = ''

            if not lot_data:
                status = "LOT Not Found"
                tag = 'error'
                errors.append(f"Row {idx+1}: LOT {lot_no} not found")
            elif qty_mt > lot_data['current_weight'] / 1000:
                status = "Insufficient"
                tag = 'error'
                errors.append(f"Row {idx+1}: LOT {lot_no} insufficient ({qty_mt:.3f} > {lot_data['current_weight']/1000:.3f})")
            elif qty_mt > lot_data['current_weight'] / 1000 * 0.9:
                status = "Near Limit"
                tag = 'warning'
                warnings.append(f"Row {idx+1}: LOT {lot_no} near limit")

            tree.insert('', END, values=(
                lot_no, sap_no, product,
                f"{qty_mt:.3f}", customer, sale_ref, status
            ), tags=(tag,))

        # === UI 통일성: 테마 인식 색상 ===
        # 에러/경고용 색상
        error_bg = ThemeColors.get('picked', is_dark)
        warning_bg = ThemeColors.get('reserved', is_dark)
        _apply_tv_theme(tree, parent=None)  # v9.0
        tree.tag_configure('error', background=error_bg)
        tree.tag_configure('warning', background=warning_bg)

        # v8.1.5: 합계 Footer
        from ..utils.tree_enhancements import TreeviewTotalFooter
        _outbound_footer = TreeviewTotalFooter(
            dialog, tree,
            ['qty_mt'],
            column_display_names={'qty_mt': 'Qty(MT)'}
        )
        _outbound_footer.pack(fill=X, padx=Spacing.SM)
        _outbound_footer.update_totals()

        # Validation result
        if errors:
            result_text = f"❌ {len(errors)} errors found - Cannot proceed"
            result_color = ThemeColors.get('danger', is_dark)
        elif warnings:
            result_text = f"⚠️ {len(warnings)} warnings - Review before proceeding"
            result_color = ThemeColors.get('warning', is_dark)
        else:
            result_text = "✅ All items validated - Ready to proceed"
            result_color = ThemeColors.get('success', is_dark)

        ttk.Label(dialog, text=result_text, foreground=result_color,
                  font=fonts.body(bold=True)).pack(pady=Spacing.XS)

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=X, padx=Spacing.SM, pady=Spacing.SM)

        def execute():
            if errors:
                CustomMessageBox.showerror(self.root, "Cannot Proceed",
                    f"Fix {len(errors)} errors before proceeding:\n\n" +
                    "\n".join(errors[:5]))
                return

            if warnings:
                if not CustomMessageBox.askyesno(self.root, "Warnings",
                    f"There are {len(warnings)} warnings.\n\n" +
                    "\n".join(warnings[:5]) +
                    "\n\nProceed anyway?"):
                    return

            dialog.destroy()
            if callback:
                callback(outbound_data)

        def export_errors():
            if not errors and not warnings:
                CustomMessageBox.showinfo(self.root, "Info", "No errors or warnings to export")
                return

            import pandas as pd

            from ..utils.constants import filedialog

            file_path = filedialog.asksaveasfilename(
                parent=self.root,
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile="outbound_validation_errors.xlsx"
            )

            if not file_path:
                return

            data = []
            for e in errors:
                data.append({'Type': 'Error', 'Message': e})
            for w in warnings:
                data.append({'Type': 'Warning', 'Message': w})

            pd.DataFrame(data).to_excel(file_path, index=False)
            CustomMessageBox.showinfo(self.root, "Exported", f"Exported to:\n{file_path}")

        if not errors:
            ttk.Button(btn_frame, text="Execute Outbound", command=execute, width=15).pack(
                side=LEFT, padx=Spacing.XS
            )

        ttk.Button(btn_frame, text="Export Errors", command=export_errors, width=12).pack(
            side=LEFT, padx=Spacing.XS
        )
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(
            side=RIGHT, padx=Spacing.XS
        )

        # ESC로 닫기
        dialog.bind('<Escape>', lambda e: dialog.destroy())
