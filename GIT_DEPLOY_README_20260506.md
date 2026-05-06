# GIT_DEPLOY_20260506 — 사용 안내

## 목적
SQM Async UI Thread Patch (P1/P2/P3 + 3차 발견 critical fix) 를
`main` 브랜치에 안전하게 commit / push / tag 하기 위한 **반자동 스크립트**.

## 파일
- `GIT_DEPLOY_20260506.ps1` — PowerShell 배포 스크립트 (대부분 라인이 주석 처리됨)
- `GIT_DEPLOY_README_20260506.md` — 이 문서

## 설계 원칙
**자동 실행은 위험하므로** 스크립트는 두 부분으로 나뉘어 있습니다.

1. **자동 실행 부분 (스크립트 상단)**
   - `cd` 이동
   - `git status`, `git diff --stat`, `git log --oneline -3`, `git tag --list "pre-async-*"`
   - 즉, **읽기 전용 진단**만 자동으로 실행됩니다.

2. **수동 실행 부분 (주석 처리됨)**
   - `git add`, `git commit`, `git push`, `git tag`, `git push --tags`
   - 대표님이 status 출력을 직접 확인한 뒤,
     `# 대표님 확인 후 아래 명령 한 줄씩 실행` 블록에서
     **주석(`#`)을 제거하며 한 줄씩** 실행하시면 됩니다.

## 실행 방법

```powershell
cd D:\program\SQM_inventory\SQM_v866_CLEAN
powershell -ExecutionPolicy Bypass -File .\GIT_DEPLOY_20260506.ps1
```

스크립트 실행 후 출력되는 `git status` 결과를 보고:

- 변경 파일 3개 (`main_webview.py`, `features/ai/ollama_manager.py`, `engine_modules/database.py`) 가
  `modified:` 로 떠야 함
- 신규 파일들 (`tests/test_frontend_connection.py`, `REPORT_*`, `AUDIT_*`, `templates/*` 등) 이
  `Untracked files:` 에 떠야 함

예상과 다르면 **거기서 멈추고** 차이를 점검하세요.

## 단계별 가이드

### Step A. modified 파일 stage
스크립트 (A) 블록의 `# git add ...` 3줄에서 `#` 제거 후 실행.

### Step B–E. 신규 파일 stage
패턴 add (`AUDIT_2차_*_20260506.md` 등) 가 들어 있어 한 줄씩 실행하면 묶음으로 stage 됩니다.

### Step F. stage 결과 검토
```powershell
git status
git diff --cached --stat
```
**Changes to be committed** 목록이 예상한 파일 수와 일치하는지 확인.

### Step G. commit
긴 멀티라인 커밋 메시지가 스크립트에 박혀 있습니다.
한 번에 복사 붙여넣기 하면 됩니다 (PowerShell backtick 줄 이음 사용).

### Step H. push
```powershell
git push origin main
```
**여기서 처음으로 원격이 바뀝니다.** 신중히.

### Step I. annotated tag + push
```powershell
git tag -a post-async-patch-20260506 -m "..."
git push origin post-async-patch-20260506
```

## Commit Message 미리보기

**제목**
```
fix(ui): resolve UI thread freeze via async dispatch + JS reentry guard
```

**본문 (요약)**
- P1 (`main_webview.py`): blocking call → QThreadPool worker
- P2 (`ollama_manager.py`): health-check / model load 비동기 + timeout
- P3 (`engine_modules/database.py`): short-lived conn + WAL
- Verification: 1차 / 2차 (P1/P2/P3/Q1/DOCS) / 3차 (Syntax/P1/P3/Compliance/Docs) / 4차 / 5차 모두 통과
- **CRITICAL (3차 발견)**: JS→Python bridge 재진입 가드 누락 → `_bridge_busy` 플래그 + try/finally 추가
- Refs: `SQM_PATCH_FINAL_REPORT_2026-05-06.md`, `SQM_WORK_ORDER_2026-05-06.md`, `MANUAL_SMOKE_CHECKLIST.md`
- Baseline: `pre-async-patch-20260506`

## Rollback (만약 문제 생기면)

```powershell
# 1) 로컬 되돌리기
git reset --hard pre-async-patch-20260506

# 2) 원격까지 되돌리려면 (강제 push - 신중)
git push --force-with-lease origin main

# 3) 잘못 만든 post tag 삭제
git tag -d post-async-patch-20260506
git push origin :refs/tags/post-async-patch-20260506
```

## 사후 검증 체크리스트
스크립트 하단의 **POST-DEPLOY VERIFICATION** 블록 주석을 풀고 실행하면 자동으로 확인됩니다.

- [ ] `git log --oneline -3` 의 최상단에 새 commit
- [ ] `git tag --list "post-async-*"` 가 `post-async-patch-20260506` 출력
- [ ] `git status -sb` 가 `## main...origin/main` 만 표시 (ahead/behind 없음)
- [ ] `git ls-remote --tags origin "post-async-patch-20260506"` 가 1줄 출력
- [ ] 추가로: 데스크톱에서 앱 실행 → `MANUAL_SMOKE_CHECKLIST.md` 진행

## 주의
- **이 스크립트 자체는 commit/push 를 자동으로 하지 않습니다.**
- 자동화하고 싶다면 모든 `#` 를 제거해야 하지만, 권장하지 않음.
- `pre-async-patch-20260506` tag 가 로컬에 존재하는지 스크립트 상단에서 확인됩니다.
- 만약 없다면 patch 이전 baseline 이 사라진 것이므로 **즉시 중단**하고 백업/복구를 우선하세요.
