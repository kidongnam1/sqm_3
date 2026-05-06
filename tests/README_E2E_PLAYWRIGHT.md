# SQM Playwright E2E 회귀 테스트 가이드

**작성:** 2026-05-06 — Ruby (Senior Software Architect Mode)
**대상 파일:** `tests/test_e2e_playwright.py`

---

## 📌 목적

매 SQM 패치 후 **1분 이내에** 항목 4/5/6/7 자동 회귀 검증.

| 항목 | 자동화 | 비고 |
|---|---|---|
| 1. 시작 시간 | ❌ | pywebview 네이티브 (수동) |
| 2. 스플래시 화면 | ❌ | pywebview (수동) |
| 3. 메인 페이지 자동 전환 | ❌ | pywebview (수동) |
| **4. 재고 데이터 표시** | **✅** | 5개 테스트 자동 |
| **5. 입고 메뉴 다이얼로그** | **✅** | 2개 테스트 자동 |
| **6. 출고 메뉴 다이얼로그** | **✅** | 2개 테스트 자동 |
| **7. 엑셀 내보내기** | **✅ (부분)** | 메뉴 가용성만, 다운로드는 pywebview 네이티브 |
| 8. 창 닫기 + 좀비 | ❌ | OS 프로세스 관리 (수동) |
| **회귀 0**. JS 브릿지 idempotency | **✅** | 3차 패치 검증 |

---

## 🚀 1회 셋업 (~5분, 한 번만)

PowerShell:
```powershell
cd D:\program\SQM_inventory\SQM_v866_CLEAN
pip install playwright pytest-playwright
```

```powershell
playwright install chromium
```

→ 약 200MB 다운로드. 완료되면 다음부터는 즉시 실행 가능.

---

## ✅ 매 패치 후 회귀 검증 (1분)

### Step 1 — SQM 백엔드 시작 (별도 터미널)
```powershell
cd D:\program\SQM_inventory\SQM_v866_CLEAN
python main_webview.py
```
→ 창 등장 + 메인 페이지 로드 완료 대기 (~6~10초).

### Step 2 — 테스트 실행 (다른 터미널)
```powershell
cd D:\program\SQM_inventory\SQM_v866_CLEAN
python -m pytest tests/test_e2e_playwright.py -v
```

### Step 3 — 결과 해석

**모두 PASSED**:
```
tests/test_e2e_playwright.py::TestItem4InventoryData::test_page_title PASSED
tests/test_e2e_playwright.py::TestItem4InventoryData::test_app_titlebar_visible PASSED
... (10여 개 테스트)
============= 10 passed in 25.34s =============
```
→ **항목 4/5/6/7 자동 합격** + 회귀 0건. 항목 1/2/3/8 수동 30초 확인 후 git push.

**일부 SKIPPED**:
```
SKIPPED [10] reason: 백엔드 미실행 (http://127.0.0.1:8765 접속 불가)
```
→ Step 1 실행 안 했음. SQM 시작 후 재시도.

**일부 FAILED**:
```
tests/test_e2e_playwright.py::TestItem5InboundMenu::test_inbound_menu_clickable FAILED
```
→ 회귀 발생! **즉시 git revert** 또는 `git reset --hard pre-async-patch-20260506`.

---

## 🐛 디버깅 — 실패 시 추가 정보

### 옵션 A — 헤드 모드 (브라우저 창 시각 확인)
`tests/test_e2e_playwright.py` 의 `headless=True` → `False` 변경 후 재실행.

### 옵션 B — 스크린샷 자동 저장
실패 시 자동 스크린샷이 필요하면:
```powershell
python -m pytest tests/test_e2e_playwright.py --screenshot=on -v
```

### 옵션 C — 비디오 녹화
```powershell
python -m pytest tests/test_e2e_playwright.py --video=retain-on-failure -v
```

---

## ⚙️ CI/CD 통합 (선택, 장기)

### GitHub Actions 예시 (`.github/workflows/e2e.yml`):
```yaml
name: SQM E2E Regression
on: [push, pull_request]
jobs:
  e2e:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: pip install playwright pytest-playwright
      - run: playwright install chromium
      - run: python main_webview.py &
      - run: sleep 15
      - run: python -m pytest tests/test_e2e_playwright.py -v
```

→ 매 push/PR 마다 자동 회귀 검증. 실패 시 머지 차단 가능.

---

## 📋 테스트 케이스 목록

### TestItem4InventoryData (5개)
- `test_page_title` — 페이지 타이틀에 "SQM" 또는 "S.I.M.S"
- `test_app_titlebar_visible` — 앱 타이틀바 가시성 + 버전 표시
- `test_menubar_loaded` — 파일/입고/출고 메뉴 표시
- `test_dashboard_kpi_api` — `/api/dashboard/kpi` 200 응답
- `test_critical_js_modules_loaded` — 7개 핵심 JS 200 로드

### TestItem5InboundMenu (2개)
- `test_inbound_menu_clickable` — 입고 메뉴 클릭 + 드롭다운 등장
- `test_inbound_submenu_actions_present` — 3개 이상 액션 버튼 존재

### TestItem6OutboundMenu (2개)
- `test_outbound_menu_clickable` — 출고 메뉴 클릭 + 드롭다운 등장
- `test_inventory_api_responds` — `/api/dashboard/sidebar-counts` 200

### TestItem7ExcelExport (1개)
- `test_export_menu_present` — 파일 → 내보내기 서브메뉴 존재

### TestRegressionP1P2P3 (2개)
- `test_no_console_errors_on_load` — JS 에러 0건
- `test_js_bridge_idempotency_guard_present` — 3차 패치 idempotency 검증

**합계: 12개 테스트, ~25초 소요**

---

## 🛡 안전 보장

- **NON-DESTRUCTIVE**: 어떤 테스트도 실제 데이터 수정/삭제하지 않음
- **READ-ONLY**: 메뉴 클릭, 응답 확인, 셀렉터 가시성만 검증
- **STATELESS**: 각 테스트가 독립된 페이지 컨텍스트 사용
- **OFFLINE-SAFE**: 백엔드 미실행 시 자동 skip (false-fail 0%)

---

## 🎯 향후 확장 (별도 세션)

- **단위 테스트 추가**: 입고 다이얼로그 폼 입력 + 취소 (데이터 미저장)
- **다국어 검증**: ko/en 메뉴 라벨 동시 검증
- **성능 측정**: Lighthouse CI 통합으로 페이지 성능 추적
- **시각 회귀 검증**: Percy.io 또는 Playwright snapshot 비교

---

**Ruby (Senior Software Architect) — Playwright E2E 자산 — 2026-05-06.**
