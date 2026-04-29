# -*- coding: utf-8 -*-
"""review_center.py - Phase B 검수센터(Review Center) — B2+B3/B4

목표(MVP+B2+B3/B4):
- 원본 PDF 보기(PyMuPDF)
- 드래그(ROI)로 텍스트 추출(텍스트 PDF 우선)
- 캡처(클립보드 이미지) 붙여넣기 + OCR → 빈 결과 시 Gemini 폴백(B4)
- 저장된 규칙 자동 적용: 페이지 열 때 해당 ROI 텍스트 자동 추출(B3)
- 사용자가 정답 값 입력 → 미리보기 데이터에 즉시 반영
- 적용 후 QC 재검증 콜백(있으면 호출)
- ROI 규칙 저장(SQLite) : review_rules
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import os
import time
import logging
import tkinter as tk
from tkinter import ttk, messagebox as msgbox

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from PIL import Image, ImageTk, ImageGrab
except Exception:
    Image = None
    ImageTk = None
    ImageGrab = None

try:
    from ..utils.ocr_utils import run_ocr_with_gemini_fallback
except Exception:
    run_ocr_with_gemini_fallback = None

try:
    from ..utils.review_rules import load_rules, extract_text_by_rule
except Exception:
    load_rules = None
    extract_text_by_rule = None

try:
    from ..utils.ui_constants import setup_dialog_geometry_persistence
except Exception:
    setup_dialog_geometry_persistence = None


class ReviewCenterDialog:
    """검수센터 UI"""

    def __init__(self, parent, engine, doc_paths, preview_data_ref, refresh_preview_cb=None, rerun_qc_cb=None):
        self.parent = parent
        self.engine = engine
        self.doc_paths = doc_paths or {}
        self.preview_data = preview_data_ref
        self.refresh_preview_cb = refresh_preview_cb
        self.rerun_qc_cb = rerun_qc_cb

        self.win = None
        self.canvas = None
        self._imgtk = None

        self._doc = None
        self._page_index = 0
        self._zoom = 1.6

        self._roi_start = None
        self._roi_rect_id = None
        self._roi_last = None  # (x0,y0,x1,y1) in canvas coords

        self.var_doc = tk.StringVar(value=self._first_available_doc())
        self.var_field = tk.StringVar(value="bl_no")
        self.var_row = tk.StringVar(value="1")
        self.var_extracted = tk.StringVar(value="")
        self.var_value = tk.StringVar(value="")
        self.var_status = tk.StringVar(value="")

    def _first_available_doc(self):
        for k in ["BL", "PACKING_LIST", "INVOICE", "DO"]:
            p = self.doc_paths.get(k)
            if p and os.path.exists(p):
                return k
        return next(iter(self.doc_paths.keys()), "BL")

    def show(self):
        if fitz is None:
            msgbox.showerror("검수센터", "PyMuPDF(fitz)가 필요합니다.")
            return

        self.win = create_themed_toplevel(self.parent)
        self.win.title("🧪 검수센터 (Review Center)")
        self.win.minsize(900, 600)
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(self.win, "review_center", self.parent, "large")
        else:
            self.win.geometry("1200x760")
            try:
                from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence as _sgp
                _sgp(self.win, "review_center_win", None, "large")
            except Exception as e:
                logger.warning(f'[UI] review_center: {e}')
        self._build_ui()
        self._open_doc(self.var_doc.get())

        self.win.transient(self.parent)
        self.win.grab_set()
        self.win.focus_force()

    def _build_ui(self):
        root = self.win
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        left = ttk.Frame(root, padding=10)
        left.grid(row=0, column=0, sticky="nsw")
        right = ttk.Frame(root, padding=10)
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(left, text="문서").pack(anchor="w")
        doc_combo = ttk.Combobox(
            left, textvariable=self.var_doc, state="readonly",
            values=[k for k in ["PACKING_LIST", "INVOICE", "BL", "DO"] if self.doc_paths.get(k)]
        )
        doc_combo.pack(fill="x", pady=(0, 10))
        doc_combo.bind("<<ComboboxSelected>>", lambda e: self._open_doc(self.var_doc.get()))

        ttk.Label(left, text="대상 필드").pack(anchor="w")
        field_combo = ttk.Combobox(left, textvariable=self.var_field, state="readonly",
                                   values=["bl_no", "lot_no", "container_no"])
        field_combo.pack(fill="x", pady=(0, 10))

        ttk.Label(left, text="적용 행 번호(미리보기)").pack(anchor="w")
        ttk.Entry(left, textvariable=self.var_row).pack(fill="x", pady=(0, 10))

        ttk.Separator(left).pack(fill="x", pady=8)

        ttk.Label(left, text="ROI 추출 텍스트").pack(anchor="w")
        ttk.Entry(left, textvariable=self.var_extracted).pack(fill="x", pady=(0, 10))

        ttk.Label(left, text="정답 값 입력").pack(anchor="w")
        ttk.Entry(left, textvariable=self.var_value).pack(fill="x", pady=(0, 10))

        ttk.Button(left, text="✅ 적용 + QC 재검증", command=self._apply_value).pack(fill="x", pady=(0, 6))
        ttk.Button(left, text="💾 규칙 저장(ROI)", command=self._save_rule).pack(fill="x", pady=(0, 6))
        ttk.Button(left, text="📋 캡처 붙여넣기(OCR)", command=self._paste_clipboard_ocr).pack(fill="x", pady=(0, 6))

        ttk.Label(left, textvariable=self.var_status, foreground=tc('text_muted')).pack(anchor="w", pady=(10, 0))

        nav = ttk.Frame(right)
        nav.pack(fill="x")
        ttk.Button(nav, text="◀ 이전", command=lambda: self._move_page(-1)).pack(side="left")
        ttk.Button(nav, text="다음 ▶", command=lambda: self._move_page(1)).pack(side="left", padx=(6, 0))
        ttk.Button(nav, text="＋ 확대", command=lambda: self._set_zoom(self._zoom + 0.2)).pack(side="right")
        ttk.Button(nav, text="－ 축소", command=lambda: self._set_zoom(max(0.8, self._zoom - 0.2))).pack(side="right", padx=(6, 0))

        self.canvas = tk.Canvas(right, bg=tc('bg_card'), highlightthickness=1, highlightbackground=tc('border'))
        self.canvas.pack(fill="both", expand=True, pady=(8, 0))

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

    def _open_doc(self, doc_key):
        path = self.doc_paths.get(doc_key)
        if not path or not os.path.exists(path):
            self.var_status.set("문서 파일이 없습니다.")
            return
        try:
            if self._doc:
                self._doc.close()
        except Exception:
            logger.debug("[SUPPRESSED] exception in review_center.py")  # noqa
        self._doc = fitz.open(path)
        self._page_index = 0
        self._render_page()

    def _move_page(self, delta):
        if not self._doc:
            return
        new_idx = self._page_index + delta
        if new_idx < 0 or new_idx >= self._doc.page_count:
            return
        self._page_index = new_idx
        self._render_page()

    def _set_zoom(self, zoom):
        self._zoom = float(zoom)
        self._render_page()

    def _render_page(self):
        if not self._doc or not self.canvas:
            return
        page = self._doc.load_page(self._page_index)
        mat = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        if Image is None:
            msgbox.showerror("검수센터", "Pillow(PIL)가 필요합니다.")
            return
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self._imgtk = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        self.canvas.create_image(0, 0, image=self._imgtk, anchor="nw")
        self.var_status.set(f"{os.path.basename(self._doc.name)} | page {self._page_index + 1}/{self._doc.page_count} | zoom {self._zoom:.1f}x")

        self._roi_start = None
        self._roi_last = None
        self._roi_rect_id = None
        self._auto_apply_rules_for_page()

    def _auto_apply_rules_for_page(self):
        """B3: 저장된 규칙이 있으면 현재 문서/필드/페이지에 맞는 ROI 텍스트 자동 추출."""
        if not callable(load_rules) or not callable(extract_text_by_rule) or not self._doc or not self.canvas:
            return
        db = getattr(self.engine, "db", None)
        if not db:
            return
        doc_key = (self.var_doc.get() or "").strip()
        field = (self.var_field.get() or "").strip()
        if not doc_key or not field:
            return
        try:
            rules = load_rules(db, doc_key, field)
            page_no = self._page_index + 1
            for rule in rules:
                if int(rule.get("page_no", 0)) != page_no:
                    continue
                try:
                    page = self._doc.load_page(self._page_index)
                    text = extract_text_by_rule(page, rule, self._zoom)
                    if text:
                        self.var_extracted.set(text)
                        if not self.var_value.get().strip():
                            self.var_value.set(text)
                        self.var_status.set(f"규칙 자동 적용: {field} (p.{page_no})")
                except Exception as e:
                    logger.debug("규칙 자동 적용 실패: %s", e)
                break
        except Exception as e:
            logger.debug("load_rules: %s", e)

    def _on_mouse_down(self, event):
        self._roi_start = (event.x, event.y)
        if self._roi_rect_id:
            self.canvas.delete(self._roi_rect_id)
        self._roi_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2)

    def _on_mouse_drag(self, event):
        if not self._roi_start or not self._roi_rect_id:
            return
        x0, y0 = self._roi_start
        self.canvas.coords(self._roi_rect_id, x0, y0, event.x, event.y)

    def _on_mouse_up(self, event):
        if not self._roi_start:
            return
        x0, y0 = self._roi_start
        x1, y1 = event.x, event.y
        self._roi_last = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        self._extract_text_from_roi()

    def _extract_text_from_roi(self):
        if not self._doc or self._roi_last is None:
            return
        x0, y0, x1, y1 = self._roi_last
        rect = fitz.Rect(x0 / self._zoom, y0 / self._zoom, x1 / self._zoom, y1 / self._zoom)
        page = self._doc.load_page(self._page_index)
        words = page.get_text("words") or []
        picked = []
        for w in words:
            wrect = fitz.Rect(w[0], w[1], w[2], w[3])
            if rect.intersects(wrect):
                picked.append(w[4])
        text = " ".join(picked).strip()
        self.var_extracted.set(text)
        if text and not self.var_value.get().strip():
            self.var_value.set(text)

    def _paste_clipboard_ocr(self):
        if ImageGrab is None:
            msgbox.showerror("캡처", "PIL(ImageGrab)을 사용할 수 없습니다.")
            return
        try:
            img = ImageGrab.grabclipboard()
        except Exception as e:
            msgbox.showerror("캡처", f"클립보드 이미지 읽기 실패\n\n{e}")
            return
        if img is None:
            msgbox.showwarning("캡처", "클립보드에 이미지가 없습니다. (캡처 후 다시 시도)")
            return
        text = self._ocr_image(img)
        self.var_extracted.set(text)
        if text and not self.var_value.get().strip():
            self.var_value.set(text)

    def _ocr_image(self, img):
        """B4: OCR 우선, 빈 결과 시 Gemini Vision 폴백."""
        if callable(run_ocr_with_gemini_fallback):
            try:
                return run_ocr_with_gemini_fallback(img) or ""
            except Exception as e:
                logger.warning("OCR+Gemini fallback 실패: %s", e)
                return ""
        try:
            import pytesseract
            return (pytesseract.image_to_string(img, lang="eng+kor") or "").strip()
        except Exception as e:
            logger.warning("OCR(tesseract) failed: %s", e)
        return ""

    def _apply_value(self):
        field = (self.var_field.get() or "").strip()
        value = (self.var_value.get() or "").strip()
        if not field or not value:
            msgbox.showwarning("적용", "필드/정답 값을 확인해 주세요.")
            return
        try:
            row_idx = int(float(self.var_row.get().strip() or "1"))
        except Exception:
            row_idx = 1
        if row_idx < 1 or row_idx > len(self.preview_data):
            msgbox.showerror("적용", f"행 번호 범위 오류: 1~{len(self.preview_data)}")
            return
        self.preview_data[row_idx - 1][field] = value

        if callable(self.refresh_preview_cb):
            try:
                self.refresh_preview_cb()
            except Exception as e:
                logger.debug(f"refresh_preview_cb suppressed: {e}")

        if callable(self.rerun_qc_cb):
            try:
                self.rerun_qc_cb()
            except Exception as e:
                logger.debug(f"rerun_qc_cb suppressed: {e}")

        self.var_status.set(f"✅ 적용 완료: {row_idx}행 / {field} = {value}")

    def _save_rule(self):
        if self._roi_last is None:
            msgbox.showwarning("규칙 저장", "먼저 PDF에서 드래그로 ROI를 지정해 주세요.")
            return
        field = (self.var_field.get() or "").strip()
        sample = (self.var_value.get() or "").strip()
        if not field or not sample:
            msgbox.showwarning("규칙 저장", "필드와 정답 값을 입력해 주세요.")
            return

        db = getattr(self.engine, "db", None)
        if db is None:
            msgbox.showwarning("규칙 저장", "engine.db를 찾을 수 없어 규칙을 저장할 수 없습니다.")
            return

        doc_key = self.var_doc.get()
        page_no = self._page_index + 1
        x0, y0, x1, y1 = self._roi_last

        try:
            db.execute(
                """CREATE TABLE IF NOT EXISTS review_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_type TEXT NOT NULL,
                    field TEXT NOT NULL,
                    page_no INTEGER NOT NULL,
                    x0 REAL NOT NULL, y0 REAL NOT NULL, x1 REAL NOT NULL, y1 REAL NOT NULL,
                    zoom REAL NOT NULL,
                    sample_value TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            db.execute(
                """INSERT INTO review_rules(doc_type, field, page_no, x0,y0,x1,y1, zoom, sample_value, created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (doc_key, field, page_no, float(x0), float(y0), float(x1), float(y1), float(self._zoom), sample,
                 time.strftime("%Y-%m-%d %H:%M:%S"))
            )
            self.var_status.set("💾 규칙 저장 완료 (review_rules)")
        except Exception as e:
            msgbox.showerror("규칙 저장 실패", str(e))
