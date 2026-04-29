"""
SQM v5.0.9 - Allocation Table 미리보기 다이얼로그
=================================================

v5.0.9 수정사항:
- 샘플/톤백 정확한 구분 (product명 + qty_mt 기반)
- 제품별 요약: 제품명, 톤백 수/kg, 샘플 수/kg 명확 표시
- 레이아웃: 요약 영역 최소화 → 상세내역 영역 최대화
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from gui_app_modular.utils.ui_constants import tc
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from tkinter import ttk
from typing import Dict, List

from ..utils.ui_constants import setup_dialog_geometry_persistence


def _is_sample_item(item: Dict) -> bool:
    """
    샘플 여부 판단 (v5.1.0: tonbag_compat 통일 기준)
    
    판단 순서:
    1. is_sample 필드가 있으면 최우선
    2. product에 'sample' 포함
    3. sub_lt(tonbag_no) == 0  
    4. qty_mt <= 0.001 (1kg)
    """
    try:
        from engine_modules.tonbag_compat import is_sample_tonbag
        return is_sample_tonbag(item)
    except ImportError:
        # fallback: 기존 로직
        product = str(item.get('product', '')).lower()
        qty_mt = float(item.get('qty_mt', 0))
        if 'sample' in product:
            return True
        if qty_mt <= 0.001:
            return True
        return False


class AllocationPreviewDialog:
    """
    Allocation Table 출고 미리보기 다이얼로그 (v5.0.9)
    
    레이아웃:
    - 요약 영역: 최소 (1줄 콤팩트 + 제품별 톤백/샘플)
    - 상세내역: 최대 (Treeview 확장)
    """

    def __init__(self, parent, allocation_items: List[Dict],
                 on_confirm: Callable, on_cancel: Callable = None):
        self.parent = parent
        self.allocation_items = allocation_items
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        # 다이얼로그 생성 (Phase4: DialogSize + 직전 크기 복원)
        self.dialog = create_themed_toplevel(parent)
        self.dialog.title("📋 출고 Allocation 미리보기")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        setup_dialog_geometry_persistence(self.dialog, "allocation_preview_dialog", parent, "large")

        # 통계 계산
        self.stats = self._calculate_stats()

        # UI 구성
        self._build_ui()

    def _calculate_stats(self) -> Dict:
        """
        v5.0.9: 정확한 톤백/샘플 구분 통계
        """
        by_product = {}
        total_tb_count = 0
        total_tb_weight = 0.0
        total_sp_count = 0
        total_sp_weight = 0.0
        customer = ''

        for item in self.allocation_items:
            # 제품명에서 _sample 등 제거하여 기본 제품명 추출
            raw_product = str(item.get('product', 'Unknown'))
            base_product = raw_product.replace('_sample', '').replace('_Sample', '').replace(' Sample', '').replace(' sample', '').strip()
            if not base_product:
                base_product = 'Unknown'

            if base_product not in by_product:
                by_product[base_product] = {
                    'tonbag_count': 0,
                    'tonbag_weight_kg': 0.0,
                    'sample_count': 0,
                    'sample_weight_kg': 0.0,
                }

            qty_kg = float(item.get('qty_mt', 0)) * 1000

            if _is_sample_item(item):
                by_product[base_product]['sample_count'] += 1
                by_product[base_product]['sample_weight_kg'] += qty_kg
                total_sp_count += 1
                total_sp_weight += qty_kg
            else:
                by_product[base_product]['tonbag_count'] += 1
                by_product[base_product]['tonbag_weight_kg'] += qty_kg
                total_tb_count += 1
                total_tb_weight += qty_kg

            if not customer:
                customer = str(item.get('sold_to', ''))

        return {
            'by_product': by_product,
            'total_tonbag_count': total_tb_count,
            'total_tonbag_weight_kg': total_tb_weight,
            'total_sample_count': total_sp_count,
            'total_sample_weight_kg': total_sp_weight,
            'total_count': total_tb_count + total_sp_count,
            'total_weight_kg': total_tb_weight + total_sp_weight,
            'customer': customer,
        }

    def _build_ui(self):
        """v5.0.9: 요약 최소화 + 상세내역 최대화 레이아웃"""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill='both', expand=True)

        # ═══════════════════════════════════════════════════════
        # 1. 콤팩트 요약 (고정 높이, 최소 공간)
        # ═══════════════════════════════════════════════════════
        summary_frame = ttk.LabelFrame(main_frame, text="📊 출고 요약", padding=6)
        summary_frame.pack(fill='x', pady=(0, 5))

        today = datetime.now().strftime('%Y-%m-%d')
        s = self.stats

        # 1줄 요약: 날짜 | 출고처 | 총합계
        line1 = (
            f"📅 {today}   │   "
            f"🏢 {s['customer']}   │   "
            f"📦 톤백 {s['total_tonbag_count']}개 ({s['total_tonbag_weight_kg']:,.0f} kg)   "
            f"🧪 샘플 {s['total_sample_count']}개 ({s['total_sample_weight_kg']:,.1f} kg)   │   "
            f"합계 {s['total_count']}개 ({s['total_weight_kg']:,.1f} kg)"
        )
        ttk.Label(summary_frame, text=line1, font=('맑은 고딕', 10, 'bold')).pack(anchor='w')

        # 제품별 요약 (콤팩트 1줄씩)
        for product_name, pstats in s['by_product'].items():
            line = (
                f"  ▸ {product_name}:  "
                f"톤백 {pstats['tonbag_count']}개 / {pstats['tonbag_weight_kg']:,.0f} kg,  "
                f"샘플 {pstats['sample_count']}개 / {pstats['sample_weight_kg']:,.1f} kg"
            )
            ttk.Label(summary_frame, text=line, font=('맑은 고딕', 10)).pack(anchor='w')

        # ═══════════════════════════════════════════════════════
        # 2. 상세 내역 (최대 확장)
        # ═══════════════════════════════════════════════════════
        detail_frame = ttk.LabelFrame(
            main_frame,
            text=f"📋 상세 내역 ({len(self.allocation_items)}건)",
            padding=5
        )
        detail_frame.pack(fill='both', expand=True, pady=(0, 5))

        # Treeview
        columns = ['no', 'type', 'lot_no', 'product', 'qty_mt', 'qty_kg',
                   'sub_lt', 'sold_to', 'warehouse', 'customs']
        tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=20)

        tree.heading('no', text='#', anchor='center')
        tree.heading('type', text='구분', anchor='center')
        tree.heading('lot_no', text='LOT NO', anchor='center')
        tree.heading('product', text='PRODUCT', anchor='center')
        tree.heading('qty_mt', text='QTY(MT)', anchor='center')
        tree.heading('qty_kg', text='QTY(kg)', anchor='center')
        tree.heading('sub_lt', text='톤백#', anchor='center')
        tree.heading('sold_to', text='출고처', anchor='center')
        tree.heading('warehouse', text='WH', anchor='center')
        tree.heading('customs', text='Customs', anchor='center')

        tree.column('no', width=35, anchor='center')
        tree.column('type', width=55, anchor='center')
        tree.column('lot_no', width=110, anchor='center')
        tree.column('product', width=130, anchor='w')
        tree.column('qty_mt', width=85, anchor='e')
        tree.column('qty_kg', width=85, anchor='e')
        tree.column('sub_lt', width=55, anchor='center')
        tree.column('sold_to', width=200, anchor='w')
        tree.column('warehouse', width=45, anchor='center')
        tree.column('customs', width=80, anchor='center')

        # 데이터 삽입
        for idx, item in enumerate(self.allocation_items, 1):
            is_sample = _is_sample_item(item)
            qty_mt = float(item.get('qty_mt', 0))
            qty_kg = qty_mt * 1000
            type_str = '🧪샘플' if is_sample else '📦톤백'
            tag = 'sample' if is_sample else 'tonbag'

            tree.insert('', 'end', values=(
                idx,
                type_str,
                item.get('lot_no', ''),
                item.get('product', ''),
                f"{qty_mt:.3f}",
                f"{qty_kg:,.1f}",
                item.get('sub_lt', ''),
                item.get('sold_to', ''),
                item.get('warehouse', ''),
                item.get('customs', ''),
            ), tags=(tag,))

        # 스타일 (샘플 = 파란색 배경)
        tree.tag_configure('sample', background=tc('shipped'), foreground=tc('info'))
        tree.tag_configure('tonbag', background=tc('bg_card'))

        # 스크롤바
        v_scroll = tk.Scrollbar(detail_frame, orient='vertical', command=tree.yview)
        h_scroll = tk.Scrollbar(detail_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')

        # v8.1.8: 합계 footer
        from gui_app_modular.utils.tree_enhancements import TreeviewTotalFooter
        _alloc_prev_footer = TreeviewTotalFooter(
            detail_frame, tree,
            summable_column_ids=['qty_mt', 'qty_kg'],
            column_display_names={'qty_mt': 'QTY(MT)', 'qty_kg': 'QTY(kg)'},
            column_formats={'qty_mt': ',.3f'},
        )
        _alloc_prev_footer.pack(fill='x')

        # ═══════════════════════════════════════════════════════
        # 3. 확인/취소 버튼 (콤팩트 한 줄)
        # ═══════════════════════════════════════════════════════
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(5, 0))

        ttk.Label(
            btn_frame,
            text="❓ 위 내용으로 출고를 실행하시겠습니까?",
            font=('맑은 고딕', 11, 'bold'),
            foreground=tc('danger')
        ).pack(side='left', padx=(0, 20))

        ttk.Button(
            btn_frame,
            text="❌ 취소",
            command=self._on_cancel_click,
            width=15
        ).pack(side='right', padx=5)

        ttk.Button(
            btn_frame,
            text="✅ 출고 실행",
            command=self._on_confirm_click,
            width=15
        ).pack(side='right', padx=5)

        # ESC 키 바인딩
        self.dialog.bind('<Escape>', lambda e: self._on_cancel_click())

    def _on_confirm_click(self):
        """확인 버튼 클릭"""
        self.dialog.destroy()
        if self.on_confirm:
            self.on_confirm(self.allocation_items)

    def _on_cancel_click(self):
        """취소 버튼 클릭"""
        self.dialog.destroy()
        if self.on_cancel:
            self.on_cancel()


__all__ = ['AllocationPreviewDialog']
