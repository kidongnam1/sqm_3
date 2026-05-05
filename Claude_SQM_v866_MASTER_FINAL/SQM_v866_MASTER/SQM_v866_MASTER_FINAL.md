# 🔴 SQM v866 — Sub-Agent Team MASTER
**실제 폴더 분석 기반 / Ruby 2026-05-01**
**버전:** v8.6.5 (SQM_v865_CLEAN → v866 진행 중)
**진입점:** `main_webview.py` → FastAPI port **8765** → `frontend/index.html`
**현재 단계:** Phase 5 완료 (44 passed) → **Phase 6 EXE 빌드 + 기능 완성 진행 중**

---

## ⚡ MASTER Agent 시작 즉시 실행

```
1. 이 파일 전체 읽기
2. CLAUDE.md 읽기 (프로젝트 영구 메모리)
3. docs/handoff/ 3개 JSON 읽기:
   - v864_2_structure.json   (메뉴 5개, 탭 9개, 툴바 7개)
   - feature_matrix.json     (85개 기능 매핑)
   - design_tokens.json      (156개 색상, 디자인 토큰)
4. SUBAGENT_MISSION_v2.md 읽기 (Agent E 파서 비교 미션 확인)
5. SUMMARY.md 읽기 (있으면 — 컨텍스트 복원)
6. progress.txt 읽기 → 마지막 DONE 다음부터 시작
7. python scripts/telegram_notify.py start
8. Agent 팀 편성 → P0-TASK-00 (Agent E) 와 P0-TASK-01 (MASTER) 병렬 시작
```

---

## 🏗️ v866 실제 폴더 구조 (분석 완료)

```
SQM_v866_CLEAN/                   ← 프로젝트 루트
├── main_webview.py               ← 진입점 (PyWebView + uvicorn port 8765)
├── 실행.bat                      ← 더블클릭 실행 (CP949)
├── config.py                     ← DB_PATH=data/db/sqm_inventory.db
├── version.py                    ← __version__ = "8.6.5"
├── CLAUDE.md                     ← 영구 메모리 (수정 금지)
├── TIER1_PLAN.md                 ← 마이그레이션 전략
├── SUBAGENT_MISSION_v2.md        ← 이전 미션 (참고용)
│
├── frontend/                     ← HTML/CSS/JS 프론트엔드
│   ├── index.html                ← 메인 HTML
│   ├── css/
│   │   ├── design-system.css     ← design_tokens.json 변환본
│   │   └── v864-layout.css       ← 레이아웃
│   └── js/
│       ├── sqm-inline.js         ← ⚠️ 310KB 대용량 (Edit 툴 금지)
│       ├── api-client.js         ← fetch 표준 클라이언트
│       ├── router.js             ← 9탭 라우터
│       ├── state.js              ← 전역 상태
│       ├── toast.js              ← 토스트 알림
│       ├── shortcuts.js          ← 키보드 단축키
│       ├── pages/                ← 탭별 JS (9개, 50~112줄)
│       │   ├── inventory.js
│       │   ├── allocation.js
│       │   ├── picked.js
│       │   ├── outbound.js
│       │   ├── return.js
│       │   ├── scan.js
│       │   ├── tonbag.js
│       │   ├── log.js
│       │   └── dashboard.js
│       ├── handlers/             ← 메뉴/툴바 핸들러
│       │   ├── menubar.js
│       │   ├── toolbar.js
│       │   └── topbar.js
│       └── components/
│           ├── alerts.js
│           ├── auto_refresh.js
│           └── statusbar.js
│
├── backend/                      ← FastAPI 백엔드
│   ├── api/
│   │   ├── __init__.py           ← FastAPI app + 라우터 등록 (594줄)
│   │   ├── inventory_api.py      ← 재고 조회 (567줄)
│   │   ├── inbound.py            ← 입고 처리 (1974줄) ← 최대
│   │   ├── outbound_api.py       ← 출고 처리 (1043줄)
│   │   ├── allocation_api.py     ← 배정 (338줄)
│   │   ├── tonbag_api.py         ← 톤백 (182줄)
│   │   ├── dashboard.py          ← KPI (316줄)
│   │   ├── scan.py (없음→신규)   ← Scan 탭 API
│   │   ├── actions.py            ← 기타 액션 (756줄)
│   │   ├── actions2.py           ← (585줄)
│   │   ├── actions3.py           ← (367줄)
│   │   ├── queries.py            ← 조회 (624줄)
│   │   ├── queries2.py           ← (356줄)
│   │   ├── queries3.py           ← (295줄)
│   │   ├── carriers.py           ← 선사 (223줄) ← GET에서 쓰기 버그 있음
│   │   ├── settings.py           ← 설정 (570줄)
│   │   ├── info.py               ← 정보 (162줄)
│   │   ├── ai_gemini.py          ← AI (229줄)
│   │   ├── debug_log.py          ← 디버그 로그
│   │   ├── controls.py           ← 제어 (281줄)
│   │   └── optional.py           ← 선택 기능 (136줄)
│   └── common/
│       ├── cache.py
│       └── errors.py
│
├── engine_modules/               ← 핵심 엔진 (수정 금지)
│   └── inventory_modular/
│       └── engine.py             ← SQMInventoryEngineV3
├── features/parsers/             ← 파서 (수정 금지)
├── parsers/document_parser_modular/ ← BL/DO/PL/FA 파서
├── tests/
│   ├── fixtures/                 ← PDF 16개 (4선사 × 4문서)
│   └── test_phase5_parity.py     ← 44 passed (기준 유지)
├── docs/handoff/                 ← 설계도 3종 (수정 금지)
├── scripts/
│   └── telegram_notify.py        ← Telegram SYNC 알림 ← 이 파일 추가 필요
└── data/db/sqm_inventory.db      ← SQLite DB
```

