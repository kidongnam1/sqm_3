"""
SQM - 스프레드시트형 붙여넣기 테이블 다이얼로그
==============================================
입고 템플릿·로케이션 매핑 등에서 파일 대신 화면에 표를 띄우고 Ctrl+V 붙여넣기 후 업로드.
데이터 영역은 Entry 그리드로 구현해 가로·세로 셀 경계선이 보이도록 함.
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import logging
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import List, Optional, Tuple

from .ui_constants import ThemeColors, apply_modal_window_options, center_dialog

logger = logging.getLogger(__name__)

# 데이터 행 수 (가로·세로 선이 보이는 그리드)
DEFAULT_DATA_ROWS = 30      # 기본 행 수 (붙여넣기 시 자동 확장)
MAX_DATA_ROWS = 2000        # 최대 행 수 (대량 붙여넣기 지원: 880행 이상)

# 헤더 행 자동 감지 키워드
_HEADER_KEYWORDS = {
    'lot_no', 'lot no', 'lotno', 'sap_no', 'sap no', 'product',
    'qty_mt', 'qty', 'mt', 'customer', 'sold_to', 'sale_ref',
    'outbound_date', 'warehouse', 'wh', '품명', '수량', '고객'
}


def _detect_header_row(line: str, ncols: int) -> bool:
    """붙여넣기 첫 행이 헤더인지 감지."""
    parts = [p.strip().lower().replace(' ', '_') for p in line.replace('\r', '').split('\t')]
    match_count = sum(1 for p in parts if p in _HEADER_KEYWORDS)
    return match_count >= min(2, ncols)


def _paste_into_grid(entries: List[List[tk.Entry]], ncols: int,
                     inner_frame=None, col_widths=None, bg_cell='#FFFFFF',
                     fg_cell='#333333', sep_cell="\t", sep_row="\n",
                     col_ids: Optional[List[str]] = None,
                     auto_number_column: Optional[str] = None) -> int:
    """클립보드 내용을 Entry 그리드에 채움. 행 자동확장/헤더 스킵 지원."""
    try:
        raw = entries[0][0].winfo_toplevel().clipboard_get()
    except tk.TclError:
        return 0
    lines = [ln for ln in raw.strip().split(sep_row) if ln.strip()]
    if not lines:
        return 0

    # 헤더 행 스킵
    start_line = 0
    if _detect_header_row(lines[0], ncols):
        start_line = 1
        logger.info("붙여넣기: 헤더 행 감지 → 스킵")
    data_lines = lines[start_line:]
    if not data_lines:
        return 0

    skip_idx = -1
    if auto_number_column and col_ids and auto_number_column in col_ids:
        skip_idx = col_ids.index(auto_number_column)

    # 첫 빈 행 찾기 (순번 컬럼은 제외)
    start_row = 0
    for ri, row_e in enumerate(entries):
        if all(
            not (e.get() or '').strip()
            for ci, e in enumerate(row_e)
            if ci != skip_idx
        ):
            start_row = ri
            break

    # 행 부족 시 자동 확장
    needed_rows = start_row + len(data_lines)
    while len(entries) < needed_rows and len(entries) < MAX_DATA_ROWS:
        if inner_frame is None:
            break
        row_idx = len(entries)
        row_entries = []
        for col_idx in range(ncols):
            width_chars = max(4, min((col_widths[col_idx] if col_widths else 80) // 8, 24))
            e = tk.Entry(
                inner_frame,
                width=width_chars,
                font=("맑은 고딕", 9),
                relief="solid",
                bd=1,
                bg=bg_cell,
                fg=fg_cell,
                insertbackground=fg_cell,
            )
            if col_idx == skip_idx:
                e.configure(state='readonly', readonlybackground=bg_cell, disabledforeground=fg_cell)
            e.grid(row=row_idx, column=col_idx, sticky="nsew", padx=0, pady=0)
            row_entries.append(e)
        entries.append(row_entries)

    filled = 0
    for data_idx, line in enumerate(data_lines):
        row_idx = start_row + data_idx
        if row_idx >= len(entries):
            logger.warning(
                f"붙여넣기 행 초과: {len(data_lines)}행 중 {filled}행만 채움 "
                f"(최대 {MAX_DATA_ROWS}행)"
            )
            break
        parts = [p.strip() for p in line.replace("\r", "").split(sep_cell)]
        target_cols = [ci for ci in range(ncols) if ci != skip_idx]
        for part_idx, col_idx in enumerate(target_cols):
            val = parts[part_idx] if part_idx < len(parts) else ""
            try:
                entries[row_idx][col_idx].delete(0, tk.END)
                entries[row_idx][col_idx].insert(0, val)
            except (tk.TclError, IndexError) as e:
                logger.debug(f"[_paste_into_grid] Suppressed: {e}")
        filled += 1

    return filled


def show_paste_table_dialog(
    parent: tk.Misc,
    title: str,
    columns: List[Tuple[str, str, int]],
    instruction: str = "아래 표에 데이터를 붙여넣기(Ctrl+V) 한 뒤 [확인]을 누르세요.",
    confirm_text: str = "확인",
    cancel_text: str = "취소",
    on_confirm: Optional[Callable[[List[dict]], None]] = None,
    min_size: Tuple[int, int] = (720, 420),
    auto_number_column: Optional[str] = None,
) -> None:
    """
    스프레드시트형 테이블 다이얼로그. 컬럼 헤더 + 데이터 셀에 가로·세로 경계선 표시, Ctrl+V 붙여넣기 지원.
    """
    win = create_themed_toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(True, True)
    win.minsize(min_size[0], min_size[1])
    apply_modal_window_options(win)

    frm = ttk.Frame(win, padding=12)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frm, text=instruction, font=("맑은 고딕", 10), wraplength=680).pack(anchor=tk.W, pady=(0, 8))
    paste_status_var = tk.StringVar(value="붙여넣기 대기 중 (Ctrl+V). 여러 번 붙여넣으면 빈 다음 행부터 누적 입력됩니다.")
    ttk.Label(frm, textvariable=paste_status_var, font=("맑은 고딕", 9)).pack(anchor=tk.W, pady=(0, 6))

    col_ids = [c[0] for c in columns]
    [c[1] for c in columns]
    col_widths = [min(c[2], 180) for c in columns]
    ncols = len(col_ids)
    nrows = DEFAULT_DATA_ROWS

    try:
        from ..mixins.theme_mixin import _is_dark_theme
        is_dark = _is_dark_theme(win)
    except Exception:
        is_dark = False
    bg_cell = ThemeColors.get("bg_card", is_dark) or "#FFFFFF"
    fg_cell = ThemeColors.get("text_primary", is_dark) or "#333333"
    header_bg = ThemeColors.get("btn_report", is_dark) or "#4472C4"

    # 헤더 행 (가로·세로 선 있게 Label + relief)
    header_frm = tk.Frame(frm)
    header_frm.pack(fill=tk.X, pady=(0, 0))
    for col_idx, (cid, disp, w) in enumerate(columns):
        width_chars = max(4, min(w // 8, 24))
        lbl = tk.Label(
            header_frm,
            text=disp,
            width=width_chars,
            anchor="center",
            font=("맑은 고딕", 9, "bold"),
            relief="ridge",
            bd=1,
            bg=header_bg,
            fg=tc('text_primary'),
        )
        lbl.grid(row=0, column=col_idx, sticky="nsew", padx=(0, 0), pady=(0, 0))
    header_frm.grid_columnconfigure(list(range(ncols)), weight=1)

    # 데이터 영역: Entry 그리드 (가로·세로 선이 보이도록 relief + bd)
    table_container = tk.Frame(frm)
    table_container.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

    canvas = tk.Canvas(table_container, highlightthickness=0)
    # 스크롤바 가시성 강화: 배경과 반대 대비색 사용
    sb_trough = "#111111" if not is_dark else "#f2f2f2"
    sb_thumb = "#f2f2f2" if not is_dark else "#111111"
    sb_active = "#ffffff" if not is_dark else "#000000"
    sb_width = 16
    scroll_y = tk.Scrollbar(
        table_container,
        orient=tk.VERTICAL,
        command=canvas.yview,
        width=sb_width,
        troughcolor=sb_trough,
        bg=sb_thumb,
        activebackground=sb_active,
        relief="solid",
        bd=1,
    )
    scroll_x = tk.Scrollbar(
        table_container,
        orient=tk.HORIZONTAL,
        command=canvas.xview,
        width=sb_width,
        troughcolor=sb_trough,
        bg=sb_thumb,
        activebackground=sb_active,
        relief="solid",
        bd=1,
    )

    inner = tk.Frame(canvas)
    inner.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

    entries: List[List[tk.Entry]] = []
    num_idx = col_ids.index(auto_number_column) if auto_number_column and auto_number_column in col_ids else -1

    for row_idx in range(nrows):
        row_entries = []
        for col_idx in range(ncols):
            width_chars = max(4, min(col_widths[col_idx] // 8, 24))
            e = tk.Entry(
                inner,
                width=width_chars,
                font=("맑은 고딕", 9),
                relief="solid",
                bd=1,
                bg=bg_cell,
                fg=fg_cell,
                insertbackground=fg_cell,
            )
            if col_idx == num_idx:
                e.configure(state='readonly', readonlybackground=bg_cell, disabledforeground=fg_cell)
            e.grid(row=row_idx, column=col_idx, sticky="nsew", padx=0, pady=0)
            row_entries.append(e)
        entries.append(row_entries)
    for c in range(ncols):
        inner.grid_columnconfigure(c, weight=1)
    for r in range(nrows):
        inner.grid_rowconfigure(r, weight=0)

    scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
    scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _on_paste(event=None):
        count = _paste_into_grid(
            entries, ncols, inner, col_widths, bg_cell, fg_cell,
            col_ids=col_ids, auto_number_column=auto_number_column
        )
        if count > 0:
            if auto_number_column and auto_number_column in col_ids:
                for ri, row_e in enumerate(entries):
                    try:
                        row_has_data = any((row_e[ci].get() or '').strip() for ci in range(ncols) if ci != num_idx)
                        row_e[num_idx].configure(state='normal')
                        row_e[num_idx].delete(0, tk.END)
                        row_e[num_idx].insert(0, str(ri + 1) if row_has_data else "")
                        row_e[num_idx].configure(state='readonly')
                    except (tk.TclError, ValueError, IndexError):
                        continue
            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            try:
                filled_rows = 0
                for row_e in entries:
                    if any((e.get() or '').strip() for e in row_e):
                        filled_rows += 1
                paste_status_var.set(f"최근 붙여넣기 {count}행 완료 · 현재 총 입력 {filled_rows}행")
            except (tk.TclError, ValueError):
                logger.debug("[SUPPRESSED] exception in paste_table_dialog.py")  # noqa
        else:
            paste_status_var.set("클립보드에 붙여넣을 데이터가 없거나 형식이 비어 있습니다.")
        return "break"

    inner.bind("<Control-v>", _on_paste)
    inner.bind("<Control-V>", _on_paste)
    for row_entries in entries:
        for e in row_entries:
            e.bind("<Control-v>", _on_paste)
            e.bind("<Control-V>", _on_paste)

    def _on_confirm():
        rows = []
        num_idx = col_ids.index(auto_number_column) if auto_number_column and auto_number_column in col_ids else -1
        for row_entries in entries:
            row = {}
            for i, e in enumerate(row_entries):
                cid = col_ids[i] if i < len(col_ids) else ""
                try:
                    row[cid] = (e.get() or "").strip()
                except (tk.TclError, TypeError):
                    row[cid] = ""
            has_payload = False
            for i, cid in enumerate(col_ids):
                if i == num_idx:
                    continue
                if (row.get(cid) or '').strip():
                    has_payload = True
                    break
            if has_payload:
                rows.append(row)
        if on_confirm and rows:
            try:
                on_confirm(rows)
                win.destroy()
            except Exception as e:
                logger.exception("paste_table on_confirm: %s", e)
                try:
                    from .ui_constants import CustomMessageBox
                    CustomMessageBox.showerror(win, "오류", f"처리 중 오류:\n{e}")
                except Exception as _ui_e:
                    logging.getLogger(__name__).debug(f"[붙여넣기] 오류 표시 실패: {_ui_e}")
        elif not rows:
            try:
                from .ui_constants import CustomMessageBox
                CustomMessageBox.showwarning(win, "데이터 없음", "유효한 데이터가 없습니다.")
            except Exception as _ui_e:
                logging.getLogger(__name__).debug(f"[붙여넣기] 경고 표시 실패: {_ui_e}")
        else:
            win.destroy()

    def _on_cancel():
        win.destroy()

    btn_frm = ttk.Frame(frm)
    btn_frm.pack(fill=tk.X, pady=(12, 0))
    ttk.Button(btn_frm, text=confirm_text, command=_on_confirm).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frm, text=cancel_text, command=_on_cancel).pack(side=tk.LEFT, padx=4)

    win.geometry(f"{min_size[0]}x{min_size[1]}")
    center_dialog(win, parent)
    try:
        if entries and entries[0]:
            entries[0][0].focus_set()
    except tk.TclError as e:
        logger.debug(f"[_on_cancel] Suppressed: {e}")
