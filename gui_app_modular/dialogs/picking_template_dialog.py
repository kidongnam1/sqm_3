# -*- coding: utf-8 -*-
"""
SQM v7.4.0 — 출고 피킹 템플릿 관리 다이얼로그 (고객사 프로파일)
=================================================================
설계 원칙: picking_table INSERT + picking_engine에서 실제 사용하는 컬럼만.

DB 컬럼 13개:
  template_id, template_name, customer, customer_code,
  port_loading, port_discharge, delivery_terms,
  contact_person, contact_email,
  bag_weight_kg, storage_location, note, is_active

사용 패턴:
  ① 출고 피킹 버튼 → 팝업 → 고객사 선택 → 피킹 실행 (on_select_callback 모드)
  ② 메뉴 → 피킹 템플릿 관리 → 고객사 추가/편집/삭제 (관리 모드)
"""
from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import is_dark  # v8.0.9
from gui_app_modular.utils.ui_constants import tc  # v8.1.3: top-level import (gui_bootstrap 종속 제거)
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.constants import BOTH, END, LEFT, RIGHT, X, Y, NSEW

logger = logging.getLogger(__name__)

try:
    from gui_app_modular.utils.ui_constants import (
        DialogSize, apply_modal_window_options, center_dialog,
        setup_dialog_geometry_persistence,
    )
except ImportError:
    DialogSize = center_dialog = apply_modal_window_options = None
    setup_dialog_geometry_persistence = None

try:
    from gui_app_modular.utils.custom_messagebox import CustomMessageBox
except ImportError:
    CustomMessageBox = None

try:
    from gui_app_modular.utils.theme_colors import ThemeColors
except ImportError:
    ThemeColors = None

BAG_WEIGHT_OPTIONS  = [500, 1000]
DELIVERY_TERMS_LIST = ['CIF', 'FOB', 'CFR', 'EXW', 'DAP', 'DDP', 'FCA']

# ── DB 헬퍼 ─────────────────────────────────────────────────────────────────

_COLS = [
    'template_id', 'template_name', 'customer', 'customer_code',
    'port_loading', 'port_discharge', 'delivery_terms',
    'contact_person', 'contact_email',
    'bag_weight_kg', 'storage_location', 'note', 'is_active',
]

def load_templates(engine) -> list:
    try:
        rows = engine.db.fetchall(
            f"SELECT {','.join(_COLS)} FROM picking_template "
            "ORDER BY is_active DESC, customer"
        )
        result = []
        for r in (rows or []):
            result.append(dict(r) if hasattr(r, 'keys') else dict(zip(_COLS, r)))
        return result
    except Exception as e:
        logger.error(f"[PickingTemplate] load 오류: {e}")
        return []


def save_template(engine, data: dict) -> bool:
    try:
        engine.db.execute(f"""
            INSERT OR REPLACE INTO picking_template ({','.join(_COLS[:-1])}, is_active)
            VALUES ({','.join(':'+c for c in _COLS[:-1])}, :is_active)
        """, data)
        return True
    except Exception as e:
        logger.error(f"[PickingTemplate] save 오류: {e}")
        return False


def delete_template(engine, template_id: str) -> bool:
    if template_id == 'UNKNOWN_CUSTOMER':
        return False
    try:
        engine.db.execute(
            "DELETE FROM picking_template WHERE template_id=?", (template_id,))
        return True
    except Exception as e:
        logger.error(f"[PickingTemplate] delete 오류: {e}")
        return False


# ── 다이얼로그 ───────────────────────────────────────────────────────────────

