# SQM v866 DB 중복 금지 수정 계획서

> 작성일: 2026-05-03  
> 대상: `D:\program\SQM_inventory\SQM_v866_CLEAN`  
> 문서 목적: 코드 수정 전 작업 범위, 원칙, 우선순위, 검증 기준을 정리  
> 주의: 이 문서는 **수정 계획서**이며, 실제 코드 변경 내역이 아니다.

---

## 1. 최종 운영 원칙

사용자 기준의 최종 원칙은 아래와 같다.

```text
반품을 제외한 모든 업무 흐름에서 DB 중복은 금지한다.
반품은 예외적으로 재고 흐름 복귀를 허용한다.
단, 같은 반품 건을 두 번 처리하는 것은 금지한다.
```

대상 업무 흐름:

```text
입고 → Allocation → Picked → Outbound → 이동
```

예외 업무 흐름:

```text
반품 → RETURN/AVAILABLE 복귀 → 이후 다시 정상 재고 흐름 진입 가능
```

---

## 2. 중복 금지 기준

### 2.1 입고

금지 기준:

- 같은 `lot_no`가 `inventory`에 두 번 들어가면 안 된다.
- 같은 `lot_no + sub_lt`가 `inventory_tonbag`에 두 번 들어가면 안 된다.
- 같은 `tonbag_uid`가 두 톤백에 중복되면 안 된다.

현재 상태:

- `inventory.lot_no`는 DB UNIQUE.
- `inventory_tonbag(lot_no, sub_lt)`는 DB UNIQUE.
- OneStop 입고는 파일 내부 중복 LOT와 기존 DB LOT를 차단하도록 보강되어 있음.

작업 필요:

- 운영 DB에 실제 UNIQUE 인덱스가 존재하는지 확인.
- Tk/레거시 입고 경로도 동일 엔진 경로를 타는지 확인.

---

### 2.2 Allocation

금지 기준:

- 활성 상태의 동일 LOT/고객/SALE REF 배정 중복 금지.
- 같은 LOT 모드 배정이 `tonbag_id IS NULL` 상태로 반복 생성되면 안 된다.
- 같은 Allocation 파일을 반복 업로드해 같은 배정이 DB에 중복 생성되면 안 된다.

현재 상태:

- 엔진 코드에서 중복 검사 존재.
- `allocation_plan` 활성 중복 방지 인덱스 존재.
- 단, `tonbag_id IS NULL`인 LOT 모드에서는 DB UNIQUE가 완전하지 않을 수 있음.

작업 필요:

- LOT 모드 전용 DB UNIQUE 인덱스 추가 계획.
- `duplicate_file` 감지 결과를 API 응답에 명확히 노출.
- 동일 Allocation 파일 재업로드 정책 결정:
  - 기본 차단
  - 또는 관리자 확인 후 진행

권장:

```text
기본은 차단.
필요 시 기존 배정 취소 후 재업로드.
```

---

### 2.3 Picked

금지 기준:

- 같은 `Picking No` 재업로드 금지.
- 같은 톤백이 활성 상태의 `picking_table`에 두 번 들어가면 안 된다.
- 같은 `lot_no + sub_lt`가 반품/취소 없이 두 Picking에 포함되면 안 된다.

현재 상태:

- 웹 Picking 업로드 경로에는 중복 차단 보강됨.
- 그러나 DB 레벨 활성 UNIQUE 제약은 아직 약함.

작업 필요:

- `picking_table` 활성 중복 방지 DB 인덱스 추가.
- 후보 1: `tonbag_id` 기준 활성 중복 차단.
- 후보 2: `lot_no + sub_lt` 기준 활성 중복 차단.
- 기존 운영 DB에 중복 행이 있으면 먼저 정리 필요.

---

### 2.4 Outbound / Sales Order

금지 기준:

- 같은 Sales Order No가 반품/해결 없이 다시 처리되면 안 된다.
- 같은 `picking_id`가 두 번 SOLD/OUTBOUND 처리되면 안 된다.
- 같은 `tonbag_id`가 두 번 SOLD/OUTBOUND 처리되면 안 된다.
- 같은 톤백이 OUTBOUND/SOLD 상태인데 다시 출고되면 안 된다.

현재 상태:

- Sales Order 엔진에서 중복 차단 보강됨.
- `sold_table` 중복 방지 인덱스 생성 로직 존재.
- 스캔 출고 일부 경로는 직접 UPDATE 방식이 있어 엔진 멱등 로직을 우회할 수 있음.

작업 필요:

