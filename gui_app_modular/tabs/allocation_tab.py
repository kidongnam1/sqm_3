"""
v7.0 3단계: ALLOCATION 탭 — allocation_plan(RESERVED) 기반 LOT 리스트 + 전체 배정 보기
"""
import logging
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from ..utils.constants import BOTH, LEFT, VERTICAL, YES, X
from ..utils.ui_constants import is_dark, CustomMessageBox, Spacing, ThemeColors, apply_tooltip

logger = logging.getLogger(__name__)

ALLOCATION_LOT_COLUMNS = [
    ('expand',       '☐',         56, 'center'),
    ('row_num',      'No.',        50, 'center'),
    ('lot_no',       'LOT NO',    130, 'center'),
    ('customer',     '고객사',    160, 'w'),
    ('total_mt',     '배정수량(MT)', 110, 'e'),
    ('tonbag_count', '톤백수',     70, 'e'),
    ('plan_date',    '출고예정일', 110, 'center'),
]

ALLOCATION_DETAIL_COLUMNS = [
    ('row_num',   'No.',         50, 'center'),
    ('lot_no',    'LOT NO',     130, 'center'),
    ('tonbag_no', '톤백No',      90, 'center'),
    ('customer',  '고객사',     160, 'w'),
    ('qty_mt',    '배정수량(MT)', 110, 'e'),
    ('created_at','배정일',     110, 'center'),
]


