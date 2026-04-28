# -*- coding: utf-8 -*-
"""전역 자동 툴팁 유틸 (메뉴/팝업 공통)."""

import logging
import re
import tkinter as tk
from tkinter import ttk

from gui_app_modular.utils.ui_constants import tc

from .menu_tab_tooltips import tooltip_for_menu_label
from .ui_constants import apply_tooltip

logger = logging.getLogger(__name__)


def _clean_label(label: str) -> str:
    text = str(label or "")
    text = re.sub(r"[\u2460-\u2473]", "", text)  # ①② 같은 번호 문자 제거
    text = re.sub(r"[^\w\s가-힣/+().,\-]", " ", text)  # 이모지/특수기호 제거
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fit_60(text: str) -> str:
    t = (text or "").strip()
    if len(t) <= 60:
        return t
    return t[:57].rstrip() + "..."


def build_tooltip_text(label: str, widget_class: str = "") -> str:
    """라벨/위젯명을 바탕으로 60자 이내 툴팁 생성."""
    reg = tooltip_for_menu_label(label)
    if reg:
        return _fit_60(reg)
    s = _clean_label(label).lower()
    if "pdf" in s and ("입고" in s or "스캔" in s):
        return _fit_60("PDF 서류를 분석해 LOT/SAP/BL을 채웁니다. 예: PL+Invoice+BL 선택 후 파싱→미리보기 확인.")
    if "db 업로드" in s:
        return _fit_60("미리보기 데이터를 DB에 저장합니다. 예: 오류 행 수정 후 DB 업로드를 눌러 재고 리스트로 반영.")
    if "엑셀" in s or "excel" in s:
        return _fit_60("현재 결과를 엑셀로 내보냅니다. 예: 필터 적용 상태로 내보내기 후 거래처 공유 파일로 사용.")
    if "파싱" in s:
        return _fit_60("선택 문서를 읽어 표 데이터를 생성합니다. 예: 파싱 시작→누락 경고 확인→미리보기에서 값 점검.")
    if "재고" in s:
        return _fit_60("재고 목록/통계를 조회합니다. 예: 필터를 선택해 AVAILABLE/PICKED/SOLD 상태별 수량을 비교.")
    if "출고" in s:
        return _fit_60("출고 흐름을 실행합니다. 예: 배정→스캔검증→확정 순서로 진행하고 오류 행은 먼저 정정.")
    if "백업" in s or "복원" in s:
        return _fit_60("DB 보호 작업입니다. 예: 작업 전 백업 생성 후 문제 시 복원으로 이전 상태를 즉시 되돌립니다.")
    if "도움말" in s or "설명서" in s:
        return _fit_60("사용 가이드를 엽니다. 예: 처음 사용자라면 단축키/업무 순서 문서를 먼저 확인하세요.")
    if "필터" in s:
        return _fit_60("조회 조건을 적용합니다. 예: SAP/BL/상태를 선택해 필요한 행만 남기고 업로드 정확도를 높입니다.")
    if "treeview" in widget_class.lower():
        return _fit_60("표 데이터를 선택/편집할 수 있습니다. 예: 더블클릭 편집, Ctrl+C/V 붙여넣기로 대량 수정.")
    if "combobox" in widget_class.lower():
        return _fit_60("목록에서 값을 선택합니다. 예: LOT를 고른 뒤 실제수량(kg)을 입력해 검증 상태를 업데이트.")
    if "entry" in widget_class.lower() or "text" in widget_class.lower():
        return _fit_60("값을 입력하는 칸입니다. 예: YYYY-MM-DD 형식 날짜 또는 숫자만 입력 후 적용 버튼 클릭.")
    base = _clean_label(label) or "이 항목"
    return _fit_60(f"{base} 기능을 실행합니다. 예: 클릭 후 표시되는 안내 순서대로 확인·저장하면 됩니다.")


def apply_auto_tooltip(widget, label: str = "") -> None:
    """위젯에 자동 생성 툴팁 적용."""
    if getattr(widget, "_auto_tooltip_bound", False):
        return
    cls = widget.winfo_class() if hasattr(widget, "winfo_class") else ""
    text = build_tooltip_text(label or getattr(widget, "cget", lambda *_: "")("text"), cls)
    apply_tooltip(widget, text)
    widget._auto_tooltip_bound = True


def apply_auto_tooltips_in(container) -> None:
    """컨테이너 하위의 인터랙티브 위젯에 자동 툴팁 적용."""
    if not container or not hasattr(container, "winfo_children"):
        return
    target_types = (
        tk.Button, ttk.Button, tk.Menubutton, ttk.Menubutton,
        tk.Entry, ttk.Entry, ttk.Combobox, ttk.Checkbutton,
        ttk.Radiobutton, ttk.Treeview, tk.Text, tk.Listbox,
        tk.Label, ttk.Label,
    )
    stack = [container]
    while stack:
        w = stack.pop()
        try:
            children = w.winfo_children()
            stack.extend(children)
            if isinstance(w, target_types):
                label = ""
                try:
                    label = w.cget("text")
                except Exception:
                    label = ""
                apply_auto_tooltip(w, label)
        except Exception:
            continue


