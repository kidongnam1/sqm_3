# -*- coding: utf-8 -*-
from __future__ import annotations
"""
SQM v8.0.6 patch — 사전 문서확인 + 첫 파싱 라인 검수 다이얼로그
================================================================
목적
- 빠른 PDF(폴더) / 피킹리스트 파싱 전에 사용자 검수 단계 추가
- 문서유형(BL/PL/FA/DO/OTHER/EXCLUDE) 확인
- 첫 파싱 라인(대표 레코드) 표시 및 직접 수정
- AI 자연어 수정 요청 텍스트를 구조화된 명령으로 전달할 준비값 생성

주의
- 이 파일은 '드롭인 패치' 성격의 신규 모듈입니다.
- 기존 화면/엔진과 연결은 docs/INTEGRATION_GUIDE.md 기준으로 반영하십시오.
"""
from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc

from dataclasses import dataclass, field
from typing import Any
import copy
import json
import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

DOC_TYPES = ("BL", "PL", "FA", "DO", "OTHER", "EXCLUDE")
FIELD_TYPES = ("string", "int", "float", "date", "enum", "unknown")


@dataclass
class PreviewField:
    key: str
    label: str
    value: Any = ""
    field_type: str = "string"
    required: bool = False
    allowed_values: list[str] = field(default_factory=list)
    status: str = "대기"
    message: str = ""


@dataclass
class ReviewItem:
    file_path: str
    file_name: str
    auto_doc_type: str = "OTHER"
    user_doc_type: str = "OTHER"
    detect_reason: str = ""
    preview_fields: list[PreviewField] = field(default_factory=list)
    preview_status: str = "대기"
    excluded: bool = False
    ai_instruction: str = ""
    ai_last_suggestion: dict[str, Any] | None = None


