# SQM v8.6.5 Ollama 자동화 패치 지시서

작성일: 2026-04-28  
대상 폴더: `D:\program\SQM_inventory\SQM_v865_CLEAN`

## 목적

AI fallback에서 Ollama를 실사용 가능하게 만들기 위해 다음 과정을 프로그램 안에서 자동화한다.

```text
1. Ollama 설치 여부 확인
2. localhost:11434 health check
3. 서버 꺼져 있으면 ollama serve 백그라운드 실행
4. qwen2.5:14b 모델 존재 여부 확인
5. 모델이 없으면 사용자 확인 후 ollama pull 실행
6. 설정창에 Ollama 상태 표시
```

## 기본 정책

- Ollama는 무료/로컬 AI provider다.
- API key는 사용하지 않는다.
- 자동 설치는 하지 않는다. 설치가 안 되어 있으면 설치 안내만 표시한다.
- `ollama serve`는 사용자가 허용한 경우에만 백그라운드 실행한다.
- `ollama pull`은 대용량 다운로드이므로 반드시 사용자 확인 후 실행한다.
- 모델 다운로드 중에는 GUI가 멈추면 안 된다.
- 실패해도 전체 프로그램 실행은 막지 않는다. Gemini/Groq/OpenRouter 등 다음 provider 흐름은 유지한다.

## 수정 대상 파일

### 1. 신규 파일: `features/ai/ollama_manager.py`

역할:

- Ollama CLI 설치 여부 확인
- Ollama 서버 health check
- Ollama 서버 백그라운드 실행
- 설치된 모델 목록 조회
- 모델 pull 실행
- 설정창/파서에서 사용할 상태 객체 제공

권장 구조:

```python
from dataclasses import dataclass


@dataclass
class OllamaStatus:
    installed: bool
    server_running: bool
    model_available: bool
    cli_path: str = ""
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:14b"
    message: str = ""


def find_ollama_cli() -> str:
    ...


def check_ollama_server(base_url: str = "http://localhost:11434") -> bool:
    ...


def start_ollama_server() -> bool:
    ...


def list_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    ...


def has_ollama_model(model: str, base_url: str = "http://localhost:11434") -> bool:
    ...


def pull_ollama_model(model: str) -> bool:
    ...


def get_ollama_status(base_url: str, model: str) -> OllamaStatus:
    ...
```

구현 세부:

```text
find_ollama_cli()
  - shutil.which("ollama") 우선
  - Windows 기본 설치 경로 후보 확인
  - 없으면 "" 반환

check_ollama_server()
  - GET http://localhost:11434/api/tags
  - 2초 timeout
  - 성공 시 True

start_ollama_server()
  - subprocess.Popen(["ollama", "serve"], ...)
  - Windows에서는 CREATE_NO_WINDOW 또는 STARTUPINFO 사용
  - 실행 후 1~3초 health check retry

list_ollama_models()
  - GET /api/tags
  - models[].name 추출

has_ollama_model()
  - 정확히 qwen2.5:14b 또는 태그 prefix 일치 확인

pull_ollama_model()
  - subprocess.Popen(["ollama", "pull", model])
  - GUI thread에서 직접 wait 금지
```

### 2. 수정 파일: `features/ai/local_llm_parser.py`

수정 내용:

- Ollama parser 생성 전에 `ollama_manager.get_ollama_status()`를 선택적으로 호출한다.
- 서버가 꺼져 있으면 자동 실행이 허용된 경우만 `start_ollama_server()`를 호출한다.
- 모델이 없으면 명확한 RuntimeError를 반환한다.

주의:

- 파싱 중에 모델 pull을 자동으로 시작하지 않는다.
- 모델 pull은 설정창에서 사용자 확인 후 수행한다.

### 3. 수정 파일: `config.py`

추가 설정:

```ini
[Ollama]
base_url = http://localhost:11434
model = qwen2.5:14b
auto_start = true
auto_pull_confirm = true
```

추가 상수:

```python
OLLAMA_AUTO_START = _settings.get("ollama_auto_start", True)
OLLAMA_AUTO_PULL_CONFIRM = _settings.get("ollama_auto_pull_confirm", True)
```

`get_settings()`에도 같은 값을 포함한다.

### 4. 수정 파일: `core/config.py`

