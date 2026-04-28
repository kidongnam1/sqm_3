# -*- coding: utf-8 -*-
"""
SQM v6.3.1 — S1 원스톱 출고 다이얼로그 (통합본)
==================================================
PATCH-02 + 02A + 02B + 02C + 02D 전체 머지
작성일: 2026-03-02

4단계 워크플로우:
  ① 입력(붙여넣기/AI) → ② 톤백선택(LOT일괄/랜덤/수동) → ③ 스캔검증(하드스톱) → ④ 확정

상태 머신: DRAFT → WAIT_SCAN → FINALIZED / REVIEW_REQUIRED / ERROR
핵심 정책:
  - actual > expected → ⛔ ERROR (하드스톱, FINALIZED 불가)
  - actual < expected → ⚠️ REVIEW_REQUIRED (사유 선택 후 승인)
  - actual = expected → ✅ FINALIZED
  - 배치 간 톤백 중복 선택 차단 (v2.2 #1)
  - SOLD는 FINALIZED 확정 후에만 적용
  - 근거문서 첨부 + SHA-256 해시 중복 차단 (v2.2 #4)
  - OUT 스캔 파일(xlsx/csv) 로드 + 미매칭 톤백 감지 (v2.2 #2,#3)
  - audit_log DB 이벤트 기록 (루비안 Q2)
  - 근거문서 폴더 자동 복사 + 90일 정리 (루비안 Q3, Q2)
  - 감사 로그 뷰어 + CSV 내보내기 (루비안 Q1)
"""
# ══════════════════════════════════════════════════════════════
# 🎨 색상 사용 원칙 (v3.8.0 — 절대 준수)
# ══════════════════════════════════════════════════════════════
# ✅ 올바른 방법: tc() 함수 사용 (라이트/다크 자동 전환)
#     from gui_app_modular.utils.ui_constants import tc
#     label.config(fg=tc('text_primary'), bg=tc('bg_primary'))
#     entry.config(fg=tc('text_primary'), bg=tc('bg_entry'))
#     frame.config(bg=tc('bg_secondary'))
#
# ❌ 금지: 하드코딩 색상 사용
#     label.config(fg=tc('text_primary'))         # 다크 배경에서 안 보임
#     label.config(fg=tc('text_primary'))         # 라이트 배경에서 안 보임
#     label.config(bg=tc('bg_primary'))       # 라이트 모드에서 검은 배경
#
# 📋 주요 tc() 키:
#     text_primary   — 일반 텍스트 (라이트: #2c3e50  다크: #FF8C00)
#     text_secondary — 보조 텍스트
#     text_muted     — 비활성 텍스트 (gray 대체)
#     bg_primary     — 기본 배경
#     bg_secondary   — 보조 배경
#     bg_card        — 카드/패널 배경
#     bg_entry       — 입력창 배경
#     success        — 성공 (녹색 계열)
#     warning        — 경고 (주황 계열)
#     danger         — 오류 (빨간 계열)
#     info           — 정보 (파란 계열)
# ══════════════════════════════════════════════════════════════

from gui_app_modular.utils.ui_constants import create_themed_toplevel, tc  # v8.0.9, v8.4.1
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
import logging
import random
import tkinter as tk
from tkinter import ttk, filedialog, BOTH, YES, X, Y, LEFT, RIGHT, END, W
from tkinter import VERTICAL
from datetime import datetime, date
import hashlib
import csv
import os
import shutil
import json

import openpyxl  # 필수 (pip install openpyxl)
HAS_OPENPYXL = True

from ..utils.ui_constants import CustomMessageBox, setup_dialog_geometry_persistence

logger = logging.getLogger(__name__)

try:
    from theme_aware import ThemeAware
except Exception as e:  # 테마 유틸 미탑재 환경 호환
    logger.warning(f"[UI] ThemeAware import failed: {e}")
    ThemeAware = None

# ── 상태 머신 ──
BATCH_STATUS = {
    'DRAFT': '출고초안',
    'WAIT_SCAN': '스캔대기',
    'FINALIZED': '출고확정',
    'REVIEW_REQUIRED': '확인대기',
    'ERROR': '오류(하드스톱)',
}

STATUS_COLOR = {
    'DRAFT': '#6366f1',
    'WAIT_SCAN': '#d97706',
    'FINALIZED': '#059669',
    'REVIEW_REQUIRED': '#ea580c',
    'ERROR': '#dc2626',
}

SHORTAGE_REASONS = [
    "재고 부족 (잔여분 다음 배치)",
    "현장 판단 (품질/포장 문제 제외)",
    "고객 요청 변경 (출고 중 수량 조정)",
    "기타 (사유 직접 입력)",
]


