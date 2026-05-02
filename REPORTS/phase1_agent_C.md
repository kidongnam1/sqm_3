# Phase 1-C: DB 스키마 감사 결과
날짜: 2026-04-30

---

## 체크1: 테이블 목록
총 37개 테이블:

| 테이블명 | 컬럼 수 |
|---|---|
| allocation_approval | 6 |
| allocation_import_batch | 9 |
| allocation_plan | 31 |
| audit_log | 8 |
| carrier_profile | 6 |
| container_info | 10 |
| document_bl | 36 |
| document_do | 30 |
| document_invoice | 33 |
| document_pl | 23 |
| freetime_info | 8 |
| inbound_template | 15 |
| inventory | 39 |
| inventory_detail | 9 |
| inventory_snapshot | 9 |
| inventory_tonbag | 28 |
| migration_flags | 3 |
| move_batch | 14 |
| outbound | 12 |
| outbound_item | 12 |
| outbound_scan | 10 |
| parsing_log | 11 |
| picking_list_detail | 9 |
| picking_list_order | 21 |
| picking_table | 24 |
| picking_template | 13 |
| product_master | 10 |
| return_history | 10 |
| sales_order_import_log | 12 |
| schema_version | 5 |
| shipment | 20 |
| sold_table | 25 |
| sqlite_sequence | 2 |
| sqlite_stat1 | 3 |
| stock_movement | 20 |
| tonbag_move_log | 14 |
| uid_swap_history | 8 |

---

## 체크2: carrier_rules 검증

**[FAIL] carrier_rules 테이블이 DB에 존재하지 않음**

- `sqlite_master` 조회 결과: `carrier_rules` 테이블 없음 (COUNT = 0)
- DB에 레코드 없음 → ONE BL 패턴 확인 불가

**원인 분석:**
- `backend/api/__init__.py`의 `_run_db_migrations()` 함수에 carrier_rules CREATE TABLE 문이 존재하고, 함수 최하단에서 `_run_db_migrations()` 호출이 있음
- 그러나 이 마이그레이션은 **FastAPI 앱 import 시점**에 실행됨 (앱 서버가 한 번도 기동된 적 없는 DB이거나, migration이 예외로 중단됐을 가능성)
- DB 파일이 마지막으로 수정된 시각 기준 (`Apr 30 04:57`), 서버 기동이 있었다면 테이블이 존재해야 함
- **결론: carrier_rules 마이그레이션이 실제 DB에 적용되지 않은 상태**

**코드 상 ONE BL 패턴 (migration INSERT 기준):**
- carrier_rules 초기 INSERT 코드: `pattern = 'ONEY[A-Z0-9]{8,15}'` ← ONEY 올바름
- UPDATE 조건: `WHERE pattern = 'ONEU[A-Z0-9]{6,10}'` → ONEU → ONEY 교정 로직 존재

---

## 체크3: 마이그레이션 코드 확인

파일: `backend/api/__init__.py` (lines 33~112)

| 항목 | 상태 |
|---|---|
| carrier_rules CREATE TABLE 문 | [PASS] 존재 (line 62~73) |
| ONE BL UPDATE 문 (ONEU→ONEY) | [PASS] 존재 (line 77~88) |
| 초기 INSERT (ONEY 패턴) | [PASS] 존재 (line 93~104) |
| 실행 시점 | module-level `_run_db_migrations()` 호출 (line 112) — FastAPI app 생성 전, import 시 즉시 실행 |

**[FAIL] 실제 DB에 적용 여부:** 미적용
- DB에 carrier_rules 테이블 없음 → 앱이 실행된 적 없거나 마이그레이션 중 예외 발생 후 silent 처리됨
- `except Exception as e: logging.warning(...)` 로 실패 시 경고만 출력하고 계속 진행 → 운영 환경에서 마이그레이션 실패가 무음으로 넘어갈 수 있음

---

## 체크4: 컬럼 일치 확인

