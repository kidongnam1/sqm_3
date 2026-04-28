# 🛡️ Tier 1: Safe Zone 구축 — 실행 지시서

> **Claude Code에서 이 파일을 열고 "이 계획대로 실행해줘"라고 말씀하시면 됩니다.**

---

## 🎯 Tier 1 목표 (Definition of Done)

**"빈 껍데기 PyWebView 앱이 exe로 빌드되어 실행된다."**

- ✅ PyWebView 창이 열린다
- ✅ FastAPI 서버가 백그라운드에서 실행된다
- ✅ DB 연결이 정상이다
- ✅ HTML 메뉴바/사이드바/상단 툴바가 v864.2와 동일한 모양으로 그려진다
- ✅ 버튼 클릭 시 "준비 중 (Tier 2에서 구현)" Toast 메시지가 뜬다
- ✅ Dark/Light 테마 토글이 작동한다
- ✅ PyInstaller로 exe가 빌드된다

**비즈니스 로직은 단 한 줄도 없습니다.** UI 껍데기 + 인프라 배선만.

---

## 📅 일정

- **Day 1 (2026-04-22):** 백엔드 skeleton + 프론트엔드 shell
- **Day 2 (2026-04-23):** 테마 시스템 + exe 빌드 + 사장님 검수

---

## 🤖 Sub-Agent 투입 계획

### Agent A (백엔드 엔지니어)
**미션:** FastAPI skeleton 구축 + PyWebView 통합

**입력 파일:**
- `docs/handoff/v864_2_structure.json`
- `docs/handoff/feature_matrix.json` (API 네이밍만 참조)

**산출물:**
```
backend/
├── main.py              # PyWebView + FastAPI 통합 실행
├── app.py               # FastAPI 앱 정의
├── api/
│   ├── __init__.py
│   └── placeholder.py   # "준비 중" 반환하는 스텁
├── legacy/              # v864.2 handlers 복사 준비 (Tier 2에서 채움)
├── config.py            # DB 경로, 포트 설정
└── requirements.txt
```

**검증:**
- `python backend/main.py` 실행 시 PyWebView 창이 열림
- `http://localhost:8000/docs` 접근 시 FastAPI Swagger UI 표시

### Agent B (프론트엔드 엔지니어)
**미션:** HTML shell + CSS 디자인 시스템 구축

**입력 파일:**
- `docs/handoff/design_tokens.json` → `design-tokens.css`로 변환
- `docs/handoff/v864_2_structure.json` → 메뉴/사이드바 구조 복제

**산출물:**
```
frontend/
├── index.html           # 메인 SPA 껍데기
├── design-tokens.css    # design_tokens.json 기반 CSS 변수
├── components/
│   ├── menubar.html     # 7개 메뉴 (파일/입고/출고/재고/보고서/설정/도움말)
│   ├── quick-toolbar.html # 7개 버튼 (PDF입고/즉시출고/반품/재고조회/정합성/백업/설정)
│   ├── sidebar.html     # 9개 탭 (Inventory~Scan)
│   └── statusbar.html   # 하단 상태바
├── pages/
│   └── placeholder.html # 각 탭의 기본 "준비 중" 페이지
└── js/
    ├── app.js           # 초기화
    ├── router.js        # 사이드바 탭 전환
    ├── theme-toggle.js  # Dark/Light 토글
    └── toast.js         # "준비 중" 알림
```

**검증:**
- 브라우저에서 `index.html` 열기 → v864.2와 레이아웃 동일
- 메뉴 클릭 → 드롭다운 열림 (아이템 클릭 시 Toast)
- 사이드바 클릭 → URL 해시 변경 (`#/inventory`)
- 테마 토글 → Dark ↔ Light 전환

### Agent C (빌드 & QA)
**미션:** PyInstaller로 exe 빌드 + 스모크 테스트

**입력:**
- Agent A, B의 산출물

**산출물:**
```
build/
├── SQM_v864_3.spec      # PyInstaller 설정
└── dist/
    └── SQM_v864_3.exe   # 단일 파일 빌드
docs/
└── TIER1_COMPLETION_REPORT.md  # 검수 체크리스트
```

**검증 (Smoke Test 체크리스트):**
- [ ] exe 더블클릭 → 앱 실행
- [ ] 창 크기 1500x900 기본값
- [ ] 7개 메뉴 전부 클릭 가능 (드롭다운 열림)
- [ ] 7개 툴바 버튼 전부 클릭 시 Toast 표시
- [ ] 9개 사이드바 탭 전부 전환 가능
- [ ] Dark/Light 토글 작동
- [ ] FastAPI Swagger UI 접근 가능 (`http://localhost:8765/docs`)
- [ ] 창 닫으면 FastAPI 프로세스도 종료
- [ ] 앱 재시작 시 이전 창 크기/테마 복원

---

## 🔧 Claude Code 실행 절차

### 1단계: Plan 모드로 검토
```
> /plan Tier 1 실행 계획을 TIER1_PLAN.md 기반으로 상세화해줘
```

### 2단계: 3명 동시 투입
```
> Agent A, B, C를 병렬로 투입해서 TIER1_PLAN.md의 Tier 1 작업을 실행해줘.
  각 Agent는 자신의 미션에 집중하고, 완료 시 보고서를 docs/progress/에 남길 것.
```

### 3단계: 통합 & 검증
```
> /verify-parity Tier 1
```

### 4단계: Git 커밋
```
> Tier 1 완료 커밋 생성. 메시지: "feat(tier1): PyWebView shell with full UI replica of v864.2"
> 태그: v864.3-tier1
```

### 5단계: 사장님 검수 대기
- Smoke Test 체크리스트 전부 ✅ 확인
- 문제 발견 시 → `git reset --hard v864.3-tier1`로 복구 후 재작업

---

## ⚠️ Tier 1 단계의 절대 금지 사항

1. ❌ **비즈니스 로직 작성 금지** — Tier 2 소관
2. ❌ **DB 수정 금지** — 읽기 연결만 테스트
3. ❌ **v864.2 원본 코드 수정 금지** — `backend/legacy/`에 복사할 준비만
4. ❌ **프레임워크(React, Vue 등) 추가 금지** — Vanilla만
5. ❌ **테마 하드코딩 금지** — 반드시 CSS 변수 사용

---

## ✅ Tier 1 완료 후 다음 단계

Tier 1 통과 시 → `TIER2_PLAN.md` 작성하여 Top 10 기능 선별 시작.

**Top 10 후보 (사장님 확정 필요):**
1. PDF 입고
2. 즉시 출고
3. 재고 조회
4. 반품 처리
5. 정합성 검사
6. 백업
7. Dashboard 표시
8. Alert 영역 갱신
9. 테마 토글 (실제 저장 포함)
10. 로그 뷰

---

## 📊 성공 지표

| 지표 | 목표 | 측정 방법 |
|---|---|---|
| UI 시각적 일치도 | SSIM ≥ 0.85 | v864.2 스크린샷과 자동 비교 |
| 클릭 가능 요소 | 25개 이상 반응 | 수동 체크리스트 |
| exe 빌드 시간 | < 5분 | PyInstaller 로그 |
| exe 실행 시간 | < 3초 | 스탑워치 |
| 메모리 사용 | < 300MB | 작업관리자 |

---

**작성일:** 2026-04-21
**작성자:** Ruby (Senior Software Architect Mode)
**기반 문서:** `CLAUDE.md`, `docs/handoff/*.json`
