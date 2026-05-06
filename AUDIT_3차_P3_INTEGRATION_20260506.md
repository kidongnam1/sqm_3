# 3차 감사 보고서 — P1+P2+P3 통합 (database.py)

**일자:** 2026-05-06
**대상:** `engine_modules/database.py` lines 855–930
**감사자:** 3차 통합 감사관

## Executive verdict: 🟡 (Yellow — ship-blockers 없음, 개선 권장 1건)

코드는 동작하며 회귀 위험은 낮음. 다만 (a) 인터프리터 종료 시점에 워커 스레드 데몬화가 Python 3.9+에 암묵 의존하고, (b) 모듈 로컬 import 위치 컨벤션 위반이 사소한 스타일 부담으로 남음.

## 1. atexit timing analysis
- LIFO 순서로 `_db_executor.shutdown(wait=False)`가 실행됨 → DB executor가 다른 콜러보다 **먼저 등록**되면 후행 콜러의 atexit이 실행될 때 executor는 이미 shutdown된 상태. `submit()` 호출 시 `RuntimeError: cannot schedule new futures after shutdown` 가능.
- **현재 상태:** `engine_modules/__init__.py` line 9에서 `database`를 즉시 import → 패키지를 처음 import한 시점이 가장 빠르므로 executor는 보통 **가장 먼저 등록 = 가장 늦게 실행**. 따라서 일반적인 종료 경로에서 안전.
- **잔존 리스크:** late-shutdown 경로에서 새 작업이 큐에 들어올 가능성은 낮음. **수용 가능**.

## 2. Module reload edge case
- `importlib.reload(database)` 시 새 `_db_executor`가 생성되지만 atexit는 **구 executor의 shutdown bound method**를 보유 → 신 executor는 종료 콜백 없음. 리소스 누수.
- SQM 프로덕션에서 reload를 쓰지 않으므로 **수용 가능**. (pytest fixture 등 테스트 환경에서만 주의)

## 3. Python version assumption (★ 최우선 개선점)
- `ThreadPoolExecutor` 워커 스레드의 `daemon` 기본값은 **Python 3.9부터 True**. Python 3.7/3.8에서는 non-daemon → `wait=False`여도 인터프리터가 워커 종료까지 대기하여 **shutdown 효과 무력화**.
- 리포지토리에 `requires-python` 명시 없음 (`pyproject.toml`/`setup.py` 미확인). 런타임 코드는 `sys.version_info`만 출력 용도로 사용.
- **권고:** docstring 또는 모듈 상단에 "Python 3.9+ assumed (ThreadPoolExecutor daemon workers)" 명시, 또는 명시적 데몬 보강 (아래 hot-fix).

## 4. Integration risks (P1+P2+P3 import graph)
- `engine_modules/__init__.py` → `database` (eager). 따라서 `_db_executor`는 패키지 첫 import 시 즉시 4개 워커 스레드 풀 컨테이너 생성 (lazy spawn).
- `main_webview.py` 자체는 `database`/`engine_modules`를 직접 import하지 않음 (grep 0건). PyWebView 이벤트 루프는 메인 스레드 GUI 루프이며, ThreadPoolExecutor는 별도 스레드 풀이라 **충돌 없음**.
- `features/ai/ollama_manager.py` 는 `database`/`engine_modules` 미참조 → 순환 import 리스크 0.
- 직접 호출자: `engine_modules/inventory_modular/engine.py`, `backend/api/{actions2,inventory_adjust_api}.py`, `gui_app_modular/dialogs/...`, `features/ai/gemini_chat_query.py`. 모두 `from engine_modules.database import SQMDatabase` 패턴, executor에 의존하지 않음. **통합 안전.**

## 5. on_done 콜백 스레드 안전성
- 현재 docstring (`UI code is responsible for marshalling the on_done result back to the UI thread if needed`, lines 862-863) 명시 있음. **충분.**
- 단, 콜백은 worker thread에서 실행됨이 명시되지 않음 — "from a follow-up thread"로 모호. 향후 PyWebView/Tk 콜백에서 직접 UI를 건드릴 위험 존재 → 사용 예시 1줄 추가 권장.

## 6. 권장 hot-fix (선택, 비차단)
1. **Python 3.9+ 보장 또는 명시적 데몬화** (가장 우선):
   - `pyproject.toml`에 `requires-python = ">=3.9"` 추가, 또는
   - 명시적 `_db_executor._adjust_thread_count()` 후 `for t in _db_executor._threads: t.daemon = True` (private API라 비권장).
2. `import atexit as _atexit`를 파일 상단 import 블록으로 이동 (PEP 8 / E402). 동작 동일, 가독성↑.
3. on_done docstring 사용 예시 1줄 보강 (UI 마샬링 패턴).
4. (선택) `_db_executor`를 `WeakValueDictionary` 또는 모듈 함수로 lazy 생성 → reload 안전성 확보.

## 결론
P1+P2+P3 통합은 **기능적으로 통과**. Python 3.9 미만 환경에서만 잠재적 종료 지연 이슈 존재. 프로덕션이 3.9+로 고정돼 있다면 현 상태로 출시 가능, 단 docstring에 1줄 명시 권장.
