# -*- coding: utf-8 -*-
"""
SQM 재고관리 시스템 - SQLite 데이터베이스 모듈
==============================================

v3.6.0: Docstring 보강

모듈 개요:
    SQLite 데이터베이스 연결, 쿼리 실행, 트랜잭션 관리를 담당합니다.
    스레드 안전성, WAL 모드, 네트워크 모드를 자동으로 처리합니다.

주요 클래스:
    - SQMDatabase: SQLite 데이터베이스 관리 클래스

사용 예시:
    >>> from engine_modules.database import SQMDatabase
    >>> db = SQMDatabase('data/inventory.db')
    >>> 
    >>> # 단일 조회
    >>> row = db.fetchone("SELECT * FROM inventory WHERE lot_no = ?", ('1234567890',))
    >>> 
    >>> # 전체 조회
    >>> rows = db.fetchall("SELECT * FROM inventory WHERE status = ?", ('AVAILABLE',))
    >>> 
    >>> # 트랜잭션
    >>> with db.transaction():
    ...     db.execute("INSERT INTO inventory ...")
    ...     db.execute("UPDATE inventory SET ...")
    >>> 
    >>> # 백업
    >>> backup_path = db.create_backup(reason='before_import')

의존성:
    - sqlite3 (내장)
    - threading (내장)

작성자: Ruby
버전: v3.6.0
"""

import sqlite3

# v6.2.7: Python 3.12+ DeprecationWarning 대응
# sqlite3 기본 date/datetime 어댑터가 3.12에서 deprecated
import datetime as _dt
sqlite3.register_adapter(_dt.date, lambda d: d.isoformat())
sqlite3.register_adapter(_dt.datetime, lambda d: d.isoformat())
sqlite3.register_converter("date", lambda b: _dt.date.fromisoformat(b.decode()))
sqlite3.register_converter("datetime", lambda b: _dt.datetime.fromisoformat(b.decode()))
import os
import logging
import threading
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any, Callable, TYPE_CHECKING
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, Future

# 타입 힌팅용 (런타임에는 import 안 함)
if TYPE_CHECKING:
    pass  # 필요시 추가

# 로깅 설정
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# DB 재시도 상수 (v5.1.2)
# ═══════════════════════════════════════════════════════════
DB_MAX_RETRIES = 3          # 최대 재시도 횟수
DB_RETRY_DELAY = 0.5        # 초기 대기 (초)
DB_RETRY_BACKOFF = 2        # 지수 백오프 배율


try:
    from engine_modules.database_interface import DatabaseInterface
except ImportError:
    DatabaseInterface = object  # fallback

from .db_migration_mixin import DatabaseMigrationMixin
from .db_schema_mixin import DatabaseSchemaMixin
from utils.common import norm_bl_no_for_query  # v9.0


