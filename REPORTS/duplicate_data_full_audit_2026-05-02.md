# SQM 전 프로그램 — 데이터 중복·멱등성 전수 감사 보고서

> **작성일:** 2026-05-02  
> **범위:** `SQM_v866_CLEAN` — 스키마·마이그레이션·엔진(`engine_modules`)·백엔드(`backend/api`)·프론트(`frontend/js`)·스캔 코어(`core`)·GUI(`gui_app_modular`)를 아우르는 **중복 가능성** 및 **권장 조치** 정리.  
> **주의:** 모든 소스를 한 줄씩 읽은 엄밀한 정적 분석이 아니라, 저장소 전반에 대한 **체계적 코드·스키마 추적**에 기반한다.

---

## 1. 용어 정의

| 구분 | 의미 | 예 |
|------|------|-----|
| **불허 중복 (버그 성)** | 동일 비즈니스 키로 마스터·상태가 이중 반영되는 것 | 동일 LOT 행 2개, 동일 톤백 이중 SOLD |
| **허용 다행 (정상)** | 이벤트·이력·감사·문서 스냅샷 — 여러 행이 설계상 맞음 | `stock_movement` 다행, 재파싱 `document_*` 다행 |
| **경고만** | 비즈니스는 진행, 운영자 확인 권고 | SAP가 다른 LOT와 겹침 [IB-09] |

---

## 2. DB 스키마·마이그레이션 — 물리적 중복 방지

### 2.1 핵심 마스터

| 대상 | 제약 / 인덱스 | 효과 |
|------|----------------|------|
| `inventory.lot_no` | `UNIQUE NOT NULL` | **동일 LOT 마스터 2행 불가** |
| `inventory_tonbag` | `UNIQUE(lot_no, sub_lt)` | **같은 LOT·같은 sub_lt 2행 불가** |
| `shipment.sap_no` | `UNIQUE` | **선적(shipment) 테이블** SAP 1행 — `inventory.sap_no`와 **별개** |
| `inventory_snapshot` | `UNIQUE(snapshot_date)` | 일자당 1스냅샷 |
| `move_batch.batch_id` | `PRIMARY KEY` | 배치 ID 유일 |
| `carrier_profile.carrier_id` | `PRIMARY KEY` (앱 기동 마이그레이션) | 선사 프로필 1행/ID |

### 2.2 마이그레이션으로 추가된 UNIQUE (적용 DB 기준)

| 이름 | 대상 | 비고 |
|------|------|------|
| `idx_tonbag_uid_unique` | `inventory_tonbag(tonbag_uid)` | UID 전역 유일(채워진 행) |
| `idx_tonbag_sample_per_lot` | Partial — 샘플 톤백 LOT당 1 | `is_sample=1` |
| `idx_tonbag_bl_lot_no` | `(bl_no, lot_no, tonbag_no)` | v5.2.0 — **기존 중복 있으면 인덱스 생성 실패 가능** |
| `ux_alloc_line` | `allocation_plan(import_batch_id, line_no)` | 동일 배치·동일 라인 이중 불가 |
| `idx_alloc_no_dup` | Partial — `status IN ('RESERVED','STAGED')` 시 `(lot_no, customer, sale_ref, tonbag_id)` | 활성 예약 중복 방지 |
| `idx_sold_dedup` | `sold_table(sales_order_no, lot_no, COALESCE(sub_lt,''))` | SO 재업로드 등 **중복 SOLD 행** DB 차단(인덱스 생성 성공 시) |

### 2.3 트리거·보조

- **`inventory.current_weight` 음수 방지** — BEFORE UPDATE 트리거 (v8.7.1 마이그레이션 개념).

### 2.4 UNIQUE가 없거나 약한 테이블 (다행·버전 허용)

- `document_invoice`, `document_bl`, `document_pl`, `document_do` — LOT당 **복수 행 가능**(재파싱·재업로드).
- `stock_movement`, `audit_log`, `parsing_log`, `tonbag_move_log` 등 — **이력 성격**, 동일 유형 **다행 가능**.
- `picking_table` — 기본 CREATE만 보면 **강한 비즈니스 UNIQUE 없음**; `sold_table`은 dedup 인덱스로 **일부 키** 보강.
- `outbound` / `outbound_item` — 출고 **건·라인** 다중이 일반적.
- `return_history` / `return_log` — **반품·이력** 다행이 자연스러움.

