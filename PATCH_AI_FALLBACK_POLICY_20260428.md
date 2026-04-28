# SQM v8.6.5 AI Fallback 정책 패치 지시서

작성일: 2026-04-28  
대상 폴더: `D:\program\SQM_inventory\SQM_v865_CLEAN`

## 목적

Gemini 일일 한도, 503 고부하, API 장애가 발생해도 입고 서류 파싱이 중단되지 않도록 AI fallback 구조를 확장한다.

기본 원칙은 다음과 같다.

1. 기존 정규식/좌표/템플릿 파서는 항상 1순위로 사용한다.
2. AI는 부족한 필드 보강 또는 구조화 보조로만 사용한다.
3. 기본값은 무료 또는 로컬 AI만 사용한다.
4. 유료 AI는 자동 호출하지 않는다.
5. 유료 AI 호출 전에는 반드시 사용자 확인을 받는다.
6. AI 결과는 DB 저장 전에 schema 검증, 정합성 검증, 미리보기 확인을 거친다.

## 권장 호출 순서

```text
1. deterministic parser
2. Gemini free tier
3. Groq free tier
4. OpenRouter fixed free model
5. Ollama local
6. LM Studio local
7. Paid AI, user approved only
8. preview and validation before DB save
```

## 수정 대상 파일

### 1. `config.py`

AI provider 설정을 통합한다.

추가할 설정 섹션:

```ini
[AI]
free_fallback_enabled = true
local_ai_enabled = true
paid_ai_enabled = false
require_paid_confirm = true
provider_order = deterministic,gemini,groq,openrouter,ollama,lmstudio,paid_openai

[Groq]
api_key =
model = llama-3.3-70b-versatile

[OpenRouter]
api_key =
model = meta-llama/llama-3.1-8b-instruct:free

[Ollama]
base_url = http://localhost:11434
model = qwen2.5:14b

[LMStudio]
base_url = http://localhost:1234/v1
model = local-model

[OpenAI]
api_key =
model = gpt-4o-mini
enabled = false
paid_only = true
```

구현 규칙:

- API key 우선순위는 `ENV -> keyring -> settings.ini` 순서로 유지한다.
- paid provider는 `paid_ai_enabled=true`이고 사용자 승인도 받은 경우에만 실행한다.
- settings.ini에 평문 API key 저장을 기본 방식으로 사용하지 않는다.
- 기존 `DISABLE_OPENAI_FALLBACK`은 신규 정책과 호환되도록 유지하거나 deprecate 처리한다.

### 2. 신규 파일: `features/ai/ai_fallback_policy.py`

역할:

- provider별 무료/로컬/유료 여부 정의
- 현재 설정 기준으로 사용 가능한 provider 목록 생성
- paid provider 실행 가능 여부 판단

핵심 구조:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AiProviderPolicy:
    name: str
    enabled: bool
    is_paid: bool
    is_local: bool
    requires_user_confirm: bool


def build_provider_policy(settings) -> list[AiProviderPolicy]:
    ...


def can_use_paid_provider(settings, user_confirmed: bool) -> bool:
    return (
        settings.paid_ai_enabled
        and (not settings.require_paid_confirm or user_confirmed)
    )
```

### 3. 신규 파일: `features/ai/ai_fallback_router.py`

역할:

- 문서 파싱 중 AI 보강이 필요한 경우 provider 순서대로 시도
- 429, quota, 503, timeout, invalid JSON 발생 시 다음 provider로 이동
- paid provider는 승인 전 skip
- 모든 결과를 공통 schema로 normalize

구현 규칙:

- provider 실패는 전체 파싱 실패로 바로 처리하지 않는다.
- 마지막 provider까지 실패한 경우에만 사용자에게 복구 옵션을 보여준다.
- 실패 로그에는 provider 이름, 에러 종류, 다음 조치를 남긴다.
- API 응답 원문을 DB에 직접 저장하지 않는다.

### 4. 신규 파일: `features/ai/groq_parser.py`

역할:

- Groq API를 사용한 JSON 구조화 provider
- 무료 fallback provider로 동작

주의:

- Groq는 빠르지만 문서 OCR 자체보다는 추출된 텍스트 구조화에 사용한다.
- JSON schema 강제와 후처리 검증이 필수다.

### 5. 신규 파일: `features/ai/openrouter_parser.py`

역할:

- OpenRouter 무료 모델 provider

주의:

- `:free` 모델 중 하나를 고정해서 사용한다.
- 자동 라우팅 모델을 기본값으로 두지 않는다.
- 모델 변경 시 결과 품질이 변할 수 있으므로 설정 화면에 현재 모델명을 표시한다.

### 6. 신규 파일: `features/ai/local_llm_parser.py`

역할:

- Ollama, LM Studio 같은 로컬 OpenAI-compatible endpoint provider

지원 대상:

```text
Ollama:    http://localhost:11434
LM Studio: http://localhost:1234/v1
```

주의:

- 로컬 모델은 속도와 품질이 PC 사양에 따라 달라진다.
- 추천 용도는 누락 필드 보강, 문장 구조화, 후보값 제안이다.
- 최종 DB 저장 전 검증은 동일하게 수행한다.

### 7. 기존 파일 수정: `features/ai/gemini_parser.py`

수정 내용:

- 공통 provider interface에 맞춘다.
- Gemini 503, quota, rate limit 발생 시 router가 다음 provider로 넘어갈 수 있도록 명확한 예외 타입 또는 결과 코드를 반환한다.
- Gemini 실패를 전체 파싱 실패로 바로 보여주지 않는다.

### 8. 기존 파일 수정: `features/ai/openai_parser.py`

수정 내용:

- paid provider로 분류한다.
- 기본 설정에서는 자동 호출하지 않는다.
- 사용자 승인 token 또는 flag가 없는 경우 실행하지 않고 `PaidProviderSkipped` 상태를 반환한다.

### 9. 기존 파일 수정: `gui_app_modular/dialogs/settings_dialog.py`

설정 화면에 AI provider 설정을 추가한다.

필수 UI:

```text
[x] 무료 AI fallback 사용
[x] 로컬 AI fallback 사용
[ ] 유료 AI 사용 허용
[x] 유료 AI 호출 전 매번 확인

