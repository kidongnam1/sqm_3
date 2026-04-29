# -*- coding: utf-8 -*-
"""
SQM v6.2.7 — 제품 마스터 관리 다이얼로그
==========================================
도구 메뉴 > 📦 제품 마스터 관리

기능:
  - 기본 제품 8종 내장 (SQM 표준)
  - 사용자 추가/수정/삭제
  - 약칭(code), Full Name, 한글명, 톤백 지원 여부
  - 제품 코드 자동 연동 (입고 시 product_code 참조)
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  기본 제품 데이터 (SQM 표준 8종)
# ═══════════════════════════════════════════════════════════

DEFAULT_PRODUCTS = [
    ('NSH', 'Nickel Sulfate Hexahydrate',    '황산니켈',         1, 1),
    ('LCA', 'Lithium Carbonate Anhydrous',   '탄산리튬',         1, 1),
    ('CSH', 'Cobalt Sulfate Heptahydrate',   '황산코발트',       0, 1),
    ('NCM', 'Nickel Cobalt Manganese',       '니켈코발트망간',    0, 1),
    ('NCA', 'Nickel Cobalt Aluminum',        '니켈코발트알루미늄', 0, 1),
    ('LFP', 'Lithium Iron Phosphate',        '리튬인산철',       0, 1),
    ('LMO', 'Lithium Manganese Oxide',       '리튬망간산화물',    0, 1),
    ('LCO', 'Lithium Cobalt Oxide',          '리튬코발트산화물',  0, 1),
]
# (code, full_name, korean_name, tonbag_support, is_default)


def ensure_product_master_table(db) -> None:
    """product_master 테이블 생성 + 기본 데이터 삽입."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS product_master (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    NOT NULL UNIQUE,
            full_name   TEXT    NOT NULL,
            korean_name TEXT    NOT NULL DEFAULT '',
            tonbag_support INTEGER NOT NULL DEFAULT 0,
            is_default  INTEGER NOT NULL DEFAULT 0,
            is_active   INTEGER NOT NULL DEFAULT 1,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT,
            updated_at  TEXT
        )
    """)
    # 기본 데이터 삽입 (중복 무시)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for idx, (code, full_name, korean_name, tonbag, is_def) in enumerate(DEFAULT_PRODUCTS):
        try:
            db.execute(
                """INSERT OR IGNORE INTO product_master 
                   (code, full_name, korean_name, tonbag_support, is_default, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (code, full_name, korean_name, tonbag, is_def, idx * 10, now)
            )
        except Exception as e:
            logger.debug(f"product_master 기본 데이터 삽입 스킵: {code} - {e}")
    try:
        db.commit()
    except Exception:
        logger.debug("[SUPPRESSED] exception in product_master_dialog.py")  # noqa


def get_all_products(db, active_only: bool = True):
    """제품 목록 조회."""
    sql = "SELECT * FROM product_master"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY sort_order, code"
    return db.fetchall(sql) or []


def get_product_by_code(db, code: str):
    """코드로 제품 조회."""
    return db.fetchone(
        "SELECT * FROM product_master WHERE code = ?", (code.upper().strip(),))


def add_product(db, code: str, full_name: str, korean_name: str = '',
                tonbag_support: bool = False) -> dict:
    """제품 추가."""
    result = {'success': False, 'message': ''}
    code = code.upper().strip()
    if not code:
        result['message'] = '제품 코드를 입력하세요.'
        return result
    if not full_name.strip():
        result['message'] = '영문 제품명을 입력하세요.'
        return result
    if len(code) > 10:
        result['message'] = '제품 코드는 최대 10자입니다.'
        return result

    existing = get_product_by_code(db, code)
    if existing:
        result['message'] = f'이미 존재하는 코드: {code}'
        return result

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        max_row = db.fetchone("SELECT MAX(sort_order) as mx FROM product_master")
        max_order = (max_row.get('mx') or 0) if max_row else 0

        db.execute(
            """INSERT INTO product_master 
               (code, full_name, korean_name, tonbag_support, is_default, sort_order, created_at)
               VALUES (?, ?, ?, ?, 0, ?, ?)""",
            (code, full_name.strip(), korean_name.strip(),
             1 if tonbag_support else 0, max_order + 10, now)
        )
        db.commit()
        result['success'] = True
        result['message'] = f'제품 추가 완료: {code}'
    except Exception as e:
        result['message'] = f'추가 실패: {e}'
    return result