### 2.5 `carrier_rules` 이중 정의 이슈

- `backend/api/__init__.py`의 `CREATE TABLE carrier_rules`와 `backend/api/settings.py`의 정의가 **UNIQUE·CHECK 등이 다를 수 있음**.
- 실제 DB가 **어느 경로로 최초 생성**됐는지에 따라 **규칙 중복 허용 여부**가 달라질 수 있음 — **감사·정리 권장**.

---

## 3. 엔진(`engine_modules`) — 비즈니스 중복 방지

### 3.1 입고

- `process_inbound`: `_check_lot_exists` — 기존 LOT면 **입고 중단**.
- DB: `inventory.lot_no` UNIQUE — **최종 방어**.
- SAP: **다른 LOT와 동일 SAP 가능** — [IB-09] **경고**, 전역 DB UNIQUE 아님.
- B/L 공란 등 — 하드스톱(정책).

### 3.2 Allocation 예약 (`reserve_from_allocation` 등)

- **G5** 등: 기존 RESERVED + 이번 배치가 MXBG 총량 초과 시 **배치 전체 하드스톱**.
- **source_fingerprint**: 이미 RESERVED에 동일 지문이 있으면 `duplicate_file` **플래그** — **API 응답에 항상 노출되지는 않을 수 있음**; **차단이 아닌 감지**에 가깝다.
- **Partial UNIQUE** — 활성 예약 조합 이중 방지.
- **import_batch + line** UNIQUE.

### 3.3 출고 실행 `process_outbound`

- **All-or-Nothing** 트랜잭션(개념) — 가용 부족 시 실패.
- 연속 호출: **이미 PICKED/상태 반영** 후이면 **재처리 어려움**.

### 3.4 출고 확정 `confirm_outbound`

- `_co_guard_against_double_outbound`: `sold_table`에 **tonbag_id 이미 있으면** 확정 **전체 차단**.
- `_co_insert_sold_row` + DB **`idx_sold_dedup`**(적용 시) — 키 조합 중복 INSERT 방지.
- **가드 쿼리**는 `sold_table` **상태 필터 없이** tonbag_id 존재만 볼 수 있어, **RETURNED 등 레거시 행**이 남으면 **오탐·차단** 이론상 가능.

### 3.5 `quick_outbound`

- 트랜잭션 내 AVAILABLE `LIMIT count` — **같은 톤백 이중 PICKED**는 통상 어려움.
- `allocation_plan`에 `EXECUTED` INSERT — Partial UNIQUE는 **RESERVED/STAGED**에만 적용.

### 3.6 `quick-paste` (API가 엔진을 **행마다** 호출)

- **행별 독립** — 전체 단일 트랜잭션 아님.
- **같은 붙여넣기에 동일 LOT 두 줄** — **연속 두 번 quick**과 유사 → **의도치 않은 이중 처리** 가능.

### 3.7 이동·배치(엔진 메서드)

- `submit_batch_move` / `approve_batch_move` / `reject_batch_move` — **move_batch** 워크플로.
- 톤백 위치: `update_tonbag_location` 등(Excel API에서 반복 호출).

---

## 4. 스캔·바코드 (`core/barcode_scan_engine.py`)

- **`_is_uid_already_confirmed`**: `outbound_scan_log`에 동일 UID·`undone=0`이면 **`DUPLICATE_CONFIRMED`** 로 재확정 차단.
- 배치 입력 내 **동일 UID 중복** — 목록으로 집계·경고.
- **Gate1·목표 중량** 등 추가 검증 있음.

---

## 5. FastAPI — 경로별 특성·불일치 (중복·안전성 강도)

### 5.1 동일 `/api/scan` 라우터 이중 등록

- `inventory_api.scan_router`와 `scan_api.router` — **경로가 겹치면 FastAPI 등록 순서**에 따라 한쪽이 우선. **동작 일관성 확인 권장**.

### 5.2 `POST /api/scan/process` (`inventory_api`)

- `action=outbound` 등 — **단순 SQL** 수준, **`sub_lt`만** 쓰는 분기 등 — **엔진 스캔 확정과 안전장치 불일치**.

### 5.3 `POST /api/scan/confirm_outbound` (`scan_api`)

- PICKED → SOLD **직접 UPDATE**.
- **`barcode_scan_engine`·`outbound_scan_log` 멱등 없음**.

### 5.4 원스톱 백엔드 (`outbound_api`)