- 운영 DB에 `idx_sold_dedup` 실제 존재 확인.
- 스캔 출고 경로 통일.
- 직접 UPDATE 방식 출고 API 제거 또는 엔진 위임.

---

### 2.5 이동

금지 기준:

- 이동은 반품 예외가 아니다.
- 같은 톤백을 같은 위치로 다시 이동하면 안 된다.
- 같은 위치에 두 개의 활성 톤백이 동시에 존재하면 안 된다.
- 이동 금지 상태의 톤백은 이동하면 안 된다.

현재 상태:

- 엔진 `update_tonbag_location`에는 상태 제한, 동일 위치 차단, capacity 검사 있음.
- 하지만 위치 점유 검사 조건이 자기 자신 제외 방식으로 부정확할 수 있음.
- Move 프론트가 실제 백엔드 API 계약과 맞지 않는 경로/필드를 호출하는 위험이 있음.
- 일부 scan move API는 엔진 검증을 우회해 직접 UPDATE함.

작업 필요:

- 위치 점유 조건 수정.
- Move 프론트 호출을 검증된 백엔드 경로로 정합화.
- scan move API도 엔진 `update_tonbag_location`으로 위임.
- LOT 전체 일괄 이동 API와 톤백 단건 이동 API를 명확히 분리.

---

### 2.6 반품

허용 기준:

- 반품은 예외적으로 재고 흐름 복귀를 허용한다.
- OUTBOUND/SOLD/PICKED 상태의 톤백이 RETURN 또는 AVAILABLE로 돌아오는 것은 정상이다.
- 반품 후 다시 Allocation/Picked/Outbound 흐름에 들어갈 수 있다.

금지 기준:

- 같은 반품 건을 두 번 처리하면 안 된다.
- 이미 `RETURN` 또는 `AVAILABLE`인 톤백을 다시 반품 처리하면 안 된다.
- 같은 `lot_no + sub_lt + 원출고정보`가 반복 반품 이력으로 생성되면 안 된다.

현재 상태:

- 반품 로직은 `picking_table`, `sold_table`, `allocation_plan`을 정리하는 구조가 있음.
- 이미 AVAILABLE인 경우 차단 로직이 있음.
- 반품 이력 중복 차단은 추가 확인 필요.

작업 필요:

- 반품 처리 전 기존 반품 이력 확인.
- 같은 원출고 기준 중복 반품 차단.
- `return_history`와 `return_log` 통합 조회 시 중복 집계 여부 확인.

---

## 3. 수정 대상 목록

### 3.1 DB 마이그레이션

대상 파일:

- `engine_modules/db_migration_mixin.py`

작업:

- `picking_table` 활성 중복 방지 UNIQUE 인덱스 추가.
- `allocation_plan` LOT 모드 활성 중복 방지 UNIQUE 인덱스 추가.
- 필요 시 `return_history` 또는 `return_log` 중복 방지 인덱스 검토.
- 운영 DB에 기존 중복 데이터가 있으면 인덱스 생성 전 정리 절차 필요.

검증:

```sql
PRAGMA index_list('inventory_tonbag');
PRAGMA index_list('allocation_plan');
PRAGMA index_list('picking_table');
PRAGMA index_list('sold_table');
PRAGMA index_list('return_history');
```

---

### 3.2 Move 수정

대상 파일 후보:

- `engine_modules/inventory_modular/tonbag_mixin.py`
- `backend/api/actions2.py`
- `backend/api/scan_api.py`
- `backend/api/tonbag_api.py`
- `frontend/js/sqm-inline.js`

작업:

- 위치 점유 조건 수정.
- 직접 UPDATE 이동 경로 제거 또는 엔진 위임.
- Move 화면의 API 경로와 payload 정합화.
- 단건 톤백 이동과 LOT 일괄 이동을 분리.

검증 시나리오:

- 같은 위치로 이동 시 차단.
- 다른 톤백이 점유 중인 위치로 이동 시 차단.
- PICKED/OUTBOUND/SOLD 톤백 이동 시 차단.
- 정상 AVAILABLE/RESERVED 톤백 이동 시 성공.

---

### 3.3 Scan 경로 통일

대상 파일 후보:

- `backend/api/scan_api.py`
- `backend/api/inventory_api.py`
- `core/barcode_scan_engine.py`
- `frontend/js/sqm-inline.js`
- `frontend/js/pages/scan.js`

작업:

- 출고 확정 스캔은 `barcode_scan_engine`으로 통일.
- 직접 `inventory_tonbag` 상태를 UPDATE하는 경로 제거 또는 내부용 제한.
- `outbound_scan_log` 기반 중복 확정 방지 사용.

