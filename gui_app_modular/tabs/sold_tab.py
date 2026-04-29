"""
v7.0 5단계: SOLD 탭 — sold_table(SOLD) 기반 LOT 리스트 + 전체 판매 보기 + 기간 필터 + Excel 내보내기
"""
import logging
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from ..utils.constants import BOTH, LEFT, VERTICAL, YES, X
from ..utils.tree_enhancements import bind_period_vars_debounced
from ..utils.ui_constants import is_dark, Spacing, ThemeColors, apply_tooltip

logger = logging.getLogger(__name__)

# v8.1.5: 출고 확정 시 'OUTBOUND', 레거시 'SOLD' 행 병행 조회
_SOLD_TABLE_ACTIVE_STATUSES = ("'SOLD'", "'OUTBOUND'", "'CONFIRMED'")

SOLD_LOT_COLUMNS = [
    ('row_num',        'No.',        50, 'center'),
    ('lot_no',         'LOT NO',    130, 'center'),
    ('sales_order_no', '판매주문No', 130, 'center'),
    ('customer',       '고객사',    160, 'w'),
    ('tonbag_count',   '톤백수',     70, 'e'),
    ('total_kg',       '중량(kg)',  110, 'e'),
    ('sold_date',      '판매일',    110, 'center'),
]

SOLD_DETAIL_COLUMNS = [
    ('row_num',        'No.',        50, 'center'),
    ('lot_no',         'LOT NO',    130, 'center'),
    ('tonbag_no',      '톤백No',     90, 'center'),
    ('sales_order_no', '판매주문No', 130, 'center'),
    ('customer',       '고객사',    160, 'w'),
    ('sold_qty_kg',    '중량(kg)',  110, 'e'),
    ('sold_date',      '판매일',    110, 'center'),
]


