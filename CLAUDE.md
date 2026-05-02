# SQM Inventory v865 — PyWebView Migration Project

> **이 파일은 Claude Code가 프로젝트를 작업할 때 자동으로 읽는 영구 메모리입니다.**
> 세션이 바뀌어도 이 내용은 기억됩니다. 수정 시 신중하게.

---

## 🧠 프로젝트 전용 메모리 규칙 (v865 한정) — 최우선

> **등록일:** 2026-04-21 12:13 KST
> **수정일:** 2026-04-28 KST (주 작업 폴더 변경: Claude_SQM_v865 → SQM_v865_CLEAN / GitHub sqm_3 초기 커밋 완료)
> **등록자:** Nam Ki-dong (사장님)
> **승인자:** Ruby (Senior Software Architect)

> ⚠️ **계층 안내:** 범용(모든 프로그램 공통) 규칙은 **상위 `F:\program\CLAUDE.md`** 에 있음. 이 파일은 **v865 프로젝트 전용** 규칙만 담음.
> Claude Code는 작업 폴더에서 부모 방향으로 올라가며 모든 CLAUDE.md를 자동으로 합쳐 읽으므로, 두 파일은 자동 상속됨.

> 🗂️ **주 작업 폴더 변경 (2026-04-28):** `Claude_SQM_v865\` → **`SQM_v865_CLEAN\`** (현재 폴더)
> GitHub: `https://github.com/kidongnam1/sqm_3` (main 브랜치, 초기 커밋 완료)
> `Claude_SQM_v865\`는 참조용으로만 유지. 앞으로 모든 개발은 이 폴더에서 진행.

**v865 프로젝트 작업 시 반드시 "이 프로젝트 폴더(현재 폴더 = `SQM_v865_CLEAN\`)"의 내용을 전부 참조·반영한다. 절대경로 하드코딩 금지.**

구체적으로:

1. **작업 시작 전 필수 확인 (이 프로젝트 한정):**
   - `./CLAUDE.md` (이 파일 — v865 규칙/아키텍처)
   - `./docs/handoff/v864_2_structure.json` (UI 구조)
   - `./docs/handoff/feature_matrix.json` (85개 기능 매핑)
   - `./docs/handoff/design_tokens.json` (디자인 토큰)
   - `./TIER1_PLAN.md` (현재 Tier 실행 지시서 — 있을 경우)

2. **코드 작성 시 필수 일치:**
   - 색상/폰트/간격 → `design_tokens.json` 값만 사용 (하드코딩 금지)
   - 기능 → `feature_matrix.json`의 엔드포인트/핸들러 이름과 일치
   - 비즈니스 로직 → `./engine_modules/`, `./features/`, `./parsers/`, `./utils/` 재활용

3. **새 파일/기능 추가 시 필수 검증:**
   - 이 폴더에 이미 존재하는지 `Glob`/`Grep`로 먼저 확인
   - 중복 생성 금지 (Dead code 방지)
   - 파일 위치는 "디렉토리 구조 (목표 상태)" 섹션을 따름

4. **모호한 경우 처리:**
   - 폴더 내용과 사장님 지시가 충돌하면 → 즉시 질문 (가정 금지)
   - 폴더에 정보가 없으면 → "없음"이라고 명확히 보고

5. **다른 프로젝트와의 격리:**
   - 이 프로젝트 외부 폴더(예: 다른 v8xx, LPG 자동화 등)에서 작업할 때는 **이 파일의 규칙을 적용하지 말 것**
   - v865 핸드오프 JSON 3종은 **이 프로젝트 안에서만** 의미 있음

**위반 시 결과:** 규칙 위반 코드는 그 자리에서 롤백. 예외 없음.

---

## 🎯 프로젝트 목표

Tkinter + ttkbootstrap로 만들어진 **SQM Inventory v864.2** (광양 GY Logis 물류창고 재고관리 시스템)를 **PyWebView + HTML/CSS/JS + FastAPI** 기반 **v865**으로 마이그레이션.

**핵심 원칙:** 겉모습(UI)과 기능(Behavior) **둘 다 v864.2와 100% 동일**해야 함. 껍데기만 HTML로 바뀔 뿐, 사용자 경험은 변하지 않아야 함.

---

## 📦 핵심 산출물 (DO NOT DELETE)

`docs/handoff/` 폴더에 3개의 핵심 JSON 파일이 있습니다. 이것은 Cowork 모드에서 Sub-Agent 3명이 2026-04-21에 추출한 **프로젝트의 설계도**입니다.

| 파일 | 용도 | 절대 삭제 금지 |
|---|---|---|
| `docs/handoff/v864_2_structure.json` | v864.2 메인창 UI 구조 (메뉴 5개, 탭 9개, 툴바 7개, Mixin 18개) | ✅ |
| `docs/handoff/feature_matrix.json` | **85개 기능 완전 매핑표** (Tkinter callback → FastAPI endpoint → JS handler) | ✅ |
| `docs/handoff/design_tokens.json` | 디자인 토큰 (156개 색상, 17개 테마, 폰트, 간격) | ✅ |

**작업 시작 전 반드시 이 3개 파일을 먼저 읽을 것.**

---

## 🏗️ 아키텍처 규칙 (절대 원칙)

### Rule 1: v864.2 비즈니스 로직은 그대로 재활용
- `engine_modules/`, `features/`, `parsers/`, `utils/`의 코드는 **수정 금지**
- FastAPI는 기존 handler 함수를 **HTTP로 감싸는 얇은 wrapper**만 담당
- 이유: v864.2는 이미 실사용 중인 검증된 코드. 리팩토링 = 버그 양산

### Rule 2: UI/Logic Decoupling
- `backend/` = FastAPI + 기존 로직 재활용
- `frontend/` = HTML/CSS/JS (순수 UI만)
- `frontend/`에 비즈니스 로직 금지 (단, 간단한 표시/숨김 상태는 허용)

### Rule 3: Feature Parity 100%
- `feature_matrix.json`의 85개 기능 중 **단 하나도 누락 금지**
- optional 11개는 "준비 중" 메시지라도 UI상 표시할 것

### Rule 4: 에러 처리 의무
- 모든 FastAPI 엔드포인트는 try/except + HTTPException
- 모든 JS fetch는 try/catch + 사용자 Toast 알림
- 빈 화면(blank screen) 절대 금지

---

## 🚦 마이그레이션 전략: 3-Tier Progressive

**큰 바위를 한 번에 움직이지 말고, 작은 돌로 쪼개서 옮긴다.**

### 🛡️ Tier 1 (Day 1~2): Safe Zone 구축
- PyWebView 창 + FastAPI skeleton + DB 연결만
- 메뉴/사이드바는 HTML/CSS로 그려놓고 클릭 시 "준비 중" 메시지
- **EXE 빌드 성공**이 Tier 1의 Definition of Done
- 상세: `TIER1_PLAN.md` 참조

### 🎯 Tier 2 (Day 3~5): Top 10 기능 이전
- 사장님(Nam Ki-dong) 실사용 상위 10개 기능만
- 각 기능마다 v864.2와 결과 비교 검증 필수
- 문제 발생 시 해당 기능만 git revert (전체 롤백 아님)

### 🏁 Tier 3 (Day 6~10): 나머지 75개 배치 이전
- 25개씩 3배치로 나눔
- 각 배치 완료 후 사장님 검수 → 다음 배치 진입
- optional 11개는 마지막 배치에 포함

---

## 📁 디렉토리 구조 (목표 상태)

```
Claude_SQM_v864_3/
├── CLAUDE.md                        ← 이 파일 (프로젝트 영구 메모리)
├── TIER1_PLAN.md                    ← Tier 1 실행 지시서
├── docs/
│   └── handoff/                     ← Cowork 산출물 (수정 금지)
│       ├── v864_2_structure.json
│       ├── feature_matrix.json
│       └── design_tokens.json
├── .claude/
│   ├── settings.local.json
│   └── commands/                    ← 커스텀 slash commands
│       ├── tier1-start.md
│       ├── tier2-implement.md
│       ├── verify-parity.md
│       └── feature-status.md
├── backend/                         ← FastAPI 앱
│   ├── main.py
│   ├── api/                         ← 엔드포인트 (얇은 wrapper)
│   ├── legacy/                      ← v864.2 handlers 그대로 복사
│   └── requirements.txt
├── frontend/                        ← HTML/CSS/JS
│   ├── index.html
│   ├── design-tokens.css            ← design_tokens.json에서 변환
│   ├── components/                  ← 메뉴바, 사이드바 등
│   ├── pages/                       ← 탭별 페이지
│   └── js/
│       ├── handlers/                ← onclick 핸들러 (85개)
│       ├── router.js
│       ├── api-client.js
│       └── state.js
├── engine_modules/                  ← v864.2 원본 (수정 금지)
├── features/                        ← v864.2 원본 (수정 금지)
├── parsers/                         ← v864.2 원본 (수정 금지)
└── utils/                           ← v864.2 원본 (수정 금지)
```

---

## 🛠️ 기술 스택

| 계층 | 기술 | 이유 |
|---|---|---|
| Desktop Shell | **PyWebView 5.1.0** | Python 생태계 유지, exe 빌드 용이 |
| Backend | **FastAPI 0.104.1** + Uvicorn 0.24.0 | 비동기 지원, 타입 안정성 |
| Frontend | **Vanilla HTML/CSS/JS** | 프레임워크 없이 — 빌드 스텝 최소화, 학습 곡선 제거 |
| Data | **pandas 2.1.3 + openpyxl 3.1.2 + SQLite** | v864.2와 동일 |
| Packaging | **PyInstaller 6.2.0** | exe 단일 파일 배포 |

### ❌ 쓰지 말 것 (의도적 선택)
- React/Vue/Svelte — 복잡도 증가, 빌드 스텝 필요
- TypeScript — Python 개발자 학습 비용
- Tailwind CSS — design_tokens.json으로 자체 디자인 시스템 보유
- Docker — Windows 데스크톱 단일 사용자 환경에 과함

---

## 🎨 디자인 규칙

- **기본 테마:** `darkly` (Dark) — v864.2와 동일
- **토글:** Dark/Light 둘 다 지원 필수 (우상단 버튼)
- **폰트:** Malgun Gothic (맑은 고딕) + Segoe UI fallback
- **아이콘:** 이모지 기반 (예: 📦 📥 📤 📊) — 별도 아이콘 라이브러리 의존 없음
- **색상:** `design_tokens.json`의 값만 사용. 하드코딩 금지. `design-tokens.css`의 CSS 변수로 참조

---

## 🗺️ 전체 Phase 로드맵 (v865 종단 지도)

| Phase | 이름 | 상태 |
|---|---|---|
| Phase 0 | Safety Net 구축 (pytest, smoke test) | ✅ 완료 |
| Phase 1 | UI Manifest + 85 기능 매핑 | ✅ 완료 |
| Phase 1c | UI 요소 복구 (메뉴/툴바/사이드바) | ✅ 완료 |
| Phase 2 | TOP 3 엔드포인트 + 런타임 검증 (Step 1~3) | ✅ 완료 |
| Phase 3 | Dashboard KPI 실데이터 + 건강성 가시화 | ✅ 완료 |
| **Phase 4** | **사이드바 9탭 + 메뉴 60개 + PDF 입고 배선** | ✅ **완료** |
| **Phase 5** | **회귀 테스트 자동화 (v864.2 ↔ v865 비교)** | ✅ **완료** |
| **Phase 6** | **EXE 빌드 + 배포 (PyInstaller 단일 실행파일)** | 🟡 **다음** |
| Phase 7 | 사장님 실사용 1주 + 버그 수집 | ⏳ 대기 |
| Phase 8 | 🏆 v865 공식 릴리스 (GY Logis 전환) | 🎯 최종 |

**전체 진행률 (2026-04-27 기준):** 약 80% (Phase 0~5 완료)
**예상 최종 릴리스일:** 2026-05-09 (이상) ~ 2026-05-25 (현실, 본업 병행 감안)

---

## 🚀 Phase 4 완료 현황 (2026-04-22 최종)

### Phase 4 핵심 산출물
- **sqm-inline.js:** 56 KB 단일 IIFE — ENDPOINTS 67개 (HTML data-action 1:1 매핑), 9탭 라우터, 캐시버스팅 `?v=864.3.3`
- **backend/api/inventory_api.py:** 신규 (307 lines) — `/api/inventory`, `/api/allocation`, `/api/tonbags`, `/api/scan/process`, `/api/health`
- **backend/api/inbound.py:** POST `/api/inbound/pdf` (base64 → PyMuPDF → DB)
- **backend/api/dashboard.py:** GET `/api/dashboard/stats`, GET `/api/dashboard/alerts`
- **backend/api/menubar.py:** POST `/api/menu/-on-settings`
- **backend/api/__init__.py:** 총 17개 라우터 등록
- **index.html:** 완전한 HTML + 캐시버스팅
- **실행.bat:** PyWebView 정상종료 오탐(exit code 1) 수정 → `errorlevel 2`
- **보고서:** `REPORTS/PHASE4_COMPLETE.md`, `REPORTS/PHASE4_FINAL_FIX.md`

### Phase 4 검증 현황
- ✅ JS syntax (node --check): PASS
- ✅ Python syntax (5개 파일): ALL PASS
- ✅ HTML data-action coverage: 68/68 (0 missing)
- ✅ Backend routers: 17개 등록
- ✅ bash `\!` 오염: 0건

## ✅ Phase 5 완료 현황 (2026-04-27)

### Phase 5 핵심 산출물
- **tests/test_phase5_parity.py:** 44개 패리티 회귀 테스트 (44 passed)
  - 버그 5종 자동 감지: null바이트/\!오염/파일잘림/mxbg_pallet키명/lot_sqm미전달/update_dict비컬럼
- **inbound.py 버그 수정 완료:**
  - Gemini lot dict: `tonbag_count` → `mxbg_pallet` 키명 통일
  - Gemini 프롬프트: `mxbg_pallet` + `lot_sqm` 항목 추가
  - Invoice/BL/DO update_dict: 실제 DB 컬럼 기준 재확인 (voyage, do_no, invoice_date 등 유효 확인)
- **전수 패리티 감사:** Tier-1A / Tier-1B / Tier-2 → DB 17개 필드 완전 추적 완료

## 🎯 Phase 6 Next Target

- **목표:** PyInstaller 단일 EXE 파일 빌드 — Windows 배포용
- **범위:** PyInstaller spec 작성, hidden imports 해결, 빌드 테스트, 실행 검증
- **Gate Condition:** test_phase5_parity.py 44 passed + EXE 실행 시 FastAPI 정상 기동
- **새 세션 시작:** CLAUDE.md 읽고 Phase 6 진입

---

## 🧪 품질 기준 (Definition of Done)

각 기능 이전 완료로 인정받으려면:

1. ✅ **UI 일치** — v864.2와 SSIM 0.85 이상 (자동 스크린샷 비교)
2. ✅ **기능 일치** — 같은 입력 → 같은 출력 (v864.2와 회귀 테스트)
3. ✅ **에러 처리** — 실패 시 사용자에게 명확한 Toast 메시지
4. ✅ **로그** — 주요 액션은 `features/reports/` 로그 파일에 기록
5. ✅ **롤백 가능** — git revert로 해당 기능만 되돌릴 수 있어야 함

---

## 👤 개발자 정보

- **사용자:** Nam Ki-dong (남기동)
- **역할:** Practical Tech CEO — LPG 충전소(서울) + GY Logis 물류창고(광양) + 건설업
- **개발 실력:** 숙련된 Python 프로그래머 (SQM v864.2 직접 개발)
- **선호 설명 방식:** 중학생 수준, 간결, 논리적 단계, 결정적 결론
- **OS:** Windows, F:\ 드라이브 사용, CMD 환경
- **협업 도구:** Cowork(문서/이메일/학습) + **Claude Code(개발)**

---

## 🚨 자주 하는 실수 (방지)

1. **v864.2 원본 수정** → 절대 금지. `backend/legacy/`로 복사 후 수정 (복사본만)
2. **MD 파일 인코딩** → 반드시 UTF-8. CP949(EUC-KR) 금지
3. **색상 하드코딩** → 항상 `design-tokens.css` 변수 사용
4. **빈 화면 배포** → 모든 영역에 로딩/에러/빈상태 UI 필수
5. **테스트 없이 다음 Tier 진입** → 각 Tier 종료 시 사장님 승인 필수
6. **대용량 JS 파일(100KB↑) Edit 툴 직접 수정 금지** → 반드시 Python 스크립트로 처리

   > ⚠️ **사고 이력 (2026-04-27):** `sqm-inline.js` (310KB)를 Edit 툴로 수정하다
   > 파일 말미가 잘려 4KB로 붕괴. sqm_2 백업으로 복구 후 Python 원자적 쓰기로 재적용.
   >
   > **올바른 절차:**
   > ```python
   > # 1. 백업 원본 읽기
   > with open(SRC, 'r', encoding='utf-8') as f: c = f.read()
   > # 2. str.replace() 로 변경
   > c = c.replace(OLD, NEW, 1)
   > # 3. 바이트 레벨 오염 제거 (bash heredoc → \! 오염 주의)
   > raw = raw.replace(bytes([0x5c, 0x21]), bytes([0x21]))
   > # 4. 단일 write — 절대 Edit 툴 사용 금지
   > with open(DEST, 'w', encoding='utf-8', newline='\n') as f: f.write(c)
   > # 5. node --check 로 문법 검증 필수
   > ```
   >
   > **백업 위치:** `sqm_2/Claude_SQM_v864_3/frontend/js/sqm-inline.js` (Phase 5 완료본, 308KB, 2026-04-24)

---

## 📞 문제 발생 시

1. `feature_matrix.json`에서 해당 기능의 `tkinter_source` 확인
2. v864.2 원본 코드 참조
3. `docs/handoff/`의 3개 JSON 재확인
4. 여전히 막히면 → 사장님께 구체적 질문 (가정하지 말 것)

---

**버전:** v865
**작성일:** 2026-04-21
**작성자:** Ruby (Senior Software Architect Mode)
**기반:** Cowork Sub-Agent 3인 산출물 (Agent 1 구조분석, Agent 2 기능추출, Agent 3 디자인토큰)

---

## 🤖 루비(Ruby) 행동 규칙 — 영구 적용 (2026-04-30 사장님 승인)

> 이 규칙은 Nam Ki-dong 사장님과 루비가 2026-04-30 세션에서 합의한 내용입니다.
> 모든 세션에서 반드시 적용합니다. 예외 없음.

### Rule A — 추천 먼저, 질문은 그 다음
- 루비가 사장님께 선택을 물을 때는 **반드시 루비의 Best Practice를 먼저 제시**한 후 질문
- 형식: "**루비의 추천:** [선택지] — 이유: [한 줄 근거] / 확인 부탁드립니다: [A/B/C]"
- 사장님이 루비 추천과 다른 선택을 하면 → "다른 방향을 선택하신 이유가 있으신가요?" 한 마디 질문 (강요 아님, 학습 목적)

### Rule B — 추천 강도 구분
- **기술 결정** (코드 구조, 아키텍처, 빌드, 성능): 루비가 강하게 추천 → "이렇게 하세요" 톤
- **비즈니스 결정** (일정, 우선순위, 예산, 배포 타이밍): 옵션 제시 → "이게 유리해 보이지만, 사장님 상황이 우선입니다" 톤
- **경계 모호한 경우** (예: "언제 배포?") → 루비가 판단해서 강도 결정. 별도 질문 안 함

### Rule C — 틀렸을 때 즉시 학습 + CLAUDE.md 자동 기록
- 루비 추천이 틀렸다고 확인되면 → "이전 판단은 [X]였는데, 맞는 방향은 [Y]였습니다 — 다음부터 반영합니다"로 명시 정정
- 중요한 학습 내용은 사장님 확인 없이 **루비가 자동으로 CLAUDE.md에 기록**
- 기록 위치: 이 섹션 하단 `### 루비 학습 로그`