검증 시나리오:

- 같은 UID 2회 스캔 시 두 번째는 차단.
- OUTBOUND/SOLD 상태 UID 스캔 시 차단.
- PICKED 상태 정상 UID 스캔 시 1회만 OUTBOUND 처리.

---

### 3.4 OneStop 출고 정리

대상 파일 후보:

- `frontend/js/sqm-inline.js`
- `backend/api/outbound_api.py`

작업:

- `onestop-pick` 프론트 연결 확인.
- `onestop-complete` 프론트 연결 확인.
- 로컬 상태만 바꾸는 흐름 제거.
- 실제 DB 상태 전이는 검증 API를 통해서만 수행.

검증 시나리오:

- DRAFT → WAIT_SCAN 시 DB 상태가 실제 PICKED 또는 정책상 예약 상태로 일관되게 변경.
- FINALIZED → OUTBOUND 시 DB에 중복 SOLD/OUTBOUND 행 생성 금지.
- 같은 마법사 완료 버튼 재실행 시 차단.

---

### 3.5 반품 중복 방지

대상 파일 후보:

- `engine_modules/inventory_modular/return_mixin.py`
- `features/parsers/return_inbound_engine.py`
- `engine_modules/return_reinbound_engine.py`

작업:

- 반품 처리 전 동일 반품 이력 존재 여부 확인.
- 이미 RETURN/AVAILABLE 상태인 톤백 재반품 차단.
- `return_history`와 `return_log` 중복 집계 방지.

검증 시나리오:

- OUTBOUND 톤백 반품 1회 성공.
- 같은 톤백 반품 2회차 차단.
- 반품 후 AVAILABLE 복귀 성공.
- 복귀 후 정상 Allocation/Picked/Outbound 재진입 가능.

---

## 4. 작업 순서 제안

전체 적용 순서는 아래가 적합하다.

1. 운영 DB 현재 중복/인덱스 상태 점검
2. DB 마이그레이션 설계 및 인덱스 추가
3. Move 중복 방지 및 API 정합성 수정
4. Scan 출고 경로 통일
5. OneStop 출고 경로 연결 정리
6. 반품 자체 중복 방지 추가
7. 프론트 오류 표시 및 중복 차단 메시지 정리
8. 회귀 테스트

---

## 5. 회귀 테스트 체크리스트

### 입고

- 같은 LOT 두 번 입고 시 차단.
- 같은 파일 안에 같은 LOT 두 줄이면 저장 전 차단.
- 정상 신규 LOT는 저장.

### Allocation

- 같은 Allocation 파일 재업로드 시 차단.
- 같은 LOT/고객/SALE REF 활성 중복 차단.
- 반품 복귀 후 새 배정은 정책상 허용.

### Picked

- 같은 Picking No 재업로드 차단.
- 같은 톤백이 활성 Picking에 두 번 들어가는지 차단.

### Outbound

- 같은 SO No 재업로드 차단.
- 같은 Picking/Same Tonbag SOLD 중복 차단.
- 같은 UID 두 번 스캔 차단.

### Move

- 같은 위치 이동 차단.
- 점유 위치 이동 차단.
- 이동 금지 상태 차단.
- 정상 이동 성공.

### Return

- 정상 반품 성공.
- 같은 반품 2회 처리 차단.
- 반품 후 AVAILABLE 복귀 성공.
- 복귀 후 재출고 흐름 정상.

---

## 6. 작업 전 확인 필요 사항

코드 수정 전 아래를 먼저 확인해야 한다.

1. 현재 운영 DB에 이미 중복 데이터가 있는지
2. UNIQUE 인덱스가 실제 생성되어 있는지
3. Tk GUI를 계속 사용할지, 웹만 기준으로 할지
4. 문서 테이블 `document_*`는 이력 보존인지 최신 1건 정책인지
5. 반품 후 재출고 가능 조건을 상태 기준으로 어떻게 둘지

---

## 7. 최종 결론

이 작업은 단순한 중복 제거가 아니라, 프로그램 전체의 DB 상태 전이 원칙을 맞추는 작업이다.

핵심은 아래 한 줄이다.

```text
반품으로 정식 복귀한 경우만 다시 재고 흐름에 들어올 수 있고,
그 외 모든 흐름에서는 같은 실물 데이터가 DB에 중복 반영되면 안 된다.
```

따라서 실제 수정은 DB 제약, 백엔드 엔진, API 경로, 프론트 호출, 반품 예외 처리까지 함께 진행해야 한다.

