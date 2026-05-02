"""
SQM v6.1.1 - 테마 변경 시 전체 위젯 자동 갱신 엔진
====================================================

테마 토글 때 화면에 존재하는 모든 Treeview(+ 네이티브 위젯)를
자동 탐색하여 색상을 일괄 재적용합니다.

사용법:
    from gui_app_modular.utils.theme_refresh import refresh_all_widgets_for_theme
    stats = refresh_all_widgets_for_theme(self)
"""

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


def _walk_widgets(root_widget):
    """루트 위젯부터 모든 자식 위젯을 스택으로 탐색하는 제너레이터."""
    visited = set()
    stack = [root_widget]
    while stack:
        w = stack.pop()
        w_id = id(w)
        if w_id in visited:
            continue
        visited.add(w_id)
        yield w
        try:
            children = w.winfo_children()
            stack.extend(children)
        except (tk.TclError, RuntimeError) as e:
            logger.debug(f"[_walk_widgets] Suppressed: {e}")


def _safe_lookup(style: ttk.Style, widget_class: str, option: str, fallback: str) -> str:
    """ttk.Style.lookup()을 안전하게 호출."""
    try:
        value = style.lookup(widget_class, option)
        if not value or str(value).strip() == '':
            return fallback
        return str(value)
    except (tk.TclError, RuntimeError, ValueError):
        return fallback


def _is_dark_color(color_str: str) -> bool:
    """색상 문자열의 명도로 다크 여부 판별."""
    if not color_str:
        return False
    try:
        c = color_str.strip().lower()
        if c in ('white', '#ffffff', '#fff'):
            return False
        if c in ('black', '#000000', '#000'):
            return True
        if c.startswith('#'):
            h = c.lstrip('#')
            if len(h) == 3:
                h = ''.join([ch * 2 for ch in h])
            if len(h) >= 6:
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                return brightness < 128
        return False
    except (ValueError, IndexError):
        return False


def get_theme_colors_from_style() -> dict:
    """현재 ttk.Style에서 Treeview 관련 색상을 동적으로 조회."""
    style = ttk.Style()
    fg = _safe_lookup(style, "Treeview", "foreground", "")
    bg = _safe_lookup(style, "Treeview", "background", "")
    field_bg = _safe_lookup(style, "Treeview", "fieldbackground", bg)
    if not fg or fg.strip() == '':
        fg = _safe_lookup(style, ".", "foreground", "#000000")
    if not bg or bg.strip() == '':
        bg = _safe_lookup(style, ".", "background", "#ffffff")
    if not field_bg or field_bg.strip() == '':
        field_bg = bg
    sel_bg = _safe_lookup(style, "Treeview", "selectbackground", "#0078D7")
    sel_fg = _safe_lookup(style, "Treeview", "selectforeground", "#ffffff")
    if not sel_bg or sel_bg.strip() == '':
        sel_bg = tc('select_bg')
    if not sel_fg or sel_fg.strip() == '':
        sel_fg = tc('select_fg')
    heading_fg = _safe_lookup(style, "Treeview.Heading", "foreground", fg)
    heading_bg = _safe_lookup(style, "Treeview.Heading", "background", bg)
    is_dark = _is_dark_color(bg)
    return {
        'fg': fg, 'bg': bg, 'field_bg': field_bg,
        'sel_fg': sel_fg, 'sel_bg': sel_bg,
        'heading_fg': heading_fg, 'heading_bg': heading_bg,
        'is_dark': is_dark,
    }


