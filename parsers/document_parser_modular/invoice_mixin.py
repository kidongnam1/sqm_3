# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - Invoice 파서 Mixin
=========================================

v9.0: Gemini API 완전 제거 — PyMuPDF 좌표 기반 파싱으로 전환

고객사(SQM SALAR SpA)가 단일이므로 양식이 항상 동일
→ 각 필드의 고정 좌표로 직접 추출 (API 비용 없음, 속도 빠름)

추출 항목:
    - Invoice No:   우상단 N° 번호
    - Date:         FECHA/DATE 오른쪽
    - SAP No:       Ref.SQM/Our Order 오른쪽
    - BL No:        BL-AWB-CRT Number 아래 + vessel로 선사코드 추론
    - Vessel:       Transporte/Transport 오른쪽
    - Origin:       Origen/Origin 오른쪽
    - Destination:  Destino/Destination 오른쪽
    - Quantity MT:  Cantidad 컬럼 숫자
    - Product Code: 제품코드 컬럼
    - Product Name: 제품명 컬럼
    - Unit Price:   Precio Unit 컬럼
    - Total Amount: Valor Total 컬럼
    - Net Weight:   KG Netos 오른쪽
    - Gross Weight: KG Bruto 오른쪽
    - LOT 목록:     N° LOTES: 다음 텍스트

