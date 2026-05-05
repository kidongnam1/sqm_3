# SQM v8.6.5 — 서브에이전트 팀 작업 지시서 v2
**작성일:** 2026-04-29  
**작성자:** Ruby (Senior Software Architect)  
**대상 폴더:** `D:\program\SQM_inventory\SQM_v865_CLEAN`  
**총 에이전트:** 4팀 (A / B / C / D) — 병렬 실행 가능

---

## 전체 목표 요약

| 번호 | 분류 | 내용 | 담당 에이전트 |
|------|------|------|-------------|
| ① | 테스트 & 분석 | 6방식 파서 비교 최대 5회 실행 → 정확도 테이블 생성 | **Agent A** |
| ② | 버그 수정 (최우선) | `_zFloatTop` IIFE 스코프 오류 (ReferenceError) | **Agent B** |
| ③ | 버그 수정 | `config_logging.py` CP949 UnicodeEncodeError | **Agent B** |
| ④ | 버그 수정 | `carriers.py` GET 엔드포인트가 쓰기(INSERT/commit)까지 수행 | **Agent C** |
| ⑤ | 개선 | `inbound.py` 예외 `pass` → 단계별 실패 사유 명시 | **Agent C** |
| ⑥ | UI 개선 | 6방식 선택기: 좌표=기본 고정, 나머지 5개 사용자 선택 | **Agent D** |
| ⑦ | Ruby 추가 항목 | 운영 안정성·편의성 자체 검토 후 즉시 반영 | **Agent C** |

> ⚠️ **대용량 파일 수정 규칙 (필수)**  
> `frontend/js/sqm-inline.js` (약 310 KB)는 **Edit 툴 사용 금지**.  
> 반드시 Python 스크립트로 읽고·교체·단일 write 후 `node --check`로 검증.

---

## Agent A — 6방식 파서 비교 테스트 (최대 5회)

### 목적
`scripts/run_comparison_windows.py`를 실행하여 6가지 파싱 방식의 정확도를 측정한다.  
**"좌표 파싱(①)"을 정답(기준값)으로 삼고**, 나머지 5개 AI 방식이 좌표 파싱 결과와 얼마나 일치하는지를 퍼센트 정확도로 환산한다.

### 실행 조건
- 최대 5회 반복 실행 (단, 16개 문서 × 6방식이 모두 성공하면 1회로 종료)
- API KEY가 없는 방식은 "KEY없음 — SKIP"으로 기록 (오류로 처리하지 않음)
- 각 반복 시 이전 결과와 diff 비교 → 안정성 판단

### 대상 파일
```
scripts/run_comparison_windows.py   ← 실행 스크립트
tests/fixtures/                     ← PDF 원본 (16개)
REPORTS/parse_comparison_6method.html  ← 결과 저장 위치 (신규)
```

### 결과 산출물 — 정확도 테이블 (HTML + 콘솔 출력)

아래 형식으로 결과 테이블을 만든다.

| 선사 | 문서 | 필드수 | ①좌표(기준) | ②Gemini | ③Groq | ④xAI | ⑤OpenRouter | ⑥OpenAI |
|------|------|--------|------------|---------|-------|------|------------|---------|
| ONE | DO | 10 | 100% | 90% | — | — | 80% | 85% |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |
| **합계** | | | **100%** | **?%** | **?%** | **?%** | **?%** | **?%** |

**정확도 계산 방식:**
1. 좌표 파싱 결과를 "정답"으로 설정
2. 각 AI 방식의 필드별 결과값을 정답과 문자열 비교 (strip + lower 후)
3. `일치 필드 수 / 전체 필드 수 × 100` = 해당 방식의 정확도(%)
4. 5회 평균값을 최종 보고서에 기재

### 실행 명령
```powershell
cd D:\program\SQM_inventory\SQM_v865_CLEAN
python scripts\run_comparison_windows.py
```

결과 HTML을 `REPORTS\parse_comparison_6method_final.html`에 저장.

---

## Agent B — 프론트엔드 버그 수정 (최우선 2건)

### B-1: `_zFloatTop` IIFE 스코프 오류 수정 (Critical)

**파일:** `frontend/js/sqm-inline.js`  
**위치:** line 2053 (변수 선언부)

