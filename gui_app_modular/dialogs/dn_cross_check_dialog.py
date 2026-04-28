# -*- coding: utf-8 -*-
"""
SQM v8.6.4 — DN 교차검증 다이얼로그 (dn_cross_check_dialog.py)

Author: Ruby
Version: 1.0.0 (2026-03-29)

고객 Sales Order / DN Excel 파일을 업로드하고
SQM DB와 교차검증 결과를 표시하는 다이얼로그.
"""
import logging
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional

logger = logging.getLogger(__name__)

BG    = "#0f172a"
CARD  = "#1e293b"
FG    = "#e2e8f0"
ACCENT= "#22d3ee"
OK_C  = "#4ade80"
WARN_C= "#fbbf24"
ERR_C = "#f87171"
BORDER= "#334155"


class DNCheckDialog:
    """고객 DN vs SQM DB 교차검증 다이얼로그."""

    def __init__(self, parent, db_adapter):
        self.parent     = parent
        self.db         = db_adapter
        self.excel_path = tk.StringVar()
        self._result    = None
        self._build()

    def _build(self):
        dlg = tk.Toplevel(self.parent)
        dlg.title("DN 교차검증 — 고객 Sales Order vs SQM DB")
        dlg.configure(bg=BG)
        dlg.resizable(True, True)
        dlg.geometry("720x560")
        self.dlg = dlg

        # ── 헤더 ──
        hdr = tk.Frame(dlg, bg=BG, pady=12, padx=20)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔍 DN 교차검증",
                 font=("Segoe UI", 14, "bold"),
                 bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(hdr, text="고객 Sales Order / DN Excel vs SQM 출고 DB",
                 font=("Segoe UI", 10), bg=BG, fg="#94a3b8").pack(side="left", padx=12)

        # ── 파일 선택 ──
        file_frame = tk.Frame(dlg, bg=CARD, padx=16, pady=12,
                              highlightbackground=BORDER, highlightthickness=1)
        file_frame.pack(fill="x", padx=20, pady=(0,8))

        tk.Label(file_frame, text="고객 DN / Sales Order 파일:",
                 bg=CARD, fg=FG, font=("Segoe UI", 10)).pack(anchor="w")

        row = tk.Frame(file_frame, bg=CARD)
        row.pack(fill="x", pady=(4,0))

        ttk.Entry(row, textvariable=self.excel_path, width=55
                  ).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="📂 파일 선택",
                   command=self._select_file).pack(side="left", padx=(6,0))
        ttk.Button(row, text="🔍 검증 실행",
                   command=self._run_check).pack(side="left", padx=(4,0))

        # ── 결과 영역 ──
        result_frame = tk.Frame(dlg, bg=BG, padx=20)
        result_frame.pack(fill="both", expand=True, pady=(0,8))

        tk.Label(result_frame, text="검증 결과",
                 bg=BG, fg="#94a3b8", font=("Segoe UI", 9)).pack(anchor="w")

        # 트리뷰
        cols = ("level", "field", "dn_value", "sqm_value", "message")
        tree = ttk.Treeview(result_frame, columns=cols, show="headings",
                            height=14, selectmode="browse")
        self.tree = tree

        headers = {"level": ("구분",50), "field": ("필드",80),
                   "dn_value": ("고객 DN",120), "sqm_value": ("SQM DB",120),
                   "message": ("메시지",300)}
        for c, (h, w) in headers.items():
            tree.heading(c, text=h)
            tree.column(c, width=w, minwidth=40)

        scroll_y = ttk.Scrollbar(result_frame, orient="vertical",
                                  command=tree.yview)
        tree.configure(yscrollcommand=scroll_y.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        # 태그 색상
        tree.tag_configure("OK",    foreground=OK_C)
        tree.tag_configure("WARN",  foreground=WARN_C)
        tree.tag_configure("ERROR", foreground=ERR_C)

        # ── 요약 + 버튼 ──
        bottom = tk.Frame(dlg, bg=BG, padx=20, pady=10)
        bottom.pack(fill="x")

        self.summary_var = tk.StringVar(value="파일을 선택하고 검증을 실행하세요.")
        tk.Label(bottom, textvariable=self.summary_var,
                 bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left")

        ttk.Button(bottom, text="✕ 닫기",
                   command=dlg.destroy).pack(side="right")
        ttk.Button(bottom, text="📋 결과 복사",
                   command=self._copy_result).pack(side="right", padx=(0,6))

        # 중앙 배치
        dlg.update_idletasks()
        w, h = 720, 560
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _select_file(self):
        path = filedialog.askopenfilename(
            parent=self.dlg,
            title="고객 DN / Sales Order Excel 선택",
            filetypes=[("Excel", "*.xlsx *.xls"), ("전체", "*.*")]
        )
        if path:
            self.excel_path.set(path)

    def _run_check(self):
        path = self.excel_path.get().strip()
        if not path:
            self.summary_var.set("⚠️ 파일을 먼저 선택하세요.")
            return

        # 트리뷰 초기화
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.summary_var.set("검증 중...")
        self.dlg.update()

        try:
            from engine_modules.dn_cross_check_engine import (
                parse_dn_excel, cross_check_dn
            )
            dn_data = parse_dn_excel(path)
            if not dn_data:
                self.summary_var.set("❌ Excel 파일 파싱 실패 — 형식을 확인하세요.")
                return

            so_no = dn_data.get("sales_order_no", "")
            result = cross_check_dn(self.db, so_no, dn_data)
            self._result = result

            # 결과 표시
            for item in result.items:
                tag = item.level
                self.tree.insert("", "end", values=(
                    {"OK":"✅ OK","WARN":"⚠️ 경고","ERROR":"❌ 오류"}.get(item.level, item.level),
                    item.field,
                    item.dn_value[:40],
                    item.sqm_value[:40],
                    item.message,
                ), tags=(tag,))

            self.summary_var.set(result.summary)

        except Exception as e:
            self.summary_var.set(f"❌ 오류: {e}")
            logger.warning(f"[DN검증] 실행 오류: {e}")

    def _copy_result(self):
        if not self._result:
            return
        lines = [self._result.summary, ""]
        for item in self._result.items:
            lines.append(str(item))
        text = "\n".join(lines)
        try:
            self.dlg.clipboard_clear()
            self.dlg.clipboard_append(text)
        except Exception as _e:
            logger.debug(f"[DNCheck] 클립보드 복사 실패: {_e}")


def show_dn_check_dialog(parent, db_adapter) -> None:
    """DN 교차검증 다이얼로그 표시."""
    dlg = DNCheckDialog(parent, db_adapter)
    dlg.dlg.grab_set()
    parent.wait_window(dlg.dlg)
