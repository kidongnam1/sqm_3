# -*- coding: utf-8 -*-
"""
v7.9.9 [PARSE-CONFIRM]: 파싱 첫 데이터 확인 다이얼로그
======================================================
- 파싱된 첫 번째 LOT 데이터를 헤더+값 테이블로 표시
- 행별 체크박스로 포함/제외 선택
- 확인 후 전체 파싱 DB 저장 진행
"""
from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import tkinter as tk
from tkinter import ttk
import logging
import json
import time
try:
    from gui_app_modular.utils.ui_constants import ThemeColors, apply_treeview_theme, tc
    _HAS_THEME = True
except Exception:
    _HAS_THEME = False

logger = logging.getLogger(__name__)


def _dbg_log(tag: str = "", location: str = "", message: str = "", data=None) -> None:
    # v8.6.4: 프로덕션 debug 파일 쓰기 제거 → logger.debug
    # v8.7.0 [FIX]: 호출부가 (tag, location, message, data) 4-arg을 쓰고 있어 시그니처 정합
    logger.debug(f'[DBG:{tag}] {location} — {message} | {data}')


class ParsePreviewConfirmDialog:
    """
    파싱 첫 데이터 확인 다이얼로그.

    사용법:
        dlg = ParsePreviewConfirmDialog(parent, preview_data, elapsed_str)
        result = dlg.show()   # True=진행, False=취소
        checked = dlg.get_checked_indices()  # 선택된 행 인덱스 목록
    """

    def __init__(self, parent, preview_data: list, elapsed_str: str = ""):
        self.parent       = parent
        self.preview_data = preview_data  # [{'lot_no':..., 'product':..., ...}, ...]
        self.elapsed_str  = elapsed_str
        self._result      = False
        self._check_vars  = []
        self.dialog       = None

    def show(self) -> bool:
        """다이얼로그 표시 후 결과 반환 (True=전체 저장, False=취소)."""
        self._build_dialog()
        self.dialog.wait_window()
        return self._result

    def get_checked_indices(self) -> list:
        """체크된 행의 인덱스 목록 반환."""
        return [i for i, v in enumerate(self._check_vars) if v.get()]

    def _build_dialog(self):
        # region agent log
        _dbg_log(
            "H1",
            "parse_preview_confirm_dialog.py:_build_dialog:start",
            "build dialog start",
            {"preview_len": len(self.preview_data or []), "elapsed": self.elapsed_str},
        )
        # endregion
        self.dialog = create_themed_toplevel(self.parent)
        self.dialog.title("📋 파싱 결과 확인 — DB 저장 전 검토")
        try:
            from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence as _sgp
            _sgp(self.dialog, "parse_preview_confirm_dialog", None, "large")
        except Exception as e:
            logger.warning(f'[UI] parse_preview_confirm_dialog: {e}')
        self.dialog.geometry("1000x620")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # ── 상단 헤더 ──
        hdr = ttk.Frame(self.dialog, padding=(12, 8))
        hdr.pack(fill='x')
        ttk.Label(
            hdr,
            text=f"✅ 파싱 완료 — {len(self.preview_data)}개 LOT  |  소요 시간: {self.elapsed_str}",
            font=('맑은 고딕', 12, 'bold')
        ).pack(side='left')
        ttk.Label(
            hdr,
            text="체크된 항목만 DB에 저장됩니다",
            font=('맑은 고딕', 10),
            foreground=tc('text_muted')
        ).pack(side='right', padx=8)

        ttk.Separator(self.dialog, orient='horizontal').pack(fill='x')

        # ── 전체 선택/해제 버튼 ──
        ctrl = ttk.Frame(self.dialog, padding=(12, 4))
        ctrl.pack(fill='x')
        ttk.Button(ctrl, text="☑ 전체 선택",  width=12,
                   command=self._select_all).pack(side='left', padx=4)
        ttk.Button(ctrl, text="☐ 전체 해제",  width=12,
                   command=self._deselect_all).pack(side='left', padx=4)
        ttk.Label(ctrl, text=f"총 {len(self.preview_data)}개 LOT",
                  font=('맑은 고딕', 10)).pack(side='left', padx=12)

        # ── 테이블 ──
        tbl_frame = ttk.LabelFrame(
            self.dialog, text="📊 파싱 데이터 (첫 번째 LOT 기준 컬럼 확인)",
            padding=6
        )
        tbl_frame.pack(fill='both', expand=True, padx=12, pady=4)

        # 컬럼 정의
        display_cols = [
            ('check',        '✔',          40,  'center'),
            ('no',           'No.',         40,  'center'),
            ('lot_no',       'LOT NO',     120,  'center'),
            ('sap_no',       'SAP NO',      90,  'center'),
            ('product',      'PRODUCT',    110,  'w'),
            ('bl_no',        'B/L NO',     100,  'center'),
            ('container_no', 'CONTAINER',  100,  'center'),
            ('net_weight',   'NET(kg)',     80,  'e'),
            ('tonbag_count', '톤백수',      60,  'center'),
            ('ship_date',    '선적일',       90,  'center'),
            ('arrival_date', '입항일',       90,  'center'),
            ('warehouse',    '창고',         70,  'center'),
        ]

        col_ids = [c[0] for c in display_cols if c[0] != 'check']
        self.tree = ttk.Treeview(
            tbl_frame, columns=col_ids,
            show='headings', height=14, selectmode='none'
        )
        for cid, txt, w, anchor in display_cols:
            if cid == 'check':
                continue
            self.tree.heading(cid, text=txt, anchor='center')
            self.tree.column(cid, width=w, anchor=anchor, stretch=(cid == 'product'))

        vsb = ttk.Scrollbar(tbl_frame, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(tbl_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        # v8.1.8: 합계 footer
        from ..utils.tree_enhancements import TreeviewTotalFooter
        self._parse_footer = TreeviewTotalFooter(
            self.dialog, self.tree,
            summable_column_ids=['net_weight'],
            column_display_names={'net_weight': 'NET(kg)'},
        )
        self._parse_footer.pack(fill='x', padx=8)
        vsb.pack(side='right',  fill='y')
        # v8.1.9: TreeviewTotalFooter
        try:
            from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter as _TTF
            _footer = _TTF(
                tbl_frame, self.tree,
                summable_column_ids=['net_weight'],
                column_display_names={'net_weight': 'NET(kg)'},
                column_formats={'net_weight': ',.0f'},
            )
            _footer.pack(fill='x')
            self._footer_tree = _footer
        except Exception as e:
            logger.warning(f'[UI] parse_preview_confirm_dialog: {e}')
        hsb.pack(side='bottom', fill='x')

        # 체크박스 오버레이 프레임 (Treeview 위에 체크박스 배치는 어려우므로
        # 별도 canvas로 처리 대신 행 태그로 시각화 + 클릭으로 토글)
        self._check_vars  = []
        self._iid_list    = []

        for idx, row in enumerate(self.preview_data):
            var = tk.BooleanVar(value=True)
            self._check_vars.append(var)

            lot_no  = str(row.get('lot_no', '') or '')
            # region agent log
            if idx < 3:
                _dbg_log(
                    "H1",
                    "parse_preview_confirm_dialog.py:_build_dialog:row_before_values",
                    "row value before float cast",
                    {
                        "idx": idx,
                        "lot_no": lot_no,
                        "net_weight_raw": row.get("net_weight", None),
                        "net_weight_type": str(type(row.get("net_weight", None))),
                    },
                )
            # endregion
            values  = (
                idx + 1,
                lot_no,
                str(row.get('sap_no', '') or ''),
                str(row.get('product', '') or ''),
                str(row.get('bl_no', '') or ''),
                str(row.get('container_no', '') or ''),
                f"{float(row.get('net_weight', 0) or 0):,.0f}",
                str(row.get('tonbag_count', '') or ''),
                str(row.get('ship_date', '') or '')[:10],
                str(row.get('arrival_date', '') or '')[:10],
                str(row.get('warehouse', '') or ''),
            )
            iid = self.tree.insert('', 'end', values=values, tags=('checked',))
            self._iid_list.append(iid)

        # region agent log
        _dbg_log(
            "H3",
            "parse_preview_confirm_dialog.py:_build_dialog:after_insert",
            "tree rows inserted",
            {
                "tree_children_count": len(self.tree.get_children()),
                "iid_count": len(self._iid_list),
                "first_item": self.tree.item(self._iid_list[0]) if self._iid_list else {},
            },
        )
        # endregion

        # v9.0: Treeview 배경/전경색 명시적 적용 (다크 테마 대응)
        _is_dark = False
        try:
            parent_theme = getattr(self.parent, 'current_theme', '') or ''
            if not parent_theme:
                parent_theme = getattr(getattr(self.parent, 'master', None), 'current_theme', '') or ''
            if _HAS_THEME:
                _is_dark = ThemeColors.is_dark_theme(parent_theme)
        except Exception:
            logger.debug("[SUPPRESSED] exception in parse_preview_confirm_dialog.py")  # noqa

        if _is_dark:
            _row_bg    = tc('bg_card')   # 딥 네이비 행 배경 (0d1b2a보다 밝게)
            _row_fg    = tc('warning')   # 주황 텍스트
            _unsel_bg  = tc('bg_secondary')   # 미체크 행
            _unsel_fg  = tc('text_muted')
        else:
            _row_bg    = tc('bg_card')   # 화이트 배경
            _row_fg    = tc('text_primary')   # 진한 텍스트
            _unsel_bg  = tc('bg_secondary')
            _unsel_fg  = tc('text_muted')

        self.tree.tag_configure('checked',   background=_row_bg,   foreground=_row_fg)
        self.tree.tag_configure('unchecked', background=_unsel_bg, foreground=_unsel_fg)
        # region agent log
        _dbg_log(
            "H3",
            "parse_preview_confirm_dialog.py:_build_dialog:style_colors",
            "tree style colors",
            {
                "is_dark": _is_dark,
                "row_bg": _row_bg,
                "row_fg": _row_fg,
                "unsel_bg": _unsel_bg,
                "unsel_fg": _unsel_fg,
            },
        )
        # endregion

        # Treeview 전체 행 기본 색상도 강제 적용
        try:
            style = ttk.Style()
            style.configure('ParsePreview.Treeview',
                background=_row_bg,
                foreground=_row_fg,
                fieldbackground=_row_bg,
                rowheight=32)
            style.map('ParsePreview.Treeview',
                background=[('selected', '#0066CC' if _is_dark else '#d6eaf8')],
                foreground=[('selected', '#FF8C00' if _is_dark else '#1a5276')])
            self.tree.configure(style='ParsePreview.Treeview')
        except Exception as _se:
            logger.debug(f"[SUPPRESSED] {type(_se).__name__}: {_se}")  # noqa

        # 클릭으로 체크/해제 토글
        self.tree.bind('<Button-1>', self._on_tree_click)

        # ── 하단 버튼 ──
        btn_frame = ttk.Frame(self.dialog, padding=(12, 8))
        btn_frame.pack(fill='x', side='bottom')

        ttk.Button(
            btn_frame,
            text="✅ 선택 항목 DB 저장 진행",
            width=22,
            command=self._on_confirm
        ).pack(side='right', padx=6)

        ttk.Button(
            btn_frame,
            text="❌ 취소",
            width=10,
            command=self._on_cancel
        ).pack(side='right', padx=4)

        self._update_header_count()

    def _on_tree_click(self, event):
        """행 클릭 시 체크 토글."""
        region = self.tree.identify_region(event.x, event.y)
        if region not in ('cell', 'tree'):
            return
        iid = self.tree.identify_row(event.y)
        if not iid or iid not in self._iid_list:
            return
        idx = self._iid_list.index(iid)
        var = self._check_vars[idx]
        var.set(not var.get())
        tag = 'checked' if var.get() else 'unchecked'
        self.tree.item(iid, tags=(tag,))
        self._update_header_count()

    def _select_all(self):
        for i, var in enumerate(self._check_vars):
            var.set(True)
            self.tree.item(self._iid_list[i], tags=('checked',))
        self._update_header_count()

    def _deselect_all(self):
        for i, var in enumerate(self._check_vars):
            var.set(False)
            self.tree.item(self._iid_list[i], tags=('unchecked',))
        self._update_header_count()

    def _update_header_count(self):
        checked = sum(1 for v in self._check_vars if v.get())
        total   = len(self._check_vars)
        try:
            self.dialog.title(
                f"📋 파싱 결과 확인 — {checked}/{total}개 선택됨 | 소요: {self.elapsed_str}"
            )
        except Exception:
            logger.debug("[SUPPRESSED] exception in parse_preview_confirm_dialog.py")  # noqa

    def _on_confirm(self):
        checked = sum(1 for v in self._check_vars if v.get())
        if checked == 0:
            tk.messagebox.showwarning(
                "선택 없음", "저장할 LOT를 1개 이상 선택해 주세요.",
                parent=self.dialog
            )
            return
        self._result = True
        self.dialog.destroy()

    def _on_cancel(self):
        self._result = False
        self.dialog.destroy()
