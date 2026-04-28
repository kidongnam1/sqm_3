"""
SQM 재고관리 시스템 - 통합 문서 파서 V3 (모듈화 버전)
=====================================================

v3.6.0: document_parser_v2.py 모듈화

모듈 개요:
    4종 선적 문서(Invoice, Packing List, B/L, D/O)를 파싱하는
    통합 문서 파서입니다. Mixin 패턴으로 모듈화되었습니다.

사용 예시:
    >>> from parsers.document_parser_modular import DocumentParserV3
    >>> 
    >>> parser = DocumentParserV3(gemini_api_key='your_key')
    >>> 
    >>> # 개별 문서 파싱
    >>> invoice = parser.parse_invoice('invoice.pdf')
    >>> packing = parser.parse_packing_list('packing.pdf')
    >>> bl = parser.parse_bl('bl.pdf')
    >>> do = parser.parse_do('do.pdf')
    >>> 
    >>> # 자동 감지 파싱
    >>> doc = parser.parse_document('unknown.pdf')
    >>> 
    >>> # 전체 선적 문서 파싱
    >>> shipment = parser.parse_shipment_documents(
    ...     invoice_path='invoice.pdf',
    ...     packing_path='packing.pdf',
    ...     bl_path='bl.pdf',
    ...     do_path='do.pdf'
    ... )

작성자: Ruby (남기동)
버전: v3.6.0
"""

import logging
from typing import Any, Optional

from ..document_models import ShipmentDocuments
from .base import DocumentParserBase
from .bl_mixin import BLMixin
from .do_mixin import DOMixin
from .invoice_mixin import InvoiceMixin
from .packing_mixin import PackingMixin

logger = logging.getLogger(__name__)