class S1OneStopOutboundDialog:
    """S1 원스톱 출고 — 4단계 워크플로우 다이얼로그"""

    def __init__(self, app, engine, initial_lot_no: str = ''):
        self.app = app
        self.engine = engine
        self.db = engine.db
        self.root = app.root
        self._initial_lot_no = str(initial_lot_no or '').strip()  # v8.3.1: 우클릭 즉시 출고

        # 워크플로우 데이터
        self.batches = []           # [{id, product, lot_no, request_qty, status, ...}]
        self.tonbag_selections = {} # batch_id → set(tonbag_id)
        self.scan_results = {}      # batch_id → {actual_qty, diff}
        self.review_reasons = {}    # batch_id → reason str
        self.completed = []
        self._is_dark = False
        self._status_colors = dict(STATUS_COLOR)

        # ★ v2.2 신규 상태
        self.proof_docs = []        # [{id, name, path, size, hash, added_at}]
        self.proof_hashes = set()   # 중복 방지용 해시 셋
        self.out_scan_data = None   # OUT 스캔 파일 파싱 결과
        self.unmatched_tonbags = [] # 미매칭 톤백 목록

        # ★ Q3: 근거문서 저장 폴더 (data/proof_docs/YYYY-MM-DD/)
        self.proof_base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data', 'proof_docs', date.today().isoformat()
        )
        os.makedirs(self.proof_base_dir, exist_ok=True)

        # ★ Q2: audit_log 테이블 자동 생성 (없으면)
        self._ensure_audit_table()

        # ★ Q2: 90일 초과 근거문서 폴더 자동 정리
        self._cleanup_old_proof_docs(retention_days=90)

    def _detect_dark_mode(self):
        """현재 테마가 다크인지 안전하게 판별"""
        if ThemeAware:
            try:
                return ThemeAware.is_dark()
            except Exception as e:
                logger.warning(f"[UI] ThemeAware.is_dark() check failed: {e}")
        try:
            style = ttk.Style()
            bg = style.lookup("TFrame", "background") or style.lookup(".", "background") or ""
            if bg.startswith("#") and len(bg) >= 7:
                r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
                return (r * 299 + g * 587 + b * 114) / 1000 < 128
        except Exception as e:
            logger.warning(f"[UI] dark mode detection via style lookup failed: {e}")
        return False

    def _setup_notebook_style(self):
        """S1 전용 Notebook 스타일 (메인앱 전역 탭 숨김 스타일과 분리)"""
        style = ttk.Style()
        notebook_style = "S1.TNotebook"
        tab_style = "S1.TNotebook.Tab"

        base_nb_layout = style.layout("TNotebook")
        if base_nb_layout:
            style.layout(notebook_style, base_nb_layout)

        base_tab_layout = style.layout("TNotebook.Tab")
        if not base_tab_layout:
            base_tab_layout = [
                ("Notebook.tab", {
                    "sticky": "nswe",
                    "children": [("Notebook.padding", {
                        "side": "top",
                        "sticky": "nswe",
                        "children": [("Notebook.focus", {
                            "side": "top",
                            "sticky": "nswe",
                            "children": [("Notebook.label", {"side": "top", "sticky": ""})]
                        })]
                    })]
                })
            ]
        style.layout(tab_style, base_tab_layout)

        fg_sel = "#ffffff" if self._is_dark else "#0f172a"
        fg_unsel = "#cbd5e1" if self._is_dark else "#334155"
        bg_unsel = "#334155" if self._is_dark else "#e2e8f0"
        bg_sel = "#1f2937" if self._is_dark else "#ffffff"

        style.configure(tab_style, padding=(12, 6), foreground=fg_unsel, background=bg_unsel)
        style.map(
            tab_style,
            foreground=[("selected", fg_sel), ("!selected", fg_unsel)],
            background=[("selected", bg_sel), ("!selected", bg_unsel)],
        )
        return notebook_style

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # DB / 감사 유틸리티
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _ensure_audit_table(self):
        """audit_log 테이블 없으면 생성"""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type  TEXT NOT NULL,
                    event_data  TEXT,
                    batch_id    TEXT,
                    tonbag_id   TEXT,
                    user_note   TEXT,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    created_by  TEXT DEFAULT 'S1_ONESTOP'
                )
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_event
                ON audit_log(event_type, created_at)
            """)
            self.db.conn.commit()
        except Exception as e:
            logger.warning(f"[S1] audit_log 테이블 생성 스킵: {e}")

    def _write_audit(self, event_type, event_data=None, batch_id=None,
                     tonbag_id=None, user_note=None):
        """audit_log에 이벤트 1건 기록"""
        try:
            data_str = json.dumps(event_data, ensure_ascii=False) if event_data else None
            self.db.execute(
                "INSERT INTO audit_log (event_type, event_data, batch_id, tonbag_id, "
                "user_note, created_at) VALUES (?,?,?,?,?,?)",
                (event_type, data_str, batch_id, tonbag_id, user_note,
                 datetime.now().isoformat())
            )
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"[S1] audit_log 기록 실패: {event_type} → {e}")

    def _cleanup_old_proof_docs(self, retention_days=90):
        """90일 초과 proof_docs 날짜 폴더 삭제 (audit_log 레코드는 보존)"""
        try:
            base = os.path.dirname(self.proof_base_dir)  # data/proof_docs/
            if not os.path.isdir(base):
                return

            cutoff = date.today().toordinal() - retention_days
            removed = 0

            for entry in os.listdir(base):
                entry_path = os.path.join(base, entry)
                if not os.path.isdir(entry_path):
                    continue

                try:
                    folder_date = date.fromisoformat(entry)
                except (ValueError, TypeError):
                    continue

                if folder_date.toordinal() < cutoff:
                    file_count = len(os.listdir(entry_path))
                    shutil.rmtree(entry_path, ignore_errors=True)
                    removed += 1
                    logger.info(
                        f"[S1] proof_docs 정리: {entry} 삭제 "
                        f"({file_count}개 파일, {retention_days}일 초과)")

                    self._write_audit(
                        event_type='PROOF_CLEANUP',
                        event_data={
                            'folder': entry,
                            'file_count': file_count,
                            'retention_days': retention_days,
                        },
                        user_note=f"자동 정리: {entry} ({file_count}개 파일)"
                    )

            if removed > 0:
                logger.info(f"[S1] proof_docs 자동 정리 완료: {removed}개 폴더 삭제")

        except Exception as e:
            logger.warning(f"[S1] proof_docs 자동 정리 실패: {e}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 다이얼로그 표시
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def show(self):
        """다이얼로그 표시"""
        self.win = create_themed_toplevel(self.root)
        self.win.title("🚀 S1 원스톱 출고 — v6.3.1")
        self.win.transient(self.root)
        self.win.grab_set()
        setup_dialog_geometry_persistence(self.win, "onestop_outbound_dialog", self.root, "large")
        self._is_dark = self._detect_dark_mode()
        if ThemeAware:
            try:
                self._status_colors = ThemeAware.status_colors()
                ThemeAware.apply_to_toplevel(self.win)
            except Exception as e:
                logger.debug(f"[S1] ThemeAware 적용 스킵: {e}")

        # ── 상단: 상태 머신 표시 + 컬러 바 ──
        top_fr = ttk.Frame(self.win)
        top_fr.pack(fill=X, padx=10, pady=(8, 4))

        ttk.Label(top_fr, text="🚀 S1 원스톱 출고",
                  font=("맑은 고딕", 14, "bold")).pack(side=LEFT)

        # ★ 1단계: 현재 상태 컬러 바
        self._status_bar_canvas = tk.Canvas(top_fr, width=180, height=24,
                                             highlightthickness=0)
        self._status_bar_canvas.pack(side=LEFT, padx=(20, 10))
        self._status_bar_label = ttk.Label(top_fr, text="DRAFT",
                                            font=("맑은 고딕", 10, "bold"))
        self._status_bar_label.pack(side=LEFT)

        sm_fr = ttk.Frame(top_fr)
        sm_fr.pack(side=RIGHT)
        for i, (k, v) in enumerate(BATCH_STATUS.items()):
            ttk.Label(sm_fr, text=v, font=("맑은 고딕", 8),
                      foreground=self._status_colors.get(k, STATUS_COLOR[k])).pack(side=LEFT, padx=2)
            if i < len(BATCH_STATUS) - 1:
                ttk.Label(sm_fr, text="→", font=("맑은 고딕", 8)).pack(side=LEFT)

        # ── 노트북 (4단계 탭) ──
        self.nb = ttk.Notebook(self.win, style=self._setup_notebook_style())
        self.nb.pack(fill=BOTH, expand=YES, padx=10, pady=5)

        self.tab1 = ttk.Frame(self.nb)  # 입력
        self.tab2 = ttk.Frame(self.nb)  # 톤백선택
        self.tab3 = ttk.Frame(self.nb)  # 스캔검증
        self.tab4 = ttk.Frame(self.nb)  # 완료

        self.nb.add(self.tab1, text="  ① 입력 (붙여넣기)  ")
        self.nb.add(self.tab2, text="  ② 톤백 선택  ", state='disabled')
        self.nb.add(self.tab3, text="  ③ 스캔 검증  ", state='disabled')
        self.nb.add(self.tab4, text="  ④ 완료  ", state='disabled')

        # ★ 1단계: 탭 제목 배지 초기값
        self._tab_titles = [
            "  ① 입력 (붙여넣기)  ",
            "  ② 톤백 선택  ",
            "  ③ 스캔 검증  ",
            "  ④ 완료  ",
        ]

        self._build_tab1()
        self._build_tab2()
        self._build_tab3()
        self._build_tab4()

        # ── 하단: 재고 요약 ──
        self._build_footer()

        # v8.3.1 [즉시 출고]: 우클릭으로 열렸을 때 LOT 자동 채우기
        if self._initial_lot_no:
            self.win.after(100, self._prefill_initial_lot)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 1: 입력 (붙여넣기)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _build_tab1(self):
        fr = self.tab1

        # 안내
        info_fr = ttk.LabelFrame(fr, text="입력 형식")
        info_fr.pack(fill=X, padx=8, pady=5)
        ttk.Label(info_fr, text="LOT NO → 수량(MT) → 거래처 → SALE REF (탭/콤마 구분, 엑셀에서 복사-붙여넣기)",
                  font=("맑은 고딕", 9)).pack(padx=8, pady=4)

        # ── v8.3.2: 고객사 콤보박스 + Sale Ref 빠른 입력 ─────────────
        quick_fr = ttk.LabelFrame(fr, text="🏢 고객사 빠른 선택 (선택 시 붙여넣기 란 자동 업데이트)")
        quick_fr.pack(fill=X, padx=8, pady=(0, 3))

        q_row = ttk.Frame(quick_fr)
        q_row.pack(fill=X, padx=6, pady=4)

        ttk.Label(q_row, text="고객사:", font=("맑은 고딕", 9)).pack(side=LEFT)
        self._cust_var = tk.StringVar()
        self._cust_combo = ttk.Combobox(
            q_row, textvariable=self._cust_var,
            width=22, font=("맑은 고딕", 9)
        )
        self._cust_combo.pack(side=LEFT, padx=(4, 12))
        # v8.3.2: 콤보 선택 즉시 적용 (Enter 또는 선택)
        self._cust_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_quick_customer())
        self._cust_combo.bind('<Return>', lambda e: self._apply_quick_customer())

        ttk.Label(q_row, text="Sale Ref:", font=("맑은 고딕", 9)).pack(side=LEFT)
        self._sale_ref_var = tk.StringVar()
        ttk.Entry(q_row, textvariable=self._sale_ref_var,
                  width=18, font=("맑은 고딕", 9)).pack(side=LEFT, padx=(4, 12))

        ttk.Button(
            q_row, text="✏️ 붙여넣기 란에 적용",
            command=self._apply_quick_customer
        ).pack(side=LEFT, padx=4)

        ttk.Button(
            q_row, text="🔄 고객사 목록 새로고침",
            command=self._refresh_customer_list
        ).pack(side=LEFT, padx=2)

        # 고객사 목록 초기 로드
        self._refresh_customer_list()

        # 텍스트 입력 — ★ 2단계: placeholder 안내 텍스트
        self.paste_text = tk.Text(fr, height=12, font=("Consolas", 10), wrap='none')
        self.paste_text.pack(fill=BOTH, expand=YES, padx=8, pady=5)
        self._paste_placeholder = "  엑셀에서 복사 후 Ctrl+V 붙여넣기\n\n  형식: LOT NO ⟶ 수량(MT) ⟶ 거래처 ⟶ SALE REF\n  (탭 또는 콤마 구분)\n\n  📂 또는 파일을 드래그 앤 드롭"
        self._show_placeholder()
        self.paste_text.bind('<FocusIn>', self._on_paste_focus_in)
        self.paste_text.bind('<FocusOut>', self._on_paste_focus_out)

        # ★ v2.2 근거문서 첨부
        doc_fr = ttk.LabelFrame(fr, text="📎 근거문서 (선택)")
        doc_fr.pack(fill=X, padx=8, pady=3)

        doc_btn_fr = ttk.Frame(doc_fr)
        doc_btn_fr.pack(fill=X, padx=4, pady=2)
        ttk.Button(doc_btn_fr, text="+ 파일 첨부",
                   command=self._attach_proof_doc).pack(side=LEFT, padx=2)
        self.proof_status_var = tk.StringVar(value="첨부 없음")
        ttk.Label(doc_btn_fr, textvariable=self.proof_status_var,
                  font=("맑은 고딕", 8)).pack(side=LEFT, padx=8)

        self.proof_listbox = tk.Listbox(doc_fr, height=3, font=("Consolas", 9))
        self.proof_listbox.pack(fill=X, padx=4, pady=2)
        self.proof_listbox.bind('<Double-1>', self._preview_proof_doc)

        # 버튼 바
        btn_fr = ttk.Frame(fr)
        btn_fr.pack(fill=X, padx=8, pady=5)

        ttk.Button(btn_fr, text="📝 샘플 삽입",
                   command=self._insert_sample).pack(side=LEFT, padx=4)
        ttk.Label(btn_fr, text="", textvariable=tk.StringVar()).pack(side=LEFT, expand=YES)

        self.parse_status_var = tk.StringVar(value="")
        ttk.Label(btn_fr, textvariable=self.parse_status_var,
                  font=("맑은 고딕", 9)).pack(side=LEFT, padx=8)

        ttk.Button(btn_fr, text="🔄 파싱 → DRAFT   ▶",
                   command=self._do_parse, style='Accent.TButton').pack(side=RIGHT, padx=4, ipady=4)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 근거문서 관련 메서드
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _attach_proof_doc(self):
        """근거문서 첨부 (해시 중복 차단 + 폴더 복사 + DB 경로 저장)"""
        paths = filedialog.askopenfilenames(
            parent=self.win,
            title="근거문서 선택",
            filetypes=[
                ("모든 지원 파일", "*.pdf *.png *.jpg *.jpeg *.xlsx *.csv *.txt *.docx"),
                ("PDF", "*.pdf"), ("이미지", "*.png *.jpg *.jpeg"),
                ("Excel/CSV", "*.xlsx *.csv"), ("모든 파일", "*.*"),
            ]
        )
        for fpath in paths:
            try:
                fhash = self._hash_file(fpath)
                fname = os.path.basename(fpath)

                if fhash in self.proof_hashes:
                    CustomMessageBox.showwarning(
                        self.win, "⛔ 중복 파일",
                        f'"{fname}" 은(는) 이미 첨부됨 (hash: {fhash[:12]}...)')
                    continue

                # ★ Q3: 폴더에 복사 (해시 prefix로 중복명 방지)
                dest_name = f"{fhash[:8]}_{fname}"
                dest_path = os.path.join(self.proof_base_dir, dest_name)
                shutil.copy2(fpath, dest_path)

                self.proof_hashes.add(fhash)
                doc = {
                    'id': fhash[:16],
                    'name': fname,
                    'original_path': fpath,
                    'stored_path': dest_path,
                    'size': os.path.getsize(fpath),
                    'hash': fhash,
                    'added_at': datetime.now().strftime('%H:%M:%S'),
                }
                self.proof_docs.append(doc)
                self.proof_listbox.insert(END,
                    f"📄 {fname}  ({doc['size']/1024:.1f}KB)  [{doc['added_at']}]")

                # ★ Q2+Q3: audit 기록
                self._write_audit(
                    event_type='PROOF_ATTACH',
                    event_data={
                        'file_name': fname,
                        'file_hash': fhash,
                        'file_size': doc['size'],
                        'stored_path': dest_path,
                    },
                    user_note=f"근거문서 첨부: {fname}"
                )

                logger.info(f"[S1] 근거문서 첨부: {fname} → {dest_path}")

            except Exception as e:
                logger.error(f"[S1] 근거문서 첨부 실패: {fpath} → {e}")
                CustomMessageBox.showerror(self.win, "오류", f"파일 첨부 실패:\n{e}")

        n = len(self.proof_docs)
        self.proof_status_var.set(f"📎 {n}건 첨부" if n > 0 else "첨부 없음")

    @staticmethod
    def _hash_file(filepath, chunk_size=65536):
        """파일 SHA-256 해시 (바이너리 안전)"""
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _preview_proof_doc(self, event=None):
        """근거문서 미리보기 (이미지/PDF)"""
        sel_idx = self.proof_listbox.curselection()
        if not sel_idx:
            return
        idx = sel_idx[0]
        if idx >= len(self.proof_docs):
            return
        doc = self.proof_docs[idx]
        fpath = doc.get('stored_path') or doc.get('original_path', '')

        if not os.path.exists(fpath):
            CustomMessageBox.showwarning(self.win, "경고", f"파일 없음:\n{fpath}")
            return

        ext = os.path.splitext(fpath)[1].lower()

        if ext in ('.png', '.jpg', '.jpeg', '.gif'):
            self._show_image_preview(doc)
        elif ext == '.pdf':
            try:
                os.startfile(fpath)
            except AttributeError:
                import subprocess
                subprocess.Popen(['xdg-open', fpath])
        else:
            CustomMessageBox.showinfo(
                self.win, "📄 문서 정보",
                f"파일: {doc['name']}\n"
                f"크기: {doc['size']/1024:.1f} KB\n"
                f"해시: {doc['hash'][:24]}...\n"
                f"첨부시간: {doc['added_at']}\n\n"
                f"(이미지/PDF만 미리보기 지원)")

    def _show_image_preview(self, doc):
        """이미지 미리보기 Toplevel"""
        try:
            from PIL import Image, ImageTk
        except ImportError:
            CustomMessageBox.showwarning(self.win, "경고",
                "Pillow 미설치 — 이미지 미리보기 불가\npip install Pillow")
            return

        fpath = doc.get('stored_path') or doc.get('original_path', '')
        dlg = create_themed_toplevel(self.win)
        dlg.title(f"📄 미리보기 — {doc['name']}")
        dlg.transient(self.win)
        dlg.resizable(True, True)  # v9.0: 크기 조절 허용
        dlg.minsize(400, 300)  # v9.0: 최소 크기

        img = Image.open(fpath)
        img.thumbnail((800, 600), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)

        label = tk.Label(dlg, image=photo)
        label.image = photo
        label.pack()

        info = (f"  {doc['name']}  |  {doc['size']/1024:.1f}KB  |  "
                f"hash: {doc['hash'][:16]}...  |  {doc['added_at']}")
        ttk.Label(dlg, text=info, font=("맑은 고딕", 8)).pack(pady=3)
        ttk.Button(dlg, text="닫기", command=dlg.destroy).pack(pady=5)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 1 계속: 샘플 & 파싱
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ★ 2단계: Placeholder + 토스트 메시지
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _show_placeholder(self):
        """2-3: placeholder 텍스트 표시"""
        self.paste_text.delete('1.0', END)
        self.paste_text.insert('1.0', self._paste_placeholder)
        self.paste_text.config(fg=tc('text_muted'))
        self._paste_has_placeholder = True

    def _on_paste_focus_in(self, event=None):
        """2-3: 포커스 시 placeholder 제거"""
        if getattr(self, '_paste_has_placeholder', False):
            self.paste_text.delete('1.0', END)
            self.paste_text.config(fg='')  # 기본색 복원
            self._paste_has_placeholder = False

    def _on_paste_focus_out(self, event=None):
        """2-3: 포커스 아웃 시 빈 내용이면 placeholder 복원"""
        content = self.paste_text.get('1.0', END).strip()
        if not content:
            self._show_placeholder()

    def _show_toast(self, message, duration_ms=2500):
        """★ 2-5: 하단 토스트 메시지 (자동 사라짐)"""
        toast = tk.Label(self.win, text=f"  {message}  ",
                         bg=tc('btn_inbound'), fg=tc('text_primary'),
                         font=('맑은 고딕', 10, 'bold'),
                         padx=16, pady=8)
        toast.place(relx=0.5, rely=0.95, anchor='center')

        def _fade():
            try:
                toast.destroy()
            except tk.TclError:
                logger.debug("[SUPPRESSED] exception in onestop_outbound.py")  # noqa
        self.win.after(duration_ms, _fade)

    def _insert_sample(self):
        """테스트용 샘플 데이터"""
        try:
            rows = self.db.fetchall(
                "SELECT lot_no, COUNT(*) as cnt, SUM(weight)/1000.0 as total_mt "
                "FROM inventory_tonbag WHERE status='AVAILABLE' AND COALESCE(is_sample,0)=0 "
                "GROUP BY lot_no ORDER BY total_mt DESC LIMIT 4"
            )
            if rows:
                lines = []
                for r in rows:
                    mt = round(r['total_mt'], 3)
                    lines.append(f"{r['lot_no']}\t{mt}\tSQM\tSALE-TEST")
                self.paste_text.delete('1.0', END)
                self.paste_text.insert('1.0', '\n'.join(lines))
                self.parse_status_var.set(f"✅ 샘플 {len(rows)}건 삽입 (실제 재고 기반)")
                return
        except Exception as e:
            logger.warning(f"샘플 로드 실패: {e}")

        self.paste_text.delete('1.0', END)
        self.paste_text.insert('1.0',
            "LOT-2026-001\t5.0\tSQM\tSALE-001\n"
            "LOT-2026-002\t3.5\tPosco HY\tSALE-002\n"
        )
        self.parse_status_var.set("📝 샘플 삽입됨 (하드코딩)")

    def _prefill_initial_lot(self) -> None:
        """v8.3.1: 우클릭 즉시 출고 — LOT 자동 채우기.

        재고 현황 탭에서 LOT 우클릭 → 즉시 출고 선택 시
        해당 LOT의 가용 수량을 자동으로 입력란에 채워줍니다.
        고객사·sale_ref는 사용자가 직접 입력.
        """
        lot_no = self._initial_lot_no
        if not lot_no:
            return
        try:
            # 해당 LOT의 AVAILABLE 톤백 합계 조회
            row = self.db.fetchone(
                "SELECT COALESCE(SUM(weight), 0) AS total_kg "
                "FROM inventory_tonbag "
                "WHERE lot_no = ? AND status = 'AVAILABLE' "
                "  AND COALESCE(is_sample, 0) = 0",
                (lot_no,)
            )
            total_kg  = float(row['total_kg'] if isinstance(row, dict) else (row[0] or 0))
            total_mt  = round(total_kg / 1000.0, 3)

            # 고객사 미리 채우기 — 이전 출고 이력에서 최근 고객사 가져오기
            last_cust = ''
            try:
                hist = self.db.fetchone(
                    "SELECT customer FROM allocation_plan "
                    "WHERE lot_no = ? AND customer IS NOT NULL AND customer != '' "
                    "ORDER BY created_at DESC LIMIT 1",
                    (lot_no,)
                )
                if hist:
                    last_cust = (hist['customer'] if isinstance(hist, dict)
                                 else hist[0]) or ''
            except Exception as e:
                logger.warning(f'[UI] onestop_outbound: {e}')
            # paste_text 채우기 — 형식: lot_no\tqty_mt\tcustomer\tsale_ref
            self.paste_text.config(fg='')  # placeholder 색상 해제
            self.paste_text.delete('1.0', END)
            self.paste_text.insert(
                '1.0',
                f"{lot_no}\t{total_mt}\t{last_cust}\t"
            )
            # 고객사 콤보박스도 동기화
            if hasattr(self, '_cust_var') and last_cust:
                self._cust_var.set(last_cust)
            # 커서를 고객사 위치로 이동 (사용자가 바로 입력 가능)
            self.paste_text.mark_set('insert', f'1.{len(lot_no) + len(str(total_mt)) + 2}')
            self.paste_text.focus_set()

            self.parse_status_var.set(
                f"🚀 즉시 출고 — {lot_no}  |  가용: {total_kg:,.0f} kg ({total_mt} MT)"
                f"  |  고객사·Sale Ref 입력 후 [파싱 실행] 클릭"
            )
            logger.info(f"[즉시출고] LOT={lot_no} 자동 채우기 완료 ({total_mt} MT)")

        except Exception as e:
            logger.warning(f"[즉시출고] prefill 실패 ({lot_no}): {e}")
            self.parse_status_var.set(f"⚠️ {lot_no} 자동 채우기 실패 — 직접 입력해주세요")

    def _refresh_customer_list(self) -> None:
        """v8.3.2: 고객사 목록 DB 조회 후 콤보박스 업데이트.

        출고 이력(outbound) + Allocation 이력에서 최근 고객사 목록 수집.
        """
        try:
            customers = set()

            # 1. outbound 테이블 — 실제 출고 고객사
            rows1 = self.db.fetchall(
                "SELECT DISTINCT customer FROM outbound "
                "WHERE customer IS NOT NULL AND customer != '' "
                "ORDER BY created_at DESC LIMIT 50"
            )
            for r in (rows1 or []):
                cust = r['customer'] if isinstance(r, dict) else r[0]
                if cust and str(cust).strip():
                    customers.add(str(cust).strip())

            # 2. allocation_plan 테이블 — 배정 고객사
            rows2 = self.db.fetchall(
                "SELECT DISTINCT customer FROM allocation_plan "
                "WHERE customer IS NOT NULL AND customer != '' "
                "ORDER BY created_at DESC LIMIT 50"
            )
            for r in (rows2 or []):
                cust = r['customer'] if isinstance(r, dict) else r[0]
                if cust and str(cust).strip():
                    customers.add(str(cust).strip())

            # 3. 대표 고객사 목록 (항상 포함)
            KNOWN_CUSTOMERS = ['CATL', 'BYD', 'LG Energy Solution',
                               'POSCO HY Clean Metal', 'SQM']
            for kc in KNOWN_CUSTOMERS:
                customers.add(kc)

            sorted_list = sorted(customers)
            if hasattr(self, '_cust_combo'):
                self._cust_combo['values'] = sorted_list
                logger.debug(f"[고객사목록] {len(sorted_list)}개 로드")

        except Exception as e:
            logger.debug(f"[고객사목록] 로드 실패: {e}")
            # 기본값 유지
            if hasattr(self, '_cust_combo'):
                self._cust_combo['values'] = [
                    'CATL', 'BYD', 'LG Energy Solution',
                    'POSCO HY Clean Metal', 'SQM'
                ]

    def _apply_quick_customer(self) -> None:
        """v8.3.2: 고객사/Sale Ref를 붙여넣기 란의 모든 행에 일괄 적용."""
        customer = self._cust_var.get().strip()
        sale_ref = self._sale_ref_var.get().strip()

        if not customer:
            self.parse_status_var.set("⚠️ 고객사를 선택하거나 입력해주세요")
            return

        current = self.paste_text.get('1.0', 'end').strip()
        if not current or current == self._paste_placeholder.strip():
            self.parse_status_var.set("⚠️ LOT 데이터를 먼저 입력해주세요")
            return

        import re as _re
        updated_lines = []
        changed = 0
        for line in current.splitlines():
            line = line.strip()
            if not line:
                continue
            # 탭 구분으로 분리
            parts = _re.split(r'[	,]', line)
            if len(parts) >= 1:
                lot = parts[0].strip()
                qty = parts[1].strip() if len(parts) > 1 else ''
                # 고객사·sale_ref 강제 교체
                new_line = f"{lot}	{qty}	{customer}	{sale_ref}"
                updated_lines.append(new_line)
                changed += 1

        if updated_lines:
            self.paste_text.config(fg='')
            self.paste_text.delete('1.0', 'end')
            self.paste_text.insert('1.0', '\n'.join(updated_lines))
            self.parse_status_var.set(
                f"✅ {changed}개 행에 [{customer}] / [{sale_ref}] 적용 완료"
                f"  →  [파싱 실행] 클릭해주세요"
            )
            logger.info(f"[고객사적용] customer={customer} sale_ref={sale_ref} {changed}행")
        else:
            self.parse_status_var.set("⚠️ 적용할 행이 없습니다")


    def _do_parse(self):
        """붙여넣기 텍스트 → DRAFT 배치 생성"""
        text = self.paste_text.get('1.0', END).strip()
        if not text:
            self.parse_status_var.set("⚠️ 입력 데이터 없음")
            return

        lines = [l for l in text.split('\n') if l.strip()]
        batches = []
        errors = []

        header_kw = {'lot_no', 'lot no', 'lotno', 'sap_no', 'product', 'qty'}
        if lines and lines[0].split('\t')[0].strip().lower().replace(' ', '_') in header_kw:
            lines = lines[1:]

        for idx, line in enumerate(lines, 1):
            cols = [c.strip() for c in line.replace(',', '\t').replace(';', '\t').replace('|', '\t').split('\t')]
            if len(cols) < 2:
                errors.append(f"{idx}행: 최소 2컬럼 필요")
                continue

            lot_no = cols[0]
            if not lot_no:
                errors.append(f"{idx}행: LOT NO 누락")
                continue

            try:
                qty_mt = float(cols[1].replace(',', ''))
            except (ValueError, TypeError):
                errors.append(f"{idx}행: 수량 오류 '{cols[1]}'")
                continue

            if qty_mt <= 0:
                errors.append(f"{idx}행: 수량 0 이하")
                continue

            batch_id = f"S1-{datetime.now().strftime('%H%M%S')}-{idx}"
            batches.append({
                'id': batch_id,
                'lot_no': lot_no,
                'request_qty_mt': qty_mt,
                'request_qty_kg': qty_mt * 1000,
                'customer': cols[2] if len(cols) > 2 else '',
                'sale_ref': cols[3] if len(cols) > 3 else '',
                'status': 'DRAFT',
                'created_at': datetime.now().isoformat(),
                'selected_tonbags': [],
                'allocated_qty_kg': 0,
                'actual_qty_kg': None,
                'scan_diff_kg': None,
            })

        if not batches:
            err_msg = "유효한 행이 없습니다."
            if errors:
                err_msg += "\n" + "\n".join(errors[:5])
            self.parse_status_var.set("❌ 파싱 실패")
            CustomMessageBox.showwarning(self.win, "파싱 오류", err_msg)
            return

        # LOT 유효성 검증
        lot_nos = list(set(b['lot_no'] for b in batches))
        try:
            ph = ",".join("?" * len(lot_nos))
            avail_rows = self.db.fetchall(
                f"SELECT lot_no, COUNT(*) as cnt, SUM(weight) as total_kg "
                f"FROM inventory_tonbag "
                f"WHERE lot_no IN ({ph}) AND status='AVAILABLE' AND COALESCE(is_sample,0)=0 "
                f"GROUP BY lot_no",
                tuple(lot_nos),
            )
            avail_map = {r['lot_no']: r for r in avail_rows}
            for b in batches:
                if b['lot_no'] not in avail_map:
                    b['_warn'] = "❌ LOT 미등록 또는 가용 0"
                else:
                    info = avail_map[b['lot_no']]
                    b['_avail_cnt'] = info['cnt']
                    b['_avail_kg'] = info['total_kg']
        except Exception as e:
            logger.warning(f"LOT 검증 실패 (계속): {e}")

        self.batches = batches
        self.tonbag_selections = {b['id']: set() for b in batches}
        self.scan_results = {}
        self.review_reasons = {}

        warn_lots = [b for b in batches if b.get('_warn')]
        status = f"✅ {len(batches)}건 DRAFT"
        if errors:
            status += f" ({len(errors)}건 오류)"
        if warn_lots:
            status += f" ⚠️{len(warn_lots)}건 LOT 경고"
        self.parse_status_var.set(status)

        self.nb.tab(1, state='normal')
        self.nb.select(1)
        self._refresh_tab2()
        self._update_tab_badges()
        self._update_status_bar()

        logger.info(f"[S1] DRAFT 생성: {len(batches)}건")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 2: 톤백 선택 (LOT 일괄/랜덤/수동)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _build_tab2(self):
        """★ 4단계: 탭2 — Treeview 체크리스트 방식"""
        fr = self.tab2

        top = ttk.Frame(fr)
        top.pack(fill=X, padx=8, pady=5)
        ttk.Label(top, text="📦 LOT별 톤백 선택 — 🎲랜덤 또는 ✋수동 체크",
                  font=("맑은 고딕", 10, "bold")).pack(side=LEFT)
        ttk.Button(top, text="DRAFT → WAIT_SCAN  ▶",
                   command=self._confirm_draft, style='Accent.TButton').pack(side=RIGHT, padx=4, ipady=4)

        # ★ 2단계: 수량 프로그레스 바
        prog_fr = ttk.Frame(fr)
        prog_fr.pack(fill=X, padx=8, pady=(0, 3))
        self._prog_canvas = tk.Canvas(prog_fr, height=22, highlightthickness=0)
        self._prog_canvas.pack(fill=X)
        self._prog_label_var = tk.StringVar(value="")
        ttk.Label(prog_fr, textvariable=self._prog_label_var,
                  font=("맑은 고딕", 8)).pack(anchor='e')

        canvas = tk.Canvas(fr)
        scrollbar = tk.Scrollbar(fr, orient=VERTICAL, command=canvas.yview)
        self.tab2_inner = ttk.Frame(canvas)
        self.tab2_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.tab2_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        canvas.pack(fill=BOTH, expand=YES, padx=8)

        def _on_mousewheel(e):
            try:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            except tk.TclError:
                canvas.unbind_all("<MouseWheel>")
        canvas.bind("<MouseWheel>", _on_mousewheel)

        # ★ 4단계: 배치별 Treeview 저장
        self._batch_trees = {}

    def _refresh_tab2(self):
        """★ 4단계: 탭2 Treeview 체크리스트로 갱신"""
        for w in self.tab2_inner.winfo_children():
            w.destroy()

        self._tb_check_vars = {}
        self._batch_trees = {}

        for batch in self.batches:
            if batch['status'] != 'DRAFT':
                continue

            warn = batch.get('_warn', '')
            bid = batch['id']

            bf = ttk.LabelFrame(self.tab2_inner,
                                text=f"  {batch['lot_no']}  |  요청: {batch['request_qty_mt']:.3f} MT  "
                                     f"({batch['request_qty_kg']:.0f} kg)  "
                                     f"|  {batch['customer']}  {warn}")
            bf.pack(fill=X, padx=4, pady=4)

            # 버튼 바
            bb = ttk.Frame(bf)
            bb.pack(fill=X, padx=4, pady=2)

            ttk.Button(bb, text="🎲 랜덤 선택",
                       command=lambda b=bid: self._random_select(b)).pack(side=LEFT, padx=2)
            ttk.Button(bb, text="✅ LOT 전체",
                       command=lambda b=bid: self._select_all_lot(b)).pack(side=LEFT, padx=2)
            ttk.Button(bb, text="☐ 전체 해제",
                       command=lambda b=bid: self._clear_selection(b)).pack(side=LEFT, padx=2)

            sel_var = tk.StringVar(value="선택: 0개 / 0 kg")
            batch['_sel_var'] = sel_var
            ttk.Label(bb, textvariable=sel_var, font=("맑은 고딕", 9, "bold")).pack(side=RIGHT, padx=8)

            # 톤백 조회
            try:
                other_selected = set()
                for other_bid, other_sel in self.tonbag_selections.items():
                    if other_bid != bid:
                        other_selected.update(other_sel)

                tonbags = self.db.fetchall(
                    "SELECT id, lot_no, sub_lt, weight, location, tonbag_uid "
                    "FROM inventory_tonbag "
                    "WHERE lot_no=? AND status='AVAILABLE' AND COALESCE(is_sample,0)=0 "
                    "ORDER BY sub_lt",
                    (batch['lot_no'],)
                )
                tonbags = [t for t in tonbags if t['id'] not in other_selected]
            except Exception as e:
                logger.error(f"톤백 조회 실패: {e}")
                ttk.Label(bf, text=f"⚠️ 톤백 조회 실패: {e}").pack(padx=8)
                continue

            if not tonbags:
                ttk.Label(bf, text="⚠️ 가용 톤백 없음", foreground=tc('danger')).pack(padx=8, pady=4)
                continue

            total_avail_kg = sum(t['weight'] for t in tonbags)
            ttk.Label(bf, text=f"가용: {len(tonbags)}개 / {total_avail_kg:,.0f} kg",
                      font=("맑은 고딕", 8)).pack(anchor=W, padx=8)

            batch['_tonbags'] = tonbags

            # ★ 4단계: Treeview 체크리스트
            cols = ('check', 'sub_lt', 'weight', 'location', 'uid')
            tree_height = min(len(tonbags), 10)
            # v8.1.8: OutboundCheck 스타일 — rowheight 36, 폰트 10pt (체크 가시성 개선)
            _oc_style = ttk.Style()
            try:
                _oc_style.configure('OutboundCheck.Treeview',
                                    rowheight=36, font=('맑은 고딕', 10))
                _oc_style.configure('OutboundCheck.Treeview.Heading',
                                    font=('맑은 고딕', 10, 'bold'))
                _tree_style = 'OutboundCheck.Treeview'
            except Exception:
                _tree_style = None
            tree = ttk.Treeview(bf, columns=cols, show='headings', height=tree_height,
                                selectmode='none',
                                style=_tree_style if _tree_style else ttk.Treeview.__name__)
            for c, w, h in [
                ('check', 56, '☐'),   # v8.1.8: 40→56px, 헤더도 ☐ 아이콘
                ('sub_lt', 80, '#'),
                ('weight', 90, '중량(kg)'), ('location', 80, '위치'),
                ('uid', 140, 'UID'),
            ]:
                tree.heading(c, text=h, anchor='center')
                tree.column(c, width=w, anchor='center', minwidth=w)

            # 태그 설정 — 선택/미선택
            sel_bg = tc('bg_secondary') if self._is_dark else '#d1fae5'
            sel_fg = tc('success') if self._is_dark else '#065f46'
            tree.tag_configure('sel', background=sel_bg, foreground=sel_fg)
            # v9.0: background/foreground 명시 (다크 테마 대응)
            try:
                from gui_app_modular.utils.ui_constants import apply_treeview_theme, tc
                apply_treeview_theme(tree, parent=self.dialog)
            except Exception as e:
                logger.warning(f"[UI] apply treeview theme failed: {e}")
            # v8.6.5: 대비 강화 (text_muted on bg_secondary → 읽기 어려움)
            tree.tag_configure('unsel', background=tc('bg_secondary'), foreground=tc('text_secondary'))

            # 데이터 삽입
            for tb in tonbags:
                is_sel = tb['id'] in self.tonbag_selections.get(bid, set())
                check_mark = "☑" if is_sel else "☐"
                tag = 'sel' if is_sel else 'unsel'
                tree.insert('', END, iid=f"{bid}_{tb['id']}", values=(
                    check_mark,
                    tb.get('sub_lt', ''),
                    f"{tb['weight']:,.0f}",
                    tb.get('location', '') or '',
                    tb.get('tonbag_uid', '') or '',
                ), tags=(tag,))

            # 클릭 이벤트 — 토글
            tree.bind('<ButtonRelease-1>',
                      lambda e, b=bid, t=tree: self._on_tree_click(e, b, t))

            # 스크롤바
            if len(tonbags) > 10:
                sb = tk.Scrollbar(bf, orient=VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=sb.set)
                sb.pack(side=RIGHT, fill=Y, padx=(0, 4))

            tree.pack(fill=X, padx=4, pady=2)
            self._batch_trees[bid] = tree

            self._update_sel_label(bid)

    def _on_tree_click(self, event, batch_id, tree):
        """★ 4단계: Treeview 행 클릭 → 톤백 선택/해제 토글"""
        item_id = tree.identify_row(event.y)
        if not item_id:
            return

        # item_id = "batch_id_tonbag_id"
        parts = item_id.split('_', 1)
        if len(parts) < 2:
            return
        tonbag_id = int(parts[1])

        sel = self.tonbag_selections.setdefault(batch_id, set())

        if tonbag_id in sel:
            # 해제
            sel.discard(tonbag_id)
            tree.set(item_id, 'check', '☐')
            tree.item(item_id, tags=('unsel',))
        else:
            # 선택 — 중복 확인
            others = self._get_other_batch_selections(batch_id)
            if tonbag_id in others:
                CustomMessageBox.showwarning(
                    self.win, "⛔ 중복 차단",
                    f"톤백 {tonbag_id}는 다른 배치에서 이미 선택됨.\n"
                    f"먼저 해당 배치에서 해제 후 재선택하세요."
                )
                return
            sel.add(tonbag_id)
            tree.set(item_id, 'check', '☑')
            tree.item(item_id, tags=('sel',))

        self._update_sel_label(batch_id)

    # ── 톤백 선택 조작 메서드 ──

    def _get_other_batch_selections(self, exclude_batch_id):
        """다른 배치에서 이미 선택된 톤백 ID 집합 반환"""
        other = set()
        for bid, sel in self.tonbag_selections.items():
            if bid != exclude_batch_id:
                other |= sel
        return other

    def _toggle_tonbag(self, batch_id, tonbag_id, var):
        """★ 4단계: 하위 호환 — 체크박스 방식 폴백 (Treeview 모드에선 미사용)"""
        sel = self.tonbag_selections.setdefault(batch_id, set())
        if var.get():
            others = self._get_other_batch_selections(batch_id)
            if tonbag_id in others:
                var.set(False)
                CustomMessageBox.showwarning(
                    self.win, "⛔ 중복 차단",
                    f"톤백 {tonbag_id}는 다른 배치에서 이미 선택됨.\n"
                    f"먼저 해당 배치에서 해제 후 재선택하세요."
                )
                return
            sel.add(tonbag_id)
        else:
            sel.discard(tonbag_id)
        self._update_sel_label(batch_id)

    def _random_select(self, batch_id):
        """요청 수량에 맞게 랜덤 선택 — ★ 4단계: Treeview 반영"""
        batch = next((b for b in self.batches if b['id'] == batch_id), None)
        if not batch:
            return
        tonbags = batch.get('_tonbags', [])
        if not tonbags:
            return

        others = self._get_other_batch_selections(batch_id)
        available = [tb for tb in tonbags if tb['id'] not in others]
        random.shuffle(available)
        picked = set()
        remaining = batch['request_qty_kg']
        for tb in available:
            if remaining <= 0:
                break
            picked.add(tb['id'])
            remaining -= tb['weight']
        if remaining > 0:
            logger.warning(f"[S1] 랜덤선택: 충분한 톤백 부족 (잔여 {remaining:,.0f} kg)")

        self.tonbag_selections[batch_id] = picked
        self._sync_tree_checks(batch_id, tonbags)
        self._update_sel_label(batch_id)

    def _select_all_lot(self, batch_id):
        """LOT 전체 선택 — ★ 4단계: Treeview 반영"""
        batch = next((b for b in self.batches if b['id'] == batch_id), None)
        if not batch:
            return
        tonbags = batch.get('_tonbags', [])
        others = self._get_other_batch_selections(batch_id)
        picked = {tb['id'] for tb in tonbags if tb['id'] not in others}
        skipped = len(tonbags) - len(picked)
        if skipped > 0:
            logger.info(f"[S1] LOT전체선택: {skipped}건 타 배치 점유로 제외")

        self.tonbag_selections[batch_id] = picked
        self._sync_tree_checks(batch_id, tonbags)
        self._update_sel_label(batch_id)

    def _clear_selection(self, batch_id):
        """전체 해제 — ★ 4단계: Treeview 반영"""
        batch = next((b for b in self.batches if b['id'] == batch_id), None)
        if not batch:
            return
        self.tonbag_selections[batch_id] = set()
        self._sync_tree_checks(batch_id, batch.get('_tonbags', []))
        self._update_sel_label(batch_id)

    def _sync_tree_checks(self, batch_id, tonbags):
        """★ 4단계: Treeview 체크마크 + 태그 일괄 동기화"""
        tree = self._batch_trees.get(batch_id)
        sel = self.tonbag_selections.get(batch_id, set())

        if tree:
            # Treeview 모드
            for tb in tonbags:
                iid = f"{batch_id}_{tb['id']}"
                try:
                    is_sel = tb['id'] in sel
                    tree.set(iid, 'check', '☑' if is_sel else '☐')
                    tree.item(iid, tags=('sel' if is_sel else 'unsel',))
                except tk.TclError:
                    logger.debug("[SUPPRESSED] exception in onestop_outbound.py")  # noqa
        else:
            # 체크박스 모드 (폴백)
            for tb in tonbags:
                key = (batch_id, tb['id'])
                if key in self._tb_check_vars:
                    self._tb_check_vars[key].set(tb['id'] in sel)

    def _update_sel_label(self, batch_id):
        """선택 현황 라벨 업데이트 + ★ 2단계: 프로그레스 바 갱신"""
        batch = next((b for b in self.batches if b['id'] == batch_id), None)
        if not batch or '_sel_var' not in batch:
            return
        sel_ids = self.tonbag_selections.get(batch_id, set())
        tonbags = batch.get('_tonbags', [])
        sel_kg = sum(tb['weight'] for tb in tonbags if tb['id'] in sel_ids)
        batch['_sel_var'].set(f"선택: {len(sel_ids)}개 / {sel_kg:,.0f} kg")

        # ★ 2단계: 전체 프로그레스 바 갱신
        self._update_progress_bar()

    def _update_progress_bar(self):
        """★ 2-2: 전체 요청 vs 선택 수량 프로그레스 바"""
        c = getattr(self, '_prog_canvas', None)
        if not c:
            return
        c.delete('all')
        w = c.winfo_width() or 400

        total_req = sum(b['request_qty_kg'] for b in self.batches if b['status'] == 'DRAFT')
        total_sel = 0
        for b in self.batches:
            if b['status'] != 'DRAFT':
                continue
            sel_ids = self.tonbag_selections.get(b['id'], set())
            tonbags = b.get('_tonbags', [])
            total_sel += sum(tb['weight'] for tb in tonbags if tb['id'] in sel_ids)

        if total_req <= 0:
            return

        ratio = total_sel / total_req
        bar_w = min(int(w * ratio), w)

        # 색상: 충분=초록, 부족=노랑, 초과=빨강
        if ratio >= 1.0:
            color = '#059669' if ratio <= 1.05 else '#dc2626'
        elif ratio >= 0.5:
            color = '#d97706'
        else:
            color = '#ef4444'

        track_color = '#334155' if self._is_dark else '#e5e7eb'
        c.create_rectangle(0, 0, w, 22, fill=track_color, outline='')
        c.create_rectangle(0, 0, bar_w, 22, fill=color, outline='')
        c.create_text(w // 2, 11, text=f"{total_sel:,.0f} / {total_req:,.0f} kg ({ratio:.0%})",
                      fill='white' if bar_w > w * 0.4 else ('#e2e8f0' if self._is_dark else '#1f2937'),
                      font=('맑은 고딕', 10, 'bold'))

        self._prog_label_var.set(
            f"{'✅ 충분' if 0.95 <= ratio <= 1.05 else '⚠️ 부족' if ratio < 0.95 else '🔴 초과'}")

    def _confirm_draft(self):
        """DRAFT → WAIT_SCAN 전환 (톤백 PICKED 처리)"""
        drafts = [b for b in self.batches if b['status'] == 'DRAFT']
        if not drafts:
            CustomMessageBox.showwarning(self.win, "경고", "DRAFT 배치가 없습니다.")
            return

        no_sel = [b for b in drafts if not self.tonbag_selections.get(b['id'])]
        if no_sel:
            lots = ", ".join(b['lot_no'] for b in no_sel)
            CustomMessageBox.showwarning(self.win, "톤백 미선택",
                                          f"다음 LOT에 톤백이 선택되지 않았습니다:\n{lots}")
            return

        # 배치별 배정 수량 계산
        for batch in drafts:
            sel_ids = self.tonbag_selections.get(batch['id'], set())
            tonbags = batch.get('_tonbags', [])
            alloc_kg = sum(tb['weight'] for tb in tonbags if tb['id'] in sel_ids)
            batch['allocated_qty_kg'] = alloc_kg
            batch['selected_tonbags'] = list(sel_ids)

        # DB: AVAILABLE → PICKED
        try:
            now_str = datetime.now().isoformat()
            wait_count = 0
            for batch in drafts:
                for tb_id in batch['selected_tonbags']:
                    self.db.execute(
                        "UPDATE inventory_tonbag SET status='PICKED', picked_to=?, "
                        "picked_date=?, sale_ref=?, updated_at=? WHERE id=?",
                        (batch['id'], date.today().isoformat(), batch['sale_ref'], now_str, tb_id)
                    )
                batch['status'] = 'WAIT_SCAN'
                wait_count += 1

            self.db.conn.commit()
            logger.info(f"[S1] {wait_count}건 DRAFT→WAIT_SCAN, 톤백 PICKED 처리 완료")
        except Exception as e:
            logger.error(f"[S1] PICKED 전환 실패: {e}", exc_info=True)
            CustomMessageBox.showerror(self.win, "오류", f"PICKED 전환 실패:\n{e}")
            return

        # 탭3 활성화 & 이동
        self.nb.tab(2, state='normal')
        self.nb.select(2)
        self._refresh_tab3()
        self._update_footer()

        # ★ 2단계: 토스트 메시지로 교체
        self._show_toast(f"✅ {wait_count}건 → WAIT_SCAN  |  톤백 PICKED 완료")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 3: 스캔 검증 (상태 머신)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _build_tab3(self):
        fr = self.tab3

        top = ttk.Frame(fr)
        top.pack(fill=X, padx=8, pady=5)
        ttk.Label(top, text="🔍 스캔 검증 — actual vs expected",
                  font=("맑은 고딕", 10, "bold")).pack(side=LEFT)
        ttk.Button(top, text="⚡ 전체 검증 실행",
                   command=self._finalize_all, style='Accent.TButton').pack(side=RIGHT, padx=4, ipady=4)

        # 규칙 안내
        rule_fr = ttk.LabelFrame(fr, text="검증 규칙")
        rule_fr.pack(fill=X, padx=8, pady=3)
        ttk.Label(rule_fr,
                  text="actual = expected → ✅ FINALIZED  |  actual < expected → ⚠️ REVIEW  |  actual > expected → ⛔ ERROR (하드스톱)",
                  font=("맑은 고딕", 9)).pack(padx=8, pady=3)

        # ★ v2.2 OUT 스캔 파일 업로드
        out_fr = ttk.LabelFrame(fr, text="📊 OUT 스캔 파일 (csv/xlsx)")
        out_fr.pack(fill=X, padx=8, pady=3)

        out_btn_fr = ttk.Frame(out_fr)
        out_btn_fr.pack(fill=X, padx=4, pady=2)
        ttk.Button(out_btn_fr, text="📂 파일 불러오기",
                   command=self._load_out_scan_file).pack(side=LEFT, padx=2)
        self.out_scan_status_var = tk.StringVar(value="파일 미선택")
        ttk.Label(out_btn_fr, textvariable=self.out_scan_status_var,
                  font=("맑은 고딕", 8)).pack(side=LEFT, padx=8)

        # ★ v2.2 미매칭 경고 라벨
        self.unmatched_var = tk.StringVar(value="")
        unmatched_color = self._status_colors.get('ERROR', '#dc2626')
        self.unmatched_label = ttk.Label(out_fr, textvariable=self.unmatched_var,
                                         font=("맑은 고딕", 9), foreground=unmatched_color)
        self.unmatched_label.pack(fill=X, padx=4, pady=1)

        # ★ 2단계 2-4: 수동 actual 입력
        manual_fr = ttk.LabelFrame(fr, text="✏️ 수동 실제수량 입력 (OUT 파일 없을 때)")
        manual_fr.pack(fill=X, padx=8, pady=3)
        manual_inner = ttk.Frame(manual_fr)
        manual_inner.pack(fill=X, padx=4, pady=2)
        ttk.Label(manual_inner, text="LOT NO:", font=("맑은 고딕", 9)).pack(side=LEFT, padx=2)
        self._manual_lot_var = tk.StringVar()
        ttk.Combobox(manual_inner, textvariable=self._manual_lot_var,
                     width=18, state='readonly').pack(side=LEFT, padx=2)
        ttk.Label(manual_inner, text="실제(kg):", font=("맑은 고딕", 9)).pack(side=LEFT, padx=(8, 2))
        self._manual_kg_var = tk.StringVar()
        ttk.Entry(manual_inner, textvariable=self._manual_kg_var, width=12).pack(side=LEFT, padx=2)
        ttk.Button(manual_inner, text="적용", command=self._apply_manual_actual).pack(side=LEFT, padx=4)

        # 트리뷰
        cols = ('lot_no', 'customer', 'request_kg', 'alloc_kg', 'actual_kg', 'diff_kg', 'status', 'action')
        self.tab3_tree = ttk.Treeview(fr, columns=cols, show='headings', height=12)
        for c, w, h in [
            ('lot_no', 120, 'LOT NO'), ('customer', 100, '거래처'),
            ('request_kg', 90, '요청(kg)'), ('alloc_kg', 90, '배정(kg)'),
            ('actual_kg', 90, '실제(kg)'), ('diff_kg', 80, '차이(kg)'),
            ('status', 100, '상태'), ('action', 80, '조치'),
        ]:
            self.tab3_tree.heading(c, text=h, anchor='center')
            self.tab3_tree.column(c, width=w, anchor='center')
        self.tab3_tree.pack(fill=BOTH, expand=YES, padx=8, pady=5)
        self.tab3_tree.bind('<Double-1>', self._on_tab3_double_click)

        # 하단 버튼
        bot = ttk.Frame(fr)
        bot.pack(fill=X, padx=8, pady=5)
        self.tab3_status_var = tk.StringVar(value="")
        ttk.Label(bot, textvariable=self.tab3_status_var, font=("맑은 고딕", 9)).pack(side=LEFT)
        ttk.Button(bot, text="📦 확정건 출고 완료  ▶",
                   command=self._move_to_completed, style='Accent.TButton').pack(side=RIGHT, padx=4, ipady=4)

    # ── OUT 스캔 파일 관련 메서드 ──

    def _load_out_scan_file(self):
        """OUT 스캔 파일 (csv/tsv/xlsx) 로드 → 배치별 actual_qty 산출 + 미매칭 감지"""
        fpath = filedialog.askopenfilename(
            parent=self.win,
            title="OUT 스캔 파일 선택",
            filetypes=[
                ("스캔 파일", "*.csv *.tsv *.txt *.xlsx *.xls"),
                ("Excel", "*.xlsx *.xls"),
                ("CSV/TSV", "*.csv *.tsv *.txt"),
            ]
        )
        if not fpath:
            return

        try:
            records = self._parse_scan_file(fpath)
        except Exception as e:
            logger.error(f"[S1] OUT 파일 파싱 실패: {e}", exc_info=True)
            CustomMessageBox.showerror(self.win, "파싱 오류", f"OUT 파일 파싱 실패:\n{e}")
            return

        if not records:
            CustomMessageBox.showwarning(self.win, "경고", "유효한 레코드가 없습니다.")
            return

        # ── 배치별 actual_qty 매칭 ──
        # selected_tonbags는 내부적으로 DB id(int)를 사용하지만,
        # OUT 파일은 tonbag_uid 문자열로 들어오는 경우가 많아 id/uid 둘 다 매칭한다.
        all_selected_by_id = {}   # "id(str)" -> batch_id
        all_selected_by_uid = {}  # "uid(str)" -> batch_id
        selected_ids = []
        for batch in self.batches:
            for tb_id in batch.get('selected_tonbags', []):
                tb_id_str = str(tb_id).strip()
                if not tb_id_str:
                    continue
                all_selected_by_id[tb_id_str] = batch['id']
                selected_ids.append(tb_id)

        if selected_ids:
            try:
                placeholders = ",".join("?" for _ in selected_ids)
                uid_rows = self.db.fetchall(
                    "SELECT id, tonbag_uid FROM inventory_tonbag "
                    f"WHERE id IN ({placeholders})",
                    tuple(selected_ids),
                )
                for row in uid_rows:
                    uid = str(row.get('tonbag_uid') or '').strip()
                    if not uid:
                        continue
                    bid = all_selected_by_id.get(str(row.get('id')).strip())
                    if bid:
                        all_selected_by_uid[uid] = bid
            except Exception as e:
                logger.warning(f"[S1] OUT 매칭용 UID 조회 실패 (id 매칭만 사용): {e}")

        batch_scan_kg = {}
        unmatched = []

        for rec in records:
            tb_id = rec.get('tonbag_id', '').strip()
            weight = rec.get('weight', 0)
            if not tb_id:
                continue

            bid = all_selected_by_id.get(tb_id) or all_selected_by_uid.get(tb_id)
            if bid:
                batch_scan_kg[bid] = batch_scan_kg.get(bid, 0) + weight
            else:
                unmatched.append(rec)

        # ── 배치에 actual 반영 ──
        for batch in self.batches:
            if batch['status'] not in ('WAIT_SCAN', 'DRAFT'):
                continue
            if batch['id'] in batch_scan_kg:
                batch['actual_qty_kg'] = batch_scan_kg[batch['id']]
                batch['scan_diff_kg'] = batch['actual_qty_kg'] - batch['request_qty_kg']

        # ── 결과 표시 ──
        matched = len(records) - len(unmatched)
        fname = os.path.basename(fpath)
        self.out_scan_data = {
            'file': fname, 'total': len(records),
            'matched': matched, 'unmatched': len(unmatched),
        }
        self.out_scan_status_var.set(
            f"📊 {fname} — 전체: {len(records)}건 | "
            f"매칭: {matched} | 미매칭: {len(unmatched)}")

        # ★ 미매칭 경고
        self.unmatched_tonbags = unmatched
        if unmatched:
            ids = ', '.join(u.get('tonbag_id', '?') for u in unmatched[:5])
            suffix = f" 외 {len(unmatched)-5}건" if len(unmatched) > 5 else ""
            self.unmatched_var.set(
                f"⛔ 미매칭 {len(unmatched)}건 — 무단 출고 의심!  [{ids}{suffix}]")
            logger.warning(f"[S1] ⛔ 미매칭 톤백 {len(unmatched)}건: {ids}{suffix}")

            # ★ Q2: 미매칭 이벤트 DB 기록
            for u in unmatched:
                self._write_audit(
                    event_type='UNMATCHED_SCAN',
                    event_data={
                        'tonbag_id': u.get('tonbag_id'),
                        'weight': u.get('weight', 0),
                        'scan_file': fname,
                    },
                    tonbag_id=u.get('tonbag_id'),
                    user_note=f"OUT 스캔 미매칭 — 무단 출고 의심 ({fname})"
                )
            logger.info(f"[S1] audit_log: UNMATCHED_SCAN {len(unmatched)}건 기록 완료")
        else:
            self.unmatched_var.set("")

        logger.info(f"[S1] OUT 파일 로드: {fname} → {matched}/{len(records)} 매칭")

    def _parse_scan_file(self, fpath):
        """csv/tsv/xlsx 파싱 → [{tonbag_id, weight, ...}]"""
        ext = os.path.splitext(fpath)[1].lower()
        if ext in ('.xlsx', '.xls') and HAS_OPENPYXL:
            return self._parse_xlsx(fpath)
        else:
            return self._parse_csv(fpath)

    def _parse_xlsx(self, fpath):
        """openpyxl로 xlsx 파싱"""
        wb = openpyxl.load_workbook(fpath, data_only=True, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()

        if not rows:
            return []

        header = [str(c).strip().lower() if c else '' for c in rows[0]]
        tb_col = self._find_col(header, ['tonbag_id', 'tonbag', 'tb_id', 'id', '톤백'])
        wt_col = self._find_col(header, ['weight', 'kg', '무게', '중량', 'net_weight'])

        records = []
        start = 1 if tb_col is not None else 0
        if tb_col is None:
            tb_col, wt_col = 0, 1

        for row in rows[start:]:
            if not row or len(row) <= max(tb_col, wt_col or 0):
                continue
            tb_id = str(row[tb_col]).strip() if row[tb_col] else ''
            weight = 0
            if wt_col is not None and row[wt_col]:
                try:
                    weight = float(str(row[wt_col]).replace(',', ''))
                except (ValueError, TypeError):
                    logger.debug("[SUPPRESSED] exception in onestop_outbound.py")  # noqa
            if tb_id:
                records.append({'tonbag_id': tb_id, 'weight': weight})

        return records

    def _parse_csv(self, fpath):
        """csv/tsv 파싱"""
        with open(fpath, 'r', encoding='utf-8-sig') as f:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=',\t|;')
            reader = csv.reader(f, dialect)
            rows = list(reader)

        if not rows:
            return []

        header = [c.strip().lower() for c in rows[0]]
        tb_col = self._find_col(header, ['tonbag_id', 'tonbag', 'tb_id', 'id', '톤백'])
        wt_col = self._find_col(header, ['weight', 'kg', '무게', '중량'])

        records = []
        start = 1 if tb_col is not None else 0
        if tb_col is None:
            tb_col, wt_col = 0, 1

        for row in rows[start:]:
            if not row or len(row) <= tb_col:
                continue
            tb_id = row[tb_col].strip()
            weight = 0
            if wt_col is not None and len(row) > wt_col:
                try:
                    weight = float(row[wt_col].replace(',', ''))
                except (ValueError, TypeError):
                    logger.debug("[SUPPRESSED] exception in onestop_outbound.py")  # noqa
            if tb_id:
                records.append({'tonbag_id': tb_id, 'weight': weight})

        return records

    @staticmethod
    def _find_col(header, candidates):
        """헤더에서 후보 컬럼명 매칭"""
        for i, h in enumerate(header):
            for cand in candidates:
                if cand in h:
                    return i
        return None

    # ── 스캔 검증 메서드 ──

    def _refresh_tab3(self):
        """탭3 트리뷰 갱신 — ★ 1단계: 행별 상태 배경색 + 배지 업데이트"""
        tree = self.tab3_tree

        # ★ 1단계: 상태별 행 배경색 태그 설정
        tree.tag_configure('row_FINALIZED', background=tc('available'), foreground=tc('success'))
        tree.tag_configure('row_REVIEW_REQUIRED', background=tc('picked'), foreground=tc('danger'))
        tree.tag_configure('row_ERROR', background=tc('bg_secondary'), foreground=tc('danger'))
        tree.tag_configure('row_WAIT_SCAN', background=tc('shipped'), foreground=tc('info'))
        # ★ 다크모드 대응
        try:
            from theme_aware import ThemeAware
            if ThemeAware.is_dark():
                tree.tag_configure('row_FINALIZED', background=tc('bg_secondary'), foreground=tc('success'))
                tree.tag_configure('row_REVIEW_REQUIRED', background=tc('bg_secondary'), foreground=tc('warning'))
                tree.tag_configure('row_ERROR', background=tc('bg_secondary'), foreground=tc('danger'))
                tree.tag_configure('row_WAIT_SCAN', background=tc('bg_secondary'), foreground=tc('info'))
        except (ImportError, Exception):
            logger.debug("[SUPPRESSED] exception in onestop_outbound.py")  # noqa

        tree.delete(*tree.get_children())

        for batch in self.batches:
            if batch['status'] not in ('WAIT_SCAN', 'FINALIZED', 'REVIEW_REQUIRED', 'ERROR'):
                continue

            actual = batch.get('actual_qty_kg')
            diff = batch.get('scan_diff_kg')

            actual_str = f"{actual:,.0f}" if actual is not None else "(미스캔)"
            diff_str = f"{diff:+,.0f}" if diff is not None else "—"

            action = ""
            if batch['status'] == 'REVIEW_REQUIRED':
                action = "더블클릭→사유"
            elif batch['status'] == 'ERROR':
                action = "더블클릭→정정"

            # ★ 1단계: 상태별 태그 적용
            row_tag = f"row_{batch['status']}"
            tree.insert('', END, iid=batch['id'], values=(
                batch['lot_no'], batch['customer'],
                f"{batch['request_qty_kg']:,.0f}", f"{batch['allocated_qty_kg']:,.0f}",
                actual_str, diff_str,
                BATCH_STATUS.get(batch['status'], batch['status']),
                action,
            ), tags=(row_tag,))

        fin = sum(1 for b in self.batches if b['status'] == 'FINALIZED')
        rev = sum(1 for b in self.batches if b['status'] == 'REVIEW_REQUIRED')
        err = sum(1 for b in self.batches if b['status'] == 'ERROR')
        wscan = sum(1 for b in self.batches if b['status'] == 'WAIT_SCAN')
        self.tab3_status_var.set(
            f"스캔대기: {wscan} | 확정: {fin} | 확인대기: {rev} | 오류: {err}")

        # ★ 1단계: 탭 배지 + 상태 바 갱신
        self._update_tab_badges()
        self._update_status_bar()
        # ★ 2단계: 수동 입력 콤보 갱신
        self._update_manual_lot_combo()

    def _finalize_all(self):
        """전체 WAIT_SCAN 배치 검증 실행"""
        processed = 0
        for batch in self.batches:
            if batch['status'] != 'WAIT_SCAN':
                continue

            # ★ v2.2: OUT 파일 데이터 우선, 없으면 allocated = actual (폴백)
            if batch.get('actual_qty_kg') is not None:
                actual_kg = batch['actual_qty_kg']
            else:
                actual_kg = batch['allocated_qty_kg']
                batch['actual_qty_kg'] = actual_kg

            diff = actual_kg - batch['request_qty_kg']
            batch['scan_diff_kg'] = diff

            if diff > 0:
                batch['status'] = 'ERROR'
                logger.warning(f"[S1] ⛔ 하드스톱: {batch['lot_no']} actual({actual_kg}) > expected({batch['request_qty_kg']})")
            elif diff < 0:
                batch['status'] = 'REVIEW_REQUIRED'
                logger.info(f"[S1] ⚠️ REVIEW: {batch['lot_no']} 부족 {diff:+,.0f} kg")
            else:
                batch['status'] = 'FINALIZED'
                logger.info(f"[S1] ✅ FINALIZED: {batch['lot_no']} 수량 일치")

            processed += 1

        self._refresh_tab3()

        if processed > 0:
            if any(b['status'] == 'FINALIZED' for b in self.batches):
                self.nb.tab(3, state='normal')

    def _on_tab3_double_click(self, event):
        """더블클릭: REVIEW_REQUIRED → 사유 선택, ERROR → 정정"""
        sel = self.tab3_tree.selection()
        if not sel:
            return
        batch_id = sel[0]
        batch = next((b for b in self.batches if b['id'] == batch_id), None)
        if not batch:
            return

        if batch['status'] == 'REVIEW_REQUIRED':
            self._show_review_dialog(batch)
        elif batch['status'] == 'ERROR':
            self._show_error_correction(batch)

    def _show_review_dialog(self, batch):
        """수량 부족 사유 선택 다이얼로그"""
        dlg = create_themed_toplevel(self.win)
        dlg.title(f"⚠️ 사유 선택 — {batch['lot_no']}")
        dlg.transient(self.win)
        dlg.resizable(True, True)  # v9.0: 크기 조절 허용
        dlg.minsize(400, 300)  # v9.0: 최소 크기
        dlg.grab_set()
        dlg.resizable(True, True)  # v9.0: 크기 조절 허용
        dlg.minsize(400, 300)  # v9.0: 최소 크기
        setup_dialog_geometry_persistence(dlg, "onestop_outbound_review_dialog", self.win, "small")

        ttk.Label(dlg, text=f"LOT: {batch['lot_no']}", font=("맑은 고딕", 11, "bold")).pack(pady=8)
        ttk.Label(dlg, text=f"요청: {batch['request_qty_kg']:,.0f} kg  →  실제: {batch['actual_qty_kg']:,.0f} kg  "
                            f"(차이: {batch['scan_diff_kg']:+,.0f} kg)",
                  font=("맑은 고딕", 9)).pack(pady=4)

        reason_var = tk.StringVar()
        for r in SHORTAGE_REASONS:
            ttk.Radiobutton(dlg, text=r, variable=reason_var, value=r).pack(anchor=W, padx=20, pady=2)

        def approve():
            reason = reason_var.get()
            if not reason:
                CustomMessageBox.showwarning(dlg, "경고", "사유를 선택해주세요.")
                return
            batch['status'] = 'FINALIZED'
            batch['review_reason'] = reason
            self.review_reasons[batch['id']] = reason
            self.nb.tab(3, state='normal')
            logger.info(f"[S1] REVIEW→FINALIZED: {batch['lot_no']} 사유='{reason}'")
            dlg.destroy()
            self._refresh_tab3()

        ttk.Button(dlg, text="✅ 승인 → FINALIZED", command=approve).pack(pady=10)

    def _show_error_correction(self, batch):
        """하드스톱 정정 다이얼로그"""
        msg = (f"⛔ 하드스톱: {batch['lot_no']}\n\n"
               f"요청: {batch['request_qty_kg']:,.0f} kg\n"
               f"실제: {batch['actual_qty_kg']:,.0f} kg\n"
               f"초과: +{batch['scan_diff_kg']:,.0f} kg\n\n"
               f"정정 이벤트를 생성하시겠습니까?\n"
               f"(REVIEW_REQUIRED로 전환 후 사유 선택 가능)")

        if CustomMessageBox.askyesno(self.win, "⛔ 정정 이벤트", msg):
            batch['status'] = 'REVIEW_REQUIRED'
            batch['corrected'] = True
            logger.info(f"[S1] ERROR→REVIEW: {batch['lot_no']} 정정 이벤트")
            self._refresh_tab3()

    def _move_to_completed(self):
        """FINALIZED 건 → 출고 완료 (SOLD)"""
        finalized = [b for b in self.batches if b['status'] == 'FINALIZED']
        if not finalized:
            CustomMessageBox.showwarning(self.win, "경고", "확정된 배치가 없습니다.")
            return

        # DB: PICKED → SOLD
        try:
            now_str = datetime.now().isoformat()
            sold_count = 0
            for batch in finalized:
                for tb_id in batch['selected_tonbags']:
                    self.db.execute(
                        "UPDATE inventory_tonbag SET status='OUTBOUND', "
                        "outbound_date=?, updated_at=? WHERE id=? AND status='PICKED'",
                        (date.today().isoformat(), now_str, tb_id)
                    )
                    sold_count += 1

                batch['status'] = 'COMPLETED'
                batch['completed_at'] = now_str
                # ★ Q3: 근거문서 경로 배치에 기록
                batch['proof_docs'] = [
                    {'name': d['name'], 'path': d['stored_path'], 'hash': d['hash']}
                    for d in self.proof_docs
                ]
                self.completed.append(batch)

            self.db.conn.commit()
            logger.info(f"[S1] {len(finalized)}건 출고 완료, {sold_count}개 톤백 SOLD")

            # ★ Q2: 출고 완료 이벤트 기록
            for batch in finalized:
                self._write_audit(
                    event_type='OUTBOUND_SOLD',
                    event_data={
                        'lot_no': batch['lot_no'],
                        'customer': batch['customer'],
                        'request_qty_kg': batch['request_qty_kg'],
                        'actual_qty_kg': batch.get('actual_qty_kg', batch['allocated_qty_kg']),
                        'tonbag_count': len(batch.get('selected_tonbags', [])),
                        'review_reason': batch.get('review_reason'),
                        'corrected': batch.get('corrected', False),
                    },
                    batch_id=batch['id'],
                    user_note=f"S1 원스톱 출고 완료: {batch['lot_no']} → {batch['customer']}"
                )

        except Exception as e:
            logger.error(f"[S1] SOLD 전환 실패: {e}", exc_info=True)
            CustomMessageBox.showerror(self.win, "오류", f"출고 완료 실패:\n{e}")
            return

        # 배치 목록에서 제거
        self.batches = [b for b in self.batches if b['status'] != 'COMPLETED']

        # 탭4 활성화 & 이동
        self.nb.tab(3, state='normal')
        self.nb.select(3)
        self._refresh_tab4()

        # 메인 앱 새로고침
        try:
            self.app._refresh_after_outbound_action("S1_onestop_outbound")
        except Exception as e:
            logger.warning(f"[UI] refresh after outbound action failed: {e}")

        CustomMessageBox.showinfo(self.win, "🚚 출고 완료",
                                  f"{len(finalized)}건 출고 완료!\n{sold_count}개 톤백 → SOLD")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TAB 4: 완료 이력
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _build_tab4(self):
        fr = self.tab4

        ttk.Label(fr, text="✅ 출고 완료 이력", font=("맑은 고딕", 10, "bold")).pack(padx=8, pady=8, anchor=W)

        cols = ('lot_no', 'customer', 'request', 'actual', 'diff', 'tonbags', 'docs', 'reason', 'time')
        self.tab4_tree = ttk.Treeview(fr, columns=cols, show='headings', height=10)
        for c, w, h in [
            ('lot_no', 110, 'LOT NO'), ('customer', 90, '거래처'),
            ('request', 80, '요청(kg)'), ('actual', 80, '실제(kg)'),
            ('diff', 70, '차이'), ('tonbags', 50, '톤백'),
            ('docs', 40, '📎'), ('reason', 130, '사유'), ('time', 130, '완료시간'),
        ]:
            self.tab4_tree.heading(c, text=h, anchor='center')
            self.tab4_tree.column(c, width=w, anchor='center')
        self.tab4_tree.pack(fill=BOTH, expand=YES, padx=8, pady=5)

        # ★ 3단계 3-1: 요약 → 숫자 카드형 대시보드
        card_fr = ttk.Frame(fr)
        card_fr.pack(fill=X, padx=8, pady=5)

        self._card_count = tk.StringVar(value="0")
        self._card_kg = tk.StringVar(value="0")
        self._card_tb = tk.StringVar(value="0")

        for var, label, color in [
            (self._card_count, "총 건수", "#2563eb"),
            (self._card_kg, "총 중량(kg)", "#059669"),
            (self._card_tb, "총 톤백", "#7c3aed"),
        ]:
            card = tk.Frame(card_fr, bg=color, padx=16, pady=8)
            card.pack(side=LEFT, expand=YES, fill=X, padx=4)
            tk.Label(card, textvariable=var, bg=color, fg=tc('text_primary'),
                     font=('맑은 고딕', 20, 'bold')).pack()
            tk.Label(card, text=label, bg=color, fg=tc('text_primary'),
                     font=('맑은 고딕', 10)).pack()

        # 기존 요약 (하위 호환)
        self.tab4_summary_var = tk.StringVar(value="")

        # 버튼
        bot = ttk.Frame(fr)
        bot.pack(fill=X, padx=8, pady=5)
        ttk.Button(bot, text="📋 새 출고 시작",
                   command=self._restart).pack(side=LEFT, padx=4)
        ttk.Button(bot, text="📋 감사 로그 보기",
                   command=self._show_audit_log_viewer).pack(side=LEFT, padx=4)
        ttk.Button(bot, text="닫기", command=self.win.destroy).pack(side=RIGHT, padx=4)

    def _refresh_tab4(self):
        tree = self.tab4_tree
        tree.delete(*tree.get_children())
        for b in self.completed:
            reason = b.get('review_reason', '수량일치')
            if b.get('corrected'):
                reason += " [정정]"
            doc_count = len(b.get('proof_docs', []))
            tree.insert('', END, values=(
                b['lot_no'], b['customer'],
                f"{b['request_qty_kg']:,.0f}",
                f"{b.get('actual_qty_kg', b['allocated_qty_kg']):,.0f}",
                f"{b.get('scan_diff_kg', 0):+,.0f}",
                len(b.get('selected_tonbags', [])),
                f"{doc_count}건" if doc_count > 0 else "—",
                reason,
                b.get('completed_at', '')[:19],
            ))

        total_kg = sum(b.get('actual_qty_kg', b['allocated_qty_kg']) for b in self.completed)
        total_tb = sum(len(b.get('selected_tonbags', [])) for b in self.completed)
        self.tab4_summary_var.set(
            f"총 {len(self.completed)}건  |  {total_kg:,.0f} kg  |  {total_tb}개 톤백")

        # ★ 3단계: 숫자 카드 갱신
        self._card_count.set(str(len(self.completed)))
        self._card_kg.set(f"{total_kg:,.0f}")
        self._card_tb.set(str(total_tb))

        # ★ 1단계: 배지 갱신
        self._update_tab_badges()
        self._update_status_bar()

    def _restart(self):
        """새 출고 시작"""
        self.batches = []
        self.tonbag_selections = {}
        self.scan_results = {}
        self.review_reasons = {}
        # ★ v2.2 상태 초기화
        self.proof_docs = []
        self.proof_hashes.clear()
        self.out_scan_data = None
        self.unmatched_tonbags = []
        # UI 초기화
        self.paste_text.delete('1.0', END)
        self._show_placeholder()
        self.parse_status_var.set("")
        self.proof_listbox.delete(0, END)
        self.proof_status_var.set("첨부 없음")
        self.out_scan_status_var.set("파일 미선택")
        self.unmatched_var.set("")
        self.nb.tab(0, text=self._tab_titles[0])
        self.nb.tab(1, text=self._tab_titles[1])
        self.nb.tab(2, text=self._tab_titles[2])
        self.nb.tab(3, text=self._tab_titles[3])
        self.nb.tab(1, state='disabled')
        self.nb.tab(2, state='disabled')
        self.nb.tab(3, state='disabled')
        self.nb.select(0)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 감사 로그 뷰어 + CSV 내보내기
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _show_audit_log_viewer(self):
        """감사 로그 조회 Toplevel 팝업"""
        dlg = create_themed_toplevel(self.win)
        dlg.title("📋 감사 로그 — audit_log")
        dlg.transient(self.win)
        dlg.resizable(True, True)  # v9.0: 크기 조절 허용
        dlg.minsize(400, 300)  # v9.0: 최소 크기
        setup_dialog_geometry_persistence(dlg, "onestop_outbound_audit_log", self.win, "large")

        # ── 상단: 필터 바 ──
        filter_fr = ttk.LabelFrame(dlg, text="필터")
        filter_fr.pack(fill=X, padx=8, pady=5)

        row1 = ttk.Frame(filter_fr)
        row1.pack(fill=X, padx=4, pady=3)

        ttk.Label(row1, text="이벤트 유형:").pack(side=LEFT, padx=2)
        event_var = tk.StringVar(value="전체")
        event_combo = ttk.Combobox(row1, textvariable=event_var, width=18,
                                    values=["전체", "UNMATCHED_SCAN", "PROOF_ATTACH",
                                            "OUTBOUND_SOLD", "PROOF_CLEANUP", "AUDIT_EXPORT"],
                                    state='readonly')
        event_combo.pack(side=LEFT, padx=4)

        # v8.6.3: 공통 날짜 범위 바 통일 적용
        try:
            from ..utils.tree_enhancements import make_date_range_bar
            _db, date_from_var, date_to_var = make_date_range_bar(
                row1, lambda: None,
                default_from='today', default_to='today')
            _db.pack(side=LEFT, padx=(12,2))
        except Exception:
            date_from_var = tk.StringVar(value=date.today().isoformat())
            date_from_entry = ttk.Entry(row1, textvariable=date_from_var, width=12)
            date_from_entry.pack(side=LEFT, padx=2)
        try:
            from gui_app_modular.utils.tree_enhancements import attach_date_placeholder
            attach_date_placeholder(date_from_entry, date_from_var)
        except Exception as e:
            logger.warning(f'[UI] onestop_outbound: {e}')
        ttk.Label(row1, text="종료일:").pack(side=LEFT, padx=(8, 2))
        date_to_var = tk.StringVar(value=date.today().isoformat())
        date_to_entry = ttk.Entry(row1, textvariable=date_to_var, width=12)
        date_to_entry.pack(side=LEFT, padx=2)
        try:
            from gui_app_modular.utils.tree_enhancements import attach_date_placeholder
            attach_date_placeholder(date_to_entry, date_to_var)
        except Exception as e:
            logger.warning(f'[UI] onestop_outbound: {e}')
        # ── 트리뷰 ──
        cols = ('id', 'event_type', 'batch_id', 'tonbag_id', 'user_note', 'created_at')
        tree = ttk.Treeview(dlg, columns=cols, show='headings', height=16)
        for c, w, h in [
            ('id', 50, 'ID'), ('event_type', 130, '이벤트'),
            ('batch_id', 100, '배치ID'), ('tonbag_id', 100, '톤백ID'),
            ('user_note', 280, '메모'), ('created_at', 150, '시간'),
        ]:
            tree.heading(c, text=h, anchor='center')
            tree.column(c, width=w, anchor='center' if w < 120 else W)
        tree.pack(fill=BOTH, expand=YES, padx=8, pady=5)

        vsb = tk.Scrollbar(dlg, orient=VERTICAL, command=tree.yview)
        xsb = tk.Scrollbar(dlg, orient=HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=xsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        xsb.pack(side=BOTTOM, fill=X)

        status_var = tk.StringVar(value="")
        ttk.Label(dlg, textvariable=status_var,
                  font=("맑은 고딕", 9)).pack(padx=8, pady=2, anchor=W)

        # ── 상세보기 (더블클릭) ──
        def on_double_click(event):
            sel = tree.selection()
            if not sel:
                return
            row_id = tree.item(sel[0], 'values')[0]
            try:
                row = self.db.fetchone(
                    "SELECT * FROM audit_log WHERE id=?", (int(row_id),))
                if row:
                    detail = (
                        f"ID: {row['id']}\n"
                        f"이벤트: {row['event_type']}\n"
                        f"배치ID: {row.get('batch_id', '—')}\n"
                        f"톤백ID: {row.get('tonbag_id', '—')}\n"
                        f"메모: {row.get('user_note', '—')}\n"
                        f"시간: {row['created_at']}\n"
                        f"작성자: {row.get('created_by', '—')}\n"
                        f"─────────────────\n"
                        f"상세 데이터 (JSON):\n{row.get('event_data', '—')}"
                    )
                    CustomMessageBox.showinfo(dlg, "📋 감사 로그 상세", detail)
            except Exception as e:
                logger.error(f"[S1] audit 상세 조회 실패: {e}")

        tree.bind('<Double-1>', on_double_click)

        # ── 조회 함수 ──
        def do_search():
            tree.delete(*tree.get_children())
            evt = event_var.get()
            try:
                from gui_app_modular.utils.tree_enhancements import parse_date_range as _pdr
                d_from, d_to = _pdr(date_from_var.get().strip(), date_to_var.get().strip())
                d_from = d_from or ''
                d_to   = d_to   or ''
            except Exception:
                d_from = date_from_var.get().strip()
                d_to   = date_to_var.get().strip()

            sql = "SELECT id, event_type, batch_id, tonbag_id, user_note, created_at FROM audit_log WHERE 1=1"
            params = []

            if evt != "전체":
                sql += " AND event_type=?"
                params.append(evt)

            if d_from:
                sql += " AND created_at >= ?"
                params.append(d_from + "T00:00:00")
            if d_to:
                sql += " AND created_at <= ?"
                params.append(d_to + "T23:59:59")

            sql += " ORDER BY created_at DESC LIMIT 500"

            try:
                rows = self.db.fetchall(sql, tuple(params))
                for r in rows:
                    tree.insert('', END, values=(
                        r['id'], r['event_type'],
                        r.get('batch_id', '—') or '—',
                        r.get('tonbag_id', '—') or '—',
                        (r.get('user_note', '') or '')[:50],
                        r['created_at'][:19],
                    ))
                status_var.set(f"조회 결과: {len(rows)}건 (최대 500건)")
            except Exception as e:
                status_var.set(f"조회 오류: {e}")
                logger.error(f"[S1] audit_log 조회 실패: {e}")

        ttk.Button(row1, text="🔍 조회", command=do_search).pack(side=LEFT, padx=(12, 4))
        ttk.Button(row1, text="오늘 전체", command=lambda: [
            event_var.set("전체"),
            date_from_var.set(date.today().isoformat()),
            date_to_var.set(date.today().isoformat()),
            do_search()
        ]).pack(side=LEFT, padx=2)

        # 하단 버튼
        bot = ttk.Frame(dlg)
        bot.pack(fill=X, padx=8, pady=5)
        ttk.Button(bot, text="📥 CSV 내보내기",
                   command=lambda: self._export_audit_csv(tree, status_var)
                   ).pack(side=LEFT, padx=4)
        ttk.Button(bot, text="닫기", command=dlg.destroy).pack(side=RIGHT, padx=4)

        # 초기 로드
        do_search()

    def _export_audit_csv(self, tree, status_var):
        """현재 조회 결과를 CSV 파일로 내보내기"""
        items = tree.get_children()
        if not items:
            CustomMessageBox.showwarning(self.win, "경고", "내보낼 데이터가 없습니다.\n먼저 조회를 실행해주세요.")
            return

        default_name = f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        fpath = filedialog.asksaveasfilename(
            parent=self.win,
            title="감사 로그 CSV 저장",
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[("CSV 파일", "*.csv"), ("모든 파일", "*.*")],
        )
        if not fpath:
            return

        try:
            with open(fpath, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                columns = ('ID', '이벤트유형', '배치ID', '톤백ID', '메모', '시간')
                writer.writerow(columns)
                for item in items:
                    vals = tree.item(item, 'values')
                    writer.writerow(vals)

            count = len(items)
            status_var.set(f"✅ CSV 내보내기 완료: {count}건 → {os.path.basename(fpath)}")
            logger.info(f"[S1] audit CSV 내보내기: {count}건 → {fpath}")

            self._write_audit(
                event_type='AUDIT_EXPORT',
                event_data={
                    'export_file': os.path.basename(fpath),
                    'record_count': count,
                },
                user_note=f"감사 로그 CSV 내보내기: {count}건"
            )

        except Exception as e:
            logger.error(f"[S1] CSV 내보내기 실패: {e}")
            CustomMessageBox.showerror(self.win, "오류", f"CSV 내보내기 실패:\n{e}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 하단: 재고 현황
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ★ 2단계: 수동 actual + 토스트
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _apply_manual_actual(self):
        """★ 2-4: 수동 actual 수량 적용"""
        lot = self._manual_lot_var.get()
        kg_str = self._manual_kg_var.get().strip().replace(',', '')

        if not lot:
            CustomMessageBox.showwarning(self.win, "선택 필요", "LOT를 선택하세요.")
            return
        try:
            kg = float(kg_str)
        except (ValueError, TypeError):
            CustomMessageBox.showwarning(self.win, "입력 오류", "숫자를 입력하세요.")
            return

        batch = next((b for b in self.batches if b['lot_no'] == lot
                       and b['status'] == 'WAIT_SCAN'), None)
        if not batch:
            CustomMessageBox.showwarning(self.win, "없음", f"WAIT_SCAN 상태의 {lot}가 없습니다.")
            return

        batch['actual_qty_kg'] = kg
        batch['scan_diff_kg'] = kg - batch['request_qty_kg']

        self._show_toast(f"✅ {lot}: 실제수량 {kg:,.0f} kg 적용")
        self._manual_kg_var.set("")
        self._refresh_tab3()

    def _update_manual_lot_combo(self):
        """★ 2-4: 수동 입력 LOT 콤보박스 목록 갱신"""
        try:
            combo = None
            for w in self.tab3.winfo_children():
                for c in w.winfo_children():
                    for gc in c.winfo_children():
                        if isinstance(gc, ttk.Combobox):
                            combo = gc
                            break
            if combo:
                lots = [b['lot_no'] for b in self.batches if b['status'] == 'WAIT_SCAN']
                combo['values'] = lots
                if lots:
                    self._manual_lot_var.set(lots[0])
        except Exception as e:
            logger.warning(f"[UI] refresh manual lot combo values failed: {e}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ★ 1단계 UI 개선: 상태바 + 탭 배지
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _update_status_bar(self):
        """★ 1단계 1-4: 현재 최우선 상태에 맞는 컬러 바 표시"""
        c = self._status_bar_canvas
        c.delete('all')

        # 우선순위: ERROR > REVIEW > WAIT_SCAN > FINALIZED > DRAFT
        statuses = [b['status'] for b in self.batches] if self.batches else ['DRAFT']
        if 'ERROR' in statuses:
            cur = 'ERROR'
        elif 'REVIEW_REQUIRED' in statuses:
            cur = 'REVIEW_REQUIRED'
        elif 'WAIT_SCAN' in statuses:
            cur = 'WAIT_SCAN'
        elif 'FINALIZED' in statuses:
            cur = 'FINALIZED'
        else:
            cur = 'DRAFT'

        color = self._status_colors.get(cur, STATUS_COLOR.get(cur, '#6366f1'))
        c.create_rectangle(0, 0, 180, 24, fill=color, outline='')
        c.create_text(90, 12, text=BATCH_STATUS.get(cur, cur),
                      fill='white', font=('맑은 고딕', 10, 'bold'))
        self._status_bar_label.configure(text='', foreground=color)

    def _update_tab_badges(self):
        """★ 1단계 1-2: 탭 제목에 건수 배지 표시"""
        try:
            n_draft = sum(1 for b in self.batches if b['status'] == 'DRAFT')
            n_wscan = sum(1 for b in self.batches if b['status'] in
                         ('WAIT_SCAN', 'FINALIZED', 'REVIEW_REQUIRED', 'ERROR'))
            n_done = len(self.completed) if hasattr(self, 'completed') else 0

            self.nb.tab(0, text=f"  ① 입력 ({len(self.batches)}건)  " if self.batches else self._tab_titles[0])
            self.nb.tab(1, text=f"  ② 톤백 선택 ({n_draft}건)  " if n_draft > 0 else self._tab_titles[1])
            self.nb.tab(2, text=f"  ③ 스캔 검증 ({n_wscan}건)  " if n_wscan > 0 else self._tab_titles[2])
            self.nb.tab(3, text=f"  ④ 완료 ({n_done}건)  " if n_done > 0 else self._tab_titles[3])
        except (tk.TclError, Exception):
            logger.debug("[SUPPRESSED] exception in onestop_outbound.py")  # noqa

    def _build_footer(self):
        fr = ttk.LabelFrame(self.win, text="📊 톤백 재고 현황")
        fr.pack(fill=X, padx=10, pady=(0, 8))

        # ★ 3단계 3-3: 스택 바
        self._footer_canvas = tk.Canvas(fr, height=24, highlightthickness=0)
        self._footer_canvas.pack(fill=X, padx=8, pady=(3, 1))

        self.footer_var = tk.StringVar(value="")
        ttk.Label(fr, textvariable=self.footer_var, font=("Consolas", 9)).pack(padx=8, pady=(0, 3))
        self._update_footer()

    def _update_footer(self):
        try:
            rows = self.db.fetchall(
                "SELECT status, COUNT(*) as cnt, SUM(weight) as total_kg "
                "FROM inventory_tonbag WHERE COALESCE(is_sample,0)=0 "
                "GROUP BY status ORDER BY status"
            )
            parts = []
            status_data = {}
            for r in rows:
                parts.append(f"{r['status']}: {r['cnt']}개 ({r['total_kg']:,.0f} kg)")
                status_data[r['status']] = r['cnt']
            self.footer_var.set("  |  ".join(parts) if parts else "재고 없음")

            # ★ 3단계: 스택 바 그리기
            c = self._footer_canvas
            c.delete('all')
            total = sum(status_data.values()) or 1
            w = c.winfo_width() or 600

            colors = {'AVAILABLE': '#059669', 'PICKED': '#d97706', 'SOLD': '#2563eb',
                      'RESERVED': '#7c3aed', 'DEPLETED': '#9ca3af'}
            x = 0
            for status, cnt in status_data.items():
                bar_w = max(int(w * cnt / total), 2)
                color = colors.get(status, '#6b7280')
                c.create_rectangle(x, 0, x + bar_w, 24, fill=color, outline='')
                if bar_w > 40:
                    c.create_text(x + bar_w // 2, 12, text=f"{status} {cnt}",
                                  fill='white', font=('맑은 고딕', 8))
                x += bar_w
        except Exception as e:
            logger.warning(f"[UI] footer inventory status bar rendering failed: {e}")
            self.footer_var.set("재고 조회 실패")
