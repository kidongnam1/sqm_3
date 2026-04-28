# -*- coding: utf-8 -*-
"""
scan_tab.py — SQM 스캔 탭 (v7.4.0)

바코드/QR 스캔 입력 + 빠른처리 4버튼 + 스캔 이력 표시.

빠른처리 버튼:
  📋 배정 등록   → AVAILABLE  → RESERVED  (allocation 등록)
  🚛 화물 결정   → RESERVED   → PICKED    (picking 확정)
  ✅ 출고확정     → PICKED     → OUTBOUND  (출고 완료)
  🔄 반품등록     → OUTBOUND   → RETURN    (반품 입고 대기)
  📦 재입고       → RETURN     → AVAILABLE (재고 복구 완료)
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

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import CustomMessageBox, tc
import logging
import datetime
from engine_modules.constants import (
    STATUS_AVAILABLE, STATUS_RESERVED, STATUS_PICKED,
)  # v7.5.0: 하드코딩 상수 → 중앙화
import tkinter as tk

logger = logging.getLogger(__name__)


class ScanTabMixin:
    """스캔 탭 UI + 이벤트 핸들러."""

    # ──────────────────────────────────────────────
    # 탭 셋업
    # ──────────────────────────────────────────────
    def _setup_scan_tab(self) -> None:
        """스캔 탭 초기화."""
        try:
            import ttkbootstrap as ttk
        except ImportError:
            import tkinter.ttk as ttk

        try:
            from ..utils.constants import BOTH, LEFT, RIGHT, X, Y, YES, VERTICAL
        except Exception as e:
            logger.warning(f"[UI] constants import fallback: {e}")
            BOTH = 'both'; LEFT = 'left'; RIGHT = 'right'
            X = 'x'; Y = 'y'; YES = True; VERTICAL = 'vertical'

        try:
            from ..utils.ui_constants import ThemeColors, Spacing, make_tab_header
        except Exception as e:
            logger.warning(f"[UI] ThemeColors/Spacing import fallback: {e}")
            class ThemeColors:
                @staticmethod
                def get(k, d='#ffffff'): return d
                @staticmethod
                def is_dark_theme(t): return 'dark' in str(t).lower()
            class Spacing:
                XS = 4; SM = 8; MD = 12
            make_tab_header = None

        frame = self.tab_scan

        # v8.1.8: 표준 헤더 추가
        try:
            if make_tab_header:
                make_tab_header(frame, "📷 Scan", status_color='#06b6d4')
        except Exception as e:
            logger.warning(f'[UI] scan_tab: {e}')
        # ── 상단: 스캔 입력 영역 ────────────────────
        scan_input_frame = ttk.LabelFrame(frame, text="📷 바코드 / QR 스캔 입력")
        scan_input_frame.pack(fill=X, padx=Spacing.Tab.OUTER_PADX
                              if hasattr(Spacing, 'Tab') else Spacing.SM,
                              pady=(0, Spacing.SM))

        inner = ttk.Frame(scan_input_frame)
        inner.pack(fill=X, padx=Spacing.SM, pady=Spacing.SM)

        ttk.Label(inner, text="톤백 번호:").pack(side=LEFT, padx=(0, Spacing.XS))
        self._scan_entry_var = tk.StringVar()
        self._scan_entry = ttk.Entry(inner, textvariable=self._scan_entry_var, width=35,
                                     font=('맑은 고딕', 11))
        self._scan_entry.pack(side=LEFT, padx=Spacing.XS)
        self._scan_entry.bind('<Return>', self._on_scan_enter)
        self._scan_entry.bind('<KeyRelease>', self._on_scan_keyrelease)  # E3: 자동완성
        self._ac_listbox_win = None  # E3: 드롭다운 윈도우

        btn_scan_exec = ttk.Button(inner, text="🔍 조회", command=self._on_scan_lookup,
                                   bootstyle='primary')
        btn_scan_exec.pack(side=LEFT, padx=Spacing.XS)

        btn_scan_clear = ttk.Button(inner, text="🗑 지우기", command=self._on_scan_clear,
                                    bootstyle='secondary-outline')
        btn_scan_clear.pack(side=LEFT, padx=Spacing.XS)

        # ⚡ 빠른 스캔 모드: 체크 ON → 팝업 없이 즉시 PICKED 전환
        self._fast_scan_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            inner,
            text="⚡ 빠른 스캔",
            variable=self._fast_scan_var,
            bootstyle="warning-round-toggle",
        ).pack(side=LEFT, padx=(Spacing.SM, 0))

        # 🔕 무음 모드: 오류 시 팝업 없이 레이블만 표시 (연속 스캔용)
        self._silent_scan_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            inner,
            text="🔕 무음",
            variable=self._silent_scan_var,
            bootstyle="secondary-round-toggle",
        ).pack(side=LEFT, padx=(Spacing.XS, 0))

        # 조회 결과 표시 레이블
        self._scan_result_var = tk.StringVar(value="톤백 번호를 입력하거나 스캔하세요.")
        lbl_result = ttk.Label(scan_input_frame, textvariable=self._scan_result_var,
                               font=('맑은 고딕', 10))
        lbl_result.pack(padx=Spacing.SM, pady=(0, Spacing.SM))

        # ── 중단: 빠른처리 4버튼 ────────────────────
        quick_frame = ttk.LabelFrame(frame, text="⚡ 빠른처리")
        quick_frame.pack(fill=X, padx=Spacing.SM, pady=(0, Spacing.SM))

        btn_bar = ttk.Frame(quick_frame)
        btn_bar.pack(fill=X, padx=Spacing.SM, pady=Spacing.SM)

        QUICK_BTNS = [
            ("📋 배정 등록",  '#2563eb', '#dbeafe', self._on_quick_allocate),
            ("🚛 화물 결정",  '#d97706', '#fef3c7', self._on_quick_pick),
            ("✅ 출고확정",   '#059669', '#d1fae5', self._on_quick_outbound),
            ("🔄 반품등록",   '#0891b2', '#cffafe', self._on_quick_return),
            ("📦 재입고",     '#7c3aed', '#ede9fe', self._on_quick_reinbound),
        ]

        for label, color, hover_color, cmd in QUICK_BTNS:
            btn = tk.Button(
                btn_bar, text=label, command=cmd,
                bg=color, fg='#ffffff',
                font=('맑은 고딕', 11, 'bold'),
                relief='flat', padx=16, pady=8, cursor='hand2',
                activebackground=hover_color, activeforeground=color
            )
            btn.pack(side=LEFT, padx=Spacing.SM, pady=Spacing.XS)

        # ── 하단: 스캔 이력 ─────────────────────────
        hist_frame = ttk.LabelFrame(frame, text="📋 스캔 이력")
        hist_frame.pack(fill=BOTH, expand=YES, padx=Spacing.SM, pady=(0, Spacing.SM))

        cols = ('time', 'tonbag_uid', 'lot_no', 'action', 'result')
        self.tree_scan_hist = ttk.Treeview(
            hist_frame, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H
        )
        col_cfg = [
            ('time',       '시간',       120, 'center'),
            ('tonbag_uid', '톤백번호',   160, 'w'),
            ('lot_no',     'LOT번호',    140, 'w'),
            ('action',     '처리',        90, 'center'),
            ('result',     '결과',       260, 'w'),
        ]
        for cid, label, width, anchor in col_cfg:
            self.tree_scan_hist.heading(cid, text=label, anchor='center')
            self.tree_scan_hist.column(cid, width=width, anchor=anchor, stretch=True)

        scr = tk.Scrollbar(hist_frame, orient=VERTICAL, command=self.tree_scan_hist.yview)
        self.tree_scan_hist.configure(yscrollcommand=scr.set)
        self.tree_scan_hist.pack(side=LEFT, fill=BOTH, expand=YES)
        scr.pack(side=RIGHT, fill=Y)
        # v8.1.9: TreeviewTotalFooter
        try:
            from ..utils.tree_enhancements import TreeviewTotalFooter as _TTF
            self._scan_total_footer = _TTF(hist_frame, self.tree_scan_hist, [])
            self._scan_total_footer.pack(fill='x')
        except Exception:
            self._scan_total_footer = None
        # v8.1.8: 합계 footer (건수만)
        try:
            from ..utils.tree_enhancements import TreeviewTotalFooter
            self._scan_footer = TreeviewTotalFooter(
                hist_frame, self.tree_scan_hist,
                summable_column_ids=[],
            )
            self._scan_footer.pack(fill='x')
        except Exception as e:
            logger.warning(f'[UI] scan_tab: {e}')
        # 이력 태그
        self.tree_scan_hist.tag_configure('ok',   foreground=tc('success'))
        self.tree_scan_hist.tag_configure('fail', foreground=tc('danger'))
        self.tree_scan_hist.tag_configure('warn', foreground=tc('warning'))

        # 포커스
        self._scan_entry.focus_set()

    # ──────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────
    def _scan_get_uid(self) -> str:
        """입력창에서 톤백 UID 반환."""
        return (self._scan_entry_var.get() or '').strip()

    def _scan_add_hist(self, uid: str, lot_no: str, action: str, result: str, ok: bool) -> None:
        """이력 트리뷰에 한 줄 추가."""
        now = datetime.datetime.now().strftime('%H:%M:%S')
        tag = 'ok' if ok else 'fail'
        tree = getattr(self, 'tree_scan_hist', None)
        if tree:
            tree.insert('', 0, values=(now, uid, lot_no, action, result), tags=(tag,))
            if hasattr(self, '_scan_total_footer') and self._scan_total_footer:
                self._scan_total_footer.update_totals()

    def _scan_lookup_tonbag(self, uid: str):
        """DB에서 톤백 조회 → dict or None."""
        try:
            row = self.db.fetchone(
                "SELECT lot_no, sub_lt, status, weight, location, is_sample "
                "FROM inventory_tonbag WHERE tonbag_uid=?", (uid,)
            )
            if row:
                if isinstance(row, dict):
                    return row
                return dict(zip(('lot_no','sub_lt','status','weight','location','is_sample'), row))
        except Exception as e:
            logger.error(f"스캔 조회 오류: {e}")
        return None

    # ──────────────────────────────────────────────
    # 이벤트 핸들러
    # ──────────────────────────────────────────────
    def _on_scan_enter(self, event=None) -> None:
        self._on_scan_lookup()

    def _on_scan_clear(self) -> None:
        self._scan_entry_var.set('')
        self._scan_result_var.set("톤백 번호를 입력하거나 스캔하세요.")
        if hasattr(self, '_scan_entry'):
            self._scan_entry.focus_set()

    def _on_scan_keyrelease(self, event=None) -> None:
        """v9.1 E3: LOT 번호 입력 중 자동완성 드롭다운 표시."""
        import tkinter as _tk
        text = self._scan_entry_var.get().strip()

        # 드롭다운 닫기
        if hasattr(self, '_ac_listbox_win') and self._ac_listbox_win:
            try:
                self._ac_listbox_win.destroy()
            except Exception as e:
                logger.warning(f"[UI] autocomplete listbox destroy failed: {e}")
            self._ac_listbox_win = None

        # 4자 이상 입력 시 DB 검색
        if len(text) < 4:
            return
        if not hasattr(self, 'db') or not self.db:
            return

        try:
            rows = self.db.fetchall(
                "SELECT DISTINCT tonbag_uid FROM inventory_tonbag "
                "WHERE tonbag_uid LIKE ? AND status NOT IN ('OUTBOUND','SOLD') "
                "LIMIT 8",
                (text + '%',)
            ) or []
            # LOT 번호도 검색
            lot_rows = self.db.fetchall(
                "SELECT DISTINCT lot_no FROM inventory "
                "WHERE lot_no LIKE ? LIMIT 8",
                (text + '%',)
            ) or []
        except Exception as _e:
            logger.debug(f"[SUPPRESSED] {type(_e).__name__}: {_e}")  # noqa
            return

        candidates = []
        seen = set()
        for r in rows:
            uid = r['tonbag_uid'] if isinstance(r, dict) else r[0]
            if uid and uid not in seen:
                candidates.append(uid)
                seen.add(uid)
        for r in lot_rows:
            lot = r['lot_no'] if isinstance(r, dict) else r[0]
            if lot and lot not in seen:
                candidates.append(lot)
                seen.add(lot)

        if not candidates:
            return

        # 드롭다운 생성
        try:
            entry = self._scan_entry
            x = entry.winfo_rootx()
            y = entry.winfo_rooty() + entry.winfo_height()

            win = create_themed_toplevel(self)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"250x{min(len(candidates)*22+4, 180)}+{x}+{y}")
            win.attributes('-topmost', True)
            self._ac_listbox_win = win

            lb = _tk.Listbox(win, font=("맑은 고딕", 10), activestyle='dotbox',
                             selectmode='single', bd=1, relief='solid')
            lb.pack(fill='both', expand=True)
            for c_item in candidates:
                lb.insert('end', c_item)

            def _on_select(ev=None):
                sel = lb.curselection()
                if sel:
                    val = lb.get(sel[0])
                    self._scan_entry_var.set(val)
                    self._scan_entry.icursor('end')
                if self._ac_listbox_win:
                    try:
                        self._ac_listbox_win.destroy()
                    except Exception as e:
                        logger.warning(f"[UI] autocomplete listbox destroy on select failed: {e}")
                    self._ac_listbox_win = None
                self._scan_entry.focus_set()

            lb.bind('<Return>', _on_select)
            lb.bind('<Double-Button-1>', _on_select)
            lb.bind('<FocusOut>', lambda e: win.destroy() if win.winfo_exists() else None)
            win.bind('<Escape>', lambda e: win.destroy())

        except Exception as _e:
            logger.debug(f"[SUPPRESSED] {type(_e).__name__}: {_e}")  # noqa


    def _on_scan_lookup(self) -> None:
        """톤백 UID 조회 후 결과 표시."""
        uid = self._scan_get_uid()
        if not uid:
            self._scan_result_var.set("⚠️ 톤백 번호를 입력하세요.")
            return
        tb = self._scan_lookup_tonbag(uid)
        if not tb:
            self._scan_result_var.set(f"❌ 없음: {uid}")
            self._scan_add_hist(uid, '-', '조회', '톤백 없음', False)
            return
        lot   = tb.get('lot_no', '-')
        stat  = tb.get('status', '-')
        wt    = tb.get('weight', 0)
        loc   = tb.get('location') or '-'
        samp  = '(샘플)' if tb.get('is_sample') or tb.get('sub_lt') == 0 else ''
        self._scan_result_var.set(
            f"✅ LOT: {lot}  상태: {stat}  무게: {wt}kg  위치: {loc}  {samp}"
        )

    def _on_quick_allocate(self) -> None:
        """📋 배정 등록: AVAILABLE → RESERVED."""
        import tkinter.messagebox as msgbox
        uid = self._scan_get_uid()
        if not uid:
            self._scan_warn("입력 없음", "톤백 번호를 스캔하거나 입력하세요.", parent=self)
            return
        tb = self._scan_lookup_tonbag(uid)
        if not tb:
            self._scan_add_hist(uid, '-', '배정등록', '톤백 없음', False)
            return
        if tb.get('status') != STATUS_AVAILABLE:
            msg = f"AVAILABLE 상태가 아님 (현재: {tb.get('status')})"
            self._scan_add_hist(uid, tb.get('lot_no','-'), '배정등록', msg, False)
            self._scan_warn("상태 오류", msg, parent=self)
            return
        # 배정 등록은 Allocation 다이얼로그로 위임
        msgbox.showinfo("배정 등록",
                        f"LOT {tb.get('lot_no')} 배정은\n메뉴 → 배정 업로드 / 판매배정 탭을 이용하세요.",
                        parent=self)
        self._scan_add_hist(uid, tb.get('lot_no','-'), '배정등록', '다이얼로그로 이동', True)

    def _on_quick_pick(self) -> None:
        """🚛 화물 결정: RESERVED → PICKED."""
        import tkinter.messagebox as msgbox
        uid = self._scan_get_uid()
        if not uid:
            self._scan_warn("입력 없음", "톤백 번호를 스캔하거나 입력하세요.", parent=self)
            return
        tb = self._scan_lookup_tonbag(uid)
        if not tb:
            self._scan_add_hist(uid, '-', '화물결정', '톤백 없음', False)
            return
        if tb.get('is_sample') or tb.get('sub_lt') == 0:
            msg = "샘플 톤백은 화물 결정 불가"
            self._scan_add_hist(uid, tb.get('lot_no','-'), '화물결정', msg, False)
            self._scan_warn("샘플 차단", msg, parent=self)
            return
        if tb.get('status') != STATUS_RESERVED:
            msg = f"RESERVED 상태가 아님 (현재: {tb.get('status')})"
            self._scan_add_hist(uid, tb.get('lot_no','-'), '화물결정', msg, False)
            self._scan_warn("상태 오류", msg, parent=self)
            return
        # 빠른 스캔 모드: 팝업 없이 즉시 처리
        fast_mode = getattr(self, '_fast_scan_var', None)
        if fast_mode and fast_mode.get():
            pass  # 팝업 없이 바로 진행
        else:
            ok = msgbox.askyesno("화물 결정", f"톤백 {uid}\nRESERVED → PICKED 처리합니까?", parent=self)
            if not ok:
                return
        try:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            lot_no    = tb.get('lot_no', '')
            tonbag_id = tb.get('id')
            sub_lt    = tb.get('sub_lt')
            qty_kg    = float(tb.get('weight_kg') or tb.get('initial_weight') or 0)

            # ── v9.1: RESERVED → PICKED 전환 ─────────────────────────────
            self.db.execute(
                "UPDATE inventory_tonbag SET status='PICKED', updated_at=? WHERE tonbag_uid=?",
                (now, uid)
            )

            # ── v9.1: picking_table 자동 생성 ────────────────────────────
            # Picking List PDF 업로드 후 스캔 시 picking_table 행이 없으면 생성
            # Sales Order 업로드 시 lot_no + picking_no 매칭에 필요
            try:
                # 이미 picking_table에 있으면 스킵 (중복 방지)
                existing = self.db.fetchone(
                    "SELECT id FROM picking_table WHERE tonbag_uid=? AND status='ACTIVE' LIMIT 1",
                    (uid,)
                )
                if not existing:
                    # allocation_plan에서 customer, sale_ref, outbound_id 조회
                    plan = self.db.fetchone(
                        "SELECT customer, sale_ref, outbound_id FROM allocation_plan "
                        "WHERE lot_no=? AND status IN ('RESERVED','PICKED') "
                        "ORDER BY id DESC LIMIT 1",
                        (lot_no,)
                    )
                    customer = ''
                    _outbound_id = None
                    _sales_order_no = ''
                    remark   = 'scan_화물결정'
                    if plan:
                        if hasattr(plan, 'keys'):
                            plan = dict(plan)
                        else:
                            plan = dict(zip(['customer','sale_ref','outbound_id'], plan))
                        customer = plan.get('customer', '')
                        _outbound_id = plan.get('outbound_id')
                        remark   = f"scan_화물결정 sale_ref={plan.get('sale_ref','')}"

                    # picking_no: Picking List 업로드로 이미 생성된 행에서 가져옴
                    pk_row = self.db.fetchone(
                        "SELECT picking_no FROM picking_table "
                        "WHERE lot_no=? AND status='ACTIVE' ORDER BY id DESC LIMIT 1",
                        (lot_no,)
                    )
                    picking_no = ''
                    if pk_row:
                        picking_no = str(pk_row[0] if not hasattr(pk_row,'keys')
                                         else dict(pk_row).get('picking_no','')) or ''

                    # ★ v8.1.5 BUG-14: picking_list_order에서 sales_order_no 조회
                    try:
                        plo = self.db.fetchone(
                            "SELECT sales_order FROM picking_list_order "
                            "WHERE lot_no=? ORDER BY id DESC LIMIT 1", (lot_no,)
                        )
                        if plo:
                            _sales_order_no = str(plo.get('sales_order', '') if isinstance(plo, dict)
                                                  else (plo[0] if plo else '')) or ''
                    except Exception as _e:
                        logger.debug(f"picking_list_order 조회 스킵: {_e}")

                    self.db.execute(
                        """INSERT INTO picking_table
                        (lot_no, tonbag_id, sub_lt, tonbag_uid, picking_no,
                         customer, qty_kg, status, picking_date, created_by, remark,
                         outbound_id, sales_order_no)
                        VALUES (?,?,?,?,?,?,?,'ACTIVE',?,'system',?,?,?)""",
                        (lot_no, tonbag_id, sub_lt, uid, picking_no,
                         customer, qty_kg, now, remark,
                         _outbound_id, _sales_order_no)
                    )
                    logger.debug(f"[scan_pick] picking_table 생성: {uid} picking_no={picking_no}")
            except Exception as _pe:
                logger.debug(f"[scan_pick] picking_table 생성 스킵: {_pe}")

            fast = fast_mode and fast_mode.get()
            hist_msg = 'PICKED 완료 ⚡빠른스캔' if fast else 'PICKED 완료 (picking_table 연동)'
            self._scan_add_hist(uid, lot_no, '화물결정', hist_msg, True)
            self._scan_result_var.set(f"✅ {uid} → PICKED {'⚡' if fast else '완료'}")

            # 포커스 자동 복귀 (연속 스캔 편의)
            if hasattr(self, '_scan_entry'):
                self._scan_entry.delete(0, 'end')
                self._scan_entry.focus_set()

            if hasattr(self, 'refresh_bus_deferred'):
                self.refresh_bus_deferred(reason='scan_quick_pick')

        except Exception as e:
            self._scan_add_hist(uid, tb.get('lot_no','-'), '화물결정', str(e), False)

    def _on_quick_outbound(self) -> None:
        """✅ 출고확정: PICKED → OUTBOUND."""
        import tkinter.messagebox as msgbox
        uid = self._scan_get_uid()
        if not uid:
            self._scan_warn("입력 없음", "톤백 번호를 스캔하거나 입력하세요.", parent=self)
            return
        tb = self._scan_lookup_tonbag(uid)
        if not tb:
            self._scan_add_hist(uid, '-', '출고확정', '톤백 없음', False)
            return
        if tb.get('is_sample') or tb.get('sub_lt') == 0:
            msg = "샘플 톤백은 출고 불가"
            self._scan_add_hist(uid, tb.get('lot_no','-'), '출고확정', msg, False)
            self._scan_warn("샘플 차단", msg, parent=self)
            return
        if tb.get('status') != STATUS_PICKED:
            msg = f"PICKED 상태가 아님 (현재: {tb.get('status')})"
            self._scan_add_hist(uid, tb.get('lot_no','-'), '출고확정', msg, False)
            self._scan_warn("상태 오류", msg, parent=self)
            return
        ok = msgbox.askyesno("출고 확정", f"톤백 {uid}\nPICKED → OUTBOUND 처리합니까?", parent=self)
        if not ok:
            return
        try:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.db.execute(
                "UPDATE inventory_tonbag SET status='OUTBOUND', updated_at=? WHERE tonbag_uid=?",
                (now, uid)
            )
            # ★ v8.1.5 BUG-13: sold_table 자동 INSERT
            try:
                tb_full = self.db.fetchone(
                    "SELECT id, lot_no, sub_lt, tonbag_uid, weight "
                    "FROM inventory_tonbag WHERE tonbag_uid=?", (uid,)
                )
                if tb_full:
                    _lot = tb_full.get('lot_no', '') if isinstance(tb_full, dict) else ''
                    _tb_id = tb_full.get('id', None) if isinstance(tb_full, dict) else None
                    _sub_lt = tb_full.get('sub_lt', 0) if isinstance(tb_full, dict) else 0
                    _qty_kg = float((tb_full.get('weight', 0) if isinstance(tb_full, dict) else 0) or 0)
                    plan = self.db.fetchone(
                        "SELECT customer, sale_ref FROM allocation_plan "
                        "WHERE lot_no=? AND status IN ('RESERVED','EXECUTED') "
                        "ORDER BY id DESC LIMIT 1", (_lot,)
                    )
                    pick_row = self.db.fetchone(
                        "SELECT id, picking_no, sales_order_no FROM picking_table "
                        "WHERE tonbag_uid=? AND status='ACTIVE' LIMIT 1", (uid,)
                    )
                    inv = self.db.fetchone(
                        "SELECT sap_no, bl_no FROM inventory WHERE lot_no=?", (_lot,)
                    )
                    _plan_d = dict(plan) if plan and hasattr(plan, 'keys') else (plan if isinstance(plan, dict) else {})
                    _pick_d = dict(pick_row) if pick_row and hasattr(pick_row, 'keys') else (pick_row if isinstance(pick_row, dict) else {})
                    _inv_d = dict(inv) if inv and hasattr(inv, 'keys') else (inv if isinstance(inv, dict) else {})
                    self.db.execute(
                        """INSERT OR IGNORE INTO sold_table
                        (lot_no, tonbag_id, sub_lt, tonbag_uid, picking_id,
                         sales_order_no, picking_no, sap_no, bl_no,
                         customer, sold_qty_mt, sold_qty_kg,
                         status, sold_date, created_by, remark)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'CONFIRMED',?,'system',?)""",
                        (
                            _lot, _tb_id, _sub_lt, uid,
                            _pick_d.get('id'),
                            _pick_d.get('sales_order_no') or _plan_d.get('sale_ref', ''),
                            _pick_d.get('picking_no', ''),
                            _inv_d.get('sap_no', ''),
                            _inv_d.get('bl_no', ''),
                            _plan_d.get('customer', ''),
                            round(_qty_kg / 1000, 4),
                            _qty_kg,
                            now,
                            f"scan_출고확정 uid={uid}"
                        )
                    )
                    logger.info(f"[scan_outbound] sold_table INSERT: {uid} lot={_lot}")
            except Exception as _se:
                logger.warning(f"[scan_outbound] sold_table INSERT 실패: {_se}")
            self._scan_add_hist(uid, tb.get('lot_no','-'), '출고확정', 'OUTBOUND 전환 완료', True)
            self._scan_result_var.set(f"✅ {uid} → OUTBOUND 완료")
            # P4: 출고확정 후 전체 탭 새로고침
            if hasattr(self, 'refresh_bus_deferred'):
                self.refresh_bus_deferred(reason='scan_quick_outbound')
        except Exception as e:
            self._scan_add_hist(uid, tb.get('lot_no','-'), '출고확정', str(e), False)

    def _on_quick_return(self) -> None:
        """🔄 반품등록: OUTBOUND/SOLD → RETURN.
        v9.1: status만 변경하지 않고 process_return() 호출로
              inventory 중량 복구 + return_history + stock_movement 기록.
        """
        import tkinter.messagebox as msgbox
        uid = self._scan_get_uid()
        if not uid:
            self._scan_warn("입력 없음", "톤백 번호를 스캔하거나 입력하세요.", parent=self)
            return
        tb = self._scan_lookup_tonbag(uid)
        if not tb:
            self._scan_add_hist(uid, '-', '반품등록', '톤백 없음', False)
            return

        lot_no = tb.get('lot_no', '')
        sub_lt = tb.get('sub_lt')
        status = tb.get('status', '')

        # 샘플 차단
        if tb.get('is_sample') or tb.get('sub_lt') == 0:
            msg = "샘플 톤백은 반품 불가"
            self._scan_add_hist(uid, lot_no, '반품등록', msg, False)
            self._scan_warn("샘플 차단", msg, parent=self)
            return

        # 반품 가능 상태 확인
        returnable = ('PICKED', 'OUTBOUND', 'SOLD', 'CONFIRMED', 'SHIPPED', 'RESERVED')
        if status not in returnable:
            msg = f"반품 불가 상태 (현재: {status})"
            self._scan_add_hist(uid, lot_no, '반품등록', msg, False)
            self._scan_warn("상태 오류", msg, parent=self)
            return

        ok = msgbox.askyesno(
            "반품 등록",
            f"톤백 {uid}\nLOT: {lot_no} / 상태: {status}\n"
            f"반품 처리합니까?\n(재고 복구 + 이력 기록)",
            parent=self
        )
        if not ok:
            return
        try:
            # ── v9.1: process_return() 호출 — 정식 반품 처리 ──────
            # inventory 중량 복구 + return_history + stock_movement +
            # allocation_plan CANCELLED + picking_table RETURNED
            engine = getattr(self, 'engine', None)
            if engine and hasattr(engine, 'return_single_tonbag'):
                result = engine.return_single_tonbag(
                    lot_no=lot_no,
                    sub_lt=sub_lt,
                    reason='스캔_반품등록',
                    remark=f'scan uid={uid}',
                )
            elif engine and hasattr(engine, 'process_return'):
                result = engine.process_return(
                    [{'lot_no': lot_no, 'sub_lt': sub_lt,
                      'reason': '스캔_반품등록',
                      'remark': f'scan uid={uid}'}],
                    source_type='RETURN_SCAN'
                )
            else:
                # 폴백: status만 변경 (engine 없는 환경)
                logger.warning("[scan_return] engine 없음 — status만 변경")
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.db.execute(
                    "UPDATE inventory_tonbag SET status='RETURN', updated_at=? WHERE tonbag_uid=?",
                    (now, uid)
                )
                result = {'success': True, 'returned': 1}

            if result.get('success') or result.get('returned', 0) > 0:
                self._scan_add_hist(uid, lot_no, '반품등록',
                                     '반품 완료 (재고복구+이력)', True)
                self._scan_result_var.set(f"✅ {uid} → RETURN (재고 복구)")
            else:
                errs = result.get('errors', ['알 수 없는 오류'])
                msg  = errs[0] if errs else '반품 실패'
                self._scan_add_hist(uid, lot_no, '반품등록', msg, False)
                msgbox.showerror("반품 실패", msg, parent=self)
                return

            # 입력창 클리어 + 포커스 복귀
            if hasattr(self, '_scan_entry'):
                self._scan_entry.delete(0, 'end')
                self._scan_entry.focus_set()

            if hasattr(self, 'refresh_bus_deferred'):
                self.refresh_bus_deferred(reason='scan_quick_return')

        except Exception as e:
            self._scan_add_hist(uid, lot_no, '반품등록', str(e), False)
            msgbox.showerror("오류", str(e)[:300], parent=self)

    def _on_quick_reinbound(self) -> None:
        """📦 재입고: RETURN → AVAILABLE.
        v9.1: 반품 대기(RETURN) 톤백에 위치를 지정하고 AVAILABLE로 복구.
        finalize_return_to_available() 호출.
        """
        import tkinter.messagebox as msgbox
        uid = self._scan_get_uid()
        if not uid:
            self._scan_warn("입력 없음", "톤백 번호를 스캔하거나 입력하세요.", parent=self)
            return
        tb = self._scan_lookup_tonbag(uid)
        if not tb:
            self._scan_add_hist(uid, '-', '재입고', '톤백 없음', False)
            return

        lot_no = tb.get('lot_no', '')
        sub_lt = tb.get('sub_lt')
        status = tb.get('status', '')

        if status != 'RETURN':
            msg = f"RETURN 상태가 아님 (현재: {status})"
            self._scan_add_hist(uid, lot_no, '재입고', msg, False)
            self._scan_warn("상태 오류", msg, parent=self)
            return

        # 현재 위치 표시
        cur_loc = tb.get('location', '') or ''
        location = CustomMessageBox.askstring(
            self,
            "재입고 위치",
            f"톤백 {uid} (LOT: {lot_no})\n배치할 위치를 입력하세요.\n(공백이면 기존 위치 유지)",
            initial=cur_loc,
        )
        if location is None:  # 취소
            return
        location = location.strip() or cur_loc

        try:
            # ── v9.1: finalize_return_to_available() 호출 ─────────
            engine = getattr(self, 'engine', None)
            if engine and hasattr(engine, 'finalize_return_to_available'):
                result = engine.finalize_return_to_available(
                    lot_no=lot_no,
                    sub_lt=sub_lt,
                    location=location or None,
                )
            else:
                # 폴백: status만 변경
                logger.warning("[scan_reinbound] engine 없음 — status만 변경")
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.db.execute(
                    "UPDATE inventory_tonbag SET status='AVAILABLE', updated_at=? WHERE tonbag_uid=?",
                    (now, uid)
                )
                result = {'success': True, 'message': 'status 변경'}

            if result.get('success'):
                msg = f"재입고 완료 → AVAILABLE (위치: {location or '기존유지'})"
                self._scan_add_hist(uid, lot_no, '재입고', msg, True)
                self._scan_result_var.set(f"✅ {uid} → AVAILABLE")
                msgbox.showinfo("완료", f"재입고 처리 완료\n\n{msg}", parent=self)
            else:
                err = result.get('message', '재입고 실패')
                self._scan_add_hist(uid, lot_no, '재입고', err, False)
                msgbox.showerror("재입고 실패", err, parent=self)
                return

            if hasattr(self, '_scan_entry'):
                self._scan_entry.delete(0, 'end')
                self._scan_entry.focus_set()

            if hasattr(self, 'refresh_bus_deferred'):
                self.refresh_bus_deferred(reason='scan_reinbound')

        except Exception as e:
            self._scan_add_hist(uid, lot_no, '재입고', str(e), False)
            msgbox.showerror("오류", str(e)[:300], parent=self)


    def _scan_clear_and_focus(self) -> None:
        """스캔 후 입력창 클리어 + 포커스 복귀."""
        if hasattr(self, '_scan_entry'):
            self._scan_entry.delete(0, 'end')
            self._scan_entry.focus_set()

    def _scan_warn(self, title: str, msg: str, parent=None) -> None:
        """v9.1: 무음 모드 ON → 레이블 표시, OFF → 팝업 표시."""
        import tkinter.messagebox as _mb
        self._scan_result_var.set(f"⚠️ {msg}")
        silent = getattr(self, '_silent_scan_var', None)
        if silent and silent.get():
            return  # 팝업 없이 레이블만
        _mb.showwarning(title, msg, parent=parent or self)

    def _scan_error(self, title: str, msg: str, parent=None) -> None:
        """v9.1: 무음 모드 ON → 레이블 표시, OFF → 팝업 표시."""
        import tkinter.messagebox as _mb
        self._scan_result_var.set(f"❌ {msg}")
        silent = getattr(self, '_silent_scan_var', None)
        if silent and silent.get():
            return
        _mb.showerror(title, msg, parent=parent or self)