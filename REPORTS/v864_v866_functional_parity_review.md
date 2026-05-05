# v864.2 vs SQM_v866_CLEAN 기능 대응 검토 리포트

| 항목 | 내용 |
|------|------|
| **문서 버전** | 1.1 |
| **작성일** | 2026-05-01 |
| **검토 기준** | **기능(동작) 동일 여부** — UI 메뉴 위치·라벨 일치는 필수 아님 |
| **비교 원본** | `D:\program\SQM_inventory\Claude_SQM_v864_20260329_FULL` (Tkinter v864 계열) |
| **비교 대상** | `D:\program\SQM_inventory\SQM_v866_CLEAN` (PyWebView + FastAPI) |

---

## 1. 검토에 사용한 근거 파일

### 1.1 원본(v864) — 메뉴·기능 단일 정의

| 파일 | 용도 |
|------|------|
| `gui_app_modular/menu_registry.py` | `FILE_MENU_INBOUND_ITEMS`, `FILE_MENU_OUTBOUND_ITEMS`, `MENU_STOCK_ITEMS`, `MENU_REPORT_ITEMS`, `MENU_SETTINGS_ITEMS`, `MENU_HELP_ITEMS`, 백업·내보내기·AI 도구 등 |
| `gui_app_modular/mixins/custom_menubar.py` | 탑레벨 메뉴 순서(📤 출고 → 📁 파일 → …), 파일 내 🔧 도구 서브(문서 변환 등), 🔧 도구 메뉴 전체, 👁️ View, 📦 품목 등 |

### 1.2 대상(v866_clean) — UI·라우팅

| 파일 | 용도 |
|------|------|
| `frontend/index.html` | 탑 메뉴(파일·입고·출고·재고·보고서·**검색**·설정/도구·도움말), 툴바, 사이드바 9탭, `data-action` 목록 |
| `frontend/js/handlers/menubar.js` | `MENUBAR_MAP`, 각 항목의 `POST /api/menu/...` 경로 |
| `frontend/js/api-client.js` | `apiCall`, 404/501 처리 |
| `backend/api/__init__.py` | 라우터 등록; **구 `/api/menu/*` 일괄 스텁 제거** 주석 |
| `backend/api/actions.py`, `queries.py`, `info.py`, `inbound.py`, `outbound_api.py`, `allocation_api.py`, `tonbag_api.py`, `dashboard.py`, `optional.py` 등 | 기능별 실제 HTTP 엔드포인트 |
| `docs/handoff/feature_matrix.json` | F001~ 기능 ID와 Tk 콜백·제안 API 매핑 (85개 스키마) |
| `docs/handoff/v864_2_structure.json` | 사이드바 탭·툴바·메뉴 개념 구조 (핸드오프 스냅샷) |

---

## 2. 검토 방법(메서드)

1. **정적 분석**: 원본은 `menu_registry`의 `(라벨, app 메서드명)`과 대상은 `data-action`·`MENUBAR_MAP`·백엔드 `include_router`를 대조.
2. **기능 단위 판정**: 메뉴 깊이·탭 위치가 달라도, **같은 업무(같은 Tk 메서드·같은 엔진 경로)에 연결되면 동등**으로 볼 수 있음(사용자 기준 반영).
3. **한계**: 실제 클릭·DB 반영까지의 **E2E 검증은 본 리포트에 포함하지 않음**. 정적 분석상 “엔드포인트 없음·404·구 스텁 경로”인 경우 **기능 미연결 가능성**으로 표시.

---

## 3. 표기 규칙

| 기호 | 의미 |
|------|------|
| **○** | v864.2에 해당 기능이 있고, v866에서 **동일 목적의 API·탭·스크립트 경로가 존재**하거나, 분산 라우터로 **대체 연결된 것으로 보이는 경우** |
| **X** | v864.2에 있는 기능인데, v866에서 **해당 HTTP 경로 부재·menubar만 `/api/menu/*` 가리킴·엔진 미호출** 등으로 **동작 불가·미구현 가능성이 높은 경우** |
| **△** | v866에만 있거나, 핸드오프/신규 UI로 **원본 대비 추가된 항목** |

※ 본 표는 **코드·라우터 목록 기준**이며, 최종 ○는 **사용자 업무 테스트**로 확정하는 것이 안전함.

---

## 4. 아키텍처 차이(전체에 영향)

### 4.1 메뉴 백엔드 통합 스텁 제거

`backend/api/__init__.py` 주석 요지:

- 과거 `backend.api.menubar`(대량 NotReady/스텁) **제거됨**
- 실제 동작은 **`/api/inbound`, `/api/outbound`, `/api/allocation`, `/api/action*`, `/api/queries*`** 등으로 **분산**

### 4.2 `menubar.js`와의 불일치 위험

