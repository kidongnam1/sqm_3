# run_master — Anthropic API 대체 초안

`run_master.bat` 안의 `claude --print`는 Claude Code **구독/크레딧**에 묶일 수 있습니다.  
대신 **Anthropic Messages API**(유료 API 키)로 같은 **페이즈별 지시 프롬프트**를 받으려면 아래를 사용합니다.

## 파일

| 파일 | 역할 |
|------|------|
| `scripts/run_master_api.py` | `MASTER_P1~P4`, `CLAUDE.md`, `progress.txt`(및 복구 시 `error_report.md`)를 읽어 API로 전송 |
| `run_master_api.bat` | 기존 `run_master.bat`와 동일 분기(PHASE1~4, 스킵 규칙), 호출만 Python API 스크립트로 교체 |

## 준비

1. [Anthropic Console](https://console.anthropic.com/)에서 API 키 발급·결제 확인  
2. **환경 변수 `ANTHROPIC_API_KEY`** — 보통 아래 중 하나로 등록해 두면 됩니다.  
   - Windows: **설정 → 시스템 → 정보 → 고급 시스템 설정 → 환경 변수** (사용자 또는 시스템)  
   - Cursor/터미널은 새 세션부터 해당 변수를 상속합니다.  
   - 이미 등록했다면 **CMD에서 `set` 할 필요 없음**.  

선택 (세션 한정으로만 덮어쓸 때):

```bat
set ANTHROPIC_API_KEY=sk-ant-api03-...
set ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

3. 단일 페이즈만 테스트:

```bat
cd /d D:\program\SQM_inventory\SQM_v866_CLEAN
python scripts\run_master_api.py --phase 1
```

응답 본문은 콘솔에 출력되고, **`REPORTS/run_master_last_api_response.txt`** 에도 저장됩니다.

## 전체 실행

```bat
run_master_api.bat
```

## 한계 (반드시 읽기)

- 이 방식은 **텍스트 답변만** 받습니다. **파일 수정·터미너 명령 실행·ZIP 생성은 하지 않습니다.**  
  실제 적용은 Cursor/사람이 수행합니다.  
- `CLAUDE.md` 등이 길면 내부에서 잘릴 수 있습니다. 환경변수 **`RUN_MASTER_MAX_CONTEXT_CHARS`**(기본 180000)로 상한을 조정할 수 있습니다.  
- **`ANTHROPIC_API_KEY`를 저장소에 커밋하지 마세요.** ENV 또는 로컬 전용 설정만 사용하세요.

## 원래 배치와 병행

- 기존 `run_master.bat`는 그대로 두었습니다.  
- API만 쓸 때는 **`run_master_api.bat`** 만 실행하면 됩니다.
