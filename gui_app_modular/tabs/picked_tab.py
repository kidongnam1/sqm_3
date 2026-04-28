"""
v7.0 4단계: PICKED 탭 — picking_table(ACTIVE) 기반 LOT 리스트 + 전체 피킹 보기
"""
import logging
import tkinter as tk
from tkinter import ttk

from ..utils.constants import BOTH, LEFT, VERTICAL, YES, X
from ..utils.ui_constants import is_dark, Spacing, ThemeColors, apply_tooltip

logger = logging.getLogger(__name__)

PICKED_LOT_COLUMNS = [
    ('row_num',      'No.',       50, 'center'),
    ('lot_no',       'LOT NO',   130, 'center'),
    ('picking_no',   '피킹No',   130, 'center'),
    ('customer',     '고객사',   160, 'w'),
    ('tonbag_count', '톤백수',    70, 'e'),
    ('total_kg',     '중량(kg)', 110, 'e'),
    ('picking_date', '피킹일',   110, 'center'),
]

PICKED_DETAIL_COLUMNS = [
    ('row_num',     'No.',       50, 'center'),
    ('lot_no',      'LOT NO',   130, 'center'),
    ('tonbag_no',   '톤백No',    90, 'center'),
    ('picking_no',  '피킹No',   130, 'center'),
    ('customer',    '고객사',   160, 'w'),
    ('qty_kg',      '중량(kg)', 110, 'e'),
    ('picking_date','피킹일',   110, 'center'),
]