---

## ⚠️ v866 절대 불변 원칙

| # | 원칙 | 근거 |
|---|------|------|
| 1 | `sub_lt` 컬럼 삭제/변경 금지 | 53개 파일 연동, UNIQUE INDEX |
| 2 | `engine_modules/` `features/` `parsers/` `utils/` 수정 금지 | 검증된 비즈니스 로직 |
| 3 | `frontend/js/sqm-inline.js` Edit 툴 직접 수정 금지 | 310KB 대용량, 파일 붕괴 위험 |
| 4 | `docs/handoff/` 3개 JSON 삭제/수정 금지 | 설계 기준 |
| 5 | 색상 하드코딩 금지 → `design-tokens.css` CSS 변수만 | 테마 일관성 |
| 6 | 모든 FastAPI 엔드포인트 try/except + HTTPException | Rule 4 |
| 7 | 모든 JS fetch → try/catch + Toast 알림 | Rule 4 |
| 8 | 빈 화면(blank screen) 절대 금지 | Rule 4 |
| 9 | `배치파일` CP949 + CRLF 필수 | 한글 경로 |
| 10 | pytest test_phase5_parity.py 44 passed 유지 | 회귀 방지 |

---

## 🔌 포트 8765 정책 (MASTER / Agent 공통)

**원칙:** 우선 **번호 유지** + **충돌 원인 제거**. 포트 번호만 임의로 바꾸지 않는다.

| 순서 | 조치 | 설명 |
|:---:|:---|:---|
| 1 | **번호 유지** | 기본 포트 **8765** 유지 (`main_webview.py`, HOW_TO_RUN, 본 문서, 더블실행 방지 전제와 일치). |
| 2 | **충돌 원인 제거** | `netstat` 등으로 점유 확인 후 **해당 프로세스 종료**(이전 세션의 `python main_webview.py` / uvicorn 잔류). 앱 기동 시 **`main_webview.py` 내 포트 점검·좀비 PID 종료** 로직을 우선 활용. |
| 3 | **변경은 최후** | 그래도 번호를 바꿀 때만: **`API_PORT` + WebView 로드 URL + 프론트/스크립트의 `8765` 하드코딩 + 배치·문서**를 **동일 포트로 한 번에** 맞춘다. 한 곳만 수정하면 접속 불일치로 빈 화면·Connection refused가 난다. |

환경 검증(P0-TASK-01)의 `netstat` 단계는 위 **1→2** 절차와 함께 본다.

---

## ♻️ RETRY PROTOCOL (전 TASK 공통)

```
에러 발생 즉시:

RETRY 1회차:
  → 에러 메시지 원문 읽기
  → 해당 파일만 수정 (다른 파일 건드리지 말 것)
  → python -m py_compile [파일] 또는 node --check [파일]
  → python scripts/telegram_notify.py retry [TASK] 1 "[에러요약]"
  → SUMMARY.md: "RETRY-1: [TASK] [내용]" 추가

RETRY 2회차:
  → 동일 에러 → 관련 파일 처음부터 재분석
  → 추측 금지 — 파일 읽고 원인 파악 후 수정
  → python scripts/telegram_notify.py retry [TASK] 2 "[수정내용]"

RETRY 3회차 실패:
  → error_report.md 작성 (표준 양식, 기록용)
  → python scripts/telegram_notify.py blocked [TASK] "[사유]"
  → progress.txt: "RECOVERY_REQUIRED: [TASK]" 기록
  → Ruby가 즉시 수정 시도 후 다음 TASK 진행 (STOP 금지)

판단 불가 에러(우선 자동복구 시도, 불가 시 보고 후 다음 TASK 진행):
  OperationalError: no such column
    → DB 스키마 불일치. 기동님: "python -c 'import sqlite3; ...PRAGMA table_info'"
  ModuleNotFoundError: engine_modules
    → PYTHONPATH 미설정. 기동님: "set PYTHONPATH=%CD%"
  ConnectionRefusedError: 8765
    → main_webview.py 미실행. 기동님: "python main_webview.py 먼저 실행"
  node: command not found
    → Node.js 미설치. 기동님: "node.js 설치 필요"
  JS sqm-inline.js 파일 크기 급감 (정상: ~310KB)
    → 파일 붕괴. 즉시 .bak 또는 .bak2 복원
```

---

## 🔖 체크포인트 규칙

