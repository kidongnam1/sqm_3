"""
SQM v3.8.4 — 원스톱 입고 팝업
4종 서류(PL, Invoice, BL, DO)를 한 화면에서:
  파일 선택 → 체크 표시 → 파싱 → 미리보기 → DB 업로드

작성일: 2025-02-06
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
from engine_modules.constants import CARRIER_OPTIONS, STATUS_AVAILABLE
# v8.0.6 [MULTI-TEMPLATE] 다중 템플릿 후보 엔진 연결
try:
    from features.parsers.onestop_inbound_candidate_patch import (
        parse_bl_with_candidate,
        parse_do_with_candidate,
    )
    _HAS_CANDIDATE_ENGINE = True
except ImportError:
    _HAS_CANDIDATE_ENGINE = False
import os
import time
import json
import tkinter as tk
from tkinter import ttk, filedialog, BOTH, YES, X, Y, LEFT, RIGHT, BOTTOM, END, VERTICAL, HORIZONTAL
import logging
from engine_modules.constants import DEFAULT_TONBAG_WEIGHT  # v8.6.1
import threading
from datetime import datetime, timedelta, date as _date_type
from copy import deepcopy

# 비즈니스 기본값
from core.constants import DEFAULT_WAREHOUSE

from ..utils.ui_constants import (
    ThemeColors, DialogSize, center_dialog, apply_modal_window_options,
    setup_dialog_geometry_persistence, is_dark,
)
from core.types import safe_float
from ..utils.tree_enhancements import HeaderFilterBar

# v5.8.7: DatePicker 달력 UI — gui_bootstrap 통일 (ttkbootstrap.DateEntry, 없으면 텍스트 입력 폴백)
from ..utils.gui_bootstrap import DateEntry, HAS_DATEENTRY

logger = logging.getLogger(__name__)
ENABLE_PARSE_CONFIRM = False  # v8.1.x: 파싱 결과 확인 팝업 비활성화


def _dbg_log(tag: str = "", location: str = "", message: str = "", data=None) -> None:
    # v8.6.4: 프로덕션 debug 파일 쓰기 제거 → logger.debug
    # v8.7.0 [FIX]: 호출부가 (tag, location, message, data) 4-arg을 쓰고 있어 시그니처 정합
    logger.debug(f'[DBG:{tag}] {location} — {message} | {data}')


# 미리보기 컬럼 정의 — 종전 4개 파일 입고 테이블(재고 탭)과 동일한 열 순서
PREVIEW_COLUMNS = [
    ("no",               "NO",               50,  "center"),
    ("lot_no",           "LOT NO",          110,  "center"),
    ("sap_no",           "SAP NO",          110,  "center"),
    ("bl_no",            "BL NO",           150,  "center"),
    ("product",          "PRODUCT",         180,  "center"),
    ("status",           "STATUS",           80,  "center"),
    ("container_no",     "CONTAINER",       130,  "center"),
    ("product_code",     "CODE",            100,  "center"),
    ("lot_sqm",          "LOT SQM",          80,  "center"),
    ("mxbg_pallet",      "MXBG",             70,  "center"),
    ("net_weight",       "NET(Kg)",          90,  "center"),
    ("gross_weight",     "GROSS(kg)",         90,  "center"),
    ("salar_invoice_no", "INVOICE NO",      120,  "center"),
    ("ship_date",        "SHIP DATE",        90,  "center"),
    ("arrival_date",     "ARRIVAL",          90,  "center"),
    ("con_return",       "CON RETURN",       95,  "center"),
    ("free_time",        "FREE TIME",        80,  "center"),
    ("warehouse",        "WH",              100,  "center"),
]

# v7.4.0: 서류 순서 BL→PL→INV→DO (BL 먼저 → 선사 감지 → 맞춤 힌트 적용)
DOC_TYPES = [
    ('BL',           '① Bill of Loading (선하증권)', True),
    ('PACKING_LIST', '② Packing List (포장명세서)', True),
    ('INVOICE',      '③ Invoice, FA (송장)',        True),
    ('DO',           '④ Delivery Order (인도지시서) (선택사항)', False),
]


from .inbound_dialog_base import InboundDialogBase
from .inbound_upload_mixin import InboundUploadMixin

# v5.7.5: 진행률 팝업 조정 — 업로드2: 창·폰트 더 키움
PROGRESS_POPUP_WIDTH = 880
PROGRESS_POPUP_HEIGHT = 380
PROGRESS_POPUP_CLOSE_DELAY_MS = 1600


class OneStopInboundDialog(InboundUploadMixin, InboundDialogBase):
    """v3.8.4 원스톱 입고 팝업
    
    하나의 팝업에서:
    1. 4종 파일 선택 (각각 [파일 선택] 버튼 + ✅ 체크)
    2. [파싱 시작] → 프로그레스 바
    3. 18열 미리보기 테이블
    4. [DB 업로드] 또는 [Excel 내보내기]
    """
    
    def __init__(self, parent, engine, log_fn=None, app=None):
        self.parent = parent
        self.engine = engine
        self.app = app  # v3.8.8: 메인 앱 참조 (새로고침용)
        self._log = log_fn or (lambda msg, **kw: logger.info(msg))
        
        # 파일 경로 저장
        self.file_paths = {}  # {doc_type: file_path}
        self._last_selected_dir = ""
        
        # 파싱 결과
        self.parsed_results = {}
        self.preview_data = []
        
        # 업로드 결과
        self.upload_success = False
        # v5.8.9: 컨테이너 번호 접미사(-숫자) 디폴트 숨김, 필요 시 표시
        self._show_container_suffix = False
        # 파싱 결과 팝업에서 DB 업로드 선택 시, 완료 후 엑셀 내보내기 여부 질의
        self._ask_excel_after_upload = False
        
        # UI 참조
        self.dialog = None
        self.file_labels = {}
        self.check_labels = {}
        self.tree = None
        self.btn_parse = None
        self.btn_reparse = None
        self.btn_upload = None
        self.btn_excel = None
        self.btn_undo = None
        self.btn_redo = None
        self.btn_reset_original = None
        self.filter_bar = None
        self._var_upload_by_view_order = None
        self._editing_item = None
        self._preview_anchor = (0, 0)  # (row_idx, col_idx)
        self._edited_rows = set()
        self._undo_stack = []
        self._redo_stack = []
        self._max_history = 50
        self._sort_col = None
        self._sort_desc = False
        self._view_indices = []
        self._original_preview_data = []
        # v6.4.0: 빠른 PDF 스캔 자동 파싱 플래그 (show() 호출 전 기본값)
        self._auto_start_parse   = False
        self._skip_parse_confirm = False
        # v6.4.0 PATCH_PACKAGE: compact 모드 — 원스톱 창은 작게, 파싱 결과는 메인 창에만 표시
        # v8.7.0 [FIX]: 미리보기가 다이얼로그 내부에서 안 보이는 문제 해결 위해 기본값 False로 전환.
        #   compact_mode=True였을 때는 파싱 결과가 메인 창에만 반영되어 사용자가 입고 다이얼로그
        #   안에서 검증이 불가능했음. 이제 다이얼로그 하단에 미리보기 테이블 표시.
        self.compact_mode = False
        self._compact_tree_frame = None
    
    def show(
        self,
        initial_files: dict = None,
        auto_start_parse: bool = False,
        skip_parse_confirm: bool = False,
    ) -> None:
        """팝업 표시.
        initial_files      : { 'DO': 경로 } 등 드래그앤드롭/캡처 이미지 사전 지정.
        auto_start_parse   : True 이면 팝업이 열리자마자 파싱 자동 시작 (빠른 폴더 스캔).
        skip_parse_confirm : True 이면 파싱 시작 확인 팝업 생략.
        """
        self._initial_files      = initial_files or {}
        self._auto_start_parse   = bool(auto_start_parse)
        self._skip_parse_confirm = bool(skip_parse_confirm)
        logger.info(
            "OneStopInboundDialog.show(files=%s, auto_start=%s, skip_confirm=%s)",
            list((initial_files or {}).keys()),
            auto_start_parse,
            skip_parse_confirm,
        )
        # 초기 파일이 있으면 해당 폴더를 다음 파일 선택의 시작 폴더로 사용
        try:
            for _p in self._initial_files.values():
                if _p and os.path.exists(_p):
                    _d = os.path.dirname(_p)
                    if _d and os.path.isdir(_d):
                        self._last_selected_dir = _d
                        break
        except Exception as e:
            logger.debug(f"초기 폴더 경로 설정 무시: {e}")
        self._create_dialog()
    
    def _attach_doc_tooltip(self, widget, text: str):
        """v3.8.9: 문서 위젯에 툴팁 추가.

        v8.7.0 [UX]:
          • 위치: 위젯 왼쪽 위 11시 방향 (기존 마우스 커서 +15,+10 → 4시 방향이라 버튼 가림)
          • 자동 숨김 3초
          • 클릭 시 즉시 숨김
        """
        tip = None
        hide_after = None

        def _destroy():
            nonlocal tip, hide_after
            if hide_after:
                try:
                    widget.after_cancel(hide_after)
                except Exception as _e:
                    logger.debug(f"tooltip hide cancel: {_e}")
                hide_after = None
            if tip:
                try:
                    tip.destroy()
                except Exception as _e:
                    logger.debug(f"tooltip destroy: {_e}")
                tip = None

        def enter(_e):
            nonlocal tip, hide_after
            _destroy()
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            _od = is_dark()
            lbl = tk.Label(tip, text=text, justify='left',
                          background=ThemeColors.get('bg_card', _od),
                          foreground=ThemeColors.get('text_primary', _od),
                          relief='solid', borderwidth=1,
                          font=('맑은 고딕', 11), padx=10, pady=6,
                          wraplength=520)
            lbl.pack()

            # v8.7.0: 11시 방향 멀리 배치
            try:
                tip.update_idletasks()
                tw = tip.winfo_reqwidth()
                th = tip.winfo_reqheight()
                wx = widget.winfo_rootx()
                wy = widget.winfo_rooty()
                sw = widget.winfo_screenwidth()
                sh = widget.winfo_screenheight()
                x = wx - tw - 30
                y = wy - th - 20
                if x < 0:
                    x = max(0, wx - tw + 24)
                if y < 0:
                    y = wy + widget.winfo_height() + 8
                if x + tw > sw:
                    x = sw - tw - 2
                if y + th > sh:
                    y = sh - th - 2
                tip.wm_geometry(f"+{x}+{y}")
            except Exception as _e:
                logger.debug(f"tooltip geometry: {_e}")

            # 3초 자동 숨김
            try:
                hide_after = widget.after(3000, _destroy)
            except Exception as _e:
                logger.debug(f"tooltip schedule: {_e}")

        def leave(_e):
            _destroy()

        widget.bind('<Enter>', enter, add='+')
        widget.bind('<Leave>', leave, add='+')
        widget.bind('<Button-1>', lambda _e: _destroy(), add='+')
        widget.bind('<Button-3>', lambda _e: _destroy(), add='+')
    

    # =========================================================================
    # v7.0.0: _create_dialog 분리 — 4개 서브메서드 (테스트 가시성 확보)
    # =========================================================================
    def _build_inbound_doc_frame(self, main) -> None:
        """문서 파일 선택 프레임 (PL/INV/BL/DO + 파싱 버튼)"""
        self._build_inbound_doc_frame_impl(main)

    def _build_inbound_progress_frame(self, main) -> None:
        """진행 상태 프레임 (⏱ 파싱 진행 표시)"""
        self._build_inbound_progress_frame_impl(main)

    def _build_inbound_preview_frame(self, main) -> None:
        """미리보기 프레임 (📊 Treeview)"""
        self._build_inbound_preview_frame_impl(main)

    def _build_inbound_button_frame(self, main) -> None:
        """버튼 프레임 (업로드/취소/내보내기 등)"""
        self._build_inbound_button_frame_impl(main)


    def _build_inbound_doc_frame_impl(self, main) -> None:
        pass  # 실제 구현은 _create_dialog 본문에 포함

    def _build_inbound_progress_frame_impl(self, main) -> None:
        pass

    def _build_inbound_preview_frame_impl(self, main) -> None:
        pass

    def _build_inbound_button_frame_impl(self, main) -> None:
        pass

    def _create_dialog(self) -> None:
        """원스톱 입고 팝업 생성"""
        self.dialog = create_themed_toplevel(self.parent)
        try:
            from version import __version__ as _sqm_ver
        except ImportError:
            _sqm_ver = "8.1.1"
        self.dialog.title(f"📥 입고 — SQM v{_sqm_ver}")
        apply_modal_window_options(self.dialog)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        if getattr(self, 'compact_mode', False):
            # compact: 미리보기는 메인 창에만 — 단, 진행/버튼 행은 표시되도록 최소 높이 확보 + 상하 크기 조절 허용
            self.dialog.geometry("1180x560")
            self.dialog.minsize(900, 420)
            self.dialog.resizable(True, True)
            center_dialog(self.dialog, self.parent)
        else:
            self.dialog.minsize(720, 520)
            try:
                sw = self.parent.winfo_screenwidth()
                sh = self.parent.winfo_screenheight()
                # v8.1.6: 서류 4줄 세로 배치에 맞춰 기본 창 확대
                w = min(1320, int(sw * 0.82))
                h = min(900, int(sh * 0.88))
                x = (sw - w) // 2
                y = max(30, (sh - h) // 2)
                self.dialog.geometry(f"{w}x{h}+{x}+{y}")
            except Exception as e:
                logger.warning(f"[UI] dialog geometry calculation failed: {e}")
                self.dialog.geometry(DialogSize.get_geometry(self.parent, 'large'))
                center_dialog(self.dialog, self.parent)
            setup_dialog_geometry_persistence(self.dialog, "onestop_inbound_dialog", self.parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        main = ttk.Frame(self.dialog, padding=6)
        main.pack(fill=BOTH, expand=YES)

        # ═══════════════════════════════════════════════════════════
        # v8.3.3 [UX] 상단 진행 단계 표시 — Flexport 스타일
        # ═══════════════════════════════════════════════════════════
        _is_dark = is_dark()
        _bg      = ThemeColors.get('bg_secondary', _is_dark)
        _accent  = ThemeColors.get('accent',       _is_dark)
        _muted   = ThemeColors.get('text_muted',   _is_dark)
        _border  = ThemeColors.get('border',       _is_dark)
        _text    = ThemeColors.get('text_primary',  _is_dark)

        step_fr = tk.Frame(main, bg=_bg, pady=6)
        step_fr.pack(fill=X, pady=(0, 6))

        STEPS = [
            ('①', '서류 선택', '파일 업로드'),
            ('②', '파싱 실행', 'AI 분석'),
            ('③', '결과 확인', '미리보기'),
            ('④', 'DB 저장',   '입고 완료'),
        ]
        step_fr.columnconfigure(tuple(range(len(STEPS) * 2 - 1)), weight=1)
        for col_i, (num, title, sub) in enumerate(STEPS):
            col = col_i * 2
            cell = tk.Frame(step_fr, bg=_bg)
            cell.grid(row=0, column=col, padx=8)
            # 단계 번호 원형 배지
            tk.Label(
                cell, text=num,
                bg=_accent if col_i == 0 else _bg,
                fg='#0f172a' if col_i == 0 else _muted,
                font=('맑은 고딕', 11, 'bold'),
                width=3, relief='flat',
            ).pack(side=LEFT, padx=(0, 4))
            # 단계 텍스트
            txt_fr = tk.Frame(cell, bg=_bg)
            txt_fr.pack(side=LEFT)
            tk.Label(
                txt_fr, text=title,
                bg=_bg,
                fg=_accent if col_i == 0 else _text,
                font=('맑은 고딕', 10, 'bold' if col_i == 0 else 'normal'),
            ).pack(anchor='w')
            tk.Label(
                txt_fr, text=sub,
                bg=_bg, fg=_muted,
                font=('맑은 고딕', 8),
            ).pack(anchor='w')
            # 구분 화살표
            if col_i < len(STEPS) - 1:
                tk.Label(
                    step_fr, text='›',
                    bg=_bg, fg=_muted,
                    font=('', 16),
                ).grid(row=0, column=col + 1)

        self._step_labels = [
            step_fr.grid_slaves(row=0, column=i*2)[0]
            for i in range(len(STEPS))
            if step_fr.grid_slaves(row=0, column=i*2)
        ]
        self._step_fr_ref  = step_fr
        self._step_bg      = _bg
        self._step_accent  = _accent
        self._step_muted   = _muted
        self._step_text    = _text
        self._current_step = 0

        # ─── 구분선 ───────────────────────────────────────────────
        tk.Frame(main, bg=_border, height=1).pack(fill=X, pady=(0, 6))

        # ═══════════════════════════════════════════════════════════
        # 1. 선사/템플릿 선택 (v8.7.0: 서류 파싱 전에 진행)
        # ═══════════════════════════════════════════════════════════
        # ── v8.0.0 [TEMPLATE-TABLE]: 파싱 템플릿 선택 — 테이블 방식 ──────────
        _tpl_row = ttk.Frame(main)
        _tpl_row.pack(fill=X, pady=(0, 2))
        _os_dark_tpl = is_dark()

        # 숨김 콤보: StringVar·values만 사용 (선사 콤보+팝업으로 템플릿 선택)
        self._tpl_var = tk.StringVar(value='')
        self._tpl_combo = ttk.Combobox(
            self.dialog, textvariable=self._tpl_var, state='readonly', width=1
        )
        self._tpl_combo.bind('<<ComboboxSelected>>', self._on_template_selected)

        ttk.Label(
            _tpl_row, text="적용 템플릿:",
            font=('맑은 고딕', 11, 'bold'),
            foreground=ThemeColors.get('text_primary', _os_dark_tpl)
        ).pack(side=LEFT, padx=(4, 4))

        # 선택된 템플릿 요약 (선사·이름·톤백·BL형식)
        self._tpl_selected_lbl = ttk.Label(
            _tpl_row, text="(미선택)",
            font=('맑은 고딕', 11), foreground=tc('text_muted')
        )
        self._tpl_selected_lbl.pack(side=LEFT, padx=(0, 8))

        # v9.0: D/O 나중에 버튼 → _tpl_row로 이동
        ttk.Separator(_tpl_row, orient='vertical').pack(
            side=LEFT, fill='y', padx=(8, 8), pady=2
        )
        self.btn_add_do_later = ttk.Button(
            _tpl_row, text="📋 D/O 나중에",
            command=self._on_add_do_later,
            state='normal', width=20
        )
        self.btn_add_do_later.pack(side=LEFT, padx=2)

        # 선사 콤보/뱃지 공용 — _load_template_combo()가 _apply_template_to_carrier_badge에서 참조
        self._inbound_template_data: dict = {}
        self._carrier_manual_var = tk.StringVar(value='UNKNOWN')

        # ── v6.4.0: 선사 뱃지 행 (BL 파싱 후 선사 정보 표시) ──────────────
        _carrier_row = ttk.Frame(main)
        _carrier_row.pack(fill=X, pady=(0, 2))
        _os_dark2 = is_dark()
        _lbl_ship = ttk.Label(
            _carrier_row,
            text="🚢 선사:",
            font=('맑은 고딕', 12, 'bold'),
            foreground=ThemeColors.get('text_primary', _os_dark2)
        )
        _lbl_ship.pack(side=LEFT, padx=(4, 4))
        # v8.1.6: 선사 콤보 선택 → 해당 carrier_id 템플릿만 테이블 팝업
        self._carrier_pick_combo = ttk.Combobox(
            _carrier_row,
            textvariable=self._carrier_manual_var,
            values=list(CARRIER_OPTIONS),
            state='readonly',
            width=16,
            font=('맑은 고딕', 11),
        )
        self._carrier_pick_combo.pack(side=LEFT, padx=(0, 8))
        self._carrier_pick_combo.bind(
            '<<ComboboxSelected>>', self._on_carrier_combo_selected)
        self._attach_doc_tooltip(
            self._carrier_pick_combo,
            "선사를 고르면 해당 선사로 등록된 파싱 템플릿만 팝업됩니다.\n"
            "목록에서 템플릿을 고른 뒤 [선택 확인]을 누르세요.\n"
            "취소하면 이전 선사 선택으로 돌아갑니다.",
        )
        # v8.1.5: 선사 뱃지 클릭 → 파싱 템플릿 표(선사·단가 포함) 바로 열기
        self._carrier_label = tk.Label(
            _carrier_row,
            text="  뱃지 클릭: 템플릿 목록  ",
            font=('맑은 고딕', 12, 'bold'),
            fg=tc('badge_text'),
            bg=tc('bg_secondary'),
            relief="flat", padx=8, pady=2, bd=0, cursor="hand2",
        )
        self._carrier_label.pack(side=LEFT, padx=(0, 8))
        self._carrier_label.bind(
            '<Button-1>', lambda _e: self._show_template_table_picker_for_current_carrier())
        self._attach_doc_tooltip(
            self._carrier_label,
            "클릭하면 현재 콤보 선사 기준으로 템플릿 목록이 열립니다.\n"
            "(선사가 UNKNOWN이면 전체 템플릿)\n"
            "위 드롭다운에서 선사를 고르면 해당 선사 템플릿만 자동으로 팝업됩니다."
        )

        # v8.7.0: 🚢 선사 재파싱 버튼 — 선사 콤보와 같은 줄에 배치
        self.btn_reparse_carrier = ttk.Button(
            _carrier_row, text="🚢 선사 재파싱",
            command=self._reparse_after_carrier_change,
            state='disabled', width=14,
        )
        self.btn_reparse_carrier.pack(side=LEFT, padx=(0, 10))
        self._attach_doc_tooltip(
            self.btn_reparse_carrier,
            "🚢 선사 뱃지로 템플릿을 바꾼 뒤, BL/PL/Invoice/DO를 해당 선사로 다시 파싱합니다.\n"
            "템플릿에 선사·톤백 단가가 함께 적용됩니다.",
        )

        # 파싱 템플릿 초기 로드 (_carrier_label 생성 후에 호출해야 뱃지 동기화 정상 동작)
        self._load_template_combo()

        # ═══════════════════════════════════════════════════════════
        # 2. 입고서류 선택 — 4종 서류 세로 4줄 + 파싱 버튼 줄 (v8.1.6)
        # ═══════════════════════════════════════════════════════════
        file_frame = ttk.Frame(main)
        file_frame.pack(fill=BOTH, expand=False, pady=(0, 4))

        doc_list = ttk.Frame(file_frame)
        doc_list.pack(fill=X, pady=(0, 6))
        doc_list.columnconfigure(0, weight=1)

        _doc_meta = {d[0]: d for d in DOC_TYPES}
        # 화면 표시 순서: ① BL → ② PL → ③ Invoice/FA → ④ DO (DOC_TYPES·파싱 순서와 동일)
        _ui_doc_order = [
            ('BL', '① Bill of Loading'),
            ('PACKING_LIST', '② Packing List'),
            ('INVOICE', '③ Invoice, FA'),
            ('DO', '④ Delivery Order'),
        ]

        # v3.8.9: 서류별 상세 툴팁 — v5.7.5: Invoice/FA, Bill of Loading, Delivery Order
        _tooltips = {
            'PACKING_LIST': '📦 Packing List (포장명세서)\n\n• LOT번호, 제품명, 수량, 중량 정보 추출\n• 필수 서류 — 없으면 입고 불가\n• PDF 또는 Excel 파일 지원',
            'INVOICE':      '📑 Invoice, FA (송장)\n\n• SAP번호, 단가, 총금액 정보 추출\n• 필수 서류 — 없으면 SAP번호 누락\n• PDF 파일 지원',
            'BL':           '🚢 Bill of Loading (선하증권)\n\n• BL번호, 선박명, 출항일, 도착일 추출\n• 필수 서류 — 없으면 선적 정보 누락\n• PDF 파일 지원',
            'DO':           '📋 Delivery Order (인도지시서)\n\n• 인도 장소, Free Time 정보 추출\n• 선택 서류 — 없어도 입고 가능\n• PDF 파일 지원',
        }

        _os_dark = is_dark()
        _bg_card   = ThemeColors.get('bg_card',      _os_dark)
        _bg_hover  = ThemeColors.get('bg_hover',      _os_dark)
        _border_c  = ThemeColors.get('border',        _os_dark)
        _accent_c  = ThemeColors.get('accent',        _os_dark)
        _txt_pri   = ThemeColors.get('text_primary',  _os_dark)
        _txt_muted = ThemeColors.get('text_muted',    _os_dark)
        _success_c = ThemeColors.get('success',       _os_dark)

        # 서류 타입별 아이콘 + 색상
        _doc_icons = {
            'BL':           ('🚢', '#0e7490'),   # Cyan-700
            'PACKING_LIST': ('📦', '#166534'),   # Green-800
            'INVOICE':      ('📑', '#92400e'),   # Amber-800
            'DO':           ('📋', '#1e3a5f'),   # Blue-900
        }

        for row_i, (doc_type, short_lbl) in enumerate(_ui_doc_order):
            _, doc_name, required = _doc_meta[doc_type]
            icon, icon_bg = _doc_icons.get(doc_type, ('📄', '#334155'))

            # ── 카드형 컨테이너 ──────────────────────────────────
            card = tk.Frame(
                doc_list,
                bg=_bg_card,
                highlightbackground=_border_c,
                highlightthickness=1,
                pady=4, padx=6,
            )
            card.grid(row=row_i, column=0, sticky='ew', pady=(0, 4))
            card.columnconfigure(3, weight=1)

            # 아이콘 배지
            tk.Label(
                card, text=icon,
                bg=icon_bg, fg='#ffffff',
                font=('', 14), width=2, pady=2,
            ).grid(row=0, column=0, sticky='w', padx=(0, 8))

            # 서류명 + 필수/선택 태그
            label_fr = tk.Frame(card, bg=_bg_card)
            label_fr.grid(row=0, column=1, sticky='w', padx=(0, 8))
            tk.Label(
                label_fr, text=short_lbl,
                bg=_bg_card, fg=_txt_pri,
                font=('맑은 고딕', 11, 'bold'),
            ).pack(side=LEFT)
            _req_text  = ' 필수' if required else ' 선택'
            _req_color = '#dc2626' if required else _txt_muted   # Red-600 / muted
            tk.Label(
                label_fr, text=_req_text,
                bg=_bg_card, fg=_req_color,
                font=('맑은 고딕', 10),
            ).pack(side=LEFT, padx=(4, 0))

            # 파일 선택 버튼
            btn_sel = tk.Button(
                card, text='📂 파일 선택',
                command=lambda dt=doc_type: self._select_file(dt),
                font=('맑은 고딕', 10),
                bg=ThemeColors.get('btn_neutral', _os_dark),
                fg=ThemeColors.get('badge_text', _os_dark),
                activebackground=_bg_hover,
                padx=8, pady=3, cursor='hand2', bd=0,
                relief='flat',
            )
            btn_sel.grid(row=0, column=2, sticky='w', padx=(0, 8))
            _req_str = '(필수)' if required else '(선택)'
            self._attach_doc_tooltip(btn_sel, f"클릭하여 {doc_name} 파일 선택 {_req_str}")

            # 체크 아이콘 (선택 전: ○  선택 후: ✓)
            check_label = tk.Label(
                card, text='○',
                bg=_bg_card, fg=_txt_muted,
                font=('맑은 고딕', 13, 'bold'),
            )
            check_label.grid(row=0, column=3, sticky='e', padx=(0, 8))
            self.check_labels[doc_type] = check_label

            # 파일명 표시
            file_label = tk.Label(
                card, text='',
                bg=_bg_card, fg=_accent_c,
                font=('맑은 고딕', 10), anchor='w',
            )
            file_label.grid(row=0, column=4, sticky='ew')
            card.columnconfigure(4, weight=1)
            self.file_labels[doc_type] = file_label

            # 파일 선택 시 체크 → ✓ + 초록색으로 변경
            def _make_select_cmd(dt=doc_type, card_ref=card,
                                  chk=check_label, flbl=file_label):
                orig_cmd = lambda: self._select_file(dt)
                def _wrapped():
                    orig_cmd()
                    if self.file_paths.get(dt):
                        chk.config(text='✓', fg=_success_c)
                        card_ref.config(
                            highlightbackground=_success_c
                        )
                return _wrapped
            btn_sel.config(command=_make_select_cmd())

            # 툴팁
            self._attach_doc_tooltip(card, _tooltips.get(doc_type, ''))

        # 드래그앤드롭/캡처 이미지 등 초기 파일 지정
        for doc_type, path in getattr(self, '_initial_files', {}).items():
            if doc_type in self.file_labels and path:
                self.file_paths[doc_type] = path
                self.file_labels[doc_type].configure(text=os.path.basename(path))
                self.check_labels[doc_type].configure(text="✓", fg=_success_c)

        actions = ttk.Frame(file_frame)
        actions.pack(fill=X, pady=(4, 0))

        # v8.5.9: 📁 멀티 선택 버튼 — Ctrl+클릭으로 BL/PL/FA/DO 한번에 선택
        self.btn_folder = ttk.Button(
            actions, text="📁 멀티 선택",
            command=self._select_folder,
            width=13,
        )
        self.btn_folder.pack(side=LEFT, padx=(0, 6))
        self._attach_doc_tooltip(
            self.btn_folder,
            "Ctrl+클릭으로 BL·PL·FA·DO 파일을 한번에 선택합니다.\n"
            "파일명/내용 기반으로 서류 유형을 자동 감지합니다.",
        )

        self.btn_parse = ttk.Button(
            actions, text="▶  파싱 시작",
            command=self._start_parsing,
            state='disabled', width=14,
            style='Accent.TButton',
        )
        self.btn_parse.pack(side=LEFT, padx=(0, 6))
        self._attach_doc_tooltip(
            self.btn_parse,
            "선택한 서류를 분석합니다\n\n• Bill of Loading → BL번호, 선박, 일정 추출\n"
            "• Packing List → LOT, 수량, 중량 추출\n"
            "• Invoice, FA → SAP번호, 금액 추출\n"
            "• Delivery Order → 인도장소, Free Time 추출",
        )

        self.btn_reparse = ttk.Button(
            actions, text="↻ 다시 파싱",
            command=self._reparse_with_current_files,
            state='disabled', width=11,
        )
        self.btn_reparse.pack(side=LEFT, padx=(0, 6))
        self._attach_doc_tooltip(
            self.btn_reparse,
            "이미 선택한 동일 파일로 재파싱합니다.\n파일을 다시 선택하지 않아도 됩니다.",
        )

        # v8.7.0: 🚢 선사 재파싱 버튼은 선사 행(_carrier_row)으로 이동됨

        self.parse_hint = ttk.Label(
            actions, text="",
            foreground=tc('text_primary'), font=('맑은 고딕', 12),
        )
        self.parse_hint.pack(side=LEFT, fill=X, expand=True, padx=(4, 0))
        self._update_parse_hint()
        
        # v6.5.0: 빠른 폴더 스캔 자동 파싱 — 3단계 안전 타이밍
        #   1) update_idletasks() — 모든 pending UI 이벤트 즉시 처리
        #   2) after_idle()       — 이벤트 루프가 완전히 idle 상태 확인
        #   3) after(500)         — Windows 렌더링 여유 시간 500ms 확보
        if getattr(self, '_auto_start_parse', False):
            def _deferred_start():
                try:
                    if self.dialog and self.dialog.winfo_exists():
                        self._log("⚡ 자동 파싱 시작 (빠른 스캔 모드)")
                        self.dialog.after(500, self._start_parsing)
                except Exception as _e:
                    logger.warning("자동 파싱 예약 실패: %s", _e)
            try:
                self.dialog.update_idletasks()
                self.dialog.after_idle(_deferred_start)
            except Exception as e:
                logger.warning(f"[UI] deferred start scheduling failed: {e}")

        # v8.7.0: 선사/템플릿 선택 블록은 입고서류 위로 이동됨 (중복 제거)

        # v5.7.5: 프로그레스 (팝업 + 인라인)
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")
        self._progress_popup = None
        self._progress_popup_label = None
        self._progress_popup_bar = None
        
        # ═══════════════════════════════════════════════════════════
        # 1.5 진행 상태 (미리보기 위에 고정 — 진행/데이터 혼동 방지)
        # ═══════════════════════════════════════════════════════════
        _pop_dark = is_dark()
        progress_section = ttk.LabelFrame(main, text="⏱ 진행 상태", padding=8)
        progress_section.pack(fill=X, pady=(6, 4))
        self._progress_inline_placeholder = ttk.Label(
            progress_section, text="파싱을 시작하면 진행 상황이 여기에 표시됩니다.",
            font=('맑은 고딕', 11), foreground=ThemeColors.get('text_muted', _pop_dark))
        self._progress_inline_placeholder.pack(anchor='w')
        self._progress_inline_frame = ttk.Frame(progress_section)
        # 아래에서 pack하지 않음 — 파싱 시작 시 pack, 완료 후 forget
        self._progress_inline_msg = ttk.Label(self._progress_inline_frame, text="", font=('맑은 고딕', 12, 'bold'))
        self._progress_inline_msg.pack(anchor='w')
        _ps = ttk.Style()
        _ps.configure('Inline.Horizontal.TProgressbar', troughcolor=ThemeColors.get('bg_secondary', _pop_dark), thickness=12)
        self._progress_bar_container = ttk.Frame(self._progress_inline_frame)
        self._progress_bar_container.pack(fill=X, pady=(4, 2))
        self._progress_inline_bar = ttk.Progressbar(self._progress_bar_container, maximum=100, mode='determinate', style='Inline.Horizontal.TProgressbar')
        self._progress_inline_bar.pack(fill=X)
        self._progress_inline_busy = ttk.Label(self._progress_bar_container, text="진행 중 ●", font=('맑은 고딕', 10),
                                               foreground=ThemeColors.get('statusbar_icon_warn', _pop_dark))
        self._progress_inline_busy.place(relx=0, rely=0.5, anchor='w')
        _row2 = ttk.Frame(self._progress_inline_frame)
        _row2.pack(fill=X)
        self._progress_inline_pct_elapsed = ttk.Label(_row2, text="", font=('맑은 고딕', 10), foreground=ThemeColors.get('text_secondary', _pop_dark))
        self._progress_inline_pct_elapsed.pack(side=tk.RIGHT)
        
        # ═══════════════════════════════════════════════════════════
        # 2. 미리보기 테이블 — compact_mode에서는 생성 생략, 결과는 메인 창에만 표시
        # ═══════════════════════════════════════════════════════════
        _tree_dark = is_dark()
        self._var_show_container_suffix = tk.BooleanVar(value=False)
        if not getattr(self, 'compact_mode', False):
            self._tree_frame_visible = False
            tree_frame = ttk.LabelFrame(main, text="📊 미리보기 (스케일링·처리된 데이터)", padding=4)
            self._tree_frame = tree_frame
            import tkinter.font as tkfont
            preview_font = tkfont.Font(family='맑은 고딕', size=11)
            _ = tkfont.Font(family='맑은 고딕', size=10, weight='bold')  # heading_font reserved
            row_height = preview_font.metrics('linespace') + 6
            _tree_fg = ThemeColors.get('text_primary', _tree_dark)
            style = ttk.Style()
            style.configure('Preview.Treeview',
                            font=('맑은 고딕', 11),
                            rowheight=row_height,
                            foreground=_tree_fg,
                            fieldbackground=ThemeColors.get('bg_card', _tree_dark))
            style.configure('Preview.Treeview.Heading',
                            font=('맑은 고딕', 10, 'bold'), anchor='center')
            columns = tuple(col[0] for col in PREVIEW_COLUMNS)
            self.tree = ttk.Treeview(
                tree_frame, columns=columns, show="headings",
                height=18, selectmode='extended',
                style='Preview.Treeview'
            )
            # v8.6.4: 파싱 결과 수동 편집 활성화 (더블클릭 + Ctrl+C/V)
            self.tree._enable_global_editable = True
            self.tree._on_tree_data_changed = self._sync_tree_edit_to_preview_data
            self.tree.tag_configure('odd', background=ThemeColors.get('tree_stripe', _tree_dark), foreground=_tree_fg)
            self.tree.tag_configure('even', background=ThemeColors.get('bg_card', _tree_dark), foreground=_tree_fg)
            self.tree.tag_configure('edited', background=ThemeColors.get('warning', _tree_dark), foreground=_tree_fg)
            self.tree.tag_configure('xc_critical', background=tc('picked'), foreground=tc('danger'))
            self.tree.tag_configure('xc_warning', background=tc('picked'), foreground=tc('warning'))
            self.tree.tag_configure('xc_info', background=tc('reserved'), foreground=tc('text_muted'))
            for col_id, header, width, anchor in PREVIEW_COLUMNS:
                self.tree.heading(
                    col_id, text=header, anchor='center',
                    command=lambda c=col_id: self._toggle_preview_sort(c))
                self.tree.column(col_id, width=width, anchor=anchor, minwidth=35)
            scrollbar_y = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
            scrollbar_x = ttk.Scrollbar(tree_frame, orient=HORIZONTAL, command=self.tree.xview)
            self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
            scrollbar_x.pack(side=BOTTOM, fill=X)
            self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
            scrollbar_y.pack(side=RIGHT, fill=Y)
            self._setup_preview_edit_bindings()
            chk_container = ttk.Checkbutton(
                tree_frame, text="컨테이너 번호 접미사(-숫자) 표시",
                variable=self._var_show_container_suffix,
                command=self._on_toggle_container_suffix
            )
            chk_container.pack(anchor='w', padx=4, pady=(2, 0))
            self.filter_bar = HeaderFilterBar(
                main, self.tree,
                filter_columns=[
                    ('sap_no', 'SAP', 120),
                    ('bl_no', 'BL', 120),
                    ('container_no', 'CONTAINER', 120),
                    ('product', 'PRODUCT', 140),
                    ('status', 'STATUS', 90),
                ],
                on_filter=self._on_change_preview_filter,
                is_dark=_tree_dark
            )
            self.filter_bar.pack(fill=X, pady=(2, 2))
            # v8.7.0 [FIX]: tree_frame을 다이얼로그에 즉시 배치
            #   이전엔 _show_preview_table() 호출을 통해 pack하도록 설계됐으나
            #   _show_preview_table() 호출 경로가 코드베이스 어디에도 없어 영구 숨김 상태였음.
            #   compact_mode=False일 때는 항상 미리보기 테이블을 보이게 한다.
            try:
                tree_frame.pack(fill=BOTH, expand=YES, pady=(0, 3))
                self._tree_frame_visible = True
            except Exception as _pe:
                logger.warning(f"[UI] tree_frame pack failed: {_pe}")
        else:
            self.tree = None
            self.filter_bar = None
            self._tree_frame = None
            self._tree_frame_visible = False
        
        self._build_inbound_action_buttons(main, _tree_dark)
    
    # ═══════════════════════════════════════════════════════════
    # 4. 하단 한 줄 — 액션 버튼 (v8.1.3: _create_dialog에서 분리)
    # ═══════════════════════════════════════════════════════════

    def _build_inbound_action_buttons(self, main, _tree_dark: bool) -> None:
        """하단 액션 버튼 바 구성: [엑셀][되돌리기][다시실행][원본초기화][업로드순서][DB업로드][템플릿저장] (합계) [취소]"""
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=X, pady=(8, 0))

        _font = getattr(self, '_toolbar_font', '맑은 고딕') if hasattr(self, '_toolbar_font') else '맑은 고딕'
        _btn_font_size = 15
        _btn_fg = ThemeColors.get('badge_text', _tree_dark)
        _blue = ThemeColors.get('info', _tree_dark)
        _red = ThemeColors.get('statusbar_icon_err', _tree_dark)

        self.btn_excel = tk.Button(
            btn_frame, text="📥 Excel 내보내기",
            command=self._export_to_excel, state='disabled',
            font=(_font, _btn_font_size, 'bold'), bg=_blue, fg=_btn_fg,
            padx=15, pady=6, cursor='hand2', bd=0
        )
        self.btn_excel.pack(side=LEFT, padx=(0, 5))

        self.btn_undo = tk.Button(
            btn_frame, text="↶ 되돌리기",
            command=self._undo_preview_edit, state='disabled',
            font=(_font, 11, 'bold'), bg=ThemeColors.get('btn_neutral', _tree_dark), fg=_btn_fg,
            padx=10, pady=6, cursor='hand2', bd=0
        )
        self.btn_undo.pack(side=LEFT, padx=(5, 0))
        self.btn_redo = tk.Button(
            btn_frame, text="↷ 다시실행",
            command=self._redo_preview_edit, state='disabled',
            font=(_font, 11, 'bold'), bg=ThemeColors.get('btn_neutral', _tree_dark), fg=_btn_fg,
            padx=10, pady=6, cursor='hand2', bd=0
        )
        self.btn_redo.pack(side=LEFT, padx=(5, 0))

        self.btn_reset_original = tk.Button(
            btn_frame, text="⟲ 원본 초기화",
            command=self._reset_preview_to_original, state='disabled',
            font=(_font, 11, 'bold'), bg=ThemeColors.get('btn_neutral', _tree_dark), fg=_btn_fg,
            padx=10, pady=6, cursor='hand2', bd=0
        )
        self.btn_reset_original.pack(side=LEFT, padx=(5, 0))

        self._var_upload_by_view_order = tk.BooleanVar(value=False)
        chk_upload_order = ttk.Checkbutton(
            btn_frame,
            text="DB 업로드 시 현재 정렬/필터 순서 적용",
            variable=self._var_upload_by_view_order
        )
        chk_upload_order.pack(side=LEFT, padx=(8, 0))

        self.btn_upload = tk.Button(
            btn_frame, text="📤 DB 업로드",
            command=self._on_upload, state='disabled',
            font=(_font, _btn_font_size, 'bold'), bg=_blue, fg=_btn_fg,
            padx=20, pady=8, cursor='hand2', bd=0
        )
        self.btn_upload.pack(side=LEFT, padx=(5, 0))
        self._attach_doc_tooltip(self.btn_upload,
            "미리보기 데이터를 DB에 저장합니다\n\n• 저장 후 재고리스트에 자동 반영\n• 중복 LOT는 자동 스킵\n• 저장 완료 후 재고리스트 화면 표시")

        _green = '#27ae60'
        self.btn_save_template = tk.Button(
            btn_frame, text="📋 템플릿 저장",
            command=self._on_save_current_as_template, state='disabled',
            font=(_font, _btn_font_size - 1, 'bold'), bg=_green, fg=_btn_fg,
            padx=12, pady=8, cursor='hand2', bd=0
        )
        self.btn_save_template.pack(side=LEFT, padx=(5, 0))
        self._attach_doc_tooltip(self.btn_save_template,
            "현재 파싱 설정(선사·톤백단가·제품)을\n새 템플릿으로 저장합니다.\n파싱 완료 후 활성화됩니다.")

        self.summary_var = tk.StringVar(value="")
        _summary_lbl = ttk.Label(btn_frame, textvariable=self.summary_var,
                                font=('맑은 고딕', 13, 'bold'),
                                foreground=ThemeColors.get('statusbar_progress', _tree_dark))
        _summary_lbl.pack(side=LEFT, fill=X, expand=True, padx=10)

        tk.Button(
            btn_frame, text="❌ 취소",
            command=self._on_cancel,
            font=(_font, _btn_font_size, 'bold'), bg=_red, fg=_btn_fg,
            padx=20, pady=8, cursor='hand2', bd=0
        ).pack(side=RIGHT, padx=(5, 0))

    # ═══════════════════════════════════════════════════════════
    # 파일 선택
    # ═══════════════════════════════════════════════════════════

    def _update_parse_hint(self) -> None:
        """파싱 시작 옆 업로드 상태 문구 갱신: 총 4개 중 N개 업로드되었습니다."""
        n = len(self.file_paths)
        if not getattr(self, 'parse_hint', None):
            return
        _hint_dark = is_dark()
        if 'BL' not in self.file_paths and 'PACKING_LIST' not in self.file_paths:
            self.parse_hint.config(
                text="💡 최소 Packing List를 선택하세요",
                foreground=ThemeColors.get('text_muted', _hint_dark)
            )
            if self.btn_parse:
                self.btn_parse.config(state='disabled')
            if self.btn_reparse:
                self.btn_reparse.config(state='disabled')
        else:
            if self.btn_parse:
                self.btn_parse.config(state='normal')
            if self.btn_reparse:
                self.btn_reparse.config(state='normal')
            self.parse_hint.config(
                text=f"총 4개 중 {n}개 업로드되었습니다.",
                foreground=ThemeColors.get('text_primary', _hint_dark)
            )

    def _reparse_with_current_files(self) -> None:
        """파일 재선택 없이 현재 file_paths로 재파싱."""
        if 'BL' not in self.file_paths and 'PACKING_LIST' not in self.file_paths:
            from ..utils.custom_messagebox import CustomMessageBox
            CustomMessageBox.showwarning(self.dialog, "재파싱 불가", "BL 또는 Packing List 파일이 필요합니다.")
            return
        try:
            from ..utils.custom_messagebox import CustomMessageBox
            ok = CustomMessageBox.askyesno(
                self.dialog,
                "재파싱 확인",
                "기존 미리보기 결과를 덮어쓰고 재파싱합니다.\n\n계속하시겠습니까?"
            )
        except (ImportError, ModuleNotFoundError):
            from tkinter import messagebox as msgbox
            ok = msgbox.askyesno(
                "재파싱 확인",
                "기존 미리보기 결과를 덮어쓰고 재파싱합니다.\n\n계속하시겠습니까?"
            )
        if not ok:
            return
        # v8.0.6: 재파싱은 확인창 없이 바로 파싱 진행 (이미 askyesno로 확인함)
        self._do_start_parsing_after_template()

    def _activate_step(self, step_index: int) -> None:
        """v8.3.3 [UX]: 진행 단계 배지 활성화 — Flexport 스타일.

        step_index: 0=서류선택, 1=파싱실행, 2=결과확인, 3=DB저장
        """
        if not hasattr(self, '_step_labels') or not self._step_labels:
            return
        try:
            accent = getattr(self, '_step_accent', '#22d3ee')
            bg     = getattr(self, '_step_bg',     '#1e293b')
            muted  = getattr(self, '_step_muted',  '#475569')
            text   = getattr(self, '_step_text',   '#f1f5f9')

            for i, cell in enumerate(self._step_labels):
                if not cell.winfo_exists():
                    continue
                is_active   = (i == step_index)
                is_done     = (i < step_index)
                cell_bg     = bg

                # 셀 내 위젯 재색칠
                children = cell.winfo_children()
                if children:
                    # 첫 번째 자식: 번호 배지
                    badge = children[0]
                    if is_active:
                        badge.config(bg=accent,  fg='#0f172a')
                    elif is_done:
                        badge.config(bg='#166534', fg='#4ade80')  # 완료: 그린
                    else:
                        badge.config(bg=bg,  fg=muted)
                    badge.config(highlightthickness=0, relief='flat')

                    # 두 번째 자식: 텍스트 프레임
                    if len(children) > 1:
                        txt_fr = children[1]
                        for lbl in txt_fr.winfo_children():
                            font = lbl.cget('font') or ''
                            is_title = 'bold' in str(font) or lbl.grid_info().get('row', 0) == 0
                            if is_active:
                                lbl.config(fg=accent if is_title else text)
                            elif is_done:
                                lbl.config(fg='#4ade80' if is_title else muted)
                            else:
                                lbl.config(fg=muted)

            self._current_step = step_index
        except Exception as e:
            logger.debug(f"[_activate_step] 스킵: {e}")

    def _select_folder(self) -> None:
        """v8.5.9: Ctrl+클릭 멀티파일 선택 → 자동 서류 감지(BL/PL/FA/DO).

        ① 파일 탐색기에서 Ctrl+클릭으로 여러 파일 한번에 선택
        ② InboundDocDetector로 파일명/텍스트 기반 서류 유형 자동 판별
        ③ BL → PL → FA → DO 순서로 등록
        """
        initial_dir = ""
        try:
            if self._last_selected_dir and os.path.isdir(self._last_selected_dir):
                initial_dir = self._last_selected_dir
        except Exception as e:
            logger.warning(f'[UI] onestop_inbound: {e}')
        _dlg = self.dialog

        # ── 탐색기 열기 전 다이얼로그 최소화 ────────────────────
        try:
            if _dlg and _dlg.winfo_exists():
                _dlg.withdraw()
        except Exception as e:
            logger.debug(f"[UI] dialog withdraw skipped: {e}")

        _filetypes = [
            ("PDF files", "*.pdf *.PDF"),
            ("Image (D/O 캡처)", "*.png *.jpg *.jpeg"),
            ("All files", "*.*"),
        ]

        # ── Ctrl+클릭 멀티 선택 (askopenfilenames 복수형) ─────
        selected = filedialog.askopenfilenames(
            parent=self.parent,
            title="입고 서류 선택 (Ctrl+클릭으로 BL, PL, FA, DO 한번에 선택)",
            initialdir=initial_dir if initial_dir else None,
            filetypes=_filetypes,
        )

        # 다이얼로그 복원
        try:
            if _dlg and _dlg.winfo_exists():
                _dlg.deiconify()
                _dlg.lift()
                _dlg.focus_force()
        except Exception as e:
            logger.debug(f"[UI] dialog restore skipped: {e}")

        if not selected:
            self._log("⚠️ 파일 선택이 취소되었습니다.")
            return

        # ── 선택 폴더 기억 ─────────────────────────────────────
        try:
            first_dir = os.path.dirname(selected[0])
            if first_dir and os.path.isdir(first_dir):
                self._last_selected_dir = first_dir
        except Exception as e:
            logger.warning(f"[UI] 선택 폴더 기억 실패: {e}")

        # ── InboundDocDetector로 서류 유형 자동 감지 ────────────
        try:
            from gui_app_modular.handlers.inbound_doc_detector import InboundDocDetector
            detector = InboundDocDetector(log_fn=self._log)

            # 선택된 파일들의 공통 폴더 + 파일명 추출
            folder = os.path.dirname(selected[0])
            file_names = [os.path.basename(p) for p in selected]
            # 선택 파일만 대상으로 감지 (다른 폴더 파일도 지원)
            detected = detector.detect_from_folder(folder, file_names)
        except Exception as e:
            logger.error(f"[onestop] 서류 자동 감지 실패: {e}")
            detected = {}

        # ── 감지 실패 시 파일 개수 기반 순서 배정 (fallback) ────
        if not detected and selected:
            self._log("🔄 자동 감지 실패 — 선택 순서대로 BL→PL→FA→DO 배정")
            _fallback_order = ['BL', 'PACKING_LIST', 'INVOICE', 'DO']
            for i, path in enumerate(selected):
                if i < len(_fallback_order):
                    detected[_fallback_order[i]] = path

        # ── UI에 등록 ──────────────────────────────────────────
        registered = []
        _success_c = ThemeColors.get('success', is_dark())

        for doc_type in ['BL', 'PACKING_LIST', 'INVOICE', 'DO']:
            if doc_type not in detected:
                continue
            path = detected[doc_type]
            fname = os.path.basename(path)
            self.file_paths[doc_type] = path
            try:
                self.file_labels[doc_type].config(
                    text=fname,
                    foreground=ThemeColors.get('text_primary', is_dark())
                )
                self.check_labels[doc_type].config(text="✅", fg=_success_c)
            except Exception as e:
                logger.warning(f'[UI] onestop_inbound: {e}')
            self._log(f"📂 {doc_type}: {fname}")
            registered.append(doc_type)

        if registered:
            self._log(f"📁 멀티 선택 완료: {len(registered)}종 ({', '.join(registered)})")
            if any(v for v in self.file_paths.values()):
                self._activate_step(0)
            self._update_parse_hint()
        else:
            self._log("⚠️ 서류 유형을 감지할 수 없습니다. 개별 선택을 이용해주세요.")

    def _select_file(self, doc_type: str):
        """서류별 파일 선택 — v8.1.8: 탐색기 열기 전 입고 다이얼로그 임시 최소화 → 선택 후 복원"""
        type_names = {
            'PACKING_LIST': 'Packing List',
            'INVOICE': 'Invoice, FA',
            'BL': 'Bill of Loading',
            'DO': 'Delivery Order',
        }

        # 직전에 선택한 폴더를 계속 열어 파일 선택 시간을 단축한다.
        initial_dir = ""
        try:
            if self._last_selected_dir and os.path.isdir(self._last_selected_dir):
                initial_dir = self._last_selected_dir
            elif doc_type in self.file_paths:
                prev_dir = os.path.dirname(self.file_paths.get(doc_type, ""))
                if prev_dir and os.path.isdir(prev_dir):
                    initial_dir = prev_dir
        except Exception as e:
            logger.debug(f"초기 폴더 계산 무시: {e}")

        # v8.1.8: 탐색기가 입고 다이얼로그 뒤에 가리지 않도록
        # 탐색기 열기 전 잠시 숨김(withdraw) → 선택 후 복원(deiconify)
        _dlg = self.dialog
        try:
            if _dlg and _dlg.winfo_exists():
                _dlg.withdraw()
        except Exception:
            _dlg = None

        file_path = filedialog.askopenfilename(
            parent=self.parent,
            title=f"{type_names.get(doc_type, doc_type)} 파일 선택",
            initialdir=initial_dir if initial_dir else None,
            filetypes=[
                ("PDF files", "*.pdf"),
                ("Image (D/O 캡처)", "*.png *.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )

        # 입고 다이얼로그 복원
        try:
            if _dlg and _dlg.winfo_exists():
                _dlg.deiconify()
                _dlg.lift()
                _dlg.focus_force()
        except Exception as e:
            logger.warning(f'[UI] onestop_inbound: {e}')
        if not file_path:
            return

        try:
            selected_dir = os.path.dirname(file_path)
            if selected_dir and os.path.isdir(selected_dir):
                self._last_selected_dir = selected_dir
        except Exception as e:
            logger.debug(f"선택 폴더 저장 무시: {e}")
        
        self.file_paths[doc_type] = file_path
        fname = os.path.basename(file_path)
        
        # UI 업데이트
        self.file_labels[doc_type].config(text=fname, foreground=ThemeColors.get('text_primary', is_dark()))
        self.check_labels[doc_type].config(text="✅")
        
        self._log(f"📂 {doc_type}: {fname}")

        # v8.3.3 [UX]: 파일 1개 이상 선택 시 단계1(서류선택) 활성화
        if any(v for v in self.file_paths.values()):
            self._activate_step(0)
        
        # 파싱 버튼 활성화 조건: PL 필수
        self._update_parse_hint()
    
    # ═══════════════════════════════════════════════════════════
    # 파싱
    # ═══════════════════════════════════════════════════════════
    
    # ── v7.2.0: 입고 파싱 템플릿 관련 메서드 ───────────────────────────────

    def _load_template_combo(self):
        """DB에서 활성 템플릿 목록을 콤보박스에 로드."""
        try:
            rows = self.engine.db.fetchall(
                "SELECT template_id, template_name, bag_weight_kg, "
                "carrier_id, product_hint, weight_format, "
                "COALESCE(bl_format,'') AS bl_format, "
                "gemini_hint_packing, gemini_hint_invoice, gemini_hint_bl "
                "FROM inbound_template WHERE is_active=1 "
                "ORDER BY carrier_id, bag_weight_kg"
            )
            self._template_map = {}  # display_name → template dict
            names = []
            KEYS = ['template_id','template_name','bag_weight_kg',
                    'carrier_id','product_hint','weight_format','bl_format',
                    'gemini_hint_packing','gemini_hint_invoice','gemini_hint_bl']
            for r in (rows or []):
                t = dict(r) if hasattr(r, 'keys') else dict(zip(KEYS, r))
                self._template_map[t['template_name']] = t
                names.append(t['template_name'])
            self._tpl_combo['values'] = names
            # 기본값: UNKNOWN_500
            default = next((n for n in names if 'UNKNOWN' in n and '500' in n), None)
            if not default and names:
                default = names[0]
            if default:
                self._tpl_var.set(default)
                self._on_template_selected()
        except Exception as e:
            logger.debug(f"[onestop] 템플릿 콤보 로드 실패: {e}")

    def _on_template_selected(self, _event=None):
        """템플릿 변수 반영 → 요약 라벨·선사 뱃지."""
        name = self._tpl_var.get()
        t = getattr(self, '_template_map', {}).get(name)
        if not t:
            return
        bag = t.get('bag_weight_kg', 500)
        self._inbound_template_data = t
        logger.debug(f"[onestop] 템플릿 선택: {name} / {bag}kg")
        # v8.0.0: 선택 라벨 업데이트
        if hasattr(self, '_update_tpl_selected_label'):
            try:
                self._update_tpl_selected_label()
            except Exception as e:
                logger.warning(f"[UI] template selected label update failed: {e}")
        self._apply_template_to_carrier_badge(t)

    def _normalize_carrier_for_combo(self, raw: str) -> str:
        """DB/BL의 carrier_id를 CARRIER_OPTIONS 표기(예: CMA_CGM)로 맞춤."""

        def _fold(x: str) -> str:
            return (x or "").strip().upper().replace(" ", "_").replace("-", "_")

        r = _fold(raw or "UNKNOWN")
        for opt in CARRIER_OPTIONS:
            if _fold(opt) == r:
                return opt
        s = (raw or "").strip()
        if s in CARRIER_OPTIONS:
            return s
        return "UNKNOWN"

    def _carrier_id_matches_filter(self, filt: str, template_carrier: str) -> bool:
        """공백/언더스코어 차이를 무시하고 carrier_id 일치 여부."""

        def _fold(x: str) -> str:
            return (x or "").strip().upper().replace(" ", "_").replace("-", "_")

        return _fold(filt) == _fold(template_carrier or "UNKNOWN")

    def _auto_match_template_by_carrier(self, carrier_id: str) -> dict | None:
        """v8.5.9: BL 파싱 후 감지된 선사로 DB 템플릿 자동 매칭.

        선사 미선택 상태에서 파싱 시작 → BL이 선사를 감지하면
        해당 선사의 활성 템플릿을 자동으로 찾아 반환.
        동일 선사 템플릿이 여러 개면 is_default=1 우선, 없으면 첫 번째.
        """
        try:
            engine = getattr(self, 'engine', None)
            if not engine:
                return None
            db = getattr(engine, 'db', None) or engine
            conn = getattr(db, 'conn', None) or getattr(db, '_conn', None)
            if not conn:
                return None

            cursor = conn.execute(
                "SELECT * FROM inbound_templates WHERE is_active = 1 ORDER BY is_default DESC, template_name ASC"
            )
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            norm_cid = carrier_id.strip().upper().replace(" ", "_").replace("-", "_")

            for row in rows:
                tpl = dict(zip(columns, row))
                tpl_cid = str(tpl.get('carrier_id', '') or '').strip().upper().replace(" ", "_").replace("-", "_")
                if tpl_cid == norm_cid:
                    return tpl

            # template_id에서 선사명 추론 매칭
            for row in rows:
                tpl = dict(zip(columns, row))
                tpl_id_upper = str(tpl.get('template_id', '') or '').upper()
                if norm_cid in tpl_id_upper:
                    return tpl

        except Exception as e:
            logger.debug(f"[onestop] 선사 자동 템플릿 매칭 DB 조회 실패: {e}")
        return None

    def _on_carrier_combo_selected(self, _event=None) -> None:
        """선사 콤보 변경 시 해당 선사 템플릿만 팝업. 취소 시 이전 선사로 복원."""
        cid = self._normalize_carrier_for_combo(
            (self._carrier_manual_var.get() or "UNKNOWN").strip())
        self._carrier_manual_var.set(cid)
        prev_raw = (getattr(self, "_inbound_template_data", None) or {}).get(
            "carrier_id", "UNKNOWN"
        )
        revert = self._normalize_carrier_for_combo(str(prev_raw or "UNKNOWN"))
        self._show_template_table_picker(
            carrier_filter=cid, on_cancel_carrier_revert=revert
        )

    def _show_template_table_picker_for_current_carrier(self) -> None:
        """뱃지/라벨 클릭: UNKNOWN이면 전체, 아니면 현재 콤보 선사만."""
        cid = self._normalize_carrier_for_combo(
            (self._carrier_manual_var.get() or "UNKNOWN").strip()
        )
        flt = None if cid == "UNKNOWN" else cid
        self._show_template_table_picker(carrier_filter=flt, on_cancel_carrier_revert=None)

    def _apply_template_to_carrier_badge(self, t: dict) -> None:
        """템플릿의 carrier_id → 수동 변수·선사 뱃지(클릭 시 템플릿 표)."""
        if not t or not hasattr(self, '_carrier_label'):
            return
        cid = self._normalize_carrier_for_combo(
            str(t.get('carrier_id', 'UNKNOWN') or 'UNKNOWN')
        )
        try:
            self._carrier_manual_var.set(cid)
        except Exception:
            logger.debug("[onestop] carrier_manual_var 설정 생략")
        try:
            from features.ai.bl_carrier_registry import CARRIER_TEMPLATES
            _ctpl = CARRIER_TEMPLATES.get(cid)
            cname = _ctpl.carrier_name if _ctpl else cid
        except Exception as e:
            logger.debug(f"[onestop] 선사명 조회: {e}")
            cname = cid
        try:
            if cid == 'UNKNOWN':
                self._carrier_label.config(
                    text="  뱃지 클릭: 템플릿 목록  ",
                    fg=tc('badge_text'),
                    bg=tc('bg_secondary'),
                    cursor='hand2',
                )
            else:
                self._update_carrier_badge(f"[선사: {cname}] (템플릿)", cid)
        except Exception as e:
            logger.warning(f"[UI] carrier badge from template failed: {e}")

    def _on_save_current_as_template(self) -> None:
        """v7.9.9 [Q2]: 현재 파싱 설정을 새 템플릿으로 저장."""
        import tkinter as _tk
        from tkinter import ttk as _ttk
        import uuid, re

        # 현재 선택된 템플릿 데이터 (있으면 기본값으로 활용)
        cur = getattr(self, '_inbound_template_data', {}) or {}

        # ── 저장 다이얼로그 ──
        dlg = create_themed_toplevel(self.dialog)
        dlg.title("📋 현재 파싱 설정을 템플릿으로 저장")
        dlg.geometry("500x380")
        dlg.resizable(False, False)
        dlg.transient(self.dialog)
        dlg.grab_set()

        _ttk.Label(dlg, text="현재 파싱 설정을 새 템플릿으로 저장합니다.",
                   font=('맑은 고딕', 11)).pack(pady=(16, 6), padx=16, anchor='w')

        form = _ttk.Frame(dlg, padding=16)
        form.pack(fill='both', expand=True)
        form.columnconfigure(1, weight=1)

        # 템플릿 ID
        _ttk.Label(form, text="템플릿 ID *", font=('맑은 고딕', 10, 'bold'),
                   anchor='e', width=14).grid(row=0, column=0, sticky='e', pady=6)
        var_id = _tk.StringVar(value=cur.get('template_id', f"TPL_{uuid.uuid4().hex[:6].upper()}"))
        _ttk.Entry(form, textvariable=var_id, font=('맑은 고딕', 11)).grid(
            row=0, column=1, sticky='ew', padx=(8, 0), pady=6)

        # 템플릿 이름
        _ttk.Label(form, text="템플릿 이름 *", font=('맑은 고딕', 10, 'bold'),
                   anchor='e', width=14).grid(row=1, column=0, sticky='e', pady=6)
        _default_name = cur.get('template_name', '') or "새 템플릿"
        var_name = _tk.StringVar(value=_default_name)
        _ttk.Entry(form, textvariable=var_name, font=('맑은 고딕', 11)).grid(
            row=1, column=1, sticky='ew', padx=(8, 0), pady=6)

        # 선사
        CARRIER_OPTIONS = ['UNKNOWN','MSC','MAERSK','CMA CGM','COSCO','EVERGREEN',
                           'HMM','ONE','PIL','SITC','YANG MING','ZIM']
        _ttk.Label(form, text="선사", font=('맑은 고딕', 10, 'bold'),
                   anchor='e', width=14).grid(row=2, column=0, sticky='e', pady=6)
        var_carrier = _tk.StringVar(value=cur.get('carrier_id', 'UNKNOWN'))
        _ttk.Combobox(form, textvariable=var_carrier, values=CARRIER_OPTIONS,
                      state='normal', font=('맑은 고딕', 11), width=16).grid(
            row=2, column=1, sticky='w', padx=(8, 0), pady=6)

        # 톤백 단가
        _ttk.Label(form, text="톤백 단가(kg)", font=('맑은 고딕', 10, 'bold'),
                   anchor='e', width=14).grid(row=3, column=0, sticky='e', pady=6)
        var_bag = _tk.StringVar(value=str(cur.get('bag_weight_kg', 500)))
        _ttk.Combobox(form, textvariable=var_bag, values=['500', '1000'],
                      state='readonly', font=('맑은 고딕', 11), width=8).grid(
            row=3, column=1, sticky='w', padx=(8, 0), pady=6)

        # 제품 힌트
        _ttk.Label(form, text="제품 힌트", font=('맑은 고딕', 10, 'bold'),
                   anchor='e', width=14).grid(row=4, column=0, sticky='e', pady=6)
        var_prod = _tk.StringVar(value=cur.get('product_hint', 'LITHIUM CARBONATE'))
        _ttk.Entry(form, textvariable=var_prod, font=('맑은 고딕', 11)).grid(
            row=4, column=1, sticky='ew', padx=(8, 0), pady=6)

        # 버튼
        btn_row = _ttk.Frame(dlg, padding=(16, 8))
        btn_row.pack(fill='x', side='bottom')
        result = [False]

        def _do_save():
            t_id   = var_id.get().strip()
            t_name = var_name.get().strip()
            if not t_id or not t_name:
                _tk.messagebox.showwarning("입력 오류", "템플릿 ID와 이름은 필수입니다.", parent=dlg)
                return
            if not re.match(r'^[A-Za-z0-9_\-]+$', t_id):
                _tk.messagebox.showwarning("ID 형식 오류",
                    "템플릿 ID는 영문·숫자·_·- 만 사용 가능합니다.", parent=dlg)
                return
            try:
                from gui_app_modular.dialogs.inbound_template_dialog import save_template
                data = {
                    'template_id':   t_id,
                    'template_name': t_name,
                    'carrier_id':    var_carrier.get(),
                    'bag_weight_kg': int(var_bag.get()),
                    'product_hint':  var_prod.get().strip(),
                    'weight_format': cur.get('weight_format', 'EURO'),
                    'bl_format':     str(cur.get('bl_format', '') or ''),
                    'gemini_hint_packing': cur.get('gemini_hint_packing', ''),
                    'gemini_hint_invoice': cur.get('gemini_hint_invoice', ''),
                    'gemini_hint_bl':      cur.get('gemini_hint_bl', ''),
                    'note': f"파싱 결과에서 자동 생성 (v7.9.9)",
                    'is_active': 1,
                }
                ok = save_template(self.engine, data)
                if ok:
                    result[0] = True
                    # 콤보박스 갱신
                    if hasattr(self, '_load_template_combo'):
                        self._load_template_combo()
                    dlg.destroy()
                    from gui_app_modular.utils.custom_messagebox import CustomMessageBox
                    CustomMessageBox.showinfo(
                        self.dialog, "템플릿 저장 완료",
                        f"✅ 템플릿 '{t_name}' 저장 완료! 다음 파싱 시 콤보박스에서 선택 가능합니다."


                    )
                else:
                    _tk.messagebox.showerror("저장 실패", "템플릿 저장 중 오류가 발생했습니다.", parent=dlg)
            except Exception as _e:
                _tk.messagebox.showerror("오류", f"저장 실패: {_e}", parent=dlg)
                logger.error(f"[템플릿 저장] {_e}")

        _ttk.Button(btn_row, text="💾 저장", width=12, command=_do_save).pack(side='right', padx=6)
        _ttk.Button(btn_row, text="취소",    width=8,  command=dlg.destroy).pack(side='right')


    def _show_template_table_picker(
        self,
        carrier_filter=None,
        on_cancel_carrier_revert=None,
    ) -> None:
        """v8.0.0 [TEMPLATE-TABLE]: 템플릿 테이블 선택 팝업.
        carrier_filter가 있으면 해당 carrier_id 템플릿만 표시.
        on_cancel_carrier_revert: 콤보에서 연 경우 취소·닫기 시 선사 콤보 복원값.
        """
        from tkinter import ttk as _ttk

        all_templates = list(getattr(self, '_template_map', {}).values())
        templates = all_templates
        if carrier_filter is not None:
            cf = self._normalize_carrier_for_combo(str(carrier_filter))
            templates = [
                t for t in all_templates
                if self._carrier_id_matches_filter(cf, str(t.get('carrier_id', 'UNKNOWN')))
            ]
            if not templates:
                try:
                    from gui_app_modular.utils.custom_messagebox import CustomMessageBox
                    CustomMessageBox.showwarning(
                        self.dialog,
                        "템플릿 없음",
                        f"선사 「{cf}」로 등록된 입고 파싱 템플릿이 없습니다.\n"
                        f"[⚙ 템플릿 관리]에서 해당 선사로 템플릿을 추가하세요.",
                    )
                except Exception as e:
                    logger.warning(f"[onestop] 템플릿 없음 알림 실패: {e}")
                if on_cancel_carrier_revert is not None:
                    try:
                        self._carrier_manual_var.set(
                            self._normalize_carrier_for_combo(on_cancel_carrier_revert)
                        )
                    except Exception as e:
                        logger.debug(f"[onestop] 선사 콤보 복원 생략: {e}")
                return

        popup = create_themed_toplevel(self.dialog)
        if carrier_filter is not None:
            cf = self._normalize_carrier_for_combo(str(carrier_filter))
            popup.title(f"📋 파싱 템플릿 선택 ({cf})")
        else:
            popup.title("📋 파싱 템플릿 선택")
        popup.geometry("780x420")
        popup.resizable(True, True)
        popup.transient(self.dialog)
        popup.grab_set()

        confirmed = [False]

        def _close_without_apply():
            if (
                not confirmed[0]
                and on_cancel_carrier_revert is not None
            ):
                try:
                    self._carrier_manual_var.set(
                        self._normalize_carrier_for_combo(on_cancel_carrier_revert)
                    )
                except Exception as e:
                    logger.debug(f"[onestop] 선사 콤보 복원: {e}")
            try:
                popup.destroy()
            except Exception as e:
                logger.debug(f"[onestop] picker destroy: {e}")

        popup.protocol('WM_DELETE_WINDOW', _close_without_apply)

        # ── 헤더 ──
        hdr = _ttk.Frame(popup, padding=(12, 8))
        hdr.pack(fill='x')
        if carrier_filter is not None:
            cf = self._normalize_carrier_for_combo(str(carrier_filter))
            _hdr_txt = f"「{cf}」 선사 템플릿을 클릭하여 선택하세요"
        else:
            _hdr_txt = "템플릿을 클릭하여 선택하세요"
        _ttk.Label(hdr, text=_hdr_txt,
                   font=('맑은 고딕', 12, 'bold')).pack(side='left')

        def _open_template_manager_from_picker():
            confirmed[0] = True
            try:
                popup.destroy()
            except Exception as e:
                logger.debug(f"[onestop] picker destroy before mgr: {e}")
            self._open_template_manager()

        _ttk.Button(hdr, text="⚙ 템플릿 관리",
                    command=_open_template_manager_from_picker).pack(side='right')

        _ttk.Separator(popup, orient='horizontal').pack(fill='x')

        # ── 테이블 ──
        tbl = _ttk.Frame(popup, padding=(12, 6))
        tbl.pack(fill='both', expand=True)

        cols = ('sel', 'carrier', 'name', 'bag_kg', 'product', 'bl_format')
        tree = _ttk.Treeview(tbl, columns=cols, show='headings',
                              height=12, selectmode='browse')

        for cid, txt, w, anchor in [
            ('sel',      '✔',          36,  'center'),
            ('carrier',  '선사',        110, 'center'),
            ('name',     '템플릿 이름', 220, 'w'),
            ('bag_kg',   '톤백 단가',   80,  'center'),
            ('product',  '제품 힌트',   160, 'w'),
            ('bl_format','BL 형식',     80,  'center'),
        ]:
            tree.heading(cid, text=txt, anchor='center')
            tree.column(cid, width=w, anchor=anchor)

        vsb = _ttk.Scrollbar(tbl, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        # 데이터 삽입
        current = self._tpl_var.get()
        tree.tag_configure('selected_row', background=tc('bg_secondary'), foreground=tc('text_primary'))
        tree.tag_configure('even_row',     background=tc('bg_secondary'))
        tree.tag_configure('odd_row',      background=tc('bg_card'))

        iid_map = {}  # iid → template_name

        for idx, t in enumerate(templates):
            name   = t.get('template_name', '')
            sel    = '✔' if name == current else ''
            carrier = t.get('carrier_id', 'UNKNOWN')
            bag_kg  = f"{t.get('bag_weight_kg', 500)} kg"
            product = (t.get('product_hint', '') or '')[:20]
            bl_fmt  = t.get('bl_format', '') or '-'
            tag = 'selected_row' if name == current else ('even_row' if idx % 2 == 0 else 'odd_row')
            iid = tree.insert('', 'end',
                              values=(sel, carrier, name, bag_kg, product, bl_fmt),
                              tags=(tag,))
            iid_map[iid] = name
            if name == current:
                tree.see(iid)
                tree.selection_set(iid)

        # ── 클릭 선택 ──
        selected = [current]

        def on_click(event):
            iid = tree.identify_row(event.y)
            if not iid:
                return
            name = iid_map.get(iid, '')
            if not name:
                return
            selected[0] = name
            # 체크 표시 갱신
            keys = list(iid_map.keys())
            for i, values in [(i, tree.item(i, 'values')) for i in iid_map]:
                n = iid_map[i]
                new_sel = '✔' if n == name else ''
                tree.item(i, values=(new_sel,) + values[1:])
                tag = 'selected_row' if n == name else ('even_row' if keys.index(i) % 2 == 0 else 'odd_row')
                tree.item(i, tags=(tag,))

        tree.bind('<Button-1>', on_click)
        tree.bind('<Double-1>', lambda e: _do_select())

        # ── 하단 버튼 ──
        btn_row = _ttk.Frame(popup, padding=(12, 8))
        btn_row.pack(fill='x', side='bottom')

        def _do_select():
            name = selected[0]
            if name and name in self._template_map:
                confirmed[0] = True
                self._tpl_var.set(name)
                self._on_template_selected()
                try:
                    popup.destroy()
                except Exception as e:
                    logger.debug(f"[onestop] picker destroy after select: {e}")

        _ttk.Button(btn_row, text="✅ 선택 확인", width=14,
                    command=_do_select).pack(side='right', padx=6)
        _ttk.Button(btn_row, text="취소", width=8,
                    command=_close_without_apply).pack(side='right')

        # 선택 개수 표시
        count_lbl = _ttk.Label(btn_row,
                               text=f"표시 {len(templates)}개 / 전체 {len(all_templates)}개",
                               font=('맑은 고딕', 10))
        count_lbl.pack(side='left')

    def _update_tpl_selected_label(self) -> None:
        """v8.0.0: 선택된 템플릿 이름을 라벨에 표시."""
        lbl = getattr(self, '_tpl_selected_lbl', None)
        if not lbl:
            return
        name = self._tpl_var.get()
        t    = getattr(self, '_template_map', {}).get(name, {})
        if name and t:
            carrier = t.get('carrier_id', '')
            bag_kg  = t.get('bag_weight_kg', 500)
            bl_fmt  = t.get('bl_format', '') or ''
            bl_info = f"  BL:{bl_fmt}" if bl_fmt else ''
            lbl.config(
                text=f"{carrier} — {name}  ({bag_kg}kg{bl_info})",
                foreground=tc('info')
            )
        else:
            lbl.config(text="(미선택)", foreground=tc('text_muted'))

    def _open_template_manager(self):
        """템플릿 관리 다이얼로그 열기 (콜백 없음 → 관리 전용)."""
        try:
            from gui_app_modular.dialogs.inbound_template_dialog import InboundTemplateDialog
            current_theme = getattr(self.parent, 'current_theme', 'darkly')
            InboundTemplateDialog(self.dialog, self.engine, current_theme=current_theme)
            # 관리 후 콤보박스 갱신
            self._load_template_combo()
        except Exception as e:
            logger.error(f"[onestop] 템플릿 관리 다이얼로그 오류: {e}")

    def _start_parsing(self) -> None:
        """
        v8.0.6 [PREPARSE-SELECT]: 파싱 시작 버튼 클릭 시
        파싱 선택 확인창(PreParseSelectDialog)을 먼저 표시.
        사용자가 서류 목록·템플릿·옵션을 확인하고 [실행] 버튼을 눌러야만 파싱 진행.
        auto_start_parse 모드(빠른 폴더 스캔)는 기존 방식 유지.

        v8.7.0 [POLICY]: 파싱 시작 전 선사 필수 선택 검증 추가.
          자동 감지 로직이 제거됐으므로 사용자가 반드시 콤보·뱃지로 선사를 지정해야 함.
        """
        # v8.7.0: 선사 필수 선택 검증
        _cid = ''
        try:
            _cid = (self._carrier_manual_var.get() or '').strip().upper() if hasattr(self, '_carrier_manual_var') else ''
        except Exception:
            _cid = ''
        if not _cid or _cid == 'UNKNOWN':
            try:
                from ..utils.custom_messagebox import CustomMessageBox
                CustomMessageBox.showwarning(
                    self.dialog, "🚢 선사 선택 필요",
                    "파싱 시작 전에 반드시 선사를 선택하세요.\n\n"
                    "v8.7.0부터 자동 선사 감지가 비활성화되었습니다.\n"
                    "상단 [🚢 선사:] 드롭다운에서 선사를 선택하거나,\n"
                    "뱃지 클릭으로 템플릿 목록에서 선택하세요."
                )
            except Exception as e:
                logger.warning(f"[UI] 선사 미선택 경고 표시 실패: {e}")
            return

        # v6.4.0: auto_start_parse 모드 — 버튼 강제 활성화 후 즉시 파싱
        if getattr(self, '_auto_start_parse', False):
            if self.btn_parse and str(self.btn_parse.cget('state')) == 'disabled':
                self.btn_parse.config(state='normal')
            self._do_start_parsing_after_template()
            return

        # v8.0.6: 일반 모드 → 파싱 선택 확인창 표시
        self._show_preparse_select_dialog()

    def _show_preparse_select_dialog(self) -> None:
        """
        v8.0.6 [PREPARSE-SELECT]: 파싱 전 확인창 표시.
        사용자가 [실행]을 눌러야 _on_preparse_execute() 호출 → 실제 파싱 진행.
        """
        try:
            from gui_app_modular.dialogs.preparse_select_dialog import PreParseSelectDialog
        except ImportError as e:
            logger.error("[onestop] PreParseSelectDialog 로드 실패: %s — 기존 방식으로 진행", e)
            self._show_template_select_before_parse()
            return

        current_tpl = getattr(self, '_inbound_template_data', None) or {}
        current_theme = getattr(self.parent, 'current_theme', 'darkly')

        def _on_execute(template_data: dict, use_multi_template: bool) -> None:
            self._on_preparse_execute(template_data, use_multi_template)

        PreParseSelectDialog(
            parent=self.dialog,
            file_paths=dict(self.file_paths),
            engine=self.engine,
            current_template=current_tpl,
            on_execute=_on_execute,
            current_theme=current_theme,
        )

    def _on_preparse_execute(
        self, template_data: dict, use_multi_template: bool
    ) -> None:
        """
        v8.0.6 [PREPARSE-SELECT]: PreParseSelectDialog [실행] 콜백.
        템플릿 적용 + 멀티템플릿 플래그 저장 → 기존 파싱 흐름 연결.
        """
        # 템플릿 적용
        if template_data:
            self._inbound_template_data = template_data
            try:
                tname = template_data.get('template_name', '')
                if hasattr(self, '_tpl_var'):
                    self._tpl_var.set(tname)
                self._load_template_combo()
                self._tpl_var.set(tname)
                if hasattr(self, '_update_tpl_selected_label'):
                    self._update_tpl_selected_label()
            except Exception as e:
                logger.warning(f"[UI] template confirmation UI update failed: {e}")
            self._log_safe(
                f"✅ 템플릿 확정: {template_data.get('template_name','')} "
                f"/ {template_data.get('bag_weight_kg', 500)}kg"
            )
            self._apply_template_to_carrier_badge(template_data)

        # 멀티템플릿 플래그 저장 (candidate_patch가 읽음)
        self._use_multi_template_flag = bool(use_multi_template)
        if use_multi_template:
            self._log_safe("🔍 다중 템플릿 후보 모드: ON")
        else:
            self._log_safe("📌 단일 템플릿 모드: OFF (기존 템플릿만 사용)")

        # 기존 파싱 흐름 진행
        self._do_start_parsing_after_template()

    def _show_template_select_before_parse(self) -> None:
        """파싱 전 템플릿 선택 다이얼로그 표시."""
        try:
            from gui_app_modular.dialogs.inbound_template_dialog import InboundTemplateDialog
            current_theme = getattr(self.parent, 'current_theme', 'darkly')

            def _on_template_chosen(t: dict):
                """템플릿 선택 완료 콜백 → 파싱 진행."""
                # 선택된 템플릿 적용
                self._inbound_template_data = t
                # 콤보박스 + 뱃지 동기화
                try:
                    tname = t.get('template_name', '')
                    self._tpl_var.set(tname)
                    self._load_template_combo()
                    self._tpl_var.set(tname)
                    if hasattr(self, '_update_tpl_selected_label'):
                        self._update_tpl_selected_label()
                except Exception as e:
                    logger.warning(f"[UI] template selection UI update failed: {e}")
                self._apply_template_to_carrier_badge(t)
                self._log_safe(
                    f"✅ 템플릿 선택: {t.get('template_name','')} "
                    f"/ {t.get('bag_weight_kg',500)}kg")
                # 실제 파싱 진행
                self._do_start_parsing_after_template()

            InboundTemplateDialog(
                self.dialog,
                self.engine,
                current_theme=current_theme,
                on_select_callback=_on_template_chosen,
            )
        except Exception as e:
            logger.error(f"[onestop] 템플릿 선택 다이얼로그 오류: {e}")
            # 오류 시 현재 선택 그대로 파싱 진행
            self._do_start_parsing_after_template()

    def _do_start_parsing_after_template(self) -> None:
        """템플릿 선택 완료 후 기존 파싱 흐름 진행 (서류 확인 → 파싱 실행)."""
        # 들어온 서류 / 빠진 서류 분류
        received = []
        missing = []
        do_missing = False
        short_names = {
            'PACKING_LIST': 'Packing List',
            'INVOICE': 'Invoice, FA',
            'BL': 'Bill of Loading',
            'DO': 'Delivery Order',
        }
        for doc_type, _doc_name, _required in DOC_TYPES:
            name = short_names.get(doc_type, doc_type)
            if doc_type in self.file_paths:
                received.append(name)
            else:
                missing.append(name)
                if doc_type == 'DO':
                    do_missing = True
        
        # 메시지 구성: 들어온 서류 / 빠진 서류 / D/O 안내 / 진행할까요?
        lines = []
        if received:
            lines.append(f"✅ 들어온 서류: {', '.join(received)}")
        if missing:
            lines.append(f"⚠️ 빠진 서류: {', '.join(missing)}")
        if do_missing:
            lines.append("\n📋 D/O가 빠진 경우에는 입항일 혹은 프리타임을 반드시 입력해야 합니다.")
        lines.append("\n진행할까요?")
        msg = "\n".join(lines)
        
        # v6.4.0: skip_parse_confirm=True (빠른 폴더 스캔) 이면 확인 팝업 생략
        if not getattr(self, '_skip_parse_confirm', False):
            from ..utils.custom_messagebox import CustomMessageBox
            proceed = CustomMessageBox.askyesno(
                self.dialog,
                "입고 서류 확인",
                msg
            )
            if not proceed:
                return
        
        if missing:
            self._update_progress(0, f"ℹ️ {', '.join(missing)} 미선택 — 해당 정보 생략")
        
        self.btn_parse.config(state='disabled')
        if self.btn_reparse:
            self.btn_reparse.config(state='disabled')
        self._show_progress_inline()
        # v8.3.3 [UX]: 파싱 시작 → 단계2 활성화
        self._activate_step(1)

        thread = threading.Thread(
            target=self._parse_thread,
            daemon=True
        )
        thread.start()
    
    def _show_progress_inline(self) -> None:
        """진행 상태를 미리보기 위 인라인 영역에만 표시 (팝업 없음, 움직임 표시 포함)"""
        ph = getattr(self, '_progress_inline_placeholder', None)
        fr = getattr(self, '_progress_inline_frame', None)
        if ph and ph.winfo_ismapped():
            ph.pack_forget()
        if fr:
            fr.pack(fill=X)
        self._progress_start_time = time.time()
        if getattr(self, '_progress_inline_bar', None):
            self._progress_inline_bar['value'] = 0
        if getattr(self, '_progress_inline_msg', None):
            self._progress_inline_msg.config(text="준비 중...")
        if getattr(self, '_progress_inline_pct_elapsed', None):
            self._progress_inline_pct_elapsed.config(text="0%  ·  경과: 0:00")
        if getattr(self, '_progress_inline_busy', None):
            self._progress_inline_busy.config(text="진행 중 ●")
            self._progress_inline_busy.place(relx=0, rely=0.5, anchor='w')
        self._start_progress_elapsed_tick()
        self._start_progress_busy_animation()

    def _hide_progress_inline(self) -> None:
        """진행 완료 후 인라인 영역을 플레이스홀더로 복귀"""
        fr = getattr(self, '_progress_inline_frame', None)
        ph = getattr(self, '_progress_inline_placeholder', None)
        if fr and fr.winfo_ismapped():
            fr.pack_forget()
        if ph:
            ph.pack(anchor='w')

    def _show_progress_popup(self) -> None:
        """작업진행 전용 창 사용 안 함 — 기존 화면(인라인 진행 상태)만 사용"""

    def _progress_elapsed_tick(self) -> None:
        """경과 시간 표시 업데이트 (1초 간격) — 팝업·인라인 둘 다"""
        start = getattr(self, '_progress_start_time', None)
        if start is None:
            self._progress_elapsed_job = self.dialog.after(1000, self._progress_elapsed_tick) if self.dialog and self.dialog.winfo_exists() else None
            return
        secs = int(time.time() - start)
        if secs >= 3600:
            h, r = divmod(secs, 3600)
            m, s = divmod(r, 60)
            elapsed_text = f"경과: {h}:{m:02d}:{s:02d}"
        else:
            m, s = divmod(secs, 60)
            elapsed_text = f"경과: {m}:{s:02d}"
        # 인라인 경과 (현재 퍼센트 + 경과)
        pct_elapsed = getattr(self, '_progress_inline_pct_elapsed', None)
        if pct_elapsed and pct_elapsed.winfo_ismapped():
            pct = getattr(self, 'progress_var', None)
            pct_val = int(pct.get()) if pct else 0
            pct_elapsed.config(text=f"{pct_val}%  ·  {elapsed_text}")
        self._progress_elapsed_job = self.dialog.after(1000, self._progress_elapsed_tick) if self.dialog and self.dialog.winfo_exists() else None

    def _start_progress_elapsed_tick(self) -> None:
        """경과 시간 타이머 시작"""
        self._progress_elapsed_job = None
        if self.dialog and self.dialog.winfo_exists():
            self._progress_elapsed_job = self.dialog.after(1000, self._progress_elapsed_tick)

    def _stop_progress_elapsed_tick(self) -> None:
        """경과 시간 타이머 중지"""
        if getattr(self, '_progress_elapsed_job', None):
            try:
                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.after_cancel(self._progress_elapsed_job)
            except (tk.TclError, ValueError) as e:
                logger.debug(f"Suppressed: {e}")
        self._progress_elapsed_job = None

    def _progress_busy_tick(self) -> None:
        """진행 중 움직임 표시 — 기존 화면(인라인) 진행 상태 영역에만 표시"""
        phase = getattr(self, '_progress_busy_phase', 0) % 4
        self._progress_busy_phase = phase + 1
        texts = ['진행 중 ●  ', '진행 중 ●● ', '진행 중 ●●●', '진행 중 ●● ']
        inline_busy = getattr(self, '_progress_inline_busy', None)
        if inline_busy and inline_busy.winfo_ismapped():
            inline_busy.config(text=texts[phase])
        self._progress_busy_job = self.dialog.after(400, self._progress_busy_tick) if self.dialog and self.dialog.winfo_exists() else None

    def _start_progress_busy_animation(self) -> None:
        self._progress_busy_phase = 0
        if self.dialog and self.dialog.winfo_exists():
            self._progress_busy_job = self.dialog.after(400, self._progress_busy_tick)

    def _stop_progress_busy_animation(self) -> None:
        if getattr(self, '_progress_busy_job', None):
            try:
                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.after_cancel(self._progress_busy_job)
            except (tk.TclError, ValueError):
                logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
        self._progress_busy_job = None

    def _hide_progress_popup(self) -> None:
        """진행률 팝업 닫기"""
        self._stop_progress_busy_animation()
        self._stop_progress_elapsed_tick()
        try:
            if getattr(self, '_progress_popup', None) and self._progress_popup.winfo_exists():
                self._progress_popup.destroy()
        except Exception as e:
            logger.debug(f"Suppressed: {e}")
        self._progress_popup = None
        self._progress_popup_label = None
        self._progress_popup_bar = None
        self._progress_popup_pct = None
        self._progress_popup_busy = None
        self._progress_popup_elapsed = None

    def _update_progress(self, pct: int, message: str):
        """프로그레스 바 업데이트 (스레드 안전) — 팝업 + 인라인 동기화, 로그 탭에도 기록"""
        def _update():
            self.progress_var.set(pct)
            self.status_var.set(message)
            if message.strip() and getattr(self, '_log', None):
                try:
                    self._log(message)
                except (RuntimeError, ValueError):
                    logger.info(message)
            # 팝업
            bar = getattr(self, '_progress_popup_bar', None)
            if bar and bar.winfo_exists():
                bar['value'] = max(0, min(100, pct))
                if self._progress_popup_label:
                    self._progress_popup_label.config(text=message)
                if getattr(self, '_progress_popup_pct', None):
                    self._progress_popup_pct.config(text=f"{pct}%" if pct >= 0 else "—")
            # 인라인 (미리보기 위) — 기존 화면 프로그레스 바만 사용
            inline_bar = getattr(self, '_progress_inline_bar', None)
            inline_msg = getattr(self, '_progress_inline_msg', None)
            inline_busy = getattr(self, '_progress_inline_busy', None)
            if inline_bar and inline_bar.winfo_ismapped():
                inline_bar['value'] = max(0, min(100, pct))
            if inline_busy and inline_busy.winfo_ismapped():
                relx = max(0, min(1.0, pct / 100.0))
                if relx > 0.92:
                    relx = 0.92
                inline_busy.place(relx=relx, rely=0.5, anchor='w')
            if inline_msg and inline_msg.winfo_ismapped():
                inline_msg.config(text=message)
            if pct >= 100 or (pct == 0 and message.strip().startswith("❌")):
                self._stop_progress_busy_animation()
                if inline_busy and inline_busy.winfo_ismapped():
                    inline_busy.config(text="완료" if pct >= 100 else "오류")
                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.after(PROGRESS_POPUP_CLOSE_DELAY_MS, self._hide_progress_popup)
                self.dialog.after(PROGRESS_POPUP_CLOSE_DELAY_MS + 100, self._hide_progress_inline)
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.after(0, _update)
    
    def _parse_thread(self) -> None:  # v8.6.4 [SRP] refactored — sub-methods below
        """백그라운드 파싱"""
        try:
            from parsers.document_parser_modular import DocumentParserV3 as DocumentParserV2  # v7.5.0: V3 마이그레이션
            self._cross_check_result = None

            parser = self._pt_init_parser(DocumentParserV2)

            # 템플릿 힌트/선사 추출
            ctx = self._pt_extract_template_hints()

            # v8.7.0 [FIX]: 수동 선사 선택이 DO 좌표 파서 분기에 반영되도록 _last_carrier_id 강제 주입
            # (do_mixin.parse_do는 self._last_carrier_id를 가장 먼저 참조하고, 없으면 파일명 fallback)
            _forced_cid = (ctx.get('tpl_carrier_id') or '').strip().upper()
            if _forced_cid and _forced_cid != 'UNKNOWN':
                try:
                    parser._last_carrier_id = _forced_cid
                    self._log_safe(f"  🔒 파서 선사 고정: {_forced_cid} (BL/DO 자동감지 덮어쓰기)")
                except Exception as _e:
                    logger.debug(f"parser._last_carrier_id 설정 실패(무시): {_e}")

            # v6.4.0: 파싱 시작 시 선사 뱃지 초기화
            if hasattr(self, '_carrier_label') and self._carrier_label:
                try:
                    self._carrier_label.config(
                        text="  ⏳ 파싱 중...  ",
                        fg=tc('text_primary'), bg=tc('text_muted')
                    )
                except Exception as e:
                    logger.warning(f"[UI] carrier label parsing status update failed: {e}")

            # 서류별 파싱 루프
            pl_result, inv_result, bl_result, do_result, total = self._pt_parse_documents(
                parser, ctx
            )

            # 최종 병합
            self._update_progress(85, "📊 데이터 병합 중...")
            self._merge_results(inv_result, pl_result, bl_result, do_result)

            # D/O 날짜 누락 처리
            self._pt_handle_missing_dates(do_result)

            # 경고 수집 + 크로스 체크 + 복구 다이얼로그
            self._pt_collect_warnings_and_crosscheck(
                pl_result, inv_result, bl_result, do_result
            )

            # 미리보기·버튼·스냅샷
            self._pt_finalize_preview()

            elapsed_sec = time.time() - getattr(self, '_progress_start_time', time.time())
            elapsed_str = f"{elapsed_sec:.1f}초" if elapsed_sec < 60 else f"{int(elapsed_sec // 60)}분 {elapsed_sec % 60:.0f}초"
            self._update_progress(100, f"✅ 파싱 완료 — {len(self.preview_data)}개 LOT ({elapsed_str})")
            # v8.3.3 [UX]: 파싱 완료 → 단계3(결과 확인) 활성화
            if self.dialog and self.dialog.winfo_exists():
                self.dialog.after(0, lambda: self._activate_step(2))

            # 파싱 확인 다이얼로그
            self._pt_parse_confirm(pl_result, elapsed_str)

            self._log_safe(f"✅ 파싱 완료: {len(self.preview_data)} LOT, {total}종 서류 (경과: {elapsed_str})")

        except (RuntimeError, ValueError) as e:
            self._update_progress(0, f"❌ 오류: {e}")
            self._log_safe(f"❌ 파싱 오류: {e}")
            logger.error(f"원스톱 파싱 오류: {e}", exc_info=True)
            self._enable_parse_btn()

    # ───────────────────────────────────────────────────────────────
    # _parse_thread sub-methods  (v8.6.4 [SRP])
    # ───────────────────────────────────────────────────────────────

    def _pt_init_parser(self, ParserClass):  # v8.6.4 [SRP]
        """Gemini API 키 확인 후 파서 인스턴스 반환"""
        gemini_key = os.environ.get('GEMINI_API_KEY', '')
        if not gemini_key:
            try:
                from core.config import get_settings
                settings = get_settings()
                gemini_key = settings.get('gemini_api_key', '')
            except (ImportError, ModuleNotFoundError) as _e:
                logger.debug(f"onestop_inbound: {_e}")

        # v5.5.1: 모든 파싱은 API(Gemini) 강제
        if not gemini_key or str(gemini_key).strip() == '' or str(gemini_key).startswith('your-'):
            raise RuntimeError("API-only 모드: Gemini API Key가 필요합니다. 설정에서 API Key를 입력하세요.")

        return ParserClass(gemini_api_key=gemini_key)

    def _pt_extract_template_hints(self) -> dict:  # v8.6.4 [SRP]
        """선택된 템플릿에서 bag_weight / gemini_hint / carrier_id 추출"""
        # ── v7.2.0: 선택된 템플릿에서 bag_weight_kg 주입 ─────────────────
        # ── v7.3.0: gemini_hint 3종 추출 ────────────────────────────────
        _tpl = getattr(self, '_inbound_template_data', {}) or {}
        _bag_weight       = int(_tpl.get('bag_weight_kg') or DEFAULT_TONBAG_WEIGHT)  # v8.6.1
        _hint_packing     = str(_tpl.get('gemini_hint_packing', '') or '')
        _hint_invoice     = str(_tpl.get('gemini_hint_invoice', '') or '')
        _hint_bl          = str(_tpl.get('gemini_hint_bl',      '') or '')
        _bl_format        = str(_tpl.get('bl_format', '') or '')  # v8.0.0
        _tpl_id           = _tpl.get('template_id', 'NONE')
        # v8.4.5: DB 템플릿 carrier_id 추출
        _tpl_carrier_id   = str(_tpl.get('carrier_id', '') or '').strip().upper()

        # v8.4.5 Rev2: template_id 기반 carrier_id 자동 보정
        _CARRIER_FROM_TPL = {
            'MSC':      'MSC',    'MAERSK': 'MAERSK',
            'MERSK':    'MAERSK', 'HMM':    'HMM',
            'COSCO':    'COSCO',  'CMA':    'CMA_CGM',
            'EVERGREEN':'EVERGREEN', 'ONE': 'ONE',
            'HAPAG':    'HAPAG',
        }
        _tpl_id_upper = str(_tpl_id or '').upper()
        _inferred = ''
        for _kw, _cv in _CARRIER_FROM_TPL.items():
            if _kw in _tpl_id_upper:
                _inferred = _cv
                break
        # template_id 추론 결과와 DB carrier_id가 다르면 template_id 우선
        if _inferred and _inferred != _tpl_carrier_id:
            logger.warning(
                f"[onestop] carrier_id 불일치 수정: DB='{_tpl_carrier_id}' "
                f"template_id 추론='{_inferred}' → {_inferred} 사용"
            )
            _tpl_carrier_id = _inferred
        # carrier_id가 비어있으면 template_id 추론값 사용
        elif not _tpl_carrier_id and _inferred:
            _tpl_carrier_id = _inferred

        logger.info(
            f"[onestop] 파싱 템플릿: {_tpl_id} / {_bag_weight}kg "
            f"/ 힌트PL={bool(_hint_packing)} INV={bool(_hint_invoice)} BL={bool(_hint_bl)}"
            f" / 선사={_tpl_carrier_id or '미지정'}"
        )

        return {
            'bag_weight': _bag_weight,
            'hint_packing': _hint_packing,
            'hint_invoice': _hint_invoice,
            'hint_bl': _hint_bl,
            'bl_format': _bl_format,
            'tpl_id': _tpl_id,
            'tpl_carrier_id': _tpl_carrier_id,
        }

    def _pt_parse_documents(self, parser, ctx: dict):  # v8.6.4 [SRP]
        """서류별 파싱 루프 — BL → PL → INV → DO 순서"""
        # v7.3.9: 파싱 순서 변경 BL → PL → Invoice → DO
        parse_order = ['BL', 'PACKING_LIST', 'INVOICE', 'DO']
        to_parse = [(dt, self.file_paths[dt]) for dt in parse_order if dt in self.file_paths]
        total = len(to_parse)
        if total == 0:
            self._update_progress(90, "파싱할 파일이 없습니다")
            return None, None, None, None, 0

        icons = {'PACKING_LIST': '📦', 'INVOICE': '📑', 'BL': '🚢', 'DO': '📋'}
        doc_type_display = {
            'PACKING_LIST': 'Packing List',
            'INVOICE': 'Invoice, FA',
            'BL': 'Bill of Loading',
            'DO': 'Delivery Order',
        }

        pl_result = None
        inv_result = None
        bl_result = None
        do_result = None

        for idx, (doc_type, file_path) in enumerate(to_parse):
            fname = os.path.basename(file_path)
            icon = icons.get(doc_type, '📄')
            pct = int(10 + 70 * idx / total)
            doc_name = doc_type_display.get(doc_type, doc_type)
            self._update_progress(pct, f"현재 파싱 중: {doc_name} — {fname}")
            self._log_safe(f"{icon} {doc_type} 파싱: {fname}")

            try:
                if doc_type == 'PACKING_LIST':
                    pl_result = parser.parse_packing_list(
                        file_path,
                        bag_weight_kg=ctx['bag_weight'],
                        gemini_hint=ctx['hint_packing'],     # v7.3.0
                    )
                    self.parsed_results['packing_list'] = pl_result
                    _lots = getattr(pl_result, 'lots', []) if pl_result else []
                    if _lots:
                        _tnw = getattr(pl_result, 'total_net_weight_kg', 0) or 0
                        self._log_safe(f"  ✅ LOTs: {len(_lots)}, Net: {_tnw:,.0f}kg")

                elif doc_type == 'INVOICE':
                    inv_result = parser.parse_invoice(
                        file_path,
                        gemini_hint=ctx['hint_invoice'],     # v7.3.0
                    )
                    self.parsed_results['invoice'] = inv_result
                    if inv_result:
                        self._log_safe(f"  ✅ SAP: {getattr(inv_result, 'sap_no', '')}, Invoice: {getattr(inv_result, 'salar_invoice_no', '')}")

                elif doc_type == 'BL':
                    bl_result = self._pt_parse_bl(parser, file_path, ctx)
                    # v7.3.9: 선사 감지 → 힌트 동적 교체 (ctx 변이)
                    self._pt_handle_bl_carrier_detection(bl_result, ctx)

                elif doc_type == 'DO':
                    # v8.0.6 [MULTI-TEMPLATE]: 다중 템플릿 후보 엔진 적용
                    if _HAS_CANDIDATE_ENGINE:
                        do_result = parse_do_with_candidate(
                            parser,
                            file_path,
                            log_fn=self._log_safe,
                        )
                    else:
                        do_result = parser.parse_do(file_path)
                    self.parsed_results['do'] = do_result
                    if do_result:
                        self._log_safe(f"  ✅ D/O: B/L={getattr(do_result, 'bl_no', '')}")

            except (ValueError, TypeError, AttributeError, RuntimeError) as e:
                self._log_safe(f"  ❌ {doc_type} 파싱 오류: {e}")
                logger.error(f"파싱 오류 [{doc_type}]: {e}", exc_info=True)
                # RuntimeError: Gemini API-Only 실패(예: JSON 추출 실패) → 입고 미완료 → 재고/톤백 리스트에 데이터 없음
                if isinstance(e, RuntimeError) and doc_type == 'PACKING_LIST':
                    self._log_safe("  💡 Packing List 실패 시 입고가 완료되지 않아 톤백 리스트에 표시되지 않습니다.")
            else:
                # 서류 하나 파싱 직후마다 병합 후 미리보기 테이블·메인 화면에 실시간 반영
                self._merge_results(inv_result, pl_result, bl_result, do_result)
                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: self._push_preview_to_main())
                    if not getattr(self, 'compact_mode', False):
                        self.dialog.after(0, lambda: self._refresh_preview_tree_only())

        return pl_result, inv_result, bl_result, do_result, total

    def _pt_parse_bl(self, parser, file_path: str, ctx: dict):  # v8.6.4 [SRP]
        """BL 서류 파싱 — 다중 템플릿 후보 엔진 또는 단일 파싱"""
        # v8.0.6 [MULTI-TEMPLATE]: 다중 템플릿 후보 엔진 적용
        if _HAS_CANDIDATE_ENGINE:
            _use_multi = getattr(self, '_use_multi_template_flag', True)
            bl_result = parse_bl_with_candidate(
                parser,
                file_path,
                hint_bl=ctx['hint_bl'],
                bl_format=ctx['bl_format'],
                log_fn=self._log_safe,
                use_multi=_use_multi,
                db_carrier_id=ctx['tpl_carrier_id'],  # v8.4.5: DB 템플릿 선사 우선
            )
        else:
            bl_result = parser.parse_bl(
                file_path,
                gemini_hint=ctx['hint_bl'],
                bl_format=ctx['bl_format'],
            )
        self.parsed_results['bl'] = bl_result
        if bl_result:
            # v6.4.0: 선사 뱃지 표시
            _carrier_id   = getattr(bl_result, 'carrier_id', '')
            _carrier_name = getattr(bl_result, 'carrier_name', '')
            if _carrier_id and _carrier_id != 'UNKNOWN':
                _badge = f"[선사: {_carrier_name or _carrier_id}]"
            else:
                _badge = "[선사: 미확인]"
            self._log_safe(
                f"  ✅ B/L: {getattr(bl_result, 'bl_no', '')} "
                f"{_badge}  "
                f"Containers: {getattr(bl_result, 'total_containers', 0)}"
            )
            # 선사 뱃지를 UI 레이블에도 업데이트
            if self.dialog and self.dialog.winfo_exists():
                self.dialog.after(
                    0,
                    lambda b=_badge: self._update_carrier_badge(b)
                )
            # v7.4.0: 선사 재파싱 버튼 활성화
            if self.dialog and self.dialog.winfo_exists():
                self.dialog.after(0, lambda: (
                    hasattr(self, 'btn_reparse_carrier') and
                    self.btn_reparse_carrier.config(state='normal')
                ))
        return bl_result

    def _pt_handle_bl_carrier_detection(self, bl_result, ctx: dict):  # v8.6.4 [SRP]
        """BL 파싱 후 선사 감지 → PL/INV 힌트 동적 교체 + 템플릿 자동 매칭"""
        if not bl_result:
            return
        _carrier_id = getattr(bl_result, 'carrier_id', '')
        if not _carrier_id or _carrier_id == 'UNKNOWN':
            return

        # v8.5.9: 선사 미선택 상태에서 파싱 시 BL 감지 선사로 템플릿 자동 매칭
        if not ctx['tpl_carrier_id'] or ctx['tpl_carrier_id'] == 'UNKNOWN':
            try:
                _auto_tpl = self._auto_match_template_by_carrier(_carrier_id)
                if _auto_tpl:
                    ctx['tpl_carrier_id'] = _carrier_id
                    ctx['bag_weight'] = int(_auto_tpl.get('bag_weight_kg', ctx['bag_weight']))
                    ctx['hint_packing'] = str(_auto_tpl.get('gemini_hint_packing', '') or '') or ctx['hint_packing']
                    ctx['hint_invoice'] = str(_auto_tpl.get('gemini_hint_invoice', '') or '') or ctx['hint_invoice']
                    ctx['hint_bl'] = str(_auto_tpl.get('gemini_hint_bl', '') or '') or ctx['hint_bl']
                    ctx['bl_format'] = str(_auto_tpl.get('bl_format', '') or '') or ctx['bl_format']
                    self._inbound_template_data = _auto_tpl
                    self._log_safe(
                        f"  🔄 선사 자동 매칭: {_carrier_id} → "
                        f"템플릿 '{_auto_tpl.get('template_name', '')}' "
                        f"({ctx['bag_weight']}kg)"
                    )
                    # UI 동기화
                    if self.dialog and self.dialog.winfo_exists():
                        self.dialog.after(0, lambda t=_auto_tpl: self._apply_template_to_carrier_badge(t))
            except Exception as _ate:
                logger.debug(f"선사 자동 템플릿 매칭 실패(무시): {_ate}")

        try:
            from features.ai.bl_carrier_registry import CARRIER_TEMPLATES
            _ctpl = CARRIER_TEMPLATES.get(_carrier_id)
            if _ctpl:
                # 수동 선택 Combobox도 동기화
                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.after(
                        0,
                        lambda c=_carrier_id: (
                            hasattr(self, '_carrier_manual_var') and
                            self._carrier_manual_var.set(
                                self._normalize_carrier_for_combo(c)
                            )
                        )
                    )
                # 힌트 교체 (템플릿 힌트 없을 때만)
                if not ctx['hint_packing'] and hasattr(_ctpl, 'bl_no_prompt_hint'):
                    ctx['hint_packing'] = (
                        f"이 서류는 {_ctpl.carrier_name} 선사의 Packing List입니다. "
                        f"BL번호 형식: {_ctpl.bl_format_hint}"
                    )
                if not ctx['hint_invoice'] and hasattr(_ctpl, 'carrier_name'):
                    ctx['hint_invoice'] = (
                        f"이 서류는 {_ctpl.carrier_name} 선사의 Invoice/FA입니다."
                    )
                self._log_safe(
                    f"  🔄 선사 힌트 동적 교체: {_ctpl.carrier_name} "
                    f"(PL힌트={'ON' if ctx['hint_packing'] else 'OFF'}, "
                    f"INV힌트={'ON' if ctx['hint_invoice'] else 'OFF'})"
                )
        except Exception as _he:
            logger.debug(f"선사 힌트 교체 실패(무시): {_he}")

    def _pt_handle_missing_dates(self, do_result):  # v8.6.4 [SRP]
        """D/O 없거나 arrival_date 누락 시 사용자 입력 팝업"""
        # ═══════════════════════════════════════════════════════
        # ★★★ v5.8.7: D/O 없거나 arrival_date 누락 시 사용자 입력
        # ═══════════════════════════════════════════════════════
        self._do_deferred = False  # D/O 추후 첨부 플래그
        _need_date_input = False
        if not do_result:
            _need_date_input = True
            self._log_safe("📋 D/O 미첨부 — 날짜 정보 수동 입력 필요")
        elif self.preview_data and not (self.preview_data[0].get('arrival_date') or '').strip():
            _need_date_input = True
            self._log_safe("📋 D/O에서 입항일 추출 실패 — 수동 입력 필요")

        if _need_date_input and self.preview_data:
            prefilled_ship = ''
            if self.preview_data:
                prefilled_ship = self.preview_data[0].get('ship_date', '') or ''

            import queue
            date_queue = queue.Queue()

            def _show_date_popup():
                self._hide_progress_popup()
                result = self._ask_missing_dates(prefilled_ship, do_result)
                date_queue.put(result)

            if self.dialog and self.dialog.winfo_exists():
                self.dialog.after(0, _show_date_popup)
                try:
                    user_dates = date_queue.get(timeout=300)
                except queue.Empty:
                    user_dates = None

                if user_dates:
                    if user_dates.get('deferred'):
                        # "D/O 추후 첨부" 선택
                        self._do_deferred = True
                        self._log_safe("  📋 D/O 추후 첨부 선택됨 — arrival_date 없이 진행")
                    else:
                        for row in self.preview_data:
                            if user_dates.get('ship_date') and not (row.get('ship_date') or '').strip():
                                row['ship_date'] = user_dates['ship_date']
                            if user_dates.get('arrival_date'):
                                row['arrival_date'] = user_dates['arrival_date']
                            # con_return은 입항일/반납일/Free time 중 하나 입력 시 항상 계산되어 반환됨 — 반드시 적용
                            if 'con_return' in user_dates:
                                row['con_return'] = user_dates.get('con_return', '') or ''
                            if user_dates.get('free_time') is not None:
                                row['free_time'] = str(user_dates.get('free_time', ''))
                        self._log_safe(f"  ✅ 수동 입력: arrival={user_dates.get('arrival_date')}, con_return={user_dates.get('con_return')}, free_time={user_dates.get('free_time')}")
                else:
                    self._log_safe("  ⚠️ 날짜 입력 취소 — arrival_date 없이 진행")

    def _pt_collect_warnings_and_crosscheck(self, pl_result, inv_result, bl_result, do_result):  # v8.6.4 [SRP]
        """파싱 결과 경고 수집 + 크로스 체크 + 에러 복구 다이얼로그"""
        # v3.8.9: 파싱 결과 경고 (누락된 정보)
        _warnings = []
        if not pl_result or not getattr(pl_result, 'lots', None):
            _warnings.append("⚠️ Packing List: LOT 정보 추출 실패")
        if not inv_result or not getattr(inv_result, 'sap_no', None):
            _warnings.append("⚠️ Invoice: SAP번호 추출 실패 — 수동 입력 필요")
        if not bl_result or not getattr(bl_result, 'bl_no', None):
            _warnings.append("⚠️ B/L: BL번호 추출 실패 — 수동 입력 필요")

        # ── v8.6.4: AI 파싱 오류 복구 다이얼로그 ──────────────────────
        self._pt_show_error_recovery_dialog(bl_result, pl_result, inv_result, do_result)

        # v6.2.1: 4종 서류 크로스 체크 엔진 (읽기 전용 검증)
        try:
            from parsers.cross_check_engine import cross_check_documents
            xc = cross_check_documents(
                invoice=inv_result,
                packing_list=pl_result,
                bl=bl_result,
                do=do_result,
            )
            self._cross_check_result = xc

            if not xc.is_clean:
                self._log_safe(f"\n{'='*40}")
                self._log_safe(f"🔍 {xc.summary}")
                for item in xc.items:
                    self._log_safe(f"  {item}")
                self._log_safe(f"{'='*40}")
                # v8.4.5 Rev2: INFO 레벨(환적 자동인식 등)은 팝업 제외, 로그에만 표시
                from parsers.cross_check_engine import CheckLevel as _CL
                for item in xc.items:
                    if item.level >= _CL.WARNING:
                        _warnings.append(str(item))
                if xc.has_critical:
                    _warnings.insert(
                        0,
                        f"🚫 심각한 불일치 {xc.critical_count}건 — 서류 확인 후 재파싱 권장",
                    )
            else:
                self._log_safe("✅ 4종 서류 크로스 체크 통과 — 불일치 없음")
        except (ImportError, Exception) as e:
            logger.debug(f"[CrossCheck] 원스톱 크로스 체크 스킵: {e}")

        if _warnings:
            _warn_msg = "\n".join(_warnings)
            self._log_safe(f"\n{'='*40}\n{_warn_msg}\n{'='*40}")
            # GUI 경고
            def _show_warn():
                from ..utils.custom_messagebox import CustomMessageBox
                try:
                    CustomMessageBox.showwarning(self.dialog, "파싱 결과 확인", _warn_msg)
                except Exception as e:
                    logger.warning(f"파싱 결과 경고창 표시 실패: {e}")
            if self.dialog and self.dialog.winfo_exists():
                self.dialog.after(500, _show_warn)

    def _pt_show_error_recovery_dialog(self, bl_result, pl_result, inv_result, do_result):  # v8.6.4 [SRP]
        """누락 필드 에러코드 분류 후 수동 입력 복구 다이얼로그 표시"""
        try:
            from gui_app_modular.dialogs.parse_error_recovery_dialog import (
                classify_parse_error, show_parse_error_recovery
            )
            _recovery_codes = []
            if bl_result:
                _recovery_codes += classify_parse_error(bl_result)
            if pl_result:
                _recovery_codes += classify_parse_error(pl_result)
            if inv_result:
                _recovery_codes += classify_parse_error(inv_result)
            if do_result:
                _recovery_codes += classify_parse_error(do_result)

            if _recovery_codes:
                self._log_safe(
                    f"[복구] 파싱 누락 필드 감지: {_recovery_codes} → 수동 입력 다이얼로그 표시"
                )
                def _show_recovery_dialog():
                    try:
                        # 각 결과 객체별로 복구 다이얼로그 표시
                        if bl_result:
                            _bl_codes = classify_parse_error(bl_result)
                            if _bl_codes:
                                show_parse_error_recovery(
                                    self.dialog, _bl_codes, bl_result,
                                    title="B/L 파싱 오류 복구"
                                )
                        if pl_result:
                            _pl_codes = classify_parse_error(pl_result)
                            if _pl_codes:
                                show_parse_error_recovery(
                                    self.dialog, _pl_codes, pl_result,
                                    title="Packing List 파싱 오류 복구"
                                )
                        if inv_result:
                            _inv_codes = classify_parse_error(inv_result)
                            if _inv_codes:
                                show_parse_error_recovery(
                                    self.dialog, _inv_codes, inv_result,
                                    title="Invoice 파싱 오류 복구"
                                )
                        if do_result:
                            _do_codes = classify_parse_error(do_result)
                            if _do_codes:
                                show_parse_error_recovery(
                                    self.dialog, _do_codes, do_result,
                                    title="D/O 파싱 오류 복구"
                                )
                    except Exception as _re:
                        logger.debug(f"[복구다이얼로그] 표시 실패: {_re}")

                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.after(100, _show_recovery_dialog)
        except ImportError:
            pass  # noqa: parse_error_recovery_dialog 미존재 시 무시

    def _pt_finalize_preview(self):  # v8.6.4 [SRP]
        """병합 후 메인 반영 + 스냅샷 + 미리보기 + 버튼 활성화"""
        # 병합 직후 메인 화면 재고 리스트에 실시간 반영
        if self.dialog and self.dialog.winfo_exists() and self.preview_data:
            self.dialog.after(0, lambda: self._push_preview_to_main())

        # 파싱 직후 원본 스냅샷(원본 초기화 기준점)
        self._capture_original_preview_state()
        self._sort_col = None
        self._sort_desc = False
        # v6.5.0: tkinter UI는 메인 스레드에서만 호출 — after(0)으로 위임
        if not getattr(self, 'compact_mode', False):
            if self.dialog and self.dialog.winfo_exists():
                self.dialog.after(0, self._update_sort_headings)
            self._update_filter_values_from_preview()
            if self.btn_reset_original and self.btn_reset_original.winfo_exists():
                self.btn_reset_original.config(state='normal' if self._original_preview_data else 'disabled')

        # 표시
        self._update_progress(95, "📋 미리보기 준비...")
        if not getattr(self, 'compact_mode', False) and self.dialog and self.dialog.winfo_exists():
            self.dialog.after(0, self._show_preview_table)
        self._display_preview()
        # 파싱 완료 후 DB 업로드·Excel 버튼이 반드시 보이도록 폴백 (순차 삽입 완료 전에도 활성화)
        _preview_len = len(self.preview_data)
        def _ensure_buttons_visible():
            if not self.dialog or not self.dialog.winfo_exists():
                return
            if _preview_len and getattr(self, 'preview_data', None) and len(self.preview_data) == _preview_len:
                if getattr(self, 'btn_excel', None) and self.btn_excel.winfo_exists():
                    self.btn_excel.config(state='normal')
                if getattr(self, 'btn_upload', None) and self.btn_upload.winfo_exists():
                    if self._has_required_docs():
                        self.btn_upload.config(state='normal')
        # v7.9.9 [Q2]: 템플릿 저장 버튼 활성화
        if getattr(self, 'btn_save_template', None):
            try:
                self.btn_save_template.config(state='normal')
            except Exception as e:
                logger.warning(f"[UI] save template button state change failed: {e}")
            else:
                self.btn_upload.config(state='disabled')
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.after(400, _ensure_buttons_visible)

    def _pt_parse_confirm(self, pl_result, elapsed_str: str):  # v8.6.4 [SRP]
        """파싱 완료 후 체크박스 확인 다이얼로그 (v7.9.9 [PARSE-CONFIRM])"""
        # v8.1.x: 사용자 요청으로 기본 비활성화 (즉시 DB 업로드/Excel 단계로 이동)
        if ENABLE_PARSE_CONFIRM and getattr(self, 'preview_data', None) and len(self.preview_data) > 0:
            try:
                # v8.0.6 [BUG-FIX]: PackingListData에 success 속성 없음
                # getattr(pl_result, 'success', False) 는 항상 False 반환
                # → lots 건수로만 판단하도록 수정
                _pl_ok = (
                    pl_result and
                    len(getattr(pl_result, 'lots', []) or []) > 0
                )
                if not _pl_ok and len(self.preview_data) > 0:
                    import tkinter.messagebox as _mb
                    _go = _mb.askyesno(
                        "PL 검증 경고",
                        "⚠️ Packing List 파싱 실패 또는 LOT 정보 없음\n\n"
                        "PL 없이 저장하면 톤백 수/중량 검증이 생략됩니다.\n"
                        "그래도 저장하시겠습니까?",
                        parent=self.dialog
                    )
                    if not _go:
                        self._update_progress(0, "⚠️ PL 검증 미통과 — DB 저장 중단")
                        self._log_safe("⚠️ [P3] PL 실패로 인해 DB 저장 취소")
                        return

                from .parse_preview_confirm_dialog import ParsePreviewConfirmDialog
                _confirm_dlg = ParsePreviewConfirmDialog(
                    self.dialog, self.preview_data, elapsed_str
                )
                _confirmed = _confirm_dlg.show()
                if not _confirmed:
                    # 사용자가 취소 — 파싱 데이터 초기화
                    self._update_progress(0, "⚠️ 사용자 취소 — DB 저장 중단")
                    self._log_safe("⚠️ 파싱 확인 취소 — DB 저장 중단")
                    return
                # 체크 해제된 행 제거
                _checked = _confirm_dlg.get_checked_indices()
                if len(_checked) < len(self.preview_data):
                    self.preview_data = [
                        self.preview_data[i] for i in _checked
                    ]
                    self._log_safe(
                        f"ℹ️ {len(self.preview_data)}개 LOT 선택 저장 "
                        f"({len(_checked)}/{len(_checked) + (len(self.preview_data) - len(_checked))} 선택)"
                    )
            except Exception as _ce:
                # region agent log
                _dbg_log(
                    "H4",
                    "onestop_inbound.py:parse_confirm_except",
                    "parse confirm dialog skipped by exception",
                    {
                        "error": str(_ce),
                        "preview_len": len(self.preview_data or []),
                        "preview_sample_net_weight": (
                            self.preview_data[0].get("net_weight", None)
                            if self.preview_data else None
                        ),
                    },
                )
                # endregion
                logger.debug(f"[PARSE-CONFIRM] 다이얼로그 생략: {_ce}")
        else:
            # region agent log
            _dbg_log(
                "H5",
                "onestop_inbound.py:parse_confirm_disabled",
                "parse confirm disabled",
                {"enabled": ENABLE_PARSE_CONFIRM, "preview_len": len(self.preview_data or [])},
            )
            # endregion
    
    # ═══════════════════════════════════════════════════════════
    # 데이터 병합 (4종 → 18열)
    # ═══════════════════════════════════════════════════════════
    
    def _merge_results(self, invoice, pl, bl, do) -> list:
        """4종 파싱 결과를 18열 미리보기 데이터로 병합"""
        self.preview_data = []
        self._edited_rows = set()
        self._undo_stack = []
        self._redo_stack = []
        self._update_undo_redo_buttons()
        
        if not pl or not getattr(pl, 'lots', None):
            if invoice and getattr(invoice, 'lot_numbers', None):
                for idx, lot_no in enumerate(getattr(invoice, 'lot_numbers', []), 1):
                    row = self._empty_row(idx)
                    row['sap_no'] = getattr(invoice, 'sap_no', '') or ''
                    row['lot_no'] = lot_no
                    row['product'] = getattr(invoice, 'product', '') or 'LITHIUM CARBONATE'
                    row['salar_invoice_no'] = getattr(invoice, 'salar_invoice_no', '') or ''
                    row['ship_date'] = str(getattr(invoice, 'invoice_date', '')) if getattr(invoice, 'invoice_date', None) else ''
                    if bl:
                        row['bl_no'] = self._format_bl(getattr(bl, 'bl_no', '') or '')
                    self._fill_do(row, do)
                    row['status'] = STATUS_AVAILABLE
                    self.preview_data.append(row)
            elif do and getattr(self.engine, 'db', None):
                # D/O만 있는 경우: DB에서 기존 LOT(B/L 기준) 자동 조회해 미리보기 구성
                try:
                    do_bl_raw = str(getattr(do, 'bl_no', '') or '').strip()
                    do_bl_fmt = self._format_bl(do_bl_raw)
                    candidates = [x for x in {do_bl_raw, do_bl_fmt} if x]
                    db_rows = []
                    for c in candidates:
                        rows = self.engine.db.fetchall(
                            "SELECT * FROM inventory WHERE bl_no = ? ORDER BY lot_no",
                            (norm_bl_no_for_query(c) or c,)  # v9.0
                        ) or []
                        if rows:
                            db_rows = rows
                            break
                    for idx, rec in enumerate(db_rows, 1):
                        row = self._empty_row(idx)
                        row['sap_no'] = str(rec.get('sap_no', '') or '')
                        row['bl_no'] = str(rec.get('bl_no', '') or do_bl_fmt or do_bl_raw or '')
                        row['container_no'] = str(rec.get('container_no', '') or '')
                        row['product'] = str(rec.get('product', '') or 'LITHIUM CARBONATE')
                        row['product_code'] = str(rec.get('product_code', '') or '')
                        row['lot_no'] = str(rec.get('lot_no', '') or '')
                        row['lot_sqm'] = str(rec.get('lot_sqm', '') or '')
                        row['mxbg_pallet'] = str(rec.get('mxbg_pallet', '') or '10')
                        _nw = rec.get('net_weight', '')
                        _gw = rec.get('gross_weight', '')
                        row['net_weight'] = f"{float(_nw):,.1f}" if str(_nw) not in ('', 'None', 'none') else ''
                        row['gross_weight'] = f"{float(_gw):,.3f}" if str(_gw) not in ('', 'None', 'none') else ''
                        row['salar_invoice_no'] = str(rec.get('salar_invoice_no', '') or '')
                        row['ship_date'] = str(rec.get('ship_date', '') or '')[:10]
                        row['arrival_date'] = str(rec.get('arrival_date', '') or '')[:10]
                        row['con_return'] = str(rec.get('con_return', '') or '')[:10]
                        row['free_time'] = str(rec.get('free_time', '') or '')
                        row['warehouse'] = str(rec.get('warehouse', '') or DEFAULT_WAREHOUSE)
                        row['status'] = str(rec.get('status', '') or STATUS_AVAILABLE)
                        self._fill_do(row, do)
                        self.preview_data.append(row)
                    if self.preview_data:
                        self._log_safe(f"📎 D/O 기반 DB 자동매칭: {len(self.preview_data)}건 (B/L 기준)")
                except Exception as e:
                    logger.debug(f"D/O 단독 DB 자동매칭 실패: {e}")
            return
        
        _lots = list(getattr(pl, 'lots', []) or [])
        _lots_sorted = sorted(
            enumerate(_lots, 1),
            key=lambda p: self._lot_order_key(p[1], p[0])
        )
        for idx, (_src, lot) in enumerate(_lots_sorted, 1):
            row = self._empty_row(idx)
            row['sap_no'] = getattr(pl, 'sap_no', '') or (getattr(invoice, 'sap_no', '') if invoice else '') or ''
            row['container_no'] = getattr(lot, 'container_no', '') or ''
            row['product'] = getattr(pl, 'product', '') or 'LITHIUM CARBONATE'
            row['product_code'] = getattr(pl, 'code', '') or ''
            row['lot_no'] = getattr(lot, 'lot_no', '') or ''
            row['lot_sqm'] = getattr(lot, 'lot_sqm', '') or ''
            
            _mxbg = getattr(lot, 'mxbg_pallet', None)
            row['mxbg_pallet'] = str(_mxbg) if _mxbg else '10'
            
            _nw = getattr(lot, 'net_weight_kg', None)
            row['net_weight'] = f"{float(_nw):,.1f}" if _nw else ''
            
            _gw = getattr(lot, 'gross_weight_kg', None)
            row['gross_weight'] = f"{float(_gw):,.3f}" if _gw else ''
            
            # v3.8.8: B/L ship_date 우선, Invoice 폴백 — 업로드3/4: 파싱값으로 채움 (날짜는 YYYY-MM-DD)
            if bl:
                row['bl_no'] = self._format_bl(getattr(bl, 'bl_no', '') or '')
                _sd = getattr(bl, 'ship_date', None)
                if _sd:
                    row['ship_date'] = str(_sd)[:10] if len(str(_sd)) >= 10 else str(_sd)
            
            if invoice:
                row['salar_invoice_no'] = getattr(invoice, 'salar_invoice_no', '') or ''
                if not (row.get('ship_date') or '').strip():
                    _id = getattr(invoice, 'invoice_date', None)
                    if _id:
                        row['ship_date'] = str(_id)[:10] if len(str(_id)) >= 10 else str(_id)
                if not row['sap_no']:
                    row['sap_no'] = getattr(invoice, 'sap_no', '') or ''
            
            self._fill_do(row, do)
            if not (row.get('warehouse') or '').strip():
                row['warehouse'] = DEFAULT_WAREHOUSE
            row['status'] = STATUS_AVAILABLE
            self.preview_data.append(row)
    
    def _empty_row(self, no: int) -> dict:
        row = {col[0]: '' for col in PREVIEW_COLUMNS}
        row['no'] = str(no)
        return row
    
    def _date_str(self, val) -> str:
        """날짜를 YYYY-MM-DD 문자열로. None/'None'/비어있으면 '' 반환 (date.today() 사용 안 함)."""
        if val is None or (isinstance(val, str) and (not val.strip() or val.strip() in ('None', 'none'))):
            return ''
        if hasattr(val, 'isoformat'):
            return str(val.isoformat())[:10]
        s = str(val).strip()
        return s[:10] if len(s) >= 10 and s not in ('None', 'none') else (s if s and s not in ('None', 'none') else '')

    def _format_bl(self, bl_no) -> str:
        if not bl_no:
            return ''
        bl_no = str(bl_no).strip()
        if bl_no.isdigit() and len(bl_no) >= 9:
            return f"MAEU{bl_no}"
        return bl_no
    
    def _fill_do(self, row: dict, do) -> None:
        """v3.8.8: D/O 데이터로 미리보기 행 보완 (free_time 계산 포함)"""
        if not do:
            return
        if not row.get('bl_no') and getattr(do, 'bl_no', None):
            row['bl_no'] = str(getattr(do, 'bl_no', ''))
        
        # arrival_date (업로드3/4: D/O 파싱값으로 채움, YYYY-MM-DD)
        # v5.8.8: 날짜가 아닌 값(예: '광양')이면 넣지 않음 — ARRIVAL 컬럼 혼동 방지
        arr = getattr(do, 'arrival_date', None)
        if arr and str(arr) != 'None':
            _s = str(arr).strip()[:10]
            if len(_s) == 10 and _s.count('-') == 2 and _s.replace('-', '').isdigit():
                row['arrival_date'] = _s
        
        # warehouse
        wh = getattr(do, 'warehouse_name', '') or getattr(do, 'warehouse', '')
        if wh:
            row['warehouse'] = str(wh)
        
        # FREE TIME = con_return(컨테이너 반납일) - arrival_date (일수). D/O의 Free_Time 컬럼 = 반납일
        ft_infos = getattr(do, 'free_time_info', []) or []
        if ft_infos and arr and str(arr) != 'None':
            try:
                con_return_str = ''
                for ft in ft_infos:
                    # v8.7.0 [FIX D-1.4]: FreeTimeInfo.free_time_until 필드 없음 — dead fallback 제거
                    ftd = getattr(ft, 'free_time_date', '') if not isinstance(ft, dict) else (ft.get('free_time_date') or '')
                    if ftd and str(ftd) != 'None':
                        con_return_str = str(ftd)[:10]
                        break
                if not con_return_str:
                    logger.debug(
                        "[원스톱 미리보기] D/O free_time_info 있으나 반납일 없음 — CON RETURN/FREE TIME 빈칸. 항목 수: %s",
                        len(ft_infos),
                    )
                if con_return_str:
                    con_return_dt = datetime.strptime(con_return_str, '%Y-%m-%d').date()
                    arr_dt = datetime.strptime(str(arr)[:10], '%Y-%m-%d').date()
                    days = (con_return_dt - arr_dt).days
                    row['free_time'] = str(max(0, days))
                    row['con_return'] = str(con_return_str)[:10]
                    logger.debug(
                        "[원스톱 미리보기] D/O 반납일 적용: con_return=%s, free_time(일수)=%s",
                        row['con_return'],
                        row['free_time'],
                    )
            except (ValueError, TypeError) as e:
                logging.getLogger(__name__).debug(f"free_time 계산 실패: {e}")
        # 업로드4: free_time 일수만 있는 경우 → free_time_info[0].storage_free_days 참조
        # v8.7.0 [FIX D-1.4]: DOData.free_time 필드 없음(항상 None) → ft_infos[0].storage_free_days로 교체.
        if not (row.get('free_time') or '').strip():
            days_val = None
            try:
                for _fti in (ft_infos or []):
                    sfd = getattr(_fti, 'storage_free_days', None) if not isinstance(_fti, dict) else _fti.get('storage_free_days')
                    if sfd and int(sfd) > 0:
                        days_val = int(sfd)
                        break
            except (TypeError, ValueError) as _sfe:
                logger.debug(f"storage_free_days 추출 실패(무시): {_sfe}")
            if days_val is not None:
                row['free_time'] = str(days_val)
                # FREE TIME 일수만 있으면 반납일(con_return) = arrival_date + 일수
                if not (row.get('con_return') or '').strip() and arr and str(arr) != 'None':
                    try:
                        arr_dt = datetime.strptime(str(arr)[:10], '%Y-%m-%d').date()
                        con_dt = arr_dt + timedelta(days=int(days_val))
                        row['con_return'] = con_dt.strftime('%Y-%m-%d')
                    except (ValueError, TypeError):
                        logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
    
    # ═══════════════════════════════════════════════════════════
    # ★★★ v5.8.7: 날짜 입력 팝업 (DatePicker 달력 UI)
    # ═══════════════════════════════════════════════════════════
    
    def _ask_missing_dates(self, prefilled_ship: str = '', do_result=None) -> dict:
        """
        사용자에게 입항일·반납기한·Free time을 물어보는 DatePicker 팝업.
        선적일(Ship Date)은 B/L에서 이미 추출되어 톤백 리스트에 있으므로 묻지 않음.
        
        호출 조건:
            1) D/O 자체가 없을 때
            2) D/O는 있는데 arrival_date 추출 실패 시
        
        UI:
            - 입항일(필수), 컨테이너 반납기한(con_return), Free time(일수).
            - 도착일·con_return·free time 중 하나만 입력해도 나머지 자동 계산. 반납일-입항일=Free time.
            - gui_bootstrap HAS_DATEENTRY면 달력, 없으면 텍스트 입력. "D/O 추후 첨부" 가능.
        
        Returns:
            dict: {'ship_date': str, 'arrival_date': str, 'con_return': str, 'free_time': str}
            또는 {'deferred': True} (D/O 추후 첨부)
            또는 None (취소)
        """
        result_holder = [None]
        
        def _build_popup():
            win = None
            try:
                win = create_themed_toplevel(self.dialog)
                
                if not do_result:
                    win.title("📋 D/O 미첨부 — 날짜 정보 입력")
                    msg_text = "D/O가 없습니다. 입항일 등을 직접 입력하거나,\n나중에 D/O를 추가할 수 있습니다."
                else:
                    win.title("📋 D/O 파싱 실패 — 날짜 정보 입력")
                    msg_text = "D/O에서 날짜를 읽지 못했습니다.\n직접 입력하거나 나중에 D/O를 다시 첨부할 수 있습니다."
                
                win.geometry(DialogSize.get_geometry(self.dialog, 'medium'))
                apply_modal_window_options(win)
                win.transient(self.dialog)
                win.grab_set()
                center_dialog(win, self.dialog)
                
                frame = ttk.Frame(win, padding=20)
                frame.pack(fill=tk.BOTH, expand=True)
                
                # 안내 메시지
                ttk.Label(frame, text=msg_text,
                         font=('맑은 고딕', 11, 'bold'),
                         wraplength=460).pack(anchor='w', pady=(0, 12))
                
                # ── 날짜/입력 필드 공통 참조: .get(), .set(val), .widget ──
                class _FieldRef:
                    def __init__(self, get_fn, widget, set_fn):
                        self.get = get_fn
                        self.widget = widget
                        self.set = set_fn
                
                # ── 헬퍼: DateEntry( gui_bootstrap ) 또는 텍스트 입력 생성 ──
                def _make_date_field(parent, label, hint, prefill='', required=False):
                    """HAS_DATEENTRY면 ttkbootstrap 달력, 없으면 텍스트 입력. _FieldRef 반환( .get/.set/.widget )"""
                    _cal_dark = is_dark()
                    lf = ttk.LabelFrame(parent,
                        text=f"{'★ ' if required else ''}{label}{' — 필수' if required else ''}",
                        padding=8)
                    lf.pack(fill=tk.X, pady=(0, 8))
                    
                    var = tk.StringVar(value=prefill)
                    
                    if HAS_DATEENTRY and DateEntry is not None:
                        startdate = None
                        if prefill:
                            try:
                                parts = prefill.split('-')
                                startdate = _date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                            except (ValueError, IndexError):
                                logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
                        de = DateEntry(lf, dateformat='%Y-%m-%d', startdate=startdate,
                                       bootstyle='info', width=16)
                        de.pack(side=tk.LEFT, padx=(0, 8))
                        ttk.Label(lf, text=hint,
                                 font=('맑은 고딕', 10), foreground=ThemeColors.get('text_muted', _cal_dark)).pack(side=tk.LEFT)
                        def _get():
                            return (de.entry.get() or '').strip() if de and de.winfo_exists() else ''
                        def _set(v):
                            if de and de.winfo_exists():
                                try:
                                    parts = str(v).strip().split('-')
                                    if len(parts) == 3:
                                        d = _date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                                        de.configure(startdate=d)
                                        de.entry.delete(0, tk.END)
                                        de.entry.insert(0, d.strftime('%Y-%m-%d'))
                                    else:
                                        de.entry.delete(0, tk.END)
                                        de.entry.insert(0, str(v))
                                except (ValueError, IndexError, TypeError):
                                    de.entry.delete(0, tk.END)
                                    de.entry.insert(0, str(v))
                        return _FieldRef(_get, de, _set)
                    else:
                        entry = ttk.Entry(lf, textvariable=var,
                                         font=('맑은 고딕', 11), width=16)
                        entry.pack(side=tk.LEFT, padx=(0, 8))
                        ttk.Label(lf, text=hint,
                                 font=('맑은 고딕', 10), foreground=ThemeColors.get('text_muted', _cal_dark)).pack(side=tk.LEFT)
                        return _FieldRef(lambda: (var.get() or '').strip(), entry, var.set)
                
                # ── 선적일(ship_date) 미표시 — B/L에서 추출되므로 톤백 리스트에 이미 있음 ──
                ship_var = None
                
                arrival_var = _make_date_field(frame,
                    "입항일 (Arrival Date)",
                    "YYYY-MM-DD (예: 2025-10-17)",
                    required=True)
                
                con_return_ref = _make_date_field(frame,
                    "컨테이너 반납기한 (con_return)",
                    "반납일 YYYY-MM-DD (비우면 Free time 일수로)")
                
                # Free time은 일수(숫자) 전용 — DateEntry 사용 시 '14' 입력이 깨지므로 항상 Entry
                _ft_dark = is_dark()
                lf_ft = ttk.LabelFrame(frame, text="Free time (일수)", padding=8)
                lf_ft.pack(fill=tk.X, pady=(0, 8))
                ft_var = tk.StringVar(value='')
                ft_entry = ttk.Entry(lf_ft, textvariable=ft_var, font=('맑은 고딕', 11), width=10)
                ft_entry.pack(side=tk.LEFT, padx=(0, 8))
                ttk.Label(lf_ft, text="반납일-입항일=Free time (둘 중 하나만 입력 시 나머지 자동 계산·자동 입력 시 상대 필드 비활성화)",
                         font=('맑은 고딕', 10), foreground=ThemeColors.get('text_muted', _ft_dark)).pack(side=tk.LEFT)
                ft_ref = _FieldRef(lambda: (ft_var.get() or '').strip(), ft_entry, ft_var.set)
                
                # 에러 표시
                err_var = tk.StringVar()
                _err_dark = is_dark()
                ttk.Label(frame, textvariable=err_var,
                         font=('맑은 고딕', 10), foreground=ThemeColors.get('danger', _err_dark)).pack(anchor='w', pady=(4, 0))
                
                # ── con_return ↔ free_time 상호 계산·비활성화 (둘 중 하나 입력 시 상대 필드 자동 계산 후 비활성화) ──
                _updating_silently = {'v': False}
                def _sync_from_con_return(*_):
                    if _updating_silently['v']:
                        return
                    arr = (arrival_var.get() or '').strip()
                    cr = (con_return_ref.get() or '').strip()
                    if not arr or not cr or not _validate_date(arr) or not _validate_date(cr):
                        return
                    try:
                        arr_d = _date_type(*[int(x) for x in arr.split('-')])
                        cr_d = _date_type(*[int(x) for x in cr.split('-')])
                        ft_days = max(0, (cr_d - arr_d).days)
                        _updating_silently['v'] = True
                        ft_ref.set(str(ft_days))
                        ft_entry.config(state='disabled')
                    except (ValueError, IndexError, TypeError):
                        logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
                    finally:
                        _updating_silently['v'] = False
                def _sync_from_ft(*_):
                    if _updating_silently['v']:
                        return
                    arr = (arrival_var.get() or '').strip()
                    ft_raw = (ft_ref.get() or '').strip()
                    if not arr or not ft_raw or not _validate_date(arr):
                        return
                    if not ft_raw.isdigit() or int(ft_raw) < 0:
                        return
                    try:
                        arr_d = _date_type(*[int(x) for x in arr.split('-')])
                        cr_d = arr_d + timedelta(days=int(ft_raw))
                        cr_str = cr_d.strftime('%Y-%m-%d')
                        _updating_silently['v'] = True
                        con_return_ref.set(cr_str)
                        w = con_return_ref.widget
                        if hasattr(w, 'entry'):
                            w.entry.config(state='disabled')
                        else:
                            w.config(state='disabled')
                    except (ValueError, IndexError, TypeError):
                        logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
                    finally:
                        _updating_silently['v'] = False
                def _enable_both():
                    _updating_silently['v'] = True
                    try:
                        ft_entry.config(state='normal')
                        w = con_return_ref.widget
                        if hasattr(w, 'entry'):
                            w.entry.config(state='normal')
                        else:
                            w.config(state='normal')
                    finally:
                        _updating_silently['v'] = False
                # FocusOut 바인딩 (입력 완료 후 상대 필드 계산·비활성화)
                if hasattr(con_return_ref.widget, 'entry'):
                    con_return_ref.widget.entry.bind('<FocusOut>', _sync_from_con_return)
                else:
                    con_return_ref.widget.bind('<FocusOut>', _sync_from_con_return)
                ft_entry.bind('<FocusOut>', _sync_from_ft)
                
                # ── 날짜 검증 함수 ──
                def _validate_date(s):
                    import re as _re
                    if not s:
                        return True
                    s = s.strip()
                    if _re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', s):
                        try:
                            parts = s.split('-')
                            _date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                            return True
                        except ValueError:
                            return False
                    return False
                
                # ── 확인 버튼 ── (반납일 또는 Free time 중 하나만 알면 나머지 자동 계산)
                def _on_ok():
                    err_var.set('')
                    try:
                        arr = (arrival_var.get() or '').strip()
                        if not arr:
                            err_var.set("⚠️ 입항일은 필수입니다!")
                            return
                        if not _validate_date(arr):
                            err_var.set("⚠️ 입항일 형식 오류 (YYYY-MM-DD)")
                            return
                        arr_d = _date_type(*[int(x) for x in arr.split('-')])
                    except (ValueError, IndexError, TypeError) as e:
                        err_var.set("⚠️ 입항일 파싱 오류 (YYYY-MM-DD)")
                        logger.debug(f"[_ask_missing_dates] 입항일 파싱: {e}")
                        return
                    # arrival_date > ship_date (선적일이 있으면)
                    if prefilled_ship and _validate_date(prefilled_ship.strip()):
                        try:
                            ship_d = _date_type(*[int(x) for x in prefilled_ship.strip().split('-')])
                            if arr_d <= ship_d:
                                err_var.set("⚠️ 입항일은 선적일보다 이후여야 합니다.")
                                return
                        except (ValueError, IndexError, TypeError):
                            logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
                    ship = ''
                    if ship_var is not None:
                        ship = (ship_var.get() or '').strip()
                        if ship and not _validate_date(ship):
                            err_var.set("⚠️ 선적일 형식 오류 (YYYY-MM-DD)")
                            return
                    con_return_str = (con_return_ref.get() or '').strip()
                    ft_raw = (ft_var.get() or '').strip()
                    free_time_str = ''
                    try:
                        # free_time을 입력했으면 이를 우선 기준으로 con_return을 계산
                        # (DateEntry 표시값 지연 반영/잠금 상태에서도 일관된 결과 보장)
                        if ft_raw:
                            if not ft_raw.isdigit() or int(ft_raw) < 0:
                                err_var.set("⚠️ Free time: 0 이상 일수(숫자) 입력")
                                return
                            free_time_str = ft_raw
                            con_return_d = arr_d + timedelta(days=int(ft_raw))
                            con_return_str = con_return_d.strftime('%Y-%m-%d')
                        elif con_return_str:
                            if not _validate_date(con_return_str):
                                err_var.set("⚠️ 반납기한(con_return): YYYY-MM-DD 형식")
                                return
                            cr_d = _date_type(*[int(x) for x in con_return_str.split('-')])
                            free_time_str = str(max(0, (cr_d - arr_d).days))
                        else:
                            free_time_str = '14'
                            con_return_str = (arr_d + timedelta(days=14)).strftime('%Y-%m-%d')
                    except (ValueError, IndexError, TypeError) as e:
                        err_var.set("⚠️ 반납일/Free time 계산 오류 — 형식 확인")
                        logger.debug(f"[_ask_missing_dates] 반납일·Free time: {e}")
                        return
                    # con_return >= arrival_date (당일 반납 포함 허용)
                    try:
                        cr_d = _date_type(*[int(x) for x in con_return_str.split('-')])
                        if cr_d < arr_d:
                            err_var.set("⚠️ 컨테이너 반납일은 입항일과 같거나 이후여야 합니다.")
                            return
                    except (ValueError, IndexError, TypeError):
                        logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
                    # 사용자 확인 단계: Free time·반납일 표시 후 맞음/다시 입력 선택
                    from ..utils.custom_messagebox import CustomMessageBox
                    confirmed = CustomMessageBox._create_dialog(
                        win, "입력 확인",
                        f"Free time {free_time_str}일, 컨테이너 반납일은 {con_return_str} 입니다.\n\n맞습니까?",
                        'question',
                        [('맞음', True), ('다시 입력', False)],
                        default_button=0
                    )
                    if not confirmed:
                        return  # 다시 입력 — 날짜 팝업 유지, 사용자가 수정 후 재확인 가능
                    result_holder[0] = {
                        'ship_date': ship,
                        'arrival_date': arr,
                        'con_return': con_return_str,
                        'free_time': free_time_str,
                    }
                    win.destroy()
                    return
                
                # ── D/O 추후 첨부 버튼 ──
                def _on_defer():
                    result_holder[0] = {'deferred': True}
                    win.destroy()
                
                # ── 취소 ──
                def _on_cancel():
                    result_holder[0] = None
                    win.destroy()
                
                # ── 버튼 배치 ──
                btn_frame = ttk.Frame(frame)
                btn_frame.pack(fill=tk.X, pady=(12, 0))
                
                ttk.Button(btn_frame, text="✅ 확인",
                          command=_on_ok, width=10).pack(side=tk.LEFT, padx=(0, 8))
                
                ttk.Button(btn_frame, text="✏️ 수정",
                          command=_enable_both, width=10).pack(side=tk.LEFT, padx=(0, 8))
                
                ttk.Button(btn_frame, text="📋 D/O 추후 첨부",
                          command=_on_defer, width=16).pack(side=tk.LEFT, padx=(0, 8))
                
                ttk.Button(btn_frame, text="❌ 취소",
                          command=_on_cancel, width=10).pack(side=tk.LEFT)
                
                win.protocol("WM_DELETE_WINDOW", _on_cancel)
                return win
                
            except Exception as e:
                logger.error(f"[_ask_missing_dates] 팝업 오류: {e}", exc_info=True)
                return None
        
        if not self.dialog or not self.dialog.winfo_exists():
            return None
        
        win = _build_popup()
        if win and win.winfo_exists():
            win.wait_window(win)
        return result_holder[0]
    
    # ═══════════════════════════════════════════════════════════
    # 미리보기 표시
    # ═══════════════════════════════════════════════════════════
    
    def _push_preview_to_main(self) -> None:
        """파싱된 미리보기 데이터를 메인 화면 재고 리스트에 실시간 반영"""
        if not getattr(self, 'app', None) or not hasattr(self.app, '_set_parsing_preview_data'):
            return
        if not self.preview_data:
            return
        try:
            self.app._set_parsing_preview_data(list(self.preview_data))
        except (RuntimeError, ValueError, TypeError) as e:
            logger.debug(f"푸시 미리보기 실패: {e}")

    def _clear_preview_from_main(self) -> None:
        """메인 화면 파싱 미리보기 해제 후 DB 기준으로 복원"""
        if not getattr(self, 'app', None) or not hasattr(self.app, '_set_parsing_preview_data'):
            return
        try:
            self.app._set_parsing_preview_data(None)
        except (RuntimeError, ValueError, TypeError) as e:
            logger.debug(f"미리보기 해제 실패: {e}")

    def _format_container_display(self, val) -> str:
        """컨테이너 번호: 디폴트로 접미사 -숫자 제거. 표시 옵션 켜면 원문 반환."""
        if not val or not isinstance(val, str):
            return val or ''
        if getattr(self, '_show_container_suffix', False):
            return val.strip()
        s = val.strip()
        if '-' in s:
            pre, _, suf = s.rpartition('-')
            if suf.isdigit():
                return pre
        return s
    
    def _on_toggle_container_suffix(self) -> None:
        """컨테이너 접미사 표시 체크 시 미리보기 테이블 갱신"""
        var = getattr(self, '_var_show_container_suffix', None)
        self._show_container_suffix = bool(var and var.get())
        if self.preview_data and getattr(self, 'tree', None) and self.tree.winfo_exists():
            self._refresh_preview_tree_only()
    
    def _row_display_values(self, row: dict) -> tuple:
        """한 행의 표시용 values (container_no는 접미사 옵션 적용)."""
        out = []
        for col in PREVIEW_COLUMNS:
            key = col[0]
            if key == 'container_no':
                out.append(self._format_container_display(row.get(key, '')))
            else:
                out.append(row.get(key, ''))
        return tuple(out)

    def _lot_order_key(self, lot, fallback_idx: int) -> tuple:
        """Packing List 원본 순서를 우선 유지(list_no 기준)."""
        raw = getattr(lot, 'list_no', None)
        if raw is None and isinstance(lot, dict):
            raw = lot.get('list_no')
        try:
            return (0, int(str(raw).strip()))
        except (ValueError, TypeError):
            return (1, int(fallback_idx))

    def _capture_original_preview_state(self) -> None:
        """파싱 직후 원본 데이터 스냅샷 저장."""
        self._original_preview_data = deepcopy(self.preview_data or [])

    def _reset_preview_to_original(self) -> None:
        """원본 초기화: 파싱 직후 상태로 복원."""
        if not self._original_preview_data:
            return
        from ..utils.custom_messagebox import CustomMessageBox
        if not CustomMessageBox.askyesno(self.dialog, "원본 초기화", "현재 편집/정렬/필터 상태를 버리고\n파싱 직후 원본으로 되돌릴까요?"):
            return
        self.preview_data = deepcopy(self._original_preview_data)
        self._edited_rows = set()
        self._undo_stack = []
        self._redo_stack = []
        self._sort_col = None
        self._sort_desc = False
        self._update_sort_headings()
        try:
            if self.filter_bar:
                self.filter_bar._reset_filters()
        except Exception as e:
            logger.debug(f"원본 초기화 필터 리셋 실패(무시): {e}")
        self._update_filter_values_from_preview()
        self._update_undo_redo_buttons()
        self._refresh_preview_tree_only()
        self._update_summary()
        self._push_preview_to_main()

    def _show_preview_table(self) -> None:
        """v6.5.0: 파싱 완료 후 미리보기 테이블 표시. compact_mode에서는 no-op."""
        if getattr(self, 'compact_mode', False) or not getattr(self, '_tree_frame', None):
            return
        if getattr(self, "_tree_frame_visible", False):
            return
        try:
            self._tree_frame.pack(fill=BOTH, expand=YES, pady=(0, 3))
            self._tree_frame_visible = True
        except Exception as e:
            logger.warning(f"[UI] show preview table failed: {e}")

    def _hide_preview_table(self) -> None:
        """v6.5.0: 미리보기 테이블 숨김. compact_mode에서는 no-op."""
        if getattr(self, 'compact_mode', False) or not getattr(self, '_tree_frame', None):
            return
        if not getattr(self, "_tree_frame_visible", False):
            return
        try:
            self._tree_frame.pack_forget()
            self._tree_frame_visible = False
        except Exception as e:
            logger.warning(f"[UI] hide preview table failed: {e}")

    def _update_sort_headings(self) -> None:
        if getattr(self, 'compact_mode', False):
            return
        if not getattr(self, 'tree', None) or not self.tree.winfo_exists():
            return
        for col_id, header, _w, _a in PREVIEW_COLUMNS:
            suffix = ""
            if col_id == self._sort_col:
                suffix = " ▼" if self._sort_desc else " ▲"
            self.tree.heading(
                col_id, text=f"{header}{suffix}", anchor='center',
                command=lambda c=col_id: self._toggle_preview_sort(c))

    def _toggle_preview_sort(self, col_id: str) -> None:
        if self._sort_col == col_id:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col_id
            self._sort_desc = False
        self._update_sort_headings()
        self._refresh_preview_tree_only()

    def _on_change_preview_filter(self) -> None:
        self._refresh_preview_tree_only()

    def _update_filter_values_from_preview(self) -> None:
        if not self.filter_bar:
            return
        for col_id in ('sap_no', 'bl_no', 'container_no', 'product', 'status'):
            vals = [str((r.get(col_id, '') if isinstance(r, dict) else '') or '').strip() for r in (self.preview_data or [])]
            self.filter_bar.update_filter_values(col_id, [v for v in vals if v])

    def _item_to_source_index(self, item_id: str) -> int:
        try:
            return int(str(item_id))
        except (TypeError, ValueError):
            try:
                return self.tree.index(item_id)
            except Exception as e:
                logger.warning(f"[UI] tree item index lookup failed: {e}")
                return -1

    def _matches_preview_filters(self, row: dict) -> bool:
        if not self.filter_bar:
            return True
        filters = self.filter_bar.get_filters()
        if not filters:
            return True
        for col_id, expected in filters.items():
            if str(row.get(col_id, '') or '').strip() != str(expected).strip():
                return False
        return True

    def _preview_sort_key(self, row: dict):
        col = self._sort_col
        if not col:
            return 0
        val = row.get(col, '')
        s = str(val or '').strip()
        if col in {'mxbg_pallet', 'free_time', 'net_weight', 'gross_weight'}:
            try:
                return float(s.replace(',', '')) if s else -1.0
            except ValueError:
                return -1.0
        if col in {'ship_date', 'arrival_date', 'con_return'}:
            return s[:10]
        return s.upper()

    def _build_view_indices(self) -> list:
        indices = [i for i, r in enumerate(self.preview_data or []) if self._matches_preview_filters(r)]
        if self._sort_col:
            indices = sorted(
                indices,
                key=lambda i: self._preview_sort_key(self.preview_data[i]),
                reverse=self._sort_desc
            )
        return indices

    def _get_upload_rows_for_db(self) -> list:
        """DB 업로드 대상 행 순서 결정.

        - 기본: 원본(preview_data) 순서
        - 옵션 체크 시: 현재 화면의 정렬/필터(view) 순서
        """
        rows = list(getattr(self, 'preview_data', []) or [])
        use_view_order = bool(self._var_upload_by_view_order and self._var_upload_by_view_order.get())
        if not use_view_order:
            self._log_safe("📌 DB 업로드 순서: 원본 순서(preview_data)")
            return rows
        indices = self._build_view_indices()
        ordered = [deepcopy(rows[i]) for i in indices if 0 <= i < len(rows)]
        self._log_safe(f"📌 DB 업로드 순서: 화면 정렬/필터 순서 적용 ({len(ordered)}건)")
        return ordered

    def _sync_tree_edit_to_preview_data(self) -> None:
        """v8.6.4: GlobalEditableTree 편집 후 preview_data 동기화.

        트리뷰에서 수정된 값을 preview_data에 반영하여
        DB 업로드 시 수정된 값이 사용되도록 함.
        """
        if not hasattr(self, 'tree') or not hasattr(self, 'preview_data'):
            return
        try:
            columns = [c for c, *_ in getattr(self, 'PREVIEW_COLUMNS', [])]
            if not columns:
                columns = list(self.tree['columns'])
            for item_id in self.tree.get_children():
                values = self.tree.item(item_id, 'values')
                # preview_data 인덱스 찾기
                idx = list(self.tree.get_children()).index(item_id)
                if idx < len(self.preview_data):
                    row = self.preview_data[idx]
                    if isinstance(row, dict):
                        for ci, col_id in enumerate(columns):
                            if ci < len(values):
                                row[col_id] = values[ci]
            logger.debug(f"[v8.6.4] preview_data 동기화 완료: {len(self.preview_data)}행")
        except Exception as e:
            logger.debug(f"[v8.6.4] preview_data 동기화 스킵: {e}")

    def _setup_preview_edit_bindings(self) -> None:
        """업로드1 미리보기: 엑셀형 셀 편집/복사/붙여넣기 바인딩."""
        if not getattr(self, 'tree', None):
            return
        self.tree.bind('<Double-1>', self._on_preview_cell_edit, add='+')
        self.tree.bind('<Button-1>', self._capture_preview_anchor, add='+')
        self.tree.bind('<Control-c>', self._copy_preview_selection, add='+')
        self.tree.bind('<Control-C>', self._copy_preview_selection, add='+')
        self.tree.bind('<Control-v>', self._paste_preview_from_clipboard, add='+')
        self.tree.bind('<Control-V>', self._paste_preview_from_clipboard, add='+')
        self.tree.bind('<Control-x>', self._cut_preview_selection, add='+')
        self.tree.bind('<Control-X>', self._cut_preview_selection, add='+')
        self.tree.bind('<Delete>', self._clear_preview_selection, add='+')
        self.tree.bind('<Control-z>', self._undo_preview_edit, add='+')
        self.tree.bind('<Control-Z>', self._undo_preview_edit, add='+')
        self.tree.bind('<Control-y>', self._redo_preview_edit, add='+')
        self.tree.bind('<Control-Y>', self._redo_preview_edit, add='+')
        if getattr(self, 'dialog', None):
            self.dialog.bind('<Control-z>', self._undo_preview_edit, add='+')
            self.dialog.bind('<Control-Z>', self._undo_preview_edit, add='+')
            self.dialog.bind('<Control-y>', self._redo_preview_edit, add='+')
            self.dialog.bind('<Control-Y>', self._redo_preview_edit, add='+')
            self.dialog.bind('<Control-x>', self._cut_preview_selection, add='+')
            self.dialog.bind('<Control-X>', self._cut_preview_selection, add='+')
            self.dialog.bind('<Delete>', self._clear_preview_selection, add='+')

    def _snapshot_preview_state(self) -> dict:
        return {
            'preview_data': deepcopy(self.preview_data),
            'edited_rows': set(self._edited_rows),
        }

    def _push_undo_snapshot(self) -> None:
        self._undo_stack.append(self._snapshot_preview_state())
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_redo_buttons()

    def _restore_preview_state(self, state: dict) -> None:
        self.preview_data = deepcopy(state.get('preview_data', []))
        self._edited_rows = set(state.get('edited_rows', set()))
        self._refresh_preview_tree_only()
        self._update_summary()
        self._push_preview_to_main()
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self) -> None:
        try:
            if self.btn_undo and self.btn_undo.winfo_exists():
                self.btn_undo.config(state='normal' if self._undo_stack else 'disabled')
            if self.btn_redo and self.btn_redo.winfo_exists():
                self.btn_redo.config(state='normal' if self._redo_stack else 'disabled')
        except (RuntimeError, tk.TclError):
            logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa

    def _undo_preview_edit(self, event=None):
        self._finish_preview_editing(save=True)
        if not self._undo_stack:
            return "break"
        self._redo_stack.append(self._snapshot_preview_state())
        state = self._undo_stack.pop()
        self._restore_preview_state(state)
        self._log_safe("↶ 되돌리기 적용")
        return "break"

    def _redo_preview_edit(self, event=None):
        self._finish_preview_editing(save=True)
        if not self._redo_stack:
            return "break"
        self._undo_stack.append(self._snapshot_preview_state())
        state = self._redo_stack.pop()
        self._restore_preview_state(state)
        self._log_safe("↷ 다시실행 적용")
        return "break"

    def _preview_col_names(self) -> list:
        return [c[0] for c in PREVIEW_COLUMNS]

    def _editable_preview_columns(self) -> set:
        # No/Status는 시스템 관리 컬럼으로 편집 제외
        return set(self._preview_col_names()) - {'no', 'status'}

    def _capture_preview_anchor(self, event=None) -> None:
        if not getattr(self, 'tree', None):
            return
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return
        try:
            row_idx = self.tree.index(row_id)  # view index (필터/정렬 반영)
            col_idx = max(0, int(col_id.replace('#', '')) - 1)
            self._preview_anchor = (row_idx, col_idx)
        except (ValueError, TypeError, tk.TclError):
            logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa

    # v6.2.7: 제품 마스터 콤보박스 생성
    def _create_product_combobox(self, current_val, x, y, w, h):
        """product 열 더블클릭 시 제품 마스터 드롭다운 표시."""
        try:
            from .product_master_helper import get_product_choices
            choices = get_product_choices(self.engine.db)
        except Exception as e:
            logger.warning(f"[UI] get product choices from master failed: {e}")
            choices = ['LITHIUM CARBONATE', 'NICKEL SULFATE HEXAHYDRATE']
        
        combo = ttk.Combobox(self.tree, values=choices, font=('맑은 고딕', 10),
                             state='normal')
        
        # 현재 값과 매칭되는 항목 찾기
        current_upper = current_val.strip().upper()
        matched = False
        for i, ch in enumerate(choices):
            if current_upper in ch.upper():
                combo.current(i)
                matched = True
                break
        if not matched:
            combo.set(current_val)
        
        combo.place(x=x, y=y, width=max(w, 300), height=h)
        
        # 선택 시 product_code 자동 연동
        def _on_product_selected(event=None):
            selected = combo.get()
            try:
                from .product_master_helper import parse_product_choice
                code, full_name = parse_product_choice(selected)
                combo.set(full_name)  # 풀네임만 셀에 저장
                
                # product_code 자동 업데이트
                if code and self._editing_item:
                    row_id = self._editing_item[0]
                    try:
                        row_idx = self._item_to_source_index(row_id)
                        if 0 <= row_idx < len(self.preview_data):
                            self.preview_data[row_idx]['product_code'] = code
                    except (ValueError, TypeError):
                        logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
            except Exception as e:
                logger.warning(f"[UI] product combobox selection handling failed: {e}")
        
        combo.bind('<<ComboboxSelected>>', _on_product_selected)
        return combo

    def _on_preview_cell_edit(self, event=None) -> None:
        """셀 더블클릭 인라인 편집."""
        if not getattr(self, 'tree', None):
            return
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col_id = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not col_id or not row_id:
            return
        cols = self._preview_col_names()
        try:
            col_idx = int(col_id.replace('#', '')) - 1
        except ValueError:
            return
        if col_idx < 0 or col_idx >= len(cols):
            return
        col_name = cols[col_idx]
        if col_name not in self._editable_preview_columns():
            return
        self._capture_preview_anchor(event)
        self._finish_preview_editing(save=True)
        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current_val = str(self.tree.set(row_id, col_name))
        
        # v6.2.7: product 열은 제품 마스터 콤보박스
        if col_name == 'product':
            entry = self._create_product_combobox(current_val, x, y, w, h)
        else:
            entry = tk.Entry(self.tree, font=('맑은 고딕', 10))
            entry.insert(0, current_val.replace(',', ''))
            entry.select_range(0, 'end')
            entry.place(x=x, y=y, width=w, height=h)
        
        entry.focus_set()
        self._editing_item = (row_id, col_name, entry)
        entry.bind('<Return>', lambda e: self._finish_preview_editing(save=True))
        entry.bind('<Escape>', lambda e: self._finish_preview_editing(save=False))
        entry.bind('<FocusOut>', lambda e: self._finish_preview_editing(save=True))

    def _coerce_preview_value(self, col_name: str, value: str) -> str:
        v = (value or '').strip()
        if col_name in {'mxbg_pallet', 'free_time'}:
            if not v:
                return ''
            try:
                return str(max(0, int(float(v.replace(',', '')))))
            except ValueError:
                return ''
        if col_name in {'net_weight', 'gross_weight'}:
            if not v:
                return ''
            try:
                return f"{float(v.replace(',', '')):,.1f}"
            except ValueError:
                return ''
        if col_name in {'ship_date', 'arrival_date', 'con_return'}:
            if not v:
                return ''
            s = v[:10]
            if len(s) == 10 and s.count('-') == 2 and s.replace('-', '').isdigit():
                return s
            return ''
        return v

    def _update_preview_cell(self, row_idx: int, col_name: str, new_value: str) -> None:
        if row_idx < 0 or row_idx >= len(self.preview_data):
            return
        if col_name not in self._editable_preview_columns():
            return
        coerced = self._coerce_preview_value(col_name, new_value)
        self.preview_data[row_idx][col_name] = coerced
        self._edited_rows.add(row_idx)

    def _finish_preview_editing(self, save: bool = True) -> None:
        if not self._editing_item:
            return
        row_id, col_name, entry = self._editing_item
        raw_val = entry.get().strip()
        entry.destroy()
        self._editing_item = None
        if not save:
            return
        try:
            row_idx = self._item_to_source_index(row_id)
            if row_idx < 0 or row_idx >= len(self.preview_data):
                return
            old_val = str(self.preview_data[row_idx].get(col_name, ''))
            new_val = self._coerce_preview_value(col_name, raw_val)
            if old_val == new_val:
                return
            self._push_undo_snapshot()
            self._update_preview_cell(row_idx, col_name, raw_val)
            # v6.2.7: product 변경 시 product_code 자동 연동
            if col_name == 'product' and row_idx < len(self.preview_data):
                try:
                    from .product_master_helper import auto_detect_product_code
                    detected_code = auto_detect_product_code(self.engine.db, new_val)
                    if detected_code:
                        self.preview_data[row_idx]['product_code'] = detected_code
                except Exception as e:
                    logger.warning(f"[UI] auto detect product code failed: {e}")
            self._refresh_preview_tree_only()
            self._update_summary()
            self._push_preview_to_main()
        except (ValueError, TypeError, tk.TclError):
            logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa

    def _copy_preview_selection(self, event=None):
        """선택 행 TSV 복사 (엑셀 붙여넣기 호환)."""
        if not getattr(self, 'tree', None):
            return "break"
        items = self.tree.selection()
        if not items:
            focused = self.tree.focus()
            if focused:
                items = (focused,)
        if not items:
            return "break"
        headers = [c[1] for c in PREVIEW_COLUMNS]
        lines = ['\t'.join(headers)]
        for item_id in items:
            vals = self.tree.item(item_id, 'values')
            lines.append('\t'.join(str(v) for v in vals))
        self.tree.clipboard_clear()
        self.tree.clipboard_append('\n'.join(lines))
        return "break"

    def _selected_preview_cells(self):
        """선택 행 + 마지막 클릭 열 기준의 셀 좌표 목록."""
        if not getattr(self, 'tree', None):
            return []
        cols = self._preview_col_names()
        sel_items = list(self.tree.selection())
        if not sel_items:
            focus = self.tree.focus()
            if focus:
                sel_items = [focus]
        if not sel_items:
            return []
        _row_anchor, col_idx = self._preview_anchor
        col_idx = max(0, min(col_idx, len(cols) - 1))
        col_name = cols[col_idx]
        if col_name not in self._editable_preview_columns():
            return []
        out = []
        for item_id in sel_items:
            try:
                row_idx = self._item_to_source_index(item_id)
                if 0 <= row_idx < len(self.preview_data):
                    out.append((row_idx, col_name))
            except (ValueError, TypeError, tk.TclError):
                continue
        return out

    def _clear_preview_selection(self, event=None):
        """Delete: 선택 셀 비우기."""
        cells = self._selected_preview_cells()
        if not cells:
            return "break"
        self._push_undo_snapshot()
        for row_idx, col_name in cells:
            self._update_preview_cell(row_idx, col_name, '')
        self._refresh_preview_tree_only()
        self._update_summary()
        self._push_preview_to_main()
        return "break"

    def _cut_preview_selection(self, event=None):
        """Ctrl+X: 선택 셀 복사 후 비우기."""
        cells = self._selected_preview_cells()
        if not cells:
            return "break"
        values = []
        for row_idx, col_name in cells:
            values.append(str(self.preview_data[row_idx].get(col_name, '') or ''))
        try:
            self.tree.clipboard_clear()
            self.tree.clipboard_append('\n'.join(values))
        except tk.TclError:
            logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
        self._push_undo_snapshot()
        for row_idx, col_name in cells:
            self._update_preview_cell(row_idx, col_name, '')
        self._refresh_preview_tree_only()
        self._update_summary()
        self._push_preview_to_main()
        return "break"

    def _paste_preview_from_clipboard(self, event=None):
        """선택 셀을 시작점으로 TSV 블록 붙여넣기."""
        if not getattr(self, 'tree', None):
            return "break"
        try:
            raw = self.tree.clipboard_get()
        except tk.TclError:
            return "break"
        lines = [ln for ln in raw.replace('\r', '').split('\n') if ln.strip()]
        if not lines:
            return "break"
        start_row, start_col = self._preview_anchor  # start_row는 view index
        cols = self._preview_col_names()
        # 헤더 포함 복사분이면 첫 줄 스킵
        first_parts = [p.strip() for p in lines[0].split('\t')]
        if first_parts and len(first_parts) == len(cols):
            header_names = [c[1] for c in PREVIEW_COLUMNS]
            if all(fp in header_names for fp in first_parts[: min(3, len(first_parts))]):
                lines = lines[1:]
        if lines:
            self._push_undo_snapshot()
        view_items = list(self.tree.get_children())
        for r_off, line in enumerate(lines):
            view_idx = start_row + r_off
            if view_idx >= len(view_items):
                break
            row_idx = self._item_to_source_index(view_items[view_idx])
            if row_idx < 0 or row_idx >= len(self.preview_data):
                continue
            parts = [p.strip() for p in line.split('\t')]
            for c_off, val in enumerate(parts):
                col_idx = start_col + c_off
                if col_idx >= len(cols):
                    break
                col_name = cols[col_idx]
                self._update_preview_cell(row_idx, col_name, val)
        self._refresh_preview_tree_only()
        self._update_summary()
        self._push_preview_to_main()
        return "break"
    
    def _refresh_preview_tree_only(self) -> None:
        """미리보기 테이블만 현재 preview_data로 갱신 (요약/버튼/팝업 없음). 파싱 중 실시간 표시용."""
        if getattr(self, 'compact_mode', False):
            return
        if not getattr(self, 'tree', None) or not self.tree.winfo_exists():
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not self.preview_data:
            return
        xc = getattr(self, '_cross_check_result', None)
        xc_lot_levels = {}
        xc_global_level = None
        xc_active = bool(xc) and not bool(getattr(xc, 'is_clean', True))
        if xc_active:
            # 크로스체크가 있을 때만 LOT 레벨을 리프레시 1회당 1번 계산해 재사용한다.
            if hasattr(xc, 'get_lot_levels'):
                try:
                    xc_lot_levels = xc.get_lot_levels() or {}
                except Exception as _e:
                    logger.debug(f"onestop_inbound: {_e}")
                    xc_lot_levels = {}
            xc_global_level = getattr(xc, 'global_level', None)

        self._view_indices = self._build_view_indices()
        for pos, src_idx in enumerate(self._view_indices):
            row = self.preview_data[src_idx]
            row['no'] = str(src_idx + 1)
            values = self._row_display_values(row)
            base_tag = 'even' if pos % 2 == 0 else 'odd'
            if src_idx in self._edited_rows:
                tag = 'edited'
            elif xc_active:
                lot_no = (row.get('lot_no') or '').strip()
                lot_level = xc_lot_levels.get(lot_no) if lot_no else None
                effective = None
                if lot_level is not None and xc_global_level is not None:
                    try:
                        effective = max(lot_level, xc_global_level)
                    except Exception as _e:
                        logger.debug(f"onestop_inbound: {_e}")
                        effective = lot_level
                elif lot_level is not None:
                    effective = lot_level
                elif xc_global_level is not None:
                    effective = xc_global_level

                try:
                    level_num = int(effective) if effective is not None else 0
                except (TypeError, ValueError) as _e:
                    logger.debug(f"onestop_inbound: {_e}")
                    level_num = 0

                if level_num >= 3:
                    tag = 'xc_critical'
                elif level_num == 2:
                    tag = 'xc_warning'
                elif level_num == 1:
                    tag = 'xc_info'
                elif hasattr(xc, 'get_row_tag') and lot_no:
                    # 구버전 객체 호환: 계산 실패 시 기존 API로 최종 시도
                    try:
                        tag = xc.get_row_tag(lot_no) or base_tag
                    except Exception as _e:
                        logger.debug(f"onestop_inbound: {_e}")
                        tag = base_tag
                else:
                    tag = base_tag
            else:
                tag = base_tag
            self.tree.insert('', END, iid=str(src_idx), values=values, tags=(tag,))

    def _display_preview(self) -> None:
        """미리보기 테이블 표시 — 한 번에가 아니라 순차적으로 행 추가 (보기 편하게). compact_mode에서는 메인 창만 갱신."""
        def _update():
            self._push_preview_to_main()
            self._update_summary()
            if self.preview_data and self._has_required_docs():
                self.btn_upload.config(state='normal')
            else:
                self.btn_upload.config(state='disabled')
            if self.preview_data:
                self.btn_excel.config(state='normal')
            if getattr(self, 'compact_mode', False):
                return
            if not getattr(self, 'tree', None) or not self.tree.winfo_exists():
                return
            self._refresh_preview_tree_only()
            self._update_filter_values_from_preview()

        if self.dialog and self.dialog.winfo_exists():
            self.dialog.after(0, _update)
    
    def _has_required_docs(self) -> bool:
        """필수 서류 3종(Packing List, Invoice, B/L)이 모두 선택·파싱되었는지 확인"""
        for doc_type, _name, required in DOC_TYPES:
            if required and doc_type not in self.file_paths:
                return False
        return True
    
    def _update_summary(self) -> None:
        """합계행"""
        if not self.preview_data:
            self.summary_var.set("")
            return
        
        containers = set(r['container_no'] for r in self.preview_data if r['container_no'])
        total_tb = 0
        total_net = 0.0
        total_gross = 0.0
        
        for r in self.preview_data:
            try:
                total_tb += int(r.get('mxbg_pallet', '10')) if r.get('mxbg_pallet', '') else 0
            except (ValueError, TypeError) as _e:
                logger.debug(f"onestop_inbound: {_e}")
            try:
                total_net += safe_float(r['net_weight']) if r['net_weight'] else 0
            except (ValueError, TypeError) as _e:
                logger.debug(f"onestop_inbound: {_e}")
            try:
                total_gross += safe_float(r['gross_weight']) if r['gross_weight'] else 0
            except (ValueError, TypeError) as _e:
                logger.debug(f"onestop_inbound: {_e}")
        
        self.summary_var.set(
            f"합계: {len(self.preview_data)} LOT | "
            f"{len(containers)} 컨테이너 | "
            f"{total_tb} 톤백 | "
            f"Net {total_net:,.0f} kg | "
            f"Gross {total_gross:,.0f} kg"
        )
    

    def _show_success_and_close(self, count: int):
        # v8.3.3 [UX]: DB 저장 완료 → 단계4 활성화
        try:
            self._activate_step(3)
        except Exception as e:
            logger.warning(f'[UI] onestop_inbound: {e}')
        def _close():
            if self.dialog and self.dialog.winfo_exists():
                _app = self.app if self.app else None
                _ask_more_inbound = False
                # v5.8.9: 파싱 결과 팝업에서 DB 업로드 선택 시, 완료 후 엑셀 내보내기 여부 질의
                if getattr(self, '_ask_excel_after_upload', False):
                    self._ask_excel_after_upload = False
                    try:
                        from ..utils.custom_messagebox import CustomMessageBox
                        if CustomMessageBox.askyesno(self.dialog, "엑셀 내보내기",
                            "DB 업로드가 완료되었습니다.\n엑셀 내보내기도 하시겠습니까?\n(아니오를 누르면 여기서 종료합니다.)"):
                            self._export_to_excel()
                    except (ImportError, ModuleNotFoundError):
                        logger.debug("[SUPPRESSED] exception in onestop_inbound.py")  # noqa
                _msg = self._build_upload_summary_message(count)
                try:
                    from ..utils.custom_messagebox import CustomMessageBox
                    # 1) 업데이트 요약 확인
                    CustomMessageBox.showinfo(self.dialog, "업데이트 완료 요약", _msg)
                except (ImportError, ModuleNotFoundError):
                    CustomMessageBox.info(None, "완료", _msg)

                # 2) 사용자 확인 후 화면 데이터 정리 (업로드1/업로드2)
                self._reset_after_upload_success()

                # 3) 추가 입고 여부 확인
                try:
                    from ..utils.custom_messagebox import CustomMessageBox
                    _ask_more_inbound = CustomMessageBox.askyesno(
                        self.dialog,
                        "추가 입고 선택 (예=추가 입고 / 아니오=종료)",
                        "추가로 입고 작업을 하시겠습니까?\n\n"
                        "예: 추가 입고 화면을 다시 엽니다.\n"
                        "아니오: 이번 입고 프로세스를 종료합니다."
                    )
                except (ImportError, ModuleNotFoundError):
                    from tkinter import messagebox as msgbox
                    _ask_more_inbound = msgbox.askyesno(
                        "추가 입고 선택 (예=추가 입고 / 아니오=종료)",
                        "추가로 입고 작업을 하시겠습니까?\n\n"
                        "예: 추가 입고 화면을 다시 엽니다.\n"
                        "아니오: 이번 입고 프로세스를 종료합니다."
                    )

                self.dialog.destroy()
                
                # v3.8.9: 업로드 후 재고리스트 탭 이동 + 자동 새로고침
                # dialog.destroy() 후이므로 app.root.after 사용
                if _app:
                    try:
                        _root = getattr(_app, 'root', None)
                        if _root:
                            if hasattr(_app, 'notebook') and hasattr(_app, 'tab_inventory'):
                                _root.after(200, lambda: _app.notebook.select(_app.tab_inventory))
                            _app._safe_refresh()
                            logger.info("[onestop] 전체 탭 새로고침 완료")
                            if _ask_more_inbound and hasattr(_app, '_on_onestop_inbound'):
                                if hasattr(_app, '_reset_inventory_view_for_new_inbound'):
                                    _root.after(300, _app._reset_inventory_view_for_new_inbound)
                                _root.after(700, _app._on_onestop_inbound)
                                logger.info("[onestop] 추가 입고 요청으로 원스톱 입고 재오픈")
                            elif not _ask_more_inbound:
                                logger.info("[onestop] 추가 입고 없음 — 입고 프로세스 종료")
                    except (RuntimeError, ValueError) as e:
                        logger.debug(f"재고 새로고침 호출 실패: {e}")
        
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.after(100, _close)

    def _build_upload_summary_message(self, count: int) -> str:
        """업로드 완료 요약 문자열 생성."""
        rows = list(getattr(self, 'preview_data', []) or [])
        edited_cnt = len(getattr(self, '_edited_rows', set()) or set())
        sap_set = {str(r.get('sap_no', '') or '').strip() for r in rows if str(r.get('sap_no', '') or '').strip()}
        bl_set = {str(r.get('bl_no', '') or '').strip() for r in rows if str(r.get('bl_no', '') or '').strip()}
        cont_set = {str(r.get('container_no', '') or '').strip() for r in rows if str(r.get('container_no', '') or '').strip()}
        total_net = 0.0
        for r in rows:
            try:
                total_net += safe_float(r.get('net_weight', 0) or 0)
            except (ValueError, TypeError) as _e:
                logger.debug(f"onestop_inbound: {_e}")
        return (
            f"✅ {count}개 LOT 저장 완료\n\n"
            f"- 수정된 행: {edited_cnt}건\n"
            f"- SAP NO: {len(sap_set)}종\n"
            f"- BL NO: {len(bl_set)}종\n"
            f"- 컨테이너: {len(cont_set)}개\n"
            f"- 총 NET: {total_net:,.0f} kg"
        )

    def _reset_after_upload_success(self) -> None:
        """업로드 성공 후 로컬/메인 미리보기 데이터 정리."""
        try:
            self.preview_data = []
            self.parsed_results = {}
            self._original_preview_data = []
            self._cross_check_result = None
            self._edited_rows = set()
            self._undo_stack = []
            self._redo_stack = []
            self._view_indices = []
            if hasattr(self, '_update_summary'):
                self._update_summary()
            if hasattr(self, '_update_undo_redo_buttons'):
                self._update_undo_redo_buttons()
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.debug(f"업로드 후 로컬 미리보기 정리 실패: {e}")
        self._clear_preview_from_main()
    
    def _enable_buttons(self) -> None:
        def _u():
            try:
                if self.btn_upload and self.btn_upload.winfo_exists():
                    self.btn_upload.config(state='normal')
                if self.btn_excel and self.btn_excel.winfo_exists():
                    self.btn_excel.config(state='normal')
            except (RuntimeError, ValueError) as _e:
                logger.debug(f'Suppressed: {_e}')
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.after(0, _u)
    
    # ─────────────────────────────────────────────────────────────
    # v6.4.0: 선사 뱃지 UI 업데이트
    # ─────────────────────────────────────────────────────────────


    def _reparse_after_carrier_change(self) -> None:
        """v7.4.0: 수동 선사 변경 후 PL/INV 재파싱."""
        cid = getattr(self, '_carrier_manual_var', None)
        cid = cid.get().strip() if cid else 'UNKNOWN'
        if cid == 'UNKNOWN':
            try:
                from ..utils.custom_messagebox import CustomMessageBox
                CustomMessageBox.showwarning(
                    self.dialog, "선사 미선택",
                    "🚢 선사 드롭다운에서 선사를 고르거나, 뱃지를 눌러 템플릿을 선택하세요.\n"
                    "(템플릿에 선사·톤백 단가가 포함됩니다.)"
                )
            except Exception as e:
                logger.warning(f"[UI] show carrier not selected warning failed: {e}")
            return
        if 'PACKING_LIST' not in self.file_paths:
            try:
                from ..utils.custom_messagebox import CustomMessageBox
                CustomMessageBox.showwarning(
                    self.dialog, "재파싱 불가", "Packing List 파일이 없습니다."
                )
            except Exception as e:
                logger.warning(f"[UI] show no packing list warning failed: {e}")
            return
        try:
            from features.ai.bl_carrier_registry import CARRIER_TEMPLATES
            _ctpl = CARRIER_TEMPLATES.get(cid)
            cname = _ctpl.carrier_name if _ctpl else cid
            # 힌트 강제 교체
            _tpl = getattr(self, '_inbound_template_data', {}) or {}
            # v8.7.0 [FIX]: 수동 선사 변경 시 carrier_id도 같이 덮어써서 BL/DO 파싱에 강제 반영
            _tpl['carrier_id'] = cid
            if _ctpl:
                if not _tpl.get('gemini_hint_packing'):
                    _tpl['gemini_hint_packing'] = (
                        f"이 서류는 {cname} 선사의 Packing List입니다. "
                        f"BL번호 형식: {getattr(_ctpl, 'bl_format_hint', '')}"
                    )
                if not _tpl.get('gemini_hint_invoice'):
                    _tpl['gemini_hint_invoice'] = (
                        f"이 서류는 {cname} 선사의 Invoice/FA입니다."
                    )
                # v8.7.0 [FIX]: BL 힌트도 비어있으면 채워서 multi-template 감지를 사용자 선택으로 유도
                if not _tpl.get('gemini_hint_bl'):
                    _tpl['gemini_hint_bl'] = (
                        f"이 서류는 {cname} 선사의 Bill of Lading입니다. "
                        f"BL번호 형식: {getattr(_ctpl, 'bl_format_hint', '')}"
                    )
                self._inbound_template_data = _tpl
        except Exception as e:
            logger.debug(f"선사 힌트 강제 교체 실패: {e}")
        self._log_safe(f"🚢 선사 재파싱 시작: {cid} → BL/PL/INV/DO 힌트 적용")
        # v8.0.6: 선사 재파싱은 확인창 없이 바로 파싱 진행
        self._do_start_parsing_after_template()

    def _on_add_do_later(self) -> None:
        """v7.4.0: D/O 나중에 추가 — do_update_dialog로 연결."""
        try:
            from ..dialogs.do_update_dialog import DoUpdateDialog
            current_theme = getattr(self.parent, 'current_theme', 'darkly')
            DoUpdateDialog(self.dialog, self.engine, current_theme=current_theme)
            self._log_safe("📋 D/O 후속 연결 다이얼로그 열림")
        except Exception as e:
            logger.error(f"D/O 나중에 추가 오류: {e}")
            try:
                from ..utils.custom_messagebox import CustomMessageBox
                CustomMessageBox.showerror(
                    self.dialog, "오류",
                    f"D/O 다이얼로그를 열 수 없습니다.\n{e}\n\n"
                    f"메뉴 → 입고 → [D/O 후속 연결] 을 사용하세요."
                )
            except Exception as e:
                logger.warning(f"[UI] show D/O dialog error message failed: {e}")

    def _update_carrier_badge(self, badge_text: str, style_carrier_id: str = '') -> None:
        """
        BL 파싱 후 선사 뱃지를 입고 다이얼로그 BL 버튼 아래 라벨에 표시.
        badge_text 예시: "[선사: Mediterranean Shipping Company]"
        선사별 전경색(fg) + 배경색(bg) 적용.
        """
        try:
            if not hasattr(self, '_carrier_label') or self._carrier_label is None:
                return  # 위젯 미생성 시 무시 (로그에는 이미 출력됨)
            # 선사별 (전경색, 배경색) 매핑
            _style_map = {
                "MSC":     ("#FFFFFF", "#0066CC"),  # 흰 글씨 / MSC 블루
                "MAERSK":  ("#FFFFFF", "#009B77"),  # 흰 글씨 / Maersk 그린
                "HMM":     ("#FFFFFF", "#E63946"),  # 흰 글씨 / HMM 레드
                "CMA_CGM": ("#FFFFFF", "#E07B39"),  # 흰 글씨 / CMA 오렌지
                "ONE":     ("#FFFFFF", "#E91B8B"),  # 흰 글씨 / ONE 핑크
            }
            _carrier_id = (style_carrier_id or "").strip()
            bl_r = self.parsed_results.get('bl')
            if not _carrier_id and bl_r:
                _carrier_id = getattr(bl_r, 'carrier_id', '') or ''
            _fg, _bg = _style_map.get(_carrier_id, ("#333333", "#DDDDDD"))  # 기본 회색
            self._carrier_label.config(
                text=f"  {badge_text}  ",
                fg=_fg, bg=_bg, cursor='hand2',
            )
        except Exception as _e:
            logger.debug(f"[CarrierBadge] UI 업데이트 실패(무시): {_e}")

    def _enable_parse_btn(self):
        def _u():
            if self.dialog and self.dialog.winfo_exists():
                self._update_parse_hint()
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.after(0, _u)
    
    def _on_cancel(self):
        self._clear_preview_from_main()
        if self.dialog:
            self.dialog.destroy()
    
    def _log_safe(self, msg: str):
        try:
            if self._log:
                if self.dialog and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: self._log(msg))
                else:
                    self._log(msg)
        except (RuntimeError, ValueError):
            logger.info(msg)
