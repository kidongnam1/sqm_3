# SQM v866 DB 중복 금지 원칙 및 수정 대상 보고서

> 작성일: 2026-05-03  
> 대상 폴더: `D:\program\SQM_inventory\SQM_v866_CLEAN`  
> 기준: 사용자 운영 원칙 및 현재 v866 코드 점검 결과  
> 핵심 원칙: **반품을 제외한 모든 업무 흐름에서 같은 실물 데이터가 DB에 중복 반영되면 안 된다.**

---

## 1. 최종 원칙

사용자가 정정한 최종 원칙은 아래와 같다.

```text
입고 → Allocation → Picked → Outbound → 이동
위 흐름에서는 DB 중복을 허용하지 않는다.

단, 반품은 예외이다.
반품으로 정식 복귀한 데이터만 다시 재고 흐름에 들어올 수 있다.

하지만 반품 자체도 같은 반품 건을 두 번 처리하는 중복은 허용하지 않는다.
```

즉, 예외는 **이동이 아니라 반품**이다.  
이동은 중복 금지 대상이다.

---

## 2. 중복 금지 대상

### 2.1 절대 중복 금지 대상

아래 테이블 또는 업무 실체는 중복되면 안 된다.

| 구분 | 기준 |
|---|---|
| 입고 LOT | 동일 `lot_no` 중복 금지 |
| 톤백 | 동일 `lot_no + sub_lt` 중복 금지 |
| 톤백 UID | 동일 `tonbag_uid` 중복 금지 |
| Allocation | 활성 상태의 동일 LOT/고객/SALE REF 중복 금지 |
| Picking | 동일 Picking No 재업로드 및 동일 톤백 중복 Picking 금지 |
| Outbound | 동일 톤백/동일 Picking/Sales Order 중복 출고 금지 |
| 이동 | 동일 톤백의 같은 위치 중복 이동, 동일 위치 점유 중복 금지 |

### 2.2 허용 가능한 다행 데이터

아래는 업무 실체 중복이 아니라 이력/감사/문서 보존 성격이므로 여러 행이 있을 수 있다.

| 테이블 | 성격 |
|---|---|
| `stock_movement` | 재고 변동 이력 |
| `audit_log` | 감사 로그 |
| `return_history` | 반품 이력 |
| `tonbag_move_log` | 이동 이력 |
| `document_bl`, `document_pl`, `document_do`, `document_invoice` | 문서 파싱/재파싱 이력 |

단, 이력 테이블도 **같은 이벤트가 실수로 두 번 실행되어 생긴 중복**은 막아야 한다.

---

## 3. 현재 프로그램 상태 요약

### 3.1 입고

현재 상태:

- `inventory.lot_no`는 DB에서 `UNIQUE`.
- `inventory_tonbag(lot_no, sub_lt)`는 DB에서 `UNIQUE`.
- OneStop 입고 저장 시 파일 내부 중복 LOT 차단 로직을 추가함.
- OneStop 입고 저장 시 이미 DB에 있는 LOT 차단 로직을 추가함.
- 프론트에서도 저장 전 같은 파일 내부 중복 LOT를 1차 차단함.

판단:

```text
입고 중복 방지는 비교적 안전한 상태이다.
```

남은 확인:

- 운영 DB에 실제 UNIQUE 인덱스가 존재하는지 확인 필요.
- 레거시 Tk 입고 경로도 동일 원칙을 타는지 최종 확인 필요.

---

### 3.2 Allocation

현재 상태:

- `reserve_from_allocation` 엔진에 중복 검사 로직이 있음.
- 같은 `lot_no + customer + sale_ref + outbound_date` 활성 배정은 코드에서 차단함.
- LOT 단위 `sale_ref + lot_no` 중복도 일부 차단함.
- `allocation_plan`에 중복 방지 인덱스가 존재함.

위험 지점:

- 현재 `allocation_plan` 중복 방지 인덱스는 `tonbag_id`를 포함한다.
- LOT 모드에서는 `tonbag_id`가 `NULL`일 수 있다.
- SQLite에서는 `NULL`이 포함된 UNIQUE가 완전한 중복 차단으로 동작하지 않을 수 있다.

판단:

```text
정상 엔진 경로는 대부분 안전하지만,
LOT 모드 Allocation은 DB 레벨 보강이 필요하다.
```

수정 필요:

