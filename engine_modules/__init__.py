"""
SQM 재고관리 시스템 - 엔진 모듈 패키지
v3.8.5: 모듈화 + PreflightMixin 통합

사용법:
    from engine_modules import SQMDatabase, SQMInventoryEngine
"""

from engine_modules.database import SQMDatabase
from engine_modules.inventory import SQMInventoryEngine
from engine_modules.inventory_modular.preflight_mixin import PreflightMixin

# v3.8.5: SQMInventoryEngine이 이미 PreflightMixin을 MRO에 포함
SQMInventoryEngineSafe = SQMInventoryEngine

# 하위 호환: 메서드 없는 경우에만 추가 (순환 import 시 None 방어)
if PreflightMixin is not None and SQMInventoryEngine is not None:
    for method_name in ['preflight_check_inbound', 'preflight_check_outbound',
                        'process_inbound_safe', 'process_outbound_safe',
                        '_get_preflight_validator']:
        if hasattr(PreflightMixin, method_name) and not hasattr(SQMInventoryEngine, method_name):
            setattr(SQMInventoryEngine, method_name, getattr(PreflightMixin, method_name))

__all__ = [
    'SQMDatabase',
    'SQMInventoryEngine',
    'SQMInventoryEngineSafe',
    'PreflightMixin'
]