```
progress.txt 기록:
  DONE: [TASK명] ([시각]) Agent:[A/B/C/D]
  RETRY-1: [TASK명] [에러요약]
  BLOCKED: [TASK명] [사유]

SUMMARY.md 업데이트 시점:
  - 각 SYNC 포인트
  - RETRY 발생 시
  - 환경 정보 발견 시 (Python버전, 라이브러리 등)
```

---

## 🤖 Sub-Agent 팀 구성 (5 Agent)

```
MASTER Agent  ← 전체 조율, SYNC 관리, Telegram 알림
  │
  ├── Agent A (Frontend JS)
  │     담당: frontend/js/ 전체
  │     핵심: sqm-inline.js는 Python 스크립트로만 수정
  │     시작: SYNC-1 이후
  │
  ├── Agent B (Backend API)
  │     담당: backend/api/ 전체
  │     핵심: engine_modules 얇게 감싸기만
  │     시작: SYNC-1 이후
  │
  ├── Agent C (Bug Fix + Stability)
  │     담당: 기존 버그 수정 (SUBAGENT_MISSION_v2 항목)
  │     핵심: 기존 코드 최소 변경 원칙
  │     시작: SYNC-1 이후
  │
  ├── Agent D (Test + QA + ZIP)
  │     담당: pytest + 교차검증 + 패치 ZIP
  │     핵심: 44 passed 유지 + node --check 필수
  │     시작: SYNC-3 이후
  │
  └── Agent E (Parser Comparison) ← 완전 독립 병렬 실행
        담당: 6방식 파서 비교 테스트 (SUBAGENT_MISSION_v2 Agent A 미션)
        핵심: UI/API 작업과 완전 독립 — 동시 실행 가능
        시작: P0-TASK-00 (Phase 0 시작과 동시)
        완료: REPORTS/parse_comparison_6method_final.html 생성
```

### Agent E 독립 실행 원칙
```
Agent E는 다른 Agent와 공유 파일이 없음
  읽기: tests/fixtures/*.pdf (16개), scripts/run_comparison_windows.py
  쓰기: REPORTS/parse_comparison_6method_final.html (신규)
  절대 쓰지 않는 곳: frontend/, backend/, engine_modules/

MASTER Agent는 Agent E의 완료를 기다리지 않고
다른 Phase를 진행함. Agent E는 비동기 완전 독립.
```

---

# PHASE 0 — 환경 검증 + 파서 비교 병렬 시작

## P0-TASK-00: 6방식 파서 비교 테스트 (Agent E) ← MASTER와 동시 시작

**담당:** Agent E (완전 독립 — 다른 TASK와 무관)
**참조:** SUBAGENT_MISSION_v2.md Agent A 섹션
**예상:** 30~60분 (API 응답 시간 포함)
**병렬 실행:** P0-TASK-01 (환경 검증) 과 동시에 시작

### 목적
6가지 파싱 방식의 정확도를 측정하여 최적 방식 결정.
좌표 파싱(①)을 기준값으로 삼고, 나머지 5개 AI 방식의 일치율을 퍼센트로 환산.

### 대상 PDF (tests/fixtures/ — 16개)
```
HAPAG_BL.pdf / HAPAG_DO.pdf / HAPAG_FA.pdf / HAPAG_PL.pdf
MAERSK_BL.pdf / MAERSK_DO.pdf / MAERSK_FA.pdf / MAERSK_PL.pdf
MSC_BL.pdf / MSC_DO.pdf / MSC_FA.pdf / MSC_PL.pdf
ONE_BL.pdf / ONE_DO.pdf / ONE_FA.pdf / ONE_PL.pdf
```

### 6가지 파싱 방식
| 방식 | 상태 | 비고 |
|------|------|------|
| ① 좌표 등록 | 항상 실행 | 기본값, API 비용 없음, 기준값 |
| ② Gemini | 실행 | settings.ini api_key 확인 |
| ③ Groq | 키 상태 확인 후 | 폐기됐으면 SKIP |
| ④ xAI | 실행 | settings.ini 키 있음 |
| ⑤ OpenRouter | 실행 | deepseek-r1:free |
| ⑥ OpenAI | 크레딧 확인 후 | 없으면 SKIP |

### 실행 방법

```bash
cd D:\program\SQM_inventory\SQM_v866_CLEAN
python scripts\run_comparison_windows.py
```

실행 전 확인:
```bash
# API 키 상태 확인
python -c "
from config import GEMINI_API_KEY, OPENAI_API_KEY
print('Gemini:', 'OK' if GEMINI_API_KEY else 'MISSING')
print('OpenAI:', 'OK' if OPENAI_API_KEY else 'MISSING')
import configparser
c = configparser.ConfigParser()
c.read('settings.ini')
xai = c.get('xAI', 'api_key', fallback='')
print('xAI:', 'OK' if xai and not xai.startswith('your') else 'MISSING')
"
```

### 정확도 계산 기준
```
정답(기준): 좌표 파싱(①) 결과
정확도: 일치 필드 수 / 전체 필드 수 × 100 (%)
strip + lower 후 문자열 비교
3회 반복 → 평균값
```

