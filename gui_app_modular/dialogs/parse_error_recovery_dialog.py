# -*- coding: utf-8 -*-
"""
SQM v8.6.4 — AI 파싱 오류 복구 다이얼로그

Author: Ruby
Version: 1.0.0 (2026-03-29)

AI 파싱 실패 시 오류를 자동 분류하고 수동 입력 폼을 제공.
사용자가 입력한 값을 파싱 결과 객체에 직접 적용.

지원 에러코드 9종:
  ERR-BL-01: BL No 미추출
  ERR-BL-02: Vessel/Voyage 미추출
  ERR-PL-01: LOT No 미추출
  ERR-PL-02: SAP No 미추출
  ERR-PL-03: 무게 미추출
  ERR-IV-01: Invoice No 미추출
  ERR-IV-02: LOT/SAP 불일치
  ERR-DO-01: Arrival Date 미추출
  ERR-DO-02: Container/Free Time 미추출
"""
import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional

logger = logging.getLogger(__name__)

# ── 에러코드 정의 ──────────────────────────────────────────────────────────
ERROR_CODES = {
    'ERR-BL-01': {
        'title':   'BL No 미추출',
        'desc':    'AI가 선하증권 번호(BL No)를 인식하지 못했습니다.',
        'fields':  [('bl_no', 'BL No', 'MEDU1234567890')],
        'doc':     'BL',
    },
    'ERR-BL-02': {
        'title':   'Vessel / Voyage 미추출',
        'desc':    '선박명 또는 항차 번호를 인식하지 못했습니다.',
        'fields':  [('vessel', '선박명 (Vessel)', 'MSC BLESSING'),
                    ('voyage', '항차 (Voyage)', '234N')],
        'doc':     'BL',
    },
    'ERR-PL-01': {
        'title':   'LOT No 미추출',
        'desc':    'Packing List에서 LOT 번호를 인식하지 못했습니다.',
        'fields':  [('lot_no', 'LOT No (8~11자리)', '1125082734')],
        'doc':     'PL',
    },
    'ERR-PL-02': {
        'title':   'SAP No 미추출',
        'desc':    'SAP 문서번호(10자리)를 인식하지 못했습니다.',
        'fields':  [('sap_no', 'SAP No (10자리)', '2200033062')],
        'doc':     'PL',
    },
    'ERR-PL-03': {
        'title':   '무게 미추출',
        'desc':    '순중량(Net Weight) 또는 총중량(Gross Weight)을 인식하지 못했습니다.',
        'fields':  [('net_weight',   'Net Weight (kg)',   '500.0'),
                    ('gross_weight', 'Gross Weight (kg)', '512.5')],
        'doc':     'PL',
    },
    'ERR-IV-01': {
        'title':   'Invoice No 미추출',
        'desc':    '인보이스 번호를 인식하지 못했습니다.',
        'fields':  [('invoice_no', 'Invoice No', 'INV-2026-001')],
        'doc':     'Invoice',
    },
    'ERR-IV-02': {
        'title':   'LOT / SAP 불일치',
        'desc':    'Invoice의 LOT No 또는 SAP No가 Packing List와 다릅니다.',
        'fields':  [('lot_no', 'LOT No (수동 확인 후 입력)', ''),
                    ('sap_no', 'SAP No (수동 확인 후 입력)', '')],
        'doc':     'Invoice',
    },
    'ERR-DO-01': {
        'title':   'Arrival Date 미추출',
        'desc':    'D/O에서 입항일(Arrival Date)을 인식하지 못했습니다.',
        'fields':  [('arrival_date', '입항일 (YYYY-MM-DD)', '2025-10-22')],
        'doc':     'DO',
    },
    'ERR-DO-02': {
        'title':   'Container / Free Time 미추출',
        'desc':    '컨테이너 번호 또는 반납일(Free Time)을 인식하지 못했습니다.',
        'fields':  [('container_no', '컨테이너 No', 'MSCU1234567'),
                    ('con_return',   '반납일 (YYYY-MM-DD)', '2025-11-05')],
        'doc':     'DO',
    },
}


