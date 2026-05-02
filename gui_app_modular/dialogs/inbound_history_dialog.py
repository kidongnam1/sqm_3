"""
입고현황 조회 다이얼로그 (성능 보완 버전)
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import os
from datetime import datetime as _dt
from datetime import timedelta

logger = logging.getLogger(__name__)


class InboundHistoryDialog:
    """기간별 LOT/톤백 조회 다이얼로그."""

    def __init__(self, parent, engine, log_fn=None, app=None):
        self.parent = parent
        self.engine = engine
        self.app = app
        self._log = log_fn or (lambda msg, **kw: logger.info(msg))

        self.dialog = None
        self.tree_lot = None
        self.tree_tonbag = None
        self.summary_label = None
        self.btn_export = None
        self.entry_start = None
        self.entry_end = None

        self._lot_rows = []
        self._tonbag_rows = []

    def show(self) -> None:
        try:
            self._create_dialog()
        except Exception as e:
            logger.error("입고현황 조회 다이얼로그 초기화 오류: %s", e, exc_info=True)
            try:
                from ..utils.ui_constants import CustomMessageBox
                CustomMessageBox.showerror(self.parent, "오류", f"입고현황 조회 창 초기화 오류:\n{e}")
            except Exception as _ui_e:
                logging.getLogger(__name__).debug(f"[입고현황] 오류 표시 실패: {_ui_e}")
            try:
                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.destroy()
            except Exception as _de:
                logging.getLogger(__name__).debug(f"[입고현황] 다이얼로그 정리 실패: {_de}")

    def _create_dialog(self) -> None:
        from ..utils.constants import BOTH, LEFT, RIGHT, W, X, Y, tk, ttk
        from ..utils.ui_constants import (
            setup_dialog_geometry_persistence,
        )

        self.dialog = create_themed_toplevel(self.parent)
        self.dialog.title("📋 입고현황 조회")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        setup_dialog_geometry_persistence(self.dialog, "inbound_history_dialog", self.parent, "large")

        # 일부 Tk/ttk 조합에서 LabelFrame의 padding 옵션이 오류를 내므로
        # 내부 Frame에 여백을 주는 방식으로 호환성을 확보한다.
        top = ttk.LabelFrame(self.dialog, text="📅 조회 기간 (입고일 기준)")
        top.pack(fill=X, padx=10, pady=(10, 5))
        top_inner = ttk.Frame(top)
        top_inner.pack(fill=X, padx=8, pady=8)

        # v8.6.3: 공통 날짜 범위 바 통일 적용
        try:
            from ..utils.tree_enhancements import make_date_range_bar
            _date_bar, self._start_var, self._end_var = \
                make_date_range_bar(top_inner, self._on_query)
            _date_bar.pack(side=LEFT)
        except Exception as _e:
            import logging as _lg; _lg.getLogger(__name__).warning(f'make_date_range_bar: {_e}')
            self._start_var = tk.StringVar(); self._end_var = tk.StringVar()

        # v8.1.8: 플레이스홀더 — 비우면 전체 기간 조회
        self._start_var = tk.StringVar(value='')
        self._end_var   = tk.StringVar(value='')
        # v8.6.3: StringVar는 make_date_range_bar에서 직접 생성
        try:
            from gui_app_modular.utils.tree_enhancements import attach_date_placeholder
        except Exception as e:
            logger.warning(f'[UI] inbound_history_dialog: {e}')
        for label, days in [("이번 달", 0), ("최근 7일", 7), ("최근 30일", 30), ("최근 90일", 90), ("전체", -1)]:
            ttk.Button(top_inner, text=label, width=8, command=lambda d=days: self._set_quick_range(d)).pack(side=LEFT, padx=2)
        ttk.Button(top_inner, text="🔍 조회", command=self._search).pack(side=LEFT, padx=(10, 0))

        self.summary_label = ttk.Label(self.dialog, text="기간을 선택하고 조회하세요.", anchor=W)
        self.summary_label.pack(fill=X, padx=10)

        nb = ttk.Notebook(self.dialog)
        nb.pack(fill=BOTH, expand=True, padx=10, pady=5)

        lot_frame = ttk.Frame(nb)
        nb.add(lot_frame, text="📦 LOT 기준")
        lot_cols = ("no", "lot_no", "sap_no", "bl_no", "product", "net_weight", "mxbg", "container_no", "warehouse", "stock_date", "status")
        self.tree_lot = ttk.Treeview(lot_frame, columns=lot_cols, show='headings', height=16)
        for col, hdr, w in [
            ("no", "No.", 45), ("lot_no", "LOT No.", 115), ("sap_no", "SAP No.", 115), ("bl_no", "B/L No.", 120),
            ("product", "Product", 135), ("net_weight", "Net(Kg)", 95), ("mxbg", "Tonbag Count", 95),
            ("container_no", "Container", 120), ("warehouse", "Warehouse", 90), ("stock_date", "Inbound Date", 105), ("status", "Status", 85),
        ]:
            self.tree_lot.heading(col, text=hdr, command=lambda c=col: self._sort_tree(self.tree_lot, c), anchor='center')
            self.tree_lot.column(col, width=w, anchor='e' if col in ("no", "net_weight", "mxbg") else 'center')
        sb1y = tk.Scrollbar(lot_frame, orient='vertical', command=self.tree_lot.yview)
        sb1x = tk.Scrollbar(lot_frame, orient='horizontal', command=self.tree_lot.xview)
        self.tree_lot.configure(yscrollcommand=sb1y.set, xscrollcommand=sb1x.set)
        self.tree_lot.pack(side=LEFT, fill=BOTH, expand=True)
        sb1y.pack(side=RIGHT, fill=Y)
        # v8.1.9: TreeviewTotalFooter
        try:
            from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter as _TTF
            _footer = _TTF(
                lot_frame, self.tree_lot,
                summable_column_ids=['net_weight'],
                column_display_names={'net_weight': 'NET(kg)'},
                column_formats={'net_weight': ',.0f'},
            )
            _footer.pack(fill='x')
            self._footer_tree_lot = _footer
        except Exception as e:
            logger.warning(f'[UI] inbound_history_dialog: {e}')
        sb1x.pack(side='bottom', fill=X)

        tb_frame = ttk.Frame(nb)
        nb.add(tb_frame, text="📦 톤백 기준")
        tb_cols = ("no", "lot_no", "sub_lt", "tonbag_no", "weight", "is_sample", "location", "status", "product", "stock_date")
        self.tree_tonbag = ttk.Treeview(tb_frame, columns=tb_cols, show='headings', height=16)
        for col, hdr, w in [
            ("no", "No.", 45), ("lot_no", "LOT No.", 115), ("sub_lt", "Sub LT", 65), ("tonbag_no", "Tonbag No.", 110),
            ("weight", "Weight(Kg)", 90), ("is_sample", "Sample", 70), ("location", "Location", 100), ("status", "Status", 85),
            ("product", "Product", 130), ("stock_date", "Inbound Date", 105),
        ]:
            self.tree_tonbag.heading(col, text=hdr, command=lambda c=col: self._sort_tree(self.tree_tonbag, c), anchor='center')
            self.tree_tonbag.column(col, width=w, anchor='e' if col in ("no", "sub_lt", "weight") else 'center')
        sb2y = tk.Scrollbar(tb_frame, orient='vertical', command=self.tree_tonbag.yview)
        sb2x = tk.Scrollbar(tb_frame, orient='horizontal', command=self.tree_tonbag.xview)
        self.tree_tonbag.configure(yscrollcommand=sb2y.set, xscrollcommand=sb2x.set)
        self.tree_tonbag.pack(side=LEFT, fill=BOTH, expand=True)
        sb2y.pack(side=RIGHT, fill=Y)
        sb2x.pack(side='bottom', fill=X)

        bottom = ttk.Frame(self.dialog)
        bottom.pack(fill=X, padx=8, pady=8)
        ttk.Button(bottom, text="❌ 닫기", command=self.dialog.destroy).pack(side=RIGHT, padx=5)
        self.btn_export = ttk.Button(bottom, text="📊 Excel 내보내기", command=self._export_excel, state='disabled')
        self.btn_export.pack(side=RIGHT, padx=5)

        self._search()

    def _set_quick_range(self, days: int) -> None:
        today = _dt.now()
        self.entry_end.delete(0, 'end')
        self.entry_end.insert(0, today.strftime('%Y-%m-%d'))
        self.entry_start.delete(0, 'end')
        if days == 0:
            self.entry_start.insert(0, today.replace(day=1).strftime('%Y-%m-%d'))
        elif days == -1:
            self.entry_start.insert(0, '2020-01-01')
        else:
            self.entry_start.insert(0, (today - timedelta(days=days)).strftime('%Y-%m-%d'))
        self._search()

    def _search(self) -> None:
        """기간 검색 — v8.1.8: 둘 다 비면 전체 기간 조회."""
        from gui_app_modular.utils.tree_enhancements import parse_date_range

        start_raw = getattr(self, '_start_var', None)
        start_raw = start_raw.get().strip() if start_raw else self.entry_start.get().strip()
        end_raw   = getattr(self, '_end_var', None)
        end_raw   = end_raw.get().strip() if end_raw else self.entry_end.get().strip()
        # 플레이스홀더 텍스트는 빈 값으로 처리
        if start_raw == 'YYYY-MM-DD': start_raw = ''
        if end_raw   == 'YYYY-MM-DD': end_raw   = ''
        d_from, d_to = parse_date_range(start_raw, end_raw)

        # 둘 다 비면 전체 기간 — WHERE 조건 없이 조회
        if d_from is None and d_to is None:
            where_clause = "1=1"
            params = ()
            start, end = '', ''
        else:
            start = d_from or '2000-01-01'
            end   = d_to   or '2099-12-31'
            end_plus1 = (_dt.strptime(end, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            # stock_date 우선, 누락분은 created_at 폴백
            where_clause = (
                "((stock_date IS NOT NULL AND stock_date <> '' AND stock_date >= ? AND stock_date < ?) "
                "OR ((stock_date IS NULL OR stock_date = '') AND created_at >= ? AND created_at < ?))"
            )
            params = (start, end_plus1, start, end_plus1)

        try:
            self._lot_rows = self.engine.db.fetchall(
                "SELECT lot_no, sap_no, bl_no, product, net_weight, mxbg_pallet, container_no, warehouse, stock_date, status "
                f"FROM inventory WHERE {where_clause} ORDER BY stock_date DESC, lot_no",
                params
            ) or []
        except Exception as e:
            logger.debug(f"입고 LOT 조회 오류: {e}")
            self._lot_rows = []

        try:
            self._tonbag_rows = self.engine.db.fetchall(
                "SELECT t.lot_no, t.sub_lt, t.tonbag_no, t.weight, t.is_sample, t.location, t.status, "
                "       i.product, i.stock_date "
                "FROM inventory_tonbag t "
                "JOIN inventory i ON t.lot_no = i.lot_no "
                f"WHERE {where_clause} "
                "ORDER BY t.lot_no, t.sub_lt",
                params
            ) or []
        except Exception as e:
            logger.debug(f"입고 톤백 조회 오류: {e}")
            self._tonbag_rows = []

        self._display_results(start, end)

    def _val(self, row, idx, key):
        if hasattr(row, 'keys'):
            return row.get(key, '') or ''
        try:
            return row[idx] if row[idx] is not None else ''
        except (IndexError, TypeError):
            return ''

    def _display_results(self, start: str, end: str) -> None:
        self.tree_lot.delete(*self.tree_lot.get_children())
        self.tree_tonbag.delete(*self.tree_tonbag.get_children())

        total_net = 0.0
        for i, r in enumerate(self._lot_rows, 1):
            nw = float(self._val(r, 4, 'net_weight') or 0)
            total_net += nw
            self.tree_lot.insert('', 'end', values=(
                i,
                self._val(r, 0, 'lot_no'),
                self._val(r, 1, 'sap_no'),
                self._val(r, 2, 'bl_no'),
                self._val(r, 3, 'product'),
                f"{nw:,.1f}",
                self._val(r, 5, 'mxbg_pallet'),
                self._val(r, 6, 'container_no'),
                self._val(r, 7, 'warehouse'),
                str(self._val(r, 8, 'stock_date'))[:10],
                self._val(r, 9, 'status'),
            ))

        for i, r in enumerate(self._tonbag_rows, 1):
            is_sample = str(self._val(r, 4, 'is_sample'))
            self.tree_tonbag.insert('', 'end', values=(
                i,
                self._val(r, 0, 'lot_no'),
                self._val(r, 1, 'sub_lt'),
                self._val(r, 2, 'tonbag_no'),
                f"{float(self._val(r, 3, 'weight') or 0):,.1f}",
                '샘플' if is_sample == '1' else '',
                self._val(r, 5, 'location'),
                self._val(r, 6, 'status'),
                self._val(r, 7, 'product'),
                str(self._val(r, 8, 'stock_date') or '')[:10],
            ))

        lot_cnt = len(self._lot_rows)
        tb_cnt = len(self._tonbag_rows)
        sample_cnt = sum(1 for r in self._tonbag_rows if str(self._val(r, 4, 'is_sample')) == '1')
        self.summary_label.configure(
            text=f"📊 {start} ~ {end} | LOT Rows: {lot_cnt:,}건 | Tonbag Rows: {tb_cnt:,}건 (Sample {sample_cnt:,}) | Total Weight: {total_net:,.1f} Kg"
        )
        self.btn_export.configure(state='normal' if lot_cnt > 0 else 'disabled')

    def _sort_tree(self, tree, col) -> None:
        items = [(tree.set(k, col), k) for k in tree.get_children('')]
        try:
            items.sort(key=lambda t: float(str(t[0]).replace(',', '')))
        except (ValueError, TypeError):
            items.sort(key=lambda t: str(t[0]))
        reverse = getattr(tree, f'_sort_reverse_{col}', False)
        if reverse:
            items.reverse()
        setattr(tree, f'_sort_reverse_{col}', not reverse)
        for idx, (_, k) in enumerate(items):
            tree.move(k, '', idx)

    def _export_excel(self) -> None:
        from ..utils.constants import filedialog
        from ..utils.ui_constants import CustomMessageBox
        if not self._lot_rows:
            CustomMessageBox.showwarning(self.dialog, "경고", "내보낼 데이터가 없습니다.")
            return

        start = self.entry_start.get().strip().replace('-', '')
        end = self.entry_end.get().strip().replace('-', '')
        save_path = filedialog.asksaveasfilename(
            parent=self.parent,
            title="Excel 저장",
            defaultextension=".xlsx",
            initialfile=f"입고현황_{start}_{end}.xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if not save_path:
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws1 = wb.active
            ws1.title = "LOT 기준"
            ws1.append(['No.', 'LOT No.', 'SAP No.', 'B/L No.', '제품', 'NET(Kg)', '톤백수', '컨테이너', '창고', '입고일', '상태'])
            for i, r in enumerate(self._lot_rows, 1):
                ws1.append([
                    i, self._val(r, 0, 'lot_no'), self._val(r, 1, 'sap_no'), self._val(r, 2, 'bl_no'),
                    self._val(r, 3, 'product'), float(self._val(r, 4, 'net_weight') or 0),
                    int(float(self._val(r, 5, 'mxbg_pallet') or 0)), self._val(r, 6, 'container_no'),
                    self._val(r, 7, 'warehouse'), str(self._val(r, 8, 'stock_date'))[:10], self._val(r, 9, 'status')
                ])

            ws2 = wb.create_sheet("톤백 기준")
            ws2.append(['No.', 'LOT No.', 'Sub LT', '톤백번호', '무게(Kg)', '샘플', '위치', '상태', '제품', '입고일'])
            for i, r in enumerate(self._tonbag_rows, 1):
                ws2.append([
                    i, self._val(r, 0, 'lot_no'), self._val(r, 1, 'sub_lt'), self._val(r, 2, 'tonbag_no'),
                    float(self._val(r, 3, 'weight') or 0), '샘플' if str(self._val(r, 4, 'is_sample')) == '1' else '',
                    self._val(r, 5, 'location'), self._val(r, 6, 'status'), self._val(r, 7, 'product'),
                    str(self._val(r, 8, 'stock_date') or '')[:10]
                ])

            try:
                from utils.sqm_excel_alignment import apply_sqm_workbook_alignment
                apply_sqm_workbook_alignment(wb)
            except Exception:
                pass
            wb.save(save_path)
            CustomMessageBox.showinfo(self.dialog, "완료", f"저장 완료: {os.path.basename(save_path)}")
            try:
                os.startfile(save_path)
            except (AttributeError, OSError) as e:
                logger.warning(f"[_export_excel] Suppressed: {e}")
        except ImportError:
            CustomMessageBox.showerror(self.dialog, "오류", "openpyxl이 설치되지 않았습니다.")
        except (OSError, PermissionError) as e:
            CustomMessageBox.showerror(self.dialog, "오류", f"파일 저장 실패:\n{e}")
