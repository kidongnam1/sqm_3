"""
SQM v6.12.1 — 반품 미리보기 편집 다이얼로그
=============================================
Excel 반품 입고 시 DB 반영 전 미리보기 + 셀 편집 기능.
수동입고 미리보기와 동일한 인라인 편집 패턴.
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
from gui_app_modular.utils.ui_constants import tc  # v8.1.3: top-level import (gui_bootstrap 종속 제거)
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


class ReturnInboundPreviewDialog:
    """
    반품 입고 미리보기 + 편집 다이얼로그.

    Args:
        parent: 부모 윈도우
        items: 파싱된 반품 아이템 리스트
            [{'lot_no': ..., 'weight_mt': ..., 'tonbag_count': ..., 'picking_no': ...,
              'reason': ..., 'remark': ...}, ...]
        on_confirm: 확인 시 콜백 — 편집된 items를 인자로 받음
        current_theme: 현재 테마
    """

    EDITABLE_COLS = ('lot_no', 'picking_no', 'reason', 'remark')
    DISPLAY_COLS = ('no', 'lot_no', 'weight_mt', 'tonbag_count', 'picking_no',
                    'reason', 'remark')
    HEADERS = ('#', 'LOT NO', '중량(MT)', '톤백수', 'PICKING NO',
               '반품 사유', '비고')
    WIDTHS = (35, 100, 70, 55, 90, 140, 120)

    def __init__(self, parent, items: list, on_confirm=None,
                 current_theme: str = 'darkly'):
        self.parent = parent
        self.items = items
        self.on_confirm = on_confirm
        self.confirmed = False
        self._editing_item = None

        dark_mode = is_dark() if ThemeColors else False
        bg = ThemeColors.get('bg_card', is_dark()) if ThemeColors else '#FFFFFF'
        fg = ThemeColors.get('text_primary', is_dark()) if ThemeColors else '#000000'

        self.popup = create_themed_toplevel(parent)
        self.popup.title(f"🔄 반품 입고 미리보기 ({len(items)}건)")
        self.popup.transient(parent)
        self.popup.grab_set()
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(self.popup, "return_preview_dialog", parent, "large")
        elif DialogSize:
            self.popup.geometry(DialogSize.get_geometry(parent, 'large'))
            if apply_modal_window_options:
                apply_modal_window_options(self.popup)
            if center_dialog:
                center_dialog(self.popup, parent)
        else:
            self.popup.geometry("850x500")
        self.popup.configure(bg=bg)

        # ═══ 안내 ═══
        info = tk.Frame(self.popup, bg=bg, pady=5)
        info.pack(fill=X, padx=10)
        tk.Label(info,
                 text=f"총 {len(items)}건 | 사유·비고 셀 더블클릭 편집 가능 | 1건이라도 실패 시 전체 롤백",
                 font=('맑은 고딕', 10), bg=bg, fg=tc('danger')).pack(anchor='w')

        # ═══ Treeview ═══
        tree_frame = tk.Frame(self.popup, bg=bg)
        tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(
            tree_frame, columns=self.DISPLAY_COLS, show='headings', height=15
        )
        # 자체 인라인 편집 로직 사용(전역 editable 훅 중복 방지)
        self.tree._disable_global_editable = True
        for cid, hdr, w in zip(self.DISPLAY_COLS, self.HEADERS, self.WIDTHS):
            self.tree.heading(cid, text=hdr, anchor='center')
            anchor = 'e' if cid in ('weight_mt', 'tonbag_count') else 'center'
            self.tree.column(cid, width=w, anchor=anchor)

        sb = tk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        sb_x = tk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=sb_x.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        # v8.1.8: 합계 footer
        from ..utils.tree_enhancements import TreeviewTotalFooter
        self._return_footer = TreeviewTotalFooter(
            tree_frame, self.tree,
            summable_column_ids=['weight_mt', 'tonbag_count'],
            column_display_names={'weight_mt': '중량(MT)', 'tonbag_count': '톤백수'},
            column_formats={'weight_mt': ',.3f'},
        )
        self._return_footer.pack(fill='x')
        sb.pack(side=RIGHT, fill=Y)
        # v8.1.9: TreeviewTotalFooter
        try:
            from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter as _TTF
            _footer = _TTF(
                tree_frame, self.tree,
                summable_column_ids=['weight_mt'],
                column_display_names={'weight_mt': '중량(MT)'},
                column_formats={'weight_mt': ',.3f'},
            )
            _footer.pack(fill='x')
            self._footer_tree = _footer
        except Exception as e:
            logger.warning(f'[UI] return_dialog: {e}')
        sb_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 데이터 로드
        for idx, item in enumerate(items):
            self.tree.insert('', END, iid=str(idx), values=(
                idx + 1,
                item.get('lot_no', ''),
                f"{item.get('weight_mt', 0):.2f}",
                item.get('tonbag_count', 0),
                item.get('picking_no', ''),
                item.get('reason', ''),
                item.get('remark', ''),
            ))

        self.tree.bind('<Double-1>', self._on_cell_edit)

        # ═══ 하단 버튼 ═══
        btn_bar = tk.Frame(self.popup, bg=bg, pady=8)
        btn_bar.pack(fill=X, padx=10)

        total_mt = sum(it.get('weight_mt', 0) for it in items)
        total_tb = sum(it.get('tonbag_count', 0) for it in items)
        tk.Label(btn_bar,
                 text=f"합계: {total_mt:.1f} MT | 톤백 {total_tb}개 | ⚠️ 매칭 실패 시 전체 중단",
                 font=('맑은 고딕', 10), bg=bg, fg=fg).pack(side=LEFT)

        ttk.Button(btn_bar, text="취소", command=self.popup.destroy).pack(side=RIGHT, padx=5)
        ttk.Button(btn_bar, text="🔄 반품 실행", command=self._on_submit).pack(side=RIGHT, padx=5)

        self.popup.wait_window()

    def _on_cell_edit(self, event):
        """셀 더블클릭 → 인라인 Entry 편집."""
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col_id = self.tree.identify_column(event.x)
        col_idx = int(col_id.replace('#', '')) - 1
        if col_idx < 0 or col_idx >= len(self.DISPLAY_COLS):
            return
        col_name = self.DISPLAY_COLS[col_idx]
        if col_name not in self.EDITABLE_COLS:
            return

        item = self.tree.identify_row(event.y)
        if not item:
            return

        self._finish_editing()

        bbox = self.tree.bbox(item, col_id)
        if not bbox:
            return
        x, y, w, h = bbox

        current_val = self.tree.set(item, col_name)
        entry = tk.Entry(self.tree, font=('맑은 고딕', 10))
        entry.insert(0, current_val)
        entry.select_range(0, 'end')
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()

        self._editing_item = (item, col_name, entry)
        entry.bind('<Return>', lambda e: self._finish_editing())
        entry.bind('<Escape>', lambda e: self._cancel_editing())
        entry.bind('<FocusOut>', lambda e: self._finish_editing())

    def _finish_editing(self):
        if not self._editing_item:
            return
        item, col_name, entry = self._editing_item
        new_val = entry.get().strip()
        entry.destroy()
        self._editing_item = None

        idx = int(item)
        self.items[idx][col_name] = new_val
        self.tree.set(item, col_name, new_val)

    def _cancel_editing(self):
        if self._editing_item:
            self._editing_item[2].destroy()
            self._editing_item = None

    def _on_submit(self):
        self._finish_editing()
        self.confirmed = True
        self.popup.destroy()
        if self.on_confirm:
            self.on_confirm(self.items)


# ─── v7.0.0: RETURN_AS_REINBOUND 정책 다이얼로그 ─────────────────────────────
try:
    from engine_modules.return_reinbound_engine import ReturnReinboundEngine
    _ENGINE_AVAILABLE = True
except ImportError:
    ReturnReinboundEngine = None
    _ENGINE_AVAILABLE = False


class ReturnReinboundDialog:
    """
    RETURN_AS_REINBOUND 정책 반품 처리 다이얼로그 (v7.0.0).

    기존 입고 다이얼로그의 Rack Scan → Tonbag Scan 흐름을 재활용하여
    반품 처리를 수행합니다.

    처리 흐름:
      1. 출고 이력(outbound_id, lot_no) 표시
      2. Rack 위치 PDA 스캔 입력
      3. 반품 사유 입력
      4. ReturnReinboundEngine.process() 호출
      5. 결과 표시 (성공 / 오류)

    Args:
        parent:      부모 윈도우
        db_conn:     sqlite3.Connection (운영 DB)
        outbound_id: 원출고 ID (OUT…)
        lot_no:      반품 LOT 번호
        customer:    고객사 명
        on_success:  성공 시 콜백 (return_id, new_location) → None
        current_theme: 테마명
    """

    def __init__(
        self,
        parent,
        db_conn,
        outbound_id: str,
        lot_no: str,
        customer: str = '',
        on_success=None,
        current_theme: str = 'darkly',
    ):
        self.parent      = parent
        self.db_conn     = db_conn
        self.outbound_id = outbound_id
        self.lot_no      = lot_no
        self.customer    = customer
        self.on_success  = on_success
        self.result      = None

        self.popup = create_themed_toplevel(parent)
        self.popup.title(f"반품 처리 — {lot_no}")
        self.popup.resizable(True, True)

        if apply_modal_window_options:
            apply_modal_window_options(self.popup)
        if center_dialog:
            center_dialog(self.popup, 420, 340)

        self._build_ui()

    def _build_ui(self):
        pad = dict(padx=12, pady=6)

        # ── 정보 표시 ──
        info_frame = ttk.LabelFrame(self.popup, text="반품 정보", padding=8)
        info_frame.pack(fill='x', **pad)

        ttk.Label(info_frame, text=f"LOT NO:      {self.lot_no}").pack(anchor='w')
        ttk.Label(info_frame, text=f"출고 ID:     {self.outbound_id}").pack(anchor='w')
        ttk.Label(info_frame, text=f"고객사:      {self.customer}").pack(anchor='w')

        # ── 새 위치 입력 (PDA 스캔) ──
        loc_frame = ttk.LabelFrame(self.popup, text="새 Rack 위치 (PDA 스캔)", padding=8)
        loc_frame.pack(fill='x', **pad)

        ttk.Label(loc_frame, text="위치 코드:").pack(anchor='w')
        self.loc_var = tk.StringVar()
        loc_entry = ttk.Entry(loc_frame, textvariable=self.loc_var, width=20)
        loc_entry.pack(anchor='w', pady=2)
        loc_entry.focus_set()
        ttk.Label(
            loc_frame,
            text="예: B-02-03-01",
            foreground=tc('text_muted'),
        ).pack(anchor='w')

        # ── 반품 사유 ──
        reason_frame = ttk.LabelFrame(self.popup, text="반품 사유", padding=8)
        reason_frame.pack(fill='x', **pad)

        self.reason_var = tk.StringVar(value='계약 변경')
        for reason in ['품질 이슈', '계약 변경', '물류 오류', '직접 입력']:
            ttk.Radiobutton(
                reason_frame,
                text=reason,
                variable=self.reason_var,
                value=reason,
                command=self._on_reason_change,
            ).pack(anchor='w')

        self.reason_custom = ttk.Entry(reason_frame, width=30, state='disabled')
        self.reason_custom.pack(anchor='w', pady=2)

        # ── 버튼 ──
        btn_frame = ttk.Frame(self.popup)
        btn_frame.pack(fill='x', padx=12, pady=10)

        ttk.Button(
            btn_frame, text="✅ 반품 처리",
            command=self._on_confirm,
        ).pack(side='left', padx=4)

        ttk.Button(
            btn_frame, text="취소",
            command=self.popup.destroy,
        ).pack(side='left', padx=4)

        # 상태 표시
        self.status_var = tk.StringVar()
        ttk.Label(self.popup, textvariable=self.status_var, foreground=tc('danger')).pack(pady=4)

    def _on_reason_change(self):
        if self.reason_var.get() == '직접 입력':
            self.reason_custom.config(state='normal')
            self.reason_custom.focus_set()
        else:
            self.reason_custom.config(state='disabled')

    def _on_confirm(self):
        new_location = self.loc_var.get().strip()
        if not new_location:
            self.status_var.set("⚠ 위치 코드를 입력하세요 (PDA 스캔)")
            return

        reason = self.reason_var.get()
        if reason == '직접 입력':
            reason = self.reason_custom.get().strip() or '반품'

        if not _ENGINE_AVAILABLE:
            self.status_var.set("⚠ ReturnReinboundEngine 로드 실패")
            return

        try:
            engine = ReturnReinboundEngine(self.db_conn)
            result = engine.process(
                outbound_id=self.outbound_id,
                lot_no=self.lot_no,
                new_location=new_location,
                reason=reason,
            )

            if result.ok:
                self.result = result
                self.popup.destroy()
                if self.on_success:
                    self.on_success(result.return_id, new_location)
                if CustomMessageBox:
                    CustomMessageBox.show_info(
                        self.parent,
                        title="반품 처리 완료",
                        message=(
                            f"반품 처리 완료\n\n"
                            f"반품 ID: {result.return_id}\n"
                            f"LOT: {self.lot_no}\n"
                            f"새 위치: {new_location}\n"
                            f"톤백 복구: {result.tonbags_restored}개\n"
                            f"중량 복구: {result.weight_restored:,.1f}kg"
                        ),
                    )
            else:
                self.status_var.set(f"⚠ {result.error}")

        except Exception as e:
            self.status_var.set(f"⚠ 처리 오류: {e}")
            logger.exception("ReturnReinboundDialog 처리 오류")