def update_product(db, product_id: int, code: str, full_name: str,
                   korean_name: str, tonbag_support: bool) -> dict:
    """제품 수정."""
    result = {'success': False, 'message': ''}
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        db.execute(
            """UPDATE product_master 
               SET code=?, full_name=?, korean_name=?, tonbag_support=?, updated_at=?
               WHERE id=?""",
            (code.upper().strip(), full_name.strip(), korean_name.strip(),
             1 if tonbag_support else 0, now, product_id)
        )
        db.commit()
        result['success'] = True
        result['message'] = f'수정 완료: {code}'
    except Exception as e:
        result['message'] = f'수정 실패: {e}'
    return result


def delete_product(db, product_id: int) -> dict:
    """제품 삭제 (비활성화)."""
    result = {'success': False, 'message': ''}
    try:
        row = db.fetchone("SELECT code, is_default FROM product_master WHERE id=?", (product_id,))
        if not row:
            result['message'] = '제품을 찾을 수 없습니다.'
            return result
        if row.get('is_default'):
            result['message'] = f'기본 제품({row["code"]})은 삭제할 수 없습니다.'
            return result

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            "UPDATE product_master SET is_active=0, updated_at=? WHERE id=?",
            (now, product_id))
        db.commit()
        result['success'] = True
        result['message'] = f'삭제 완료: {row["code"]}'
    except Exception as e:
        result['message'] = f'삭제 실패: {e}'
    return result


# ═══════════════════════════════════════════════════════════
#  GUI 다이얼로그
# ═══════════════════════════════════════════════════════════