### inventory 테이블 (39개 컬럼)
```
id, lot_no, lot_sqm, sap_no, bl_no, container_no, product, product_code,
net_weight, gross_weight, initial_weight, current_weight, picked_weight,
mxbg_pallet, tonbag_count, ship_date, arrival_date, stock_date,
salar_invoice_no, warehouse, status, sold_to, sale_ref, vessel, free_time,
con_return, location, customs, inbound_date, voyage, do_no, invoice_date,
total_amount, currency, unit_price, remarks, created_at, updated_at, folio
```

### shipment_records 테이블
**[없음]** — 해당 테이블 DB에 존재하지 않음 (0 columns)

### lot_records 테이블
**[없음]** — 해당 테이블 DB에 존재하지 않음 (0 columns)

> 참고: 코드에서 `shipment_records` / `lot_records` 직접 참조 없음.
> inbound.py는 `engine.add_inventory_from_dict()` 경유로 `inventory` 테이블에 저장.

### update_dict 키 vs inventory 컬럼 대조

**Invoice update_dict (6개 키):**
| 키 | inventory 컬럼 존재 | 판정 |
|---|---|---|
| sap_no | ✅ | OK |
| salar_invoice_no | ✅ | OK |
| ship_date | ✅ | OK |
| total_amount | ✅ | OK |
| unit_price | ✅ | OK |
| invoice_date | ✅ | OK |

**BL update_dict (4개 키):**
| 키 | inventory 컬럼 존재 | 판정 |
|---|---|---|
| bl_no | ✅ | OK |
| vessel | ✅ | OK |
| voyage | ✅ | OK |
| ship_date | ✅ | OK |

**add_inventory_from_dict 주요 키 (16개, onestop-save 기준):**
| 키 | inventory 컬럼 존재 | 판정 |
|---|---|---|
| lot_no | ✅ | OK |
| sap_no | ✅ | OK |
| bl_no | ✅ | OK |
| product | ✅ | OK |
| container_no | ✅ | OK |
| product_code | ✅ | OK |
| lot_sqm | ✅ | OK |
| mxbg_pallet | ✅ | OK |
| net_weight | ✅ | OK |
| gross_weight | ✅ | OK |
| salar_invoice_no | ✅ | OK |
| ship_date | ✅ | OK |
| arrival_date | ✅ | OK |
| con_return | ✅ | OK |
| free_time | ✅ | OK |
| warehouse | ✅ | OK |

**불일치: 없음** — 모든 update_dict 키가 inventory 컬럼에 존재함

---

## 체크5: DB 무결성

```
integrity_check: ok
```

**파일 크기: 744.0 KB (0.727 MB)**
(측정: Python os.path.getsize 기준 — `ls -lh` 결과와 동일 728K)

---

## 종합 판정: YELLOW

### 정상 항목
- inventory 테이블 39개 컬럼 정상 (folio, vessel migration 컬럼 포함)
- update_dict 키 전체 OK (Invoice 6개 / BL 4개 / add_inventory 16개 — 불일치 0건)
- DB 무결성 ok
- migration 코드 자체는 올바름 (ONEY 패턴 포함)

### 요주의 항목 (YELLOW 근거)

1. **carrier_rules 테이블 미존재** — 앱 서버를 한 번이라도 기동해야 마이그레이션이 적용됨.
   - Phase 6 EXE 빌드 테스트 시 최초 기동 후 재확인 필수
   - 기동 전 배포 환경에서는 `parse_alarm` 모듈이 carrier_rules를 조회할 경우 예외 가능성 있음

2. **마이그레이션 silent fail 위험** — `_run_db_migrations()` 예외 처리가 `logging.warning`으로 흡수됨.
   - 실패 시 운영 환경에서 증상 없이 기능 결함 발생 가능
   - 권장: 마이그레이션 실패 시 startup 이벤트에서 명시적 경고 또는 앱 기동 거부

3. **shipment_records / lot_records 테이블 없음** — 임무 명세서에 명시된 테이블이나 실제 코드에서 직접 참조 없음 (구버전 v864 잔재 명칭으로 추정). 현재 v866 코드는 `inventory` 단일 테이블 사용.

---

*생성: Phase 1-C DB 스키마 감사 Agent (2026-04-30)*
