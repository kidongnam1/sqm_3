# -*- coding: utf-8 -*-
"""
SQM v4.0.1 — 입고 서류 업데이트 Mixin
=======================================

inbound_processor.py에서 분리:
- Invoice/BL/DO 기반 기존 LOT 업데이트
- Free Time 계산
- Excel 일괄 입고
"""
import os
import logging
from ..utils.custom_messagebox import CustomMessageBox
from typing import Optional, Any

logger = logging.getLogger(__name__)


class InboundUpdateMixin:
    """입고 서류 업데이트 + Excel 입고 Mixin"""


    def _process_excel_inbound(self, excel_path: str) -> None:
        """Process Excel inbound file"""

        
        filename = os.path.basename(excel_path)
        self._start_task("Excel Inbound", f"Processing: {filename}")
        self._log(f"Excel inbound: {filename}")
        
        try:
            # Detect Excel type and process
            result = self._import_inbound_excel_auto(excel_path)
            
            if result and result.get('success'):
                lots_count = result.get('lots_processed', 0)
                self._end_task(True, f"OK Excel inbound: {lots_count} LOTs")
                self._log(f"OK Excel inbound: {lots_count} LOTs")
                
                self._safe_refresh()
                CustomMessageBox.showinfo(self.root, "Excel Inbound Complete",
                    f"Excel inbound complete!\n\n"
                    f"File: {filename}\n"
                    f"LOTs: {lots_count}")
            else:
                errors = result.get('errors', ['Unknown error']) if result else ['Processing failed']
                self._end_task(False, "X Excel inbound failed")
                self._log(f"X Excel inbound failed: {errors}")
                CustomMessageBox.showerror(self.root, "Excel Inbound Failed", f"Failed:\n{errors}")
                
        except (RuntimeError, ValueError) as e:
            logger.error(f"Excel inbound error: {e}")
            self._end_task(False, f"X Error: {str(e)[:50]}...")
            self._log(f"X Excel inbound error: {e}")
            CustomMessageBox.show_detailed_error(self.root, "Error", "Excel inbound error", exception=e)