`frontend/js/handlers/menubar.js`의 `MENUBAR_MAP`은 여전히 **`POST /api/menu/-on-pdf-inbound`** 형태를 가리킴.

- 백엔드에 **`/api/menu/` 라우터가 없으면** 해당 경로로 호출 시 **404**
- `api-client.js`는 **404/501 시 즉시 실패**(재시도 안 함)

**결론:** 실제 메인창은 **`sqm-inline.js`의 `bindAll` → `dispatchAction` → `ENDPOINTS`** 가 표준 경로이며, `menubar.js`의 `/api/menu/*` 는 **별도로 import·바인딩되지 않으면 메뉴 클릭에 사용되지 않음**. 레거시 `MENUBAR_MAP`만 두고 쓰면 404 위험은 여전하므로, **메뉴 액션은 `sqm-inline` 기준으로 검증**하는 것이 맞음 → 기능별 **실측 권장**.

---

## 5. 원본(v864) 메뉴 구조 요약 (기능 출처)

### 5.1 탑레벨 순서 (`custom_menubar._create_menus`)

1. **📤 출고** — `FILE_MENU_OUTBOUND_ITEMS`
2. **📁 파일** — 입고(`FILE_MENU_INBOUND_ITEMS`), 내보내기, 백업, 파일 내 🔧도구(문서변환 OCR 등), 최근 파일, 종료
3. **📝 보고서** — `MENU_REPORT_ITEMS`
4. **🔧 도구** — 제품 마스터, D/O 후속 연결, PDF/이미지 변환 서브, 문서변환 OCR, PDF 보고서 서브, 정합성, Gemini 서브, DB 보호(조건부), DB 검사/최적화, 로그, 고급(조건부) 등
5. **👁️ View** — 탭 이동·테마
6. **❓ 도움말** — `MENU_HELP_ITEMS`
7. **📦 품목** — 품목별 재고 요약 / LOT 조회 / 입출고 현황

### 5.2 입고 서브 (`FILE_MENU_INBOUND_ITEMS` — 순서 유지)

| 순번 | 라벨 | Tk 메서드 | 비고 |
|------|------|-----------|------|
| 1 | PDF 스캔 입고 | `_on_pdf_inbound` | |
| 2 | 엑셀 파일 수동 입고 | `_bulk_import_inventory_simple` | |
| — | 구분선 | | |
| 3 | D/O 후속 연결 | `_on_do_update` | |
| 4 | 톤백 위치 매핑 | `_on_tonbag_location_upload` | optional |
| 5 | 대량 이동 승인 | `_on_move_approval_queue` | optional |
| — | 구분선 | | |
| 6 | 반품(재입고) | `_show_return_dialog` | 하위 모드 2종 |
| 7 | 반품 입고(Excel) | `_on_return_inbound_upload` | |
| 8 | 반품 사유 통계 | `_show_return_statistics` | |
| — | 구분선 | | |
| 9 | 입고 현황 조회 | `_bulk_import_inventory` | optional |
| — | 구분선 | | |
| 10 | 입고 파싱 템플릿 관리 | `_on_inbound_template_manage` | |
| 11 | 제품 마스터 관리 | `_show_product_master` | |
| 12 | 이메일 설정 | `_show_email_config` | |
| — | 구분선 | | |
| 13 | 정합성 검증(시각화) | `_on_integrity_report_v760` | |
| 14 | LOT 상태 정합성 복구 | `_on_fix_lot_status_integrity` | |

### 5.3 D/O 후속 연결(원본)과 톤백 위치 매핑

| 기능 | 원본 핸들러 | 비고 |
|------|-------------|------|
| D/O 후속 연결 | **`_on_do_update`** | 입고 메뉴 항목 + **🔧 도구** 메뉴에도 동일 명칭으로 중복 배치 (`MENU_SETTINGS_ITEMS`) |
| 톤백 위치 매핑 | **`_on_tonbag_location_upload`** | optional — 앱에 메서드 있을 때만 표시 |

v866 `index.html`에서는 입고 쪽 **「📋 D/O」** 하위에 `onDoUpload`, `onDoUpdate`(라벨: D/O PDF 업로드 / D/O 수동 수정) 등으로 **쪼개져** 있으며, **단일「D/O 후속 연결」과 1:1 라벨 대응은 아님**. 기능이 `_on_do_update`와 **완전 동일한지**는 **실행 경로(sqm-inline vs menubar)** 확인 필요.

### 5.4 툴바 (`v864_2_structure.json` / `toolbar_mixin` 개념)

원본 툴바 핵심: PDF 입고, 즉시 출고, 반품, 재고 조회, 정합성, 백업, 설정 등.

