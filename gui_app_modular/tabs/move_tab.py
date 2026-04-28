# -*- coding: utf-8 -*-
"""
SQM v8.1.8 — Move 탭 (🔀 Tonbag Location Move & Transfer)
==========================================================

바코드 스캔으로 톤백 이동 처리 + Excel 업로드 + 이동 이력 조회.

스캔 워크플로우:
  1. 톤백 바코드 스캔 → 현재 위치 자동 조회
  2. 목적지 위치 입력
  3. ✅ Move 버튼 → tonbag_move_log 기록 + inventory_tonbag.location 업데이트
"""
import datetime
import logging
import tkinter as tk
from tkinter import ttk

from ..utils.ui_constants import Spacing, tc

logger = logging.getLogger(__name__)


class MoveTabMixin:
    """🔀 Move 탭 — 톤백 스캔 이동 + 이력 관리 (v8.1.8)."""

    def _setup_move_tab(self) -> None:
        frame = self.tab_move

        # ── 표준 헤더 (v8.1.8: make_tab_header 적용) ──────────────
        try:
            from ..utils.ui_constants import make_tab_header
            make_tab_header(frame, "🔀 Move Management", status_color='#8b5cf6')
        except Exception:
            tk.Label(frame, text="🔀 Move Management",
                     font=('맑은 고딕', 12, 'bold')).pack(
                fill='x', padx=Spacing.Tab.OUTER_PADX, pady=Spacing.Tab.HEADER_PADY)

        # ══════════════════════════════════════════════════════════
        # 스캔 패널
        # ══════════════════════════════════════════════════════════
        scan_lf = ttk.LabelFrame(frame, text="⚡ Scan to Move")
        scan_lf.pack(fill='x', padx=Spacing.Tab.OUTER_PADX, pady=(Spacing.SM, 0))

        # 1행 — 톤백 UID 스캔
        row1 = tk.Frame(scan_lf)
        row1.pack(fill='x', padx=Spacing.SM, pady=(Spacing.SM, 2))

        tk.Label(row1, text="Tonbag UID:", width=12, anchor='e').pack(side='left')
        self._move_uid_var = tk.StringVar()
        self._move_uid_entry = ttk.Entry(row1, textvariable=self._move_uid_var,
                                          width=32, font=('Consolas', 10))
        self._move_uid_entry.pack(side='left', padx=Spacing.XS)
        self._move_uid_entry.bind('<Return>', lambda e: self._on_move_scan_uid())
        ttk.Button(row1, text="🔍 Lookup",
                   command=self._on_move_scan_uid).pack(side='left', padx=Spacing.XS)

        tk.Label(row1, text="Current:", width=8, anchor='e').pack(side='left', padx=(Spacing.MD, 0))
        self._move_cur_loc_var = tk.StringVar(value='—')
        tk.Label(row1, textvariable=self._move_cur_loc_var,
                 font=('맑은 고딕', 10, 'bold')).pack(side='left', padx=Spacing.XS)
        self._move_lot_info_var = tk.StringVar(value='')
        tk.Label(row1, textvariable=self._move_lot_info_var,
                 font=('맑은 고딕', 10)).pack(side='left', padx=Spacing.SM)

        # 2행 — 목적지 + 이동 실행
        row2 = tk.Frame(scan_lf)
        row2.pack(fill='x', padx=Spacing.SM, pady=(2, Spacing.SM))

        tk.Label(row2, text="To Location:", width=12, anchor='e').pack(side='left')
        self._move_to_var = tk.StringVar()
        self._move_to_entry = ttk.Entry(row2, textvariable=self._move_to_var,
                                         width=32, font=('Consolas', 10))
        self._move_to_entry.pack(side='left', padx=Spacing.XS)
        self._move_to_entry.bind('<Return>', lambda e: self._on_move_execute())

        self._move_exec_btn = tk.Button(
            row2, text="✅  Move", command=self._on_move_execute,
            bg='#059669', fg='white', font=('맑은 고딕', 10, 'bold'),
            relief='flat', padx=14, pady=6, cursor='hand2', state='disabled'
        )
        self._move_exec_btn.pack(side='left', padx=Spacing.SM)
        ttk.Button(row2, text="🗑 Clear",
                   command=self._on_move_scan_clear).pack(side='left', padx=2)

        self._move_continuous_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="연속 스캔",
                         variable=self._move_continuous_var).pack(side='left', padx=(Spacing.MD, 0))

        # 결과 메시지
        self._move_msg_var = tk.StringVar(value="톤백 바코드를 스캔하거나 UID를 입력하세요.")
        self._move_msg_lbl = tk.Label(scan_lf, textvariable=self._move_msg_var,
                                       font=('맑은 고딕', 10), anchor='w')
        self._move_msg_lbl.pack(fill='x', padx=Spacing.SM, pady=(0, Spacing.XS))

        self._move_current_row = None
        self._move_current_uid = None

        # ── 버튼 바 ───────────────────────────────────────────────
        btn_bar = tk.Frame(frame)
        btn_bar.pack(fill='x', padx=Spacing.Tab.OUTER_PADX, pady=Spacing.Tab.BTN_BAR_PADY)
        ttk.Button(btn_bar, text="📍 Location Upload (Excel)",
                   command=lambda: self._on_tonbag_location_upload()
                   if hasattr(self, '_on_tonbag_location_upload') else None
                   ).pack(side='left', padx=(0, Spacing.Tab.BTN_GAP))
        ttk.Button(btn_bar, text="✅ Move Approval",
                   command=lambda: self._on_move_approval_queue()
                   if hasattr(self, '_on_move_approval_queue') else None
                   ).pack(side='left', padx=(0, Spacing.Tab.BTN_GAP))
        ttk.Button(btn_bar, text="🔄 Refresh",
                   command=self._refresh_move_tab).pack(side='right')

        # ── 요약 카드 ─────────────────────────────────────────────
        card_frame = tk.Frame(frame)
        card_frame.pack(fill='x', padx=Spacing.Tab.OUTER_PADX, pady=(0, Spacing.XS))
        self._move_summary_labels = {}
        for col_key, col_title in [('pending', 'Pending'), ('approved', 'Approved'), ('completed', 'Completed')]:
            card = tk.Frame(card_frame, relief='solid', bd=1)
            card.pack(side='left', fill='x', expand=True, padx=Spacing.Tab.BTN_GAP)
            tk.Label(card, text=col_title, font=('맑은 고딕', 10)).pack(pady=(Spacing.XS, 0))
            lbl = tk.Label(card, text='—', font=('맑은 고딕', 18, 'bold'))
            lbl.pack(pady=(0, Spacing.XS))
            self._move_summary_labels[col_key] = lbl

        # ── 필터 바 ───────────────────────────────────────────────
        filter_bar = tk.Frame(frame)
        filter_bar.pack(fill='x', padx=Spacing.Tab.OUTER_PADX, pady=(0, Spacing.XS))
        tk.Label(filter_bar, text="Status:").pack(side='left')
        self._move_status_var = tk.StringVar(value='ALL')
        cb = ttk.Combobox(filter_bar, textvariable=self._move_status_var,
                          values=['ALL', 'PENDING', 'APPROVED', 'COMPLETED', 'REJECTED'],
                          state='readonly', width=12)
        cb.pack(side='left', padx=Spacing.SM)
        cb.bind('<<ComboboxSelected>>', lambda e: self._refresh_move_tab())
        tk.Label(filter_bar, text="LOT:").pack(side='left', padx=(Spacing.MD, Spacing.XS))
        self._move_lot_filter_var = tk.StringVar()
        lot_e = ttk.Entry(filter_bar, textvariable=self._move_lot_filter_var, width=16)
        lot_e.pack(side='left', padx=2)
        lot_e.bind('<Return>', lambda e: self._refresh_move_tab())
        ttk.Button(filter_bar, text="🔍", width=3,
                   command=self._refresh_move_tab).pack(side='left')

        # ── 이동 이력 트리뷰 ──────────────────────────────────────
        hist_lf = ttk.LabelFrame(frame, text="📋 Move History")
        hist_lf.pack(fill='both', expand=True, padx=Spacing.Tab.OUTER_PADX, pady=Spacing.Tab.TREE_PADY)
        cols = ('time', 'lot_no', 'tonbag_no', 'from_loc', 'to_loc', 'status', 'operator')
        self.tree_move = ttk.Treeview(hist_lf, columns=cols, show='headings', height=Spacing.Tab.TREE_MIN_H)
        for col, heading, width in [
            ('time', 'Time', 110), ('lot_no', 'LOT NO', 120), ('tonbag_no', 'Tonbag No', 90),
            ('from_loc', 'From', 120), ('to_loc', 'To', 120),
            ('status', 'Status', 80), ('operator', 'Operator', 90),
        ]:
            self.tree_move.heading(col, text=heading,
                                   command=lambda c=col: self._sort_move_tree(c))
            self.tree_move.column(col, width=width, anchor='center')
        vsb = ttk.Scrollbar(hist_lf, orient='vertical', command=self.tree_move.yview)
        self.tree_move.configure(yscrollcommand=vsb.set)
        self.tree_move.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self.tree_move.tag_configure('ok', foreground='#22c55e')
        self.tree_move.tag_configure('fail', foreground='#ef4444')
        self.tree_move.tag_configure('pending', foreground='#f97316')
        self.tree_move.bind('<Double-1>', self._on_move_row_double_click)
        self._move_uid_entry.focus_set()

    # ──────────────────────────────────────────────────────────────
    # 스캔 핸들러
    # ──────────────────────────────────────────────────────────────
    def _on_move_scan_uid(self) -> None:
        """톤백 UID 조회 → 현재 위치 표시."""
        uid = (self._move_uid_var.get() or '').strip()
        if not uid:
            self._move_msg('입력값이 없습니다.', 'warn')
            return
        row = None
        try:
            raw = self.db.fetchone(
                "SELECT lot_no, sub_lt, status, weight, location, tonbag_no "
                "FROM inventory_tonbag WHERE tonbag_uid=?", (uid,)
            )
            if raw:
                row = raw if isinstance(raw, dict) else dict(
                    zip(('lot_no', 'sub_lt', 'status', 'weight', 'location', 'tonbag_no'), raw)
                )
        except Exception as _e:
            logger.error(f"[MoveTab] lookup: {_e}")
        if not row:
            self._move_msg(f"톤백을 찾을 수 없습니다: {uid}", 'fail')
            self._move_cur_loc_var.set('—')
            self._move_lot_info_var.set('')
            self._move_exec_btn.config(state='disabled')
            self._move_current_row = None
            self._move_current_uid = None
            return
        cur_loc = row.get('location') or '미배정'
        lot_no  = row.get('lot_no', '')
        weight  = float(row.get('weight') or 0)
        self._move_cur_loc_var.set(cur_loc)
        self._move_lot_info_var.set(
            f"LOT: {lot_no}  sub_lt: {row.get('sub_lt','')}  "
            f"{row.get('status','')}  {weight:,.1f} kg"
        )
        self._move_msg(f"✅ 확인 — {uid}  현재 위치: [{cur_loc}]", 'ok')
        self._move_exec_btn.config(state='normal')
        self._move_current_row = row
        self._move_current_uid = uid
        self._move_to_entry.focus_set()
        self._move_to_entry.select_range(0, 'end')

    def _on_move_execute(self) -> None:
        """이동 실행 — DB 업데이트 + 이력 기록."""
        row = self._move_current_row
        uid = self._move_current_uid
        to_loc = (self._move_to_var.get() or '').strip().upper()
        if not row or not uid:
            self._move_msg('먼저 톤백을 스캔하세요.', 'warn')
            return
        if not to_loc:
            self._move_msg('목적지 위치를 입력하세요.', 'warn')
            self._move_to_entry.focus_set()
            return
        from_loc  = row.get('location') or ''
        lot_no    = row.get('lot_no', '')
        sub_lt    = row.get('sub_lt', 0)
        tonbag_no = row.get('tonbag_no') or ''
        weight    = float(row.get('weight') or 0)
        now       = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        today     = now[:10]
        try:
            with self.db.transaction("IMMEDIATE"):
                # ① inventory_tonbag 위치 업데이트
                self.db.execute(
                    "UPDATE inventory_tonbag SET location=?, location_updated_at=?, updated_at=? "
                    "WHERE tonbag_uid=?", (to_loc, now, now, uid)
                )
                # ② tonbag_move_log 기록
                self.db.execute(
                    "INSERT INTO tonbag_move_log "
                    "(lot_no, sub_lt, tonbag_no, from_location, to_location, "
                    " move_date, status, operator, source_type, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED', 'system', 'SCAN', ?)",
                    (lot_no, sub_lt, tonbag_no, from_loc, to_loc, today, now)
                )
                # ③ stock_movement 이력
                self.db.execute(
                    "INSERT INTO stock_movement "
                    "(lot_no, movement_type, qty_kg, from_location, to_location, "
                    " remarks, source_type, created_at) "
                    "VALUES (?, 'RELOCATE', ?, ?, ?, ?, 'SCAN_MOVE', ?)",
                    (lot_no, weight, from_loc, to_loc,
                     f"sub_lt={sub_lt} uid={uid} SCAN", now)
                )
            msg = f"✅ 이동 완료: [{from_loc or '?'}] → [{to_loc}]  ({uid})"
            self._move_msg(msg, 'ok')
            logger.info(f"[MoveTab] {msg}")
            # 이력 트리에 즉시 반영
            if hasattr(self, 'tree_move'):
                self.tree_move.insert('', 0, values=(
                    now[11:19], lot_no, tonbag_no or uid,
                    from_loc, to_loc, 'COMPLETED', 'system'
                ), tags=('ok',))
            self._update_move_summary_cards()
            # 연속 스캔 모드
            if getattr(self, '_move_continuous_var', None) and self._move_continuous_var.get():
                self._move_uid_var.set('')
                self._move_to_var.set('')
                self._move_cur_loc_var.set('—')
                self._move_lot_info_var.set('')
                self._move_exec_btn.config(state='disabled')
                self._move_current_row = None
                self._move_current_uid = None
                self._move_uid_entry.focus_set()
            else:
                self._move_to_var.set('')
                self._move_to_entry.focus_set()
        except Exception as _e:
            logger.error(f"[MoveTab] execute: {_e}", exc_info=True)
            self._move_msg(f"❌ 이동 실패: {_e}", 'fail')

    def _on_move_scan_clear(self) -> None:
        """스캔 패널 초기화."""
        self._move_uid_var.set('')
        self._move_to_var.set('')
        self._move_cur_loc_var.set('—')
        self._move_lot_info_var.set('')
        self._move_msg_var.set("톤백 바코드를 스캔하거나 UID를 입력하세요.")
        if hasattr(self, '_move_msg_lbl'):
            self._move_msg_lbl.config(fg=tc('text_muted'))
        self._move_exec_btn.config(state='disabled')
        self._move_current_row = None
        self._move_current_uid = None
        self._move_uid_entry.focus_set()

    def _move_msg(self, text: str, level: str = 'ok') -> None:
        """결과 메시지 표시."""
        color_map = {'ok': '#22c55e', 'warn': '#f97316', 'fail': '#ef4444'}
        self._move_msg_var.set(text)
        lbl = getattr(self, '_move_msg_lbl', None)
        if lbl:
            lbl.config(fg=color_map.get(level, tc('text_primary')))

    # ──────────────────────────────────────────────────────────────
    # 데이터 갱신
    # ──────────────────────────────────────────────────────────────
    def _refresh_move_tab(self) -> None:
        """이력 트리뷰 + 요약 카드 새로고침."""
        try:
            if not hasattr(self, 'tree_move'):
                return
            self.tree_move.delete(*self.tree_move.get_children())
            fval     = getattr(self, '_move_status_var', tk.StringVar(value='ALL')).get()
            lot_fval = (getattr(self, '_move_lot_filter_var', None) or
                        tk.StringVar()).get().strip()
            rows = []
            if hasattr(self, 'engine') and hasattr(self.engine, 'get_move_history'):
                rows = self.engine.get_move_history(
                    status=None if fval == 'ALL' else fval,
                    lot_no=lot_fval or None,
                    limit=500
                ) or []
            for r in rows:
                st = r.get('status', '')
                tag = 'ok' if st == 'COMPLETED' else ('pending' if st == 'PENDING' else 'fail')
                created = str(r.get('created_at') or '')
                self.tree_move.insert('', 'end', values=(
                    created[11:19] if len(created) >= 19 else created,
                    r.get('lot_no', ''), r.get('tonbag_no', ''),
                    r.get('from_location', ''), r.get('to_location', ''),
                    st, r.get('operator', ''),
                ), tags=(tag,))
            self._update_move_summary_cards(rows)
        except Exception as _e:
            logger.debug(f"[MoveTab] refresh: {_e}")

    def _update_move_summary_cards(self, rows=None) -> None:
        """요약 카드 갱신."""
        try:
            if rows is None and hasattr(self, 'engine') and hasattr(self.engine, 'get_move_history'):
                rows = self.engine.get_move_history(limit=1000) or []
            rows = rows or []
            lbl = getattr(self, '_move_summary_labels', {})
            for key, status in [('pending', 'PENDING'), ('approved', 'APPROVED'), ('completed', 'COMPLETED')]:
                cnt = sum(1 for r in rows if r.get('status') == status)
                if lbl.get(key):
                    lbl[key].config(text=str(cnt))
        except Exception as _e:
            logger.debug(f"[MoveTab] summary_cards: {_e}")

    def _sort_move_tree(self, col: str) -> None:
        """컬럼 클릭 정렬."""
        try:
            items = [(self.tree_move.set(k, col), k) for k in self.tree_move.get_children('')]
            items.sort()
            for idx, (_, k) in enumerate(items):
                self.tree_move.move(k, '', idx)
        except Exception as _e:
            logger.debug(f"[MoveTab] sort: {_e}")

    def _on_move_row_double_click(self, event=None) -> None:
        """이력 행 더블클릭 → Move Approval 다이얼로그."""
        tree = getattr(self, 'tree_move', None)
        if not tree or not tree.selection():
            return
        if hasattr(self, '_on_move_approval_queue'):
            self._on_move_approval_queue()
