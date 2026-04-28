"""
SQM v4.1.0 — LOT 상세 추적 다이얼로그 (품목별 상세)
===================================================

LOT 더블클릭/우클릭 시:
1. LOT 기본 정보 (제품, 입고일, 잔량 등)
2. 톤백 현황 (판매가능/출고/샘플 구분, 중량 합계)
3. 재고 이동 이력 (INBOUND/OUTBOUND/RETURN 타임라인)
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
from engine_modules.constants import STATUS_AVAILABLE, STATUS_PICKED, STATUS_RESERVED, STATUS_SOLD
import logging

from ..utils.ui_constants import (
    CustomMessageBox,
    apply_tooltip,
    get_status_display,
    setup_dialog_geometry_persistence,
)

logger = logging.getLogger(__name__)



# v9.0: Treeview 테마 헬퍼
def _apply_tv_theme(tree, parent=None, **kw):
    try:
        from gui_app_modular.utils.ui_constants import apply_treeview_theme
        apply_treeview_theme(tree, parent=parent)
    except Exception:
        logger.debug("[SUPPRESSED] exception in lot_detail_dialog.py")  # noqa

class LotDetailDialogMixin:
    """LOT 상세 다이얼로그 Mixin — SQMInventoryApp에 mix-in"""

    def _show_lot_detail_popup(self, lot_no: str, source_tab: str = None) -> None:
        """v4.1.0 / v7.0: LOT 상세 추적 팝업. source_tab: inventory|allocation|picked|sold 에 따라 톤백 소스 변경."""
        from ..utils.constants import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y, tk, ttk
        from ..utils.ui_constants import ThemeColors

        # ── LOT 정보 조회 (inventory에 없어도 톤백만 보여줄 수 있음) ──
        lot_info = self.engine.db.fetchone(
            "SELECT * FROM inventory WHERE lot_no = ?", (lot_no,))
        if not lot_info:
            lot_info = {'lot_no': lot_no, 'product': '-', 'status': '-', 'initial_weight': 0, 'current_weight': 0,
                        'sap_no': '', 'bl_no': '', 'container_no': '', 'ship_date': '', 'arrival_date': '', 'warehouse': ''}

        # ── 톤백 조회 (v7.0: source_tab에 따라 테이블 선택) ──
        source = (source_tab or '').lower()
        if source == 'allocation':
            rows = self.engine.db.fetchall(
                "SELECT sub_lt, qty_mt, customer, outbound_date, created_at FROM allocation_plan WHERE lot_no = ? AND status = 'RESERVED' ORDER BY sub_lt",
                (lot_no,))
            tonbags = [{'sub_lt': r.get('sub_lt'), 'weight': float(r.get('qty_mt') or 0) * 1000, 'status': STATUS_RESERVED,
                        'location': '', 'picked_date': (r.get('created_at') or '')[:10], 'picked_to': str(r.get('customer') or ''),
                        'outbound_date': (r.get('outbound_date') or '')[:10], 'is_sample': 0, 'remarks': ''} for r in (rows or [])]
        elif source == 'picked':
            rows = self.engine.db.fetchall(
                "SELECT sub_lt, qty_kg, customer, picking_date FROM picking_table WHERE lot_no = ? AND status = 'ACTIVE' ORDER BY sub_lt",
                (lot_no,))
            tonbags = [{'sub_lt': r.get('sub_lt'), 'weight': float(r.get('qty_kg') or 0), 'status': STATUS_PICKED,
                        'location': '', 'picked_date': (r.get('picking_date') or '')[:10], 'picked_to': str(r.get('customer') or ''),
                        'outbound_date': '', 'is_sample': 0, 'remarks': ''} for r in (rows or [])]
        elif source == 'sold':
            rows = self.engine.db.fetchall(
                "SELECT sub_lt, sold_qty_kg, customer, sold_date FROM sold_table WHERE lot_no = ? AND status = 'SOLD' ORDER BY sub_lt",
                (lot_no,))
            tonbags = [{'sub_lt': r.get('sub_lt'), 'weight': float(r.get('sold_qty_kg') or 0), 'status': STATUS_SOLD,
                        'location': '', 'picked_date': '', 'picked_to': str(r.get('customer') or ''),
                        'outbound_date': (r.get('sold_date') or '')[:10], 'is_sample': 0, 'remarks': ''} for r in (rows or [])]
        else:
            tonbags = self.engine.db.fetchall("""
                SELECT sub_lt, weight, status, location, picked_date,
                       picked_to, outbound_date, is_sample, remarks
                FROM inventory_tonbag
                WHERE lot_no = ?
                ORDER BY is_sample DESC, sub_lt
            """, (lot_no,)) or []

        # ── 이력 조회 (base 스키마: movement_type, qty_kg, remarks, created_at)
        movements = self.engine.db.fetchall("""
            SELECT movement_type, created_at AS movement_date, qty_kg,
                   NULL AS before_weight, NULL AS after_weight, NULL AS reference_no, remarks
            FROM stock_movement
            WHERE lot_no = ?
            ORDER BY created_at DESC
        """, (lot_no,))

        # ── 테마 (v5.8.7 Phase2: ThemeColors 단일 소스) ──
        dark_mode = is_dark()
        bg = ThemeColors.get('bg_card', is_dark)
        fg = ThemeColors.get('text_primary', is_dark)
        header_bg = ThemeColors.get('statusbar_bg', is_dark) if is_dark else ThemeColors.get('text_primary', is_dark)
        card_bg = ThemeColors.get('bg_secondary', is_dark)

        popup = create_themed_toplevel(self.root)
        popup.title(f"LOT 상세 추적 - {lot_no}")
        popup.transient(self.root)
        popup.grab_set()
        setup_dialog_geometry_persistence(popup, "lot_detail_dialog", self.root, "large")
        popup.configure(bg=bg)

        # ═══════════════════════════════════════════
        # 1. 상단 헤더 — LOT 기본 정보
        # ═══════════════════════════════════════════
        header = tk.Frame(popup, bg=header_bg, padx=15, pady=12)
        header.pack(fill=X)

        product = lot_info.get('product', '-') or '-'
        status = lot_info.get('status', '-') or '-'
        init_w = lot_info.get('initial_weight', 0) or 0
        curr_w = lot_info.get('current_weight', 0) or 0
        out_w = init_w - curr_w

        status_icons = {
            'AVAILABLE': '✅', 'PICKED': '📤', 'CONFIRMED': '✔️',
            'SHIPPED': '🚢', 'DEPLETED': '❌', 'RESERVED': '🔒'
        }
        s_icon = status_icons.get(status, '❓')

        # v5.6.9: LOT 상세 팝업 스타일 통일 (폰트/정렬)
        FONT_TITLE = ('맑은 고딕', 16, 'bold')
        FONT_SUBTITLE = ('맑은 고딕', 12)
        FONT_LABEL = ('맑은 고딕', 10)
        FONT_VALUE = ('맑은 고딕', 11, 'bold')
        FONT_WEIGHT = ('맑은 고딕', 11, 'bold')

        tk.Label(header, text=f"📦 {lot_no}", font=FONT_TITLE,
                 bg=header_bg, fg=fg).pack(side=LEFT)
        status_disp = get_status_display(status) or status
        tk.Label(header, text=f"  |  {product}  |  {s_icon} {status_disp}",
                 font=FONT_SUBTITLE, bg=header_bg, fg=fg).pack(side=LEFT, padx=10)

        # ── 정보 카드 행 (v5.6.9: 정렬/간격 통일) ──
        info_bar = tk.Frame(popup, bg=card_bg, padx=12, pady=10)
        info_bar.pack(fill=X, padx=10, pady=(5, 0))

        info_items = [
            ('SAP NO', lot_info.get('sap_no', '-') or '-'),
            ('B/L NO', lot_info.get('bl_no', '-') or '-'),
            ('CONTAINER', lot_info.get('container_no', '-') or '-'),
            ('SHIP DATE', lot_info.get('ship_date', '-') or '-'),
            ('ARRIVAL', lot_info.get('arrival_date', '-') or '-'),
            ('창고', lot_info.get('warehouse', '-') or '-'),
        ]
        _label_fg = fg if is_dark else ThemeColors.get('text_secondary')
        for c, (label, value) in enumerate(info_items):
            f = tk.Frame(info_bar, bg=card_bg)
            f.grid(row=0, column=c, padx=(0, 20), sticky='w')
            tk.Label(f, text=label, font=FONT_LABEL, bg=card_bg, fg=_label_fg).pack(anchor='w')
            tk.Label(f, text=str(value), font=FONT_VALUE, bg=card_bg, fg=fg).pack(anchor='w')

        # ── 중량 카드 ──
        weight_bar = tk.Frame(popup, bg=card_bg, padx=12, pady=10)
        weight_bar.pack(fill=X, padx=10, pady=(3, 5))

        pct = (out_w / init_w * 100) if init_w > 0 else 0
        weight_items = [
            ('📥 입고', f'{init_w:,.0f} kg', ThemeColors.get('statusbar_progress')),
            ('💰 잔량', f'{curr_w:,.0f} kg', ThemeColors.get('badge_db')),
            ('📤 출고', f'{out_w:,.0f} kg', ThemeColors.get('statusbar_icon_warn', is_dark)),
            ('📊 출고율', f'{pct:.1f}%', ThemeColors.get('statusbar_icon_err') if pct > 80 else ThemeColors.get('statusbar_icon_warn')),
        ]
        for label, value, color in weight_items:
            f = tk.Frame(weight_bar, bg=card_bg)
            f.pack(side=LEFT, padx=(0, 28))
            tk.Label(f, text=label, font=FONT_LABEL, bg=card_bg, fg=_label_fg).pack(anchor='w')
            tk.Label(f, text=value, font=FONT_WEIGHT, bg=card_bg, fg=fg if is_dark else color).pack(anchor='w')

        # ═══════════════════════════════════════════
        # 2. 중단 — Notebook (톤백 + 이력)
        # ═══════════════════════════════════════════
        nb = ttk.Notebook(popup)
        nb.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # ── TAB 1: 톤백 현황 ──
        tab_tonbag = ttk.Frame(nb)
        nb.add(tab_tonbag, text=f"  📦 톤백 현황 ({len(tonbags)}개)  ")

        tb_cols = ('no', 'sub_lt', 'weight', 'status', 'type', 'location',
                   'picked_to', 'picked_date', 'outbound_date')
        tb_tree = ttk.Treeview(tab_tonbag, columns=tb_cols, show='headings', height=12)

        # v5.6.9: 톤백 테이블 컬럼 너비/정렬 통일
        for cid, txt, w, anchor in [
            ('no', 'No.', 45, 'center'), ('sub_lt', '톤백#', 65, 'center'),
            ('weight', '중량(kg)', 95, 'e'), ('status', '상태', 85, 'center'),
            ('type', '구분', 70, 'center'), ('location', '위치', 85, 'center'),
            ('picked_to', '출고처', 110, 'w'), ('picked_date', '출고지정일', 95, 'center'),
            ('outbound_date', '출고완료일', 95, 'center'),
        ]:
            tb_tree.heading(cid, text=txt, anchor='center')
            tb_tree.column(cid, width=w, anchor=anchor)

        sb_tb = tk.Scrollbar(tab_tonbag, orient=VERTICAL, command=tb_tree.yview)
        sb_tb_x = tk.Scrollbar(tab_tonbag, orient='horizontal', command=tb_tree.xview)
        tb_tree.configure(yscrollcommand=sb_tb.set, xscrollcommand=sb_tb_x.set)
        tb_tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb_tb.pack(side=RIGHT, fill=Y)
        sb_tb_x.pack(side='bottom', fill='x')

        avail_cnt = 0
        picked_cnt = 0
        sample_cnt = 0
        avail_kg = 0.0
        picked_kg = 0.0

        for idx, tb in enumerate(tonbags, 1):
            sub_lt = tb['sub_lt'] if isinstance(tb, dict) else tb[0]
            weight = (tb['weight'] if isinstance(tb, dict) else tb[1]) or 0
            st = (tb['status'] if isinstance(tb, dict) else tb[2]) or ''
            loc = (tb['location'] if isinstance(tb, dict) else tb[3]) or ''
            p_date = (tb['picked_date'] if isinstance(tb, dict) else tb[4]) or ''
            p_to = (tb['picked_to'] if isinstance(tb, dict) else tb[5]) or ''
            o_date = (tb['outbound_date'] if isinstance(tb, dict) else tb[6]) or ''
            is_sample = (tb['is_sample'] if isinstance(tb, dict) else tb[7]) or 0

            tb_type = '🧪 샘플' if is_sample else '📦 정규'
            if is_sample:
                sample_cnt += 1
            elif st == STATUS_AVAILABLE:
                avail_cnt += 1
                avail_kg += weight
            elif st in ('PICKED', 'SOLD', 'SHIPPED'):
                picked_cnt += 1
                picked_kg += weight

            tag = 'available' if st == STATUS_AVAILABLE else ('picked' if st in ('PICKED','SOLD') else
                   ('shipped' if st == 'SHIPPED' else 'depleted'))
            if is_sample:
                tag = 'sample'

            tb_no_disp = '0' if (is_sample or sub_lt == 0) else sub_lt
            st_disp = get_status_display(st) or st
            tb_tree.insert('', END, values=(
                idx, tb_no_disp, f'{weight:,.1f}', st_disp, tb_type, loc, p_to, p_date, o_date
            ), tags=(tag,))

        _apply_tv_theme(tb_tree, parent=None)  # v9.0
        tb_tree.tag_configure('available', background=ThemeColors.get('available', is_dark), foreground=fg)
        tb_tree.tag_configure('picked', background=ThemeColors.get('picked', is_dark), foreground=fg)
        tb_tree.tag_configure('shipped', background=ThemeColors.get('shipped', is_dark), foreground=fg)
        tb_tree.tag_configure('depleted',
            background='#e8e8e8' if not is_dark else '#1a1a2e',
            foreground='#666666' if not is_dark else '#9a9ab0')
        tb_tree.tag_configure('sample', background=ThemeColors.get('available', is_dark), foreground=fg)

        # 톤백 요약 바
        tb_summary = tk.Frame(tab_tonbag, bg=card_bg, pady=5)
        tb_summary.pack(fill=X, side='bottom')
        tk.Label(tb_summary,
            text=f"✅ 판매가능: {avail_cnt}개 ({avail_kg:,.0f}kg)  |  "
                 f"📤 출고: {picked_cnt}개 ({picked_kg:,.0f}kg)  |  "
                 f"🧪 샘플: {sample_cnt}개  |  총: {len(tonbags)}개",
            font=('맑은 고딕', 11), bg=card_bg, fg=fg).pack(padx=10)

        # ── TAB 2: 재고 이동 이력 ──
        tab_history = ttk.Frame(nb)
        nb.add(tab_history, text=f"  📋 이동 이력 ({len(movements)}건)  ")

        mv_cols = ('no', 'type', 'date', 'qty_kg', 'before', 'after', 'ref', 'remarks')
        mv_tree = ttk.Treeview(tab_history, columns=mv_cols, show='headings', height=12)

        for cid, txt, w, anchor in [
            ('no', 'No.', 40, 'center'), ('type', '유형', 100, 'center'),
            ('date', '일시', 150, 'center'), ('qty_kg', '수량(kg)', 100, 'e'),
            ('before', '이전잔량', 100, 'e'), ('after', '이후잔량', 100, 'e'),
            ('ref', '참조번호', 120, 'w'), ('remarks', '비고', 150, 'w'),
        ]:
            mv_tree.heading(cid, text=txt, anchor='center')
            mv_tree.column(cid, width=w, anchor=anchor)

        sb_mv = tk.Scrollbar(tab_history, orient=VERTICAL, command=mv_tree.yview)
        sb_mv_x = tk.Scrollbar(tab_history, orient='horizontal', command=mv_tree.xview)
        mv_tree.configure(yscrollcommand=sb_mv.set, xscrollcommand=sb_mv_x.set)
        mv_tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb_mv.pack(side=RIGHT, fill=Y)
        sb_mv_x.pack(side='bottom', fill='x')

        type_icons = {
            'INBOUND': '📥 입고', 'OUTBOUND': '📤 출고',
            'RETURN': '🔄 반품', 'ADJUST': '⚙️ 조정'
        }

        for idx, mv in enumerate(movements, 1):
            mt = (mv['movement_type'] if isinstance(mv, dict) else mv[0]) or ''
            md = (mv['movement_date'] if isinstance(mv, dict) else mv[1]) or ''
            qty = (mv['qty_kg'] if isinstance(mv, dict) else mv[2]) or 0
            bw = (mv['before_weight'] if isinstance(mv, dict) else mv[3]) or 0
            aw = (mv['after_weight'] if isinstance(mv, dict) else mv[4]) or 0
            ref = (mv['reference_no'] if isinstance(mv, dict) else mv[5]) or ''
            rem = (mv['remarks'] if isinstance(mv, dict) else mv[6]) or ''

            tag = 'inbound' if 'INBOUND' in mt.upper() else (
                  'outbound' if 'OUTBOUND' in mt.upper() else (
                  'return_mv' if 'RETURN' in mt.upper() else ''))

            mv_tree.insert('', END, values=(
                idx, type_icons.get(mt.upper(), mt), str(md)[:19],
                f'{qty:,.1f}', f'{bw:,.0f}', f'{aw:,.0f}', ref, rem
            ), tags=(tag,))

        _apply_tv_theme(mv_tree, parent=None)  # v9.0
        mv_tree.tag_configure('inbound', background=ThemeColors.get('available', is_dark), foreground=fg)
        mv_tree.tag_configure('outbound', background=ThemeColors.get('picked', is_dark), foreground=fg)
        mv_tree.tag_configure('return_mv', background=ThemeColors.get('available', is_dark), foreground=fg)

        if not movements:
            mv_tree.insert('', END, values=('', '이력 없음', '', '', '', '', '', ''))

        # ── TAB 3: allocation_plan 이력 + 톤백 상태 요약 (도구 메뉴와 동일 정보) ──
        tab_alloc = ttk.Frame(nb)
        nb.add(tab_alloc, text="  📊 Allocation·배정  ")
        if hasattr(self, "_attach_lot_allocation_audit_tab"):
            self._attach_lot_allocation_audit_tab(tab_alloc, lot_no)
        else:
            ttk.Label(
                tab_alloc,
                text="Allocation·배정 패널을 불러올 수 없습니다. 앱을 최신 빌드로 갱신하세요.",
            ).pack(padx=12, pady=16)

        # ═══════════════════════════════════════════
        # 3. 하단 버튼
        # ═══════════════════════════════════════════
        btn_bar = tk.Frame(popup, bg=bg, pady=8)
        btn_bar.pack(fill=X, padx=10)

        if avail_cnt > 0:
            _btn_out = ttk.Button(btn_bar, text="📤 빠른 출고",
                                  command=lambda: self._quick_outbound_from_detail(popup, lot_no))
            _btn_out.pack(side=LEFT, padx=5)
            apply_tooltip(_btn_out, "이 LOT의 판매가능 톤백으로 출고 화면을 엽니다. 수량·출고처 입력 후 출고를 완료할 수 있습니다.")
        _btn_pdf = ttk.Button(btn_bar, text="📋 PDF 출력",
                              command=lambda: self._export_lot_detail_pdf(lot_no))
        _btn_pdf.pack(side=LEFT, padx=5)
        apply_tooltip(_btn_pdf, "이 LOT의 상세 정보(기본정보·톤백 목록·이력)를 PDF 파일로 저장합니다.")
        _btn_close = ttk.Button(btn_bar, text="닫기", command=popup.destroy)
        _btn_close.pack(side=RIGHT, padx=5)
        apply_tooltip(_btn_close, "LOT 상세 창을 닫습니다.")

        popup.bind('<Escape>', lambda e: popup.destroy())

    def _quick_outbound_from_detail(self, parent_popup, lot_no: str) -> None:
        """LOT 상세에서 빠른 출고"""
        parent_popup.destroy()
        if hasattr(self, '_show_manual_outbound_dialog'):
            self._show_manual_outbound_dialog(lot_no, 1)

    def _export_lot_detail_pdf(self, lot_no: str = None) -> None:
        """LOT 상세 PDF 출력"""
        if hasattr(self, '_generate_lot_detail_pdf'):
            if lot_no:
                self._generate_lot_detail_pdf(lot_no=lot_no)
            else:
                self._generate_lot_detail_pdf()
        else:
            CustomMessageBox.showinfo(self.root, "안내", "PDF 출력 기능 준비 중")
