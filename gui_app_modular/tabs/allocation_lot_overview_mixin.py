# -*- coding: utf-8 -*-
"""
v8.1.8 — 판매배정 LOT 통합 현황 (일반 톤백 / 샘플 분리 / 배정 비율)

- 일반 톤백만 총계·AVAILABLE·RESERVED·PICKED·출고 및 배정 비율 분모
- allocation_plan(tonbag_id IS NULL) LOT 모드 MT 합산 (RESERVED)
- 샘플: LOT당 개수 검증(0/1/다수 경고) + 상태 표시(인라인 컬럼)
- 배정 비율: (일반 RESERVED+PICKED+출고 kg + LOT모드 plan MT×1000) / 일반 톤백 총 kg
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_LOV_COLS: Tuple[Tuple[str, str, int, str], ...] = (
    ("row_num", "No.", 44, "center"),
    ("lot_no", "LOT NO", 118, "center"),
    ("sap_no", "SAP NO", 100, "center"),
    ("total_ns", "총 톤백(일반)", 100, "e"),
    ("avail", "AVAILABLE", 120, "e"),
    ("reserved", "RESERVED(배정)", 160, "e"),
    ("picked", "PICKED", 100, "e"),
    ("outbound", "출고", 100, "e"),
    ("alloc_pct", "배정 비율", 72, "e"),
    ("lot_state", "LOT 상태", 88, "center"),
    ("sample_1kg", "샘플(1kg)", 100, "center"),
)


def _abbr_status(st: str) -> str:
    m = {
        "AVAILABLE": "AVAIL",
        "RESERVED": "RSV",
        "PICKED": "PICK",
        "SOLD": "SOLD",
        "OUTBOUND": "OUT",
        "SHIPPED": "SHP",
        "DEPLETED": "DEP",
        "RETURN": "RET",
        "SAMPLE": "SMP",
    }
    return m.get(str(st or "").upper(), (st or "-")[:5])


def _sample_cell(sample_count: int, statuses: List[str]) -> str:
    """샘플 컬럼: 0=없음, 1=상태, 2+=경고. 집계와 행 불일치 시 경고."""
    if sample_count <= 0:
        if statuses:
            return "⚠ 불일치"
        return "없음"
    if sample_count > 1:
        return f"⚠ {sample_count}개?"
    return f"1·{_abbr_status(statuses[0] if statuses else '')}"


def _fmt_ns(n: int, kg: float) -> str:
    if n <= 0 and kg <= 0:
        return "—"
    mt = kg / 1000.0
    return f"{n} ({mt:.1f}MT)"


def _compute_lot_state(
    ns_total: int,
    ns_avail_n: int,
    ns_rsv_n: int,
    ns_pick_n: int,
    ns_out_n: int,
    plan_mt: float,
) -> str:
    if ns_total <= 0 and plan_mt > 0:
        return "FULL RSV"
    if ns_out_n > 0 and ns_avail_n == 0 and ns_rsv_n == 0 and ns_pick_n == 0 and ns_total > 0:
        return "OUTBOUND"
    if ns_pick_n > 0 and ns_avail_n == 0 and ns_rsv_n == 0 and ns_out_n == 0 and ns_total > 0 and ns_pick_n == ns_total:
        return "PICKED"
    if ns_total > 0 and ns_rsv_n == ns_total and ns_avail_n == 0 and ns_pick_n == 0 and ns_out_n == 0:
        return "FULL RSV"
    if ns_rsv_n > 0 or plan_mt > 0.0001 or ns_pick_n > 0 or ns_out_n > 0:
        return "PARTIAL"
    return "AVAILABLE"


def _alloc_ratio_pct(ns_total_kg: float, ns_rsv_kg: float, ns_pick_kg: float, ns_out_kg: float, plan_mt: float) -> int:
    extra = max(0.0, float(plan_mt or 0.0)) * 1000.0
    alloc_kg = float(ns_rsv_kg or 0) + float(ns_pick_kg or 0) + float(ns_out_kg or 0) + extra
    if ns_total_kg <= 0:
        return 0
    return min(100, int(round(100.0 * alloc_kg / ns_total_kg)))


class AllocationLotOverviewMixin:
    """판매배정 탭 — LOT 통합 현황 창."""

    def _fetch_allocation_lot_overview_rows(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        inventory 기준 LOT + inventory_tonbag(일반/샘플 분리) + allocation_plan LOT모드 MT.
        """
        meta: Dict[str, Any] = {"error": None}
        if not getattr(self, "engine", None) or not getattr(self.engine, "db", None):
            meta["error"] = "DB 없음"
            return [], meta
        db = self.engine.db
        rows_out: List[Dict[str, Any]] = []
        try:
            inv_rows = db.fetchall(
                """
                SELECT lot_no, COALESCE(sap_no, '') AS sap_no
                FROM inventory
                WHERE TRIM(COALESCE(lot_no, '')) != ''
                ORDER BY lot_no
                """
            )
        except Exception as e:
            logger.exception("LOT 통합: inventory 조회 실패: %s", e)
            meta["error"] = str(e)
            return [], meta

        try:
            tb_rows = db.fetchall(
                """
                SELECT
                    lot_no,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 THEN 1 ELSE 0 END) AS ns_total,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 THEN COALESCE(weight, 0) ELSE 0 END) AS ns_total_kg,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 AND status = 'AVAILABLE' THEN 1 ELSE 0 END) AS ns_avail_n,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 AND status = 'AVAILABLE' THEN COALESCE(weight, 0) ELSE 0 END) AS ns_avail_kg,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 AND status = 'RESERVED' THEN 1 ELSE 0 END) AS ns_rsv_n,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 AND status = 'RESERVED' THEN COALESCE(weight, 0) ELSE 0 END) AS ns_rsv_kg,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 AND status = 'PICKED' THEN 1 ELSE 0 END) AS ns_pick_n,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 AND status = 'PICKED' THEN COALESCE(weight, 0) ELSE 0 END) AS ns_pick_kg,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 AND status IN ('SOLD','OUTBOUND','SHIPPED','DEPLETED') THEN 1 ELSE 0 END) AS ns_out_n,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 0 AND status IN ('SOLD','OUTBOUND','SHIPPED','DEPLETED') THEN COALESCE(weight, 0) ELSE 0 END) AS ns_out_kg,
                    SUM(CASE WHEN COALESCE(is_sample, 0) = 1 THEN 1 ELSE 0 END) AS sp_count
                FROM inventory_tonbag
                GROUP BY lot_no
                """
            )
        except Exception as e:
            logger.exception("LOT 통합: tonbag 집계 실패: %s", e)
            meta["error"] = str(e)
            return [], meta

        tb_map: Dict[str, Dict[str, Any]] = {}
        for r in tb_rows or []:
            lot = str(r.get("lot_no") or "").strip()
            if lot:
                tb_map[lot] = dict(r)

        try:
            sp_status = db.fetchall(
                """
                SELECT lot_no, status
                FROM inventory_tonbag
                WHERE COALESCE(is_sample, 0) = 1
                """
            )
        except Exception as e:
            logger.debug("LOT 통합: 샘플 상태 조회: %s", e)
            sp_status = []

        sp_by_lot: Dict[str, List[str]] = {}
        for r in sp_status or []:
            lot = str(r.get("lot_no") or "").strip()
            if not lot:
                continue
            sp_by_lot.setdefault(lot, []).append(str(r.get("status") or ""))

        try:
            plan_rows = db.fetchall(
                """
                SELECT ap.lot_no,
                       SUM(COALESCE(ap.qty_mt, 0)) AS plan_mt,
                       MAX(COALESCE(ap.sale_ref, '')) AS sale_ref
                FROM allocation_plan ap
                WHERE ap.status = 'RESERVED' AND ap.tonbag_id IS NULL
                  AND TRIM(COALESCE(ap.lot_no, '')) != ''
                GROUP BY ap.lot_no
                """
            )
        except Exception as e:
            logger.debug("LOT 통합: plan LOT모드: %s", e)
            plan_rows = []

        plan_map: Dict[str, Dict[str, Any]] = {}
        for r in plan_rows or []:
            lot = str(r.get("lot_no") or "").strip()
            if lot:
                plan_map[lot] = dict(r)

        for ir in inv_rows or []:
            lot = str(ir.get("lot_no") or "").strip()
            if not lot:
                continue
            sap = str(ir.get("sap_no") or "").strip()
            t = tb_map.get(lot, {})
            ns_total = int(t.get("ns_total") or 0)
            ns_total_kg = float(t.get("ns_total_kg") or 0)
            ns_avail_n = int(t.get("ns_avail_n") or 0)
            ns_avail_kg = float(t.get("ns_avail_kg") or 0)
            ns_rsv_n = int(t.get("ns_rsv_n") or 0)
            ns_rsv_kg = float(t.get("ns_rsv_kg") or 0)
            ns_pick_n = int(t.get("ns_pick_n") or 0)
            ns_pick_kg = float(t.get("ns_pick_kg") or 0)
            ns_out_n = int(t.get("ns_out_n") or 0)
            ns_out_kg = float(t.get("ns_out_kg") or 0)
            sp_count = int(t.get("sp_count") or 0)
            st_list = sp_by_lot.get(lot, [])
            if len(st_list) != sp_count and sp_count > 0:
                st_list = st_list[: max(1, sp_count)]

            pm = plan_map.get(lot, {})
            plan_mt = float(pm.get("plan_mt") or 0)
            sale_ref = str(pm.get("sale_ref") or "").strip()

            rsv_mt = ns_rsv_kg / 1000.0 + plan_mt
            reserved_txt = "—"
            if ns_rsv_n > 0 or plan_mt > 0.0001:
                reserved_txt = f"{ns_rsv_n} ({rsv_mt:.1f}MT)"
                if sale_ref:
                    reserved_txt += f" · {sale_ref[:16]}"

            pct = _alloc_ratio_pct(ns_total_kg, ns_rsv_kg, ns_pick_kg, ns_out_kg, plan_mt)
            bar = "█" * (pct // 10) + "░" * max(0, 10 - pct // 10)
            ratio_txt = f"{bar} {pct}%"

            state = _compute_lot_state(
                ns_total, ns_avail_n, ns_rsv_n, ns_pick_n, ns_out_n, plan_mt
            )
            has_reserved = ns_rsv_n > 0 or plan_mt > 0.0001
            sample_txt = _sample_cell(sp_count, st_list)

            rows_out.append(
                {
                    "lot_no": lot,
                    "sap_no": sap or "—",
                    "total_ns": f"{ns_total}개" if ns_total else "0",
                    "avail": _fmt_ns(ns_avail_n, ns_avail_kg),
                    "reserved": reserved_txt,
                    "picked": _fmt_ns(ns_pick_n, ns_pick_kg),
                    "outbound": _fmt_ns(ns_out_n, ns_out_kg),
                    "alloc_pct": ratio_txt,
                    "lot_state": state,
                    "sample_1kg": sample_txt,
                    "_filter_state": state,
                    "_has_reserved": has_reserved,
                }
            )

        return rows_out, meta

    def _on_open_allocation_lot_overview(self) -> None:
        """LOT 통합 현황 Toplevel (중복 열리면 앞으로)."""
        root = getattr(self, "root", None)
        wattr = "_alloc_lot_overview_win"
        old = getattr(self, wattr, None)
        try:
            if old is not None and old.winfo_exists():
                old.lift()
                old.focus_force()
                return
        except tk.TclError:
            pass  # TclError: widget destroyed
        from ..utils.ui_constants import create_themed_toplevel, Spacing

        _par = root if root is not None else getattr(tk, "_default_root", None)
        win = create_themed_toplevel(_par, title="LOT 통합 현황 (일반·샘플 분리)")
        try:
            from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence as _sgp
            _sgp(win, "alloc_lot_overview_win", _par, "large")
        except Exception as e:
            logger.warning(f'[UI] allocation_lot_overview_mixin: {e}')
        win.geometry("1180x640")
        setattr(self, wattr, win)

        top = ttk.Frame(win, padding=Spacing.SM)
        top.pack(fill=tk.BOTH, expand=True)

        filt = ttk.Frame(top)
        filt.pack(fill=tk.X, pady=(0, Spacing.SM))
        ttk.Label(filt, text="LOT / SAP 검색").pack(side=tk.LEFT, padx=(0, 4))
        q_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=q_var, width=28).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(filt, text="상태").pack(side=tk.LEFT, padx=(0, 4))
        st_var = tk.StringVar(value="전체")
        states = ("전체", "AVAILABLE", "RESERVED", "PARTIAL", "FULL RSV", "PICKED", "OUTBOUND")
        ttk.Combobox(filt, textvariable=st_var, values=states, width=12, state="readonly").pack(
            side=tk.LEFT, padx=(0, 12)
        )
        show_sample_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filt, text="샘플 컬럼 표시", variable=show_sample_var).pack(side=tk.LEFT, padx=(0, 12))

        cnt_var = tk.StringVar(value="")
        ttk.Label(filt, textvariable=cnt_var).pack(side=tk.LEFT, padx=(8, 0))

        tree_fr = ttk.Frame(top)
        tree_fr.pack(fill=tk.BOTH, expand=True)
        cols = [c[0] for c in _LOV_COLS]
        inner = ttk.Frame(tree_fr)
        inner.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(inner, columns=cols, show="headings", height=22, selectmode="browse")
        for cid, label, width, anchor in _LOV_COLS:
            tree.heading(cid, text=label, anchor="center")
            tree.column(cid, width=width, anchor=anchor, stretch=True)
        sy = tk.Scrollbar(inner, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sy.set, xscrollcommand=None)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = tk.Scrollbar(tree_fr, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(xscrollcommand=sx.set)
        sx.pack(fill=tk.X)

        foot = ttk.Label(
            top,
            text="배정 비율 = (일반 RESERVED·PICKED·출고 중량 + LOT모드 배정 MT) ÷ 일반 톤백 총중량. 샘플(1kg)은 분모·비율에서 제외.",
            font=("맑은 고딕", 8),
            wraplength=1080,
        )
        foot.pack(fill=tk.X, pady=(Spacing.SM, 0))

        def _apply_show_sample() -> None:
            all_ids = [c[0] for c in _LOV_COLS]
            if show_sample_var.get():
                tree["displaycolumns"] = all_ids
            else:
                tree["displaycolumns"] = [c for c in all_ids if c != "sample_1kg"]

        def _refresh() -> None:
            for iid in tree.get_children(""):
                tree.delete(iid)
            raw, meta = self._fetch_allocation_lot_overview_rows()
            if meta.get("error"):
                cnt_var.set(f"오류: {meta['error']}")
                return
            q = q_var.get().strip().upper()
            st_f = st_var.get().strip()
            n_show = 0
            idx = 0
            for r in raw:
                if q and q not in str(r.get("lot_no", "")).upper() and q not in str(r.get("sap_no", "")).upper():
                    continue
                if st_f and st_f != "전체":
                    if st_f == "RESERVED":
                        if not r.get("_has_reserved"):
                            continue
                    elif r.get("_filter_state") != st_f:
                        continue
                idx += 1
                tree.insert(
                    "",
                    "end",
                    values=(
                        str(idx),
                        r["lot_no"],
                        r["sap_no"],
                        r["total_ns"],
                        r["avail"],
                        r["reserved"],
                        r["picked"],
                        r["outbound"],
                        r["alloc_pct"],
                        r["lot_state"],
                        r["sample_1kg"],
                    ),
                )
                n_show += 1
            cnt_var.set(f"{n_show}개 LOT 표시 (전체 {len(raw)} LOT)")

        _apply_show_sample()

        def _on_toggle_sample(*_args) -> None:
            _apply_show_sample()

        show_sample_var.trace_add("write", _on_toggle_sample)

        bf = ttk.Frame(top)
        bf.pack(fill=tk.X, pady=(Spacing.SM, 0))
        ttk.Button(bf, text="조회", command=_refresh).pack(side=tk.LEFT, padx=(0, Spacing.SM))
        ttk.Button(bf, text="닫기", command=win.destroy).pack(side=tk.LEFT)

        _refresh()

        def _on_close() -> None:
            try:
                setattr(self, wattr, None)
            except Exception as e:
                logger.debug("LOT overview close: %s", e)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)
