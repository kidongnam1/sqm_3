# -*- coding: utf-8 -*-
"""
SQM Inventory Engine - Utilities
================================

v2.9.91 - Extracted from inventory.py

Safe parsing and utility functions
"""

import logging
from datetime import datetime, date
from typing import Optional, List, Any, Dict

logger = logging.getLogger(__name__)


def safe_parse_date(date_value: Any, formats: List[str] = None) -> Optional[date]:
    """
    Safe date parsing
    
    Args:
        date_value: Date value (str, date, datetime)
        formats: Date formats to try
        
    Returns:
        Parsed date object or None
    """
    if date_value is None:
        return None
    
    # Already date/datetime
    if isinstance(date_value, datetime):
        return date_value.date()
    if isinstance(date_value, date):
        return date_value
    
    # pandas Timestamp
    if hasattr(date_value, 'date'):
        try:
            return date_value.date()
        except (ValueError, TypeError, KeyError) as _e:
            logger.debug(f"utils: {_e}")
    
    # String parsing
    if isinstance(date_value, str):
        if formats is None:
            formats = [
                '%Y-%m-%d', '%Y.%m.%d', '%d/%m/%Y', 
                '%m/%d/%Y', '%Y%m%d', '%d-%m-%Y'
            ]
        
        date_str = str(date_value).strip()
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError as _e:
                logger.debug(f"[SUPPRESSED] exception in utils.py: {_e}")  # noqa
        
        logger.debug(f"Date parsing failed: {date_value}")
    
    return None


def safe_parse_float(value: Any, default: float = 0.0) -> float:
    """
    Safe float parsing
    
    Args:
        value: Value to convert
        default: Default on failure
        
    Returns:
        Parsed float or default
    """
    if value is None:
        return default
    
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return float(value)
    except (ValueError, TypeError) as e:
        logger.debug(f"Float parsing failed: {value} - {e}")
        return default


def safe_parse_int(value: Any, default: int = 0) -> int:
    """
    Safe integer parsing
    
    Args:
        value: Value to convert
        default: Default on failure
        
    Returns:
        Parsed int or default
    """
    if value is None:
        return default
    
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return int(float(value))
    except (ValueError, TypeError) as e:
        logger.debug(f"Int parsing failed: {value} - {e}")
        return default


class PackingDataAdapter:
    """
    Adapter to access dict like an object
    
    Converts dict packing data to object-like access
    """
    
    def __init__(self, data: Dict):
        """PackingData 초기화"""
        self._data = data
        self.lots = data.get('lots', [])
        self.sap_no = data.get('sap_no', '')
        self.bl_no = data.get('bl_no', '')
        self.folio = data.get('folio', '')
        self.vessel = data.get('vessel', '')
        self.product = data.get('product', '')
        self.product_code = data.get('product_code', '')
        self.customer = data.get('customer', '')
        self.destination = data.get('destination', '')
        self.ship_date = data.get('ship_date')
        self.arrival_date = data.get('arrival_date')
        self.eta_busan = data.get('eta_busan')
        self.stock_date = data.get('stock_date')
        self.salar_invoice_no = data.get('salar_invoice_no', '')
        
        # Calculated fields
        total_weight = sum(lot.get('net_weight', 0) for lot in self.lots)
        self.total_net_weight = total_weight
        self.total_lots = len(self.lots)
    
    def __getattr__(self, name: str):
        """dict 스타일 속성 접근"""
        return self._data.get(name, '')
    
    def get(self, key: str, default: Any = None) -> Any:
        """dict.get() 호환 메서드"""
        return self._data.get(key, default)


def dict_to_packing_data(data: Dict) -> PackingDataAdapter:
    """
    Convert dict to PackingListData-like object
    
    Args:
        data: Dictionary packing data
        
    Returns:
        PackingDataAdapter object
    """
    return PackingDataAdapter(data)


def format_lot_no(lot_no: Any) -> str:
    """
    Format LOT number (remove decimals from float)
    
    Args:
        lot_no: LOT number value
        
    Returns:
        Formatted string
    """
    if lot_no is None:
        return ""
    
    if isinstance(lot_no, float):
        return str(int(lot_no))
    
    lot_str = str(lot_no).strip()
    if '.' in lot_str:
        lot_str = lot_str.split('.')[0]
    
    return lot_str


def format_weight(weight_kg: float, unit: str = 'kg') -> str:
    """
    Format weight value
    
    Args:
        weight_kg: Weight in kg
        unit: Output unit ('kg', 'MT')
        
    Returns:
        Formatted string
    """
    if unit.upper() == 'MT':
        return f"{weight_kg / 1000:.3f}"
    else:
        return f"{weight_kg:,.2f}"