def classify_parse_error(result_obj) -> list:
    """파싱 결과 객체를 분석해 해당하는 에러코드 목록 반환.

    Args:
        result_obj: BLData / PackingData / InvoiceData / DOData 등

    Returns:
        list of error_code strings
    """
    errors = []
    obj_type = type(result_obj).__name__.upper()

    def _has(attr):
        v = getattr(result_obj, attr, None)
        return bool(v and str(v).strip())

    if 'BL' in obj_type or 'BLDATA' in obj_type:
        if not _has('bl_no'):        errors.append('ERR-BL-01')
        if not _has('vessel'):       errors.append('ERR-BL-02')

    if 'PACKING' in obj_type or 'PL' in obj_type:
        lots = getattr(result_obj, 'lots', []) or getattr(result_obj, 'lot_no', None)
        if not lots:                 errors.append('ERR-PL-01')
        if not _has('sap_no'):       errors.append('ERR-PL-02')
        # v8.7.0 [FIX]: PackingListData는 문서 단위 net_weight가 없을 수 있음 →
        #   net_weight → total_net_weight_kg → total_net_weight → lots 합 → rows 합 순으로 판정
        _nw = 0.0
        try:
            _nw = float(getattr(result_obj, 'net_weight', 0) or 0)
            if _nw <= 0:
                _nw = float(getattr(result_obj, 'total_net_weight_kg', 0) or 0)
            if _nw <= 0:
                _nw = float(getattr(result_obj, 'total_net_weight', 0) or 0)
            if _nw <= 0 and lots:
                _nw = sum(
                    float(getattr(lt, 'net_weight_kg', 0) or 0) for lt in lots
                )
            if _nw <= 0:
                rows = getattr(result_obj, 'rows', []) or []
                _nw = sum(
                    float(getattr(r, 'net_weight', 0) or getattr(r, 'net_weight_kg', 0) or 0)
                    for r in rows
                )
        except (TypeError, ValueError):
            _nw = 0.0
        if _nw <= 0:                 errors.append('ERR-PL-03')

    if 'INVOICE' in obj_type:
        if not _has('invoice_no'):   errors.append('ERR-IV-01')

    if 'DO' in obj_type or 'DODATA' in obj_type:
        if not _has('arrival_date'): errors.append('ERR-DO-01')
        ctrs = getattr(result_obj, 'containers', []) or []
        if not ctrs:                 errors.append('ERR-DO-02')

    return errors


