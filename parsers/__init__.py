"""
SQM 재고관리 - 파서 패키지 (v2.9.43)

★★★ Single Source of Truth ★★★
- 모든 데이터 모델: document_models.py
- 모든 파싱 로직: document_parser_modular/ (V3)
- PDF 파싱: pdf_parser.py
- 출고 할당: allocation_parser.py
- 문서 감지: document_detector.py (v2.9.43 NEW)
- v8.5.6: document_parser_v2.py 삭제 → V3 직접 export
"""

# =============================================================================
# 문서 유형 감지 (v2.9.43 NEW)
# =============================================================================
from .document_detector import (
    DetectionResult,
    DocumentDetector,
    DocumentType,
    ScoreEntry,
    detect_document_type,
    detect_with_report,
)

# =============================================================================
# 데이터 모델 (Single Source of Truth)
# =============================================================================
from .document_models import (
    AuditMixin,
    # Base
    BaseModel,
    BLData,
    # Document Parsing
    ContainerInfo,
    CustomerStock,
    DOData,
    FreeTimeInfo,
    FreightCharge,
    # DB Models
    InboundRecord,
    InventoryItem,
    InventorySummary,
    # Documents
    InvoiceData,
    LOTInfo,
    OutboundItem,
    OutboundOrder,
    OutboundStatus,
    PackingListData,
    PackingListHeader,
    PackingListRow,
    ShipmentDocuments,
    StockMovement,
    StockStatus,
    # Enum
    TransactionType,
)

# =============================================================================
# 메인 파서 (v3.0 — v8.5.6: V2 래퍼 삭제, V3 직접 export)
# =============================================================================
from .document_parser_modular import DocumentParserV3 as DocumentParserV2
from .document_parser_modular import DocumentParserV3

# =============================================================================
# PDF 파서
# =============================================================================
try:
    from .pdf_parser import PDFParser, parse_pdf
except ImportError:
    PDFParser = None
    parse_pdf = None

# =============================================================================
# 출고 할당 파서
# =============================================================================
try:
    from .allocation_parser import AllocationData, AllocationParser
except ImportError:
    AllocationParser = None
    AllocationData = None

# =============================================================================
# Picking List 파서 (LBM 스타일, picking_list_order/detail 매칭)
# =============================================================================
try:
    from .picking_list_parser import (
        NET_WEIGHT_IMPLICIT_SAMPLE_KG,
        BatchLine,
        ItemBlock,
        PickingDoc,
        build_pick_plan,
        decode_net_weight_kg,
        parse_picking_list_pdf,
        parse_picking_text,
        to_sqm_picking_detail_rows,
        to_sqm_picking_order_row,
    )
except ImportError:
    BatchLine = None
    ItemBlock = None
    PickingDoc = None
    decode_net_weight_kg = None
    NET_WEIGHT_IMPLICIT_SAMPLE_KG = None
    parse_picking_text = None
    parse_picking_list_pdf = None
    to_sqm_picking_order_row = None
    to_sqm_picking_detail_rows = None
    build_pick_plan = None

# Base Parser
from .base import BaseParser

# =============================================================================
# 크로스 체크 엔진 (v6.2.1 NEW)
# =============================================================================
try:
    from .cross_check_engine import (
        CheckItem,
        CheckLevel,
        CrossCheckEngine,
        CrossCheckResult,
        cross_check_documents,
    )
except ImportError:
    CrossCheckEngine = None
    CrossCheckResult = None
    CheckItem = None
    CheckLevel = None
    cross_check_documents = None

# =============================================================================
# Export
# =============================================================================
__all__ = [
    # ===== 문서 감지 (v2.5.4 NEW) =====
    "DocumentDetector",
    "DocumentType",
    "DetectionResult",
    "ScoreEntry",
    "detect_document_type",
    "detect_with_report",
    # ===== 메인 (권장) =====
    # 파서 (v8.5.6: V3 직접 export, V2 별칭 유지)
    "DocumentParserV2",
    "DocumentParserV3",
    # PDF 파서
    "PDFParser",
    "parse_pdf",
    # 출고 할당
    "AllocationParser",
    "AllocationData",
    # Picking List (LBM)
    "BatchLine",
    "ItemBlock",
    "PickingDoc",
    "parse_picking_text",
    "parse_picking_list_pdf",
    "to_sqm_picking_order_row",
    "to_sqm_picking_detail_rows",
    "build_pick_plan",
    "decode_net_weight_kg",
    "NET_WEIGHT_IMPLICIT_SAMPLE_KG",
    # 데이터 모델
    "ContainerInfo",
    "FreeTimeInfo",
    "LOTInfo",
    "FreightCharge",
    "InvoiceData",
    "PackingListHeader",
    "PackingListRow",
    "PackingListData",
    "BLData",
    "DOData",
    "ShipmentDocuments",
    # DB 모델
    "InboundRecord",
    "InventoryItem",
    "InventorySummary",
    "StockMovement",
    "OutboundItem",
    "OutboundOrder",
    "CustomerStock",
    # Enum
    "TransactionType",
    "StockStatus",
    "OutboundStatus",
    # Base
    "BaseModel",
    "AuditMixin",
    "BaseParser",
    # 크로스 체크 (v6.2.1)
    "CrossCheckEngine",
    "CrossCheckResult",
    "CheckItem",
    "CheckLevel",
    "cross_check_documents",
]
