"""
SQM v5.5.3 — 컬럼 표시/숨김 위젯
================================
v5.5.3 patch_03: tk→ttk 전환으로 테마 자동 대응
v5.7.5: 표시 모드(컬럼/본문/날짜) 제거 — 행 높이 선택 UI 삭제
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import List, Tuple

from .ui_constants import FontScale, FontStyle, Spacing

logger = logging.getLogger(__name__)


class ColumnToggleBar:
    """
    컬럼 표시/숨김 체크박스 바

    v5.5.3 patch_03: ttk 위젯 사용 → 테마 자동 대응

    Usage:
        toggle_bar = ColumnToggleBar(parent, tree, columns)
        toggle_bar.pack(fill='x')
    """

    def __init__(self, parent, tree, toggle_columns: List[Tuple],
                 is_dark: bool = False):
        """
        Args:
            parent: 부모 위젯
            tree: Treeview 위젯
            toggle_columns: [(col_id, label)] 또는 [(col_id, label, default_visible), ...]
            is_dark: 하위 호환 (사용하지 않음)
        """
        self.tree = tree
        self.toggle_vars = {}
        self.toggle_columns = [(c[0], c[1]) for c in toggle_columns]

        # ttk.Frame — 테마 자동 대응 (Phase3: 8px 그리드)
        _fonts = FontScale()
        self.frame = ttk.Frame(parent, padding=(Spacing.XS, Spacing.XS))

        # 왼쪽: "표시 컬럼:" + 체크박스
        left_frame = ttk.Frame(self.frame)
        left_frame.pack(side='left', fill='x', expand=True)

        _lbl_col = ttk.Label(left_frame, text="표시 컬럼:",
                             font=_fonts.get_font(FontStyle.SMALL, 'bold'))
        _lbl_col.pack(side='left', padx=(0, Spacing.SM))
        self._apply_tooltip_safe(_lbl_col, "체크 해제 시 해당 컬럼이 목록에서 숨겨집니다. 체크하면 다시 표시됩니다.")

        for item in toggle_columns:
            col_id, label = item[0], item[1]
            default_visible = item[2] if len(item) >= 3 else True
            var = tk.BooleanVar(value=default_visible)
            chk = ttk.Checkbutton(
                left_frame,
                text=label,
                variable=var,
                command=lambda c=col_id, v=var: self._toggle_column(c, v)
            )
            chk.pack(side='left', padx=Spacing.XS)
            self.toggle_vars[col_id] = var
            self._apply_tooltip_safe(chk, f"'{label}' 컬럼 표시/숨김. 해제 시 목록에서 이 컬럼이 사라집니다.")

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def _apply_tooltip_safe(self, widget, text: str) -> None:
        try:
            from .ui_constants import apply_tooltip
            apply_tooltip(widget, text)
        except Exception as e:
            logger.debug(f"Suppressed: {e}")

    def _toggle_column(self, col_id: str, var: tk.BooleanVar) -> None:
        """
        컬럼 표시/숨김.
        v5.7.4: displaycolumns가 ('#all',) 튜플로 오는 경우 정규화·필터링하여
        Invalid column index #all 에러 방지 (재고 리스트·톤백 리스트 공통).
        """
        if not self.tree:
            logger.warning("Treeview가 연결되지 않음")
            return

        try:
            raw = self.tree['displaycolumns']
            all_cols = list(self.tree['columns'])

            # 빈값, 문자열 '#all', 튜플 ('#all',) 등 모두 실제 컬럼 목록으로 정규화
            if not raw or raw == '' or raw == '#all':
                current_display = list(all_cols)
            elif getattr(raw, '__iter__', None) and len(raw) == 1 and raw[0] == '#all':
                current_display = list(all_cols)
            else:
                current_display = list(raw)

            # Tk가 반환한 값에 '#all'이 섞여 있으면 제거 (Invalid column index #all 방지)
            current_display = [c for c in current_display if c != '#all']
            if not current_display:
                current_display = list(all_cols)

            if var.get():
                # 체크 → 표시
                if col_id not in current_display and col_id in all_cols:
                    idx = all_cols.index(col_id)
                    insert_pos = 0
                    for i, c in enumerate(current_display):
                        if c in all_cols and all_cols.index(c) < idx:
                            insert_pos = i + 1
                    current_display.insert(insert_pos, col_id)
            else:
                # 해제 → 숨김
                if col_id in current_display:
                    current_display.remove(col_id)

            # 빈 tuple은 사용하지 않음: 최소 한 컬럼은 유지
            if not current_display:
                current_display = list(all_cols)

            self.tree['displaycolumns'] = tuple(current_display)
            logger.debug(f"컬럼 토글: {col_id} → {'표시' if var.get() else '숨김'}")

        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"컬럼 토글 오류(무시): {e}")

    def get_visible_columns(self) -> List[str]:
        """현재 표시 중인 컬럼 목록"""
        return [col_id for col_id, var in self.toggle_vars.items() if var.get()]


__all__ = ['ColumnToggleBar']
