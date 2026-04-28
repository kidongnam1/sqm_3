# -*- coding: utf-8 -*-
"""
engine_modules/migration_manager.py — SQM v8.3.0
===================================================
DB 마이그레이션 버전 관리 (Alembic 스타일)

기능:
  1. schema_version 테이블로 현재 DB 버전 추적
  2. 어느 버전에서 시작해도 안전하게 최신 버전으로 업그레이드
  3. 마이그레이션 이력 기록 (언제, 어떤 버전으로 올렸는지)
  4. 롤백 불필요 — 각 마이그레이션은 IF NOT EXISTS로 멱등성 보장

사용 예:
    from engine_modules.migration_manager import MigrationManager
    mgr = MigrationManager(db)
    mgr.upgrade()         # 최신 버전으로 업그레이드
    mgr.current_version() # 현재 버전 확인
    mgr.history()         # 마이그레이션 이력 조회
"""

import logging
from datetime import datetime
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)

# ── 버전 번호 체계 ────────────────────────────────────────────────
# (version_int, version_str, description)
# version_int: 비교용 정수 (예: 2890 = v2.8.9)
MIGRATION_REGISTRY: List[tuple] = [
    (289,  'v2.8.9',  'Picking List 테이블'),
    (388,  'v3.8.8',  '컬럼 통일 마이그레이션'),
    (391,  'v3.9.1',  '샘플 톤백 마이그레이션'),
    (396,  'v3.9.6',  '검색 인덱스 6개'),
    (420,  'v4.2.0',  'tonbag_uid 마이그레이션'),
    (423,  'v4.2.3',  '톤백 위치 관리'),
    (520,  'v5.2.0',  'tonbag_no TEXT'),
    (588,  'v5.8.8',  'con_return 컬럼'),
    (591,  'v5.9.1',  'tonbag FK 컬럼'),
    (593,  'v5.9.3',  'allocation_plan 테이블'),
    (5992, 'v5.9.92', 'allocation_plan.source'),
    (599,  'v5.9.9',  'missing_columns'),
    (600,  'v6.0.0',  'picking/sold 테이블'),
    (601,  'v6.0.1',  'picking_list meta'),
    (622,  'v6.2.2',  '조회 성능 인덱스'),
    (623,  'v6.2.3',  'stock_movement audit 컬럼'),
    (624,  'v6.2.4',  'allocation fingerprint'),
    (625,  'v6.2.5',  'uid_swap 인덱스'),
    (626,  'v6.2.6',  'allocation lot_mode 인덱스'),
    (627,  'v6.2.7',  'stock_movement ref 컬럼'),
    (628,  'v6.2.8',  'allocation_import_batch'),
    (629,  'v6.2.9',  'allocation gate 컬럼'),
    (630,  'v6.3.0',  'allocation approval workflow'),
    (631,  'v6.3.1',  'sales_order perf'),
    (632,  'v6.3.2',  'sales_order_import_log'),
    (633,  'v6.3.3',  'allocation export_type'),
    (635,  'v6.3.5',  'outbound_no'),
    (675,  'v6.7.5',  'ALLOC_CONFLICT 인덱스'),
    (686,  'v6.8.6',  '성능 인덱스'),
    (691,  'v6.9.1',  'picking_table 컬럼'),
    (700,  'v7.0.0',  'return_log 통합'),
    (710,  'v7.1.0',  'return_history → return_log'),
    (720,  'v7.2.0',  '입고 파싱 템플릿'),
    (740,  'v7.4.0',  '피킹 템플릿'),
    (800,  'v8.0.0',  'BL 번호 형식'),
    (809,  'v8.0.9',  'inline_edit'),
    (817,  'v8.1.7',  'tonbag_move_log'),
    (830,  'v8.3.0',  'audit_log + daily_report + schema_version'),
]