- `tonbag_id IS NULL`인 LOT 모드 전용 활성 중복 방지 UNIQUE 인덱스 추가.
- 동일 Allocation 파일 재업로드 시 `duplicate_file`을 API 응답에 명확히 표시.
- 중복 파일을 단순 경고로 둘지, 기본 차단으로 둘지 정책 확정.

---

### 3.3 Picked

현재 상태:

- 기존에는 `PickingEngine.check_duplicate()`가 있었지만 실제 `process()`에서 강하게 차단하지 않는 위험이 있었다.
- 현재는 같은 `Picking No` 재업로드를 차단하도록 보강함.
- 이미 살아 있는 `picking_table` 톤백은 다시 Picking 되지 않도록 보강함.
- 중복 Picking 발생 시 API에서 `409`를 반환하도록 보강함.

위험 지점:

- `picking_table`에는 아직 강한 DB UNIQUE 제약이 부족하다.
- 코드 경로를 우회하면 중복 행이 들어갈 가능성이 남는다.

판단:

```text
웹 Picking 업로드 경로는 보강됐지만,
DB 레벨 활성 중복 UNIQUE 제약이 추가로 필요하다.
```

수정 필요:

- `picking_table`에 활성 상태 기준 중복 방지 인덱스 추가.
- 예: 같은 `tonbag_id`가 `ACTIVE`, `SOLD`, `OUTBOUND` 상태로 두 번 존재하지 못하게 차단.
- 같은 `picking_no + lot_no + sub_lt` 활성 중복도 차단 후보.

---

### 3.4 Outbound / Sales Order

현재 상태:

- Sales Order No 중복은 엔진에서 차단함.
- 기존에는 `SOLD` 중심으로 보던 중복 검사를 `PENDING` 포함 처리 이력까지 보도록 보강함.
- 같은 `picking_id` 또는 `tonbag_id`가 `sold_table`에 다시 들어가지 못하도록 보강함.
- `sold_table`에는 `idx_sold_dedup` UNIQUE 인덱스 생성 로직이 있음.

위험 지점:

- 운영 DB에 기존 중복 데이터가 있으면 UNIQUE 인덱스 생성이 실패했을 수 있다.
- 스캔 API 중 일부 경로는 `barcode_scan_engine`의 멱등 로직을 타지 않을 수 있다.

판단:

```text
정상 Sales Order / Outbound 경로는 비교적 안전하다.
다만 운영 DB 인덱스 존재 여부와 스캔 경로 통일이 필요하다.
```

수정 필요:

- 운영 DB에서 `idx_sold_dedup` 실제 존재 확인.
- `scan_api`, `inventory_api.scan_router`, `barcode_scan_engine` 경로 통일.
- 직접 UPDATE 방식 스캔 API는 폐쇄하거나 엔진 경로로 위임.

---

### 3.5 이동

현재 상태:

- 이동은 상태 제한이 있다.
- `PICKED`, `SOLD`, `OUTBOUND`, `SHIPPED` 등은 이동 금지 상태로 취급된다.
- 같은 위치 이동은 차단한다.
- 위치 capacity 검사도 있다.

위험 지점:

현재 위치 점유 검사 조건이 자기 자신 제외 조건으로는 위험하다.

현재 형태:

```sql
AND lot_no != ? AND sub_lt != ?
```

이 조건은 같은 LOT의 다른 톤백이 같은 위치에 있는 경우를 놓칠 수 있다.

의도에 더 맞는 형태:

```sql
AND NOT (lot_no = ? AND sub_lt = ?)
```

또한 Move 탭 프론트 호출 경로와 실제 백엔드 API 계약이 어긋난 것으로 보인다.

판단:

```text
이동은 반품 예외가 아니므로 중복 금지 대상이다.
현재 Move 쪽은 수정 필요성이 높다.
```

수정 필요:

- 위치 점유 조건식 수정.
- Move 탭 API 경로와 payload 정합성 수정.
- 이동은 반드시 `engine.update_tonbag_location` 같은 검증된 경로를 타게 해야 함.
- 같은 이동 요청의 재승인/재실행 차단 확인.

---

### 3.6 반품

현재 상태:

