"""
SQM 재고관리 시스템 - 재고 엔진 V3 (모듈화 버전)
=================================================

import logging
import sqlite3
logger = logging.getLogger(__name__)
v3.6.0: Docstring 보강, PostgreSQL 지원

모듈 개요:
    재고 관리의 핵심 비즈니스 로직을 담당하는 메인 엔진입니다.
    Mixin 패턴으로 11개 모듈로 분리되어 있습니다.

주요 클래스:
    - SQMInventoryEngineV3: 메인 재고 엔진
    - SQMInventoryEngine: 하위 호환용 별칭

Mixin 구성:
    - InboundMixin: 입고 처리 (PDF 파싱, Excel 입고)
    - OutboundMixin: 출고 처리 (Allocation 기반)
    - QueryMixin: 재고 조회 (LOT, 선적, 톤백)
    - ExportMixin: Excel 내보내기 (옵션 1-3)
    - ExportMixin: Excel 내보내기 (옵션 1-6, v5.5.3 통합)
    - ShipmentMixin: 선적 문서 처리
    - TonbagMixin: 톤백 관리
    - ReturnMixin: 반품 처리
    - ImportMixin: Excel 가져오기
    - PreflightMixin: All-or-Nothing 검증
    - CRUDMixin: 기본 CRUD 및 검색

사용 예시:
    >>> from engine_modules.inventory import SQMInventoryEngine
    >>> 
    >>> # 엔진 초기화 (SQLite 기본)
    >>> engine = SQMInventoryEngine()
    >>> 
    >>> # 재고 조회
    >>> inventory = engine.get_inventory_list()
    >>> 
    >>> # 통계
    >>> stats = engine.get_statistics()
    >>> print(f"총 LOT: {stats['total_lots']}개")
    >>> 
    >>> # 헬스 체크
    >>> health = engine.health_check()

데이터베이스:
    - SQLite (기본): config.DB_PATH 사용
    - PostgreSQL: config.DB_TYPE='postgresql' 설정 시

작성자: Ruby (남기동)
버전: v3.6.0
"""

import logging
import os
import sqlite3
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Import mixins
from .export_mixin import ExportMixin
from .inbound_mixin import InboundMixin
from .outbound_mixin import OutboundMixin
from .query_mixin import QueryMixin

# New mixins (v2.9.91)
# v5.5.3 P6: ExportExtendedMixin 제거 (죽은 코드 — export_mixin.py로 통합 완료)

try:
    from .shipment_mixin import ShipmentMixin
except ImportError:
    ShipmentMixin = object

try:
    from .tonbag_mixin import TonbagMixin
except ImportError:
    TonbagMixin = object

try:
    from .return_mixin import ReturnMixin
except ImportError:
    ReturnMixin = object

try:
    from .import_mixin import ImportMixin
except ImportError:
    ImportMixin = object

try:
    from .preflight_mixin import PreflightMixin
except ImportError:
    PreflightMixin = object

try:
    from .crud_mixin import CRUDMixin
except ImportError:
    CRUDMixin = object

try:
    from .integrity_mixin import IntegrityMixin
except ImportError:
    IntegrityMixin = object

# v5.5.3 P8: OutboundExtendedMixin 제거 (죽은 코드 — 메서드 호출처 0건)

# v5.6.7: lot_management_mixin.py 제거 (빈 placeholder) — object로 대체
LotManagementMixin = object


