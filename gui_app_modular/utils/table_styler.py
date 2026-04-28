"""
SQM 재고관리 시스템 - 테이블 스타일 유틸리티
============================================

v4.2.2: 그리드 라인, 줄무늬, 가독성 개선

작성자: Ruby
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from gui_app_modular.utils.ui_constants import ThemeColors

logger = logging.getLogger(__name__)


class TableStyler:
    """테이블 스타일 관리 클래스"""

    # 색상 테마 (라이트)
    COLORS = {
        # 그리드 라인
        'grid_line': '#e0e0e0',
        'grid_line_strong': '#bdbdbd',

        # 줄무늬 (Striped rows)
        'row_even': '#ffffff',
        'row_odd': '#f5f5f5',
        'row_even_selected': '#e3f2fd',
        'row_odd_selected': '#bbdefb',
        # v5.7.5: 선택 행 글자색 — 연한 배경에서도 데이터가 보이도록 진한색
        'row_selected_fg': '#1a1a1a',

        # 헤더
        'header_bg': '#1976d2',
        'header_fg': '#ffffff',

        # 테두리
        'border': '#9e9e9e',
    }

    # v8.6.4: ProDark Slate 팔레트 통합 — Tailwind Slate 기반
    COLORS_DARK = {
        'grid_line': '#334155',        # Slate-700
        'grid_line_strong': '#475569', # Slate-600
        'row_even': '#0f172a',         # Slate-900 (ProDark bg_primary)
        'row_odd': '#1e293b',          # Slate-800 (ProDark bg_secondary)
        'row_even_selected': '#164e63',# Cyan-900 (ProDark selection)
        'row_odd_selected': '#155e75', # Cyan-800
        'row_selected_fg': '#ecfeff',  # Cyan-50
        'header_bg': '#1e293b',        # Slate-800
        'header_fg': '#f1f5f9',        # Slate-100
        'border': '#334155',           # Slate-700
        'foreground': '#f1f5f9',       # Slate-100
        'fieldbackground': '#0f172a',  # Slate-900
    }

    # 행 높이 (v8.7.0 Phase1: normal 36px로 가독성 개선)
    ROW_HEIGHT = {
        'compact': 24,
        'normal': 40,  # v8.6.4: 36→40
        'comfortable': 40,
    }

    @classmethod
    def apply_grid_lines(
        cls,
        treeview: ttk.Treeview,
        show_vertical: bool = True,
        show_horizontal: bool = True,
        is_dark: bool = False
    ) -> None:
        """
        Treeview에 그리드 라인 스타일 적용 (v5.6.9: 다크 테마 시 글씨 밝은색)
        
        Args:
            treeview: 대상 Treeview 위젯
            show_vertical: 세로 그리드 라인 표시
            show_horizontal: 가로 그리드 라인 표시
            is_dark: 다크 테마 여부 — True면 foreground/fieldbackground 밝은색
        """
        style = ttk.Style()
        style_name = f"Grid.{id(treeview)}.Treeview"
        colors = cls.COLORS_DARK if is_dark else cls.COLORS
        fg = colors.get('foreground', '#f0f0f0') if is_dark else '#1a1a1a'
        fbg = colors.get('fieldbackground', '#1e1e1e') if is_dark else cls.COLORS['row_even']

        style.configure(
            style_name,
            background=colors['row_even'],
            foreground=fg,
            fieldbackground=fbg,
            borderwidth=1,
            relief='solid'
        )

        # v5.7.5: 선택 행 foreground 명시 — 연한 배경에서 글자가 사라지는 현상 수정
        # ★ v6.3.1: !selected foreground도 명시 — 다크 모드 비선택 행 글자 안 보임 수정
        selected_fg = colors.get('row_selected_fg', '#1a1a1a' if not is_dark else '#e0e0e0')
        style.map(
            style_name,
            background=[
                ('selected', colors['row_even_selected']),
                ('!selected', colors['row_odd'])
            ],
            foreground=[
                ('selected', selected_fg),
                ('!selected', fg),
            ]
        )

        treeview.configure(style=style_name)

        if show_vertical or show_horizontal:
            style.configure(
                f"{style_name}.Heading",
                background=colors['header_bg'],
                foreground=colors['header_fg'],
                relief='raised',
                borderwidth=1,
                anchor='center',
            )

    @classmethod
    def update_grid_style_for_theme(cls, treeview: ttk.Treeview, is_dark: bool) -> None:
        """v5.6.9: 테마 변경 시 Grid/RowHeight 스타일 전체 갱신 (배경+글씨 — 다크에서 행 배경도 어둡게)"""
        try:
            style_name = treeview.cget('style')
            if not style_name or not (style_name.startswith('Grid.') or style_name.startswith('RowHeight.')):
                return
            style = ttk.Style()
            colors = cls.COLORS_DARK if is_dark else cls.COLORS
            fg = colors.get('foreground', '#f0f0f0') if is_dark else '#1a1a1a'
            fbg = colors.get('fieldbackground', '#1e1e1e') if is_dark else cls.COLORS['row_even']
            # 배경·전경·필드배경 전부 갱신
            style.configure(
                style_name,
                background=colors['row_even'],
                foreground=fg,
                fieldbackground=fbg,
                borderwidth=1,
                relief='solid'
            )
            # 행 배경·선택 행 글자색 맵 갱신 (v5.7.5: selected foreground로 선택 시 가독성 유지)
            # ★ v6.3.1: !selected foreground 추가
            _sel_fg = colors.get('row_selected_fg', '#1a1a1a' if not is_dark else '#e0e0e0')
            style.map(
                style_name,
                background=[
                    ('selected', colors['row_even_selected']),
                    ('!selected', colors['row_odd'])
                ],
                foreground=[
                    ('selected', _sel_fg),
                    ('!selected', fg),
                ]
            )
            style.configure(
                f"{style_name}.Heading",
                background=colors['header_bg'],
                foreground=colors['header_fg'],
                relief='raised',
                borderwidth=1,
                anchor='center',
            )
            # ★ v6.3.1: 줄무늬 태그 foreground도 갱신
            for tag_name in ('evenrow', 'oddrow', 'even', 'odd'):
                try:
                    existing = treeview.tag_configure(tag_name)
                    if existing and existing.get('background'):
                        treeview.tag_configure(tag_name, foreground=fg)
                except (tk.TclError, ValueError):
                    logger.debug("[SUPPRESSED] exception in table_styler.py")  # noqa
        except (tk.TclError, ValueError, TypeError) as e:
            logger.debug(f"Grid 스타일 테마 갱신 무시: {e}")

    @classmethod
    def apply_striped_rows(
        cls,
        treeview: ttk.Treeview,
        tag_even: str = 'evenrow',
        tag_odd: str = 'oddrow',
        is_dark: bool = False
    ) -> None:
        """
        Treeview에 줄무늬(striped rows) 적용
        ★ v6.3.1: foreground 필수 설정 — 다크 모드 글자 안 보임 근본 수정
        
        Args:
            treeview: 대상 Treeview
            tag_even: 짝수 행 태그
            tag_odd: 홀수 행 태그
            is_dark: 다크 테마 여부
        """
        colors = cls.COLORS_DARK if is_dark else cls.COLORS
        fg = colors.get('foreground', '#f0f0f0') if is_dark else '#1a1a1a'

        # ★ 핵심 수정: background + foreground 동시 설정
        treeview.tag_configure(tag_even, background=colors['row_even'], foreground=fg)
        treeview.tag_configure(tag_odd, background=colors['row_odd'], foreground=fg)

        # 기존 아이템에 태그 적용
        for idx, item in enumerate(treeview.get_children()):
            tag = tag_even if idx % 2 == 0 else tag_odd
            treeview.item(item, tags=(tag,))

    @classmethod
    def set_row_height(
        cls,
        treeview: ttk.Treeview,
        mode: str = 'normal'
    ) -> None:
        """
        행 높이 설정.
        이미 Grid.xxx 스타일이면 해당 스타일에 rowheight만 추가(테마 색 유지).
        """
        height = cls.ROW_HEIGHT.get(mode, cls.ROW_HEIGHT['normal'])
        style = ttk.Style()
        current = treeview.cget('style') or ''
        if current.startswith('Grid.'):
            style.configure(current, rowheight=height)
        else:
            style_name = f"RowHeight.{id(treeview)}.Treeview"
            style.configure(style_name, rowheight=height)
            treeview.configure(style=style_name)

    @classmethod
    def toggle_column(
        cls,
        treeview: ttk.Treeview,
        column_id: str,
        visible: bool
    ) -> None:
        """
        컬럼 표시/숨김 토글
        
        Args:
            treeview: 대상 Treeview
            column_id: 컬럼 ID
            visible: True=표시, False=숨김
        """
        # NoneType 체크
        if treeview is None:
            logger.warning(f"toggle_column: treeview가 None입니다 (column_id={column_id})")
            return

        if visible:
            # 컬럼 너비 복원 (기본값 또는 저장된 값)
            width = getattr(treeview, f'_{column_id}_width', 100)
            treeview.column(column_id, width=width, minwidth=50)
        else:
            # 현재 너비 저장
            current_width = treeview.column(column_id, 'width')
            setattr(treeview, f'_{column_id}_width', current_width)
            # 너비 0으로 설정 (숨김)
            treeview.column(column_id, width=0, minwidth=0)

    @classmethod
    def create_style_toolbar(
        cls,
        parent: tk.Widget,
        treeview: ttk.Treeview,
        toggleable_columns: Optional[List[tuple]] = None
    ) -> tk.Frame:
        """
        스타일 조정 툴바 생성
        
        Args:
            parent: 부모 위젯
            treeview: 대상 Treeview
            toggleable_columns: [(컬럼ID, 표시명), ...]
            
        Returns:
            툴바 프레임
        """
        _ts_dark = ThemeColors.is_dark_theme(getattr(parent, 'current_theme', 'darkly'))
        _ts_bg = ThemeColors.get('bg_secondary', _ts_dark)
        _ts_fg = ThemeColors.get('text_primary', _ts_dark)
        toolbar = tk.Frame(parent, bg=_ts_bg, pady=5)

        # 왼쪽: 컬럼 토글
        if toggleable_columns:
            tk.Label(
                toolbar,
                text="표시 컬럼:",
                bg=_ts_bg,
                fg=_ts_fg,
                font=('맑은 고딕', 10)
            ).pack(side=tk.LEFT, padx=(10, 5))

            for col_id, col_name in toggleable_columns:
                var = tk.BooleanVar(value=True)

                def make_toggle(cid, v):
                    def toggle():
                        cls.toggle_column(treeview, cid, v.get())
                    return toggle

                cb = tk.Checkbutton(
                    toolbar,
                    text=col_name,
                    variable=var,
                    command=make_toggle(col_id, var),
                    bg=_ts_bg,
                    fg=_ts_fg,
                    font=('맑은 고딕', 10)
                )
                cb.pack(side=tk.LEFT, padx=2)

        # v5.7.5: 표시 모드(컬럼/본문/날짜) UI 제거 — 행 높이는 기본(normal) 고정
        return toolbar

    @classmethod
    def refresh_striped_rows(
        cls,
        treeview: ttk.Treeview,
        tag_even: str = 'evenrow',
        tag_odd: str = 'oddrow'
    ) -> None:
        """
        줄무늬 새로고침 (데이터 변경 후 호출)
        ★ v6.3.1: 태그 foreground도 현재 테마에 맞게 재설정
        
        Args:
            treeview: 대상 Treeview
            tag_even: 짝수 행 태그
            tag_odd: 홀수 행 태그
        """
        # ★ 현재 테마 감지 → foreground 동기화
        is_dark = cls._detect_dark()
        colors = cls.COLORS_DARK if is_dark else cls.COLORS
        fg = colors.get('foreground', '#f0f0f0') if is_dark else '#1a1a1a'
        treeview.tag_configure(tag_even, background=colors['row_even'], foreground=fg)
        treeview.tag_configure(tag_odd, background=colors['row_odd'], foreground=fg)

        for idx, item in enumerate(treeview.get_children()):
            tag = tag_even if idx % 2 == 0 else tag_odd
            treeview.item(item, tags=(tag,))

    @classmethod
    def _detect_dark(cls) -> bool:
        """현재 ttk.Style 배경색으로 다크 모드 자동 감지"""
        try:
            style = ttk.Style()
            bg = style.lookup('Treeview', 'background') or style.lookup('.', 'background') or ''
            if not bg:
                return False
            c = bg.strip().lstrip('#')
            if len(c) == 3:
                c = ''.join(ch * 2 for ch in c)
            if len(c) >= 6:
                r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                return (r * 299 + g * 587 + b * 114) / 1000 < 128
        except Exception:
            logger.debug("[SUPPRESSED] exception in table_styler.py")  # noqa
        return False


# 간편 함수
def apply_table_style(
    treeview: ttk.Treeview,
    grid_lines: bool = True,
    striped_rows: bool = True,
    row_height: str = 'normal',
    is_dark: bool = False
) -> None:
    """
    테이블에 스타일 일괄 적용 (v5.6.9: is_dark 시 다크 테마 글씨 가시성)
    
    Args:
        treeview: 대상 Treeview
        grid_lines: 그리드 라인 표시
        striped_rows: 줄무늬 표시
        row_height: 행 높이 ('compact', 'normal', 'comfortable')
        is_dark: 다크 테마 여부
    """
    if grid_lines:
        TableStyler.apply_grid_lines(treeview, is_dark=is_dark)

    if striped_rows:
        TableStyler.apply_striped_rows(treeview, is_dark=is_dark)

    TableStyler.set_row_height(treeview, row_height)


# 테스트
if __name__ == '__main__':
    root = tk.Tk()
    root.title("Table Style Test")
    root.geometry("800x400")

    # 테스트 Treeview
    columns = ('col1', 'col2', 'col3', 'col4')
    tree = ttk.Treeview(root, columns=columns, show='headings', height=15)

    for col in columns:
        tree.heading(col, text=col.upper(), anchor='center')
        tree.column(col, width=150)

    # 테스트 데이터
    for i in range(20):
        tree.insert('', 'end', values=(f'Data {i}-1', f'Data {i}-2', f'Data {i}-3', f'Data {i}-4'))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 스타일 적용
    apply_table_style(tree, grid_lines=True, striped_rows=True, row_height='normal')

    # 툴바 생성
    toolbar = TableStyler.create_style_toolbar(
        root,
        tree,
        toggleable_columns=[('col2', 'COL2'), ('col3', 'COL3')]
    )
    toolbar.pack(side=tk.BOTTOM, fill=tk.X)

    root.mainloop()
