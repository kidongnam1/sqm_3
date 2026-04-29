"""
SQM 재고관리 시스템 - 재고 엔진 (Facade)
==========================================

v6.8.6: 불필요한 re-export 제거 (18개 미사용 import 정리)
★ 외부 코드는 engine_modules.inventory_modular 직접 import 사용 권장

기존 코드:
    from engine_modules.inventory import SQMInventoryEngine
    engine = SQMInventoryEngine(db_path)
위 코드가 그대로 동작합니다.
"""

import logging

logger = logging.getLogger(__name__)

# v6.8.6: SQMInventoryEngine 단일 export만 유지 (re-export 18개 제거)
try:
    from engine_modules.inventory_modular import SQMInventoryEngine  # noqa: F401
    logger.debug("[v6.8.6] inventory.py: 모듈화 버전 사용")
except ImportError as e:
    logger.error(f"[v6.8.6] 모듈화 버전 import 실패: {e}")
    SQMInventoryEngine = None

__all__ = ['SQMInventoryEngine']
