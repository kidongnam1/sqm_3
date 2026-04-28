# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - 입고 처리 Mixin
======================================

v3.6.6: SQLAlchemy → SQMDatabase API 전환 (self.db 기반)

작성자: Ruby (남기동)
버전: v3.6.6
"""

import sqlite3
import logging
from datetime import date, datetime
from typing import Dict, List

from .base import InventoryBaseMixin
import re  # v5.3.0
from utils.common import normalize_lot, norm_tonbag_no_std, norm_bl_no, norm_sap_no, norm_container_no

logger = logging.getLogger(__name__)

# 비즈니스 기본값
from core.constants import DEFAULT_WAREHOUSE, SAMPLE_WEIGHT_KG, STATUS_AVAILABLE
from engine_modules.tonbag_weight_rules import build_rule_result






# --- v5.3.0 helpers: alias + normalization + audit raw capture ---
def _get_sub_lt_raw(tb: dict):
    """Extract raw tonbag/sub_lt value from various possible keys (case-insensitive)."""
    if not isinstance(tb, dict):
        return None, None
    priority = ['bag_no','tonbag_no','sub_lt','dmsub_lt','dm_sub_lt','DM SUB LT','DM_SUB_LT']
    for k in priority:
        if k in tb and tb.get(k) not in (None, ''):
            return tb.get(k), str(k)
    lower_map = {str(k).lower(): k for k in tb.keys()}
    for lk in ['bag_no','tonbag_no','sub_lt','dmsub_lt','dm_sub_lt','dm sub lt']:
        if lk in lower_map:
            k = lower_map[lk]
            v = tb.get(k)
            if v not in (None, ''):
                return v, str(k)
    return None, None

class InboundMixin(InventoryBaseMixin):
    """입고 처리 Mixin (v3.6.6: SQMDatabase API 기반)"""
    

    # ══════════════════════════════════════════════════════════════════════
    # v8.6.4: process_inbound 분해 — 서브메서드 3개
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _inb_normalize_packing(packing_data) -> dict:
        """v8.6.4: packing_data → 표준 dict 정규화 (process_inbound 분해 1/3)"""
        if isinstance(packing_data, dict):
            return packing_data
        if hasattr(packing_data, 'to_dict'):
            return packing_data.to_dict()
        if hasattr(packing_data, '_data'):
            return packing_data._data
        if hasattr(packing_data, 'get'):
            return {k: packing_data.get(k)
                    for k in dir(packing_data) if not k.startswith('_')}
        logger.warning("[입고] packing_data 타입 인식 불가 — 빈 dict 사용")
        return {}

    @staticmethod
    def _inb_validate_lot(packing: dict, result: dict) -> bool:
        """v8.6.4: LOT/무게/BL 기본 유효성 검증 (process_inbound 분해 2/3).

        Returns:
            True → 통과 / False → 치명 오류, 입고 중단
        """
        from engine_modules.constants import (
            INBOUND_ERROR_INVALID_LOT, INBOUND_ERROR_INVALID_WEIGHT
        )
        lot_no = str(packing.get('lot_no') or '').strip()
        if not lot_no:
            result['errors'].append("[IB-01] LOT 번호 누락")
            return False

        if len(lot_no) < 8 or len(lot_no) > 11 or not re.match(r'^\d+$', lot_no):
            result['warnings'].append(
                f"[IB-PC1] LOT 번호 형식 경고: '{lot_no}' (SQM 기준 10자리 숫자)"
            )

        total_w = float(packing.get('total_weight') or packing.get('weight') or 0)
        if total_w <= 0:
            result['errors'].append(f"[IB-02] 무게 0 또는 음수: {total_w}")
            return False

        return True

    @staticmethod
    def _inb_record_audit(db, lot_no: str, batch_id: str,
                          source_type: str, source_file: str,
                          bag_count: int, total_weight: float) -> None:
        """v8.6.4: 입고 audit_log 기록 (process_inbound 분해 3/3)."""
        import json as _json
        try:
            db.execute(
                """INSERT INTO audit_log
                   (event_type, event_data, batch_id, created_by)
                   VALUES (?, ?, ?, ?)""",
                ('INBOUND',
                 _json.dumps({
                     'lot_no': lot_no, 'bags': bag_count,
                     'weight_kg': total_weight,
                     'source': source_type,
                     'file': source_file,
                 }, ensure_ascii=False),
                 batch_id,
                 'inbound_mixin')
            )
        except Exception as _ae:
            logger.debug(f"[입고] audit_log 기록 스킵: {_ae}")

    def process_inbound(self, packing_data, invoice_data=None, 
                        bl_data=None, do_data=None,
                        source_type: str = '', source_file: str = '') -> Dict:
        """
        입고 처리
        
        Args:
            packing_data: 패킹 리스트 데이터 (dict 또는 PackingData)
            invoice_data: 인보이스 데이터 (선택)
            bl_data: B/L 데이터 (선택)
            do_data: D/O 데이터 (선택)
            source_type: 입고 출처 ('PDF', 'EXCEL_MANUAL', 'EXCEL_PASTE', '')
            source_file: 원본 파일명 (감사 추적용)
        
        Returns:
            dict: {success, message, lot_no, created_lots, created_tonbags, errors, warnings}
        """
        result = {
            'success': False,
            'message': '',
            'lot_no': None,
            'created_lots': [],
            'created_tonbags': 0,
            'errors': [],
            'warnings': [],
        }
        
        try:
            # v3.8.8: 항상 dict로 정규화 (PackingData wrapping 제거)
            if isinstance(packing_data, dict):
                packing = packing_data
            elif hasattr(packing_data, 'to_dict'):
                packing = packing_data.to_dict()
            elif hasattr(packing_data, '_data'):
                packing = packing_data._data
            elif hasattr(packing_data, 'get'):
                # PackingData 또는 dict-like 객체
                packing = {k: packing_data.get(k) for k in [
                    'lot_no', 'sap_no', 'bl_no', 'container_no', 'product', 'product_code',
                    'lot_sqm', 'mxbg_pallet', 'net_weight', 'gross_weight', 'salar_invoice_no',
                    'ship_date', 'arrival_date', 'free_time', 'free_time_date',
                    'warehouse', 'vessel', 'tonbags',
                ] if packing_data.get(k) is not None}
            else:
                packing = vars(packing_data) if hasattr(packing_data, '__dict__') else {}
            
            logger.info(f"[process_inbound] lot_no={packing.get('lot_no')!r}, keys_count={len(packing)}")
            
            # 필수 필드 검증
            if not packing.get('lot_no'):
                result['errors'].append(f"LOT 번호가 없습니다 (type={type(packing_data).__name__}, keys={list(packing.keys())[:5]})")
                return result
            
            lot_no = normalize_lot(packing.get('lot_no')) or str(packing.get('lot_no') or '').strip()
            if not lot_no:
                result['errors'].append("LOT 번호가 비어 있습니다.")
                return result

            # LOT NO 길이 검증
            if len(lot_no) > 30:
                result['errors'].append(f"LOT 번호가 너무 깁니다: {len(lot_no)}자 (최대 30자)")
                return result
            
            # PC-1: LOT 번호 형식 검증 (SQM: 10자리 숫자, 경고만)
            if lot_no and not re.match(r'^\d{8,11}$', lot_no):  # v8.6.4: 8~11자리
                result['warnings'].append(
                    f"LOT 번호 형식 주의: '{lot_no}' (SQM 표준: 10자리 숫자)")
            
            # 중량 검증
            weight = self._safe_parse_float(
                packing.get('net_weight')
            )
            if weight <= 0:
                result['errors'].append(f"유효하지 않은 중량: {weight}")
                return result
            
            # 중복 확인
            if self._check_lot_exists(lot_no):
                result['errors'].append(f"이미 존재하는 LOT: {lot_no}")
                return result
            
            # v6.9.8 [IB-09]: SAP 번호 중복 WARNING 강화 (에러코드 명확화)
            # 동일 SAP가 다른 LOT에 있으면 [IB-09] 코드로 경고
            sap_no_raw = packing.get('sap_no', '')
            if sap_no_raw:
                sap_std = norm_sap_no(sap_no_raw) or str(sap_no_raw).strip()
                if sap_std:
                    try:
                        dup_row = self.db.fetchone(
                            "SELECT lot_no FROM inventory WHERE sap_no = ? AND lot_no != ?",
                            (sap_std, lot_no))
                        if dup_row:
                            existing_lot = dup_row['lot_no'] if isinstance(dup_row, dict) else dup_row[0]
                            _ib09_warn = (
                                f"[IB-09][SAP_DUPLICATE] SAP 번호 중복: '{sap_std}' "
                                f"— 기존 LOT {existing_lot}에도 동일 SAP 존재 "
                                f"(의도된 경우 무시 가능, 단 SAP 오입력 여부 확인 권장)"
                            )
                            result['warnings'].append(_ib09_warn)
                            logger.warning(_ib09_warn)
                    except (sqlite3.OperationalError, KeyError):
                        pass  # sap_no 컬럼 없는 구버전 DB — 스킵

            # v6.9.5 [IB-08 HARD STOP]: B/L 번호 공란 → 입고 차단
            # 기존: 경고만 (WARNING) → 개선: HARD STOP
            # 이유: BL 없으면 통관/LOT 추적 불가 → 재고 사고 위험
            bl_no_raw = packing.get('bl_no', '')
            bl_str_check = str(bl_no_raw).strip() if bl_no_raw else ''
            if not bl_str_check:
                _bl_err = (
                    f"[IB-08] B/L 번호 없음 (lot={packing.get('lot_no','?')}) "
                    f"— B/L 번호는 필수 항목입니다. 입고 서류를 확인하세요."
                )
                logger.error(_bl_err)
                result['errors'].append(_bl_err)
                result['success'] = False
                return result  # 해당 LOT 입고 중단 (단일 LOT 처리 함수)

            # v6.9.8 [IB-10]: B/L 번호 형식 검증 경고 강화 ([IB-10] 코드)
            if bl_str_check and not re.match(r'^[A-Z]{4}\d{7,}$', bl_str_check.upper()):
                _ib10_warn = (
                    f"[IB-10][BL_FORMAT_WARN] B/L 번호 형식 주의: '{bl_str_check}' "
                    f"(표준: 영문4자리+숫자7자리 이상, 예: HDMU1234567) "
                    f"— 통관 서류 재확인 권장"
                )
                result['warnings'].append(_ib10_warn)
                logger.warning(_ib10_warn)
            bl_no_raw = bl_str_check  # 이후 코드에서 그대로 사용
            
            # v6.9.6 [AV-05]: location 없음 WARNING
            # location = 창고 내 세부 위치(rack 등)
            # 입고 시 미지정이면 WARNING → 재고관리에서 위치 배정 권장
            _loc_val = str(packing.get('location') or '').strip()
            if not _loc_val:
                _av05_warn = (
                    f"[AV-05] 창고 위치(location) 미지정 (lot={lot_no}) "
                    f"— 입고 후 재고관리→위치 설정 권장 "
                    f"(warehouse='{packing.get('warehouse', DEFAULT_WAREHOUSE)}')"
                )
                result['warnings'].append(_av05_warn)
                logger.warning(_av05_warn)

            # 트랜잭션으로 원자적 처리
            with self.db.transaction():
                # LOT 생성
                # v8.7.0 Phase 2: invoice_data를 _prepare_lot_data에 전달 (이전엔 누락되어 BL/INV 6필드 유실)
                lot_data = self._prepare_lot_data(packing, bl_data, do_data, invoice_data=invoice_data)
                self._insert_lot(lot_data)
                
                # v3.8.4: 생성된 LOT의 inventory_id 조회
                inv_row = self.db.fetchone(
                    "SELECT id FROM inventory WHERE lot_no = ?", (lot_no,))
                inventory_id = inv_row['id'] if inv_row and isinstance(inv_row, dict) else (
                    inv_row[0] if inv_row else None)
                
                # 톤백 생성 (명시적 tonbags 또는 bag_count 기반 자동 생성)
                tonbags = packing.get('tonbags') or []
                if not tonbags:
                    bag_count = self._safe_parse_int(
                        packing.get('mxbg_pallet')
                    )
                    # v6.9.1 [I5]: bag_count=0 → 톤백 없는 LOT 생성 차단
                    if bag_count <= 0:
                        result['errors'].append(
                            f"[ZERO_BAGCOUNT] 톤백 수량이 0입니다. "
                            f"mxbg_pallet={packing.get('mxbg_pallet')!r} 확인 필요"
                        )
                        return result
                    if bag_count > 0:
                        total_w = self._safe_parse_float(
                            packing.get('net_weight')
                        )
                        # v7.2.0: 입고 템플릿에서 주입된 bag_weight_kg 우선 사용
                        # v5.7.1 핵심: 대원칙 — 샘플 1kg 차감 후 나눔
                        # 잘못된 식: per_bag = total_w / bag_count  → 5001/10 = 500.1 (정합성 깨짐)
                        # 올바른 식: per_bag = (total_w - 1) / bag_count → 5000/10 = 500.0
                        sample_kg = SAMPLE_WEIGHT_KG
                        _tpl_bag_kg = packing.get('bag_weight_kg')  # 템플릿 주입값
                        rule = build_rule_result(total_w, bag_count, sample_kg,
                                                 expected_per_bag=_tpl_bag_kg)
                        per_bag = rule.tonbag_weight_kg
                        result['rule_status'] = rule.rule_status
                        tonbags = [
                            {'sub_lt': i + 1, 'weight_kg': per_bag}
                            for i in range(bag_count)
                        ]
                
                # v3.8.4: inventory_id 전달하여 FK 연결
                sap_std = norm_sap_no(packing.get('sap_no')) or ''
                bl_std = norm_bl_no(packing.get('bl_no')) or ''
                tonbag_count = self._insert_tonbags(
                    lot_no,
                    sap_std,
                    bl_std,
                    tonbags,
                    inventory_id=inventory_id
                )
                # v8.7.0 [FIX]: inventory.tonbag_count를 실제 삽입된 톤백 수로 갱신
                #   (기존: DDL default=0 고정, mxbg_pallet은 파싱값이지만 tonbag_count는 항상 0 → VIEW 집계 오류)
                if inventory_id is not None and tonbag_count > 0:
                    try:
                        self.db.execute(
                            "UPDATE inventory SET tonbag_count = ? WHERE id = ?",
                            (tonbag_count, inventory_id))
                    except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                        logger.debug(f"inventory.tonbag_count 업데이트 스킵: {_e}")
                # v5.8.8: 톤백에도 con_return(컨테이너 반납일) 동일 적용
                if lot_data.get('con_return'):
                    try:
                        self.db.execute(
                            "UPDATE inventory_tonbag SET con_return = ? WHERE lot_no = ?",
                            (lot_data['con_return'], lot_no))
                    except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as _e:
                        logger.debug(f"톤백 con_return 업데이트 스킵(컬럼 없을 수 있음): {_e}")

                # v8.7.0 Phase 3-A: DO의 containers[] / free_time_info[] → container_info / freetime_info 테이블 저장
                # (기존 con_return 단일 필드는 그대로 유지, 상세 1:N 보존 — demurrage 추적용)
                if inventory_id is not None:
                    self._insert_do_details(lot_no, inventory_id, do_data)
                    # v8.7.0 Phase 3-B: Invoice 전필드를 document_invoice 테이블에 보존
                    self._insert_document_invoice(lot_no, inventory_id, invoice_data)
                    # v8.7.0 Phase 3-B: BL/PL/DO 전필드를 대칭 3테이블에 보존
                    self._insert_document_bl(lot_no, inventory_id, bl_data)
                    self._insert_document_pl(lot_no, inventory_id, packing)
                    self._insert_document_do(lot_no, inventory_id, do_data)

                # v3.8.4: 톤백 합계 = LOT 중량 검증
                if tonbag_count > 0:
                    tb_sum_row = self.db.fetchone(
                        "SELECT SUM(weight) as total FROM inventory_tonbag WHERE lot_no = ?",
                        (lot_no,))
                    tb_sum = (tb_sum_row['total'] if isinstance(tb_sum_row, dict) else tb_sum_row[0]) if tb_sum_row else 0
                    lot_weight = self._safe_parse_float(
                        packing.get('net_weight'))
                    if lot_weight > 0 and abs(tb_sum - lot_weight) > 0.5:
                        # v6.9.1 [I3]: 경고 → HARD-STOP (중량 정합성 핵심 불변 조건)
                        _i3_msg = (
                            f"[WEIGHT_MISMATCH] 톤백 합계({tb_sum:.1f}kg) ≠ "
                            f"LOT 중량({lot_weight:.1f}kg) "
                            f"차이: {abs(tb_sum - lot_weight):.1f}kg — 입고 차단"
                        )
                        result['errors'].append(_i3_msg)
                        logger.error(f"[I3] {_i3_msg}")
                        return result
                
                # v5.1.4: 입고 후 즉시 정합성 검증 (트랜잭션 안)
                if hasattr(self, 'verify_lot_integrity'):
                    integrity = self.verify_lot_integrity(lot_no)
                    if not integrity.get('valid', True):
                        result['warnings'].extend(integrity.get('errors', []))
                        logger.warning(f"입고 후 정합성 경고 ({lot_no}): {integrity.get('errors')}")
                
                # v6.12 Addon-A: 입고 stock_movement 이력 기록 (감사 추적)
                # v6.12.1: source_type, source_file 추가
                try:
                    _src_type = source_type or 'UNKNOWN'
                    # v7.0.0 [I-BUG-1]: stock_movement qty_kg 샘플 제외 수정
                    # 기존: weight (톤백합계 + 샘플1kg 포함)
                    # 수정: weight - SAMPLE_WEIGHT_KG (순수 화물 중량, 샘플 미포함)
                    _sm_qty_kg = max(0.0, float(weight) - float(SAMPLE_WEIGHT_KG))
                    self.db.execute("""
                        INSERT INTO stock_movement
                        (lot_no, movement_type, qty_kg, remarks, source_type, source_file, created_at)
                        VALUES (?, 'INBOUND', ?, ?, ?, ?, ?)
                    """, (lot_no, _sm_qty_kg,
                           f"tonbags={tonbag_count}, product={packing.get('product','')}, "
                           f"sap={packing.get('sap_no','')}, bl={packing.get('bl_no','')} "
                           f"[total={weight:.1f}kg, sample={SAMPLE_WEIGHT_KG}kg 제외]",
                           _src_type, source_file or '',
                           datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    logger.info(f"[stock_movement] INBOUND 기록: {lot_no}, {_sm_qty_kg}kg (샘플제외), source={_src_type}")
                except Exception as _sm_e:
                    logger.debug(f"[stock_movement] INBOUND 기록 스킵: {_sm_e}")
                
                # v6.9.1 [I6]: tonbag_count=0 → 유령 LOT 방지 HARD-STOP
                if tonbag_count == 0:
                    result['errors'].append(
                        f"[ZERO_TONBAG] LOT {lot_no}: 생성된 톤백이 없습니다. "
                        f"입고 데이터를 확인해주세요."
                    )
                    return result
                result['success'] = True
                result['message'] = f"입고 완료: {lot_no}"
                result['lot_no'] = lot_no
                result['created_lots'].append(lot_no)
                result['created_tonbags'] = tonbag_count

                # v8.3.0 [Phase 9]: INBOUND audit_log 기록
                try:
                    from engine_modules.audit_helper import write_audit, EVT_INBOUND
                    write_audit(self.db, EVT_INBOUND, lot_no=lot_no, detail={
                        'net_weight_kg': weight,
                        'product':  packing.get('product', ''),
                        'bl_no':    packing.get('bl_no', ''),
                        'sap_no':   packing.get('sap_no', ''),
                        'tonbags':  tonbag_count,
                    })
                except Exception as _ae:
                    logger.debug(f"[INBOUND audit] 스킵: {_ae}")
            
            self._log_operation("입고", {
                'lot_no': lot_no, 
                'tonbags': tonbag_count
            })
            
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"입고 처리 오류: {e}", exc_info=True)
            result['errors'].append(str(e))
        
        return result
    
    def _check_lot_exists(self, lot_no: str) -> bool:
        """LOT 존재 여부 확인"""
        try:
            row = self.db.fetchone(
                "SELECT 1 FROM inventory WHERE lot_no = ?", (lot_no,)
            )
            return row is not None
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError):
            return False
    
    def _prepare_lot_data(self, packing, bl_data=None,
                          do_data=None, invoice_data=None) -> Dict:
        """LOT 데이터 준비 (v3.8.8: dict/PackingData/dataclass 모두 지원).

        변수 구분 (혼동 방지): arrival_date=입항일(날짜 YYYY-MM-DD), warehouse=창고(예: 광양),
        free_time_date=con_return=컨테이너 반납일, free_time=일수(반납일-입항일).

        v8.7.0: invoice_data 파라미터 명시 추가 — 기존엔 process_inbound에서만 받고
        _prepare_lot_data 시그니처에서 빠져 BL/INV 파생 6컬럼이 DB 유실됐음.
        """
        # v3.8.8: 모든 타입 → dict 변환 + 디버깅
        orig_type = type(packing).__name__
        if not isinstance(packing, dict):
            if hasattr(packing, 'to_dict'):
                packing = packing.to_dict()
            elif hasattr(packing, '_data'):
                packing = packing._data
            else:
                try:
                    from dataclasses import asdict
                    packing = asdict(packing)
                except (TypeError, ImportError):
                    packing = vars(packing) if hasattr(packing, '__dict__') else {}

        # v8.7.0: bl_data / invoice_data / do_data 모두 dict로 정규화
        def _to_dict(obj):
            if obj is None:
                return {}
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, 'to_dict'):
                try:
                    return obj.to_dict()
                except Exception as _e:
                    logger.debug("[inbound] to_dict() 실패, 대체 경로 사용: %s", _e)
            try:
                from dataclasses import asdict, is_dataclass
                if is_dataclass(obj):
                    return asdict(obj)
            except (TypeError, ImportError):
                pass
            return vars(obj) if hasattr(obj, '__dict__') else {}

        bl_dict = _to_dict(bl_data)
        inv_dict = _to_dict(invoice_data)
        do_dict = _to_dict(do_data)
        
        # 디버깅: lot_no 값 확인
        logger.info(f"[_prepare_lot_data] type={orig_type}, lot_no={packing.get('lot_no')!r}, keys={list(packing.keys())[:5]}")
        
        weight = self._safe_parse_float(
            packing.get('net_weight')
        )
        gross = self._safe_parse_float(
            packing.get('gross_weight')
        ) or weight
        bag_count = self._safe_parse_int(
            packing.get('mxbg_pallet')
        )
        
        lot_no_std = normalize_lot(packing.get('lot_no')) or str(packing.get('lot_no') or '').strip()
        bl_std = norm_bl_no(packing.get('bl_no')) or str(packing.get('bl_no') or '').strip()
        sap_std = norm_sap_no(packing.get('sap_no')) or str(packing.get('sap_no') or '').strip()
        # v8.7.0: BL/Invoice/DO 파생 6필드 추출 ─ Phase 2
        #   원천 우선순위: packing_dict(GUI 선병합) > bl_dict/inv_dict/do_dict(engine 직접)
        def _pick(*candidates):
            """첫 유효값 반환(None/빈문자/0 제외)."""
            for v in candidates:
                if v is None:
                    continue
                s = str(v).strip()
                if s and s.lower() not in ('none', 'nan'):
                    return v
            return ''

        _voyage = _pick(packing.get('voyage'), bl_dict.get('voyage'))
        _do_no = _pick(packing.get('do_no'), do_dict.get('do_no'))
        _inv_date_raw = _pick(
            packing.get('invoice_date'),
            inv_dict.get('invoice_date'),
        )
        _inv_date_parsed = self._safe_parse_date(_inv_date_raw) if _inv_date_raw else None
        _invoice_date = _inv_date_parsed.strftime('%Y-%m-%d') if _inv_date_parsed else ''

        def _num(v, default=0.0):
            try:
                if v is None or str(v).strip() == '':
                    return default
                return float(v)
            except (TypeError, ValueError):
                return default

        _total_amount = _num(_pick(
            packing.get('total_amount'),
            inv_dict.get('total_amount'),
        ))
        _currency = str(_pick(
            packing.get('currency'),
            inv_dict.get('currency'),
        ) or '').upper().strip()[:10]
        _unit_price = _num(_pick(
            packing.get('unit_price'),
            inv_dict.get('unit_price'),
        ))

        lot_data = {
            'lot_no': lot_no_std or packing.get('lot_no'),
            'product': packing.get('product', ''),
            'product_code': packing.get('product_code', ''),
            'bl_no': bl_std or packing.get('bl_no', ''),
            'sap_no': sap_std or packing.get('sap_no', ''),
            'container_no': norm_container_no(packing.get('container_no')) or str(packing.get('container_no') or ''),
            'lot_sqm': packing.get('lot_sqm', ''),
            'net_weight': weight,
            'gross_weight': gross,
            'initial_weight': weight,
            'current_weight': weight,
            'picked_weight': 0,
            'mxbg_pallet': bag_count,
            # v8.7.0 Phase 2: BL/Invoice/DO 파생 필드
            'voyage': str(_voyage or ''),
            'do_no': str(_do_no or ''),
            'invoice_date': _invoice_date,
            'total_amount': _total_amount,
            'currency': _currency,
            'unit_price': _unit_price,
            'salar_invoice_no': packing.get('salar_invoice_no', ''),
            'ship_date': packing.get('ship_date', ''),
            'warehouse': packing.get('warehouse', DEFAULT_WAREHOUSE),
            'vessel': packing.get('vessel', ''),
            'inbound_date': date.today().strftime('%Y-%m-%d'),
            'status': STATUS_AVAILABLE,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
                # v3.8.7: Invoice 데이터 보완
        if packing.get('salar_invoice_no'):
            lot_data['salar_invoice_no'] = packing['salar_invoice_no']
        # v5.6.6: invoice_no fallback 제거 (salar_invoice_no 단일)
        
        # ship_date: 파싱 가능할 때만 설정. B/L·Invoice에서 채워져야 함.
        if packing.get('ship_date'):
            sd = self._safe_parse_date(packing['ship_date'])
            lot_data['ship_date'] = sd.strftime('%Y-%m-%d') if sd else ''
        
        # 입항일(arrival_date): 파싱된 값만 사용. 모를 때는 반드시 비움 — warehouse('광양')와 혼동 금지
        arrival_date = None
        if do_data and do_data.get('arrival_date'):
            arrival_date = self._safe_parse_date(do_data.get('arrival_date'))
        if not arrival_date and packing.get('arrival_date'):
            arrival_date = self._safe_parse_date(packing.get('arrival_date'))
        lot_data['arrival_date'] = arrival_date.strftime('%Y-%m-%d') if arrival_date else ''

        # v8.7.0 [FIX]: stock_date 바인딩 — DOData.stock_date 우선, 없으면 arrival_date로 fallback
        stock_date = None
        if do_data and do_data.get('stock_date'):
            stock_date = self._safe_parse_date(do_data.get('stock_date'))
        if not stock_date and packing.get('stock_date'):
            stock_date = self._safe_parse_date(packing.get('stock_date'))
        if not stock_date:
            stock_date = arrival_date  # arrival_date와 동일일로 기본 설정
        lot_data['stock_date'] = stock_date.strftime('%Y-%m-%d') if stock_date else ''
        
        # con_return = 컨테이너 반납일 (D/O의 Free_Time 컬럼 = 반납일). free_time = (con_return - arrival_date) 일수
        # v8.5.5 [PATCH2]: do_data.containers[i].free_time / free_time_date 키 다중 경로 참조
        def _extract_do_con_return(do_d):
            """do_data(dict or DOData)에서 컨테이너 반납일 문자열 추출."""
            if not do_d:
                return ''
            # 1) do_data 자체에 free_time_date 키 (MSC coord 파서 v8.5.5 이후 세팅)
            val = ''
            if isinstance(do_d, dict):
                val = (do_d.get('free_time_date') or do_d.get('con_return') or
                       do_d.get('free_time') or '')
            else:
                val = (getattr(do_d, 'free_time_date', '') or
                       getattr(do_d, 'con_return', '') or '')
            if val and str(val).strip():
                return str(val).strip()[:10]
            # 2) do_data.containers[] 첫 번째 항목의 free_time / free_time_date
            containers = (do_d.get('containers', []) if isinstance(do_d, dict)
                          else getattr(do_d, 'containers', []))
            dates = []
            for c in (containers or []):
                for key in ('free_time_date', 'free_time', 'con_return'):
                    v = (c.get(key) if isinstance(c, dict) else getattr(c, key, '')) or ''
                    v = str(v).strip()[:10]
                    if v and len(v) == 10 and v[4] == '-':
                        dates.append(v)
                        break
            # 가장 늦은 날짜를 대표값으로 반환
            return max(dates) if dates else ''

        con_return_str = (
            packing.get('con_return', '') or
            packing.get('free_time_date', '') or
            _extract_do_con_return(do_data)
        )
        con_return_date = self._safe_parse_date(con_return_str) if con_return_str else None
        lot_data['con_return'] = con_return_date.strftime('%Y-%m-%d') if con_return_date else ''

        free_time = 0
        if not con_return_str:
            logger.debug(f"[_prepare_lot_data] FREE TIME 0: con_return_date 미제공 lot_no={packing.get('lot_no')!r}")
        if con_return_date and arrival_date:
            free_time = (con_return_date - arrival_date).days
            if free_time < 0:
                free_time = 0
        
        # packing에서 이미 계산된 free_time(일수)이 있으면 우선 사용
        if packing.get('free_time'):
            try:
                free_time = int(float(packing['free_time']))
            except (ValueError, TypeError) as _e:
                logger.debug(f"free_time 변환 실패: {packing.get('free_time')!r} → {_e}")
        
        lot_data['free_time'] = free_time
        
        # v6.2.7: product_code 자동감지 (비어있으면 product_master에서 매칭)
        if not lot_data.get('product_code'):
            try:
                from gui_app_modular.dialogs.product_master_helper import auto_detect_product_code
                detected = auto_detect_product_code(self.db, lot_data.get('product', ''))
                if detected:
                    lot_data['product_code'] = detected
            except Exception:
                logger.debug("[SUPPRESSED] exception in inbound_mixin.py")  # noqa
        
        return lot_data
    
    def _insert_lot(self, lot_data: Dict) -> None:
        """LOT 삽입 (v6.2.8: 컬럼명 화이트리스트 검증)"""
        # 안전성: 컬럼명이 알파벳+밑줄만 포함하는지 검증
        for col in lot_data.keys():
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
                raise ValueError(f"잘못된 컬럼명: {col!r}")
        columns = ', '.join(lot_data.keys())
        placeholders = ', '.join(['?'] * len(lot_data))
        
        sql = f"INSERT INTO inventory ({columns}) VALUES ({placeholders})"
        self.db.execute(sql, tuple(lot_data.values()))
    
    def _insert_tonbags(self, lot_no: str, sap_no: str, bl_no: str,
                        tonbags: List[Dict], inventory_id: int = None) -> int:
        """톤백 삽입 (v5.2.0: tonbag_no TEXT + 샘플 하드스톱)"""
        if not tonbags:
            return 0
        
        count = 0
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        today = date.today().strftime('%Y-%m-%d')
        
        for tb_idx, tb in enumerate(tonbags, start=1):  # v6.9.1 [I4]
            weight = self._safe_parse_float(tb.get('weight_kg') or tb.get('weight'))
            raw_sub_lt, raw_key = _get_sub_lt_raw(tb)
            # v6.2.7: raw_sub_lt → 정규화만 사용 (미사용 변수 제거)
            # 정규화: 001/1 -> tonbag_no "001", sub_lt 1 (문자열 0 패딩 + DB는 정수)
            tonbag_no, sub_lt_int = norm_tonbag_no_std(raw_sub_lt, is_sample=False)
            if not tonbag_no or sub_lt_int == 0:
                # v6.9.1 [I4]: count+1 → 루프 인덱스 기반 (충돌 방지)
                fallback = tb_idx
                tonbag_no = str(fallback).zfill(3)
                sub_lt_int = fallback

            sql = """
                INSERT INTO inventory_tonbag 
                (inventory_id, lot_no, sap_no, bl_no, sub_lt, tonbag_no,
                 weight, status, is_sample, inbound_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'AVAILABLE', 0, ?, ?)
            """
            try:
                self.db.execute(sql, (inventory_id, lot_no, sap_no, bl_no,
                                      sub_lt_int, tonbag_no, weight, today, now))
                count += 1
            except sqlite3.IntegrityError as _ie:
                # v6.9.7 [AV-07]: tonbag_uid/sub_lt UNIQUE 충돌 명확 에러
                _uid_chk = self.db.fetchone(
                    "SELECT tonbag_uid, status FROM inventory_tonbag "
                    "WHERE lot_no=? AND sub_lt=?", (lot_no, sub_lt_int)
                )
                _exist_info = (
                    f"기존 UID={_uid_chk.get('tonbag_uid','')} "
                    f"status={_uid_chk.get('status','')}"
                    if _uid_chk else "기존 레코드 확인 불가"
                )
                raise ValueError(
                    f"[AV-07][TONBAG_UID_CONFLICT] 톤백 UID 충돌: "
                    f"LOT {lot_no} sub_lt={sub_lt_int} (tonbag_no={tonbag_no}) "
                    f"— {_exist_info} | 원인: {_ie}"
                ) from _ie
        
        # v5.5.3: 샘플 톤백 자동 생성 (sub_lt=0, tonbag_no="S00", 1kg, is_sample=1)
        # ★ 샘플 생성 실패 = 하드스톱 (All-or-Nothing)
        # ★ v7.6.0: 샘플 중복 생성 방지 — INSERT 전 사전 검증
        _existing_sample = self.db.fetchone(
            "SELECT id, weight FROM inventory_tonbag "
            "WHERE lot_no = ? AND COALESCE(is_sample,0) = 1 LIMIT 1",
            (lot_no,)
        )
        if _existing_sample:
            # 이미 샘플 존재 → 무게 검증 후 INSERT 생략 (중복 방지)
            _ex_w = float(_existing_sample.get('weight') or 0
                          if isinstance(_existing_sample, dict)
                          else _existing_sample[1] or 0)
            if abs(_ex_w - 1.0) > 0.01:
                raise ValueError(
                    f"[v7.6.0] 샘플 중복 감지 — 기존 샘플 무게 오류: "
                    f"LOT {lot_no} 기존={_ex_w}kg (필수 1.000kg). "
                    f"DB 수동 확인 필요."
                )
            logger.warning(
                f"[_insert_tonbags] 샘플 중복 방지: LOT {lot_no}에 "
                f"샘플이 이미 존재하여 INSERT 생략 (weight={_ex_w}kg)"
            )
        else:
            self.db.execute("""
                INSERT INTO inventory_tonbag 
                (inventory_id, lot_no, sap_no, bl_no, sub_lt, tonbag_no,
                 weight, status, is_sample, inbound_date, created_at)
                VALUES (?, ?, ?, ?, 0, 'S00', 1.0, 'AVAILABLE', 1, ?, ?)
            """, (inventory_id, lot_no, sap_no, bl_no, today, now))
            count += 1
            logger.info(f"[_insert_tonbags] 샘플 톤백 생성: {lot_no}/S00 (1kg)")
        
        # v5.2.0: 샘플 존재 검증 (하드스톱)
        sample_check = self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM inventory_tonbag WHERE lot_no = ? AND is_sample = 1",
            (lot_no,))
        sample_cnt = (sample_check['cnt'] if isinstance(sample_check, dict) else sample_check[0]) if sample_check else 0
        if sample_cnt != 1:
            raise ValueError(f"샘플 정책 위반: LOT {lot_no}에 샘플 {sample_cnt}개 (필수 정확히 1개)")
        
        # v6.12 Addon-B: tonbag_uid 명시적 백필 보장
        # SQLite TRIGGER(trg_tonbag_uid_insert)가 정상 동작하면 이미 UID가 있지만,
        # 트리거 미생성/마이그레이션 누락 시에도 UID를 보장합니다.
        try:
            null_uid_count = self.db.fetchone(
                "SELECT COUNT(*) as cnt FROM inventory_tonbag "
                "WHERE lot_no = ? AND (tonbag_uid IS NULL OR tonbag_uid = '')",
                (lot_no,))
            null_cnt = (null_uid_count['cnt'] if isinstance(null_uid_count, dict)
                        else null_uid_count[0]) if null_uid_count else 0
            if null_cnt > 0:
                # 샘플 UID
                self.db.execute(
                    "UPDATE inventory_tonbag SET tonbag_uid = lot_no || '-S00' "
                    "WHERE lot_no = ? AND (COALESCE(is_sample,0)=1 OR sub_lt=0) "
                    "AND (tonbag_uid IS NULL OR tonbag_uid = '')",
                    (lot_no,))
                # 일반 톤백 UID
                self.db.execute(
                    "UPDATE inventory_tonbag SET tonbag_uid = lot_no || '-' || tonbag_no "
                    "WHERE lot_no = ? AND COALESCE(is_sample,0)=0 AND sub_lt > 0 "
                    "AND (tonbag_uid IS NULL OR tonbag_uid = '')",
                    (lot_no,))
                logger.info(f"[_insert_tonbags] tonbag_uid 백필: {lot_no} ({null_cnt}건)")
        except Exception as _uid_e:
            logger.debug(f"[_insert_tonbags] tonbag_uid 백필 스킵: {_uid_e}")
        
        return count

    # v8.7.0 Phase 3-A: D/O 복수 컨테이너·반납일 1:N 저장
    def _insert_do_details(self, lot_no, inventory_id, do_data):
        """v8.7.0 Phase 3-A: DO의 containers[]/free_time_info[]를 별도 테이블에 1:N 저장.

        do_data는 dict 또는 DOData 인스턴스. 둘 다 지원.
        기존 con_return 단일 필드는 그대로 유지(하위 호환), 상세는 freetime_info 테이블에 보존.
        """
        if not do_data:
            return
        # dict / dataclass 정규화
        def _get(obj, key, default=''):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        # containers[]
        containers = _get(do_data, 'containers', []) or []
        for c in containers:
            cno = ''
            try:
                cno = str(_get(c, 'container_no', '') or '').strip()
                if not cno:
                    continue
                self.db.execute(
                    """INSERT INTO container_info
                       (lot_no, inventory_id, container_no, seal_no, size_type,
                        weight_kg, measurement_cbm, package_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (lot_no, inventory_id, cno,
                     str(_get(c, 'seal_no', '') or ''),
                     str(_get(c, 'size_type', '') or ''),
                     self._safe_parse_float(_get(c, 'weight_kg', 0)),
                     self._safe_parse_float(_get(c, 'measurement_cbm', 0)),
                     self._safe_parse_int(_get(c, 'package_count', 0)))
                )
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                logger.debug(f"[container_info] INSERT 스킵 ({cno}): {e}")
            except Exception as e:
                logger.debug(f"[container_info] INSERT 스킵 ({cno}): {e}")

        # free_time_info[]
        ft_list = _get(do_data, 'free_time_info', []) or []
        for ft in ft_list:
            try:
                ftd_raw = _get(ft, 'free_time_date', '') or ''
                ftd = str(ftd_raw).strip()[:10] if ftd_raw else ''
                if not ftd:
                    continue
                self.db.execute(
                    """INSERT INTO freetime_info
                       (lot_no, inventory_id, container_no, free_time_date,
                        return_location, storage_free_days)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (lot_no, inventory_id,
                     str(_get(ft, 'container_no', '') or ''),
                     ftd,
                     str(_get(ft, 'return_location', '') or ''),
                     self._safe_parse_int(_get(ft, 'storage_free_days', 0)))
                )
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                logger.debug(f"[freetime_info] INSERT 스킵: {e}")
            except Exception as e:
                logger.debug(f"[freetime_info] INSERT 스킵: {e}")

        logger.info(
            f"[Phase3-A] DO 상세 저장: lot={lot_no} "
            f"containers={len(containers)}건 freetime={len(ft_list)}건"
        )

    # v8.7.0 Phase 3-B: Invoice 전필드를 별도 테이블에 보존
    def _insert_document_invoice(self, lot_no, inventory_id, invoice_data):
        """v8.7.0 Phase 3-B: InvoiceData의 비즈니스 필드 전체를 document_invoice에 보존.

        invoice_data는 dict 또는 InvoiceData 인스턴스. 둘 다 지원.
        raw_response/error_message/success/raw_text/bag_weight_kg/pl_warnings/lot_numbers는
        운영 가치 없어 저장하지 않음.

        기존 inventory 테이블의 invoice_date/total_amount/currency/unit_price 4필드는 유지
        (Phase 2와 호환), 이 메서드는 독립 테이블에 전필드 보존만 담당.

        예외 suppression: 실패해도 본 입고 트랜잭션을 무효화하지 않음(logger.debug 내림).
        """
        if not invoice_data:
            return

        # dict / dataclass 정규화
        def _get(obj, key, default=''):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        def _date_iso(v):
            """date/datetime → 'YYYY-MM-DD' str. None/빈값 → None(→ NULL)."""
            if v in (None, ''):
                return None
            if hasattr(v, 'isoformat'):
                try:
                    return v.isoformat()[:10]
                except (ValueError, TypeError):
                    return None
            s = str(v).strip()
            return s[:10] if s else None

        def _ts_iso(v):
            """timestamp → ISO str. None/빈값 → None."""
            if v in (None, ''):
                return None
            if hasattr(v, 'isoformat'):
                try:
                    return v.isoformat()
                except (ValueError, TypeError):
                    return None
            s = str(v).strip()
            return s if s else None

        invoice_no = ''
        try:
            invoice_no = str(_get(invoice_data, 'invoice_no', '') or '').strip()
            self.db.execute(
                """INSERT INTO document_invoice
                   (lot_no, inventory_id,
                    sap_no, invoice_no, salar_invoice_no, invoice_date,
                    customer_ref, inv_acc_doc, delivery_transport, bl_no,
                    customer_code, customer_name, customer_address,
                    product_code, product_name,
                    quantity_mt, unit_price, total_amount, currency,
                    net_weight_kg, gross_weight_kg,
                    package_count, package_type, jar_count,
                    vessel, origin, destination,
                    incoterm, payment_term,
                    source_file, parsed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lot_no, inventory_id,
                    str(_get(invoice_data, 'sap_no', '') or ''),
                    invoice_no,
                    str(_get(invoice_data, 'salar_invoice_no', '') or ''),
                    _date_iso(_get(invoice_data, 'invoice_date', None)),
                    str(_get(invoice_data, 'customer_ref', '') or ''),
                    str(_get(invoice_data, 'inv_acc_doc', '') or ''),
                    str(_get(invoice_data, 'delivery_transport', '') or ''),
                    str(_get(invoice_data, 'bl_no', '') or ''),
                    str(_get(invoice_data, 'customer_code', '') or ''),
                    str(_get(invoice_data, 'customer_name', '') or ''),
                    str(_get(invoice_data, 'customer_address', '') or ''),
                    str(_get(invoice_data, 'product_code', '') or ''),
                    str(_get(invoice_data, 'product_name', '') or ''),
                    self._safe_parse_float(_get(invoice_data, 'quantity_mt', 0)),
                    self._safe_parse_float(_get(invoice_data, 'unit_price', 0)),
                    self._safe_parse_float(_get(invoice_data, 'total_amount', 0)),
                    str(_get(invoice_data, 'currency', '') or '').upper().strip(),
                    self._safe_parse_float(_get(invoice_data, 'net_weight_kg', 0)),
                    self._safe_parse_float(_get(invoice_data, 'gross_weight_kg', 0)),
                    self._safe_parse_int(_get(invoice_data, 'package_count', 0)),
                    str(_get(invoice_data, 'package_type', '') or ''),
                    self._safe_parse_int(_get(invoice_data, 'jar_count', 0)),
                    str(_get(invoice_data, 'vessel', '') or ''),
                    str(_get(invoice_data, 'origin', '') or ''),
                    str(_get(invoice_data, 'destination', '') or ''),
                    str(_get(invoice_data, 'incoterm', '') or ''),
                    str(_get(invoice_data, 'payment_term', '') or ''),
                    str(_get(invoice_data, 'source_file', '') or ''),
                    _ts_iso(_get(invoice_data, 'parsed_at', None)),
                )
            )
            logger.info(
                f"[Phase3-B] document_invoice 저장: lot={lot_no} invoice={invoice_no!r}"
            )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.debug(
                f"[document_invoice] INSERT 스킵 (lot={lot_no}, inv={invoice_no!r}): {e}"
            )
        except Exception as e:
            logger.debug(
                f"[document_invoice] INSERT 스킵 (lot={lot_no}, inv={invoice_no!r}): {e}"
            )

    def _insert_document_bl(self, lot_no, inventory_id, bl_data):
        """v8.7.0 Phase 3-B: BLData의 헤더/요약 필드를 document_bl에 보존.

        bl_data는 dict 또는 BLData 인스턴스. 둘 다 지원.
        raw_response/error_message/success/raw_text/containers/freight_charges는 저장하지 않음
        (containers는 Phase 3-A container_info 테이블이 1:N 저장 중).

        예외 suppression: 실패해도 본 입고 트랜잭션을 무효화하지 않음(logger.debug 내림).
        """
        if not bl_data:
            return

        def _get(obj, key, default=''):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        def _date_iso(v):
            if v in (None, ''):
                return None
            if hasattr(v, 'isoformat'):
                try:
                    return v.isoformat()[:10]
                except (ValueError, TypeError):
                    return None
            s = str(v).strip()
            return s[:10] if s else None

        def _ts_iso(v):
            if v in (None, ''):
                return None
            if hasattr(v, 'isoformat'):
                try:
                    return v.isoformat()
                except (ValueError, TypeError):
                    return None
            s = str(v).strip()
            return s if s else None

        bl_no = ''
        try:
            bl_no = str(_get(bl_data, 'bl_no', '') or '').strip()
            # ship_date가 없으면 shipped_on_board_date로 대체 (BLData 양쪽 필드 존재)
            ship_date_val = _get(bl_data, 'ship_date', None) or _get(bl_data, 'shipped_on_board_date', None)
            self.db.execute(
                """INSERT INTO document_bl
                   (lot_no, inventory_id,
                    bl_no, booking_no, carrier_id, carrier_name, scac, svc_contract, sap_no,
                    vessel, voyage,
                    shipper_name, shipper_address,
                    consignee_name, consignee_address, notify_party,
                    port_of_loading, port_of_discharge,
                    place_of_receipt, place_of_delivery, place_of_issue,
                    ship_date, issue_date,
                    product_name,
                    total_containers, total_packages,
                    net_weight_kg, gross_weight_kg, total_cbm,
                    freight_terms, total_freight_usd, total_freight_krw,
                    source_file, parsed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lot_no, inventory_id,
                    bl_no,
                    str(_get(bl_data, 'booking_no', '') or ''),
                    str(_get(bl_data, 'carrier_id', '') or ''),
                    str(_get(bl_data, 'carrier_name', '') or ''),
                    str(_get(bl_data, 'scac', '') or ''),
                    str(_get(bl_data, 'svc_contract', '') or ''),
                    str(_get(bl_data, 'sap_no', '') or ''),
                    str(_get(bl_data, 'vessel', '') or ''),
                    str(_get(bl_data, 'voyage', '') or ''),
                    str(_get(bl_data, 'shipper_name', '') or ''),
                    str(_get(bl_data, 'shipper_address', '') or ''),
                    str(_get(bl_data, 'consignee_name', '') or ''),
                    str(_get(bl_data, 'consignee_address', '') or ''),
                    str(_get(bl_data, 'notify_party', '') or ''),
                    str(_get(bl_data, 'port_of_loading', '') or ''),
                    str(_get(bl_data, 'port_of_discharge', '') or ''),
                    str(_get(bl_data, 'place_of_receipt', '') or ''),
                    str(_get(bl_data, 'place_of_delivery', '') or ''),
                    str(_get(bl_data, 'place_of_issue', '') or ''),
                    _date_iso(ship_date_val),
                    _date_iso(_get(bl_data, 'issue_date', None)),
                    str(_get(bl_data, 'product_name', '') or ''),
                    self._safe_parse_int(_get(bl_data, 'total_containers', 0)),
                    self._safe_parse_int(_get(bl_data, 'total_packages', 0)),
                    self._safe_parse_float(_get(bl_data, 'net_weight_kg', 0)),
                    self._safe_parse_float(_get(bl_data, 'gross_weight_kg', 0)),
                    self._safe_parse_float(_get(bl_data, 'total_cbm', 0)),
                    str(_get(bl_data, 'freight_terms', '') or ''),
                    self._safe_parse_float(_get(bl_data, 'total_freight_usd', 0)),
                    self._safe_parse_float(_get(bl_data, 'total_freight_krw', 0)),
                    str(_get(bl_data, 'source_file', '') or ''),
                    _ts_iso(_get(bl_data, 'parsed_at', None)),
                )
            )
            logger.info(
                f"[Phase3-B] document_bl 저장: lot={lot_no} bl={bl_no!r}"
            )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.debug(
                f"[document_bl] INSERT 스킵 (lot={lot_no}, bl={bl_no!r}): {e}"
            )
        except Exception as e:
            logger.debug(
                f"[document_bl] INSERT 스킵 (lot={lot_no}, bl={bl_no!r}): {e}"
            )

    def _insert_document_pl(self, lot_no, inventory_id, packing):
        """v8.7.0 Phase 3-B: PackingListData의 헤더/요약 필드를 document_pl에 보존.

        packing은 _prepare_lot_data가 정규화한 dict 또는 PackingListData 인스턴스.
        containers[]는 저장하지 않음 (컨테이너는 container_info 테이블이 관리).

        v8.7.0 [U-1 b]: lots[]를 JSON으로 직렬화하여 lots_json 컬럼에 보존
          - 감사·재파싱·역조회용. 개별 톤백 운영은 inventory_tonbag이 담당.
          - JSON 직렬화 실패 시 빈 문자열 저장(본 입고 블로킹 금지).

        예외 suppression: 실패해도 본 입고 트랜잭션을 무효화하지 않음.
        """
        if not packing:
            return

        def _get(obj, key, default=''):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        def _date_iso(v):
            if v in (None, ''):
                return None
            if hasattr(v, 'isoformat'):
                try:
                    return v.isoformat()[:10]
                except (ValueError, TypeError):
                    return None
            s = str(v).strip()
            return s[:10] if s else None

        def _ts_iso(v):
            if v in (None, ''):
                return None
            if hasattr(v, 'isoformat'):
                try:
                    return v.isoformat()
                except (ValueError, TypeError):
                    return None
            s = str(v).strip()
            return s if s else None

        # v8.7.0 [U-1 b]: lots[] → JSON 직렬화
        def _serialize_lots(lots_obj):
            """LOTInfo dataclass / dict 리스트를 JSON 문자열로 변환.
            실패 시 빈 문자열 반환 — 본 입고에 영향 없음.
            """
            if not lots_obj:
                return ''
            import json as _json
            from dataclasses import asdict as _asdict, is_dataclass as _is_dc
            try:
                serializable = []
                for lt in lots_obj:
                    if isinstance(lt, dict):
                        serializable.append(lt)
                    elif _is_dc(lt):
                        serializable.append(_asdict(lt))
                    elif hasattr(lt, '__dict__'):
                        serializable.append(vars(lt))
                    else:
                        # 알 수 없는 타입은 문자열로라도 보존
                        serializable.append({'raw': str(lt)})
                # date/datetime은 isoformat 문자열로 변환
                def _default(o):
                    if hasattr(o, 'isoformat'):
                        return o.isoformat()
                    return str(o)
                return _json.dumps(serializable, ensure_ascii=False, default=_default)
            except Exception as _e:
                logger.debug(f"[U-1 b] lots_json 직렬화 실패(빈값 저장): {_e}")
                return ''

        folio = ''
        try:
            folio = str(_get(packing, 'folio', '') or '').strip()
            # PackingListData는 header.arrival_date에 값이 있을 수 있음
            # GUI 정규화 dict은 packing['arrival_date']로 이미 받아옴
            arrival_date_val = _get(packing, 'arrival_date', None)
            if not arrival_date_val:
                # dataclass의 header 객체 fallback
                hdr = _get(packing, 'header', None)
                if hdr:
                    arrival_date_val = _get(hdr, 'arrival_date', None)
            # total_net_weight_kg 없으면 net_weight로 fallback (GUI packing_dict 호환)
            _net = _get(packing, 'total_net_weight_kg', 0) or _get(packing, 'net_weight', 0)
            _gross = _get(packing, 'total_gross_weight_kg', 0) or _get(packing, 'gross_weight', 0)
            _code = _get(packing, 'code', '') or _get(packing, 'product_code', '')
            # v8.7.0 [U-1 b]: lots[] 보존 — GUI는 `_pl_lots_raw`로 명시적 전달,
            #   엔진 직접 호출(paste 등)은 `lots` 또는 `rows` 사용
            _lots_raw = (
                _get(packing, '_pl_lots_raw', None)
                or _get(packing, 'lots', None)
                or _get(packing, 'rows', None)
                or []
            )
            _lots_json = _serialize_lots(_lots_raw)
            self.db.execute(
                """INSERT INTO document_pl
                   (lot_no, inventory_id,
                    folio, product, packing, code,
                    vessel, customer, destination,
                    bl_no, sap_no, arrival_date,
                    total_lots, total_net_weight_kg, total_gross_weight_kg,
                    total_maxibag, total_plastic_jars,
                    footer_note, lots_json,
                    source_file, parsed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lot_no, inventory_id,
                    folio,
                    str(_get(packing, 'product', '') or ''),
                    str(_get(packing, 'packing', '') or ''),
                    str(_code or ''),
                    str(_get(packing, 'vessel', '') or ''),
                    str(_get(packing, 'customer', '') or ''),
                    str(_get(packing, 'destination', '') or ''),
                    str(_get(packing, 'bl_no', '') or ''),
                    str(_get(packing, 'sap_no', '') or ''),
                    _date_iso(arrival_date_val),
                    self._safe_parse_int(_get(packing, 'total_lots', 0)),
                    self._safe_parse_float(_net),
                    self._safe_parse_float(_gross),
                    self._safe_parse_int(_get(packing, 'total_maxibag', 0) or _get(packing, 'mxbg_pallet', 0)),
                    self._safe_parse_int(_get(packing, 'total_plastic_jars', 0)),
                    str(_get(packing, 'footer_note', '') or ''),
                    _lots_json,
                    str(_get(packing, 'source_file', '') or ''),
                    _ts_iso(_get(packing, 'parsed_at', None)),
                )
            )
            logger.info(
                f"[Phase3-B] document_pl 저장: lot={lot_no} folio={folio!r} "
                f"lots_json={len(_lots_json)}bytes"
            )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.debug(
                f"[document_pl] INSERT 스킵 (lot={lot_no}, folio={folio!r}): {e}"
            )
        except Exception as e:
            logger.debug(
                f"[document_pl] INSERT 스킵 (lot={lot_no}, folio={folio!r}): {e}"
            )

    def _insert_document_do(self, lot_no, inventory_id, do_data):
        """v8.7.0 Phase 3-B: DOData의 헤더/요약 필드를 document_do에 보존.

        do_data는 dict 또는 DOData 인스턴스. 둘 다 지원.
        containers[]/free_time_info[]/raw_*/error_*는 저장하지 않음
        (Phase 3-A container_info / freetime_info 테이블이 1:N 저장 중).

        total_containers는 dataclass에 직접 필드가 없으므로 containers len()으로 계산.
        예외 suppression: 실패해도 본 입고 트랜잭션을 무효화하지 않음.
        """
        if not do_data:
            return

        def _get(obj, key, default=''):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        def _date_iso(v):
            if v in (None, ''):
                return None
            if hasattr(v, 'isoformat'):
                try:
                    return v.isoformat()[:10]
                except (ValueError, TypeError):
                    return None
            s = str(v).strip()
            return s[:10] if s else None

        def _ts_iso(v):
            if v in (None, ''):
                return None
            if hasattr(v, 'isoformat'):
                try:
                    return v.isoformat()
                except (ValueError, TypeError):
                    return None
            s = str(v).strip()
            return s if s else None

        do_no = ''
        try:
            do_no = str(_get(do_data, 'do_no', '') or '').strip()
            # total_containers: dataclass 직속 필드가 없으므로 containers[] 길이 fallback
            _total_containers = _get(do_data, 'total_containers', None)
            if _total_containers in (None, '', 0):
                _conts = _get(do_data, 'containers', []) or []
                try:
                    _total_containers = len(_conts) if hasattr(_conts, '__len__') else 0
                except (TypeError, AttributeError):
                    _total_containers = 0
            self.db.execute(
                """INSERT INTO document_do
                   (lot_no, inventory_id,
                    do_no, bl_no, sap_no, carrier_id,
                    vessel, voyage, flag,
                    port_of_loading, port_of_discharge, final_destination, place_of_delivery,
                    arrival_date, stock_date, issue_date,
                    warehouse_code, warehouse_name,
                    free_time, con_return,
                    total_containers, total_packages,
                    gross_weight_kg, measurement_cbm,
                    mrn, msn,
                    source_file, parsed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lot_no, inventory_id,
                    do_no,
                    str(_get(do_data, 'bl_no', '') or ''),
                    str(_get(do_data, 'sap_no', '') or ''),
                    str(_get(do_data, 'carrier_id', '') or ''),
                    str(_get(do_data, 'vessel', '') or ''),
                    str(_get(do_data, 'voyage', '') or ''),
                    str(_get(do_data, 'flag', '') or ''),
                    str(_get(do_data, 'port_of_loading', '') or ''),
                    str(_get(do_data, 'port_of_discharge', '') or ''),
                    str(_get(do_data, 'final_destination', '') or ''),
                    str(_get(do_data, 'place_of_delivery', '') or ''),
                    _date_iso(_get(do_data, 'arrival_date', None)),
                    _date_iso(_get(do_data, 'stock_date', None)),
                    _date_iso(_get(do_data, 'issue_date', None)),
                    str(_get(do_data, 'warehouse_code', '') or ''),
                    str(_get(do_data, 'warehouse_name', '') or ''),
                    self._safe_parse_int(_get(do_data, 'free_time', 0)),
                    str(_get(do_data, 'con_return', '') or _get(do_data, 'free_time_date', '') or ''),
                    self._safe_parse_int(_total_containers),
                    self._safe_parse_int(_get(do_data, 'total_packages', 0)),
                    self._safe_parse_float(_get(do_data, 'gross_weight_kg', 0)),
                    self._safe_parse_float(_get(do_data, 'measurement_cbm', 0)),
                    str(_get(do_data, 'mrn', '') or ''),
                    str(_get(do_data, 'msn', '') or ''),
                    str(_get(do_data, 'source_file', '') or ''),
                    _ts_iso(_get(do_data, 'parsed_at', None)),
                )
            )
            logger.info(
                f"[Phase3-B] document_do 저장: lot={lot_no} do={do_no!r}"
            )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            logger.debug(
                f"[document_do] INSERT 스킵 (lot={lot_no}, do={do_no!r}): {e}"
            )
        except Exception as e:
            logger.debug(
                f"[document_do] INSERT 스킵 (lot={lot_no}, do={do_no!r}): {e}"
            )


    # NOTE: process_inbound_safe, preflight_check_inbound
    #   → PreflightMixin으로 이관 완료 (v3.8.4 데드코드 정리)