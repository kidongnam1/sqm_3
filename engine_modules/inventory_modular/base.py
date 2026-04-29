# -*- coding: utf-8 -*-
"""
기본 설정 및 유틸리티
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class InventoryBaseMixin:
    """기본 유틸리티 Mixin"""
    
    @staticmethod
    def _safe_parse_date(date_value: Any, formats: List[str] = None) -> Optional[date]:
        """안전한 날짜 파싱"""
        if date_value is None:
            return None
        
        if isinstance(date_value, datetime):
            return date_value.date()
        
        if isinstance(date_value, date):
            return date_value
        
        if not isinstance(date_value, str):
            return None
        
        date_str = str(date_value).strip()
        if not date_str or date_str in ('None', 'none', 'null', 'NULL'):
            return None

        formats = formats or [
            '%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y',
            '%Y.%m.%d', '%m/%d/%Y', '%d.%m.%Y', '%Y%m%d',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str[:10], fmt).date()
            except ValueError as _e:
                logger.debug(f"[SUPPRESSED] exception in base.py: {_e}")  # noqa

        logger.warning(f"날짜 파싱 실패: {date_str!r}")
        return None
    
    @staticmethod
    def _safe_parse_float(value: Any, default: float = 0.0) -> float:
        """안전한 float 변환"""
        if value is None:
            return default
        
        if isinstance(value, (int, float)):
            return float(value)
        
        try:
            cleaned = str(value).replace(',', '').strip()
            return float(cleaned) if cleaned else default
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def _safe_parse_int(value: Any, default: int = 0) -> int:
        """안전한 int 변환"""
        if value is None:
            return default
        
        if isinstance(value, int):
            return value
        
        try:
            if isinstance(value, float):
                return int(value)
            cleaned = str(value).replace(',', '').strip()
            return int(float(cleaned)) if cleaned else default
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def _safe_str(value: Any, default: str = '') -> str:
        """안전한 문자열 변환"""
        if value is None:
            return default
        return str(value).strip()
    
    # v6.2.8 제거: _calculate_weight_mt (미사용, weight/1000으로 인라인)

    def _log_operation(self, operation: str, details: Dict = None) -> None:
        """작업 로깅"""
        msg = f"[{operation}]"
        if details:
            msg += f" {details}"
        logger.info(msg)
    
class PackingData:
    """패킹 데이터 래퍼"""
    
    def __init__(self, data: Union[Dict, Any]):
        """LotRecord 초기화"""
        if isinstance(data, dict):
            self._data = data
        else:
            self._data = {}
            for attr in dir(data):
                if not attr.startswith('_'):
                    try:
                        self._data[attr] = getattr(data, attr)
                    except (AttributeError, TypeError) as e:
                        logger.debug(f'예외 발생 (getattr): {e}')
    
    def __getattr__(self, name: str) -> Any:
        """dict 스타일 속성 접근"""
        if name == '_data':
            return super().__getattribute__(name)
        return self._data.get(name)
    
    def get(self, key: str, default: Any = None) -> Any:
        """dict.get() 호환 메서드"""
        return self._data.get(key, default)
    
    def to_dict(self) -> Dict:
        """dict 변환"""
        return self._data.copy()


class InventoryResult:
    """작업 결과 클래스"""
    
    def __init__(self, success: bool, message: str = '', data: Any = None):
        """ProcessResult 초기화"""
        self.success = success
        self.message = message
        self.data = data
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def add_error(self, error: str):
        """에러 메시지 추가"""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str):
        """경고 메시지 추가"""
        self.warnings.append(warning)
    
    # REMOVED v8.6.4: duplicate to_dict()
