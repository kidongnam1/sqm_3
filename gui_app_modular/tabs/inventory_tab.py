# -*- coding: utf-8 -*-
"""
SQM v3.9.1 — 재고 현황 탭 (18열 + 체크박스 열선택)
===================================================
- 18열 전체 표시 (inventory 테이블 매핑)
- ⚙️ 열 선택 체크박스 팝업
- 검색 입력박스 + 상태 필터 유지
- 선택출고/상세보기/선택정보 삭제

★ v5.5.2 UI 기준: 톤백 리스트(tonbag_tab.py)는 이 탭과 동일한 구도로 유지.
  필터/표시 컬럼/버튼/통계 바 순서·스타일을 바꿀 때는 tonbag_tab도 함께 수정할 것.
"""

# ══════════════════════════════════════════════════════════════
# 🎨 색상 사용 원칙 (v3.8.0 — 절대 준수)
# ══════════════════════════════════════════════════════════════
# ✅ 올바른 방법: tc() 함수 사용 (라이트/다크 자동 전환)
#     from gui_app_modular.utils.ui_constants import tc
#     label.config(fg=tc('text_primary'), bg=tc('bg_primary'))
#     entry.config(fg=tc('text_primary'), bg=tc('bg_entry'))
#     frame.config(bg=tc('bg_secondary'))
#
# ❌ 금지: 하드코딩 색상 사용
#     label.config(fg=tc('text_primary'))         # 다크 배경에서 안 보임
#     label.config(fg=tc('text_primary'))         # 라이트 배경에서 안 보임
#     label.config(bg=tc('bg_primary'))       # 라이트 모드에서 검은 배경
#
# 📋 주요 tc() 키:
#     text_primary   — 일반 텍스트 (라이트: #2c3e50  다크: #FF8C00)
#     text_secondary — 보조 텍스트
#     text_muted     — 비활성 텍스트 (gray 대체)
#     bg_primary     — 기본 배경
#     bg_secondary   — 보조 배경
#     bg_card        — 카드/패널 배경
#     bg_entry       — 입력창 배경
#     success        — 성공 (녹색 계열)
#     warning        — 경고 (주황 계열)
#     danger         — 오류 (빨간 계열)
#     info           — 정보 (파란 계열)
# ══════════════════════════════════════════════════════════════

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
from engine_modules.constants import (
    STATUS_AVAILABLE, STATUS_RETURN, STATUS_DEPLETED, STATUS_PICKED,
    STATUS_RESERVED, STATUS_SOLD, STATUS_OUTBOUND,  # v7.2.0
)
import sqlite3
import tkinter as tk
from ..utils.ui_constants import is_dark, ThemeColors, Spacing, apply_modal_window_options, get_status_display, setup_dialog_geometry_persistence
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 19열 정의: (컬럼ID, 표시명, 기본폭, 정렬, 기본표시여부)
# v8.1.4: 실무 리스트 헤더는 Avail~Outbound(Kg)까지 기본 전부 표시 (가로 스크롤)
# 톤백 개수(↓*) 열만 기본 OFF — 메뉴「표시 컬럼」에서 켤 수 있음
# ═══════════════════════════════════════════════════════════════
INVENTORY_COLUMNS = [
    ('row_num',            'No.',            50, 'center', True),
    ('lot_no',             'LOT NO',        132, 'center', True),
    ('sap_no',             'SAP NO',        132, 'center', True),
    ('bl_no',              'BL NO',         152, 'center', True),
    ('product',            'PRODUCT',       180, 'w',      True),
    ('status',             'STATUS',        100, 'center', True),
    ('current_weight',     'Balance(Kg)',   110, 'e',      True),
    ('net_weight',         'NET(Kg)',       110, 'e',      True),
    ('container_no',       'CONTAINER',     142, 'center', True),
    ('mxbg_pallet',        'MXBG',           82, 'center', True),
    ('avail_bags',         'Avail',          72, 'e',      True),
    ('tb_avail',           '↓Avail개',       74, 'e',      False),
    ('tb_reserved',        '↓Resv개',        74, 'e',      False),
    ('tb_picked',          '↓Pick개',        74, 'e',      False),
    ('tb_sold',            '↓Sold개',        74, 'e',      False),
    ('salar_invoice_no',   'INVOICE NO',    120, 'center', True),
    ('ship_date',          'SHIP DATE',     108, 'center', True),
    ('arrival_date',       'ARRIVAL',       108, 'center', True),
    ('con_return',         'CON RETURN',    108, 'center', True),
    ('free_time',          'FREE TIME',      92, 'center', True),
    ('warehouse',          'WH',             92, 'w',      True),
    ('customs',            'CUSTOMS',       102, 'center', True),
    ('initial_weight',     'Inbound(Kg)',   110, 'e',      True),
    ('outbound_weight',    'Outbound(Kg)',  110, 'e',      True),
]


try:
    from ..utils.sort_utils import make_sort_key as _make_sort_key_inv
except ImportError:
    def _make_sort_key_inv(col, numeric_cols):
        def _k(item):
            v = item[0]
            try: return (0, float(v)) if col in numeric_cols else (0, str(v).lower())
            except Exception: return (1, str(v))
        return _k

make_sort_key = _make_sort_key_inv


