"""
core.column_registry — 엑셀 헤더 ↔ DB 컬럼 매핑 레지스트리 (v5.9.4)
====================================================================

프로그램에서 생성한 엑셀을 다시 불러올 때 컬럼명 불일치를 원천 방지.
모든 엑셀 내보내기/불러오기는 이 레지스트리를 경유합니다.

사용 예시:
    from core.column_registry import COLUMN_REGISTRY, normalize_header, db_to_excel_header

    # 엑셀 헤더 → DB 컬럼
    db_col = normalize_header("LOT NO")  # → "lot_no"

    # DB 컬럼 → 엑셀 헤더
    excel_h = db_to_excel_header("lot_no")  # → "LOT NO"
"""
import re

COLUMN_REGISTRY = {
    # db_column: (excel_header, aliases...)
    'lot_no':           ('LOT NO', 'LOT_NO', 'LOTNO', 'LOT', 'LOT NUMBER'),
    'sap_no':           ('SAP NO', 'SAP_NO', 'SAPNO', 'SAP'),
    'bl_no':            ('BL NO', 'BL_NO', 'BLNO', 'BL', 'B/L NO'),
    'container_no':     ('CONTAINER', 'CONTAINER_NO', 'CONTAINER NO', 'CONT', 'CNTR'),
    'product':          ('PRODUCT', 'PRODUCT_NAME', 'PRODUCT_CODE'),
    'product_code':     ('CODE', 'PRODUCT_CODE'),
    'lot_sqm':          ('LOT SQM', 'LOT_SQM', 'LOTSQM'),
    'net_weight':       ('NET(Kg)', 'NET_WEIGHT', 'NET WEIGHT', 'NET(KG)', 'NET_KG'),
    'gross_weight':     ('GROSS(kg)', 'GROSS_WEIGHT', 'GROSS WEIGHT', 'GROSS(KG)', 'GROSS_KG'),
    'mxbg_pallet':      ('MXBG', 'MXBG_PALLET', 'PALLET'),
    'tonbag_count':     ('TONBAG', 'TONBAG_COUNT', 'TONBAG COUNT'),
    'ship_date':        ('SHIP DATE', 'SHIP_DATE', 'SHIPPED_DATE'),
    'arrival_date':     ('ARRIVAL', 'ARRIVAL_DATE', 'ARRIVAL DATE', '입고일', '입항일'),
    'con_return':       ('CON RETURN', 'CON_RETURN', 'CONTAINER RETURN'),
    'free_time':        ('FREE TIME', 'FREE_TIME', 'FREETIME'),
    'salar_invoice_no': ('INVOICE NO', 'SALAR_INVOICE_NO', 'INVOICE_NO', 'INVOICE'),
    'warehouse':        ('WH', 'WAREHOUSE'),
    'status':           ('STATUS',),
    'current_weight':   ('Balance(Kg)', 'BALANCE', 'CURRENT_WEIGHT', 'BALANCE(KG)'),
    'initial_weight':   ('Initial(Kg)', 'INITIAL_WEIGHT', 'INITIAL(KG)'),
    'picked_weight':    ('Picked(Kg)', 'PICKED_WEIGHT', 'PICKED(KG)'),
    'sold_to':          ('SOLD TO', 'SOLD_TO', 'CUSTOMER', 'BUYER'),
    'sale_ref':         ('SALE REF', 'SALE_REF', 'SALEREF'),
    'vessel':           ('VESSEL',),
    'sub_lt':           ('TONBAG NO', 'SUB_LT', 'SUB LT', 'SUBLT', 'SUBLOT'),
    'weight':           ('Weight(Kg)', 'WEIGHT', 'WEIGHT(KG)'),
    'location':         ('LOCATION', 'LOC'),
    'tonbag_uid':       ('UID', 'TONBAG_UID'),
    'outbound_date':    ('OUTBOUND DATE', 'OUTBOUND_DATE', '출고일'),
    'qty_mt':           ('QTY (MT)', 'QTY_MT', 'QTY(MT)', 'QTY', 'QUANTITY'),
    'eta_busan':        ('ETA BUSAN', 'ETA_BUSAN', 'ETA'),
    'date_in_stock':    ('DATE IN STOCK', 'DATE_IN_STOCK', 'INBOUND_DATE', 'STOCK_DATE'),
    'customs':          ('CUSTOMS',),
    'gw':               ('GW', 'GROSS_WEIGHT', 'GROSS WEIGHT'),
}

_NORM_CACHE: dict = {}


def _normalize_key(s: str) -> str:
    """정규화: 대문자, 공백/하이픈/괄호 → 언더스코어"""
    return re.sub(r'[\s\-()]+', '_', s.strip().upper()).rstrip('_')


def _build_cache() -> None:
    """alias → db_column 역매핑 캐시 빌드"""
    if _NORM_CACHE:
        return
    for db_col, aliases in COLUMN_REGISTRY.items():
        _NORM_CACHE[_normalize_key(db_col)] = db_col
        for alias in aliases:
            _NORM_CACHE[_normalize_key(alias)] = db_col


def normalize_header(header: str) -> str:
    """
    엑셀 헤더 문자열 → DB 컬럼명 변환.
    매핑 실패 시 snake_case 변환 후 반환.
    """
    _build_cache()
    key = _normalize_key(header)
    if key in _NORM_CACHE:
        return _NORM_CACHE[key]
    return re.sub(r'[\s\-]+', '_', header.strip().lower())


def db_to_excel_header(db_column: str) -> str:
    """
    DB 컬럼명 → 엑셀 표준 헤더 변환.
    레지스트리에 없으면 Title Case 반환.
    """
    entry = COLUMN_REGISTRY.get(db_column)
    if entry:
        return entry[0]
    return db_column.replace('_', ' ').title()


def normalize_dataframe_columns(columns: list) -> list:
    """pandas DataFrame 컬럼 리스트를 DB 컬럼명으로 일괄 변환."""
    return [normalize_header(c) for c in columns]
