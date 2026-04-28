"""
SQM v4.1.2 — 품목관리 핸들러
==============================

품목별 재고 요약, LOT 조회, 입출고 현황
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import sqlite3

from ..utils.ui_constants import CustomMessageBox, ThemeColors

# v9.0: Treeview 테마 색상 헬퍼
try:
    from gui_app_modular.utils.ui_constants import apply_treeview_theme as _apply_tv_theme
except Exception:
    def _apply_tv_theme(tree, parent=None, **kw): pass


logger = logging.getLogger(__name__)


class ProductManagementMixin:
    """품목관리 Mixin — SQMInventoryApp에 mix-in"""

    def _show_product_summary(self) -> None:
        """v4.1.2: 품목별 재고 요약 팝업"""
        from ..utils.constants import BOTH, END, LEFT, RIGHT, VERTICAL, Y, tk, ttk

        popup = create_themed_toplevel(self.root)
        popup.title("📋 품목별 재고 요약")
        try:
            from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence as _sgp
            _sgp(popup, "product_inventory_summary_popup", self.root, "large")
        except Exception as e:
            logger.warning(f'[UI] product_handlers: {e}')
        popup.geometry("800x500")
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="📋 품목별 재고 요약",
                 font=('맑은 고딕', 16, 'bold'), fg=ThemeColors.get('text_primary')).pack(pady=10)

        cols = ('product', 'lots', 'tonbags', 'avail_tb', 'total_kg', 'avail_kg', 'out_pct')
        tree = ttk.Treeview(popup, columns=cols, show='headings', height=15)
        for cid, txt, w, anchor in [
            ('product', '제품명', 180, 'w'), ('lots', 'LOT수', 60, 'center'),
            ('tonbags', '톤백(전체)', 80, 'center'), ('avail_tb', '톤백(판매가능)', 80, 'center'),
            ('total_kg', '입고량(kg)', 110, 'e'), ('avail_kg', '잔량(kg)', 110, 'e'),
            ('out_pct', '출고율', 70, 'center'),
        ]:
            tree.heading(cid, text=txt, anchor='center')
            tree.column(cid, width=w, anchor=anchor)

        sb = tk.Scrollbar(popup, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 0), pady=5)
        sb.pack(side=RIGHT, fill=Y, padx=(0, 10), pady=5)
        # v8.1.9: TreeviewTotalFooter
        try:
            from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter as _TTF
            _f = _TTF(popup, tree, summable_column_ids=[])
            _f.pack(fill='x', padx=(10, 0))
        except Exception as e:
            logger.warning(f'[UI] product_handlers: {e}')
        try:
            rows = self.engine.db.fetchall("""
                SELECT
                    i.product,
                    COUNT(DISTINCT i.lot_no) AS lots,
                    COUNT(t.id) AS tonbags,
                    SUM(CASE WHEN t.status='AVAILABLE' THEN 1 ELSE 0 END) AS avail_tb,
                    COALESCE(SUM(i.initial_weight), 0) / COUNT(DISTINCT i.lot_no) * COUNT(DISTINCT i.lot_no) AS dummy,
                    COALESCE(SUM(CASE WHEN t.status='AVAILABLE' THEN t.weight ELSE 0 END), 0) AS avail_kg,
                    COALESCE(SUM(t.weight), 0) AS all_tb_kg
                FROM inventory i
                LEFT JOIN inventory_tonbag t ON i.lot_no = t.lot_no
                GROUP BY i.product
                ORDER BY avail_kg DESC
            """)

            # 별도로 입고량 집계
            init_rows = self.engine.db.fetchall("""
                SELECT product, SUM(initial_weight) AS init_kg
                FROM inventory GROUP BY product
            """)
            init_map = {}
            for r in init_rows:
                p = r['product'] if isinstance(r, dict) else r[0]
                k = r['init_kg'] if isinstance(r, dict) else r[1]
                init_map[p] = float(k or 0)

            grand_init = 0
            grand_avail = 0
            for r in rows:
                product = r['product'] if isinstance(r, dict) else r[0]
                lots = r['lots'] if isinstance(r, dict) else r[1]
                tonbags = r['tonbags'] if isinstance(r, dict) else r[2]
                avail_tb = r['avail_tb'] if isinstance(r, dict) else r[3]
                avail_kg = float((r['avail_kg'] if isinstance(r, dict) else r[5]) or 0)
                init_kg = init_map.get(product, 0)
                out_pct = ((init_kg - avail_kg) / max(init_kg, 1)) * 100 if init_kg > 0 else 0

                grand_init += init_kg
                grand_avail += avail_kg

                tree.insert('', END, values=(
                    product or '-', lots or 0, tonbags or 0, avail_tb or 0,
                    f"{init_kg:,.0f}", f"{avail_kg:,.0f}", f"{out_pct:.1f}%"
                ))

            # 합계 행
            g_pct = ((grand_init - grand_avail) / max(grand_init, 1)) * 100 if grand_init > 0 else 0
            tree.insert('', END, values=(
                '합계', '', '', '', f"{grand_init:,.0f}", f"{grand_avail:,.0f}", f"{g_pct:.1f}%"
            ), tags=('total',))
            _apply_tv_theme(tree, parent=None)  # v9.0
            tree.tag_configure('total', background=ThemeColors.get('chart_grid'), font=('맑은 고딕', 10, 'bold'))

        except (sqlite3.OperationalError, sqlite3.DatabaseError, ValueError, KeyError) as e:
            logger.error(f"품목 요약 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"품목 요약 조회 실패:\n{e}")

        ttk.Button(popup, text="닫기", command=popup.destroy).pack(pady=8)
        popup.bind('<Escape>', lambda e: popup.destroy())

    def _show_product_lot_lookup(self) -> None:
        """v4.1.2: 품목별 LOT 조회 — 품목 선택 → 해당 LOT + 톤백 수 표시"""
        from ..utils.constants import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y, tk, ttk

        popup = create_themed_toplevel(self.root)
        popup.title("🔍 품목별 LOT 조회")
        popup.geometry("850x550")
        popup.transient(self.root)
        popup.grab_set()

        # 상단: 품목 선택
        sel_frame = ttk.Frame(popup, padding=8)
        sel_frame.pack(fill=X)
        ttk.Label(sel_frame, text="🔍 품목 선택:", font=('맑은 고딕', 12, 'bold')).pack(side=LEFT, padx=5)

        product_var = tk.StringVar(value='전체')
        try:
            products = self.engine.db.fetchall("SELECT DISTINCT product FROM inventory ORDER BY product")
            prod_list = ['전체'] + [str(p['product'] if isinstance(p, dict) else p[0]) for p in products]
        except (sqlite3.OperationalError, sqlite3.DatabaseError, ValueError):
            prod_list = ['전체']

        combo = ttk.Combobox(sel_frame, textvariable=product_var, values=prod_list,
                             state='readonly', width=25)
        combo.pack(side=LEFT, padx=5)

        # 트리뷰
        cols = ('lot_no', 'sap_no', 'product', 'status', 'init_kg', 'curr_kg',
                'total_tb', 'avail_tb', 'sample_tb', 'inbound_date')
        tree = ttk.Treeview(popup, columns=cols, show='headings', height=16)
        for cid, txt, w, anchor in [
            ('lot_no', 'LOT NO', 100, 'w'), ('sap_no', 'SAP NO', 80, 'w'),
            ('product', '제품', 100, 'w'), ('status', '상태', 80, 'center'),
            ('init_kg', '입고(kg)', 85, 'e'), ('curr_kg', '잔량(kg)', 85, 'e'),
            ('total_tb', '톤백수', 55, 'center'), ('avail_tb', '판매가능', 50, 'center'),
            ('sample_tb', '샘플', 50, 'center'), ('inbound_date', '입고일', 90, 'center'),
        ]:
            tree.heading(cid, text=txt, anchor='center')
            tree.column(cid, width=w, anchor=anchor)

        sb = tk.Scrollbar(popup, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 0), pady=5)
        sb.pack(side=RIGHT, fill=Y, padx=(0, 10), pady=5)
        # v8.1.9: TreeviewTotalFooter
        try:
            from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter as _TTF
            _f = _TTF(popup, tree, summable_column_ids=[])
            _f.pack(fill='x', padx=(10, 0))
        except Exception as e:
            logger.warning(f'[UI] product_handlers: {e}')
        def refresh(event=None):
            for item in tree.get_children():
                tree.delete(item)

            prod = product_var.get()
            try:
                query = """
                    SELECT i.lot_no, i.sap_no, i.product, i.status,
                           i.initial_weight, i.current_weight,
                           COALESCE(i.stock_date, i.inbound_date) AS inbound_date,
                           COUNT(t.id) AS total_tb,
                           SUM(CASE WHEN t.status='AVAILABLE' AND COALESCE(t.is_sample,0)=0 THEN 1 ELSE 0 END) AS avail_tb,
                           SUM(CASE WHEN COALESCE(t.is_sample,0)=1 THEN 1 ELSE 0 END) AS sample_tb
                    FROM inventory i
                    LEFT JOIN inventory_tonbag t ON i.lot_no = t.lot_no
                """
                params = []
                if prod and prod != '전체':
                    query += " WHERE i.product = ?"
                    params.append(prod)
                query += " GROUP BY i.lot_no ORDER BY i.product, i.lot_no"

                rows = self.engine.db.fetchall(query, params)
                for r in rows:
                    lot = r['lot_no'] if isinstance(r, dict) else r[0]
                    sap = (r['sap_no'] if isinstance(r, dict) else r[1]) or ''
                    prd = (r['product'] if isinstance(r, dict) else r[2]) or ''
                    st = (r['status'] if isinstance(r, dict) else r[3]) or ''
                    init = float((r['initial_weight'] if isinstance(r, dict) else r[4]) or 0)
                    curr = float((r['current_weight'] if isinstance(r, dict) else r[5]) or 0)
                    idate = (r['inbound_date'] if isinstance(r, dict) else r[6]) or ''
                    ttb = (r['total_tb'] if isinstance(r, dict) else r[7]) or 0
                    atb = (r['avail_tb'] if isinstance(r, dict) else r[8]) or 0
                    stb = (r['sample_tb'] if isinstance(r, dict) else r[9]) or 0

                    tree.insert('', END, values=(
                        lot, sap, prd, st, f"{init:,.0f}", f"{curr:,.0f}",
                        ttb, atb, stb, str(idate)[:10]
                    ))
            except (sqlite3.OperationalError, sqlite3.DatabaseError, ValueError, KeyError) as e:
                logger.error(f"품목 LOT 조회 오류: {e}")

        combo.bind('<<ComboboxSelected>>', refresh)
        refresh()

        # LOT 더블클릭 → 상세 팝업
        def on_dbl(event):
            sel = tree.selection()
            if sel:
                lot_no = str(tree.item(sel[0])['values'][0])
                if hasattr(self, '_show_lot_detail_popup'):
                    self._show_lot_detail_popup(lot_no)

        tree.bind('<Double-1>', on_dbl)

        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="닫기", command=popup.destroy).pack()
        popup.bind('<Escape>', lambda e: popup.destroy())

    def _show_product_movement(self) -> None:
        """v4.1.2: 품목별 입출고 현황"""
        from ..utils.constants import BOTH, END, LEFT, RIGHT, VERTICAL, Y, tk, ttk

        popup = create_themed_toplevel(self.root)
        popup.title("📊 품목별 입출고 현황")
        popup.geometry("700x450")
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="📊 품목별 입출고 현황",
                 font=('맑은 고딕', 16, 'bold'), fg=ThemeColors.get('text_primary')).pack(pady=10)

        cols = ('product', 'inbound_cnt', 'inbound_kg', 'outbound_cnt', 'outbound_kg', 'return_cnt')
        tree = ttk.Treeview(popup, columns=cols, show='headings', height=12)
        for cid, txt, w, anchor in [
            ('product', '제품', 150, 'w'), ('inbound_cnt', '입고건수', 70, 'center'),
            ('inbound_kg', '입고(kg)', 100, 'e'), ('outbound_cnt', '출고건수', 70, 'center'),
            ('outbound_kg', '출고(kg)', 100, 'e'), ('return_cnt', '반품', 60, 'center'),
        ]:
            tree.heading(cid, text=txt, anchor='center')
            tree.column(cid, width=w, anchor=anchor)

        sb = tk.Scrollbar(popup, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 0), pady=5)
        sb.pack(side=RIGHT, fill=Y, padx=(0, 10), pady=5)
        # v8.1.9: TreeviewTotalFooter
        try:
            from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter as _TTF
            _f = _TTF(popup, tree, summable_column_ids=[])
            _f.pack(fill='x', padx=(10, 0))
        except Exception as e:
            logger.warning(f'[UI] product_handlers: {e}')
        try:
            rows = self.engine.db.fetchall("""
                SELECT
                    i.product,
                    SUM(CASE WHEN m.movement_type='INBOUND' THEN 1 ELSE 0 END) AS in_cnt,
                    SUM(CASE WHEN m.movement_type='INBOUND' THEN m.qty_kg ELSE 0 END) AS in_kg,
                    SUM(CASE WHEN m.movement_type='OUTBOUND' THEN 1 ELSE 0 END) AS out_cnt,
                    SUM(CASE WHEN m.movement_type='OUTBOUND' THEN m.qty_kg ELSE 0 END) AS out_kg,
                    SUM(CASE WHEN m.movement_type='RETURN' THEN 1 ELSE 0 END) AS ret_cnt
                FROM inventory i
                LEFT JOIN stock_movement m ON i.lot_no = m.lot_no
                GROUP BY i.product
                ORDER BY in_kg DESC
            """)

            for r in rows:
                product = (r['product'] if isinstance(r, dict) else r[0]) or '-'
                in_c = int((r['in_cnt'] if isinstance(r, dict) else r[1]) or 0)
                in_k = float((r['in_kg'] if isinstance(r, dict) else r[2]) or 0)
                out_c = int((r['out_cnt'] if isinstance(r, dict) else r[3]) or 0)
                out_k = float((r['out_kg'] if isinstance(r, dict) else r[4]) or 0)
                ret_c = int((r['ret_cnt'] if isinstance(r, dict) else r[5]) or 0)

                tree.insert('', END, values=(
                    product, in_c, f"{in_k:,.0f}", out_c, f"{out_k:,.0f}", ret_c
                ))

        except (sqlite3.OperationalError, sqlite3.DatabaseError, ValueError, KeyError) as e:
            logger.error(f"품목 입출고 현황 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"조회 실패:\n{e}")

        ttk.Button(popup, text="닫기", command=popup.destroy).pack(pady=8)
        popup.bind('<Escape>', lambda e: popup.destroy())