class SQMDatabase(DatabaseSchemaMixin, DatabaseMigrationMixin, DatabaseInterface):
    """
    SQLite 데이터베이스 관리 (v3.9.6: Mixin 분할)

    v5.5.3: db_validation_mixin 제거 (검증/백업은 본 클래스에서 직접 구현)
    v3.9.6: 마이그레이션 → db_migration_mixin.py
    v2.5.4 개선 (검토안 반영):
    1. 스레드 안전성 - check_same_thread=False + 쓰기 락
    2. DB 경로 단일화 - config.DB_PATH 사용
    3. Foreign Key 활성화 - PRAGMA foreign_keys=ON
    4. 네트워크 모드 자동 감지 - UNC 경로 시 WAL OFF

    이전 개선:
    - 트랜잭션 컨텍스트 매니저, Online Backup API
    - 자동 백업, WAL 모드, 입력 검증, 로그 로테이션
    """

    # LOT 번호 유효성 검사 패턴 (10자리 숫자)
    # v2.9.0: 112로 시작한다고 단정하지 않음
    # LOT 검증은 engine_modules.validators.validate_lot_no 단일 소스 사용

    # 백업 설정
    MAX_BACKUPS = 5  # 최대 백업 파일 수

    def __init__(self, db_path: str = None, use_wal: bool = None, network_mode: bool = None) -> None:
        """
        Args:
            db_path: DB 파일 경로 (None이면 config.DB_PATH 사용)
            use_wal: WAL 모드 사용 여부 (None이면 자동 감지)
            network_mode: 네트워크 공유 모드 (None이면 자동 감지)
        """
        # A2: DB 경로 단일화 - config에서 가져오기
        if db_path is None:
            try:
                from core.config import DB_PATH
                db_path = str(DB_PATH)
            except ImportError:
                try:
                    from config import DB_PATH as _DB_PATH
                    db_path = str(_DB_PATH)
                except ImportError:
                    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'db', 'sqm_inventory.db')

        self.db_path = db_path
        self.backup_dir = os.path.join(os.path.dirname(db_path) if db_path != ':memory:' else '.', 'backups')

        # 네트워크 모드 자동 감지 (UNC 경로 또는 명시적 설정)
        if network_mode is None:
            self.network_mode = self._detect_network_path(db_path) if db_path != ':memory:' else False
        else:
            self.network_mode = network_mode

        # WAL 모드: 네트워크면 자동으로 OFF
        if use_wal is None:
            self.use_wal = not self.network_mode
        else:
            self.use_wal = use_wal

        # :memory: DB가 아닌 경우에만 디렉토리 생성
        if db_path != ':memory:':
            db_dir = os.path.dirname(db_path)
            if db_dir:  # 빈 문자열이 아닌 경우에만
                os.makedirs(db_dir, exist_ok=True)
            os.makedirs(self.backup_dir, exist_ok=True)

        # A1: 스레드 안전성 - 쓰기 락
        self._write_lock = threading.RLock()
        self._local = threading.local()  # 스레드별 연결 저장
        # v6.3.5: 모든 스레드 연결 추적 (close_all용)
        self._all_connections: list = []
        self._all_connections_lock = threading.Lock()

        self._connection = None
        self._cursor = None
        self._last_backup_time = None
        # P0-3: _in_transaction → thread-local (self._local.in_transaction)
        # 초기화는 각 스레드에서 getattr()로 처리

        self._init_database()
        self._set_busy_timeout()
        self._create_indexes()
        
        # ★★★ v2.9.25: DB 스키마 자동 점검/마이그레이션 ★★★
        self._verify_schema()
        self._log_explain_query_plan_once()

        if self.network_mode:
            logger.info("네트워크 모드 감지: WAL OFF, synchronous=FULL")

    @staticmethod
    def _detect_network_path(path: str) -> bool:
        """
        네트워크 경로 자동 감지

        - UNC 경로 (\\\\server\\share) → True
        - 일반 경로 → False
        """
        # Windows UNC 경로
        if path.startswith('\\\\') or path.startswith('//'):
            return True
        # 추가 휴리스틱: 환경변수 설정
        if os.environ.get('SQM_NETWORK_MODE', '').lower() in ('1', 'true', 'yes'):
            return True
        return False

    @property
    def conn(self) -> sqlite3.Connection:
        """
        스레드 안전한 DB 연결 반환

        v2.5.4: check_same_thread=False + 스레드별 연결
        """
        # 스레드별 연결 사용 (thread-local)
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None,  # 수동 트랜잭션 관리
                check_same_thread=False  # A1: 스레드 안전성 핵심
            )
            self._local.conn.row_factory = sqlite3.Row
            # v6.3.5: 전체 연결 목록에 등록 (close_all 대상)
            with self._all_connections_lock:
                self._all_connections.append(self._local.conn)

            # A3: Foreign Key 활성화 및 검증 (P0-3 패치)
            self._local.conn.execute("PRAGMA foreign_keys=ON")
            _fk_check = self._local.conn.execute("PRAGMA foreign_keys").fetchone()
            if not _fk_check or _fk_check[0] != 1:
                logger.error(
                    "[DB] PRAGMA foreign_keys 활성화 실패 — "
                    "LOT 삭제 시 고아 톤백 누적 위험. WAL 모드 확인 필요."
                )
            self._local.conn.execute("PRAGMA busy_timeout=30000")

            # 네트워크 모드에 따른 저널 모드 설정
            if self.network_mode:
                self._local.conn.execute("PRAGMA journal_mode=DELETE")
                self._local.conn.execute("PRAGMA synchronous=FULL")
            elif self.use_wal:
                self._local.conn.execute("PRAGMA journal_mode=WAL")
                self._local.conn.execute("PRAGMA synchronous=NORMAL")

        return self._local.conn

    @property
    def cursor(self) -> sqlite3.Cursor:
        """재사용 가능한 커서"""
        if self._cursor is None:
            self._cursor = self.conn.cursor()
        return self._cursor

    # =========================================================================
    # v2.5.4: 트랜잭션 컨텍스트 매니저 (쓰기 락 포함)
    # =========================================================================

    @contextmanager
    def transaction(self, mode: str = "IMMEDIATE") -> Any:
        """
        트랜잭션 컨텍스트 매니저 - 원자적 작업 보장 (Phase 3: HardStop 통합)

        v2.5.4: 쓰기 락 추가로 스레드 안전성 확보
        v4.2.3: HardStopException은 절대 삼키지 않고 롤백 후 재발생

        사용 예:
            with db.transaction():
                db.execute("INSERT ...")
                db.execute("UPDATE ...")
                # 예외 발생 시 자동 롤백

        Args:
            mode: DEFERRED(기본), IMMEDIATE(쓰기 락 선점), EXCLUSIVE(배타적)
        """
        # 쓰기 락 획득 (스레드 안전성) - v2.5.4 수정
        self._write_lock.acquire()

        # ✅ v2.5.4 수정: 중첩 트랜잭션 시 락을 유지한 채로 yield
        if getattr(self._local, 'in_transaction', False):
            try:
                yield
            finally:
                self._write_lock.release()  # RLock 카운터 감소
            return

        self._local.in_transaction = True
        try:
            self.conn.execute(f"BEGIN {mode}")
            yield
            self.conn.commit()
            logger.debug(f"트랜잭션 커밋 완료 (mode={mode})")
        except Exception as e:
            # Phase 3: 모든 예외에서 롤백 (TypeError/KeyError 등도 포함)
            self.conn.rollback()
            logger.error(f"트랜잭션 롤백: {type(e).__name__}: {e}")
            
            # HardStopException은 절대 삼키지 않음
            try:
                from .exceptions import HardStopException
                if isinstance(e, HardStopException):
                    logger.warning("HardStopException 감지 - 즉시 재발생")
            except ImportError as _e:
                logger.debug(f"Suppressed: {_e}")
            
            raise  # 모든 예외 재발생
        finally:
            self._local.in_transaction = False
            self._write_lock.release()

    # =========================================================================
    # v2.5.4: Online Backup API (검토안 B단계)
    # =========================================================================

    def create_backup(self, reason: str = "manual") -> Optional[str]:
        """
        데이터베이스 백업 생성 (Online Backup API 사용)

        sqlite3.Connection.backup()을 사용하여 동시 접근 중에도
        일관된 백업을 생성합니다.

        Args:
            reason: 백업 사유 (manual, before_import, before_delete 등)

        Returns:
            백업 파일 경로 또는 None (실패 시)
        """
        try:
            if not os.path.exists(self.db_path):
                return None

            # 백업 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"sqm_inventory_{timestamp}_{reason}.db"
            backup_path = os.path.join(self.backup_dir, backup_name)

            # Online Backup API 사용 (일관성 보장)
            with sqlite3.connect(backup_path) as backup_conn:
                self.conn.backup(backup_conn)

            self._last_backup_time = datetime.now()
            logger.info(f"DB 백업 생성 (Online API): {backup_name}")

            # 오래된 백업 정리
            self._cleanup_old_backups()

            return backup_path

        except (sqlite3.Error, OSError) as e:
            logger.error(f"백업 실패: {e}")
            return None

    def _cleanup_old_backups(self) -> None:
        """오래된 백업 파일 정리 (v5.2.0: 공용 함수 위임)"""
        try:
            from utils.backup import cleanup_old_backups_in_dir
            cleanup_old_backups_in_dir(self.backup_dir, self.MAX_BACKUPS, '.db')
        except ImportError:
            # fallback: utils.backup 없을 때
            try:
                backups = sorted([
                    f for f in os.listdir(self.backup_dir) if f.endswith('.db')
                ])
                while len(backups) > self.MAX_BACKUPS:
                    old = backups.pop(0)
                    os.remove(os.path.join(self.backup_dir, old))
                    logger.info(f"오래된 백업 삭제: {old}")
            except (sqlite3.Error, OSError) as e:
                logger.warning(f"백업 정리 실패: {e}")

    def restore_from_backup(self, backup_path: str) -> bool:
        """
        백업에서 복원

        Args:
            backup_path: 백업 파일 경로

        Returns:
            성공 여부
        """
        try:
            if not os.path.exists(backup_path):
                logger.error(f"백업 파일 없음: {backup_path}")
                return False

            # 현재 연결 종료
            self.close()

            # 복원 전 현재 DB 백업
            self.create_backup("before_restore")

            # 복원 수행
            import shutil
            shutil.copy2(backup_path, self.db_path)

            logger.info(f"DB 복원 완료: {backup_path}")
            return True

        except (sqlite3.Error, OSError) as e:
            logger.error(f"복원 실패: {e}")
            return False

    def get_backup_list(self) -> List[Dict]:
        """백업 목록 조회"""
        backups = []
        try:
            for f in os.listdir(self.backup_dir):
                if f.endswith('.db'):
                    path = os.path.join(self.backup_dir, f)
                    stat = os.stat(path)
                    backups.append({
                        'name': f,
                        'path': path,
                        'size_mb': stat.st_size / 1024 / 1024,
                        'created': datetime.fromtimestamp(stat.st_mtime)
                    })
            backups.sort(key=lambda x: x['created'], reverse=True)
        except (sqlite3.Error, OSError) as e:
            logger.error(f"백업 목록 조회 실패: {e}")
        return backups

    # =========================================================================
    # 개선 #2: WAL 모드
    # =========================================================================

    @classmethod
    def validate_lot_no(cls, lot_no: str, strict: bool = True) -> Tuple[bool, str]:
        """
        LOT 번호 유효성 검사. 단일 소스: engine_modules.validators.validate_lot_no
        strict 인자는 하위 호환용(무시). 검증 기준은 validators와 동일.
        """
        from engine_modules.validators import validate_lot_no as _validate_lot_no
        return _validate_lot_no(lot_no)

    @staticmethod
    def validate_weight(weight: float) -> Tuple[bool, str]:
        """
        무게 유효성 검사

        Args:
            weight: 검사할 무게 (kg)

        Returns:
            (유효 여부, 오류 메시지)
        """
        if weight is None:
            return False, "무게가 None입니다"

        try:
            weight = float(weight)
        except (ValueError, TypeError):
            return False, f"유효하지 않은 무게: {weight}"

        if weight < 0:
            return False, f"무게는 음수일 수 없습니다: {weight}"

        if weight > 50000:  # 50톤 초과
            return False, f"무게가 비정상적으로 큽니다: {weight}kg"

        return True, ""

    @staticmethod
    def validate_sap_no(sap_no: str) -> Tuple[bool, str]:
        """SAP NO 유효성 검사. 단일 소스: engine_modules.validators.validate_sap_no"""
        from core.validators import validate_sap_no as _validate_sap_no
        return _validate_sap_no(sap_no)

    # =========================================================================
    # 개선 #5: DB 락 감지
    # =========================================================================

    def _set_busy_timeout(self) -> None:
        """busy timeout 설정 (락 대기 시간)"""
        try:
            # 30초 대기 후 타임아웃
            self.execute("PRAGMA busy_timeout=30000")
            logger.debug("busy_timeout 설정: 30초")
        except (sqlite3.Error, OSError) as e:
            logger.warning(f"busy_timeout 설정 실패: {e}")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        SQL 실행 (락 감지 및 재시도 포함)
        v5.1.2: 상수 기반 재시도, 상세 로깅
        """
        retry_delay = DB_RETRY_DELAY

        for attempt in range(DB_MAX_RETRIES):
            try:
                cursor = self.conn.cursor()
                cursor.execute(sql, params)

                # ✅ 트랜잭션 중이면 commit하지 않음 (롤백 가능하도록)
                if not getattr(self._local, 'in_transaction', False):
                    self.conn.commit()

                return cursor
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < DB_MAX_RETRIES - 1:
                    logger.warning(
                        f"DB 락 감지, 재시도 {attempt + 1}/{DB_MAX_RETRIES} "
                        f"({retry_delay:.1f}s 대기) SQL: {sql[:80]}"
                    )
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= DB_RETRY_BACKOFF
                else:
                    raise

        raise sqlite3.OperationalError("DB 락 타임아웃")

    def executemany(self, sql: str, params_list: List[tuple]) -> sqlite3.Cursor:
        """
        Batch INSERT/UPDATE용 executemany (락 감지 포함)
        v5.1.2: 상수 기반 재시도
        """
        retry_delay = DB_RETRY_DELAY

        for attempt in range(DB_MAX_RETRIES):
            try:
                cursor = self.conn.cursor()
                cursor.executemany(sql, params_list)

                # ✅ 트랜잭션 중이면 commit하지 않음
                if not getattr(self._local, 'in_transaction', False):
                    self.conn.commit()

                return cursor
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < DB_MAX_RETRIES - 1:
                    logger.warning(
                        f"DB 락 감지 (executemany), 재시도 {attempt + 1}/{DB_MAX_RETRIES} "
                        f"({retry_delay:.1f}s 대기)"
                    )
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= DB_RETRY_BACKOFF
                else:
                    raise

        raise sqlite3.OperationalError("DB 락 타임아웃 (executemany)")

    def begin_transaction(self) -> None:
        """
        트랜잭션 시작 (v5.1.2: BEGIN IMMEDIATE 재시도 추가)
        
        ★★★ 중요 ★★★
        - _write_lock 획득
        - _in_transaction = True 설정
        - 중첩 호출 시 락만 유지 (BEGIN 재실행 안 함)
        - SQLITE_BUSY 시 지수 백오프 재시도 (최대 3회)
        """
        self._write_lock.acquire()
        if getattr(self._local, 'in_transaction', False):
            # 중첩 트랜잭션: 이미 시작됨 (RLock 카운터만 증가)
            return
        
        # BEGIN IMMEDIATE도 SQLITE_BUSY 가능 → 재시도
        max_retries = 3
        retry_delay = 0.5
        for attempt in range(max_retries):
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                self._local.in_transaction = True
                logger.debug("트랜잭션 시작 (BEGIN IMMEDIATE)")
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(
                        f"BEGIN IMMEDIATE 락 감지, 재시도 {attempt + 1}/{max_retries} "
                        f"({retry_delay:.1f}s 대기)"
                    )
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self._write_lock.release()
                    raise

    def commit(self) -> None:
        """
        트랜잭션 커밋 (v2.9.51: 락 해제 보장)
        """
        try:
            self.conn.commit()
            logger.debug("트랜잭션 커밋 완료")
        finally:
            self._local.in_transaction = False
            try:
                self._write_lock.release()
            except RuntimeError as _e:
                logger.debug(f"[database] 무시: {_e}")

    def rollback(self) -> None:
        """
        트랜잭션 롤백 (v2.9.51: 락 해제 보장)
        """
        try:
            self.conn.rollback()
            logger.debug("트랜잭션 롤백 완료")
        finally:
            self._local.in_transaction = False
            try:
                self._write_lock.release()
            except RuntimeError as _e:
                logger.debug(f"[database] 무시: {_e}")

    # v5.9.0 P0-7: _TransactionContext 제거 — L212의 @contextmanager transaction()이
    # HardStopException 보호를 포함한 유일한 구현.
    # 기존 _TransactionContext는 HardStop 보호 없이 transaction()을 덮어쓰고 있었음.

    def close_all(self) -> None:
        """v6.3.5: 모든 스레드 연결 종료 + WAL checkpoint.

        threading.local()로 스레드마다 독립 연결이 생성되므로
        close()는 호출 스레드 연결만 닫음.
        close_all()은 _all_connections 전체를 닫아
        Windows WinError 32(파일 잠금)없이 DB 삭제를 가능하게 함.
        """
        import gc
        # 1) WAL checkpoint: WAL 내용 main DB 병합 후 잠금 해제
        try:
            if hasattr(self._local, 'conn') and self._local.conn:
                self._local.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("[Database.close_all] WAL checkpoint(TRUNCATE) 완료")
        except Exception as _e:
            logger.debug(f"[Database.close_all] WAL checkpoint 실패(무시): {_e}")

        # 2) 등록된 모든 스레드 연결 종료
        with self._all_connections_lock:
            conns = list(self._all_connections)
            self._all_connections.clear()
        closed = 0
        for conn in conns:
            try:
                if conn:
                    conn.close()
                    closed += 1
            except Exception as _e:
                logger.debug(f"[Database.close_all] 연결 종료 예외(무시): {_e}")
        logger.info(f"[Database.close_all] {closed}개 연결 종료")

        # 3) thread-local 참조 제거
        if hasattr(self._local, 'conn'):
            self._local.conn = None
        self._cursor = None
        self._connection = None

        # 4) GC 강제 실행 — Python 내부 순환참조 정리
        gc.collect()

    def close(self) -> None:
        """
        연결 종료
        v2.5.4: thread-local 연결도 안전하게 종료 (Windows 파일잠김 방지)
        """
        # thread-local 연결 종료
        if hasattr(self, '_local') and hasattr(self._local, 'conn') and self._local.conn:
            try:
                self._local.conn.close()
            except (AttributeError, RuntimeError) as e:
                logger.debug(f'DB 예외 (무시): {e}')  # v2.9.75  # 연결 종료 예외 무시
            finally:
                self._local.conn = None

        # 기존 연결 종료
        if self._cursor:
            try:
                self._cursor.close()
            except (sqlite3.Error, OSError) as e:
                logger.debug(f'DB 예외 (무시): {e}')  # v2.9.75  # 커서 종료 예외 무시
            finally:
                self._cursor = None
        if self._connection:
            try:
                self._connection.close()
            except (sqlite3.Error, OSError) as e:
                logger.debug(f'DB 예외 (무시): {e}')  # v2.9.75  # 메인 연결 종료 예외 무시
            finally:
                self._connection = None

    def fetchone(self, sql: str, params: tuple = (),
                 use_cache: bool = False, cache_ttl: int = 30) -> Optional[dict]:
        """
        단일 행 조회 (dict 반환)

        v5.0.0: sqlite3.Row를 dict로 변환하여 반환
        v6.5.4: use_cache=True 시 QueryCache 경유 (SELECT 전용)
        """
        if use_cache and sql.strip().upper().startswith('SELECT'):
            try:
                from engine_modules.query_cache import QueryCache
                _cache = getattr(self, '_query_cache', None)
                if _cache is None:
                    self._query_cache = QueryCache(ttl=cache_ttl)
                    _cache = self._query_cache
                cached = _cache.get(sql, params)
                if cached is not None:
                    return cached
                cursor = self.conn.cursor()
                cursor.execute(sql, params)
                row = cursor.fetchone()
                result = dict(row) if row else None
                _cache.set(sql, params, result)
                return result
            except Exception as _ce:
                # v8.7.1 [VISIBILITY]: 캐시 실패를 debug 로깅 (구조적 수정은 Phase 2.5)
                logger.warning("[DB.fetchone] 캐시 경로 실패, 비캐시 폴백: %s", _ce, exc_info=True)
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = (),
                 use_cache: bool = False, cache_ttl: int = 30) -> List[dict]:
        """
        다중 행 조회 (list[dict] 반환)

        v5.0.0: sqlite3.Row를 dict로 변환하여 반환
        v6.5.4: use_cache=True 시 QueryCache 경유 (SELECT 전용)
        """
        if use_cache and sql.strip().upper().startswith('SELECT'):
            try:
                from engine_modules.query_cache import QueryCache
                _cache = getattr(self, '_query_cache', None)
                if _cache is None:
                    self._query_cache = QueryCache(ttl=cache_ttl)
                    _cache = self._query_cache
                cached = _cache.get(sql, params)
                if cached is not None:
                    return cached
                cursor = self.conn.cursor()
                cursor.execute(sql, params)
                result_raw = cursor.fetchall()
                result = [dict(row) for row in result_raw] if result_raw else []
                _cache.set(sql, params, result)
                return result
            except Exception as _ce:
                # v8.7.1 [VISIBILITY]: 캐시 실패를 warning 로깅 (구조적 수정은 Phase 2.5)
                logger.warning("[DB.fetchall] 캐시 경로 실패, 비캐시 폴백: %s", _ce, exc_info=True)
        try:
            from .performance import monitor
            import time
            start = time.time()
        except ImportError:
            monitor = None
            start = None

        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        result = cursor.fetchall()
        
        # v5.0.0: sqlite3.Row를 dict로 변환
        result = [dict(row) for row in result] if result else []
        
        # 성능 측정
        if monitor and start:
            elapsed = time.time() - start
            if elapsed > 0.5:  # 0.5초 이상 느린 쿼리만
                logger.warning(f"⚠️ 느린 쿼리 ({elapsed:.3f}s): {sql[:100]}...")
                monitor._record("DB_fetchall", elapsed, "fetchall")
        
        return result


    def cache_invalidate(self, pattern: str = None) -> None:
        """
        v6.5.4: 쓰기 작업 후 캐시 무효화
        INSERT/UPDATE/DELETE 후 호출하여 stale 데이터 방지
        """
        _cache = getattr(self, '_query_cache', None)
        if _cache is not None:
            _cache.invalidate(pattern)

    def cache_stats(self) -> dict:
        """v6.5.4: 캐시 통계 조회"""
        _cache = getattr(self, '_query_cache', None)
        if _cache is not None:
            return _cache.get_stats()
        return {'hits': 0, 'misses': 0, 'total': 0, 'hit_rate': 0.0, 'cache_size': 0}

    def _log_explain_query_plan_once(self) -> None:
        """
        앱 시작 시 1회 핵심 쿼리의 실행 계획(EXPLAIN QUERY PLAN) 로그를 남긴다.
        인덱스 적용 여부를 운영 환경에서 빠르게 점검하기 위한 진단 도구.
        """
        # 운영 기본 OFF: SQM_LOG_EQP=1 일 때만 활성화
        if str(os.environ.get("SQM_LOG_EQP", "")).strip().lower() not in ("1", "true", "yes", "on"):
            return

        if getattr(self, "_eqp_logged_once", False):
            return
        self._eqp_logged_once = True

        plans = [
            (
                "inbound_history_lot",
                "SELECT lot_no, sap_no, bl_no, product, net_weight, mxbg_pallet, container_no, warehouse, stock_date, status "
                "FROM inventory "
                "WHERE ((stock_date IS NOT NULL AND stock_date <> '' AND stock_date >= ? AND stock_date < ?) "
                "OR ((stock_date IS NULL OR stock_date = '') AND created_at >= ? AND created_at < ?)) "
                "ORDER BY stock_date DESC, lot_no",
                ("2026-01-01", "2026-02-01", "2026-01-01", "2026-02-01"),
            ),
            (
                "inbound_history_tonbag_join",
                "SELECT t.lot_no, t.sub_lt, t.tonbag_no, t.weight, t.is_sample, t.location, t.status, i.product, i.stock_date "
                "FROM inventory_tonbag t "
                "JOIN inventory i ON t.lot_no = i.lot_no "
                "WHERE ((i.stock_date IS NOT NULL AND i.stock_date <> '' AND i.stock_date >= ? AND i.stock_date < ?) "
                "OR ((i.stock_date IS NULL OR i.stock_date = '') AND i.created_at >= ? AND i.created_at < ?)) "
                "ORDER BY t.lot_no, t.sub_lt",
                ("2026-01-01", "2026-02-01", "2026-01-01", "2026-02-01"),
            ),
            (
                "do_update_raw_exact_bl",
                "SELECT lot_no, bl_no, product, net_weight, status, arrival_date, free_time, free_time_date, con_return, warehouse, container_no "
                "FROM inventory WHERE COALESCE(lot_no,'') <> '' AND COALESCE(bl_no, '') = ? COLLATE NOCASE ORDER BY lot_no",
                ("258468669",)  # v9.0: 숫자만 조회,
            ),
            (
                "movement_lot_history",
                "SELECT id, lot_no, movement_type, qty_kg, created_at "
                "FROM stock_movement WHERE lot_no = ? ORDER BY created_at DESC",
                ("1125122363",),
            ),
        ]

        try:
            cur = self.conn.cursor()
            logger.info("[EQP] 시작: 핵심 쿼리 실행 계획 점검")
            for name, sql, params in plans:
                try:
                    cur.execute("EXPLAIN QUERY PLAN " + sql, params)
                    rows = cur.fetchall() or []
                    details = []
                    for r in rows:
                        if hasattr(r, "keys"):
                            details.append(str(r["detail"]))
                        else:
                            details.append(str(r[3]))
                    logger.info(f"[EQP] {name}: {' | '.join(details)}")
                except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                    logger.debug(f"[EQP] {name} 점검 스킵: {e}")
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.debug(f"[EQP] 초기화 실패: {e}")

    def insert_returning_id(self, sql: str, params: tuple = ()) -> Optional[int]:
        """
        P3: INSERT 후 생성된 ID 반환 (DB 독립적)
        
        SQLite: cursor.lastrowid
        PostgreSQL 전환 시: RETURNING id 사용으로 오버라이드
        """
        cursor = self.execute(sql, params)
        return cursor.lastrowid if hasattr(cursor, 'lastrowid') else None

    # v5.9.4: _init_database, _init_*_table, _migrate_v243, _verify_schema,
    # _create_indexes → db_schema_mixin.py (DatabaseSchemaMixin)으로 분리

    # ── 아래는 모두 db_schema_mixin.py로 이동 (v5.9.4) ──
    # _init_shipment_table, _init_inventory_table, _init_tonbag_table,
    # _init_outbound_tables, _init_movement_tables, _init_snapshot_tables,
    # _migrate_v243, _verify_schema, get_schema_status, _create_indexes
    # ── END ──

    # 이전 코드 제거됨 — DatabaseSchemaMixin에서 제공


# ═══════════════════════════════════════════════════════════
# v8.6.6: 비동기 DB 헬퍼 (UI 스레드 락 회피용)
# ═══════════════════════════════════════════════════════════
# Use these for UI handler paths that may experience DB lock contention.
# The original sync functions (SQMDatabase.execute / fetchall / fetchone /
# begin_transaction 등) remain unchanged — battle-tested with hundreds of
# callers. These helpers ADD a non-breaking async submission path on top.
#
# Pattern:
#     fut = db_execute_async(db.fetchall, "SELECT ...", on_done=cb)
# The callable runs in a small worker pool (max_workers=4); on_done(result)
# is invoked from a follow-up thread when the work completes (or with the
# raised Exception object on failure). UI code is responsible for marshalling
# the on_done result back to the UI thread if needed.

_db_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sqm-db-")

# [2차 수정 2026-05-06] atexit 등록 — DB 락에 걸린 작업이 인터프리터 종료를 막지 않도록
# (max_workers=4 풀이라 개별 작업이 sqlite OperationalError 재시도 중일 수 있음).
import atexit as _atexit
_atexit.register(_db_executor.shutdown, wait=False)


def db_execute_async(callable_: Callable[..., Any], *args,
                     on_done: Optional[Callable[[Any], None]] = None,
                     **kwargs) -> Future:
    """
    임의의 DB 작업을 비동기로 제출.

    Use these for UI handler paths that may experience DB lock contention.
    The original sync functions remain unchanged.

    Args:
        callable_: 호출할 함수 (예: db.execute, db.fetchall, 사용자 콜백 등)
        *args, **kwargs: callable_에 전달할 인자
        on_done: 완료 시 호출할 콜백. 성공 시 결과값, 실패 시 예외 객체를
                 단일 인자로 받음. (None이면 호출 생략)

    Returns:
        concurrent.futures.Future — 호출자가 result()/exception()으로
        직접 결과를 받을 수도 있음.
    """
    fut = _db_executor.submit(callable_, *args, **kwargs)

    if on_done is not None:
        def _done_cb(f: Future) -> None:
            try:
                exc = f.exception()
                payload = exc if exc is not None else f.result()
            except Exception as _e:  # pragma: no cover - 방어적
                payload = _e
            try:
                on_done(payload)
            except Exception:
                logger.exception("[db_execute_async] on_done 콜백 실패")

        fut.add_done_callback(_done_cb)

    return fut


def db_query_async(db: 'SQMDatabase', sql: str, params: tuple = (),
                   on_done: Optional[Callable[[Any], None]] = None) -> Future:
    """
    SELECT 쿼리를 비동기로 제출 (SQMDatabase.fetchall 래핑).

    Use these for UI handler paths that may experience DB lock contention.
    The original sync functions remain unchanged.

    Args:
        db: SQMDatabase 인스턴스 (sync fetchall 호출에 사용).
        sql: 실행할 SQL 문자열.
        params: 바인딩 파라미터 튜플.
        on_done: 완료 시 호출할 콜백. 성공 시 list[dict], 실패 시 예외 객체를
                 단일 인자로 받음.

    Returns:
        concurrent.futures.Future
    """
    return db_execute_async(db.fetchall, sql, params, on_done=on_done)
