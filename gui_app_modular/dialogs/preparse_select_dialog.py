# -*- coding: utf-8 -*-
"""
gui_app_modular/dialogs/preparse_select_dialog.py — SQM v8.0.6 PATCH
====================================================================
파싱 시작 전 사용자 선택 확인 창

흐름:
  [▶ 파싱 시작] 클릭
    → PreParseSelectDialog 팝업
       ① 선택된 파일 목록 + 문서유형 표시
       ② 템플릿 선택 (기존 InboundTemplateDialog 연동)
       ③ 멀티템플릿 후보 모드 ON/OFF 체크박스
       ④ [✅ 실행] 버튼 → 실제 파싱 시작
          [취소] 버튼 → 닫기 (파싱 안 함)

설계 원칙:
  - 기존 _start_parsing() 흐름 변경 없음
  - 이 다이얼로그가 OK 반환 시에만 파싱 진행
  - 취소 시 아무것도 안 함

[수정이력]
  2026-03-17  Ruby  SQM v8.0.6 신규 생성
"""
from __future__ import annotations

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 문서유형 표시 정보
_DOC_INFO = {
    "PACKING_LIST": ("📦", "Packing List",  "필수", "#27AE60"),
    "INVOICE":      ("📑", "Invoice / FA",  "필수", "#2980B9"),
    "BL":           ("🚢", "Bill of Lading","필수", "#8E44AD"),
    "DO":           ("📋", "Delivery Order","선택", "#E67E22"),
}


