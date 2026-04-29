# -*- coding: utf-8 -*-
"""
SQM 재고관리 - 일괄 업로드 Mixin
=================================
v3.8.4 - advanced_features_mixin에서 분리

기능:
- 입고현황 일괄 업로드
- 톤백 일괄 업로드
"""

import logging
from ..utils.ui_constants import CustomMessageBox

logger = logging.getLogger(__name__)


class BulkImportMixin:
    """입고/톤백 일괄 업로드 Mixin"""

    def _bulk_import_inventory(self) -> None:
        """
        v6.2.2 성능 보완: 입고현황 조회 다이얼로그 오픈
        """
        try:
            from ..dialogs.inbound_history_dialog import InboundHistoryDialog
            dialog = InboundHistoryDialog(
                parent=self.root,
                engine=self.engine,
                log_fn=self._log,
                app=self
            )
            dialog.show()
        except (ImportError, ModuleNotFoundError) as e:
            logger.error(f"입고현황 조회 오류: {e}", exc_info=True)
            CustomMessageBox.showerror(self.root, "오류", f"입고현황 조회 오류:\n{e}")
    