def _refresh_single_treeview(tree: ttk.Treeview, colors: dict, style: ttk.Style) -> None:
    """단일 Treeview의 태그 + 스타일을 현재 테마에 맞게 갱신.
    ★ v6.3.2: 태그 background도 함께 갱신 — 다크 전환 시 밝은 배경 잔류 방지
    """
    fg = colors['fg']
    bg = colors['bg']
    is_dark = colors['is_dark']
    sel_fg = colors['sel_fg']
    sel_bg = colors['sel_bg']

    # ★ v6.3.2: odd/even 태그 — background + foreground 동시 갱신
    if is_dark:
        tag_colors = {
            'odd': ('#333333', '#e0e0e0'), 'oddrow': ('#2a2a2a', '#f0f0f0'),
            'even': ('#2b2b2b', '#e0e0e0'), 'evenrow': ('#1e1e1e', '#f0f0f0'),
            'stripe': (None, '#e0e0e0'),
        }
    else:
        tag_colors = {
            'odd': ('#F8F9FA', '#1a1a1a'), 'oddrow': ('#f5f5f5', '#1a1a1a'),
            'even': ('#FFFFFF', '#1a1a1a'), 'evenrow': ('#ffffff', '#1a1a1a'),
            'stripe': (None, '#1a1a1a'),
        }

    for tag_name, (tag_bg, tag_fg) in tag_colors.items():
        try:
            existing = tree.tag_configure(tag_name)
            if existing and (existing.get('background') or existing.get('foreground')):
                if tag_bg:
                    tree.tag_configure(tag_name, background=tag_bg, foreground=tag_fg)
                else:
                    tree.tag_configure(tag_name, foreground=tag_fg)
        except (tk.TclError, ValueError) as e:
            logger.debug(f"[_refresh_single_treeview] Suppressed: {e}")
    try:
        from gui_app_modular.utils.ui_constants import ThemeColors
        ThemeColors.configure_tags(tree, is_dark)
    except (ImportError, Exception) as e:
        logger.debug(f"ThemeColors.configure_tags skip: {e}")
        for tag_name in ('available', 'picked', 'reserved', 'shipped', 'depleted'):
            try:
                tree.tag_configure(tag_name, foreground=fg)
            except (tk.TclError, ValueError) as e:
                logger.debug(f"[_refresh_single_treeview] Suppressed: {e}")
    try:
        style_name = tree.cget('style') or 'Treeview'
        # 재고 탭 Inv.Treeview: 본문·헤더·합계바(bg_card)와 동일 팔레트 (기본 Treeview 색 덮어쓰기 방지)
        inv_unified_bg = None
        if style_name == 'Inv.Treeview':
            try:
                from gui_app_modular.utils.ui_constants import ThemeColors
                inv_unified_bg = ThemeColors.get('bg_card', is_dark)
            except (ImportError, Exception) as e:
                logger.debug(f"Inv.Treeview 통일 배경 조회 skip: {e}")
        body_bg = inv_unified_bg if inv_unified_bg else bg
        field_bg = inv_unified_bg if inv_unified_bg else colors['field_bg']
        heading_bg_use = inv_unified_bg if inv_unified_bg else colors['heading_bg']
        style.configure(style_name, foreground=fg, background=body_bg, fieldbackground=field_bg)
        style.map(style_name,
                  foreground=[('selected', sel_fg), ('!selected', fg)],
                  background=[('selected', sel_bg)])
        heading_style = f"{style_name}.Heading" if style_name != 'Treeview' else 'Treeview.Heading'
        if style_name == 'Inv.Treeview':
            style.configure(
                heading_style,
                foreground=colors['heading_fg'],
                background=heading_bg_use,
                relief='flat',
                borderwidth=0,
                anchor='center',
            )
        else:
            style.configure(
                heading_style,
                foreground=colors['heading_fg'],
                background=heading_bg_use,
                anchor='center',
            )
    except (tk.TclError, ValueError, RuntimeError) as e:
        logger.debug(f"Treeview style update skip: {e}")
    try:
        from gui_app_modular.utils.table_styler import TableStyler
        TableStyler.update_grid_style_for_theme(tree, is_dark)
    except (ImportError, Exception) as e:
        logger.debug(f"[_refresh_single_treeview] Suppressed: {e}")
    try:
        from gui_app_modular.utils.ui_constants import apply_treeview_center_alignment
        apply_treeview_center_alignment(tree)
    except (ImportError, Exception) as e:
        logger.debug(f"[_refresh_single_treeview] center_alignment skip: {e}")