class PickingTemplateDialog:
    """출고 피킹 템플릿 관리 다이얼로그."""

    def __init__(self, parent, engine, current_theme='darkly', on_select_callback=None):
        self.parent   = parent
        self.engine   = engine
        self.on_select_callback = on_select_callback
        self._templates: list = []
        self._selected_id: str = ''

        dark_mode = is_dark()
        self.bg = tc('bg_card')

        popup = create_themed_toplevel(parent)
        popup.title('📦 출고 피킹 템플릿 관리')
        popup.transient(parent)
        popup.grab_set()

        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(popup, 'picking_template_dialog', parent, 'large')
        elif DialogSize:
            popup.geometry(DialogSize.get_geometry(parent, 'large'))
            if apply_modal_window_options: apply_modal_window_options(popup)
            if center_dialog: center_dialog(popup, parent)
        else:
            popup.geometry('940x620')
        popup.configure(bg=self.bg)
        self.popup = popup
        self._build_ui()
        self._load_list()
        popup.wait_window()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        _is_select = bool(self.on_select_callback)

        # 헤더 (파란=선택모드 / 짙은회=관리모드)
        hdr = tk.Frame(self.popup,
                       bg=tc('bg_secondary') if _is_select else '#2C3E50',
                       padx=12, pady=8)
        hdr.pack(fill=X)
        _title = ('🔍 출고 피킹 템플릿 선택'
                  if _is_select else '📦 출고 피킹 템플릿 관리')
        _sub   = ('고객사에 맞는 템플릿을 선택하세요. 없으면 ➕신규 → 💾저장 후 선택.'
                  if _is_select
                  else '고객사별 피킹 고정값 관리. 출고 시 자동 주입됩니다.')
        tk.Label(hdr, text=_title,
                 font=('맑은 고딕',13,'bold'), bg=hdr.cget('bg'), fg=tc('text_primary')).pack(anchor='w')
        tk.Label(hdr, text=_sub,
                 font=('맑은 고딕',10), bg=hdr.cget('bg'), fg=tc('text_muted')).pack(anchor='w')

        # 본문
        body = tk.Frame(self.popup, bg=self.bg)
        body.pack(fill=BOTH, expand=True, padx=8, pady=6)

        left = ttk.LabelFrame(body, text='  고객사 목록  ')
        left.pack(side=LEFT, fill=Y, padx=(0,6))
        left.configure(width=220)
        left.pack_propagate(False)
        self._build_list_panel(left)

        right = ttk.LabelFrame(body, text='  상세 편집  ')
        right.pack(side=LEFT, fill=BOTH, expand=True)
        self._build_edit_panel(right)

        # 버튼바
        bar = tk.Frame(self.popup, bg=self.bg, pady=8)
        bar.pack(fill=X, padx=10)
        if _is_select:
            ttk.Button(bar, text='✅ 선택 → 피킹 시작',
                       command=self._on_apply).pack(side=LEFT, padx=(0,14))
            ttk.Separator(bar, orient='vertical').pack(side=LEFT, fill=Y, padx=6, pady=4)
            ttk.Button(bar, text='➕ 신규', command=self._on_new).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='💾 저장', command=self._on_save).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='🗑 삭제', command=self._on_delete).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='취소',   command=self.popup.destroy).pack(side=RIGHT)
        else:
            ttk.Button(bar, text='💾 저장',  command=self._on_save).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='➕ 신규',  command=self._on_new).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='🗑 삭제',  command=self._on_delete).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='닫기',     command=self.popup.destroy).pack(side=RIGHT)

    def _build_list_panel(self, parent):
        sb = tk.Scrollbar(parent, orient='vertical')
        self._list_box = tk.Listbox(
            parent, yscrollcommand=sb.set, selectmode='single',
            font=('맑은 고딕',10), activestyle='dotbox', width=24,
            bg=tc('bg_secondary'), fg=tc('text_primary'),
            selectbackground=tc('select_bg'), selectforeground=tc('text_primary'),
            relief='flat', bd=0)
        sb.config(command=self._list_box.yview)
        self._list_box.pack(side=LEFT, fill=BOTH, expand=True, padx=(4,0), pady=4)
        sb.pack(side=RIGHT, fill=Y, pady=4)
        self._list_box.bind('<<ListboxSelect>>', self._on_list_select)

    def _build_edit_panel(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill=BOTH, expand=True, padx=6, pady=6)
        t1 = ttk.Frame(nb); nb.add(t1, text='  🏭 고객사 기본정보  ')
        t2 = ttk.Frame(nb); nb.add(t2, text='  🚢 물류 정보  ')
        t3 = ttk.Frame(nb); nb.add(t3, text='  📝 메모  ')
        self._build_tab_customer(t1)
        self._build_tab_logistics(t2)
        self._build_tab_note(t3)

    # ── Tab1: 고객사 기본정보 ───────────────────────────────────────────────

    def _build_tab_customer(self, p):
        p.columnconfigure(1, weight=1)
        self._var_id          = tk.StringVar()
        self._var_name        = tk.StringVar()
        self._var_customer    = tk.StringVar()
        self._var_cust_code   = tk.StringVar()
        self._var_contact     = tk.StringVar()
        self._var_email       = tk.StringVar()
        self._var_active      = tk.IntVar(value=1)

        rows = [
            ('템플릿 ID *',   self._var_id,        '예) CATL_CIF  (영문+숫자, 공백없이)'),
            ('템플릿 이름 *', self._var_name,       '예) 🏭 CATL — CIF 광양'),
            ('거래처명 *',    self._var_customer,   '예) CATL, BYD, LG에너지솔루션'),
            ('거래처 코드',   self._var_cust_code,  'sold_to 코드 (SAP 기준, 없으면 공란)'),
            ('담당자',        self._var_contact,    '피킹 리스트 Contact Person'),
            ('이메일',        self._var_email,      '피킹 리스트 Contact Email'),
        ]
        for r_idx, (label, var, tip) in enumerate(rows):
            base = r_idx * 2
            ttk.Label(p, text=label, font=('맑은 고딕',10,'bold'),
                      anchor='e', width=14).grid(
                row=base, column=0, sticky='e', padx=(8,6), pady=(8,0))
            ttk.Entry(p, textvariable=var, font=('맑은 고딕',11)).grid(
                row=base, column=1, sticky='ew', padx=(0,8), pady=(8,0))
            ttk.Label(p, text=tip, font=('맑은 고딕', 10),
                      foreground=tc('text_muted')).grid(
                row=base+1, column=1, sticky='w', padx=(0,8))

        last = len(rows)*2
        ttk.Label(p, text='활성화', font=('맑은 고딕',10,'bold'),
                  anchor='e', width=14).grid(
            row=last, column=0, sticky='e', padx=(8,6), pady=(10,0))
        ttk.Checkbutton(p, text='사용 중', variable=self._var_active).grid(
            row=last, column=1, sticky='w', padx=(0,8), pady=(10,0))

    # ── Tab2: 물류 정보 ────────────────────────────────────────────────────

    def _build_tab_logistics(self, p):
        p.columnconfigure(1, weight=1)
        self._var_port_load   = tk.StringVar(value='GWANGYANG, SOUTH KOREA')
        self._var_port_dis    = tk.StringVar()
        self._var_delivery    = tk.StringVar(value='CIF')
        self._var_bag_weight  = tk.IntVar(value=500)
        self._var_storage     = tk.StringVar(value='1001 GY logistics')

        def row(r, label, widget_fn, tip=None):
            ttk.Label(p, text=label, font=('맑은 고딕',10,'bold'),
                      anchor='e', width=14).grid(
                row=r*2, column=0, sticky='e', padx=(8,6), pady=(8,0))
            widget_fn(r*2)
            if tip:
                ttk.Label(p, text=tip, font=('맑은 고딕', 10),
                          foreground=tc('text_muted')).grid(
                    row=r*2+1, column=1, sticky='w', padx=(0,8))

        def e(var, r):
            ttk.Entry(p, textvariable=var, font=('맑은 고딕',11)).grid(
                row=r, column=1, sticky='ew', padx=(0,8), pady=(8,0))

        def e_delivery(r):
            ttk.Combobox(p, textvariable=self._var_delivery,
                         values=DELIVERY_TERMS_LIST, state='normal',
                         font=('맑은 고딕',11), width=10).grid(
                row=r, column=1, sticky='w', padx=(0,8), pady=(8,0))

        def e_bag(r):
            frm = ttk.Frame(p); frm.grid(row=r, column=1, sticky='w', padx=(0,8), pady=(8,0))
            cb = ttk.Combobox(frm, textvariable=self._var_bag_weight,
                              values=BAG_WEIGHT_OPTIONS, state='readonly',
                              font=('맑은 고딕',11,'bold'), width=8)
            cb.pack(side=LEFT)
            self._bag_badge = tk.Label(frm, text='', font=('맑은 고딕',10,'bold'),
                                       fg=tc('text_primary'), bg=tc('btn_inbound'), relief='flat', padx=6, pady=1)
            self._bag_badge.pack(side=LEFT, padx=(6,0))
            cb.bind('<<ComboboxSelected>>', self._refresh_bag_badge)

        row(0, '선적항',      lambda r: e(self._var_port_load, r),
            '기본값: GWANGYANG, SOUTH KOREA')
        row(1, '양하항 *',    lambda r: e(self._var_port_dis, r),
            '예) TIANJIN, CHINA  /  BUSAN, SOUTH KOREA')
        row(2, '인코텀즈',    e_delivery, 'CIF / FOB / CFR 등')
        row(3, '톤백 단가',   e_bag,      '고객사 요청 단가 (500 or 1000 kg)')
        row(4, '창고 위치',   lambda r: e(self._var_storage, r),
            'picking_table storage_location (예: 1001 GY logistics)')

    def _refresh_bag_badge(self, _=None):
        try:
            v = int(self._var_bag_weight.get())
            bg = tc('success') if v == 500 else tc('warning')
            self._bag_badge.config(text=f'  {v:,} kg  ', bg=bg)
        except Exception:
            logger.debug("[SUPPRESSED] exception in picking_template_dialog.py")  # noqa

    # ── Tab3: 메모 ─────────────────────────────────────────────────────────

    def _build_tab_note(self, p):
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)
        tk.Label(p, text='담당자 메모 (자유 입력)',
                 font=('맑은 고딕',10,'bold'), anchor='w').grid(
            row=0, column=0, sticky='w', padx=8, pady=(8,2))
        self._text_note = tk.Text(p, font=('맑은 고딕',11),
                                  wrap='word', relief='solid', bd=1)
        self._text_note.grid(row=1, column=0, sticky=NSEW, padx=8, pady=(0,8))

    # ── 데이터 ─────────────────────────────────────────────────────────────

    def _load_list(self):
        self._templates = load_templates(self.engine)
        self._list_box.delete(0, END)
        for t in self._templates:
            icon = '✅' if t.get('is_active', 1) else '⛔'
            self._list_box.insert(END, f"{icon} {t['template_name']}")
        if self._templates:
            self._list_box.selection_set(0)
            self._show_template(self._templates[0])

    def _on_list_select(self, _=None):
        sel = self._list_box.curselection()
        if sel and sel[0] < len(self._templates):
            self._show_template(self._templates[sel[0]])

    def _show_template(self, t: dict):
        self._selected_id = t.get('template_id', '')
        self._var_id.set(t.get('template_id', ''))
        self._var_name.set(t.get('template_name', ''))
        self._var_customer.set(t.get('customer', ''))
        self._var_cust_code.set(t.get('customer_code', ''))
        self._var_contact.set(t.get('contact_person', ''))
        self._var_email.set(t.get('contact_email', ''))
        self._var_port_load.set(t.get('port_loading', 'GWANGYANG, SOUTH KOREA'))
        self._var_port_dis.set(t.get('port_discharge', ''))
        self._var_delivery.set(t.get('delivery_terms', 'CIF'))
        self._var_bag_weight.set(t.get('bag_weight_kg', 500))
        self._var_storage.set(t.get('storage_location', '1001 GY logistics'))
        self._var_active.set(t.get('is_active', 1))
        self._text_note.delete('1.0', END)
        self._text_note.insert('1.0', t.get('note', ''))
        self._refresh_bag_badge()

    def _collect_data(self) -> dict:
        return {
            'template_id':      self._var_id.get().strip(),
            'template_name':    self._var_name.get().strip(),
            'customer':         self._var_customer.get().strip(),
            'customer_code':    self._var_cust_code.get().strip(),
            'port_loading':     self._var_port_load.get().strip(),
            'port_discharge':   self._var_port_dis.get().strip(),
            'delivery_terms':   self._var_delivery.get().strip(),
            'contact_person':   self._var_contact.get().strip(),
            'contact_email':    self._var_email.get().strip(),
            'bag_weight_kg':    int(self._var_bag_weight.get()),
            'storage_location': self._var_storage.get().strip(),
            'note':             self._text_note.get('1.0', END).strip(),
            'is_active':        self._var_active.get(),
        }

    # ── 버튼 핸들러 ────────────────────────────────────────────────────────

    def _on_new(self):
        self._show_template({
            'template_id': '', 'template_name': '', 'customer': '',
            'customer_code': '', 'port_loading': 'GWANGYANG, SOUTH KOREA',
            'port_discharge': '', 'delivery_terms': 'CIF',
            'contact_person': '', 'contact_email': '',
            'bag_weight_kg': 500, 'storage_location': '1001 GY logistics',
            'note': '', 'is_active': 1,
        })
        self._selected_id = ''

    def _on_save(self):
        data = self._collect_data()
        # 필수 입력 검증
        for fld, label in [('template_id','템플릿 ID'), ('template_name','템플릿 이름'),
                            ('customer','거래처명')]:
            if not data[fld]:
                messagebox.showwarning('입력 오류', f'{label}을(를) 입력하세요.',
                                       parent=self.popup); return
        if ' ' in data['template_id']:
            messagebox.showwarning('입력 오류', '템플릿 ID에 공백 불가.',
                                   parent=self.popup); return

        if not save_template(self.engine, data):
            messagebox.showerror('저장 오류', '저장 중 오류가 발생했습니다.',
                                 parent=self.popup); return

        # 리스트 갱신 + 저장 항목 선택 유지
        self._load_list()
        for i, t in enumerate(self._templates):
            if t['template_id'] == data['template_id']:
                self._list_box.selection_clear(0, END)
                self._list_box.selection_set(i)
                self._list_box.see(i)
                self._selected_id = data['template_id']
                break

        # 파싱 선택 모드: 저장 직후 "이 템플릿으로 피킹 시작?" 안내
        if self.on_select_callback:
            proceed = messagebox.askyesno(
                '저장 완료',
                f"✅ [{data['template_id']}] 저장 완료!\n\n"
                f"이 템플릿으로 바로 피킹을 시작하시겠습니까?\n\n"
                f"  거래처: {data['customer']}\n"
                f"  인코텀즈: {data['delivery_terms']}  /  단가: {data['bag_weight_kg']:,} kg",
                parent=self.popup,
            )
            if proceed:
                self._on_apply()
        else:
            msg = f"템플릿 [{data['template_id']}] 저장 완료"
            (CustomMessageBox.showinfo(self.popup, '저장 완료', msg)
             if CustomMessageBox else
             messagebox.showinfo('저장 완료', msg, parent=self.popup))

    def _on_delete(self):
        if not self._selected_id:
            messagebox.showwarning('선택 없음', '삭제할 템플릿을 먼저 선택하세요.',
                                   parent=self.popup); return
        if self._selected_id == 'UNKNOWN_CUSTOMER':
            messagebox.showwarning('삭제 불가', '기본 preset(UNKNOWN_CUSTOMER)은 삭제 불가.',
                                   parent=self.popup); return
        if not messagebox.askyesno('삭제 확인',
                                   f'[{self._selected_id}] 를 삭제하시겠습니까?',
                                   parent=self.popup): return
        if delete_template(self.engine, self._selected_id):
            self._load_list()
        else:
            messagebox.showerror('오류', '삭제 실패', parent=self.popup)

    def _on_apply(self):
        """콜백 모드: 선택 템플릿을 피킹에 적용."""
        sel = self._list_box.curselection()
        idx = sel[0] if sel else 0
        t = self._templates[idx] if idx < len(self._templates) else None
        if not t:
            messagebox.showwarning('선택 없음', '템플릿을 선택하세요.',
                                   parent=self.popup); return
        if self.on_select_callback:
            self.on_select_callback(t)
        self.popup.destroy()
