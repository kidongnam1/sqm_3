# -*- coding: utf-8 -*-
"""
SQM v6.2.7 — 제품별 재고 현황 리포트 다이얼로그
=================================================
도구 메뉴 > 📊 제품별 재고 현황
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def show_product_inventory_report(app) -> None:
    """제품별 재고 현황 리포트 다이얼로그."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, filedialog
    except ImportError:
        return

    engine = getattr(app, 'engine', None)
    if not engine:
        messagebox.showerror("오류", "엔진이 초기화되지 않았습니다.")
        return

    try:
        from .product_master_helper import get_product_inventory_report
        from .product_master_dialog import ensure_product_master_table
        ensure_product_master_table(engine.db)
    except ImportError:
        messagebox.showerror("오류", "제품 마스터 모듈을 찾을 수 없습니다.")
        return

    try:
        from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence, tc
    except ImportError:
        setup_dialog_geometry_persistence = None

    root = getattr(app, 'root', app)
    # ─── 메인 윈도우 ───
    dlg = create_themed_toplevel(app)
    dlg.title("📊 제품별 재고 현황 리포트")
    dlg.resizable(True, True)
    dlg.transient(app)
    dlg.grab_set()
    if setup_dialog_geometry_persistence:
        setup_dialog_geometry_persistence(dlg, "product_inventory_report", root, "large")
    else:
        dlg.geometry("900x500")

    # ─── 상단 ───
    header = ttk.Frame(dlg, padding=8)
    header.pack(fill='x')
    ttk.Label(header, text="📊 제품별 재고 현황",
              font=('', 13, 'bold')).pack(side='left')
    ttk.Label(header, text=f"  ({datetime.now():%Y-%m-%d %H:%M})",
              foreground=tc('text_muted')).pack(side='left')

    # ─── Treeview ───
    tree_frame = ttk.Frame(dlg, padding=(8, 0, 8, 4))
    tree_frame.pack(fill='both', expand=True)

    columns = ('code', 'product', 'korean', 'lots', 'tonbags',
               'total', 'available', 'reserved', 'picked')
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                        height=15, selectmode='browse')

    headings = [
        ('code', '코드', 60),
        ('product', '제품명', 220),
        ('korean', '한글명', 120),
        ('lots', 'LOT수', 60),
        ('tonbags', '톤백수', 60),
        ('total', '총 중량(kg)', 110),
        ('available', '가용(kg)', 100),
        ('reserved', '예약(kg)', 100),
        ('picked', '출고(kg)', 100),
    ]
    for cid, text, width in headings:
        tree.heading(cid, text=text, anchor='center')
        align = 'center' if cid in ('code', 'lots', 'tonbags') else ('e' if 'kg' in text or '중량' in text else 'w')
        tree.column(cid, width=width, anchor=align)

    scrollbar = tk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    # v8.1.8: 가로 스크롤바 추가
    _xsb = tk.Scrollbar(tree_frame, orient='horizontal', command=tree.xview)
    tree.configure(xscrollcommand=_xsb.set)
    _xsb.pack(side='bottom', fill='x')
    # v8.1.8: 합계 footer
    from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter
    _footer = TreeviewTotalFooter(
        dlg, tree,
        summable_column_ids=['total', 'available', 'reserved', 'picked'],
        column_display_names={'total':'총중량(kg)','available':'가용(kg)','reserved':'예약(kg)','picked':'출고(kg)'},
    )
    _footer.pack(fill='x', padx=6)

    # ─── 요약 ───
    summary_frame = ttk.Frame(dlg, padding=8)
    summary_frame.pack(fill='x')
    summary_lbl = ttk.Label(summary_frame, text="", font=('', 10))
    summary_lbl.pack(side='left')

    def _refresh():
        tree.delete(*tree.get_children())
        data = get_product_inventory_report(engine.db)

        total_lots = 0
        total_bags = 0
        total_kg = 0
        total_avail = 0

        for d in data:
            d = dict(d) if not isinstance(d, dict) else d
            code = d.get('code', '')
            full_name = d.get('full_name', d.get('product', ''))
            korean = d.get('korean_name', '')
            lots = d.get('lot_count', 0)
            bags = d.get('tonbag_count', 0)
            total = d.get('total_kg', 0)
            avail = d.get('available_kg', d.get('current_kg', 0))
            reserved = d.get('reserved_kg', 0)
            picked = d.get('picked_kg', 0)

            tree.insert('', 'end', values=(
                code, full_name, korean, lots, bags,
                f"{total:,.1f}", f"{avail:,.1f}",
                f"{reserved:,.1f}", f"{picked:,.1f}"
            ))

            total_lots += lots
            total_bags += bags
            total_kg += total
            total_avail += avail

        summary_lbl.config(
            text=f"합계: {len(data)}개 제품 | {total_lots} LOT | "
                 f"{total_bags} 톤백 | 총 {total_kg:,.1f}kg | "
                 f"가용 {total_avail:,.1f}kg"
        )

    def _export_excel():
        """Excel 내보내기."""
        try:
            import openpyxl
        except ImportError:
            messagebox.showwarning("안내", "openpyxl 미설치", parent=dlg)
            return

        path = filedialog.asksaveasfilename(
            parent=dlg,
            title="제품별 재고 현황 저장",
            defaultextension='.xlsx',
            filetypes=[('Excel', '*.xlsx')],
            initialfilename=f"제품별재고현황_{datetime.now():%Y%m%d}.xlsx"
        )
        if not path:
            return

        try:
            data = get_product_inventory_report(engine.db)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "제품별 재고"

            headers = ['코드', '제품명', '한글명', 'LOT수', '톤백수',
                       '총중량(kg)', '가용(kg)', '예약(kg)', '출고(kg)']
            ws.append(headers)

            for d in data:
                d = dict(d) if not isinstance(d, dict) else d
                ws.append([
                    d.get('code', ''),
                    d.get('full_name', d.get('product', '')),
                    d.get('korean_name', ''),
                    d.get('lot_count', 0),
                    d.get('tonbag_count', 0),
                    d.get('total_kg', 0),
                    d.get('available_kg', d.get('current_kg', 0)),
                    d.get('reserved_kg', 0),
                    d.get('picked_kg', 0),
                ])

            try:
                from utils.sqm_excel_alignment import apply_sqm_workbook_alignment
                apply_sqm_workbook_alignment(wb)
            except Exception:
                pass
            wb.save(path)
            messagebox.showinfo("완료", f"저장 완료:\n{path}", parent=dlg)
        except Exception as e:
            messagebox.showerror("오류", f"저장 실패:\n{e}", parent=dlg)

    # ─── 하단 버튼 ───
    btn_frame = ttk.Frame(dlg, padding=8)
    btn_frame.pack(fill='x')
    ttk.Button(btn_frame, text="🔄 새로고침", command=_refresh).pack(side='left', padx=4)
    ttk.Button(btn_frame, text="📥 Excel 저장", command=_export_excel).pack(side='left', padx=4)
    ttk.Button(btn_frame, text="닫기", command=dlg.destroy).pack(side='right', padx=4)

    _refresh()
    dlg.wait_window()
