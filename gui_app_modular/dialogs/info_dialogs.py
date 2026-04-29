# -*- coding: utf-8 -*-
"""
SQM Inventory - Information Dialogs
===================================

v3.6.0 - 안정성/효율성/편의성 강화
- 다이얼로그 크기 표준화 (DialogSize)
- 간격 표준화 (Spacing)
- 폰트 스케일링 (FontScale)
- 컬럼 너비 표준화 (ColumnWidth)
- 중앙 배치 (center_dialog)
"""

import logging

logger = logging.getLogger(__name__)


class InfoDialogsMixin:
    """
    Information dialogs mixin
    
    Mixed into SQMInventoryApp class
    """
    