class PreParseSelectDialog:
    """
    파싱 전 사용자 확인 창.

    Parameters
    ----------
    parent          : 부모 Toplevel (onestop_inbound.dialog)
    file_paths      : { 'BL': '/path/to/bl.pdf', ... }
    engine          : InventoryEngine (템플릿 로드용)
    current_template: 현재 선택된 템플릿 dict (없으면 None)
    on_execute      : 실행 콜백 fn(template_data: dict, use_multi_template: bool)
    current_theme   : 테마 문자열
    """

    def __init__(
        self,
        parent: tk.Misc,
        file_paths: Dict[str, str],
        engine: Any,
        current_template: Optional[Dict[str, Any]] = None,
        on_execute: Optional[Callable[[Dict[str, Any], bool], None]] = None,
        current_theme: str = "darkly",
    ) -> None:
        self._parent = parent
        self._file_paths = file_paths
        self._engine = engine
        self._template_data: Dict[str, Any] = dict(current_template or {})
        self._on_execute = on_execute
        self._theme = current_theme
        # v8.7.0 [POLICY]: 멀티 템플릿 자동 비교 기본값 False (UI 옵션 제거됨, 사용자 입력 기반 정책)
        self._use_multi_template = tk.BooleanVar(value=False)
        self._dialog: Optional[tk.Toplevel] = None
        self._tpl_name_var = tk.StringVar(
            value=self._template_data.get("template_name", "(미선택)")
        )
        self._build()

    # ──────────────────────────────────────────────────────────────
    # 창 빌드
    # ──────────────────────────────────────────────────────────────
    def _build(self) -> None:
        dlg = create_themed_toplevel(self._parent)
        self._dialog = dlg
        dlg.title("파싱 준비 확인")
        dlg.resizable(True, True)
        dlg.minsize(480, 520)   # v9.0: 최소 크기 보장
        dlg.grab_set()

        # v9.0: 창 크기 저장/복원 (setup_dialog_geometry_persistence 사용)
        try:
            from gui_app_modular.utils.ui_constants import (
                setup_dialog_geometry_persistence, center_dialog
            ,
    tc
)
            setup_dialog_geometry_persistence(
                dlg, "preparse_select_dialog", self._parent, "medium"
            )
        except Exception:
            # fallback: 직접 geometry 설정
            try:
                px = self._parent.winfo_rootx() + self._parent.winfo_width() // 2
                py = self._parent.winfo_rooty() + self._parent.winfo_height() // 2
                dlg.geometry(f"540x580+{px - 270}+{py - 290}")
            except Exception:
                dlg.geometry("540x580")

        # ── 배경색 ──────────────────────────────────────────────
        try:
            from gui_app_modular.utils.ui_constants import ThemeColors
            _dark = ThemeColors.is_dark_theme(self._theme)
            bg = ThemeColors.get("bg_primary", _dark)
            fg = ThemeColors.get("text_primary", _dark)
            sec_bg = ThemeColors.get("bg_secondary", _dark)
        except Exception:
            bg, fg, sec_bg, _dark = "#FFFFFF", "#212529", "#F8F9FA", False

        dlg.configure(bg=bg)

        pad = {"padx": 16, "pady": 8}

        # ── 제목 (고정) ────────────────────────────────────────
        tk.Label(
            dlg,
            text="📋  파싱 준비 확인",
            font=("맑은 고딕", 15, "bold"),
            bg=bg, fg=fg,
        ).pack(fill=tk.X, **pad)

        ttk.Separator(dlg).pack(fill=tk.X, padx=16)

        # ── 스크롤 영역 (콘텐츠가 넘칠 때 스크롤) ────────────
        canvas_frame = tk.Frame(dlg, bg=bg)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        _canvas = tk.Canvas(canvas_frame, bg=bg, highlightthickness=0)
        _scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=_canvas.yview)
        _canvas.configure(yscrollcommand=_scrollbar.set)

        _scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        _canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 스크롤 내부 frame
        _inner = tk.Frame(_canvas, bg=bg)
        _canvas_window = _canvas.create_window((0, 0), window=_inner, anchor="nw")

        def _on_inner_configure(e):
            _canvas.configure(scrollregion=_canvas.bbox("all"))

        def _on_canvas_configure(e):
            _canvas.itemconfig(_canvas_window, width=e.width)

        _inner.bind("<Configure>", _on_inner_configure)
        _canvas.bind("<Configure>", _on_canvas_configure)

        # 마우스 휠 스크롤
        def _on_mousewheel(e):
            _canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        _canvas.bind_all("<MouseWheel>", _on_mousewheel)
        dlg.bind("<Destroy>", lambda e: _canvas.unbind_all("<MouseWheel>"))

        # 이후 섹션은 dlg 대신 _inner 에 붙임
        dlg = _inner  # 로컬 변수 재할당으로 기존 코드 그대로 사용

        # ── ① 선택된 파일 목록 ──────────────────────────────────
        sec1 = tk.Frame(dlg, bg=sec_bg, bd=1, relief="solid")
        sec1.pack(fill=tk.X, padx=16, pady=(10, 4))

        tk.Label(
            sec1,
            text="① 선택된 서류",
            font=("맑은 고딕", 12, "bold"),
            bg=sec_bg, fg=fg,
            anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(6, 2))

        doc_order = ["PACKING_LIST", "INVOICE", "BL", "DO"]
        for dt in doc_order:
            icon, name, req, color = _DOC_INFO.get(
                dt, ("📄", dt, "선택", "#555555")
            )
            row = tk.Frame(sec1, bg=sec_bg)
            row.pack(fill=tk.X, padx=10, pady=1)

            if dt in self._file_paths:
                fname = os.path.basename(self._file_paths[dt])
                status_text = f"✅ {fname}"
                status_color = "#27AE60"
            else:
                status_text = f"☐ 미선택 ({req})"
                status_color = "#E74C3C" if req == "필수" else "#95A5A6"

            tk.Label(
                row,
                text=f"{icon} {name}",
                font=("맑은 고딕", 11),
                bg=sec_bg, fg=fg,
                width=20, anchor="w",
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=status_text,
                font=("맑은 고딕", 11),
                bg=sec_bg, fg=status_color,
                anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 파일 0개 경고
        if not self._file_paths:
            tk.Label(
                sec1,
                text="⚠️  선택된 파일이 없습니다. 최소 Packing List 또는 BL이 필요합니다.",
                font=("맑은 고딕", 11),
                bg=sec_bg, fg=tc('danger'),
                anchor="w", wraplength=460,
            ).pack(fill=tk.X, padx=10, pady=(4, 6))

        # ── ② 템플릿 선택 ────────────────────────────────────────
        sec2 = tk.Frame(dlg, bg=sec_bg, bd=1, relief="solid")
        sec2.pack(fill=tk.X, padx=16, pady=4)

        hdr2 = tk.Frame(sec2, bg=sec_bg)
        hdr2.pack(fill=tk.X, padx=10, pady=(6, 4))

        tk.Label(
            hdr2,
            text="② 파싱 템플릿",
            font=("맑은 고딕", 12, "bold"),
            bg=sec_bg, fg=fg,
        ).pack(side=tk.LEFT)

        tk.Button(
            hdr2,
            text="🔄 변경",
            font=("맑은 고딕", 10),
            command=self._change_template,
            bg=tc('btn_report'), fg=tc('text_primary'),
            bd=0, padx=8, pady=2,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        tpl_row = tk.Frame(sec2, bg=sec_bg)
        tpl_row.pack(fill=tk.X, padx=10, pady=(0, 6))

        self._tpl_label = tk.Label(
            tpl_row,
            textvariable=self._tpl_name_var,
            font=("맑은 고딕", 11),
            bg=sec_bg,
            fg=tc('info') if self._template_data else "#E74C3C",
            anchor="w",
        )
        self._tpl_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        bag_kg = self._template_data.get("bag_weight_kg", "?")
        carrier = self._template_data.get("carrier_id", "?")
        self._tpl_detail_label = tk.Label(
            tpl_row,
            text=f"({carrier} / {bag_kg}kg/백)" if self._template_data else "",
            font=("맑은 고딕", 10),
            bg=sec_bg, fg=tc('text_muted'),
        )
        self._tpl_detail_label.pack(side=tk.LEFT)

        # v8.7.0 [POLICY]: "🔍 다중 템플릿 후보 자동 비교" 옵션 완전 제거.
        #   사용자 정책: "철저히 사용자 입력 기반" — AI 자동 선사 감지 경로 비활성화.
        #   기존 _use_multi_template BooleanVar는 시그니처 호환 위해 False로 고정 유지.
        self._use_multi_template.set(False)

        # ── 구분선 ───────────────────────────────────────────────
        ttk.Separator(dlg).pack(fill=tk.X, padx=16, pady=(8, 0))

        # ── 하단 버튼 (스크롤 밖 고정) ────────────────────────
        dlg = self._dialog   # 버튼은 실제 Toplevel에 붙임
        ttk.Separator(dlg).pack(fill=tk.X, padx=0, pady=0)
        btn_frame = tk.Frame(dlg, bg=bg)
        btn_frame.pack(fill=tk.X, padx=16, pady=12, side=tk.BOTTOM)

        tk.Button(
            btn_frame,
            text="취소",
            font=("맑은 고딕", 12),
            command=self._on_cancel,
            bg=tc('bg_secondary'), fg=tc('text_primary'),
            bd=0, padx=20, pady=8,
            cursor="hand2", width=8,
        ).pack(side=tk.RIGHT, padx=(8, 0))

        self._btn_execute = tk.Button(
            btn_frame,
            text="✅  실 행",
            font=("맑은 고딕", 13, "bold"),
            command=self._on_execute_click,
            bg=tc('btn_inbound'), fg=tc('text_primary'),
            bd=0, padx=24, pady=8,
            cursor="hand2", width=10,
        )
        self._btn_execute.pack(side=tk.RIGHT)

        # 파일 없으면 실행 버튼 비활성
        has_min_file = (
            "PACKING_LIST" in self._file_paths or "BL" in self._file_paths
        )
        if not has_min_file:
            self._btn_execute.config(state="disabled", bg=tc('bg_secondary'))

        # 템플릿 미선택 경고 라벨
        if not self._template_data:
            tk.Label(
                dlg,
                text="⚠️ 템플릿을 선택하지 않으면 기본값(500kg/백)으로 파싱됩니다.",
                font=("맑은 고딕", 10),
                bg=bg, fg=tc('warning'),
                anchor="w", wraplength=460,
            ).pack(fill=tk.X, padx=16, pady=(0, 4))

        dlg.protocol("WM_DELETE_WINDOW", self._on_cancel)
        dlg.focus_set()

    # ──────────────────────────────────────────────────────────────
    # 템플릿 변경
    # ──────────────────────────────────────────────────────────────
    def _change_template(self) -> None:
        """InboundTemplateDialog 호출 → 선택 시 자체 UI 갱신."""
        try:
            from gui_app_modular.dialogs.inbound_template_dialog import InboundTemplateDialog

            def _on_chosen(t: Dict[str, Any]) -> None:
                self._template_data = dict(t)
                name = t.get("template_name", "(미선택)")
                bag_kg = t.get("bag_weight_kg", "?")
                carrier = t.get("carrier_id", "?")
                self._tpl_name_var.set(name)
                self._tpl_label.config(fg=tc('info'))
                self._tpl_detail_label.config(
                    text=f"({carrier} / {bag_kg}kg/백)"
                )

            InboundTemplateDialog(
                self._dialog,
                self._engine,
                current_theme=self._theme,
                on_select_callback=_on_chosen,
            )
        except Exception as e:
            logger.error("[PreParseSelectDialog] 템플릿 변경 오류: %s", e)

    # ──────────────────────────────────────────────────────────────
    # 실행 / 취소
    # ──────────────────────────────────────────────────────────────
    def _on_execute_click(self) -> None:
        """실행 버튼 — 창 닫은 후 콜백 호출."""
        use_multi = self._use_multi_template.get()
        tpl = dict(self._template_data)
        logger.info(
            "[PreParseSelectDialog] 실행: template=%s multi=%s",
            tpl.get("template_name", "NONE"),
            use_multi,
        )
        # ★ 창을 먼저 닫고 콜백 실행 (grab_set 해제 후 파싱 시작)
        dlg = self._dialog
        self._dialog = None
        if dlg:
            try:
                dlg.grab_release()
            except Exception:
                logger.debug("[SUPPRESSED] exception in preparse_select_dialog.py")  # noqa
            dlg.destroy()
        if self._on_execute:
            try:
                self._on_execute(tpl, use_multi)
            except Exception as e:
                logger.error("[PreParseSelectDialog] 실행 콜백 오류: %s", e)

    def _on_cancel(self) -> None:
        """취소 — 파싱 없이 닫기."""
        if self._dialog:
            self._dialog.destroy()
            self._dialog = None