### Rule D — 확신 없음 명시
- 루비가 60% 이하 확신일 때는 → "확신 없음 (약 X%)" 표시 후 그래도 최선 추천 제시
- 100% 확신처럼 말하는 것은 사장님을 오도하는 행위 → 금지

---

### 루비 학습 로그
| 날짜 | 틀린 판단 | 올바른 방향 | 반영 내용 |
|---|---|---|---|
| (기록 시작) | — | — | — |
| 2026-05-02 | Rule A 위반 — 메뉴 분리 제안 시 질문 먼저 함 | 추천안 먼저 제시 후 질문 | Rule A 재확인 완료 |

---

## 🔜 다음 세션 인수인계 (2026-05-02 기준)

> **새 세션 시작 시 이 섹션부터 읽을 것.**

### 완료된 작업 (v8.6.6)
- ✅ ONE BL 파싱 3종 버그 수정 (bl_mixin.py)
- ✅ Gemini DO hint mrn/msn 4선사 추가 (ai_fallback.py)
- ✅ parse_alarm.py 신규 (CRITICAL/WARNING/INFO 알람 시스템)
- ✅ inbound.py parse_alarm 연결 + parse_alarms 응답 키 추가
- ✅ carrier_rules DB 테이블 생성 + ONE BL ONEY 패턴 등록
- ✅ Phase 1 Release Hardening 4-에이전트 완료 → CRITICAL 3건 수정
  - inbound.py inbound_bl() 함수 복원 (1945→1974줄)
  - sqm-inline.js null 바이트 13,497개 제거
  - sqm-onestop-inbound.js null 바이트 16,756개 제거