def show_parse_error_recovery(
    parent,
    error_codes: list,
    result_obj=None,
    title: str = "파싱 오류 — 수동 입력",
) -> dict:
    """AI 파싱 오류 복구 다이얼로그 표시.

    Args:
        parent:       부모 tk 위젯
        error_codes:  에러코드 리스트 (classify_parse_error 반환값)
        result_obj:   파싱 결과 객체 (None이면 값만 반환)
        title:        다이얼로그 타이틀

    Returns:
        dict: {field_name: user_input_value} — 빈 dict이면 취소
    """
    if not error_codes:
        return {}

    # 표시할 필드 수집 (에러코드 순서대로, 중복 제거)
    all_fields = []
    seen_fields = set()
    error_descs = []
    for code in error_codes:
        info = ERROR_CODES.get(code)
        if not info:
            continue
        error_descs.append(f"[{code}] {info['title']}: {info['desc']}")
        for field_name, label, placeholder in info['fields']:
            if field_name not in seen_fields:
                all_fields.append((field_name, label, placeholder))
                seen_fields.add(field_name)

    if not all_fields:
        return {}

    # ── 다이얼로그 생성 ──────────────────────────────────────────────────
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.grab_set()

    # 테마 색상 (PRO DARK 기준)
    BG      = '#0f172a'
    FG      = '#e2e8f0'
    ACCENT  = '#22d3ee'
    ERR_CLR = '#f87171'
    CARD    = '#1e293b'
    BORDER  = '#334155'

    dlg.configure(bg=BG)

    # ── 헤더 ──
    hdr = tk.Frame(dlg, bg=BG, pady=12, padx=20)
    hdr.pack(fill='x')

    tk.Label(hdr, text="⚠️  AI 파싱 오류 복구",
             font=('Segoe UI', 14, 'bold'),
             bg=BG, fg=ACCENT).pack(anchor='w')

    # ── 오류 설명 카드 ──
    card = tk.Frame(dlg, bg=CARD, padx=16, pady=12,
                    highlightbackground=ERR_CLR, highlightthickness=1)
    card.pack(fill='x', padx=20, pady=(0,10))

    for desc in error_descs:
        tk.Label(card, text=f"• {desc}", bg=CARD, fg=ERR_CLR,
                 font=('Segoe UI', 10), wraplength=480, justify='left'
                 ).pack(anchor='w', pady=1)

    tk.Label(card, text="아래에 올바른 값을 직접 입력해 주세요.",
             bg=CARD, fg='#94a3b8', font=('맑은 고딕', 10, 'italic')
             ).pack(anchor='w', pady=(6,0))

    # ── 입력 폼 ──
    form = tk.Frame(dlg, bg=BG, padx=20, pady=8)
    form.pack(fill='x')

    entries = {}
    for field_name, label, placeholder in all_fields:
        row = tk.Frame(form, bg=BG, pady=4)
        row.pack(fill='x')

        tk.Label(row, text=label, bg=BG, fg=FG,
                 font=('Segoe UI', 10), width=24, anchor='w'
                 ).pack(side='left')

        entry_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=entry_var, width=30)
        entry.pack(side='left', padx=(6,0))

        # placeholder 힌트 (회색)
        if placeholder:
            entry.insert(0, placeholder)
            entry.config(foreground='#64748b')

            def _on_focus_in(e, ev=entry, ph=placeholder, ev_var=entry_var):
                if ev.get() == ph:
                    ev.delete(0, 'end')
                    ev.config(foreground='white')

            def _on_focus_out(e, ev=entry, ph=placeholder):
                if not ev.get():
                    ev.insert(0, ph)
                    ev.config(foreground='#64748b')

            entry.bind('<FocusIn>',  _on_focus_in)
            entry.bind('<FocusOut>', _on_focus_out)

        entries[field_name] = (entry_var, placeholder)

    # ── 버튼 ──
    btn_frame = tk.Frame(dlg, bg=BG, pady=12, padx=20)
    btn_frame.pack(fill='x')

    result = {}

    def _on_apply():
        for fname, (var, ph) in entries.items():
            val = var.get().strip()
            if val and val != ph:
                result[fname] = val
        if result_obj is not None:
            _apply_recovery_values(result_obj, result)
        dlg.destroy()

    def _on_cancel():
        dlg.destroy()

    ttk.Button(btn_frame, text="✅ 적용", command=_on_apply
               ).pack(side='right', padx=(6,0))
    ttk.Button(btn_frame, text="✕ 취소", command=_on_cancel
               ).pack(side='right')

    # 창 중앙 배치
    dlg.update_idletasks()
    w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
    sw = parent.winfo_screenwidth()
    sh = parent.winfo_screenheight()
    dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    dlg.wait_window()
    return result


def _apply_recovery_values(result_obj, values: dict) -> None:
    """사용자 입력값을 파싱 결과 객체에 직접 적용.

    Args:
        result_obj: 파싱 결과 객체
        values:     {field_name: value} dict
    """
    for field, value in values.items():
        if not value:
            continue
        try:
            if hasattr(result_obj, field):
                # 날짜 필드 처리
                if 'date' in field:
                    from utils.common import norm_date_any
                    parsed = norm_date_any(value)
                    setattr(result_obj, field, parsed or value)
                # 무게 필드 처리
                elif 'weight' in field:
                    setattr(result_obj, field, float(value))
                else:
                    setattr(result_obj, field, value)
                logger.info(f"[복구] {type(result_obj).__name__}.{field} = {value!r}")
            else:
                # 객체에 속성이 없으면 동적 추가
                setattr(result_obj, field, value)
                logger.debug(f"[복구] 동적 속성 추가: {field} = {value!r}")
        except Exception as e:
            logger.warning(f"[복구] {field} 적용 실패: {e}")
