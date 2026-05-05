# v864.2 vs SQM_v866_CLEAN — 메뉴·하부메뉴 전수 검증표 (정적·코드 기준)

| 항목 | 내용 |
|------|------|
| **원본 기준** | `Claude_SQM_v864_20260329_FULL/gui_app_modular/menu_registry.py` + `mixins/custom_menubar.py` |
| **대상 UI** | `frontend/index.html` + `frontend/js/sqm-inline.js` 의 `ENDPOINTS` / `dispatchAction` |
| **검증 성격** | **코드·라우팅 연결 여부** (실제 업무 E2E 클릭 검증 아님) |

### 기호

| 기호 | 의미 |
|------|------|
| **○** | Web에서 메뉴(또는 동등 액션)·백엔드/모달 경로가 연결됨 |
| **△** | **연결은 되었으나** v864와 **이름·분할·동작이 완전 동일하진 않음** (대체·축약·분할) |
| **✕** | **메뉴 없음** 또는 **명확한 미구현·스텁·준비 중** |
| **◇** | v864에서 **optional**(메서드 없으면 메뉴 숨김) — 원본에서도 안 보일 수 있음 |

---

## 1. 탑레벨 메뉴 구조 차이

| v864 (`custom_menubar`) | v866 (`index.html`) |
|---------------------------|---------------------|
| 📤 출고 → 📁 파일 → 📝 보고서 → 🔧 도구 → 👁️ View → ❓ 도움말 → 📦 품목 | 📁 파일 → 📥 입고 → 📤 출고 → 📊 재고 → 📝 보고서 → 🔍 검색 → 🔧 설정/도구 → ❓ 도움말 |

→ **탑 레벨 이름·순서는 다름**. 사용자 기준 **기능만 같으면 됨**이면 구조 차이는 **△**로 두고 항목별로만 ○/✕ 판정.

---

## 2. 📤 출고 (`FILE_MENU_OUTBOUND_ITEMS`)

| # | v864 하부 메뉴 | v866 | 판정 | 비고 |
|---|----------------|------|------|------|
| 1 | 🚀 즉시 출고(원스톱) | 입고 아님 **출고** > 즉시 출고 > `onOnQuickOutbound` | ○ | |
| 2 | 📤 빠른 출고(붙여넣기) | `onQuickOutboundPaste` | ○ | |
| 3 | 📋 Picking List 업로드(PDF) | `onPickingListUpload` | ○ | |
| 4 | 📊 바코드 스캔 업로드 | `onBarcodeScanUpload` | ○ | |
| 5 | 📷 스캔 탭으로 이동 | `onGoScanTab` | ○ | |
| 6 | 📋 Allocation 입력 | `onInventoryAllocation` | ○ | |
| 7 | ✅ 승인 대기 | `onApprovalQueue` | ○ | ◇ optional |
| 8 | 📌 예약 반영(승인분) | `onApplyApproved` | ○ | ◇ |
| 9 | 📜 승인 이력 조회 | `onApprovalHistory` | ○ | ◇ |
| 10 | 📋 판매 배정 탭으로 이동 | `onGoAllocationTab` | ○ | |
| 11 | 📋 출고 현황 조회 | 출고 > 조회/관리 `onOutboundStatus` | △ | 경로만 다름 |
| 12 | 📊 Sales Order 업로드 | `onSalesOrderUpload` | ○ | ◇ |
| 13 | 🔁 Swap 리포트 | `onSwapReport` | ○ | ◇ |
| 14 | 📦 출고 피킹 템플릿 관리 | `onPickingTemplateManage` | ○ | |

---

## 3. 📁 파일 — 📥 입고 서브 (`FILE_MENU_INBOUND_ITEMS`)