class InventoryTabMixin:
    """
    재고 현황 탭 Mixin (v3.8.4: 18열)
    """

    def _setup_inventory_tab(self) -> None:
        """재고 현황 탭 설정"""
        from ..utils.constants import ttk, tk, VERTICAL, BOTH, YES, LEFT, RIGHT, X, Y

        # 앱 시작 시 파싱 미리보기 오버레이는 비활성 상태로 시작
        self._parsing_preview_data = None
        # v8.1.5: DB 재고를 기본 표시. 입고 시작 시에만 백지로 전환.
        self._blank_inventory_until_first_parse = False
        self._blank_inventory_notice_shown = False

        _is_dark = is_dark()
        ThemeColors.get('bg_secondary', _is_dark)

        # v7.0: 판매가능 탭 제목 + LOT/톤백 전환 (가독성: 폰트 확대)
        # 탭 헤더 (v7.3.7 심플화)
        try:
            from ..utils.ui_constants import make_tab_header
            _is_dark_hdr = is_dark()
            self._inv_count_var = tk.StringVar(value="")
            make_tab_header(self.tab_inventory, "📦 판매가능 LOT 리스트",
                            status_color='#10b981', count_var=self._inv_count_var,
                            is_dark=_is_dark_hdr)
        except Exception:
            logger.debug("[SUPPRESSED] exception in inventory_tab.py")  # noqa

        # v7.3.7: LOT/톤백 라디오버튼 코드 제거 (v3.8.9에서 비표시 결정, 잔존 코드 정리)
        self._inv_view_switch_var = tk.StringVar(value='recovery')
        self._inv_show_all_tonbags = False

        # 재고 뷰 컨테이너 (필터/토글/버튼/스플릿 패널)
        self._inv_recovery_container = ttk.Frame(self.tab_inventory)
        self._inv_recovery_container.pack(fill=BOTH, expand=YES)

        # 열 표시 상태 딕셔너리
        self._inv_col_visible = {}
        for col_id, _, _, _, default_visible in INVENTORY_COLUMNS:
            self._inv_col_visible[col_id] = default_visible

        # v3.8.4: 검색 바 삭제 → 검색은 메뉴바 [🔍검색] 팝업으로 이동
        # 검색 관련 변수 초기화 (팝업에서 사용)
        self._inv_search_combos = {}
        self._date_from_var = tk.StringVar()
        self._date_to_var = tk.StringVar()
        self.status_var = tk.StringVar(value="전체")
        self.search_var = tk.StringVar()
        # ① v6.8.2: 위치 미배정 드릴다운 필터 플래그
        self._unassigned_loc_filter_var = tk.BooleanVar(value=False)
        self._unassigned_loc_filter_var.trace_add(
            'write', lambda *_: self._apply_unassigned_loc_filter()
        )

        # v3.8.9: LOT/톤백 라디오버튼 삭제 (톤백 상세는 톤백리스트 탭에서 관리)
        self._inv_view_mode = tk.StringVar(value='lot')  # 호환성 유지

        # ═══════════════════════════════════════════════════════
        # 헤더 정렬+필터: 상단 필터 메뉴 제거, 차트 헤더 열마다 정렬(▲▼)+리스트박스
        # ═══════════════════════════════════════════════════════
        from ..utils.tree_enhancements import HeaderSortFilterRow, TreeviewTotalFooter
        
        _is_dark_filter = is_dark()
        inv_filter_cols = [
            ('lot_no',       'LOT NO',     132),
            ('sap_no',       'SAP NO',     132),
            ('bl_no',        'BL NO',      152),
            ('container_no', 'CONTAINER',  142),
            ('product',      'PRODUCT',    172),
            ('status',       'STATUS',      98),
        ]
        # 트리 생성 전에 필터/정렬 바만 생성해 두고, 트리 생성 후 연결·pack
        self._inv_filter_bar = None
        self._inv_header_row = None
        self._inv_header_row_place = ttk.Frame(self._inv_recovery_container)
        self._inv_header_row_place.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))

        # v5.0.2: 컬럼 토글 바 — 판매가능 탭에서는 위 메뉴 제거 요청으로 미표시 (트리만 헤더 정렬+필터)
        try:
            from ..utils.column_toggle import ColumnToggleBar
            toggleable_cols = [(c[0], c[1], c[4]) for c in INVENTORY_COLUMNS]
            self._inv_toggle_bar = ColumnToggleBar(
                self._inv_recovery_container,
                None,
                toggleable_cols,
                is_dark=_is_dark_filter
            )
            # self._inv_toggle_bar.pack(...) — 상단 UI 제거로 비표시
        except (ImportError, Exception) as e:
            logger.debug(f"컬럼 토글바 생성 실패: {e}")
            self._inv_toggle_bar = None

        # v7.3.7: 비표시 버튼 프레임 코드 제거 (메뉴에서 동일 기능 사용 가능)
        self._inv_btn_frame = None

        # ═══════════════════════════════════════════════════════
        # 재고 LOT 리스트 단일 영역 (하단 인라인 톤백 상세 패널 제거 — 더블클릭 팝업 사용)
        # ═══════════════════════════════════════════════════════
        self._inv_list_outer = ttk.Frame(self._inv_recovery_container)
        self._inv_list_outer.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)

        # 트리·스크롤·합계줄 배경을 Treeview와 동일(bg_card)으로 — ttk.Frame 기본색과 이음새 제거
        _is_dark_tv = is_dark()
        _tv_bg = ThemeColors.get('bg_card', _is_dark_tv)
        _tv_fg = ThemeColors.get('text_primary', _is_dark_tv)
        _tv_field = _tv_bg
        _tv_head_bg = _tv_bg
        _tv_head_fg = ThemeColors.get('text_primary', _is_dark_tv)

        tree_frame = tk.Frame(
            self._inv_list_outer,
            bg=_tv_bg,
            highlightthickness=0,
        )
        tree_frame.pack(fill=BOTH, expand=YES)
        self._inv_tree_frame = tree_frame

        # 모든 18열로 생성
        all_col_ids = [c[0] for c in INVENTORY_COLUMNS]
        
        # v3.8.9: 트리뷰 스타일 — 테마 인식 (글자 흐림 수정) | v5.7.5: 가독성 위해 폰트 14로 확대
        import tkinter.font as tkfont
        _style = ttk.Style()
        _inv_font = tkfont.Font(family='맑은 고딕', size=11)
        _inv_head_font = tkfont.Font(family='맑은 고딕', size=11, weight='bold')
        _row_h = _inv_font.metrics('linespace') + 10
        
        _style.configure('Inv.Treeview', 
                         font=_inv_font,
                         rowheight=_row_h,
                         background=_tv_bg,
                         foreground=_tv_fg,
                         fieldbackground=_tv_field)
        # v8.1.4: 헤더 셀 사이 세로 테두리 제거(업로드 2 참고 — flat 헤더)
        _style.configure(
            'Inv.Treeview.Heading',
            font=_inv_head_font,
            background=_tv_head_bg,
            foreground=_tv_head_fg,
            relief='flat',
            borderwidth=0,
            anchor='center',
        )
        
        # v6.1.1: 선택/비선택 행 foreground 명시 (테마 가시성)
        _style.map('Inv.Treeview',
                   background=[('selected', ThemeColors.get('tree_select_bg', _is_dark_tv))],
                   foreground=[
                       ('selected', ThemeColors.get('tree_select_fg', _is_dark_tv)),
                       ('!selected', _tv_fg),
                   ])
        
        self.tree_inventory = ttk.Treeview(
            tree_frame, columns=all_col_ids, show="headings", height=20,
            selectmode='extended', style='Inv.Treeview'
        )

        self._sort_column = None
        self._sort_reverse = False

        # 헤더 + 컬럼 설정
        for col_id, label, width, anchor, visible in INVENTORY_COLUMNS:
            self.tree_inventory.heading(
                col_id, text=label, anchor='center',
                command=lambda c=col_id: self._sort_treeview(self.tree_inventory, c)
            )
            if visible:
                self.tree_inventory.column(col_id, width=width, anchor=anchor, stretch=True)
            else:
                self.tree_inventory.column(col_id, width=0, minwidth=0, stretch=False)
        
        # v8.1.4: Grid.* 스타일 미사용 — 열 사이 세로선(헤더/본문) 제거, Inv.Treeview 유지
        try:
            from ..utils.tree_enhancements import apply_striped_rows
            apply_striped_rows(self.tree_inventory, is_dark=_is_dark_tv)
        except (ImportError, Exception) as e:
            logger.debug(f"재고 트리 줄무늬 초기화 실패: {e}")

        # 스크롤바 — 트랙 색을 카드/보조 배경에 맞춰 이음새 완화
        _sb_trough = ThemeColors.get('bg_secondary', _is_dark_tv)
        v_scroll = tk.Scrollbar(
            tree_frame, orient=VERTICAL, command=self.tree_inventory.yview,
            bg=_tv_bg, troughcolor=_sb_trough, activebackground=_tv_head_bg,
            highlightthickness=0, bd=0,
        )
        h_scroll = tk.Scrollbar(
            tree_frame, orient='horizontal', command=self.tree_inventory.xview,
            bg=_tv_bg, troughcolor=_sb_trough, activebackground=_tv_head_bg,
            highlightthickness=0, bd=0,
        )
        self.tree_inventory.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree_inventory.pack(side=LEFT, fill=BOTH, expand=YES)
        v_scroll.pack(side=RIGHT, fill=Y)
        h_scroll.pack(side='bottom', fill=X)

        # 하단 총합 (합계 가능한 숫자 컬럼만)
        inv_sum_cols = ['current_weight', 'net_weight', 'initial_weight', 'outbound_weight', 'mxbg_pallet']
        self._inv_total_footer = TreeviewTotalFooter(
            tree_frame, self.tree_inventory, inv_sum_cols,
            column_display_names={'current_weight': 'Balance(Kg)', 'net_weight': 'NET(Kg)',
                                 'initial_weight': 'Inbound(Kg)', 'outbound_weight': 'Outbound(Kg)', 'mxbg_pallet': 'MXBG'}
        )
        self._inv_total_footer.pack(fill=X, pady=(2, 0))

        # v5.7.5: 하단 요약바 제거 (LOT/톤백/입고/잔량/출고/가용/소진/출고율)

        # 테마 색상
        self._apply_inventory_theme_colors()

        # 헤더 열 정렬+리스트박스 (상단 필터 메뉴 대체)
        inv_filter_cols = [
            ('lot_no', 'LOT NO', 132), ('sap_no', 'SAP NO', 132), ('bl_no', 'BL NO', 152),
            ('container_no', 'CONTAINER', 142), ('product', 'PRODUCT', 172), ('status', 'STATUS', 98),
        ]
        def _on_inv_header_sort(col_id):
            self._sort_treeview(self.tree_inventory, col_id)
            if getattr(self, '_inv_header_row', None):
                self._inv_header_row.set_sort(col_id, self._sort_reverse)

        self._inv_header_row = HeaderSortFilterRow(
            self._inv_header_row_place,
            self.tree_inventory,
            inv_filter_cols,
            on_filter=self._on_inv_filter_apply,
            on_sort=_on_inv_header_sort,
            is_dark=_is_dark_tv,
            date_from_var=self._date_from_var,
            date_to_var=self._date_to_var,
            container_suffix_var=getattr(self, '_container_suffix_var', None),
            on_container_suffix_toggle=getattr(self, '_on_container_suffix_toggle', None),
            show_opt_row=True,
            opt_row_side="right",
        )
        self._inv_header_row.pack(fill=X)
        self._inv_filter_bar = self._inv_header_row

        # v5.0.2: 컬럼 토글바에 treeview 연결 (v8.7.0: 초기 displaycolumns 적용)
        if hasattr(self, '_inv_toggle_bar') and self._inv_toggle_bar:
            self._inv_toggle_bar.tree = self.tree_inventory
            self._apply_column_visibility()

        # v4.0.6: 하단 NET(KG) / Balance 합계 바
        # v5.6.1: FooterTotalBar 제거 — stats_frame 1줄로 통합
        # self._inv_footer = FooterTotalBar(self.tab_inventory, is_dark=_is_dark_filter)
        # self._inv_footer.pack(fill=X, padx=5, pady=(0, 2))

        # 이벤트
        # v7.9.9 [Q2]: 더블클릭 → _on_inv_double_click 팝업으로 통일 (기존 _on_lot_double_click 대체)
        self.tree_inventory.bind('<Double-1>', self._on_inv_double_click)  # v7.9.9 [Q2]: 더블클릭 팝업
        # U5: 우클릭 컨텍스트 메뉴
        self.tree_inventory.bind('<Button-3>', self._on_inventory_right_click)

        # 톤백 보기 뷰 (재고리스트 탭 안 메뉴) — 초기에는 숨김
        self._inv_tonbag_container = ttk.Frame(self.tab_inventory)
        tb_bar = ttk.Frame(self._inv_tonbag_container)
        tb_bar.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        ttk.Button(tb_bar, text="← LOT 리스트로", command=self._on_back_to_lot_list).pack(side=LEFT, padx=Spacing.XS)
        ttk.Button(tb_bar, text="🔄 새로고침", command=self._refresh_inv_tonbag_view).pack(side=LEFT, padx=Spacing.XS)
        tb_tree_frame = ttk.Frame(self._inv_tonbag_container)
        tb_tree_frame.pack(fill=BOTH, expand=YES)
        _tb_cols = ('row_num', 'lot_no', 'tonbag_no', 'status', 'weight', 'uid', 'location')
        self._inv_tonbag_tree = ttk.Treeview(tb_tree_frame, columns=_tb_cols, show='headings', height=Spacing.Tab.TREE_MIN_H, selectmode='extended')
        for cid, txt, w in [
            ('row_num', 'No.', 50), ('lot_no', 'LOT NO', 120), ('tonbag_no', 'TONBAG NO', 90),
            ('status', 'STATUS', 90), ('weight', 'Balance(Kg)', 100), ('uid', 'UID', 120), ('location', 'LOCATION', 100),
        ]:
            self._inv_tonbag_tree.heading(cid, text=txt, anchor='center')
            self._inv_tonbag_tree.column(cid, width=w)
        _sb = tk.Scrollbar(tb_tree_frame, orient=VERTICAL, command=self._inv_tonbag_tree.yview)
        _sb2 = tk.Scrollbar(tb_tree_frame, orient='horizontal', command=self._inv_tonbag_tree.xview)
        self._inv_tonbag_tree.configure(yscrollcommand=_sb.set, xscrollcommand=_sb2.set)
        self._inv_tonbag_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        _sb.pack(side='right', fill='y')
        _sb2.pack(side='bottom', fill=X)
        self._inv_tonbag_footer = TreeviewTotalFooter(
            tb_tree_frame, self._inv_tonbag_tree, ['weight'],
            column_display_names={'weight': 'Balance(Kg)'}
        )
        self._inv_tonbag_footer.pack(fill=X, pady=(2, 0))

    def _on_inv_view_switch(self) -> None:
        """재고 보기 / 톤백 보기 전환"""
        mode = getattr(self, '_inv_view_switch_var', None) and self._inv_view_switch_var.get() or 'recovery'
        if mode == 'tonbag':
            self._inv_show_all_tonbags = False
            self._inv_recovery_container.pack_forget()
            self._inv_tonbag_container.pack(fill=tk.BOTH, expand=True, padx=Spacing.XS, pady=Spacing.XS)
            self._refresh_inv_tonbag_view()
        else:
            self._inv_tonbag_container.pack_forget()
            self._inv_recovery_container.pack(fill=tk.BOTH, expand=True)

    def _on_show_all_tonbags(self) -> None:
        """v7.0 2단계: [전체 톤백 펼치기] — 판매가능 톤백 전체 표시, LOT 리스트 숨김"""
        self._inv_show_all_tonbags = True
        self._inv_recovery_container.pack_forget()
        self._inv_tonbag_container.pack(fill=tk.BOTH, expand=True, padx=Spacing.XS, pady=Spacing.XS)
        self._refresh_inv_tonbag_view()

    def _on_back_to_lot_list(self) -> None:
        """v7.0 2단계: [← LOT 리스트로] — 톤백 전체 뷰에서 LOT 리스트로 복귀"""
        self._inv_show_all_tonbags = False
        self._inv_tonbag_container.pack_forget()
        self._inv_recovery_container.pack(fill=tk.BOTH, expand=True)
        self._safe_refresh()
    def _refresh_inv_tonbag_view(self) -> None:
        """재고리스트 탭 내 톤백 보기 트리 새로고침. v7.0: [전체 톤백 펼치기] 시 판매가능 전부 조회."""
        if not hasattr(self, '_inv_tonbag_tree'):
            return
        self._inv_tonbag_tree.delete(*self._inv_tonbag_tree.get_children())
        try:
            if getattr(self, '_inv_show_all_tonbags', False):
                # v7.0 2단계: 전체 톤백 펼치기 — inventory_tonbag WHERE status='AVAILABLE' (샘플 제외)
                rows = self.engine.db.fetchall(
                    """SELECT lot_no, sub_lt, tonbag_no, weight, location, inbound_date, bl_no
                       FROM inventory_tonbag WHERE status = 'AVAILABLE' AND COALESCE(is_sample, 0) = 0
                       ORDER BY lot_no, sub_lt"""
                ) if hasattr(self.engine, 'db') and self.engine.db else []
                for idx, tb in enumerate(rows or [], 1):
                    lot_no = str(tb.get('lot_no', ''))
                    sub_lt = tb.get('sub_lt', '')
                    tonbag_no = tb.get('tonbag_no') or (f"{sub_lt:>3}" if sub_lt != '' else '-')
                    w = float(tb.get('weight', 0) or 0)
                    loc = str(tb.get('location', '') or '')
                    inbound = str(tb.get('inbound_date', '') or '')
                    bl = str(tb.get('bl_no', '') or '')
                    st = inbound or '-'
                    uid = bl
                    self._inv_tonbag_tree.insert('', 'end', values=(idx, lot_no, tonbag_no, st, f"{w:,.0f}", uid, loc))
            else:
                tonbags = self.engine.get_tonbags_with_inventory() if hasattr(self.engine, 'get_tonbags_with_inventory') else []
                if not tonbags and hasattr(self.engine, 'get_tonbags'):
                    tonbags = self.engine.get_tonbags() or []
                for idx, tb in enumerate(tonbags, 1):
                    lot_no = str(tb.get('lot_no', ''))
                    sub_lt = tb.get('sub_lt', '')
                    tonbag_no = tb.get('tonbag_no') or (f"{sub_lt:>3}" if sub_lt != '' else '-')
                    _s = tb.get('tonbag_status') or tb.get('status', STATUS_AVAILABLE)
                    # 판매가능 탭의 톤백 리스트는 AVAILABLE만 표시 (샘플 제외)
                    if _s != STATUS_AVAILABLE:
                        continue
                    if tb.get('is_sample', 0):
                        continue
                    _disp = get_status_display(_s) or _s
                    st = ('✅ ' if _s == STATUS_AVAILABLE else ('🔒 ' if _s == STATUS_RESERVED else '')) + _disp
                    w = float(tb.get('weight', tb.get('current_weight', 0)) or 0)
                    uid = str(tb.get('tonbag_uid', ''))
                    loc = str(tb.get('location', ''))
                    self._inv_tonbag_tree.insert('', 'end', values=(idx, lot_no, tonbag_no, st, f"{w:,.0f}", uid, loc))
            if hasattr(self, '_inv_tonbag_footer') and self._inv_tonbag_footer:
                self._inv_tonbag_footer.update_totals()
        except Exception as e:
            logger.debug(f"톤백 보기 새로고침: {e}")

    def _on_inv_double_click(self, event) -> None:
        """v7.9.9 [Q2]: LOT 더블클릭 → 톤백 상세 팝업"""
        import tkinter as _tk
        from tkinter import ttk as _ttk

        sel = self.tree_inventory.selection()
        if not sel:
            return
        item = self.tree_inventory.item(sel[0])
        vals = item.get('values', [])
        if len(vals) < 2:
            return
        lot_no = str(vals[1]).strip()
        if not lot_no:
            return

        # ── 팝업 창 생성 ──
        popup = create_themed_toplevel(self.root if hasattr(self, 'root') else None)
        popup.title(f"🎒 톤백 상세 — {lot_no}")
        popup.geometry("900x550")
        popup.resizable(True, True)

        # 제목
        title_frame = _ttk.Frame(popup)
        title_frame.pack(fill='x', padx=Spacing.Tab.OUTER_PADX, pady=(Spacing.SM, Spacing.XS))
        _ttk.Label(
            title_frame, text=f"📦 LOT: {lot_no}",
            font=('맑은 고딕', 12, 'bold')
        ).pack(side='left')
        _ttk.Button(
            title_frame, text="✖ 닫기", width=8,
            command=popup.destroy
        ).pack(side='right')

        # 요약 정보 (LOT 기본 정보)
        try:
            lot_info = self.engine.db.fetchone(
                "SELECT product, status, current_weight, net_weight, "
                "bl_no, container_no, arrival_date FROM inventory WHERE lot_no=?",
                (lot_no,)
            )
            if lot_info:
                info_frame = _ttk.LabelFrame(popup, text="LOT 정보", padding=6)
                info_frame.pack(fill='x', padx=Spacing.Tab.OUTER_PADX, pady=(0, Spacing.XS))
                fields = [
                    ("제품", lot_info.get('product', '')),
                    ("상태", lot_info.get('status', '')),
                    ("현재고(kg)", f"{lot_info.get('current_weight', 0):,.0f}"),
                    ("순중량(kg)", f"{lot_info.get('net_weight', 0):,.0f}"),
                    ("B/L No.", lot_info.get('bl_no', '')),
                    ("컨테이너", lot_info.get('container_no', '')),
                    ("입항일", str(lot_info.get('arrival_date', '') or '')[:10]),
                ]
                for i, (lbl, val) in enumerate(fields):
                    r, c = divmod(i, 3)
                    _ttk.Label(info_frame, text=f"{lbl}:", font=('맑은 고딕', 10, 'bold')).grid(
                        row=r, column=c*2, sticky='e', padx=(8,2), pady=2)
                    _ttk.Label(info_frame, text=str(val), font=('맑은 고딕', 10)).grid(
                        row=r, column=c*2+1, sticky='w', padx=(0,12), pady=2)
        except Exception as _e:
            logger.debug(f"[SUPPRESSED] {type(_e).__name__}: {_e}")  # noqa

        # 톤백 테이블
        tb_frame = _ttk.LabelFrame(popup, text="톤백 목록", padding=4)
        tb_frame.pack(fill='both', expand=True, padx=Spacing.Tab.OUTER_PADX, pady=(0, Spacing.SM))

        cols = ('no', 'sub_lt', 'weight', 'status', 'location', 'picked_to', 'outbound_date')
        tree = _ttk.Treeview(tb_frame, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H)
        for cid, txt, w, anchor in [
            ('no',           'No.',      40,  'center'),
            ('sub_lt',       '톤백#',    60,  'center'),
            ('weight',       '중량(kg)', 90,  'e'),
            ('status',       '상태',     110, 'center'),
            ('location',     '위치',     90,  'center'),
            ('picked_to',    '출고처',   130, 'w'),
            ('outbound_date','출고일',   100, 'center'),
        ]:
            tree.heading(cid, text=txt, anchor='center')
            tree.column(cid, width=w, anchor=anchor)

        vsb = _ttk.Scrollbar(tb_frame, orient='vertical',   command=tree.yview)
        hsb = _ttk.Scrollbar(tb_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')

        # 데이터 로드
        try:
            tonbags = self.engine.db.fetchall(
                """SELECT sub_lt, weight, status, location, picked_to, outbound_date
                   FROM inventory_tonbag WHERE lot_no=? ORDER BY sub_lt""",
                (lot_no,)
            )
            total_kg = 0.0
            for idx, tb in enumerate(tonbags or [], 1):
                from engine_modules.constants import (
                    STATUS_AVAILABLE, STATUS_RESERVED, STATUS_PICKED
                )
                _s  = tb.get('status', STATUS_AVAILABLE)
                _kg = float(tb.get('weight') or 0)
                total_kg += _kg
                status_icon = {
                    STATUS_AVAILABLE: '✅ 가용',
                    STATUS_RESERVED:  '🔒 예약',
                    STATUS_PICKED:    '🚛 피킹',
                }.get(_s, _s)
                tree.insert('', 'end', values=(
                    idx,
                    tb.get('sub_lt'),
                    f"{_kg:,.0f}",
                    status_icon,
                    tb.get('location') or '-',
                    tb.get('picked_to') or '-',
                    str(tb.get('outbound_date') or '')[:10] or '-',
                ))

            # 합계 행
            cnt = len(tonbags or [])
            _ttk.Label(
                tb_frame,
                text=f"  총 {cnt}개 톤백  |  합계 {total_kg:,.0f} kg",
                font=('맑은 고딕', 10, 'bold')
            ).pack(side='bottom', anchor='w', pady=2)

        except Exception as _e:
            _ttk.Label(tb_frame, text=f"데이터 로드 오류: {_e}").pack()

        popup.transient()
        popup.grab_set()
        popup.focus_set()

    # ═══════════════════════════════════════════════════════
    # 열 선택 체크박스 팝업
    # ═══════════════════════════════════════════════════════

    def _apply_column_visibility(self) -> None:
        """
        v5.0.2: 열 표시/숨김 적용 (개선)
        
        width=0으로만 하면 헤더는 보이는 문제가 있어서
        displaycolumns를 사용하여 완전히 숨김
        """
        try:
            # 표시할 컬럼만 추출
            visible_columns = []
            for col_id, label, width, anchor, _ in INVENTORY_COLUMNS:
                if self._inv_col_visible.get(col_id, True):
                    visible_columns.append(col_id)
            
            # displaycolumns 설정으로 컬럼 표시/숨김
            self.tree_inventory.configure(displaycolumns=visible_columns)
            
            # 표시되는 컬럼의 너비 재설정
            for col_id, label, width, anchor, _ in INVENTORY_COLUMNS:
                if col_id in visible_columns:
                    self.tree_inventory.column(col_id, width=width, minwidth=40, stretch=True)
            
            logger.debug(f"✅ 컬럼 표시 적용: {len(visible_columns)}개 표시")
            
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"컬럼 표시/숨김 실패: {e}")

    # ═══════════════════════════════════════════════════════
    # 테마 / 검색 / 필터
    # ═══════════════════════════════════════════════════════


    def _execute_inv_combo_search(self) -> None:
        """콤보 검색 실행"""
        self._refresh_inventory()

    def _reset_inv_combo_search(self) -> None:
        """콤보 검색 초기화"""
        for field, (var, cb) in self._inv_search_combos.items():
            var.set('전체')
        if hasattr(self, '_date_from_var'):
            self._date_from_var.set('')
        if hasattr(self, '_date_to_var'):
            self._date_to_var.set('')
        self._refresh_inventory()

    # ═══════════════════════════════════════════════════════
    # U5: 우클릭 컨텍스트 메뉴
    # ═══════════════════════════════════════════════════════
    
    def _on_inventory_right_click(self, event) -> None:
        """재고리스트 우클릭 컨텍스트 메뉴"""
        import tkinter as tk
        
        item_id = self.tree_inventory.identify_row(event.y)
        if not item_id:
            return
        
        self.tree_inventory.selection_set(item_id)
        values = self.tree_inventory.item(item_id)['values']
        if not values:
            return
        
        lot_no = str(values[0]).strip()
        
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"📋 LOT 복사: {lot_no}", 
                        command=lambda: self._copy_to_clipboard(lot_no))
        menu.add_separator()
        menu.add_command(label="🔍 톤백 상세 보기", 
                        command=lambda: self._show_lot_tonbag_detail(lot_no))
        menu.add_command(label="🚀 즉시 출고 (원스톱)", 
                        command=lambda: self._quick_outbound_from_context(lot_no))
        menu.add_command(label="🔄 반품 (재입고)", 
                        command=lambda: self._return_from_context(lot_no))
        menu.add_separator()
        menu.add_command(label="📊 LOT 이력 조회", 
                        command=lambda: self._show_lot_history(lot_no))
        menu.add_separator()
        menu.add_command(label="📝 전체 행 복사", 
                        command=lambda: self._copy_row_to_clipboard(values))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._log(f"📋 클립보드 복사: {text}")
    
    def _copy_row_to_clipboard(self, values) -> None:
        text = '\t'.join(str(v) for v in values)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._log("📋 행 데이터 클립보드 복사")
    
    def _show_lot_tonbag_detail(self, lot_no: str) -> None:
        """LOT 톤백 상세 팝업"""
        import tkinter as tk
        from tkinter import ttk as _ttk
        
        tonbags = self.engine.db.fetchall(
            """SELECT sub_lt, weight, status, location, picked_to, 
                      outbound_date, updated_at
               FROM inventory_tonbag WHERE lot_no = ? ORDER BY sub_lt""",
            (lot_no,)
        )
        
        dlg = create_themed_toplevel(self.root)
        dlg.title(f"🎒 톤백 상세 — {lot_no}")
        apply_modal_window_options(dlg)
        dlg.transient(self.root)
        setup_dialog_geometry_persistence(dlg, "tonbag_detail_dialog", self.root, "medium")
        
        cols = ('sub_lt', 'weight', 'status', 'location', 'picked_to', 'outbound_date')
        tree = _ttk.Treeview(dlg, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H)
        
        for col, text, w in [
            ('sub_lt', '톤백#', 60), ('weight', '중량(kg)', 100),
            ('status', '상태', 100), ('location', '위치', 80),
            ('picked_to', '출고처', 120), ('outbound_date', '출고일', 120)
        ]:
            tree.heading(col, text=text, anchor='center')
            tree.column(col, width=w, anchor='center')
        
        for i, tb in enumerate(tonbags):
            _s = tb.get('status', STATUS_AVAILABLE)
            status_text = get_status_display(_s) or _s
            tags = ('stripe',) if i % 2 == 1 else ()
            tree.insert('', 'end', values=(
                tb['sub_lt'], f"{(tb['weight'] or 0):,.0f}",
                status_text, tb['location'] or '',
                tb['picked_to'] or '', str(tb['outbound_date'] or '')[:10]
            ), tags=tags)
        
        _stripe_bg = ThemeColors.get('tree_stripe', getattr(self, '_is_dark', False))
        tree.tag_configure('stripe', background=_stripe_bg)
        
        scroll = tk.Scrollbar(dlg, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True, padx=Spacing.XS, pady=Spacing.XS)
        scroll.pack(side='right', fill='y', pady=Spacing.XS)
        
        total = sum((tb['weight'] or 0) for tb in tonbags)
        avail = sum((tb['weight'] or 0) for tb in tonbags if tb['status'] == STATUS_AVAILABLE)
        _ttk.Label(dlg, text=f"합계: {len(tonbags)}개 / {total:,.0f}kg (판매가능: {avail:,.0f}kg)",
                  font=('', 13, 'bold')).pack(side='bottom', pady=Spacing.XS)
    
    def _quick_outbound_from_context(self, lot_no: str) -> None:
        """v8.3.1: 우클릭 즉시 출고 — LOT 미리 채운 원스톱 출고 다이얼로그 열기."""
        try:
            # LOT 상태 확인 — AVAILABLE이 아니면 경고
            inv = self.engine.db.fetchone(
                "SELECT status, current_weight FROM inventory WHERE lot_no = ?",
                (lot_no,)
            )
            if not inv:
                from ..utils.ui_constants import CustomMessageBox
                CustomMessageBox.showerror(
                    self.root, "오류", f"LOT을 찾을 수 없습니다: {lot_no}"
                )
                return
            status = inv.get('status') if isinstance(inv, dict) else inv[0]
            cw = float(
                inv.get('current_weight', 0) if isinstance(inv, dict) else inv[1]
            )
            if status not in ('AVAILABLE', 'PARTIAL', 'RESERVED'):
                from ..utils.ui_constants import CustomMessageBox
                CustomMessageBox.showwarning(
                    self.root, "출고 불가",
                    f"{lot_no}  상태: {status}\n"
                    f"AVAILABLE / PARTIAL / RESERVED 상태만 즉시 출고 가능합니다."
                )
                return
            if cw <= 0:
                from ..utils.ui_constants import CustomMessageBox
                CustomMessageBox.showwarning(
                    self.root, "재고 없음",
                    f"{lot_no}: 가용 재고가 없습니다. (current_weight={cw:.0f}kg)"
                )
                return

            # 원스톱 출고 다이얼로그 — initial_lot_no 전달
            from gui_app_modular.dialogs.onestop_outbound import S1OneStopOutboundDialog
            dlg = S1OneStopOutboundDialog(
                self.app, self.engine, initial_lot_no=lot_no
            )
            dlg.show()

        except Exception as e:
            logger.error(f"[즉시출고] 오류: {e}", exc_info=True)
            try:
                from ..utils.ui_constants import CustomMessageBox
                CustomMessageBox.showerror(self.root, "오류", str(e))
            except Exception as e:
                logger.warning(f'[UI] inventory_tab: {e}')
    def _return_from_context(self, lot_no: str) -> None:
        """
        컨텍스트 메뉴 반품 처리 — RETURN_AS_REINBOUND 정책 (v7.0.0).

        1. outbound_log 에서 해당 LOT의 최근 출고 이력 조회
        2. ReturnReinboundDialog 호출 (PDA 스캔 UI)
        3. 성공 시 inventory 뷰 자동 갱신
        """
        try:
            from gui_app_modular.dialogs.return_dialog import ReturnReinboundDialog
        except ImportError:
            logger.error("[v7.0.0] ReturnReinboundDialog import 실패")
            if hasattr(self, '_on_return_process'):
                self._on_return_process()
            return

        # ── 최근 출고 이력 조회 ───────────────────────────────────────────────
        ob = self.engine.db.fetchone(
            """SELECT outbound_id, customer
               FROM outbound_log
               WHERE lot_no = ?
               ORDER BY rowid DESC LIMIT 1""",
            (lot_no,)
        )

        if not ob:
            # 출고 이력 없으면 기존 방식 fallback
            logger.warning(f"[v7.0.0] 출고 이력 없음: {lot_no} — 기존 반품 처리로 fallback")
            if hasattr(self, '_on_return_process'):
                self._on_return_process()
            return

        outbound_id = ob.get('outbound_id') or ob['outbound_id']
        customer    = ob.get('customer', '')

        # ── DB raw connection 추출 ────────────────────────────────────────────
        raw_conn = getattr(self.engine.db, '_local', None)
        if raw_conn:
            raw_conn = getattr(raw_conn, 'conn', None)
        if raw_conn is None:
            raw_conn = getattr(self.engine.db, '_conn', None)

        if raw_conn is None:
            logger.error("[v7.0.0] DB raw connection 추출 실패 — fallback")
            if hasattr(self, '_on_return_process'):
                self._on_return_process()
            return

        # ── ReturnReinboundDialog 오픈 ────────────────────────────────────────
        def _on_return_success(return_id: str, new_location: str) -> None:
            self._log(
                f"✅ 반품 완료 | {lot_no} | {return_id} | 위치: {new_location}"
            )
            self._refresh_inventory()

        ReturnReinboundDialog(
            parent=self.root,
            db_conn=raw_conn,
            outbound_id=outbound_id,
            lot_no=lot_no,
            customer=customer,
            on_success=_on_return_success,
            current_theme=getattr(self, 'current_theme', 'darkly'),
        )
    
    def _show_lot_history(self, lot_no: str) -> None:
        """LOT 이력 조회"""
        import tkinter as tk
        from tkinter import ttk as _ttk
        
        # customer, movement_date 컬럼 없어도 동작 (base 스키마: movement_type, qty_kg, created_at)
        movements = self.engine.db.fetchall(
            """SELECT movement_type, qty_kg,
                   '' AS customer, created_at AS movement_date, created_at
               FROM stock_movement WHERE lot_no = ? ORDER BY created_at DESC""",
            (lot_no,)
        )
        
        dlg = create_themed_toplevel(self.root)
        dlg.title(f"📊 LOT 이력 — {lot_no}")
        apply_modal_window_options(dlg)
        dlg.transient(self.root)
        setup_dialog_geometry_persistence(dlg, "lot_history_dialog", self.root, "medium")
        
        cols = ('type', 'qty', 'customer', 'date', 'created')
        tree = _ttk.Treeview(dlg, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H)
        
        type_icons = {
            'OUTBOUND': '📤 출고', 'INBOUND': '📥 입고',
            'CANCEL_OUTBOUND': '↩️ 취소', 'RETURN': '🔄 반품'
        }
        
        for col, text, w in [
            ('type', '유형', 100), ('qty', '수량(kg)', 100),
            ('customer', '고객', 120), ('date', '날짜', 100), ('created', '등록일', 120)
        ]:
            tree.heading(col, text=text, anchor='center')
            tree.column(col, width=w, anchor='e' if col == 'qty' else 'center')
        
        for i, mv in enumerate(movements):
            tree.insert('', 'end', values=(
                type_icons.get(mv['movement_type'], mv['movement_type']),
                f"{(mv['qty_kg'] or 0):,.0f}",
                mv['customer'] or '',
                str(mv['movement_date'] or '')[:10],
                str(mv['created_at'] or '')[:16]
            ), tags=('stripe',) if i % 2 == 1 else ())
        
        _stripe_bg = ThemeColors.get('tree_stripe', getattr(self, '_is_dark', False))
        tree.tag_configure('stripe', background=_stripe_bg)
        tree.pack(fill='both', expand=True, padx=Spacing.XS, pady=Spacing.XS)
        
        if not movements:
            _ttk.Label(dlg, text="이력이 없습니다.", foreground=tc('text_muted')).pack(pady=Spacing.LG)

    def _apply_inventory_theme_colors(self) -> None:
        """테마 색상 적용 (v5.6.9: Grid 스타일 foreground 갱신 — 다크에서 글씨 보이게)"""
        dark_mode = is_dark()
        ThemeColors.configure_tags(self.tree_inventory, is_dark)
        try:
            from ..utils.table_styler import TableStyler
            TableStyler.update_grid_style_for_theme(self.tree_inventory, is_dark)
        except (ImportError, Exception) as e:
            logger.debug(f"Grid 스타일 테마 갱신 무시: {e}")

    def _on_search(self, *args) -> None:
        self._refresh_inventory()

    def _on_status_filter(self, event) -> None:
        self._refresh_inventory()

    def _convert_preview_to_inventory_items(self, preview_data: list) -> list:
        """원스톱 파싱 미리보기 데이터를 재고 탭 형식으로 변환 (실시간 표시용)"""
        result = []
        for row in preview_data:
            try:
                nw = row.get('net_weight', '') or '0'
                if isinstance(nw, str):
                    nw = nw.replace(',', '').strip()
                net = float(nw) if nw else 0.0
            except (ValueError, TypeError):
                net = 0.0
            mxbg = row.get('mxbg_pallet', '10') or '10'
            if isinstance(mxbg, str) and mxbg.isdigit():
                mxbg = int(mxbg)
            else:
                try:
                    mxbg = int(float(mxbg))
                except (ValueError, TypeError):
                    mxbg = 10
            result.append({
                'lot_no': str(row.get('lot_no', '')),
                'sap_no': str(row.get('sap_no', '')),
                'bl_no': str(row.get('bl_no', '')),
                'container_no': str(row.get('container_no', '')),
                'product': str(row.get('product', '')),
                'mxbg_pallet': mxbg,
                'avail_bags': mxbg,
                'net_weight': net,
                'salar_invoice_no': str(row.get('salar_invoice_no', '')),
                'ship_date': str(row.get('ship_date', ''))[:10] if row.get('ship_date') else '',
                'arrival_date': str(row.get('arrival_date', ''))[:10] if row.get('arrival_date') else '',
                'con_return': str(row.get('con_return', ''))[:10] if row.get('con_return') else '',
                'free_time': str(row.get('free_time', '')),
                'warehouse': str(row.get('warehouse', '')),
                'status': str(row.get('status', STATUS_AVAILABLE)),
                'customs': '',
                'initial_weight': net,
                'current_weight': net,
            })
        return result

    def _set_parsing_preview_data(self, data) -> None:
        """파싱 미리보기 데이터 설정/해제. None이면 창을 비우고, 파싱 결과만 올 때만 표시. PL list_no 순서 유지(정렬하지 않음)."""
        self._parsing_preview_data = data
        if isinstance(data, list) and len(data) > 0:
            self._blank_inventory_until_first_parse = False
        else:
            # 파싱 전/해제 시: 기존 데이터 clear, 파싱 결과만 보여줌
            self._blank_inventory_until_first_parse = True
        self._refresh_inventory()

    def _reset_inventory_view_for_new_inbound(self) -> None:
        """추가 입고 시작 전 재고 탭 화면 상태를 초기화한다."""
        try:
            # 사용자 확인(추가 입고=예) 직후 메인 창 데이터를 즉시 비움
            self._parsing_preview_data = None
            self._blank_inventory_until_first_parse = True
            self._blank_inventory_notice_shown = False

            if hasattr(self, 'search_var'):
                self.search_var.set('')
            if hasattr(self, '_date_from_var'):
                self._date_from_var.set('')
            if hasattr(self, '_date_to_var'):
                self._date_to_var.set('')
            if hasattr(self, 'status_var'):
                self.status_var.set('전체')

            # 헤더 필터/콤보 필터 초기화
            if hasattr(self, '_inv_filter_bar') and hasattr(self._inv_filter_bar, '_reset_filters'):
                self._inv_filter_bar._reset_filters()
            elif hasattr(self, '_reset_inv_combo_search'):
                self._reset_inv_combo_search()

            # [전체 톤백 펼치기] 상태라면 LOT 리스트 화면으로 복귀
            if getattr(self, '_inv_show_all_tonbags', False):
                self._on_back_to_lot_list()

            # 선택 초기화
            if hasattr(self, 'tree_inventory') and self.tree_inventory.winfo_exists():
                self.tree_inventory.selection_remove(self.tree_inventory.selection())
        except Exception as e:
            logger.debug(f"추가 입고 전 재고 화면 초기화 무시: {e}")
        self._refresh_inventory()

    def _apply_unassigned_loc_filter(self) -> None:
        """① v6.8.2: 위치 미배정 드릴다운 — 해당 LOT 목록 강조 표시."""
        if not getattr(self, '_unassigned_loc_filter_var', None):
            return
        if not self._unassigned_loc_filter_var.get():
            return
        try:
            rows = self.engine.db.fetchall("""
                SELECT DISTINCT lot_no
                FROM inventory_tonbag
                WHERE status = 'AVAILABLE'
                  AND COALESCE(is_sample, 0) = 0
                  AND (location IS NULL OR TRIM(location) = '')
                ORDER BY lot_no
            """)
            lots = [r['lot_no'] if isinstance(r, dict) else r[0] for r in (rows or [])]
            if lots and hasattr(self, 'tree_inventory'):
                # 트리에서 해당 LOT 행 선택
                for child in self.tree_inventory.get_children():
                    vals = self.tree_inventory.item(child, 'values')
                    if vals and str(vals[0]).strip() in lots:
                        self.tree_inventory.selection_add(child)
                        self.tree_inventory.see(child)
            logger.info(f"[① 드릴다운] 위치 미배정 {len(lots)} LOT 하이라이트")
        except Exception as e:
            logger.debug(f"[드릴다운 필터] {e}")
        finally:
            self._unassigned_loc_filter_var.set(False)  # 플래그 초기화

    def _refresh_inventory(self) -> None:
        """재고 목록 새로고침 (18열 + 콤보 검색 + Date 기간)"""
        if not hasattr(self, 'tree_inventory'):
            return
        
        self.tree_inventory.delete(*self.tree_inventory.get_children())

        search_text = self.search_var.get().strip().lower()
        # v7.0 2단계: 판매가능 탭 전용 — status 필터 고정 (판매가능만 표시)
        status_filter_normalized = STATUS_AVAILABLE  # DB 값

        # 콤보 검색 조건
        combo_filters = {}
        if hasattr(self, '_inv_search_combos'):
            for field, (var, cb) in self._inv_search_combos.items():
                val = var.get()
                if val and val != '전체':
                    combo_filters[field] = val
        # v4.0.6: 헤더 필터바 조건 (status는 위에서 별도 처리하므로 제외)
        if hasattr(self, '_inv_filter_bar'):
            for k, v in self._inv_filter_bar.get_filters().items():
                if k != 'status':
                    combo_filters[k] = v
        
        # Date 기간 조건
        date_from = ''
        date_to = ''
        if hasattr(self, '_date_from_var'):
            date_from = self._date_from_var.get().strip().replace('-', '')
        if hasattr(self, '_date_to_var'):
            date_to = self._date_to_var.get().strip().replace('-', '')

        try:
            # 파싱 팝업에서 실시간 푸시된 미리보기 데이터가 있으면 재고 리스트에 표시
            preview = getattr(self, '_parsing_preview_data', None)
            if preview is not None and isinstance(preview, list) and len(preview) > 0:
                inventory = self._convert_preview_to_inventory_items(preview)
                if hasattr(self, '_log'):
                    self._log(f"📋 파싱 미리보기: 재고 리스트에 {len(inventory)}건 표시 (저장 전)")
            elif getattr(self, '_blank_inventory_until_first_parse', False):
                inventory = []
                if hasattr(self, '_log') and not getattr(self, '_blank_inventory_notice_shown', False):
                    self._log("ℹ️ 초기 화면은 백지 상태로 시작합니다. 파싱 시작 후 데이터가 표시됩니다.")
                    self._blank_inventory_notice_shown = True
            else:
                inventory = self.engine.get_all_inventory()

            # v6.8.8: TONBAG 상태별 집계 — 단일 쿼리로 4가지 상태 한 번에 조회
            avail_map      = {}
            reserved_map   = {}
            picked_map     = {}
            sold_map       = {}
            try:
                tb_rows = self.engine.db.fetchall(
                    "SELECT lot_no, status, COUNT(*) AS cnt "
                    "FROM inventory_tonbag "
                    "WHERE COALESCE(is_sample, 0) = 0 "
                    "GROUP BY lot_no, status"
                )
                for r in (tb_rows or []):
                    _lot = str(r.get('lot_no', '')).strip()
                    _st  = str(r.get('status', '')).strip().upper()
                    _cnt = int(r.get('cnt', 0) or 0)
                    if _st == STATUS_AVAILABLE:
                        avail_map[_lot]    = avail_map.get(_lot, 0) + _cnt
                    elif _st == STATUS_RESERVED:
                        reserved_map[_lot] = reserved_map.get(_lot, 0) + _cnt
                    elif _st == STATUS_PICKED:
                        picked_map[_lot]   = picked_map.get(_lot, 0) + _cnt
                    elif _st in ('OUTBOUND', 'SOLD'):  # v7.2.0: OUTBOUND+SOLD 통합
                        sold_map[_lot]     = sold_map.get(_lot, 0) + _cnt
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                logger.debug(f"TONBAG 상태 집계 조회 실패(기본 0 처리): {e}")

            for item in inventory:
                lot_no = str(item.get('lot_no', '')).strip()
                product = str(item.get('product', ''))
                sap_no = str(item.get('sap_no', ''))

                # 즉시 검색 필터
                if search_text:
                    searchable = f"{lot_no} {product} {sap_no} {item.get('bl_no','')}".lower()
                    if search_text not in searchable:
                        continue

                # 상태 필터 (전체 / 판매가능 / 판매배정 / 판매화물 결정 / 출고)
                status = item.get('status', STATUS_AVAILABLE)
                if status_filter_normalized and status != status_filter_normalized:
                    continue
                
                # 콤보 검색 필터 + 헤더 필터바
                skip = False
                for field, val in combo_filters.items():
                    item_val = str(item.get(field, ''))
                    if item_val != val:
                        skip = True
                        break
                if skip:
                    continue
                
                # v8.1.5: 기간 필터 — 입항→입고일→선적일→생성일
                if date_from or date_to:
                    from ..utils.tree_enhancements import row_reference_date_ymd
                    ref_d = row_reference_date_ymd(item)
                    if date_from and ref_d and ref_d < date_from:
                        continue
                    if date_to and ref_d and ref_d > date_to:
                        continue

                # v3.9.1: 18열 값 추출
                row_num = len(self.tree_inventory.get_children()) + 1
                vals = []
                for col_id, _, _, _, _ in INVENTORY_COLUMNS:
                    if col_id == 'row_num':
                        vals.append(str(row_num))
                        continue
                    elif col_id == 'outbound_weight':
                        # 출고량 = 입고 - 잔량
                        try:
                            init_w = float(item.get('initial_weight', 0) or 0)
                            curr_w = float(item.get('current_weight', 0) or 0)
                            out_w = init_w - curr_w
                            vals.append(f"{out_w:,.0f}" if out_w > 0 else '0')
                        except (ValueError, TypeError):
                            vals.append('0')
                        continue
                    elif col_id == 'customs_status':
                        vals.append(str(item.get('customs_status', '') or ''))
                        continue
                    elif col_id == 'avail_bags':
                        vals.append(str(avail_map.get(lot_no, 0)))
                        continue
                    elif col_id == 'tb_avail':
                        vals.append(str(avail_map.get(lot_no, 0)))
                        continue
                    elif col_id == 'tb_reserved':
                        vals.append(str(reserved_map.get(lot_no, 0)))
                        continue
                    elif col_id == 'tb_picked':
                        vals.append(str(picked_map.get(lot_no, 0)))
                        continue
                    elif col_id == 'tb_sold':
                        vals.append(str(sold_map.get(lot_no, 0)))
                        continue
                    
                    v = item.get(col_id, '')
                    if v is None:
                        v = ''
                    # 컨테이너 구분(-1, -2) 옵션: 꺼져 있으면 접미사 제거
                    if col_id == 'container_no' and hasattr(self, '_format_container_no'):
                        v = self._format_container_no(str(v))
                    # 숫자 포맷팅
                    if col_id in ('net_weight', 'current_weight', 'initial_weight'):
                        try:
                            v = f"{float(v):,.0f}" if v else '0'
                        except (ValueError, TypeError):
                            v = str(v)
                    elif col_id in ('mxbg_pallet', 'free_time'):
                        try:
                            v = f"{int(float(v)):,}" if v else ''
                        except (ValueError, TypeError):
                            v = str(v)
                    elif col_id == 'con_return':
                        # CON RETURN은 날짜(YYYY-MM-DD) 형식이므로 앞 10자리만
                        v = str(v)[:10] if v and str(v) not in ('None', 'nan') else ''
                        if not v:
                            # DB에 없으면 arrival_date + free_time으로 계산
                            arr = str(item.get('arrival_date', ''))[:10]
                            ft = str(item.get('free_time', ''))
                            if arr and ft and ft.isdigit():
                                try:
                                    arr_dt = datetime.strptime(arr, '%Y-%m-%d')
                                    ret_dt = arr_dt + timedelta(days=int(ft))
                                    v = ret_dt.strftime('%Y-%m-%d')
                                except (ValueError, TypeError):
                                    logger.debug("[SUPPRESSED] exception in inventory_tab.py")  # noqa
                    # U2: 화물 상태 표시 (전체/판매가능/판매배정/판매화물 결정/출고)
                    elif col_id == 'status':
                        v = get_status_display(str(v)) or str(v)
                    else:
                        v = str(v)
                    vals.append(v)

                tag = status.lower() if status in [STATUS_AVAILABLE, STATUS_PICKED, STATUS_RESERVED, 'SHIPPED', STATUS_DEPLETED] else ''
                # U1: 교대 줄무늬 (상태색이 있으면 stripe 제외 → 상태색 우선)
                row_idx = len(self.tree_inventory.get_children())
                tags = [tag] if tag else []
                if row_idx % 2 == 1 and not tag:
                    tags.append('stripe')
                self.tree_inventory.insert('', 'end', values=vals, tags=tuple(tags))

            # ═══ v6.3.2-colorful: 상태별 고유 전경색 (단일색 덮어쓰기 제거) ═══
            _dk = is_dark()
            _stripe_bg = ThemeColors.get('tree_stripe', _dk)
            _fg = tc('text_primary') if _dk else '#1a1a1a'
            # ★ 상태별 고유 전경색 (밝은 배경엔 짙은 글씨, 어두운 배경엔 밝은 글씨)
            # v8.6.5: 대비 강화 — WCAG AA 4.5:1 기준 충족
            _sfg = {
                'available': '#6ee7b7' if _dk else '#064e3b',
                'reserved':  '#fcd34d' if _dk else '#78350f',
                'picked':    '#c4b5fd' if _dk else '#4c1d95',
                'shipped':   '#93c5fd' if _dk else '#0a2844',
            }
            self.tree_inventory.tag_configure('available',
                background=ThemeColors.get('available', _dk), foreground=_sfg['available'])
            self.tree_inventory.tag_configure('picked',
                background=ThemeColors.get('picked', _dk), foreground=_sfg['picked'])
            self.tree_inventory.tag_configure('reserved',
                background=ThemeColors.get('reserved', _dk), foreground=_sfg['reserved'])
            self.tree_inventory.tag_configure('shipped',
                background=ThemeColors.get('shipped', _dk), foreground=_sfg['shipped'])
            self.tree_inventory.tag_configure('depleted',
                background='#e8e8e8' if not _dk else '#1a1a2e',
                foreground='#666666' if not _dk else '#9a9ab0')
            self.tree_inventory.tag_configure('stripe',
                background=_stripe_bg, foreground=_fg)

            self._refresh_summary()
            if hasattr(self, '_inv_total_footer') and self._inv_total_footer:
                self._inv_total_footer.update_totals()

            # 빈 목록일 때 안내 메시지 표시 (목록이 안 보이는 것이 아님을 안내)
            if len(self.tree_inventory.get_children()) == 0:
                self._show_empty_state_hint()
            else:
                self._hide_empty_state_hint()
            
            # v3.8.7: 재고 탭 하단 통계 갱신
            self._refresh_inv_stats()
            
            # U4: 상태바 실시간 재고 요약 갱신
            if hasattr(self, '_update_statusbar_summary'):
                self._update_statusbar_summary()
            
            # v4.2.2: 테이블 스타일 줄무늬 새로고침
            try:
                from ..utils.table_styler import TableStyler
                TableStyler.refresh_striped_rows(self.tree_inventory)
            except (ImportError, Exception) as e:
                logger.debug(f"줄무늬 새로고침 실패: {e}")
                # Fallback: 기존 방식
                try:
                    from ..utils.tree_enhancements import apply_striped_rows
                    _dk2 = is_dark()
                    apply_striped_rows(self.tree_inventory, is_dark=_dk2)
                except (ImportError, Exception) as _e2:
                    logger.debug(f"기존 방식 줄무늬도 실패: {_e2}")
            
            # STATUS 집계 라벨 + LOT/SAP/… 목록은 DB DISTINCT로 채움(빈 목록 덮어쓰기 방지)
            self._update_inv_filter_values(inventory)
            self._populate_filter_dropdowns()
            
            # v5.6.1: FooterTotalBar 제거 (stats_frame 1줄로 통합)
            # self._update_inv_footer()

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"재고 조회 오류: {e}")
            self._log(f"⚠️ 재고 조회 오류: {e}")
    

    def _refresh_inv_stats(self) -> None:
        """v3.8.7: 재고 탭 하단 통계. v7.0 2단계: 판매가능 탭 — 판매가능(LOT/톤백/무게)만 표시."""
        if not hasattr(self, '_inv_summary_label'):
            return
        try:
            # v7.0: 판매가능만 집계 (LOT 수, 톤백 수, 총 무게)
            stats = self.engine.db.fetchone("""
                SELECT COUNT(*) AS total_lots, COALESCE(SUM(current_weight), 0) AS total_current
                FROM inventory WHERE status = 'AVAILABLE'
            """) if hasattr(self.engine, 'db') and self.engine.db else None
            tb_stats = self.engine.db.fetchone("""
                SELECT COUNT(*) AS total, COALESCE(SUM(weight), 0) AS total_kg
                FROM inventory_tonbag WHERE status = 'AVAILABLE' AND COALESCE(is_sample, 0) = 0
            """) if hasattr(self.engine, 'db') and self.engine.db else None
            total_lots = current_kg = 0
            tb_total = tb_kg = 0
            if stats:
                total_lots = stats.get('total_lots', 0) or 0
                current_kg = (stats.get('total_current', 0) or 0) / 1000.0
            if tb_stats:
                tb_total = tb_stats.get('total') or 0
                tb_kg = (tb_stats.get('total_kg') or 0) / 1000.0
            line = (
                f"📦 판매가능 LOT: {total_lots:,}  🎒 톤백: {tb_total:,}  💰 총 중량: {current_kg:,.1f} MT (LOT) / {tb_kg:,.1f} MT (톤백)"
            )
            self._inv_summary_label.config(text=line)
        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"inv_stats 갱신 오류: {e}")

    # ═══════════════════════════════════════════════════════
    # v4.0.6: 필터바 / 합계바 메서드
    # ═══════════════════════════════════════════════════════
    
    def _on_inv_filter_apply(self) -> None:
        """v4.0.6: 재고 필터 적용 시 새로고침"""
        self._safe_refresh()
    def _update_inv_filter_values(self, inventory) -> None:
        """STATUS 콤보만 집계 라벨 갱신. LOT/SAP/BL 등 목록은 _populate_filter_dropdowns(DB)로 통일."""
        if not hasattr(self, '_inv_filter_bar'):
            return
        try:
            inv = inventory or []
            cnt_total = len(inv)
            cnt_avail = sum(1 for i in inv if (i.get('status') or '') == STATUS_AVAILABLE)
            cnt_reserved = sum(1 for i in inv if (i.get('status') or '') == STATUS_RESERVED)
            cnt_picked = sum(1 for i in inv if (i.get('status') or '') == STATUS_PICKED)
            cnt_sold = sum(1 for i in inv if (i.get('status') or '') in (STATUS_OUTBOUND, STATUS_SOLD))
            cnt_return = sum(1 for i in inv if (i.get('status') or '') == STATUS_RETURN)
            status_values = [
                f"전체 ({cnt_total})", f"판매가능 ({cnt_avail})", f"판매배정 ({cnt_reserved})",
                f"판매화물 결정 ({cnt_picked})", f"출고완료 ({cnt_sold})",
                f"반품대기 ({cnt_return})",
            ]
            combo = self._inv_filter_bar.filter_combos.get('status')
            if combo:
                combo['values'] = status_values
                cur = self._inv_filter_bar.filter_vars['status'].get()
                if cur not in status_values and status_values:
                    self._inv_filter_bar.filter_vars['status'].set(status_values[0])
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"필터 값 업데이트 오류: {e}")
    
    def _update_inv_footer(self) -> None:
        """v4.0.6: 하단 합계 바 — 트리뷰 표시 행 기준"""
        if not hasattr(self, '_inv_footer'):
            return
        try:
            net_total = 0.0
            balance_total = 0.0
            rows = 0
            
            for item_id in self.tree_inventory.get_children(''):
                vals = self.tree_inventory.item(item_id, 'values')
                rows += 1
                # NET(Kg) = index 7, Balance(Kg) = index 15 (INVENTORY_COLUMNS 기준)
                try:
                    net_total += float(str(vals[7]).replace(',', ''))
                except (ValueError, TypeError, IndexError) as _e:
                    logger.debug(f"Suppressed: {_e}")
                try:
                    balance_total += float(str(vals[15]).replace(',', ''))
                except (ValueError, TypeError, IndexError) as _e:
                    logger.debug(f"Suppressed: {_e}")
            
            self._inv_footer.update({
                'rows': rows,
                'net_kg': net_total,
                'balance_kg': balance_total,
            })
        except (ValueError, TypeError) as e:
            logger.debug(f"inv footer 오류: {e}")

    def _refresh_inventory_async(self) -> None:
        def load_data():
            return self.engine.get_all_inventory()
        def update_ui(inventory):
            self._refresh_inventory()
        self._run_background(load_data, update_ui)

    def _on_lot_double_click(self, event) -> None:
        """LOT 더블클릭 → v4.1.0: 상세 추적 팝업"""
        selection = self.tree_inventory.selection()
        if not selection:
            return
        
        item_id = selection[0]
        item = self.tree_inventory.item(item_id)
        values = item.get('values', [])
        item.get('tags', ())
        
        if not values or len(values) < 2:
            return
        
        # values[0] = row_num, values[1] = lot_no (INVENTORY_COLUMNS 기준)
        lot_no = str(values[1]).strip()
        if not lot_no:
            return
        
        # v4.1.0: 상세 추적 팝업 표시
        if hasattr(self, '_show_lot_detail_popup'):
            self._show_lot_detail_popup(lot_no)

    def _sort_treeview(self, tree, col: str) -> None:
        """트리뷰 정렬"""
        if self._sort_column == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = col
            self._sort_reverse = False

        items = [(tree.set(item, col), item) for item in tree.get_children('')]

        numeric_cols = ['net_weight', 'gross_weight', 'current_weight', 'initial_weight',
                       'mxbg_pallet', 'free_time']

        sort_key = make_sort_key(col, numeric_cols)  # v7.0.0 [REFACTOR-1]

        items.sort(key=sort_key, reverse=self._sort_reverse)

        for index, (_, item) in enumerate(items):
            tree.move(item, '', index)

        # U7: 헤더 정렬 표시 개선 (▲▼)
        arrow = " ▼" if self._sort_reverse else " ▲"
        for c_id, c_label, _, _, _ in INVENTORY_COLUMNS:
            if c_id == col:
                tree.heading(c_id, text=f"{c_label}{arrow}", anchor='center')
            else:
                tree.heading(c_id, text=c_label, anchor='center')
    

    def _show_empty_state_hint(self) -> None:
        """표시할 데이터가 없을 때 안내 라벨 표시 (목록 영역은 보이지만 비어 있음을 안내)."""
        self._hide_empty_state_hint()
        if not hasattr(self, '_inv_tree_frame') or not self._inv_tree_frame.winfo_exists():
            return
        try:
            _is_dark = is_dark()
            _fg = ThemeColors.get('text_primary', _is_dark)
            _msg = (
                "표시할 데이터가 없습니다. "
                "입고 파싱을 실행했거나 DB에 판매가능(AVAILABLE) 데이터가 있으면 여기에 표시됩니다. "
                "필터/기간을 완화해 보세요."
            )
            self._empty_hint = tk.Label(
                self._inv_tree_frame,
                text=_msg,
                font=('맑은 고딕', 10),
                fg=_fg,
                bg=ThemeColors.get('bg_card', _is_dark),
                wraplength=500,
            )
            self._empty_hint.pack(side=tk.TOP, fill=tk.X, pady=Spacing.MD, padx=Spacing.Tab.OUTER_PADX)
        except Exception as e:
            logger.debug(f"빈 상태 안내 표시 실패: {e}")
            self._empty_hint = None

    def _hide_empty_state_hint(self) -> None:
        """빈 상태 안내 숨김"""
        if hasattr(self, '_empty_hint') and self._empty_hint:
            try:
                self._empty_hint.destroy()
            except (ValueError, TypeError, KeyError) as _e:
                logger.debug(f'Suppressed: {_e}')
            self._empty_hint = None
    
    def _populate_filter_dropdowns(self) -> None:
        """
        DB DISTINCT로 LOT/SAP/BL/CONTAINER/PRODUCT 목록 채움.
        STATUS는 _update_inv_filter_values에서만 설정.
        """
        def _row_val(row, key: str):
            if row is None:
                return None
            try:
                if isinstance(row, dict):
                    return row.get(key)
                return dict(row).get(key)
            except (TypeError, ValueError) as e:
                logger.debug(f"필터 행 변환: {e}")
                return None

        try:
            if hasattr(self, '_inv_filter_bar') and hasattr(self._inv_filter_bar, 'lot_combo'):
                lots = self.engine.db.fetchall(
                    "SELECT DISTINCT lot_no FROM inventory WHERE lot_no IS NOT NULL AND TRIM(lot_no) != '' ORDER BY lot_no"
                )
                seen = []
                for row in (lots or []):
                    v = _row_val(row, 'lot_no')
                    if v is not None and str(v).strip():
                        seen.append(str(v).strip())
                self._inv_filter_bar.lot_combo['values'] = ['전체'] + sorted(set(seen))

            if hasattr(self, '_inv_filter_bar') and hasattr(self._inv_filter_bar, 'sap_combo'):
                saps = self.engine.db.fetchall(
                    "SELECT DISTINCT sap_no FROM inventory "
                    "WHERE sap_no IS NOT NULL AND TRIM(sap_no) != '' "
                    "ORDER BY sap_no"
                )
                seen = []
                for row in (saps or []):
                    v = _row_val(row, 'sap_no')
                    if v is not None and str(v).strip():
                        seen.append(str(v).strip())
                self._inv_filter_bar.sap_combo['values'] = ['전체'] + sorted(set(seen))

            if hasattr(self, '_inv_filter_bar') and hasattr(self._inv_filter_bar, 'bl_combo'):
                bls = self.engine.db.fetchall(
                    "SELECT DISTINCT bl_no FROM inventory "
                    "WHERE bl_no IS NOT NULL AND TRIM(bl_no) != '' "
                    "ORDER BY bl_no"
                )
                seen = []
                for row in (bls or []):
                    v = _row_val(row, 'bl_no')
                    if v is not None and str(v).strip():
                        seen.append(str(v).strip())
                self._inv_filter_bar.bl_combo['values'] = ['전체'] + sorted(set(seen))

            if hasattr(self, '_inv_filter_bar') and hasattr(self._inv_filter_bar, 'container_combo'):
                containers = self.engine.db.fetchall(
                    "SELECT DISTINCT container_no FROM inventory "
                    "WHERE container_no IS NOT NULL AND TRIM(container_no) != '' "
                    "ORDER BY container_no"
                )
                seen = []
                for row in (containers or []):
                    v = _row_val(row, 'container_no')
                    if v is not None and str(v).strip():
                        seen.append(str(v).strip())
                self._inv_filter_bar.container_combo['values'] = ['전체'] + sorted(set(seen))

            if hasattr(self, '_inv_filter_bar') and hasattr(self._inv_filter_bar, 'product_combo'):
                products = self.engine.db.fetchall(
                    "SELECT DISTINCT product FROM inventory "
                    "WHERE product IS NOT NULL AND TRIM(product) != '' "
                    "ORDER BY product"
                )
                seen = []
                for row in (products or []):
                    v = _row_val(row, 'product')
                    if v is not None and str(v).strip():
                        seen.append(str(v).strip())
                self._inv_filter_bar.product_combo['values'] = ['전체'] + sorted(set(seen))

            logger.debug("✅ 필터 드롭다운 채우기 완료")

        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"필터 드롭다운 채우기 실패: {e}")

