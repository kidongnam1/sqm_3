# -*- coding: utf-8 -*-
"""
v6.6.0 ⑤ 대량 이동 PENDING→Supervisor 승인 UI 헬퍼
----------------------------------------------------
호출: show_move_approval_dialog(parent, engine)
"""
from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import CustomMessageBox, tc
import logging
logger = logging.getLogger(__name__)


def show_move_approval_dialog(parent, engine):
    """PENDING 대량 이동 목록 → 승인/반려 다이얼로그."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        logger.error("tkinter 없음")
        return

    pending = engine.get_pending_batch_moves()

    dlg = create_themed_toplevel(parent)
    dlg.title("📦 대량 이동 승인 — PENDING 목록")
    try:
        from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence as _sgp
        _sgp(dlg, "move_approval_dialog", parent, "large")
    except Exception as e:
        logger.debug(f"Dialog geometry setup skipped: {e}")
    dlg.geometry("760x480")
    dlg.transient(parent)
    dlg.grab_set()

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill='both', expand=True)

    ttk.Label(frm, text="대량 이동 승인 대기 목록",
              font=('', 12, 'bold')).pack(anchor='w', pady=(0, 6))

    cols = ('batch_id', 'total', 'reason', 'submitted_by', 'submitted_at', 'note')
    headers = ('배치 ID', '수량', '사유', '요청자', '요청시각', '비고')

    tree = ttk.Treeview(frm, columns=cols, show='headings', height=12)
    widths = (180, 60, 100, 80, 150, 120)
    for c, h, w in zip(cols, headers, widths):
        tree.heading(c, text=h, anchor='center')
        tree.column(c, width=w, anchor='center')

    for row in pending:
        tree.insert('', 'end', values=(
            row.get('batch_id', ''),
            row.get('total_count', 0),
            row.get('reason_code', ''),
            row.get('submitted_by', ''),
            row.get('submitted_at', ''),
            (row.get('note') or '')[:30],
        ))

    sb = ttk.Scrollbar(frm, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side='left', fill='both', expand=True)
    sb.pack(side='left', fill='y')

    if not pending:
        ttk.Label(frm, text="✅ 승인 대기 항목이 없습니다.",
                  foreground=tc('success')).pack(pady=20)

    btn_frm = ttk.Frame(dlg, padding=8)
    btn_frm.pack(fill='x')

    def _get_sel():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("알림", "배치를 선택하세요.", parent=dlg)
            return None
        vals = tree.item(sel[0])['values']
        return vals[0] if vals else None

    def do_approve():
        bid = _get_sel()
        if not bid:
            return
        if not messagebox.askyesno("승인 확인",
                f"배치 [{bid}] 를 승인하시겠습니까?\n\n"
                "승인 즉시 모든 톤백 위치가 변경됩니다.", parent=dlg):
            return
        res = engine.approve_batch_move(bid, approver='supervisor')
        if res['success']:
            messagebox.showinfo("완료",
                f"✅ 승인 완료\n\n배치: {bid}\n"
                f"적용: {res['applied']}건 / 스킵: {res['skipped']}건", parent=dlg)
            dlg.destroy()
        else:
            messagebox.showerror("오류", f"승인 실패:\n{res.get('error','')}", parent=dlg)

    def do_reject():
        bid = _get_sel()
        if not bid:
            return
        reason = CustomMessageBox.askstring(
            dlg, "반려 사유", f"배치 [{bid}] 반려 사유를 입력하세요:"
        )
        if reason is None:
            return
        res = engine.reject_batch_move(bid, rejector='supervisor', reason=reason)
        if res['success']:
            messagebox.showinfo("완료", f"반려 완료: {bid}", parent=dlg)
            dlg.destroy()
        else:
            messagebox.showerror("오류", res.get('error', ''), parent=dlg)

    ttk.Button(btn_frm, text="✅ 승인", command=do_approve).pack(side='left', padx=4)
    ttk.Button(btn_frm, text="❌ 반려", command=do_reject).pack(side='left', padx=4)
    ttk.Button(btn_frm, text="닫기", command=dlg.destroy).pack(side='right', padx=4)

    ttk.Label(btn_frm,
              text="※ 소량(4개 이하)은 업로드 즉시 반영 / 5개 이상은 승인 후 반영",
              foreground=tc('text_muted')).pack(side='left', padx=10)