작성자: Ruby (남기동)
버전: v9.0
"""

import logging
import re
from datetime import datetime
from typing import Optional, List

from core.types import safe_float
from ..document_models import InvoiceData

logger = logging.getLogger(__name__)
# ── SQM SALAR SpA 고정 상수 (고객 단일, 제품 단일) ──────────
_CUSTOMER_NAME  = "SOQUIMICH LLC"
_PRODUCT_NAME   = "LITHIUM CARBONATE - BATTERY GRADE - MICRONIZED"
_PRODUCT_CODE   = "MIC9000.00"
_CURRENCY       = "USD"
_SUPPLIER_NAME  = "SQM SALAR SpA"



# ── 선사명 → SCAC 코드 매핑 ────────────────────────────────
_VESSEL_TO_SCAC = {
    'MAERSK': 'MAEU',
    'MSC':    'MEDU',
    'COSCO':  'COSU',
    'CMA CGM':'CMDU',
    'HAPAG':  'HLCU',
    'HMM':    'HDMU',
    'ONE':    'ONEY',
    'EVERGREEN': 'EGLV',
    'YANG MING': 'YMLU',
    'PIL':    'PILU',
}
# DEAD CODE REMOVED v8.6.4: _get_scac_from_vessel()
# 사유: 전체 코드베이스에서 호출 없음 (2026-03-28 감사)
# 원본 9줄 제거


def _parse_euro_number(s: str) -> float:
    """유럽식 숫자 파싱: 1.573.034,54 → 1573034.54"""
    s = re.sub(r'[^\d,.]', '', str(s or ''))
    if not s:
        return 0.0
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _clean_package_type(s: str) -> str:
    """FA 포장명에서 줄바꿈/특수 공백/뒤쪽 구두점을 제거."""
    s = str(s or '').replace('\xa0', ' ')
    s = re.sub(r'\s+', ' ', s).strip(' ,;:')
    return s


class InvoiceMixin:
    """Invoice 파서 Mixin — v9.0 좌표 기반 완전 독립 파서."""

    def parse_invoice(self, pdf_path: str, **kwargs) -> Optional[InvoiceData]:
        """SQM SALAR SpA Invoice(FA) 좌표 기반 파싱.

        Gemini API 완전 제거. PyMuPDF로 PDF 좌표 직접 추출.
        고객사 단일(SQM SALAR SpA) → 양식 고정 → 좌표 고정.
        """
        logger.info(f"[INVOICE] 좌표 기반 파싱 시작: {pdf_path}")
        try:
            from core.pdf_engine import open_pdf
            doc  = open_pdf(pdf_path)
            page = doc[0]
            W    = page.rect.width
            H    = page.rect.height
            words_raw = page.get_text("words")
            # 전체 텍스트 (LOT 파싱용)
            full_text = page.get_text("text") or ""
            doc.close()
        except Exception as e:
            raise RuntimeError(f"[INVOICE] PDF 읽기 실패: {e}")

        words = [
            {'text': w[4], 'x0': float(w[0]), 'x1': float(w[2]),
             'top': float(w[1]), 'bottom': float(w[3])}
            for w in words_raw
        ]

        # ── 앵커 기반 드리프트 보정 (v10.0) ──────────────────────
        _FA_ANCHORS = {
            'FECHA/DATE':           (69.75, 21.45),
            'Ref.SQM/Our':          (76.68, 31.96),
            'Origen/Origin':        (56.13, 38.91),
            'Transporte/Transport': (53.24, 42.38),
            'BL-AWB-CRT':           (75.92, 42.38),
        }
        _dx_l, _dy_l = [], []
        for w in words:
            if w['text'] in _FA_ANCHORS:
                ex, ey = _FA_ANCHORS[w['text']]
                _dx_l.append(w['x0']/W*100 - ex)
                _dy_l.append(w['top']/H*100 - ey)
        if _dx_l:
            _dx_l.sort(); _dy_l.sort()
            _m = len(_dx_l)//2
            _dx, _dy = _dx_l[_m], _dy_l[_m]
        else:
            _dx, _dy = 0.0, 0.0
        logger.debug(f'[INVOICE] FA drift dx={_dx:+.3f}%  dy={_dy:+.3f}%')

        def by_xy(x1, x2, y1, y2, h_tol=0.8, v_tol=0.0) -> str:
            ax0 = x1+_dx-h_tol; ax1 = x2+_dx+h_tol
            ay0 = y1+_dy-v_tol; ay1 = y2+_dy+v_tol
            hits = sorted(
                [w for w in words
                 if ax0 <= w['x0']/W*100 <= ax1
                 and ay0 <= w['top']/H*100 <= ay1],
                key=lambda w: (w['top'], w['x0'])
            )
            return ' '.join(w['text'] for w in hits)

        # ── 필드 추출 ────────────────────────────────────────────

        # Invoice No: 우상단 N° 옆 숫자
        invoice_no = re.sub(r'[^\d]', '',
                             by_xy(74, 95, 11, 13))

        # Date: FECHA/DATE 오른쪽
        date_raw = re.sub(r'^[:\s]+', '',
                          by_xy(77, 95, 21, 23)).strip()
        # "31.01.2026" → "2026-01-31"
        invoice_date = ''
        dm = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', date_raw)
        if dm:
            invoice_date = f"{dm.group(3)}-{dm.group(2).zfill(2)}-{dm.group(1).zfill(2)}"

        # SAP No: Ref.SQM/Our Order 오른쪽
        sap_raw = by_xy(78, 95, 33, 35)
        sap_no  = re.sub(r'[^\d]', '', sap_raw)[:10]

        # Vessel: Transporte/Transport 오른쪽 (y=44.7%)
        vessel = by_xy(49, 73, 44, 46)

        # BL No: v8.4.5 수정 — 직접 추출 방식
        # 구방식: bl_digits(숫자만) + scac(vessel에서 추론) → HDMU963970 오파싱
        # 신방식: BL No 전체 직접 추출 → MEDUFP963970 정확 추출
        bl_raw_full = by_xy(77, 95, 44, 46)
        # 알파+숫자 형식(MEDUFP963970, 263764814 등) 직접 매칭
        bl_m = re.search(r'([A-Z]{2,12}\d{6,12}|\d{8,12})', bl_raw_full)
        bl_no = bl_m.group(1) if bl_m else re.sub(r'[^\dA-Z]', '', bl_raw_full)
        # v8.6.5: MAERSK 9자리 순수숫자 bl_no → MAEU 접두사 추가 (vessel명 기반)
        if re.fullmatch(r'\d{9}', bl_no or ''):
            vessel_upper = str(vessel or '').upper()
            for _vk, _sc in _VESSEL_TO_SCAC.items():
                if _vk in vessel_upper:
                    bl_no = f'{_sc}{bl_no}'
                    break

        # Origin / Destination
        origin      = by_xy(53, 73, 40, 42)
        destination = by_xy(74, 95, 40, 42)

        # Incoterm
        incoterm = by_xy(5, 15, 42, 44)

        # v8.5.6 [PATCH3-BUG2]: Quantity MT 좌표 수정
        # MSC FA 실측: y=48%, MAERSK FA도 동일 범위 커버
        qty_raw = by_xy(5, 22, 47, 51)
        # 숫자만 추출 (헤더 텍스트 제거)
        _qty_m = re.search(r'(\d{2,4}[,.]?\d{1,3})', qty_raw)
        quantity_mt = _parse_euro_number(_qty_m.group(1)) if _qty_m else 0.0

        # Product Code: x=27%
        prod_code = _PRODUCT_CODE  # v9.1: 고정 상수

        # Product Name: x=38~52%, y=49~52%
        # v9.1: 제품명/제품코드는 고정 상수 (SQM SALAR SpA 단일 제품)
        prod_name = _PRODUCT_NAME

        # Unit Price: x=68~78%
        unit_price = _parse_euro_number(by_xy(68, 78, 49, 51))

        # Total Amount: x=84~95%
        total_amount = _parse_euro_number(by_xy(84, 95, 49, 51))

        # v8.5.6 [PATCH3-BUG2]: Net/Gross Weight — 정규식 기반으로 교체
        # MSC FA 실측: "KG Netos/Net KG 120.024KG" / "Bruto/KG Gross 123.150"
        # 좌표 방식이 두 서류 레이아웃에서 불일치 → 정규식이 더 안정적
        _nw_m = re.search(r'Netos/Net\s*KG\s*(\d[\d.,]+)', full_text, re.IGNORECASE)
        if not _nw_m:
            _nw_m = re.search(r'KG\s*Netos[^\d]*(\d[\d.,]+)', full_text, re.IGNORECASE)
        nw_clean = _nw_m.group(1) if _nw_m else ''
        net_weight_kg = _parse_euro_number(nw_clean) * 1000 \
                        if _parse_euro_number(nw_clean) < 1000 \
                        else _parse_euro_number(nw_clean)

        _gw_m = re.search(r'Bruto/KG\s*Gross\s*(\d[\d.,]+)', full_text, re.IGNORECASE)
        if not _gw_m:
            _gw_m = re.search(r'KG\s*Gross\s*(\d[\d.,]+)', full_text, re.IGNORECASE)
        gw_clean = _gw_m.group(1) if _gw_m else ''
        gross_weight_kg = _parse_euro_number(gw_clean) * 1000 \
                          if _parse_euro_number(gw_clean) < 1000 \
                          else _parse_euro_number(gw_clean)

        # Package Count — 정규식 기반
        _pkg_m = re.search(r'Number\s*of\s*Packaging\s*(\d+)', full_text, re.IGNORECASE)
        try:
            package_count = int(_pkg_m.group(1)) if _pkg_m else 0
        except (ValueError, TypeError):
            package_count = 0

        # Package Type — 정규식 기반
        _pkgt_m = re.search(r'Type\s*of\s*(?:Packaging|Envase)[^\n]*\n?([^\n]{3,40})', full_text, re.IGNORECASE)
        package_type = _clean_package_type(_pkgt_m.group(1) if _pkgt_m else by_xy(80, 96, 71, 74))

        # LOT 목록: N° LOTES: 다음 텍스트 파싱
        lot_numbers: List[str] = []
        lot_section = re.search(
            r'N[°o]?\s*LOTES\s*:(.*?)(?=Monto|Banco|$)',
            full_text, re.DOTALL | re.IGNORECASE
        )
        if lot_section:
            lot_text = lot_section.group(1)
            lot_numbers = re.findall(r'(\d{8,11})/[\d,.]+T?', lot_text)  # v8.6.4

        # ── 결과 조립 ────────────────────────────────────────────
        result = InvoiceData()
        result.source_file      = pdf_path
        result.parsed_at        = datetime.now()
        result.customer_name  = _CUSTOMER_NAME
        if hasattr(result, "supplier"):
            result.supplier = _SUPPLIER_NAME
        result.invoice_no       = invoice_no
        result.salar_invoice_no = invoice_no
        result.invoice_date     = invoice_date
        result.sap_no           = sap_no
        result.bl_no            = bl_no
        result.vessel           = vessel
        result.origin           = origin
        result.destination      = destination
        result.incoterm         = incoterm
        result.product_code     = prod_code
        result.product_name     = prod_name
        result.quantity_mt      = quantity_mt
        result.unit_price       = unit_price
        result.total_amount     = total_amount
        result.currency         = 'USD'
        result.net_weight_kg    = net_weight_kg
        result.gross_weight_kg  = gross_weight_kg
        result.package_count    = package_count
        result.package_type     = package_type
        result.lot_numbers      = lot_numbers
        result.success          = bool(sap_no and invoice_no)
        result.error_message    = "" if result.success else "[INVOICE] invoice_no 또는 sap_no 미추출"

        logger.info(
            "[INVOICE] 좌표 파싱 완료: invoice=%s sap=%s bl=%s success=%s",
            invoice_no, sap_no, bl_no, result.success
        )

        # ── AI fallback (좌표 파싱 실패 시) ──────────────────────────────
        if not result.success:
            logger.warning("[INVOICE] 좌표 파싱 실패 → AI fallback 시도: %s", pdf_path)
            try:
                from .ai_fallback import parse_invoice_ai
                ai_result = parse_invoice_ai(
                    self, pdf_path,
                    partial=result,
                    carrier_id=kwargs.get("carrier_id", ""),
                    provider=kwargs.get("provider", "gemini"),
                )
                if ai_result and getattr(ai_result, "success", False):
                    logger.info("[INVOICE] AI fallback 성공: invoice=%s",
                                getattr(ai_result, "invoice_no", "?"))
                    return ai_result
                else:
                    logger.warning("[INVOICE] AI fallback도 실패")
            except Exception as ai_err:
                logger.warning("[INVOICE] AI fallback 오류: %s", ai_err)

        return result