**문제 설명:**  
`_zFloatTop`과 `_bringToFront()` 함수는 IIFE(`(function(){...})()`) 내부에 선언되어 있다.  
그런데 HTML 문자열 안에 `onmousedown="..._zFloatTop"` 형태로 인라인 이벤트로 참조하면,  
HTML 인라인 이벤트는 **전역 스코프(window)**만 보기 때문에 `_zFloatTop`을 찾지 못해  
`ReferenceError: _zFloatTop is not defined`가 발생한다.  
이 오류는 OneStop 등 핵심 모달 화면의 드래그를 완전히 막는 장애다.

**수정 방법 (Python 스크립트로 처리):**
```python
# Step 1: sqm-inline.js를 UTF-8로 읽기
# Step 2: _zFloatTop 변수 선언을 IIFE 바깥 window 스코프로 노출
#   변경 전: var _zFloatTop = 10100;
#   변경 후: window._sqmZ = window._sqmZ || 10100;
#            function _bringToFront(el){ el.style.zIndex = ++window._sqmZ; }
# Step 3: 인라인 onmousedown에서 _zFloatTop 참조 → window._sqmZ 로 교체
# Step 4: 단일 write (newline='\n', encoding='utf-8')
# Step 5: node --check 로 문법 검증
```

**검증:** `node --check frontend/js/sqm-inline.js` → 0 errors

---

### B-2: `config_logging.py` CP949 UnicodeEncodeError 수정

**파일:** `config_logging.py`  
**위치:** line 52–61 (StreamBridge.write 메서드)

**문제 설명:**  
현재 `self._original.write(s)`는 원본 콘솔 스트림에 문자열을 그대로 쓴다.  
Windows CMD/PowerShell 환경의 기본 인코딩은 CP949(EUC-KR)이며,  
이모지(`📦`, `✅`)나 일부 유니코드가 로그에 섞이면  
`UnicodeEncodeError: 'cp949' codec can't encode character`가 발생해  
실제 장애 로그가 묻혀버린다.

**수정 방법:**
```python
# 변경 전 (line 57-61):
try:
    self._original.write(s)
except (OSError, ValueError) as e:
    logger.debug(f"[write] Suppressed: {e}")

# 변경 후:
try:
    enc = getattr(self._original, 'encoding', 'utf-8') or 'utf-8'
    safe = s.encode(enc, errors='replace').decode(enc)
    self._original.write(safe)
except (OSError, ValueError, UnicodeError) as e:
    logger.debug(f"[write] Suppressed: {e}")
```

**검증:** `python -c "import config_logging"` → 오류 없음

---

## Agent C — 백엔드 안정화 (3건 + Ruby 자체 추가)

### C-1: `carriers.py` GET 엔드포인트 쓰기 작업 분리

**파일:** `backend/api/carriers.py`  
**위치:** line 55–87 (`list_carriers`, `get_carrier`)

**문제 설명:**  
`list_carriers()`와 `get_carrier()`가 `_ensure_default_carriers(con)`을 호출하며  
`INSERT OR IGNORE` + `commit()`을 수행한다.  
읽기 전용 GET 요청이 DB 쓰기 잠금까지 유발하므로, 동시 요청 시 락 경합·응답 지연이 생긴다.  
특히 FastAPI가 동시 요청을 처리할 때 SQLite WAL 모드가 아니면 `database is locked` 오류로 이어질 수 있다.

**수정 방법:**
```python
# 모듈 레벨에 초기화 완료 플래그 추가
_carriers_initialized = False

def _ensure_default_carriers_once():
    """앱 기동 시 1회만 실행 (GET 요청마다 실행하지 않음)"""
    global _carriers_initialized
    if _carriers_initialized:
        return
    con = _get_con()
    try:
        _ensure_default_carriers(con)
    finally:
        con.close()
    _carriers_initialized = True

# list_carriers, get_carrier에서 _ensure_default_carriers(con) 호출 제거
# 대신 backend/app.py 의 startup 이벤트에 _ensure_default_carriers_once() 등록
```