### 측정 필드 목록 (DO 기준)
```
container_no / vessel_name / voyage_no / arrival_date /
do_no / shipper / consignee / free_time / port_of_discharge
```

### 결과 산출물

```
REPORTS/parse_comparison_6method_final.html

필수 포함 내용:
┌────────┬──────┬────────┬─────────┬───────┬──────┬─────────────┬────────┐
│ 선사   │ 문서 │ 필드수 │ ①좌표  │ ②Gem │ ③Gr │ ④xAI      │ ⑤ORouter│
├────────┼──────┼────────┼─────────┼───────┼──────┼─────────────┼────────┤
│ ONE    │ DO   │ 9      │ 100%   │ 89%  │ SKIP│ 78%        │ 82%   │
│ HAPAG  │ BL   │ 7      │ 100%   │ 95%  │ SKIP│ 88%        │ 91%   │
│ ...    │ ...  │ ...    │ ...    │ ...  │ ...│ ...        │ ...   │
├────────┼──────┼────────┼─────────┼───────┼──────┼─────────────┼────────┤
│ 합계   │      │        │ 100%   │ ?%   │ ?% │ ?%         │ ?%    │
└────────┴──────┴────────┴─────────┴───────┴──────┴─────────────┴────────┘

추가: 방식별 평균 응답 시간 (초)
추가: API 비용 추정 (건당)
추가: Ruby 최종 권장 방식 (정확도/비용/속도 종합)
```

### RETRY 규칙 (Agent E 전용)
```
API 오류 발생 시:
  → 해당 방식만 SKIP 처리 (다른 방식은 계속)
  → "API_ERROR: [방식명] — SKIP" 으로 결과표에 표시

run_comparison_windows.py 실행 오류:
  → RETRY 1회차: python -c "import pdfplumber; ..." 라이브러리 확인
  → RETRY 2회차: 개별 PDF 파일 하나씩 테스트
  → RETRY 3회차 실패: REPORTS/parse_error_report.md 작성 후 STOP

파일 없음 오류:
  → tests/fixtures/ 경로 확인
  → 없으면 즉시 STOP: "fixtures PDF 없음 — 기동님 확인 필요"
```

### 완료 조건
```
[ ] REPORTS/parse_comparison_6method_final.html 생성
[ ] 최소 ①좌표 방식 결과 있음 (나머지는 SKIP 허용)
[ ] 결과표에 정확도 % 표시됨
[ ] Ruby 최종 권장 방식 한 줄 명시

완료 후:
  python scripts/telegram_notify.py send "[파서비교] 완료: 최고정확도=[방식]([%]%)"
  progress.txt: "DONE: P0-TASK-00 Agent:E"
```

---

## P0-TASK-01: 환경 사전 검증

**예상: 5분**

```bash
python --version
# → 3.10 이상 필수

node --version
# → 18+ 필수 (sqm-inline.js node --check 용)

python -c "import webview; print('pywebview:', webview.__version__)"
python -c "import fastapi; print('fastapi:', fastapi.__version__)"
python -c "import uvicorn; print('uvicorn OK')"
python -c "import pdfplumber; print('pdfplumber OK')"
python -c "import fitz; print('PyMuPDF OK')"

# DB 존재 확인
python -c "
import os
db = 'data/db/sqm_inventory.db'
print('DB:', os.path.exists(db), '-', os.path.getsize(db) if os.path.exists(db) else 0, 'bytes')
"

# 포트 확인 (정책: 번호 유지 + 충돌 원인 제거 → 상단 "포트 8765 정책" 참고)
netstat -an | findstr "8765"
# → 사용 중이면 좀비/이중 실행 의심 → 프로세스 종료 후 재시도. 임의 포트 변경은 최후 수단.

# engine 로드 확인
python -c "
from engine_modules.inventory_modular.engine import SQMInventoryEngineV3
from config import DB_PATH
e = SQMInventoryEngineV3(str(DB_PATH))
print('Engine OK')
"

# 기존 테스트 기준 확인
python -m pytest tests/test_phase5_parity.py -q --tb=no 2>&1 | tail -3
# → 44 passed 확인
```

완료 후:
- SUMMARY.md 환경 정보 기록
- python scripts/telegram_notify.py env_ok [Python버전] [Node버전]
- progress.txt: DONE: P0-TASK-01

---

# PHASE 1 — 기존 버그 수정 (Agent C) ← 최우선

**근거:** SUBAGENT_MISSION_v2.md 의 미완료 버그들이 현재 운영을 막고 있음

## P1-TASK-01: carriers.py GET → 쓰기 버그 수정

**파일:** `backend/api/carriers.py`
**문제:** GET 엔드포인트가 INSERT/commit 실행
**예상: 15분**

```python
# 수정 원칙:
# GET /api/carriers/* → 읽기 전용 (SELECT만)
# 쓰기 작업은 POST/PUT 엔드포인트로 분리

# 수정 방법:
# 1. carriers.py 전체 읽기
# 2. GET 함수 내부에서 con.execute(INSERT/UPDATE/DELETE) 찾기
# 3. 해당 로직을 POST 엔드포인트로 이동
# 4. GET 엔드포인트는 SELECT만 남김
```

