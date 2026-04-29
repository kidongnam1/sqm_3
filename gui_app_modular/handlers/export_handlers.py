"""
SQM Inventory - Export Handlers
===============================

v2.9.91 - Extracted from gui_app.py

Excel export functions
"""

import logging
import os
from datetime import date

from ..utils.ui_constants import CustomMessageBox

logger = logging.getLogger(__name__)


class ExportHandlersMixin:
    """
    Export handlers mixin
    
    Mixed into SQMInventoryApp class
    """

    def _on_export_click(self, option: int = 1) -> None:
        """
        Export button click
        
        Args:
            option: Export format
                1 = Customs format
                3 = Ruby format (18 columns)
                4 = Sub LOT format
                5 = LOT format
                6 = Combined format (LOT + Tonbag)
                7 = Detailed inventory
        """
        from ..utils.constants import filedialog

        today_str = date.today().strftime('%Y_%m_%d')

        # File names by option
        option_config = {
            1: ("SQM-Customs-{}.xlsx", "Customs"),
            3: ("SQM-Inventory-{}.xlsx", "Inventory (Ruby)"),
            4: ("SQM-SubLOT-{}.xlsx", "Sub LOT"),
            5: ("SQM-LOT-{}.xlsx", "LOT"),
            6: ("SQM-Combined-{}.xlsx", "Combined (LOT+Tonbag)"),
            7: ("SQM-DetailedInventory-{}.xlsx", "Detailed Inventory"),
            8: ("SQM-ReturnHistory-{}.xlsx", "Return History"),
            9: ("SQM-IntegrityReport-{}.xlsx", "Integrity Report"),
            10: ("Detail_of_Outbound_{}.xlsx", "Outbound Report"),
            11: ("Sales_order_DN_{}.xlsx", "Sales Order DN Report"),
        }

        file_template, option_name = option_config.get(option, option_config[1])
        default_name = file_template.format(today_str)

        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title=f"Save Location ({option_name})",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )

        if not file_path:
            return

        # Start task
        self._start_task("Excel Export", f"Exporting... ({option_name})")
        self._log(f"Excel export [{option_name}]: {os.path.basename(file_path)}")

        try:
            self._log("Loading data...")
            self._log("Creating Excel...")

            include_sample = True
            if option == 4:
                choice = CustomMessageBox.askyesnocancel(
                    self.root,
                    "톤백리스트 출력 기준",
                    "톤백리스트 Excel 출력 기준을 선택하세요.\n\n"
                    "예(YES): 샘플 포함\n"
                    "아니오(NO): 샘플 제외\n"
                    "취소(CANCEL): 출력 중단"
                )
                if choice is None:
                    self._end_task(False, "사용자 취소")
                    self._log("톤백리스트 Excel 출력 취소")
                    return
                include_sample = bool(choice)

            # 같은 이름 파일 있으면 _1, _2 ... 붙여 저장 (엔진 내부 처리)
            actual_path = self.engine.export_to_excel(
                file_path,
                option=option,
                include_sample=include_sample
            )

            self._end_task(True, f"OK Export complete: {os.path.basename(actual_path)}")
            self._log(f"OK Export complete: {actual_path}")

            # Option-specific message
            messages = {
                3: "Export complete (Ruby format)\n\n18 columns",
                4: "Export complete (Sub LOT)\n\nTonbag level details",
                6: "Export complete (Combined)\n\nLOT + Tonbag combined",
                7: "Export complete (Detailed)\n\nAll tonbag details (14 columns)",
            }
            msg = messages.get(option, "Export complete")

            if CustomMessageBox.askyesno(self.root, "Complete", f"{msg}\n\nOpen file?"):
                self._open_file(actual_path)

        except (OSError, IOError, PermissionError) as e:
            self._end_task(False, f"Export failed: {str(e)[:50]}...")
            self._log(f"X Export failed: {e}")
            CustomMessageBox.showerror(self.root, "Error", f"Export failed\n{e}")

    def _open_file(self, file_path: str) -> None:
        """Open file with default application. Excel 동일 이름 열림 시 순번 붙여서 오픈 제안."""
        from ..utils.excel_file_helper import open_excel_with_fallback

        def _ask_yes(title: str, msg: str) -> bool:
            return CustomMessageBox.askyesno(self.root, title, msg)

        ok = open_excel_with_fallback(
            self.root, file_path,
            ask_yes=_ask_yes,
        )
        if ok:
            self._log(f"File opened: {os.path.basename(file_path)}")
        else:
            self._log("WARNING Failed to open file (or user chose no)")
            CustomMessageBox.showwarning(
                self.root, "파일 열기",
                "같은 이름의 파일이 열려있습니다.\n파일을 닫은 후 다시 시도하세요."
            )

    def _export_tonbag_list(self) -> None:
        """Export tonbag list to Excel"""
        from ..utils.constants import HAS_PANDAS, filedialog, pd

        if not HAS_PANDAS:
            CustomMessageBox.showerror(self.root, "Error", "pandas not installed")
            return

        try:
            # Get tonbag data
            tonbags = self.engine.get_all_tonbags()

            if not tonbags:
                CustomMessageBox.showwarning(self.root, "Warning", "No tonbag data")
                return

            # Select save path
            file_path = filedialog.asksaveasfilename(
                parent=self.root,
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"tonbag_list_{len(tonbags)}.xlsx"
            )

            if not file_path:
                return

            from ..utils.excel_file_helper import get_unique_excel_path
            file_path = get_unique_excel_path(file_path)
            # Create DataFrame
            df = pd.DataFrame(tonbags)
            df.to_excel(file_path, index=False)

            self._log(f"Tonbag list exported: {file_path}")
            CustomMessageBox.showinfo(self.root, "Complete",
                f"Tonbag list exported.\n\n"
                f"Records: {len(tonbags)}\n"
                f"File: {file_path}")

            if CustomMessageBox.askyesno(self.root, "Open", "Open file?"):
                self._open_file(file_path)

        except (RuntimeError, ValueError) as e:
            logger.error(f"Tonbag export error: {e}")
            CustomMessageBox.showerror(self.root, "Error", f"Export failed: {e}")
