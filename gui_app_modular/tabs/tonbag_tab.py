# -*- coding: utf-8 -*-
"""
SQM 재고관리 - 톤백 탭
======================

v3.6.0 - UI 통일성 적용
v5.5.2 - 재고 리스트(Inventory) UI 기준 통일
  - 필터 바 1개만 사용 (재고와 동일: LOT NO, SAP NO, BL NO, CONTAINER, PRODUCT, STATUS + 초기화)
  - 표시 컬럼 바 → 액션 바 → 트리 → 푸터 순서 (재고와 동일)
  - ★ 유지보수: 재고 리스트(inventory_tab.py) UI가 바뀌면 이 탭도 동일하게 반영할 것.
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
from engine_modules.constants import STATUS_AVAILABLE, STATUS_DEPLETED, STATUS_PICKED, STATUS_RESERVED, STATUS_SOLD
import logging
from datetime import datetime, timedelta

from ..utils.ui_constants import is_dark, CustomMessageBox, get_status_display
import tkinter as tk
logger = logging.getLogger(__name__)


try:
    from ..utils.sort_utils import make_sort_key
except ImportError:
    def make_sort_key(col, numeric_cols):
        def _k(item):
            v = item[0]
            try: return (0, float(v)) if col in numeric_cols else (0, str(v).lower())
            except Exception: return (1, str(v))
        return _k


class TonbagTabMixin:
    """
    톤백 탭 Mixin
    
    SQMInventoryApp 클래스에 mix-in 됩니다.
    """
    
    def _setup_tonbag_tab(self) -> None:
        """톤백 탭 설정 (v5.0.2: 필터바 추가, v8.7.0: 기본 표시 8개)"""
        # 탭 헤더 (v7.3.7 심플화)
        try:
            from ..utils.ui_constants import make_tab_header, ThemeColors
            _is_dark_tb_hdr = is_dark()
            self._tonbag_count_var = getattr(self, '_tonbag_count_var', None) or __import__('tkinter').StringVar()
            make_tab_header(self.tab_tonbag, "🔩 톤백 리스트",
                            status_color='#f59e0b', count_var=self._tonbag_count_var,
                            is_dark=_is_dark_tb_hdr)
        except Exception:
            logger.debug("[SUPPRESSED] exception in tonbag_tab.py")  # noqa
        from ..utils.constants import ttk, tk, VERTICAL, HORIZONTAL, BOTH, YES, LEFT, RIGHT, X, Y
        from ..utils.ui_constants import Spacing, ThemeColors, apply_tooltip

        # 컬럼 정의 — 기본 전부 표시, 필요 시 "표시 컬럼" 체크로 숨김
        self._tonbag_columns = [
            ('row_num',            'No.',            50, 'center', True),
            ('lot_no',             'LOT NO',        120, 'center', True),
            ('tonbag_no_print',    'TONBAG NO',      95, 'center', True),
            ('sap_no',             'SAP NO',        120, 'center', True),
            ('bl_no',              'BL NO',         140, 'center', True),
            ('product',            'PRODUCT',       170, 'w',      True),
            ('tonbag_status',      'STATUS',         95, 'center', True),
            ('current_weight',     'Balance(Kg)',   105, 'e',      True),
            ('tonbag_uid',         'UID',           150, 'center', True),
            ('container_no',       'CONTAINER',     135, 'center', True),
            ('location',           'LOCATION',      115, 'w',      True),
            ('net_weight',         'NET(Kg)',        105, 'e',      True),
            ('salar_invoice_no',   'INVOICE NO',    110, 'center', True),
            ('ship_date',          'SHIP DATE',      95, 'center', True),
            ('arrival_date',       'ARRIVAL',        95, 'center', True),
            ('con_return',         'CON RETURN',     95, 'center', True),
            ('free_time',          'FREE TIME',      80, 'center', True),
            ('warehouse',          'WH',             85, 'w',      True),
            ('customs',            'CUSTOMS',        90, 'center', True),
            ('initial_weight',     'Inbound(Kg)',   105, 'e',      True),
            ('outbound_weight',    'Outbound(Kg)',  105, 'e',      True),
        ]
        self._tonbag_col_visible = {c[0]: c[4] for c in self._tonbag_columns}

        # ═══════════════════════════════════════════════════════════════
        # v5.0.8: 헤더 필터 바 (재고 리스트와 완전 동일)
        # ═══════════════════════════════════════════════════════════════
        _is_dark_filter = is_dark()
        
        self._tonbag_filter_bar = None
        try:
            from ..utils.tree_enhancements import HeaderFilterBar, TreeviewTotalFooter
            
            if not hasattr(self, '_date_from_var'):
                self._date_from_var = tk.StringVar()
            if not hasattr(self, '_date_to_var'):
                self._date_to_var = tk.StringVar()
            # 재고 리스트와 동일: LOT NO, SAP NO, BL NO, CONTAINER, PRODUCT, STATUS + 기간 + 초기화
            tonbag_filter_cols = [
                ('lot_no',       'LOT NO',     120),
                ('sap_no',       'SAP NO',     120),
                ('bl_no',        'BL NO',      140),
                ('container_no', 'CONTAINER',  130),
                ('product',      'PRODUCT',    160),
                ('tonbag_status','STATUS',      90),
            ]
            self._tonbag_filter_bar = HeaderFilterBar(
                self.tab_tonbag, None, tonbag_filter_cols,
                on_filter=self._on_tonbag_filter_apply,
                is_dark=_is_dark_filter,
                date_from_var=self._date_from_var,
                date_to_var=self._date_to_var,
                container_suffix_var=getattr(self, '_container_suffix_var', None),
                on_container_suffix_toggle=getattr(self, '_on_container_suffix_toggle', None),
            )
            self._tonbag_filter_bar.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        except (ImportError, AttributeError) as e:
            logger.debug(f"HeaderFilterBar 로딩 실패: {e}")
        
        # v5.0.2: 컬럼 토글 바 (v8.7.0: 20열 + 기본표시 8개만)
        try:
            from ..utils.column_toggle import ColumnToggleBar
            tonbag_toggle_cols = [(c[0], c[1], c[4]) for c in self._tonbag_columns]
            self._tonbag_toggle_bar = ColumnToggleBar(
                self.tab_tonbag,
                None,
                tonbag_toggle_cols,
                is_dark=_is_dark_filter
            )
            self._tonbag_toggle_bar.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))
        except (ImportError, Exception) as e:
            logger.debug(f"컬럼 토글바 생성 실패: {e}")
        
        # ═══════════════════════════════════════════════════════════════
        # v5.9.7: 스플릿 패널 (마스터-상세) — 톤백 리스트 + LOT 톤백 상세
        # ═══════════════════════════════════════════════════════════════
        from ..utils.split_panel import MasterDetailSplitPanel

        self._tb_split_panel = MasterDetailSplitPanel(
            self.tab_tonbag,
            detail_title="📦 LOT 톤백 상세 (선택 행의 LOT)",
            master_weight=3,
            detail_weight=1
        )
        self._tb_split_panel.pack(fill=BOTH, expand=YES, padx=Spacing.XS, pady=Spacing.XS)

        tree_frame = ttk.Frame(self._tb_split_panel.get_master_container())
        tree_frame.pack(fill=BOTH, expand=YES)
        self._tonbag_tree_frame = tree_frame
        
        # v3.8.9: 재고리스트와 동일 컬럼 + TONBAG NO 추가 (MXBG 다음) | v5.7.5: 가독성 위해 폰트 14로 확대
        import tkinter.font as tkfont
        _style = ttk.Style()
        _tb_font = tkfont.Font(family='맑은 고딕', size=11)
        _tb_head_font = tkfont.Font(family='맑은 고딕', size=11, weight='bold')
        _tb_row_h = _tb_font.metrics('linespace') + 6
        
        _is_dark_tb = is_dark()
        _tb_bg = ThemeColors.get('bg_card', _is_dark_tb)
        _tb_fg = ThemeColors.get('text_primary', _is_dark_tb)
        _tb_field = _tb_bg
        _tb_hd_bg = ThemeColors.get('bg_secondary', _is_dark_tb)
        _tb_hd_fg = ThemeColors.get('text_primary', _is_dark_tb)
        
        _style.configure('Tb.Treeview',
                         font=_tb_font, rowheight=_tb_row_h,
                         background=_tb_bg, foreground=_tb_fg,
                         fieldbackground=_tb_field)
        _style.configure('Tb.Treeview.Heading',
                         font=_tb_head_font,
                         background=_tb_hd_bg, foreground=_tb_hd_fg,
                         anchor='center')
        # v6.1.1: 선택/비선택 행 foreground 명시 (테마 가시성)
        _style.map('Tb.Treeview',
                   background=[('selected', ThemeColors.get('tree_select_bg', _is_dark_tb))],
                   foreground=[
                       ('selected', ThemeColors.get('tree_select_fg', _is_dark_tb)),
                       ('!selected', _tb_fg),
                   ])
        
        col_ids = [c[0] for c in self._tonbag_columns]
        self.tree_sublot = ttk.Treeview(
            tree_frame, columns=col_ids, show="headings", height=Spacing.Tab.TREE_MIN_H,
            selectmode='extended', style='Tb.Treeview'
        )
        
        self._tonbag_sort_column = None
        self._tonbag_sort_reverse = False
        for col_id, label, width, anchor, visible in self._tonbag_columns:
            self.tree_sublot.heading(
                col_id, text=label, anchor='center',
                command=lambda c=col_id: self._sort_tonbag_treeview(c)
            )
            if visible:
                self.tree_sublot.column(col_id, width=width, anchor=anchor, minwidth=50)
            else:
                self.tree_sublot.column(col_id, width=0, minwidth=0)
        visible_cols = [c[0] for c in self._tonbag_columns if c[4]]
        self.tree_sublot.configure(displaycolumns=visible_cols)
        
        # v4.2.2: 테이블 스타일 적용 (v5.6.9: 다크 테마 시 글씨 가시성)
        try:
            from ..utils.table_styler import apply_table_style
            apply_table_style(
                self.tree_sublot,
                grid_lines=True,
                striped_rows=True,
                row_height='normal',
                is_dark=_is_dark_tb
            )
        except (ImportError, Exception) as e:
            logger.debug(f"테이블 스타일 적용 실패: {e}")
        
        # 스크롤바
        scrollbar_y = tk.Scrollbar(tree_frame, orient=VERTICAL, 
                                    command=self.tree_sublot.yview)
        scrollbar_x = tk.Scrollbar(tree_frame, orient=HORIZONTAL, 
                                    command=self.tree_sublot.xview)
        self.tree_sublot.configure(yscrollcommand=scrollbar_y.set, 
                                   xscrollcommand=scrollbar_x.set)
        
        scrollbar_x.pack(side='bottom', fill=X)
        self.tree_sublot.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar_y.pack(side=RIGHT, fill=Y)

        tb_sum_cols = ['current_weight', 'net_weight', 'initial_weight', 'outbound_weight', 'free_time']
        self._tonbag_total_footer = TreeviewTotalFooter(
            tree_frame, self.tree_sublot, tb_sum_cols,
            column_display_names={'current_weight': 'Balance(Kg)', 'net_weight': 'NET(Kg)',
                                 'initial_weight': 'Inbound(Kg)', 'outbound_weight': 'Outbound(Kg)', 'free_time': 'FREE TIME'}
        )
        self._tonbag_total_footer.pack(fill=X, pady=(2, 0))

        self.tree_sublot.bind('<<TreeviewSelect>>', self._on_tonbag_selection_change)

        # v5.9.7: 상세 패널 — 선택 톤백의 LOT 내 톤백 목록
        self._setup_tonbag_lot_detail_panel()
        
        # v4.0.6 / v5.5.2: 단일 필터바에 treeview 연결 (재고 리스트와 동일)
        if hasattr(self, '_tonbag_filter_bar'):
            self._tonbag_filter_bar.tree = self.tree_sublot
        
        # v5.0.2: 컬럼 토글바에 treeview 연결 (v8.7.0: 초기 displaycolumns는 위에서 이미 적용)
        if hasattr(self, '_tonbag_toggle_bar') and self._tonbag_toggle_bar:
            self._tonbag_toggle_bar.tree = self.tree_sublot

        # ═══════════════════════════════════════════════════════════════
        # v5.5.2: 액션/통계 바 (재고 리스트와 동일 — 트리 아래, 재고 통계 바와 같은 스타일)
        # ═══════════════════════════════════════════════════════════════
        _tb_bg = ThemeColors.get('bg_secondary', _is_dark_tb)
        ThemeColors.get('bg_card', _is_dark_tb)
        ThemeColors.get('border', _is_dark_tb)
        ThemeColors.get('text_primary', _is_dark_tb)
        
        # v5.5.3 patch_04: ttk 프레임 전환 (테마 자동 대응)
        self._tonbag_stats_action_frame = ttk.Frame(self.tab_tonbag, padding=(Spacing.XS, Spacing.XS))
        self._tonbag_stats_action_frame.pack(fill=X, padx=Spacing.XS, pady=(0, Spacing.XS))

        _inner = ttk.Frame(self._tonbag_stats_action_frame)
        _inner.pack(fill=X, padx=Spacing.XS)

        # v7.3.7: 버튼 2그룹 재배치 — 주요(왼쪽) / 보조(오른쪽)
        btn_frame = ttk.Frame(_inner)
        btn_frame.pack(side=LEFT, fill=X, expand=True)

        # ── 주요 버튼 (왼쪽 3개) ──
        btn_primary = ttk.Frame(btn_frame)
        btn_primary.pack(side=LEFT)

        self.btn_tonbag_batch_outbound = ttk.Button(
            btn_primary, text="📤 일괄 출고",
            command=self._on_tonbag_batch_outbound,
            state='disabled'
        )
        self.btn_tonbag_batch_outbound.pack(side=LEFT, padx=(0, Spacing.XS))
        apply_tooltip(self.btn_tonbag_batch_outbound, '선택한 톤백들을 일괄 출고 처리')

        btn_tonbag_location = ttk.Button(
            btn_primary, text="📍 위치 업로드",
            command=self._on_tonbag_location_upload
        )
        btn_tonbag_location.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(btn_tonbag_location, '로케이션 테이블(LOT·톤백번호·위치)을 읽어 LOCATION 반영')

        self.btn_tonbag_copy_uid = ttk.Button(
            btn_primary, text="📋 UID 복사",
            command=self._on_tonbag_copy_uid,
            state='disabled'
        )
        self.btn_tonbag_copy_uid.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(self.btn_tonbag_copy_uid, '선택한 톤백의 UID를 클립보드에 복사')

        ttk.Separator(btn_frame, orient='vertical').pack(side=LEFT, fill='y', padx=Spacing.SM)

        self.lbl_tonbag_selection = ttk.Label(btn_frame, text="선택: 0개 | 합계: 0 kg")
        self.lbl_tonbag_selection.pack(side=LEFT, padx=Spacing.XS)

        # ── 보조 버튼 (오른쪽 3개) ──
        btn_secondary = ttk.Frame(btn_frame)
        btn_secondary.pack(side=RIGHT)

        self.btn_tonbag_cancel_outbound = ttk.Button(
            btn_secondary, text="↩️ 출고 취소",
            command=self._on_tonbag_cancel_outbound,
            state='disabled'
        )
        self.btn_tonbag_cancel_outbound.pack(side=RIGHT, padx=(Spacing.XS, 0))
        apply_tooltip(self.btn_tonbag_cancel_outbound, '선택한 판매화물 결정 톤백의 출고를 취소하고 재고 복구')

        self.btn_tonbag_label = ttk.Button(
            btn_secondary, text="🏷️ 라벨 출력",
            command=self._on_tonbag_print_label,
            state='disabled'
        )
        self.btn_tonbag_label.pack(side=RIGHT, padx=Spacing.XS)
        apply_tooltip(self.btn_tonbag_label, '선택한 톤백의 라벨을 PDF로 출력')

        btn_tonbag_export = ttk.Button(
            btn_secondary, text="📥 Excel",
            command=lambda: self._on_export_click(option=4)
        )
        btn_tonbag_export.pack(side=RIGHT, padx=Spacing.XS)
        apply_tooltip(btn_tonbag_export, '톤백 현황을 Excel 파일로 내보내기')
        
        # v5.7.5: 하단 요약 라벨(총/가용/출고) 제거

        search_frame = ttk.Frame(_inner)
        search_frame.pack(side=RIGHT)
        
        # STATUS = 전체 / 판매가능 / 판매배정 / 판매화물 결정 / 출고 5종, 개수 표시
        _lbl_status = ttk.Label(search_frame, text="상태:")
        _lbl_status.pack(side=LEFT, padx=(0, Spacing.XS))
        apply_tooltip(_lbl_status, "톤백 상태로 필터: 전체 / 판매가능 / 판매배정 / 판매화물 결정 / 출고. 괄호 안 숫자는 해당 개수.")
        self.tonbag_status_var = tk.StringVar(value="전체 (0)")
        self._sublot_status_combo = ttk.Combobox(
            search_frame, textvariable=self.tonbag_status_var,
            values=["전체 (0)", "판매가능 (0)", "판매배정 (0)", "판매화물 결정 (0)", "출고 (0)"],
            state="readonly", width=18
        )
        self._sublot_status_combo.pack(side=LEFT, padx=(0, Spacing.SM))
        self._sublot_status_combo.bind('<<ComboboxSelected>>', self._on_tonbag_filter)
        apply_tooltip(self._sublot_status_combo, "전체 / 판매가능 / 판매배정 / 판매화물 결정 / 출고 중 선택하면 목록이 해당 상태만 표시됩니다. 숫자는 현재 데이터 기준 개수.")
        
        self._show_sample_var = tk.BooleanVar(value=True)  # v5.6.1: 샘플 기본 표시
        self._chk_show_sample = ttk.Checkbutton(
            search_frame, text="🧪 샘플 표시",
            variable=self._show_sample_var,
            command=self._on_tonbag_filter_refresh
        )
        self._chk_show_sample.pack(side=LEFT, padx=(0, Spacing.SM))
        apply_tooltip(self._chk_show_sample, '샘플 톤백(sub_lt=0, 1kg) 표시/숨김 토글')
        
        # v5.5.3 patch_04: 검색 박스 ttk 전환
        search_box = ttk.Frame(search_frame)
        search_box.pack(side=LEFT)

        _lbl_search = ttk.Label(search_box, text='🔍')
        _lbl_search.pack(side=LEFT, padx=Spacing.XS)
        apply_tooltip(_lbl_search, "LOT NO, SAP NO, BL NO, 제품명, CONTAINER 등에 포함된 글자로 실시간 필터. 입력 시마다 목록이 갱신됩니다.")
        self.tonbag_search_var = tk.StringVar()
        self.tonbag_search_var.trace('w', self._on_tonbag_search)
        tonbag_search_entry = ttk.Entry(search_box, textvariable=self.tonbag_search_var,
                                         width=15)
        tonbag_search_entry.pack(side=LEFT, pady=Spacing.XS, padx=(0, Spacing.XS))
        apply_tooltip(tonbag_search_entry, "검색어 입력 시 LOT NO·SAP NO·BL NO·제품명·CONTAINER에서 해당 글자가 포함된 행만 표시됩니다.")

        # 기간 필터는 HeaderFilterBar 안에 STATUS와 초기화 사이에 통합됨 (v5.7.5)

        # ═══════════════════════════════════════════════════════════════
        # 하단 NET(Kg) 합계 바 (재고와 동일)
        # ═══════════════════════════════════════════════════════════════
        # v5.6.1: FooterTotalBar 제거 — lbl_sublot_summary 1줄로 통합
        # self._tb_footer = FooterTotalBar(self.tab_tonbag, is_dark=_is_dark_tb)
        # self._tb_footer.pack(fill=X, padx=5, pady=(0, 2))
        
        # 이벤트 바인딩
        self.tree_sublot.bind('<Double-1>', self._on_tonbag_double_click)
        self.tree_sublot.bind('<Button-3>', self._on_tonbag_right_click)  # v7.0.1: 우클릭 컨텍스트 메뉴
        self.tree_sublot.bind('<<TreeviewSelect>>', self._on_tonbag_select)
    
    def _on_tonbag_location_upload(self) -> None:
        """로케이션 테이블(엑셀/붙여넣기) → 톤백 리스트(lot_no·톤백번호 동일 행) location 반영 후 톤백 리스트 새로고침."""
        from ..dialogs.tonbag_location_upload import show_tonbag_location_upload_dialog
        def _after_upload():
            self._safe_refresh()
        show_tonbag_location_upload_dialog(self.root, self.engine, callback=_after_upload)
    
    def _on_tonbag_select(self, event=None) -> None:
        """톤백 선택 시 컨텍스트 버튼 활성화"""
        selection = self.tree_sublot.selection()
        count = len(selection)
        
        # 버튼 상태 업데이트
        state = 'normal' if count > 0 else 'disabled'
        if hasattr(self, 'btn_tonbag_batch_outbound'):
            self.btn_tonbag_batch_outbound.config(state=state)
        if hasattr(self, 'btn_tonbag_label'):
            self.btn_tonbag_label.config(state=state)
        # v3.8.4: 출고 취소 버튼
        if hasattr(self, 'btn_tonbag_cancel_outbound'):
            self.btn_tonbag_cancel_outbound.config(state=state)
        
        # 선택 정보 업데이트
        if hasattr(self, 'lbl_tonbag_selection'):
            total_kg = 0
            for item_id in selection:
                values = self.tree_sublot.item(item_id, 'values')
                if len(values) >= 10:
                    try:
                        total_kg += float(str(values[9]).replace(',', ''))  # NET(kg) index 9
                    except (ValueError, TypeError) as e:
                        logger.debug(f"{type(e).__name__}: {e}")
            self.lbl_tonbag_selection.config(text=f"선택: {count}개 | 합계: {total_kg:,.0f} kg")
    
    def _on_tonbag_batch_outbound(self) -> None:
        """선택된 톤백 일괄 출고"""
        selection = self.tree_sublot.selection()
        if not selection:
            return
        
        tonbag_list = []
        for item_id in selection:
            values = self.tree_sublot.item(item_id, 'values')
            if len(values) >= 3:
                # TONBAG NO = index 2; 샘플 표기 'S'/'S0'/'S00' → sub_lt 0
                raw = str(values[2]).strip().upper()
                try:
                    sub_lt = 0 if raw in ('S', 'S0', 'S00') else int(values[2])
                except (ValueError, TypeError):
                    sub_lt = 0 if raw in ('S', 'S0', 'S00') else 0
                tonbag_list.append({
                    'lot_no': values[1],   # LOT NO (index 1)
                    'sub_lt': sub_lt,
                })
        
        if tonbag_list:
            self._show_batch_tonbag_outbound_dialog(tonbag_list)
    
    def _show_batch_tonbag_outbound_dialog(self, tonbag_list: list) -> None:
        """일괄 톤백 출고 다이얼로그"""
        from ..utils.constants import tk, ttk
        from ..utils.ui_constants import Spacing
        
        from ..utils.ui_constants import apply_modal_window_options, setup_dialog_geometry_persistence
        dialog = create_themed_toplevel(self.root)
        dialog.title(f"일괄 출고 - {len(tonbag_list)}개 톤백")
        apply_modal_window_options(dialog)
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "batch_tonbag_outbound_dialog", self.root, "small")
        
        # 톤백 목록 표시
        ttk.Label(dialog, text=f"선택된 톤백: {len(tonbag_list)}개", 
                 font=('맑은 고딕', 18, 'bold')).pack(pady=Spacing.SM)
        
        listbox = tk.Listbox(dialog, height=8)
        for tb in tonbag_list:
            disp = '0' if tb['sub_lt'] == 0 else tb['sub_lt']
            listbox.insert('end', f"{tb['lot_no']} / {disp}")
        listbox.pack(fill='x', padx=Spacing.LG, pady=Spacing.XS)
        
        # 출고처 입력
        dest_frame = ttk.Frame(dialog)
        dest_frame.pack(fill='x', padx=Spacing.LG, pady=Spacing.SM)
        
        ttk.Label(dest_frame, text="출고처:").pack(side='left')
        dest_var = tk.StringVar()
        dest_entry = ttk.Entry(dest_frame, textvariable=dest_var, width=25)
        dest_entry.pack(side='left', padx=Spacing.SM)
        dest_entry.focus()
        
        # 버튼
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=Spacing.MD)
        
        def do_batch_outbound():
            destination = dest_var.get().strip()
            if not destination:
                CustomMessageBox.showwarning(self.root, "경고", "출고처를 입력하세요.")
                return
            
            success_count = 0
            for tb in tonbag_list:
                try:
                    result = self.engine.pick_tonbag(tb['lot_no'], tb['sub_lt'], destination)
                    if result.get('success'):
                        success_count += 1
                except (RuntimeError, ValueError) as _e:
                    logger.debug(f"Suppressed: {_e}")
            
            dialog.destroy()
            self._safe_refresh()
            CustomMessageBox.showinfo(
                self.root, "완료", 
                f"일괄 출고 완료\n\n성공: {success_count}/{len(tonbag_list)}개"
            )
        
        ttk.Button(btn_frame, text="일괄 출고", command=do_batch_outbound, width=12).pack(side='left', padx=Spacing.XS)
        ttk.Button(btn_frame, text="취소", command=dialog.destroy, width=12).pack(side='left', padx=Spacing.XS)
        
        dialog.bind('<Return>', lambda e: do_batch_outbound())
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def _on_tonbag_print_label(self) -> None:
        """선택된 톤백 라벨 출력"""
        selection = self.tree_sublot.selection()
        if not selection:
            return
        
        CustomMessageBox.showinfo(
            self.root, "라벨 출력", 
            f"선택된 {len(selection)}개 톤백의 라벨을 출력합니다.\n\n(기능 구현 예정)"
        )
    
    def _on_tonbag_search(self, *args) -> None:
        """톤백 검색"""
        self._refresh_tonbag()
    
    def _on_tonbag_filter(self, event=None) -> None:
        """톤백 상태 필터"""
        self._refresh_tonbag()
    
    def _setup_tonbag_lot_detail_panel(self) -> None:
        """톤백 탭 상세 패널: 선택 톤백의 LOT 내 톤백 목록"""
        from ..utils.constants import ttk, VERTICAL, BOTH, LEFT
        detail_container = self._tb_split_panel.get_detail_container()
        cols = ('sub_lt', 'weight', 'status', 'location', 'picked_to', 'outbound_date')
        # v8.1.5: tree + scrollbar wrapper
        tree_wrapper = ttk.Frame(detail_container)
        tree_wrapper.pack(fill=BOTH, expand=True)
        self._tb_lot_detail_tree = ttk.Treeview(
            tree_wrapper, columns=cols, show='headings', height=8
        )
        for cid, txt, w in [
            ('sub_lt', '톤백#', 60), ('weight', '중량(kg)', 90),
            ('status', '상태', 90), ('location', '위치', 80),
            ('picked_to', '출고처', 120), ('outbound_date', '출고일', 100)
        ]:
            self._tb_lot_detail_tree.heading(cid, text=txt, anchor='center')
            self._tb_lot_detail_tree.column(cid, width=w)
        sb = tk.Scrollbar(tree_wrapper, orient=VERTICAL, command=self._tb_lot_detail_tree.yview)
        sb_x = tk.Scrollbar(tree_wrapper, orient='horizontal', command=self._tb_lot_detail_tree.xview)
        self._tb_lot_detail_tree.configure(yscrollcommand=sb.set, xscrollcommand=sb_x.set)
        self._tb_lot_detail_tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb.pack(side='right', fill='y')
        sb_x.pack(side='bottom', fill='x')
        # v8.1.5: 합계 Footer
        from ..utils.constants import X
        self._tb_lot_detail_footer = TreeviewTotalFooter(
            detail_container, self._tb_lot_detail_tree,
            ['weight'],
            column_display_names={'weight': '중량(kg)'}
        )
        self._tb_lot_detail_footer.pack(fill=X)

    def _on_tonbag_selection_change(self, event) -> None:
        """톤백 선택 변경 → LOT 톤백 상세 패널 갱신"""
        sel = self.tree_sublot.selection()
        if not sel or not hasattr(self, '_tb_lot_detail_tree'):
            return
        item = self.tree_sublot.item(sel[0])
        vals = item.get('values', [])
        if len(vals) < 2:
            return
        lot_no = str(vals[1]).strip()
        if not lot_no:
            return
        self._tb_lot_detail_tree.delete(*self._tb_lot_detail_tree.get_children())
        self._tb_split_panel.set_detail_title(f"📦 LOT 톤백 상세 — {lot_no}")
        try:
            tonbags = self.engine.db.fetchall(
                """SELECT sub_lt, weight, status, location, picked_to, outbound_date
                   FROM inventory_tonbag WHERE lot_no = ? ORDER BY sub_lt""",
                (lot_no,)
            )
            for tb in (tonbags or []):
                st = get_status_display(tb.get('status')) or tb.get('status') or ''
                self._tb_lot_detail_tree.insert('', 'end', values=(
                    tb.get('sub_lt'), f"{(tb.get('weight') or 0):,.0f}",
                    st, tb.get('location') or '', tb.get('picked_to') or '',
                    str(tb.get('outbound_date') or '')[:10]
                ))
        except Exception as e:
            logger.debug(f"톤백 LOT 상세 로드: {e}")
        if hasattr(self, '_tb_lot_detail_footer'):
            self._tb_lot_detail_footer.update_totals()

    def _on_tonbag_filter_apply(self) -> None:
        """v5.0.2: 헤더 필터바 적용"""
        self._refresh_tonbag()
    
    def _on_tonbag_filter_refresh(self) -> None:
        """v3.9.5: 샘플 체크박스 변경 시 새로고침"""
        self._refresh_tonbag()

    def _sort_tonbag_treeview(self, col: str) -> None:
        """톤백 트리 헤더 클릭 시 오름차순/내림차순 정렬 (헤더 ▲▼ 표시)"""
        tree = self.tree_sublot
        if self._tonbag_sort_column == col:
            self._tonbag_sort_reverse = not self._tonbag_sort_reverse
        else:
            self._tonbag_sort_column = col
            self._tonbag_sort_reverse = False
        items = [(tree.set(item, col), item) for item in tree.get_children('')]
        numeric_cols = ['row_num', 'current_weight', 'net_weight', 'initial_weight', 'outbound_weight']
        if col in numeric_cols:
            sort_key = make_sort_key(col, numeric_cols)  # v7.0.0 [REFACTOR-1]
        items.sort(key=sort_key, reverse=self._tonbag_sort_reverse)
        for idx, (_, item) in enumerate(items):
            tree.move(item, '', idx)
        arrow = " ▼" if self._tonbag_sort_reverse else " ▲"
        for c_id, c_label, _, _, _ in self._tonbag_columns:
            tree.heading(
                c_id,
                text=f"{c_label}{arrow}" if c_id == col else c_label,
                anchor='center',
            )
    
    def _refresh_tonbag_list(self) -> None:
        """v8.7.0 [FIX G-1.2 CRITICAL]: outbound_handlers.py가 5지점에서 호출하던 alias.
        기존엔 정의 없어서 `if hasattr(self, '_refresh_tonbag_list')` 체크에 걸려 6지점 모두 silent skip.
        실제 refresh 로직은 _refresh_tonbag에 있으므로 여기로 위임.
        """
        try:
            self._refresh_tonbag()
        except Exception as e:
            logger.debug(f"[_refresh_tonbag_list] 위임 실패(무시): {e}")

    def _refresh_tonbag(self) -> None:
        """v3.8.9: 톤백 목록 새로고침 — 재고리스트 컬럼 + TONBAG NO"""
        from ..utils.ui_constants import ThemeColors
        
        if not hasattr(self, 'tree_sublot'):
            return
        # 트리뷰 초기화
        self.tree_sublot.delete(*self.tree_sublot.get_children())
        
        search_text = self.tonbag_search_var.get().strip().lower()
        status_filter = self.tonbag_status_var.get()
        
        try:
            # v3.8.9: JOIN 쿼리 — 재고(inventory) + 톤백(inventory_tonbag)
            if hasattr(self.engine, 'get_tonbags_with_inventory'):
                tonbags = self.engine.get_tonbags_with_inventory()
                # 재고는 있는데 톤백만 비어 있으면 JOIN/스키마 오류 가능 → 단순 톤백 조회 + LOT 정보 보강
                if not tonbags and hasattr(self.engine, 'get_inventory'):
                    inv_list = self.engine.get_inventory()
                    if inv_list:
                        raw = self.engine.get_tonbags() if hasattr(self.engine, 'get_tonbags') else getattr(self.engine, 'get_all_tonbags', lambda: [])()
                        inv_by_lot = {str(i.get('lot_no')): i for i in inv_list}
                        for tb in raw:
                            lot_no = tb.get('lot_no')
                            if lot_no and lot_no in inv_by_lot:
                                i = inv_by_lot[lot_no]
                                tb = dict(tb)
                                tb.setdefault('product', i.get('product'))
                                tb.setdefault('container_no', i.get('container_no'))
                                tb.setdefault('mxbg_pallet', i.get('mxbg_pallet'))
                                tb.setdefault('net_weight', i.get('net_weight'))
                                tb.setdefault('salar_invoice_no', i.get('salar_invoice_no'))
                                tb.setdefault('ship_date', i.get('ship_date'))
                                tb.setdefault('arrival_date', i.get('arrival_date'))
                                tb.setdefault('con_return', i.get('con_return'))
                                tb.setdefault('free_time', i.get('free_time'))
                                tb.setdefault('warehouse', i.get('warehouse'))
                                tb.setdefault('customs', i.get('customs'))
                                tb.setdefault('current_weight', i.get('current_weight'))
                                tb.setdefault('initial_weight', i.get('initial_weight'))
                                tb.setdefault('location', tb.get('location', '') or '')
                                tb['tonbag_status'] = tb.get('status', STATUS_AVAILABLE)
                                tonbags.append(tb)
                        if tonbags:
                            logger.warning("톤백 리스트: get_tonbags_with_inventory가 비어 있어 get_tonbags+LOT 보강으로 표시합니다. DB 스키마/JOIN 확인 권장.")
            if not tonbags and hasattr(self.engine, 'get_all_tonbags'):
                tonbags = self.engine.get_all_tonbags()
            if not tonbags:
                tonbags = []

            # STATUS 옵션별 개수: 전체 / 판매가능 / 판매배정 / 판매화물 결정 / 출고
            _cnt_total = _cnt_avail = _cnt_reserved = _cnt_picked = _cnt_sold = 0
            _show_sample = getattr(self, '_show_sample_var', None)
            for _tb in tonbags:
                if _tb.get('is_sample', 0) and _show_sample and not _show_sample.get():
                    continue
                _cnt_total += 1
                _st = _tb.get('tonbag_status', _tb.get('status', STATUS_AVAILABLE))
                if _st == STATUS_AVAILABLE:
                    _cnt_avail += 1
                elif _st == STATUS_RESERVED:
                    _cnt_reserved += 1
                elif _st == STATUS_PICKED:
                    _cnt_picked += 1
                elif _st == STATUS_SOLD:
                    _cnt_sold += 1
            if hasattr(self, '_sublot_status_combo'):
                self._sublot_status_combo['values'] = [
                    f"전체 ({_cnt_total})",
                    f"판매가능 ({_cnt_avail})",
                    f"판매배정 ({_cnt_reserved})",
                    f"판매화물 결정 ({_cnt_picked})",
                    f"출고 ({_cnt_sold})",
                ]
                _cur = self.tonbag_status_var.get()
                if _cur not in self._sublot_status_combo['values'] and self._sublot_status_combo['values']:
                    self.tonbag_status_var.set(self._sublot_status_combo['values'][0])

            # 상태 필터 정규화 (표시명 → DB 값)
            _raw = (status_filter or '').strip()
            if not _raw or _raw.startswith('전체'):
                status_filter_normalized = None
            elif '판매가능' in _raw:
                status_filter_normalized = STATUS_AVAILABLE
            elif '판매배정' in _raw:
                status_filter_normalized = STATUS_RESERVED
            elif '판매화물 결정' in _raw:
                status_filter_normalized = STATUS_PICKED
            elif '출고' in _raw:
                status_filter_normalized = STATUS_SOLD
            else:
                status_filter_normalized = _raw

            # v5.7.5: 기간(날짜 범위) — 루프 밖에서 한 번만 읽기
            _df = getattr(self, '_date_from_var', None)
            _dt = getattr(self, '_date_to_var', None)
            date_from = (_df.get().strip().replace('-', '') if _df else '')
            date_to = (_dt.get().strip().replace('-', '') if _dt else '')

            total_count = 0
            available_count = 0
            picked_count = 0
            _dk_tonbag = is_dark()
            ThemeColors.get('text_primary', _dk_tonbag)

            for tb in tonbags:
                lot_no = str(tb.get('lot_no', ''))
                sap_no_raw = str(tb.get('sap_no', ''))
                # 톤백 리스트 SAP NO: '-' 및 접미사 제거하여 표시 (예: 1125072729-S0 → 1125072729)
                sap_no = sap_no_raw.split('-')[0].strip() if '-' in sap_no_raw else sap_no_raw
                bl_no = str(tb.get('bl_no', ''))
                product = str(tb.get('product', ''))
                container = str(tb.get('container_no', ''))
                if hasattr(self, '_format_container_no'):
                    container = self._format_container_no(container)
                is_sample = tb.get('is_sample', 0)
                
                # v3.9.5: 샘플 필터 (체크박스 OFF면 샘플 숨김)
                show_sample = getattr(self, '_show_sample_var', None)
                if is_sample and show_sample and not show_sample.get():
                    continue
                
                # v4.0.8/v5.7.5: 샘플 톤백은 제품명 뒤 (S) 표기 — 짧게 표시
                if is_sample:
                    product = f"{product} (S)" if product else "(S)"
                
                # 검색 필터
                if search_text:
                    searchable = f"{lot_no} {sap_no} {bl_no} {product} {container}".lower()
                    if search_text not in searchable:
                        continue

                # v8.1.5: 기간 필터 — 재고 탭과 동일 기준일
                if date_from or date_to:
                    from ..utils.tree_enhancements import row_reference_date_ymd
                    ref_d = row_reference_date_ymd(tb)
                    if date_from and ref_d and ref_d < date_from:
                        continue
                    if date_to and ref_d and ref_d > date_to:
                        continue
                
                # 상태 필터 (전체 / 판매가능 / 판매배정 / 판매화물 결정 / 출고)
                status = tb.get('tonbag_status', tb.get('status', STATUS_AVAILABLE))
                if status_filter_normalized and status != status_filter_normalized:
                    continue
                
                # v5.0.2: 헤더 필터바 조건
                if hasattr(self, '_tonbag_filter_bar'):
                    tb_filters = self._tonbag_filter_bar.get_filters()
                    skip_fb = False
                    for fk, fv in tb_filters.items():
                        tv = str(tb.get(fk, '') or '')
                        if not tv and fk == 'status':
                            tv = status
                        if tv != fv:
                            skip_fb = True
                            break
                    if skip_fb:
                        continue
                
                total_count += 1
                
                # 상태별 태그
                if status == STATUS_AVAILABLE:
                    available_count += 1
                    tag = 'available'
                elif status in ('PICKED', 'SOLD'):
                    picked_count += 1
                    tag = 'picked'
                elif status == STATUS_RESERVED:
                    tag = 'reserved'
                elif status == 'SHIPPED':
                    tag = 'shipped'
                elif status == STATUS_DEPLETED:
                    tag = 'depleted'
                else:
                    tag = ''
                
                # 줄무늬
                row_idx = len(self.tree_sublot.get_children())
                tags = [tag] if tag else []
                if row_idx % 2 == 1 and not tag:
                    tags.append('stripe')
                
                # v3.9.0: 21열 값 구성
                row_num = len(self.tree_sublot.get_children()) + 1
                # v5.6.3: mxbg 제거 (톤백리스트에서 불필요)
                tonbag_no = tb.get('tonbag_no', tb.get('sub_lt', ''))
                
                # v5.9.0: TONBAG NO 표시 (샘플은 '0')
                tonbag_no_print = tonbag_no
                if is_sample:
                    tonbag_no_print = '0'
                
                location = tb.get('location', '') or ''
                
                # v5.7.1: NET/Balance/Inbound = 톤백 개별 무게만 사용 (LOT 총무게 net_weight 사용 금지)
                try:
                    tonbag_w = float(
                        tb.get('tonbag_weight', 0) or tb.get('weight', 0) or 0
                    )
                except (ValueError, TypeError):
                    tonbag_w = 0.0
                # Balance: tonbag_current_weight (쿼리 보강) 또는 status 기반
                _tb_current = tb.get('tonbag_current_weight')
                if _tb_current is not None and _tb_current != '':
                    try:
                        tb_balance = float(_tb_current)
                    except (ValueError, TypeError):
                        tb_balance = tonbag_w if status not in ('PICKED', 'SOLD', 'SHIPPED', 'DEPLETED') else 0.0
                else:
                    tb_balance = 0.0 if status in ('PICKED', 'SOLD', 'SHIPPED', 'DEPLETED') else tonbag_w
                # Inbound: tonbag_initial_weight 있으면 사용, 없으면 tonbag_w
                _tb_inbound = tb.get('tonbag_initial_weight')
                if _tb_inbound is not None and _tb_inbound != '':
                    try:
                        tonbag_inbound = float(_tb_inbound)
                    except (ValueError, TypeError):
                        tonbag_inbound = tonbag_w
                else:
                    tonbag_inbound = tonbag_w
                if status in ('PICKED', 'SOLD', 'SHIPPED', 'DEPLETED'):
                    tb_outbound = tonbag_w
                else:
                    tb_outbound = 0.0
                
                def _fmt(v):
                    try: return f"{float(v):,.0f}" if v else ''
                    except (ValueError, TypeError): return str(v) if v else ''
                
                # UID: DB의 tonbag_uid 사용, 공란 시 lot_no-0 / lot_no-sub_lt 로 표시
                _uid = (tb.get('tonbag_uid') or '').strip()
                if not _uid:
                    _sub = tb.get('sub_lt', tb.get('tonbag_no', ''))
                    if tb.get('is_sample') or _sub == 0 or _sub == '0' or _sub == 'S00':
                        _uid = f"{lot_no}-0"
                    else:
                        _uid = f"{lot_no}-{_sub}"
                # v5.8.8: _tonbag_columns 순서와 정확히 일치 (con_return 포함, 열 밀림 방지)
                _cr = tb.get('con_return', '') or ''
                if not _cr:
                    _arr = tb.get('arrival_date', '')
                    _ft = tb.get('free_time', '')
                    if _arr and _ft and str(_ft).isdigit():
                        try:
                            _adt = datetime.strptime(str(_arr)[:10], '%Y-%m-%d')
                            _rdt = _adt + timedelta(days=int(_ft))
                            _cr = _rdt.strftime('%Y-%m-%d')
                        except (ValueError, TypeError):
                            logger.debug("[SUPPRESSED] exception in tonbag_tab.py")  # noqa

                vals = (
                    str(row_num),                                    #  1. row_num (No.)
                    lot_no,                                          #  2. lot_no
                    str(tonbag_no_print),                            #  3. tonbag_no_print (TONBAG NO)
                    sap_no,                                          #  4. sap_no
                    bl_no,                                           #  5. bl_no
                    product,                                         #  6. product
                    get_status_display(status),  #  7. tonbag_status
                    _fmt(tb_balance),                                #  8. current_weight (Balance(Kg))
                    _uid,                                            #  9. tonbag_uid
                    container,                                       # 10. container_no
                    location,                                        # 11. location
                    _fmt(tonbag_w),                                  # 12. net_weight (NET(Kg))
                    tb.get('salar_invoice_no', '') or '',            # 13. salar_invoice_no
                    tb.get('ship_date', '') or '',                   # 14. ship_date
                    tb.get('arrival_date', '') or '',                # 15. arrival_date
                    _cr,                                            # 16. con_return (CON RETURN)
                    tb.get('free_time', '') or '',                  # 17. free_time
                    tb.get('warehouse', '') or '',                   # 18. warehouse
                    tb.get('customs', tb.get('customs_status', '')) or '',  # 19. customs
                    _fmt(tonbag_inbound),                            # 20. initial_weight (Inbound(Kg))
                    _fmt(tb_outbound) if tb_outbound > 0 else '0',   # 21. outbound_weight
                )
                
                self.tree_sublot.insert('', 'end', values=vals, tags=tuple(tags))
            
            # v6.3.2-colorful: 상태별 고유 전경색 (단일색 덮어쓰기 제거)
            _dk = is_dark()
            _fg = tc('text_primary') if _dk else '#1a1a1a'
            # v8.6.5: 대비 강화
            _sfg = {
                'available': '#6ee7b7' if _dk else '#064e3b',
                'reserved':  '#fcd34d' if _dk else '#78350f',
                'picked':    '#c4b5fd' if _dk else '#4c1d95',
                'shipped':   '#93c5fd' if _dk else '#0a2844',
            }
            self.tree_sublot.tag_configure('available',
                background=ThemeColors.get('available', _dk), foreground=_sfg['available'])
            self.tree_sublot.tag_configure('picked',
                background=ThemeColors.get('picked', _dk), foreground=_sfg['picked'])
            self.tree_sublot.tag_configure('reserved',
                background=ThemeColors.get('reserved', _dk), foreground=_sfg['reserved'])
            self.tree_sublot.tag_configure('shipped',
                background=ThemeColors.get('shipped', _dk), foreground=_sfg['shipped'])
            self.tree_sublot.tag_configure('depleted',
                background='#e8e8e8' if not _dk else '#1a1a2e',
                foreground='#666666' if not _dk else '#9a9ab0')
            self.tree_sublot.tag_configure('stripe',
                background=ThemeColors.get('tree_stripe', _dk), foreground=_fg)

            if hasattr(self, '_tonbag_total_footer') and self._tonbag_total_footer:
                self._tonbag_total_footer.update_totals()

            # v4.2.2: 테이블 스타일 줄무늬 새로고침
            try:
                from ..utils.table_styler import TableStyler
                TableStyler.refresh_striped_rows(self.tree_sublot)
            except (ImportError, Exception) as e:
                logger.debug(f"줄무늬 새로고침 실패: {e}")
                # Fallback: 기존 방식
                from ..utils.tree_enhancements import apply_striped_rows
                _dk2 = is_dark()
                apply_striped_rows(self.tree_sublot, is_dark=_dk2)
            
            # v4.0.6: 필터 드롭다운 값 업데이트
            self._update_tb_filter_values(tonbags)
            
            # v5.6.1: FooterTotalBar 제거
            # self._update_tb_footer()
            
        except (RuntimeError, ValueError) as e:
            logger.error(f"톤백 조회 오류: {e}", exc_info=True)
            self._log(f"⚠️ 톤백 조회 오류: {e}")

    # ═══════════════════════════════════════════════════════
    # v4.0.6: 톤백 필터바 / 합계바 메서드
    # ═══════════════════════════════════════════════════════
    
    def _update_tb_filter_values(self, tonbags) -> None:
        """v5.5.2: 톤백 필터 드롭다운 값 업데이트 (단일 필터바 = 재고와 동일 컬럼)"""
        if not hasattr(self, '_tonbag_filter_bar'):
            return
        try:
            cols = {'lot_no': [], 'sap_no': [], 'bl_no': [], 'container_no': [],
                    'product': [], 'tonbag_status': []}
            for tb in tonbags:
                for c in cols:
                    val = str(tb.get(c, '') or '')
                    if not val and c == 'tonbag_status':
                        val = str(tb.get('status', '') or '')
                    if val:
                        cols[c].append(val)
            for c, vals in cols.items():
                self._tonbag_filter_bar.update_filter_values(c, vals)
        except (ValueError, TypeError) as e:
            logger.debug(f"톤백 필터 값 오류: {e}")
    
    def _update_tb_footer(self) -> None:
        """v4.0.6: 톤백 하단 합계 바"""
        if not hasattr(self, '_tb_footer'):
            return
        try:
            net_total = 0.0
            balance_total = 0.0
            rows = 0
            for item_id in self.tree_sublot.get_children(''):
                vals = self.tree_sublot.item(item_id, 'values')
                rows += 1
                # NET(Kg) = index 9, Balance(Kg) = index 17 (톤백 20열 기준)
                try:
                    net_total += float(str(vals[9]).replace(',', ''))
                except (ValueError, TypeError, IndexError) as _e:
                    logger.debug(f"Suppressed: {_e}")
                try:
                    balance_total += float(str(vals[17]).replace(',', ''))
                except (ValueError, TypeError, IndexError) as _e:
                    logger.debug(f"Suppressed: {_e}")
            self._tb_footer.update({
                'rows': rows, 'net_kg': net_total, 'balance_kg': balance_total,
            })
        except (ValueError, TypeError) as e:
            logger.debug(f"톤백 footer 오류: {e}")
    
    def _on_tonbag_double_click(self, event) -> None:
        """톤백 더블클릭 - 수동 출고"""
        selection = self.tree_sublot.selection()
        if not selection:
            return
        
        item = self.tree_sublot.item(selection[0])
        values = item['values']
        
        if len(values) >= 17:
            lot_no = values[1]   # LOT NO (col 2, index 1)
            raw_tb = str(values[2]).strip().upper()
            try:
                sub_lt = 0 if raw_tb in ('S', 'S0', 'S00') else int(values[2])
            except (ValueError, TypeError):
                sub_lt = 0
            status = values[16]  # STATUS (index 16); values[15]=WH(창고)
            
            if status == STATUS_AVAILABLE:
                self._show_manual_outbound_dialog(lot_no, sub_lt)
            else:
                CustomMessageBox.showinfo(self.root, "알림", f"이 톤백은 현재 {status} 상태입니다.")
    
    def _show_manual_outbound_dialog(self, lot_no: str, sub_lt: str) -> None:
        """수동 출고 다이얼로그"""
        from ..utils.constants import tk, ttk
        from ..utils.ui_constants import (
            Spacing, FontScale, center_dialog, setup_dialog_geometry_persistence
        )
        
        # === UI 통일성: 폰트 스케일 ===
        try:
            dpi = self.root.winfo_fpixels('1i')
        except (ImportError, ModuleNotFoundError):
            dpi = 96
        fonts = FontScale(dpi)
        
        # === UI 통일성: 다이얼로그 크기 저장/복원 ===
        dialog = create_themed_toplevel(self.root)
        dialog.title(f"수동 출고 - {lot_no}/{sub_lt}")
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "manual_tonbag_outbound_dialog", self.root, "small")
        
        # === UI 통일성: 간격 표준화 ===
        # 정보 표시
        info_frame = ttk.Frame(dialog, padding=Spacing.MD)
        info_frame.pack(fill='x')
        
        ttk.Label(info_frame, text=f"LOT NO: {lot_no}", font=fonts.body()).pack(anchor='w')
        ttk.Label(info_frame, text=f"톤백 NO: {sub_lt if sub_lt != 0 else '0'}", font=fonts.body()).pack(anchor='w')
        
        # 출고처 입력
        dest_frame = ttk.Frame(dialog, padding=(Spacing.MD, 0, Spacing.MD, Spacing.SM))
        dest_frame.pack(fill='x')
        
        ttk.Label(dest_frame, text="출고처:", font=fonts.body()).pack(side='left')
        dest_var = tk.StringVar()
        dest_entry = ttk.Entry(dest_frame, textvariable=dest_var, width=30)
        dest_entry.pack(side='left', padx=Spacing.SM)
        dest_entry.focus()
        
        # 버튼
        btn_frame = ttk.Frame(dialog, padding=Spacing.MD)
        btn_frame.pack(fill='x')
        
        def do_outbound():
            destination = dest_var.get().strip()
            if not destination:
                CustomMessageBox.showwarning(self.root, "경고", "출고처를 입력하세요.")
                return
            
            try:
                result = self.engine.pick_tonbag(lot_no, sub_lt, destination)
                if result.get('success'):
                    CustomMessageBox.showinfo(self.root, "완료", f"출고 처리 완료\n\n{lot_no}/{sub_lt} → {destination}")
                    dialog.destroy()
                    self._safe_refresh()
                else:
                    CustomMessageBox.showerror(self.root, "오류", result.get('message', '출고 처리 실패'))
            except (RuntimeError, ValueError) as e:
                CustomMessageBox.showerror(self.root, "오류", f"출고 처리 오류: {e}")
        
        ttk.Button(btn_frame, text="출고 처리", command=do_outbound, width=12).pack(side='left', padx=Spacing.XS)
        ttk.Button(btn_frame, text="취소", command=dialog.destroy, width=12).pack(side='left', padx=Spacing.XS)
        
        # === UI 통일성: 중앙 배치 ===
        center_dialog(dialog, self.root)
        
        # Enter 키 바인딩, ESC로 닫기
        dialog.bind('<Return>', lambda e: do_outbound())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def _on_tonbag_cancel_outbound(self) -> None:
        """v3.8.4: 선택한 톤백 출고 취소 (inventory 복구 포함)"""
        from ..utils.custom_messagebox import CustomMessageBox
        
        selection = self.tree_sublot.selection()
        if not selection:
            CustomMessageBox.showwarning(self.root, "선택 필요", "출고 취소할 톤백을 선택하세요.")
            return
        
        # PICKED 상태만 필터
        cancel_items = []
        for item_id in selection:
            values = self.tree_sublot.item(item_id)['values']
            if len(values) >= 17:
                status = str(values[16]).strip()  # STATUS (index 16); values[15]=WH
                if status == STATUS_PICKED:
                    # TONBAG NO = index 2; 샘플 'S'/'S0'/'S00' → sub_lt 0
                    raw = str(values[2]).strip().upper()
                    try:
                        sub_lt = 0 if raw in ('S', 'S0', 'S00') else int(values[2])
                    except (ValueError, TypeError):
                        sub_lt = 0 if raw in ('S', 'S0', 'S00') else 0
                    cancel_items.append({
                        'lot_no': str(values[1]),
                        'sub_lt': sub_lt,
                    })
        
        if not cancel_items:
            CustomMessageBox.showwarning(self.root, "대상 없음", 
                "선택한 항목 중 PICKED 상태인 톤백이 없습니다.")
            return
        
        if not CustomMessageBox.askyesno(self.root, "출고 취소 확인",
            f"{len(cancel_items)}건의 출고를 취소하시겠습니까?\n\n"
            f"톤백 상태: PICKED → AVAILABLE\n"
            f"LOT 잔량이 자동 복구됩니다."):
            return
        
        try:
            if hasattr(self.engine, 'cancel_outbound_bulk'):
                result = self.engine.cancel_outbound_bulk(cancel_items)
            else:
                # Fallback: 개별 처리
                result = {'success': True, 'cancelled': 0, 'errors': []}
                for item in cancel_items:
                    r = self.engine.cancel_outbound_tonbag(item['lot_no'], item['sub_lt'])
                    if r.get('success'):
                        result['cancelled'] += 1
                    else:
                        result['errors'].extend(r.get('errors', []))
                result['success'] = result['cancelled'] > 0
            
            if result.get('success'):
                self._log(f"✅ 출고 취소 완료: {result['cancelled']}건")
                CustomMessageBox.showinfo(self.root, "완료", 
                    f"출고 취소 완료: {result['cancelled']}건\n재고가 복구되었습니다.")
                self._safe_refresh()
            else:
                errs = '\n'.join(result.get('errors', ['알 수 없는 오류']))
                CustomMessageBox.showerror(self.root, "오류", f"출고 취소 실패:\n{errs}")
                
        except (RuntimeError, ValueError) as e:
            logger.error(f"출고 취소 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"출고 취소 오류:\n{e}")

    def _on_tonbag_copy_uid(self) -> None:
        """v4.2.0: 선택한 톤백의 UID를 클립보드에 복사"""
        from ..utils.custom_messagebox import CustomMessageBox
        
        selection = self.tree_sublot.selection()
        if not selection:
            CustomMessageBox.showwarning(self.root, "선택 필요", "복사할 톤백을 선택하세요.")
            return
        
        # UID 수집 (tonbag_uid는 4번째 컬럼, 0-based index 3)
        uid_list = []
        for item_id in selection:
            values = self.tree_sublot.item(item_id)['values']
            if len(values) > 3:
                uid = str(values[3]).strip()  # tonbag_uid (index 3)
                if uid and uid != '':
                    uid_list.append(uid)
        
        if not uid_list:
            CustomMessageBox.showwarning(self.root, "UID 없음", 
                "선택한 톤백에 UID가 없습니다.\n(마이그레이션 필요)")
            return
        
        # 클립보드에 복사 (줄바꿈으로 구분)
        clipboard_text = '\n'.join(uid_list)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(clipboard_text)
            self.root.update()  # 클립보드 즉시 반영
            
            self._log(f"📋 UID 복사 완료: {len(uid_list)}개")
            CustomMessageBox.showinfo(self.root, "복사 완료", 
                f"{len(uid_list)}개의 UID가 클립보드에 복사되었습니다.\n\n"
                f"Excel에 Ctrl+V로 붙여넣으세요.")
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"클립보드 복사 오류: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"클립보드 복사 실패:\n{e}")

    def _on_tonbag_selection_changed(self, event=None) -> None:
        """v4.2.0: 톤백 선택 변경 시 버튼 활성화/비활성화 (UID 복사 포함)"""
        selection = self.tree_sublot.selection()
        has_selection = len(selection) > 0
        
        # 일괄 출고 버튼
        if hasattr(self, 'btn_tonbag_batch_outbound'):
            self.btn_tonbag_batch_outbound.config(state='normal' if has_selection else 'disabled')
        
        # 출고 취소 버튼
        if hasattr(self, 'btn_tonbag_cancel_outbound'):
            self.btn_tonbag_cancel_outbound.config(state='normal' if has_selection else 'disabled')
        
        # 라벨 출력 버튼
        if hasattr(self, 'btn_tonbag_label'):
            self.btn_tonbag_label.config(state='normal' if has_selection else 'disabled')
        
        # v4.2.0: UID 복사 버튼
        if hasattr(self, 'btn_tonbag_copy_uid'):
            self.btn_tonbag_copy_uid.config(state='normal' if has_selection else 'disabled')
        
        # 선택 정보 업데이트
        if has_selection and hasattr(self, 'lbl_tonbag_selection'):
            total_weight = 0
            for item_id in selection:
                values = self.tree_sublot.item(item_id)['values']
                try:
                    # v5.6.3: NET(Kg) = index 9 (MXBG 제거 후 20열 기준)
                    w = float(str(values[9]).replace(',', '')) if len(values) > 9 else 0
                    total_weight += w
                except (ValueError, IndexError) as _e:
                    logger.debug(f"tonbag_tab: {_e}")
            self.lbl_tonbag_selection.config(
                text=f"선택: {len(selection)}개 | 합계: {total_weight:,.0f} kg")
        elif hasattr(self, 'lbl_tonbag_selection'):
            self.lbl_tonbag_selection.config(text="선택: 0개 | 합계: 0 kg")
    

    # ═══════════════════════════════════════════════════════
    # v7.0.1: 톤백 우클릭 컨텍스트 메뉴 — 위치 변경
    # ═══════════════════════════════════════════════════════
    
    def _on_tonbag_right_click(self, event) -> None:
        """톤백 우클릭 — 컨텍스트 메뉴 표시"""
        from ..utils.constants import tk

        # 클릭 위치의 아이템 선택
        item_id = self.tree_sublot.identify_row(event.y)
        if not item_id:
            return
        self.tree_sublot.selection_set(item_id)

        # lot_no 추출 (컬럼 인덱스 1)
        values = self.tree_sublot.item(item_id).get('values', [])
        lot_no = str(values[1]).strip() if len(values) > 1 else ''

        # 컨텍스트 메뉴 생성
        popup = tk.Menu(self.root, tearoff=0)
        popup.add_command(label="📍 위치 변경", command=self._on_tonbag_edit_location)
        popup.add_separator()
        popup.add_command(label="📋 UID 복사", command=self._on_tonbag_copy_uid)
        popup.add_separator()
        popup.add_command(label="↩️ 출고 취소", command=self._on_tonbag_cancel_outbound)
        popup.add_separator()
        popup.add_command(
            label="🔄 반품 (재입고)",
            command=lambda: self._on_tonbag_return(lot_no),
        )

        try:
            popup.tk_popup(event.x_root, event.y_root)
        finally:
            popup.grab_release()

    def _on_tonbag_return(self, lot_no: str) -> None:
        """
        톤백 우클릭 반품 처리 — RETURN_AS_REINBOUND 정책 (v7.0.0).

        inventory_tab._return_from_context 와 동일한 흐름:
          1. outbound_log 최근 출고 조회
          2. ReturnReinboundDialog 호출
          3. 성공 시 tonbag 뷰 자동 갱신
        """
        if not lot_no:
            return

        try:
            from gui_app_modular.dialogs.return_dialog import ReturnReinboundDialog
        except ImportError:
            logger.error("[v7.0.0] ReturnReinboundDialog import 실패 (tonbag_tab)")
            return

        # 최근 출고 이력 조회
        ob = self.engine.db.fetchone(
            """SELECT outbound_id, customer
               FROM outbound_log
               WHERE lot_no = ?
               ORDER BY rowid DESC LIMIT 1""",
            (lot_no,)
        )

        if not ob:
            logger.warning(f"[v7.0.0] 출고 이력 없음 (tonbag_tab): {lot_no}")
            return

        outbound_id = ob.get('outbound_id') or ob['outbound_id']
        customer    = ob.get('customer', '')

        # DB raw connection 추출
        raw_conn = getattr(self.engine.db, '_local', None)
        if raw_conn:
            raw_conn = getattr(raw_conn, 'conn', None)
        if raw_conn is None:
            raw_conn = getattr(self.engine.db, '_conn', None)
        if raw_conn is None:
            logger.error("[v7.0.0] DB raw connection 추출 실패 (tonbag_tab)")
            return

        def _on_success(return_id: str, new_location: str) -> None:
            self._log(
                f"✅ 반품 완료 | {lot_no} | {return_id} | 위치: {new_location}"
            )
            if hasattr(self, '_refresh_tonbag_list'):
                self._refresh_tonbag_list()
            elif hasattr(self, 'refresh'):
                self.refresh()

        ReturnReinboundDialog(
            parent=self.root,
            db_conn=raw_conn,
            outbound_id=outbound_id,
            lot_no=lot_no,
            customer=customer,
            on_success=_on_success,
            current_theme=getattr(self, 'current_theme', 'darkly'),
        )
    
    def _on_tonbag_edit_location(self) -> None:
        """v7.0.1: 톤백 개별 위치 변경 다이얼로그"""
        from ..utils.constants import tk, ttk
        from ..utils.ui_constants import (
            Spacing, FontScale, center_dialog
        )
        from ..utils.custom_messagebox import CustomMessageBox
        
        selection = self.tree_sublot.selection()
        if not selection:
            CustomMessageBox.showinfo(self.root, "알림", "위치를 변경할 톤백을 선택하세요.")
            return
        
        item = self.tree_sublot.item(selection[0])
        values = item['values']
        
        if len(values) < 17:
            return
        
        lot_no = str(values[1])
        raw_tb = str(values[2]).strip().upper()
        try:
            sub_lt = 0 if raw_tb in ('S', 'S0', 'S00') else int(values[2])
        except (ValueError, TypeError):
            sub_lt = 0
        
        # 현재 위치 — 컬럼 인덱스 확인
        current_loc = ''
        try:
            # tree_sublot 컬럼 순서에서 location 위치 찾기
            cols = self.tree_sublot['columns']
            if 'location' in cols:
                loc_idx = list(cols).index('location')
                current_loc = str(values[loc_idx]) if loc_idx < len(values) else ''
                if current_loc.lower() in ('none', 'nan', ''):
                    current_loc = ''
        except (ValueError, IndexError):
            current_loc = ''
        
        # === 다이얼로그 생성 ===
        try:
            dpi = self.root.winfo_fpixels('1i')
        except Exception:
            dpi = 96
        fs = FontScale(dpi)
        
        from ..utils.ui_constants import apply_modal_window_options as _apply_modal
        dlg = create_themed_toplevel(self.root)
        dlg.title(f"📍 위치 변경 — {lot_no}-{sub_lt}")
        dlg.transient(self.root)
        dlg.grab_set()
        _apply_modal(dlg)
        
        frame = ttk.Frame(dlg, padding=Spacing.LG)
        frame.pack(fill='both', expand=True)
        
        # 정보 표시
        info_frame = ttk.LabelFrame(frame, text="톤백 정보", padding=Spacing.MD)
        info_frame.pack(fill='x', pady=(0, Spacing.MD))
        
        ttk.Label(info_frame, text=f"LOT: {lot_no}", font=('', fs.body)).pack(anchor='w')
        ttk.Label(info_frame, text=f"톤백 번호: {sub_lt}", font=('', fs.body)).pack(anchor='w')
        ttk.Label(info_frame, text=f"현재 위치: {current_loc or '(미지정)'}", font=('', fs.body)).pack(anchor='w')
        
        # ④ 새 위치 입력
        loc_frame = ttk.LabelFrame(frame, text="새 위치", padding=Spacing.MD)
        loc_frame.pack(fill='x', pady=(0, Spacing.MD))

        ttk.Label(loc_frame, text="형식: A-01-01-01 (구역-열-층-칸)",
                  font=('', fs.small)).pack(anchor='w')

        var_location = tk.StringVar(value=current_loc)
        ent_location = ttk.Entry(loc_frame, textvariable=var_location,
                                 font=('', fs.body), width=25)
        ent_location.pack(fill='x', pady=(Spacing.XS, 0))
        ent_location.focus_set()
        ent_location.select_range(0, 'end')

        # ③ ④ 사유코드 드롭다운 (VALID_MOVE_REASONS — v6.6.0 §7)
        reason_frame = ttk.LabelFrame(frame, text="이동 사유 ★ 필수", padding=Spacing.MD)
        reason_frame.pack(fill='x', pady=(0, Spacing.MD))

        REASON_LABELS = {
            'RELOCATE':        '일반 재배치',
            'RACK_REPAIR':     '랙 수리',
            'INVENTORY_AUDIT': '재고 실사',
            'PICKING_OPT':     '피킹 최적화',
            'RETURN_PUTAWAY':  '반품 적치',
            'CORRECTION':      '위치 보정',
            'OTHER':           '기타 (비고 필수)',
        }
        reason_opts = [f"{v} ({k})" for k, v in REASON_LABELS.items()]
        var_reason = tk.StringVar(value=reason_opts[0])
        cb_reason = ttk.Combobox(reason_frame, textvariable=var_reason,
                                 values=reason_opts, state='readonly',
                                 font=('', fs.body), width=28)
        cb_reason.pack(fill='x', pady=(Spacing.XS, 0))

        # 비고 (OTHER 선택 시 필수)
        note_frame = ttk.LabelFrame(frame, text="비고 (OTHER 선택 시 필수)", padding=Spacing.MD)
        note_frame.pack(fill='x', pady=(0, Spacing.MD))

        var_note = tk.StringVar()
        ent_note = ttk.Entry(note_frame, textvariable=var_note,
                             font=('', fs.body), width=35)
        ent_note.pack(fill='x')

        # 버튼
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')

        def do_update():
            new_loc = var_location.get().strip().upper()
            if not new_loc:
                CustomMessageBox.showwarning(dlg, "경고", "새 위치를 입력하세요.")
                return

            # 사유 코드 파싱 (예: "일반 재배치 (RELOCATE)" → "RELOCATE")
            sel = var_reason.get()
            import re as _re
            m = _re.search(r'\(([A-Z_]+)\)', sel)
            reason_code = m.group(1) if m else 'RELOCATE'
            note = var_note.get().strip()

            # OTHER 사유 → note 강제
            if reason_code == 'OTHER' and not note:
                CustomMessageBox.showwarning(dlg, "경고",
                    "기타(OTHER) 선택 시 비고를 입력하세요.")
                ent_note.focus_set()
                return

            # ④ 이중 확인 팝업
            confirm_msg = (
                f"톤백 이동을 진행하시겠습니까?\n\n"
                f"LOT: {lot_no}  톤백: {sub_lt}\n"
                f"이동: [{current_loc or '미지정'}] → [{new_loc}]\n"
                f"사유: {sel}"
            )
            if not CustomMessageBox.askyesno(dlg, "이동 확인", confirm_msg):
                return

            result = self.engine.update_tonbag_location(
                lot_no, sub_lt, new_loc,
                source='MANUAL',
                reason_code=reason_code,
                operator=getattr(self, '_current_user', 'GUI'),
                note=note,
            )
            if result['success']:
                from_loc = result.get('from_location', '')
                msg = (f"✅ 위치 변경 완료\n\n"
                       f"{lot_no}-{sub_lt}\n"
                       f"[{from_loc}] → [{new_loc}]\n"
                       f"사유: {REASON_LABELS.get(reason_code, reason_code)}\n\n"
                       f"📋 이동 이력이 stock_movement에 기록되었습니다.")
                CustomMessageBox.showinfo(dlg, "완료", msg)
                dlg.destroy()
                self._refresh_tonbag()
            else:
                err = result.get('error', '알 수 없는 오류')
                CustomMessageBox.showerror(dlg, "오류", f"위치 변경 실패:\n{err}")

        ttk.Button(btn_frame, text="✅ 변경", command=do_update,
                   style='success.TButton').pack(side='right', padx=Spacing.XS)
        ttk.Button(btn_frame, text="취소", command=dlg.destroy).pack(side='right', padx=Spacing.XS)
        
        # Enter 키 바인딩
        ent_location.bind('<Return>', lambda e: do_update())
        dlg.bind('<Escape>', lambda e: dlg.destroy())
        
        center_dialog(dlg, self.root, width=350, height=280)
