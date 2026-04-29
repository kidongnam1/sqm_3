# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - 통합 PDF 파서 (v2.5.4)
Packing List, Invoice, B/L, D/O 문서 자동 파싱

v2.5.4 개선:
- 파일명 기반 문서 유형 감지 우선
- 로깅 추가

Author: Ruby
Version: 2.5.4
"""

import re
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from core.pdf_engine import open_pdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


# =============================================================================
# 데이터 클래스 정의
# =============================================================================

@dataclass
class PackingListData:
    """Packing List 파싱 결과"""
    folio: str = ""
    product: str = ""
    product_code: str = ""
    packing: str = ""
    vessel: str = ""
    customer: str = ""
    destination: str = ""
    lots: List[Dict] = field(default_factory=list)
    total_net_weight: float = 0.0
    total_gross_weight: float = 0.0
    total_lots: int = 0
    source_file: str = ""
    parsed_at: datetime = None
    sap_no: str = ""              # v2.9.1: Invoice에서 추출한 SAP NO
    bl_no: str = ""               # v2.9.6: D/O에서 추출한 BL NO
    salar_invoice_no: str = ""    # v2.9.7: Invoice에서 추출한 Salar Invoice No
    arrival_date: date = None     # v2.9.7: D/O에서 추출한 입항일
    ship_date: date = None        # v2.9.7: Invoice에서 추출한 선적일


@dataclass
class InvoiceData:
    """Invoice 파싱 결과"""
    invoice_no: str = ""
    invoice_date: date = None
    customer: str = ""
    customer_code: str = ""
    product: str = ""
    product_code: str = ""
    quantity_mt: float = 0.0
    unit_price: float = 0.0
    total_amount: float = 0.0
    currency: str = "USD"
    incoterm: str = ""
    origin: str = ""
    destination: str = ""
    vessel: str = ""
    bl_no: str = ""
    sap_no: str = ""
    lots: List[str] = field(default_factory=list)
    source_file: str = ""
    parsed_at: datetime = None


@dataclass
class BLData:
    """B/L 파싱 결과"""
    bl_no: str = ""
    booking_no: str = ""
    shipper: str = ""
    consignee: str = ""
    notify_party: str = ""
    vessel: str = ""
    voyage: str = ""
    port_of_loading: str = ""
    port_of_discharge: str = ""
    ship_date: date = None
    issue_date: date = None
    containers: List[Dict] = field(default_factory=list)
    total_weight: float = 0.0
    total_packages: int = 0
    freight_charges: List[Dict] = field(default_factory=list)
    source_file: str = ""
    parsed_at: datetime = None


@dataclass
class DOData:
    """D/O 파싱 결과"""
    do_no: str = ""
    bl_no: str = ""
    shipper: str = ""
    consignee: str = ""
    vessel: str = ""
    voyage: str = ""
    port_of_loading: str = ""
    port_of_discharge: str = ""
    arrival_date: date = None
    issue_date: date = None
    containers: List[Dict] = field(default_factory=list)
    free_time_info: List[Dict] = field(default_factory=list)
    source_file: str = ""
    parsed_at: datetime = None


# =============================================================================
# PDF 파서 클래스
# =============================================================================

class PDFParser:
    """통합 PDF 파서"""

    def __init__(self):
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF가 설치되지 않았습니다: pip install pymupdf")
        self.errors = []

    def detect_document_type(self, pdf_path: str, use_gemini_fallback: bool = True) -> str:
        """
        PDF 문서 유형 자동 감지
        
        ★★★ v2.7.1: 3단계 통합 파이프라인 ★★★
        1단계: 파일명 패턴 (가장 빠르고 안정)
        2단계: PDF 텍스트 키워드 분석
        3단계: Gemini AI 판정 (옵션, fallback)

        파일명 패턴 예시:
        - 2200033057_FA.pdf → INVOICE (FA = Factura)
        - 2200033057_PackingList1.pdf → PACKING_LIST
        - 2200033057_BL.pdf → BL
        - MAEU258468669_DO.pdf → DO
        
        Returns:
            문서 유형: "PACKING_LIST", "INVOICE", "BL", "DO", "UNKNOWN"
        """
        detection_scores = {
            'PACKING_LIST': 0,
            'INVOICE': 0,
            'BL': 0,
            'DO': 0
        }
        # _detection_source removed (v6.2.7: unused)  # noqa: F841
        
        try:
            # ============================================
            # 1단계: 파일명 기반 감지 (가장 신뢰성 높음!)
            # ============================================
            filename = Path(pdf_path).stem.upper()

            # Invoice: _FA, FA_, INVOICE, INV
            if '_FA' in filename or 'FA_' in filename or 'INVOICE' in filename:
                logger.info(f"[문서감지] 1단계(파일명): INVOICE ({filename})")
                return "INVOICE"

            # B/L: _BL, BL_, B_L
            if '_BL' in filename or 'BL_' in filename or ' BL' in filename or 'BL ' in filename:
                logger.info(f"[문서감지] 1단계(파일명): BL ({filename})")
                return "BL"

            # D/O: _DO, DO_, D_O, MAEU/MSCU/HLCU 등 (컨테이너 SCAC 코드)
            scac_prefixes = ['MAEU', 'MSCU', 'HLCU', 'CMAU', 'OOLU', 'COSU', 'EGLV']
            if '_DO' in filename or 'DO_' in filename or ' DO' in filename:
                logger.info(f"[문서감지] 1단계(파일명): DO ({filename})")
                return "DO"
            if any(filename.startswith(scac) for scac in scac_prefixes):
                logger.info(f"[문서감지] 1단계(파일명-SCAC): DO ({filename})")
                return "DO"

            # Packing List: PACKING, PACKINGLIST, PL, PLIST (숫자 접미사 포함)
            # 예: PackingList1.pdf, PACKING_LIST.pdf, 2200033057_PL.pdf
            if ('PACKINGLIST' in filename or 'PACKING_LIST' in filename or 
                'PACKING' in filename or '_PL' in filename or 'PL_' in filename or
                'PLIST' in filename):
                logger.info(f"[문서감지] 1단계(파일명): PACKING_LIST ({filename})")
                return "PACKING_LIST"
            
            # 숫자 접미사 패턴 (PACKINGLIST1, PACKING1 등)
            import re
            if re.search(r'PACKING\s*LIST\d*', filename) or re.search(r'PACKING\d+', filename):
                logger.info(f"[문서감지] 1단계(파일명-정규식): PACKING_LIST ({filename})")
                return "PACKING_LIST"

            # ============================================
            # 2단계: 텍스트 기반 감지 (키워드 점수)
            # ============================================
            doc = None
            try:
                doc = open_pdf(pdf_path)
                text = ""
                for page in doc:
                    text += page.get_text()
            finally:
                if doc:
                    doc.close()

            text_upper = text.upper().replace('\xa0', ' ')  # non-breaking space 처리

            # 텍스트가 거의 없으면 이미지 PDF (D/O 가능성 높음)
            if len(text.strip()) < 100:
                logger.info(f"[문서감지] 2단계(텍스트): 텍스트 적음 → DO 추정 ({filename})")
                detection_scores['DO'] += 10
            else:
                # Invoice 키워드 점수
                invoice_keywords = ["FACTURA", "EXPORT INVOICE", "COMMERCIAL INVOICE",
                                   "UNIT PRICE USD", "TOTAL AMOUNT USD", "FOB VALUE", "SAP NO"]
                invoice_score = sum(2 for kw in invoice_keywords if kw in text_upper)
                detection_scores['INVOICE'] += invoice_score
                
                # B/L 키워드 점수
                bl_keywords = ["NON-NEGOTIABLE WAYBILL", "BILL OF LADING", "BOOKING NO",
                              "SHIPPER:", "CONSIGNEE:", "NOTIFY PARTY:", "SHIPPED ON BOARD"]
                bl_score = sum(2 for kw in bl_keywords if kw in text_upper)
                detection_scores['BL'] += bl_score
                
                # D/O 키워드 점수
                do_keywords = ["DELIVERY ORDER", "발급확인서", "FREE TIME", "화물인도지시서", "컨테이너"]
                do_score = sum(2 for kw in do_keywords if kw in text_upper or kw in text)
                detection_scores['DO'] += do_score
                
                # Packing List 키워드 점수
                packing_keywords = ["PACKING LIST", "PACKINGLIST", "FOLIO:", "LOT NO",
                                   "NET WEIGHT", "GROSS WEIGHT", "MAXIBAG", "MX 500", "MX500", "MXBG"]
                packing_score = sum(2 for kw in packing_keywords if kw in text_upper)
                detection_scores['PACKING_LIST'] += packing_score

            # 2단계 결과 판정
            max_score = max(detection_scores.values())
            if max_score >= 4:  # 최소 2개 이상 키워드 매칭
                best_type = max(detection_scores, key=detection_scores.get)
                logger.info(f"[문서감지] 2단계(텍스트): {best_type} (점수: {detection_scores})")
                return best_type

            # ============================================
            # 3단계: Gemini AI 판정 (fallback, 옵션)
            # ============================================
            if use_gemini_fallback and max_score < 4:
                try:
                    from gemini_parser import GeminiDocumentParser
                    from core.config import GEMINI_API_KEY
                    
                    if GEMINI_API_KEY and GEMINI_API_KEY != 'your-api-key-here':
                        gemini = GeminiDocumentParser(GEMINI_API_KEY)
                        
                        # Gemini에게 문서 유형 질문
                        gemini_type = gemini.detect_document_type(pdf_path)
                        
                        if gemini_type and gemini_type != "UNKNOWN":
                            logger.info(f"[문서감지] 3단계(Gemini): {gemini_type} ({filename})")
                            return gemini_type
                            
                except (ImportError, ModuleNotFoundError) as gemini_error:
                    logger.warning(f"[문서감지] Gemini fallback 실패: {gemini_error}")

            # 모든 단계 실패
            logger.warning(f"[문서감지] 알 수 없음: {filename} (점수: {detection_scores})")
            return "UNKNOWN"

        except (ValueError, TypeError, AttributeError) as e:
            self.errors.append(f"문서 유형 감지 실패: {str(e)}")
            logger.error(f"[문서감지] 오류: {e}")
            return "UNKNOWN"

    def parse(self, pdf_path: str, doc_type: str = None) -> Any:
        """PDF 파싱 (자동 또는 지정된 유형으로)"""
        if doc_type is None:
            doc_type = self.detect_document_type(pdf_path)

        if doc_type == "PACKING_LIST":
            return self.parse_packing_list(pdf_path)
        elif doc_type == "INVOICE":
            return self.parse_invoice(pdf_path)
        elif doc_type == "BL":
            return self.parse_bl(pdf_path)
        elif doc_type == "DO":
            return self.parse_do(pdf_path)
        else:
            self.errors.append(f"알 수 없는 문서 유형: {doc_type}")
            return None

    def _extract_text(self, pdf_path: str) -> str:
        """PDF에서 텍스트 추출 (v2.9.40: 안전한 파일 핸들링)"""
        doc = None
        try:
            doc = open_pdf(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        finally:
            if doc:
                doc.close()

    # =========================================================================
    # Packing List 파서
    # =========================================================================

    def parse_packing_list(self, pdf_path: str) -> Optional[PackingListData]:
        """Packing List PDF 파싱 (v2.5.4 - 상세 로깅)"""
        try:
            text = self._extract_text(pdf_path)
            result = PackingListData()
            result.source_file = pdf_path
            result.parsed_at = datetime.now()

            # 디버그 로그
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[PACKING LIST] 파싱 시작: {pdf_path}")
            logger.debug(f"[PACKING LIST] 텍스트 길이: {len(text)}")
            logger.debug(f"[PACKING LIST] 텍스트 미리보기: {text[:500]}...")

            # Folio 추출
            folio_match = re.search(r'Folio\s*:?\s*(\d{7})', text, re.IGNORECASE)
            if folio_match:
                result.folio = folio_match.group(1)
                logger.info(f"[PACKING LIST] Folio 찾음: {result.folio}")
            else:
                # 대체 패턴
                folio_match = re.search(r'(\d{7})', text[:500])
                if folio_match:
                    result.folio = folio_match.group(1)
                    logger.info(f"[PACKING LIST] Folio (대체): {result.folio}")
                else:
                    logger.warning("[PACKING LIST] Folio 못 찾음!")

            # 제품 추출
            if "LITHIUM CARBONATE" in text.upper():
                result.product = "LITHIUM CARBONATE"
                if "BATTERY GRADE" in text.upper():
                    result.product += " - BATTERY GRADE"
                if "MICRONIZED" in text.upper():
                    result.product += " - MICRONIZED"
                logger.info(f"[PACKING LIST] 제품: {result.product}")

            # 제품 코드 추출 (개선: MIC9000.00 패턴 인식)
            code_patterns = [
                r'(MIC\d{4})',  # MIC9000
                r'(CRY\d{4})',  # CRY9000
                r'CODE\s*:?\s*(MIC\d+)',  # CODE: MIC9000
                r'CODE\s*:?\s*([A-Z]{3}\d{4})',
            ]
            for pattern in code_patterns:
                code_match = re.search(pattern, text.upper())
                if code_match:
                    result.product_code = code_match.group(1)
                    logger.info(f"[PACKING LIST] 제품코드: {result.product_code}")
                    break

            # 기본값 설정 (Lithium Carbonate + 코드 못 찾으면)
            if not result.product_code and "LITHIUM CARBONATE" in text.upper():
                result.product_code = "MIC9000"  # 기본 코드
                logger.info(f"[PACKING LIST] 제품코드 (기본값): {result.product_code}")

            # 포장 정보 추출 (MIC9000.00/500 KG)
            packing_match = re.search(r'(MIC\d+\.?\d*/?\.?\d*\s*KG)', text, re.IGNORECASE)
            if packing_match:
                result.packing = packing_match.group(1)

            # 선박 추출
            vessel_match = re.search(r'([A-Z]+\s+MAERSK\s+\d+\w*)', text, re.IGNORECASE)
            if vessel_match:
                result.vessel = vessel_match.group(1)

            # 고객 추출
            if "SOQUIMICH" in text.upper():
                result.customer = "SOQUIMICH LLC"

            # 목적지 추출
            dest_match = re.search(r'DESTINATION\s*:?\s*(\w+)', text, re.IGNORECASE)
            if dest_match:
                result.destination = dest_match.group(1)
            elif "GWANGYANG" in text.upper():
                result.destination = "GWANGYANG"

            # 컨테이너 및 LOT 추출
            result.lots = self._extract_lots_from_packing_list(text)
            result.total_lots = len(result.lots)
            logger.info(f"[PACKING LIST] LOT 추출: {result.total_lots}개")

            if result.total_lots == 0:
                logger.warning("[PACKING LIST] ⚠️ LOT 0개! PDF가 이미지 기반일 수 있음")
                # Gemini API 사용 제안
                logger.info("[PACKING LIST] Gemini API 파싱 시도 권장")

            # 총 중량 계산
            if result.lots:
                result.total_net_weight = sum(lot.get('net_weight', 0) for lot in result.lots)
                result.total_gross_weight = sum(lot.get('gross_weight', 0) for lot in result.lots)
            else:
                # 대체 추출
                net_match = re.search(r'(\d{2,3}[,.]?\d{3})\s*KG\s*Net', text, re.IGNORECASE)
                if net_match:
                    result.total_net_weight = float(net_match.group(1).replace(',', '').replace('.', ''))

            return result

        except (ValueError, TypeError, KeyError) as e:
            self.errors.append(f"Packing List 파싱 오류: {str(e)}")
            import logging
            logging.getLogger(__name__).error(f"[PACKING LIST] 오류: {e}")
            return None

    def _extract_lots_from_packing_list(self, text: str) -> List[Dict]:
        """Packing List LOT 정보 추출 — v865: PDF 실제 중량 추출 (유럽식 숫자 지원)
        
        행 구조: {순번} {컨테이너} {NET/lot} {GROSS/lot} {누적NET} {누적GROSS} {LOT번호} {LOT_SQM} {MXBG}
        예: 1 FFAU535500-6 5.001 5.131,250 5.001 5.131,250 1125081447 977878 10
        유럽식: 5.001 = 5,001 kg / 5.131,250 = 5,131.25 kg
        """
        import logging
        logger = logging.getLogger(__name__)

        def parse_eu_number(s: str) -> float:
            """유럽식 숫자 → float: 5.001→5001.0 / 5.131,250→5131.25"""
            s = s.strip()
            if ',' in s:
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace('.', '')
            try:
                return float(s)
            except ValueError:
                return 0.0

        lots = []

        # ── Tier-A: 행 구조 패턴 (실제 중량 추출) ──────────────────────────
        row_pattern = re.compile(
            r'\b(\d{1,3})\s+'              # 순번
            r'([A-Z]{4}\d{6,7}-?\d?)\s+'  # 컨테이너 번호
            r'([\d.,]+)\s+'                 # NET WEIGHT per lot
            r'([\d.,]+)\s+'                 # GROSS WEIGHT per lot
            r'[\d.,]+\s+'                   # 누적 NET (skip)
            r'[\d.,]+\s+'                   # 누적 GROSS (skip)
            r'(\d{8,11})\s+'                # LOT N°
            r'(\d+)\s+'                     # LOT SQM
            r'(\d+)',                        # MXBG/PALLET
            re.DOTALL
        )

        seen_lots = set()
        for m in row_pattern.finditer(text):
            lot_no = m.group(5)
            if lot_no in seen_lots:
                continue
            seen_lots.add(lot_no)
            lots.append({
                'lot_no':      lot_no,
                'container_no': m.group(2),
                'net_weight':  parse_eu_number(m.group(3)),
                'gross_weight': parse_eu_number(m.group(4)),
                'lot_sqm':     m.group(6),
                'mxbg_pallet': int(m.group(7)),
                'plastic_jars': 1,
            })

        if lots:
            logger.info(f"[PACKING LIST] Tier-A 행패턴 추출: {len(lots)}개 LOT (실제 중량 포함)")
            return lots

        # ── Tier-B: 폴백 — LOT/컨테이너만 추출 (이미지 PDF 등) ─────────────
        logger.warning("[PACKING LIST] Tier-A 실패 → Tier-B 폴백 (중량 0, Gemini 폴백 권장)")
        container_pattern = r'([A-Z]{4}\d{6,7}-?\d?)'
        containers = re.findall(container_pattern, text)
        unique_containers = list(dict.fromkeys(containers))

        lot_pattern = r'\b(\d{8,11})\b'
        lot_numbers = re.findall(lot_pattern, text)
        unique_lots = list(dict.fromkeys(lot_numbers))

        for i, lot_no in enumerate(unique_lots):
            container = unique_containers[i % len(unique_containers)] if unique_containers else ""
            lots.append({
                'lot_no':      lot_no,
                'container_no': container,
                'net_weight':  0.0,
                'gross_weight': 0.0,
                'mxbg_pallet': 0,
                'plastic_jars': 1,
            })

        return lots


    # =========================================================================
    # Invoice 파서
    # =========================================================================

    def parse_invoice(self, pdf_path: str) -> Optional[InvoiceData]:
        """Invoice PDF 파싱"""
        try:
            text = self._extract_text(pdf_path)
            result = InvoiceData()
            result.source_file = pdf_path
            result.parsed_at = datetime.now()

            # Invoice 번호 추출
            inv_match = re.search(r'N[°o]\s*(\d{5})', text)
            if inv_match:
                result.invoice_no = inv_match.group(1)

            # 날짜 추출
            date_match = re.search(r'FECHA/DATE\s*:?\s*(\d{2}\.\d{2}\.\d{4})', text, re.IGNORECASE)
            if date_match:
                try:
                    result.invoice_date = datetime.strptime(date_match.group(1), '%d.%m.%Y').date()
                except (ValueError, TypeError, KeyError) as e:  # 날짜 파싱 실패 무시
                    logger.debug(f"[pdf_parser] 무시: {e}")

            # 고객 정보
            if "SOQUIMICH" in text.upper():
                result.customer = "SOQUIMICH LLC"

            customer_code_match = re.search(r'Cliente/Customer\s*(\d+)', text)
            if customer_code_match:
                result.customer_code = customer_code_match.group(1)

            # 제품 정보
            if "LITHIUM CARBONATE" in text.upper():
                result.product = "LITHIUM CARBONATE - BATTERY GRADE - MICRONIZED"
                result.product_code = "MIC9000.00"

            # 수량 추출
            qty_match = re.search(r'(\d{2,3}[,.]?\d{2})\s*T\s*MIC', text)
            if qty_match:
                qty_str = qty_match.group(1).replace(',', '.')
                result.quantity_mt = float(qty_str)

            # 단가 추출
            price_match = re.search(r'(\d{1,2}[,.]?\d{3}[,.]?\d{2})\s*(?:USD)?', text)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                if '.' not in price_str:
                    price_str = price_str[:-2] + '.' + price_str[-2:]
                result.unit_price = float(price_str)

            # 총 금액 추출
            amount_match = re.search(r'(\d{3}[,.]?\d{3}[,.]?\d{2})\s*(?:USD)?', text)
            if amount_match:
                amount_str = amount_match.group(1).replace(',', '')
                if '.' not in amount_str:
                    amount_str = amount_str[:-2] + '.' + amount_str[-2:]
                result.total_amount = float(amount_str)

            # Incoterm
            if "CIF" in text:
                result.incoterm = "CIF"
            elif "FOB" in text:
                result.incoterm = "FOB"

            # 출발지/도착지
            origin_match = re.search(r'Origen/Origin\s*(\w+)', text, re.IGNORECASE)
            if origin_match:
                result.origin = origin_match.group(1)

            dest_match = re.search(r'Destino/Destination\s*(\w+)', text, re.IGNORECASE)
            if dest_match:
                result.destination = dest_match.group(1)

            # 선박
            vessel_match = re.search(r'([A-Z]+\s+MAERSK\s+\d+\w*)', text, re.IGNORECASE)
            if vessel_match:
                result.vessel = vessel_match.group(1)

            # B/L 번호
            bl_match = re.search(r'BL.*?([A-Z]{0,4}\d{6,12})', text, re.IGNORECASE)  # v8.2.4: 알파숫자 확장
            if bl_match:
                result.bl_no = bl_match.group(1)

            # ★★★ v2.9.5: SAP 번호 추출 강화 ★★★
            sap_patterns = [
                r'\b(22\d{8})\b',      # 22로 시작하는 10자리
                r'\b(2200\d{6})\b',    # 2200으로 시작하는 10자리
            ]
            for pattern in sap_patterns:
                sap_match = re.search(pattern, text)
                if sap_match:
                    result.sap_no = sap_match.group(1)
                    break

            # LOT 번호들 추출 (10자리 숫자) - v2.9.0: 112 시작 조건 제거
            lot_pattern = r'\b(\d{8,11})\b'  # v8.6.4: 8~11자리
            result.lots = list(dict.fromkeys(re.findall(lot_pattern, text)))

            return result

        except (ValueError, KeyError, TypeError) as e:
            self.errors.append(f"Invoice 파싱 오류: {str(e)}")
            return None

    # =========================================================================
    # B/L 파서
    # =========================================================================

    # =========================================================================
    # 날짜 정규화 유틸 (v8.0.9: MSC/Maersk 공통)
    # =========================================================================
    @staticmethod
    def _normalize_date(date_str: str):
        """
        다양한 날짜 형식 → date 객체 변환.
        지원: 2026-01-29 / 29-Jan-2026 / 29/01/2026 / Jan 29, 2026
        실패 시 None 반환.
        """
        if not date_str:
            return None
        date_str = date_str.strip()
        _MONTH_MAP = {
            'jan':'01','feb':'02','mar':'03','apr':'04',
            'may':'05','jun':'06','jul':'07','aug':'08',
            'sep':'09','oct':'10','nov':'11','dec':'12',
        }
        # "29-Jan-2026"
        m = re.match(r'(\d{1,2})-([A-Za-z]{3})-(\d{4})', date_str)
        if m:
            d, mon, y = m.group(1), m.group(2).lower(), m.group(3)
            if mon in _MONTH_MAP:
                date_str = f"{y}-{_MONTH_MAP[mon]}-{int(d):02d}"
        # "Jan 29, 2026"
        m = re.match(r'([A-Za-z]{3})\s+(\d{1,2}),?\s+(\d{4})', date_str)
        if m:
            mon, d, y = m.group(1).lower(), m.group(2), m.group(3)
            if mon in _MONTH_MAP:
                date_str = f"{y}-{_MONTH_MAP[mon]}-{int(d):02d}"
        # "29/01/2026" 또는 "29.01.2026"
        m = re.match(r'(\d{1,2})[/.](\d{1,2})[/.](\d{4})', date_str)
        if m:
            date_str = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except (ValueError, TypeError) as _e:
                logger.debug(f"[SUPPRESSED] exception in pdf_parser.py: {_e}")  # noqa
        logger.debug("[pdf_parser] 날짜 정규화 실패: %s", date_str)
        return None

    # =========================================================================
    # 선사 자동 감지 (v8.0.9)
    # =========================================================================
    @staticmethod
    def _detect_carrier(text: str) -> str:
        """1페이지 텍스트로 선사 자동 감지. MSC/MAERSK/HMM/CMA_CGM/ONE/UNKNOWN"""
        t = text.upper()
        if 'MEDITERRANEAN SHIPPING COMPANY' in t or 'SEA WAYBILL No.' in t.replace('SEA WAYBILL NO.','SEA WAYBILL No.'):
            return 'MSC'
        if 'MAERSK' in t or 'SCAC MAEU' in t or 'NON-NEGOTIABLE WAYBILL' in t:
            return 'MAERSK'
        if 'HYUNDAI MERCHANT MARINE' in t or 'HMM CO.' in t:
            return 'HMM'
        if 'CMA CGM' in t or 'COMPAGNIE GENERALE MARITIME' in t:
            return 'CMA_CGM'
        if 'OCEAN NETWORK EXPRESS' in t:
            return 'ONE'
        return 'UNKNOWN'

    # =========================================================================
    # B/L 파서 — 멀티캐리어 (v8.0.9)
    # =========================================================================
    def parse_bl(self, pdf_path: str, gemini_hint: str = "", bl_format: str = "") -> Optional[BLData]:
        """
        B/L PDF 파싱 — 멀티캐리어 지원 (v8.0.9).
        MSC / Maersk 직접 파싱 + HMM/CMA/ONE 공통 fallback.
        date_normalizer 공통화: 29-Jan-2026 형식 지원.
        """
        try:
            text = self._extract_text(pdf_path)
            result = BLData()
            result.source_file = pdf_path
            result.parsed_at = datetime.now()

            carrier = self._detect_carrier(text)
            logger.debug("[parse_bl] 감지 선사: %s / %s", carrier, pdf_path)

            # ── 공통: Shipper / Consignee / POD ──────────────────
            if "SQM SALAR" in text.upper():
                result.shipper = "SQM SALAR SpA."
            if "SOQUIMICH" in text.upper():
                result.consignee = "SOQUIMICH LLC"
                result.notify_party = "SOQUIMICH"
            if "GWANGYANG" in text.upper():
                result.port_of_discharge = "GWANGYANG, SOUTH KOREA"
            elif "BUSAN" in text.upper():
                result.port_of_discharge = "BUSAN, SOUTH KOREA"

            # SAP NO 감지 (저장 필드 없음 → 로그만)
            sap_m = re.search(r'(2200\d{6})', text)
            if sap_m:
                logger.debug("[parse_bl] SAP NO 감지(미저장): %s", sap_m.group(1))

            # ═══════════════ MSC 전용 ═══════════════════════════
            if carrier == 'MSC':
                # BL No: MEDUFP963970 형식 (알파4+알파0~2+숫자6)
                bl_m = re.search(
                    r'SEA\s+WAYBILL\s+No\.?\s+([A-Z]{4}[A-Z0-9]{2,6}\d{4,8})',
                    text, re.IGNORECASE)
                if not bl_m:
                    bl_m = re.search(
                        r'(?:SEA WAYBILL|WAYBILL)\s+(?:No\.?|NUMBER)\s*[:\s]+([A-Z]{4}[A-Z0-9]{0,4}\d{4,8})',
                        text, re.IGNORECASE)
                if bl_m:
                    result.bl_no = bl_m.group(1).strip()

                # Booking Ref: EBKG15374163
                # MSC 형식: 'BOOKING REF. (or) SHIPPER'S REF.\nEBKG15374163'
                booking_m = re.search(
                    r'BOOKING\s+REF[^\n]*\n\s*([A-Z0-9]{8,20})',
                    text, re.IGNORECASE)
                if booking_m:
                    result.booking_no = booking_m.group(1).strip()

                # 선박명 + Voyage + POL: VESSEL AND VOYAGE NO 다음 줄에 같이 있음
                # 예: "HMM BLESSING - 0037W Puerto Angamos, Chile XXXXXXXXXXXXXXXX"
                vessel_line_m = re.search(
                    r'VESSEL AND VOYAGE NO[^\n]*\n([^\n]+)',
                    text, re.IGNORECASE)
                if vessel_line_m:
                    vessel_line = vessel_line_m.group(1).strip()
                    # 선박명+항차: "HMM BLESSING - 0037W" 패턴
                    vn_m = re.match(r'([A-Z][A-Z0-9 ]+-\s*\d{3,4}[A-Z]?)', vessel_line)
                    if vn_m:
                        v_full = vn_m.group(1).strip()
                        voy_m2 = re.search(r'-\s*(\d{3,4}[A-Z]?)\s*$', v_full)
                        if voy_m2:
                            result.voyage = voy_m2.group(1).strip()
                            result.vessel = v_full[:v_full.rfind('-')].strip()
                        else:
                            result.vessel = v_full
                        # POL: 선박명 뒤 텍스트에서 추출
                        after_vessel = vessel_line[len(vn_m.group(0)):].strip()
                        pol_m2 = re.match(r'([A-Za-z][A-Za-z\s,]+?)(?:\s+X{5,}|$)', after_vessel)
                        if pol_m2:
                            result.port_of_loading = pol_m2.group(1).strip()
                else:
                    # 보조: 알려진 선사 패턴
                    vessel_m = re.search(
                        r'(HMM\s+[A-Z ]+|EVER\s+[A-Z ]+|MSC\s+[A-Z ]+)',
                        text, re.IGNORECASE)
                    if vessel_m:
                        result.vessel = vessel_m.group(1).strip()

                if not result.port_of_loading and "Puerto Angamos" in text:
                    result.port_of_loading = "Puerto Angamos, Chile"

                # Ship Date + Issue Date
                # 실제 구조: PLACE AND DATE OF ISSUE / SHIPPED ON BOARD DATE 같은 줄
                # MSC CHILE (발행지)
                # 29-Jan-2026  (Shipped on Board)
                # 30-Jan-2026  (Issue Date)
                dates_m = re.search(
                    r'(?:PLACE AND DATE OF ISSUE|SHIPPED ON BOARD)[^\n]*\n'
                    r'[^\n]*\n'
                    r'(\d{1,2}-[A-Za-z]{3}-\d{4})\n'
                    r'(\d{1,2}-[A-Za-z]{3}-\d{4})',
                    text, re.IGNORECASE)
                if dates_m:
                    result.ship_date  = self._normalize_date(dates_m.group(1))
                    result.issue_date = self._normalize_date(dates_m.group(2))
                else:
                    # 단일 날짜 fallback
                    ship_m = re.search(
                        r'(\d{1,2}-[A-Za-z]{3}-\d{4})',
                        text, re.IGNORECASE)
                    if ship_m:
                        result.ship_date = self._normalize_date(ship_m.group(1))

                # 총 중량: "123150.000 Kgs."
                weight_m = re.search(
                    r'Total\s+(?:Gross\s+)?Weight\s*:?\s*([\d,]+\.?\d*)\s*[Kk]gs?\.?',
                    text, re.IGNORECASE)
                if weight_m:
                    result.total_weight = float(weight_m.group(1).replace(',', ''))

                # 총 패키지: "Total Items : 264"
                pkg_m = re.search(r'Total\s+Items?\s*:?\s*(\d+)', text, re.IGNORECASE)
                if pkg_m:
                    result.total_packages = int(pkg_m.group(1))

            # ═══════════════ Maersk 전용 ════════════════════════
            elif carrier == 'MAERSK':
                bl_m = re.search(r'B/L[:\s]*No\.?\s*([A-Z]{0,4}[A-Z0-9]{7,15})', text, re.IGNORECASE)  # v8.2.4
                if bl_m:
                    result.bl_no = bl_m.group(1)
                else:
                    bl_m = re.search(r'B/L:\s*([A-Z]{0,4}[A-Z0-9]{7,15})', text)  # v8.2.4
                    if bl_m:
                        result.bl_no = bl_m.group(1)

                booking_m = re.search(r'Booking\s*No\.?\s*(\d{9})', text, re.IGNORECASE)
                if booking_m:
                    result.booking_no = booking_m.group(1)
                    if not result.bl_no:
                        result.bl_no = booking_m.group(1)

                vessel_m = re.search(r'([A-Z]+\s+MAERSK)', text, re.IGNORECASE)
                if vessel_m:
                    result.vessel = vessel_m.group(1).upper()

                voy_m = re.search(r'Voyage\s*No\.?\s*\n?\s*(\d+\w*)', text, re.IGNORECASE)
                if voy_m:
                    result.voyage = voy_m.group(1)

                pol_m = re.search(r'Port of Loading\s*\n?\s*([\w\s,]+?)(?:\n|Place)', text, re.IGNORECASE)
                if pol_m:
                    result.port_of_loading = pol_m.group(1).strip()
                elif "Puerto Angamos" in text:
                    result.port_of_loading = "Puerto Angamos, Chile"

                ship_m = re.search(r'Shipped on Board.*?(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE | re.DOTALL)
                if ship_m:
                    result.ship_date = self._normalize_date(ship_m.group(1))

                issue_m = re.search(r'Date Issue.*?(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE | re.DOTALL)
                if issue_m:
                    result.issue_date = self._normalize_date(issue_m.group(1))

                # 컨테이너: ML-CL Seal 패턴
                containers = re.findall(
                    r'([A-Z]{4}\d{7})\s+(ML-[A-Z]{2}\d{7})\s+(\d+\s+DRY\s+\d+[\'"]?\d*)', text)
                for cont in containers:
                    result.containers.append({
                        'container_no': cont[0], 'seal_no': cont[1], 'type': cont[2].strip()
                    })

                weight_m = re.search(r'(\d{2,3}[,.]?\d{3})\s*KG\s*(?:Net|NET)', text, re.IGNORECASE)
                if weight_m:
                    result.total_weight = float(weight_m.group(1).replace(',','').replace('.',''))

            # ═══════════════ 공통 fallback ═══════════════════════
            else:
                bl_m = re.search(
                    r'B(?:/L|ILL OF LADING)\s*(?:No\.?|NUMBER|:)\s*([A-Z0-9]{6,20})',
                    text, re.IGNORECASE)
                if bl_m:
                    result.bl_no = bl_m.group(1)

                vessel_m = re.search(
                    r'(?:Vessel|Ship)\s*(?:Name)?\s*[:\n]\s*([A-Z][A-Z0-9 \-]{3,40})',
                    text, re.IGNORECASE)
                if vessel_m:
                    result.vessel = vessel_m.group(1).strip()

                pol_m = re.search(r'Port of Loading\s*[:\n]\s*([\w\s,]{5,50})', text, re.IGNORECASE)
                if pol_m:
                    result.port_of_loading = pol_m.group(1).strip()

                date_m = re.search(
                    r'(?:Ship|Board|On Board)[^\n]*'
                    r'(\d{1,2}[-/]\w{2,10}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})',
                    text, re.IGNORECASE)
                if date_m:
                    result.ship_date = self._normalize_date(date_m.group(1))

                weight_m = re.search(r'(?:GROSS|NET|TOTAL).*?([\d,]+\.?\d*)\s*[Kk][Gg]s?', text, re.IGNORECASE)
                if weight_m:
                    try:
                        result.total_weight = float(weight_m.group(1).replace(',',''))
                    except (ValueError, TypeError) as _e:
                        logger.debug(f"[SUPPRESSED] exception in pdf_parser.py: {_e}")  # noqa

            # ── 컨테이너 수 백업 ──────────────────────────────────
            if not result.containers and not result.total_packages:
                cnt_m = re.search(r'(\d+)\s*(?:x\s*)?containers?', text, re.IGNORECASE)
                if cnt_m:
                    result.total_packages = int(cnt_m.group(1))

            logger.debug(
                "[parse_bl] carrier=%s bl_no=%s vessel=%s pol=%s pod=%s ship_date=%s weight=%.1f",
                carrier, result.bl_no, result.vessel,
                result.port_of_loading, result.port_of_discharge,
                result.ship_date, result.total_weight
            )
            return result

        except (ValueError, TypeError, KeyError) as e:
            self.errors.append(f"B/L 파싱 오류: {str(e)}")
            logger.debug("[parse_bl] 예외: %s", e)
            return None

    # =========================================================================

    def parse_do(self, pdf_path: str) -> Optional[DOData]:
        """
        D/O PDF 파싱

        참고: D/O는 종종 이미지 PDF로 제공되어 OCR이 필요할 수 있습니다.
        텍스트가 추출되지 않는 경우 기본 정보만 파일명에서 추출합니다.
        """
        try:
            text = self._extract_text(pdf_path)
            result = DOData()
            result.source_file = pdf_path
            result.parsed_at = datetime.now()

            # 파일명에서 B/L 번호 추출 (예: MAEU258468669_DO.pdf)
            filename = Path(pdf_path).stem
            bl_from_filename = re.search(r'(?:MAEU?|MEDU|MSCU)([A-Z0-9]{6,10})', filename, re.IGNORECASE)  # v8.2.4
            if bl_from_filename:
                result.bl_no = bl_from_filename.group(1)

            # 텍스트가 있는 경우 상세 파싱
            if len(text) > 100:
                # D/O 번호
                do_match = re.search(r'D/O\s*No\.?\s*:?\s*(\w+)', text, re.IGNORECASE)
                if do_match:
                    result.do_no = do_match.group(1)

                # B/L 번호 (텍스트에서)
                bl_match = re.search(r'B/L\s*No\.?\s*:?\s*([A-Z]{2,4}[A-Z0-9]{6,12}|\d{8,12})', text, re.IGNORECASE)  # v8.2.4
                if bl_match:
                    result.bl_no = bl_match.group(1).replace('MAEU', '')

                # Shipper / Consignee
                if "SQM SALAR" in text.upper():
                    result.shipper = "SQM SALAR SPA."
                if "SOQUIMICH" in text.upper():
                    result.consignee = "SOQUIMICH LLC"

                # 선박
                vessel_match = re.search(r'([A-Z]+\s+MAERSK)', text, re.IGNORECASE)
                if vessel_match:
                    result.vessel = vessel_match.group(1).upper()

                # Voyage
                voyage_match = re.search(r'Voyage\s*(?:No\.?)?\s*:?\s*(\d+\w*)', text, re.IGNORECASE)
                if voyage_match:
                    result.voyage = voyage_match.group(1)

                # 입항일 (여러 형식 지원)
                arrival_patterns = [
                    r'(?:입항일|Arrival|ETA)\s*:?\s*(\d{4}-\d{2}-\d{2})',
                    r'(?:입항일|Arrival|ETA)\s*:?\s*(\d{4}\.\d{2}\.\d{2})',
                    r'(?:입항일|Arrival|ETA)\s*:?\s*(\d{2}/\d{2}/\d{4})',
                ]
                for pattern in arrival_patterns:
                    arrival_match = re.search(pattern, text, re.IGNORECASE)
                    if arrival_match:
                        date_str = arrival_match.group(1)
                        for fmt in ['%Y-%m-%d', '%Y.%m.%d', '%d/%m/%Y']:
                            try:
                                result.arrival_date = datetime.strptime(date_str, fmt).date()
                                break
                            except (ValueError, TypeError, KeyError):  # 날짜 파싱 실패 무시
                                continue
                        break

                # D/O 발행일
                issue_patterns = [
                    r'(?:발행일|Issue|Issued)\s*:?\s*(\d{4}-\d{2}-\d{2})',
                    r'(?:발행일|Issue|Issued)\s*:?\s*(\d{4}\.\d{2}\.\d{2})',
                ]
                for pattern in issue_patterns:
                    issue_match = re.search(pattern, text, re.IGNORECASE)
                    if issue_match:
                        date_str = issue_match.group(1)
                        for fmt in ['%Y-%m-%d', '%Y.%m.%d']:
                            try:
                                result.issue_date = datetime.strptime(date_str, fmt).date()
                                break
                            except (ValueError, TypeError, KeyError):  # 날짜 파싱 실패 무시
                                continue
                        break

                # 컨테이너 (여러 패턴)
                container_patterns = [
                    r'([A-Z]{4}\d{7})\s+([A-Z]{2}\d{7})',  # TCLU1234567 ML1234567
                    r'([A-Z]{4}\d{7})',  # 컨테이너 번호만
                ]
                for pattern in container_patterns:
                    containers = re.findall(pattern, text)
                    if containers:
                        for cont in containers:
                            if isinstance(cont, tuple):
                                result.containers.append({
                                    'container_no': cont[0],
                                    'seal_no': cont[1] if len(cont) > 1 else ''
                                })
                            else:
                                result.containers.append({
                                    'container_no': cont,
                                    'seal_no': ''
                                })
                        break

                # Free Time 정보
                free_time_match = re.search(r'Free\s*Time.*?(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE | re.DOTALL)
                if free_time_match:
                    result.free_time_info.append({
                        'free_time_until': free_time_match.group(1)
                    })

            else:
                # 텍스트가 없는 경우 (이미지 PDF) - 파일명에서 추출한 정보만 사용
                self.warnings.append(f"D/O 파일이 이미지 PDF입니다. OCR이 필요합니다: {pdf_path}")

            return result

        except (ValueError, TypeError, AttributeError) as e:
            self.errors.append(f"D/O 파싱 오류: {str(e)}")
            return None


# =============================================================================
# 편의 함수
# =============================================================================

def parse_pdf(pdf_path: str, doc_type: str = None) -> Tuple[str, Any]:
    """
    PDF 파일을 파싱하고 결과 반환

    Returns:
        (문서유형, 파싱결과) 튜플
    """
    parser = PDFParser()

    if doc_type is None:
        doc_type = parser.detect_document_type(pdf_path)

    result = parser.parse(pdf_path, doc_type)

    return doc_type, result


def parse_multiple_pdfs(pdf_paths: List[str]) -> Dict[str, Any]:
    """
    여러 PDF 파일을 파싱하고 문서 유형별로 분류

    Returns:
        {'PACKING_LIST': [...], 'INVOICE': [...], ...}
    """
    parser = PDFParser()
    results = {
        'PACKING_LIST': [],
        'INVOICE': [],
        'BL': [],
        'DO': [],
        'UNKNOWN': [],
        'ERRORS': []
    }

    for pdf_path in pdf_paths:
        try:
            doc_type = parser.detect_document_type(pdf_path)
            data = parser.parse(pdf_path, doc_type)

            if data:
                results[doc_type].append({
                    'file': pdf_path,
                    'data': data
                })
            else:
                results['ERRORS'].append({
                    'file': pdf_path,
                    'errors': parser.errors.copy()
                })
                parser.errors.clear()
        except (ValueError, TypeError, KeyError) as e:
            results['ERRORS'].append({
                'file': pdf_path,
                'errors': [str(e)]
            })

    return results


# =============================================================================
# 테스트
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        doc_type, result = parse_pdf(pdf_path)
        logger.debug(f"문서 유형: {doc_type}")
        logger.debug(f"파싱 결과: {result}")
    else:
        logger.debug("사용법: python pdf_parser.py <pdf_path>")