class DocumentParserV3(
    InvoiceMixin,
    PackingMixin,
    BLMixin,
    DOMixin,
    DocumentParserBase
):
    """
    통합 문서 파서 V3 (모듈화 버전)
    
    4종 선적 문서를 파싱합니다:
    - Invoice (상업송장)
    - Packing List (포장명세서)
    - B/L (선하증권)
    - D/O (화물인도지시서)
    
    Attributes:
        gemini_api_key: Gemini API 키
        errors: 에러 목록
        warnings: 경고 목록
    
    Example:
        >>> parser = DocumentParserV3(gemini_api_key='your_key')
        >>> invoice = parser.parse_invoice('invoice.pdf')
        >>> print(f"SAP NO: {invoice.sap_no}")
    """

    def __init__(
        self,
        gemini_api_key: str = None,
        *,
        provider: str = None,
        api_key: str = None,
    ):
        """
        Args:
            gemini_api_key: Gemini API 키 (하위 호환)
            provider: AI provider ('gemini'|'openai'|'anthropic')
            api_key: provider의 API 키
        """
        super().__init__(gemini_api_key, provider=provider, api_key=api_key)
        logger.info("DocumentParserV3 (모듈화 버전) 초기화 — provider=%s", self.provider)

    def parse_document(self, pdf_path: str, doc_type: str = None) -> Optional[Any]:
        """
        문서 자동 감지 파싱
        
        Args:
            pdf_path: PDF 파일 경로
            doc_type: 문서 유형 (None이면 자동 감지)
                - 'INVOICE', 'PACKING_LIST', 'BL', 'DO'
        
        Returns:
            파싱 결과 (문서 유형에 따라 다름)
        """
        if doc_type is None:
            diagnosis = self.diagnose_pdf(pdf_path)
            doc_type = diagnosis.get('detected_type', 'UNKNOWN')

        doc_type = doc_type.upper()

        if doc_type == 'INVOICE':
            return self.parse_invoice(pdf_path)
        elif doc_type == 'PACKING_LIST':
            return self.parse_packing_list(pdf_path)
        elif doc_type == 'BL':
            return self.parse_bl(pdf_path)
        elif doc_type == 'DO':
            return self.parse_do(pdf_path)
        else:
            logger.warning(f"알 수 없는 문서 유형: {doc_type}")
            return None

    def parse_shipment_documents(
        self,
        invoice_path: str = None,
        packing_path: str = None,
        bl_path: str = None,
        do_path: str = None
    ) -> ShipmentDocuments:
        """
        선적 관련 문서들 일괄 파싱
        
        Args:
            invoice_path: Invoice PDF 경로
            packing_path: Packing List PDF 경로
            bl_path: B/L PDF 경로
            do_path: D/O PDF 경로
        
        Returns:
            ShipmentDocuments: 파싱된 모든 문서 데이터
        """
        result = ShipmentDocuments()

        if invoice_path:
            logger.info(f"Invoice 파싱: {invoice_path}")
            result.invoice = self.parse_invoice(invoice_path)

        if packing_path:
            logger.info(f"Packing List 파싱: {packing_path}")
            result.packing_list = self.parse_packing_list(packing_path)

        if bl_path:
            logger.info(f"B/L 파싱: {bl_path}")
            result.bl = self.parse_bl(bl_path)

        if do_path:
            logger.info(f"D/O 파싱: {do_path}")
            result.do = self.parse_do(do_path)

        # 문서 간 교차 검증 (기존 빈 값 보완)
        result = self._validate_shipment_documents(result)

        # v6.2.1: 크로스 체크 엔진으로 정밀 검증
        try:
            from ..cross_check_engine import cross_check_documents
            cross_result = cross_check_documents(
                invoice=result.invoice,
                packing_list=result.packing_list,
                bl=result.bl,
                do=result.do
            )
            result.cross_check_result = cross_result
            if not cross_result.is_clean:
                logger.warning(f"[CrossCheck] {cross_result.summary}")
                for item in cross_result.items:
                    if item.level.value >= 2:
                        result.validation_errors.append(str(item))
        except (ImportError, Exception) as e:
            logger.debug(f"[CrossCheck] 크로스 체크 스킵: {e}")

        return result

    def _validate_shipment_documents(self, docs: ShipmentDocuments) -> ShipmentDocuments:
        """
        문서 간 데이터 교차 검증 및 보완
        
        Args:
            docs: 파싱된 문서들
        
        Returns:
            ShipmentDocuments: 검증/보완된 문서들
        """
        # SAP NO 교차 검증
        sap_numbers = []
        if docs.invoice and docs.invoice.sap_no:
            sap_numbers.append(docs.invoice.sap_no)
        if docs.packing_list and docs.packing_list.sap_no:
            sap_numbers.append(docs.packing_list.sap_no)
        if docs.bl and docs.bl.sap_no:
            sap_numbers.append(docs.bl.sap_no)
        if docs.do and docs.do.sap_no:
            sap_numbers.append(docs.do.sap_no)

        # 가장 많이 나온 SAP NO로 통일
        if sap_numbers:
            from collections import Counter
            most_common = Counter(sap_numbers).most_common(1)[0][0]

            if docs.invoice and not docs.invoice.sap_no:
                docs.invoice.sap_no = most_common
            if docs.packing_list and not docs.packing_list.sap_no:
                docs.packing_list.sap_no = most_common
            if docs.bl and not docs.bl.sap_no:
                docs.bl.sap_no = most_common
            if docs.do and not docs.do.sap_no:
                docs.do.sap_no = most_common

        # B/L No 교차 검증
        bl_numbers = []
        if docs.invoice and docs.invoice.bl_no:
            bl_numbers.append(docs.invoice.bl_no)
        if docs.bl and docs.bl.bl_no:
            bl_numbers.append(docs.bl.bl_no)
        if docs.do and docs.do.bl_no:
            bl_numbers.append(docs.do.bl_no)

        if bl_numbers:
            most_common_bl = Counter(bl_numbers).most_common(1)[0][0]

            if docs.invoice and not docs.invoice.bl_no:
                docs.invoice.bl_no = most_common_bl
            if docs.bl and not docs.bl.bl_no:
                docs.bl.bl_no = most_common_bl
            if docs.do and not docs.do.bl_no:
                docs.do.bl_no = most_common_bl

        return docs


# 하위 호환성을 위한 별칭
DocumentParser = DocumentParserV3
