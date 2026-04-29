# -*- coding: utf-8 -*-
"""
SQM v6.3.1 — theme_aware.py (테마 가시성 근본 해결)
=====================================================
★ 3가지 근본 원인을 한번에 수정:
  1. ttk.Label hardcoded foreground → 테마 반응형 색상 제공
  2. Toplevel 생성 시점 문제 → 다이얼로그 열 때 자동 테마 적용
  3. 하드코딩 색상 → 테마 안전 색상 API

사용법:
  from ..utils.theme_aware import ThemeAware

  # 1) 현재 테마에 맞는 색상 가져오기
  fg = ThemeAware.fg()          # 기본 텍스트
  bg = ThemeAware.bg()          # 기본 배경
  red = ThemeAware.accent('error')   # 에러 빨강 (다크/라이트 대응)
  gray = ThemeAware.accent('muted')  # 회색 텍스트

  # 2) Toplevel 생성 직후 테마 적용
  dlg = tk.Toplevel(root)
  ThemeAware.apply_to_toplevel(dlg)

  # 3) 기존 하드코딩 색상 안전 변환
  safe_red = ThemeAware.safe_color('#dc2626')  # 다크면 밝은 빨강 반환
"""
from gui_app_modular.utils.ui_constants import tc
import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


class ThemeAware:
    """테마 변경에 자동 대응하는 색상 유틸리티"""

    # ── 라이트/다크 각각 가독성 보장 색상표 ──
    _ACCENTS = {
        'light': {
            'error':    '#dc2626',  # 빨강
            'warning':  '#d97706',  # 주황
            'success':  '#059669',  # 초록
            'info':     '#2563eb',  # 파랑
            'muted':    '#6b7280',  # 회색
            'purple':   '#7c3aed',  # 보라
            'draft':    '#6366f1',
            'wait':     '#d97706',
            'final':    '#059669',
            'review':   '#ea580c',
            'hardstop': '#dc2626',
        },
        'dark': {
            'error':    '#f87171',  # 밝은 빨강
            'warning':  '#fbbf24',  # 밝은 주황
            'success':  '#34d399',  # 밝은 초록
            'info':     '#60a5fa',  # 밝은 파랑
            'muted':    '#9ca3af',  # 밝은 회색
            'purple':   '#a78bfa',  # 밝은 보라
            'draft':    '#818cf8',
            'wait':     '#fbbf24',
            'final':    '#34d399',
            'review':   '#fb923c',
            'hardstop': '#f87171',
        },
    }

    # 하드코딩 색상 → 다크 모드 안전 색상 매핑
    _DARK_SAFE_MAP = {
        '#dc2626': '#f87171', 'red': '#f87171', 'darkred': '#f87171',
        '#d97706': '#fbbf24', 'orange': '#fbbf24',
        '#059669': '#34d399', 'green': '#34d399', 'darkgreen': '#34d399',
        '#6366f1': '#818cf8', 'purple': '#a78bfa',
        '#ea580c': '#fb923c',
        '#2563eb': '#60a5fa', 'blue': '#60a5fa', 'darkblue': '#93c5fd',
        'gray': '#9ca3af', 'grey': '#9ca3af',
        '#000000': '#e5e7eb', 'black': '#e5e7eb',
    }

    @classmethod
    def is_dark(cls) -> bool:
        """현재 테마가 다크 모드인지 확인 (v8.6.4: _GLOBAL_IS_DARK 우선 참조)"""
        # 1순위: ui_constants 전역 상태 (set_global_theme에서 관리)
        try:
            from gui_app_modular.utils.ui_constants import _GLOBAL_IS_DARK
            return _GLOBAL_IS_DARK
        except ImportError:
            pass
        # 2순위: 실제 ttk 배경색으로 판단
        try:
            style = ttk.Style()
            bg = style.lookup('TFrame', 'background') or style.lookup('.', 'background')
            if not bg:
                return False
            return cls._is_dark_color(bg)
        except Exception:
            return False

    @classmethod
    def fg(cls) -> str:
        """현재 테마 기본 텍스트 색상"""
        try:
            style = ttk.Style()
            fg = style.lookup('TLabel', 'foreground') or style.lookup('.', 'foreground')
            return fg if fg else ('#e5e7eb' if cls.is_dark() else '#1f2937')
        except Exception:
            return '#e5e7eb' if cls.is_dark() else '#1f2937'

    @classmethod
    def bg(cls) -> str:
        """현재 테마 기본 배경 색상"""
        try:
            style = ttk.Style()
            bg = style.lookup('TFrame', 'background') or style.lookup('.', 'background')
            return bg if bg else ('#1e2a35' if cls.is_dark() else '#ffffff')
        except Exception:
            return '#1e2a35' if cls.is_dark() else '#ffffff'

    @classmethod
    def accent(cls, name: str) -> str:
        """테마 안전 강조색 반환

        Args:
            name: 'error', 'warning', 'success', 'info', 'muted', 'purple',
                  'draft', 'wait', 'final', 'review', 'hardstop'
        """
        palette = cls._ACCENTS['dark'] if cls.is_dark() else cls._ACCENTS['light']
        return palette.get(name, cls.fg())

    @classmethod
    def safe_color(cls, color: str) -> str:
        """하드코딩 색상 → 현재 테마에서 가시성 보장 색상 반환

        라이트 모드: 원본 그대로 반환
        다크 모드: 밝은 대체색 반환
        """
        if not cls.is_dark():
            return color
        c = color.strip().lower()
        return cls._DARK_SAFE_MAP.get(c, color)

    @classmethod
    def status_colors(cls) -> dict:
        """S1 워크플로우 상태 색상 (현재 테마 대응)"""
        return {
            'DRAFT': cls.accent('draft'),
            'WAIT_SCAN': cls.accent('wait'),
            'FINALIZED': cls.accent('final'),
            'REVIEW_REQUIRED': cls.accent('review'),
            'ERROR': cls.accent('hardstop'),
        }

    @classmethod
    def apply_to_toplevel(cls, dialog: tk.Toplevel) -> None:
        """★ Toplevel 다이얼로그에 현재 테마 색상 일괄 적용

        다이얼로그 생성 직후 호출하면 모든 자식 위젯이 테마 색상을 상속.
        기존 theme_refresh가 놓치는 '생성 시점 이후 Toplevel' 문제 해결.
        """
        is_dark = cls.is_dark()
        theme_fg = cls.fg()
        theme_bg = cls.bg()

        try:
            # 다이얼로그 자체 배경 (tk.Toplevel은 네이티브)
            dialog.configure(bg=theme_bg)
        except (tk.TclError, RuntimeError):
            logger.debug("[THEME-FAIL] file=exception in theme_aware.py reason=theme_apply_error")  # noqa

        # 생성 후 100ms 후 자식 위젯 스캔 (위젯 생성 완료 보장)
        def _fix_children():
            try:
                cls._walk_fix(dialog, theme_fg, theme_bg, is_dark)
            except Exception as e:
                logger.debug(f"[ThemeAware] toplevel fix 실패: {e}")

        dialog.after(100, _fix_children)

    @classmethod
    def apply_to_toplevel_now(cls, dialog: tk.Toplevel) -> None:
        """즉시 실행 버전 (모든 위젯 생성 완료 후 호출)"""
        is_dark = cls.is_dark()
        cls._walk_fix(dialog, cls.fg(), cls.bg(), is_dark)

    @classmethod
    def _walk_fix(cls, root_widget, theme_fg, theme_bg, is_dark):
        """위젯 트리 순회하며 색상 수정"""
        stack = [root_widget]
        visited = set()

        while stack:
            w = stack.pop()
            w_id = id(w)
            if w_id in visited:
                continue
            visited.add(w_id)

            try:
                # v8.6.4: _tc_skip=True 위젯은 테마 변경에서 보호
                if getattr(w, '_tc_skip', False):
                    children = w.winfo_children()
                    stack.extend(children)
                    continue
                # ★ 핵심 수정 #1: ttk.Label hardcoded foreground 처리
                if isinstance(w, ttk.Label):
                    try:
                        current_fg = str(w.cget('foreground'))
                        if current_fg and current_fg != theme_fg:
                            # 하드코딩된 색상이 현재 배경에서 안 보이면 교체
                            if cls._needs_fix(current_fg, theme_bg, is_dark):
                                safe = cls.safe_color(current_fg)
                                w.configure(foreground=safe)
                    except (tk.TclError, RuntimeError):
                        logger.debug("[THEME-FAIL] file=exception in theme_aware.py reason=theme_apply_error")  # noqa

                # tk.Text, tk.Listbox: 배경/전경 동기화
                elif isinstance(w, (tk.Text, tk.Listbox)):
                    try:
                        w.configure(fg=theme_fg, bg=theme_bg,
                                    insertbackground=theme_fg if isinstance(w, tk.Text) else theme_fg)
                        if isinstance(w, tk.Listbox):
                            w.configure(selectbackground=tc('select_bg'),
                                        selectforeground=tc('text_primary') if is_dark else '#1a5276')
                    except (tk.TclError, RuntimeError):
                        logger.debug("[THEME-FAIL] file=exception in theme_aware.py reason=theme_apply_error")  # noqa

                # tk.Label (not ttk): 대비 확인
                elif isinstance(w, tk.Label) and not isinstance(w, ttk.Label):
                    try:
                        current_fg = str(w.cget('fg'))
                        current_bg = str(w.cget('bg'))
                        if cls._low_contrast(current_fg, current_bg, w):
                            w.configure(fg=theme_fg, bg=theme_bg)
                    except (tk.TclError, RuntimeError):
                        logger.debug("[THEME-FAIL] file=exception in theme_aware.py reason=theme_apply_error")  # noqa

                # tk.Frame 배경
                elif isinstance(w, tk.Frame) and not isinstance(w, ttk.Frame):
                    try:
                        w.configure(bg=theme_bg)
                    except (tk.TclError, RuntimeError):
                        logger.debug("[THEME-FAIL] file=exception in theme_aware.py reason=theme_apply_error")  # noqa

                # 자식 탐색
                children = w.winfo_children()
                stack.extend(children)

            except (tk.TclError, RuntimeError) as _e:
                logger.debug(f"[SUPPRESSED] exception in theme_aware.py: {_e}")  # noqa

    @classmethod
    def _needs_fix(cls, fg_color: str, bg_color: str, is_dark: bool) -> bool:
        """색상이 배경 대비 가시성 부족한지 확인"""
        fg_b = cls._brightness(fg_color)
        bg_b = cls._brightness(bg_color)
        if fg_b is None or bg_b is None:
            # 파싱 불가 → 다크면 어두운색 의심, 라이트면 밝은색 의심
            c = fg_color.strip().lower()
            if is_dark:
                return c in ('black', '#000000', '#1a1a1a', '#333333',
                             'darkred', 'darkgreen', 'darkblue',
                             '#dc2626', '#059669', '#d97706', '#6366f1', '#ea580c')
            else:
                return c in ('white', '#ffffff', '#f0f0f0', '#e0e0e0')
        # 대비 비율 부족 (80 미만)
        return abs(fg_b - bg_b) < 80

    @classmethod
    def _low_contrast(cls, fg, bg, widget) -> bool:
        """위젯의 실제 렌더링 색상 기준 대비 확인"""
        try:
            r1, g1, b1 = widget.winfo_rgb(fg)
            r2, g2, b2 = widget.winfo_rgb(bg)
            b_fg = (r1/257 * 299 + g1/257 * 587 + b1/257 * 114) / 1000
            b_bg = (r2/257 * 299 + g2/257 * 587 + b2/257 * 114) / 1000
            return abs(b_fg - b_bg) < 80
        except Exception:
            return False

    @staticmethod
    def _brightness(color: str) -> float:
        """16진수 색상의 밝기 (0~255)"""
        try:
            c = color.strip().lstrip('#')
            if len(c) == 3:
                c = ''.join(ch * 2 for ch in c)
            if len(c) >= 6:
                r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                return (r * 299 + g * 587 + b * 114) / 1000
        except (ValueError, IndexError):
            logger.debug("[THEME-FAIL] file=exception in theme_aware.py reason=theme_apply_error")  # noqa
        return None

    @staticmethod
    def _is_dark_color(color: str) -> bool:
        c = color.strip().lstrip('#')
        if len(c) == 3:
            c = ''.join(ch * 2 for ch in c)
        try:
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            return (r * 299 + g * 587 + b * 114) / 1000 < 128
        except (ValueError, IndexError):
            return False
