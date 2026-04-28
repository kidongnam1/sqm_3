# -*- coding: utf-8 -*-
"""LOT별 allocation_plan 이력 + inventory_tonbag 현황 요약 (도구 메뉴 / LOT 상세 탭)."""

import logging
import tkinter as tk
from tkinter import ttk

from ..utils.ui_constants import (
    CustomMessageBox,
    ThemeColors,
    apply_tooltip,
    create_themed_toplevel,
    get_status_display,
    is_dark,
    setup_dialog_geometry_persistence,
)

logger = logging.getLogger(__name__)


def _table_exists(db, name: str) -> bool:
    try:
        r = db.fetchone(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (name,),
        )
        return bool(r)
    except Exception as e:
        logger.debug("table_exists %s: %s", name, e)
        return False


def _plan_column_names(db) -> set:
    try:
        rows = db.fetchall("PRAGMA table_info(allocation_plan)") or []
        return {str(r.get("name", "")).lower() for r in rows if r}
    except Exception as e:
        logger.debug("PRAGMA allocation_plan: %s", e)
        return set()


class LotAllocationAuditMixin:
    """allocation_plan(배정 이력) + inventory_tonbag(현재 톤백) 조회."""

    def _lot_allocation_audit_fill(self, container: tk.Frame, lot_no: str) -> None:
        for w in container.winfo_children():
            try:
                w.destroy()
            except tk.TclError:
                pass  # TclError: widget destroyed
        lot_no = (lot_no or "").strip()
        _dark = is_dark()
        bg = ThemeColors.get("bg_card", _dark)
        fg = ThemeColors.get("text_primary", _dark)
        muted = ThemeColors.get("text_muted", _dark)
        container.configure(bg=bg)

        if not lot_no:
            tk.Label(container, text="LOT 번호를 선택하거나 입력하세요.", bg=bg, fg=muted).pack(
                padx=8, pady=12
            )
            return

        db = self.engine.db
        sum_fr = tk.Frame(container, bg=bg)
        sum_fr.pack(fill=tk.X, padx=8, pady=(8, 4))

        # ── 1) inventory_tonbag: 현재 상태별 건수·중량 ──
        tb_lines = []
        if _table_exists(db, "inventory_tonbag"):
            try:
                rows = db.fetchall(
                    """
                    SELECT status, COUNT(*) AS cnt, COALESCE(SUM(weight), 0) AS kg
                    FROM inventory_tonbag
                    WHERE lot_no = ?
                    GROUP BY status
                    ORDER BY status
                    """,
                    (lot_no,),
                )
                for r in rows or []:
                    st = r.get("status") if isinstance(r, dict) else r[0]
                    cnt = r.get("cnt") if isinstance(r, dict) else r[1]
                    kg = r.get("kg") if isinstance(r, dict) else r[2]
                    disp = get_status_display(str(st)) if st else ""
                    tb_lines.append(f"{disp or st}: {int(cnt)}개 / {float(kg or 0):,.0f} kg")
            except Exception as e:
                logger.debug("tonbag summary: %s", e)
                tb_lines.append(f"(톤백 요약 조회 오류: {e})")
        else:
            tb_lines.append("(inventory_tonbag 테이블 없음)")

        tk.Label(
            sum_fr,
            text="[현재] inventory_tonbag (실시간)",
            font=("맑은 고딕", 10, "bold"),
            bg=bg,
            fg=fg,
        ).pack(anchor="w")
        tk.Label(
            sum_fr,
            text="  " + ("  |  ".join(tb_lines) if tb_lines else "데이터 없음"),
            font=("맑은 고딕", 9),
            bg=bg,
            fg=fg,
            wraplength=720,
            justify="left",
        ).pack(anchor="w")

        # ── 2) allocation_plan: 배정·예약 이력 ──
        tk.Label(
            sum_fr,
            text="[이력] allocation_plan (상태·SALE REF·톤백 ID 등)",
            font=("맑은 고딕", 10, "bold"),
            bg=bg,
            fg=fg,
        ).pack(anchor="w", pady=(10, 0))

        if not _table_exists(db, "allocation_plan"):
            tk.Label(
                sum_fr,
                text="  allocation_plan 테이블이 없습니다.",
                bg=bg,
                fg=muted,
            ).pack(anchor="w")
            return

        cols_set = _plan_column_names(db)
        if not cols_set:
            tk.Label(sum_fr, text="  allocation_plan 스키마를 읽을 수 없습니다.", bg=bg, fg=muted).pack(
                anchor="w"
            )
            return

        want = [
            "id",
            "tonbag_id",
            "sub_lt",
            "customer",
            "sale_ref",
            "qty_mt",
            "outbound_date",
            "status",
            "created_at",
            "cancelled_at",
            "source_file",
        ]
        sel = [c for c in want if c in cols_set]
        if "id" not in sel and "id" in cols_set:
            sel.insert(0, "id")
        if not sel:
            tk.Label(sum_fr, text="  표시할 컬럼이 없습니다.", bg=bg, fg=muted).pack(anchor="w")
            return

        sql = f"SELECT {', '.join(sel)} FROM allocation_plan WHERE lot_no = ? ORDER BY id DESC"
        try:
            plan_rows = db.fetchall(sql, (lot_no,)) or []
        except Exception as e:
            logger.warning("allocation_plan 조회 실패: %s", e)
            tk.Label(sum_fr, text=f"  조회 오류: {e}", bg=bg, fg=muted).pack(anchor="w")
            return

        tb_fr = tk.Frame(container, bg=bg)
        tb_fr.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        display_cols = tuple(sel)
        tree = ttk.Treeview(tb_fr, columns=display_cols, show="headings", height=14)
        hdr_map = {
            "id": "ID",
            "tonbag_id": "톤백ID",
            "sub_lt": "SubLT",
            "customer": "고객",
            "sale_ref": "SALE REF",
            "qty_mt": "QTY(MT)",
            "outbound_date": "출고일",
            "status": "상태",
            "created_at": "생성",
            "cancelled_at": "취소",
            "source_file": "출처파일",
        }
        w_map = {
            "id": 50,
            "tonbag_id": 70,
            "sub_lt": 55,
            "customer": 120,
            "sale_ref": 100,
            "qty_mt": 72,
            "outbound_date": 88,
            "status": 88,
            "created_at": 130,
            "cancelled_at": 130,
            "source_file": 200,
        }
        for c in display_cols:
            tree.heading(c, text=hdr_map.get(c, c.upper()), anchor='center')
            tree.column(c, width=w_map.get(c, 90), anchor="center")

        vsb = ttk.Scrollbar(tb_fr, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tb_fr, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tb_fr.grid_rowconfigure(0, weight=1)
        tb_fr.grid_columnconfigure(0, weight=1)

        def _row_tb_id(row):
            v = row.get("tonbag_id") if isinstance(row, dict) else None
            return v is not None and str(v).strip() != ""

        _with_tb = sum(1 for r in plan_rows if _row_tb_id(r))
        tk.Label(
            sum_fr,
            text=f"  plan {len(plan_rows)}건 (tonbag_id 지정 {_with_tb}건) · LOT 모드 예약은 tonbag_id 비어 있을 수 있음",
            font=("맑은 고딕", 8),
            bg=bg,
            fg=muted,
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        for r in plan_rows:
            vals = []
            for i, c in enumerate(display_cols):
                if isinstance(r, dict):
                    v = r.get(c)
                else:
                    v = r[i] if i < len(r) else None
                if v is None:
                    vals.append("")
                elif c == "qty_mt":
                    try:
                        vals.append(f"{float(v):.4f}")
                    except (TypeError, ValueError):
                        vals.append(str(v))
                else:
                    s = str(v)
                    vals.append(s[:80] + ("…" if len(s) > 80 else ""))
            tree.insert("", tk.END, values=tuple(vals))

    def _attach_lot_allocation_audit_tab(self, parent, lot_no: str) -> None:
        body = tk.Frame(parent)
        body.pack(fill=tk.BOTH, expand=True)
        self._lot_allocation_audit_fill(body, lot_no)

    def _show_lot_allocation_audit_dialog(self, initial_lot: str = "") -> None:
        """도구 메뉴: LOT 선택 후 allocation_plan + 톤백 요약."""
        if not getattr(self, "engine", None) or not getattr(self.engine, "db", None):
            CustomMessageBox.showwarning(self.root, "확인", "DB가 준비되지 않았습니다.")
            return

        popup = create_themed_toplevel(self.root)
        popup.title("📊 LOT Allocation·톤백 현황")
        setup_dialog_geometry_persistence(popup, "lot_allocation_audit_dialog", self.root, "large")
        popup.transient(self.root)
        popup.grab_set()
        _dark = is_dark()
        bg = ThemeColors.get("bg_card", _dark)
        fg = ThemeColors.get("text_primary", _dark)
        popup.configure(bg=bg)

        top = tk.Frame(popup, bg=bg, padx=10, pady=8)
        top.pack(fill=tk.X)
        tk.Label(top, text="LOT NO:", bg=bg, fg=fg, font=("맑은 고딕", 10)).pack(side=tk.LEFT)
        lot_var = tk.StringVar(value=(initial_lot or "").strip())

        lot_list = []
        try:
            db = self.engine.db
            if _table_exists(db, "allocation_plan"):
                q = """
                    SELECT lot_no FROM (
                        SELECT DISTINCT lot_no FROM inventory
                        WHERE lot_no IS NOT NULL AND TRIM(lot_no) != ''
                        UNION
                        SELECT DISTINCT lot_no FROM allocation_plan
                        WHERE lot_no IS NOT NULL AND TRIM(lot_no) != ''
                    ) ORDER BY lot_no
                """
            else:
                q = (
                    "SELECT DISTINCT lot_no FROM inventory "
                    "WHERE lot_no IS NOT NULL AND TRIM(lot_no) != '' ORDER BY lot_no"
                )
            rows = db.fetchall(q) or []
            lot_list = [
                str(r.get("lot_no") if isinstance(r, dict) else r[0]).strip()
                for r in rows
                if r
            ]
        except Exception as e:
            logger.debug("lot list: %s", e)

        combo = ttk.Combobox(top, textvariable=lot_var, values=lot_list, width=36)
        combo.pack(side=tk.LEFT, padx=8)

        body = tk.Frame(popup, bg=bg)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        def _do_refresh():
            self._lot_allocation_audit_fill(body, lot_var.get())

        btn = ttk.Button(top, text="조회", command=_do_refresh)
        btn.pack(side=tk.LEFT, padx=4)
        apply_tooltip(btn, "선택 LOT의 톤백 요약·allocation_plan 이력을 갱신합니다.")

        ttk.Button(top, text="닫기", command=popup.destroy).pack(side=tk.RIGHT, padx=4)
        popup.bind("<Escape>", lambda e: popup.destroy())

        if lot_var.get():
            popup.after(80, _do_refresh)
