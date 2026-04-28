"""
SQM Inventory - Features v2.7 Mixin
===================================

v2.9.91 - Extracted from gui_app.py

v2.7 extended features: stock alerts, batch outbound, predictions, dark mode
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import json
import logging
from pathlib import Path

from ..utils.ui_constants import is_dark, CustomMessageBox, ThemeColors

logger = logging.getLogger(__name__)


class FeaturesV2Mixin:
    """
    v2.7 features mixin
    
    Mixed into SQMInventoryApp class
    """

    def _show_stock_alerts(self) -> None:
        """Show stock alerts (v2.7.0)"""
        from ..utils.constants import BOTH, END, tk, ttk

        if not hasattr(self, 'features_v2') or not self.features_v2:
            CustomMessageBox.showinfo(self.root, "Info", "Extended features not enabled")
            return

        alerts = self.features_v2.stock_monitor.get_all_alerts()

        if not alerts:
            CustomMessageBox.showinfo(self.root, "Stock Alerts", "No stock alerts")
            return

        # Popup window
        popup = create_themed_toplevel(self.root)
        popup.title("Stock Alerts")
        popup.geometry("600x400")
        popup.transient(self.root)

        # Treeview
        columns = ("lot_no", "product", "weight", "level", "message")
        tree = ttk.Treeview(popup, columns=columns, show="headings", height=15)

        tree.heading("lot_no", text="LOT NO", anchor='center')
        tree.heading("product", text="Product", anchor='center')
        tree.heading("weight", text="Weight(MT)", anchor='center')
        tree.heading("level", text="Level", anchor='center')
        tree.heading("message", text="Message", anchor='center')

        tree.column("lot_no", width=120)
        tree.column("product", width=80)
        tree.column("weight", width=80, anchor="e")
        tree.column("level", width=80, anchor="center")
        tree.column("message", width=200)

        for alert in alerts:
            level = alert.get('level', 'INFO')
            tag = 'critical' if level == 'CRITICAL' else 'warning' if level == 'WARNING' else ''

            tree.insert('', END, values=(
                alert.get('lot_no', ''),
                alert.get('product', ''),
                f"{alert.get('current_weight_mt', 0):.3f}",
                level,
                alert.get('message', ''),
            ), tags=(tag,))

        tree.tag_configure('critical', background=ThemeColors.get('picked', is_dark()))
        tree.tag_configure('warning', background=ThemeColors.get('reserved', is_dark()))

        tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        ttk.Button(popup, text="Close", command=popup.destroy).pack(pady=10)

    def _show_batch_outbound(self) -> None:
        """Show batch outbound dialog (v2.7.0)"""
        from ..utils.constants import BOTH, END, LEFT, RIGHT, W, X, tk, ttk

        if not hasattr(self, 'features_v2') or not self.features_v2:
            CustomMessageBox.showinfo(self.root, "Info", "Extended features not enabled")
            return

        popup = create_themed_toplevel(self.root)
        popup.title("Batch Outbound")
        popup.geometry("700x500")
        popup.transient(self.root)
        popup.grab_set()

        # Input frame
        input_frame = ttk.LabelFrame(popup, text="Add Outbound Item")
        input_frame.pack(fill=X, padx=10, pady=5)

        # LOT NO
        ttk.Label(input_frame, text="LOT NO:").grid(row=0, column=0, sticky=W, padx=5, pady=2)
        lot_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=lot_var, width=20).grid(row=0, column=1, padx=5, pady=2)

        # Quantity
        ttk.Label(input_frame, text="Qty(MT):").grid(row=0, column=2, sticky=W, padx=5, pady=2)
        qty_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=qty_var, width=10).grid(row=0, column=3, padx=5, pady=2)

        # Customer
        ttk.Label(input_frame, text="Customer:").grid(row=1, column=0, sticky=W, padx=5, pady=2)
        customer_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=customer_var, width=30).grid(row=1, column=1, columnspan=3, sticky=W, padx=5, pady=2)

        # Items list
        list_frame = ttk.LabelFrame(popup, text="Batch Items")
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        columns = ("lot_no", "qty", "customer")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)

        tree.heading("lot_no", text="LOT NO", anchor='center')
        tree.heading("qty", text="Qty(MT)", anchor='center')
        tree.heading("customer", text="Customer", anchor='center')

        tree.column("lot_no", width=150)
        tree.column("qty", width=100, anchor="e")
        tree.column("customer", width=200)

        tree.pack(fill=BOTH, expand=True)

        # Summary
        summary_var = tk.StringVar(value="Items: 0 | Total: 0.000 MT")
        ttk.Label(popup, textvariable=summary_var, font=('', 13, 'bold')).pack(pady=5)

        batch_items = []

        def add_item():
            lot_no = lot_var.get().strip()
            qty_str = qty_var.get().strip()
            customer = customer_var.get().strip()

            if not lot_no or not qty_str:
                CustomMessageBox.showwarning(self.root, "Input Required", "Enter LOT NO and Quantity")
                return

            try:
                qty = float(qty_str)
            except ValueError:
                CustomMessageBox.showwarning(self.root, "Invalid", "Invalid quantity")
                return

            batch_items.append({
                'lot_no': lot_no,
                'qty_mt': qty,
                'sold_to': customer,
            })

            tree.insert('', END, values=(lot_no, f"{qty:.3f}", customer))

            # Update summary
            total = sum(item['qty_mt'] for item in batch_items)
            summary_var.set(f"Items: {len(batch_items)} | Total: {total:.3f} MT")

            # Clear inputs
            lot_var.set('')
            qty_var.set('')

        def execute_batch():
            if not batch_items:
                CustomMessageBox.showwarning(self.root, "No Items", "Add items first")
                return

            total = sum(item['qty_mt'] for item in batch_items)
            if not CustomMessageBox.askyesno(self.root, "Confirm Batch Outbound",
                f"Execute batch outbound?\n\n"
                f"Items: {len(batch_items)}\n"
                f"Total: {total:.3f} MT"):
                return

            try:
                result = self.engine.process_outbound(batch_items, source='EXCEL', stop_at_picked=False)

                if result.get('success'):
                    CustomMessageBox.showinfo(self.root, "Complete",
                        f"Batch outbound complete!\n\n"
                        f"Processed: {result.get('items_processed', 0)}\n"
                        f"Total: {result.get('total_picked', 0):.3f} MT")
                    popup.destroy()
                    self._refresh_inventory()
                else:
                    errors = '\n'.join(result.get('errors', [])[:5])
                    CustomMessageBox.showerror(self.root, "Error", f"Outbound failed:\n{errors}")
            except (RuntimeError, ValueError) as e:
                CustomMessageBox.showerror(self.root, "Error", f"Batch outbound error:\n{e}")

        def remove_selected():
            selected = tree.selection()
            if not selected:
                return

            for item_id in selected:
                idx = tree.index(item_id)
                if idx < len(batch_items):
                    batch_items.pop(idx)
                tree.delete(item_id)

            # Update summary
            total = sum(item['qty_mt'] for item in batch_items)
            summary_var.set(f"Items: {len(batch_items)} | Total: {total:.3f} MT")

        # Buttons
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(fill=X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Add Item", command=add_item).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove", command=remove_selected).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Execute Batch", command=execute_batch).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=popup.destroy).pack(side=RIGHT, padx=5)

    def _show_outbound_prediction(self) -> None:
        """Show outbound prediction (v2.7.0)"""
        from ..utils.constants import BOTH, END, tk, ttk

        if not hasattr(self, 'features_v2') or not self.features_v2:
            CustomMessageBox.showinfo(self.root, "Info", "Extended features not enabled")
            return

        predictions = self.features_v2.outbound_predictor.get_all_predictions()

        if not predictions:
            CustomMessageBox.showinfo(self.root, "Outbound Prediction", "No prediction data")
            return

        popup = create_themed_toplevel(self.root)
        popup.title("Outbound Prediction (LOT Depletion)")
        popup.geometry("700x450")
        popup.transient(self.root)

        columns = ("lot_no", "product", "weight", "predicted", "days")
        tree = ttk.Treeview(popup, columns=columns, show="headings", height=15)

        tree.heading("lot_no", text="LOT NO", anchor='center')
        tree.heading("product", text="Product", anchor='center')
        tree.heading("weight", text="Weight(MT)", anchor='center')
        tree.heading("predicted", text="Predicted Depletion", anchor='center')
        tree.heading("days", text="Days Left", anchor='center')

        tree.column("lot_no", width=150)
        tree.column("product", width=80)
        tree.column("weight", width=80, anchor="e")
        tree.column("predicted", width=120, anchor="center")
        tree.column("days", width=80, anchor="center")

        for pred in predictions:
            days = pred.get('days_remaining')
            days_text = f"{days} days" if days else "N/A"

            tag = ''
            if days and days <= 7:
                tag = 'urgent'
            elif days and days <= 30:
                tag = 'warning'

            tree.insert('', END, values=(
                pred['lot_no'],
                pred['product'],
                f"{pred['current_weight_mt']:.3f}",
                pred['predicted_depletion'],
                days_text
            ), tags=(tag,))

        tree.tag_configure('urgent', background=ThemeColors.get('picked', is_dark()))
        tree.tag_configure('warning', background=ThemeColors.get('reserved', is_dark()))

        tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        ttk.Button(popup, text="Close", command=popup.destroy).pack(pady=10)

    def _toggle_dark_mode(self) -> None:
        """Toggle dark mode (v2.8.3)"""
        from ..utils.constants import HAS_TTKBOOTSTRAP

        try:
            if HAS_TTKBOOTSTRAP and hasattr(self.root, 'style'):
                current = getattr(self, 'current_theme', 'darkly')

                dark_themes = ['darkly', 'cyborg', 'solar', 'superhero', 'vapor']

                if current in dark_themes:
                    new_theme = 'darkly'  # Light (v3.0)
                else:
                    new_theme = 'darkly'  # Dark

                try:
                    self.root.style.theme_use(new_theme)
                    self.current_theme = new_theme
                    self._save_theme_preference(new_theme)

                    mode = "Dark Mode" if new_theme in dark_themes else "Light Mode"
                    self._log(f"{mode} applied (theme: {new_theme})")
                except (ValueError, TypeError, AttributeError) as e:
                    CustomMessageBox.showwarning(self.root, "Theme Change Failed",
                        f"Theme change error: {e}\n\n"
                        "Restart app and try again.")
            else:
                if hasattr(self, 'theme_manager') and self.theme_manager:
                    new_theme = self.theme_manager.toggle_theme()
                    CustomMessageBox.showinfo(self.root, "Theme Changed",
                        f"Theme changed to '{new_theme}'.\n"
                        "Changes apply on restart.")
                else:
                    CustomMessageBox.showinfo(self.root, "Info", "Theme feature not enabled")
        except (RuntimeError, ValueError) as e:
            logger.error(f"Theme toggle error: {e}")
            CustomMessageBox.showerror(self.root, "Error", f"Theme error:\n{e}")

    # v3.6.2: _save/_load_theme_preference 제거 (theme_mixin.py에서 정의)
    # MRO 충돌 방지

    def _save_filter_preset(self) -> None:
        """Save current filter as preset (v2.7.0)"""


        if not hasattr(self, 'filter_presets'):
            self.filter_presets = {}

        filters = {
            'status': self.status_var.get() if hasattr(self, 'status_var') else 'ALL',
            'search': self.search_var.get() if hasattr(self, 'search_var') else ''
        }

        name = CustomMessageBox.askstring(
            self.root, "Save Filter", "Enter preset name:"
        )

        if not name:
            return

        self.filter_presets[name] = filters
        self._persist_filter_presets()

        CustomMessageBox.showinfo(self.root, "Saved", f"Filter preset '{name}' saved")

    def _load_filter_preset(self) -> None:
        """Load filter preset (v2.7.0)"""
        from ..utils.constants import tk

        if not hasattr(self, 'filter_presets') or not self.filter_presets:
            CustomMessageBox.showinfo(self.root, "Info", "No saved filter presets")
            return

        # Create selection dialog
        popup = create_themed_toplevel(self.root)
        popup.title("Load Filter Preset")
        popup.geometry("300x200")
        popup.transient(self.root)
        popup.grab_set()

        from ..utils.constants import BOTH, END, ttk

        listbox = tk.Listbox(popup, height=8)
        listbox.pack(fill=BOTH, expand=True, padx=10, pady=10)

        for name in self.filter_presets.keys():
            listbox.insert(END, name)

        def load_selected():
            selection = listbox.curselection()
            if not selection:
                return

            name = listbox.get(selection[0])
            filters = self.filter_presets.get(name, {})

            if hasattr(self, 'status_var'):
                self.status_var.set(filters.get('status', 'ALL'))
            if hasattr(self, 'search_var'):
                self.search_var.set(filters.get('search', ''))

            self._refresh_inventory()
            popup.destroy()

        ttk.Button(popup, text="Load", command=load_selected).pack(pady=5)
        ttk.Button(popup, text="Cancel", command=popup.destroy).pack()

    def _persist_filter_presets(self) -> None:
        """Save filter presets to file"""
        try:
            presets_file = Path(__file__).parent.parent.parent / "filter_presets.json"
            with open(presets_file, 'w', encoding='utf-8') as f:
                json.dump(self.filter_presets, f, ensure_ascii=False, indent=2)
        except (OSError, IOError, PermissionError) as e:
            logger.warning(f"Filter presets save failed: {e}")

    def _generate_daily_report(self) -> None:
        """Generate daily report (v2.7.0)"""


        if not hasattr(self, 'features_v2') or not self.features_v2:
            CustomMessageBox.showinfo(self.root, "Info", "Extended features not enabled")
            return

        try:
            report = self.features_v2.generate_daily_report()

            if report:
                CustomMessageBox.showinfo(self.root, "Daily Report Generated",
                    f"Report saved to:\n{report.get('path', 'N/A')}")
            else:
                CustomMessageBox.showwarning(self.root, "Warning", "Report generation failed")
        except (RuntimeError, ValueError) as e:
            CustomMessageBox.showerror(self.root, "Error", f"Report error:\n{e}")
