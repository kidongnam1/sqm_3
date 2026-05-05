# SQM Inventory v866 — PyWebView 마이그레이션 프로젝트

> **이 파일은 Claude / Cowork 가 세션 시작 시 자동으로 읽는 영구 메모리입니다.**
> 세션이 바뀌어도 이 내용은 유지됩니다. 수정 시 신중하게.

---

## 🧠 프로젝트 전용 메모리 규칙 — 최우선

> **최초 등록:** 2026-04-21 | **최종 수정:** 2026-05-05
> **등록자:** Nam Ki-dong (사장님) | **승인자:** Ruby (Senior Software Architect)

> ⚠️ **계층 안내:** 범용(모든 프로그램 공통) 규칙은 **상위 `F:\program\CLAUDE.md`** 에 있음.
> 이 파일은 **v866 프로젝트 전용** 규칙만 담음. 두 파일은 자동 상속됨.

> 🗂️ **주 작업 폴더:** `D:\program\SQM_inventory\SQM_v866_CLEAN`
> **GitHub:** `https://github.com/kidongnam1/sqm_3` (main 브랜치)

**v866 프로젝트 작업 시 반드시 이 폴더(= `SQM_v866_CLEAN\`)의 내용을 전부 참조·반영한다. 절대경로 하드코딩 금지.**

### 작업 시작 전 필수 확인
1. `./CLAUDE.md` — 이 파일 (v866 규칙/아키텍처/현황)
2. `./docs/handoff/v864_2_structure.json` — UI 구조 (메뉴 5개, 탭 9개, 툴바 7개)
3. `./docs/handoff/feature_matrix.json` — **85개 기능 완전 매핑표**
4. `./docs/handoff/design_tokens.json` — 디자인 토큰 (156색상, 17테마)

### 코드 작성 시 필수 규칙
- 색상/폰트/간격 → `design_tokens.json` 값만 사용 (하드코딩 금지)
- 기능 → `feature_matrix.json`의 엔드포인트/핸들러 이름과 일치
- 비즈니스 로직 → `./engine_modules/`, `./features/`, `./parsers/`, `./utils/` 재활용

### 새 파일/기능 추가 시 필수 검증
- 이 폴더에 이미 존재하는지 `Glob`/`Grep`로 먼저 확인 (중복 생성 금지)
- 파일 위치는 아래 "디렉토리 구조" 섹션을 따름
- 폴더 내용과 사장님 지시가 충돌하면 → 즉시 질문 (가정 금지)

**위반 시:** 규칙 위반 코드는 그 자리에서 롤백. 예외 없음.

---

## 🎯 프로젝트 목표

Tkinter + ttkbootstrap 기반 **SQM Inventory v864.2** (광양 GY Logis 물류창고 재고관리 시스템)를
**PyWebView 5 + HTML/CSS/JS + FastAPI** 기반 **v866**으로 완전 마이그레이션.

**핵심 원칙:** UI와 기능(Behavior) 둘 다 v864.2와 100% 동일. 껍데기만 HTML로 바뀔 뿐, 사용자 경험은 변하지 않아야 함.

---

## 📦 핵심 산출물 (절대 삭제 금지)

`docs/handoff/` 폴더의 3개 JSON — Cowork Sub-Agent 3인이 2026-04-21 추출한 **프로젝트 설계도**

| 파일 | 용도 |
|------|------|
| `docs/handoff/v864_2_structure.json` | v864.2 UI 구조 (메뉴/탭/툴바/Mixin) |
| `docs/handoff/feature_matrix.json` | 85개 기능 매핑 (Tkinter → FastAPI → JS) |
| `docs/handoff/design_tokens.json` | 디자인 토큰 (색상/폰트/간격) |

---

## 🏗️ 아키텍처 규칙 (절대 원칙)

### Rule 1: v864.2 비즈니스 로직 재활용 (수정 금지)
- `engine_modules/`, `features/`, `parsers/`, `utils/` 코드 **수정 금지**
- FastAPI는 기존 handler 함수를 **HTTP로 감싸는 얇은 wrapper**만 담당
- 이유: v864.2는 실사용 검증된 코드. 리팩토링 = 버그 양산

### Rule 2: UI/Logic 완전 분리
- `backend/` = FastAPI + 기존 로직 재활용
- `frontend/` = HTML/CSS/JS (순수 UI만, 비즈니스 로직 금지)

### Rule 3: Feature Parity 100%
- `feature_matrix.json`의 85개 기능 중 단 하나도 누락 금지
- optional 11개는 "준비 중" 메시지라도 UI상 표시

### Rule 4: 에러 처리 의무
- 모든 FastAPI 엔드포인트: try/except + HTTPException
- 모든 JS fetch: try/catch + 사용자 Toast 알림
- 빈 화면(blank screen) 절대 금지

### Rule 5: 300줄 이상 파일 — Edit 툴 직접 수정 절대 금지
> ⚠️ **사고 이력:** sqm-inline.js Edit 툴 수정 → 4KB로 붕괴 (2026-04-27)
> 5차 세션 전수검사에서 49개 파일 truncated 발견 → git 복구 (2026-05-04)

**올바른 절차 (반드시 Python 스크립트 사용):**
```python
with open(SRC, 'r', encoding='utf-8') as f: c = f.read()
c = c.replace(OLD, NEW, 1)
raw = c.encode('utf-8').replace(bytes([0x5c,0x21]), bytes([0x21]))  # \! 오염 방지
with open(DEST, 'w', encoding='utf-8', newline='\n') as f: f.write(raw.decode('utf-8'))
# JS 파일은 반드시: node --check <파일>
# Python 파일은 반드시: python -m py_compile <파일>
```

### Rule 6: git 작업은 반드시 Windows CMD에서 직접 실행
- VM(Linux 쉘)에서 git commit/push 금지 — GIT_INDEX_FILE 사고 재발 방지
- 항상 사장님이 CMD에서 직접 실행

---

## 🛠️ 기술 스택

| 계층 | 기술 |
|------|------|
| Desktop Shell | **PyWebView 5.1.0** |
| Backend | **FastAPI 0.104.1** + Uvicorn 0.24.0 |
| Frontend | **Vanilla HTML/CSS/JS** (프레임워크 없음) |
| Data | **pandas 2.1.3 + openpyxl 3.1.2 + SQLite** |
| AI | **Google Gemini** (PDF 파싱 / OCR) |
| Packaging | **PyInstaller 6.2.0** (EXE 단일 파일) |

**❌ 쓰지 말 것:** React/Vue/Svelte, TypeScript, Tailwind CSS, Docker

---

## 🎨 디자인 규칙

- **기본 테마:** Dark (darkly) — v864.2와 동일, localStorage `sqm_theme` 우선
- **토글:** Dark/Light 둘 다 지원 (우상단 버튼)
- **폰트:** Malgun Gothic (맑은 고딕) + Segoe UI fallback
- **아이콘:** 이모지 기반 (📦 📥 📤 📊) — 별도 라이브러리 의존 없음
- **색상:** `design-tokens.css` CSS 변수만 사용, 하드코딩 금지

---

## 📁 실제 디렉토리 구조 (2026-05-05 현재)

```
SQM_v866_CLEAN/
├── CLAUDE.md                    ← 이 파일 (영구 메모리)
├── main_webview.py              ← PyWebView 앱 진입점
├── 실행.bat                     ← Windows 실행 스크립트
├── sqm_inventory.db             ← SQLite DB (실데이터)
├── SMQ 입,출고 재고관리 파일_int.xlsx  ← 통합 Excel (INVENTORY 단일시트)
│
├── docs/handoff/                ← 설계도 3종 (수정 금지)
│   ├── v864_2_structure.json
│   ├── feature_matrix.json
│   └── design_tokens.json
│
├── backend/
│   ├── main.py                  ← FastAPI 앱
│   ├── requirements.txt
│   └── api/                     ← 엔드포인트 28개 파일
│       ├── __init__.py          ← 17개 라우터 등록
│       ├── actions.py           ← /api/action/* (LOT Excel, integrity 등)
│       ├── actions2.py          ← /api/action2/* (톤백 Excel, outbound 등)
│       ├── actions3.py          ← /api/action3/* (Invoice Excel 등)
│       ├── allocation_api.py    ← /api/allocation/*
│       ├── dashboard.py         ← /api/dashboard/stats, alerts
│       ├── inbound.py           ← /api/inbound/pdf (PDF 입고)
│       ├── inventory_api.py     ← /api/inventory, /api/tonbags
│       ├── inventory_adjust_api.py ← /api/inventory/adjust
│       ├── refresh_excel_api.py ← /api/inventory/refresh-excel-status
│       ├── template_ai_api.py   ← /api/inbound/templates/generate-from-docs
│       └── (기타 19개)
│
├── frontend/
│   ├── index.html               ← 단일 페이지 앱 (SPA)
│   ├── design-tokens.css        ← CSS 변수 (색상/폰트/간격)
│   └── js/
│       ├── sqm-core.js          ← ENDPOINTS 67개, renderPage, Toast, API
│       ├── sqm-inventory.js     ← 재고목록 탭 + MXBG 톤백모달
│       ├── sqm-allocation.js    ← 배분(Allocation) 탭
│       ├── sqm-picked.js        ← 픽업(Picked) 탭
│       ├── sqm-logistics.js     ← 물류 6탭 (입고/출고/반품/이동/로그/스캔)
│       ├── sqm-tonbag.js        ← 톤백 탭 (대형, 4551줄)
│       ├── sqm-onestop-inbound.js ← OneStop 입고 wizard
│       └── sqm-inline.js.bak_presplit  ← 분할 전 원본 백업
│
├── features/ai/
│   ├── gemini_parser.py         ← Invoice/BL/DO PDF 파싱
│   ├── gemini_utils.py          ← PRODUCT_MAPPING (MIC/CRY/LHT)
│   ├── ocr_auto_tuner.py        ← GeminiCallGate (Circuit Breaker)
│   └── carrier_templates/       ← 선사별 BL 템플릿 (Layer 1)
│       ├── one.py, hapag.py, mersk.py, msc.py, hmm_cmacgm.py, generic.py
│
├── parsers/
│   ├── allocation_parser.py     ← Allocation Excel 파싱
│   └── document_parser_modular/
│       └── invoice_mixin.py     ← Invoice 파싱 (_detect_product_code 동적 감지)
│
├── engine_modules/              ← v864.2 원본 (수정 금지)
├── utils/                       ← v864.2 원본 (수정 금지)
│
├── resources/templates/
│   └── allocation/              ← 고객사 Allocation 양식 (3개)
│       ├── jakarta_9col.json + .xlsx    (Jakarta 계열, 9컬럼)
│       ├── song_aaa_10col.json + .xlsx  (Song/LGES + AAA/CATL, 10컬럼)
│       └── woo_ptlbm_13col.json + .xlsx (Woo/PTLBM, 13컬럼)
│
├── tests/
│   ├── test_phase5_parity.py    ← 44개 패리티 회귀 테스트
│   ├── test_sample_parity.py    ← 6개 샘플 정합성 테스트
│   └── (기타 8개)
│
└── scripts/
    └── refresh_excel_status.py  ← DB → _int.xlsx STATUS 컬럼 일괄 갱신
```

---

## 🗺️ Phase 로드맵 (v866 전체)

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 0 | Safety Net 구축 (pytest, smoke test) | ✅ 완료 |
| Phase 1 | UI Manifest + 85 기능 매핑 | ✅ 완료 |
| Phase 1c | UI 요소 복구 (메뉴/툴바/사이드바) | ✅ 완료 |
| Phase 2 | TOP 3 엔드포인트 + 런타임 검증 | ✅ 완료 |
| Phase 3 | Dashboard KPI 실데이터 + 건강성 가시화 | ✅ 완료 |
| Phase 4 | 사이드바 9탭 + 메뉴 60개 + PDF 입고 배선 | ✅ 완료 |
| Phase 5 | 회귀 테스트 자동화 (v864.2 ↔ v866 비교) | ✅ 완료 |
| **Phase 6** | **EXE 빌드 + 배포 (PyInstaller 단일 실행파일)** | 🟡 **다음** |
| Phase 7 | 사장님 실사용 1주 + 버그 수집 | ⏳ 대기 |
| Phase 8 | 🏆 v866 공식 릴리스 (GY Logis 전환) | 🎯 최종 |

**전체 진행률 (2026-05-05 기준):** 약 85% (Phase 0~5 완료 + 다수 버그 수정)
**예상 릴리스:** 2026-05-25 (본업 병행 감안)

---

## ✅ 현재 완료된 주요 기능 현황

### JS 분할 아키텍처 (2026-05-05)
sqm-inline.js (391KB, 7133줄) → 6개 IIFE 파일로 분할 완료
- `sqm-core.js`: ENDPOINTS 67개, renderPage, showToast, apiCall, 상태관리
- `sqm-inventory.js`: 재고목록 + MXBG 톤백모달
- `sqm-allocation.js`: 배분 페이지
- `sqm-picked.js`: 픽업 페이지
- `sqm-logistics.js`: 물류 6탭
- `sqm-tonbag.js`: 톤백 탭 (대형)

파일간 공유 패턴: `window.*` 노출 + 각 파일 상단 alias preamble

### 제품 코드 지원 (2026-05-05)
| 제품코드 | 제품명 | 감지 키워드 |
|----------|--------|------------|
| MIC9000.00 | LITHIUM CARBONATE - BATTERY GRADE - MICRONIZED | micronized, mic9000 |
| CRY9000.00 | LITHIUM CARBONATE - BATTERY GRADE - CRYSTAL | crystal, cry9000 |
| LHT-B/450 | LITHIUM HYDROXIDE MONOHYDRATE - BATTERY GRADE | hydroxide, lht-b |

### Excel 통합 (2026-05-03)
- `SMQ 입,출고 재고관리 파일_int.xlsx` — IN/UNSOLD/SOLD 3시트 → INVENTORY 단일시트
- STATUS 컬럼 자동 관리: AVAILABLE(초록) / RESERVED(노란) / SOLD(빨강)

### Allocation 양식 (현재 4개, 2026-05-05 추가)
- jakarta_9col, song_aaa_10col, woo_ptlbm_13col, **woo_202606** (5행헤더블록 신규)
- 위치: `resources/templates/allocation/`

### Allocation 버그 수정 (2026-05-05)
- **Bug①** `outbound_mixin.py` LOT mode loop → UNIQUE 위반: 1행 INSERT로 수정
- **Bug②** `sqm-allocation.js` `_allocState` undefined → 빈화면: 모듈 내 선언 추가
- **Bug③** `queries.py` allocation-summary → inventory JOIN 추가: SAP NO/PRODUCT/WH 채움 + PICKED/SOLD 탭도 활성화
- **Bug④** `outbound_mixin.py` LOT mode → `inventory_tonbag.status` RESERVED 미갱신: executemany UPDATE 추가 (commit 9bc4463)
- **Bug⑤** Dashboard/Inventory AVAILABLE 오버카운트: `inventory.current_weight`(LOT레벨) → `inventory_tonbag.weight`(톤백레벨) 집계로 교정 + `reserved_mt`/`picked_mt` 필드 추가 + 재고현황 바 차트 렌더링 추가

### 사이드바 Inventory 하위메뉴 구조 (2026-05-05)
- 사이드바 Inventory 버튼 → 4개 하위메뉴 토글: Available / Allocation / Picked / Return
- 각 항목 배지: N개 톤백 · X.XXX MT 표시 (30초 자동 갱신)
- Available 전용 페이지 추가: AVAILABLE 상태 LOT 목록 (Avail/Rsv MT 컬럼)
- 관련 파일: `index.html`, `v864-layout.css`, `sqm-core.js`, `sqm-inventory.js`
- 백엔드: `dashboard.py` `/api/dashboard/sidebar-counts` 엔드포인트 추가
- JS 파일 분할 버그 수정: `sqm-inventory.js` 꼬리 truncation 복구, `sqm-picked.js` 잘못 포함된 inbound 코드 제거 → `sqm-logistics.js`로 이동

### 선사 BL 템플릿 (Layer 1)
- ONE, HAPAG, MAERSK, MSC, HMM/CMACGM, GENERIC (6개)
- 위치: `features/ai/carrier_templates/`

### 설계 결정 기록 (2026-05-05 사장님 확정) ← 방지책① 의무 기록
| 항목 | 결정 | 이유 |
|------|------|------|
| `current_weight` 샘플백 포함 | ✅ 포함 | 샘플백(is_sample=1)도 판매 가능 → 재고 정합성 필수 |
| Excel 내보내기 방식 | `exports/` 폴더 저장 + `os.startfile()` | PyWebView 5에서 StreamingResponse + `<a download>` 비동작 |
| `crud_mixin.py` 수정 | Rule 1 예외 허용 | 비즈니스 규칙 오류 교정 (샘플 제외가 잘못된 설계였음) |
| 버전 표기 | `v8.6.6` | 메이저.마이너.패치 표준 시맨틱 버저닝 |
| DB 경로 | `data/db/sqm_inventory.db` | 루트의 `sqm_inventory.db` 아님 — 주의 |

---

## 🔴 현재 미완료 — 최우선 처리 순서

### 1. 앱 재시작 후 확인 항목 (Bug④⑤ + 사이드바 검증)
- 완전 종료 후 재시작 (단순 새로고침 금지)
- Dashboard → 상단 "재고 현황" 바 차트 표시 확인 (Available/Reserved/Picked MT)
- alloc_test_v2_*.xlsx 중 1개 업로드 → Available↓ Reserved↑ 반영 확인
- Inventory탭 → Balance 옆 "Avail/Rsv(MT)" 컬럼: 초록=가용MT, 파랑=배분MT
- 배분 탭 RESERVED 행 SAP NO / PRODUCT / WH 데이터 표시 확인
- 사이드바 Inventory 클릭 → 하위메뉴(Available/Allocation/Picked/Return) 펼침 확인
- Available 메뉴 클릭 → AVAILABLE LOT 목록 표시 확인
- 배지(N개·X MT) 30초마다 자동 갱신 확인

### 2. Phase 6 — EXE 빌드
- PyInstaller spec 작성 → hidden imports 해결 → 빌드 테스트 → 실행 검증
- Gate: test_phase5_parity.py 44 passed + EXE 실행 시 FastAPI 정상 기동

---

## 🧪 Definition of Done (기능 이전 완료 기준)

1. ✅ JS syntax — `node --check`
2. ✅ Python syntax — `py_compile` 전수검사
3. ✅ 기능 일치 — v864.2와 같은 입력 → 같은 출력
4. ✅ 에러 처리 — 실패 시 Toast 알림
5. ✅ 롤백 가능 — git revert로 해당 기능만 되돌릴 수 있음

---

## 👤 개발자 정보

- **사용자:** Nam Ki-dong (남기동) — Practical Tech CEO
- **사업:** LPG 충전소(서울) + GY Logis 물류창고(광양) + 건설업
- **개발 실력:** 숙련된 Python 프로그래머 (SQM v864.2 직접 개발)
- **선호 설명:** 중학생 수준, 간결, 논리적 단계, 결정적 결론
- **OS:** Windows, D:\program 폴더, CMD 환경
- **협업:** Cowork (문서/이메일) + Claude Code (개발)

---

## 🚨 자주 하는 실수 방지

1. **v864.2 원본 수정** → 절대 금지. 복사본(`backend/legacy/`)만 수정
2. **MD 파일 인코딩** → 반드시 UTF-8. CP949(EUC-KR) 금지
3. **색상 하드코딩** → `design-tokens.css` 변수만 사용
4. **300줄↑ 파일 Edit 툴 수정** → Rule 5 참조, Python 스크립트 사용
5. **VM에서 git commit** → Rule 6 참조, Windows CMD에서만 실행
6. **세션 종료 전 전수검사 생략** → py_compile + node --check 필수
7. **설계 결정 이유 미기록** (방지책①) → 수정할 때마다 `왜`를 CLAUDE.md에 함께 기록. "당연하다"도 기록 대상
8. **코드 읽기 전 수정** (방지책②) → "버그같다" 판단해도 → 관련 코드 주석/원인 먼저 확인 → 이해 후 수정. 추측 금지
9. **300줄↑ 파일 작은 수정도 Edit 툴 사용** (방지책③) → 예외 없이 Python 스크립트 사용 (Rule 5 재확인)

---

## 🤖 루비(Ruby) 행동 규칙 — 영구 적용 (2026-04-30 사장님 승인)

### Rule A — 추천 먼저, 질문은 그 다음
- 형식: "**루비의 추천:** [선택지] — 이유: [한 줄] / 확인: [A/B/C]"
- 사장님이 다른 선택 시 → "다른 방향을 선택하신 이유가 있으신가요?" (강요 아님)

### Rule B — 추천 강도 구분
- **기술 결정** (코드/아키텍처/빌드): 강하게 → "이렇게 하세요" 톤
- **비즈니스 결정** (일정/예산/배포): → "이게 유리해 보이지만, 사장님 상황이 우선" 톤

### Rule C — 틀렸을 때 즉시 학습 + CLAUDE.md 자동 기록
- "이전 판단은 [X]였는데, 맞는 방향은 [Y]였습니다 — 다음부터 반영합니다"

### Rule D — 확신 없음 명시
- 60% 이하 확신 시 → "확신 없음 (약 X%)" 표시 후 최선 추천

### Rule E — 응답 포맷 (매 응답 필수)
- 첫 줄: `[Question] — YYYY-MM-DD HH:MM` / `[Intent]` / `[Response]`
- 마지막: 실용 영어/베트남어 문장 1개 (발음 포함)

---

### 루비 학습 로그
| 날짜 | 틀린 판단 | 올바른 방향 | 반영 |
|------|-----------|-------------|------|
| 2026-05-02 | Rule A 위반 — 질문 먼저 | 추천 먼저 후 질문 | Rule A 재확인 |
| 2026-05-04 | [Question]/[Intent]/시간 포맷 누락 | 매 응답 헤더 필수 | Rule E 추가 |
| 2026-05-04 | GIT_INDEX_FILE로 커밋 → 400개 파일 삭제 | git은 CMD에서만 | Rule 6 추가 |
| 2026-05-04 | 전수검사 미실시 → truncated 파일 방치 | 세션 종료 전 전수검사 필수 | Rule 5 강화 |
| 2026-05-05 | CLAUDE.md에 v865 표기 방치 | 폴더명(v866)과 버전 일치 필수 | 전면 재작성 |
| 2026-05-05 | 코드 주석 미확인 → 샘플백 포함 여부 flip-flop 3회 | 수정 전 코드+주석 반드시 먼저 읽기 | 방지책② 추가 |
| 2026-05-05 | StreamingResponse PyWebView 비호환 재발 | exports/+os.startfile() 패턴만 사용 | 설계결정 기록 |

---

**버전:** v866
**최종 수정:** 2026-05-05 (방지책①②③ + 설계결정 기록 추가)
**작성자:** Ruby (Senior Software Architect)
**프로젝트 폴더:** `D:\program\SQM_inventory\SQM_v866_CLEAN`
**GitHub:** `https://github.com/kidongnam1/sqm_3`