class MenuTooltipManager:
    """tk.Menu 항목 hover 시 툴팁 표시 (v8.7.0: 11시 방향 멀리 + 3초 자동숨김 + 클릭숨김)."""

    def __init__(self, root):
        self.root = root
        self._tip = None
        self._menus = set()
        self._hide_id = None

    def attach(self, menu: tk.Menu) -> None:
        if not menu or menu in self._menus:
            return
        self._menus.add(menu)
        menu.bind("<<MenuSelect>>", lambda e, m=menu: self._on_select(m), add="+")
        menu.bind("<Unmap>", lambda _e: self._hide(), add="+")
        menu.bind("<Destroy>", lambda _e: self._hide(), add="+")
        # v8.7.0: 메뉴 클릭 시 툴팁 숨김
        menu.bind("<Button-1>", lambda _e: self._hide(), add="+")
        menu.bind("<Button-3>", lambda _e: self._hide(), add="+")

    def _on_select(self, menu: tk.Menu) -> None:
        try:
            idx = menu.index("active")
            if idx is None:
                self._hide()
                return
            label = str(menu.entrycget(idx, "label") or "").strip()
            if not label:
                self._hide()
                return
            text = build_tooltip_text(label, "Menu")
            self._show(text)
        except Exception:
            self._hide()

    def _show(self, text: str) -> None:
        self._hide()
        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        lbl = tk.Label(
            tip,
            text=_fit_60(text),
            justify="left",
            bg=tc('bg_secondary'),
            fg=tc('text_primary'),
            relief="solid",
            borderwidth=1,
            padx=10,
            pady=6,
            font=("맑은 고딕", 9),
            wraplength=520,  # 가로로 길게
        )
        lbl.pack()

        # v8.7.0 [UX]: 11시 방향 멀리 — 포인터에서 왼쪽 30px, 위 20px 떨어짐
        try:
            tip.update_idletasks()
            tw = tip.winfo_reqwidth()
            th = tip.winfo_reqheight()
            px = self.root.winfo_pointerx()
            py = self.root.winfo_pointery()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = px - tw - 30
            y = py - th - 20
            if y < 0:
                y = py + 18
            if x < 0:
                x = 2
            if x + tw > sw:
                x = sw - tw - 2
            if y + th > sh:
                y = sh - th - 2
            tip.wm_geometry(f"+{x}+{y}")
        except Exception as e:
            logger.debug("MenuTooltip position: %s", e)

        self._tip = tip
        # v8.7.0 [UX]: 자동 숨김 3초 (기존 5초)
        try:
            self._hide_id = self.root.after(3000, self._hide)
        except Exception as e:
            logger.debug("MenuTooltip auto-hide: %s", e)

    def _hide(self) -> None:
        if self._hide_id:
            try:
                self.root.after_cancel(self._hide_id)
            except Exception as e:
                logger.debug("MenuTooltip hide_cancel: %s", e)
            self._hide_id = None
        if self._tip and self._tip.winfo_exists():
            self._tip.destroy()
        self._tip = None


def install_global_auto_tooltips(root) -> None:
    """메인/팝업 창 생성 시 자동 툴팁 부착."""
    if not root or getattr(root, "_auto_tooltip_installed", False):
        return
    root._auto_tooltip_installed = True

    menu_mgr = MenuTooltipManager(root)
    root._menu_tooltip_manager = menu_mgr

    # 생성되는 모든 Menu에 자동 hover 툴팁 부착
    if not getattr(tk.Menu, "_auto_tooltip_patched", False):
        _orig_menu_init = tk.Menu.__init__

        def _patched_menu_init(self_menu, *args, **kwargs):
            """tk.Menu 생성 시 자동으로 MenuTooltipManager에 등록."""
            _orig_menu_init(self_menu, *args, **kwargs)
            try:
                menu_mgr.attach(self_menu)
            except Exception as e:
                logger.debug("_patched_menu_init attach error: %s", e)


        tk.Menu.__init__ = _patched_menu_init
        tk.Menu._auto_tooltip_patched = True

    def _walk_attach_menus(widget):
        """앱 기동 시 이미 생성된 tk.Menu에도 <<MenuSelect>> 툴팁 부착."""
        stack = [widget]
        while stack:
            w = stack.pop()
            try:
                children = w.winfo_children()
            except (tk.TclError, RuntimeError, AttributeError) as e:
                logger.debug("winfo_children: %s", e)
                continue
            stack.extend(children)
            if isinstance(w, tk.Menu):
                try:
                    menu_mgr.attach(w)
                except Exception as e:
                    logger.debug("menu_mgr.attach: %s", e)

    def _scan(widget):
        try:
            apply_auto_tooltips_in(widget)
            try:
                if isinstance(widget, tk.Menu):
                    menu_mgr.attach(widget)
            except Exception as e:
                logger.debug("attach Menu in scan: %s", e)
        except Exception as e:
            logger.debug("apply_auto_tooltips_in: %s", e)

    root.bind_all("<Map>", lambda e: root.after(100, lambda: _scan(e.widget)), add="+")
    root.bind_all("<Enter>", lambda e: root.after(0, lambda: _scan(e.widget)), add="+")
    root.after(200, lambda: _walk_attach_menus(root))
    root.after(400, lambda: _walk_attach_menus(root))
    root.after(400, lambda: _scan(root))