### 🔴 미완료 — 최우선 처리
1. **git push** — `git_final_push.bat` 더블클릭으로 완료
   - index.lock 문제 있었음. 배치 파일이 자동 처리함
   - 커밋 메시지: COMMIT_MSG_866.txt + COMMIT_MSG_phase1.txt

2. **메뉴 재구조화** (이 세션에서 중단 → 다음 세션 작업 예정)
   - 대상 파일: `frontend/index.html` + `frontend/js/sqm-inline.js`
   - **절대 주의: sqm-inline.js (321KB) Edit 툴 직접 수정 금지 → Python 스크립트 사용**

   **변경 내용 10가지 (2026-05-02 전체 검토 완료):**
   ```
   ━━━ 구조 변경 (메뉴 이동/승격) ━━━
   ① Allocation → 최상위 독립 메뉴 승격 (입고↔출고 사이)
      - 포함: Allocation 입력, 승인 대기, 예약 반영, 승인 이력 조회
      - LOT Allocation 톤백 현황 (설정>제품관리에서 이동)

   ② 출고 메뉴 슬림화 → 실행 메뉴만 유지
      - 남기는 것: 즉시 출고, Picking List, 조회/관리
      - 제거: Allocation(①), Sales Order(③)

   ③ Sales Order → 보고서 메뉴로 이동
      - onSalesOrderUpload → 보고서 > 📊 Sales Order 신규 서브메뉴
      - onSalesOrderDN 중복 제거 (보고서>송장/DN에만 유지)

   ④ BL 선사 도구 → 파일 메뉴에서 입고 메뉴로 이동
      - 이유: 입고 파싱 작업과 직접 관련

   ⑤ Gemini AI → 파일 메뉴에서 설정/도구로 이동
      - API 키 설정, 연결 테스트, AI 채팅 모두 이동

   ⑥ 톤백 위치 매핑 → 입고 메뉴에서 재고>🏭 창고관리 신규 서브메뉴로 이동

   ⑦ 대량 이동 승인 → 입고 메뉴에서 재고>🏭 창고관리로 이동

   ━━━ 중복 제거 ━━━
   ⑧ onIntegrityCheck 중복 제거
      - 입고>정합성 항목 제거, 설정/도구>정합성만 유지

   ⑨ onInboundTemplateManage 중복 제거
      - 입고 직속 버튼 제거, 입고>조회/관리 안에만 유지

   ⑩ onSalesOrderDN 중복 제거
      - 출고>Sales Order 항목 제거, 보고서>송장/DN에만 유지
   ```
   **최종 메뉴 순서:** 파일 / 입고 / 📋Allocation(NEW) / 출고 / 재고 / 보고서 / 설정/도구 / 도움말

