# -*- coding: utf-8 -*-
"""
Unified document parsing service.

입고 문서와 출고 피킹 문서의 상위 진입점을 분리해 둔다.
DocumentParserV3는 입고 선적서류 책임을 유지하고, PickingListParser는
출고 피킹 문서 책임을 유지한다.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DocumentParsingService:
    """입고/출고 문서 파싱을 하나의 서비스 경계에서 라우팅한다."""

    def parse_inbound_documents(
        self,
        *,
        packing_path: str,
        bl_path: Optional[str] = None,
        invoice_path: Optional[str] = None,
        do_path: Optional[str] = None,
        carrier_id: str = "",
        bag_weight_kg: Optional[int] = None,
        gemini_hint: str = "",
    ) -> Any:
        """
        입고 선적서류 파싱.

        DocumentParserV3의 책임을 유지하기 위한 얇은 서비스 래퍼다.
        """
        from parsers.document_parser_modular.parser import DocumentParserV3

        parser = DocumentParserV3()
        if bag_weight_kg is None and not gemini_hint:
            return parser.parse_shipment_documents(
                invoice_path=invoice_path,
                packing_path=packing_path,
                bl_path=bl_path,
                do_path=do_path,
                carrier_id=carrier_id,
            )

        # parse_shipment_documents는 PL별 옵션 전달을 지원하지 않으므로
        # 옵션이 있는 경우 명시적으로 조립한다.
        from parsers.document_models import ShipmentDocuments

        result = ShipmentDocuments()
        pl_kwargs = {}
        if bag_weight_kg is not None:
            pl_kwargs["bag_weight_kg"] = bag_weight_kg
        if gemini_hint:
            pl_kwargs["gemini_hint"] = gemini_hint
        if carrier_id:
            pl_kwargs["carrier_id"] = carrier_id

        result.packing_list = parser.parse_packing_list(packing_path, **pl_kwargs)
        if invoice_path:
            result.invoice = parser.parse_invoice(invoice_path)
        if bl_path:
            result.bl = parser.parse_bl(bl_path, carrier_id=carrier_id) if carrier_id else parser.parse_bl(bl_path)
        if do_path:
            result.do = parser.parse_do(do_path, carrier_id=carrier_id) if carrier_id else parser.parse_do(do_path)
        try:
            from parsers.cross_check_engine import cross_check_documents

            result.cross_check_result = cross_check_documents(
                invoice=result.invoice,
                packing_list=result.packing_list,
                bl=result.bl,
                do=result.do,
            )
        except Exception as e:
            logger.warning("[DocumentParsingService] inbound cross-check skipped: %s", e)
        return result

    def parse_picking_list(self, pdf_path: str) -> dict:
        """
        출고 Picking List 파싱.

        피킹 문서는 DocumentParserV3에 흡수하지 않고 전용 파서를 사용한다.
        """
        from features.parsers.picking_list_parser import PickingListParser

        return PickingListParser().parse(pdf_path)


def parse_picking_list_pdf(pdf_path: str) -> dict:
    """기존 호출부 호환용 함수."""
    return DocumentParsingService().parse_picking_list(pdf_path)