def _refresh_native_widget(widget, colors: dict) -> None:
    """tk.Text, tk.Label, tk.Listbox fg/bg를 테마와 충돌 시에만 동기화."""
    # 컬러 고정 영역(툴바/탭 등)은 테마 리프레시에서 제외
    if getattr(widget, '_keep_colorful_theme', False):
        return
    if getattr(widget, '_tc_skip', False):
        return
    is_dark = colors['is_dark']
    theme_fg = colors['fg']
    theme_bg = colors['bg']
    sel_bg = colors.get('sel_bg', '#0078D7')
    sel_fg = colors.get('sel_fg', '#ffffff')

    def _brightness_of(color_value: str):
        """
        위젯 기준 실제 RGB 밝기(0~255) 계산.
        시스템 색상명(SystemWindowText 등)도 winfo_rgb로 해석 가능.
        """
        try:
            r16, g16, b16 = widget.winfo_rgb(color_value)
            r8, g8, b8 = r16 / 257.0, g16 / 257.0, b16 / 257.0
            return (r8 * 299 + g8 * 587 + b8 * 114) / 1000.0
        except (tk.TclError, RuntimeError, ValueError):
            return None

    try:
        current_fg = str(widget.cget('fg')) if hasattr(widget, 'cget') else ''
        current_bg = str(widget.cget('bg')) if hasattr(widget, 'cget') else ''
    except (tk.TclError, RuntimeError):
        return
    if not current_fg:
        return
    fg_b = _brightness_of(current_fg)
    bg_b = _brightness_of(current_bg)

    # 색상을 해석할 수 없거나 대비가 부족하면 테마 색으로 강제 동기화
    needs_fix = fg_b is None or bg_b is None
    if not needs_fix:
        low_contrast = abs(fg_b - bg_b) < 80
        wrong_bg_for_theme = (is_dark and bg_b > 170) or ((not is_dark) and bg_b < 85)
        wrong_fg_for_theme = (is_dark and fg_b < 120) or ((not is_dark) and fg_b > 180)
        needs_fix = low_contrast or wrong_bg_for_theme or wrong_fg_for_theme

    if needs_fix:
        try:
            widget.configure(fg=theme_fg)
            widget.configure(bg=theme_bg)
            if isinstance(widget, tk.Listbox):
                widget.configure(selectbackground=sel_bg, selectforeground=sel_fg)
            if isinstance(widget, tk.Text):
                widget.configure(insertbackground=theme_fg)
        except (tk.TclError, RuntimeError) as e:
            logger.debug(f"[_brightness_of] Suppressed: {e}")




def _refresh_ttk_label(widget, colors: dict) -> None:
    """v6.3.1: ttk.Label hardcoded foreground → 테마 안전색 변환"""
    is_dark = colors['is_dark']
    theme_fg = colors['fg']

    DARK_SAFE = {
        '#dc2626': '#f87171', 'red': '#f87171', 'darkred': '#f87171',
        '#d97706': '#fbbf24', 'orange': '#fbbf24',
        '#059669': '#34d399', 'green': '#34d399', 'darkgreen': '#34d399',
        '#6366f1': '#818cf8', 'purple': '#a78bfa',
        '#ea580c': '#fb923c',
        '#2563eb': '#60a5fa', 'blue': '#60a5fa', 'darkblue': '#93c5fd',
        'gray': '#9ca3af', 'grey': '#9ca3af',
        '#000000': '#e5e7eb', 'black': '#e5e7eb',
    }
    LIGHT_SAFE = {
        '#f87171': '#dc2626', '#fbbf24': '#d97706', '#34d399': '#059669',
        '#818cf8': '#6366f1', '#fb923c': '#ea580c', '#60a5fa': '#2563eb',
        '#9ca3af': '#6b7280', '#e5e7eb': '#1f2937',
        'white': '#1f2937', '#ffffff': '#1f2937',
    }

    try:
        current_fg = str(widget.cget('foreground')).strip().lower()
        if not current_fg or current_fg == theme_fg.strip().lower():
            return

        if is_dark:
            safe = DARK_SAFE.get(current_fg)
            if safe:
                widget.configure(foreground=safe)
        else:
            safe = LIGHT_SAFE.get(current_fg)
            if safe:
                widget.configure(foreground=safe)
    except (tk.TclError, RuntimeError, ValueError) as e:
        logger.debug(f"[_refresh_ttk_label] Suppressed: {e}")