`config.py`에서 추가된 Ollama 상수를 re-export한다.

```python
OLLAMA_AUTO_START
OLLAMA_AUTO_PULL_CONFIRM
```

### 5. 수정 파일: `gui_app_modular/dialogs/settings_dialog.py`

설정창의 AI Fallback 정책 영역에 Ollama 상태 표시를 추가한다.

필수 UI:

```text
Ollama 상태:
  설치: 확인됨 / 미설치
  서버: 실행 중 / 중지
  모델: qwen2.5:14b 있음 / 없음

[Ollama 상태 새로고침]
[Ollama 서버 시작]
[qwen2.5:14b 모델 다운로드]
```

동작:

```text
Ollama 상태 새로고침
  - get_ollama_status() 호출
  - 결과 label 갱신

Ollama 서버 시작
  - 설치되어 있지 않으면 설치 안내
  - 설치되어 있으면 start_ollama_server()
  - 성공/실패 메시지 표시

qwen2.5:14b 모델 다운로드
  - 반드시 확인창 표시
  - 다운로드는 background thread에서 실행
  - 완료 후 상태 새로고침
```

확인창 문구:

```text
Ollama 모델 qwen2.5:14b를 다운로드합니다.
파일 크기가 클 수 있고 시간이 오래 걸릴 수 있습니다.
계속할까요?

[다운로드] [취소]
```

### 6. 수정 파일: `parsers/document_parser_modular/ai_fallback.py`

수정 내용:

- Ollama provider 호출 전 상태 확인을 강화한다.
- 서버가 꺼져 있고 `OLLAMA_AUTO_START=true`이면 서버 시작을 1회 시도한다.
- 모델이 없으면 Ollama provider를 실패 처리하고 다음 provider로 넘어간다.
- 이 실패는 전체 파싱 실패가 아니라 provider skip으로 처리한다.

로그 예:

```text
[Ollama] CLI not installed - skipping local provider
[Ollama] server not running - auto start attempted
[Ollama] model qwen2.5:14b not found - skipping provider
```

## 금지 사항

- 프로그램 시작 시 무조건 `ollama pull` 실행 금지
- 사용자의 확인 없이 모델 다운로드 금지
- Ollama 미설치 상태에서 프로그램 실행 차단 금지
- Ollama 실패를 전체 입고 파싱 실패로 즉시 처리 금지
- API key 입력란에 `ollama_key` 같은 항목 추가 금지

## 테스트 추가

### 신규 테스트 파일

```text
tests/test_ollama_manager.py
```

### 필수 테스트

```text
1. CLI 미설치 시 installed=False 반환
2. 서버 health check 실패 시 server_running=False 반환
3. /api/tags 응답에서 모델 목록을 정상 파싱
4. qwen2.5:14b 모델 존재 여부 확인
5. Ollama 미설치 시 ai_fallback router가 다음 provider로 넘어감
6. paid provider는 Ollama 실패 후에도 승인 없이는 호출되지 않음
```

mock 대상:

```text
shutil.which
urllib.request.urlopen
subprocess.Popen
```

## 완료 기준

```text
[ ] 설정창에서 Ollama 설치/서버/모델 상태가 보인다.
[ ] 서버가 꺼져 있으면 버튼으로 시작할 수 있다.
[ ] 모델이 없으면 버튼으로 다운로드할 수 있다.
[ ] 다운로드 전 사용자 확인창이 뜬다.
[ ] 다운로드 중 GUI가 멈추지 않는다.
[ ] Ollama 실패 시 다음 무료/로컬 provider로 넘어간다.
[ ] 유료 AI는 여전히 사용자 승인 전 호출되지 않는다.
[ ] python -m compileall -q . 통과
[ ] tests/test_ollama_manager.py 통과
[ ] tests/test_ai_fallback_policy.py 통과
[ ] tests/test_ai_fallback_router.py 통과
```

## 구현 우선순위

1. `features/ai/ollama_manager.py` 작성
2. manager 단위 테스트 작성
3. `local_llm_parser.py`에 상태 확인 연결
4. `ai_fallback.py`에서 Ollama 실패 시 skip 처리 확인
5. `config.py`, `core/config.py` 설정 추가
6. `settings_dialog.py`에 상태 표시와 버튼 추가
7. compileall 및 테스트 실행

