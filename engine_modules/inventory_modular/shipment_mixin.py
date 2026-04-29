# -*- coding: utf-8 -*-
"""
SQM Inventory Engine - Shipment Mixin
=====================================

v2.9.91 - Extracted from inventory.py

Shipment document processing (parse, preview, process)
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ShipmentMixin:
    """
    Shipment processing mixin
    
    Methods for PDF document parsing and shipment inbound
    """
    

    def get_shipment_list(self) -> List[Dict]:
        """
        Get shipment list
        
        Returns:
            List of shipment records
        """
        query = """
            SELECT 
                id, sap_no, bl_no, folio, product,
                total_qty_mt, total_lots, ship_date, arrival_date,
                status, created_at
            FROM shipment
            ORDER BY created_at DESC
        """
        return self.db.fetchall(query)
    

    # NOTE: get_shipment_detail → 미호출로 삭제 (v3.8.4 데드코드 정리)
