"""
SQM v3.8.4 — DB 추상화 인터페이스 (PostgreSQL 마이그레이션 대비)

P1: SQLite/PostgreSQL 공통 인터페이스 정의
    - 모든 DB 구현체는 이 ABC를 상속
    - engine/GUI는 이 인터페이스만 의존
    - DB 전환 시 코드 변경 최소화
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional


class DatabaseInterface(ABC):
    """
    SQM 데이터베이스 공통 인터페이스
    
    SQLite(SQMDatabase)와 PostgreSQL(PostgreSQLDatabase) 모두 이 인터페이스를 구현.
    비즈니스 로직은 이 인터페이스에만 의존하여 DB 전환을 투명하게 처리.
    
    Usage:
        db: DatabaseInterface = create_database()  # 팩토리로 생성
        with db.transaction():
            db.execute("INSERT INTO ...", (val1, val2))
            row = db.fetchone("SELECT * FROM ... WHERE id = ?", (1,))
    """

    # =========================================================================
    # 핵심 CRUD
    # =========================================================================

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> Any:
        """SQL 실행 (INSERT/UPDATE/DELETE)"""
        ...

    @abstractmethod
    def executemany(self, sql: str, params_list: List[tuple]) -> Any:
        """배치 SQL 실행"""
        ...

    @abstractmethod
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """단일 행 조회 (dict 반환)"""
        ...

    @abstractmethod
    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict]:
        """다중 행 조회 (list[dict] 반환)"""
        ...

    # =========================================================================
    # 트랜잭션
    # =========================================================================

    @abstractmethod
    @contextmanager
    def transaction(self, mode: str = ""):
        """
        트랜잭션 컨텍스트 매니저
        
        Usage:
            with db.transaction():
                db.execute(...)  # 예외 시 자동 롤백
        """
        ...

    @abstractmethod
    def commit(self) -> None:
        """트랜잭션 커밋"""
        ...

    @abstractmethod
    def rollback(self) -> None:
        """트랜잭션 롤백"""
        ...

    # =========================================================================
    # 연결 관리
    # =========================================================================

    @abstractmethod
    def close(self) -> None:
        """DB 연결 종료"""
        ...

    # =========================================================================
    # 백업
    # =========================================================================

    @abstractmethod
    def create_backup(self, reason: str = "manual") -> Optional[str]:
        """DB 백업 생성"""
        ...

    # =========================================================================
    # 유틸리티 (DB 독립적 헬퍼)
    # =========================================================================

    @staticmethod
    def now_str() -> str:
        """현재 시각 문자열 (Python 기반, DB 함수 대신 사용)"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def today_str() -> str:
        """오늘 날짜 문자열"""
        return datetime.now().strftime('%Y-%m-%d')

    @staticmethod
    def placeholder() -> str:
        """
        파라미터 플레이스홀더
        
        SQLite: ?
        PostgreSQL: %s
        
        주의: 이 메서드 대신 SQL 레이어에서 자동 변환하는 것을 권장.
              _convert_query()가 ? → %s 변환을 처리함.
        """
        return "?"  # 기본값 SQLite, PG 구현체에서 오버라이드

    def insert_returning_id(self, sql: str, params: tuple = ()) -> Optional[int]:
        """
        INSERT 후 생성된 ID 반환 (DB 독립적)
        
        SQLite: last_insert_rowid()
        PostgreSQL: RETURNING id
        
        서브클래스에서 오버라이드.
        """
        cursor = self.execute(sql, params)
        if hasattr(cursor, 'lastrowid'):
            return cursor.lastrowid
        return None


# =========================================================================
# SQL 호환성 헬퍼 (DB 독립적 SQL 생성)
# =========================================================================

class SQLCompat:
    """
    SQLite ↔ PostgreSQL SQL 호환성 헬퍼
    
    DB 전용 문법을 표준 SQL로 변환하거나,
    호환 가능한 SQL을 생성하는 유틸리티.
    
    Usage:
        from engine_modules.database_interface import SQLCompat
        
        # datetime('now') 대신
        now = SQLCompat.current_timestamp()  # Python datetime 반환
        
        # INSERT OR IGNORE 대신
        sql = SQLCompat.insert_ignore('inventory_detail', ['lot_no', 'key', 'value'])
        
        # GROUP_CONCAT 대신
        sql = SQLCompat.string_agg('product', ',')  # COALESCE 기반
    """

    _db_type: str = 'sqlite'  # 'sqlite' or 'postgresql'

    @classmethod
    def set_db_type(cls, db_type: str):
        """DB 타입 설정 (sqlite/postgresql)"""
        cls._db_type = db_type.lower()

    @classmethod
    def is_postgresql(cls) -> bool:
        """PostgreSQL 모드 여부 반환"""
        return cls._db_type == 'postgresql'

    @classmethod
    def current_timestamp(cls) -> str:
        """현재 시각 (Python 기반 — DB 함수 사용 안 함)"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @classmethod
    def current_date(cls) -> str:
        """오늘 날짜"""
        return datetime.now().strftime('%Y-%m-%d')

    @classmethod
    def insert_ignore(cls, table: str, columns: List[str]) -> str:
        """
        INSERT OR IGNORE (SQLite) / ON CONFLICT DO NOTHING (PostgreSQL) 생성
        """
        cols = ', '.join(columns)
        placeholders = ', '.join(['?'] * len(columns))

        if cls.is_postgresql():
            return f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        else:
            return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"

    @classmethod
    def upsert(cls, table: str, columns: List[str],
               conflict_cols: List[str], update_cols: List[str] = None) -> str:
        """
        UPSERT 생성 (INSERT ... ON CONFLICT ... DO UPDATE)
        """
        cols = ', '.join(columns)
        placeholders = ', '.join(['?'] * len(columns))
        conflict = ', '.join(conflict_cols)

        if update_cols is None:
            update_cols = [c for c in columns if c not in conflict_cols]

        if cls.is_postgresql():
            updates = ', '.join(f"{c} = EXCLUDED.{c}" for c in update_cols)
            return (f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}")
        else:
            updates = ', '.join(f"{c} = excluded.{c}" for c in update_cols)
            return (f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}")

    @classmethod
    def string_agg(cls, column: str, separator: str = ',') -> str:
        """GROUP_CONCAT (SQLite) / STRING_AGG (PostgreSQL)"""
        if cls.is_postgresql():
            return f"STRING_AGG({column}::TEXT, '{separator}')"
        else:
            return f"GROUP_CONCAT({column}, '{separator}')"

    @classmethod
    def auto_id_type(cls) -> str:
        """자동 증가 ID 타입"""
        if cls.is_postgresql():
            return "SERIAL PRIMARY KEY"
        else:
            return "INTEGER PRIMARY KEY AUTOINCREMENT"

    @classmethod
    def boolean_true(cls) -> str:
        """DB별 TRUE 리터럴 반환"""
        if cls.is_postgresql():
            return "TRUE"
        return "1"

    @classmethod
    def boolean_false(cls) -> str:
        """DB별 FALSE 리터럴 반환"""
        if cls.is_postgresql():
            return "FALSE"
        return "0"
