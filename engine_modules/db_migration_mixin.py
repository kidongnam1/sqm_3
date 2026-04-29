# -*- coding: utf-8 -*-
"""
SQM Inventory - Database Migration Mixin
=========================================

v3.9.6 - Extracted from database.py (1,378 lines → 분할)

마이그레이션 함수들만 분리:
- _migrate_v243
- _migrate_v289_picking_list
- _migrate_v388_column_unify
- _migrate_v391_sample_tonbag
- _migrate_v396_search_indexes
"""

import logging
import re
import sqlite3

logger = logging.getLogger(__name__)


class DatabaseMigrationMixin:
    """마이그레이션 전용 Mixin — SQMDatabase에 MRO로 합성"""

    def _run_all_migrations(self) -> None:
        """모든 마이그레이션 순차 실행 (v243 제외 — database.py에서 직접 호출)"""
        if getattr(self, '_migrations_applied', False):
            logger.debug("[마이그레이션] 이미 실행됨 — 스킵")
            return
        self._migrations_applied = True
        self._migrate_v289_picking_list()
        self._migrate_v388_column_unify()
        self._migrate_v391_sample_tonbag()
        self._migrate_v396_search_indexes()
        self._migrate_v420_tonbag_uid()
        self._migrate_v423_tonbag_location()
        self._migrate_v520_tonbag_no_text()
        self._migrate_v588_con_return()
        self._migrate_v591_tonbag_fk_columns()
        self._migrate_v593_allocation_plan()
        self._migrate_v5992_allocation_source()
        self._migrate_v599_missing_columns()
        self._migrate_v600_picking_sold_tables()
        self._migrate_v601_picking_list_meta()
        self._migrate_v622_query_indexes()
        self._migrate_v623_stock_movement_audit_columns()
        self._migrate_v624_allocation_fingerprint()
        self._migrate_v625_uid_swap_report_indexes()
        self._migrate_v626_allocation_lot_mode_indexes()
        self._migrate_v627_stock_movement_ref_columns()
        self._migrate_v628_allocation_import_batch()
        self._migrate_v629_allocation_gate_columns()
        self._migrate_v630_allocation_approval_workflow()
        self._migrate_v631_sales_order_perf()
        self._migrate_v632_sales_order_import_log()
        self._migrate_v633_allocation_export_type()   # v2.6.1: export_type 컬럼
        self._migrate_v635_outbound_no()
        self._migrate_v700_return_log_reinbound()      # v7.0.0: RETURN_AS_REINBOUND 정책
        self._migrate_v675_conflict_indexes()           # v6.7.5: ALLOC_CONFLICT 인덱스 2개
        self._migrate_v710_return_history_to_log()     # v7.1.0: return_history → return_log 통합
        self._migrate_v720_inbound_template()          # v7.2.0: 입고 파싱 템플릿 관리
        self._migrate_v800_template_bl_format()         # v8.0.0: BL 번호 형식 직접 지정
        self._migrate_v740_picking_template()          # v7.4.0: 출고 피킹 템플릿 (고객사 프로파일)
        self._migrate_v686_performance_indexes()       # v6.8.6: 성능 인덱스
        self._migrate_v691_picking_table_cols()        # v6.9.1: picking_list_no, gate1_result (status, lot_status, alloc_sale_ref)
        self._migrate_v809_inline_edit()
        self._migrate_v817_tonbag_move_log()           # v8.1.7: 톤백 이동 이력 테이블
        self._migrate_v857_sold_table_outbound_report()  # v8.5.7: 출고 보고서용 컬럼 추가
        self._migrate_v271_allocation_sc_rcvd()           # v2.7.1: allocation_plan SC RCVD 컬럼
        self._migrate_v271_add_missing_indexes()          # v2.7.1: 누락 인덱스 3개 추가
        self._migrate_v870_inventory_bl_invoice_cols()    # v8.7.0: inventory BL/Invoice 6컬럼 추가
        self._migrate_v870_container_freetime_tables()    # v8.7.0 Phase 3-A: 컨테이너/반납일 1:N 테이블
        self._migrate_v870_document_invoice()             # v8.7.0 Phase 3-B: Invoice 전필드 보존 테이블
        self._migrate_v870_document_bl()                  # v8.7.0 Phase 3-B: BL 전필드 보존 테이블
        self._migrate_v870_document_pl()                  # v8.7.0 Phase 3-B: PL 헤더/요약 보존 테이블
        self._migrate_v870_document_do()                  # v8.7.0 Phase 3-B: DO 전필드 보존 테이블
        # P0/P1 보안/데이터 무결성 패치
        self._migrate_v871_allocation_no_dup_index()      # v8.7.1 P0-4: allocation_plan 중복 예약 방지
        self._migrate_v871_inventory_weight_floor()        # v8.7.1 P0-5: inventory 음수 중량 방지 트리거
        self._migrate_v871_allocation_tonbag_id_index()   # v8.7.1 P1-8: allocation_plan.tonbag_id 인덱스
        # Phase 4-A 회귀 강화 패치
        self._migrate_v872_inventory_weight_floor_insert()  # v8.7.2 P1: INSERT 경로 음수 방지 트리거
        self._migrate_v872_sold_table_dedup_index()         # v8.7.2 P4: sold_table 중복 방지 인덱스

    def _migrate_v633_allocation_export_type(self) -> None:
        """
        v6.3.3 RUBI patch: allocation_plan.export_type 컬럼 추가.

        목적: Allocation 파일의 Export 컬럼값('반송', '일반수출' 등)을 DB에 보존.
        - 빈 문자열 기본값 → 기존 행 NULL 없음
        - 향후 활용: 세관 신고 구분, 반송 전용 리포트, 출고 유형별 필터링

        마이그레이션 안전:
        - duplicate column 오류 → 조용히 무시 (이미 존재)
        - 기타 오류 → warning 로그 후 계속 진행
        """
        try:
            self.execute(
                "ALTER TABLE allocation_plan ADD COLUMN export_type TEXT DEFAULT ''"
            )
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_alloc_plan_export_type "
                "ON allocation_plan(export_type)"
            )
            logger.info("[v6.3.3] allocation_plan.export_type 컬럼 추가 완료")
        except (sqlite3.OperationalError, OSError) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                logger.debug("[v6.3.3] allocation_plan.export_type 이미 존재")
            else:
                logger.warning(f"[v6.3.3] allocation_plan.export_type 추가 오류: {e}")

    def _migrate_v635_outbound_no(self) -> None:
        """v6.3.5: outbound 테이블 outbound_no, total_lots 컬럼 (RUBI 패치·출고번호 콤보/배너용)."""
        for col, ctype in [("outbound_no", "TEXT"), ("total_lots", "INTEGER DEFAULT 0")]:
            try:
                self.execute(f"ALTER TABLE outbound ADD COLUMN {col} {ctype}")
                logger.info(f"[v6.3.5] outbound.{col} 추가됨")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" not in str(e).lower() and "already exists" not in str(e).lower():
                    logger.debug(f"[v6.3.5] outbound.{col} 스킵: {e}")

    def _migrate_v700_return_log_reinbound(self) -> None:
        """
        v7.0.0: RETURN_AS_REINBOUND 정책 — return_log 컬럼 3개 추가.

        추가 컬럼:
          - processed_as  TEXT DEFAULT 'REINBOUND'  (정책 식별자)
          - new_location  TEXT                       (PDA 재스캔 위치)
          - operator_id   TEXT DEFAULT 'SYSTEM'      (작업자 추적)

        멱등성 보장: 이미 컬럼이 존재하면 건너뜀.
        기존 row backfill: processed_as=NULL 이면 'REINBOUND' 으로 채움.

        앱 시작 시 _run_all_migrations() 에 의해 1회 자동 실행됨.
        수동 실행 불필요.
        """
        new_cols = [
            ("processed_as", "TEXT DEFAULT 'REINBOUND'"),
            ("new_location",  "TEXT"),
            ("operator_id",   "TEXT DEFAULT 'SYSTEM'"),
        ]
        added = []
        for col_name, col_def in new_cols:
            try:
                self.execute(
                    f"ALTER TABLE return_log ADD COLUMN {col_name} {col_def}"
                )
                added.append(col_name)
                logger.info(f"[v7.0.0] return_log.{col_name} 추가됨")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" not in str(e).lower() and "already exists" not in str(e).lower():
                    logger.debug(f"[v7.0.0] return_log.{col_name} 스킵: {e}")

        # 기존 row backfill (NULL → 기본값)
        if added:
            try:
                self.execute(
                    "UPDATE return_log SET processed_as = 'REINBOUND' "
                    "WHERE processed_as IS NULL"
                )
                self.execute(
                    "UPDATE return_log SET operator_id = 'SYSTEM' "
                    "WHERE operator_id IS NULL"
                )
                logger.info(
                    f"[v7.0.0] return_log backfill 완료 "
                    f"(추가된 컬럼: {', '.join(added)})"
                )
            except (sqlite3.OperationalError, OSError) as e:
                logger.warning(f"[v7.0.0] return_log backfill 오류: {e}")

    def _migrate_v675_conflict_indexes(self) -> None:
        """
        v6.7.5 [A][B]: Allocation Row 충돌 차단 + 성능 인덱스 추가

        [A] idx_alloc_plan_lot_customer_ref:
            reserve_from_allocation의 ALLOC_CONFLICT 검사 쿼리 최적화
            (lot_no, customer, sale_ref, status) 복합 조회

        [B] idx_alloc_plan_customer_status:
            고객사별 예약 현황 조회 최적화 (allocation_dialog 필터 등)
        """
        try:
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_alloc_plan_lot_customer_ref "
                "ON allocation_plan(lot_no, customer, sale_ref, status)"
            )
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_alloc_plan_customer_status "
                "ON allocation_plan(customer, status)"
            )
            self.commit()
            logger.info("[v6.7.5] allocation_plan 충돌차단+성능 인덱스 2개 추가 완료")
        except Exception as e:
            logger.error(f"[v6.7.5] _migrate_v675_conflict_indexes 실패: {e}")
            try:
                self.rollback()
            except Exception:
                logger.debug("[SUPPRESSED] exception in db_migration_mixin.py")  # noqa


    def _migrate_v631_sales_order_perf(self) -> None:
        """
        v6.2.3: Sales Order 업로드 성능/정합성 보강
        - picking_table 복합 인덱스(샘플/일반 필터 포함)
        - sold_table 조회 인덱스
        """
        try:
            self.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_picking_lot_pick_status_sample_id
                ON picking_table(lot_no, picking_no, status, is_sample, id)
                """
            )
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v6.2.3] idx_picking_lot_pick_status_sample_id 스킵: {e}")

        try:
            self.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_picking_lot_pick_status_id
                ON picking_table(lot_no, picking_no, status, id)
                """
            )
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v6.2.3] idx_picking_lot_pick_status_id 스킵: {e}")

        try:
            self.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sold_order_status
                ON sold_table(sales_order_no, status)
                """
            )
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v6.2.3] idx_sold_order_status 스킵: {e}")

    def _migrate_v632_sales_order_import_log(self) -> None:
        """
        v6.2.3: Sales Order 업로드 감사 로그 테이블.
        """
        try:
            self.execute(
                """
                CREATE TABLE IF NOT EXISTS sales_order_import_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_run_id TEXT,
                    sales_order_no TEXT,
                    file_name TEXT,
                    file_hash TEXT,
                    mode TEXT DEFAULT 'normal',
                    sold_count INTEGER DEFAULT 0,
                    pending_count INTEGER DEFAULT 0,
                    warnings_json TEXT DEFAULT '[]',
                    elapsed_ms INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    created_by TEXT DEFAULT 'system'
                )
                """
            )
            self.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_so_import_log_run
                ON sales_order_import_log(import_run_id)
                """
            )
            self.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_so_import_log_so
                ON sales_order_import_log(sales_order_no, created_at)
                """
            )
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] sales_order_import_log 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v630_allocation_approval_workflow(self) -> None:
        """
        v6.2.3: Allocation 승인 워크플로우 스키마
        - allocation_plan: workflow_status/risk_flags/approved_by/approved_at/rejected_reason
        - allocation_approval: 승인/반려 이력
        """
        alter_cols = [
            ("workflow_status", "TEXT DEFAULT 'AUTO_APPROVED'"),
            ("risk_flags", "TEXT DEFAULT ''"),
            ("approved_by", "TEXT"),
            ("approved_at", "TEXT"),
            ("rejected_reason", "TEXT"),
        ]
        try:
            for col_name, col_type in alter_cols:
                try:
                    self.execute(f"ALTER TABLE allocation_plan ADD COLUMN {col_name} {col_type}")
                    logger.info(f"[v6.2.3] allocation_plan.{col_name} 컬럼 추가 완료")
                except (sqlite3.OperationalError, OSError) as e:
                    if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                        logger.debug(f"[v6.2.3] allocation_plan.{col_name} 이미 존재")
                    else:
                        raise

            self.execute(
                """
                CREATE TABLE IF NOT EXISTS allocation_approval (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    allocation_plan_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    actor TEXT,
                    reason TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_alloc_approval_plan ON allocation_approval(allocation_plan_id, created_at)"
            )
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_alloc_plan_workflow ON allocation_plan(status, workflow_status, lot_no)"
            )
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] allocation 승인 워크플로우 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v627_stock_movement_ref_columns(self) -> None:
        """
        v6.2.3: stock_movement 근거 추적 컬럼 보강
        - ref_table/ref_id/source/actor/details_json
        """
        alter_cols = [
            ("ref_table", "TEXT"),
            ("ref_id", "INTEGER"),
            ("source", "TEXT"),
            ("actor", "TEXT"),
            ("details_json", "TEXT"),
        ]
        try:
            for col_name, col_type in alter_cols:
                try:
                    self.execute(f"ALTER TABLE stock_movement ADD COLUMN {col_name} {col_type}")
                    logger.info(f"[v6.2.3] stock_movement.{col_name} 컬럼 추가 완료")
                except (sqlite3.OperationalError, OSError) as e:
                    if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                        logger.debug(f"[v6.2.3] stock_movement.{col_name} 이미 존재")
                    else:
                        raise
            try:
                self.execute(
                    "CREATE INDEX IF NOT EXISTS idx_stock_mv_ref ON stock_movement(ref_table, ref_id)"
                )
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v6.2.3] idx_stock_mv_ref 생성 스킵: {e}")
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] stock_movement ref 컬럼 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v628_allocation_import_batch(self) -> None:
        """
        v6.2.3: allocation_import_batch 테이블 추가
        - Allocation 업로드 이력/실패 리포트 경로 기록
        """
        try:
            self.execute(
                """
                CREATE TABLE IF NOT EXISTS allocation_import_batch (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT,
                    conflict_policy TEXT DEFAULT 'block_duplicates',
                    total_lines INTEGER DEFAULT 0,
                    passed_lines INTEGER DEFAULT 0,
                    failed_lines INTEGER DEFAULT 0,
                    report_csv_path TEXT,
                    report_json_path TEXT,
                    imported_at TEXT DEFAULT (datetime('now'))
                )
                """
            )
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] allocation_import_batch 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v629_allocation_gate_columns(self) -> None:
        """
        v6.2.3: allocation_plan 원장/검증 컬럼 보강
        - import_batch_id/line_no
        - gate_status/fail_code/fail_reason/validated_at
        - ux_alloc_line(import_batch_id, line_no)
        """
        alter_cols = [
            ("import_batch_id", "INTEGER"),
            ("line_no", "INTEGER"),
            ("gate_status", "TEXT"),
            ("fail_code", "TEXT"),
            ("fail_reason", "TEXT"),
            ("validated_at", "TEXT"),
        ]
        try:
            for col_name, col_type in alter_cols:
                try:
                    self.execute(f"ALTER TABLE allocation_plan ADD COLUMN {col_name} {col_type}")
                    logger.info(f"[v6.2.3] allocation_plan.{col_name} 컬럼 추가 완료")
                except (sqlite3.OperationalError, OSError) as e:
                    if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                        logger.debug(f"[v6.2.3] allocation_plan.{col_name} 이미 존재")
                    else:
                        raise
            try:
                self.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_alloc_line ON allocation_plan(import_batch_id, line_no)"
                )
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v6.2.3] ux_alloc_line 생성 스킵: {e}")
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] allocation_plan gate 컬럼 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v622_query_indexes(self) -> None:
        """
        v6.2.2: 조회/후속연결 성능 인덱스 보강
        - 입고현황 조회 기간 필터(stock_date, created_at)
        - D/O 후속 연결 BL 매칭(case-insensitive)
        - LOT 이동 이력 조회(lot_no + created_at)
        """
        idx_sql = [
            "CREATE INDEX IF NOT EXISTS idx_inventory_created_at ON inventory(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_stock_created ON inventory(stock_date, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_bl_no_nocase ON inventory(bl_no COLLATE NOCASE)",
            "CREATE INDEX IF NOT EXISTS idx_movement_lot_created ON stock_movement(lot_no, created_at)",
        ]
        added = 0
        for sql in idx_sql:
            try:
                self.execute(sql)
                added += 1
            except (sqlite3.OperationalError, OSError) as _e:
                logger.debug(f"[v6.2.2] 인덱스 생성 스킵: {_e}")
        if added:
            try:
                self.execute("ANALYZE")
            except (sqlite3.OperationalError, OSError) as _e:
                logger.debug(f"[v6.2.2] ANALYZE 스킵: {_e}")
            self.commit()
            logger.info(f"[v6.2.2] 조회 성능 인덱스 {added}개 점검/생성")

    def _migrate_v623_stock_movement_audit_columns(self) -> None:
        """
        v6.2.3: stock_movement 감사 추적 컬럼 보강
        - source_type: 변경 출처 구분
        - source_file: 원본 파일 경로/파일명
        """
        try:
            try:
                self.execute("ALTER TABLE stock_movement ADD COLUMN source_type TEXT DEFAULT ''")
                logger.info("[v6.2.3] stock_movement.source_type 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.debug(f"[v6.2.3] stock_movement.source_type 이미 존재: {e}")
                else:
                    raise

            try:
                self.execute("ALTER TABLE stock_movement ADD COLUMN source_file TEXT DEFAULT ''")
                logger.info("[v6.2.3] stock_movement.source_file 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.debug(f"[v6.2.3] stock_movement.source_file 이미 존재: {e}")
                else:
                    raise
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] stock_movement 감사 컬럼 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v624_allocation_fingerprint(self) -> None:
        """
        v6.2.3: allocation_plan.source_fingerprint 컬럼 추가 (중복 업로드 감지 강화)
        """
        try:
            try:
                self.execute("ALTER TABLE allocation_plan ADD COLUMN source_fingerprint TEXT DEFAULT ''")
                logger.info("[v6.2.3] allocation_plan.source_fingerprint 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.debug(f"[v6.2.3] allocation_plan.source_fingerprint 이미 존재: {e}")
                else:
                    raise
            try:
                self.execute(
                    "CREATE INDEX IF NOT EXISTS idx_alloc_plan_source_fp "
                    "ON allocation_plan(source_fingerprint)"
                )
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v6.2.3] idx_alloc_plan_source_fp 생성 스킵: {e}")
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] allocation fingerprint 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v625_uid_swap_report_indexes(self) -> None:
        """
        v6.2.3: Swap 리포트 조회 성능용 인덱스 보강
        - uid_swap_history.created_at
        - uid_swap_history.lot_no + created_at
        """
        try:
            self.execute(
                """
                CREATE TABLE IF NOT EXISTS uid_swap_history (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no              TEXT NOT NULL,
                    expected_tonbag_id  INTEGER,
                    expected_uid        TEXT,
                    scanned_tonbag_id   INTEGER,
                    scanned_uid         TEXT,
                    reason              TEXT,
                    created_at          TEXT DEFAULT (datetime('now'))
                )
                """
            )
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_uid_swap_created_at ON uid_swap_history(created_at)"
            )
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_uid_swap_lot_created ON uid_swap_history(lot_no, created_at)"
            )
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] uid_swap_history 인덱스 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v626_allocation_lot_mode_indexes(self) -> None:
        """
        v6.2.3: LOT 단위 예약 모드 조회/소진 성능 인덱스
        - allocation_plan(status, tonbag_id, lot_no)
        """
        try:
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_alloc_plan_status_tonbag_lot "
                "ON allocation_plan(status, tonbag_id, lot_no)"
            )
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v6.2.3] allocation_plan LOT 모드 인덱스 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v601_picking_list_meta(self) -> None:
        """v6.1.0: picking_list_order 메타데이터 컬럼 추가 (Gate-1 연동)."""
        add_cols = [
            ('picking_list_order', 'picking_no', "TEXT DEFAULT ''"),
            ('picking_list_order', 'delivery_terms', "TEXT DEFAULT ''"),
            ('picking_list_order', 'port_loading', "TEXT DEFAULT ''"),
            ('picking_list_order', 'port_discharge', "TEXT DEFAULT ''"),
            ('picking_list_order', 'containers', "INTEGER DEFAULT 1"),
            ('picking_list_order', 'contact_person', "TEXT DEFAULT ''"),
            ('picking_list_order', 'contact_email', "TEXT DEFAULT ''"),
            ('picking_list_order', 'total_nw_kg', "TEXT DEFAULT ''"),
            ('picking_list_order', 'total_gw_kg', "TEXT DEFAULT ''"),
            ('picking_list_order', 'gate1_result', "TEXT DEFAULT ''"),
        ]
        for table, col, col_type in add_cols:
            try:
                self.execute(f'ALTER TABLE {table} ADD COLUMN {col} {col_type}')
                logger.info(f'[v6.1.0] {table}.{col} 추가')
            except sqlite3.OperationalError as e:
                logger.debug(f'[v6.1.0] {col} 이미 존재: {e}')
        try:
            self.commit()
        except sqlite3.OperationalError:
            logger.debug("[SUPPRESSED] exception in db_migration_mixin.py")  # noqa

    def _migrate_v588_con_return(self) -> None:
        """
        v5.8.8: inventory.con_return, inventory_tonbag.con_return 추가
        D/O의 Free_Time 컬럼 = 컨테이너 반납일(날짜). free_time = (con_return - arrival_date) 일수.
        """
        try:
            for table, col in [('inventory', 'con_return'), ('inventory_tonbag', 'con_return')]:
                try:
                    self.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                    logger.info(f"[v5.8.8] {table}.{col} 컬럼 추가 완료")
                except (sqlite3.OperationalError, OSError) as e:
                    if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
                        logger.debug(f"[v5.8.8] {table}.{col} 이미 존재: {e}")
                    else:
                        raise
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v5.8.8] con_return 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v599_missing_columns(self) -> None:
        """
        v5.9.9: 누락된 컬럼 추가 (query_mixin, dashboard, inventory_tab 오류 방지)
        - inventory.customs: 통관 상태
        - inventory.location: 보관 위치
        - stock_movement.movement_date: 이동 시각 (created_at에서 백필)
        - stock_movement.customer: 고객
        """
        try:
            # inventory.customs
            try:
                self.execute("ALTER TABLE inventory ADD COLUMN customs TEXT")
                logger.info("[v5.9.9] inventory.customs 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.debug(f"[v5.9.9] inventory.customs 이미 존재: {e}")
                else:
                    raise
            # inventory.location
            try:
                self.execute("ALTER TABLE inventory ADD COLUMN location TEXT")
                logger.info("[v5.9.9] inventory.location 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.debug(f"[v5.9.9] inventory.location 이미 존재: {e}")
                else:
                    raise
            # stock_movement.movement_date
            try:
                self.execute("ALTER TABLE stock_movement ADD COLUMN movement_date TIMESTAMP")
                logger.info("[v5.9.9] stock_movement.movement_date 컬럼 추가 완료")
                try:
                    self.execute("UPDATE stock_movement SET movement_date = created_at WHERE movement_date IS NULL")
                    self.commit()
                except (sqlite3.OperationalError, OSError) as _e:
                    logger.debug(f"[v5.9.9] movement_date 백필 스킵: {_e}")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.debug(f"[v5.9.9] stock_movement.movement_date 이미 존재: {e}")
                else:
                    raise
            # stock_movement.customer
            try:
                self.execute("ALTER TABLE stock_movement ADD COLUMN customer TEXT")
                logger.info("[v5.9.9] stock_movement.customer 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.debug(f"[v5.9.9] stock_movement.customer 이미 존재: {e}")
                else:
                    raise
            self.commit()
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v5.9.9] missing columns 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v600_picking_sold_tables(self) -> None:
        """
        v6.0.0: SQM v6.0 4단계 상태 모델 — picking_table + sold_table 신규 생성
                allocation_plan 컬럼 확장 (picking_no, bl_no, outbound_id 추가)

        상태 모델:
            AVAILABLE → RESERVED(allocation_plan) → PICKED(picking_table) → SOLD(sold_table)

        Picking List PDF 파싱 결과 저장:
            picking_table: Batch number(lot_no) + Quantity(MT/KG) + customer_ref(Picking No)

        Sales Order Excel 처리 결과 저장:
            sold_table: LOT NO + Picking No 매칭 → SOLD 또는 PENDING
        """
        try:
            # STEP 1. allocation_plan 컬럼 확장
            extra_cols = [
                ("picking_no", "TEXT"),
                ("bl_no", "TEXT"),
                ("outbound_id", "TEXT"),
            ]
            for col_name, col_type in extra_cols:
                try:
                    self.execute(
                        f"ALTER TABLE allocation_plan ADD COLUMN {col_name} {col_type}"
                    )
                    logger.info(f"[v6.0.0] allocation_plan.{col_name} 컬럼 추가")
                except (sqlite3.OperationalError, OSError) as e:
                    if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                        logger.debug(f"[v6.0.0] allocation_plan.{col_name} 이미 존재")
                    else:
                        raise
            self.commit()

            # STEP 2. picking_table 신규 생성
            self.execute("""
                CREATE TABLE IF NOT EXISTS picking_table (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no           TEXT    NOT NULL,
                    tonbag_id        INTEGER,
                    sub_lt           INTEGER,
                    tonbag_uid       TEXT,
                    picking_no       TEXT,
                    sales_order_no   TEXT,
                    outbound_id      TEXT,
                    customer         TEXT,
                    plan_loading     TEXT,
                    creation_date    TEXT,
                    source_file      TEXT,
                    qty_mt           REAL,
                    qty_kg           REAL,
                    unit             TEXT,
                    is_sample        INTEGER DEFAULT 0,
                    storage_location TEXT,
                    status           TEXT DEFAULT 'ACTIVE',
                    picking_date     TEXT DEFAULT (datetime('now')),
                    sold_date        TEXT,
                    created_by       TEXT DEFAULT 'system',
                    remark           TEXT,
                    FOREIGN KEY (lot_no)    REFERENCES inventory(lot_no),
                    FOREIGN KEY (tonbag_id) REFERENCES inventory_tonbag(id)
                )
            """)
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_picking_lot       ON picking_table(lot_no)",
                "CREATE INDEX IF NOT EXISTS idx_picking_no        ON picking_table(picking_no)",
                "CREATE INDEX IF NOT EXISTS idx_picking_sales_ord ON picking_table(sales_order_no)",
                "CREATE INDEX IF NOT EXISTS idx_picking_uid       ON picking_table(tonbag_uid)",
                "CREATE INDEX IF NOT EXISTS idx_picking_status    ON picking_table(status)",
                "CREATE INDEX IF NOT EXISTS idx_picking_date      ON picking_table(picking_date)",
            ]:
                try:
                    self.execute(idx_sql)
                except (sqlite3.OperationalError, OSError) as _e:
                    logger.debug(f"[v6.0.0] picking_table 인덱스 스킵: {_e}")
            self.commit()
            logger.info("[v6.0.0] picking_table 생성 완료")

            # STEP 3. sold_table 신규 생성
            self.execute("""
                CREATE TABLE IF NOT EXISTS sold_table (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no           TEXT    NOT NULL,
                    tonbag_id        INTEGER,
                    sub_lt           INTEGER,
                    tonbag_uid       TEXT,
                    picking_id       INTEGER,
                    sales_order_no   TEXT,
                    sales_order_file TEXT,
                    picking_no       TEXT,
                    sap_no           TEXT,
                    bl_no            TEXT,
                    customer         TEXT,
                    sku              TEXT,
                    delivery_date    TEXT,
                    sold_qty_mt      REAL,
                    sold_qty_kg      REAL,
                    ct_plt           INTEGER,
                    status           TEXT DEFAULT 'PENDING',
                    sold_date        TEXT,
                    created_at       TEXT DEFAULT (datetime('now')),
                    confirmed_by     TEXT,
                    created_by       TEXT DEFAULT 'system',
                    remark           TEXT,
                    FOREIGN KEY (lot_no)     REFERENCES inventory(lot_no),
                    FOREIGN KEY (tonbag_id)  REFERENCES inventory_tonbag(id),
                    FOREIGN KEY (picking_id) REFERENCES picking_table(id)
                )
            """)
            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_sold_lot        ON sold_table(lot_no)",
                "CREATE INDEX IF NOT EXISTS idx_sold_uid        ON sold_table(tonbag_uid)",
                "CREATE INDEX IF NOT EXISTS idx_sold_order_no   ON sold_table(sales_order_no)",
                "CREATE INDEX IF NOT EXISTS idx_sold_picking_no ON sold_table(picking_no)",
                "CREATE INDEX IF NOT EXISTS idx_sold_status     ON sold_table(status)",
                "CREATE INDEX IF NOT EXISTS idx_sold_date       ON sold_table(sold_date)",
                "CREATE INDEX IF NOT EXISTS idx_sold_customer   ON sold_table(customer)",
            ]:
                try:
                    self.execute(idx_sql)
                except (sqlite3.OperationalError, OSError) as _e:
                    logger.debug(f"[v6.0.0] sold_table 인덱스 스킵: {_e}")
            self.commit()
            logger.info("[v6.0.0] sold_table 생성 완료")

            # STEP 4. inventory_tonbag 컬럼 추가
            tonbag_extra_cols = [
                ("picking_id", "INTEGER"),
                ("sold_id", "INTEGER"),
                ("picking_no", "TEXT"),
            ]
            for col_name, col_type in tonbag_extra_cols:
                try:
                    self.execute(
                        f"ALTER TABLE inventory_tonbag ADD COLUMN {col_name} {col_type}"
                    )
                    logger.info(f"[v6.0.0] inventory_tonbag.{col_name} 추가")
                except (sqlite3.OperationalError, OSError) as e:
                    if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                        logger.debug(f"[v6.0.0] inventory_tonbag.{col_name} 이미 존재")
                    else:
                        raise
            self.commit()
            logger.info("✅ [v6.0.0] picking_table + sold_table Migration 완료")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"❌ [v6.0.0] Migration 실패: {e}")
            self.rollback()
            raise

    def _migrate_v591_tonbag_fk_columns(self) -> None:
        """
        v5.9.1: inventory_tonbag에 FK·입고일·톤백번호·비고 컬럼 추가 (입고 업로드 시 INSERT 실패 방지)
        - inventory_id, sap_no, bl_no, inbound_date (필수)
        - tonbag_no, remarks (v5.2.0 미실행 등 방어용)
        """
        columns_to_add = [
            ("inventory_id", "INTEGER"),
            ("sap_no", "TEXT"),
            ("bl_no", "TEXT"),
            ("inbound_date", "TEXT"),
            ("tonbag_no", "TEXT"),
            ("remarks", "TEXT DEFAULT ''"),
        ]
        try:
            for col_name, col_type in columns_to_add:
                try:
                    self.execute(
                        f"ALTER TABLE inventory_tonbag ADD COLUMN {col_name} {col_type}"
                    )
                    logger.info(f"[v5.9.1] inventory_tonbag.{col_name} 컬럼 추가 완료")
                except (sqlite3.OperationalError, OSError) as e:
                    if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                        logger.debug(f"[v5.9.1] inventory_tonbag.{col_name} 이미 존재: {e}")
                    else:
                        raise
            self.commit()

            # 백필: inventory_id
            try:
                self.execute("""
                    UPDATE inventory_tonbag
                    SET inventory_id = (
                        SELECT i.id FROM inventory i WHERE i.lot_no = inventory_tonbag.lot_no
                    )
                    WHERE inventory_id IS NULL
                """)
                logger.info("[v5.9.1] inventory_id 백필 완료")
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v5.9.1] inventory_id 백필 스킵: {e}")

            # 백필: sap_no
            try:
                self.execute("""
                    UPDATE inventory_tonbag SET sap_no = (
                        SELECT COALESCE(i.sap_no,'') FROM inventory i
                        WHERE i.lot_no = inventory_tonbag.lot_no
                    ) WHERE sap_no IS NULL OR sap_no = ''
                """)
                logger.info("[v5.9.1] sap_no 백필 완료")
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v5.9.1] sap_no 백필 스킵: {e}")

            # 백필: bl_no
            try:
                self.execute("""
                    UPDATE inventory_tonbag SET bl_no = (
                        SELECT COALESCE(i.bl_no,'') FROM inventory i
                        WHERE i.lot_no = inventory_tonbag.lot_no
                    ) WHERE bl_no IS NULL OR bl_no = ''
                """)
                logger.info("[v5.9.1] bl_no 백필 완료")
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v5.9.1] bl_no 백필 스킵: {e}")

            # 백필: inbound_date (패치에 없던 부분 추가)
            try:
                self.execute("""
                    UPDATE inventory_tonbag SET inbound_date = (
                        SELECT COALESCE(i.stock_date, i.arrival_date, i.ship_date, date('now'))
                        FROM inventory i WHERE i.lot_no = inventory_tonbag.lot_no
                    ) WHERE inbound_date IS NULL OR inbound_date = ''
                """)
                logger.info("[v5.9.1] inbound_date 백필 완료")
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v5.9.1] inbound_date 백필 스킵: {e}")

            # 백필: tonbag_no (v5.2.0 미실행 시 — S00/001 형식)
            try:
                rows = self.fetchall(
                    "SELECT id, sub_lt, is_sample FROM inventory_tonbag WHERE tonbag_no IS NULL"
                )
                if rows:
                    for row in rows:
                        raw_sub_lt = row.get('sub_lt')
                        is_sample = int(row.get('is_sample') or 0)
                        if is_sample == 1 or str(raw_sub_lt or '0').strip() in ('0', ''):
                            tonbag_no = "S00"
                        else:
                            s = str(raw_sub_lt).strip()
                            tonbag_no = s.zfill(3) if re.fullmatch(r"\d+", s) else "001"
                        self.execute(
                            "UPDATE inventory_tonbag SET tonbag_no = ? WHERE id = ?",
                            (tonbag_no, row['id'])
                        )
                    logger.info(f"[v5.9.1] tonbag_no 백필 완료: {len(rows)}건")
            except (sqlite3.OperationalError, OSError, ValueError) as e:
                logger.debug(f"[v5.9.1] tonbag_no 백필 스킵: {e}")

            self.commit()
            logger.info("[v5.9.1] inventory_tonbag 백필 완료")

            # 인덱스
            try:
                self.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tonbag_inventory_id ON inventory_tonbag(inventory_id)"
                )
                self.commit()
            except (sqlite3.OperationalError, OSError) as _e:
                logger.debug(f"[v5.9.1] 인덱스 생성 스킵: {_e}")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"[v5.9.1] inventory_tonbag FK 컬럼 마이그레이션 실패: {e}")
            self.rollback()

    def _migrate_v420_tonbag_uid(self) -> None:
        """
        v4.2.0: inventory_tonbag.tonbag_uid 추가 + 백필 + 트리거
        
        규칙:
        - 일반 톤백: {lot_no}-{tonbag_no}  예) 1125072340-001
        - 샘플: {lot_no}-S00  예) 1125072340-S00
        """
        try:
            # ========================================
            # 1단계: 컬럼 추가
            # ========================================
            try:
                self.execute("ALTER TABLE inventory_tonbag ADD COLUMN tonbag_uid TEXT")
                logger.info("[v4.2.0] inventory_tonbag.tonbag_uid 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate column" in str(e).lower():
                    logger.debug(f"[v4.2.0] tonbag_uid 컬럼 이미 존재: {e}")
                else:
                    raise
            
            # ========================================
            # 2단계: 기존 데이터 백필
            # ========================================
            logger.info("[v4.2.0] 기존 데이터 tonbag_uid 백필 시작...")
            
            # 샘플 톤백 (is_sample=1 또는 sub_lt=0)
            self.execute("""
                UPDATE inventory_tonbag
                SET tonbag_uid = lot_no || '-S00'
                WHERE (COALESCE(is_sample, 0) = 1 OR sub_lt = 0)
                  AND (tonbag_uid IS NULL OR tonbag_uid = '')
            """)
            logger.info("[v4.2.0] 샘플 백필 완료")
            
            # 일반 톤백
            self.execute("""
                UPDATE inventory_tonbag
                SET tonbag_uid = lot_no || '-' || COALESCE(tonbag_no, printf('%03d', sub_lt))
                WHERE COALESCE(is_sample, 0) = 0
                  AND sub_lt > 0
                  AND (tonbag_uid IS NULL OR tonbag_uid = '')
            """)
            logger.info("[v4.2.0] 일반 톤백 백필 완료")
            
            # ========================================
            # 3단계: 유니크 인덱스 생성
            # ========================================
            logger.info("[v4.2.0] 인덱스 생성 시작...")
            
            # UID 전체 유니크
            self.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_tonbag_uid_unique
                ON inventory_tonbag(tonbag_uid)
            """)
            logger.info("[v4.2.0] idx_tonbag_uid_unique 생성 완료")
            
            # 샘플 LOT당 1개 보장
            self.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_tonbag_sample_per_lot
                ON inventory_tonbag(lot_no)
                WHERE COALESCE(is_sample, 0) = 1
            """)
            logger.info("[v4.2.0] idx_tonbag_sample_per_lot 생성 완료")
            
            # ========================================
            # 4단계: INSERT 트리거 (UID 자동 생성)
            # ========================================
            self.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_tonbag_uid_insert
                AFTER INSERT ON inventory_tonbag
                FOR EACH ROW
                WHEN NEW.tonbag_uid IS NULL OR NEW.tonbag_uid = ''
                BEGIN
                    UPDATE inventory_tonbag
                    SET tonbag_uid = CASE
                        WHEN COALESCE(NEW.is_sample, 0) = 1 OR NEW.sub_lt = 0 
                            THEN NEW.lot_no || '-S00'
                        ELSE NEW.lot_no || '-' || COALESCE(NEW.tonbag_no, printf('%03d', NEW.sub_lt))
                    END
                    WHERE id = NEW.id;
                END;
            """)
            logger.info("[v4.2.0] trg_tonbag_uid_insert 생성 완료")
            
            # ========================================
            # 5단계: UPDATE 트리거 (UID 자동 갱신)
            # ========================================
            self.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_tonbag_uid_update
                AFTER UPDATE OF lot_no, sub_lt, is_sample ON inventory_tonbag
                FOR EACH ROW
                BEGIN
                    UPDATE inventory_tonbag
                    SET tonbag_uid = CASE
                        WHEN COALESCE(NEW.is_sample, 0) = 1 OR NEW.sub_lt = 0 
                            THEN NEW.lot_no || '-S00'
                        ELSE NEW.lot_no || '-' || COALESCE(NEW.tonbag_no, printf('%03d', NEW.sub_lt))
                    END
                    WHERE id = NEW.id;
                END;
            """)
            logger.info("[v4.2.0] trg_tonbag_uid_update 생성 완료")
            
            # ========================================
            # 6단계: 커밋
            # ========================================
            self.commit()
            logger.info("[v4.2.0] ✅ tonbag_uid 마이그레이션 완료")
            
        except (sqlite3.OperationalError, OSError, sqlite3.IntegrityError) as e:
            logger.error(f"[v4.2.0] ❌ 마이그레이션 실패: {e}")
            self.rollback()
            raise

    def _migrate_v289_picking_list(self) -> None:
        """v2.9.89 마이그레이션: Picking List 테이블 추가
        ⚠️ v5.6.8: 데드 테이블 — 코드에서 사용하지 않음. 기존 DB 호환용 유지."""
        tables = [
            """CREATE TABLE IF NOT EXISTS picking_list_order (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                outbound_id INTEGER,
                sales_order TEXT DEFAULT '',
                customer_ref TEXT DEFAULT '',
                picking_date TEXT,
                status TEXT DEFAULT 'DRAFT',
                total_lots INTEGER DEFAULT 0,
                total_weight REAL DEFAULT 0,
                remarks TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (outbound_id) REFERENCES outbound(id)
            )""",
            """CREATE TABLE IF NOT EXISTS picking_list_detail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                picking_order_id INTEGER NOT NULL,
                lot_no TEXT NOT NULL,
                sub_lt TEXT,
                weight REAL DEFAULT 0,
                picked_status TEXT DEFAULT 'PENDING',
                picked_at TEXT,
                remarks TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (picking_order_id) REFERENCES picking_list_order(id),
                FOREIGN KEY (lot_no) REFERENCES inventory(lot_no)
            )""",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_picking_order_outbound ON picking_list_order(outbound_id)",
            "CREATE INDEX IF NOT EXISTS idx_picking_order_sales ON picking_list_order(sales_order)",
            "CREATE INDEX IF NOT EXISTS idx_picking_order_customer ON picking_list_order(customer_ref)",
            "CREATE INDEX IF NOT EXISTS idx_picking_detail_lot ON picking_list_detail(lot_no)",
            "CREATE INDEX IF NOT EXISTS idx_picking_detail_status ON picking_list_detail(picked_status)",
        ]
        try:
            for sql in tables:
                self.execute(sql)
            for sql in indexes:
                self.execute(sql)
            self.commit()
            logger.info("[v2.9.89] Picking List 테이블 마이그레이션 완료")
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v2.9.89] Picking List 마이그레이션 스킵: {e}")

    def _migrate_v388_column_unify(self) -> None:
        """v3.8.8: 컬럼명 통일 마이그레이션"""
        add_cols = [
            ("inventory", "salar_invoice_no", "TEXT DEFAULT ''"),
            ("inventory", "ship_date", "TEXT DEFAULT ''"),
            ("inventory", "vessel", "TEXT DEFAULT ''"),
            ("inventory", "arrival_date", "TEXT DEFAULT ''"),
            ("inventory", "inbound_date", "TEXT DEFAULT ''"),
            ("inventory", "initial_weight", "REAL DEFAULT 0"),
            ("inventory", "current_weight", "REAL DEFAULT 0"),
            ("inventory", "picked_weight", "REAL DEFAULT 0"),
            ("inventory", "mxbg_pallet", "INTEGER DEFAULT 0"),
            ("inventory_tonbag", "location", "TEXT DEFAULT ''"),
            ("inventory_tonbag", "picked_to", "TEXT DEFAULT ''"),
            ("inventory_tonbag", "pick_ref", "TEXT DEFAULT ''"),
            ("inventory_tonbag", "picked_date", "TEXT DEFAULT ''"),
            ("inventory_tonbag", "outbound_date", "TEXT DEFAULT ''"),
            ("inventory_tonbag", "remarks", "TEXT DEFAULT ''"),
        ]
        for table, col, col_type in add_cols:
            try:
                self.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            except (sqlite3.OperationalError, OSError) as _e:
                logger.debug(f'Suppressed: {_e}')
        try:
            self.commit()
            logger.info("[v3.8.8] 컬럼 통일 마이그레이션 완료")
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v3.8.8] 컬럼 통일 마이그레이션 스킵: {e}")

    def _migrate_v391_sample_tonbag(self) -> None:
        """v3.9.1: 샘플 톤백 is_sample 컬럼 추가"""
        try:
            try:
                self.execute("ALTER TABLE inventory_tonbag ADD COLUMN is_sample INTEGER DEFAULT 0")
                logger.info("[v3.9.1] inventory_tonbag.is_sample 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as _e:
                logger.debug(f'Suppressed: {_e}')
            self.execute("""
                UPDATE inventory_tonbag SET is_sample = 1
                WHERE sub_lt = 0 AND (is_sample IS NULL OR is_sample = 0)
            """)
            self.commit()
            logger.info("[v3.9.1] 샘플 톤백 마이그레이션 완료")
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v3.9.1] 샘플 톤백 마이그레이션 스킵: {e}")

    def _migrate_v396_search_indexes(self) -> None:
        """v3.9.6: 검색 성능 인덱스 추가"""
        idx_list = [
            "CREATE INDEX IF NOT EXISTS idx_inventory_bl_no ON inventory(bl_no)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_container ON inventory(container_no)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_arrival ON inventory(arrival_date)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_invoice ON inventory(salar_invoice_no)",
            "CREATE INDEX IF NOT EXISTS idx_tonbag_sample ON inventory_tonbag(is_sample)",
            "CREATE INDEX IF NOT EXISTS idx_tonbag_inv_id ON inventory_tonbag(inventory_id)",
        ]
        added = 0
        for sql in idx_list:
            try:
                self.execute(sql)
                added += 1
            except (sqlite3.OperationalError, OSError) as _e:
                logger.debug(f'Suppressed: {_e}')
        if added:
            self.commit()
            logger.info(f"[v3.9.6] 검색 인덱스 {added}개 추가")
    
    def _migrate_v423_tonbag_location(self) -> None:
        """
        v4.2.3: inventory_tonbag.location 추가 (톤백 위치 관리)
        
        컬럼:
        - location: VARCHAR(50) - 톤백 위치 (예: A-1-3, B-2-5)
        - location_updated_at: TEXT - 위치 업데이트 시간
        
        용도:
        - 바코드 스캔으로 톤백 위치 추적
        - Excel 업로드로 일괄 위치 업데이트
        """
        try:
            # ========================================
            # 1단계: location 컬럼 추가
            # ========================================
            try:
                self.execute("ALTER TABLE inventory_tonbag ADD COLUMN location TEXT")
                logger.info("[v4.2.3] inventory_tonbag.location 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate column" in str(e).lower():
                    logger.debug(f"[v4.2.3] location 컬럼 이미 존재: {e}")
                else:
                    raise
            
            # ========================================
            # 2단계: location_updated_at 컬럼 추가
            # ========================================
            try:
                self.execute("ALTER TABLE inventory_tonbag ADD COLUMN location_updated_at TEXT")
                logger.info("[v4.2.3] inventory_tonbag.location_updated_at 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate column" in str(e).lower():
                    logger.debug(f"[v4.2.3] location_updated_at 컬럼 이미 존재: {e}")
                else:
                    raise
            
            # ========================================
            # 3단계: 인덱스 생성
            # ========================================
            try:
                self.execute("CREATE INDEX IF NOT EXISTS idx_tonbag_location ON inventory_tonbag(location)")
                logger.info("[v4.2.3] location 인덱스 생성 완료")
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v4.2.3] 인덱스 생성 실패 (무시): {e}")
            
            self.commit()
            logger.info("✅ [v4.2.3] 톤백 위치 관리 마이그레이션 완료")
            
        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"❌ [v4.2.3] 톤백 위치 마이그레이션 실패: {e}")
            raise

    def _migrate_v520_tonbag_no_text(self) -> None:
        """
        v5.2.0: tonbag_no TEXT 컬럼 추가 + 기존 데이터 백필 + sale_ref 컬럼
        
        규칙:
        - 일반 톤백: sub_lt → "001", "002", ... (3자리 패딩)
        - 샘플: sub_lt=0 → "S00"
        """
        try:
            # 1단계: tonbag_no 컬럼 추가
            try:
                self.execute("ALTER TABLE inventory_tonbag ADD COLUMN tonbag_no TEXT")
                logger.info("[v5.2.0] inventory_tonbag.tonbag_no 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate column" in str(e).lower():
                    logger.debug("[v5.2.0] tonbag_no 컬럼 이미 존재")
                else:
                    raise

            # 2단계: sale_ref 컬럼 추가 (출고 참조번호)
            try:
                self.execute("ALTER TABLE inventory_tonbag ADD COLUMN sale_ref TEXT")
                logger.info("[v5.2.0] inventory_tonbag.sale_ref 컬럼 추가 완료")
            except (sqlite3.OperationalError, OSError) as e:
                if "duplicate column" in str(e).lower():
                    logger.debug("[v5.2.0] sale_ref 컬럼 이미 존재")
                else:
                    raise

            # 3단계: 기존 데이터 백필 (sub_lt → tonbag_no)
            rows = self.fetchall(
                "SELECT id, sub_lt, is_sample FROM inventory_tonbag WHERE tonbag_no IS NULL"
            )
            if rows:
                logger.info(f"[v5.2.0] tonbag_no 백필: {len(rows)}건")
                for row in rows:
                    raw_sub_lt = row.get('sub_lt')
                    is_sample = int(row.get('is_sample') or 0)
                    if is_sample == 1 or str(raw_sub_lt or '0').strip() in ('0', ''):
                        tonbag_no = "S00"
                    else:
                        s = str(raw_sub_lt).strip()
                        if re.fullmatch(r"\d+", s):
                            tonbag_no = s.zfill(3)
                        else:
                            raise ValueError(f"[v5.2.0] tonbag_no 백필 실패: 비정형 sub_lt={s} (id={row.get('id')})")
                    self.execute(
                        "UPDATE inventory_tonbag SET tonbag_no = ? WHERE id = ?",
                        (tonbag_no, row['id'])
                    )
                logger.info(f"[v5.2.0] tonbag_no 백필 완료: {len(rows)}건")

            # 4단계: 인덱스 생성
            try:
                self.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_tonbag_bl_lot_no "
                    "ON inventory_tonbag(bl_no, lot_no, tonbag_no)"
                )
                self.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tonbag_tonbag_no "
                    "ON inventory_tonbag(tonbag_no)"
                )
                logger.info("[v5.2.0] tonbag_no 인덱스 생성 완료")
            except (sqlite3.OperationalError, OSError) as e:
                logger.debug(f"[v5.2.0] 인덱스 생성 (무시): {e}")

            self.commit()
            logger.info("✅ [v5.2.0] tonbag_no TEXT 마이그레이션 완료")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, ValueError) as e:
            logger.error(f"❌ [v5.2.0] tonbag_no 마이그레이션 실패: {e}")
            raise


    # --------------------------
    # v5.3.0 Migration
    # --------------------------
    def _migrate_v593_allocation_plan(self) -> None:
        """
        v5.9.3: allocation_plan 테이블 — Allocation 엑셀에서 파싱된 출고 계획 저장.
        톤백을 RESERVED 상태로 예약하고, 출고일 도래 시 PICKED로 전환.
        """
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS allocation_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no TEXT NOT NULL,
                    tonbag_id INTEGER,
                    sub_lt INTEGER,
                    customer TEXT,
                    sale_ref TEXT,
                    qty_mt REAL,
                    outbound_date TEXT,
                    status TEXT DEFAULT 'RESERVED',
                    source_file TEXT,
                    source_fingerprint TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    executed_at TEXT,
                    cancelled_at TEXT,
                    FOREIGN KEY (tonbag_id) REFERENCES inventory_tonbag(id)
                )
            """)
            self.execute("""
                CREATE INDEX IF NOT EXISTS idx_alloc_plan_lot 
                ON allocation_plan(lot_no)
            """)
            self.execute("""
                CREATE INDEX IF NOT EXISTS idx_alloc_plan_status 
                ON allocation_plan(status)
            """)
            self.execute("""
                CREATE INDEX IF NOT EXISTS idx_alloc_plan_date 
                ON allocation_plan(outbound_date)
            """)
            self.execute("""
                CREATE INDEX IF NOT EXISTS idx_alloc_plan_source_fp
                ON allocation_plan(source_fingerprint)
            """)
            logger.info("[v5.9.3] allocation_plan 테이블 생성 완료")
        except (sqlite3.OperationalError, OSError) as e:
            if "already exists" not in str(e).lower():
                logger.warning(f"[v5.9.3] allocation_plan 생성 오류: {e}")
            else:
                logger.debug("[v5.9.3] allocation_plan 이미 존재")

    def _migrate_v710_return_history_to_log(self) -> None:
        """
        v7.1.0: return_history → return_log 완전 통합 마이그레이션.

        [배경]
          - v7.0.0 이전: 반품 데이터가 return_history 테이블에 저장됨
          - v7.0.0 이후: RETURN_AS_REINBOUND 정책으로 return_log에 저장
          - v7.1.0: return_history 기존 데이터를 return_log로 이관하여 단일 소스 완성

        [이관 규칙]
          return_history.id          → return_log.return_id (레거시 prefix 'RH-' 부여)
          return_history.lot_no      → return_log.lot_no
          return_history.original_customer → return_log.customer
          return_history.return_date → return_log.return_date
          return_history.reason      → return_log.reason
          return_history.weight_kg   → return_log.weight_kg
          processed_as               = 'LEGACY_HISTORY' (레거시 구분 표시)
          operator_id                = 'MIGRATION_v710'

        [멱등성]
          migration_flags 테이블의 v710_return_history_migrated 플래그로 중복 실행 방지.

        [주의]
          return_history 테이블은 삭제하지 않음 (레거시 참조 안전).
          UNION CTE 통계 쿼리는 return_history도 계속 읽으므로 중복 집계 방지를 위해
          이관된 row는 processed_as='LEGACY_HISTORY' 로 구분 가능.
        """
        FLAG_TABLE = "migration_flags"
        FLAG_KEY   = "v710_return_history_migrated"

        # ① migration_flags 테이블 생성 (최초 1회)
        try:
            self.execute(f"""
                CREATE TABLE IF NOT EXISTS {FLAG_TABLE} (
                    flag_key   TEXT PRIMARY KEY,
                    flag_value TEXT,
                    applied_at TEXT DEFAULT (datetime('now'))
                )
            """)
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v7.1.0] migration_flags 생성 스킵: {e}")

        # ② 이미 실행됐으면 건너뜀 (멱등성)
        try:
            row = self.fetchone(
                f"SELECT flag_value FROM {FLAG_TABLE} WHERE flag_key = ?",
                (FLAG_KEY,)
            )
            if row:
                logger.debug("[v7.1.0] return_history 마이그레이션 이미 완료 — 건너뜀")
                return
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v7.1.0] 플래그 조회 오류: {e}")

        # ③ return_history 테이블 존재 여부 확인
        try:
            count_row = self.fetchone(
                "SELECT COUNT(*) AS cnt FROM return_history"
            )
            total = count_row['cnt'] if isinstance(count_row, dict) else count_row[0]
        except (sqlite3.OperationalError, OSError):
            logger.info("[v7.1.0] return_history 테이블 없음 — 마이그레이션 불필요")
            self._set_migration_flag(FLAG_TABLE, FLAG_KEY, "SKIPPED_NO_TABLE")
            return

        if total == 0:
            logger.info("[v7.1.0] return_history 데이터 없음 — 마이그레이션 불필요")
            self._set_migration_flag(FLAG_TABLE, FLAG_KEY, "SKIPPED_EMPTY")
            return

        # ④ 이관 실행 (All-or-Nothing)
        try:
            self.execute("BEGIN")
            self.execute("""
                INSERT OR IGNORE INTO return_log (
                    return_id,
                    lot_no,
                    customer,
                    return_date,
                    reason,
                    weight_kg,
                    processed_as,
                    new_location,
                    operator_id
                )
                SELECT
                    'RH-' || CAST(id AS TEXT),
                    lot_no,
                    COALESCE(original_customer, '미기재'),
                    COALESCE(return_date, date('now')),
                    COALESCE(reason, '미기재'),
                    COALESCE(weight_kg, 0),
                    'LEGACY_HISTORY',
                    NULL,
                    'MIGRATION_v710'
                FROM return_history
            """)
            self.execute("COMMIT")

            migrated_row = self.fetchone(
                "SELECT COUNT(*) AS cnt FROM return_log WHERE operator_id = 'MIGRATION_v710'"
            )
            migrated = migrated_row['cnt'] if isinstance(migrated_row, dict) else migrated_row[0]
            logger.info(
                f"[v7.1.0] return_history → return_log 이관 완료: "
                f"{migrated}건 / 원본 {total}건"
            )
            self._set_migration_flag(FLAG_TABLE, FLAG_KEY, f"DONE:{migrated}")

        except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
            try:
                self.execute("ROLLBACK")
            except Exception:
                logger.debug("[SUPPRESSED] exception in db_migration_mixin.py")  # noqa
            logger.error(f"[v7.1.0] return_history 이관 오류 (롤백): {e}", exc_info=True)

    def _set_migration_flag(self, table: str, key: str, value: str) -> None:
        """마이그레이션 완료 플래그 저장."""
        try:
            self.execute(
                f"INSERT OR REPLACE INTO {table} (flag_key, flag_value) VALUES (?, ?)",
                (key, value)
            )
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[migration_flag] 저장 오류: {e}")


    def _migrate_v800_template_bl_format(self) -> None:
        """v8.0.0: inbound_template에 bl_format 컬럼 추가.
        형식 예: 숫자9  →  순수 숫자 9자리 (MAERSK)
                 MSCU7 →  MSCU + 숫자 7자리
                 COSU7 →  COSU + 숫자 7자리
        """
        try:
            self.execute(
                "ALTER TABLE inbound_template ADD COLUMN bl_format TEXT DEFAULT ''"
            )
            logger.info("[v8.0.0] inbound_template.bl_format 컬럼 추가 완료")
        except Exception as e:
            logger.debug(f"[v8.0.0] bl_format 이미 존재 또는 스킵: {e}")

        # 기존 선사별 기본값 설정
        presets = {
            'MSC':      'MSCU7',
            'MAERSK':   '숫자9',
            'COSCO':    'COSU7',
            'EVERGREEN':'EVER7',
            'CMA CGM':  'CMA7',
            'HMM':      'HMMU7',
            'ONE':      'ONEU7',
            'HAPAG':    'HLCU7',
        }
        try:
            for carrier, fmt in presets.items():
                self.execute(
                    "UPDATE inbound_template SET bl_format=? "
                    "WHERE carrier_id=? AND (bl_format IS NULL OR bl_format='')",
                    (fmt, carrier)
                )
            self.commit()
            logger.info("[v8.0.0] inbound_template bl_format 기본값 설정 완료")
        except Exception as e:
            logger.debug(f"[v8.0.0] bl_format 기본값 설정 스킵: {e}")

    def _migrate_v720_inbound_template(self) -> None:
        """
        v7.2.0: 입고 파싱 템플릿 관리 테이블 생성 + 기본 preset 삽입.

        [슬림 설계 원칙] 파싱 파이프라인에서 실제로 사용하는 컬럼만 유지.

        컬럼 11개:
          template_id        — PK (예: MSC_LC500)
          template_name      — 표시명
          carrier_id         — 선사 코드
          bag_weight_kg      — ★핵심: 톤백 단가 (500 or 1000), 파이프라인 주입
          product_hint       — Gemini 제품명 힌트
          weight_format      — EURO/US (중량 표기 방식, 확장 대비)
          gemini_hint_packing — PackingList 파싱 힌트 텍스트
          gemini_hint_invoice — Invoice 파싱 힌트 텍스트
          gemini_hint_bl      — B/L 파싱 힌트 텍스트
          note               — 담당자 메모
          is_active          — 1=사용중 / 0=비활성

        [기본 preset]
          UNKNOWN_500 / UNKNOWN_1000 — 선사 미확인 시 기본값
        """
        # ① 테이블 생성 (슬림 11컬럼)
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS inbound_template (
                    template_id          TEXT PRIMARY KEY,
                    template_name        TEXT NOT NULL,
                    carrier_id           TEXT NOT NULL DEFAULT 'UNKNOWN',
                    bag_weight_kg        INTEGER NOT NULL DEFAULT 500,
                    product_hint         TEXT DEFAULT '',
                    weight_format        TEXT DEFAULT 'EURO',
                    gemini_hint_packing  TEXT DEFAULT '',
                    gemini_hint_invoice  TEXT DEFAULT '',
                    gemini_hint_bl       TEXT DEFAULT '',
                    note                 TEXT DEFAULT '',
                    is_active            INTEGER DEFAULT 1
                )
            """)
            logger.info("[v7.2.0] inbound_template 테이블 생성 완료 (슬림 11컬럼)")
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v7.2.0] inbound_template 생성 스킵: {e}")

        # ② 기본 preset 삽입 (INSERT OR IGNORE — 멱등성)
        # ── Ruby 작성 MSC / MAERSK 힌트 텍스트 ───────────────────────────────
        _HINT_MSC_PL = (
            "MSC PackingList 특이사항:\n"
            "- LOT 번호는 표 왼쪽 열 'N° LOTES' 또는 'LOT NO' 헤더 아래에 10자리 숫자로 나옴.\n"
            "  형식 예시: 1125072729, 1125081215 (항상 11 또는 12로 시작)\n"
            "- mxbg(톤백 수)는 'MAXIBAGS', 'BAGS', 'MAXISACOS' 열에서 읽음. 보통 10개.\n"
            "- 중량은 유럽식 표기 (5.001,500 = 5001.5 kg). 쉼표가 소수점임.\n"
            "- 문서에 여러 페이지가 있으면 모든 페이지의 LOT를 빠짐없이 추출."
        )
        _HINT_MSC_INV = (
            "MSC Invoice(FA/FACTURA) 특이사항:\n"
            "- SAP NO는 'Ref.SQM/Our Order' 또는 'Our Order' 필드, 22로 시작하는 10자리.\n"
            "- LOT 목록은 'N° LOTES:' 뒤에 'LOT번호/중량T' 형식 (예: 1125072729/5,001T).\n"
            "  → LOT 번호(10자리)만 추출, '/5,001T' 부분 제외.\n"
            "- Invoice No는 문서 오른쪽 상단 'No.' 또는 'Invoice No.' 필드 옆 숫자.\n"
            "- B/L No는 'BL-AWB-CRT Number' 필드."
        )
        _HINT_MSC_BL = (
            "MSC B/L 특이사항:\n"
            "- B/L No 형식: MEDUFP000000 또는 숫자만 9자리 (예: 258468669).\n"
            "- 컨테이너 번호는 MSCU, TTNU, FSCU 등으로 시작하는 11자리.\n"
            "- Seal No는 'ML-CL' 뒤에 7자리 숫자 (예: ML-CL0501798).\n"
            "- 'SHIPPED ON BOARD' 날짜는 문서 하단 서명 옆에 있음."
        )
        _HINT_MAERSK_PL = (
            "MAERSK PackingList 특이사항:\n"
            "- LOT 번호는 'LOT NUMBER' 또는 'SQM LOT' 열에 10자리 숫자.\n"
            "- 중량은 유럽식 표기 사용. Net Weight 열에서 읽음.\n"
            "- 컨테이너 번호는 MSKU, MRKU, TRHU 등으로 시작.\n"
            "- mxbg는 'BAGS QTY' 또는 'QUANTITY' 열. 기본값 10개."
        )
        _HINT_MAERSK_INV = (
            "MAERSK Invoice 특이사항:\n"
            "- SAP NO는 'Customer Reference' 또는 'Our Ref' 필드, 22로 시작 10자리.\n"
            "- LOT 번호는 하단 표 또는 'N° LOTES' 섹션.\n"
            "- Vessel명은 'CHARLOTTE MAERSK', 'MAERSK EINDHOVEN' 등 MAERSK 포함."
        )
        _HINT_MAERSK_BL = (
            "MAERSK B/L(Sea Waybill) 특이사항:\n"
            "- B/L No 형식: 숫자 9자리 (예: 263764814) 또는 MAEU+숫자.\n"
            "- 'NON-NEGOTIABLE SEA WAYBILL' 또는 'BILL OF LADING' 문구 상단.\n"
            "- 컨테이너 번호는 MRKU, MSKU, TRHU, HMMU 등으로 시작 11자리.\n"
            "- Seal No는 숫자만으로 구성되는 경우도 있음."
        )

        presets = [
            {
                'template_id':         'UNKNOWN_500',
                'template_name':       '🚢 미확인 선사 — 500 kg',
                'carrier_id':          'UNKNOWN',
                'bag_weight_kg':       500,
                'product_hint':        'LITHIUM CARBONATE',
                'gemini_hint_packing': '',
                'gemini_hint_invoice': '',
                'gemini_hint_bl':      '',
                'note':                '선사 미확인 시 기본 템플릿 (500 kg 톤백)',
            },
            {
                'template_id':         'UNKNOWN_1000',
                'template_name':       '🚢 미확인 선사 — 1,000 kg',
                'carrier_id':          'UNKNOWN',
                'bag_weight_kg':       1000,
                'product_hint':        'LITHIUM CARBONATE',
                'gemini_hint_packing': '',
                'gemini_hint_invoice': '',
                'gemini_hint_bl':      '',
                'note':                '선사 미확인 시 기본 템플릿 (1000 kg 톤백)',
            },
            {
                'template_id':         'MSC_LC500',
                'template_name':       '🚢 MSC — 리튬카보네이트 500 kg',
                'carrier_id':          'MSC',
                'bag_weight_kg':       500,
                'product_hint':        'LITHIUM CARBONATE',
                'gemini_hint_packing': _HINT_MSC_PL,
                'gemini_hint_invoice': _HINT_MSC_INV,
                'gemini_hint_bl':      _HINT_MSC_BL,
                'note':                'MSC 선사 리튬카보네이트 500kg 톤백 표준 템플릿',
            },
            {
                'template_id':         'MSC_LC1000',
                'template_name':       '🚢 MSC — 리튬카보네이트 1,000 kg',
                'carrier_id':          'MSC',
                'bag_weight_kg':       1000,
                'product_hint':        'LITHIUM CARBONATE',
                'gemini_hint_packing': _HINT_MSC_PL,
                'gemini_hint_invoice': _HINT_MSC_INV,
                'gemini_hint_bl':      _HINT_MSC_BL,
                'note':                'MSC 선사 리튬카보네이트 1000kg 톤백 템플릿',
            },
            {
                'template_id':         'MAERSK_LC500',
                'template_name':       '🚢 MAERSK — 리튬카보네이트 500 kg',
                'carrier_id':          'MAERSK',
                'bag_weight_kg':       500,
                'product_hint':        'LITHIUM CARBONATE',
                'gemini_hint_packing': _HINT_MAERSK_PL,
                'gemini_hint_invoice': _HINT_MAERSK_INV,
                'gemini_hint_bl':      _HINT_MAERSK_BL,
                'note':                'MAERSK 선사 리튬카보네이트 500kg 톤백 표준 템플릿',
            },
        ]
        for p in presets:
            try:
                self.execute("""
                    INSERT OR IGNORE INTO inbound_template
                    (template_id, template_name, carrier_id, bag_weight_kg,
                     product_hint, gemini_hint_packing, gemini_hint_invoice,
                     gemini_hint_bl, note)
                    VALUES (
                        :template_id, :template_name, :carrier_id, :bag_weight_kg,
                        :product_hint, :gemini_hint_packing, :gemini_hint_invoice,
                        :gemini_hint_bl, :note
                    )
                """, p)
                logger.debug(f"[v7.2.0] preset 삽입: {p['template_id']}")
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                logger.debug(f"[v7.2.0] preset 스킵({p['template_id']}): {e}")

        logger.info("[v7.2.0] inbound_template 마이그레이션 완료 (5개 preset)")

    def _migrate_v740_picking_template(self) -> None:
        """
        v7.4.0: 출고 피킹 템플릿 (고객사 프로파일) 테이블 생성 + 기본 preset 삽입.

        [슬림 설계 원칙] picking_table INSERT + picking_engine에서 실제 사용하는 값만.

        컬럼 13개:
          template_id       — PK (예: CATL_CIF)
          template_name     — 표시명 (예: 🏭 CATL — CIF 광양)
          customer          — 거래처명 (picking_table.customer)
          customer_code     — sold_to 코드 (allocation_plan.sold_to)
          port_loading      — 선적항 (PickingListMeta.port_loading)
          port_discharge    — 양하항 (PickingListMeta.port_discharge)
          delivery_terms    — 인코텀즈 (PickingListMeta.delivery_terms)
          contact_person    — 담당자 (PickingListMeta.contact_person)
          contact_email     — 이메일 (PickingListMeta.contact_email)
          bag_weight_kg     — 톤백 단가 500/1000 (picking_engine build_pick_plan)
          storage_location  — 창고 위치 (picking_table.storage_location)
          note              — 담당자 메모
          is_active         — 1=사용중 / 0=비활성

        [기본 preset]
          UNKNOWN_CUSTOMER — 고객사 미확인 시 기본값
        """
        # ① 테이블 생성
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS picking_template (
                    template_id       TEXT PRIMARY KEY,
                    template_name     TEXT NOT NULL,
                    customer          TEXT NOT NULL DEFAULT '',
                    customer_code     TEXT DEFAULT '',
                    port_loading      TEXT DEFAULT 'GWANGYANG, SOUTH KOREA',
                    port_discharge    TEXT DEFAULT '',
                    delivery_terms    TEXT DEFAULT 'CIF',
                    contact_person    TEXT DEFAULT '',
                    contact_email     TEXT DEFAULT '',
                    bag_weight_kg     INTEGER NOT NULL DEFAULT 500,
                    storage_location  TEXT DEFAULT '1001 GY logistics',
                    note              TEXT DEFAULT '',
                    is_active         INTEGER DEFAULT 1
                )
            """)
            logger.info("[v7.4.0] picking_template 테이블 생성 완료 (슬림 13컬럼)")
        except (sqlite3.OperationalError, OSError) as e:
            logger.debug(f"[v7.4.0] picking_template 생성 스킵: {e}")

        # ② 기본 preset 삽입 (INSERT OR IGNORE — 멱등성)
        presets = [
            {
                'template_id':      'UNKNOWN_CUSTOMER',
                'template_name':    '🏭 미확인 고객사',
                'customer':         '',
                'customer_code':    '',
                'port_loading':     'GWANGYANG, SOUTH KOREA',
                'port_discharge':   '',
                'delivery_terms':   'CIF',
                'contact_person':   '',
                'contact_email':    '',
                'bag_weight_kg':    500,
                'storage_location': '1001 GY logistics',
                'note':             '고객사 미확인 시 기본 템플릿. 직접 수정하거나 신규 추가 후 사용.',
            },
        ]
        for p in presets:
            try:
                self.execute("""
                    INSERT OR IGNORE INTO picking_template (
                        template_id, template_name, customer, customer_code,
                        port_loading, port_discharge, delivery_terms,
                        contact_person, contact_email,
                        bag_weight_kg, storage_location, note
                    ) VALUES (
                        :template_id, :template_name, :customer, :customer_code,
                        :port_loading, :port_discharge, :delivery_terms,
                        :contact_person, :contact_email,
                        :bag_weight_kg, :storage_location, :note
                    )
                """, p)
                logger.debug(f"[v7.4.0] preset 삽입: {p['template_id']}")
            except (sqlite3.OperationalError, sqlite3.IntegrityError, OSError) as e:
                logger.debug(f"[v7.4.0] preset 스킵({p['template_id']}): {e}")

        logger.info("[v7.4.0] picking_template 마이그레이션 완료")

    def _migrate_v5992_allocation_source(self) -> None:
        """v5.9.92: allocation_plan.source — 출고 경로 구분 (AUTO/QUICK/EXCEL 등)."""
        try:
            self.execute("ALTER TABLE allocation_plan ADD COLUMN source TEXT DEFAULT 'AUTO'")
            logger.info("[v5.9.92] allocation_plan.source 컬럼 추가 완료")
        except (sqlite3.OperationalError, OSError) as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                logger.debug("[v5.9.92] allocation_plan.source 이미 존재")
            else:
                logger.warning(f"[v5.9.92] allocation_plan.source 추가 오류: {e}")

    def _migrate_v686_performance_indexes(self) -> None:
        """
        v6.8.6: 성능 인덱스 추가 (감사 보고서 권고사항 반영)

        추가 인덱스:
          - idx_tb_status          : WHERE status='AVAILABLE' 풀스캔 제거
          - idx_tb_lot_status      : WHERE lot_no=? AND status=? 복합 조회 최적화
          - idx_alloc_sale_ref_status : [G] LOT_MODE_DUP 차단 쿼리 최적화
        """
        indexes = [
            (
                "idx_tb_status",
                "CREATE INDEX IF NOT EXISTS idx_tb_status "
                "ON inventory_tonbag(status)"
            ),
            (
                "idx_tb_lot_status",
                "CREATE INDEX IF NOT EXISTS idx_tb_lot_status "
                "ON inventory_tonbag(lot_no, status)"
            ),
            (
                "idx_alloc_sale_ref_status",
                "CREATE INDEX IF NOT EXISTS idx_alloc_sale_ref_status "
                "ON allocation_plan(sale_ref, status)"
            ),
        ]
        for idx_name, sql in indexes:
            try:
                self.execute(sql)
                logger.info(f"[v6.8.6] 인덱스 생성 완료: {idx_name}")
            except Exception as e:
                logger.debug(f"[v6.8.6] 인덱스 스킵({idx_name}): {e}")


    def _migrate_v809_inline_edit(self) -> None:
        """
        v8.0.9 인라인 편집 지원 마이그레이션.
        - inventory_tonbag: picked_date, picked_to, outbound_date, sale_ref 컬럼 보장
        - allocation_plan: sale_ref 컬럼 보장
        기존 컬럼이 있으면 ADD COLUMN 무시 (OperationalError → debug 로그).
        """
        _cols = [
            ("inventory_tonbag", "picked_date",   "TEXT DEFAULT ''"),
            ("inventory_tonbag", "picked_to",     "TEXT DEFAULT ''"),
            ("inventory_tonbag", "outbound_date", "TEXT DEFAULT ''"),
            ("inventory_tonbag", "sale_ref",      "TEXT DEFAULT ''"),
            ("allocation_plan",  "sale_ref",      "TEXT DEFAULT ''"),
            ("allocation_plan",  "outbound_date", "TEXT DEFAULT ''"),
            ("picking_table",    "remark",        "TEXT DEFAULT ''"),
        ]
        import sqlite3
        for table, col, col_type in _cols:
            try:
                self.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                )
                logger.info("[v8.0.9] %s.%s 컬럼 추가", table, col)
            except (sqlite3.OperationalError, OSError) as _e:
                logger.debug("[v8.0.9] %s.%s 이미 존재(무시): %s", table, col, _e)
        try:
            self.commit()
        except Exception as _ce:
            logger.debug("[v8.0.9] commit 무시: %s", _ce)


    def _migrate_v691_picking_table_cols(self) -> None:
        """
        v6.9.1: picking_table 컬럼 2개 추가
          - picking_list_no : 피킹리스트 원본 번호 (추적용)
          - gate1_result    : Gate-1 검증 결과 ('PASS'/'FAIL'/'HARD_STOP')
        """
        cols_to_add = [
            ("picking_list_no", "TEXT DEFAULT ''"),
            ("gate1_result",    "TEXT DEFAULT ''"),
        ]
        for col_name, col_def in cols_to_add:
            try:
                existing = {str(r.get("name","")).lower()
                            for r in (self.fetchall("PRAGMA table_info(picking_table)") or [])}
                if col_name not in existing:
                    self.execute(
                        f"ALTER TABLE picking_table ADD COLUMN {col_name} {col_def}"
                    )
                    logger.info(f"[v6.9.1] picking_table.{col_name} 컬럼 추가")
            except Exception as e:
                logger.debug(f"[v6.9.1] picking_table.{col_name} 추가 스킵: {e}")


    def _migrate_v817_tonbag_move_log(self) -> None:
        """
        v8.1.8: tonbag_move_log 테이블 + 인덱스 생성 마이그레이션.
        + inventory_tonbag.location_updated_at 컬럼 안전 추가
          (v4.2.3에서 추가됐으나 구버전 DB에 없을 수 있음 — 이중 보장).

        기존 DB에 테이블이 없으면 생성, 이미 있으면 무시(IF NOT EXISTS).
        인덱스 3개: lot_no / status / move_date.
        """
        # ① inventory_tonbag.location_updated_at 컬럼 존재 보장
        try:
            existing_cols = {
                str(r.get('name', '')).lower()
                for r in (self.fetchall("PRAGMA table_info(inventory_tonbag)") or [])
            }
            if 'location_updated_at' not in existing_cols:
                self.execute(
                    "ALTER TABLE inventory_tonbag ADD COLUMN "
                    "location_updated_at TEXT"
                )
                logger.info("[v8.1.8] inventory_tonbag.location_updated_at 컬럼 추가")
            else:
                logger.debug("[v8.1.8] inventory_tonbag.location_updated_at 이미 존재")
        except Exception as _ce:
            logger.debug(f"[v8.1.8] location_updated_at 추가 스킵: {_ce}")

        # ② tonbag_move_log 테이블 생성
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS tonbag_move_log (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no        TEXT    NOT NULL,
                    sub_lt        INTEGER NOT NULL,
                    tonbag_no     TEXT,
                    from_location TEXT,
                    to_location   TEXT    NOT NULL,
                    move_date     DATE,
                    status        TEXT    DEFAULT 'COMPLETED',
                    approver      TEXT    DEFAULT '',
                    operator      TEXT    DEFAULT 'system',
                    remark        TEXT,
                    source_type   TEXT    DEFAULT 'MANUAL',
                    source_file   TEXT    DEFAULT '',
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lot_no) REFERENCES inventory(lot_no)
                )
            """)
            for idx_name, col in [
                ("idx_move_log_lot",    "lot_no"),
                ("idx_move_log_status", "status"),
                ("idx_move_log_date",   "move_date"),
            ]:
                try:
                    self.execute(
                        f"CREATE INDEX IF NOT EXISTS {idx_name} "
                        f"ON tonbag_move_log({col})"
                    )
                except Exception as _ie:
                    logger.debug(f"[v8.1.8] {idx_name} 인덱스 생성 스킵: {_ie}")
            logger.info("[v8.1.8] tonbag_move_log 마이그레이션 완료")
        except Exception as e:
            logger.warning(f"[v8.1.8] tonbag_move_log 마이그레이션 오류: {e}")

    def _migrate_v271_allocation_sc_rcvd(self) -> None:
        """v2.7.1: allocation_plan에 sc_rcvd 컬럼 추가 (Easpring 수령확인일).

        SC RCVD (Shipment Confirmation Received Date):
          Easpring 양식에서 수령확인일(입고 확인 날짜)을 별도로 관리.
          date_in_stock: 입고일 / sc_rcvd: 수령확인일 (통상 1~2일 차이)
        """
        import sqlite3 as _sq
        try:
            existing = {
                str(r.get("name","")).lower()
                for r in (self.fetchall("PRAGMA table_info(allocation_plan)") or [])
            }
            if "sc_rcvd" not in existing:
                self.execute(
                    "ALTER TABLE allocation_plan ADD COLUMN sc_rcvd TEXT DEFAULT NULL"
                )
                logger.info("[v2.7.1] allocation_plan.sc_rcvd 컬럼 추가 완료")
            else:
                logger.debug("[v2.7.1] allocation_plan.sc_rcvd 이미 존재 — 스킵")
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[v2.7.1] sc_rcvd 컬럼 추가 스킵: {e}")

    def _migrate_v870_inventory_bl_invoice_cols(self) -> None:
        """
        v8.7.0: inventory 테이블에 BL/Invoice/DO 파생 필드 6종 추가.

        목적:
          기존엔 bl_data / invoice_data 파라미터가 engine에서 미사용되어
          파싱된 voyage / do_no / invoice_date / total_amount / currency / unit_price
          전부 DB 유실. 이 마이그레이션이 컬럼을 보강하고 Phase 2 바인딩이 사용.

        컬럼:
          voyage        TEXT     — BL Voyage 번호(예: '535W')
          do_no         TEXT     — D/O 번호(Delivery Order ID)
          invoice_date  DATE     — Invoice 발행일
          total_amount  REAL     — Invoice 총금액
          currency      TEXT     — 통화 코드(USD/KRW 등)
          unit_price    REAL     — 단가

        안전:
          PRAGMA table_info로 기존 컬럼 확인 후 없을 때만 ALTER.
          duplicate 오류는 조용히 무시.
        """
        import sqlite3 as _sq
        cols_to_add = [
            ("voyage",       "TEXT DEFAULT ''"),
            ("do_no",        "TEXT DEFAULT ''"),
            ("invoice_date", "DATE"),
            ("total_amount", "REAL DEFAULT 0"),
            ("currency",     "TEXT DEFAULT ''"),
            ("unit_price",   "REAL DEFAULT 0"),
        ]
        try:
            existing = {
                str(r.get("name", "")).lower()
                for r in (self.fetchall("PRAGMA table_info(inventory)") or [])
            }
        except Exception as e:
            logger.debug(f"[v8.7.0] PRAGMA 조회 실패: {e}")
            existing = set()

        for col_name, col_def in cols_to_add:
            if col_name in existing:
                logger.debug(f"[v8.7.0] inventory.{col_name} 이미 존재 — 스킵")
                continue
            try:
                self.execute(f"ALTER TABLE inventory ADD COLUMN {col_name} {col_def}")
                logger.info(f"[v8.7.0] inventory.{col_name} 컬럼 추가")
            except (_sq.OperationalError, OSError) as e:
                if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                    logger.debug(f"[v8.7.0] inventory.{col_name} duplicate — 스킵")
                else:
                    logger.warning(f"[v8.7.0] inventory.{col_name} 추가 오류: {e}")

        # 조회용 인덱스 — 금액/통화/송장일 필터링 빈번
        idx_list = [
            "CREATE INDEX IF NOT EXISTS idx_inventory_invoice_date ON inventory(invoice_date)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_currency ON inventory(currency)",
        ]
        for sql in idx_list:
            try:
                self.execute(sql)
            except (_sq.OperationalError, OSError) as e:
                logger.debug(f"[v8.7.0] 인덱스 생성 스킵: {e}")

    def _migrate_v870_container_freetime_tables(self) -> None:
        """
        v8.7.0 Phase 3-A: 컨테이너(container_info) / Free Time(freetime_info) 1:N 테이블.

        목적:
          D/O 1건에 컨테이너가 복수(예: MAERSK BL은 4개 흔함)일 때, 기존 inventory
          단일 필드(container_no / con_return)에는 첫 건만 저장되어 나머지 유실.
          demurrage(체선료) 정산·반납 추적 리스크 해소용으로 별도 테이블 신설.

        스키마:
          container_info  — D/O의 containers[] (seal/size/weight/CBM/pkg 포함)
          freetime_info   — D/O의 free_time_info[] (반납지/반납일/free days)

        FK 미사용:
          기존 스타일(inventory_tonbag 등) 유지 — LOT 삭제 시 cascade는 수동 처리.

        안전:
          CREATE TABLE IF NOT EXISTS + sqlite3.OperationalError suppress.
          기존 con_return 단일 필드 로직은 그대로 유지(하위 호환).
        """
        import sqlite3 as _sq
        ddl_list = [
            ("container_info",
             """CREATE TABLE IF NOT EXISTS container_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no TEXT NOT NULL,
                    inventory_id INTEGER,
                    container_no TEXT NOT NULL,
                    seal_no TEXT DEFAULT '',
                    size_type TEXT DEFAULT '',
                    weight_kg REAL DEFAULT 0,
                    measurement_cbm REAL DEFAULT 0,
                    package_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""),
            ("freetime_info",
             """CREATE TABLE IF NOT EXISTS freetime_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no TEXT NOT NULL,
                    inventory_id INTEGER,
                    container_no TEXT DEFAULT '',
                    free_time_date DATE,
                    return_location TEXT DEFAULT '',
                    storage_free_days INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""),
        ]
        for tbl_name, sql in ddl_list:
            try:
                self.execute(sql)
                logger.info(f"[v8.7.0 Phase 3-A] {tbl_name} 테이블 확인/생성")
            except (_sq.OperationalError, OSError) as e:
                logger.debug(f"[v8.7.0 Phase 3-A] {tbl_name} 생성 스킵: {e}")

        idx_list = [
            "CREATE INDEX IF NOT EXISTS idx_container_info_lot "
            "ON container_info(lot_no)",
            "CREATE INDEX IF NOT EXISTS idx_container_info_container_no "
            "ON container_info(container_no)",
            "CREATE INDEX IF NOT EXISTS idx_freetime_info_lot "
            "ON freetime_info(lot_no)",
            "CREATE INDEX IF NOT EXISTS idx_freetime_info_date "
            "ON freetime_info(free_time_date)",
            "CREATE INDEX IF NOT EXISTS idx_freetime_info_container "
            "ON freetime_info(container_no)",
        ]
        for sql in idx_list:
            try:
                self.execute(sql)
            except (_sq.OperationalError, OSError) as e:
                logger.debug(f"[v8.7.0 Phase 3-A] 인덱스 생성 스킵: {e}")

    def _migrate_v870_document_invoice(self) -> None:
        """
        v8.7.0 Phase 3-B: Invoice 전필드 보존용 document_invoice 테이블 신설.

        목적:
          Phase 2에서 inventory 테이블에 invoice_date/total_amount/currency/unit_price 4
          필드만 추가됐지만, InvoiceData dataclass에는 customer_name/customer_code/
          customer_address/payment_term/incoterm/quantity_mt/product_code 등 비즈니스
          필드가 많아 DB에 저장되지 않고 유실. 이 테이블이 Invoice 원본 전필드를
          보존해 향후 정산/세관/대금 추적 리포트에서 활용.

        스키마:
          document_invoice — InvoiceData dataclass와 1:1 매칭(raw_*/success/error 제외)

        FK 미사용:
          기존 스타일(container_info 등) 유지 — inventory 삭제 시 수동 cascade.
          UNIQUE(lot_no, invoice_no) 제약 없음 — 재파싱/재입고 시 복수행 허용.

        안전:
          CREATE TABLE IF NOT EXISTS + sqlite3.OperationalError suppress.
          PRAGMA table_info로 기존 테이블 확인 후 idempotent 처리.
        """
        import sqlite3 as _sq
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS document_invoice (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no TEXT,
                    inventory_id INTEGER,
                    sap_no TEXT DEFAULT '',
                    invoice_no TEXT DEFAULT '',
                    salar_invoice_no TEXT DEFAULT '',
                    invoice_date DATE,
                    customer_ref TEXT DEFAULT '',
                    inv_acc_doc TEXT DEFAULT '',
                    delivery_transport TEXT DEFAULT '',
                    bl_no TEXT DEFAULT '',
                    customer_code TEXT DEFAULT '',
                    customer_name TEXT DEFAULT '',
                    customer_address TEXT DEFAULT '',
                    product_code TEXT DEFAULT '',
                    product_name TEXT DEFAULT '',
                    quantity_mt REAL DEFAULT 0,
                    unit_price REAL DEFAULT 0,
                    total_amount REAL DEFAULT 0,
                    currency TEXT DEFAULT '',
                    net_weight_kg REAL DEFAULT 0,
                    gross_weight_kg REAL DEFAULT 0,
                    package_count INTEGER DEFAULT 0,
                    package_type TEXT DEFAULT '',
                    jar_count INTEGER DEFAULT 0,
                    vessel TEXT DEFAULT '',
                    origin TEXT DEFAULT '',
                    destination TEXT DEFAULT '',
                    incoterm TEXT DEFAULT '',
                    payment_term TEXT DEFAULT '',
                    source_file TEXT DEFAULT '',
                    parsed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("[v8.7.0 Phase 3-B] document_invoice 테이블 확인/생성")
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[v8.7.0 Phase 3-B] document_invoice 생성 스킵: {e}")

        idx_list = [
            "CREATE INDEX IF NOT EXISTS idx_doc_invoice_lot "
            "ON document_invoice(lot_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_invoice_invoice_no "
            "ON document_invoice(invoice_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_invoice_sap "
            "ON document_invoice(sap_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_invoice_date "
            "ON document_invoice(invoice_date)",
        ]
        for sql in idx_list:
            try:
                self.execute(sql)
            except (_sq.OperationalError, OSError) as e:
                logger.debug(f"[v8.7.0 Phase 3-B] 인덱스 생성 스킵: {e}")

    def _migrate_v870_document_bl(self) -> None:
        """
        v8.7.0 Phase 3-B: BL 전필드 보존용 document_bl 테이블 신설.

        목적:
          BLData dataclass에 shipper/consignee/notify/port_of_*/place_of_*/
          total_containers/net_weight/gross_weight/total_cbm/freight_terms/
          booking_no/scac/carrier_id 등 비즈니스 필드가 많지만 inventory에는
          bl_no/ship_date/vessel/voyage 4~5필드만 저장되어 대부분 유실됨.
          이 테이블은 B/L 원본 전필드를 보존해 향후 선사별 리포트/물류비 분석/
          demurrage 추적에서 활용.

        스키마:
          document_bl — BLData 헤더/요약 필드 1:1 매칭
          (lots[]와 대칭되는 containers[]/freight_charges[]는 Phase 3-A의
           container_info / 별도 자식테이블이 담당 — 여기선 헤더만)

        FK 미사용, UNIQUE 제약 없음 (재파싱 중복 허용), 예외 suppress.
        """
        import sqlite3 as _sq
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS document_bl (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no TEXT,
                    inventory_id INTEGER,
                    bl_no TEXT DEFAULT '',
                    booking_no TEXT DEFAULT '',
                    carrier_id TEXT DEFAULT '',
                    carrier_name TEXT DEFAULT '',
                    scac TEXT DEFAULT '',
                    svc_contract TEXT DEFAULT '',
                    sap_no TEXT DEFAULT '',
                    vessel TEXT DEFAULT '',
                    voyage TEXT DEFAULT '',
                    shipper_name TEXT DEFAULT '',
                    shipper_address TEXT DEFAULT '',
                    consignee_name TEXT DEFAULT '',
                    consignee_address TEXT DEFAULT '',
                    notify_party TEXT DEFAULT '',
                    port_of_loading TEXT DEFAULT '',
                    port_of_discharge TEXT DEFAULT '',
                    place_of_receipt TEXT DEFAULT '',
                    place_of_delivery TEXT DEFAULT '',
                    place_of_issue TEXT DEFAULT '',
                    ship_date DATE,
                    issue_date DATE,
                    product_name TEXT DEFAULT '',
                    total_containers INTEGER DEFAULT 0,
                    total_packages INTEGER DEFAULT 0,
                    net_weight_kg REAL DEFAULT 0,
                    gross_weight_kg REAL DEFAULT 0,
                    total_cbm REAL DEFAULT 0,
                    freight_terms TEXT DEFAULT '',
                    total_freight_usd REAL DEFAULT 0,
                    total_freight_krw REAL DEFAULT 0,
                    source_file TEXT DEFAULT '',
                    parsed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("[v8.7.0 Phase 3-B] document_bl 테이블 확인/생성")
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[v8.7.0 Phase 3-B] document_bl 생성 스킵: {e}")

        idx_list = [
            "CREATE INDEX IF NOT EXISTS idx_doc_bl_lot "
            "ON document_bl(lot_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_bl_bl_no "
            "ON document_bl(bl_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_bl_carrier "
            "ON document_bl(carrier_id)",
            "CREATE INDEX IF NOT EXISTS idx_doc_bl_ship_date "
            "ON document_bl(ship_date)",
        ]
        for sql in idx_list:
            try:
                self.execute(sql)
            except (_sq.OperationalError, OSError) as e:
                logger.debug(f"[v8.7.0 Phase 3-B] document_bl 인덱스 스킵: {e}")

    def _migrate_v870_document_pl(self) -> None:
        """
        v8.7.0 Phase 3-B: PL 헤더/요약 보존용 document_pl 테이블 신설.

        목적:
          PackingListData 헤더(folio/product/packing/code/vessel/customer/
          destination/bl_no/sap_no/arrival_date) + 요약(total_lots/
          total_net_weight_kg/total_gross_weight_kg/total_maxibag/
          total_plastic_jars/footer_note)을 보존.

        스키마:
          document_pl — PackingListData 헤더/요약 1:1 매칭
          + v8.7.0 [U-1 b]: lots_json TEXT 컬럼 추가 — PL lots[] 원본을 JSON으로 통째 보존
            (감사·재파싱·역조회용; 개별 톤백 운영은 inventory_tonbag이 담당)

        arrival_date는 PackingListHeader.arrival_date에서 오며 Optional[date].
        FK 미사용, UNIQUE 제약 없음, 예외 suppress.
        """
        import sqlite3 as _sq
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS document_pl (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no TEXT,
                    inventory_id INTEGER,
                    folio TEXT DEFAULT '',
                    product TEXT DEFAULT '',
                    packing TEXT DEFAULT '',
                    code TEXT DEFAULT '',
                    vessel TEXT DEFAULT '',
                    customer TEXT DEFAULT '',
                    destination TEXT DEFAULT '',
                    bl_no TEXT DEFAULT '',
                    sap_no TEXT DEFAULT '',
                    arrival_date DATE,
                    total_lots INTEGER DEFAULT 0,
                    total_net_weight_kg REAL DEFAULT 0,
                    total_gross_weight_kg REAL DEFAULT 0,
                    total_maxibag INTEGER DEFAULT 0,
                    total_plastic_jars INTEGER DEFAULT 0,
                    footer_note TEXT DEFAULT '',
                    lots_json TEXT DEFAULT '',
                    source_file TEXT DEFAULT '',
                    parsed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("[v8.7.0 Phase 3-B] document_pl 테이블 확인/생성")
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[v8.7.0 Phase 3-B] document_pl 생성 스킵: {e}")

        # v8.7.0 [U-1 b]: 기존 DB에 lots_json 컬럼 없으면 ALTER TABLE ADD COLUMN
        try:
            existing = {
                str(r.get("name", "")).lower()
                for r in (self.fetchall("PRAGMA table_info(document_pl)") or [])
            }
            if "lots_json" not in existing:
                self.execute("ALTER TABLE document_pl ADD COLUMN lots_json TEXT DEFAULT ''")
                logger.info("[v8.7.0 U-1b] document_pl.lots_json 컬럼 추가")
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[v8.7.0 U-1b] lots_json ALTER 스킵: {e}")

        idx_list = [
            "CREATE INDEX IF NOT EXISTS idx_doc_pl_lot "
            "ON document_pl(lot_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_pl_bl_no "
            "ON document_pl(bl_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_pl_sap "
            "ON document_pl(sap_no)",
        ]
        for sql in idx_list:
            try:
                self.execute(sql)
            except (_sq.OperationalError, OSError) as e:
                logger.debug(f"[v8.7.0 Phase 3-B] document_pl 인덱스 스킵: {e}")

    def _migrate_v870_document_do(self) -> None:
        """
        v8.7.0 Phase 3-B: DO 전필드 보존용 document_do 테이블 신설.

        목적:
          DOData dataclass의 do_no/bl_no/sap_no/vessel/voyage/port_of_*/
          arrival_date/stock_date/issue_date/warehouse_code/warehouse_name/
          mrn/msn/total_packages 등 D/O 원본 필드를 보존.

        스키마:
          document_do — DOData 헤더/요약 1:1 매칭
          (containers[]/free_time_info[]는 Phase 3-A container_info/freetime_info
           테이블이 1:N 저장 중 — 여기선 요약 total_containers만)

        free_time은 DOData에 없지만 GUI가 arrival_date ~ free_time_date 차이로
        계산한 INTEGER 값을 넘겨줄 수 있어 컬럼 보존. con_return은 free_time_info
        첫 번째의 free_time_date를 GUI가 넘김.

        FK 미사용, UNIQUE 제약 없음, 예외 suppress.
        """
        import sqlite3 as _sq
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS document_do (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_no TEXT,
                    inventory_id INTEGER,
                    do_no TEXT DEFAULT '',
                    bl_no TEXT DEFAULT '',
                    sap_no TEXT DEFAULT '',
                    carrier_id TEXT DEFAULT '',
                    vessel TEXT DEFAULT '',
                    voyage TEXT DEFAULT '',
                    flag TEXT DEFAULT '',
                    port_of_loading TEXT DEFAULT '',
                    port_of_discharge TEXT DEFAULT '',
                    final_destination TEXT DEFAULT '',
                    place_of_delivery TEXT DEFAULT '',
                    arrival_date DATE,
                    stock_date DATE,
                    issue_date DATE,
                    warehouse_code TEXT DEFAULT '',
                    warehouse_name TEXT DEFAULT '',
                    free_time INTEGER DEFAULT 0,
                    con_return TEXT DEFAULT '',
                    total_containers INTEGER DEFAULT 0,
                    total_packages INTEGER DEFAULT 0,
                    gross_weight_kg REAL DEFAULT 0,
                    measurement_cbm REAL DEFAULT 0,
                    mrn TEXT DEFAULT '',
                    msn TEXT DEFAULT '',
                    source_file TEXT DEFAULT '',
                    parsed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("[v8.7.0 Phase 3-B] document_do 테이블 확인/생성")
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[v8.7.0 Phase 3-B] document_do 생성 스킵: {e}")

        idx_list = [
            "CREATE INDEX IF NOT EXISTS idx_doc_do_lot "
            "ON document_do(lot_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_do_do_no "
            "ON document_do(do_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_do_bl_no "
            "ON document_do(bl_no)",
            "CREATE INDEX IF NOT EXISTS idx_doc_do_arrival "
            "ON document_do(arrival_date)",
        ]
        for sql in idx_list:
            try:
                self.execute(sql)
            except (_sq.OperationalError, OSError) as e:
                logger.debug(f"[v8.7.0 Phase 3-B] document_do 인덱스 스킵: {e}")

    def _migrate_v271_add_missing_indexes(self) -> None:
        """v2.7.1: 성능 최적화 — 누락 인덱스 3개 추가.

        감사 결과 누락 확인:
          inventory_tonbag(status, is_sample) — 샘플 필터 쿼리 최적화
          sold_table(delivery_date)            — Outbound Report 날짜별 시트 쿼리
          stock_movement(lot_no, movement_type) — 중복 감지 쿼리
        """
        import sqlite3 as _sq
        idx_list = [
            ("idx_tb_status_is_sample",
             "CREATE INDEX IF NOT EXISTS idx_tb_status_is_sample "
             "ON inventory_tonbag(status, is_sample)"),
            ("idx_sold_delivery_date",
             "CREATE INDEX IF NOT EXISTS idx_sold_delivery_date "
             "ON sold_table(delivery_date)"),
            ("idx_mv_lot_type",
             "CREATE INDEX IF NOT EXISTS idx_mv_lot_type "
             "ON stock_movement(lot_no, movement_type)"),
        ]
        for idx_name, sql in idx_list:
            try:
                self.execute(sql)
                logger.debug(f"[v2.7.1] 인덱스 확인/생성: {idx_name}")
            except (_sq.OperationalError, OSError) as e:
                logger.debug(f"[v2.7.1] 인덱스 스킵({idx_name}): {e}")

    # =========================================================================
    # v8.7.1 P0 보안/데이터무결성 패치 마이그레이션
    # =========================================================================

    def _migrate_v871_allocation_no_dup_index(self) -> None:
        """
        v8.7.1 P0-4: allocation_plan 중복 예약 방지 Partial UNIQUE 인덱스.

        감사 발견 (BUG-C4):
          has_workflow_status_col 미존재 시 충돌 체크 스킵 → 동일
          (lot_no, customer, sale_ref, tonbag_id)가 2번 삽입 가능.

        수정: SQLite 3.9+ Partial Unique Index 사용.
          status IN ('RESERVED','STAGED') 인 행에 한해 중복 방지.
          EXECUTED/CANCELLED 는 히스토리 보존을 위해 제외.

        멱등성: CREATE INDEX IF NOT EXISTS → 재실행 안전.
        """
        import sqlite3 as _sq
        try:
            self.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_alloc_no_dup
                ON allocation_plan(lot_no, customer, sale_ref, tonbag_id)
                WHERE status IN ('RESERVED', 'STAGED')
            """)
            logger.info("[v8.7.1] allocation_plan 중복 예약 방지 UNIQUE 인덱스 추가")
        except _sq.OperationalError as e:
            err = str(e).lower()
            if "already exists" in err or "unique" in err:
                logger.debug("[v8.7.1] allocation_plan UNIQUE 인덱스 이미 존재")
            else:
                logger.warning(f"[v8.7.1] allocation_plan UNIQUE 인덱스 추가 실패: {e}")

    def _migrate_v871_inventory_weight_floor(self) -> None:
        """
        v8.7.1 P0-5: inventory.current_weight 음수 방지 BEFORE UPDATE TRIGGER.

        감사 발견 (BUG-C3):
          동시 출고+재계산 시 current_weight < 0 가능.
          SQLite는 ALTER TABLE로 CHECK 제약 추가 불가 → 트리거로 대체.

        동작:
          1) 기존 DB의 음수 중량을 0으로 보정 (일회성 cleansing)
          2) BEFORE UPDATE OF current_weight 트리거 등록 →
             NEW.current_weight < 0 이면 RAISE(FAIL) → UPDATE 중단

        멱등성: CREATE TRIGGER IF NOT EXISTS → 재실행 안전.
        """
        import sqlite3 as _sq
        # ① 기존 음수 중량 클리닝
        try:
            cleansed = self.execute(
                "UPDATE inventory SET current_weight = 0.0 "
                "WHERE current_weight < 0"
            )
            if cleansed and getattr(cleansed, 'rowcount', 0):
                logger.warning(
                    f"[v8.7.1] inventory 음수 중량 {cleansed.rowcount}건 → 0으로 보정"
                )
        except (_sq.OperationalError, OSError) as e:
            logger.debug(f"[v8.7.1] 음수 중량 클리닝 스킵: {e}")

        # ② 트리거 등록
        try:
            self.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_inventory_weight_floor
                BEFORE UPDATE OF current_weight ON inventory
                FOR EACH ROW
                WHEN NEW.current_weight < 0
                BEGIN
                    SELECT RAISE(FAIL, 'current_weight cannot be negative');
                END
            """)
            logger.info("[v8.7.1] inventory current_weight 음수 방지 TRIGGER 추가")
        except _sq.OperationalError as e:
            if "already exists" in str(e).lower():
                logger.debug("[v8.7.1] inventory weight_floor trigger 이미 존재")
            else:
                logger.warning(f"[v8.7.1] inventory weight trigger 추가 실패: {e}")

    def _migrate_v871_allocation_tonbag_id_index(self) -> None:
        """
        v8.7.1 P1-8: allocation_plan.tonbag_id 성능 인덱스 추가.

        감사 발견:
          allocation_plan.tonbag_id 는 FK + WHERE/JOIN 에서 빈번하게 조회되지만
          SQLite가 FK 자동 인덱스를 생성하지 않아 100K 행 Full Scan 발생.

        멱등성: CREATE INDEX IF NOT EXISTS → 재실행 안전.
        """
        import sqlite3 as _sq
        try:
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_allocation_plan_tonbag_id "
                "ON allocation_plan(tonbag_id)"
            )
            logger.info("[v8.7.1] allocation_plan.tonbag_id 인덱스 추가")
        except _sq.OperationalError as e:
            if "already exists" in str(e).lower():
                logger.debug("[v8.7.1] allocation_plan.tonbag_id 인덱스 이미 존재")
            else:
                logger.warning(f"[v8.7.1] allocation_plan.tonbag_id 인덱스 추가 실패: {e}")

    # =========================================================================
    # v8.5.7 마이그레이션
    # =========================================================================

    def _migrate_v857_sold_table_outbound_report(self) -> None:
        """
        v8.5.7: 출고 보고서용 sold_table 컬럼 추가 + 과거 출고 건 역보정.

        1) gross_weight_kg, sold_qty_mt, is_sample 컬럼 안전 추가
        2) 과거 OUTBOUND 톤백 → sold_table에 누락된 행 자동 INSERT
        3) 기존 행의 빈 필드(sap_no, bl_no 등) inventory JOIN으로 보정
        """
        # ── ① 컬럼 추가 (IF NOT EXISTS 스타일) ──
        cols_to_add = [
            ("gross_weight_kg", "REAL DEFAULT 0"),
            ("sold_qty_mt",     "REAL DEFAULT 0"),
            ("is_sample",       "INTEGER DEFAULT 0"),
        ]
        for col_name, col_def in cols_to_add:
            try:
                existing = {
                    str(r.get("name", "")).lower()
                    for r in (self.fetchall("PRAGMA table_info(sold_table)") or [])
                }
                if col_name not in existing:
                    self.execute(
                        f"ALTER TABLE sold_table ADD COLUMN {col_name} {col_def}"
                    )
                    logger.info(f"[v8.5.7] sold_table.{col_name} 컬럼 추가")
            except Exception as e:
                logger.debug(f"[v8.5.7] sold_table.{col_name} 추가 스킵: {e}")

        # ── ② 과거 OUTBOUND 톤백 → sold_table 누락 행 INSERT ──
        try:
            orphans = self.fetchall("""
                SELECT t.id AS tonbag_id, t.lot_no, t.sub_lt, t.tonbag_uid,
                       t.weight, t.outbound_date, t.is_sample,
                       i.sap_no, i.bl_no, i.product_code, i.product,
                       i.gross_weight, i.mxbg_pallet, i.sold_to, i.sale_ref
                FROM inventory_tonbag t
                JOIN inventory i ON t.lot_no = i.lot_no
                WHERE t.status IN ('OUTBOUND', 'SOLD')
                  AND t.id NOT IN (SELECT COALESCE(tonbag_id, 0) FROM sold_table)
            """)
            if orphans:
                for row in orphans:
                    r = dict(row) if not isinstance(row, dict) else row
                    _wt = float(r.get('weight') or 0)
                    _mt = round(_wt / 1000.0, 6)
                    _is_sample = int(r.get('is_sample') or 0)
                    _gw = 0.0
                    if _is_sample:
                        _gw = _wt * 1.025
                    elif r.get('mxbg_pallet') and r.get('gross_weight'):
                        _gw = float(r['gross_weight']) / int(r['mxbg_pallet'])
                    _sku = r.get('product_code') or ''
                    if _is_sample and _sku and 'Sample' not in _sku:
                        _sku = f"{_sku} Sample"
                    try:
                        self.execute(
                            """INSERT INTO sold_table
                            (lot_no, tonbag_id, sub_lt, tonbag_uid, sold_qty_kg, sold_qty_mt,
                             gross_weight_kg, sold_date, status, created_by,
                             sap_no, bl_no, customer, sku, delivery_date, ct_plt, is_sample)
                            VALUES (?, ?, ?, ?, ?, ?,
                                    ?, ?, 'OUTBOUND', 'migration_v857',
                                    ?, ?, ?, ?, ?, 1, ?)""",
                            (r['lot_no'], r['tonbag_id'], r.get('sub_lt', 0),
                             r.get('tonbag_uid', ''),
                             _wt, _mt, _gw,
                             r.get('outbound_date') or '',
                             r.get('sap_no', ''), r.get('bl_no', ''),
                             r.get('sold_to') or r.get('sale_ref') or '',
                             _sku,
                             str(r.get('outbound_date') or '')[:10],
                             _is_sample)
                        )
                    except Exception as _ie:
                        logger.debug(f"[v8.5.7] 과거 sold INSERT 스킵: {_ie}")
                logger.info(f"[v8.5.7] 과거 출고 {len(orphans)}건 → sold_table 역보정 완료")

        except Exception as e:
            logger.debug(f"[v8.5.7] 과거 출고 역보정 스킵: {e}")

        # ── ③ 기존 sold_table 행의 빈 필드 보정 ──
        try:
            empties = self.fetchall("""
                SELECT s.id, s.lot_no, s.tonbag_id, s.sub_lt, s.sold_qty_kg
                FROM sold_table s
                WHERE COALESCE(s.sap_no, '') = ''
                   OR COALESCE(s.bl_no, '') = ''
            """)
            if empties:
                for row in empties:
                    r = dict(row) if not isinstance(row, dict) else row
                    inv = self.fetchone(
                        "SELECT sap_no, bl_no, product_code, gross_weight, mxbg_pallet, sold_to "
                        "FROM inventory WHERE lot_no = ?",
                        (r['lot_no'],)
                    )
                    if inv:
                        iv = dict(inv) if not isinstance(inv, dict) else inv
                        _wt = float(r.get('sold_qty_kg') or 0)
                        _mt = round(_wt / 1000.0, 6)
                        _gw = 0.0
                        if iv.get('mxbg_pallet') and iv.get('gross_weight'):
                            _gw = float(iv['gross_weight']) / int(iv['mxbg_pallet'])
                        self.execute(
                            """UPDATE sold_table SET
                               sap_no = COALESCE(NULLIF(sap_no,''), ?),
                               bl_no = COALESCE(NULLIF(bl_no,''), ?),
                               sku = COALESCE(NULLIF(sku,''), ?),
                               customer = COALESCE(NULLIF(customer,''), ?),
                               sold_qty_mt = CASE WHEN COALESCE(sold_qty_mt,0) = 0 THEN ? ELSE sold_qty_mt END,
                               gross_weight_kg = CASE WHEN COALESCE(gross_weight_kg,0) = 0 THEN ? ELSE gross_weight_kg END
                            WHERE id = ?""",
                            (iv.get('sap_no', ''), iv.get('bl_no', ''),
                             iv.get('product_code', ''), iv.get('sold_to', ''),
                             _mt, _gw, r['id'])
                        )
                logger.info(f"[v8.5.7] sold_table 빈 필드 {len(empties)}건 보정 완료")
        except Exception as e:
            logger.debug(f"[v8.5.7] sold_table 보정 스킵: {e}")

    # =========================================================================
    # v8.7.2 Phase 4-A 회귀 강화 패치
    # =========================================================================

    def _migrate_v872_inventory_weight_floor_insert(self) -> None:
        """
        v8.7.2 P1: inventory.current_weight INSERT 경로 음수 방지 트리거.

        Phase 4 진단 발견 (E4-A / D-002):
          v8.7.1 트리거(trg_inventory_weight_floor)는 BEFORE UPDATE 전용.
          직접 INSERT로 음수 current_weight 행 삽입 시 트리거가 차단하지 않음.
          앱 레벨 validator가 부팅 시 감지하나 auto-fix는 DEPLETED 조건 한정.

        수정: BEFORE INSERT 트리거를 추가해 INSERT 경로도 차단.
        멱등성: CREATE TRIGGER IF NOT EXISTS → 재실행 안전.
        """
        import sqlite3 as _sq
        try:
            self.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_inventory_weight_floor_insert
                BEFORE INSERT ON inventory
                FOR EACH ROW
                WHEN NEW.current_weight < 0
                BEGIN
                    SELECT RAISE(FAIL, 'current_weight cannot be negative (insert)');
                END
            """)
            logger.info("[v8.7.2] inventory current_weight 음수 방지 INSERT TRIGGER 추가")
        except _sq.OperationalError as e:
            if "already exists" in str(e).lower():
                logger.debug("[v8.7.2] inventory weight_floor_insert trigger 이미 존재")
            else:
                logger.warning(f"[v8.7.2] inventory weight_floor_insert trigger 추가 실패: {e}")

    def _migrate_v872_sold_table_dedup_index(self) -> None:
        """
        v8.7.2 P4: sold_table 중복 방지 UNIQUE 인덱스.

        Phase 4 진단 발견 (D-001 / E3-A):
          sold_table에 (sales_order_no, lot_no, sub_lt) UNIQUE 제약 없음.
          SO 파일 재업로드 시 동일 톤백 SOLD 행이 중복 삽입될 위험.
          sales_order_engine의 import_log 체크가 1차 방어이나 DB 레벨 보강 필요.

        멱등성: CREATE UNIQUE INDEX IF NOT EXISTS → 재실행 안전.
        기존 중복 행 존재 시 인덱스 생성 실패 → warning 로그 후 계속.
        """
        import sqlite3 as _sq
        try:
            self.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_sold_dedup "
                "ON sold_table(sales_order_no, lot_no, COALESCE(sub_lt, ''))"
            )
            logger.info("[v8.7.2] sold_table 중복 방지 UNIQUE 인덱스 추가")
        except _sq.OperationalError as e:
            if "already exists" in str(e).lower():
                logger.debug("[v8.7.2] sold_table 중복 인덱스 이미 존재")
            elif "unique" in str(e).lower():
                logger.warning(f"[v8.7.2] sold_table 중복 행 존재로 인덱스 생성 불가 (기존 데이터 정리 필요): {e}")
            else:
                logger.warning(f"[v8.7.2] sold_table dedup 인덱스 추가 실패: {e}")
