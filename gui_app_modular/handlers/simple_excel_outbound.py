# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - 심플 엑셀 출고
=====================================

v5.6.0: 최소 필드(lot_no + weight_kg)만으로 출고 처리

엑셀 양식:
  | lot_no | weight_kg | customer | sale_ref |
  |--------|-----------|----------|----------|
  | LOT001 | 2500      | ABC Corp | SR001    |

필수: lot_no, weight_kg (또는 qty_mt)
선택: customer, sale_ref
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from engine_modules.constants import STATUS_DEPLETED
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class SimpleExcelOutboundMixin:
    """심플 엑셀 출고 Mixin"""


    def _show_simple_outbound_paste_dialog(self) -> None:
        """심플 출고 — 내장 형식에 데이터 붙여넣기 후 미리보기 (Excel/데이터 입력 원칙)."""
        from ..utils.paste_table_dialog import show_paste_table_dialog
        from ..utils.custom_messagebox import CustomMessageBox

        columns = [
            ("lot_no", "LOT NO", 120),
            ("weight_kg", "Weight(Kg)", 100),
            ("customer", "Customer", 130),
            ("sale_ref", "Sale Ref", 100),
        ]

        def on_confirm(rows: list) -> None:
            if not rows:
                CustomMessageBox.showwarning(self.root, "경고", "입력된 데이터가 없습니다.")
                return
            outbound_items = []
            for r in rows:
                lot_no = str(r.get("lot_no") or "").strip()
                if not lot_no:
                    continue
                try:
                    w = float(str(r.get("weight_kg") or "0").replace(",", ""))
                except (ValueError, TypeError):
                    continue
                if w <= 0:
                    continue
                outbound_items.append({
                    "lot_no": lot_no,
                    "weight_kg": w,
                    "customer": str(r.get("customer") or "").strip(),
                    "sale_ref": str(r.get("sale_ref") or "").strip(),
                })
            if not outbound_items:
                CustomMessageBox.showwarning(self.root, "경고", "유효한 출고 데이터(LOT NO, Weight(Kg))가 없습니다.")
                return
            self._show_simple_outbound_preview(outbound_items)

        show_paste_table_dialog(
            self.root,
            title="📤 심플 출고 데이터 (붙여넣기)",
            columns=columns,
            instruction="아래 표에 Excel 등에서 복사한 출고 데이터를 붙여넣기(Ctrl+V) 한 뒤 [미리보기]를 누르세요. 형식: LOT NO, Weight(Kg) 필수.",
            confirm_text="미리보기",
            cancel_text="취소",
            on_confirm=on_confirm,
            min_size=(700, 400),
        )

    def _show_simple_outbound_preview(self, items: List[Dict]) -> None:
        """심플 출고 미리보기"""
        from utils.constants import tk, ttk, BOTH, YES
        from ..utils.custom_messagebox import CustomMessageBox

        dialog = create_themed_toplevel(self.root)
        dialog.title("📤 심플 엑셀 출고 — 미리보기")
        dialog.geometry("700x450")
        dialog.resizable(True, True)  # v9.0: 크기 조절 허용
        dialog.minsize(400, 300)  # v9.0: 최소 크기
        dialog.transient(self.root)
        dialog.grab_set()

        # 상단 요약
        summary = tk.Frame(dialog, padx=10, pady=8)
        summary.pack(fill='x')
        tk.Label(summary, text=f"총 {len(items)}건 출고 예정",
                 font=('', 13, 'bold')).pack(side='left')

        total_kg = sum(i['weight_kg'] for i in items)
        tk.Label(summary, text=f"총 {total_kg:,.0f} kg ({total_kg/1000:,.2f} MT)",
                 font=('', 12)).pack(side='right')

        # Treeview
        cols = ('lot_no', 'weight_kg', 'weight_mt', 'customer', 'sale_ref', 'status')
        tree = ttk.Treeview(dialog, columns=cols, show='headings', height=15)

        headers = {
            'lot_no': ('LOT NO', 120),
            'weight_kg': ('KG', 90),
            'weight_mt': ('MT', 80),
            'customer': ('Customer', 150),
            'sale_ref': ('Sale Ref', 100),
            'status': ('Status', 100),
        }
        for c, (label, w) in headers.items():
            tree.heading(c, text=label, anchor='center')
            tree.column(c, width=w, anchor='center')

        # 검증: 각 LOT 재고 확인
        for item in items:
            lot_no = item['lot_no']
            weight_kg = item['weight_kg']

            # DB에서 LOT 확인
            lot_data = self.engine.db.fetchone(
                "SELECT current_weight, status FROM inventory WHERE lot_no = ?",
                (lot_no,))

            if not lot_data:
                status = "❌ LOT 없음"
            elif lot_data['status'] == STATUS_DEPLETED:
                status = "❌ 소진됨"
            elif float(lot_data['current_weight'] or 0) < weight_kg:
                avail = float(lot_data['current_weight'] or 0)
                status = f"⚠️ 부족 ({avail:,.0f}kg)"
            else:
                status = "✅ OK"

            tree.insert('', 'end', values=(
                lot_no,
                f"{weight_kg:,.0f}",
                f"{weight_kg/1000:,.3f}",
                item.get('customer', ''),
                item.get('sale_ref', ''),
                status
            ))
        # 입력용 미리보기: 전역 Editable Treeview 허용 (status는 편집 금지)
        tree._enable_global_editable = True
        tree._editable_exclude_cols = {"status"}

        tree.pack(fill=BOTH, expand=YES, padx=10, pady=5)

        # 버튼
        btn_frame = tk.Frame(dialog, padx=10, pady=10)
        btn_frame.pack(fill='x')

        def execute():
            # 편집된 그리드 값을 items로 재구성(LOT, KG, customer, sale_ref)
            edited_items = []
            for iid in tree.get_children(""):
                vals = tree.item(iid, "values")
                try:
                    lot_no = str(vals[0]).strip()
                    weight_kg = float(str(vals[1]).replace(",", "").strip() or 0)
                    customer = str(vals[3]).strip()
                    sale_ref = str(vals[4]).strip()
                except (ValueError, TypeError, IndexError):
                    continue
                if not lot_no or weight_kg <= 0:
                    continue
                edited_items.append({
                    "lot_no": lot_no,
                    "weight_kg": weight_kg,
                    "customer": customer,
                    "sale_ref": sale_ref,
                })
            if edited_items:
                items[:] = edited_items

            # 에러 있는 항목 확인
            has_error = any('❌' in str(tree.item(iid, 'values')[5]) for iid in tree.get_children())
            if has_error:
                CustomMessageBox.warning(dialog, "확인",
                    "❌ 오류가 있는 항목이 포함되어 있습니다.\n오류 항목은 건너뛰고 진행할까요?")

            success = 0
            errors = []

            for item in items:
                lot_no = item['lot_no']
                weight_kg = item['weight_kg']
                customer = item.get('customer', '')
                sale_ref = item.get('sale_ref', '')

                try:
                    result = self.engine.process_outbound({
                        'lot_no': lot_no,
                        'weight_kg': weight_kg,
                        'customer': customer,
                        'sale_ref': sale_ref,
                    }, source='EXCEL', stop_at_picked=False)
                    if result.get('success'):
                        success += 1
                    else:
                        errors.append(f"{lot_no}: {result.get('message', '실패')}")
                except (ValueError, TypeError, KeyError) as e:
                    errors.append(f"{lot_no}: {e}")

            dialog.destroy()

            msg = f"✅ 출고 완료: {success}/{len(items)}건"
            if errors:
                msg += f"\n\n❌ 실패 {len(errors)}건:\n" + '\n'.join(errors[:5])
            CustomMessageBox.info(self.root, "출고 결과", msg)

            # 새로고침
            self._safe_refresh()
        ttk.Button(btn_frame, text="✅ 출고 실행", command=execute).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="❌ 취소", command=dialog.destroy).pack(side='right', padx=5)

