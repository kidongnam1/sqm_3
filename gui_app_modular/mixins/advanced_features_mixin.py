"""
SQM 재고관리 - 고급 기능 Mixin (통합 래퍼)
=============================================
v3.8.4 - 3개 모듈로 분리 완료

분리된 모듈:
- bulk_import_mixin.py      (일괄 업로드)
- diagnostics_mixin.py      (진단/검증)
- advanced_dialogs_mixin.py (고급 다이얼로그)

이 파일은 하위 호환성을 위한 래퍼입니다.
"""

from .advanced_dialogs_mixin import AdvancedDialogsMixin
from .bulk_import_mixin import BulkImportMixin
from .diagnostics_mixin import DiagnosticsMixin


class AdvancedFeaturesMixin(BulkImportMixin, DiagnosticsMixin, AdvancedDialogsMixin):
    """
    고급 기능 Mixin (통합 래퍼)
    
    기존 코드에서 AdvancedFeaturesMixin을 import하던 곳은 변경 없이 동작합니다.
    """
