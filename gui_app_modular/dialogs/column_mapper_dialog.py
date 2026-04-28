"""
v3.8.4: 입고 Excel 컬럼 매핑 다이얼로그

임의의 Excel 파일에서 컬럼을 SQM 필드에 드래그&드롭 방식으로 매핑
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import logging

logger = logging.getLogger(__name__)

try:
    import tkinter as tk
    from tkinter import ttk

    from ..utils.ui_constants import (
        DialogSize,
        apply_modal_window_options,
        center_dialog,
        setup_dialog_geometry_persistence,
    )
except ImportError as _e:
    logger.debug(f"column_mapper_dialog: {_e}")
    DialogSize = None
    center_dialog = None
    apply_modal_window_options = lambda w: None
    setup_dialog_geometry_persistence = None


# SQM 필수/선택 필드 정의
SQM_FIELDS = [
    ('lot_no',       'LOT NO *',         True),
    ('product',      'PRODUCT *',        True),
    ('net_weight',   'NET WEIGHT (kg)*', True),
    ('sap_no',       'SAP NO',           False),
    ('bl_no',        'B/L NO',           False),
    ('container_no', 'CONTAINER NO',     False),
    ('gross_weight', 'GROSS WEIGHT',     False),
    ('arrival_date', 'ARRIVAL DATE',     False),
    ('stock_date',   'STOCK DATE',       False),
    ('tonbag_count', 'TONBAG COUNT',     False),
    ('cargo_location','LOCATION',        False),
    ('memo',         'MEMO',             False),
]


class ColumnMapperDialog:
    """컬럼 매핑 다이얼로그"""

    def __init__(self, parent, excel_columns: list, sample_rows: list = None):
        self.result = None  # {sqm_field: excel_column}
        self.parent = parent
        self.excel_columns = excel_columns
        self.sample_rows = sample_rows or []

        self.dialog = create_themed_toplevel(parent)
        self.dialog.title("📋 컬럼 매핑 - Excel → SQM")
        self.dialog.minsize(500, 400)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        if setup_dialog_geometry_persistence:
            setup_dialog_geometry_persistence(self.dialog, "column_mapper_dialog", parent, "medium")
        elif DialogSize and center_dialog:
            self.dialog.geometry(DialogSize.get_geometry(parent, 'medium'))
            apply_modal_window_options(self.dialog)
            center_dialog(self.dialog, parent)
        else:
            self.dialog.geometry("750x550")

        self._build_ui()
        self._auto_map()

    def _build_ui(self):
        main = ttk.Frame(self.dialog, padding=10)
        main.pack(fill='both', expand=True)

        # 안내
        ttk.Label(main, text="Excel 컬럼을 SQM 필드에 매핑하세요. * 표시는 필수 항목입니다.",
                  font=('', 13)).pack(anchor='w', pady=(0, 10))

        # 매핑 영역
        map_frame = ttk.Frame(main)
        map_frame.pack(fill='both', expand=True)

        # 스크롤
        canvas = tk.Canvas(map_frame)
        scrollbar = tk.Scrollbar(map_frame, orient='vertical', command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 헤더
        ttk.Label(inner, text="SQM 필드", font=('', 13, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Label(inner, text="Excel 컬럼", font=('', 13, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ttk.Label(inner, text="샘플 데이터", font=('', 13, 'bold')).grid(row=0, column=2, padx=5, pady=5, sticky='w')

        choices = ['(매핑 안 함)'] + [str(c) for c in self.excel_columns]

        self.combo_vars = {}
        self.sample_labels = {}

        for i, (field_key, field_label, required) in enumerate(SQM_FIELDS, 1):
            color = '#C0392B' if required else '#555555'
            ttk.Label(inner, text=field_label, foreground=color,
                      font=('', 13, 'bold' if required else '')).grid(
                row=i, column=0, padx=5, pady=3, sticky='w')

            var = tk.StringVar(value='(매핑 안 함)')
            cb = ttk.Combobox(inner, textvariable=var, values=choices,
                             state='readonly', width=25)
            cb.grid(row=i, column=1, padx=5, pady=3)
            cb.bind('<<ComboboxSelected>>', lambda e, k=field_key: self._update_sample(k))

            self.combo_vars[field_key] = var

            lbl = ttk.Label(inner, text="", foreground=tc('text_muted'), width=30)
            lbl.grid(row=i, column=2, padx=5, pady=3, sticky='w')
            self.sample_labels[field_key] = lbl

        # 버튼
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(btn_frame, text="🔄 자동 매핑", command=self._auto_map).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="❌ 취소", command=self.dialog.destroy).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="✅ 확인", command=self._on_confirm).pack(side='right', padx=5)

    def _auto_map(self):
        """컬럼명 기반 자동 매핑"""
        alias_map = {
            'lot_no': ['lot_no', 'lot no', 'lotno', 'lot', 'lot_number'],
            'product': ['product', 'product_name', 'product_code', '제품', '품목'],
            'net_weight': ['net_weight', 'net weight', 'weight', 'net_wt', '순중량', 'qty'],
            'sap_no': ['sap_no', 'sap no', 'sap', 'sapno'],
            'bl_no': ['bl_no', 'bl no', 'bl', 'b/l no', 'b/l_no', 'blno'],
            'container_no': ['container_no', 'container no', 'container', 'cntr', 'cont'],
            'gross_weight': ['gross_weight', 'gross weight', 'gw', '총중량'],
            'arrival_date': ['arrival_date', 'arrival date', 'eta', 'eta_busan', '입항일'],
            'stock_date': ['stock_date', 'stock date', 'inbound_date', '입고일', 'date_in_stock'],
            'tonbag_count': ['tonbag_count', 'tonbag count', 'tonbag', '톤백수'],
            'cargo_location': ['cargo_location', 'location', 'warehouse', 'wh', '위치', '창고'],
            'memo': ['memo', 'note', 'remark', '비고', '메모'],
        }

        for field_key, aliases in alias_map.items():
            for col in self.excel_columns:
                col_norm = str(col).lower().strip().replace(' ', '_').replace('-', '_')
                if col_norm in aliases:
                    self.combo_vars[field_key].set(str(col))
                    break

        # 샘플 업데이트
        for field_key in self.combo_vars:
            self._update_sample(field_key)

    def _update_sample(self, field_key):
        """선택된 컬럼의 샘플 데이터 표시"""
        col_name = self.combo_vars[field_key].get()
        if col_name == '(매핑 안 함)' or not self.sample_rows:
            self.sample_labels[field_key].config(text="")
            return

        try:
            col_idx = self.excel_columns.index(col_name)
            samples = []
            for row in self.sample_rows[:3]:
                if col_idx < len(row):
                    val = row[col_idx]
                    samples.append(str(val)[:20] if val is not None else '')
            self.sample_labels[field_key].config(text=" | ".join(samples))
        except (ValueError, IndexError):
            self.sample_labels[field_key].config(text="")

    def _on_confirm(self):
        """확인: 필수 필드 검증 후 결과 반환"""
        mapping = {}
        for field_key, var in self.combo_vars.items():
            val = var.get()
            if val != '(매핑 안 함)':
                mapping[field_key] = val

        # 필수 필드 검증
        missing = []
        for field_key, field_label, required in SQM_FIELDS:
            if required and field_key not in mapping:
                missing.append(field_label)

        if missing:
            from ..utils.custom_messagebox import CustomMessageBox
            CustomMessageBox.showwarning(self.dialog, "필수 항목 누락",
                "다음 필수 항목이 매핑되지 않았습니다:\n\n" + "\n".join(missing))
            return

        self.result = mapping
        self.dialog.destroy()

    def get_result(self):
        """모달 결과 반환"""
        self.dialog.wait_window()
        return self.result
