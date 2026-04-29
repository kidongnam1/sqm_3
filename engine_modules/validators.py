# ============================================================
# SQM Validators 원칙 (v8.0.5 확정 — 2026-03-16)
# ------------------------------------------------------------
# Validators must detect and report only; they must not
# directly mutate inventory summary or status.
# Auto-fix (current_weight=0, status=DEPLETED) must be
# followed by central recalc via P2_VALIDATORS_DEPLETED.
#
# 검증식 기준: AVAILABLE + RESERVED (sample 제외)
# ============================================================

"""
SQM 재고관리 시스템 - 데이터 검증 모듈
v2.9.30: 비정상 테스트 발견 취약점 수정

발견된 취약점:
1. 중복 LOT NO 허용 → 차단 필요
2. 음수 중량 저장 → 검증 필요
3. 빈 LOT 번호 허용 → 차단 필요
4. DEPLETED LOT 재출고 → 상태 검증 필요
5. 트랜잭션 롤백 실패 → All-or-Nothing 강화
6. 음수 재고 발생 → CHECK 제약 필요
7. 상태 불일치 → 정합성 검증 필요
"""

from engine_modules.constants import STATUS_AVAILABLE, STATUS_DEPLETED
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from core.types import norm_bl_no_for_query  # v9.0
if TYPE_CHECKING:
    from engine_modules.db_core import SQMDatabase

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    @classmethod
    def success(cls, warnings: List[str] = None) -> 'ValidationResult':
        """성공 ValidationResult 생성"""
        return cls(is_valid=True, errors=[], warnings=warnings or [])

    @classmethod
    def failure(cls, errors: List[str], warnings: List[str] = None) -> 'ValidationResult':
        """실패 ValidationResult 생성"""
        return cls(is_valid=False, errors=errors, warnings=warnings or [])


class InventoryValidator:
    """재고 데이터 검증기"""

    # 검증 상수
    MIN_WEIGHT_KG = 0.1          # 최소 중량 (0.1kg = 100g)
    MAX_WEIGHT_KG = 100000.0     # 최대 중량 (100톤)
    LOT_NO_PATTERN = r'^112\d{7}$'  # LOT 번호 형식: 112 + 7자리 숫자
    LOT_NO_MIN_LENGTH = 10
    LOT_NO_MAX_LENGTH = 20

    def __init__(self, db: Optional['SQMDatabase'] = None) -> None:
        """InboundValidator 초기화"""
        self.db = db

    # =========================================================================
    # LOT 번호 검증
    # =========================================================================

# DEPRECATED: duplicate of validate_lot_no() defined above — v8.6.3 removed
    # REMOVED v8.6.4: duplicate validate_lot_no() — kept first definition

    def validate_lot_no_unique(self, lot_no: str) -> ValidationResult:
        """
        LOT 번호 중복 검증 (DB 조회 필요)
        """
        if not self.db:
            return ValidationResult.success([" DB 연결 없음 - 중복 체크 스킵"])

        existing = self.db.fetchone(
            "SELECT id, lot_no, status FROM inventory WHERE lot_no = ?",
            (lot_no,)
        )

        if existing:
            return ValidationResult.failure(
                [f"이미 등록된 LOT 번호입니다: {lot_no} (상태: {existing['status']})"]
            )

        return ValidationResult.success()

    # =========================================================================
    # 중량 검증
    # =========================================================================