def refresh_all_widgets_for_theme(app) -> dict:
    """테마 변경 시 화면의 모든 위젯을 자동 탐색하여 색상 일괄 갱신."""
    stats = {'treeviews': 0, 'native_widgets': 0, 'is_dark': False}
    try:
        try:
            from fixes.global_tree_style import apply_global_tree_style
            from gui_app_modular.utils.ui_constants import _GLOBAL_IS_DARK
            _root = getattr(app, 'root', app)
            apply_global_tree_style(_root, _GLOBAL_IS_DARK)  # v8.6.4: 인자 추가
        except (ImportError, Exception) as e:
            logger.debug(f"global_tree_style 재적용 skip: {e}")
        colors = get_theme_colors_from_style()
        stats['is_dark'] = colors['is_dark']
        style = ttk.Style()
        for w in _walk_widgets(app.root):
            if getattr(w, '_tc_skip', False):
                continue
            if isinstance(w, ttk.Treeview):
                _refresh_single_treeview(w, colors, style)
                stats['treeviews'] += 1
            elif isinstance(w, (tk.Text, tk.Listbox)):
                _refresh_native_widget(w, colors)
                stats['native_widgets'] += 1
            elif isinstance(w, tk.Label) and not isinstance(w, ttk.Label):
                _refresh_native_widget(w, colors)
                stats['native_widgets'] += 1
            # ★ v6.3.1: ttk.Label hardcoded foreground 수정
            elif isinstance(w, ttk.Label):
                _refresh_ttk_label(w, colors)
                stats['native_widgets'] += 1
        logger.info(f"[v6.2.3] Theme refresh: Treeview={stats['treeviews']}, Native={stats['native_widgets']}, dark={stats['is_dark']}")
    except Exception as e:
        logger.error(f"[v6.2.3] Theme refresh 실패: {e}")
    return stats


def debug_dump_widget_theme_status(app) -> str:
    """현재 화면의 모든 위젯 테마 상태를 덤프 (디버그용)."""
    lines = ["=" * 70, "SQM v6.2.3 Widget Theme Status Dump", "=" * 70]
    colors = get_theme_colors_from_style()
    lines.append(f"Theme colors: fg={colors['fg']}, bg={colors['bg']}, dark={colors['is_dark']}\n")
    tree_count = 0
    problems = []
    for w in _walk_widgets(app.root):
        if isinstance(w, ttk.Treeview):
            tree_count += 1
            sn = w.cget('style') or 'Treeview'
            tag_info = []
            for tag in ('odd', 'even', 'available', 'picked', 'reserved'):
                try:
                    cfg = w.tag_configure(tag)
                    if cfg:
                        tfg = cfg.get('foreground', '')
                        if isinstance(tfg, (list, tuple)):
                            tfg = tfg[0] if tfg else ''
                        tag_info.append(f"{tag}:fg={tfg}")
                except Exception as _te:
                    logging.getLogger(__name__).debug(f"[테마] 태그 정보 조회 실패: {_te}")
            lines.append(f"  [TV#{tree_count}] style={sn} | {', '.join(tag_info) if tag_info else 'no tags'}")
            for tag in ('odd', 'even'):
                try:
                    cfg = w.tag_configure(tag)
                    tfg = str(cfg.get('foreground', ''))
                    if colors['is_dark'] and tfg.lower() in ('black', '#000000', ''):
                        problems.append(f"⚠️ TV#{tree_count}({sn}): '{tag}' fg='{tfg}' on DARK")
                    elif not colors['is_dark'] and tfg.lower() in ('white', '#ffffff'):
                        problems.append(f"⚠️ TV#{tree_count}({sn}): '{tag}' fg='{tfg}' on LIGHT")
                except Exception as _te:
                    logging.getLogger(__name__).debug(f"[테마] 색상 검사 실패: {_te}")
    lines.append(f"\nTotal Treeviews: {tree_count}")
    if problems:
        lines.append("\n─── PROBLEMS ───")
        lines.extend(f"  {p}" for p in problems)
    else:
        lines.append("✅ No visibility problems detected")
    lines.append("=" * 70)
    return "\n".join(lines)


