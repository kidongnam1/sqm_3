"""
Allocation 승인 워크플로우 다이얼로그.

- 승인 대기(STAGED + PENDING_APPROVAL) 조회/필터/승인/반려
- 승인 이력 조회
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import getpass
import logging
from datetime import datetime

from ..utils.ui_constants import is_dark, CustomMessageBox, ThemeColors, setup_dialog_geometry_persistence
# v8.3.0 [Phase 11]: workflow_status 상수 import (SQL 문자열 직접 사용 → 상수로 교체)
try:
    from engine_modules.constants import (
        ALLOC_WF_APPROVED, ALLOC_WF_REJECTED,
        ALLOC_WF_PENDING, ALLOC_WF_APPLIED,
    )
except ImportError:
    ALLOC_WF_APPROVED = 'APPROVED'
    ALLOC_WF_REJECTED = 'REJECTED'
    ALLOC_WF_PENDING  = 'PENDING_APPROVAL'
    ALLOC_WF_APPLIED  = 'APPLIED'

logger = logging.getLogger(__name__)


class AllocationApprovalDialog:
    def __init__(self, app):
        self.app = app
        self.root = getattr(app, "root", None)
        self.engine = getattr(app, "engine", None)

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _actor(self) -> str:
        try:
            return getpass.getuser() or "unknown"
        except Exception:
            return "unknown"

    def _has_table(self, table_name: str) -> bool:
        try:
            row = self.engine.db.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            return bool(row)
        except Exception:
            return False

    def _table_cols(self, table_name: str) -> set:
        try:
            rows = self.engine.db.fetchall(f"PRAGMA table_info({table_name})")
            cols = set()
            for r in rows or []:
                if isinstance(r, dict):
                    cols.add(str(r.get("name", "")).strip().lower())
                else:
                    cols.add(str(r[1]).strip().lower())
            return cols
        except Exception:
            return set()

    @staticmethod
    def _risk_score(row: dict) -> int:
        flags = str(row.get("risk_flags", "") or "").upper()
        qty_kg = float(row.get("qty_kg", 0) or 0)
        score = 0
        if "OVER_50PCT" in flags:
            score += 500
        if "LARGE_VOLUME" in flags:
            score += 400
        score += min(int(qty_kg // 1000), 100)
        return score

    def show_queue(self) -> None:
        if not self.engine:
            CustomMessageBox.showwarning(self.root, "확인", "엔진이 초기화되지 않았습니다.")
            return
        if not self._has_table("allocation_plan"):
            CustomMessageBox.showwarning(self.root, "확인", "allocation_plan 테이블이 없습니다.")
            return

        from ..utils.constants import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y, tk, ttk

        win = create_themed_toplevel(self.root)
        win.title("✅ Allocation 승인 대기")
        dark_mode = is_dark()
        win.configure(bg=ThemeColors.get("bg_card", is_dark))
        win.transient(self.root)
        setup_dialog_geometry_persistence(win, "allocation_approval_queue", self.root, "large")

        frame = ttk.Frame(win)
        frame.pack(fill=BOTH, expand=True, padx=8, pady=8)

        filter_bar = ttk.Frame(frame)
        filter_bar.pack(fill=X, pady=(0, 6))
        flt_lot = tk.StringVar(value="")
        flt_customer = tk.StringVar(value="")
        flt_batch = tk.StringVar(value="")
        flt_file = tk.StringVar(value="")

        ttk.Label(filter_bar, text="LOT").pack(side=LEFT, padx=(0, 4))
        ent_lot = ttk.Entry(filter_bar, textvariable=flt_lot, width=16)
        ent_lot.pack(side=LEFT, padx=(0, 8))
        ttk.Label(filter_bar, text="거래처").pack(side=LEFT, padx=(0, 4))
        ent_customer = ttk.Entry(filter_bar, textvariable=flt_customer, width=16)
        ent_customer.pack(side=LEFT, padx=(0, 8))
        ttk.Label(filter_bar, text="배치").pack(side=LEFT, padx=(0, 4))
        ent_batch = ttk.Entry(filter_bar, textvariable=flt_batch, width=12)
        ent_batch.pack(side=LEFT, padx=(0, 8))
        ttk.Label(filter_bar, text="파일").pack(side=LEFT, padx=(0, 4))
        ent_file = ttk.Entry(filter_bar, textvariable=flt_file, width=28)
        ent_file.pack(side=LEFT, padx=(0, 8))

        cols = (
            "id",
            "lot_no",
            "customer",
            "qty_mt",
            "qty_kg",
            "risk_flags",
            "source_file",
            "import_batch_id",
            "created_at",
        )
        hdrs = ("ID", "LOT", "거래처", "QTY(MT)", "QTY(KG)", "RISK", "SOURCE", "BATCH", "CREATED")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=18)
        yscroll = tk.Scrollbar(frame, orient=VERTICAL, command=tree.yview)
        xscroll = tk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        yscroll.pack(side=RIGHT, fill=Y)
        # v8.1.9: TreeviewTotalFooter
        try:
            from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter as _TTF
            _footer = _TTF(
                frame, tree,
                summable_column_ids=[],
                column_display_names={},
                column_formats={},
            )
            _footer.pack(fill='x')
            _footer_tree = _footer
        except Exception as e:
            logger.warning(f'[UI] allocation_approval_dialog: {e}')
        xscroll.pack(side=tk.BOTTOM, fill=X)

        for c, h in zip(cols, hdrs):
            tree.heading(c, text=h, anchor='center')
            tree.column(c, width=120, anchor="center")
        tree.column("source_file", width=280, anchor="w")
        tree.column("risk_flags", width=180, anchor="w")

        btns = ttk.Frame(win)
        btns.pack(fill=X, padx=8, pady=(0, 8))
        status_var = tk.StringVar(value="안내: 승인 후 목록에서 사라지면 정상 처리입니다. (승인 이력에서 확인 가능)")
        ttk.Label(win, textvariable=status_var).pack(fill=X, padx=10, pady=(0, 6))

        all_rows = []

        def _render(rows):
            tree.delete(*tree.get_children())
            for r in rows:
                plan_id = str(r.get("id"))
                tree.insert(
                    "",
                    END,
                    iid=plan_id,
                    values=(
                        r.get("id"),
                        r.get("lot_no", ""),
                        r.get("customer", ""),
                        f"{float(r.get('qty_mt', 0) or 0):.4f}",
                        f"{float(r.get('qty_kg', 0) or 0):,.0f}",
                        r.get("risk_flags", "") or "",
                        r.get("source_file", "") or "",
                        r.get("import_batch_id", "") or "",
                        r.get("created_at", "") or "",
                    ),
                )

        def _apply_filter():
            lot_q = flt_lot.get().strip().upper()
            cust_q = flt_customer.get().strip().upper()
            batch_q = flt_batch.get().strip()
            file_q = flt_file.get().strip().upper()
            rows = []
            for r in all_rows:
                lot = str(r.get("lot_no", "")).upper()
                customer = str(r.get("customer", "")).upper()
                batch = str(r.get("import_batch_id", ""))
                fpath = str(r.get("source_file", "")).upper()
                if lot_q and lot_q not in lot:
                    continue
                if cust_q and cust_q not in customer:
                    continue
                if batch_q and batch_q not in batch:
                    continue
                if file_q and file_q not in fpath:
                    continue
                rows.append(r)
            rows.sort(key=self._risk_score, reverse=True)
            _render(rows)

        def _refresh():
            nonlocal all_rows
            cols_plan = self._table_cols("allocation_plan")
            if "workflow_status" not in cols_plan:
                CustomMessageBox.showwarning(
                    win,
                    "스키마 필요",
                    "allocation_plan.workflow_status 컬럼이 없습니다.\n설정/도구 > 운영 DB 스키마 점검(1회)을 실행하세요.",
                )
                return
            rows = self.engine.db.fetchall(
                """
                SELECT id, lot_no, customer, qty_mt,
                       COALESCE(qty_mt, 0) * 1000.0 AS qty_kg,
                       COALESCE(risk_flags, '') AS risk_flags,
                       source_file, import_batch_id, created_at
                FROM allocation_plan
                WHERE status = 'STAGED' AND workflow_status = 'PENDING_APPROVAL'
                ORDER BY created_at DESC, id DESC
                """
            ) or []
            all_rows = list(rows)
            _apply_filter()
            visible_cnt = len(tree.get_children())
            if visible_cnt == 0:
                status_var.set("승인 대기 항목이 없습니다. (승인 완료되었거나 대기 건 없음)")
            else:
                status_var.set(f"현재 승인 대기: {visible_cnt}건 | 승인 후 목록에서 사라지면 정상 처리입니다.")

        def _select_all():
            items = tree.get_children()
            if not items:
                CustomMessageBox.showwarning(win, "선택 없음", "선택할 항목이 없습니다.")
                return
            tree.selection_set(items)
            tree.focus(items[0])
            tree.see(items[0])
            status_var.set(f"선택됨: {len(items)}건")

        def _clear_selection():
            tree.selection_remove(tree.get_children())
            status_var.set("선택 해제 완료")

        def _focus_after_action(previous_ids, selected_ids):
            for pid in previous_ids:
                if pid not in selected_ids and tree.exists(pid):
                    tree.selection_set(pid)
                    tree.focus(pid)
                    tree.see(pid)
                    return
            children = tree.get_children()
            if children:
                tree.selection_set(children[0])
                tree.focus(children[0])
                tree.see(children[0])

        def _approve_selected():
            sel = list(tree.selection())
            if not sel:
                CustomMessageBox.showwarning(win, "선택 필요", "승인할 행을 먼저 선택하세요.")
                return
            if not CustomMessageBox.askyesno(win, "승인", f"{len(sel)}건을 승인(APPROVED) 처리할까요?"):
                return
            actor = self._actor()
            now = self._now()
            prev = list(tree.get_children())
            try:
                approved_count = 0
                with self.engine.db.transaction("IMMEDIATE"):
                    for pid in sel:
                        cur = self.engine.db.execute(
                            """UPDATE allocation_plan
                               SET workflow_status=?, approved_by=?, approved_at=?
                               WHERE id=? AND status='STAGED'
                                 AND workflow_status='PENDING_APPROVAL'""",
                            (ALLOC_WF_APPROVED, actor, now, int(pid)),
                        )
                        try:
                            approved_count += max(0, int(getattr(cur, "rowcount", 0) or 0))
                        except Exception:
                            logger.debug("[SUPPRESSED] exception in allocation_approval_dialog.py")  # noqa
                        if self._has_table("allocation_approval"):
                            self.engine.db.execute(
                                """INSERT INTO allocation_approval
                                   (allocation_plan_id, status, actor, reason, created_at)
                                   VALUES (?, 'APPROVED', ?, ?, ?)""",
                                (int(pid), actor, "approved in queue", now),
                            )
                        # v8.3.0 [Phase 11]: 승인 audit_log 기록
                        try:
                            # 해당 allocation_plan의 lot_no 조회
                            _arow = self.engine.db.fetchone(
                                "SELECT lot_no, sold_to, sale_ref FROM allocation_plan WHERE id=?",
                                (int(pid),)
                            )
                            _lot = (_arow.get('lot_no','') if isinstance(_arow,dict)
                                    else (_arow[0] if _arow else ''))
                            _cust = (_arow.get('sold_to','') if isinstance(_arow,dict)
                                     else (_arow[1] if _arow else ''))
                            from engine_modules.audit_helper import write_audit, EVT_RESERVED
                            write_audit(
                                self.engine.db, EVT_RESERVED,
                                lot_no=_lot,
                                detail={'action': 'APPROVED', 'approved_by': actor,
                                        'customer': _cust, 'plan_id': int(pid)},
                                created_by=actor,
                            )
                        except Exception as _ae:
                            logger.debug(f"[Approval audit] 스킵: {_ae}")
                _refresh()
                _focus_after_action(prev, sel)
                remain = len(tree.get_children())
                status_var.set(f"승인 처리 완료: {approved_count or len(sel)}건 | 현재 승인 대기: {remain}건")
                CustomMessageBox.showinfo(
                    win,
                    "승인 완료",
                    f"승인 처리: {approved_count or len(sel)}건\n"
                    f"남은 승인 대기: {remain}건\n\n"
                    "※ 승인된 항목은 이 목록(PENDING_APPROVAL)에서 사라집니다.\n"
                    "확인은 [출고 > 📜 승인 이력(조회)]에서 가능합니다."
                )
            except Exception as e:
                logger.error(f"승인 처리 오류: {e}", exc_info=True)
                CustomMessageBox.showerror(win, "오류", str(e))

        def _reject_selected():
            sel = list(tree.selection())
            if not sel:
                CustomMessageBox.showwarning(win, "선택 필요", "반려할 행을 먼저 선택하세요.")
                return
            reason = CustomMessageBox.askstring(win, "반려 사유", "반려 사유를 입력하세요(필수):")
            if not reason:
                return
            actor = self._actor()
            now = self._now()
            prev = list(tree.get_children())
            try:
                with self.engine.db.transaction("IMMEDIATE"):
                    for pid in sel:
                        self.engine.db.execute(
                            """UPDATE allocation_plan
                               SET workflow_status=?, rejected_reason=?,
                                   approved_by=?, approved_at=?
                               WHERE id=? AND status='STAGED'
                                 AND workflow_status='PENDING_APPROVAL'""",
                            (ALLOC_WF_REJECTED, str(reason), actor, now, int(pid)),
                        )
                        if self._has_table("allocation_approval"):
                            self.engine.db.execute(
                                """INSERT INTO allocation_approval
                                   (allocation_plan_id, status, actor, reason, created_at)
                                   VALUES (?, 'REJECTED', ?, ?, ?)""",
                                (int(pid), actor, str(reason), now),
                            )
                        # v8.3.0 [Phase 11]: 반려 audit_log 기록
                        try:
                            _arow = self.engine.db.fetchone(
                                "SELECT lot_no, sold_to FROM allocation_plan WHERE id=?",
                                (int(pid),)
                            )
                            _lot = (_arow.get('lot_no','') if isinstance(_arow,dict)
                                    else (_arow[0] if _arow else ''))
                            from engine_modules.audit_helper import write_audit, EVT_CANCEL_RESERVATION
                            write_audit(
                                self.engine.db, EVT_CANCEL_RESERVATION,
                                lot_no=_lot,
                                detail={'action': 'REJECTED', 'rejected_by': actor,
                                        'reason': str(reason), 'plan_id': int(pid)},
                                created_by=actor,
                            )
                        except Exception as _ae:
                            logger.debug(f"[Reject audit] 스킵: {_ae}")
                _refresh()
                _focus_after_action(prev, sel)
            except Exception as e:
                logger.error(f"반려 처리 오류: {e}", exc_info=True)
                CustomMessageBox.showerror(win, "오류", str(e))

        ttk.Button(filter_bar, text="필터 적용", command=_apply_filter).pack(side=LEFT, padx=(2, 4))
        ttk.Button(filter_bar, text="초기화", command=lambda: (flt_lot.set(""), flt_customer.set(""), flt_batch.set(""), flt_file.set(""), _apply_filter())).pack(side=LEFT)
        for ent in (ent_lot, ent_customer, ent_batch, ent_file):
            ent.bind("<Return>", lambda _e: _apply_filter())

        ttk.Button(btns, text="✅ 승인", command=_approve_selected).pack(side=LEFT, padx=4)
        ttk.Button(btns, text="❌ 반려", command=_reject_selected).pack(side=LEFT, padx=4)
        ttk.Button(btns, text="☑ 전체 선택", command=_select_all).pack(side=LEFT, padx=4)
        ttk.Button(btns, text="☐ 전체 해제", command=_clear_selection).pack(side=LEFT, padx=4)
        ttk.Button(btns, text="🔄 새로고침", command=_refresh).pack(side=LEFT, padx=4)
        ttk.Button(btns, text="닫기", command=win.destroy).pack(side=RIGHT, padx=4)

        _refresh()

    def show_history(self) -> None:
        if not self.engine:
            CustomMessageBox.showwarning(self.root, "확인", "엔진이 초기화되지 않았습니다.")
            return

        from ..utils.constants import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y, tk, ttk

        win = create_themed_toplevel(self.root)
        win.title("📜 Allocation 승인 이력")
        dark_mode = is_dark()
        win.configure(bg=ThemeColors.get("bg_card", is_dark))
        win.transient(self.root)
        setup_dialog_geometry_persistence(win, "allocation_approval_history", self.root, "large")

        frame = ttk.Frame(win)
        frame.pack(fill=BOTH, expand=True, padx=8, pady=8)

        cols = ("id", "plan_id", "status", "actor", "reason", "created_at")
        hdrs = ("ID", "PLAN_ID", "STATUS", "ACTOR", "REASON", "CREATED")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=18)
        yscroll = tk.Scrollbar(frame, orient=VERTICAL, command=tree.yview)
        xscroll = tk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        yscroll.pack(side=RIGHT, fill=Y)
        xscroll.pack(side=tk.BOTTOM, fill=X)
        for c, h in zip(cols, hdrs):
            tree.heading(c, text=h, anchor='center')
            tree.column(c, width=140, anchor="center")
        tree.column("reason", width=380, anchor="w")

        try:
            if self._has_table("allocation_approval"):
                rows = self.engine.db.fetchall(
                    """
                    SELECT id, allocation_plan_id AS plan_id, status, actor, reason, created_at
                    FROM allocation_approval
                    ORDER BY id DESC
                    LIMIT 1000
                    """
                ) or []
            else:
                rows = self.engine.db.fetchall(
                    """
                    SELECT id, id AS plan_id, workflow_status AS status,
                           COALESCE(approved_by, '') AS actor,
                           COALESCE(rejected_reason, '') AS reason,
                           COALESCE(approved_at, created_at) AS created_at
                    FROM allocation_plan
                    WHERE workflow_status IN ('APPROVED', 'REJECTED', 'APPLIED')
                    ORDER BY id DESC
                    LIMIT 1000
                    """
                ) or []
            for r in rows:
                tree.insert(
                    "",
                    END,
                    values=(
                        r.get("id"),
                        r.get("plan_id"),
                        r.get("status", ""),
                        r.get("actor", ""),
                        r.get("reason", ""),
                        r.get("created_at", ""),
                    ),
                )
        except Exception as e:
            logger.error(f"승인 이력 조회 오류: {e}", exc_info=True)
            CustomMessageBox.showerror(win, "오류", str(e))

