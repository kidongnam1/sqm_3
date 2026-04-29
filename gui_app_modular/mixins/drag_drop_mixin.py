# -*- coding: utf-8 -*-
"""
SQM Inventory - Drag and Drop Mixin
===================================

v2.9.91 - Extracted from gui_app.py

File drag and drop support for the application
"""

from gui_app_modular.utils.ui_constants import create_themed_toplevel  # v8.0.9
import os
import logging
from ..utils.ui_constants import is_dark, CustomMessageBox, ThemeColors
from typing import List

logger = logging.getLogger(__name__)


class DragDropMixin:
    """
    Drag and drop mixin
    
    Mixed into SQMInventoryApp class
    """
    

    def _on_drag_enter(self, event=None) -> None:
        """v3.9.9: 드래그 진입 시 오버레이 표시"""
        if hasattr(self, '_drop_overlay'):
            return
        try:
            from ..utils.constants import tk
            self._drop_overlay = tk.Frame(self.root, bg=ThemeColors.get('statusbar_progress'))
            _dd_dark = is_dark()
            self._drop_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._drop_overlay.configure(bg=ThemeColors.get('statusbar_progress', _dd_dark))
            
            inner = tk.Frame(self._drop_overlay, bg=ThemeColors.get('info', _dd_dark), bd=3, relief='solid')
            inner.place(relx=0.1, rely=0.2, relwidth=0.8, relheight=0.6)
            
            tk.Label(inner, text="📁", bg=ThemeColors.get('info', _dd_dark), fg=ThemeColors.get('badge_text', _dd_dark),
                     font=('', 48)).pack(pady=(30, 10))
            tk.Label(inner, text="파일을 여기에 놓으세요", bg=ThemeColors.get('info', _dd_dark), fg=ThemeColors.get('badge_text', _dd_dark),
                     font=('맑은 고딕', 18, 'bold')).pack()
            tk.Label(inner, text="PDF → 입고 서류 파싱 | Excel → 입고/출고 선택",
                     bg=ThemeColors.get('info', _dd_dark), fg=ThemeColors.get('arrow_separator', _dd_dark), font=('맑은 고딕', 11)).pack(pady=5)
            
            self._drop_overlay.lift()
        except (RuntimeError, ValueError) as e:
            logger.debug(f"드롭 오버레이 오류: {e}")
    
    def _on_drag_leave(self, event=None) -> None:
        """v3.9.9: 드래그 이탈 시 오버레이 제거"""
        if hasattr(self, '_drop_overlay') and self._drop_overlay:
            try:
                self._drop_overlay.destroy()
            except (RuntimeError, ValueError) as _e:
                logger.debug(f'Suppressed: {_e}')
            self._drop_overlay = None
    
    def _on_drop(self, event) -> None:
        """Handle file drop event"""
        # v3.9.9: 오버레이 제거
        self._on_drag_leave()
        
        if not hasattr(event, 'data'):
            return
        
        # Parse dropped files
        files = self._parse_drop_data(event.data)
        
        if not files:
            return
        
        self._log(f"Dropped {len(files)} file(s)")
        
        # Process files
        self._process_dropped_files(files)
    
    def _parse_drop_data(self, data: str) -> List[str]:
        """Parse drop data to file list"""
        files = []
        
        # Handle different formats
        if data.startswith('{') and data.endswith('}'):
            # Tcl list format
            data = data[1:-1]
        
        # Split by space (handles quoted paths)
        parts = []
        current = ""
        in_quote = False
        
        for char in data:
            if char == '"':
                in_quote = not in_quote
            elif char == ' ' and not in_quote:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += char
        
        if current:
            parts.append(current)
        
        # Validate files
        for part in parts:
            path = part.strip().strip('"')
            if os.path.isfile(path):
                files.append(path)
        
        return files
    
    def _process_dropped_files(self, files: List[str]) -> None:
        """Process dropped files based on type"""

        
        pdf_files = []
        excel_files = []
        other_files = []
        
        image_extensions = ('.png', '.jpg', '.jpeg')
        for file_path in files:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.pdf':
                pdf_files.append(file_path)
            elif ext in ('.xlsx', '.xls', '.csv'):
                excel_files.append(file_path)
            elif ext in image_extensions:
                other_files.append(file_path)  # 이미지는 별도 처리(단일 시 DO로 열기)
            else:
                other_files.append(file_path)

        # Handle based on file types
        if len(files) == 1:
            file_path = files[0]
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.pdf':
                self._process_pdf_inbound(file_path)
            elif ext in image_extensions:
                # 캡처 이미지 → 원스톱 입고에서 D/O로 사전 지정
                self._process_pdf_inbound(file_path, initial_files={'DO': file_path})
            elif ext in ('.xlsx', '.xls'):
                self._show_excel_import_options(file_path)
            elif ext == '.csv':
                self._process_csv_import(file_path)
            else:
                CustomMessageBox.showinfo(self.root, "Info", f"Unsupported file type: {ext}")
        
        elif pdf_files and not excel_files:
            # Multiple PDFs - batch inbound
            self._process_batch_pdf_inbound(pdf_files)
        
        elif excel_files and not pdf_files:
            # Multiple Excel - ask which to process
            self._show_batch_excel_options(excel_files)
        
        else:
            # Mixed files
            msg = f"Dropped files:\n"
            msg += f"• PDF: {len(pdf_files)}\n"
            msg += f"• Excel: {len(excel_files)}\n"
            msg += f"• Other: {len(other_files)}\n\n"
            msg += "Process PDFs as inbound?"
            
            if pdf_files and CustomMessageBox.askyesno(self.root, "Process Files", msg):
                self._process_batch_pdf_inbound(pdf_files)
    
    def _process_pdf_inbound(self, file_path: str = None, initial_files: dict = None) -> None:
        """Process single PDF/이미지 for inbound — v5.6.5: OneStop 통합. 이미지 시 D/O로 사전 지정."""
        if hasattr(self, '_on_pdf_inbound'):
            self._on_pdf_inbound(initial_files=initial_files or {})
        else:
            self._log(f"PDF/이미지 처리 불가: {file_path}")
    
    def _process_batch_pdf_inbound(self, files: List[str]) -> None:
        """v5.6.5: 다중 PDF → 원스톱 다이얼로그 1회 호출"""
        self._log(f"📥 다중 PDF {len(files)}개 → 원스톱 입고")
        if hasattr(self, '_on_pdf_inbound'):
            self._on_pdf_inbound()
    
    def _show_excel_import_options(self, file_path: str) -> None:
        """v3.9.9: Excel 파일 처리 옵션 (한글화)"""
        from ..utils.constants import tk, ttk, X
        from ..utils.ui_constants import ThemeColors, setup_dialog_geometry_persistence

        dialog = create_themed_toplevel(self.root)
        dialog.title("📥 Excel 파일 처리")
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "excel_import_options_dialog", self.root, "small")
        
        _is_dark = is_dark()
        _bg = ThemeColors.get('bg_card', _is_dark)
        _fg = ThemeColors.get('text_primary', _is_dark)
        dialog.configure(bg=_bg)
        
        # 헤더
        header = tk.Frame(dialog, bg=ThemeColors.get('info'), pady=8)
        header.pack(fill=X)
        tk.Label(header, text="📥 Excel 파일 처리 방법 선택", bg=ThemeColors.get('info', _is_dark), fg=ThemeColors.get('badge_text', _is_dark),
                 font=('맑은 고딕', 12, 'bold')).pack()
        
        body = tk.Frame(dialog, bg=_bg, padx=20, pady=10)
        body.pack(fill='both', expand=True)
        
        tk.Label(body, text=f"📄 {os.path.basename(file_path)}", bg=_bg, fg=_fg,
                 font=('맑은 고딕', 10, 'bold')).pack(pady=(5, 15))
        
        def do_inbound():
            dialog.destroy()
            self._bulk_import_inventory_simple(file_path)
        
        def do_outbound():
            dialog.destroy()
            if hasattr(self, '_on_allocation_input_unified'):
                self._on_allocation_input_unified(initial_file=file_path)
            else:
                self._on_outbound_click(file_path)
        
        def do_status():
            dialog.destroy()
            self._import_outbound_excel_with_file(file_path)
        
        def do_location():
            dialog.destroy()
            self._import_location_excel_with_file(file_path)
        
        btn_style = {'width': 25}
        ttk.Button(body, text="📥 입고 (신규 LOT 등록)", command=do_inbound, **btn_style).pack(pady=4)
        ttk.Button(body, text="📤 출고 (톤백 PICK)", command=do_outbound, **btn_style).pack(pady=4)
        ttk.Button(body, text="📊 출고 상태 업데이트", command=do_status, **btn_style).pack(pady=4)
        ttk.Button(body, text="📍 톤백 위치 매핑", command=do_location, **btn_style).pack(pady=4)
        
        ttk.Button(body, text="취소", command=dialog.destroy).pack(pady=10)
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def _show_batch_excel_options(self, files: List[str]) -> None:
        """Show options for batch Excel import"""
        from ..utils.constants import tk, ttk
        
        from ..utils.ui_constants import setup_dialog_geometry_persistence
        dialog = create_themed_toplevel(self.root)
        dialog.title("Batch Excel Import")
        dialog.transient(self.root)
        dialog.grab_set()
        setup_dialog_geometry_persistence(dialog, "batch_excel_import_dialog", self.root, "small")
        
        ttk.Label(dialog, text=f"{len(files)} Excel files selected",
                  font=('', 13, 'bold')).pack(pady=10)
        
        ttk.Label(dialog, text="Select import type for all files:").pack(pady=5)
        
        def do_batch_inbound():
            dialog.destroy()
            for f in files:
                try:
                    self._bulk_import_inventory_simple(f)
                except (RuntimeError, ValueError) as e:
                    self._log(f"Error importing {f}: {e}")
            CustomMessageBox.showinfo(self.root, "Complete", f"Processed {len(files)} files")
            self._safe_refresh()
        def do_batch_outbound():
            dialog.destroy()
            for f in files:
                try:
                    if hasattr(self, '_on_allocation_input_unified'):
                        self._on_allocation_input_unified(initial_file=f)
                    else:
                        self._on_outbound_click(f)
                except (RuntimeError, ValueError) as e:
                    self._log(f"Error processing {f}: {e}")
            CustomMessageBox.showinfo(self.root, "Complete", f"Processed {len(files)} files")
            self._safe_refresh()
        ttk.Button(dialog, text="All as Inbound", command=do_batch_inbound, width=20).pack(pady=5)
        ttk.Button(dialog, text="All as Outbound", command=do_batch_outbound, width=20).pack(pady=5)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=15)
    
    def _process_csv_import(self, file_path: str) -> None:
        """Process CSV file import"""

        
        # CSV: 톤백 위치 업로드 기능 제거됨 — 입고로 처리할지만 안내
        if CustomMessageBox.askyesno(self.root, "CSV 가져오기",
            f"CSV 파일을 입고 Excel로 처리할까요?\n\n{os.path.basename(file_path)}"):
            self._bulk_import_inventory_simple(file_path)
    
    def _import_outbound_excel_with_file(self, file_path: str) -> None:
        """Import outbound status with pre-selected file"""
        if hasattr(self, '_import_outbound_excel'):
            # Store file and call import
            self._pending_file = file_path
            self._import_outbound_excel()
    
    def _import_location_excel_with_file(self, file_path: str) -> None:
        """로케이션 Excel로 톤백 리스트(lot_no·톤백번호 동일 행) location 반영 후 톤백 리스트 새로고침."""
        from ..dialogs.tonbag_location_upload import run_location_upload_with_file
        def _after_upload():
            self._safe_refresh()
        run_location_upload_with_file(self.root, self.engine, file_path, callback=_after_upload)