**검증:**
```bash
python -m py_compile backend/api/carriers.py
grep -n "INSERT\|UPDATE\|DELETE\|commit" backend/api/carriers.py
# → GET 함수 내부에 없어야 함
```
**완료 후:** progress.txt 기록

---

## P1-TASK-02: config_logging.py CP949 UnicodeEncodeError 수정

**파일:** `config_logging.py`
**문제:** 한글 로그 메시지 출력 시 CP949 인코딩 오류
**예상: 10분**

```python
# 수정 원칙:
# FileHandler 생성 시 encoding='utf-8' 명시
# StreamHandler는 sys.stdout 인코딩 문제 방어

# 수정 패턴:
# 변경 전: logging.FileHandler(log_path)
# 변경 후: logging.FileHandler(log_path, encoding='utf-8')

# StreamHandler 방어:
# handler = logging.StreamHandler()
# handler.stream = open(sys.stdout.fileno(), mode='w',
#                       encoding='utf-8', closefd=False)
# 또는: errors='replace' 추가
```

**검증:**
```bash
python -m py_compile config_logging.py
python -c "
import logging
from config_logging import setup_logging
setup_logging()
logging.getLogger('test').info('한글 테스트 Korean Log Test')
print('OK')
"
```
**완료 후:** progress.txt 기록

---

## P1-TASK-03: sqm-inline.js _zFloatTop IIFE 스코프 오류

**파일:** `frontend/js/sqm-inline.js` (310KB)
**경고:** Python 스크립트로만 수정. Edit 툴 절대 금지.
**예상: 20분**

```python
# 수정 스크립트 (Python으로 작성):
src = 'frontend/js/sqm-inline.js'
bak = 'frontend/js/sqm-inline.js.bak3'

import shutil
shutil.copy2(src, bak)  # 백업 먼저

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 변경 전: var _zFloatTop = 10100;
# 변경 후: window._sqmZ = window._sqmZ || 10100;
content = content.replace(
    'var _zFloatTop = 10100;',
    'window._sqmZ = window._sqmZ || 10100;',
    1
)

# _bringToFront 함수를 window 스코프로 노출
# 변경 전: function _bringToFront(el) { el.style.zIndex = ++_zFloatTop; }
# 변경 후: window._bringToFront = function(el) { el.style.zIndex = ++window._sqmZ; };
content = content.replace(
    'function _bringToFront(el)',
    'window._bringToFront = function(el)',
    1
)

with open(src, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

print(f'파일 크기: {len(content.encode())} bytes')
# → 정상: 약 310,000 bytes. 급감하면 즉시 bak 복원
```

**검증:**
```bash
node --check frontend/js/sqm-inline.js
# → 0 errors

# 파일 크기 확인
python -c "import os; print(os.path.getsize('frontend/js/sqm-inline.js'), 'bytes')"
# → 300,000 이상이어야 함
```
**완료 후:** progress.txt 기록

---

### SYNC-1: Phase 1 완료 + Agent E 중간 확인

```
MASTER Agent 확인:
[ ] carriers.py GET 읽기 전용 확인
[ ] config_logging.py 한글 로그 정상
[ ] sqm-inline.js 파일 크기 정상 (300KB+)
[ ] node --check 통과

Agent E 상태 확인 (블로킹 아님):
[ ] P0-TASK-00 완료됐으면 → Telegram 알림 결과 공유
[ ] 아직 진행 중이면 → 그대로 계속 (기다리지 않음)

→ python scripts/telegram_notify.py sync1 3
→ Agent B/D 병렬 시작
```

---

# PHASE 2 — 백엔드 API 완성 (Agent B)

**현황:** backend/api/ 에 대부분 구현됨. 누락/미완성 항목 보완.

## P2-TASK-01: API 엔드포인트 전수 검증

**예상: 20분**

```bash
# 현재 등록된 라우터 목록 확인
grep -n "router\.\|app\.\|@app\." backend/api/__init__.py | head -50

# 각 엔드포인트 응답 형식 확인
# → 모든 응답이 {"success": bool, "data": ..., "message": str} 형식인지 확인
grep -rn "return {" backend/api/ --include="*.py" | grep -v "success" | head -20
# → success 없는 응답 발견 시 수정 대상
```

## P2-TASK-02: Scan API 신규 생성

**파일:** `backend/api/scan_api.py` (신규)
**연결:** `engine_modules/inventory_modular/engine.py` → SQMInventoryEngineV3
**예상: 30분**