class AllocationTabMixin:
    """v7.0: ALLOCATION 탭 — allocation_plan(RESERVED) LOT 리스트 + 전체 배정 보기"""

    def _setup_allocation_tab(self) -> None:
        """ALLOCATION 탭 UI (LOT 리스트 + [전체 배정 보기] + 복귀)"""

        _is_dark = is_dark()
        frame = self.tab_allocation

        # 탭 헤더 (v7.6.0 심플화)
        try:
            from ..utils.ui_constants import make_tab_header
            self._alloc_count_var = tk.StringVar(value="")
            make_tab_header(frame, "📋 판매배정 LOT 리스트",
                            status_color='#3b82f6', count_var=self._alloc_count_var,
                            is_dark=_is_dark)
        except Exception:
            ttk.Label(frame, text="📋 판매배정 LOT 리스트").pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))

        # 버튼 바: 우측 고정(_btn_right: 전체 배정·Excel) + 좌측 새로고침/취소 — 좌측 긴 문구와 pack(RIGHT) 겹침 방지 (v8.1.6)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        _btn_right = ttk.Frame(btn_frame)
        _btn_right.pack(side=tk.RIGHT, padx=(Spacing.XS, 0))
        btn_show_all = ttk.Button(_btn_right, text="📋 전체 배정 보기", command=self._on_show_all_allocation)
        btn_show_all.pack(side=LEFT, padx=(0, Spacing.XS))
        apply_tooltip(btn_show_all, "판매 배정 톤백 전체 목록. [← LOT 리스트로]로 복귀.")
        btn_alloc_export = ttk.Button(_btn_right, text="📥 Excel 내보내기", command=self._on_allocation_export_excel)
        btn_alloc_export.pack(side=LEFT, padx=(0, 0))
        apply_tooltip(btn_alloc_export, "현재 판매배정 목록을 Excel로 내보내기")

        self._alloc_btn_back_top = ttk.Button(
            btn_frame, text="← LOT 리스트로", command=self._on_back_to_allocation_lot_list)
        apply_tooltip(self._alloc_btn_back_top, "LOT 요약 리스트 화면으로 돌아갑니다.")
        # v8.1.5 BUG-01: 선 숨김 — 전체배정 보기 진입 시에만 표시
        self._alloc_btn_back_top.pack_forget()

        self._alloc_btn_refresh = ttk.Button(btn_frame, text="🔄 새로고침", command=self._refresh_allocation)
        self._alloc_btn_refresh.pack(side=LEFT, padx=Spacing.XS)
        btn_cancel = ttk.Button(btn_frame, text="❌ 판매 배정 취소 (→ 판매가능)", command=self._on_allocation_cancel_to_available)
        btn_cancel.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_cancel, "선택한 LOT 또는 전체 배정을 취소하여 판매가능으로 되돌립니다.")
        # v7.7.1: SALE REF 일괄 취소 버튼
        btn_cancel_ref = ttk.Button(btn_frame, text="🔢 SALE REF 일괄 취소",
                                    command=self._on_allocation_cancel_by_sale_ref)
        btn_cancel_ref.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_cancel_ref, "판매참조번호(SALE REF) 입력 → 해당 번호의 모든 배정을 한 번에 취소합니다.")
        btn_lot_ov = ttk.Button(btn_frame, text="📊 LOT 현황", command=self._on_open_allocation_lot_overview)
        btn_lot_ov.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(
            btn_lot_ov,
            "LOT별 일반 톤백·샘플(1kg)·LOT모드 배정(MT) 통합. 배정 비율은 일반 톤백 총중량 기준(샘플 제외).",
        )
        # v8.6.5: 배정 전체 초기화 버튼
        btn_reset_all = ttk.Button(btn_frame, text="🧹 전체 초기화",
                                    command=self._on_allocation_reset_all)
        btn_reset_all.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_reset_all,
            "모든 배정(RESERVED/PICKED/OUTBOUND)을 한 번에 취소하고 톤백을 AVAILABLE로 복원합니다.")

        # v8.6.5: 개별 단계 되돌리기 버튼 3개
        # 두 번째 줄 프레임
        btn_frame2 = ttk.Frame(frame, padding=(8, 0, 8, 4))
        btn_frame2.pack(fill=X)
        ttk.Label(btn_frame2, text="↩️ 단계 되돌리기:", font=('맑은 고딕', 10)).pack(side=LEFT, padx=(0, 4))

        btn_revert_alloc = ttk.Button(btn_frame2, text="RESERVED → AVAILABLE",
                                       command=lambda: self._on_revert_step('RESERVED'))
        btn_revert_alloc.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_revert_alloc, "배정(RESERVED) 상태를 취소하여 AVAILABLE로 되돌립니다.")

        btn_revert_picked = ttk.Button(btn_frame2, text="PICKED → RESERVED",
                                        command=lambda: self._on_revert_step('PICKED'))
        btn_revert_picked.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_revert_picked, "피킹(PICKED) 상태를 되돌려 RESERVED로 복원합니다.")

        btn_revert_outbound = ttk.Button(btn_frame2, text="OUTBOUND → PICKED",
                                          command=lambda: self._on_revert_step('OUTBOUND'))
        btn_revert_outbound.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_revert_outbound, "출고(OUTBOUND/SOLD) 상태를 되돌려 PICKED로 복원합니다.")

        # v8.4.1 [E]: 전체 선택 / 전체 해제 토글 버튼
        self._alloc_select_all_state = False
        btn_select_all = ttk.Button(btn_frame, text="☑ 전체 선택",
                                     command=self._on_allocation_toggle_select_all)
        btn_select_all.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_select_all, "목록의 모든 LOT를 선택/해제합니다.")
        self._alloc_btn_select_all = btn_select_all

        self._alloc_btn_cancel = btn_cancel
        self._alloc_btn_show_all = btn_show_all

        # LOT 리스트 컨테이너
        self._alloc_lot_container = ttk.Frame(frame)
        self._alloc_lot_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)

        tree_frame = ttk.Frame(self._alloc_lot_container)
        tree_frame.pack(fill=BOTH, expand=YES)
        cols = [c[0] for c in ALLOCATION_LOT_COLUMNS]
        self.tree_allocation = ttk.Treeview(
            tree_frame, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H,
            selectmode='extended', style='Alloc.Treeview' if hasattr(ttk.Style(), 'configure') else None
        )
        # v8.1.8: Alloc.Treeview rowheight 36 — 펼침 ☐/☑ 가시성 개선
        try:
            _alloc_style = ttk.Style()
            _alloc_style.configure('Alloc.Treeview', rowheight=32,
                                   font=('맑은 고딕', 10))
            _alloc_style.configure('Alloc.Treeview.Heading', font=('맑은 고딕', 10, 'bold'))
        except Exception as _se:
            logger.debug(f"[UI] Alloc.Treeview 스타일: {_se}")
        for col_id, label, width, anchor in ALLOCATION_LOT_COLUMNS:
            self.tree_allocation.heading(col_id, text=label, anchor='center')
            self.tree_allocation.column(col_id, width=width, anchor=anchor, stretch=True)
        scroll = tk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree_allocation.yview)
        scroll_x = tk.Scrollbar(tree_frame, orient='horizontal', command=self.tree_allocation.xview)
        self.tree_allocation.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        self.tree_allocation.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll.pack(side=tk.RIGHT, fill='y')
        scroll_x.pack(side=tk.BOTTOM, fill='x')
        try:
            from ..utils.tree_enhancements import apply_striped_rows as _asr
            _asr(self.tree_allocation, _is_dark)
        except Exception as e:
            logger.debug(f"apply_striped_rows: {e}")

        self.tree_allocation.bind('<Double-1>', self._on_allocation_inline_edit)
        # detail 더블클릭도 인라인 편집
        # (LOT 팝업은 우클릭 메뉴로 이동)
        self.tree_allocation.bind('<Button-3>', self._on_allocation_right_click)  # v6.7.1 ④
        # v8.1.5 PATCH-D: 펼침 열 클릭 바인딩
        self.tree_allocation.bind('<Button-1>', self._on_alloc_tree_expand_click, add='+')
        try:
            from ..utils.ui_constants import tc as _tc_alloc
            self.tree_allocation.tag_configure('alloc_line',
                foreground=_tc_alloc('text_muted'))      # v8.1.8: #94a3b8 → tc(text_muted)
            self.tree_allocation.tag_configure('alloc_subtotal', font=('맑은 고딕', 10, 'bold'))
        except Exception as e:
            logger.debug(f'allocation tree tags: {e}')

        # v8.1.5: LOT 리스트 하단 합계 (total_mt, tonbag_count)
        from ..utils.tree_enhancements import TreeviewTotalFooter
        self._alloc_lot_footer = TreeviewTotalFooter(
            self._alloc_lot_container, self.tree_allocation, ['total_mt', 'tonbag_count'],
            column_display_names={c[0]: c[1] for c in ALLOCATION_LOT_COLUMNS}
        )
        self._alloc_lot_footer.pack(fill=X)

        # 하단 통계
        self._alloc_summary_label = ttk.Label(self._alloc_lot_container, text="LOT 0개 / 톤백 0개 / 총 0 MT")
        self._alloc_summary_label.pack(fill=X, pady=(Spacing.XS, 0))
        # v8.1.5 PATCH-D: 펼침 안내 문구
        try:
            import tkinter as _tk
            from ..utils.ui_constants import tc as _tc_hint
            _hint = _tk.Label(
                self._alloc_lot_container,
                text='펼침(☐) 열을 누르면 해당 LOT의 톤백별 배정수량·출고예정일·배정일과 소계가 펼쳐집니다. 다시 누르면 접힙니다.',
                font=('맑은 고딕', 8), fg=_tc_hint('text_muted'), anchor='w', justify='left'
            )
            _hint.pack(fill='x', padx=4, pady=(0, 2))
        except Exception as e:
            logger.warning(f'[UI] allocation_tab: {e}')
        # 전체 배정 보기 컨테이너 (초기 숨김)
        self._alloc_detail_container = ttk.Frame(frame)
        tb_bar = ttk.Frame(self._alloc_detail_container)
        tb_bar.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        ttk.Button(tb_bar, text="← LOT 리스트로", command=self._on_back_to_allocation_lot_list).pack(side=LEFT, padx=Spacing.XS)
        ttk.Button(tb_bar, text="🔄 새로고침", command=self._on_show_all_allocation).pack(side=LEFT, padx=Spacing.XS)
        btn_detail_cancel_selected = ttk.Button(tb_bar, text="❌ 선택 취소 (→ 판매가능)", command=self._on_allocation_detail_cancel_selected)
        btn_detail_cancel_selected.pack(side=LEFT, padx=Spacing.XS)
        btn_detail_cancel_all = ttk.Button(tb_bar, text="❌ 전체 취소 (→ 판매가능)", command=self._on_allocation_detail_cancel_all)
        btn_detail_cancel_all.pack(side=LEFT, padx=Spacing.XS)
        self._alloc_detail_btn_cancel_selected = btn_detail_cancel_selected
        self._alloc_detail_btn_cancel_all = btn_detail_cancel_all
        detail_tree_frame = ttk.Frame(self._alloc_detail_container)
        detail_tree_frame.pack(fill=BOTH, expand=YES)
        detail_cols = [c[0] for c in ALLOCATION_DETAIL_COLUMNS]
        self.tree_allocation_detail = ttk.Treeview(
            detail_tree_frame, columns=detail_cols, show='headings', height=Spacing.Tab.TREE_MIN_H, selectmode='extended'
        )
        for col_id, label, width, anchor in ALLOCATION_DETAIL_COLUMNS:
            self.tree_allocation_detail.heading(col_id, text=label, anchor='center')
            self.tree_allocation_detail.column(col_id, width=width, anchor=anchor, stretch=True)
        scroll2 = tk.Scrollbar(detail_tree_frame, orient=VERTICAL, command=self.tree_allocation_detail.yview)
        scroll2_x = tk.Scrollbar(detail_tree_frame, orient='horizontal', command=self.tree_allocation_detail.xview)
        self.tree_allocation_detail.configure(yscrollcommand=scroll2.set, xscrollcommand=scroll2_x.set)
        self.tree_allocation_detail.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll2.pack(side=tk.RIGHT, fill='y')
        scroll2_x.pack(side=tk.BOTTOM, fill='x')
        # 전체 배정 보기 하단 합계 (건수, 배정수량 MT)
        from ..utils.tree_enhancements import TreeviewTotalFooter
        self._alloc_detail_footer = TreeviewTotalFooter(
            self._alloc_detail_container, self.tree_allocation_detail, ['qty_mt'],
            column_display_names={'qty_mt': '배정수량(MT)'}
        )
        self._alloc_detail_footer.pack(fill=X)
        # v8.1.5 BUG-02: 전체배정 컨테이너 초기 숨김 (하단 버튼 바 포함)
        self._alloc_detail_container.pack_forget()

        self._refresh_allocation()

    def _on_allocation_export_excel(self) -> None:
        """판매배정(Allocation) 데이터 Excel 내보내기"""
        try:
            from tkinter import filedialog

            import pandas as pd

            # allocation_plan 데이터 조회
            sql = """
                SELECT ap.id, ap.lot_no, ap.sub_lt, ap.customer, ap.qty_mt, ap.outbound_date, ap.created_at
                FROM allocation_plan ap
                LEFT JOIN inventory_tonbag tb ON ap.tonbag_id = tb.id
                WHERE ap.status = 'RESERVED'
                ORDER BY COALESCE(tb.is_sample, 0), ap.lot_no, ap.sub_lt
            """
            rows = self.engine.db.fetchall(sql) if hasattr(self.engine, 'db') and self.engine.db else []

            # fallback: inventory_tonbag에서 RESERVED 조회
            if not rows and getattr(self, '_alloc_fallback', False):
                sql_fb = """
                    SELECT lot_no, sub_lt, picked_to AS customer, weight, outbound_date, updated_at
                    FROM inventory_tonbag
                    WHERE status = 'RESERVED'
                    ORDER BY lot_no, sub_lt
                """
                fb_rows = self.engine.db.fetchall(sql_fb) if hasattr(self.engine, 'db') and self.engine.db else []
                if fb_rows:
                    # 형식 변환
                    for r in fb_rows:
                        r_dict = dict(r)
                        r_dict['qty_mt'] = (float(r_dict.get('weight') or 0) / 1000.0)
                        r_dict['created_at'] = r_dict.get('updated_at')
                        rows.append(r_dict)

            if not rows:
                if hasattr(self, '_log'):
                    self._log("내보낼 판매배정 데이터가 없습니다.")
                return

            df = pd.DataFrame(rows)
            # 컬럼명 매핑 (보기 좋게)
            col_map = {
                'lot_no': 'LOT NO',
                'sub_lt': 'Sub LOT',
                'customer': '고객사',
                'qty_mt': '배정수량(MT)',
                'outbound_date': '출고예정일',
                'created_at': '배정일',
                'weight': '중량(kg)'
            }
            df.rename(columns=col_map, inplace=True)

            path = filedialog.asksaveasfilename(
                parent=getattr(self, "root", None),
                defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx'), ('All', '*.*')],
                initialfile=f"ALLOCATION_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
            if path:
                df.to_excel(path, index=False)
                if hasattr(self, '_log'):
                    self._log(f"✅ 판매배정 Excel 저장: {path}")
        except ImportError:
            logger.debug("pandas 없음: Excel 내보내기 스킵")
        except Exception as e:
            logger.debug(f"_on_allocation_export_excel: {e}")

    def _refresh_allocation(self) -> None:
        """ALLOCATION LOT 리스트 새로고침 — allocation_plan WHERE status='RESERVED' GROUP BY lot_no"""
        if not getattr(self, 'tree_allocation', None):
            return
        for item in self.tree_allocation.get_children(''):
            self.tree_allocation.delete(item)
        # 예약 상태 동기화(톤백 상태 기반) — 기존 데이터 불일치 보정
        if hasattr(self.engine, 'db') and self.engine.db and hasattr(self.engine, '_recalc_lot_status'):
            try:
                lot_rows = self.engine.db.fetchall(
                    "SELECT DISTINCT lot_no FROM inventory_tonbag WHERE status IN ('RESERVED','PICKED','SOLD','SHIPPED')"
                )
                for r in lot_rows or []:
                    lot_no = str(r.get('lot_no', '')).strip() if isinstance(r, dict) else ''
                    if lot_no:
                        self.engine._recalc_lot_status(lot_no)
            except Exception as e:
                logger.debug(f"_refresh_allocation status sync skip: {e}")
        try:
            # v8.1.5: GROUP BY lot_no + 출고예정일(dkey) — 같은 LOT라도 출고예정일이 다르면 별도 행
            rows = self.engine.db.fetchall("""
                SELECT ap.lot_no, ap.customer,
                    SUM(COALESCE(ap.qty_mt, 0)) AS total_mt,
                    COUNT(*) AS tonbag_count,
                    COALESCE(date(ap.outbound_date), '0000-00-00') AS plan_date
                FROM allocation_plan ap
                LEFT JOIN inventory_tonbag tb ON ap.tonbag_id = tb.id
                WHERE ap.status = 'RESERVED'
                GROUP BY ap.lot_no, COALESCE(date(ap.outbound_date), '0000-00-00')
                ORDER BY MIN(COALESCE(tb.is_sample, 0)), ap.lot_no, plan_date
            """) if hasattr(self.engine, 'db') and self.engine.db else []
            self._alloc_fallback = False
            if not rows and hasattr(self.engine, 'db') and self.engine.db:
                fb_rows = self.engine.db.fetchall("""
                    SELECT lot_no,
                        MAX(COALESCE(picked_to, '')) AS customer,
                        SUM(COALESCE(weight, 0)) / 1000.0 AS total_mt,
                        COUNT(*) AS tonbag_count,
                        COALESCE(date(outbound_date), '0000-00-00') AS plan_date
                    FROM inventory_tonbag
                    WHERE status = 'RESERVED'
                    GROUP BY lot_no, COALESCE(date(outbound_date), '0000-00-00')
                    ORDER BY MIN(COALESCE(is_sample, 0)), lot_no, plan_date
                """)
                if fb_rows:
                    rows = fb_rows
                    self._alloc_fallback = True
            for idx, r in enumerate(rows or [], 1):
                lot_no = str(r.get('lot_no', ''))
                customer = str(r.get('customer', '') or '-')
                total_mt = float(r.get('total_mt') or 0)
                tonbag_count = int(r.get('tonbag_count') or 0)
                raw_date = str(r.get('plan_date') or '')[:10]
                plan_date = raw_date if raw_date and raw_date != '0000-00-00' else '-'
                self.tree_allocation.insert('', 'end', values=(
                    '☐', str(idx), lot_no, customer, f"{total_mt:,.2f}", str(tonbag_count), plan_date
                ))
            # v8.1.5: LOT 리스트 하단 합계 갱신
            if hasattr(self, '_alloc_lot_footer') and self._alloc_lot_footer:
                self._alloc_lot_footer.update_totals()
            # 통계
            total_lots = len(rows or [])
            unique_lots = len(set(str(r.get('lot_no', '')) for r in (rows or [])))
            total_tb = sum(int(r.get('tonbag_count') or 0) for r in (rows or []))
            total_mt = sum(float(r.get('total_mt') or 0) for r in (rows or []))
            if hasattr(self, '_alloc_summary_label'):
                summary_text = f"LOT {unique_lots}개 / 행 {total_lots}개 / 톤백 {total_tb}개 / 총 {total_mt:,.2f} MT"
                if getattr(self, '_alloc_fallback', False):
                    summary_text += "  (톤백 기준 표시)"
                self._alloc_summary_label.config(text=summary_text)
            # v8.1.5: 탭 헤더 카운트 업데이트
            if hasattr(self, '_alloc_count_var'):
                self._alloc_count_var.set(f"{unique_lots} LOT / {total_tb}건")
            # allocation_plan은 비어 있는데 RESERVED 톤백이 있는 경우 경고 표시
            if total_lots == 0 and not getattr(self, '_alloc_fallback', False) and hasattr(self.engine, 'db') and self.engine.db:
                try:
                    row = self.engine.db.fetchone(
                        "SELECT COUNT(*) AS cnt FROM inventory_tonbag WHERE status = 'RESERVED'"
                    )
                    reserved_cnt = row.get('cnt', 0) if isinstance(row, dict) else (row[0] if row else 0)
                    if reserved_cnt > 0 and hasattr(self, '_alloc_summary_label'):
                        self._alloc_summary_label.config(
                            text=f"LOT 0개 / 톤백 0개 / 총 0 MT  (⚠ RESERVED 톤백 {reserved_cnt}개 — allocation_plan 비어 있음)"
                        )
                except Exception as e:
                    logger.debug(f"_refresh_allocation reserved check: {e}")
        except Exception as e:
            logger.debug(f"_refresh_allocation: {e}")
            if hasattr(self, '_log'):
                self._log(f"⚠️ 배정 목록 조회 오류: {e}")

    def _on_show_all_allocation(self) -> None:
        """전체 배정 보기 — allocation_plan 전체 행 표시"""
        if not getattr(self, 'tree_allocation_detail', None):
            return
        for item in self.tree_allocation_detail.get_children(''):
            self.tree_allocation_detail.delete(item)
        try:
            rows = self.engine.db.fetchall("""
                SELECT ap.id, ap.lot_no, ap.sub_lt, ap.customer, ap.qty_mt, ap.created_at
                FROM allocation_plan ap
                LEFT JOIN inventory_tonbag tb ON ap.tonbag_id = tb.id
                WHERE ap.status = 'RESERVED'
                ORDER BY COALESCE(tb.is_sample, 0), ap.lot_no, ap.sub_lt
            """) if hasattr(self.engine, 'db') and self.engine.db else []
            self._alloc_fallback = False
            if not rows and hasattr(self.engine, 'db') and self.engine.db:
                fb_rows = self.engine.db.fetchall("""
                    SELECT id, lot_no, sub_lt, picked_to AS customer, weight, updated_at, outbound_date
                    FROM inventory_tonbag
                    WHERE status = 'RESERVED'
                    ORDER BY lot_no, sub_lt
                """)
                if fb_rows:
                    rows = fb_rows
                    self._alloc_fallback = True
            for idx, r in enumerate(rows or [], 1):
                plan_id = r.get('id')
                lot_no = str(r.get('lot_no', ''))
                sub_lt = r.get('sub_lt', '')
                tonbag_no = str(sub_lt) if sub_lt is not None else '-'
                customer = str(r.get('customer', '') or '-')
                if getattr(self, '_alloc_fallback', False):
                    qty_mt = float(r.get('weight') or 0) / 1000.0
                    created = str(r.get('updated_at') or r.get('outbound_date') or '')[:10] if (r.get('updated_at') or r.get('outbound_date')) else '-'
                    iid = f"tb_{plan_id}" if plan_id is not None else ''
                else:
                    qty_mt = float(r.get('qty_mt') or 0)
                    created = str(r.get('created_at') or '')[:10] if r.get('created_at') else '-'
                    iid = f"plan_{plan_id}" if plan_id is not None else ''
                self.tree_allocation_detail.insert(
                    '', 'end', iid=iid or None, values=(
                        str(idx), lot_no, tonbag_no, customer, f"{qty_mt:,.2f}", created
                    )
                )
            if hasattr(self, '_alloc_detail_footer') and self._alloc_detail_footer:
                self._alloc_detail_footer.update_totals()
            self._alloc_lot_container.pack_forget()
            self._alloc_detail_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)
            # 상단에도 복귀 버튼 표시 (전체 배정 보기만 쓰다 보면 하단 줄만 보고 못 찾는 경우 방지)
            try:
                _bt = getattr(self, "_alloc_btn_back_top", None)
                _rf = getattr(self, "_alloc_btn_refresh", None)
                if _bt is not None and _rf is not None and _rf.winfo_exists():
                    try:
                        _bt.pack_forget()
                    except tk.TclError:
                        pass  # TclError: widget destroyed
                    _bt.pack(side=LEFT, padx=Spacing.XS, before=_rf)
            except (tk.TclError, AttributeError) as e:
                logger.debug(f"[_on_show_all_allocation] back_top pack: {e}")
        except Exception as e:
            logger.debug(f"_on_show_all_allocation: {e}")

    def _on_back_to_allocation_lot_list(self) -> None:
        """LOT 리스트로 복귀"""
        try:
            _bt = getattr(self, "_alloc_btn_back_top", None)
            if _bt is not None:
                _bt.pack_forget()
        except (tk.TclError, AttributeError) as e:
            logger.debug(f"[_on_back_to_allocation_lot_list] back_top forget: {e}")
        self._alloc_detail_container.pack_forget()
        self._alloc_lot_container.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)
        self._refresh_allocation()

    # ── v8.1.5 PATCH-D: 펼침 상세 ─────────────────────────────────────────
    def _on_alloc_tree_expand_click(self, event) -> None:
        """펼침 열(☐/☑) 클릭 시 상세 행 토글."""
        tree = self.tree_allocation
        region = tree.identify_region(event.x, event.y)
        if region not in ('cell', 'heading'):
            return
        col = tree.identify_column(event.x)
        if col != '#1':  # 첫 번째 열(expand)만 반응
            return
        row_iid = tree.identify_row(event.y)
        if not row_iid:
            return
        # 자식 행 클릭 시 부모로 올라감
        if tree.parent(row_iid):
            return
        vals = list(tree.item(row_iid).get('values') or [])
        if not vals:
            return
        already_open = (str(vals[0]).strip() == '☑')
        # ── 접기 ──
        if already_open:
            for child in tree.get_children(row_iid):
                tree.delete(child)
            vals[0] = '☐'
            tree.item(row_iid, values=vals)
            return
        # ── 펼치기 ──
        cols = [c[0] for c in ALLOCATION_LOT_COLUMNS]
        def _cv(key):
            try:
                idx = cols.index(key)
                return str(vals[idx]).strip() if len(vals) > idx else ''
            except (ValueError, IndexError):
                return ''
        lot_no   = _cv('lot_no')
        plan_date = _cv('plan_date') or '-'
        if not lot_no:
            return
        self._alloc_load_expand_detail(tree, row_iid, lot_no, plan_date)
        vals[0] = '☑'
        tree.item(row_iid, values=vals)

    def _alloc_load_expand_detail(self, tree, parent_iid: str, lot_no: str, plan_date: str) -> None:
        """lot_no + 출고예정일 기준 allocation_plan 상세 행 + 소계를 자식 노드로 삽입."""
        if not hasattr(self.engine, 'db') or not self.engine.db:
            return
        try:
            od_filter = plan_date if plan_date and plan_date != '-' else None
            params = [lot_no]
            date_sql = ''
            if od_filter:
                date_sql = " AND DATE(ap.outbound_date) = DATE(?)"
                params.append(od_filter)

            rows = self.engine.db.fetchall(
                "SELECT ap.sub_lt, ap.qty_mt, ap.outbound_date, ap.created_at, "
                "       COALESCE(tb.tonbag_no, ap.sub_lt) AS tonbag_label "
                "FROM allocation_plan ap "
                "LEFT JOIN inventory_tonbag tb ON ap.tonbag_id = tb.id "
                "WHERE ap.lot_no = ? AND ap.status = 'RESERVED' "
                + date_sql +
                " ORDER BY ap.sub_lt",
                tuple(params)
            ) or []

            if not rows:
                tree.insert(parent_iid, 'end', tags=('alloc_line',),
                            values=('', '—', '—', '—', '—', '—', '(상세 없음)'))
                return

            tot_mt  = 0.0
            tot_tb  = 0
            for r in rows:
                qty    = float(r.get('qty_mt') or 0)
                odate  = str(r.get('outbound_date') or '')[:10] or '-'
                cdate  = str(r.get('created_at') or '')[:10] or '-'
                tlabel = str(r.get('tonbag_label') or r.get('sub_lt') or '-')
                tot_mt  += qty
                tot_tb  += 1
                tree.insert(parent_iid, 'end', tags=('alloc_line',), values=(
                    '', '',          # expand, No.
                    '',              # lot_no (생략)
                    tlabel,          # customer 열에 톤백 라벨 표시
                    f'{qty:,.3f}',   # total_mt
                    '1',             # tonbag_count
                    odate,           # plan_date → 출고예정일
                ))

            # 소계 행
            tree.insert(parent_iid, 'end', tags=('alloc_subtotal',), values=(
                '', '',
                f'소계 ({tot_tb}개)',
                '',
                f'{tot_mt:,.3f}',
                str(tot_tb),
                '',
            ))
        except Exception as e:
            logger.debug(f'[_alloc_load_expand_detail] {e}')
            tree.insert(parent_iid, 'end', tags=('alloc_line',),
                        values=('', '—', '—', '—', '—', '—', '(조회 오류)'))

    _ALLOC_EDITABLE = {
        'customer':   '고객사',
        'plan_date':  '출고예정일',
        'sale_ref':   'SALE REF',
        'total_mt':   '배정수량(MT)',  # ※ 무게 보존 경고 후 허용
    }

    def _on_allocation_lot_double_click(self, event) -> None:
        """LOT 더블클릭 → 해당 LOT의 RESERVED 톤백 팝업 (우클릭 유지)"""
        pass  # 우클릭 메뉴로 이동 — 더블클릭은 _on_allocation_inline_edit 사용

    def _on_allocation_inline_edit(self, event) -> None:
        """더블클릭한 셀 → 인라인 Entry 위젯으로 직접 수정 (v8.0.9)"""
        tree = self.tree_allocation
        region = tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col_id_raw = tree.identify_column(event.x)   # '#1', '#2', ...
        row_iid   = tree.identify_row(event.y)
        if not row_iid:
            return

        # 컬럼 인덱스 → 컬럼 키
        col_idx = int(col_id_raw.replace('#', '')) - 1
        cols    = [c[0] for c in ALLOCATION_LOT_COLUMNS]
        if col_idx >= len(cols):
            return
        col_key = cols[col_idx]

        if col_key not in self._ALLOC_EDITABLE:
            return  # 수정 불가 컬럼 — 무시

        # 현재 셀 값
        vals     = list(tree.item(row_iid, 'values'))
        cur_val  = str(vals[col_idx]) if col_idx < len(vals) else ''

        # DB plan_id 조회 (iid = plan_id 또는 row에서 lot_no로 조회)
        # v8.1.5 BUG-03 동일 패턴: 안전 추출
        try:
            lot_no = str(vals[cols.index('lot_no')]).strip() if 'lot_no' in cols and len(vals) > cols.index('lot_no') else ''
        except (ValueError, IndexError):
            lot_no = ''

        # 셀 좌표 계산
        bbox = tree.bbox(row_iid, col_id_raw)
        if not bbox:
            return
        x, y, w, h = bbox

        # 인라인 Entry 위젯 생성
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
                return  # 변경 없음
            # 무게 수정 경고
            if col_key == 'total_mt':
                try:
                    from ..utils.custom_messagebox import CustomMessageBox
                    warn_msg = 'qty_mt 변경: 무게 보존 법칙 영향 가능. 계속하시겠습니까?'
                    if not CustomMessageBox.askyesno(
                        self.root, 'qty_mt 수정 경고', warn_msg
                    ):
                        return
                except Exception as e:
                    logger.warning(f"[UI] allocation qty_mt 검증: {e}")
            self._apply_allocation_edit(row_iid, col_idx, col_key, new_val, lot_no, vals)

        def _cancel(ev=None):
            entry.destroy()

        entry.bind('<Return>',  _commit)
        entry.bind('<KP_Enter>', _commit)
        entry.bind('<Escape>',  _cancel)
        entry.bind('<FocusOut>', _commit)

    def _apply_allocation_edit(self, row_iid, col_idx, col_key, new_val, lot_no, vals) -> None:
        """
        allocation_plan 수정 → inventory_tonbag 자동 동기화 → audit_log 기록 (v8.0.9)
        """
        if not hasattr(self, 'engine') or not self.engine or not hasattr(self.engine, 'db'):
            return
        db = self.engine.db

        # ── 컬럼 매핑: allocation_plan 필드 → inventory_tonbag 필드 ──────
        ALLOC_TO_TONBAG = {
            'customer':  'picked_to',
            'plan_date': 'outbound_date',
            'sale_ref':  'sale_ref',
            'total_mt':  'qty_mt',
        }
        tonbag_col = ALLOC_TO_TONBAG.get(col_key)

        # ── allocation_plan 컬럼 매핑 ──────────────────────────────────
        ALLOC_COL_MAP = {
            'customer':  'customer',
            'plan_date': 'outbound_date',
            'sale_ref':  'sale_ref',
            'total_mt':  'qty_mt',
        }
        alloc_col = ALLOC_COL_MAP.get(col_key, col_key)

        try:
            # ① allocation_plan UPDATE
            db.execute(
                f"UPDATE allocation_plan SET {alloc_col}=?, created_at=datetime('now','localtime') "
                f"WHERE lot_no=? AND status='RESERVED'",
                (new_val, lot_no)
            )

            # ② inventory_tonbag 자동 동기화
            if tonbag_col:
                db.execute(
                    f"UPDATE inventory_tonbag SET {tonbag_col}=?, updated_at=datetime('now','localtime') "
                    f"WHERE lot_no=? AND status='RESERVED'",
                    (new_val, lot_no)
                )

            # ③ inventory 동기화 (customer → picked_to 없음, outbound_date 없음)
            # inventory 테이블은 LOT 단위 summary — 필요 시 확장

            # ④ audit_log 기록
            try:
                import json
                db.execute(
                    "INSERT INTO audit_log(event_type, event_data, created_by, created_at) "
                    "VALUES (?, ?, ?, datetime('now','localtime'))",
                    (
                        'INLINE_EDIT_ALLOC',
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
                logger.debug("[THEME-FAIL] file=allocation_tab.py reason=audit_log_write: %s", ae)

            db.commit()

            # ⑤ 트리 셀 즉시 업데이트 + 펼침 상태 초기화 (수치 어긋남 방지)
            new_vals = list(vals)
            new_vals[col_idx] = new_val
            # v8.1.5 PATCH-D: 펼침 중이면 닫기 (☑→☐ + 자식 삭제)
            if new_vals and str(new_vals[0]).strip() == '☑':
                for _ch in self.tree_allocation.get_children(row_iid):
                    self.tree_allocation.delete(_ch)
                new_vals[0] = '☐'
            self.tree_allocation.item(row_iid, values=new_vals)

            # ⑥ Detail 테이블 즉시 갱신 (전체 배정 보기 열려 있으면)
            try:
                if (getattr(self, 'tree_allocation_detail', None) and
                        getattr(self, '_alloc_detail_container', None) and
                        self._alloc_detail_container.winfo_ismapped()):
                    self._on_show_all_allocation()
            except Exception as _de:
                logger.debug("[InlineEdit/Alloc] detail 갱신 무시: %s", _de)

            logger.info("[InlineEdit/Alloc] lot_no=%s %s: %s → %s",
                        lot_no, col_key, vals[col_idx] if col_idx < len(vals) else '', new_val)

        except Exception as e:
            logger.error("[InlineEdit/Alloc] 수정 실패: %s", e)
            try:
                from ..utils.custom_messagebox import CustomMessageBox
                CustomMessageBox.showerror(self.root, '수정 실패', str(e))
            except Exception as e2:
                logger.warning(f"[UI] allocation 에러 다이얼로그 표시 실패: {e2}")

    def _on_allocation_right_click(self, event) -> None:
        """④ v6.7.1: 선택 항목 취소 컨텍스트 메뉴"""
        iid = self.tree_allocation.identify_row(event.y)
        # v8.1.5 PATCH-D: 자식 행(펼침 상세)이면 부모 LOT 행 기준으로 메뉴 표시
        if iid and self.tree_allocation.parent(iid):
            iid = self.tree_allocation.parent(iid)
        if iid:
            sel = self.tree_allocation.selection()
            if iid not in sel:
                self.tree_allocation.selection_set(iid)
        sel = [i for i in self.tree_allocation.selection()
               if not self.tree_allocation.parent(i)]
        if not sel:
            return
        popup = tk.Menu(self.root, tearoff=0)
        popup.add_command(
            label=f"❌ 선택 {len(sel)}건 예약 취소",
            command=lambda: self._cancel_selected_allocations(sel)
        )
        popup.add_separator()
        popup.add_command(label="전체 취소 (주의)", command=self._cancel_all_allocations)
        try:
            popup.tk_popup(event.x_root, event.y_root)
        finally:
            popup.grab_release()

    def _cancel_selected_allocations(self, selection) -> None:
        """④ v6.7.1: 선택한 allocation_plan 건만 취소."""
        from gui_app_modular.utils.custom_messagebox import CustomMessageBox
        # 선택 항목에서 plan_id 추출 (iid = plan_id 또는 values[0])
        plan_ids = []
        lot_labels = []
        for iid in selection:
            vals = self.tree_allocation.item(iid)['values']
            try:
                # allocation_tab 컬럼: lot_no, customer, qty_mt, outbound_date, ...
                lot_no = str(vals[0]) if vals else ''
                # allocation_plan id는 iid로 저장 시도
                try:
                    pid = int(iid)
                    plan_ids.append(pid)
                except (ValueError, TypeError):
                    logger.debug("[SUPPRESSED] exception in allocation_tab.py")  # noqa
                if lot_no:
                    lot_labels.append(lot_no)
            except (IndexError, TypeError):
                logger.debug("[SUPPRESSED] exception in allocation_tab.py")  # noqa

        if not plan_ids and not lot_labels:
            CustomMessageBox.showwarning(self.root, "알림", "취소할 항목을 선택하세요.")
            return

        msg = (
            f"선택한 {len(selection)}건 예약을 취소하시겠습니까?\n\n"
            f"LOT: {', '.join(lot_labels[:5])}{'...' if len(lot_labels)>5 else ''}\n\n"
            f"⚠️ 취소 후 AVAILABLE로 복원됩니다."
        )
        if not CustomMessageBox.askyesno(self.root, "예약 취소 확인", msg):
            return

        try:
            if plan_ids:
                result = self.engine.cancel_reservation(plan_ids=plan_ids)
            else:
                # plan_id 없으면 lot_no 기반 취소
                cancelled = 0
                for lot_no in lot_labels:
                    r = self.engine.cancel_reservation(lot_no=lot_no)
                    cancelled += r.get('cancelled', 0)
                result = {'success': True, 'cancelled': cancelled}

            if result.get('success'):
                CustomMessageBox.showinfo(
                    self.root, "취소 완료",
                    f"✅ {result.get('cancelled', 0)}개 톤백 예약 취소 완료"
                )
                self._refresh_allocation()
            else:
                CustomMessageBox.showerror(
                    self.root, "취소 실패",
                    "\n".join(result.get('errors', ['알 수 없는 오류']))
                )
        except Exception as e:
            CustomMessageBox.showerror(self.root, "오류", str(e))

    def _cancel_all_allocations(self) -> None:
        """④ v6.7.1: 전체 취소 — 명시적 경고 후 실행."""
        from gui_app_modular.utils.custom_messagebox import CustomMessageBox
        if not CustomMessageBox.askyesno(
            self.root, "⚠️ 전체 취소 경고",
            "RESERVED 상태 톤백 전체를 AVAILABLE로 되돌립니다.\n\n"
            "이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?"
        ):
            return
        try:
            result = self.engine.cancel_reservation()
            if result.get('success'):
                CustomMessageBox.showinfo(
                    self.root, "전체 취소 완료",
                    f"✅ {result.get('cancelled', 0)}개 톤백 전체 예약 취소 완료"
                )
                self._refresh_allocation()
            else:
                CustomMessageBox.showerror(
                    self.root, "실패",
                    "\n".join(result.get('errors', ['알 수 없는 오류']))
                )
        except Exception as e:
            CustomMessageBox.showerror(self.root, "오류", str(e))


    def _on_allocation_cancel_by_sale_ref(self) -> None:
        """v7.7.1: SALE REF 기준 일괄 취소 -> 판매가능."""
        root = getattr(self, 'root', None)
        engine = getattr(self, 'engine', None)
        if not engine or not hasattr(engine, 'cancel_reservation'):
            from ..utils.ui_constants import CustomMessageBox
            CustomMessageBox.showwarning(root, "기능 없음", "예약 취소 기능을 사용할 수 없습니다.")
            return
        try:
            sale_ref = CustomMessageBox.askstring(
                root,
                "SALE REF 일괄 취소",
                "취소할 SALE REF(판매참조번호)를 입력하세요.\n예: 1955",
            )
        except Exception as e:
            logger.exception("SALE REF 일괄 취소 입력창 오류: %s", e)
            CustomMessageBox.showerror(
                root, "오류",
                f"입력 창을 열 수 없습니다.\n{e}\n\n로그에 자세한 내용이 기록됩니다.",
            )
            return
        if sale_ref is None:
            return
        if not str(sale_ref).strip():
            CustomMessageBox.showwarning(
                root, "입력 필요",
                "SALE REF를 입력한 뒤 [확인]을 눌러 주세요.\n(취소하려면 [취소] 또는 창 닫기)",
            )
            return
        sale_ref = str(sale_ref).strip()
        try:
            preview = engine.db.fetchall(
                "SELECT COUNT(*) as cnt, COUNT(DISTINCT lot_no) as lots "
                "FROM allocation_plan WHERE sale_ref=? AND status='RESERVED'",
                (sale_ref,)
            )
            cnt  = int(preview[0].get('cnt',0)  if isinstance(preview[0], dict) else preview[0][0]) if preview else 0
            lots = int(preview[0].get('lots',0) if isinstance(preview[0], dict) else preview[0][1]) if preview else 0
        except Exception:
            cnt, lots = 0, 0
        from ..utils.ui_constants import CustomMessageBox
        if cnt == 0:
            CustomMessageBox.showwarning(
                root, "대상 없음",
                "SALE REF='" + sale_ref + "'에 해당하는 RESERVED 예약이 없습니다."
            )
            return
        if not CustomMessageBox.askyesno(
            root, "SALE REF 일괄 취소",
            "SALE REF='" + sale_ref + "' 예약 " + str(cnt) + "건 (" + str(lots) + "개 LOT)을\n"
            "모두 취소하여 판매가능으로 되돌립니다.\n\n계속하시겠습니까?"
        ):
            return
        result = engine.cancel_reservation(sale_ref=sale_ref)
        cancelled = result.get('cancelled', 0)
        if result.get('success') or cancelled > 0:
            CustomMessageBox.showinfo(
                root, "취소 완료",
                "SALE REF='" + sale_ref + "' 예약 " + str(cancelled) + "건 취소 완료.\n(-> 판매가능으로 복원)"
            )
            logger.info("[SALE_REF_CANCEL] sale_ref=" + sale_ref + " " + str(cancelled) + "건 취소")
        else:
            errs = result.get('errors', [])
            CustomMessageBox.showwarning(root, "취소 실패", "\n".join(errs) if errs else "취소 실패")
        self._safe_refresh()

    def _on_allocation_cancel_to_available(self) -> None:
        """판매 배정(LOT 리스트)에서 취소 → 판매가능.
        v8.1.8 BUG-B 수정: _alloc_fallback 상태에서도 취소 허용.
        탭에서 LOT 선택 시 선택분만, 미선택 시 전체 확인 후 실행.
        """
        root = getattr(self, 'root', None)
        engine = getattr(self, 'engine', None)
        if not engine or not hasattr(engine, 'cancel_reservation'):
            CustomMessageBox.showwarning(root, "기능 없음", "예약 취소 기능을 사용할 수 없습니다.")
            return

        # v8.1.8: _alloc_fallback이더라도 inventory_tonbag 직접 조회로 폴백
        is_fallback = getattr(self, '_alloc_fallback', False)
        sel = self.tree_allocation.selection()
        cols = [c[0] for c in ALLOCATION_LOT_COLUMNS]

        if sel:
            # ── 탭 선택 항목 우선 처리 ────────────────────────────────────
            def _col_val(vals, key):
                try:
                    idx = cols.index(key)
                    return str(vals[idx]).strip() if len(vals) > idx else ''
                except (ValueError, IndexError):
                    return ''
            targets = []
            for s in sel:
                vals = self.tree_allocation.item(s).get('values', [])
                lot_no = _col_val(vals, 'lot_no')
                plan_date = _col_val(vals, 'plan_date') or '-'
                if lot_no:
                    targets.append((lot_no, plan_date))
            targets = list(dict.fromkeys(targets))
            if not targets:
                return
            if not CustomMessageBox.askyesno(
                root, "판매 배정 취소",
                f"선택한 {len(targets)}개 행의 배정을 취소하여 판매가능으로 되돌립니다.\n계속하시겠습니까?"
            ):
                return
            total = 0
            for lot_no, plan_date in targets:
                od = plan_date if plan_date and plan_date != '-' else None
                r = engine.cancel_reservation(lot_no=lot_no, outbound_date=od)
                total += r.get('cancelled', 0)
            CustomMessageBox.showinfo(root, "취소 완료", f"{total}건 취소되었습니다. (→ 판매가능)")
        else:
            # ── 선택 없음: 전체 취소 ─────────────────────────────────────
            warn_msg = ""
            if is_fallback:
                warn_msg = ("[폴백 모드] allocation_plan 데이터 없음 — "
                            "inventory_tonbag RESERVED 기준으로 취소합니다.\n\n")
            if not CustomMessageBox.askyesno(
                root, "전체 취소",
                f"{warn_msg}전체 판매 배정을 취소하여 판매가능으로 되돌립니다.\n계속하시겠습니까?"
            ):
                return
            # v8.6.5: RESERVED + PICKED + OUTBOUND 전체 활성 배정 취소
            all_active = engine.db.fetchall(
                "SELECT id, status FROM allocation_plan "
                "WHERE status IN ('RESERVED','PENDING_APPROVAL','STAGED','PICKED','EXECUTED','OUTBOUND','SOLD','SHIPPED','CONFIRMED')"
            ) or []
            all_plan_ids = [row['id'] if isinstance(row, dict) else row[0] for row in all_active]
            if not all_plan_ids:
                CustomMessageBox.showinfo(root, "취소 완료", "취소할 배정이 없습니다.")
                self._safe_refresh()
                return
            # 상태별 건수 표시
            _statuses = {}
            for row in all_active:
                s = row['status'] if isinstance(row, dict) else row[1]
                _statuses[s] = _statuses.get(s, 0) + 1
            _status_summary = ', '.join(f"{s}:{c}건" for s, c in _statuses.items())
            if not CustomMessageBox.askyesno(
                root, "전체 취소 (PICKED/OUTBOUND 포함)",
                f"전체 {len(all_plan_ids)}건을 취소합니다.\n"
                f"({_status_summary})\n\n"
                f"PICKED/OUTBOUND 상태도 모두 AVAILABLE로 복원됩니다.\n계속하시겠습니까?"
            ):
                return
            has_picked = any(s in _statuses for s in ('PICKED', 'EXECUTED'))
            has_outbound = any(s in _statuses for s in ('OUTBOUND', 'SOLD', 'SHIPPED', 'CONFIRMED'))
            r = engine.cancel_reservation(
                plan_ids=all_plan_ids,
                include_picked=has_picked,
                include_outbound=has_outbound
            )
            total = r.get('cancelled', 0)
            CustomMessageBox.showinfo(root, "취소 완료", f"{total}건 취소되었습니다. (→ 판매가능)")
        self._safe_refresh()

    def _on_revert_step(self, from_status: str) -> None:
        """v8.6.5: 개별 단계 되돌리기 — 지정 상태만 직전 상태로 복원."""
        root = getattr(self, 'root', None)
        engine = getattr(self, 'engine', None)
        if not engine:
            return

        # 상태 그룹 매핑
        _STATUS_GROUPS = {
            'RESERVED': {
                'source': ('RESERVED', 'PENDING_APPROVAL', 'STAGED'),
                'target_tb': 'AVAILABLE',
                'target_plan': 'CANCELLED',
                'label': 'RESERVED → AVAILABLE',
                'tb_clear': ('picked_to', 'sale_ref'),
            },
            'PICKED': {
                'source': ('PICKED', 'EXECUTED'),
                'target_tb': 'RESERVED',
                'target_plan': 'RESERVED',
                'label': 'PICKED → RESERVED',
                'tb_clear': ('outbound_date',),
            },
            'OUTBOUND': {
                'source': ('OUTBOUND', 'SOLD', 'SHIPPED', 'CONFIRMED'),
                'target_tb': 'PICKED',
                'target_plan': 'EXECUTED',
                'label': 'OUTBOUND → PICKED',
                'tb_clear': ('outbound_date',),
            },
        }
        grp = _STATUS_GROUPS.get(from_status)
        if not grp:
            return

        try:
            source_ph = ','.join('?' * len(grp['source']))
            plans = engine.db.fetchall(
                f"SELECT id, lot_no, tonbag_id, status FROM allocation_plan "
                f"WHERE status IN ({source_ph})",
                grp['source']
            ) or []
        except Exception as e:
            CustomMessageBox.showerror(root, "오류", f"조회 실패: {e}")
            return

        if not plans:
            CustomMessageBox.showinfo(root, grp['label'],
                f"{'/'.join(grp['source'])} 상태의 배정이 없습니다.")
            return

        cnt = len(plans)
        if not CustomMessageBox.askyesno(
            root, f"↩️ {grp['label']}",
            f"{'/'.join(grp['source'])} 상태 {cnt}건을\n"
            f"{grp['target_tb']}로 되돌립니다.\n\n계속하시겠습니까?"
        ):
            return

        try:
            from datetime import datetime
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            reverted = 0

            with engine.db.transaction("IMMEDIATE"):
                touched_lots = set()
                for plan in plans:
                    _plan_id = plan.get('id') if isinstance(plan, dict) else plan[0]
                    _lot = plan.get('lot_no', '') if isinstance(plan, dict) else plan[1]
                    _tb_id = plan.get('tonbag_id') if isinstance(plan, dict) else plan[2]

                    # 톤백 상태 복원
                    if _tb_id:
                        if grp['target_tb'] == 'AVAILABLE':
                            engine.db.execute(
                                "UPDATE inventory_tonbag SET status=?, "
                                "picked_to=NULL, sale_ref=NULL, outbound_date=NULL, updated_at=? "
                                "WHERE id=?", (grp['target_tb'], now, _tb_id))
                        else:
                            engine.db.execute(
                                "UPDATE inventory_tonbag SET status=?, outbound_date=NULL, updated_at=? "
                                "WHERE id=?", (grp['target_tb'], now, _tb_id))
                    elif _lot:
                        # LOT 모드
                        src_ph = ','.join('?' * len(grp['source']))
                        if grp['target_tb'] == 'AVAILABLE':
                            engine.db.execute(
                                f"UPDATE inventory_tonbag SET status=?, "
                                f"picked_to=NULL, sale_ref=NULL, outbound_date=NULL, updated_at=? "
                                f"WHERE lot_no=? AND status IN ({src_ph})",
                                [grp['target_tb'], now, _lot] + list(grp['source']))
                        else:
                            engine.db.execute(
                                f"UPDATE inventory_tonbag SET status=?, outbound_date=NULL, updated_at=? "
                                f"WHERE lot_no=? AND status IN ({src_ph})",
                                [grp['target_tb'], now, _lot] + list(grp['source']))

                    # OUTBOUND → PICKED: sold_table도 되돌리기
                    if from_status == 'OUTBOUND' and _lot:
                        engine.db.execute(
                            "UPDATE sold_table SET status='RETURNED' "
                            "WHERE lot_no=? AND status IN ('OUTBOUND','SOLD')", (_lot,))

                    # allocation_plan 상태 변경
                    engine.db.execute(
                        "UPDATE allocation_plan SET status=?, cancelled_at=? WHERE id=?",
                        (grp['target_plan'], now, _plan_id))

                    reverted += 1
                    if _lot:
                        touched_lots.add(_lot)

                # LOT 상태 재계산
                for lot in touched_lots:
                    if hasattr(engine, '_recalc_lot_status'):
                        engine._recalc_lot_status(lot)

                # 이력
                engine.db.execute(
                    "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                    "VALUES (?, ?, 0, ?, ?)",
                    ('ALL', f'REVERT_{from_status}', f"{reverted}건 {grp['label']}", now))

            CustomMessageBox.showinfo(root, "되돌리기 완료",
                f"{reverted}건 {grp['label']} 완료")
            logger.info(f"[되돌리기] {reverted}건 {grp['label']}")

        except Exception as e:
            logger.error(f"[되돌리기] 오류: {e}", exc_info=True)
            CustomMessageBox.showerror(root, "되돌리기 실패", f"오류:\n{e}")

        self._safe_refresh()

    def _on_allocation_reset_all(self) -> None:
        """v8.6.5: 배정 전체 초기화 — 모든 상태의 배정을 CANCELLED + 톤백 AVAILABLE 복원."""
        root = getattr(self, 'root', None)
        engine = getattr(self, 'engine', None)
        if not engine:
            return

        # 현황 조회
        try:
            stats = engine.db.fetchall(
                "SELECT status, COUNT(*) as cnt FROM allocation_plan "
                "WHERE status NOT IN ('CANCELLED') GROUP BY status"
            ) or []
        except Exception as e:
            CustomMessageBox.showerror(root, "오류", f"현황 조회 실패: {e}")
            return

        if not stats:
            CustomMessageBox.showinfo(root, "초기화", "취소할 배정이 없습니다. (모두 CANCELLED 상태)")
            return

        # 상태별 현황 표시
        total = 0
        lines = []
        for row in stats:
            s = row['status'] if isinstance(row, dict) else row[0]
            c = row['cnt'] if isinstance(row, dict) else row[1]
            lines.append(f"  • {s}: {c}건")
            total += c

        msg = (
            f"배정 전체 초기화\n\n"
            f"현재 활성 배정 {total}건:\n" +
            "\n".join(lines) +
            f"\n\n이 배정을 전부 CANCELLED 처리하고\n"
            f"톤백을 AVAILABLE로 복원합니다.\n\n"
            f"계속하시겠습니까?"
        )
        if not CustomMessageBox.askyesno(root, "🧹 배정 전체 초기화", msg):
            return

        # 2차 확인
        if not CustomMessageBox.askyesno(
            root, "⚠️ 최종 확인",
            f"정말로 {total}건 전체를 초기화하시겠습니까?\n"
            f"이 작업은 되돌릴 수 없습니다.\n"
            f"(DB 백업은 자동 생성됩니다)"
        ):
            return

        try:
            import sqlite3
            from datetime import datetime
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # DB 백업
            import shutil, os
            db_path = engine.db.db_path if hasattr(engine.db, 'db_path') else str(getattr(engine.db, '_db_path', ''))
            if db_path and os.path.exists(db_path):
                backup = db_path.replace('.db', f'_reset_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
                shutil.copy2(db_path, backup)
                logger.info(f"[배정초기화] 백업: {backup}")

            # LOT 수집
            lots = engine.db.fetchall(
                "SELECT DISTINCT lot_no FROM allocation_plan WHERE status NOT IN ('CANCELLED')"
            ) or []
            lot_nos = [r['lot_no'] if isinstance(r, dict) else r[0] for r in lots]

            with engine.db.transaction("IMMEDIATE"):
                # 1. allocation_plan 전체 CANCELLED
                cnt_plan = engine.db.execute(
                    "UPDATE allocation_plan SET status='CANCELLED', cancelled_at=? "
                    "WHERE status NOT IN ('CANCELLED')", (now,)
                )

                # 2. 톤백 AVAILABLE 복원 (RESERVED/PICKED 상태)
                cnt_tb = 0
                if lot_nos:
                    ph = ','.join('?' * len(lot_nos))
                    cnt_tb = engine.db.execute(
                        f"UPDATE inventory_tonbag SET status='AVAILABLE', "
                        f"picked_to=NULL, sale_ref=NULL, outbound_date=NULL, updated_at=? "
                        f"WHERE lot_no IN ({ph}) AND status IN ('RESERVED','PICKED')",
                        [now] + lot_nos
                    )

                    # 3. LOT 상태 복원
                    engine.db.execute(
                        f"UPDATE inventory SET status='AVAILABLE' "
                        f"WHERE lot_no IN ({ph}) AND status IN ('RESERVED','PICKED','PARTIAL')",
                        lot_nos
                    )

                # 4. 이력
                engine.db.execute(
                    "INSERT INTO stock_movement (lot_no, movement_type, qty_kg, remarks, created_at) "
                    "VALUES (?, 'RESET_ALL_ALLOCATION', 0, ?, ?)",
                    ('ALL', f"총 {total}건 초기화", now)
                )

            CustomMessageBox.showinfo(
                root, "초기화 완료",
                f"배정 {total}건 → CANCELLED\n"
                f"톤백 AVAILABLE 복원 완료\n\n"
                f"배정 엑셀을 다시 업로드하세요."
            )
            logger.info(f"[배정초기화] {total}건 CANCELLED, 톤백 복원 완료")

        except Exception as e:
            logger.error(f"[배정초기화] 오류: {e}", exc_info=True)
            CustomMessageBox.showerror(root, "초기화 실패", f"오류 발생:\n{e}")

        self._safe_refresh()

    def _on_allocation_toggle_select_all(self) -> None:
        """v8.4.1 [E]: 전체 선택 / 전체 해제 토글."""
        tree = getattr(self, 'tree_allocation', None)
        if not tree:
            return
        all_items = tree.get_children()
        if not all_items:
            return
        self._alloc_select_all_state = not getattr(self, '_alloc_select_all_state', False)
        if self._alloc_select_all_state:
            tree.selection_set(all_items)
            if hasattr(self, '_alloc_btn_select_all'):
                self._alloc_btn_select_all.config(text="☐ 전체 해제")
        else:
            tree.selection_remove(*all_items)
            if hasattr(self, '_alloc_btn_select_all'):
                self._alloc_btn_select_all.config(text="☑ 전체 선택")

    def _on_allocation_detail_cancel_selected(self) -> None:
        """전체 배정 보기에서 선택한 행만 취소 → 판매가능.
        v8.1.8 BUG-B 수정: _alloc_fallback 차단 제거."""
        root = getattr(self, 'root', None)
        engine = getattr(self, 'engine', None)
        if not engine or not hasattr(engine, 'cancel_reservation'):
            CustomMessageBox.showwarning(root, "기능 없음", "예약 취소 기능을 사용할 수 없습니다.")
            return
        sel = self.tree_allocation_detail.selection()
        if not sel:
            CustomMessageBox.showwarning(root, "선택 필요", "취소할 행을 선택하세요.")
            return
        plan_ids = []
        for iid in sel:
            if isinstance(iid, str) and iid.startswith("plan_"):
                try:
                    plan_ids.append(int(iid.replace("plan_", "")))
                except ValueError as e:
                    logger.warning(f"[_on_allocation_detail_cancel_selected] Suppressed: {e}")
        if not plan_ids:
            CustomMessageBox.showwarning(root, "선택 필요", "취소할 배정 행을 선택하세요.")
            return
        if not CustomMessageBox.askyesno(
            root, "선택 취소",
            f"선택한 {len(plan_ids)}건을 취소하여 판매가능으로 되돌립니다.\n계속하시겠습니까?"
        ):
            return
        r = engine.cancel_reservation(plan_ids=plan_ids)
        CustomMessageBox.showinfo(root, "취소 완료", r.get('message', f"{r.get('cancelled', 0)}건 취소됨"))
        self._on_show_all_allocation()
        self._safe_refresh()

    def _on_allocation_detail_cancel_all(self) -> None:
        """전체 배정 보기에서 전체 취소 → 판매가능.
        v8.6.5: PICKED/OUTBOUND 포함 전체 취소."""
        root = getattr(self, 'root', None)
        engine = getattr(self, 'engine', None)
        if not engine or not hasattr(engine, 'cancel_reservation'):
            CustomMessageBox.showwarning(root, "기능 없음", "예약 취소 기능을 사용할 수 없습니다.")
            return
        # v8.6.5: 전체 활성 배정 조회 (RESERVED + PICKED + OUTBOUND)
        all_active = engine.db.fetchall(
            "SELECT id, status FROM allocation_plan "
            "WHERE status IN ('RESERVED','PENDING_APPROVAL','STAGED','PICKED','EXECUTED','OUTBOUND','SOLD','SHIPPED','CONFIRMED')"
        ) or []
        all_plan_ids = [row['id'] if isinstance(row, dict) else row[0] for row in all_active]
        if not all_plan_ids:
            CustomMessageBox.showinfo(root, "취소 완료", "취소할 배정이 없습니다.")
            return
        _statuses = {}
        for row in all_active:
            s = row['status'] if isinstance(row, dict) else row[1]
            _statuses[s] = _statuses.get(s, 0) + 1
        _status_summary = ', '.join(f"{s}:{c}건" for s, c in _statuses.items())
        if not CustomMessageBox.askyesno(
            root, "전체 취소 (PICKED/OUTBOUND 포함)",
            f"전체 {len(all_plan_ids)}건을 취소합니다.\n({_status_summary})\n\n계속하시겠습니까?"
        ):
            return
        has_picked = any(s in _statuses for s in ('PICKED', 'EXECUTED'))
        has_outbound = any(s in _statuses for s in ('OUTBOUND', 'SOLD', 'SHIPPED', 'CONFIRMED'))
        r = engine.cancel_reservation(
            plan_ids=all_plan_ids,
            include_picked=has_picked,
            include_outbound=has_outbound
        )
        CustomMessageBox.showinfo(root, "취소 완료", r.get('message', f"{r.get('cancelled', 0)}건 취소됨"))
        self._on_show_all_allocation()
        self._safe_refresh()