v866 `index.html`은 `tb-pdf-inbound`, `tb-quick-outbound`, `tb-return`, `tb-inventory`, `tb-integrity`, `tb-backup`, `tb-settings` 등 **대응 버튼 존재** — UI 위치는 동일하지 않아도 됨(사용자 기준).

---

## 6. 대상(v866_clean) UI·액션 요약

### 6.1 사이드바 9탭

`index.html` — `data-route`: inventory, allocation, picked, outbound, return, move, dashboard, log, scan.

핸드오프 `v864_2_structure.json`의 `sidebar_tabs`와 **이름·순서 대응**됨.

### 6.2 입고 메뉴 — 사용자 지적 사항 반영(정적 확인)

| 항목 | 상태 |
|------|------|
| **신규 입고 하위 — PDF + 엑셀** | **반영됨 (v1.1):** `📄 신규 입고` 아래 `onOnPdfInbound`와 **`onInboundManual`(엑셀 파일 수동 입고)** 동급 배치. (`handlers/menubar.js`의 F002와 별개로 **실제 클릭은 sqm-inline 경로**) |
| **PDF/문서 변환 위치·명칭** | 파일 메뉴 `onDocConvert`(PDF/이미지 변환) 유지 — 사용자 요청대로 **설정/도구 이동·「입고 서류 파싱」명칭 변경**은 **미반영(향후 코딩)** |

### 6.3 백엔드에 명시된 분산 매핑 예 (`__init__.py` 주석)

- 톤백 위치 매핑(F004): `tonbag_api` → `POST /api/tonbag/location-upload` 등
- Allocation 일부: `allocation_api`
- 즉시 출고 등: `outbound_api`

즉 **기능이 `/api/menu/*`가 아닌 다른 URL**으로 구현된 경우가 많음.

---

## 7. 기능 단위 대응표 (메뉴 레지스트리 기준 → v866 정적 판정)

아래는 **원본 `menu_registry` + 출고 리스트**의 대표 항목에 대해, **UI 존재 + 백엔드 분산 가능성**만 반영한 요약입니다.  
세부는 `feature_matrix.json` F001~ 과 1:1 추적이 필요합니다.

### 7.1 입고 (`FILE_MENU_INBOUND_ITEMS`)

| # | 원본 기능 | 기호 | 비고 |
|---|-----------|------|------|
| 1 | PDF 스캔 입고 | ○/△ | UI·인바운드 API 존재 / menubar 경로와 병행 시 경로 통일 필요 |
| 2 | 엑셀 수동 입고 | ○ | 신규 입고 하위 **`onInboundManual`** 배치됨; 별칭 `onBulkImportInventorySimple`도 `ENDPOINTS`에 동일 모달로 연결 |
| 3 | D/O 후속 연결 | △ | 원본은 `_on_do_update` 단일; v866는 D/O 하위 분할·설정 메뉴 중복 가능 → **동작 동일 여부 실측** |
| 4 | 톤백 위치 매핑 | ○ | `tonbag_api` 등록; UI `onInventoryMove` — **엔드포인트명과 sqm-inline 연결 확인** |
| 5 | 대량 이동 승인 | △ | 메뉴에 있음 — 백엔드 구현 depth 확인 필요 |
| 6~8 | 반품 계열 | △ | 다이얼로그 기반 — Web에서 모달/501 여부 확인 필요 |
| 9 | 입고 현황 조회 | △ | optional |
| 10~12 | 템플릿·제품·이메일 | △ | |
| 13~14 | 정합성·LOT 복구 | ○ | `actions`·`queries`·integrity 관련 일부 구현 존재 |

### 7.2 출고 (`FILE_MENU_OUTBOUND_ITEMS`)

원스톱·피킹·Allocation·Sales Order 등 **항목 수 많음**. v866 `index.html` 출고 메뉴·`outbound_api`와 **대부분 이름 대응**하나, **원본 Tk 메서드와 HTTP 바디 1:1**은 **기능 테스트 없이 ○ 확정 불가** → **X/△ 혼재 가능**.

### 7.3 재고·보고서·설정·도움말

- **재고(`MENU_STOCK_ITEMS`)**: v866 상단 **「재고」** 메뉴로 분리 — 위치 다름, 기능만 동일하면 됨(사용자 기준).
- **보고서(`MENU_REPORT_ITEMS`)**: 「보고서」메뉴에 서브 다수 존재.
- **설정/도구**: 원본 `MENU_SETTINGS_ITEMS` + 별도 **🔧 도구** 메뉴와 **역할 분산** — 통합 여부는 기능 테스트로 판단.

---

## 8. 결론 및 권장 다음 단계