```python
# backend/api/scan_api.py

from fastapi import APIRouter
from config import DB_PATH
from engine_modules.inventory_modular.engine import SQMInventoryEngineV3

router = APIRouter(prefix="/api/scan", tags=["scan"])

@router.post("/lookup")
async def scan_lookup(uid: str):
    """UID로 톤백 현재 상태 조회"""
    try:
        engine = SQMInventoryEngineV3(str(DB_PATH))
        # engine의 기존 조회 함수 활용
        result = engine.get_tonbag_by_uid(uid)  # 실제 함수명 확인 필요
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/confirm_outbound")
async def scan_confirm_outbound(uid: str):
    """PICKED → OUTBOUND → SOLD (유일한 SOLD 전환 경로)"""
    try:
        engine = SQMInventoryEngineV3(str(DB_PATH))
        result = engine.confirm_outbound_by_scan(uid)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/return")
async def scan_return(uid: str, reason: str = ""):
    """OUTBOUND → RETURN"""
    try:
        engine = SQMInventoryEngineV3(str(DB_PATH))
        result = engine.process_return_by_scan(uid, reason)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.put("/move")
async def scan_move(uid: str, to_location: str):
    """톤백 위치 변경 (status 유지)"""
    try:
        engine = SQMInventoryEngineV3(str(DB_PATH))
        result = engine.move_tonbag(uid, to_location)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}
```

**주의:** engine 실제 함수명은 아래 확인 후 사용:
```bash
grep -n "def confirm_outbound\|def process_return\|def move_tonbag\|def get_tonbag" \
    engine_modules/inventory_modular/engine.py | head -20
```

**검증:**
```bash
python -m py_compile backend/api/scan_api.py
```
**완료 후:** progress.txt 기록

## P2-TASK-03: Integrity API 신규 생성

**파일:** `backend/api/integrity_api.py` (신규)
**예상: 20분**

```python
# backend/api/integrity_api.py
from fastapi import APIRouter
from config import DB_PATH
import sqlite3

router = APIRouter(prefix="/api/integrity", tags=["integrity"])

@router.get("/check")
async def integrity_check():
    """전체 무게 정합성 검사
    공식: initial_weight = current_weight + picked_weight (±1.0kg)
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        # inventory 테이블에서 무게 불일치 LOT 조회
        rows = conn.execute("""
            SELECT lot_no,
                   initial_weight,
                   current_weight,
                   picked_weight,
                   ABS(initial_weight - (current_weight + picked_weight)) as diff
            FROM inventory
            WHERE ABS(initial_weight - (current_weight + picked_weight)) > 1.0
        """).fetchall()
        conn.close()

        total = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        error_list = [dict(r) for r in rows]

        return {
            "success": True,
            "data": {
                "total": total,
                "ok": total - len(error_list),
                "error": len(error_list),
                "details": error_list
            }
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
```

**검증:**
```bash
python -m py_compile backend/api/integrity_api.py
```
**완료 후:** progress.txt 기록

## P2-TASK-04: 신규 라우터 backend/__init__.py 등록

```python
# backend/api/__init__.py 하단에 추가
from backend.api.scan_api import router as scan_router
from backend.api.integrity_api import router as integrity_router

app.include_router(scan_router)
app.include_router(integrity_router)
```

**검증:**
```bash
python -c "from backend.api import app; print('라우터 수:', len(app.routes))"
```
**완료 후:** progress.txt 기록

---

# PHASE 3 — 프론트엔드 JS 완성 (Agent A)

**현황:** frontend/js/pages/ 9개 파일 존재 (50~112줄). 기능 연결 미완성 부분 보완.

## P3-TASK-01: api-client.js 표준화 확인

**파일:** `frontend/js/api-client.js`
**예상: 15분**

```javascript
// 아래 함수들이 반드시 있어야 함
// 없으면 추가, 있으면 패턴 확인

async function apiGet(endpoint, params = {}) {
    const url = new URL(`http://localhost:8765${endpoint}`);
    Object.entries(params).forEach(([k, v]) => url.searchParams.append(k, v));
    try {
        const res = await fetch(url.toString());
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data.success) throw new Error(data.message || '서버 오류');
        return data;
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}