| # | v864 항목 | v866 | 판정 | 비고 |
|---|-----------|------|------|------|
| 1 | 📄 PDF 스캔 입고 | 신규 입고 > `onOnPdfInbound` | ○ | |
| 2 | 📊 엑셀 파일 수동 입고 | 신규 입고 > `onInboundManual` | ○ | |
| — | 구분선 | — | | |
| 3 | 📋 D/O 후속 연결 | **단일 항목 없음** — D/O > `onDoUpload` / `onDoUpdate` 로 분리 | △ | 같은 `_on_do_update` 흐름을 **두 갈래 UI**로 표현 |
| 4 | 📍 톤백 위치 매핑 | `onInventoryMove` | ○ | ◇ optional |
| 5 | ✅ 대량 이동 승인 | `onMoveApprovalQueue` | ○ | ◇ |
| — | 구분선 | — | | |
| 6 | 🔄 반품(재입고) | 반품 > `onReturnDialog` | △ | v864는 소량/다량 **하위 서브**; Web은 단일 진입 |
| 7 | 📂 반품 입고(Excel) | `onReturnInboundUpload` | ○ | |
| 8 | 📊 반품 사유 통계 | **메뉴 항목 삭제** (`index.html` 주석). `ENDPOINTS`의 `onReturnStatistics`는 남음 | ✕ | 메뉴로는 미노출 |
| — | 구분선 | — | | |
| 9 | 📋 입고 현황 조회 | 조회/관리 > `onInboundList` | △ | ◇ optional |
| — | 구분선 | — | | |
| 10 | 📝 입고 파싱 템플릿 관리 | `onInboundTemplateManage` (중복 배치) | ○ | |
| 11 | 📦 제품 마스터 관리 | `onProductMaster` → 집계 모달 | △ | **CRUD 아님** (조회·집계 수준) |
| 12 | ⚙️ 이메일 설정 | `onEmailConfig` | ○ | |
| — | 구분선 | — | | |
| 13 | 🔍 정합성 검증(시각화) | 정합성 > `onIntegrityCheck` | △ | v764 시각화 전용과 완전 동일 단정 불가 |
| 14 | 🛠️ LOT 상태 정합성 복구 | `onFixLotIntegrity` | △ | 동일 API 경로 재사용 가능 |

---

## 4. 📁 파일 — 💾 내보내기 (`FILE_MENU_EXPORT_ITEMS`)

| v864 | v866 메뉴 | 판정 | 비고 |
|------|-----------|------|------|
| 📋 통관요청 양식 | **전용 메뉴 없음** (`onExportCustoms`는 ENDPOINTS만 존재) | ✕ | |
| 📊 루비리 양식 | 동상 (`onExportRubyli`) | ✕ | |
| 🎒 톤백 현황 | 재고 메뉴 `onExportTonbag` 등과 유사 기능은 **재고 > 톤백리스트** 등으로 일부 대응 가능 | △ | 옵션 번호별 분기와 1:1 아님 |
| ⭐ 통합 현황 | `onExportIntegrated` ENDPOINT만 | ✕ | 메뉴 미노출 |

---

## 5. 📁 파일 — 🔐 백업 (`FILE_MENU_BACKUP_ITEMS`)

| v864 | v866 | 판정 |
|------|------|------|
| 💾 백업 생성 | 파일 > 백업 `onOnBackup` | ○ |
| 🔄 복원 | `onRestore` | ○ |
| 📋 백업 목록 | `onBackupList` | ○ |
| ⏰ 자동 백업 설정 | `onAutoBackupSettings` | ○ |

---

## 6. 📁 파일 — 🔧 도구 (파일 메뉴 안의 작은 도구 서브)

| v864 | v866 | 판정 | 비고 |
|------|------|------|------|
| 📷 문서 변환 (OCR/PDF) | 파일 > `onDocConvert` | ✕ | 모달 내 **Phase 6 안내 스텁** 수준 |
| 🩺 데이터 정합성 검사 | 파일 메뉴에 **직접 동일 라벨 없음**. 설정/도구·입고 정합성 등으로 분산 | △ | |

---

## 7. 📁 파일 — 📂 최근 파일 · 종료

| v864 | v866 | 판정 |
|------|------|------|
| 📂 최근 파일 | `onRecentFiles` | ○ |
| 종료 | `onExit` | ○ |

---