# DEPRECATED: duplicate of validate_weight() defined above — v8.6.3 removed

    # REMOVED v8.6.4: duplicate validate_weight() — kept first definition

    # =========================================================================
    # 출고 검증
    # =========================================================================

    def validate_outbound(self, lot_no: str, outbound_qty: float) -> ValidationResult:
        """
        출고 유효성 검증
        
        검증 항목:
        1. LOT 존재 여부
        2. LOT 상태 (AVAILABLE/PARTIAL만 출고 가능)
        3. 재고량 충분 여부
        """
        errors = []
        warnings = []

        if not self.db:
            return ValidationResult.failure(["DB 연결 없음"])

        # 1. LOT 조회
        lot = self.db.fetchone(
            "SELECT lot_no, current_weight, status FROM inventory WHERE lot_no = ?",
            (lot_no,)
        )

        if not lot:
            errors.append(f"존재하지 않는 LOT입니다: {lot_no}")
            return ValidationResult.failure(errors)

        # v6.8.9: 출고 가능 판정 — LOT.status 대신 TONBAG 집계 기준
        # LOT.status는 보조 표시용이므로 신뢰하지 않음
        try:
            tb_counts = self.db.fetchall(
                "SELECT status, COUNT(*) AS cnt FROM inventory_tonbag "
                "WHERE lot_no = ? AND COALESCE(is_sample,0)=0 GROUP BY status",
                (lot_no,)
            )
            _tb_map = {str(r.get('status','')).upper(): int(r.get('cnt',0)) for r in (tb_counts or [])}
        except Exception:
            _tb_map = {}

        _avail_cnt = _tb_map.get('AVAILABLE', 0)
        _total_cnt = sum(_tb_map.values())

        # 2. 상태 체크 — TONBAG 기준
        if _total_cnt > 0 and _avail_cnt == 0:
            # 전량 SOLD/PICKED/RESERVED — 출고 가능 톤백 없음
            errors.append(f"출고 가능한 톤백이 없습니다: {lot_no} (AVAILABLE 0개)")
            return ValidationResult.failure(errors)

        # DEPLETED 보조 체크 (LOT.status가 DEPLETED이고 TONBAG도 없으면 차단)
        if lot['status'] == STATUS_DEPLETED and _avail_cnt == 0:
            errors.append(f"이미 출고 완료된 LOT입니다: {lot_no}")
            return ValidationResult.failure(errors)

        # 3. 재고량 체크
        current = lot['current_weight'] or 0
        if outbound_qty > current:
            errors.append(
                f"재고 부족: {lot_no} - 요청 {outbound_qty}kg, 보유 {current}kg"
            )
            return ValidationResult.failure(errors)

        # 4. 전량 출고 경고
        if outbound_qty == current:
            warnings.append(f"전량 출고됩니다: {lot_no} ({current}kg)")

        return ValidationResult.success(warnings)

    # =========================================================================
    # 입고 데이터 통합 검증
    # =========================================================================

    def validate_inbound_data(self, packing_data) -> ValidationResult:
        """
        입고 데이터 통합 검증
        
        검증 항목:
        1. 필수 필드 존재 여부
        2. SAP NO 유효성
        3. 각 LOT 데이터 검증
        """
        errors = []
        warnings = []

        # 1. 필수 필드 체크
        if not packing_data:
            return ValidationResult.failure(["입고 데이터가 없습니다"])

        # 딕셔너리와 객체 모두 지원
        if isinstance(packing_data, dict):
            lots = packing_data.get('lots', [])
            sap_no = packing_data.get('sap_no')
        else:
            lots = getattr(packing_data, 'lots', [])
            sap_no = getattr(packing_data, 'sap_no', None)

        if not lots:
            return ValidationResult.failure(["LOT 데이터가 없습니다"])

        # 2. SAP NO 체크
        if not sap_no or not str(sap_no).strip():
            warnings.append("SAP NO가 없습니다 (자동 생성됩니다)")
        elif self.db:
            existing = self.db.fetchone("SELECT id FROM shipment WHERE sap_no = ?", (sap_no,))
            if existing:
                errors.append(f"이미 등록된 SAP NO입니다: {sap_no}")
                return ValidationResult.failure(errors, warnings)

        # 3. 각 LOT 검증
        lot_nos_in_batch = set()  # 배치 내 중복 체크용

        for idx, lot in enumerate(lots):
            lot_no = lot.get('lot_no', '')

            # 3.1 LOT 번호 검증
            lot_result = self.validate_lot_no(lot_no)
            if not lot_result.is_valid:
                errors.extend([f"LOT #{idx+1}: {e}" for e in lot_result.errors])
                continue
            warnings.extend([f"LOT #{idx+1}: {w}" for w in lot_result.warnings])

            # 3.2 배치 내 중복 체크
            if lot_no in lot_nos_in_batch:
                errors.append(f"LOT #{idx+1}: 배치 내 중복 LOT 번호: {lot_no}")
                continue
            lot_nos_in_batch.add(lot_no)

            # 3.3 DB 중복 체크
            if self.db:
                unique_result = self.validate_lot_no_unique(lot_no)
                if not unique_result.is_valid:
                    errors.extend([f"LOT #{idx+1}: {e}" for e in unique_result.errors])

            # 3.4 중량 검증
            net_weight = lot.get('net_weight', 0)
            weight_result = self.validate_weight(net_weight, f"LOT #{idx+1} 순중량")
            if not weight_result.is_valid:
                errors.extend(weight_result.errors)
            warnings.extend(weight_result.warnings)

        # 결과 반환
        if errors:
            return ValidationResult.failure(errors, warnings)

        return ValidationResult.success(warnings)

    # =========================================================================
    # 데이터 정합성 검증
    # =========================================================================

    def check_data_integrity(self) -> ValidationResult:
        """
        전체 데이터 정합성 검증
        
        검증 항목:
        1. 음수 재고 존재 여부
        2. 상태-재고 불일치
        3. 필수 필드 NULL 여부
        4. inventory↔tonbag 크로스 검증 (v3.8.4)
           - inventory.current_weight vs sum(inventory_tonbag.weight) where status IN ('AVAILABLE','SAMPLE')
           - 불일치 시: 톤백 일부가 RESERVED/PICKED/SOLD이거나, 톤백 행 누락·수정 불일치 가능
        5. MXBG ↔ 톤백 수량 정합성
        """
        if not self.db:
            return ValidationResult.failure(["DB 연결 없음"])

        errors = []
        warnings = []

        # 1. 음수 재고 체크
        negative = self.db.fetchone(
            "SELECT COUNT(*) as cnt, MIN(current_weight) as min_wt FROM inventory WHERE current_weight < 0"
        )
        if negative and negative['cnt'] > 0:
            errors.append(f"음수 재고 발견: {negative['cnt']}건 (최소값: {negative['min_wt']}kg)")

        # 2. 상태-재고 불일치 체크
        depleted_with_stock = self.db.fetchone("""
            SELECT COUNT(*) as cnt FROM inventory 
            WHERE status = 'DEPLETED' AND current_weight > 0
        """)
        if depleted_with_stock and depleted_with_stock['cnt'] > 0:
            errors.append(f"상태 불일치: DEPLETED인데 재고 있음 {depleted_with_stock['cnt']}건")

        available_no_stock = self.db.fetchone("""
            SELECT COUNT(*) as cnt FROM inventory 
            WHERE status = 'AVAILABLE' AND current_weight <= 0
        """)
        if available_no_stock and available_no_stock['cnt'] > 0:
            warnings.append(f"상태 불일치: AVAILABLE인데 재고 없음 {available_no_stock['cnt']}건")

        # 3. 필수 필드 NULL 체크
        null_fields = self.db.fetchone("""
            SELECT COUNT(*) as cnt FROM inventory 
            WHERE lot_no IS NULL OR lot_no = '' 
               OR product IS NULL OR product = ''
        """)
        if null_fields and null_fields['cnt'] > 0:
            errors.append(f"필수 필드 누락: {null_fields['cnt']}건")

        # 4. v3.8.4: inventory↔tonbag 크로스 검증 (중량)
        # 비교: inventory.current_weight vs 톤백 weight 합계.
        # AVAILABLE, RESERVED, PICKED 포함 (출고 확정 SOLD 전까지는 재고로 봄).
        # v8.6.4-fix: SAMPLE 제외 — 샘플 톤백(1kg)은 inventory.current_weight에 미포함.
        try:
            cross_check = self.db.fetchall("""
                SELECT
                    i.lot_no,
                    i.current_weight AS inv_weight,
                    COALESCE(t.tonbag_total_weight, 0) AS tonbag_weight
                FROM inventory i
                LEFT JOIN (
                    SELECT lot_no, SUM(weight) AS tonbag_total_weight
                    FROM inventory_tonbag
                    WHERE status IN ('AVAILABLE','RESERVED','PICKED')
                      AND COALESCE(is_sample, 0) = 0
                    GROUP BY lot_no
                ) t ON i.lot_no = t.lot_no
                WHERE i.current_weight > 0
                  AND ABS(i.current_weight - COALESCE(t.tonbag_total_weight, 0)) > 0.01
                LIMIT 50
            """)
            if cross_check:
                for row in cross_check[:5]:
                    lot = row['lot_no']
                    inv_w = row['inv_weight']
                    ton_w = row['tonbag_weight']
                    diff = abs(inv_w - ton_w)
                    # 오차 과대(톤백 합계 거의 없는데 재고는 큰 경우 등) → 데이터 오류 가능성
                    if ton_w < 100 and inv_w > 1000:
                        errors.append(
                            f"심각한 크로스 불일치: {lot} (재고 Balance={inv_w:.0f}kg, 톤백테이블 합계={ton_w:.0f}kg). "
                            "재고 화면은 정상이어도, 톤백 테이블(inventory_tonbag)의 weight 값이 1 등으로 잘못 저장된 경우입니다. "
                            "500kg 톤백이면 weight=500 이어야 합니다. 톤백 탭 또는 DB에서 해당 LOT의 톤백 행을 확인하세요."
                        )
                    elif diff > 1000:
                        errors.append(
                            f"크로스 불일치(오차 과대): {lot} (inventory={inv_w:.0f}kg, tonbag합계={ton_w:.0f}kg). "
                            "톤백 weight/행 또는 상태 확인 필요."
                        )
                    elif diff <= 1.0 and inv_w == ton_w + 1 and ton_w > 0:
                        # v8.7.1 [SAFETY-HOLD]: 자동보정 비활성화 (데이터 손실 방지)
                        # ─────────────────────────────────────────────────────
                        # 과거(v8.6.4): inventory.current_weight=5001, 본품톤백합=5000
                        # → "샘플 1kg 포함 오류"로 간주하고 inventory를 5000으로 강제 수정.
                        # 조사(2026-04-20): 이 규칙이 적용된 5개 LOT 전부
                        # 실제로는 is_sample=1 샘플 톤백(1kg, AVAILABLE)이 존재함.
                        # → 5001은 "본품 5000 + 샘플 1"의 올바른 총량일 가능성 높음.
                        # → 자동 수정은 샘플 1kg을 회계에서 사라지게 함 (실제 유실 확인).
                        # ─────────────────────────────────────────────────────
                        # 안전 조치:
                        #  1) UPDATE 비활성화 — 의심 상태만 경고
                        #  2) audit_log 기록 — 사후 추적 가능
                        #  3) 사용자 결정 대기 — 재활성화 또는 영구 삭제 판단
                        try:
                            # 샘플 존재 여부 확인 (진단 힌트)
                            _sample_check = self.db.fetchone(
                                "SELECT COUNT(*) AS cnt, COALESCE(SUM(weight),0) AS wsum "
                                "FROM inventory_tonbag "
                                "WHERE lot_no = ? AND COALESCE(is_sample,0)=1 "
                                "  AND status IN ('AVAILABLE','RESERVED','PICKED')",
                                (lot,)
                            )
                            _s_cnt = (_sample_check or {}).get('cnt', 0) if isinstance(_sample_check, dict) else (_sample_check[0] if _sample_check else 0)
                            _s_sum = (_sample_check or {}).get('wsum', 0) if isinstance(_sample_check, dict) else (_sample_check[1] if _sample_check else 0)

                            # audit_log 기록 (자동 수정을 '하지 않았음'을 감사 로그에 남김)
                            try:
                                self.db.execute(
                                    "INSERT INTO audit_log (event_type, event_data, user_note, created_by) "
                                    "VALUES (?, ?, ?, ?)",
                                    (
                                        'VALIDATOR_SAFETY_HOLD',
                                        f'{{"lot":"{lot}","inv_w":{inv_w},"ton_w_nosample":{ton_w},'
                                        f'"sample_cnt":{_s_cnt},"sample_sum":{_s_sum},'
                                        f'"rule":"v8.6.4_auto_correct","action":"HELD_NOT_APPLIED"}}',
                                        f'자동보정 보류: {lot} inv={inv_w}kg ton(-sample)={ton_w}kg sample={_s_sum}kg — 수정 안 함',
                                        'system_v8.7.1',
                                    )
                                )
                            except Exception as _ae:
                                logger.warning("[정합성][SAFETY-HOLD] audit_log 기록 실패: %s", _ae)

                            # warning 격상 (info → warning)
                            logger.warning(
                                "[정합성][SAFETY-HOLD] %s: inv=%skg ton(-sample)=%skg sample(cnt=%s,sum=%skg) "
                                "— 자동보정 비활성화. 사용자 확인 필요.",
                                lot, inv_w, ton_w, _s_cnt, _s_sum,
                            )
                            warnings.append(
                                f"크로스 불일치 [보류]: {lot} (inv={inv_w:.0f}kg, 본품톤백={ton_w:.0f}kg, "
                                f"샘플톤백={_s_sum:.0f}kg/{_s_cnt}개). "
                                "자동보정 비활성화 — 실제 5kg 유실 사례 확인 후 사용자 결정 대기."
                            )
                        except Exception as fix_e:
                            logger.warning("[정합성][SAFETY-HOLD] %s 진단 실패: %s", lot, fix_e)
                            warnings.append(
                                f"크로스 불일치: {lot} (inventory={inv_w:.0f}kg, tonbag합계={ton_w:.0f}kg). "
                                "원인: 샘플 포함 여부 확인 필요 — 자동보정 보류 중."
                            )
                    else:
                        warnings.append(
                            f"크로스 불일치: {lot} (inventory={inv_w:.0f}kg, tonbag합계={ton_w:.0f}kg). "
                            "원인: inventory 현재중량과 톤백(AVAILABLE+RESERVED+PICKED, 샘플 제외) 합계 불일치."
                        )
                if len(cross_check) > 5:
                    more = len(cross_check) - 5
                    severe = sum(1 for r in cross_check[5:] if (r['tonbag_weight'] or 0) < 100 and (r['inv_weight'] or 0) > 1000)
                    if severe > 0:
                        errors.append(f"... 외 심각한 불일치 {severe}건 포함 총 {more}건 추가")
                    else:
                        warnings.append(f"... 외 {more}건 추가 불일치")
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"크로스 검증 스킵: {e}")

        # 5. v3.8.7: MXBG ↔ 톤백 수량 정합성 검증 — 샘플 톤백 제외
        try:
            mxbg_check = self.db.fetchall("""
                SELECT 
                    i.lot_no,
                    i.mxbg_pallet AS mxbg,
                    COALESCE(t.tonbag_count, 0) AS actual_count
                FROM inventory i
                LEFT JOIN (
                    SELECT lot_no, COUNT(*) AS tonbag_count
                    FROM inventory_tonbag 
                    WHERE COALESCE(is_sample, 0) = 0
                    GROUP BY lot_no
                ) t ON i.lot_no = t.lot_no
                WHERE i.mxbg_pallet > 0
                  AND COALESCE(t.tonbag_count, 0) > 0
                  AND i.mxbg_pallet != COALESCE(t.tonbag_count, 0)
            """)
            if mxbg_check:
                for row in mxbg_check[:5]:
                    lot = row['lot_no']
                    mxbg = row['mxbg']
                    actual = row['actual_count']
                    errors.append(
                        f"MXBG↔톤백 수량 불일치: {lot} (MXBG={mxbg}, 실제톤백={actual})"
                    )
                if len(mxbg_check) > 5:
                    errors.append(f"... 외 {len(mxbg_check) - 5}건 추가 MXBG 불일치")
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"MXBG 검증 스킵: {e}")

        # 6. v7.0.1: 위치 미지정 톤백 경고 (AVAILABLE 상태만)
        try:
            no_location = self.db.fetchone("""
                SELECT COUNT(*) as cnt FROM inventory_tonbag
                WHERE status = 'AVAILABLE'
                  AND COALESCE(is_sample, 0) = 0
                  AND (location IS NULL OR location = '')
            """)
            if no_location and no_location['cnt'] > 0:
                warnings.append(
                    f"위치 미지정 톤백: {no_location['cnt']}개 (AVAILABLE 상태, 샘플 제외). "
                    "톤백 탭 → 위치 업로드로 매핑 가능."
                )
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"위치 미지정 검증 스킵: {e}")

        if errors:
            return ValidationResult.failure(errors, warnings)

        return ValidationResult.success(warnings)

    # =========================================================================
    # 데이터 복구
    # =========================================================================

    def fix_data_integrity(self, dry_run: bool = True) -> Dict:
        """
        데이터 정합성 문제 자동 복구
        
        Args:
            dry_run: True면 실제 수정 없이 시뮬레이션만
            
        Returns:
            복구 결과 딕셔너리
        """
        if not self.db:
            return {'success': False, 'error': 'DB 연결 없음'}

        result = {
            'success': True,
            'dry_run': dry_run,
            'fixes': [],
            'errors': []
        }

        try:
            # 1. 음수 재고 → 0으로 수정
            negative_lots = self.db.fetchall(
                "SELECT lot_no, current_weight FROM inventory WHERE current_weight < 0"
            )
            if negative_lots:
                # v8.2.0 N+1 최적화: 개별 UPDATE → 배치 UPDATE
                if not dry_run:
                    neg_lot_nos = [
                        (lot['lot_no'] if isinstance(lot, dict) else lot[0])
                        for lot in negative_lots
                    ]
                    _ph = ','.join('?' * len(neg_lot_nos))
                    self.db.execute(
                        f"UPDATE inventory SET current_weight = 0, status = 'DEPLETED' "
                        f"WHERE lot_no IN ({_ph})",
                        tuple(neg_lot_nos)
                    )
                    for lot in negative_lots:
                        lot_no = lot['lot_no'] if isinstance(lot, dict) else lot[0]
                        if hasattr(self, '_recalc_current_weight'):
                            self._recalc_current_weight(lot_no, reason='P2_VALIDATORS_DEPLETED')
                for lot in negative_lots:
                    lot_no = lot['lot_no'] if isinstance(lot, dict) else lot[0]
                    cur_w  = lot['current_weight'] if isinstance(lot, dict) else lot[1]
                    result['fixes'].append(f"음수 재고 수정: {lot_no} ({cur_w}kg → 0)")

            # 2. v6.8.9: DEPLETED인데 AVAILABLE 톤백 있으면 → TONBAG 기준으로 복구
            depleted_with_stock = self.db.fetchall("""
                SELECT inv.lot_no, inv.current_weight, inv.net_weight,
                       (SELECT COUNT(*) FROM inventory_tonbag tb
                        WHERE tb.lot_no=inv.lot_no AND tb.status='AVAILABLE'
                        AND COALESCE(tb.is_sample,0)=0) AS avail_cnt,
                       (SELECT COUNT(*) FROM inventory_tonbag tb
                        WHERE tb.lot_no=inv.lot_no AND tb.status IN ('SOLD','OUTBOUND')
                        AND COALESCE(tb.is_sample,0)=0) AS sold_cnt
                FROM inventory inv
                WHERE inv.status = 'DEPLETED'
            """)
            for lot in depleted_with_stock:
                _ac = int(lot.get('avail_cnt') or 0)
                _sc = int(lot.get('sold_cnt') or 0)
                if _ac == 0:
                    continue  # AVAILABLE 없음 → DEPLETED 유지
                # AVAILABLE 있음 → PARTIAL or AVAILABLE
                new_status = 'PARTIAL' if _sc > 0 else STATUS_AVAILABLE
                if not dry_run:
                    self.db.execute(
                        "UPDATE inventory SET status = ? WHERE lot_no = ?",
                        (new_status, lot['lot_no'])
                    )
                result['fixes'].append(f"상태 수정: {lot['lot_no']} DEPLETED → {new_status}")

            # 3. v6.8.9: AVAILABLE/PARTIAL인데 TONBAG 전량 SOLD → DEPLETED
            available_no_stock = self.db.fetchall("""
                SELECT inv.lot_no,
                       (SELECT COUNT(*) FROM inventory_tonbag tb
                        WHERE tb.lot_no=inv.lot_no AND tb.status='AVAILABLE'
                        AND COALESCE(tb.is_sample,0)=0) AS avail_cnt,
                       (SELECT COUNT(*) FROM inventory_tonbag tb
                        WHERE tb.lot_no=inv.lot_no
                        AND COALESCE(tb.is_sample,0)=0) AS total_cnt
                FROM inventory inv
                WHERE inv.status IN ('AVAILABLE','PARTIAL')
            """)
            for lot in available_no_stock:
                _ac    = int(lot.get('avail_cnt') or 0)
                _total = int(lot.get('total_cnt') or 0)
                if _total > 0 and _ac == 0:
                    if not dry_run:
                        self.db.execute(
                            "UPDATE inventory SET status = 'DEPLETED' WHERE lot_no = ?",
                            (lot['lot_no'],)
                        )
                    result['fixes'].append(f"상태 수정: {lot['lot_no']} → DEPLETED (AVAILABLE 톤백 0개)")

            # 4. v3.8.7: Free Time 일괄 계산 (arrival_date 있고 free_time이 0인 LOT)
            # D/O별 Free Time이 동일하므로, 같은 BL의 다른 LOT에서 free_time 보완
            try:
                missing_ft = self.db.fetchall("""
                    SELECT lot_no, arrival_date, bl_no
                    FROM inventory 
                    WHERE arrival_date IS NOT NULL 
                      AND arrival_date != ''
                      AND (free_time IS NULL OR free_time = 0)
                """)
                # v8.3.1 [Phase A6]: N+1 → 배치 pre-fetch
                _bl_set = set()
                for lot in missing_ft:
                    bl = lot.get('bl_no', '') or ''
                    if bl:
                        _bl_set.add(norm_bl_no_for_query(bl) or bl)
                _bl_ft_map = {}
                if _bl_set:
                    _bl_list = list(_bl_set)
                    _pl = ','.join('?' * len(_bl_list))
                    _ft_rows = self.db.fetchall(
                        f"SELECT bl_no, free_time FROM inventory WHERE bl_no IN ({_pl}) AND free_time > 0",
                        tuple(_bl_list)
                    ) or []
                    for _r in _ft_rows:
                        _bn = _r['bl_no'] if isinstance(_r, dict) else _r[0]
                        _ft = _r['free_time'] if isinstance(_r, dict) else _r[1]
                        if _bn and _ft:
                            _bl_ft_map[_bn] = _ft
                for lot in missing_ft:
                    bl = lot.get('bl_no', '') or ''
                    bl_key = norm_bl_no_for_query(bl) or bl
                    ft_val = _bl_ft_map.get(bl_key, 0)
                    if ft_val > 0:
                        if not dry_run:
                            self.db.execute(
                                "UPDATE inventory SET free_time = ? WHERE lot_no = ?",
                                (ft_val, lot['lot_no'])
                            )
                        result['fixes'].append(
                            f"Free Time 보완: {lot['lot_no']} → {ft_val}일 (BL {bl}에서 복사)"
                        )
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                logger.debug(f"Free Time 일괄 계산 스킵: {e}")

            # 5. v3.8.7: salar_invoice_no 일괄 보완 (같은 SAP NO에서 복사)
            try:
                missing_inv = self.db.fetchall("""
                    SELECT lot_no, sap_no, bl_no
                    FROM inventory 
                    WHERE (salar_invoice_no IS NULL OR salar_invoice_no = '')
                      AND sap_no IS NOT NULL AND sap_no != ''
                """)
                # v8.3.1 [Phase A6]: SAP별 invoice_no 배치 pre-fetch
                _sap_set = {lot.get('sap_no','') for lot in missing_inv if lot.get('sap_no')}
                _sap_inv_map = {}
                if _sap_set:
                    _sap_list = list(_sap_set)
                    _pl2 = ','.join('?' * len(_sap_list))
                    _inv_rows = self.db.fetchall(
                        f"SELECT sap_no, salar_invoice_no FROM inventory "
                        f"WHERE sap_no IN ({_pl2}) AND salar_invoice_no != '' LIMIT {len(_sap_list)*2}",
                        tuple(_sap_list)
                    ) or []
                    for _r in _inv_rows:
                        _sn = _r['sap_no'] if isinstance(_r, dict) else _r[0]
                        _iv = _r['salar_invoice_no'] if isinstance(_r, dict) else _r[1]
                        if _sn and _iv and _sn not in _sap_inv_map:
                            _sap_inv_map[_sn] = _iv
                for lot in missing_inv:
                    sap = lot.get('sap_no', '') or ''
                    inv_val = _sap_inv_map.get(sap, '')
                    if inv_val:
                        if not dry_run:
                            self.db.execute(
                                "UPDATE inventory SET salar_invoice_no = ? WHERE lot_no = ?",
                                (inv_val, lot['lot_no'])
                            )
                        result['fixes'].append(
                                f"Invoice No 보완: {lot['lot_no']} → {ref['salar_invoice_no']} (SAP {sap}에서 복사)"
                            )
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                logger.debug(f"Invoice No 일괄 보완 스킵: {e}")

            if not dry_run:
                self.db.commit()

            result['total_fixes'] = len(result['fixes'])

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            result['success'] = False
            result['errors'].append(str(e))
            if not dry_run:
                self.db.rollback()

        return result

    # ═══════════════════════════════════════════════════════
    # v3.8.4 A6: 재고 스냅샷
    # ═══════════════════════════════════════════════════════

    def save_daily_snapshot(self) -> Dict:
        """일별 재고 스냅샷 저장"""
        import json
        from datetime import date as _date

        today = _date.today().isoformat()

        try:
            existing = self.db.fetchone(
                "SELECT id FROM inventory_snapshot WHERE snapshot_date = ?", (today,))

            stats = self.db.fetchone("""
                SELECT 
                    COUNT(*) AS total_lots,
                    COALESCE(SUM(current_weight), 0) AS total_weight,
                    COALESCE(SUM(CASE WHEN status != 'DEPLETED' THEN current_weight ELSE 0 END), 0) AS avail_weight,
                    COALESCE(SUM(picked_weight), 0) AS picked_weight
                FROM inventory
            """)

            tonbag_count = self.db.fetchone(
                "SELECT COUNT(*) AS cnt FROM inventory_tonbag WHERE COALESCE(is_sample,0)=0")

            product_rows = self.db.fetchall("""
                SELECT product, COUNT(*) AS lots, SUM(current_weight) AS weight
                FROM inventory GROUP BY product
            """)
            product_summary = json.dumps(
                [{'product': r['product'], 'lots': r['lots'],
                  'weight_kg': r['weight']} for r in product_rows],
                ensure_ascii=False)

            total_lots = stats['total_lots'] if stats else 0
            total_weight = stats['total_weight'] if stats else 0
            avail_weight = stats['avail_weight'] if stats else 0
            picked_weight = stats['picked_weight'] if stats else 0
            total_tonbags = tonbag_count['cnt'] if tonbag_count else 0

            if existing:
                self.db.execute("""
                    UPDATE inventory_snapshot SET
                        total_lots = ?, total_tonbags = ?,
                        total_weight_kg = ?, available_weight_kg = ?,
                        picked_weight_kg = ?, product_summary = ?,
                        created_at = CURRENT_TIMESTAMP
                    WHERE snapshot_date = ?
                """, (total_lots, total_tonbags, total_weight,
                      avail_weight, picked_weight, product_summary, today))
            else:
                self.db.execute("""
                    INSERT INTO inventory_snapshot 
                    (snapshot_date, total_lots, total_tonbags, total_weight_kg,
                     available_weight_kg, picked_weight_kg, product_summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (today, total_lots, total_tonbags, total_weight,
                      avail_weight, picked_weight, product_summary))

            self.db.commit()

            return {
                'success': True, 'date': today,
                'total_lots': total_lots, 'total_weight_kg': total_weight,
            }
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.error(f"스냅샷 저장 오류: {e}")
            return {'success': False, 'error': str(e)}


class InboundValidator(InventoryValidator):
    """입고 전용 검증기 (All-or-Nothing 지원)"""

    def validate_all_or_nothing(self, packing_data) -> ValidationResult:
        """
        All-or-Nothing 입고 검증
        
        모든 LOT이 유효해야만 입고 진행
        하나라도 실패하면 전체 거부
        """
        base_result = self.validate_inbound_data(packing_data)

        if not base_result.is_valid:
            # 에러가 있으면 전체 거부
            error_count = len(base_result.errors)
            base_result.errors.insert(0,
                f"[All-or-Nothing] {error_count}개 오류로 인해 전체 입고가 거부됩니다"
            )

        return base_result


class OutboundValidator(InventoryValidator):
    """출고 전용 검증기"""

    def validate_outbound_batch(self, outbound_list: List[Dict]) -> ValidationResult:
        """
        배치 출고 검증
        
        Args:
            outbound_list: [{'lot_no': 'xxx', 'qty': 1000}, ...]
        """
        errors = []
        warnings = []

        for idx, item in enumerate(outbound_list):
            lot_no = item.get('lot_no', '')
            qty = item.get('qty', 0)

            result = self.validate_outbound(lot_no, qty)
            if not result.is_valid:
                errors.extend([f"#{idx+1} {lot_no}: {e}" for e in result.errors])
            warnings.extend([f"#{idx+1} {lot_no}: {w}" for w in result.warnings])

        if errors:
            return ValidationResult.failure(errors, warnings)

        return ValidationResult.success(warnings)


# ============================================================================
# 편의 함수
# ============================================================================

def validate_lot_no(lot_no: str) -> Tuple[bool, str]:
    """
    LOT 번호 간단 검증 (레거시 호환)
    
    Returns:
        (is_valid, error_message)
    """
    v = InventoryValidator()
    result = v.validate_lot_no(lot_no)

    if result.is_valid:
        return True, ""
    return False, "; ".join(result.errors)


def validate_sap_no(sap_no: str) -> Tuple[bool, str]:
    """
    SAP NO 간단 검증 (레거시 호환). P1 단일 소스.
    SAP NO는 선택적(빈 값 허용). 있으면 10자리 숫자 등 형식 검사.
    """
    if not sap_no:
        return True, ""
    sap_no = str(sap_no).strip()
    if not sap_no:
        return True, ""
    if not re.match(r'^\d{10}$', sap_no):
        if not sap_no.isalnum():
            return False, f"SAP NO에 허용되지 않은 문자: {sap_no}"
    return True, ""


def validate_weight(weight: float) -> Tuple[bool, str]:
    """
    중량 간단 검증 (레거시 호환)
    """
    v = InventoryValidator()
    result = v.validate_weight(weight)

    if result.is_valid:
        return True, ""
    return False, "; ".join(result.errors)


# ============================================================================
# 테스트
# ============================================================================

if __name__ == "__main__":
    logger.debug("=" * 60)
    logger.debug("InventoryValidator 단위 테스트")
    logger.debug("=" * 60)

    v = InventoryValidator()

    # LOT 번호 테스트
    logger.debug("\n[LOT 번호 검증]")
    test_lots = ['1120001234', '', '123', 'ABC123', '1120000001']
    for lot in test_lots:
        result = v.validate_lot_no(lot)
        status = "✅" if result.is_valid else "❌"
        logger.debug(f"  {status} '{lot}': {result.errors or result.warnings or 'OK'}")

    # 중량 테스트
    logger.debug("\n[중량 검증]")
    test_weights = [5000, 0, -100, 0.001, 999999999, None]
    for w in test_weights:
        result = v.validate_weight(w)
        status = "✅" if result.is_valid else "❌"
        logger.debug(f"  {status} {w}: {result.errors or result.warnings or 'OK'}")

    logger.debug("\n✅ 테스트 완료")