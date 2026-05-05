# SQM v866 MASTER-P1: Phase 0 + Phase 1 (Bug Fix)
**읽은 후 MASTER_P2.md 로 진행**
**progress.txt 에 각 TASK 완료 기록 필수**

---
## 절대 원칙 (항상 적용)
- sub_lt 컬럼 삭제/변경 금지
- engine_modules/ 수정 금지
- sqm-inline.js Edit 툴 직접 수정 금지 (Python 스크립트만)
- pytest 44 passed 유지
- 에러 시 RETRY 3회 + Ruby 즉시 수정 후 다음 TASK 진행 (중단 금지)
- error_report.md는 기록용으로만 사용 (작성해도 STOP하지 말 것)

---
## 체크포인트 규칙
완료 시: progress.txt 에 "DONE: [TASK명]" 추가
재시작 시: progress.txt 읽어서 마지막 DONE 다음부터 시작

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

# 포트 확인
netstat -an | findstr "8765"
# → 사용 중이면 "포트 8765 충돌" 보고

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


---
## P1 완료 후 다음 단계
progress.txt 에 "DONE: PHASE1" 기록
python scripts/telegram_notify.py sync1 3
→ MASTER_P2.md 로 진행