class PreParseReviewDialog:
    def __init__(self, parent: tk.Misc, items: list[ReviewItem], title: str = "문서 사전확인 / 1행 검수"):
        self.parent = parent
        self.items = copy.deepcopy(items)
        self.title = title
        self.result: list[ReviewItem] | None = None
        self._row_vars: list[dict[str, Any]] = []
        self.dialog = create_themed_toplevel(parent)
        self.dialog.title(title)
        try:
            from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence as _sgp
            _sgp(self.dialog, "preparse_review_dialog", None, "large")
        except Exception as e:
            logger.warning(f'[UI] preparse_review_dialog: {e}')
        self.dialog.geometry("1320x760")
        self.dialog.resizable(True, True)  # v9.0: 크기 조절 허용
        self.dialog.minsize(660, 380)  # v9.0: 최소 크기
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self._build_ui()
        self._load_left_table()
        if self.items:
            self.tree.selection_set(self.tree.get_children()[0])
            self._on_select_item(None)

    def show(self) -> list[ReviewItem] | None:
        self.dialog.wait_window()
        return self.result

    def _build_ui(self) -> None:
        root = ttk.Frame(self.dialog, padding=10)
        root.pack(fill="both", expand=True)

        title_frm = ttk.Frame(root)
        title_frm.pack(fill="x", pady=(0, 8))
        ttk.Label(title_frm, text="사전 문서확인 + 첫 파싱 라인 검수", font=("맑은 고딕", 12, "bold")).pack(side="left")
        ttk.Label(title_frm, text="자동판정은 참고용, 사용자확정이 최종 기준", foreground=tc('text_muted')).pack(side="right")

        paned = ttk.Panedwindow(root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, padding=6)
        right = ttk.Frame(paned, padding=6)
        paned.add(left, weight=1)
        paned.add(right, weight=2)

        self.tree = ttk.Treeview(left, columns=("file", "auto", "user", "status"), show="headings", height=24)
        for col, text, width in [
            ("file", "파일명", 310),
            ("auto", "자동판정", 80),
            ("user", "사용자확정", 90),
            ("status", "프리뷰상태", 90),
        ]:
            self.tree.heading(col, text=text, anchor='center')
            self.tree.column(col, width=width, anchor="center" if col != "file" else "w")
        self.tree.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)

        info_frm = ttk.LabelFrame(right, text="선택 파일", padding=8)
        info_frm.pack(fill="x", pady=(0, 8))
        self.lbl_file = ttk.Label(info_frm, text="파일명: -")
        self.lbl_file.grid(row=0, column=0, sticky="w")
        self.lbl_reason = ttk.Label(info_frm, text="자동판정 근거: -")
        self.lbl_reason.grid(row=1, column=0, sticky="w", pady=(4, 0))

        type_frm = ttk.Frame(info_frm)
        type_frm.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))
        ttk.Label(type_frm, text="문서유형").pack(side="left", padx=(0, 6))
        self.cmb_doc_type = ttk.Combobox(type_frm, values=DOC_TYPES, state="readonly", width=12)
        self.cmb_doc_type.pack(side="left")
        self.cmb_doc_type.bind("<<ComboboxSelected>>", self._on_doc_type_change)

        fields_frm = ttk.LabelFrame(right, text="첫 파싱 라인 / 대표 레코드", padding=8)
        fields_frm.pack(fill="both", expand=True)

        canvas = tk.Canvas(fields_frm, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        scb = ttk.Scrollbar(fields_frm, orient="vertical", command=canvas.yview)
        scb.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scb.set)
        self.fields_host = ttk.Frame(canvas)
        self.fields_host.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.fields_host, anchor="nw")

        ai_frm = ttk.LabelFrame(right, text="AI 자연어 수정", padding=8)
        ai_frm.pack(fill="x", pady=(8, 0))
        ttk.Label(ai_frm, text="예: '세 번째 필드는 수량이 아니라 LOCATION이고, 단위는 KG로 바꿔'").pack(anchor="w")
        self.txt_ai = tk.Text(ai_frm, height=4)
        self.txt_ai.pack(fill="x", pady=(6, 6))
        btn_ai = ttk.Frame(ai_frm)
        btn_ai.pack(fill="x")
        ttk.Button(btn_ai, text="AI 요청 JSON 생성", command=self._generate_ai_payload).pack(side="left")
        ttk.Button(btn_ai, text="현재 값 검증", command=self._validate_current_fields).pack(side="left", padx=6)
        self.lbl_ai_info = ttk.Label(btn_ai, text="")
        self.lbl_ai_info.pack(side="left", padx=10)

        self.txt_ai_payload = tk.Text(ai_frm, height=8)
        self.txt_ai_payload.pack(fill="both", expand=False, pady=(6, 0))

        bottom = ttk.Frame(root)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="확정 후 진행", command=self._on_confirm).pack(side="right")
        ttk.Button(bottom, text="취소", command=self._on_cancel).pack(side="right", padx=6)

    def _load_left_table(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        for idx, item in enumerate(self.items):
            self.tree.insert("", "end", iid=str(idx), values=(item.file_name, item.auto_doc_type, item.user_doc_type, item.preview_status))

    def _current_index(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        # P1-5: 바운드 검사 주가 — 비동기 삭제 시 IndexError 방지
        if idx < 0 or idx >= len(self.items):
            logger.warning(
                f"[PreparseReview] tree index {idx} 범위 초과 "
                f"(items={len(self.items)}) — None 반환"
            )
            return None
        return idx

    def _on_select_item(self, _event) -> None:
        idx = self._current_index()
        if idx is None:
            return
        item = self.items[idx]
        self.lbl_file.configure(text=f"파일명: {item.file_name}")
        self.lbl_reason.configure(text=f"자동판정 근거: {item.detect_reason or '-'}")
        self.cmb_doc_type.set(item.user_doc_type or item.auto_doc_type or "OTHER")
        self.txt_ai.delete("1.0", "end")
        self.txt_ai.insert("1.0", item.ai_instruction or "")
        self.txt_ai_payload.delete("1.0", "end")
        if item.ai_last_suggestion:
            self.txt_ai_payload.insert("1.0", json.dumps(item.ai_last_suggestion, ensure_ascii=False, indent=2))
        self._render_fields(item)

    def _render_fields(self, item: ReviewItem) -> None:
        for child in self.fields_host.winfo_children():
            child.destroy()
        self._row_vars.clear()

        headers = ["필드", "값", "타입", "필수", "상태", "메시지"]
        for col, header in enumerate(headers):
            ttk.Label(self.fields_host, text=header, font=("맑은 고딕", 9, "bold")).grid(row=0, column=col, sticky="w", padx=4, pady=4)

        for r, field in enumerate(item.preview_fields, start=1):
            ttk.Label(self.fields_host, text=field.label).grid(row=r, column=0, sticky="w", padx=4, pady=3)
            var_val = tk.StringVar(value="" if field.value is None else str(field.value))
            ent_val = ttk.Entry(self.fields_host, textvariable=var_val, width=34)
            ent_val.grid(row=r, column=1, sticky="ew", padx=4, pady=3)

            var_type = tk.StringVar(value=field.field_type or "string")
            cmb_type = ttk.Combobox(self.fields_host, textvariable=var_type, values=FIELD_TYPES, state="readonly", width=10)
            cmb_type.grid(row=r, column=2, sticky="w", padx=4, pady=3)

            var_required = tk.BooleanVar(value=field.required)
            chk = ttk.Checkbutton(self.fields_host, variable=var_required)
            chk.grid(row=r, column=3, sticky="w", padx=4, pady=3)

            var_status = tk.StringVar(value=field.status or "대기")
            ttk.Label(self.fields_host, textvariable=var_status).grid(row=r, column=4, sticky="w", padx=4, pady=3)

            var_msg = tk.StringVar(value=field.message or "")
            ttk.Label(self.fields_host, textvariable=var_msg, foreground=tc('text_muted')).grid(row=r, column=5, sticky="w", padx=4, pady=3)

            self._row_vars.append({
                "field": field,
                "value": var_val,
                "field_type": var_type,
                "required": var_required,
                "status": var_status,
                "message": var_msg,
            })

        self.fields_host.columnconfigure(1, weight=1)

    def _on_doc_type_change(self, _event=None) -> None:
        idx = self._current_index()
        if idx is None:
            return
        self.items[idx].user_doc_type = self.cmb_doc_type.get().strip() or "OTHER"
        if self.items[idx].user_doc_type == "EXCLUDE":
            self.items[idx].excluded = True
            self.items[idx].preview_status = "제외"
        else:
            self.items[idx].excluded = False
        self._load_left_table()
        self.tree.selection_set(str(idx))

    def _validate_current_fields(self) -> None:
        idx = self._current_index()
        if idx is None:
            return
        item = self.items[idx]
        overall_ok = True
        for row in self._row_vars:
            field = row["field"]
            raw = row["value"].get().strip()
            ftype = row["field_type"].get().strip() or "string"
            required = bool(row["required"].get())
            status, message = self._validate_value(raw, ftype, required, field.allowed_values)
            row["status"].set(status)
            row["message"].set(message)
            field.value = raw
            field.field_type = ftype
            field.required = required
            field.status = status
            field.message = message
            if status == "오류":
                overall_ok = False
        item.preview_status = "검증완료" if overall_ok else "검토필요"
        self._load_left_table()
        self.tree.selection_set(str(idx))

    def _validate_value(self, raw: str, ftype: str, required: bool, allowed_values: list[str]) -> tuple[str, str]:
        if required and not raw:
            return "오류", "필수값 비어 있음"
        if not raw:
            return "정상", ""
        try:
            if ftype == "int":
                int(float(raw))
            elif ftype == "float":
                float(raw.replace(",", ""))
            elif ftype == "enum" and allowed_values:
                if raw not in allowed_values:
                    return "오류", f"허용값 아님: {allowed_values}"
            elif ftype == "date":
                parts = raw.replace("/", "-").replace(".", "-").split("-")
                if len(parts) != 3:
                    return "오류", "날짜 형식 아님"
        except Exception:
            return "오류", f"{ftype} 형식 변환 실패"
        return "정상", ""

    def _generate_ai_payload(self) -> None:
        idx = self._current_index()
        if idx is None:
            return
        item = self.items[idx]
        item.ai_instruction = self.txt_ai.get("1.0", "end").strip()
        payload = {
            "mode": "preview_field_edit",
            "file_name": item.file_name,
            "doc_type": item.user_doc_type,
            "instruction": item.ai_instruction,
            "fields": [
                {
                    "key": row["field"].key,
                    "label": row["field"].label,
                    "value": row["value"].get().strip(),
                    "field_type": row["field_type"].get().strip(),
                    "required": bool(row["required"].get()),
                    "allowed_values": row["field"].allowed_values,
                }
                for row in self._row_vars
            ],
            "return_schema": {
                "field_updates": {"FIELD_KEY": "NEW_VALUE"},
                "field_type_updates": {"FIELD_KEY": "float"},
                "remap_hints": [{"from": "column_3", "to": "LOCATION"}],
                "notes": ["brief note"],
            },
        }
        item.ai_last_suggestion = payload
        self.txt_ai_payload.delete("1.0", "end")
        self.txt_ai_payload.insert("1.0", json.dumps(payload, ensure_ascii=False, indent=2))
        self.lbl_ai_info.configure(text="AI API 호출용 JSON 초안 생성 완료")

    def _on_confirm(self) -> None:
        self._validate_current_fields()
        self.result = self.items
        self.dialog.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.dialog.destroy()