class MigrationManager:
    """DB 마이그레이션 버전 관리자."""

    SCHEMA_VERSION_TABLE = 'schema_version'

    def __init__(self, db):
        """
        Args:
            db : SQMDatabase 인스턴스
        """
        self.db = db
        self._ensure_version_table()

    # ── 초기화 ───────────────────────────────────────────────────
    def _ensure_version_table(self) -> None:
        """schema_version 테이블 생성 (없으면)."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_int  INTEGER NOT NULL,
                    version_str  TEXT    NOT NULL,
                    description  TEXT,
                    applied_at   TEXT    NOT NULL
                )
            """)
            self.db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_schema_version_int
                ON schema_version(version_int)
            """)
            logger.debug("[MigrationManager] schema_version 테이블 확인 완료")
        except Exception as e:
            logger.warning(f"[MigrationManager] schema_version 테이블 생성 실패: {e}")

    # ── 버전 조회 ────────────────────────────────────────────────
    def current_version(self) -> Optional[int]:
        """현재 적용된 최신 버전 번호 반환."""
        try:
            row = self.db.fetchone(
                "SELECT MAX(version_int) AS v FROM schema_version"
            )
            v = row.get('v') if isinstance(row, dict) else (row[0] if row else None)
            return int(v) if v is not None else 0
        except Exception:
            return 0

    def current_version_str(self) -> str:
        """현재 버전 문자열 반환."""
        try:
            row = self.db.fetchone(
                "SELECT version_str FROM schema_version "
                "ORDER BY version_int DESC LIMIT 1"
            )
            if isinstance(row, dict):
                return row.get('version_str', 'unknown')
            return row[0] if row else 'unknown'
        except Exception:
            return 'unknown'

    def history(self) -> List[dict]:
        """마이그레이션 적용 이력 반환."""
        try:
            rows = self.db.fetchall(
                "SELECT version_int, version_str, description, applied_at "
                "FROM schema_version ORDER BY version_int ASC"
            )
            return [
                dict(r) if isinstance(r, dict) else {
                    'version_int': r[0], 'version_str': r[1],
                    'description': r[2], 'applied_at':  r[3],
                }
                for r in (rows or [])
            ]
        except Exception:
            return []

    def _mark_applied(self, version_int: int, version_str: str,
                      description: str) -> None:
        """버전 적용 완료 기록."""
        try:
            self.db.execute(
                """INSERT OR IGNORE INTO schema_version
                   (version_int, version_str, description, applied_at)
                   VALUES (?, ?, ?, ?)""",
                (version_int, version_str, description,
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
        except Exception as e:
            logger.debug(f"[MigrationManager] 버전 기록 스킵: {e}")

    # ── 업그레이드 ───────────────────────────────────────────────
    def upgrade(self, target_version: Optional[int] = None) -> dict:
        """
        현재 버전에서 target_version(기본: 최신)까지 순차 업그레이드.

        Returns:
            {'applied': [버전목록], 'skipped': [버전목록], 'current': 버전번호}
        """
        cur = self.current_version()
        target = target_version or MIGRATION_REGISTRY[-1][0]

        applied = []
        skipped = []

        for version_int, version_str, description in MIGRATION_REGISTRY:
            if version_int <= cur:
                skipped.append(version_int)
                continue
            if version_int > target:
                break

            try:
                self._run_migration(version_int)
                self._mark_applied(version_int, version_str, description)
                applied.append(version_int)
                logger.info(
                    f"[MigrationManager] ✅ {version_str} 적용: {description}"
                )
            except Exception as e:
                logger.error(
                    f"[MigrationManager] ❌ {version_str} 실패: {e}"
                )
                # 마이그레이션 실패는 경고만 — 업무 차단 안 함

        result = {
            'applied':  applied,
            'skipped':  len(skipped),
            'current':  self.current_version(),
            'version_str': self.current_version_str(),
        }

        if applied:
            logger.info(
                f"[MigrationManager] 업그레이드 완료: "
                f"{len(applied)}개 적용, {len(skipped)}개 스킵"
            )
        else:
            logger.debug("[MigrationManager] 이미 최신 버전")

        return result

    def _run_migration(self, version_int: int) -> None:
        """버전별 마이그레이션 실행 (db_migration_mixin 위임)."""
        method_map = {
            289:  '_migrate_v289_picking_list',
            388:  '_migrate_v388_column_unify',
            391:  '_migrate_v391_sample_tonbag',
            396:  '_migrate_v396_search_indexes',
            420:  '_migrate_v420_tonbag_uid',
            423:  '_migrate_v423_tonbag_location',
            520:  '_migrate_v520_tonbag_no_text',
            588:  '_migrate_v588_con_return',
            591:  '_migrate_v591_tonbag_fk_columns',
            593:  '_migrate_v593_allocation_plan',
            5992: '_migrate_v5992_allocation_source',
            599:  '_migrate_v599_missing_columns',
            600:  '_migrate_v600_picking_sold_tables',
            601:  '_migrate_v601_picking_list_meta',
            622:  '_migrate_v622_query_indexes',
            623:  '_migrate_v623_stock_movement_audit_columns',
            624:  '_migrate_v624_allocation_fingerprint',
            625:  '_migrate_v625_uid_swap_report_indexes',
            626:  '_migrate_v626_allocation_lot_mode_indexes',
            627:  '_migrate_v627_stock_movement_ref_columns',
            628:  '_migrate_v628_allocation_import_batch',
            629:  '_migrate_v629_allocation_gate_columns',
            630:  '_migrate_v630_allocation_approval_workflow',
            631:  '_migrate_v631_sales_order_perf',
            632:  '_migrate_v632_sales_order_import_log',
            633:  '_migrate_v633_allocation_export_type',
            635:  '_migrate_v635_outbound_no',
            675:  '_migrate_v675_conflict_indexes',
            686:  '_migrate_v686_performance_indexes',
            691:  '_migrate_v691_picking_table_cols',
            700:  '_migrate_v700_return_log_reinbound',
            710:  '_migrate_v710_return_history_to_log',
            720:  '_migrate_v720_inbound_template',
            740:  '_migrate_v740_picking_template',
            800:  '_migrate_v800_template_bl_format',
            809:  '_migrate_v809_inline_edit',
            817:  '_migrate_v817_tonbag_move_log',
            830:  '_migrate_v830_audit_daily_report',
        }
        method_name = method_map.get(version_int)
        if method_name and hasattr(self.db, method_name):
            getattr(self.db, method_name)()

    def sync_existing(self) -> int:
        """
        기존 DB (schema_version 없는 구버전)에서 호출 시
        현재 실제로 존재하는 테이블/컬럼을 탐지해 schema_version 동기화.

        Returns:
            동기화된 버전 수
        """
        synced = 0
        try:
            tables = {
                r['name'] if isinstance(r, dict) else r[0]
                for r in (self.db.fetchall(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ) or [])
            }

            # 테이블 존재 여부로 버전 추론
            checks = [
                (289,  'picking_table',           'picking_list 테이블'),
                (420,  'inventory_tonbag',         'tonbag_uid'),
                (593,  'allocation_plan',          'allocation_plan'),
                (628,  'allocation_import_batch',  'import_batch'),
                (700,  'return_history',           'return_log'),
                (817,  'tonbag_move_log',          'tonbag_move_log'),
            ]

            for version_int, table_name, desc in checks:
                if table_name in tables:
                    row = self.db.fetchone(
                        "SELECT id FROM schema_version WHERE version_int=?",
                        (version_int,)
                    )
                    if not row:
                        version_str = next(
                            (v for vi, v, _ in MIGRATION_REGISTRY if vi == version_int),
                            f'v{version_int}'
                        )
                        self._mark_applied(version_int, version_str,
                                           f'[sync] {desc}')
                        synced += 1

            if synced:
                logger.info(
                    f"[MigrationManager] 기존 DB 동기화: {synced}개 버전 등록"
                )
        except Exception as e:
            logger.warning(f"[MigrationManager] sync_existing 실패: {e}")

        return synced
