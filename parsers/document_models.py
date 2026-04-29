"""
SQM 재고관리 - 통합 문서 데이터 모델 (v2.5.4)

★★★ Single Source of Truth ★★★
모든 데이터 클래스는 이 파일에서만 정의합니다.
다른 파일에서는 이 모듈을 import해서 사용하세요.

4개 선적 문서의 데이터 모델:
- Invoice (FA): 상업송장
- Packing List: 포장명세서
- B/L (Bill of Lading): 선하증권
- D/O (Delivery Order): 화물인도지시서

Author: Ruby
Version: 2.5.4
Date: 2026-01-09
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# =============================================================================
# 열거형 (Enum)
# =============================================================================

class TransactionType(str, Enum):
    """거래 유형"""
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    ADJUST = "ADJUST"
    TRANSFER = "TRANSFER"


class StockStatus(str, Enum):
    """재고 상태"""
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    HOLD = "HOLD"
    DAMAGED = "DAMAGED"


class OutboundStatus(str, Enum):
    """출고 상태"""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# =============================================================================
# 기본 클래스
# =============================================================================

@dataclass
class BaseModel:
    """기본 모델 클래스"""

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """딕셔너리에서 생성"""
        # 해당 클래스의 필드만 추출
        valid_fields = {f for f in cls.__dataclass_fields__} if hasattr(cls, '__dataclass_fields__') else set()
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


@dataclass
class AuditMixin:
    """감사 정보 믹스인"""
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

    def set_created(self, user: str = "SYSTEM"):
        self.created_at = datetime.now()
        self.created_by = user

    def set_updated(self, user: str = "SYSTEM"):
        self.updated_at = datetime.now()
        self.updated_by = user


# =============================================================================
# 문서 파싱용 데이터 클래스
# =============================================================================

@dataclass
class ContainerInfo:
    """컨테이너 정보"""
    container_no: str = ""           # FFAU5355006
    seal_no: str = ""                # CL0501798, ML-CL0501798
    size_type: str = ""              # 45G1, 40 DRY 9'6
    weight_kg: float = 0             # 20525.000
    measurement_cbm: float = 0       # 20.0040
    package_count: int = 0           # 44


@dataclass
class FreeTimeInfo:
    """Free Time 정보 (D/O에서 추출)"""
    container_no: str = ""
    free_time_date: str = ""         # 2025-11-11 (str로 통일)
    return_location: str = ""        # KRKNYTM
    storage_free_days: int = 0       # v4.1.7: Free Time 일수


@dataclass
class LOTInfo:
    """LOT 상세 정보 (Packing List에서 추출)"""
    list_no: int = 0                 # 1, 2, 3...
    container_no: str = ""           # FFAU535500-6
    lot_no: str = ""                 # 1125081447
    lot_sqm: str = ""                # 977878
    mxbg_pallet: int = 10            # MAXIBAG/PALLET 수량
    plastic_jars: int = 1            # PLASTIC JARS 수량
    net_weight_kg: float = 0         # 5001 (kg)
    gross_weight_kg: float = 0       # 5131.250 (kg)
    del_no: str = ""                 # 1714372
    al_no: str = ""                  # 1714381
    acc_net_weight: float = 0        # 누적 순중량
    acc_gross_weight: float = 0      # 누적 총중량


@dataclass
class FreightCharge:
    """운임 정보 (B/L에서 추출)"""
    description: str = ""            # Basic Ocean Freight
    rate: float = 0                  # 498.00
    unit: str = ""                   # Per Container
    currency: str = ""               # USD
    prepaid: float = 0               # 2490.00
    collect: float = 0


# =============================================================================
# 문서별 데이터 모델
# =============================================================================

@dataclass
class InvoiceData:
    """Invoice (상업송장) 데이터 - FA 파일"""
    # 핵심 식별자
    sap_no: str = ""                 # 2200033057 (Ref.SQM/Our Order)
    invoice_no: str = ""             # 16130 (→ salar_invoice_no로 전달됨)
    salar_invoice_no: str = ""       # v2.9.11: N° 16130 (5자리 Salar Invoice Number)
    invoice_date: Optional[date] = None        # 2025-09-06

    # 참조 번호
    customer_ref: str = ""           # 4500002194 (Ref.Cliente/Your Order)
    inv_acc_doc: str = ""            # 3200033162 - 3000002739
    delivery_transport: str = ""     # 8000056066 - 6005704
    bl_no: str = ""                  # 258468669

    # 당사자 정보
    customer_code: str = ""          # 101387
    customer_name: str = ""          # SOQUIMICH LLC
    customer_address: str = ""

    # 제품 정보
    product_code: str = ""           # MIC9000.00
    product_name: str = ""           # LITHIUM CARBONATE - BATTERY GRADE - MICRONIZED
    quantity_mt: float = 0           # 100.02 (MT)
    unit_price: float = 0            # 9272.00
    total_amount: float = 0          # 927385.44
    currency: str = "USD"

    # 중량
    net_weight_kg: float = 0         # 100020
    gross_weight_kg: float = 0       # 102625

    # 포장
    package_count: int = 0           # 200 (MAXISACO)
    package_type: str = ""           # MAXISACO MIC9000, PLASTIC JAR
    jar_count: int = 0               # 20 (PLASTIC JAR)

    # 운송 정보
    vessel: str = ""                 # CHARLOTTE MAERSK 535W
    origin: str = ""                 # PUERTO ANGAMOS-CHILE
    destination: str = ""            # GWANGYANG-SOUTH KOREA

    # 거래 조건
    incoterm: str = ""               # CIF
    payment_term: str = ""           # PAYABLE AT 90 DAYS FROM INVOICE DATE

    # LOT 목록 (Invoice에도 N° LOTES로 기재됨)
    lot_numbers: List[str] = field(default_factory=list)

    # 메타
    source_file: str = ""
    parsed_at: Optional[datetime] = None
    raw_text: str = ""

    # v9.0 Phase 2 — PackingListResult 통합 필드
    # GeminiDocumentParser.parse_packing_list()가 PackingListData를 직접 반환하도록
    # 하기 위해 필요한 필드들 (이전에는 PackingListResult에만 있었음)
    bag_weight_kg: int = None         # v8.6.1: None=미설정(DEFAULT_TONBAG_WEIGHT fallback)
    error_message: str = ""           # Gemini 파싱 오류 메시지
    raw_response: str = ""            # Gemini 원본 응답 (디버깅용)
    pl_warnings: list = None          # PL 검증 경고 목록

    # 호환성용 속성
    @property
    def customer(self) -> str:
        return self.customer_name

    @property
    def product(self) -> str:
        return self.product_name

    @property
    def lots(self) -> List[str]:
        return self.lot_numbers


    # v9.0 Phase3 — InvoiceResult 통합 필드
    success: bool = False           # 파싱 성공 여부
    error_message: str = ""         # Gemini 파싱 오류 메시지
    raw_response: str = ""          # Gemini 원본 응답


@dataclass
class PackingListHeader:
    """PACKING LIST 헤더 정보 (DB 호환용)"""
    folio: str = ""
    product: str = ""
    packing: str = ""
    code: str = ""
    vessel: str = ""
    customer: str = ""
    destination: str = ""
    bl_no: Optional[str] = None
    arrival_date: Optional[date] = None

    def __str__(self) -> str:
        return f"PackingListHeader[Folio={self.folio}, Product={self.product}]"


@dataclass
class PackingListRow:
    """PACKING LIST 상세 행 (DB 호환용)"""
    list_no: int = 0
    container: str = ""
    lot_no: str = ""
    lot_sqm: str = ""
    mxbg_pallet: int = 0
    plastic_jars: int = 0
    net_weight: float = 0.0
    gross_weight: float = 0.0
    del_no: str = ""
    al_no: str = ""
    acc_net_weight: float = 0.0
    acc_gross_weight: float = 0.0

    def __str__(self) -> str:
        return f"Row[{self.list_no}: {self.container}, LOT={self.lot_no}]"


@dataclass
class PackingListData:
    """Packing List (포장명세서) 데이터"""
    # 헤더 정보 (직접 필드)
    folio: str = ""                  # 3770868
    product: str = ""                # LITHIUM CARBONATE
    packing: str = ""                # MX 500 Kg (In Wooden Pallet)
    code: str = ""                   # MIC9000.00/500 KG
    vessel: str = ""                 # CHARLOTTE MAERSK 535W
    customer: str = ""               # SOQUIMICH LLC
    destination: str = ""            # GWANGYANG
    sap_no: str = ""                 # v3.8.8: 2200033057 (파일명에서 추출)

    # DB 호환용 헤더 객체 (선택)
    header: Optional[PackingListHeader] = None

    # LOT 상세 목록 (LOTInfo 또는 PackingListRow)
    lots: List[LOTInfo] = field(default_factory=list)
    rows: List[PackingListRow] = field(default_factory=list)  # DB 호환용

    # 요약
    total_lots: int = 0              # 20
    total_net_weight_kg: float = 0   # 100020
    total_gross_weight_kg: float = 0 # 102625
    total_maxibag: int = 0           # 200
    total_plastic_jars: int = 0      # 20

    # 컨테이너 요약
    containers: List[str] = field(default_factory=list)
    duplicate_skipped_lot_nos: List[str] = field(default_factory=list)

    # 푸터
    footer_note: str = ""

    # 로고 이미지 (PDF 보고서용)
    logo_image: Optional[bytes] = None

    # 메타
    source_file: str = ""
    parsed_at: Optional[datetime] = None
    raw_text: str = ""

    # v9.0 Phase2 — PackingListResult 통합 필드
    bag_weight_kg: int = None         # v8.6.1: None=미설정(DEFAULT_TONBAG_WEIGHT fallback)
    error_message: str = ""           # Gemini 오류 메시지
    raw_response: str = ""            # Gemini 원본 응답
    pl_warnings: list = None          # PL 검증 경고


    def __post_init__(self) -> None:
        """헤더 객체 자동 생성 (DB 호환)"""
        if self.header is None:
            self.header = PackingListHeader(
                folio=self.folio,
                product=self.product,
                packing=self.packing,
                code=self.code,
                vessel=self.vessel,
                customer=self.customer,
                destination=self.destination
            )
        # rows가 비어있고 lots가 있으면 변환
        if not self.rows and self.lots:
            for lot in self.lots:
                self.rows.append(PackingListRow(
                    list_no=lot.list_no,
                    container=lot.container_no,
                    lot_no=lot.lot_no,
                    lot_sqm=lot.lot_sqm,
                    mxbg_pallet=lot.mxbg_pallet,
                    plastic_jars=lot.plastic_jars,
                    net_weight=lot.net_weight_kg,
                    gross_weight=lot.gross_weight_kg,
                    del_no=lot.del_no,
                    al_no=lot.al_no,
                    acc_net_weight=lot.acc_net_weight,
                    acc_gross_weight=lot.acc_gross_weight
                ))

    @property
    def total_rows(self) -> int:
        return len(self.rows) or len(self.lots)

    @property
    def total_net_weight(self) -> float:
        """총 순중량 (호환용)"""
        if self.total_net_weight_kg > 0:
            return self.total_net_weight_kg
        if self.rows:
            if self.rows[-1].acc_net_weight > 0:
                return self.rows[-1].acc_net_weight
            return sum(row.net_weight for row in self.rows)
        if self.lots:
            return sum(lot.net_weight_kg for lot in self.lots)
        return 0.0

    @property
    def total_gross_weight(self) -> float:
        """총 총중량 (호환용)"""
        if self.total_gross_weight_kg > 0:
            return self.total_gross_weight_kg
        if self.rows:
            if self.rows[-1].acc_gross_weight > 0:
                return self.rows[-1].acc_gross_weight
            return sum(row.gross_weight for row in self.rows)
        if self.lots:
            return sum(lot.gross_weight_kg for lot in self.lots)
        return 0.0

    @property
    def product_code(self) -> str:
        """제품 코드 (호환용)"""
        return self.code

    def __str__(self) -> str:
        return f"PackingList[Folio={self.folio}, Rows={self.total_rows}]"


@dataclass
class BLData:
    """B/L (선하증권) 데이터"""
    # 핵심 식별자
    bl_no: str = ""                  # 258468669
    booking_no: str = ""             # 258468669 (보통 B/L과 동일)
    scac: str = ""                   # MAEU
    svc_contract: str = ""           # 298602393

    # SAP NO (B/L 2페이지에 있음)
    sap_no: str = ""                 # 2200033057

    # 당사자 정보
    shipper_name: str = ""           # SQM SALAR SpA.
    shipper_address: str = ""
    consignee_name: str = ""         # SOQUIMICH LLC
    consignee_address: str = ""
    notify_party: str = ""

    # 운송 정보
    vessel: str = ""                 # CHARLOTTE MAERSK
    voyage: str = ""                 # 535W
    port_of_loading: str = ""        # Puerto Angamos, Chile
    port_of_discharge: str = ""      # GWANGYANG, SOUTH KOREA
    place_of_receipt: str = ""
    place_of_delivery: str = ""

    # 날짜
    shipped_on_board_date: Optional[date] = None  # 2025-09-06
    ship_date: Optional[date] = None              # 호환용 alias
    issue_date: Optional[date] = None             # 2025-09-07
    place_of_issue: str = ""            # Santiago

    # 화물 정보
    product_name: str = ""           # LITHIUM CARBONATE - BATTERY GRADE - MICRONIZED
    total_containers: int = 0        # 5
    total_packages: int = 0          # 220 (44 × 5)
    net_weight_kg: float = 0         # 100020
    gross_weight_kg: float = 0       # 102625
    total_cbm: float = 0             # 100.020
    total_weight: float = 0          # 호환용

    # 컨테이너 상세
    containers: List[ContainerInfo] = field(default_factory=list)

    # 운임
    freight_charges: List[FreightCharge] = field(default_factory=list)
    total_freight_usd: float = 0     # 6180.00
    total_freight_krw: float = 0     # 250000.00
    freight_terms: str = ""          # FREIGHT PREPAID

    # 메타
    source_file: str = ""
    parsed_at: Optional[datetime] = None
    raw_text: str = ""

    # 호환용 속성
    @property
    def shipper(self) -> str:
        return self.shipper_name

    @shipper.setter
    def shipper(self, value: str):
        self.shipper_name = value

    @property
    def consignee(self) -> str:
        return self.consignee_name

    @consignee.setter
    def consignee(self, value: str):
        self.consignee_name = value


    # v9.0 Phase3 — BLResult 통합 필드
    success: bool = False           # 파싱 성공 여부
    error_message: str = ""         # Gemini 파싱 오류 메시지
    raw_response: str = ""          # Gemini 원본 응답

    # v8.4.5: 선사 정보 — 선사 뱃지 표시용
    carrier_id: str = ""            # 예: "MSC", "MAERSK"
    carrier_name: str = ""          # 예: "Mediterranean Shipping Company"
    bl_equals_booking_no: bool = False  # Maersk 전용: BL No == Booking No 정상 플래그



@dataclass
class DOData:
    """D/O (화물인도지시서) 데이터"""
    # 핵심 식별자
    do_no: str = ""                  # 241044299
    bl_no: str = ""                  # MAEU258468669 또는 258468669
    sap_no: str = ""                 # v2.9.8: 2200033057 (D/O에도 있을 수 있음)

    # 당사자 정보
    shipper: str = ""                # SQM SALAR SPA.
    consignee: str = ""              # SOQUIMICH LLC
    notify_party: str = ""           # SOQUIMICH LLC

    # 운송 정보
    vessel: str = ""                 # CHARLOTTE MAERSK
    voyage: str = ""                 # 535W
    flag: str = ""                   # DK
    port_of_loading: str = ""        # CLMJS
    port_of_discharge: str = ""      # KRKAN
    final_destination: str = ""      # KRKAN
    place_of_delivery: str = ""      # KRKAN

    # 날짜 (중요!)
    arrival_date: Optional[date] = None        # 2025-10-17 (선박 입항일)
    issue_date: Optional[date] = None          # 2025-10-20 (D/O 발행일)
    stock_date: Optional[date] = None          # v2.9.29: DATE IN STOCK (arrival_date와 분리)

    # 화물 정보
    description: str = ""            # LITHIUM CARBONATE BATTERY GRADE MICRONIZED
    gross_weight_kg: float = 0       # 102625
    measurement_cbm: float = 0       # 100.020
    total_packages: int = 0          # 220 GT

    # 컨테이너 (Seal No 포함)
    containers: List[ContainerInfo] = field(default_factory=list)

    # Free Time 정보
    free_time_info: List[FreeTimeInfo] = field(default_factory=list)

    # 창고 정보
    warehouse_code: str = ""         # 06277057
    warehouse_name: str = ""         # 광양항서부컨테이너터미널
    mrn: str = ""                    # 25MAEUK2161
    msn: str = ""                    # 1018

    # 메타
    source_file: str = ""
    parsed_at: Optional[datetime] = None
    raw_text: str = ""
    is_image_pdf: bool = False       # 이미지 PDF 여부


    # v9.0 Phase3 — DOResult 통합 필드
    success: bool = False           # 파싱 성공 여부
    error_message: str = ""         # Gemini 파싱 오류 메시지
    raw_response: str = ""          # Gemini 원본 응답



@dataclass
class ShipmentDocuments:
    """선적 문서 통합 데이터"""
    # 핵심 식별자 (교차 검증용)
    sap_no: str = ""                 # Invoice, B/L에서 추출
    bl_no: str = ""                  # 모든 문서에서 추출 가능
    folio: str = ""                  # Packing List에서만
    do_no: str = ""                  # D/O에서만

    # 개별 문서 데이터
    invoice: Optional[InvoiceData] = None
    packing_list: Optional[PackingListData] = None
    bl: Optional[BLData] = None
    do: Optional[DOData] = None

    # 통합 정보 (교차 검증 후 확정)
    product_code: str = ""
    product_name: str = ""
    vessel: str = ""
    voyage: str = ""
    origin: str = ""
    destination: str = ""

    # 날짜
    invoice_date: Optional[date] = None        # Invoice에서
    shipped_date: Optional[date] = None        # B/L에서 (선적일)
    arrival_date: Optional[date] = None        # D/O에서 (입항일)

    # 중량 (교차 검증)
    net_weight_kg: float = 0
    gross_weight_kg: float = 0

    # LOT 정보 (Packing List에서)
    total_lots: int = 0
    lots: List[LOTInfo] = field(default_factory=list)

    # 컨테이너 정보 (B/L에서)
    total_containers: int = 0
    containers: List[ContainerInfo] = field(default_factory=list)

    # 검증 상태
    is_validated: bool = False
    validation_errors: List[str] = field(default_factory=list)

    # 메타
    parsed_at: Optional[datetime] = None


# =============================================================================
# DB 저장용 모델 (InboundRecord, InventoryItem 등)
# =============================================================================

@dataclass
class InboundRecord(BaseModel, AuditMixin):
    """입고 기록 (DB 저장용)"""
    id: Optional[int] = None

    # PACKING LIST 정보
    folio: str = ""
    product: str = ""
    product_code: str = ""
    vessel: str = ""
    customer: str = ""
    destination: str = ""

    # 컨테이너/LOT 정보
    container_no: str = ""
    lot_no: str = ""
    lot_sqm: str = ""

    # 수량 정보
    pallet_count: int = 0
    net_weight: float = 0.0
    gross_weight: float = 0.0

    # 입고 정보
    inbound_date: Optional[date] = None
    warehouse_location: str = ""

    # 상태
    status: str = "AVAILABLE"

    # 감사 정보
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


@dataclass
class InventoryItem(BaseModel):
    """재고 항목"""
    id: Optional[int] = None
    lot_no: str = ""
    product: str = ""
    product_code: str = ""

    initial_weight: float = 0.0
    current_weight: float = 0.0
    reserved_weight: float = 0.0

    folio: str = ""
    container_no: str = ""
    warehouse: str = "GY"
    location: str = ""

    status: str = "AVAILABLE"

    inbound_date: Optional[date] = None
    last_movement_date: Optional[date] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class InventorySummary:
    """재고 요약"""
    product: str = ""
    total_lots: int = 0
    total_weight: float = 0.0
    available_weight: float = 0.0
    reserved_weight: float = 0.0


@dataclass
class StockMovement(BaseModel):
    """재고 이동 기록"""
    id: Optional[int] = None
    lot_no: str = ""
    movement_type: str = ""  # INBOUND, OUTBOUND, ADJUST
    quantity: float = 0.0

    reference_no: str = ""
    from_location: str = ""
    to_location: str = ""

    movement_date: Optional[date] = None
    remarks: str = ""

    created_at: Optional[datetime] = None
    created_by: Optional[str] = None


@dataclass
class OutboundItem(BaseModel):
    """출고 항목"""
    id: Optional[int] = None
    order_id: Optional[int] = None
    lot_no: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0


@dataclass
class OutboundOrder(BaseModel):
    """출고 주문"""
    id: Optional[int] = None
    order_no: str = ""
    customer: str = ""
    order_date: Optional[date] = None

    items: List[OutboundItem] = field(default_factory=list)

    total_quantity: float = 0.0
    total_amount: float = 0.0

    status: str = "PENDING"

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CustomerStock:
    """고객별 재고"""
    customer: str = ""
    product: str = ""
    total_weight: float = 0.0
    lot_count: int = 0


# =============================================================================
# 모듈 Export
# =============================================================================

__all__ = [
    # Enum
    "TransactionType",
    "StockStatus",
    "OutboundStatus",
    # Base
    "BaseModel",
    "AuditMixin",
    # Document Parsing
    "ContainerInfo",
    "FreeTimeInfo",
    "LOTInfo",
    "FreightCharge",
    # Documents
    "InvoiceData",
    "PackingListHeader",
    "PackingListRow",
    "PackingListData",
    "BLData",
    "DOData",
    "ShipmentDocuments",
    # DB Models
    "InboundRecord",
    "InventoryItem",
    "InventorySummary",
    "StockMovement",
    "OutboundItem",
    "OutboundOrder",
    "CustomerStock",
]