1. **기능 동등만 평가**할 경우, 검증 표는 **「Tk 메서드명 / 엔진 진입점」↔「실제 호출 URL + 응답」** 매트릭스가 가장 정확함.
2. **`menubar.js`의 `/api/menu/*` 일괄 경로**와 **실제 FastAPI 라우터** 불일치가 **가장 큰 리스크** — `sqm-inline.js`에서 동일 기능이 다른 엔드포인트를 쓰는지 **전역 검색으로 정리**할 것을 권장.
3. 사용자 후속 작업(코딩 시):  
   - ~~엑셀 수동 입고 → 신규입고와 **동급 메뉴** 추가~~ → **완료(부록 B)**  
   - PDF/문서 관련 → **설정/도구** 이동 + **「입고 서류 파싱」** 명칭  
   - D/O·톤백은 **원본 `_on_do_update` / `_on_tonbag_location_upload`와 같은 엔진 호출**인지 **한 번씩 E2E 확인**  
4. **하부메뉴 단위 전수 표**는 `REPORTS/v864_v866_menu_full_verification.md` 참조 (○/△/✕ 항목별 상세).

---

## 9. 팀 구성 제안 (전수 검사 작업용)

| 방식 | 장점 | 단점 |
|------|------|------|
| **단일 에이전트(연속 세션)** | 맥락 유지, 표 형식 통일 | 시간·토큰 많이 소모 |
| **서브 에이전트 병렬** | 입고/출고/보고서/설정·도구 **파트별 병렬 추출** 가능 | 마지막에 **한 사람이 표 병합·중복 제거** 필요 |

**루비 추천:** 메뉴 레지스트리 단위로 **4并行(파일·입고 / 출고 / 재고·보고서 / 도구·도움말)** 로 원본 스캔 → **단일 리더가 `handler` 기준으로 병합**하는 방식이 오류가 적음.

---

## 10. 부록: 검토 시 확인한 주요 경로

```
Claude_SQM_v864_20260329_FULL/gui_app_modular/menu_registry.py
Claude_SQM_v864_20260329_FULL/gui_app_modular/mixins/custom_menubar.py
SQM_v866_CLEAN/frontend/index.html
SQM_v866_CLEAN/frontend/js/handlers/menubar.js
SQM_v866_CLEAN/frontend/js/api-client.js
SQM_v866_CLEAN/backend/api/__init__.py
SQM_v866_CLEAN/docs/handoff/feature_matrix.json
SQM_v866_CLEAN/docs/handoff/v864_2_structure.json
```

---

*본 문서는 정적 코드 검토에 기반하며, 상용 동등성은 반드시 사용자 시나리오 기반 E2E로 보완할 것.*

---

## 부록 B — 2026-05-01 적용: `sqm-inline.js` ENDPOINTS X→O 배선

다음은 **`frontend/js/sqm-inline.js`의 `ENDPOINTS` 및 `dispatchAction`** 수정으로, 기존 `wip`(준비 중)에 가까웠던 메뉴를 실제 경로에 연결한 내역입니다. **UI 위치는 사용자 요청에 따라 추후 조정 가능.**

| 변경 전 | 변경 후 |
|---------|---------|
| `onExportLot` → wip | `export-lot-excel-dl` → `window.open(API+'/api/action/export-lot-excel')` (FileResponse 다운로드) |
| `onStockTrendChart` → wip | `GET /api/q/inventory-trend` → 기존 `renderInfoModal` |
| `onGlobalSearch` → wip | `inventory` 라우트로 이동 (전역 검색 UI 미구현 시 Inventory 검색으로 대체) |
| `onBlCarrierRegister` / `onBlCarrierAnalyze` → wip | `carrier-profile` → `showCarrierProfileModal()` (선사 프로파일 화면 통합) |
| `onAiChat` → wip | `gemini-api-settings` → API 설정 모달 (채팅 전용 UI는 미포함) |
| (신규 별칭) `onBulkImportInventorySimple` | `inbound-upload` → `showInboundManualUploadModal()` (v864 `_bulk_import_inventory_simple` 대응) |

**`frontend/index.html`:** 입고 → 신규 입고 하위에 **「📊 엑셀 파일 수동 입고」** 버튼 추가 (`data-action="onInboundManual"`).

**pytest:** `151 passed, 10 skipped` 유지. **node --check** `sqm-inline.js` 통과.

**2차 (2026-05-01 추가):** `onProductMaster` → `showProductMasterModal()` (`/api/q/product-inventory` 집계), `onAiTools` → 허브 모달(선사/Gemini), `onReportTemplates` → 일·월·재고 보고 데이터 바로가기, `onReportHistory` → `audit_log` 기반 이력 표. 설정 메뉴에 **「🤖 AI 도구 모음」** 버튼 추가.

**아직 이후 작업 권장:** v864 수준 제품 마스터 **CRUD**, 파일 기반 보고서 **양식 파일 편집기**, `onLotListExcel` 등 FileResponse GET의 다운로드 UX 통일.