## 8. 파일 메뉴에 통합된 v864 요소 (Web에서 별도 블록)

| 내용 | v866 위치 | 판정 | 비고 |
|------|-----------|------|------|
| BL 선사 도구 | 파일 > 🚢 BL 선사 도구 | △ | `carrier-profile` 통합 |
| Gemini AI | 파일 > ✨ Gemini AI | △ | AI 채팅은 설정 모달로 우회 등 |

---

## 9. 📝 보고서 (`MENU_REPORT_ITEMS`)

| v864 | v866 보고서 메뉴 | 판정 | 비고 |
|------|------------------|------|------|
| 📄 거래명세서 생성 | 송장/DN `onInvoiceGenerate` | ○ | |
| 📦 Detail of Outbound | 동명 | ○ | |
| 📋 Sales Order DN | 송장/DN·Sales Order 블록 중복 배치 | △ | 라벨 중복 |
| 🔍 DN 교차검증 | `onDnCrossCheck` | ○ | |
| 📝 고객 보고서 생성 | 커스텀 `onReportCustom` | ○ | ◇ optional |
| 📂 보고서 양식 관리 | `onReportTemplates` → 허브 모달 | △ | **파일 CRUD 아님** |
| 📋 보고서 이력 조회 | `onReportHistory` → audit 기반 | △ | v864 이력과 동일 DB 보장 안 함 |
| 📦 재고 현황 보고서 | 분석 `onInventoryReport` | ○ | |
| 📈 입출고 내역 | `onMovementHistory` | ○ | |
| 📅 월간 실적 PDF | 정기 `onReportMonthly` | ○ | ◇ optional |
| 📊 일일 현황 PDF | `onReportDaily` | ○ | ◇ optional |
| 🔖 LOT 상세 | `onLotDetailPdf` | ○ | |

---

## 10. 🔧 도구 전용 메뉴 (`_create_tools_menu`) — v864 탑레벨 「🔧 도구」

v866에는 **동일 이름의 단일 「🔧 도구」탑메뉴가 없고**, 기능이 **설정/도구·파일·보고서** 등으로 나뉨 → 구조 **△**.

| v864 🔧 도구 하부 | v866 대응 | 판정 | 비고 |
|-------------------|-----------|------|------|
| 📦 제품 마스터 관리 | 입고·설정 등 `onProductMaster` | △ | CRUD 아님 |
| 📊 제품별 재고 현황 | 설정 > 제품 관리 `onProductInventoryReport` 등 | ○ | |
| 📊 LOT Allocation·톤백 현황 | `onLotAllocationAudit` | ○ | ◇ 앱에 메서드 있을 때만 표시 |
| 📋 D/O 후속 연결 | 입고 D/O / 설정 등 | △ | 분산 |
| 📄 PDF/이미지 변환 → Excel/Word/일괄/분석 | **Web 미분해** — 통합 스텁 `onDocConvert` 수준 | ✕ | |
| 📷 문서 변환 OCR/PDF | `onDocConvert` | ✕ | 스텁 |
| 📋 PDF 보고서 서브(여러 줄) | 보고서·분석 메뉴로 대부분 존재 | △ | 한 서브에 모이진 않음 |
| 🩺 데이터 정합성 검사 | `onIntegrityCheck` 등 | ○ | |
| 🤖 Gemini AI 전체 서브 | 파일 메뉴 Gemini + `onAiTools` 허브 | △ | |
| 🛡️ DB 보护 | Web 빌드에서 조건부 미노출 가능 | ◇ | |
| 🔍 DB 검사 | 설정 DB 블록과 **라벨 완전 일치 항목 없을 수 있음** — `integrity` 계열로 분산 | △ | |
| 🔧 DB 최적화 | `onOptimizeDb` | ○ | |
| 📋 로그 정리 | `onCleanupLogs` | ○ | |
| ℹ️ DB 정보 | `onDbInfo` | ○ | |
| 🗑️ 테스트 DB 초기화 | `onTestDbReset` | ○ | ◇ 개발자 모드 |
| ✨ 고급 (입출고 검증·진단·단위테스트) | **메뉴 없음** | ✕ | ◇ HAS_FEATURES |