| 엔드포인트 | 요약 |
|------------|------|
| `onestop-pick` | AVAILABLE → PICKED 직접 UPDATE |
| `onestop-complete` | PICKED → OUTBOUND, audit — **`confirm_outbound`와 다른 트랙** |
| `onestop-scan-parse` | 스캔 파일 파싱 |

### 5.5 Allocation API

- `bulk-import-excel` → `engine.reserve_from_allocation`.
- 응답에 **`duplicate_file` 명시 필드가 항상 포함된다고 보장하기 어렵음** — 엔진 `warnings` 등에 섞일 수 있음.

### 5.6 톤백 API (`tonbag_api`)

- `location-upload` → **`engine.update_tonbag_location`** 행별.
- `batch-move/submit|pending|approve|reject` → **`submit_batch_move` 등**.

### 5.7 위치 이동 `inventory-move`

- 구현: **`backend/api/actions2.py`** → **`POST /api/action2/inventory-move`** (prefix `/api/action2`).
- 페이로드 설계: **`lot_no` + `to_loc`/`destination`**, **LOT 단위 톤백 일괄** 갱신 + `stock_movement` MOVE.

---

## 6. 프론트(`frontend/js/sqm-inline.js`) — 호출·UX

### 6.1 즉시 출고 F015

- `GET /api/outbound/quick/info`, `POST /api/outbound/quick`.
- 성공 후 **제출 버튼 비활성 유지** — 연속 이중 제출 **완화**.

### 6.2 quick-paste F016

- `POST /api/outbound/quick-paste`.
- 완료 후 **submit 다시 활성** — **동일 데이터 재실행 가능**.

### 6.3 출고 확정 F028

- `GET /api/outbound/picked-summary`, `POST /api/outbound/confirm` → 엔진 **`confirm_outbound`**.

### 6.4 대량 이동 승인

- `showBatchMoveApprovalModal`: `GET .../batch-move/pending`, `POST .../approve|reject/{batch_id}` — **정상 매칭**.

### 6.5 Move 탭 (`loadMovePage`)

| 요소 | 상태 |
|------|------|
| 이력 | `GET /api/q/movement-history` |
| Lookup | `GET /api/tonbags?sub_lt=` |
| **executeMove** | `POST /api/action/inventory-move` + `{ barcode, destination }` |
| Location Upload 버튼 | **토스트만** (“준비 중”) — **`showTonbagLocationUploadModal` 미연결** |
| Move Approval 버튼 | **토스트만** (“준비 중”) — **`showBatchMoveApprovalModal`은 메뉴 `onBatchMoveApproval`로만 연결** |

**잠재 불일치 (감사 결론):**

- 백엔드 실제 경로는 **`/api/action2/inventory-move`** 이고, 바디는 **`lot_no` 기대**.
- 프론트는 **`/api/action/inventory-move`** + **`barcode`** — **경로·필드·의도(톤백 UID vs LOT 일괄)** 가 엔드포인트 설계와 **정합하지 않을 가능성**이 큼.

### 6.6 OneStop 출고 마법사

- 호출: **`POST /api/outbound/onestop-scan-parse`** (스캔 파일).
- **`ooMoveToScan`**: 로컬 상태만 — **DB `onestop-pick` 미호출**.
- **`ooFinalize`**: 플레이스홀더 — **`onestop-complete` 미연결**.
- 코드베이스 문자열 검색상 **`onestop-pick` / `onestop-complete` 프론트 호출 없음**.

### 6.7 HTTP 멱등 키

- **Idempotency-Key** 등 **표준 이중 제출 방지 헤더 없음**.

---

## 7. 설정·DB 도구 (별도 세션에서 다룬 내용 요약)

- **DB 이력 정리** (`cleanup-logs`): `audit_log`·`stock_movement` 일부 삭제 — **사이드바 Log 조회와 별개**.
- **테스트 DB 초기화**: 트랜잭션/VACUUM/타임아웃 등 **구현 보강이 논의됨** — 운영 DB에 사용 금지 정책 유지.

*(본 보고서는 중복 데이터 정책이 핵심이므로 상세 패치 내역은 코드 변경 이력을 참고.)*

---

## 8. 구 DB·마이그레이션 미적용 리스크

- UNIQUE 인덱스 **`CREATE IF NOT EXISTS`** 실패 시(기존 중복 행) — **주석대로 “중복 방지”가 DB에 없을 수 있음**.
- 앱 업그레이드 순서에 따라 **제약이 빠진 상태**로 운영된 적이 있으면 **데이터 정리 후 인덱스 재생성** 검토.