3. **Picking List 신규 파서** (이 세션에서 분석 완료 → 구현 예정)
   - 샘플: `temp/LBM AP - SO 3073 - Picking list1.pdf`
   - 발행: SOQUIMICH LLC. (SQM 한국법인, SAP 자동생성)
   - 방향: 출고 (광양→해외), 아웃바운드 문서
   - 아키텍처: picking_mixin.py 신규 + ai_fallback.py parse_picking_ai() 추가
   - 핵심 필드: outbound_id, sales_order, customer_ref, plan_loading_date,
               port_of_loading/discharge, batch_no[], batch_qty, packing_type,
               net_weight_kg, gross_weight_kg
   - 배치 행 정규식: `Quantity:\s*(\d+\.?\d*)\s*(MT|KG)\s+Batch number:\s*(\d+)`

### 현재 DB 상태
- carrier_rules 테이블: 코드 자동 마이그레이션 준비됨, 앱 최초 기동 시 생성
- sqm_inventory.db: .gitignore에 추가됨 (git 추적 제외)

### 파일 위치 요약
| 용도 | 경로 |
|------|------|
| 메뉴 HTML | frontend/index.html |
| JS 로직 | frontend/js/sqm-inline.js (321KB, Python 수정 필수) |
| 알람 시스템 | utils/parse_alarm.py |
| 입고 API | backend/api/inbound.py (1974줄, 정상) |
| PL 파서 | parsers/document_parser_modular/packing_mixin.py |
| PL 샘플 | temp/LBM AP - SO 3073 - Picking list1.pdf |
| Phase1 보고서 | REPORTS/phase1_summary.md |

