"""
SQM v5.9.4 — DB 스키마 초기화 Mixin
====================================

database.py에서 분리 (1242줄 → ~660 + ~580).
테이블 생성(_init_*), 마이그레이션(_migrate_v243),
스키마 검증(_verify_schema), 인덱스 생성(_create_indexes)을 담당.
"""
import logging
import sqlite3
from typing import Any, Dict

logger = logging.getLogger(__name__)


class DatabaseSchemaMixin:
    """DB 스키마 초기화/검증/인덱스 — SQMDatabase에 MRO 합성"""

    def _init_database(self) -> None:
        """데이터베이스 테이블 초기화 (v4.0.3: 섹션별 분리)"""
        self._init_shipment_table()
        self._init_inventory_table()
        self._init_tonbag_table()
        self._init_outbound_tables()
        self._init_movement_tables()
        self._init_audit_log_table()   # v7.9.9 [C-1]: audit_log 중앙화
        self._init_lot_summary_view()  # v7.9.9 [H-2]: inventory_lot_summary VIEW
        self._init_snapshot_tables()
        self._init_parsing_log_table() # v8.2.4: 파싱 통계
        self._migrate_v243()
        self._migrate_v660_move()
        # v8.6.4: _run_all_migrations()이 v593+v600 포함하므로 별도 ensure 호출 제거
        # 최신 마이그레이션 체인 실행 (idempotent). 신규 컬럼/인덱스 보강 반영.
        try:
            self._run_all_migrations()
        except Exception as e:
            logger.warning(f"[스키마] 전체 마이그레이션 체인 실행 스킵/실패: {e}")

        # v8.3.0 [Phase 10]: MigrationManager — schema_version 동기화
        try:
            from engine_modules.migration_manager import MigrationManager
            mgr = MigrationManager(self)
            # 기존 DB 최초 실행 시 현재 버전 등록
            if mgr.current_version() == 0:
                mgr.sync_existing()
            # v8.3.0 버전 등록
            mgr._mark_applied(830, 'v8.3.0',
                               'audit_log + daily_report + schema_version')
            logger.debug(f"[스키마] schema_version 현재: {mgr.current_version_str()}")
        except Exception as _me:
            logger.debug(f"[스키마] MigrationManager 스킵: {_me}")

    def _ensure_allocation_and_picking_sold_tables(self) -> None:
        """allocation_plan, picking_table, sold_table 존재 보장 (예약·출고 이력용)."""
        try:
            self._migrate_v593_allocation_plan()
        except Exception as e:
            logger.warning(f"[스키마] allocation_plan 생성 스킵/실패: {e}")
        try:
            self._migrate_v600_picking_sold_tables()
        except Exception as e:
            logger.warning(f"[스키마] picking_table/sold_table 생성 스킵/실패: {e}")

    def _init_shipment_table(self) -> None:
        """선적(Shipment) 테이블"""
        self.execute("""
            CREATE TABLE IF NOT EXISTS shipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sap_no TEXT UNIQUE,
                folio TEXT,
                bl_no TEXT,
                container_no TEXT,
                product TEXT,
                product_code TEXT,
                origin TEXT DEFAULT 'Chile',
                destination TEXT DEFAULT '광양',
                ship_date DATE,
                arrival_date DATE,
                total_net_weight REAL,
                total_gross_weight REAL,
                port_of_loading TEXT,
                port_of_discharge TEXT,
                vessel TEXT,
                status TEXT DEFAULT 'ARRIVED',
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("[스키마] shipment 테이블 생성 완료")

    def _init_inventory_table(self) -> None:
        """재고(Inventory) 테이블 — v2.5.4: LOT 단위 통합 재고"""
        self.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_no TEXT UNIQUE NOT NULL,
                lot_sqm TEXT,
                sap_no TEXT,
                bl_no TEXT,
                container_no TEXT,
                product TEXT NOT NULL DEFAULT 'LITHIUM CARBONATE',
                product_code TEXT,
                net_weight REAL DEFAULT 0,
                gross_weight REAL DEFAULT 0,
                initial_weight REAL DEFAULT 0,
                current_weight REAL DEFAULT 0,
                picked_weight REAL DEFAULT 0,
                mxbg_pallet INTEGER DEFAULT 0,
                tonbag_count INTEGER DEFAULT 0,
                ship_date DATE,
                arrival_date DATE,
                stock_date DATE,
                salar_invoice_no TEXT,
                warehouse TEXT DEFAULT '광양',
                status TEXT DEFAULT 'AVAILABLE',
                sold_to TEXT,
                sale_ref TEXT,
                vessel TEXT,
                free_time INTEGER DEFAULT 0,
                con_return TEXT,
                location TEXT,
                customs TEXT,
                inbound_date TEXT,
                -- v8.7.0: BL/Invoice/DO 파생 필드
                voyage TEXT DEFAULT '',
                do_no TEXT DEFAULT '',
                invoice_date DATE,
                total_amount REAL DEFAULT 0,
                currency TEXT DEFAULT '',
                unit_price REAL DEFAULT 0,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("[스키마] inventory 테이블 생성 완료")

        self.execute("""
            CREATE TABLE IF NOT EXISTS inventory_detail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_no TEXT NOT NULL,
                container_no TEXT,
                net_weight REAL DEFAULT 0,
                gross_weight REAL DEFAULT 0,
                mxbg_pallet INTEGER DEFAULT 0,
                location TEXT,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lot_no) REFERENCES inventory(lot_no) ON DELETE CASCADE
            )
        """)
        logger.info("[스키마] inventory_detail 테이블 생성 완료")

        # v8.7.0 Phase 3-A: D/O 복수 컨테이너 / 반납일 1:N 저장 테이블
        # 기존 inventory.container_no / con_return 단일 필드는 유지하고,
        # 상세 N건은 여기에 보존(demurrage 정산 리스크 해소용).
        self.execute("""
            CREATE TABLE IF NOT EXISTS container_info (
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
            )
        """)
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_container_info_lot "
            "ON container_info(lot_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_container_info_container_no "
            "ON container_info(container_no)"
        )
        logger.info("[스키마] container_info 테이블 생성 완료")

        self.execute("""
            CREATE TABLE IF NOT EXISTS freetime_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_no TEXT NOT NULL,
                inventory_id INTEGER,
                container_no TEXT DEFAULT '',
                free_time_date DATE,
                return_location TEXT DEFAULT '',
                storage_free_days INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_freetime_info_lot "
            "ON freetime_info(lot_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_freetime_info_date "
            "ON freetime_info(free_time_date)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_freetime_info_container "
            "ON freetime_info(container_no)"
        )
        logger.info("[스키마] freetime_info 테이블 생성 완료")

        # v8.7.0 Phase 3-B: Invoice 전필드 보존용 document_invoice 테이블
        # InvoiceData dataclass와 1:1 매칭 — 기존 inventory의 4필드(invoice_date/total_amount
        # /currency/unit_price) 외 customer_*/product_*/payment_term/incoterm/quantity_mt
        # 등 비즈니스 필드 유실 방지.
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
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_invoice_lot "
            "ON document_invoice(lot_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_invoice_invoice_no "
            "ON document_invoice(invoice_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_invoice_sap "
            "ON document_invoice(sap_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_invoice_date "
            "ON document_invoice(invoice_date)"
        )
        logger.info("[스키마] document_invoice 테이블 생성 완료")

        # v8.7.0 Phase 3-B: BL/PL/DO 전필드 보존용 대칭 3테이블
        # BLData / PackingListData(헤더·요약) / DOData dataclass 와 1:1 매칭
        # Phase 3-A 의 container_info / freetime_info 테이블과 독립적으로 공존
        # (3-A는 1:N 상세, 3-B는 문서 헤더/요약)
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
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_bl_lot "
            "ON document_bl(lot_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_bl_bl_no "
            "ON document_bl(bl_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_bl_carrier "
            "ON document_bl(carrier_id)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_bl_ship_date "
            "ON document_bl(ship_date)"
        )
        logger.info("[스키마] document_bl 테이블 생성 완료")

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
                -- v8.7.0 [U-1 b]: PL lots[] 원본 JSON 보존 (감사·재파싱·역조회용)
                lots_json TEXT DEFAULT '',
                source_file TEXT DEFAULT '',
                parsed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_pl_lot "
            "ON document_pl(lot_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_pl_bl_no "
            "ON document_pl(bl_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_pl_sap "
            "ON document_pl(sap_no)"
        )
        logger.info("[스키마] document_pl 테이블 생성 완료")

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
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_do_lot "
            "ON document_do(lot_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_do_do_no "
            "ON document_do(do_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_do_bl_no "
            "ON document_do(bl_no)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_doc_do_arrival "
            "ON document_do(arrival_date)"
        )
        logger.info("[스키마] document_do 테이블 생성 완료")

    def _init_tonbag_table(self) -> None:
        """톤백(inventory_tonbag) 테이블 — 개별 톤백 관리"""
        self.execute("""
            CREATE TABLE IF NOT EXISTS inventory_tonbag (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inventory_id INTEGER,
                lot_no TEXT NOT NULL,
                sap_no TEXT,
                bl_no TEXT,
                inbound_date TEXT,
                sub_lt INTEGER NOT NULL DEFAULT 0,  -- ★삭제금지: UNIQUE INDEX(lot_no,sub_lt) 키 + 샘플 판별(=0) — 53개 파일 연동
                weight REAL DEFAULT 0.0,    -- v8.6.1: 0=미설정, 입고 시 계산값으로 덮어씌워짐
                is_sample INTEGER DEFAULT 0,
                status TEXT DEFAULT 'AVAILABLE',
                location TEXT,
                location_updated_at TEXT,
                picked_to TEXT,
                picked_date TEXT,
                pick_ref TEXT,
                outbound_date TEXT,
                sale_ref TEXT,
                tonbag_uid TEXT,
                source_sub_lt_raw TEXT,
                source_sub_lt_hdr TEXT,
                con_return TEXT,
                tonbag_no TEXT,
                remarks TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lot_no) REFERENCES inventory(lot_no) ON DELETE CASCADE,
                FOREIGN KEY (inventory_id) REFERENCES inventory(id)
            )
        """)
        self.execute("CREATE INDEX IF NOT EXISTS idx_tonbag_lot ON inventory_tonbag(lot_no)")
        # idx_tonbag_inventory_id는 _migrate_v591_tonbag_fk_columns()에서 생성 (구 DB에 inventory_id 추가 후)
        self.execute("CREATE INDEX IF NOT EXISTS idx_tonbag_status ON inventory_tonbag(status)")
        self.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tonbag_lot_sublt ON inventory_tonbag(lot_no, sub_lt)")
        logger.info("[스키마] inventory_tonbag 테이블 생성 완료")

    def _init_outbound_tables(self) -> None:
        """출고(outbound + outbound_item) 테이블"""
        self.execute("""
            CREATE TABLE IF NOT EXISTS outbound (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_ref TEXT,
                customer TEXT,
                total_qty_mt REAL DEFAULT 0,
                outbound_date DATE,
                destination TEXT,
                status TEXT DEFAULT 'PENDING',
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.execute("""
            CREATE TABLE IF NOT EXISTS outbound_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                outbound_id INTEGER,
                inventory_id INTEGER,
                lot_no TEXT NOT NULL,
                sub_lt INTEGER,
                qty_kg REAL DEFAULT 0,
                inbound_date DATE,
                location TEXT,
                customer TEXT,
                destination TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (outbound_id) REFERENCES outbound(id) ON DELETE CASCADE,
                FOREIGN KEY (inventory_id) REFERENCES inventory(id)
            )
        """)
        logger.info("[스키마] outbound, outbound_item 테이블 생성 완료")


        # RUBI Phase3: UID 스캔 즉시 확정 감사 로그
        self.execute("""
            CREATE TABLE IF NOT EXISTS outbound_scan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tonbag_id INTEGER NOT NULL,
                tonbag_uid TEXT NOT NULL,
                lot_no TEXT NOT NULL,
                weight_kg REAL DEFAULT 0,
                sale_ref TEXT,
                user_id TEXT,
                device_id TEXT,
                scanned_at TEXT DEFAULT (datetime('now')),
                voided_at TEXT,
                FOREIGN KEY (tonbag_id) REFERENCES inventory_tonbag(id)
            )
        """)
        try:
            self.execute("""CREATE INDEX IF NOT EXISTS idx_outbound_scan_lot ON outbound_scan(lot_no)""")
            self.execute("""CREATE INDEX IF NOT EXISTS idx_outbound_scan_scanned ON outbound_scan(scanned_at)""")
        except Exception:
            logger.debug("[SUPPRESSED] exception in db_schema_mixin.py")  # noqa



    def _init_lot_summary_view(self) -> None:
        """v7.9.9 [H-2]: inventory_lot_summary VIEW 추가 (A안).
        기존 코드 무변경 — VIEW만 추가. inventory_tonbag이 SSOT.
        새 집계 쿼리에서 이 VIEW를 사용하면 current_weight 동기화 문제 자동 해결.
        SQLite 3.25+ FILTER 지원.
        """
        try:
            self.execute("""
                CREATE VIEW IF NOT EXISTS inventory_lot_summary AS
                SELECT
                    lot_no,
                    COUNT(*)
                        FILTER(WHERE status='AVAILABLE' AND COALESCE(is_sample,0)=0)
                        AS available_count,
                    COALESCE(SUM(weight)
                        FILTER(WHERE status='AVAILABLE' AND COALESCE(is_sample,0)=0), 0)
                        AS current_weight_kg,
                    COUNT(*)
                        FILTER(WHERE status='RESERVED')
                        AS reserved_count,
                    COALESCE(SUM(weight)
                        FILTER(WHERE status='RESERVED'), 0)
                        AS reserved_weight_kg,
                    COUNT(*)
                        FILTER(WHERE status='PICKED')
                        AS picked_count,
                    COALESCE(SUM(weight)
                        FILTER(WHERE status='PICKED'), 0)
                        AS picked_weight_kg,
                    COUNT(*)
                        FILTER(WHERE status IN ('OUTBOUND','SOLD','SHIPPED','CONFIRMED'))
                        AS outbound_count,
                    COALESCE(SUM(weight)
                        FILTER(WHERE status IN ('OUTBOUND','SOLD','SHIPPED','CONFIRMED')), 0)
                        AS outbound_weight_kg,
                    COUNT(*)
                        FILTER(WHERE COALESCE(is_sample,0)=1)
                        AS sample_count,
                    COUNT(*)  AS total_count,
                    COALESCE(SUM(weight), 0) AS total_weight_kg
                FROM inventory_tonbag
                GROUP BY lot_no
            """)
            logger.info("[스키마] inventory_lot_summary VIEW 생성 완료")
        except Exception as e:
            logger.debug(f"[스키마] inventory_lot_summary VIEW 스킵: {e}")

    def _init_audit_log_table(self) -> None:
        """v7.9.9 [C-1]: audit_log 테이블 중앙화 — 앱 시작 시 반드시 생성 보장.
        기존: onestop_outbound.py 로컬 생성 → 컬럼 불일치 silent fail 위험
        개선: db_schema_mixin에서 통일 스키마로 생성
        컬럼 통일: event_type, event_data, batch_id, tonbag_id, user_note, created_by, created_at
        """
        try:
            self.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type  TEXT    NOT NULL,
                    event_data  TEXT,
                    batch_id    TEXT,
                    tonbag_id   TEXT,
                    user_note   TEXT,
                    created_by  TEXT    DEFAULT 'system',
                    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
                )
            """)
            self.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_event_type
                ON audit_log(event_type, created_at)
            """)
            self.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_created
                ON audit_log(created_at)
            """)
            logger.info("[스키마] audit_log 테이블 생성 완료")
        except Exception as e:
            logger.warning(f"[스키마] audit_log 생성 스킵: {e}")

    def _init_movement_tables(self) -> None:
        """재고 이동 이력(stock_movement) + 반품(return_history) 테이블"""
        self.execute("""
            CREATE TABLE IF NOT EXISTS stock_movement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_no TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                qty_kg REAL DEFAULT 0,
                from_location TEXT,
                to_location TEXT,
                customer TEXT,
                movement_date TIMESTAMP,
                source_type TEXT DEFAULT '',
                source_file TEXT DEFAULT '',
                ref_table TEXT,
                ref_id INTEGER,
                source TEXT,
                actor TEXT,
                details_json TEXT,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lot_no) REFERENCES inventory(lot_no)
            )
        """)
        try:
            # 구 DB(컬럼 미존재)에서는 초기화 단계에서 실패할 수 있으므로 마이그레이션에서 재시도.
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_stock_mv_ref ON stock_movement(ref_table, ref_id)"
            )
        except sqlite3.OperationalError as e:
            logger.debug(f"[스키마] idx_stock_mv_ref 생성 지연(마이그레이션에서 재시도): {e}")
        self.execute("""
            CREATE TABLE IF NOT EXISTS return_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_no TEXT NOT NULL,
                sub_lt INTEGER,
                return_date DATE,
                original_customer TEXT,
                original_sale_ref TEXT,
                reason TEXT,
                remark TEXT,
                weight_kg REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lot_no) REFERENCES inventory(lot_no)
            )
        """)
        logger.info("[스키마] stock_movement, return_history 테이블 생성 완료")

        # v8.1.7: tonbag_move_log — 톤백 위치 이동 이력 전용 테이블
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
        try:
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_move_log_lot "
                "ON tonbag_move_log(lot_no)"
            )
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_move_log_status "
                "ON tonbag_move_log(status)"
            )
            self.execute(
                "CREATE INDEX IF NOT EXISTS idx_move_log_date "
                "ON tonbag_move_log(move_date)"
            )
        except Exception as _e:
            logger.debug(f"[스키마] tonbag_move_log 인덱스 생성 지연: {_e}")
        logger.info("[스키마] tonbag_move_log 테이블 생성 완료")

        self.execute("""
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
        """)
        logger.info("[스키마] allocation_import_batch 테이블 생성 완료")

    def _init_parsing_log_table(self) -> None:
        """v8.2.4: 파싱 통계 테이블 — BL/DO/PL/Invoice 파싱 결과 자동 기록"""
        self.execute("""
            CREATE TABLE IF NOT EXISTS parsing_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type    TEXT NOT NULL,       -- 'BL'|'DO'|'PL'|'INVOICE'
                source_file TEXT,                -- 원본 파일명
                carrier_id  TEXT,                -- 선사 코드 (BL 전용)
                success     INTEGER DEFAULT 0,   -- 1=성공, 0=실패
                bl_no       TEXT,                -- 추출된 BL No
                lot_count   INTEGER DEFAULT 0,   -- 추출된 LOT 수 (PL 전용)
                method      TEXT,                -- 'regex'|'gemini'|'gemini_retry'
                error_msg   TEXT,                -- 실패 시 오류 메시지
                duration_ms INTEGER DEFAULT 0,   -- 파싱 소요 시간 (ms)
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_parsing_log_doc_type "
            "ON parsing_log(doc_type)"
        )
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_parsing_log_created "
            "ON parsing_log(created_at)"
        )
        logger.info("[스키마] parsing_log 테이블 생성 완료")

    def _init_snapshot_tables(self) -> None:
        """재고 스냅샷(inventory_snapshot) 테이블"""
        self.execute("""
            CREATE TABLE IF NOT EXISTS inventory_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date DATE NOT NULL,
                total_lots INTEGER DEFAULT 0,
                total_tonbags INTEGER DEFAULT 0,
                total_weight_kg REAL DEFAULT 0,
                available_weight_kg REAL DEFAULT 0,
                picked_weight_kg REAL DEFAULT 0,
                product_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(snapshot_date)
            )
        """)
        self.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_date ON inventory_snapshot(snapshot_date)")
        logger.info("[스키마] inventory_snapshot 테이블 생성 완료")


    def _migrate_v660_move(self) -> None:
        """
        v6.6.0 MOVE 기능 강화:
        - stock_movement: sub_lt, reason_code, operator 컬럼 추가
        - ⑤ move_batch 테이블: 대량 이동 PENDING→Supervisor 승인 워크플로
        - ⑥ location_move_log 폐지 → stock_movement 단일 이력 정책
        """
        try:
            cols = {r['name'] for r in (self.fetchall(
                "PRAGMA table_info(stock_movement)") or [])}
            if 'sub_lt' not in cols:
                self.execute(
                    "ALTER TABLE stock_movement ADD COLUMN sub_lt INTEGER DEFAULT NULL")
                logger.info("[v6.6.0] stock_movement.sub_lt 컬럼 추가")
            if 'reason_code' not in cols:
                self.execute(
                    "ALTER TABLE stock_movement ADD COLUMN reason_code TEXT DEFAULT NULL")
                logger.info("[v6.6.0] stock_movement.reason_code 컬럼 추가")
            if 'operator' not in cols:
                self.execute(
                    "ALTER TABLE stock_movement ADD COLUMN operator TEXT DEFAULT 'system'")
                logger.info("[v6.6.0] stock_movement.operator 컬럼 추가")
        except Exception as e:
            logger.warning(f"[v6.6.0] stock_movement 마이그레이션 오류: {e}")

        # ⑤ move_batch 테이블 — 대량 이동 PENDING→승인 워크플로
        self.execute("""
            CREATE TABLE IF NOT EXISTS move_batch (
                batch_id      TEXT PRIMARY KEY,
                status        TEXT NOT NULL DEFAULT 'PENDING',
                total_count   INTEGER DEFAULT 0,
                source        TEXT DEFAULT 'EXCEL',
                reason_code   TEXT DEFAULT 'RELOCATE',
                submitted_by  TEXT DEFAULT 'system',
                submitted_at  TEXT NOT NULL,
                approved_by   TEXT,
                approved_at   TEXT,
                rejected_by   TEXT,
                rejected_at   TEXT,
                reject_reason TEXT,
                items_json    TEXT,
                note          TEXT
            )
        """)
        logger.info("[v6.6.0] move_batch 테이블 생성")

    def _migrate_v243(self) -> None:
        """v2.4.3 스키마 마이그레이션 — 출고 리스트 필드 추가 + 톤백 테이블 이름 변경"""
        try:
            self.execute("ALTER TABLE inventory_sublot RENAME TO inventory_tonbag")
            logger.info("[마이그레이션] inventory_sublot → inventory_tonbag 이름 변경됨")
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower() and "already exists" not in str(e).lower():
                logger.debug(f"[마이그레이션] 테이블 이름 변경 스킵: {e}")

        migrations = [
            ("shipment", "port_of_loading", "TEXT"),
            ("shipment", "port_of_discharge", "TEXT"),
            ("shipment", "total_net_weight", "REAL"),
            ("shipment", "total_gross_weight", "REAL"),
            ("outbound", "destination", "TEXT"),
            ("outbound", "remarks", "TEXT"),
            ("outbound_item", "inbound_date", "DATE"),
            ("outbound_item", "location", "TEXT"),
            ("outbound_item", "customer", "TEXT"),
            ("outbound_item", "destination", "TEXT"),
            ("inventory_tonbag", "sale_ref", "TEXT"),
        ]
        for table, column, col_type in migrations:
            try:
                self.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                logger.info(f"[마이그레이션] {table}.{column} 추가됨")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    logger.debug(f"[마이그레이션] {table}.{column} 스킵: {e}")

        self._migrate_v289_picking_list()
        self._migrate_v388_column_unify()
        self._migrate_v391_sample_tonbag()
        self._migrate_v396_search_indexes()
        self._migrate_v588_con_return()
        self._migrate_v591_tonbag_fk_columns()
        self._migrate_v593_allocation_plan()
        self._migrate_v599_missing_columns()
        self._migrate_v600_picking_sold_tables()

    def _verify_schema(self) -> Dict[str, Any]:
        """DB 스키마 자동 점검 — 필수 테이블/컬럼 확인"""
        result = {
            'ok': True, 'missing_tables': [],
            'missing_columns': {}, 'warnings': []
        }
        required_tables = [
            'shipment', 'inventory', 'inventory_tonbag', 'outbound', 'outbound_item',
            'allocation_plan',  # v5.9.3 예약(RESERVED) 이력
        ]
        required_columns = {
            'shipment': ['sap_no', 'bl_no', 'arrival_date', 'origin', 'destination'],
            'inventory': ['lot_no', 'sap_no', 'product', 'current_weight', 'status'],
            'inventory_tonbag': ['lot_no', 'sub_lt', 'weight', 'status'],
        }
        try:
            existing_tables = self.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
            existing_table_names = {row['name'] for row in existing_tables}
            for table in required_tables:
                if table not in existing_table_names:
                    result['missing_tables'].append(table)
                    result['ok'] = False
            # allocation_plan 누락 시 마이그레이션 재시도 (구 DB 호환)
            if 'allocation_plan' in result['missing_tables']:
                try:
                    self._migrate_v593_allocation_plan()
                    self._migrate_v600_picking_sold_tables()
                    existing_tables = self.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
                    existing_table_names = {row['name'] for row in existing_tables}
                    if 'allocation_plan' in existing_table_names:
                        result['missing_tables'] = [t for t in result['missing_tables'] if t != 'allocation_plan']
                        result['ok'] = not result['missing_tables'] and not result['missing_columns']
                        logger.info("[스키마 점검] allocation_plan 생성 후 보정 완료")
                except Exception as e:
                    logger.debug(f"[스키마 점검] allocation_plan 보정 스킵: {e}")
            for table, columns in required_columns.items():
                if table not in existing_table_names:
                    continue
                existing_cols = self.fetchall(f"PRAGMA table_info({table})")
                existing_col_names = {row['name'] for row in existing_cols}
                missing = [col for col in columns if col not in existing_col_names]
                if missing:
                    result['missing_columns'][table] = missing
                    result['ok'] = False
            if result['ok']:
                logger.info("[스키마 점검] ✅ 모든 필수 테이블/컬럼 확인됨")
            else:
                if result['missing_tables']:
                    logger.warning(f"[스키마 점검] ⚠️ 누락된 테이블: {result['missing_tables']}")
                if result['missing_columns']:
                    logger.warning(f"[스키마 점검] ⚠️ 누락된 컬럼: {result['missing_columns']}")
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"[스키마 점검] 오류: {e}")
            result['ok'] = False
            result['warnings'].append(str(e))
        return result

    def get_schema_status(self) -> Dict[str, Any]:
        """외부에서 스키마 상태 조회용"""
        return self._verify_schema()

    def _create_indexes(self) -> None:
        """성능 향상을 위한 인덱스 생성"""
        indexes = [
            ("idx_inventory_lot_no", "inventory", "lot_no"),
            ("idx_inventory_sap_no", "inventory", "sap_no"),
            ("idx_inventory_status", "inventory", "status"),
            ("idx_inventory_stock_date", "inventory", "stock_date"),
            ("idx_inventory_created_at", "inventory", "created_at"),
            ("idx_inventory_stock_created", "inventory", "stock_date, created_at"),
            ("idx_inventory_product", "inventory", "product_code"),
            ("idx_inventory_warehouse", "inventory", "warehouse"),
            ("idx_inventory_bl_no_nocase", "inventory", "bl_no COLLATE NOCASE"),
            ("idx_inventory_lot_product", "inventory", "lot_no, product_code"),
            ("idx_inventory_sap_status", "inventory", "sap_no, status"),
            ("idx_inventory_product_status", "inventory", "product_code, status"),
            ("idx_detail_lot_no", "inventory_detail", "lot_no"),
            ("idx_detail_container", "inventory_detail", "container_no"),
            ("idx_detail_lot_container", "inventory_detail", "lot_no, container_no"),
            ("idx_shipment_sap_no", "shipment", "sap_no"),
            ("idx_shipment_bl_no", "shipment", "bl_no"),
            ("idx_shipment_folio", "shipment", "folio"),
            ("idx_shipment_status", "shipment", "status"),
            ("idx_outbound_sale_ref", "outbound", "sale_ref"),
            ("idx_outbound_customer", "outbound", "customer"),
            ("idx_outbound_date", "outbound", "outbound_date"),
            ("idx_outbound_item_lot", "outbound_item", "lot_no"),
            ("idx_outbound_item_inventory", "outbound_item", "inventory_id"),
            ("idx_outbound_item_outbound", "outbound_item", "outbound_id"),
            ("idx_movement_lot", "stock_movement", "lot_no"),
            ("idx_movement_type", "stock_movement", "movement_type"),
            ("idx_movement_date", "stock_movement", "created_at"),
            ("idx_movement_lot_created", "stock_movement", "lot_no, created_at"),
        ]
        for idx_name, table, columns in indexes:
            try:
                self.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
            except sqlite3.OperationalError as e:
                logger.debug(f"인덱스 생성 스킵: {idx_name} - {e}")
        try:
            self.execute("ANALYZE")
        except (sqlite3.Error, OSError) as e:
            logger.debug(f"ANALYZE 실패: {e}")