---

## 9. Tkinter(`gui_app_modular`) vs 웹

- 동일 기능이 **데스크톱·웹**에서 **다른 코드 경로**로 구현된 부분 존재.
- 예: `scan_tab` 등 **INSERT OR IGNORE sold_table** 등 — **웹과 동작 차이** 가능.

---

## 10. 권장 반영 사항 (우선순위 제안)

아래는 **코드 변경을 요구하는 목록이 아니라**, 중복 감사 결과를 바탕으로 한 **프로그램 반영 후보**이다. 실제 적용 시 별도 설계·테스트 필요.

### P0 — 정합성·안전

1. **Move 탭 `executeMove`**: 호출 URL을 **`/api/action2/inventory-move`** 와 맞추고, 페이로드를 **`lot_no`(또는 UID→LOT 조회 후)** + `destination` 으로 **API 계약과 일치**시키거나, **톤백 단건 이동 전용 API**를 명확히 분리.
2. **`/api/action` vs `/api/action2`**: 프론트·문서·`feature_matrix` 전수 대조 — **404·오동작** 방지.
3. **스캔 출고 단일 정책**: `scan_api` 단축 경로를 **엔진/`outbound_scan_log`와 통합**할지, **폐기·내부용 한정**할지 결정.

### P1 — 원스톱

4. **OneStop 웹 마법사**: Tab 전환 시 **`onestop-pick` / `onestop-complete`** (또는 **`confirm_outbound`**) 와 **명시적 연결** — 현재 **백엔드만 존재·UI 미연결** 구간 해소.
5. **`ooFinalize`**: 실제 확정 플로우 구현 또는 **비활성·안내 문구** 고정.

### P2 — Allocation·응답

6. **`duplicate_file`**: `bulk-import-excel` JSON에 **`duplicate_file`, `duplicate_source_fingerprint` 명시** — 운영자가 동일 파일 재업로드를 인지.
7. **`_ra_check_duplicate_file`**: 플래그만이 아니라 **정책적 차단/확인 다이얼로그** 여부를 제품 요구사항으로 확정.

### P3 — 중복 방어 보강

8. **`confirm_outbound` 가드**: `sold_table` 조회 시 **상태 필터**(필요 시) — 레거시 행으로 인한 **오탐** 검토.
9. **`quick-paste`**: 동일 LOT가 rows에 **중복**일 때 **경고·합산·거부** 옵션.

### P4 — 스키마·운영

10. **`carrier_rules`**: 단일 스키마 소스 — **`__init__.py` vs `settings.py`** 통합.
11. **운영 DB**: `PRAGMA index_list` 등으로 **dedup 인덱스 존재 여부** 확인.

### P5 — 문서·교육

12. 본 보고서를 **운영 매뉴얼 부록**으로 두고, **“로그 테이블 다행은 정상”**과 **“마스터 중복은 DB가 막음”**을 구분해 교육.

---

## 11. 검증 체크리스트 (운영·릴리스 전)

- [ ] 신규 DB에 마이그레이션 전체 적용 후 **`idx_alloc_no_dup`, `idx_sold_dedup`, `idx_tonbag_uid_unique`** 존재 여부  
- [ ] 웹에서 실사용하는 출고 경로만 나열해 **`confirm_outbound` vs 직접 UPDATE** 여부 확인  
- [ ] Move·스캔·원스톱 **E2E 시나리오** 각 1회씩 (이중 클릭·재호출 포함)  
- [ ] `carrier_rules` 실테이블 스키마 **`settings.py`와 일치 여부**

---

## 12. 종합 한 줄

**재고 마스터(LOT·톤백 슬롯·UID·일부 예약/판매 키)** 는 DB와 엔진으로 **강하게 보호**되나, **이력·문서·로그**는 **다행이 정상**인 부분이 많고, **HTTP/API·웹 미완·단축 스캔 경로·Move 탭 불일치** 때문에 **경로마다 “중복 방지 강도”가 달라질 수 있는 구간**이 남아 있다. 위 **권장 반영**으로 **사용자 체감 오류·이중 반영 리스크**를 줄일 수 있다.

---

*본 문서는 대화 기반 전수 감사 내용을 통합한 것이며, 구현 변경 시 반드시 회귀 테스트와 사장님 승인 범위를 따른다.*
