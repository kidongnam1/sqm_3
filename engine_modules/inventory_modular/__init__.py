"""
SQM Inventory Engine - Modular Package
======================================

import logging
logger = logging.getLogger(__name__)
v2.9.91 - Complete modularization of inventory.py (5,338 lines)

Structure (15 files, ~4,300 lines):
├── __init__.py          - Package init
├── utils.py             - Utility functions
├── base.py              - Base engine class
├── engine.py            - Combined engine (SQMInventoryEngineV3)
│
├── inbound_mixin.py     - Inbound processing
├── outbound_mixin.py    - Outbound processing  
├── query_mixin.py       - Query functions
│
├── export_mixin.py      - Excel export (options 1-3)
├── export_mixin.py          - Excel export (options 1-6, v5.5.3 통합)
│
├── shipment_mixin.py    - Shipment document processing
├── tonbag_mixin.py      - Tonbag management
├── return_mixin.py      - Return processing
├── import_mixin.py      - Excel import
├── preflight_mixin.py   - Preflight validation
└── crud_mixin.py        - CRUD and search

Usage:
    from engine_modules.inventory_modular import SQMInventoryEngineV3
    engine = SQMInventoryEngineV3(db_path)
    
    # Or use individual mixins
    from engine_modules.inventory_modular import QueryMixin, ExportMixin
"""

import logging

logger = logging.getLogger(__name__)

from .engine import SQMInventoryEngine, SQMInventoryEngineV3

# Export all mixins
try:
    from .crud_mixin import CRUDMixin
    from .export_mixin import ExportMixin
    from .import_mixin import ImportMixin
    from .inbound_mixin import InboundMixin
    from .integrity_mixin import IntegrityMixin
    from .outbound_mixin import OutboundMixin
    from .preflight_mixin import PreflightMixin
    from .query_mixin import QueryMixin
    from .return_mixin import ReturnMixin

    # v5.5.3 P6: export_extended_mixin 제거 (export_mixin으로 통합)
    from .shipment_mixin import ShipmentMixin
    from .tonbag_mixin import TonbagMixin
    # v5.5.3 P8: outbound_extended_mixin 제거 (죽은 코드)
    # v5.6.7: lot_management_mixin 제거 (빈 placeholder)
except ImportError as e:
    logger.warning(f"Mixin import warning: {e}")

# Export utilities
try:
    from .utils import (
        PackingDataAdapter,
        dict_to_packing_data,
        format_lot_no,
        format_weight,
        normalize_column_name,
        safe_parse_date,
        safe_parse_float,
        safe_parse_int,
    )
except ImportError as _e:
    logger.debug(f"__init__: {_e}")

__all__ = [
    # Main engine
    'SQMInventoryEngineV3',
    'SQMInventoryEngine',  # Alias
    # Mixins
    'InboundMixin',
    'OutboundMixin',
    'QueryMixin',
    'ExportMixin',
    'ShipmentMixin',
    'TonbagMixin',
    'ReturnMixin',
    'ImportMixin',
    'PreflightMixin',
    'CRUDMixin',
    'IntegrityMixin',
    # v5.6.7: LotManagementMixin 제거
    # Utils
    'safe_parse_date',
    'safe_parse_float',
    'safe_parse_int',
    'dict_to_packing_data',
    'PackingDataAdapter',
    'format_lot_no',
    'format_weight',
    'normalize_column_name',
]

try:
    from version import __version__
except ImportError:
    __version__ = "0.0.0"  # S2-3: version.py 누락 시 fallback
    import logging as _vlog
    _vlog.getLogger(__name__).warning("[버전] version.py 로드 실패 → fallback 0.0.0")