def apply_tc_theme_to_all(app_self) -> int:
    """v9.1: tc() 기반 테마 색상을 모든 tk.Widget에 일괄 적용.

    _change_theme() 에서 호출하면 테마 전환 시 하드코딩 색상이
    남아있는 tk.Widget도 tc() 팔레트 색상으로 갱신됩니다.
    """
    from gui_app_modular.utils.ui_constants import tc
    import tkinter as tk

    count = 0
    root = getattr(app_self, 'root', app_self)

    for w in _walk_widgets(root):
        try:
            wclass = w.winfo_class()
            # v8.4.1 [BUG-F]: ttk 위젯은 config(bg=...) 불가 → 스킵
            # ttk 위젯 클래스: TFrame, TLabel, TButton, TLabelframe, TEntry,
            # TCombobox, TCheckbutton, TRadiobutton, TScrollbar, Treeview 등
            if wclass.startswith('T') or wclass in ('Treeview', 'TCombobox'):
                continue
            if getattr(w, '_tc_skip', False):
                continue
            if wclass in ('Label', 'Message'):
                w.config(fg=tc('text_primary'), bg=tc('bg_primary'))
                count += 1
            elif wclass in ('Frame', 'Canvas'):
                w.config(bg=tc('bg_primary'))
                count += 1
            elif wclass == 'LabelFrame':
                w.config(fg=tc('text_primary'), bg=tc('bg_primary'))
                count += 1
            elif wclass == 'Entry':
                w.config(
                    fg=tc('text_primary'),
                    bg=tc('bg_entry'),
                    insertbackground=tc('text_primary'),
                    selectforeground=tc('select_fg'),
                    selectbackground=tc('select_bg'),
                )
                count += 1
            elif wclass == 'Text':
                w.config(
                    fg=tc('text_primary'),
                    bg=tc('bg_card'),
                    insertbackground=tc('text_primary'),
                    selectforeground=tc('select_fg'),
                    selectbackground=tc('select_bg'),
                )
                count += 1
            elif wclass == 'Listbox':
                w.config(
                    fg=tc('text_primary'),
                    bg=tc('bg_card'),
                    selectforeground=tc('select_fg'),
                    selectbackground=tc('select_bg'),
                )
                count += 1
            elif wclass in ('Button', 'Checkbutton', 'Radiobutton'):
                w.config(fg=tc('text_primary'), bg=tc('bg_secondary'),
                         activeforeground=tc('text_primary'),
                         activebackground=tc('bg_hover'))
                count += 1
            elif wclass == 'Scrollbar':
                w.config(bg=tc('bg_secondary'),
                         troughcolor=tc('bg_primary'))
                count += 1
        except Exception:
            logger.debug("[THEME-FAIL] file=theme_refresh.py reason=theme_apply_error")  # noqa

    logger.debug(f"[apply_tc_theme_to_all] {count}개 위젯 색상 갱신")
    return count
