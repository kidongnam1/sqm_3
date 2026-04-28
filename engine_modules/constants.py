import logging
from typing import Tuple

logger = logging.getLogger(__name__)
# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 — 비즈니스 상수 (v5.6.8)
==============================================

모든 하드코딩 상수를 이 파일에서 관리합니다.
값을 변경하면 시스템 전체에 자동 적용됩니다.

작성자: Ruby (남기동)
"""

# ═══════════════════════════════════════════════════════
# 1. 재고 상태 (inventory.status / inventory_tonbag.status)
# 출고 흐름: AVAILABLE → RESERVED → PICKED → OUTBOUND(출고완료)
# 반품 흐름: OUTBOUND → RETURN(반품입고 대기) → AVAILABLE(복귀 확정)
# ═══════════════════════════════════════════════════════
STATUS_AVAILABLE = 'AVAILABLE'    # 입고 완료, 출고 가능
STATUS_RESERVED = 'RESERVED'      # v5.9.3: Allocation 예약 (톤백 지정 완료, 출고 대기)
STATUS_PICKED = 'PICKED'          # 출고 실행 (피킹 완료)
STATUS_OUTBOUND = 'OUTBOUND'      # v7.2.0: 출고 완료 (신규 write 기준) — SOLD 하위호환 유지
STATUS_SOLD = 'SOLD'              # ⚠️ DEPRECATED: 읽기 전용 하위호환 — 신규 write는 STATUS_OUTBOUND 사용
STATUS_RETURN = 'RETURN'          # v7.2.0: 반품 입고 대기 (location 지정 전 임시 상태)
STATUS_PARTIAL = 'PARTIAL'        # v6.8.7: 부분 출고 (OUTBOUND+AVAILABLE 혼재) — LOT 레벨 전용
STATUS_DEPLETED = 'DEPLETED'      # 전량 출고 완료 — LOT 집계 전용
STATUS_RETURNED = 'RETURNED'      # history 전용: picking_table/sold_table 이력 기록

# 현재 재고 포함 상태 집합 (CURRENT STOCK 계산용)
# CURRENT = AVAILABLE + RESERVED + PICKED + RETURN
STATUSES_CURRENT = (STATUS_AVAILABLE, STATUS_RESERVED, STATUS_PICKED, STATUS_RETURN)

# 출고 완료 상태 집합 (하위호환: OUTBOUND + SOLD 모두 포함)
STATUSES_OUTBOUND_ALL = ('OUTBOUND', 'SOLD', 'SHIPPED', 'CONFIRMED')

# 출고 상태 (outbound.status)
OUTBOUND_PENDING = 'PENDING'      # 출고 대기
OUTBOUND_CONFIRMED = 'CONFIRMED'  # 출고 확정
OUTBOUND_CANCELLED = 'CANCELLED'  # 출고 취소

# 이동 유형 (stock_movement.movement_type)
MOVEMENT_INBOUND = 'INBOUND'
MOVEMENT_OUTBOUND = 'OUTBOUND'
MOVEMENT_RETURN = 'RETURN'
MOVEMENT_ADJUSTMENT = 'ADJUSTMENT'
MOVEMENT_QUICK_OUTBOUND = 'QUICK_OUTBOUND'
MOVEMENT_SOLD = 'SOLD'
MOVEMENT_CANCEL_OUTBOUND = 'CANCEL_OUTBOUND'
MOVEMENT_RESERVED = 'RESERVED'                # v6.12.1: Allocation 예약
MOVEMENT_CANCEL_RESERVE = 'CANCEL_RESERVE'    # v6.12.1: 예약 취소
MOVEMENT_REVERT_PICKED = 'REVERT_PICKED'      # v6.12.1: PICKED→RESERVED 되돌림
MOVEMENT_REVERT_SOLD = 'REVERT_SOLD'          # v6.12.1: SOLD→PICKED 되돌림
MOVEMENT_RELOCATE = 'RELOCATE'                # v7.0.1: 톤백 위치 이동
MOVEMENT_DO_UPDATE = 'DO_UPDATE'              # D/O 후속 연결 UPDATE 이력
MOVEMENT_INVOICE_UPDATE = 'INVOICE_UPDATE'    # Invoice 후속 연결 UPDATE 이력
MOVEMENT_BL_UPDATE = 'BL_UPDATE'              # B/L 후속 연결 UPDATE 이력
MOVEMENT_RETURN_DOC_REVIEW = 'RETURN_DOC_REVIEW'  # 반품 후 문서 연계 점검 필요 이력

# ═══════════════════════════════════════════════════════
# 2. 창고
# ═══════════════════════════════════════════════════════
DEFAULT_WAREHOUSE = '광양'
WAREHOUSE_CODE = 'GY'

# ═══════════════════════════════════════════════════════
# 3. SQM 대원칙 — 무게/톤백
# ═══════════════════════════════════════════════════════
SAMPLE_WEIGHT_KG = 1.0            # 샘플 1개 = 1kg (고정)
TONBAG_WEIGHT_500 = 500           # 500kg 톤백
TONBAG_WEIGHT_1000 = 1000         # 1000kg 톤백
DEFAULT_TONBAG_WEIGHT = 500       # fallback 기본 단가 (DB 조회 실패 시)
DEFAULT_TONBAG_COUNT = 10         # 기본 톤백 수


# ═══════════════════════════════════════════════════════
# v6.12 Addon-G: 톤백 단가 DB 조회 유틸 (500/1000kg 동적 대응)
# ═══════════════════════════════════════════════════════
def get_tonbag_unit_weight(db, lot_no: str) -> float:
    """
    해당 LOT의 실제 톤백 단가(kg)를 DB에서 조회.
    일반 톤백(is_sample=0)의 weight를 조회하여 반환.
    조회 실패 시 DEFAULT_TONBAG_WEIGHT(500) 반환.

    사용처: 출고/배정/반품에서 톤백 개수 추정 시 500 하드코딩 대신 호출.
    """
    if db is None or not lot_no:
        return DEFAULT_TONBAG_WEIGHT
    try:
        row = db.fetchone(
            "SELECT weight FROM inventory_tonbag "
            "WHERE lot_no = ? AND COALESCE(is_sample, 0) = 0 AND weight > 0 "
            "LIMIT 1",
            (lot_no,)
        )
        if row:
            w = float(row['weight'] if isinstance(row, dict) else row[0])
            if w > 0:
                return w
    except Exception as e:
        logger.debug(f"[constants] 톤백 단가 조회 실패 (LOT={lot_no}): {e}")
    return DEFAULT_TONBAG_WEIGHT


def estimate_tonbag_count(weight_kg: float, unit_weight: float = 0) -> int:
    """
    무게(kg)에서 톤백 개수 추정.
    unit_weight가 주어지면 그것으로, 아니면 DEFAULT_TONBAG_WEIGHT로 나눔.
    """
    uw = unit_weight if unit_weight > 0 else DEFAULT_TONBAG_WEIGHT
    return max(1, int(weight_kg / uw))

# ═══════════════════════════════════════════════════════
# 4. 제품 코드
# ═══════════════════════════════════════════════════════
PRODUCT_LITHIUM = 'LITHIUM CARBONATE'
PRODUCT_NICKEL = 'NICKEL SULFATE'

# ═══════════════════════════════════════════════════════
# 5. BL 접두사 (선사 코드)
# ═══════════════════════════════════════════════════════
BL_PREFIXES = ('MAEU', 'MSCU', 'HLCU', 'CMDU', 'EGLV', 'COSU', 'OOLU', 'YMLU')

# ═══════════════════════════════════════════════════════
# 6. 날짜/시간 형식
# ═══════════════════════════════════════════════════════
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# 빠른 출고 제한
QUICK_OUTBOUND_MAX_TONBAGS = 8

# ═══════════════════════════════════════════════════════
# 7. v6.12.1: 반품 사유 표준 코드
# ═══════════════════════════════════════════════════════
RETURN_REASON_CODES = [
    '품질 불량', '수량 오류', '고객 취소', '배송 문제',
    '파손/변질', '규격 불일치', '기타',
]

# 반품 알림 임계치 (N회 이상 반품 시 대시보드 경고)
RETURN_ALERT_THRESHOLD = 3

# v6.12.2: 반품 자동 승인 임계치 (이하 = 자동, 초과 = 관리자 확인 필요)
RETURN_AUTO_APPROVE_MAX_TONBAGS = 5

# ─── 입고 오류 코드 (inbound_mixin.py 참조) ──────────────────────────────
INBOUND_ERROR_INVALID_LOT    = 'LOT_FORMAT_ERROR'
INBOUND_ERROR_INVALID_WEIGHT = 'WEIGHT_INVALID_ERROR'

# ─── allocation_plan.status 전용 상수 (v6.7.1 ①) ─────────────────────
# inventory_tonbag.status(AVAILABLE/RESERVED/PICKED/SOLD)와 완전 분리
ALLOC_STAGED           = 'STAGED'            # 임시 저장 (승인 대기)
ALLOC_RESERVED         = 'RESERVED'          # 예약 확정 (톤백 묶음)
ALLOC_EXECUTED         = 'EXECUTED'          # 출고 실행 완료
ALLOC_APPLIED          = 'APPLIED'           # apply_approved 후 최종 반영
ALLOC_CANCELLED        = 'CANCELLED'         # 취소됨
ALLOC_REJECTED         = 'REJECTED'          # 반려됨

# allocation_plan.workflow_status 전용 상수
ALLOC_WF_PENDING       = 'PENDING_APPROVAL'  # 승인 대기
ALLOC_WF_APPROVED      = 'APPROVED'          # 승인 완료
ALLOC_WF_REJECTED      = 'REJECTED'          # 반려됨
ALLOC_WF_APPLIED       = 'APPLIED'           # 최종 적용 완료

# 단순 참조용: allocation_plan에서 절대 사용 금지 (tonbag 전용 상태)
# AVAILABLE, PICKED, SOLD, SHIPPED → inventory_tonbag.status 전용

# ─── 광양 거래 선사 목록 (v6.7.3) ──────────────────────────────────────
# 황산니켈·탄산리튬 주요 수입 선사 (칠레/중국 → 광양항)
CARRIER_OPTIONS = [
    'UNKNOWN',
    # ─ 글로벌 대형 선사 (광양 직기항) ─
    'MSC',          # Mediterranean Shipping Company — 광양 정기 기항
    'MAERSK',       # A.P. Moller-Maersk — 광양 정기 기항
    'CMA_CGM',      # CMA CGM — 칠레·중국 직항 다수
    'COSCO',        # COSCO Shipping — 중국산 황산니켈 주력
    'EVERGREEN',    # 에버그린 — 중국·동남아
    'ONE',          # Ocean Network Express (K-Line+MOL+NYK)
    # ─ 한국 선사 (광양 근거리) ─
    'HMM',          # HMM(현대상선) — 부산·광양 연결
    'SINOKOR',      # 시노코르(장금상선) — 한중 노선
    'KMTC',         # KMTC(고려해운) — 한중일 노선
    'HEUNG_A',      # 흥아해운 — 한중 근거리
    'DONGJIN',      # 동진상선 — 국내 연안
    'PANCON',       # 팬콘 — 한중 컨테이너
    'OTHER',
]

# ─── 광양 거래 고객사 preset (v6.7.3) ───────────────────────────────────
# 주요 배터리 제조사 (중국·한국)
CUSTOMER_PRESETS = [
    # ─ 중국 배터리 제조사 ─
    'CATL',                     # 寧德時代 — Contemporary Amperex Technology
    'CATL KOREA',               # CATL 한국 법인
    'BYD',                      # 比亞迪 — Build Your Dreams
    'SVOLT ENERGY',             # 蜂巢能源 (SVOLT)
    'CALB',                     # 中創新航 (CALB Co., Ltd.)
    'GOTION HIGH-TECH',         # 國軒高科
    'SUNWODA',                  # 珠海冠宇 / 新旺達
    'LISHEN',                   # 力神電池 (Tianjin Lishen)
    # ─ 한국 배터리 제조사 ─
    'LG ENERGY SOLUTION',       # LG에너지솔루션
    'SAMSUNG SDI',              # 삼성SDI
    'SK ON',                    # SK온
    'POSCO FUTURE M',           # POSCO퓨처엠 (전 POSCO화학)
    'ECOPRO BM',                # 에코프로BM (양극재)
    'L&F',                      # L&F (양극재)
    'COSMO ADVANCED MATERIALS', # 코스모신소재
    # ─ 기타 ─
    'OTHER',
]

# 고객사 정규화 매핑 (문서 표기 → 표준 고객명)
CUSTOMER_NAME_MAP = {
    # CATL 변형
    'CONTEMPORARY AMPEREX': 'CATL',
    'CATL KOREA CO': 'CATL KOREA',
    'CATL KOREA CO.,LTD': 'CATL KOREA',
    # LG 변형
    'LG ENERGY': 'LG ENERGY SOLUTION',
    'LG ES': 'LG ENERGY SOLUTION',
    'LGES': 'LG ENERGY SOLUTION',
    # 삼성 변형
    'SDI': 'SAMSUNG SDI',
    'SAMSUNG SDI CO.,LTD': 'SAMSUNG SDI',
    # SK 변형
    'SK INNOVATION': 'SK ON',
    'SK BATTERY': 'SK ON',
    # POSCO 변형
    'POSCO CHEMICAL': 'POSCO FUTURE M',
    'POSCO CHEM': 'POSCO FUTURE M',
    'POSCO FUTURE M CO.,LTD': 'POSCO FUTURE M',
    # EcoPro 변형
    'ECOPRO': 'ECOPRO BM',
    # CATL 소문자/공백 변형
    'CATL KOREA CO., LTD': 'CATL KOREA',
    'CATL KOREA CO., LTD.': 'CATL KOREA',
    'CONTEMPORARY AMPEREX TECHNOLOGY': 'CATL',
    # BYD 변형
    'BYD CO.,LTD': 'BYD',
    'BYD CO., LTD': 'BYD',
    # SVOLT 변형
    'SVOLT': 'SVOLT ENERGY',
    # L&F 변형
    'L AND F': 'L&F',
    'L & F': 'L&F',
}


def normalize_customer(raw: str) -> str:
    """[E] v6.8.3: 고객사명 정규화.
    CUSTOMER_NAME_MAP 기반 표준명 변환.
    매핑 없으면 UPPER().strip() 반환.
    """
    if not raw:
        return ''
    _key = str(raw).strip().upper()
    # 1. 정확히 일치
    if _key in CUSTOMER_NAME_MAP:
        return CUSTOMER_NAME_MAP[_key]
    # 2. 포함 검색 (부분 일치)
    for pattern, standard in CUSTOMER_NAME_MAP.items():
        if pattern in _key:
            return standard
    # 3. PRESETS에 있으면 그대로
    if _key in [p.upper() for p in CUSTOMER_PRESETS]:
        return _key
    return _key


# ── v8.6.4: validate_location_format GUI→Engine 이동 ──────────────────────
def validate_location_format(location: str) -> Tuple[bool, str]:
    """
    위치 형식 검증 (3파트 또는 4파트)
    
    허용 형식:
      - 3파트: A-01-01 (구역-열-층)
      - 4파트: A-01-01-10 (구역-열-층-칸) — 로케이션 약식 기본
    
    Args:
        location: 위치 문자열 (예: A-01-01 또는 A-01-01-10)
        
    Returns:
        (유효여부, 메시지)
    """
    if not location or not isinstance(location, str):
        return False, "위치가 비어있습니다"

    location = location.strip()

    if len(location) > 50:
        return False, "위치가 너무 깁니다 (최대 50자)"

    parts = location.split('-')
    if len(parts) not in (3, 4):
        return False, "형식이 올바르지 않습니다 (예: A-01-01 또는 A-01-01-10)"

    zone, row, level = parts[0], parts[1], parts[2]

    # 구역: 영문 1자
    if not zone.isalpha() or len(zone) != 1:
        return False, "구역은 영문 1자여야 합니다 (예: A)"
    # 열: 숫자
    if not row.isdigit():
        return False, "열은 숫자여야 합니다 (예: 01)"
    # 층: 숫자
    if not level.isdigit():
        return False, "층은 숫자여야 합니다 (예: 01)"
    # 4파트 시 칸(베이): 숫자
    if len(parts) == 4:
        if not parts[3].isdigit():
            return False, "칸(4번째)은 숫자여야 합니다 (예: A-01-01-10)"

    return True, "OK"