class SQMInventoryEngineV3(
    InboundMixin,
    OutboundMixin,
    ExportMixin,
    QueryMixin,
    ShipmentMixin,
    TonbagMixin,
    ReturnMixin,
    ImportMixin,
    PreflightMixin,
    CRUDMixin,
    IntegrityMixin,
    LotManagementMixin,
):
    """
    SQM Inventory Engine V3 (Modular)
    
    Complete engine with all functionality split into mixins:
    
    Core Operations:
    - InboundMixin: Inbound processing
    - OutboundMixin: Outbound processing
    - QueryMixin: Query functions
    
    Export/Import:
    - ExportMixin: Excel export (options 1-3)
    - ExportMixin: Excel export (options 1-6, v5.5.3 consolidated)
    - ImportMixin: Excel import
    
    Document Processing:
    - ShipmentMixin: PDF shipment documents
    
    Tonbag Management:
    - TonbagMixin: Tonbag CRUD
    - ReturnMixin: Return processing
    
    Validation:
    - PreflightMixin: All-or-Nothing validation
    
    Utilities:
    - CRUDMixin: Basic CRUD and search
    """

    def __init__(self, db_path: str = None):
        """
        Initialize engine

        Args:
            db_path: Database file path (SQLite) or connection string (PostgreSQL)
        """
        self.db = None  # 초기화 실패 시 close/__del__에서 접근 방지
        # ★★★ v3.6.0: PostgreSQL 지원 ★★★
        try:
            from core.config import DB_TYPE
        except ImportError:
            DB_TYPE = 'sqlite'

        self.db_type = DB_TYPE

        if DB_TYPE.lower() == 'postgresql':
            # PostgreSQL 모드
            try:
                from core.config import (
                    PG_DATABASE,
                    PG_HOST,
                    PG_MAX_CONNECTIONS,
                    PG_MIN_CONNECTIONS,
                    PG_PASSWORD,
                    PG_PORT,
                    PG_USER,
                )
                from engine_modules.database_postgresql import PostgreSQLDatabase

                self.db = PostgreSQLDatabase(
                    host=PG_HOST,
                    port=PG_PORT,
                    database=PG_DATABASE,
                    user=PG_USER,
                    password=PG_PASSWORD,
                    min_connections=PG_MIN_CONNECTIONS,
                    max_connections=PG_MAX_CONNECTIONS,
                )
                self.db_path = f"postgresql://{PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
                logger.info(f"✅ PostgreSQL 연결 완료: {PG_HOST}:{PG_PORT}/{PG_DATABASE}")

            except ImportError as e:
                logger.error(f"PostgreSQL 모듈 import 실패: {e}")
                logger.info("SQLite로 폴백합니다.")
                DB_TYPE = 'sqlite'
                self.db_type = 'sqlite'
            except (sqlite3.Error, OSError) as e:
                logger.error(f"PostgreSQL 연결 실패: {e}")
                logger.info("SQLite로 폴백합니다.")
                DB_TYPE = 'sqlite'
                self.db_type = 'sqlite'

        if DB_TYPE.lower() == 'sqlite':
            # SQLite 모드 (기존)
            self.db_path = db_path or os.environ.get('SQM_DB_PATH', '') or (str(__import__('config', fromlist=['DB_PATH']).DB_PATH) if True else 'data/db/sqm_inventory.db')

            try:
                from engine_modules.database import SQMDatabase
                self.db = SQMDatabase(self.db_path)
                logger.info(f"✅ SQLite 연결 완료: {self.db_path}")
            except ImportError:
                from sqlalchemy import create_engine
                self.engine = create_engine(
                    f'sqlite:///{self.db_path}',
                    echo=False,
                    pool_pre_ping=True
                )
                self.db = None

        self.errors = []
        self.warnings = []

        logger.info(f"SQMInventoryEngineV3 initialized: {self.db_path}")

    def get_connection(self) -> Any:
        """
        Get database connection (SQLite 호환)
        
        Dashboard 등에서 engine.get_connection()으로 직접 커넥션 접근 시 사용.
        SQMDatabase의 conn 프로퍼티를 반환합니다.
        
        Returns:
            sqlite3.Connection or equivalent
        """
        if self.db is not None:
            return self.db.conn
        raise RuntimeError("Database not initialized")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall statistics
        
        Returns:
            Statistics dict
        """
        try:
            stats = {
                'total_lots': 0,
                'total_weight_kg': 0,
                'total_weight_mt': 0,
                'available_weight_kg': 0,
                'available_weight_mt': 0,
                'picked_weight_kg': 0,
                'total_tonbags': 0,
                'available_tonbags': 0,
            }

            if self.db:
                # LOT statistics
                lot_result = self.db.fetchone("""
                    SELECT 
                        COUNT(*) as total_lots,
                        COALESCE(SUM(current_weight), 0) as available_weight,
                        COALESCE(SUM(initial_weight), 0) as total_weight,
                        COALESCE(SUM(picked_weight), 0) as picked_weight
                    FROM inventory
                """)

                if lot_result:
                    stats['total_lots'] = lot_result['total_lots'] or 0
                    stats['total_weight_kg'] = lot_result['total_weight'] or 0
                    stats['available_weight_kg'] = lot_result['available_weight'] or 0
                    stats['picked_weight_kg'] = lot_result['picked_weight'] or 0

                # Tonbag statistics
                tonbag_result = self.db.fetchone("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) as available
                    FROM inventory_tonbag
                """)

                if tonbag_result:
                    stats['total_tonbags'] = tonbag_result['total'] or 0
                    stats['available_tonbags'] = tonbag_result['available'] or 0

            # Convert to MT
            stats['total_weight_mt'] = stats['total_weight_kg'] / 1000
            stats['available_weight_mt'] = stats['available_weight_kg'] / 1000

            return stats

        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"Statistics error: {e}")
            return {}

    def health_check(self) -> Dict[str, Any]:
        """
        Check system health
        
        Returns:
            Health status dict
        """
        status = {
            'database': False,
            'db_type': getattr(self, 'db_type', 'sqlite'),
            'tables': [],
            'message': '',
        }

        try:
            if self.db:
                # Check DB connection
                self.db.fetchone("SELECT 1")
                status['database'] = True

                # Get table list (PostgreSQL 호환)
                if getattr(self, 'db_type', 'sqlite') == 'postgresql':
                    tables = self.db.fetchall("""
                        SELECT table_name as name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                else:
                    tables = self.db.fetchall("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    """)
                status['tables'] = [t['name'] for t in tables]

            status['message'] = "OK"

        except (sqlite3.Error, OSError) as e:
            status['message'] = str(e)
            logger.error(f"Health check error: {e}")

        return status

    def close(self) -> None:
        """Close engine.
        v6.3.5: close_all() 우선 사용 — WAL checkpoint + 전 스레드 연결 종료.
        """
        if getattr(self, 'db', None):
            # close_all 우선: 전체 스레드 연결 + WAL checkpoint(TRUNCATE)
            if hasattr(self.db, 'close_all'):
                try:
                    self.db.close_all()
                except Exception as _e:
                    logger.debug(f"db.close_all 실패(무시): {_e}")
                    self.db.close()  # fallback
            else:
                self.db.close()
        if hasattr(self, 'engine') and self.engine:
            self.engine.dispose()
        logger.info("SQMInventoryEngineV3 closed")

    def __del__(self) -> None:
        """v3.7.0: GC 시 DB 연결 확실히 닫기"""
        try:
            if getattr(self, 'db', None) is not None:
                self.close()
        except (ValueError, TypeError, KeyError, AttributeError) as _e:
            logger.debug(f"[engine] 무시: {_e}")


# Backward compatibility alias
SQMInventoryEngine = SQMInventoryEngineV3
