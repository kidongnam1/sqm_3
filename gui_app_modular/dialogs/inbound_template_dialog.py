# -*- coding: utf-8 -*-
"""
SQM v7.2.0 — 입고 파싱 템플릿 관리 다이얼로그 (슬림 버전)
============================================================
설계 원칙: 파싱 파이프라인에서 실제로 사용하는 컬럼만 유지.

DB 컬럼(슬림 + bl_format):
  template_id, template_name, carrier_id, bag_weight_kg,
  product_hint, weight_format, bl_format,
  gemini_hint_packing, gemini_hint_invoice, gemini_hint_bl,
  note, is_active
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

# v6.7.3: CARRIER_OPTIONS → engine_modules.constants에서 중앙 관리
from engine_modules.constants import CARRIER_OPTIONS  # noqa: E402
BAG_WEIGHT_OPTIONS = [500, 1000]


def load_templates(engine) -> list:
    try:
        rows = engine.db.fetchall(
            "SELECT template_id,template_name,carrier_id,bag_weight_kg,"
            "product_hint,weight_format,COALESCE(bl_format,'') AS bl_format,"
            "gemini_hint_packing,gemini_hint_invoice,gemini_hint_bl,"
            "note,is_active "
            "FROM inbound_template "
            "ORDER BY is_active DESC,carrier_id,bag_weight_kg"
        )
        result = []
        KEYS = ['template_id','template_name','carrier_id','bag_weight_kg',
                'product_hint','weight_format','bl_format',
                'gemini_hint_packing','gemini_hint_invoice','gemini_hint_bl',
                'note','is_active']
        for r in (rows or []):
            if hasattr(r, 'keys'):
                result.append(dict(r))
            else:
                result.append(dict(zip(KEYS, r)))
        return result
    except Exception as e:
        logger.error(f"[InboundTemplate] load 오류: {e}")
        return []


def save_template(engine, data: dict) -> bool:
    try:
        engine.db.execute("""
            INSERT OR REPLACE INTO inbound_template (
                template_id,template_name,carrier_id,bag_weight_kg,
                product_hint,weight_format,bl_format,
                gemini_hint_packing,gemini_hint_invoice,gemini_hint_bl,
                note,is_active
            ) VALUES (
                :template_id,:template_name,:carrier_id,:bag_weight_kg,
                :product_hint,:weight_format,:bl_format,
                :gemini_hint_packing,:gemini_hint_invoice,:gemini_hint_bl,
                :note,:is_active
            )
        """, data)
        return True
    except Exception as e:
        logger.error(f"[InboundTemplate] save 오류: {e}")
        return False


def delete_template(engine, template_id: str) -> bool:
    if template_id.startswith('UNKNOWN_'):
        return False
    try:
        engine.db.execute(
            "DELETE FROM inbound_template WHERE template_id=?", (template_id,))
        return True
    except Exception as e:
        logger.error(f"[InboundTemplate] delete 오류: {e}")
        return False


class InboundTemplateDialog:
    """입고 파싱 템플릿 관리 다이얼로그."""

    def __init__(self, parent, engine, current_theme='darkly', on_select_callback=None):
        self.parent = parent
        self.engine = engine
        self.on_select_callback = on_select_callback
        self._templates = []
        self._selected_id = ''

        dark_mode = is_dark()
        self.bg = tc('bg_card') if dark_mode else tc('bg_card')

        popup = create_themed_toplevel(parent)
        popup.title('📋 입고 파싱 템플릿 관리')
        popup.transient(parent)
        popup.grab_set()
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(popup,'inbound_template_dialog',parent,'large')
        elif DialogSize:
            popup.geometry(DialogSize.get_geometry(parent,'large'))
            if apply_modal_window_options: apply_modal_window_options(popup)
            if center_dialog: center_dialog(popup, parent)
        else:
            popup.geometry('940x620')
        popup.configure(bg=self.bg)
        self.popup = popup
        try:
            self._build_ui()
        except Exception as _e:
            import tkinter.messagebox as _mb
            _mb.showerror('템플릿 관리 오류', f'UI 로드 실패: {_e}')
            logger.error('[InboundTemplate] _build_ui 오류: %s', _e, exc_info=True)
            popup.destroy()
            return
        self._load_list()
        popup.wait_window()

    def _build_ui(self):
        # ── 모드 구분 ──────────────────────────────────────────────────────────
        _is_select_mode = bool(self.on_select_callback)

        # 헤더 (모드별 텍스트)
        hdr = tk.Frame(self.popup, bg=tc('bg_secondary') if _is_select_mode else '#2C3E50',
                       padx=12, pady=8)
        hdr.pack(fill=X)
        _title = ('🔍 파싱 템플릿 선택'
                  if _is_select_mode else '📋 입고 파싱 템플릿 관리')
        _subtitle = ('선사·단가에 맞는 템플릿을 선택하세요. 없으면 ➕신규 → 💾저장 후 선택.'
                     if _is_select_mode
                     else '선사 + 단가별 파싱 설정. 파이프라인에서 실제 사용하는 항목만 관리합니다.')
        tk.Label(hdr, text=_title,
                 font=('맑은 고딕',13,'bold'), bg=hdr.cget('bg'), fg=tc('text_primary')).pack(anchor='w')
        tk.Label(hdr, text=_subtitle,
                 font=('맑은 고딕',10), bg=hdr.cget('bg'), fg=tc('text_muted')).pack(anchor='w')

        # 본문 — 좌우 드래그로 폭 조절 (Panedwindow)
        body = tk.Frame(self.popup, bg=self.bg)
        body.pack(fill=BOTH, expand=True, padx=8, pady=6)

        paned = ttk.Panedwindow(body, orient='horizontal')
        paned.pack(fill=BOTH, expand=True)

        left = ttk.LabelFrame(paned, text='  템플릿 목록  ')
        self._build_list_panel(left)
        paned.add(left, weight=1)

        right = ttk.LabelFrame(paned, text='  상세 편집  ')
        self._build_edit_panel(right)
        paned.add(right, weight=3)

        try:
            paned.pane(left, minsize=140)
            paned.pane(right, minsize=300)
        except tk.TclError as _e:
            logger.debug(f"[InboundTemplate] paned minsize 무시: {_e}")

        # 하단 버튼바
        bar = tk.Frame(self.popup, bg=self.bg, pady=8)
        bar.pack(fill=X, padx=10)

        if _is_select_mode:
            # 파싱 선택 모드: [✅ 선택→파싱 시작]  [💾 저장]  [➕ 신규]  [🗑 삭제]  [취소]
            ttk.Button(bar, text='✅ 선택 → 파싱 시작',
                       command=self._on_apply).pack(side=LEFT, padx=(0,14))
            ttk.Separator(bar, orient='vertical').pack(side=LEFT, fill=Y, padx=6, pady=4)
            ttk.Button(bar, text='➕ 신규', command=self._on_new).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='💾 저장', command=self._on_save).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='🗑 삭제', command=self._on_delete).pack(side=LEFT, padx=2)
            ttk.Button(bar, text='취소',   command=self.popup.destroy).pack(side=RIGHT)
        else:
            # 관리 모드: [💾 저장]  [➕ 신규]  [🗑 삭제]  [닫기]
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
        t1 = ttk.Frame(nb); nb.add(t1, text='  📌 기본정보  ')
        t2 = ttk.Frame(nb); nb.add(t2, text='  🤖 Gemini 힌트  ')
        t3 = ttk.Frame(nb); nb.add(t3, text='  📝 메모  ')
        self._build_tab_basic(t1)
        self._build_tab_gemini(t2)
        self._build_tab_note(t3)

    def _build_tab_basic(self, p):
        p.columnconfigure(1, weight=1)
        self._var_id           = tk.StringVar()
        self._var_name         = tk.StringVar()
        self._var_carrier      = tk.StringVar(value='UNKNOWN')
        self._var_bag_weight   = tk.IntVar(value=500)
        self._var_product_hint = tk.StringVar(value='LITHIUM CARBONATE')
        self._var_weight_fmt   = tk.StringVar(value='EURO')
        self._var_bl_format    = tk.StringVar(value='')   # v8.0.0: BL 번호 형식
        self._var_active       = tk.IntVar(value=1)

        def row(r, label, widget_fn, tip=None):
            ttk.Label(p, text=label, font=('맑은 고딕',10,'bold'),
                      anchor='e', width=16).grid(
                row=r*2, column=0, sticky='e', padx=(8,6), pady=(8,0))
            widget_fn(r*2)
            if tip:
                ttk.Label(p, text=tip, font=('맑은 고딕', 10),
                          foreground=tc('text_muted')).grid(
                    row=r*2+1, column=1, sticky='w', padx=(0,8))

        def e_id(r):
            ttk.Entry(p, textvariable=self._var_id,
                      font=('맑은 고딕',11)).grid(row=r,column=1,sticky='ew',padx=(0,8),pady=(8,0))
        def e_name(r):
            ttk.Entry(p, textvariable=self._var_name,
                      font=('맑은 고딕',11)).grid(row=r,column=1,sticky='ew',padx=(0,8),pady=(8,0))
        def e_carrier(r):
            ttk.Combobox(p, textvariable=self._var_carrier, values=CARRIER_OPTIONS,
                         state='normal', font=('맑은 고딕',11), width=18).grid(
                row=r,column=1,sticky='w',padx=(0,8),pady=(8,0))
        def e_bag(r):
            frm=ttk.Frame(p); frm.grid(row=r,column=1,sticky='w',padx=(0,8),pady=(8,0))
            cb=ttk.Combobox(frm, textvariable=self._var_bag_weight,
                            values=BAG_WEIGHT_OPTIONS,state='readonly',
                            font=('맑은 고딕',11,'bold'),width=8)
            cb.pack(side=LEFT)
            self._bag_badge=tk.Label(frm,text='',font=('맑은 고딕',10,'bold'),
                                     fg=tc('text_primary'),bg=tc('btn_report'),relief='flat',padx=6,pady=1)
            self._bag_badge.pack(side=LEFT,padx=(6,0))
            cb.bind('<<ComboboxSelected>>',self._refresh_bag_badge)
        def e_prod(r):
            ttk.Entry(p, textvariable=self._var_product_hint,
                      font=('맑은 고딕',11)).grid(row=r,column=1,sticky='ew',padx=(0,8),pady=(8,0))
        def e_wfmt(r):
            ttk.Combobox(p, textvariable=self._var_weight_fmt,
                         values=['EURO','US'],state='readonly',
                         font=('맑은 고딕',11),width=8).grid(
                row=r,column=1,sticky='w',padx=(0,8),pady=(8,0))

        row(0,'템플릿 ID *',  e_id,    '예) MSC_LC500  (영문+숫자, 공백없이)')
        row(1,'템플릿 이름 *',e_name,  '예) 🚢 MSC — 리튬카보네이트 500 kg')
        row(2,'선사',         e_carrier)
        row(3,'톤백 단가(kg)',e_bag)
        row(4,'제품 힌트',    e_prod,  'Gemini에 전달할 제품명 (예: LITHIUM CARBONATE)')
        row(5,'중량 표기',    e_wfmt,  'EURO: 5.001,5 → 5001.5  /  US: 5,001.5 → 5001.5')

        # v8.0.0: BL 번호 형식
        def e_bl_fmt(r):
            frm = ttk.Frame(p); frm.grid(row=r, column=1, sticky='w', padx=(0,8), pady=(8,0))
            BL_FMT_OPTIONS = ['', '숫자9', '숫자10', '숫자11', '숫자12',
                              'MSCU7', 'MEDU7', 'COSU7', 'EVER7',
                              'HMMU7', 'ONEU7', 'HLCU7', 'YMLU7', 'CMA7']
            ttk.Combobox(frm, textvariable=self._var_bl_format,
                         values=BL_FMT_OPTIONS, state='normal',
                         font=('맑은 고딕', 11), width=12).pack(side=tk.LEFT)
            ttk.Label(frm, text='  예) 숫자9=MAERSK, MSCU7=MSC',
                      font=('맑은 고딕', 10), foreground=tc('text_muted')).pack(side=tk.LEFT)

        row(
            6,
            'BL 번호 형식',
            e_bl_fmt,
            '형식(숫자9·MSCU7 등)은 여기서 선택. 실제 BL 문구·샘플은 「🤖 Gemini 힌트」→「🚢 B/L 힌트」에 입력.',
        )

        ttk.Label(p,text='활성화',font=('맑은 고딕',10,'bold'),anchor='e',width=16).grid(
            row=12,column=0,sticky='e',padx=(8,6),pady=(10,0))
        ttk.Checkbutton(p,text='사용 중',variable=self._var_active).grid(
            row=12,column=1,sticky='w',padx=(0,8),pady=(10,0))

    def _refresh_bag_badge(self, _=None):
        try:
            v = int(self._var_bag_weight.get())
            bg = tc('btn_report') if v == 500 else '#E67E22'
            self._bag_badge.config(text=f'  {v:,} kg  ', bg=bg)
        except Exception:
            logger.debug("[SUPPRESSED] exception in inbound_template_dialog.py")  # noqa

    def _build_tab_gemini(self, p):
        p.columnconfigure(0, weight=1)
        tk.Label(p,
                 text='Gemini 파싱 힌트 (비워두면 기본 프롬프트 사용). '
                      '선사별 문서 포맷 특이사항을 입력하세요.',
                 font=('맑은 고딕', 10),fg=tc('text_muted'),anchor='w').grid(
            row=0,column=0,sticky='w',padx=8,pady=(6,2))
        # v7.4.0: 힌트 순서 BL→PL→INV (파싱 순서와 동일하게 변경)
        self._text_hint_bl  = self._hint_box(p,'🚢 B/L 힌트 (① 먼저 파싱)',    1)
        self._text_hint_pl  = self._hint_box(p,'📦 PackingList 힌트 (② 파싱)', 3)
        self._text_hint_inv = self._hint_box(p,'🧾 Invoice 힌트 (③ 파싱)',     5)

    def _hint_box(self, p, label, row):
        tk.Label(p,text=label,font=('맑은 고딕',10,'bold'),anchor='w').grid(
            row=row,column=0,sticky='w',padx=(8,0),pady=(6,0))
        txt=tk.Text(p,height=4,font=('맑은 고딕',10),wrap='word',relief='solid',bd=1)
        txt.grid(row=row+1,column=0,sticky=NSEW,padx=8,pady=(2,4))
        p.rowconfigure(row+1,weight=1)
        return txt

    def _build_tab_note(self, p):
        p.columnconfigure(0,weight=1)
        p.rowconfigure(1,weight=1)
        tk.Label(p,text='담당자 메모 (자유 입력)',
                 font=('맑은 고딕',10,'bold'),anchor='w').grid(
            row=0,column=0,sticky='w',padx=8,pady=(8,2))
        self._text_note=tk.Text(p,font=('맑은 고딕',11),wrap='word',relief='solid',bd=1)
        self._text_note.grid(row=1,column=0,sticky=NSEW,padx=8,pady=(0,8))

    def _load_list(self):
        self._templates=load_templates(self.engine)
        self._list_box.delete(0,END)
        for t in self._templates:
            icon='✅' if t.get('is_active',1) else '⛔'
            self._list_box.insert(END,f"{icon} {t['template_name']}")
        if self._templates:
            self._list_box.selection_set(0)
            self._show_template(self._templates[0])

    def _on_list_select(self,_=None):
        sel=self._list_box.curselection()
        if sel and sel[0]<len(self._templates):
            self._show_template(self._templates[sel[0]])

    def _show_template(self, t: dict):
        self._selected_id=t.get('template_id','')
        self._var_id.set(t.get('template_id',''))
        self._var_name.set(t.get('template_name',''))
        self._var_carrier.set(t.get('carrier_id','UNKNOWN'))
        self._var_bag_weight.set(t.get('bag_weight_kg',500))
        self._var_product_hint.set(t.get('product_hint','LITHIUM CARBONATE'))
        self._var_weight_fmt.set(t.get('weight_format','EURO'))
        self._var_bl_format.set(str(t.get('bl_format', '') or ''))
        self._var_active.set(t.get('is_active',1))
        for w, k in [(self._text_hint_pl,'gemini_hint_packing'),
                     (self._text_hint_inv,'gemini_hint_invoice'),
                     (self._text_hint_bl,'gemini_hint_bl')]:
            w.delete('1.0',END); w.insert('1.0',t.get(k,''))
        self._text_note.delete('1.0',END)
        self._text_note.insert('1.0',t.get('note',''))
        self._refresh_bag_badge()

    def _collect_data(self) -> dict:
        return {
            'template_id':         self._var_id.get().strip(),
            'template_name':       self._var_name.get().strip(),
            'carrier_id':          self._var_carrier.get().strip(),
            'bag_weight_kg':       int(self._var_bag_weight.get()),
            'product_hint':        self._var_product_hint.get().strip(),
            'weight_format':       self._var_weight_fmt.get().strip(),
            'bl_format':           self._var_bl_format.get().strip(),
            'gemini_hint_packing': self._text_hint_pl.get('1.0',END).strip(),
            'gemini_hint_invoice': self._text_hint_inv.get('1.0',END).strip(),
            'gemini_hint_bl':      self._text_hint_bl.get('1.0',END).strip(),
            'note':                self._text_note.get('1.0',END).strip(),
            'is_active':           self._var_active.get(),
        }

    def _on_new(self):
        self._show_template({'template_id':'','template_name':'',
            'carrier_id':'UNKNOWN','bag_weight_kg':500,
            'product_hint':'LITHIUM CARBONATE','weight_format':'EURO','bl_format':'',
            'gemini_hint_packing':'','gemini_hint_invoice':'','gemini_hint_bl':'',
            'note':'','is_active':1})
        self._selected_id=''

    def _on_save(self):
        data = self._collect_data()
        if not data['template_id']:
            messagebox.showwarning('입력 오류', '템플릿 ID를 입력하세요.', parent=self.popup); return
        if not data['template_name']:
            messagebox.showwarning('입력 오류', '템플릿 이름을 입력하세요.', parent=self.popup); return
        if ' ' in data['template_id']:
            messagebox.showwarning('입력 오류', '템플릿 ID에 공백 불가.', parent=self.popup); return

        if not save_template(self.engine, data):
            messagebox.showerror('저장 오류', '저장 중 오류가 발생했습니다.', parent=self.popup)
            return

        # ── 저장 완료 → 리스트 갱신 + 저장된 항목 선택 유지 ──
        self._load_list()
        for i, t in enumerate(self._templates):
            if t['template_id'] == data['template_id']:
                self._list_box.selection_clear(0, END)
                self._list_box.selection_set(i)
                self._list_box.see(i)
                self._selected_id = data['template_id']
                break

        # ── 파싱 선택 모드: 저장 직후 "이 템플릿으로 파싱 시작?" 안내 ──
        if self.on_select_callback:
            proceed = messagebox.askyesno(
                '저장 완료',
                f"✅ [{data['template_id']}] 저장 완료!\n\n"
                f"이 템플릿으로 바로 파싱을 시작하시겠습니까?\n\n"
                f"  선사: {data['carrier_id']}  /  단가: {data['bag_weight_kg']:,} kg",
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
            messagebox.showwarning('선택 없음','삭제할 템플릿을 선택하세요.',parent=self.popup); return
        if self._selected_id.startswith('UNKNOWN_'):
            messagebox.showwarning('삭제 불가','기본 preset은 삭제 불가.',parent=self.popup); return
        if not messagebox.askyesno('삭제 확인',f'[{self._selected_id}] 삭제하시겠습니까?',parent=self.popup):
            return
        if delete_template(self.engine,self._selected_id):
            self._load_list()
        else:
            messagebox.showerror('오류','삭제 실패',parent=self.popup)

    def _on_apply(self):
        sel=self._list_box.curselection()
        idx=sel[0] if sel else 0
        t=self._templates[idx] if idx<len(self._templates) else None
        if not t:
            messagebox.showwarning('선택 없음','템플릿을 선택하세요.',parent=self.popup); return
        if self.on_select_callback:
            self.on_select_callback(t)
        self.popup.destroy()
