"""
SQM 재고관리 시스템 - 문서 파서 모듈화 패키지
=============================================

v3.6.0: document_parser_v2.py (1,762줄) → 6개 모듈로 분리

모듈 구조:
    document_parser_modular/
    ├── __init__.py          # 이 파일 (통합 export)
    ├── base.py              # 공통 기능 (~230줄)
    ├── invoice_mixin.py     # Invoice 파서 (~220줄)
    ├── packing_mixin.py     # Packing List 파서 (~200줄)
    ├── bl_mixin.py          # B/L 파서 (~180줄)
    ├── do_mixin.py          # D/O 파서 (~250줄)
    └── parser.py            # 통합 클래스 (~180줄)

사용 예시:
    >>> from parsers.document_parser_modular import DocumentParserV3
    >>> 
    >>> parser = DocumentParserV3(gemini_api_key='your_key')
    >>> invoice = parser.parse_invoice('invoice.pdf')
    >>> packing = parser.parse_packing_list('packing.pdf')

하위 호환성:
    기존 document_parser_v2.py의 DocumentParserV2도 계속 사용 가능합니다.

작성자: Ruby (남기동)
버전: v3.6.0
"""

# 데이터 모델 re-export
from ..document_models import (
    BLData,
    ContainerInfo,
    DOData,
    FreeTimeInfo,
    InvoiceData,
    LOTInfo,
    PackingListData,
    PackingListRow,
    ShipmentDocuments,
)
from .base import DocumentParserBase
from .bl_mixin import BLMixin
from .do_mixin import DOMixin
from .invoice_mixin import InvoiceMixin
from .packing_mixin import PackingMixin
from .parser import DocumentParser, DocumentParserV3
from .picking_mixin import (
    PickingListMeta,
    PickingListParserMixin,
    PickingListResult,
    PickingLotItem,
)

__all__ = [
    # 메인 클래스
    'DocumentParserV3',
    'DocumentParser',  # 별칭

    # Mixin 클래스
    'DocumentParserBase',
    'InvoiceMixin',
    'PickingListParserMixin',
    'PickingListResult',
    'PickingListMeta',
    'PickingLotItem',
    'PackingMixin',
    'BLMixin',
    'DOMixin',

    # 데이터 모델
    'InvoiceData',
    'PackingListData',
    'PackingListRow',
    'BLData',
    'DOData',
    'ContainerInfo',
    'LOTInfo',
    'FreeTimeInfo',
    'ShipmentDocuments',
]

try:
    from version import __version__ as _ver
    __version__ = _ver
except ImportError:
    __version__ = "0.0.0"
