"""
SQM 재고관리 시스템 - 톤백 용어 통일 호환 레이어 (v5.1.0)
============================================================

배경:
  DB 컬럼명 `sub_lt`는 초기 "Sub LOT"에서 유래.
  실제로는 "톤백 번호(tonbag_no)"와 동일.
  코드 전체에서 sub_lt / tonbag_no / tonbag_uid가 혼용되어 혼란 초래.

이 모듈의 역할:
  1. DB에서 조회한 dict의 'sub_lt' 키를 'tonbag_no'로도 접근 가능하게 함
  2. 새 코드에서는 tonbag_no만 사용하도록 가이드
  3. 기존 코드의 sub_lt 참조도 깨지지 않음 (하위 호환)

사용법:
  from engine_modules.tonbag_compat import normalize_tonbag_keys, normalize_rows

  # 단일 dict
  row = normalize_tonbag_keys({'lot_no': 'LOT001', 'sub_lt': 5, 'weight': 500})
  # → {'lot_no': 'LOT001', 'sub_lt': 5, 'tonbag_no': 5, 'weight': 500}
  
  # 리스트
  rows = normalize_rows(db_result)
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 용어 매핑 정의
# ═══════════════════════════════════════════════════════════

# DB 컬럼명 → 표준 Python 키명
COLUMN_ALIASES = {
    'sub_lt': 'tonbag_no',      # 톤백 번호
    'tonbag_no': 'sub_lt',      # 역방향 (새→구)
}

# 샘플 판단 기준
SAMPLE_WEIGHT_THRESHOLD_MT = 0.001  # 1kg 이하 = 샘플
SAMPLE_SUBLT_VALUE = 0              # sub_lt=0 이면 샘플


def normalize_tonbag_keys(row: Dict) -> Dict:
    """
    DB Row dict에 tonbag_no 키를 추가 (sub_lt와 동일 값).
    기존 sub_lt 키도 유지하여 하위 호환 보장.
    
    Args:
        row: DB에서 조회한 딕셔너리
        
    Returns:
        tonbag_no 키가 추가된 딕셔너리
    """
    if not row or not isinstance(row, dict):
        return row

    result = dict(row)

    # v5.2.0: tonbag_no TEXT 컬럼이 DB에 존재하면 그것을 우선
    if 'tonbag_no' in result and result['tonbag_no'] is not None:
        # DB의 tonbag_no TEXT를 그대로 사용
        pass
    elif 'sub_lt' in result and 'tonbag_no' not in result:
        # 레거시 호환: sub_lt INTEGER → tonbag_no TEXT 변환
        sub_lt_val = result['sub_lt']
        is_sample = bool(int(result.get('is_sample') or 0))
        if is_sample or sub_lt_val == 0:
            result['tonbag_no'] = 'S00'
        elif sub_lt_val is not None:
            result['tonbag_no'] = f"{int(sub_lt_val):03d}"

    # 역방향: tonbag_no → sub_lt 추가 (새 코드에서 tonbag_no만 쓴 경우)
    if 'tonbag_no' in result and 'sub_lt' not in result:
        tn = result['tonbag_no']
        tn_str = str(tn).strip() if tn is not None else ''
        if tn_str and tn_str.upper().startswith('S'):
            result['sub_lt'] = 0
        elif tn_str and tn_str.isdigit():
            result['sub_lt'] = int(tn_str)

    return result


def normalize_rows(rows: List[Dict]) -> List[Dict]:
    """리스트 일괄 변환"""
    if not rows:
        return rows
    return [normalize_tonbag_keys(row) for row in rows]


def is_sample_tonbag(row: Dict) -> bool:
    """
    톤백이 샘플인지 판단 (v5.1.0 통일 기준)
    
    판단 순서:
    1. is_sample 필드가 있으면 최우선
    2. product명에 'sample' 포함
    3. sub_lt(tonbag_no) == 0
    4. qty_mt <= 0.001 (1kg)
    
    Args:
        row: 톤백 딕셔너리
        
    Returns:
        True=샘플, False=일반 톤백
    """
    # 1. DB 필드 is_sample 최우선
    is_sample = row.get('is_sample')
    if is_sample is not None:
        return bool(int(is_sample))

    # 2. 제품명에 sample 포함
    product = str(row.get('product', '')).lower()
    if 'sample' in product:
        return True

    # 3. sub_lt == 0 (DB 규칙)
    tonbag_no = row.get('tonbag_no') or row.get('sub_lt')
    if tonbag_no is not None:
        try:
            if int(tonbag_no) == SAMPLE_SUBLT_VALUE:
                return True
        except (ValueError, TypeError) as _e:
            logger.debug(f"Suppressed: {_e}")

    # 4. 무게 기준 (qty_mt 또는 weight)
    qty_mt = row.get('qty_mt')
    if qty_mt is not None:
        try:
            if float(qty_mt) <= SAMPLE_WEIGHT_THRESHOLD_MT:
                return True
        except (ValueError, TypeError) as _e:
            logger.debug(f"Suppressed: {_e}")

    weight_kg = row.get('weight')
    if weight_kg is not None:
        try:
            if float(weight_kg) <= SAMPLE_WEIGHT_THRESHOLD_MT * 1000:  # 1kg
                return True
        except (ValueError, TypeError) as _e:
            logger.debug(f"Suppressed: {_e}")

    return False


def get_tonbag_display_no(row: Dict) -> str:
    """
    UI 표시용 톤백 번호 문자열 반환
    
    일반: "001", "002", "003" ...
    샘플: "S00""
    
    Args:
        row: 톤백 딕셔너리
    """
    if is_sample_tonbag(row):
        return 'S00'

    tonbag_no = row.get('tonbag_no') or row.get('sub_lt') or row.get('tonbag_no_print', '?')
    s = str(tonbag_no).strip().upper()
    if s in {'S0', 'S00'}:
        return 'S00'
    if s.isdigit():
        return s.zfill(3)
    return s


def get_tonbag_uid(row: Dict) -> str:
    """
    톤백 UID 생성/반환
    
    형식: LOT번호-001 (일반), LOT번호-S00 (샘플)
    """
    # 이미 있으면 반환
    uid = row.get('tonbag_uid')
    if uid:
        return uid

    lot_no = row.get('lot_no', '')
    if is_sample_tonbag(row):
        return f"{lot_no}-S00"

    tonbag_no = row.get('tonbag_no') or row.get('sub_lt', '?')
    s = str(tonbag_no).strip().upper()
    if s in {'S0', 'S00'}:
        return f"{lot_no}-S00"
    if s.isdigit():
        s = s.zfill(3)
    return f"{lot_no}-{s}"


# ═══════════════════════════════════════════════════════════
# Excel 컬럼 매핑 (입출고 파서용)
# ═══════════════════════════════════════════════════════════

# Excel 헤더 → 내부 키 매핑 (sub_lt와 tonbag_no 모두 인식)
EXCEL_COLUMN_ALIASES = {
    'SUB_LT': 'tonbag_no',
    'SUBLT': 'tonbag_no',
    'SUB_LOT': 'tonbag_no',
    'SUBLOT': 'tonbag_no',
    'SUB LT': 'tonbag_no',
    'TONBAG': 'tonbag_no',
    'TONBAG_NO': 'tonbag_no',
    '톤백': 'tonbag_no',
    '톤백번호': 'tonbag_no',
    '톤백#': 'tonbag_no',
}


def resolve_excel_column(header: str) -> Optional[str]:
    """Excel 헤더명 → 표준 키명 변환"""
    normalized = header.strip().upper().replace(' ', '_')
    return EXCEL_COLUMN_ALIASES.get(normalized)


# ═══════════════════════════════════════════════════════════
# 고객명 통일 (v5.1.0)
# ═══════════════════════════════════════════════════════════
#
# DB 현황:
#   inventory.sold_to      — LOT에 기록된 판매처
#   outbound.customer      — 출고 건의 고객
#   inventory_tonbag.picked_to — 톤백이 출고된 대상
#
# 표준: customer (가장 널리 사용, 183회)
# DB 컬럼은 유지, Python에서 customer로 통일 접근

CUSTOMER_ALIASES = ('sold_to', 'customer', 'picked_to', 'buyer', 'consignee', 'client')


def normalize_customer_keys(row: Dict) -> Dict:
    """
    고객명 관련 키를 통일: customer로 접근 가능하게.
    기존 키도 유지하여 하위 호환 보장.
    
    우선순위: customer > sold_to > picked_to > buyer > consignee
    """
    if not row or not isinstance(row, dict):
        return row

    result = dict(row)

    # customer 키가 이미 있으면 그대로 유지
    if 'customer' in result and result['customer']:
        # sold_to, picked_to에도 복제 (역방향 호환)
        if 'sold_to' not in result:
            result['sold_to'] = result['customer']
        if 'picked_to' not in result:
            result['picked_to'] = result['customer']
        return result

    # customer 없으면 다른 키에서 가져오기
    for alias in CUSTOMER_ALIASES:
        val = result.get(alias)
        if val:
            result['customer'] = val
            # 나머지 alias에도 복제
            for other in CUSTOMER_ALIASES:
                if other not in result:
                    result[other] = val
            return result

    return result


# ═══════════════════════════════════════════════════════════
# 톤백 수량 통일 (v5.1.0)
# ═══════════════════════════════════════════════════════════
#
# DB 현황:
#   inventory.mxbg_pallet  — LOT당 톤백 수 (DB 컬럼명)
#   shipment.bag_count     — 선적 건의 톤백 수
#   쿼리 alias: tonbag_count, total_bags, bag_count
#
# 표준: tonbag_count
# DB 컬럼 mxbg_pallet은 유지, Python에서 tonbag_count로 통일

TONBAG_COUNT_ALIASES = ('mxbg_pallet', 'tonbag_count', 'bag_count', 'total_bags', 'sublot_count')


def normalize_tonbag_count_keys(row: Dict) -> Dict:
    """
    톤백 수량 관련 키를 통일: tonbag_count로 접근 가능하게.
    
    v5.6.6: 표준 = mxbg_pallet (DB 컬럼). bag_count/tonbag_count는 하위호환 alias
    """
    if not row or not isinstance(row, dict):
        return row

    result = dict(row)

    if 'tonbag_count' in result and result['tonbag_count'] is not None:
        if 'mxbg_pallet' not in result:
            result['mxbg_pallet'] = result['tonbag_count']
        return result

    for alias in TONBAG_COUNT_ALIASES:
        val = result.get(alias)
        if val is not None:
            result['tonbag_count'] = val
            for other in TONBAG_COUNT_ALIASES:
                if other not in result:
                    result[other] = val
            return result

    return result


# ═══════════════════════════════════════════════════════════
# 통합 normalize (v5.1.0)
# ═══════════════════════════════════════════════════════════

def normalize_all_keys(row: Dict) -> Dict:
    """
    모든 호환 키를 한번에 적용.
    - sub_lt → tonbag_no
    - sold_to/picked_to → customer
    - mxbg_pallet → tonbag_count
    """
    if not row or not isinstance(row, dict):
        return row
    result = normalize_tonbag_keys(row)
    result = normalize_customer_keys(result)
    result = normalize_tonbag_count_keys(result)
    return result


def normalize_all_rows(rows: List[Dict]) -> List[Dict]:
    """리스트 일괄 통합 변환"""
    if not rows:
        return rows
    return [normalize_all_keys(row) for row in rows]