`backend/app.py`에 startup 이벤트 추가:
```python
@app.on_event("startup")
def _init_carriers():
    from backend.api.carriers import _ensure_default_carriers_once
    _ensure_default_carriers_once()
```

**검증:** GET `/api/carriers` 10회 동시 호출 시 DB locked 오류 없음

---

### C-2: `inbound.py` 예외 처리 가시성 개선

**파일:** `backend/api/inbound.py`  
**위치:** line 628–641 (템플릿 조회), line 681–685 (크로스체크)

**문제 설명:**  
아래 두 구간이 `except Exception: pass` 또는 로그만 남기고 사용자에게 실패를 알리지 않는다.

1. 템플릿 조회 구간 (line 641): `except Exception: pass` → 어느 단계에서 깨졌는지 전혀 모름
2. 크로스체크 구간 (line 681): `logger.warning`만 남기고 `xc_summary = "크로스체크 엔진 미실행"` 반환 → OneStop 결과 화면에서 사용자가 부분 성공을 정상으로 착각

**수정 방법:**
```python
# 1. 템플릿 조회 예외 처리 개선
try:
    ...
except Exception as e:
    logger.warning(f"[onestop] 템플릿 조회 실패 (무시): {e}")
    tpl_product = ""  # 명시적으로 공백으로 fallback
    # 응답에 fallback 경고 추가 (warn_messages 리스트에 append)

# 2. 크로스체크 예외 시 응답 warn_messages에 포함
# xc_summary에 실패 원인 포함: "크로스체크 엔진 오류: {e.__class__.__name__}"
# 프론트엔드 파싱 로그 패널에 표시
```

프론트엔드(`sqm-inline.js`)의 파싱 결과 영역에 `warn_messages` 배열을 렌더링하는 로직 추가:  
- 성공한 단계: ✅ 표시  
- 실패·fallback 단계: ⚠️ + 원인 표시

---

### C-3: Ruby 자체 추가 검토 항목

Agent C가 위 2건 완료 후 아래 항목을 자체 검토하여 필요하면 즉시 수정:

1. **`backend/app.py` SQLite WAL 모드 활성화**  
   현재 SQLite가 WAL 모드 비활성 상태이면 동시 읽기/쓰기 시 locked 오류 가능.  
   `PRAGMA journal_mode=WAL` 설정을 startup에서 실행.

2. **`backend/api/inbound.py` 임시 파일 누수 확인**  
   `tmp_paths` 딕셔너리의 NamedTemporaryFile이 예외 발생 시 삭제되지 않을 수 있음.  
   `finally` 블록에서 `os.unlink` 처리가 완전한지 확인.

3. **FastAPI CORS 설정 강화**  
   현재 `allow_origins=["*"]`라면 운영 환경 배포 전 특정 origin으로 제한.  
   PyWebView가 `null` origin을 보내므로 `["null", "http://localhost"]` 형태로 설정.

---

## Agent D — 6방식 비교 UI: 초보자/숙련자 선택 UX

### 목적
`scripts/run_comparison_windows.py` 실행 시, 또는 프론트엔드 OneStop 파싱 설정 화면에서  
**"좌표 파싱(①)"은 항상 체크(고정·비활성화)**하고,  
**나머지 5개 방식(②~⑥)은 사용자가 체크박스로 선택**할 수 있도록 개선한다.

### 변경 대상

#### D-1: `scripts/run_comparison_windows.py` CLI 파라미터 추가
```
# 현재: 6방식 모두 고정 실행
# 변경 후:
python scripts\run_comparison_windows.py --methods coord,gemini,openai
# 또는 인터랙티브 메뉴 (--interactive 플래그)
```

메뉴 예시:
```
  [기본값 — 초보자 추천]
    ✅ ① 좌표 파싱   (항상 실행, 로컬)
    ✅ ② Gemini      (권장)
    ☐  ③ Groq        (선택)
    ☐  ④ xAI Grok   (선택)
    ☐  ⑤ OpenRouter  (선택)
    ☐  ⑥ OpenAI     (선택)

  [숙련자 모드: --all]
    ✅ 모든 방식 실행
```

#### D-2: `REPORTS/parse_comparison_6method.html` UI 상단 체크박스 패널
HTML 결과 파일 상단에 JavaScript 체크박스 패널 추가:

