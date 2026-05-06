# SQM Async UI Thread Patch — 작업 지시서

**문서 ID:** SQM-WO-20260506-001
**작성:** 2026-05-06 (수)
**작성자:** Ruby (Senior Software Architect Mode)
**발주:** 남기동 대표님
**프로젝트:** SQM Inventory v8.6.6 (광양창고)

---

## 1. 작업 개요 (Overview)

### 목적
SQM 시작 시 최대 15.7초 메인 화면 freeze 제거 + AI/DB 관련 부수 폭탄 처리

### 배경
- 2026-05-05 횡단 감사 결과 4개 폭탄 식별 (`AUDIT_2026-05-05.md`)
- youtube_unified 동일 패턴 패치 검증 완료 (`unified_launcher_window.py`)
- 동일 비동기 패턴을 SQM 에 적용

### 시공
- **Main**: Ruby (Senior Architect)
- **Sub-agents**: A (Ollama), B (DB), C (HTTP test), D (호환성), E (수동 체크리스트)

### 예상 기간
- 작업 지시서 작성: **10분**
- 대표님 승인: **5분**
- 실행 (병렬): **~60분**
- **합계: ~75분**

---

## 2. 범위 (Scope)

### IN — 포함
- ✅ `main_webview.py` 스플래시 창 패턴 적용 (P1)
- ✅ `features/ai/ollama_manager.py` 비동기화 (P2)
- ✅ `engine_modules/database.py` DB 락 worker thread 위임 (P3)
- ✅ `tests/test_frontend_connection.py` 신규 작성 (Q1)
- ✅ 기존 `tests/test_smoke_workflow.py` 호환성 보고서 (Q2)
- ✅ `MANUAL_SMOKE_CHECKLIST.md` 신규 작성 (E2E)
- ✅ 통합 보고서 `SQM_PATCH_FINAL_REPORT_2026-05-06.md`

### OUT — 제외 (별도 세션)
- ❌ SQM 다른 기능 리팩토링
- ❌ 프론트엔드 JS 코드 수정
- ❌ DB 스키마 변경
- ❌ 신규 기능 추가
- ❌ Playwright/Selenium E2E 자동화 (Level 2 — 별도 세션)
- ❌ pywebview 버전 업그레이드

---

## 3. 선결 조건 (Pre-conditions)

| 항목 | 상태 |
|---|---|
| Git 안전점 태그 `pre-async-patch-20260506` | ✅ 존재 (commit 4df1b79) |
| origin/main 동기화 | ✅ Up to date |
| Ruby SQM 폴더 Read 접근 | ✅ 검증됨 (main_webview.py 456 lines 읽음) |
| 어제 `test_smoke_workflow.py` 자산 | ✅ 존재 (역방향 감사 통과) |
| youtube_unified 동일 패턴 검증 | ✅ 완료 (P0+P1 적용, 깜빡임 해결) |

---

## 4. 작업 분해 (Task Breakdown)

### 🥇 P1 [Main = Ruby] — main_webview.py 스플래시 창 패턴

**파일:** `D:\program\SQM_inventory\SQM_v866_CLEAN\main_webview.py`
**현재 라인:** 217~456 (`main()` 함수 본체)
**백업:** `main_webview.py.bak.20260506` 생성

**변경 명세:**
1. `main()` 시작부에 백그라운드 스레드 생성:
   - `is_port_open` + `kill_zombie_on_port` + `run_api_server` 모두 백그라운드로
2. `webview.create_window()` 를 `html=SPLASH_HTML` 로 즉시 호출
3. `webview.start(func=on_window_started, debug=False)` 형태로 변경
4. `on_window_started()` 콜백:
   - 창 최대화 복원
   - `wait_for_api(timeout=10)` 백그라운드 대기
   - 성공 시 `window.load_url(API_URL)`
   - 실패 시 오류 화면 HTML 로드
5. `on_loaded()` 가중 처리:
   - `_navigated[0] = False/True` 플래그로 splash vs real URL 구분
   - real URL 로드 후만 JS 브릿지 설치

**보존:**
- `SqmPywebviewApi` 클래스 전체
- `on_closing()` 함수 전체
- 로깅, 예외 훅, window state 저장 로직

**합격 기준:**
- [ ] `python -m py_compile main_webview.py` 성공
- [ ] 모든 import 그대로 유지
- [ ] `SPLASH_HTML` 상수 추가됨
- [ ] `webview.start(func=...)` 호출 형태 변경됨
- [ ] 기존 `wait_for_api`, `kill_zombie_on_port` 함수 자체는 미변경 (호출 위치만 변경)

---

### 🥈 P2 [Sub-agent A] — ollama_manager.py 비동기화

**파일:** `D:\program\SQM_inventory\SQM_v866_CLEAN\features\ai\ollama_manager.py`
**현재 라인:** 64~82 (`start_ollama_server`)
**백업:** `ollama_manager.py.bak.20260506`