def show_product_master_dialog(app) -> None:
    """제품 마스터 관리 다이얼로그 표시."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        return
    try:
        from gui_app_modular.utils.ui_constants import setup_dialog_geometry_persistence, tc
    except ImportError:
        setup_dialog_geometry_persistence = None

    engine = getattr(app, 'engine', None)
    if not engine:
        messagebox.showerror("오류", "엔진이 초기화되지 않았습니다.")
        return

    db = engine.db
    ensure_product_master_table(db)

    root = getattr(app, 'root', app)
    # ─── 메인 윈도우 ───
    dlg = create_themed_toplevel(app)
    dlg.title("📦 제품 마스터 관리")
    dlg.resizable(True, True)
    dlg.transient(app)
    dlg.grab_set()
    if setup_dialog_geometry_persistence:
        setup_dialog_geometry_persistence(dlg, "product_master_dialog", root, "medium")
    else:
        dlg.geometry("780x520")

    # ─── 상단 설명 ───
    header = ttk.Frame(dlg, padding=8)
    header.pack(fill='x')
    ttk.Label(header, text="📦 제품 마스터 관리",
              font=('', 13, 'bold')).pack(side='left')
    ttk.Label(header, text="  (기본 제품은 수정만 가능, 삭제 불가)",
              foreground=tc('text_muted')).pack(side='left')

    # ─── Treeview ───
    tree_frame = ttk.Frame(dlg, padding=(8, 0, 8, 4))
    tree_frame.pack(fill='both', expand=True)

    columns = ('code', 'full_name', 'korean_name', 'tonbag', 'type')
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                        height=12, selectmode='browse')

    tree.heading('code', text='약칭', anchor='center')
    tree.heading('full_name', text='Full Name', anchor='center')
    tree.heading('korean_name', text='한글명', anchor='center')
    tree.heading('tonbag', text='톤백지원', anchor='center')
    tree.heading('type', text='구분', anchor='center')
    tree.column('code', width=60, anchor='center')
    tree.column('full_name', width=280, anchor='w')
    tree.column('korean_name', width=160, anchor='w')
    tree.column('tonbag', width=70, anchor='center')
    tree.column('type', width=70, anchor='center')

    scrollbar = tk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    # v8.1.8: 가로 스크롤바 추가
    _xsb = tk.Scrollbar(tree_frame, orient='horizontal', command=tree.xview)
    tree.configure(xscrollcommand=_xsb.set)
    _xsb.pack(side='bottom', fill='x')

    # ─── 입력 폼 ───
    form_frame = ttk.LabelFrame(dlg, text=" 제품 정보 ", padding=10)
    form_frame.pack(fill='x', padx=8, pady=4)

    row0 = ttk.Frame(form_frame)
    row0.pack(fill='x', pady=2)
    ttk.Label(row0, text="약칭:", width=8).pack(side='left')
    code_var = tk.StringVar()
    code_entry = ttk.Entry(row0, textvariable=code_var, width=12)
    code_entry.pack(side='left', padx=(0, 15))

    ttk.Label(row0, text="Full Name:", width=10).pack(side='left')
    fullname_var = tk.StringVar()
    ttk.Entry(row0, textvariable=fullname_var, width=35).pack(side='left', padx=(0, 15))

    row1 = ttk.Frame(form_frame)
    row1.pack(fill='x', pady=2)
    ttk.Label(row1, text="한글명:", width=8).pack(side='left')
    korean_var = tk.StringVar()
    ttk.Entry(row1, textvariable=korean_var, width=20).pack(side='left', padx=(0, 15))

    tonbag_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(row1, text="톤백 지원 (용기스펙)", variable=tonbag_var).pack(side='left', padx=(0, 15))

    # 숨은 변수
    selected_id = tk.IntVar(value=0)

    # ─── 버튼 ───
    btn_frame = ttk.Frame(dlg, padding=8)
    btn_frame.pack(fill='x')

    def _refresh():
        """목록 갱신."""
        tree.delete(*tree.get_children())
        products = get_all_products(db)
        for p in products:
            p = dict(p) if not isinstance(p, dict) else p
            tonbag_txt = "✅" if p.get('tonbag_support') else "❌"
            type_txt = "기본" if p.get('is_default') else "사용자"
            tree.insert('', 'end', iid=str(p['id']),
                        values=(p['code'], p['full_name'],
                                p['korean_name'], tonbag_txt, type_txt))

    def _on_select(event):
        """트리 선택 → 폼에 로드."""
        sel = tree.selection()
        if not sel:
            return
        pid = int(sel[0])
        selected_id.set(pid)
        row = db.fetchone("SELECT * FROM product_master WHERE id=?", (pid,))
        if row:
            row = dict(row) if not isinstance(row, dict) else row
            code_var.set(row.get('code', ''))
            fullname_var.set(row.get('full_name', ''))
            korean_var.set(row.get('korean_name', ''))
            tonbag_var.set(bool(row.get('tonbag_support', 0)))

    tree.bind('<<TreeviewSelect>>', _on_select)

    def _clear_form():
        """폼 초기화."""
        selected_id.set(0)
        code_var.set('')
        fullname_var.set('')
        korean_var.set('')
        tonbag_var.set(False)
        tree.selection_remove(*tree.selection())

    def _on_add():
        """추가."""
        r = add_product(db, code_var.get(), fullname_var.get(),
                        korean_var.get(), tonbag_var.get())
        if r['success']:
            _refresh()
            _clear_form()
            messagebox.showinfo("완료", r['message'], parent=dlg)
        else:
            messagebox.showwarning("실패", r['message'], parent=dlg)

    def _on_update():
        """수정."""
        pid = selected_id.get()
        if pid <= 0:
            messagebox.showwarning("선택", "수정할 제품을 선택하세요.", parent=dlg)
            return
        r = update_product(db, pid, code_var.get(), fullname_var.get(),
                           korean_var.get(), tonbag_var.get())
        if r['success']:
            _refresh()
            messagebox.showinfo("완료", r['message'], parent=dlg)
        else:
            messagebox.showwarning("실패", r['message'], parent=dlg)

    def _on_delete():
        """삭제."""
        pid = selected_id.get()
        if pid <= 0:
            messagebox.showwarning("선택", "삭제할 제품을 선택하세요.", parent=dlg)
            return
        if not messagebox.askyesno("확인", "선택한 제품을 삭제하시겠습니까?", parent=dlg):
            return
        r = delete_product(db, pid)
        if r['success']:
            _refresh()
            _clear_form()
            messagebox.showinfo("완료", r['message'], parent=dlg)
        else:
            messagebox.showwarning("실패", r['message'], parent=dlg)

    ttk.Button(btn_frame, text="➕ 추가", width=10, command=_on_add).pack(side='left', padx=4)
    ttk.Button(btn_frame, text="✏️ 수정", width=10, command=_on_update).pack(side='left', padx=4)
    ttk.Button(btn_frame, text="🗑️ 삭제", width=10, command=_on_delete).pack(side='left', padx=4)
    ttk.Button(btn_frame, text="🔄 초기화", width=10, command=_clear_form).pack(side='left', padx=4)
    ttk.Button(btn_frame, text="닫기", width=10,
               command=dlg.destroy).pack(side='right', padx=4)

    # 초기 로드
    _refresh()

    dlg.wait_window()