Provider 순서:
deterministic -> Gemini -> Groq -> OpenRouter -> Ollama -> LM Studio -> Paid OpenAI
```

표시할 상태:

- Gemini API key 설정 여부
- Groq API key 설정 여부
- OpenRouter API key 설정 여부
- Ollama 연결 가능 여부
- LM Studio 연결 가능 여부
- Paid OpenAI 비활성/활성 상태

### 10. 기존 파싱 흐름 수정

대상 후보:

```text
parsers/document_parser_modular/*_mixin.py
backend/api/inbound.py
gui_app_modular/dialogs/inbound_onestop_dialog.py
gui_app_modular/dialogs/parse_error_recovery_dialog.py
```

수정 내용:

- 직접 Gemini 또는 OpenAI를 호출하는 코드를 router 호출로 변경한다.
- router 결과가 `needs_paid_approval`이면 사용자 확인 dialog를 띄운다.
- AI 결과는 기존 preview table에만 반영하고 즉시 DB 저장하지 않는다.

## 유료 AI 승인 동작

유료 AI가 필요한 경우 표시 문구:

```text
무료/로컬 AI fallback으로 파싱을 완료하지 못했습니다.
유료 AI를 1회 사용해 추가 파싱을 시도할까요?

사용 provider: OpenAI
예상 작업: 현재 문서 1건 구조화

[유료 AI 사용] [취소]
```

동작 규칙:

- `취소` 선택 시 현재까지 추출된 값만 preview에 표시한다.
- `유료 AI 사용` 선택 시 현재 작업 1회에만 승인한다.
- 다음 문서에서는 다시 확인한다.
- 전역 자동 유료 호출은 기본 제공하지 않는다.

## 데이터 검증 규칙

AI provider가 반환한 값은 다음 검증을 통과해야 한다.

```text
LOT NO       비어 있으면 경고
SAP NO       known product table과 비교
BL NO        BL/D/O/Invoice 간 불일치 경고
CONTAINER    ISO container pattern 검증
NET(Kg)      숫자 변환 가능 여부
GROSS(Kg)    NET보다 작으면 경고
ARRIVAL      날짜 파싱 가능 여부
WH           등록 창고 또는 미등록 창고 경고
```

검증 실패 시:

- DB 저장 차단 또는 사용자 확인 필요
- 실패 사유를 preview table row에 표시
- 원본 문서명과 provider 이름을 같이 로그 기록

## 금지 사항

- AI 결과를 DB에 직접 저장 금지
- 유료 AI 자동 호출 금지
- settings.ini에 유료 API key 평문 저장을 기본값으로 사용 금지
- OpenRouter의 임의 자동 모델 라우팅을 기본값으로 사용 금지
- provider 실패를 숨기고 성공처럼 처리 금지
- 기존 deterministic parser를 건너뛰고 AI부터 호출 금지

## 테스트 추가

### 신규 테스트 파일

```text
tests/test_ai_fallback_policy.py
tests/test_ai_fallback_router.py
```

### 필수 테스트

```text
1. 기본 설정에서 paid provider는 실행되지 않는다.
2. Gemini 503 발생 시 Groq 또는 다음 무료 provider로 넘어간다.
3. 모든 무료 provider 실패 시 paid approval required 상태가 반환된다.
4. 사용자 승인 없이는 OpenAI provider가 skip된다.
5. 사용자 승인 후에도 결과 schema 검증 실패 시 DB 저장이 차단된다.
6. 로컬 Ollama 연결 실패 시 전체 파싱이 중단되지 않는다.
7. provider_order 설정이 실제 호출 순서에 반영된다.
```

### 기존 테스트 유지

다음 테스트는 계속 통과해야 한다.

```powershell
pytest tests/test_ai_fallback_parity.py -m integration -v --timeout=90
python -m compileall -q .
```

Gemini 503 또는 quota로 인한 skip은 허용하되, router 단위 테스트에서는 mock으로 fallback 동작을 검증해야 한다.

## 완료 기준

패치 완료 조건:

```text
[ ] 기본 실행 시 유료 AI가 호출되지 않는다.
[ ] Gemini 장애 시 무료/로컬 fallback이 자동 시도된다.
[ ] paid provider는 사용자 승인 dialog 이후 1회만 실행된다.
[ ] 파싱 결과는 preview와 검증을 거친 뒤 저장된다.
[ ] 설정 화면에서 provider 상태와 순서를 확인할 수 있다.
[ ] compileall 통과
[ ] 신규 policy/router 테스트 통과
[ ] 기존 AI fallback parity 테스트 통과 또는 외부 API 장애로 skip
```

## 구현 우선순위

1. `config.py` 설정 구조 정리
2. `ai_fallback_policy.py` 작성
3. `ai_fallback_router.py` 작성
4. 기존 Gemini/OpenAI parser를 router interface로 연결
5. Groq/OpenRouter/local provider 추가
6. 입고 서류 파싱 흐름을 router로 변경
7. 설정 dialog에 provider 제어 UI 추가
8. 테스트 추가