class SoldTabMixin:
    """v7.0: SOLD 탭 — sold_table(SOLD) 조회 전용, 기간 필터, Excel 내보내기"""

    def _setup_sold_tab(self) -> None:
        """SOLD 탭 UI"""
        from ..utils.tree_enhancements import apply_striped_rows

        _is_dark = is_dark()
        frame = self.tab_sold

        # 탭 헤더 (v7.6.0 심플화)
        try:
            from ..utils.ui_constants import make_tab_header
            self._sold_count_var = tk.StringVar(value="")
            make_tab_header(frame, "✅ 출고완료(OUTBOUND) LOT 리스트",
                            status_color='#22c55e', count_var=self._sold_count_var,
                            is_dark=_is_dark)
        except Exception:
            ttk.Label(frame, text="✅ 출고완료(OUTBOUND) LOT 리스트").pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))

        # v8.6.3: 공통 날짜 범위 바 (make_date_range_bar) 통일 적용
        try:
            from ..utils.tree_enhancements import make_date_range_bar
            _date_bar, self._sold_date_from_var, self._sold_date_to_var = \
                make_date_range_bar(frame, self._refresh_sold)
            _date_bar.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        except Exception as _e:
            logger.warning(f'[UI] sold_tab make_date_range_bar: {_e}')
            self._sold_date_from_var = tk.StringVar(value='')
            self._sold_date_to_var   = tk.StringVar(value='')
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        ttk.Button(filter_frame, text="🔄 새로고침", command=self._refresh_sold).pack(side=LEFT, padx=Spacing.XS)
        btn_revert_sold = ttk.Button(filter_frame, text="↩️ 출고 취소 (→ 판매화물 결정)", command=lambda: self._safe_call('_on_revert_sold_to_picked'))
        btn_revert_sold.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_revert_sold, "출고 확정 상태를 판매화물 결정으로 되돌립니다.")
        btn_finalize_return = ttk.Button(filter_frame, text="🔄 반품 확정 (→ AVAILABLE)",
                                         command=lambda: self._safe_call('_on_finalize_return_selected'))
        btn_finalize_return.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_finalize_return, "RETURN 상태 톤백을 선택하여 AVAILABLE로 확정 복귀합니다.")
        btn_show_all = ttk.Button(filter_frame, text="📋 전체 판매 보기", command=self._on_show_all_sold)
        btn_show_all.pack(side=tk.RIGHT, padx=Spacing.XS)
        apply_tooltip(btn_show_all, "판매(SOLD) 톤백 전체. [← LOT 리스트로]로 복귀.")

        self._sold_lot_container = ttk.Frame(frame)
        self._sold_lot_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)

        tree_frame = ttk.Frame(self._sold_lot_container)
        tree_frame.pack(fill=BOTH, expand=YES)
        cols = [c[0] for c in SOLD_LOT_COLUMNS]
        self.tree_sold = ttk.Treeview(
            tree_frame, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H, selectmode='extended'
        )
        for col_id, label, width, anchor in SOLD_LOT_COLUMNS:
            self.tree_sold.heading(col_id, text=label, anchor='center')
            self.tree_sold.column(col_id, width=width, anchor=anchor, stretch=True)
        scroll = tk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree_sold.yview)
        scroll_x = tk.Scrollbar(tree_frame, orient='horizontal', command=self.tree_sold.xview)
        self.tree_sold.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        self.tree_sold.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll.pack(side=tk.RIGHT, fill='y')
        # v8.1.9: TreeviewTotalFooter
        try:
            from ..utils.tree_enhancements import TreeviewTotalFooter
            self._sold_total_footer = TreeviewTotalFooter(
                tree_frame, self.tree_sold,
                summable_column_ids=['total_kg'],
                column_display_names={'total_kg': '중량(kg)'},
                column_formats={'total_kg': ',.0f'},
            )
            self._sold_total_footer.pack(fill='x')
        except Exception:
            self._sold_total_footer = None
        scroll_x.pack(side=tk.BOTTOM, fill='x')
        try:
            apply_striped_rows(self.tree_sold, _is_dark)
        except Exception as e:
            logger.debug(f"apply_striped_rows: {e}")

        self.tree_sold.bind('<Double-1>', self._on_sold_lot_double_click)

        # v8.1.8: TreeviewTotalFooter 교체 (기존 summary_label 대체)
        from ..utils.tree_enhancements import TreeviewTotalFooter
        self._sold_footer = TreeviewTotalFooter(
            self._sold_lot_container, self.tree_sold,
            summable_column_ids=['tonbag_count', 'total_kg'],
            column_display_names={'tonbag_count': '톤백수', 'total_kg': '중량(kg)'},
        )
        self._sold_footer.pack(fill='x')
        footer_frame = ttk.Frame(self._sold_lot_container)
        footer_frame.pack(fill=X, pady=(Spacing.XS, 0))
        ttk.Button(footer_frame, text="📥 Excel 내보내기", command=self._on_sold_export_excel).pack(side=tk.RIGHT, padx=Spacing.XS)
        apply_tooltip(footer_frame.winfo_children()[-1], "SOLD 데이터를 Excel로 내보내기 (정산/보고용)")

        self._sold_detail_container = ttk.Frame(frame)
        tb_bar = ttk.Frame(self._sold_detail_container)
        tb_bar.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        ttk.Button(tb_bar, text="← LOT 리스트로", command=self._on_back_to_sold_lot_list).pack(side=LEFT, padx=Spacing.XS)
        ttk.Button(tb_bar, text="🔄 새로고침", command=self._on_show_all_sold).pack(side=LEFT, padx=Spacing.XS)
        btn_detail_revert_sold = ttk.Button(tb_bar, text="↩️ 출고 취소 (→ 판매화물 결정)", command=lambda: self._safe_call('_on_revert_sold_to_picked'))
        btn_detail_revert_sold.pack(side=LEFT, padx=Spacing.XS)
        detail_tree_frame = ttk.Frame(self._sold_detail_container)
        detail_tree_frame.pack(fill=BOTH, expand=YES)
        detail_cols = [c[0] for c in SOLD_DETAIL_COLUMNS]
        self.tree_sold_detail = ttk.Treeview(
            detail_tree_frame, columns=detail_cols, show='headings', height=Spacing.Tab.TREE_MIN_H, selectmode='extended'
        )
        for col_id, label, width, anchor in SOLD_DETAIL_COLUMNS:
            self.tree_sold_detail.heading(col_id, text=label, anchor='center')
            self.tree_sold_detail.column(col_id, width=width, anchor=anchor, stretch=True)
        scroll2 = tk.Scrollbar(detail_tree_frame, orient=VERTICAL, command=self.tree_sold_detail.yview)
        scroll2_x = tk.Scrollbar(detail_tree_frame, orient='horizontal', command=self.tree_sold_detail.xview)
        self.tree_sold_detail.configure(yscrollcommand=scroll2.set, xscrollcommand=scroll2_x.set)
        self.tree_sold_detail.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll2.pack(side=tk.RIGHT, fill='y')
        scroll2_x.pack(side=tk.BOTTOM, fill='x')
        # v8.1.5 BUG-02 동일 패턴: detail 컨테이너 초기 숨김
        self._sold_detail_container.pack_forget()

        self._refresh_sold()

    def _get_sold_date_range(self):
        """기간 필터 값 — v8.1.8: parse_date_range 공통 유틸 사용.
        둘 다 빈 문자열 → (None, None) → 전체 기간 조회."""
        try:
            from ..utils.tree_enhancements import parse_date_range
            raw_from = self._sold_date_from_var.get().strip()
            raw_to   = self._sold_date_to_var.get().strip()
            return parse_date_range(raw_from, raw_to)
        except Exception:
            return None, None

    def _refresh_sold(self) -> None:
        """SOLD LOT 리스트 — sold_table + 기간 필터.
        v8.1.8: 기간 미입력 시 전체 조회, build_date_sql 적용."""
        if not getattr(self, 'tree_sold', None):
            return
        for item in self.tree_sold.get_children(''):
            self.tree_sold.delete(item)
        date_from, date_to = self._get_sold_date_range()
        _st = ", ".join(_SOLD_TABLE_ACTIVE_STATUSES)
        try:
            from ..utils.tree_enhancements import build_date_sql
            sql = f"""
                SELECT s.lot_no, s.customer, s.sales_order_no,
                    COUNT(*) AS tonbag_count,
                    SUM(COALESCE(s.sold_qty_kg, 0)) AS total_kg,
                    MAX(s.sold_date) AS sold_date
                FROM sold_table s
                LEFT JOIN inventory_tonbag t ON s.tonbag_id = t.id
                WHERE s.status IN ({_st})             """
            params = []
            # v8.1.8: build_date_sql — 빈 문자열이면 SQL 조건 추가 안 함 (전체 기간)
            frag, dp = build_date_sql('s.sold_date',
                                      date_from or '', date_to or '',
                                      include_null=True)
            if frag:
                sql += f" AND {frag}"
                params.extend(dp)
            sql += " GROUP BY s.lot_no, s.sales_order_no ORDER BY MIN(COALESCE(t.is_sample, 0)), s.sold_date DESC, s.lot_no"
            rows = self.engine.db.fetchall(sql, tuple(params)) \
                if hasattr(self.engine, 'db') and self.engine.db else []
            for idx, r in enumerate(rows or [], 1):
                lot_no = str(r.get('lot_no', ''))
                sales_order_no = str(r.get('sales_order_no', '') or '-')
                customer = str(r.get('customer', '') or '-')
                tonbag_count = int(r.get('tonbag_count') or 0)
                total_kg = float(r.get('total_kg') or 0)
                sold_date = str(r.get('sold_date') or '')[:10] if r.get('sold_date') else '-'
                self.tree_sold.insert('', 'end', values=(
                    str(idx), lot_no, sales_order_no, customer, str(tonbag_count), f"{total_kg:,.0f}", sold_date
                ))
            total_lots = len(rows or [])
            total_tb = sum(int(r.get('tonbag_count') or 0) for r in (rows or []))
            total_kg = sum(float(r.get('total_kg') or 0) for r in (rows or []))
            if hasattr(self, '_sold_footer'):
                self._sold_footer.update_totals()
            if hasattr(self, '_sold_summary_label'):
                self._sold_summary_label.config(
                    text=f"LOT {total_lots}개 / 톤백 {total_tb}개 / 총 {total_kg:,.0f} kg"
                )
            # v8.1.5: 탭 헤더 카운트 업데이트
            if hasattr(self, '_sold_count_var'):
                self._sold_count_var.set(f"{total_lots} LOT / {total_tb}건")
        except Exception as e:
            logger.debug(f"_refresh_sold: {e}")
        if hasattr(self, '_sold_total_footer') and self._sold_total_footer:
            self._sold_total_footer.update_totals()

    def _on_show_all_sold(self) -> None:
        """전체 판매 보기"""
        if not getattr(self, 'tree_sold_detail', None):
            return
        date_from, date_to = self._get_sold_date_range()
        for item in self.tree_sold_detail.get_children(''):
            self.tree_sold_detail.delete(item)
        _st = ", ".join(_SOLD_TABLE_ACTIVE_STATUSES)
        try:
            sql = f"""
                SELECT s.lot_no, s.sub_lt, s.sales_order_no, s.customer, s.sold_qty_kg, s.sold_date
                FROM sold_table s
                LEFT JOIN inventory_tonbag t ON s.tonbag_id = t.id
                WHERE s.status IN ({_st})             """
            params = []
            if date_from:
                sql += " AND (s.sold_date >= ? OR s.sold_date IS NULL)"
                params.append(date_from)
            if date_to:
                sql += " AND (s.sold_date <= ? OR s.sold_date IS NULL)"
                params.append(date_to + ' 23:59:59' if len(date_to) <= 10 else date_to)
            sql += " ORDER BY s.sold_date DESC, s.lot_no, s.sub_lt"
            rows = (self.engine.db.fetchall(sql, tuple(params)) if params else self.engine.db.fetchall(sql)) \
                if hasattr(self.engine, 'db') and self.engine.db else []
            for idx, r in enumerate(rows or [], 1):
                lot_no = str(r.get('lot_no', ''))
                sub_lt = r.get('sub_lt', '')
                tonbag_no = str(sub_lt) if sub_lt is not None else '-'
                sales_order_no = str(r.get('sales_order_no', '') or '-')
                customer = str(r.get('customer', '') or '-')
                sold_kg = float(r.get('sold_qty_kg') or 0)
                sold_date = str(r.get('sold_date') or '')[:10] if r.get('sold_date') else '-'
                self.tree_sold_detail.insert('', 'end', values=(
                    str(idx), lot_no, tonbag_no, sales_order_no, customer, f"{sold_kg:,.0f}", sold_date
                ))
            self._sold_lot_container.pack_forget()
            self._sold_detail_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)
        except Exception as e:
            logger.debug(f"_on_show_all_sold: {e}")

    def _on_back_to_sold_lot_list(self) -> None:
        """LOT 리스트로 복귀"""
        self._sold_detail_container.pack_forget()
        self._sold_lot_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)
        self._refresh_sold()

    def _on_sold_lot_double_click(self, event) -> None:
        """LOT 더블클릭 → 해당 LOT SOLD 톤백 팝업 (조회 전용)"""
        sel = self.tree_sold.selection()
        if not sel:
            return
        item = self.tree_sold.item(sel[0])
        vals = item.get('values', [])
        cols = [c[0] for c in SOLD_LOT_COLUMNS]
        lot_no = ''
        if 'lot_no' in cols and len(vals) > cols.index('lot_no'):
            lot_no = str(vals[cols.index('lot_no')]).strip()
        if lot_no and hasattr(self, '_show_lot_detail_popup'):
            self._show_lot_detail_popup(lot_no, 'sold')


    def _on_finalize_return_selected(self) -> None:
        """RETURN 상태 톤백을 선택하여 AVAILABLE로 확정 복귀."""
        import tkinter.messagebox as msgbox
        # 선택 항목 파악
        sel = self.tree_sold.selection() if hasattr(self, 'tree_sold') else []
        if not sel:
            msgbox.showwarning("선택 없음", "반품 확정할 LOT를 선택하세요.", parent=self)
            return
        # 선택된 LOT의 RETURN 톤백 수집
        targets = []
        for iid in sel:
            vals = self.tree_sold.item(iid, 'values')
            lot_no = vals[1] if vals and len(vals) > 1 else None  # vals[0]=row_num, vals[1]=lot_no
            if lot_no:
                try:
                    rows = self.db.fetchall(
                        "SELECT sub_lt, location FROM inventory_tonbag "
                        "WHERE lot_no=? AND status='RETURN' AND (is_sample IS NULL OR is_sample=0)",
                        (lot_no,)
                    )
                    for r in (rows or []):
                        targets.append((lot_no, r['sub_lt'] if isinstance(r, dict) else r[0],
                                        r['location'] if isinstance(r, dict) else r[1]))
                except Exception as e:
                    logger.error(f"RETURN 조회 오류: {e}")

        if not targets:
            msgbox.showinfo("대상 없음", "선택한 LOT에 RETURN 상태 톤백이 없습니다.", parent=self)
            return

        ok = msgbox.askyesno(
            "반품 확정", f"총 {len(targets)}개 톤백을 AVAILABLE로 확정합니다.\n계속하시겠습니까?",
            parent=self
        )
        if not ok:
            return

        success, fail = 0, 0
        for lot_no, sub_lt, location in targets:
            try:
                res = self.engine.finalize_return_to_available(lot_no, sub_lt, location)
                if res.get('success'):
                    success += 1
                else:
                    fail += 1
                    logger.warning(f"finalize 실패: {lot_no}-{sub_lt}: {res.get('message')}")
            except Exception as e:
                fail += 1
                logger.error(f"finalize 오류: {lot_no}-{sub_lt}: {e}")

        msgbox.showinfo(
            "반품 확정 완료",
            f"성공: {success}개 / 실패: {fail}개",
            parent=self
        )
        self._refresh_sold()

    def _on_sold_export_excel(self) -> None:
        """SOLD 데이터 Excel 내보내기 (정산/보고용)"""
        try:
            from tkinter import filedialog

            import pandas as pd
            date_from, date_to = self._get_sold_date_range()
            _st = ", ".join(_SOLD_TABLE_ACTIVE_STATUSES)
            sql = f"""
                SELECT s.lot_no, s.sales_order_no, s.customer, s.sub_lt, s.sold_qty_kg, s.sold_date, s.created_at
                FROM sold_table s
                LEFT JOIN inventory_tonbag t ON s.tonbag_id = t.id
                WHERE s.status IN ({_st})             """
            params = []
            if date_from:
                sql += " AND (s.sold_date >= ? OR s.sold_date IS NULL)"
                params.append(date_from)
            if date_to:
                sql += " AND (s.sold_date <= ? OR s.sold_date IS NULL)"
                params.append(date_to + ' 23:59:59' if len(date_to) <= 10 else date_to)
            sql += " ORDER BY s.sold_date DESC, s.lot_no, s.sub_lt"
            rows = self.engine.db.fetchall(sql, tuple(params)) if params else self.engine.db.fetchall(sql)
            if not hasattr(self.engine, 'db') or not self.engine.db:
                rows = []
            if not rows:
                if hasattr(self, '_log'):
                    self._log("내보낼 SOLD 데이터가 없습니다.")
                return
            df = pd.DataFrame(rows)
            path = filedialog.asksaveasfilename(
                parent=getattr(self, "root", None),
                defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx'), ('All', '*.*')],
                initialfile=f"SOLD_{date_from or 'all'}_{date_to or 'all'}.xlsx"
            )
            if path:
                df.to_excel(path, index=False)
                if hasattr(self, '_log'):
                    self._log(f"✅ SOLD Excel 저장: {path}")
        except ImportError:
            logger.debug("pandas 없음: Excel 내보내기 스킵")
        except Exception as e:
            logger.debug(f"_on_sold_export_excel: {e}")