**변경 명세:**
- `for _ in range(10): time.sleep(0.4); if check_ollama_server(): return True` 패턴을:
- 호출자가 `threading.Thread` 안에서 실행하도록 강제 (또는 함수 시그니처에 콜백 추가)

**합격 기준:**
- [ ] `python -m py_compile` 통과
- [ ] 메인 스레드에서 호출 시 즉시 반환 (블로킹 X)
- [ ] 결과는 콜백 또는 `Future` 로 전달

---

### 🥉 P3 [Sub-agent B] — database.py DB 락 비동기화

**파일:** `D:\program\SQM_inventory\SQM_v866_CLEAN\engine_modules\database.py`
**현재 라인:** 477-489, 508-518, 547-557 (3곳의 `time.sleep(retry_delay)`)
**백업:** `database.py.bak.20260506`

**변경 명세:**
- `sqlite3.OperationalError` 재시도 로직을 `concurrent.futures.ThreadPoolExecutor` 로 위임
- DB 호출 헬퍼 (`db_execute_async`, `db_query_async`) 신규 추가
- 호출자 측에서 점진적으로 async 헬퍼로 마이그레이션 (이번에는 P3 헬퍼만 추가)

**주의:**
- 기존 동기 호출 경로 **유지** (회귀 방지)
- 신규 async 헬퍼는 옵트인 형태로 제공

**합격 기준:**
- [ ] `python -m py_compile` 통과
- [ ] 기존 함수 시그니처 보존
- [ ] 신규 async 헬퍼 함수 정의 추가됨
- [ ] 단위 테스트 (호환성 검증)

---

### 🥉 Q1 [Sub-agent C] — HTTP 정적 검증 테스트

**신규 파일:** `D:\program\SQM_inventory\SQM_v866_CLEAN\tests\test_frontend_connection.py`

**테스트 케이스:**
1. `test_index_html_loads` — 메인 페이지 200 응답
2. `test_critical_js_modules_load` — sqm-core.js, sqm-inline.js 등 200
3. `test_api_health_endpoint` — `/api/health` 응답
4. `test_no_404_in_index_html` — 모든 `<script src>` 가 실제로 로드 가능

**합격 기준:**
- [ ] `pytest --collect-only tests/test_frontend_connection.py` 4개 케이스 인식
- [ ] 백엔드 실행 중 상태에서 `pytest tests/test_frontend_connection.py -v` 모두 통과

---

### 🥉 Q2 [Sub-agent D] — 기존 test_smoke_workflow.py 호환성 분석

**대상:** `D:\program\SQM_inventory\SQM_v866_CLEAN\tests\test_smoke_workflow.py`
**산출:** `D:\program\SQM_inventory\SQM_v866_CLEAN\tests\COMPATIBILITY_REPORT_20260506.md`

**분석 항목:**
1. 어제 만든 테스트의 시나리오 + 검증 범위 요약
2. P1/P2/P3 패치가 영향 줄 수 있는 케이스 식별
3. 패치 후 추가 검증 필요 시나리오 제안
4. 회귀 위험도 평가 (낮음/중간/높음)

**합격 기준:**
- [ ] 보고서 생성됨
- [ ] 모든 P1/P2/P3 영역 vs 테스트 케이스 매핑 완료
- [ ] 실제 테스트 실행은 본 작업 범위 외 (별도)

---

### 🥉 E2E [Sub-agent E] — 수동 검증 체크리스트

**신규 파일:** `D:\program\SQM_inventory\SQM_v866_CLEAN\MANUAL_SMOKE_CHECKLIST.md`

**8개 항목:**
1. SQM 시작 시간 측정 (기대 ~0.3초 창 등장)
2. 메인 페이지 데이터 로딩
3. 입고 등록 다이얼로그
4. 출고 등록 + 재고 반영
5. 엑셀 내보내기
6. 검색 필터
7. 창 정상 종료 (작업관리자 확인)
8. 재실행 시 좀비 없음

**합격 기준:**
- [ ] 8개 항목 명확한 기대 결과 명시
- [ ] 각 항목 합격/불합격 판정 기준 포함

---

## 5. 책임 매트릭스 (RACI)

| 작업 | Responsible | Accountable | Consulted | Informed |
|------|-------------|-------------|-----------|----------|
| P1 main_webview | Main (Ruby) | Ruby | - | 대표님 |
| P2 ollama | Sub-A | Ruby | - | 대표님 |
| P3 database | Sub-B | Ruby | - | 대표님 |
| Q1 frontend test | Sub-C | Ruby | - | 대표님 |
| Q2 호환성 분석 | Sub-D | Ruby | - | 대표님 |
| E2E 체크리스트 | Sub-E | Ruby | - | 대표님 |
| 통합 검증 + 보고서 | Main (Ruby) | 대표님 | Ruby | - |