---

## 11. 👁️ View 메뉴

| v864 View | v866 | 판정 |
|-----------|------|------|
| Refresh | `refresh-all` 상단 | ○ |
| 각 탭 이동 | 사이드바 `data-route` | ○ |
| Theme | `theme-dark` / `theme-light` | ○ |

---

## 12. 📦 품목 메뉴 (v864 탑레벨)

| v864 | v866 재고 > 품목 | 판정 |
|------|------------------|------|
| 📋 품목별 재고 요약 | `onProductSummary` | ○ |
| 🔍 품목별 LOT 조회 | `onProductLotLookup` | ○ |
| 📊 품목별 입출고 현황 | `onProductMovement` | ○ |

---

## 13. 🔧 설정/도구 (`MENU_SETTINGS_ITEMS` 요약)

| v864 설정/도구 레지스트리 | v866 | 판정 |
|---------------------------|------|------|
| 🔄 새로고침 | `refresh-all` | ○ |
| 💾 창 크기 저장 | 상단/설정 경로 분산 — `save-window-size` 등 | △ |
| ↩️ 창 크기 초기화 | 동상 | △ |
| 📦 제품 마스터 | `onProductMaster` | △ |
| 📊 제품별 재고 현황 | `onProductInventoryReport` | ○ |
| 📋 D/O 후속 연결 | 입고 쪽과 중복 가능 | △ |
| 🩺·🔍 정합성 계열 | 여러 버튼으로 분산 | △ |

---

## 14. ❓ 도움말 (`MENU_HELP_ITEMS`)

| v864 | v866 | 판정 |
|------|------|------|
| 📖 사용법 | `onHelp` | ○ |
| ⌨️ 단축키 | `onShortcuts` | ○ |
| 📊 STATUS 안내 | `onStatusGuide` | ○ | ◇ |
| 💾 백업 가이드 | `onBackupGuide` | ○ | ◇ |
| ℹ️ 시스템 정보 | `onSystemInfo` | ○ | ◇ |
| 📝 버전 정보 | `onAbout` | ○ | |

---

## 15. 액션 툴바 (양쪽 공통 개념)

| 개념 | v866 `data-action` | 판정 |
|------|---------------------|------|
| PDF 입고 | `tb-pdf-inbound` | ○ |
| 즉시 출고 | `tb-quick-outbound` | ○ |
| 반품 | `tb-return` | ○ |
| 재고 조회 | `tb-inventory` | ○ |
| 정합성 | `tb-integrity` | ○ |
| 백업 | `tb-backup` | ○ |
| 설정 | `tb-settings` | ○ |

---

## 16. 사이드바 9탭

핸드오프 `v864_2_structure.json`과 **라벨·순서 대응** → **○** (탭 전환).

---

## 17. 종합 (질문에 대한 답)

**「하나하나 하부메뉴까지 세밀하게 검증」** 한 결과,  
**○만으로 채워지지 않습니다.** 대표 갭:

1. **파일 > 내보내기** 4종 중 **통관/루비리/통합** — 메뉴 미노출 (**✕**).  
2. **반품 사유 통계** — 메뉴 의도적 삭제 (**✕**).  
3. **문서/PDF 변환 세분(OCR·Excel·Word·일괄)** — Web은 **단일 스텁 수준** (**✕**).  
4. **제품 마스터·보고서 양식 파일** — **완전 CRUD / 파일 관리 아님** (**△**).  
5. **🔧 도구** 탑메뉴 전량 복제 아님 — 기능 **분산** (**△**).  
6. **고급·DB 보护·선택적 항목** — 빌드/옵션에 따라 원본도 숨김 (**◇/✕**).

따라서 **「100% 반영」이라고 말할 수 없고**, 위 표의 **✕·△**를 줄이는 작업이 남습니다.

---

*실사용 동등성은 각 ○·△ 항목에 대해 시나리오 테스트로 확정할 것.*
