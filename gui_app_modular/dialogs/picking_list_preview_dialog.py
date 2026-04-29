"""
SQM v6.0 - Picking List PDF 파싱 결과 미리보기 다이얼로그
=========================================================

파일 선택 → 파싱 후 결과(헤더 + 아이템 목록 + 에러)를 표시.
DB 반영 버튼은 엔진 연동 시 사용.
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any, Optional

from ..utils.ui_constants import (
    setup_dialog_geometry_persistence,
)


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _doc_val(doc: Any, key: str, attr: str) -> str:
    """doc이 dict면 key, 아니면 getattr(attr)."""
    if isinstance(doc, dict):
        return _safe_str(doc.get(key, ""))
    return _safe_str(getattr(doc, attr, None))


class PickingListPreviewDialog:
    """
    Picking List PDF 파싱 결과를 보여주는 다이얼로그.
    doc: dict (features.parsers 형식) 또는 PickingDoc (parsers 형식)
    """

    def __init__(
        self,
        parent: tk.Misc,
        doc: Any,
        pdf_path: str,
        on_apply_clicked: Optional[Callable[[Any, str], None]] = None,
    ):
        self.parent = parent
        self.doc = doc
        self.pdf_path = pdf_path
        self.on_apply_clicked = on_apply_clicked

        self.dialog = create_themed_toplevel(parent)
        self.dialog.title("📋 Picking List 파싱 결과")
        setup_dialog_geometry_persistence(self.dialog, "picking_preview", parent, "large")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._build_ui()

    def _build_ui(self) -> None:
        from ..utils.ui_constants import Spacing

        main = ttk.Frame(self.dialog, padding=Spacing.DIALOG_PADDING)
        main.pack(fill=tk.BOTH, expand=True)

        # ─── 요약 ───
        summary_frame = ttk.LabelFrame(main, text="요약", padding=Spacing.SMALL)
        summary_frame.pack(fill=tk.X, pady=(0, Spacing.SMALL))

        rows = [
            ("파일", self.pdf_path),
            ("Customer reference", _doc_val(self.doc, "customer", "customer_ref")),
            ("Sales order", _doc_val(self.doc, "sales_order_no", "sales_order")),
            ("Picking No", _doc_val(self.doc, "picking_no", "requisition_no")),
            ("Plan loading date", _doc_val(self.doc, "plan_loading_date", "plan_loading_date")),
            ("Creation date", _doc_val(self.doc, "creation_date", "creation_date")),
        ]
        for i, (label, value) in enumerate(rows):
            ttk.Label(summary_frame, text=f"{label}:", font=("", 9, "bold")).grid(
                row=i, column=0, sticky=tk.W, padx=(0, 8), pady=2
            )
            ttk.Label(summary_frame, text=value or "-").grid(
                row=i, column=1, sticky=tk.W, pady=2
            )

        # ─── 경고/에러 ───
        errors = (
            self.doc.get("warnings", []) if isinstance(self.doc, dict)
            else (getattr(self.doc, "errors", []) or [])
        )
        if errors:
            err_frame = ttk.LabelFrame(main, text="⚠️ 경고/오류", padding=Spacing.SMALL)
            err_frame.pack(fill=tk.X, pady=(0, Spacing.SMALL))
            for msg in errors[:10]:
                ttk.Label(err_frame, text=msg, foreground=tc('danger')).pack(anchor=tk.W)
            if len(errors) > 10:
                ttk.Label(
                    err_frame,
                    text=f"... 외 {len(errors) - 10}건",
                    foreground=tc('text_muted'),
                ).pack(anchor=tk.W)

        # ─── 아이템 테이블 ───
        items = (
            self.doc.get("items", []) if isinstance(self.doc, dict)
            else (getattr(self.doc, "items", []) or [])
        )
        table_frame = ttk.LabelFrame(main, text="품목 / Batch", padding=Spacing.SMALL)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, Spacing.SMALL))

        is_dict_format = items and isinstance(items[0], dict)
        if is_dict_format:
            columns = ("lot_no", "qty_kg", "unit", "is_sample", "storage")
            tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
            tree._enable_global_editable = True  # v8.6.4: 편집 활성화
            tree.heading("lot_no", text="LOT NO", anchor='center')
            tree.heading("qty_kg", text="Qty(Kg)", anchor='center')
            tree.heading("unit", text="단위", anchor='center')
            tree.heading("is_sample", text="샘플", anchor='center')
            tree.heading("storage", text="Storage location", anchor='center')
            tree.column("lot_no", width=120)
            tree.column("qty_kg", width=90)
            tree.column("unit", width=50)
            tree.column("is_sample", width=50)
            tree.column("storage", width=180)
            for it in items:
                tree.insert("", tk.END, values=(
                    _safe_str(it.get("lot_no", "")),
                    it.get("qty_kg", 0),
                    _safe_str(it.get("unit", "")),
                    "Y" if it.get("is_sample") else "",
                    _safe_str(it.get("storage_location", "")),
                ))
        else:
            columns = ("material", "description", "total_qty", "unit", "batches", "batch_detail")
            tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
            tree._enable_global_editable = True  # v8.6.4: 편집 활성화
            tree.heading("material", text="자재코드", anchor='center')
            tree.heading("description", text="설명", anchor='center')
            tree.heading("total_qty", text="총량", anchor='center')
            tree.heading("unit", text="단위", anchor='center')
            tree.heading("batches", text="Batch 수", anchor='center')
            tree.heading("batch_detail", text="Batch 요약", anchor='center')
            tree.column("material", width=100)
            tree.column("description", width=180)
            tree.column("total_qty", width=80)
            tree.column("unit", width=50)
            tree.column("batches", width=70)
            tree.column("batch_detail", width=220)
            for it in items:
                mat = _safe_str(getattr(it, "material_code", ""))
                desc = _safe_str(getattr(it, "description", ""))
                total = getattr(it, "total_qty", 0)
                unit = _safe_str(getattr(it, "total_unit", ""))
                batches = getattr(it, "batches", []) or []
                batch_summary = ""
                if batches:
                    parts = [f"{getattr(b, 'batch_no', '')} {getattr(b, 'qty', 0)}{getattr(b, 'unit', '')}" for b in batches[:5]]
                    batch_summary = ", ".join(parts)
                    if len(batches) > 5:
                        batch_summary += f" ...+{len(batches) - 5}"
                tree.insert("", tk.END, values=(mat, desc, total, unit, len(batches), batch_summary))

        scroll = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        scroll_x = tk.Scrollbar(table_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # v8.1.5: 합계 Footer (Treeview 컬럼 정렬)
        from ..utils.tree_enhancements import TreeviewTotalFooter
        if is_dict_format:
            _picking_footer = TreeviewTotalFooter(
                main, tree, ['qty_kg'],
                column_display_names={'qty_kg': 'Qty(Kg)'}
            )
        else:
            _picking_footer = TreeviewTotalFooter(
                main, tree, ['total_qty'],
                column_display_names={'total_qty': '총량'}
            )
        _picking_footer.pack(fill=tk.X, pady=(0, Spacing.SMALL))
        _picking_footer.update_totals()

        # ─── 테이블 하단 합계 (건수, 무게) ───
        n_items = len(items)
        if is_dict_format:
            total_kg = sum(float(it.get("qty_kg", 0) or 0) for it in items)
            footer_text = f"건수: {n_items}  |  총 중량(Kg): {total_kg:,.0f}"
        else:
            total_qty = sum(float(getattr(it, "total_qty", 0) or 0) for it in items)
            unit = (getattr(items[0], "total_unit", "") or "MT") if items else "MT"
            footer_text = f"건수: {n_items}  |  총량: {total_qty:,.2f} {unit}"
        footer_frame = ttk.Frame(main)
        footer_frame.pack(fill=tk.X, pady=(0, Spacing.SMALL))
        ttk.Label(footer_frame, text=footer_text, font=("맑은 고딕", 10, "bold")).pack(anchor=tk.W)

        # ─── 버튼 ───
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=Spacing.SMALL)
        if self.on_apply_clicked:
            ttk.Button(
                btn_frame,
                text="DB 반영 (RESERVED → PICKED)",
                command=self._on_apply,
            ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="닫기", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _on_apply(self) -> None:
        if self.on_apply_clicked:
            try:
                self.on_apply_clicked(self.doc, self.pdf_path)
                self.dialog.destroy()
            except Exception as e:
                from ..utils.ui_constants import CustomMessageBox
                CustomMessageBox.showerror(
                    self.dialog,
                    "DB 반영 오류",
                    str(e),
                )