**기본값(Default — 체크됨):**
- `① 좌표 파싱`: 항상 체크, `disabled` (사용자가 끌 수 없음 — 항상 실행)
- `② Gemini`: 기본 체크 (권장, 가장 정확)
- `⑤ OpenRouter`: 기본 체크 (무료 fallback)

**옵션(사용자 선택 — 기본 미체크):**
- `③ Groq`: 기본 미체크 (선택 시 실행)
- `④ xAI Grok`: 기본 미체크 (선택 시 실행)
- `⑥ OpenAI`: 기본 미체크 (선택 시 실행)

- 체크박스 토글 → 해당 열 show/hide
- "전체 비교" 버튼: 6개 모두 체크
- 체크 상태는 `localStorage`에 저장 (새로고침 시 유지)

#### D-3: OneStop 파싱 설정 화면 (sqm-inline.js 연동)
OneStop 모달의 "파싱 방식" 선택 섹션에 동일한 UX 적용:

**기본 실행(고정):**
- `① 좌표 파싱`: 항상 실행 (비활성 체크박스)
- `② Gemini`: 기본 체크 (권장)
- `⑤ OpenRouter`: 기본 체크 (Gemini 실패 시 fallback)

**선택 사항:**
- `③ Groq`, `④ xAI`, `⑥ OpenAI`: 기본 미체크 → 체크 시 fallback chain에 추가
- 실행 순서: 좌표 → Gemini → OpenRouter → (선택된 나머지 순서대로)

> ⚠️ sqm-inline.js 수정은 반드시 Python 스크립트로 처리

---

## 실행 순서 및 병렬 가능 여부

```
병렬 실행 가능 (독립):
  Agent A  — 테스트 실행 (파일 수정 없음)
  Agent B  — 프론트엔드 수정 (JS, config_logging.py)
  Agent C  — 백엔드 수정 (carriers.py, inbound.py, app.py)

Agent A, B, C 완료 후:
  Agent D  — UI 선택기 (B 완료 후 sqm-inline.js에 의존)
```

---

## Definition of Done (완료 기준)

| 항목 | 완료 기준 |
|------|----------|
| Agent A | `REPORTS/parse_comparison_6method_final.html` 생성, 정확도 테이블 포함 |
| Agent B-1 | `node --check sqm-inline.js` 통과, OneStop 드래그 ReferenceError 없음 |
| Agent B-2 | `python -c "import config_logging"` 통과, 이모지 로그 UnicodeError 없음 |
| Agent C-1 | GET `/api/carriers` 10회 동시 호출 시 DB locked 오류 없음 |
| Agent C-2 | OneStop 파싱 결과에 ✅/⚠️ 단계별 상태 표시 |
| Agent D | 좌표(①) 고정체크 + 나머지 5개 사용자 선택 UI 작동 |
| 전체 | `pytest tests/test_parser_regression.py` → 14 passed, 1 skipped 유지 |

---

## 파일별 수정 담당 정리

| 파일 | 담당 | 수정 방식 |
|------|------|----------|
| `frontend/js/sqm-inline.js` | Agent B, D | Python 스크립트 (Edit 금지) |
| `config_logging.py` | Agent B | Edit 툴 가능 (소형 파일) |
| `backend/api/carriers.py` | Agent C | Edit 툴 가능 |
| `backend/api/inbound.py` | Agent C | Edit 툴 가능 |
| `backend/app.py` | Agent C | Edit 툴 가능 |
| `scripts/run_comparison_windows.py` | Agent D | Edit 툴 가능 |
| `REPORTS/parse_comparison_6method_final.html` | Agent A | 신규 생성 |

---

## 주의사항

1. **회귀 테스트 보호:** 모든 수정 후 `pytest tests/test_parser_regression.py` 실행 → 15 passed 유지
2. **Git 커밋은 사장님 승인 후:** 모든 에이전트 완료 → 사장님 검수 → 커밋
3. **절대경로 하드코딩 금지:** `from config import DB_PATH` 패턴 사용
4. **인코딩:** 모든 파일 UTF-8 + LF (`newline='\n'`)

---

*Ruby — Senior Software Architect / SQM v8.6.5*