- 반품은 예외 흐름이다.
- OUTBOUND/SOLD/PICKED/RESERVED 상태의 톤백을 RETURN 또는 AVAILABLE로 되돌릴 수 있다.
- 반품 시 `picking_table`, `sold_table`, `allocation_plan`을 `RETURNED` 또는 `CANCELLED`로 정리하는 로직이 있다.
- 이미 AVAILABLE인 톤백은 반품 처리하지 않도록 막는 로직이 있다.

중요한 기준:

```text
반품은 중복 허용이 아니라 상태 복구 예외이다.
```

즉:

- 출고 이력과 반품 이력이 같이 존재하는 것은 정상.
- 반품 후 AVAILABLE로 돌아온 톤백이 다시 Allocation/Picked/Outbound 흐름에 들어가는 것은 정상.
- 하지만 같은 반품 건을 두 번 처리하는 것은 중복이며 금지해야 한다.

판단:

```text
반품은 예외로 인정하되,
반품 자체의 중복 처리 방어는 추가 확인이 필요하다.
```

수정 필요:

- 같은 `lot_no + sub_lt + 원출고정보` 기준 반품 중복 처리 방어.
- `return_history` 또는 `return_log`에서 같은 반품 건 반복 처리 여부 확인.
- 이미 `RETURN` 또는 `AVAILABLE`인 톤백에 대한 재반품 하드스톱 유지.

---

### 3.7 문서 테이블

현재 상태:

- `document_bl`, `document_pl`, `document_do`, `document_invoice`는 재파싱/재업로드 때문에 중복 행을 허용하는 구조다.

판단:

```text
이 테이블들은 업무 실체 중복은 아니지만,
운영자가 보는 데이터와 연결될 경우 혼동 가능성이 있다.
```

정책 선택 필요:

1. 문서 이력 보존 방식 유지
2. 최신 1건만 active로 표시
3. 같은 파일 hash 또는 같은 문서번호 기준 중복 저장 차단

권장:

- 문서 테이블은 이력 보존을 유지하되, 화면/조회에서는 최신 active 1건만 쓰는 방식이 현실적이다.

---

## 4. 현재까지 반영한 수정

이번 논의 중 실제 반영된 중복 관련 수정은 아래와 같다.

### 4.1 OneStop 입고

수정 파일:

- `backend/api/inbound.py`
- `frontend/js/sqm-onestop-inbound.js`

반영 내용:

- 업로드 파일 내부 중복 LOT 차단.
- 이미 DB에 존재하는 LOT 차단.
- 프론트 저장 전 중복 LOT 1차 차단.
- 중복 발생 시 저장 중단.

### 4.2 Picking List

수정 파일:

- `features/parsers/picking_engine.py`
- `backend/api/outbound_api.py`

반영 내용:

- 같은 Picking No 재업로드 차단.
- 이미 활성 상태의 `picking_table`에 올라간 톤백 중복 Picking 차단.
- 중복 Picking 발생 시 API `409` 반환.

### 4.3 Sales Order / Outbound

수정 파일:

- `features/parsers/sales_order_engine.py`

반영 내용:

- `PENDING` 포함 기존 Sales Order 처리 이력 차단.
- 같은 `picking_id` 중복 SOLD 차단.
- 같은 `tonbag_id` 중복 SOLD 차단.

---

## 5. 앞으로 수정해야 할 항목

### P0. Move 중복 방지 수정

우선순위가 가장 높다.

수정 대상:

- `engine_modules/inventory_modular/tonbag_mixin.py`
- `frontend/js/sqm-inline.js`
- 관련 API: `/api/action/inventory-move`, `/api/action2/inventory-move`, 톤백 이동 API

필요 작업:

- 위치 점유 검사 조건 수정.
- Move 탭 프론트 API 경로 정합성 수정.
- 이동은 검증 엔진을 반드시 타도록 통일.

---

### P1. Picking DB UNIQUE 보강

수정 대상:

- DB 마이그레이션
- `engine_modules/db_migration_mixin.py`

필요 작업:

- 활성 `picking_table` 중복 방지 UNIQUE 인덱스 추가.
- 후보:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_picking_active_tonbag
ON picking_table(tonbag_id)
WHERE status NOT IN ('RETURNED', 'CANCELLED');
```

추가 후보:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_picking_active_lot_sublt
ON picking_table(lot_no, COALESCE(sub_lt, ''))
WHERE status NOT IN ('RETURNED', 'CANCELLED');
```

---

### P2. Allocation LOT 모드 UNIQUE 보강