---

## 6. 리스크 등록부 (Risk Register)

| ID | 리스크 | 영향 | 확률 | 완화책 |
|----|--------|------|------|--------|
| R1 | pywebview 가 `webview.start(func=...)` 미지원 (구버전) | 높음 | 낮음 | 시작 전 `webview.__version__` 체크. 미지원 시 P1 보수형(폴링 속도만 개선)으로 전환 |
| R2 | SPLASH_HTML 인코딩 이슈 (한글 깨짐) | 중간 | 낮음 | UTF-8 명시 + meta charset 선언 |
| R3 | `on_loaded` 두 번 발화로 JS 브릿지 중복 설치 | 중간 | 중간 | `_navigated` 플래그 + idempotent 가드 |
| R4 | P3 DB async 헬퍼가 기존 트랜잭션 동작 변경 | 높음 | 중간 | 신규 헬퍼만 추가, 기존 함수 미변경 |
| R5 | Q2 호환성 분석에서 P1~P3 영향 발견 | 중간 | 중간 | 자동 정지 정책 (대표님 승인 후 진행) |
| R6 | 서브에이전트 결과 품질 편차 | 낮음 | 중간 | 메인이 모든 결과 통합 검증 |

---

## 7. 검증 절차 (Verification Phases)

| Phase | 내용 | 누가 | 합격 기준 |
|---|---|---|---|
| 1. Syntax | `python -m py_compile <each .py>` | Main 통합 | 모든 파일 통과 |
| 2. Unit | (해당 시) pytest 새 테스트 | Main | 100% 통과 |
| 3. Compatibility | Q2 보고서 검토 | Main + 대표님 | 회귀 위험 "낮음" 이상 |
| 4. Manual | E2E 체크리스트 (대표님) | 대표님 | 8/8 합격 |
| 5. Time | 시작 시간 측정 | 대표님 | <1초 창 등장 |

---

## 8. 롤백 절차 (Rollback)

### 단일 파일 롤백
```powershell
cd D:\program\SQM_inventory\SQM_v866_CLEAN
copy /Y main_webview.py.bak.20260506 main_webview.py
copy /Y features\ai\ollama_manager.py.bak.20260506 features\ai\ollama_manager.py
copy /Y engine_modules\database.py.bak.20260506 engine_modules\database.py
```

### 전체 Git 롤백
```powershell
cd D:\program\SQM_inventory\SQM_v866_CLEAN
git reset --hard pre-async-patch-20260506
# 원격까지 되돌리려면 (대표님 승인 필요):
git push --force origin main
```

---

## 9. 성공 지표 (Success Metrics)

| 지표 | 현재 (Pre) | 목표 (Post) | 측정 방법 |
|---|---|---|---|
| 창 등장 시간 | ~15.7초 (worst), ~1.5초 (typical) | **<1초** | 수동 스톱워치 |
| AI 시작 멈춤 | 4초 | **즉시** (배경 처리) | 자동 보정 클릭 후 시간 |
| DB 락 UI 멈춤 | 0.5~1초 (간헐) | **0초** (배경) | 동시 작업 시나리오 |
| 회귀 (기존 기능) | (현재 OK) | **0건** | test_smoke_workflow.py |
| 코드 구문 오류 | 0 | **0** | ast.parse 검증 |

---

## 10. 산출물 목록 (Deliverables)

### 코드
- (변경) `main_webview.py` + `.bak.20260506`
- (변경) `features/ai/ollama_manager.py` + `.bak.20260506`
- (변경) `engine_modules/database.py` + `.bak.20260506`

### 테스트
- (신규) `tests/test_frontend_connection.py`

### 문서
- (신규) `tests/COMPATIBILITY_REPORT_20260506.md`
- (신규) `MANUAL_SMOKE_CHECKLIST.md`
- (신규) `SQM_PATCH_FINAL_REPORT_2026-05-06.md` (최종 통합)
- (이 문서) `SQM_WORK_ORDER_2026-05-06.md`

### Git
- 최종 커밋: `fix(ui): SQM async UI thread patch — startup 15.7s → <1s`
- 태그: `post-async-patch-20260506`

---

## 11. 승인 (Approval)

- [x] **남기동 대표님** — 범위/우선순위/리스크 검토 후 진행 승인 (2026-05-06 진행 승인)
- [x] **Ruby (Senior Architect)** — 기술적 타당성 확인 (작성 시점)

승인 후 메인 P1 + 서브 5개 동시 발사.

---

## 12. 변경 이력 (Changelog)

- **2026-05-06 (수)** Ruby — 초안 작성 (v1.0)

---

*이 작업 지시서는 `.claude/templates/sqm-patch-work-order.md` 템플릿을 기반으로 작성되었습니다. 향후 v8.6.7, v8.7.0 등 패치 시 동일 템플릿 재사용 가능.*