async function apiPost(endpoint, body = {}) {
    try {
        const res = await fetch(`http://localhost:8765${endpoint}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data.success) throw new Error(data.message || '서버 오류');
        return data;
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}
```

**검증:**
```bash
node --check frontend/js/api-client.js
grep -n "apiGet\|apiPost\|apiPut" frontend/js/api-client.js | head -10
```
**완료 후:** progress.txt 기록

## P3-TASK-02: inventory.js 실데이터 연결

**파일:** `frontend/js/pages/inventory.js` (현재 94줄)
**API:** `/api/inventory` (inventory_api.py)
**예상: 30분**

```javascript
// 반드시 포함할 함수들

async function loadInventory(filters = {}) {
    try {
        const data = await apiGet('/api/inventory', filters);
        renderInventoryTable(data.data);
        updateStatusBar(data.data.length);
    } catch (e) { /* apiGet이 Toast 처리 */ }
}

function renderInventoryTable(rows) {
    // 19개 컬럼 순서 고정
    // No|LOT NO|SAP NO|BL NO|PRODUCT|STATUS|Balance(Kg)|NET(Kg)|
    // CONTAINER|MXBG|INVOICE NO|SHIP DATE|ARRIVAL|CON RETURN|
    // FREE TIME|WH|CUSTOMS|Inbound(Kg)|Outbound(Kg)

    // 행 색상 (CSS 클래스로)
    // AVAILABLE → row-available
    // RESERVED  → row-reserved
    // PICKED    → row-picked
    // OUTBOUND  → row-outbound
}

// 더블클릭 → LOT 상세 모달
function onRowDoubleClick(lotNo) { /* ... */ }

// 우클릭 → 즉시 출고 컨텍스트 메뉴
function onRowRightClick(e, lotNo) { /* ... */ }

// 탭 진입 시 자동 로드
document.addEventListener('DOMContentLoaded', () => loadInventory());
```

**검증:**
```bash
node --check frontend/js/pages/inventory.js
grep -n "async function\|apiGet\|apiPost" frontend/js/pages/inventory.js
```
**완료 후:** progress.txt 기록

## P3-TASK-03: dashboard.js KPI 실데이터 연결

**파일:** `frontend/js/pages/dashboard.js` (현재 112줄)
**API:** `/api/dashboard/stats`, `/api/integrity/check`
**예상: 25분**

```javascript
// 반드시 포함할 함수들

async function loadDashboard() {
    try {
        const [stats, integrity] = await Promise.all([
            apiGet('/api/dashboard/stats'),
            apiGet('/api/integrity/check')
        ]);
        renderKpiCards(stats.data);
        renderIntegrityLight(integrity.data);
        renderProductTable(stats.data.by_product);
    } catch (e) {}
}

function renderKpiCards(data) {
    // KPI 카드 5개: AVAILABLE / RESERVED / PICKED / OUTBOUND / RETURN
    // 각: 상태명 + 톤백수 + 총 중량Kg
    // 색상: CSS 변수 (design-tokens.css) 사용
}

function renderIntegrityLight(data) {
    // data.error > 0 → 🔴
    // data.warning > 0 → 🟡
    // else → 🟢
}

// 30초 자동 갱신
setInterval(loadDashboard, 30000);
loadDashboard();  // 최초 로드
```

**검증:**
```bash
node --check frontend/js/pages/dashboard.js
grep -n "setInterval\|loadDashboard" frontend/js/pages/dashboard.js
```
**완료 후:** progress.txt 기록

## P3-TASK-04: scan.js 4버튼 연결

**파일:** `frontend/js/pages/scan.js` (현재 69줄)
**API:** `/api/scan/*`
**예상: 25분**

```javascript
// 핵심 구현

const uidInput = document.getElementById('uid-input');

// 엔터키 → 자동 조회
uidInput?.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') await lookupUid(uidInput.value.trim());
});

async function lookupUid(uid) {
    const data = await apiPost('/api/scan/lookup', {uid});
    showScanResult(data.data);
    updateActionButtons(data.data.status);
}

function updateActionButtons(status) {
    // 조건부 활성화
    document.getElementById('btn-confirm').disabled = (status !== 'PICKED');
    document.getElementById('btn-return').disabled  = (status !== 'OUTBOUND');
    document.getElementById('btn-restock').disabled = (status !== 'RETURN');
    document.getElementById('btn-move').disabled    = false;  // 항상 활성
}

// 4개 버튼 핸들러
async function confirmOutbound() {
    // PICKED → OUTBOUND → SOLD (SOLD는 이 경로만)
    await apiPost('/api/scan/confirm_outbound', {uid: uidInput.value});
}
```

**검증:**
```bash
node --check frontend/js/pages/scan.js
```
**완료 후:** progress.txt 기록

## P3-TASK-05: menubar.js 미연결 메뉴 완성

**파일:** `frontend/js/handlers/menubar.js`
**참조:** `docs/handoff/feature_matrix.json` (85개 기능)
**예상: 30분**

```bash
# 현재 연결된 메뉴 수 확인
grep -c "async function\|apiGet\|apiPost" frontend/js/handlers/menubar.js

# feature_matrix.json 에서 미연결 항목 찾기
python -c "
import json
with open('docs/handoff/feature_matrix.json') as f:
    fm = json.load(f)
missing = [f for f in fm if not f.get('js_handler')]
print(f'미연결 기능: {len(missing)}개')
for m in missing[:10]:
    print(' -', m.get('name', '?'))
"
```

각 미연결 메뉴에 대해:
- apiGet/apiPost 연결 함수 추가
- 연결 불가능한 기능은 showToast('준비 중', 'info') 처리

**검증:**
```bash
node --check frontend/js/handlers/menubar.js
```
**완료 후:** progress.txt 기록

---

### SYNC-2: Phase 2+3 완료

```
MASTER Agent 확인:
[ ] scan_api.py, integrity_api.py py_compile 통과
[ ] backend/__init__.py 신규 라우터 등록
[ ] 모든 JS 파일 node --check 통과
[ ] dashboard.js setInterval(30000) 포함
→ python scripts/telegram_notify.py sync2 [API수]
→ python scripts/telegram_notify.py sync3 [JS파일수]
→ Agent D 검증 시작
```

---

# PHASE 4 — 통합 검증 + EXE 빌드 (Agent D)

## P4-TASK-01: 교차검증 5항목

```bash
# ① SQL 오염 확인
grep -rn "\-\-" backend/api/ --include="*.py" | grep -v "^.*#" | grep -v "\.pyc"

# ② SOLD 전환 경로 확인
grep -rn "SOLD\|confirm_outbound" backend/api/ --include="*.py"
# → scan_api.py 에만 있어야 함

# ③ 미들웨어 등록 확인
grep -n "exception_handler\|add_middleware" backend/api/__init__.py

# ④ 전체 문법 검사
find backend -name "*.py" | xargs python -m py_compile
find frontend/js -name "*.js" | xargs node --check

# ⑤ 대용량 파일 크기 확인
python -c "import os; s=os.path.getsize('frontend/js/sqm-inline.js'); print(f'sqm-inline.js: {s:,} bytes'); assert s > 200000, '파일 붕괴!'"

출력:
=== 교차검증 결과 ===
① SQL 오염: [OK]/[FAIL]
② SOLD 경로: [OK]/[FAIL]
③ 미들웨어: [OK]/[FAIL]
④ 문법검사: [OK]/[FAIL]
⑤ 파일크기: [OK]/[FAIL]
```

## P4-TASK-02: pytest 기준 유지 확인

```bash
python -m pytest tests/test_phase5_parity.py -v --tb=short
# 기준: 44 passed 유지 (신규 추가 가능, 감소 불가)

# 전체 테스트
python -m pytest tests/ -q --tb=short 2>&1 | tail -5
```

## P4-TASK-03: UI 스모크 체크 요청

```
python scripts/telegram_notify.py smoke

기동님께 30초 확인 요청:
[ ] main_webview.py 실행 → 브라우저 창 열림
[ ] 사이드바 9개 탭 표시
[ ] Inventory 탭 데이터 로드
[ ] 상단 메뉴 드롭다운 열림
[ ] Dashboard KPI 숫자 표시

기동님 '확인완료' 답장 → P4-TASK-04 진행
이상 발견 → 해당 페이지 Agent A 재작업
```

## P4-TASK-04: 패치 ZIP 생성

```
파일명: Claude_SQM_v866_PATCH.zip

포함 파일 (변경된 것만):
Claude_SQM_v866_PATCH\
  backend\api\
    scan_api.py          ← 신규
    integrity_api.py     ← 신규
    carriers.py          ← 수정
    __init__.py          ← 라우터 추가
  frontend\js\
    api-client.js        ← 수정
    sqm-inline.js        ← 수정 (IIFE 버그)
    pages\
      inventory.js       ← 수정
      dashboard.js       ← 수정
      scan.js            ← 수정
    handlers\
      menubar.js         ← 수정
  config_logging.py      ← 수정
  scripts\
    telegram_notify.py   ← 신규 추가

[주의] 폴더 구조 반드시 포함. 파일만 단독 삽입 금지.
```

## P4-TASK-05: DONE.md + 완료 알림

```markdown
# SQM v866 Sub-Agent Team 작업 완료
날짜: {날짜}
팀: MASTER + Agent A/B/C/D/E

## 완료 내역
Phase 0: 환경 검증 [OK]
Phase 0 (Agent E): 6방식 파서 비교 [OK 또는 PARTIAL]
  - 최고 정확도 방식: [방식명] ([%]%)
  - 권장 방식: [방식명]
  - 결과: REPORTS/parse_comparison_6method_final.html
Phase 1: 버그 수정 3건 [OK]
  - carriers.py GET 쓰기 버그
  - config_logging.py CP949
  - sqm-inline.js _zFloatTop IIFE
Phase 2: 백엔드 API 보완 [OK]
  - scan_api.py 신규
  - integrity_api.py 신규
Phase 3: 프론트엔드 JS 완성 [OK]
  - inventory.js 실데이터 연결
  - dashboard.js KPI + 30초 갱신
  - scan.js 4버튼 연결
Phase 4: 교차검증 통과 [OK]

## 테스트 결과
pytest test_phase5_parity.py: 44 passed (기준 유지)

## 패치 파일
Claude_SQM_v866_PATCH.zip

## 다음 작업 권장 (Ruby)
1. Phase 6: PyInstaller EXE 빌드
2. 파서 비교 결과 기반 기본 파싱 방식 확정 (settings.ini 반영)
3. inbound.py 예외 pass → 단계별 실패 사유 명시
```

DONE.md 생성 후:
```
python scripts/telegram_notify.py done
```

---

## 🎯 완수율 분석

| 구성 요소 | 차단하는 실패 | 기여 |
|----------|-------------|------|
| SKILL.md + MASTER.md | 도메인/순서 혼란 | +30% |
| RETRY Protocol | 단순 코드 에러 | +15% |
| run_master.bat | 프로세스 중단 | +10% |
| progress.txt | 세션 끊김 | +10% |
| SUMMARY.md | 컨텍스트 소실 | +5% |
| env_check | 환경 불일치 | +8% |
| 판단 트리거 | 판단 불가 에러 | +4% |
| UI 스모크 체크 | UI 렌더링 오류 | +2% |
| Telegram SYNC | BLOCKED 빠른 해소 | +3% |
| v866 실구조 반영 | 경로/파일 오류 | +10% |
| **합계** | | **~97%** |

---

*SQM v866 Sub-Agent Team MASTER — Ruby 2026-05-01*
*실제 폴더 구조 분석 기반 (v8.6.5, Phase 5 완료 상태)*