class PickedTabMixin:
    """v7.0: PICKED 탭 — picking_table(ACTIVE) LOT 리스트 + 전체 피킹 보기"""

    def _setup_picked_tab(self) -> None:
        """PICKED 탭 UI"""
        from ..utils.tree_enhancements import apply_striped_rows

        _is_dark = is_dark()
        frame = self.tab_picked

        # 탭 헤더 (v7.6.0 심플화)
        try:
            from ..utils.ui_constants import make_tab_header
            self._picked_count_var = tk.StringVar(value="")
            make_tab_header(frame, "🚛 판매화물 결정 LOT 리스트",
                            status_color='#f97316', count_var=self._picked_count_var,
                            is_dark=_is_dark)
        except Exception:
            ttk.Label(frame, text="🚛 판매화물 결정 LOT 리스트").pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        ttk.Button(btn_frame, text="🔄 새로고침", command=self._refresh_picked).pack(side=LEFT, padx=Spacing.XS)
        btn_revert_picked = ttk.Button(btn_frame, text="↩️ 판매화물 결정 취소 (→ 판매 배정)", command=lambda: self._safe_call('_on_revert_picked_to_reserved'))
        btn_revert_picked.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_revert_picked, "판매화물 결정 상태를 판매 배정으로 되돌립니다.")
        btn_show_all = ttk.Button(btn_frame, text="📋 전체 피킹 보기", command=self._on_show_all_picked)
        btn_show_all.pack(side=tk.RIGHT, padx=Spacing.XS)
        apply_tooltip(btn_show_all, "피킹(ACTIVE) 톤백 전체. [← LOT 리스트로]로 복귀.")

        btn_picked_export = ttk.Button(btn_frame, text="📥 Excel 내보내기", command=self._on_picked_export_excel)
        btn_picked_export.pack(side=tk.RIGHT, padx=Spacing.XS)
        apply_tooltip(btn_picked_export, "현재 판매화물 결정 목록을 Excel로 내보내기")

        # v8.4.1 [E]: 전체 선택 / 전체 해제 토글 버튼
        self._picked_select_all_state = False
        btn_pick_select_all = ttk.Button(btn_frame, text="☑ 전체 선택",
                                          command=self._on_picked_toggle_select_all)
        btn_pick_select_all.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_pick_select_all, "목록의 모든 LOT를 선택/해제합니다.")
        self._picked_btn_select_all = btn_pick_select_all

        self._picked_lot_container = ttk.Frame(frame)
        self._picked_lot_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)

        tree_frame = ttk.Frame(self._picked_lot_container)
        tree_frame.pack(fill=BOTH, expand=YES)
        cols = [c[0] for c in PICKED_LOT_COLUMNS]
        self.tree_picked = ttk.Treeview(
            tree_frame, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H, selectmode='extended'
        )
        for col_id, label, width, anchor in PICKED_LOT_COLUMNS:
            self.tree_picked.heading(col_id, text=label, anchor='center')
            self.tree_picked.column(col_id, width=width, anchor=anchor, stretch=True)
        scroll = tk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree_picked.yview)
        scroll_x = tk.Scrollbar(tree_frame, orient='horizontal', command=self.tree_picked.xview)
        self.tree_picked.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        self.tree_picked.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll.pack(side=tk.RIGHT, fill='y')
        # v8.1.9: TreeviewTotalFooter
        try:
            from ..utils.tree_enhancements import TreeviewTotalFooter
            self._picked_total_footer = TreeviewTotalFooter(
                tree_frame, self.tree_picked,
                summable_column_ids=['total_kg'],
                column_display_names={'total_kg': '중량(kg)'},
                column_formats={'total_kg': ',.0f'},
            )
            self._picked_total_footer.pack(fill='x')
        except Exception:
            self._picked_total_footer = None
        scroll_x.pack(side=tk.BOTTOM, fill='x')
        # v8.1.8: 합계 footer
        from ..utils.tree_enhancements import TreeviewTotalFooter
        self._picked_footer = TreeviewTotalFooter(
            self._picked_lot_container, self.tree_picked,
            summable_column_ids=['tonbag_count', 'total_kg'],
            column_display_names={'tonbag_count': '톤백수', 'total_kg': '중량(kg)'},
        )
        self._picked_footer.pack(fill='x')
        try:
            apply_striped_rows(self.tree_picked, _is_dark)
        except Exception as e:
            logger.debug(f"apply_striped_rows: {e}")

        self.tree_picked.bind('<Double-1>', self._on_picked_inline_edit)

        # v8.1.8: _picked_summary_label → _picked_footer 로 대체

        self._picked_detail_container = ttk.Frame(frame)
        tb_bar = ttk.Frame(self._picked_detail_container)
        tb_bar.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        ttk.Button(tb_bar, text="← LOT 리스트로", command=self._on_back_to_picked_lot_list).pack(side=LEFT, padx=Spacing.XS)
        ttk.Button(tb_bar, text="🔄 새로고침", command=self._on_show_all_picked).pack(side=LEFT, padx=Spacing.XS)
        btn_detail_revert_picked = ttk.Button(tb_bar, text="↩️ 판매화물 결정 취소 (→ 판매 배정)", command=lambda: self._safe_call('_on_revert_picked_to_reserved'))
        btn_detail_revert_picked.pack(side=LEFT, padx=Spacing.XS)
        detail_tree_frame = ttk.Frame(self._picked_detail_container)
        detail_tree_frame.pack(fill=BOTH, expand=YES)
        detail_cols = [c[0] for c in PICKED_DETAIL_COLUMNS]
        self.tree_picked_detail = ttk.Treeview(
            detail_tree_frame, columns=detail_cols, show='headings', height=Spacing.Tab.TREE_MIN_H, selectmode='extended'
        )
        for col_id, label, width, anchor in PICKED_DETAIL_COLUMNS:
            self.tree_picked_detail.heading(col_id, text=label, anchor='center')
            self.tree_picked_detail.column(col_id, width=width, anchor=anchor, stretch=True)
        scroll2 = tk.Scrollbar(detail_tree_frame, orient=VERTICAL, command=self.tree_picked_detail.yview)
        scroll2_x = tk.Scrollbar(detail_tree_frame, orient='horizontal', command=self.tree_picked_detail.xview)
        self.tree_picked_detail.configure(yscrollcommand=scroll2.set, xscrollcommand=scroll2_x.set)
        self.tree_picked_detail.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll2.pack(side=tk.RIGHT, fill='y')
        scroll2_x.pack(side=tk.BOTTOM, fill='x')
        # v8.1.5 BUG-02 동일 패턴: detail 컨테이너 초기 숨김
        self._picked_detail_container.pack_forget()

        self._refresh_picked()

    def _on_picked_export_excel(self) -> None:
        """판매화물 결정(Picked) 데이터 Excel 내보내기"""
        try:
            from datetime import datetime
            from tkinter import filedialog

            import pandas as pd

            sql = """
                SELECT lot_no, sub_lt, picking_no, customer, qty_kg, picking_date, created_by
                FROM picking_table
                WHERE status = 'ACTIVE'
                ORDER BY COALESCE(is_sample, 0), lot_no, sub_lt
            """
            rows = self.engine.db.fetchall(sql) if hasattr(self.engine, 'db') and self.engine.db else []

            if not rows:
                if hasattr(self, '_log'):
                    self._log("내보낼 판매화물 결정 데이터가 없습니다.")
                return

            df = pd.DataFrame(rows)
            col_map = {
                'lot_no': 'LOT NO',
                'sub_lt': 'Sub LOT',
                'picking_no': 'Picking No',
                'customer': '고객사',
                'qty_kg': '중량(kg)',
                'picking_date': '피킹일',
                'created_by': '작업자'
            }
            df.rename(columns=col_map, inplace=True)

            path = filedialog.asksaveasfilename(
                parent=getattr(self, "root", None),
                defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx'), ('All', '*.*')],
                initialfile=f"PICKED_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
            if path:
                df.to_excel(path, index=False)
                if hasattr(self, '_log'):
                    self._log(f"✅ 판매화물 결정 Excel 저장: {path}")
        except ImportError:
            logger.debug("pandas 없음: Excel 내보내기 스킵")
        except Exception as e:
            logger.debug(f"_on_picked_export_excel: {e}")

    def _on_picked_toggle_select_all(self) -> None:
        """v8.4.1 [E]: Picked 탭 전체 선택 / 전체 해제 토글."""
        tree = getattr(self, 'tree_picked', None)
        if not tree:
            return
        all_items = tree.get_children()
        if not all_items:
            return
        self._picked_select_all_state = not getattr(self, '_picked_select_all_state', False)
        if self._picked_select_all_state:
            tree.selection_set(all_items)
            if hasattr(self, '_picked_btn_select_all'):
                self._picked_btn_select_all.config(text="☐ 전체 해제")
        else:
            tree.selection_remove(*all_items)
            if hasattr(self, '_picked_btn_select_all'):
                self._picked_btn_select_all.config(text="☑ 전체 선택")

    def _refresh_picked(self) -> None:
        """PICKED LOT 리스트 — picking_table WHERE status='ACTIVE' GROUP BY lot_no, picking_no"""
        if not getattr(self, 'tree_picked', None):
            return
        for item in self.tree_picked.get_children(''):
            self.tree_picked.delete(item)
        try:
            rows = self.engine.db.fetchall("""
                SELECT lot_no, customer, picking_no,
                    COUNT(*) AS tonbag_count,
                    SUM(COALESCE(qty_kg, 0)) AS total_kg,
                    MIN(picking_date) AS picking_date
                FROM picking_table
                WHERE status = 'ACTIVE'
                GROUP BY lot_no, picking_no
                ORDER BY picking_date DESC, lot_no
            """) if hasattr(self.engine, 'db') and self.engine.db else []
            for idx, r in enumerate(rows or [], 1):
                lot_no = str(r.get('lot_no', ''))
                picking_no = str(r.get('picking_no', '') or '-')
                customer = str(r.get('customer', '') or '-')
                tonbag_count = int(r.get('tonbag_count') or 0)
                total_kg = float(r.get('total_kg') or 0)
                picking_date = str(r.get('picking_date') or '')[:10] if r.get('picking_date') else '-'
                self.tree_picked.insert('', 'end', values=(
                    str(idx), lot_no, picking_no, customer, str(tonbag_count), f"{total_kg:,.0f}", picking_date
                ))
            total_lots = len(rows or [])
            total_tb = sum(int(r.get('tonbag_count') or 0) for r in (rows or []))
            total_kg = sum(float(r.get('total_kg') or 0) for r in (rows or []))
            if hasattr(self, '_picked_footer'):
                self._picked_footer.update_totals()
            if hasattr(self, '_picked_summary_label'):
                self._picked_summary_label.config(
                    text=f"LOT {total_lots}개 / 톤백 {total_tb}개 / 총 {total_kg:,.0f} kg"
                )
            # v8.1.5: 탭 헤더 카운트 업데이트
            if hasattr(self, '_picked_count_var'):
                self._picked_count_var.set(f"{total_lots} LOT / {total_tb}건")
        except Exception as e:
            logger.debug(f"_refresh_picked: {e}")
        if hasattr(self, '_picked_total_footer') and self._picked_total_footer:
            self._picked_total_footer.update_totals()

    def _on_show_all_picked(self) -> None:
        """전체 피킹 보기"""
        if not getattr(self, 'tree_picked_detail', None):
            return
        for item in self.tree_picked_detail.get_children(''):
            self.tree_picked_detail.delete(item)
        try:
            rows = self.engine.db.fetchall("""
                SELECT lot_no, sub_lt, picking_no, customer, qty_kg, picking_date
                FROM picking_table
                WHERE status = 'ACTIVE'
                ORDER BY picking_date DESC, lot_no, sub_lt
            """) if hasattr(self.engine, 'db') and self.engine.db else []
            for idx, r in enumerate(rows or [], 1):
                lot_no = str(r.get('lot_no', ''))
                sub_lt = r.get('sub_lt', '')
                tonbag_no = str(sub_lt) if sub_lt is not None else '-'
                picking_no = str(r.get('picking_no', '') or '-')
                customer = str(r.get('customer', '') or '-')
                qty_kg = float(r.get('qty_kg') or 0)
                picking_date = str(r.get('picking_date') or '')[:10] if r.get('picking_date') else '-'
                self.tree_picked_detail.insert('', 'end', values=(
                    str(idx), lot_no, tonbag_no, picking_no, customer, f"{qty_kg:,.0f}", picking_date
                ))
            self._picked_lot_container.pack_forget()
            self._picked_detail_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)
        except Exception as e:
            logger.debug(f"_on_show_all_picked: {e}")

    def _on_back_to_picked_lot_list(self) -> None:
        """LOT 리스트로 복귀"""
        self._picked_detail_container.pack_forget()
        self._picked_lot_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)
        self._refresh_picked()

    # =========================================================================
    # 인라인 편집 (v8.0.9) — picking_table + inventory_tonbag 자동 동기화
    # =========================================================================

    _PICKED_EDITABLE = {
        'customer':     'picked_to',       # → inventory_tonbag.picked_to
        'picking_date': 'picking_date',    # → picking_table 자체
        'picking_no':   'picking_no',      # → picking_table 자체
    }

    def _on_picked_lot_double_click(self, event) -> None:
        """LOT 더블클릭 (구버전 호환 — _on_picked_inline_edit 위임)"""
        self._on_picked_inline_edit(event)

    def _on_picked_inline_edit(self, event) -> None:
        """더블클릭한 셀 → 인라인 Entry 수정 (v8.0.9)"""
        import tkinter as tk
        tree = self.tree_picked
        region = tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col_id_raw = tree.identify_column(event.x)
        row_iid   = tree.identify_row(event.y)
        if not row_iid:
            return

        col_idx = int(col_id_raw.replace('#', '')) - 1
        cols    = [c[0] for c in PICKED_LOT_COLUMNS]
        if col_idx >= len(cols):
            return
        col_key = cols[col_idx]

        if col_key not in self._PICKED_EDITABLE:
            return

        vals    = list(tree.item(row_iid, 'values'))
        cur_val = str(vals[col_idx]) if col_idx < len(vals) else ''
        lot_no  = str(vals[cols.index('lot_no')]) if 'lot_no' in cols else ''

        bbox = tree.bbox(row_iid, col_id_raw)
        if not bbox:
            return
        x, y, w, h = bbox

        entry_var = tk.StringVar(value=cur_val)
        entry = tk.Entry(tree, textvariable=entry_var, justify='center',
                         font=('맑은 고딕', 10))
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        entry.select_range(0, 'end')

        def _commit(ev=None):
            new_val = entry_var.get().strip()
            entry.destroy()
            if new_val == cur_val:
                return
            self._apply_picked_edit(row_iid, col_idx, col_key, new_val, lot_no, vals)

        def _cancel(ev=None):
            entry.destroy()

        entry.bind('<Return>',   _commit)
        entry.bind('<KP_Enter>', _commit)
        entry.bind('<Escape>',   _cancel)
        entry.bind('<FocusOut>', _commit)

    def _apply_picked_edit(self, row_iid, col_idx, col_key, new_val, lot_no, vals) -> None:
        """
        picking_table 수정 → inventory_tonbag 자동 동기화 → audit_log 기록 (v8.0.9)
        """
        if not hasattr(self, 'engine') or not self.engine or not hasattr(self.engine, 'db'):
            return
        db = self.engine.db
        tonbag_col = self._PICKED_EDITABLE.get(col_key)

        try:
            # ① picking_table UPDATE
            db.execute(
                f"UPDATE picking_table SET {col_key}=? "
                f"WHERE lot_no=? AND status='ACTIVE'",
                (new_val, lot_no)
            )

            # ② inventory_tonbag 자동 동기화 (customer → picked_to)
            if tonbag_col and tonbag_col != col_key:
                db.execute(
                    f"UPDATE inventory_tonbag SET {tonbag_col}=?, updated_at=datetime('now','localtime') "
                    f"WHERE lot_no=? AND status='PICKED'",
                    (new_val, lot_no)
                )
            elif tonbag_col == col_key and col_key == 'picking_date':
                db.execute(
                    "UPDATE inventory_tonbag SET picked_date=?, updated_at=datetime('now','localtime') "
                    "WHERE lot_no=? AND status='PICKED'",
                    (new_val, lot_no)
                )

            # ③ audit_log 기록
            try:
                import json
                db.execute(
                    "INSERT INTO audit_log(event_type, event_data, created_by, created_at) "
                    "VALUES (?, ?, ?, datetime('now','localtime'))",
                    (
                        'INLINE_EDIT_PICKED',
                        json.dumps({
                            'lot_no':  lot_no,
                            'field':   col_key,
                            'old_val': str(vals[col_idx]) if col_idx < len(vals) else '',
                            'new_val': new_val,
                        }, ensure_ascii=False),
                        'user'
                    )
                )
            except Exception as ae:
                logger.debug("[THEME-FAIL] file=picked_tab.py reason=audit_log_write: %s", ae)

            db.commit()

            # ④ 트리 셀 즉시 업데이트
            new_vals = list(vals)
            new_vals[col_idx] = new_val
            self.tree_picked.item(row_iid, values=new_vals)

            # ⑤ Detail 테이블 즉시 갱신 (전체 피킹 보기 열려 있으면)
            try:
                if (getattr(self, 'tree_picked_detail', None) and
                        getattr(self, '_picked_detail_container', None) and
                        self._picked_detail_container.winfo_ismapped()):
                    self._on_show_all_picked()
            except Exception as _de:
                logger.debug("[InlineEdit/Picked] detail 갱신 무시: %s", _de)

            logger.info("[InlineEdit/Picked] lot_no=%s %s: %s → %s",
                        lot_no, col_key, vals[col_idx] if col_idx < len(vals) else '', new_val)

        except Exception as e:
            logger.error("[InlineEdit/Picked] 수정 실패: %s", e)
            try:
                from ..utils.custom_messagebox import CustomMessageBox
                CustomMessageBox.showerror(self.root, '수정 실패', str(e))
            except Exception as e2:
                logger.warning(f"[UI] picked 에러 다이얼로그 표시 실패: {e2}")
