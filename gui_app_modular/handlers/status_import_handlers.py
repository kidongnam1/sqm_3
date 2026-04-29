# -*- coding: utf-8 -*-
"""
SQM Inventory - Status Import Handlers
======================================

v2.9.91 - Extracted from gui_app.py

Import outbound status and location mapping from Excel
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
from engine_modules.constants import STATUS_PICKED
import os
import logging
from ..utils.ui_constants import CustomMessageBox
from datetime import date, datetime

logger = logging.getLogger(__name__)


class StatusImportHandlersMixin:
    """
    Status import handlers mixin
    
    Mixed into SQMInventoryApp class
    """
    
    def _import_outbound_excel(self) -> None:
        """출고 결과 Excel 불러오기 — 파일 선택 후 상세 요약 다이얼로그 표시, 사용자 확인 후 DB 반영."""
        from ..utils.constants import filedialog
        import tkinter as tk
        from tkinter import ttk

        file_path = getattr(self, '_pending_file', None)
        if file_path:
            delattr(self, '_pending_file')
        if not file_path:
            file_path = filedialog.askopenfilename(
                parent=self.root,
                title="출고 결과 Excel 선택",
                filetypes=[("Excel files", "*.xlsx;*.xls"), ("All files", "*.*")]
            )
        if not file_path:
            return

        self._set_status("출고 결과 로딩 중...")
        self._log(f"Outbound Excel: {os.path.basename(file_path)}")

        try:
            import pandas as pd

            xls = pd.ExcelFile(file_path)
            if 'outbound' in [s.lower() for s in xls.sheet_names]:
                df = pd.read_excel(file_path, sheet_name='outbound')
            else:
                df = pd.read_excel(file_path, sheet_name=0)
            self._log(f"  -> {len(df)} rows loaded")

            df.columns = [str(c).strip().upper().replace(' ', '_') for c in df.columns]
            col_map = {
                'LOT_NO': ['LOT_NO', 'LOTNO', 'LOT', 'LOT_NUMBER'],
                'SUB_LT': ['SUB_LT', 'SUBLT', 'SUB_LOT', 'SUBLOT', 'TONBAG_NO', 'TONBAG'],
                'CUSTOMER': ['CUSTOMER', 'PICKED_TO', 'SOLD_TO', 'SOLD', 'BUYER'],
                'OUTBOUND_DATE': ['OUTBOUND_DATE', 'OUTBOUNDDATE', 'PICK_DATE', 'PICKED_DATE', 'SOLD_DATE', 'DATE'],
                'SALE_REF': ['SALE_REF', 'SALEREF', 'PICK_REF', 'SALE_REFERENCE'],
            }

            def find_col(candidates):
                for c in candidates:
                    if c in df.columns:
                        return c
                return None

            lot_col = find_col(col_map['LOT_NO'])
            sub_col = find_col(col_map['SUB_LT'])
            if not lot_col or not sub_col:
                missing = ["LOT NO"] if not lot_col else []
                if not sub_col:
                    missing.append("SUB LT (톤백 NO)")
                CustomMessageBox.showerror(self.root, "컬럼 누락", f"필수 컬럼이 없습니다: {missing}")
                self._set_status("Ready")
                return

            customer_col = find_col(col_map['CUSTOMER'])
            date_col = find_col(col_map['OUTBOUND_DATE'])
            ref_col = find_col(col_map['SALE_REF'])

            # 상세 요약용 행 목록 (상태: 적용가능 / 재고없음 / 이미출고)
            preview_rows = []
            for idx, row in df.iterrows():
                lot_no = str(row.get(lot_col, ''))
                if not lot_no or lot_no == 'nan':
                    continue
                if '.' in lot_no:
                    lot_no = lot_no.split('.')[0]
                tonbag_no = self._safe_int(row.get(sub_col, 0))
                customer = str(row.get(customer_col, '')) if customer_col and pd.notna(row.get(customer_col)) else ''
                sale_ref = str(row.get(ref_col, '')) if ref_col and pd.notna(row.get(ref_col)) else ''
                outbound_date = self._safe_date(row.get(date_col)) if date_col else date.today()
                existing = self.engine.db.fetchone(
                    "SELECT id, status FROM inventory_tonbag WHERE lot_no=? AND sub_lt=?",
                    (lot_no, tonbag_no)
                )
                if not existing:
                    status = "재고없음"
                elif existing['status'] == STATUS_PICKED:
                    status = "이미출고"
                else:
                    status = "적용가능"
                preview_rows.append((lot_no, tonbag_no, customer, str(outbound_date), sale_ref or '', status))

            if not preview_rows:
                CustomMessageBox.showwarning(self.root, "안내", "출고 데이터가 없습니다.")
                self._set_status("Ready")
                return

            # 상세 요약 다이얼로그
            win = create_themed_toplevel(self.root)
            win.title("출고 결과 — 상세 요약")
            win.transient(self.root)
            win.resizable(True, True)
            win.minsize(620, 400)
            from ..utils.ui_constants import apply_modal_window_options, center_dialog
            apply_modal_window_options(win)

            frm = ttk.Frame(win, padding=12)
            frm.pack(fill=tk.BOTH, expand=True)
            ttk.Label(frm, text="출고 내용을 확인한 뒤 [DB 반영]을 누르세요.", font=("맑은 고딕", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
            cols = ("lot_no", "sub_lt", "customer", "outbound_date", "sale_ref", "status")
            tree = ttk.Treeview(frm, columns=cols, show="headings", height=14, selectmode="extended")
            for c, h in [("lot_no", "LOT NO"), ("sub_lt", "톤백 NO"), ("customer", "고객"), ("outbound_date", "출고일"), ("sale_ref", "SALE REF"), ("status", "상태")]:
                tree.heading(c, text=h, anchor='center')
                tree.column(c, width=90 if c != "customer" else 140, anchor="w")
            scroll_y = tk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
            scroll_x = tk.Scrollbar(frm, orient=tk.HORIZONTAL, command=tree.xview)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
            scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
            tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
            for r in preview_rows:
                tree.insert("", "end", values=r)
            # 입력용 미리보기: 전역 Editable Treeview 허용 (상태는 편집 금지)
            tree._enable_global_editable = True
            tree._editable_exclude_cols = {"status"}
            cnt_ok = sum(1 for r in preview_rows if r[5] == "적용가능")
            cnt_nf = sum(1 for r in preview_rows if r[5] == "재고없음")
            cnt_done = sum(1 for r in preview_rows if r[5] == "이미출고")
            summary = f"총 {len(preview_rows)}건  |  적용가능: {cnt_ok}건  |  재고없음: {cnt_nf}건  |  이미출고: {cnt_done}건"
            ttk.Label(frm, text=summary, font=("맑은 고딕", 10)).pack(anchor=tk.W, pady=6)

            def do_apply():
                win.destroy()
                self._set_status("출고 결과 반영 중...")
                updated = 0
                not_found = 0
                already_picked = 0
                blocked_reversed = 0  # SOLD/DEPLETED/RETURNED → PICKED 역전 차단 건수

                # 편집된 그리드 값 우선 반영
                grid_rows = []
                for iid in tree.get_children(""):
                    vals = tree.item(iid, "values")
                    if not vals:
                        continue
                    try:
                        lot_no = str(vals[0]).strip()
                        tonbag_no = self._safe_int(vals[1], 0)
                        customer = str(vals[2]).strip()
                        outbound_date = self._safe_date(vals[3])
                        sale_ref = str(vals[4]).strip()
                    except (ValueError, TypeError, IndexError):
                        continue
                    if not lot_no or tonbag_no <= 0:
                        continue
                    grid_rows.append((lot_no, tonbag_no, customer, outbound_date, sale_ref))

                source_rows = grid_rows if grid_rows else []
                if not source_rows:
                    # 폴백: 기존 df 기반
                    for idx, row in df.iterrows():
                        lot_no = str(row.get(lot_col, ''))
                        if not lot_no or lot_no == 'nan':
                            continue
                        if '.' in lot_no:
                            lot_no = lot_no.split('.')[0]
                        tonbag_no = self._safe_int(row.get(sub_col, 0))
                        customer = str(row.get(customer_col, '')) if customer_col and pd.notna(row.get(customer_col)) else ''
                        sale_ref = str(row.get(ref_col, '')) if ref_col and pd.notna(row.get(ref_col)) else ''
                        outbound_date = self._safe_date(row.get(date_col)) if date_col else date.today()
                        source_rows.append((lot_no, tonbag_no, customer, outbound_date, sale_ref))

                with self.engine.db.transaction():
                    for lot_no, tonbag_no, customer, outbound_date, sale_ref in source_rows:
                        existing = self.engine.db.fetchone(
                            "SELECT id, status FROM inventory_tonbag WHERE lot_no=? AND sub_lt=?",
                            (lot_no, tonbag_no)
                        )
                        if not existing:
                            not_found += 1
                            continue
                        cur = (existing.get('status') or '').strip().upper()
                        if cur == STATUS_PICKED:
                            already_picked += 1
                            continue
                        # v6.0.7+ 상태 전이 보호: AVAILABLE/RESERVED만 PICKED로 전환 허용. SOLD/DEPLETED/RETURNED 역전 차단
                        if cur in ('SOLD', 'DEPLETED', 'RETURNED', 'SHIPPED'):
                            blocked_reversed += 1
                            continue
                        self.engine.db.execute("""
                            UPDATE inventory_tonbag SET
                                status = 'PICKED',
                                picked_to = ?,
                                pick_ref = ?,
                                outbound_date = ?,
                                picked_date = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE lot_no = ? AND sub_lt = ?
                        """, (customer, sale_ref, outbound_date, outbound_date, lot_no, tonbag_no))
                        updated += 1
                self._log(f"OK Outbound: {updated} processed, {not_found} not found, {already_picked} already picked, {blocked_reversed} blocked(reversed)")
                report_path = None
                if updated > 0:
                    try:
                        report_path = self._generate_outbound_report(file_path, updated)
                        self._log(f"Report: {report_path}")
                    except (ValueError, TypeError, AttributeError) as e:
                        self._log(f"WARNING Report generation failed: {e}")
                msg = (f"출고 결과 반영 완료\n\n• 반영: {updated}건\n• 재고 없음: {not_found}건\n• 이미 출고: {already_picked}건")
                if blocked_reversed:
                    msg += f"\n• 상태 보호(역전 차단): {blocked_reversed}건"
                if report_path:
                    msg += f"\n\n보고서: {os.path.basename(report_path)}"
                    if CustomMessageBox.askyesno(self.root, "완료", msg + "\n\n보고서를 열까요?"):
                        self._open_file(report_path)
                else:
                    CustomMessageBox.showinfo(self.root, "완료", msg)
                self._safe_refresh()
                self._set_status("Ready")

            def do_cancel():
                win.destroy()
                self._set_status("Ready")

            btn_frm = ttk.Frame(frm)
            btn_frm.pack(fill=tk.X, pady=(10, 0))
            ttk.Button(btn_frm, text="DB 반영", command=do_apply).pack(side=tk.LEFT, padx=4)
            ttk.Button(btn_frm, text="취소", command=do_cancel).pack(side=tk.LEFT, padx=4)
            center_dialog(win, self.root)

        except (OSError, IOError, PermissionError) as e:
            self._log(f"X Outbound import error: {e}")
            CustomMessageBox.showerror(self.root, "오류", f"출고 결과 불러오기 실패:\n{e}")
        self._set_status("Ready")
    
    def _import_location_excel(self) -> None:
        """v7.0.1: tonbag_location_uploader로 통합 — 3단계 매칭 + 미리보기 + 이력 기록 지원."""
        try:
            from ..dialogs.tonbag_location_upload import show_tonbag_location_upload_dialog
            
            def _after_upload():
                """업로드 완료 후 탭 새로고침"""
                if hasattr(self, '_refresh_main_tabs'):
                    self._refresh_main_tabs()
                else:
                    if hasattr(self, '_refresh_inventory'):
                        self._refresh_inventory()
                    if hasattr(self, '_refresh_tonbag'):
                        self._refresh_tonbag()
            
            show_tonbag_location_upload_dialog(self.root, self.engine, callback=_after_upload)
        except (ImportError, RuntimeError) as e:
            logger.error(f"Location upload dialog 호출 실패: {e}")
            CustomMessageBox.showerror(self.root, "Error", f"Location upload failed:\n{e}")

    def _generate_outbound_report(self, source_file: str, count: int) -> str:
        """Generate outbound report after import"""
        import pandas as pd
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"output/outbound_report_{timestamp}.xlsx"
        os.makedirs("output", exist_ok=True)
        
        # Get recent outbound tonbags
        recent = self.engine.db.fetchall("""
            SELECT
                t.sap_no as SAP_NO, t.bl_no as BL_NO, t.lot_no as LOT_NO,
                t.sub_lt as Tonbag, t.weight as Weight_kg,
                t.outbound_date as Outbound_Date, t.picked_to as Customer,
                t.pick_ref as Sale_Ref
            FROM inventory_tonbag t
            WHERE t.status = 'PICKED'
            ORDER BY t.updated_at DESC
            LIMIT ?
        """, (count + 50,))
        
        # Summary
        summary_data = {
            'Item': ['Source File', 'Process Time', 'Processed Count'],
            'Value': [os.path.basename(source_file), 
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                     str(count)]
        }
        
        with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            if recent:
                pd.DataFrame(recent).to_excel(writer, sheet_name='Outbound Details', index=False)
        
        return report_path
    

    def _safe_int(self, val, default: int = 0) -> int:
        """Safe integer conversion"""
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default
    
    def _safe_date(self, val) -> date:
        """Safe date conversion"""
        import pandas as pd
        
        if pd.isna(val):
            return date.today()
        if isinstance(val, str):
            try:
                return datetime.strptime(val, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return date.today()
        if hasattr(val, 'date'):
            return val.date()
        return date.today()
    