수정 대상:

- DB 마이그레이션
- `engine_modules/db_migration_mixin.py`

필요 작업:

- `tonbag_id IS NULL`인 LOT 모드 활성 배정 중복 방지 인덱스 추가.

후보:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_alloc_lot_mode_no_dup
ON allocation_plan(lot_no, customer, sale_ref, COALESCE(outbound_date, ''))
WHERE status IN ('RESERVED', 'STAGED', 'PENDING_APPROVAL')
  AND tonbag_id IS NULL;
```

---

### P3. Scan API 경로 통일

수정 대상:

- `backend/api/scan_api.py`
- `backend/api/inventory_api.py`
- `core/barcode_scan_engine.py`
- 프론트 스캔 호출부

필요 작업:

- 직접 UPDATE 방식 스캔 API 제거 또는 내부용 제한.
- 모든 출고 스캔은 `barcode_scan_engine`을 타게 통일.
- `outbound_scan_log` 기반 멱등성 보장.

---

### P4. OneStop 출고 연결 정리

수정 대상:

- `frontend/js/sqm-inline.js`
- `backend/api/outbound_api.py`

필요 작업:

- `onestop-pick`과 `onestop-complete` 프론트 연결 여부 확인.
- 로컬 상태만 바꾸는 흐름 제거.
- 실제 DB 상태 전이는 검증 API를 통해서만 수행.

---

### P5. 반품 자체 중복 방지 확인

수정 대상:

- `engine_modules/inventory_modular/return_mixin.py`
- `features/parsers/return_inbound_engine.py`

필요 작업:

- 같은 `lot_no + sub_lt + 원출고정보` 반복 반품 차단.
- 이미 `RETURN` 또는 `AVAILABLE`인 톤백 재반품 하드스톱 확인.
- `return_history` 중복 이력이 생기지 않도록 방어.

---

### P6. 운영 DB 인덱스 실제 존재 확인

확인 대상:

- `idx_tonbag_uid_unique`
- `idx_tonbag_sample_per_lot`
- `idx_tonbag_lot_sublt`
- `idx_alloc_no_dup`
- `idx_sold_dedup`

필요 작업:

```sql
PRAGMA index_list('inventory_tonbag');
PRAGMA index_list('allocation_plan');
PRAGMA index_list('picking_table');
PRAGMA index_list('sold_table');
```

기존 중복 데이터 때문에 UNIQUE 인덱스 생성이 실패했을 가능성을 반드시 확인해야 한다.

---

## 6. 최종 판단

현재 v866은 중복 방지 로직이 전혀 없는 상태가 아니다.  
입고, Allocation, Outbound 쪽에는 이미 상당한 방어 로직이 있다.

하지만 사용자 원칙인:

```text
반품 외 DB 중복 금지
```

를 프로그램 전체에 일관되게 적용하려면 아직 수정이 필요하다.

최종 우선순위는 아래와 같다.

| 우선순위 | 항목 | 이유 |
|---|---|---|
| P0 | Move 중복/경로 수정 | 이동은 반품 예외가 아니며 현재 조건식 위험 |
| P1 | Picking DB UNIQUE 보강 | 코드 보강만으로는 우회 경로 방어 부족 |
| P2 | Allocation LOT 모드 UNIQUE 보강 | `tonbag_id IS NULL` UNIQUE 한계 |
| P3 | Scan API 통일 | 직접 UPDATE 경로가 남으면 중복 방지 강도 불일치 |
| P4 | OneStop 출고 연결 정리 | 로컬 상태와 DB 상태 전이 불일치 가능 |
| P5 | 반품 자체 중복 처리 방지 | 반품은 예외지만 같은 반품 2회 처리는 금지 |
| P6 | 운영 DB 인덱스 확인 | 코드에 있어도 실제 DB 적용 실패 가능 |

---

## 7. 결론

```text
반품으로 정식 복귀한 경우만 다시 재고 흐름에 들어올 수 있다.
그 외 입고, Allocation, Picked, Outbound, 이동에서는 같은 실물 데이터가 DB에 중복 반영되면 안 된다.
```

이 원칙에 맞추려면, 현재 수정된 입고/Picking/Sales Order 보강에 더해 **Move, Picking DB 제약, Allocation LOT 모드 제약, Scan 경로 통일, 반품 중복 방지**를 추가로 처리해야 한다.

