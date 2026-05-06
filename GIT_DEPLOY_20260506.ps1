# =============================================================================
# SQM Async UI Thread Patch - Git Deploy Script
# Date     : 2026-05-06
# Branch   : main
# Remote   : origin
# Pre-tag  : pre-async-patch-20260506 (already created before patch)
# Post-tag : post-async-patch-20260506 (will be created at end)
# =============================================================================

# 0) 작업 디렉토리 이동
Set-Location "D:\program\SQM_inventory\SQM_v866_CLEAN"

# 1) 현재 상태 먼저 확인 (대표님 눈으로 검토)
Write-Host "=== git status ===" -ForegroundColor Cyan
git status

Write-Host ""
Write-Host "=== git diff --stat (변경 라인 요약) ===" -ForegroundColor Cyan
git diff --stat

Write-Host ""
Write-Host "=== 최근 커밋 3개 ===" -ForegroundColor Cyan
git log --oneline -3

Write-Host ""
Write-Host "=== pre-async tag 확인 ===" -ForegroundColor Cyan
git tag --list "pre-async-*"

# =============================================================================
# 대표님 확인 후 아래 명령 한 줄씩 실행
# (위 git status 출력이 예상한 변경 목록과 일치하는지 반드시 확인)
# =============================================================================

# --- (A) 변경(modified) 파일 stage ---
# git add main_webview.py
# git add features/ai/ollama_manager.py
# git add engine_modules/database.py

# --- (B) 신규 추가 - 테스트 ---
# git add tests/test_frontend_connection.py
# git add tests/COMPATIBILITY_REPORT_20260506.md

# --- (C) 신규 추가 - 핵심 보고서 ---
# git add MANUAL_SMOKE_CHECKLIST.md
# git add SQM_PATCH_FINAL_REPORT_2026-05-06.md
# git add SQM_WORK_ORDER_2026-05-06.md
# git add REPORT_1차_2026-05-06.md
# git add REPORT_2차_2026-05-06.md
# git add REPORT_3차_2026-05-06.md

# --- (D) 신규 추가 - 감사(AUDIT) 파일들 (패턴으로 한 번에) ---
# git add "AUDIT_2차_*_20260506.md"
# git add "AUDIT_3차_*_20260506.md"
# git add "AUDIT_4차_*_20260506.md"
# git add "AUDIT_5차_*_20260506.md"
# # (6차가 추가되어 있다면 아래 줄도 실행)
# # git add "AUDIT_6차_*_20260506.md"

# --- (E) 신규 추가 - 재사용 템플릿 ---
# git add templates/sqm-patch-work-order.md
# git add templates/three-pass-verification.md
# git add templates/js-reentry-guard.md

# --- (F) Stage 결과 한 번 더 확인 ---
# git status
# git diff --cached --stat

# --- (G) 커밋 (heredoc 으로 멀티라인) ---
# git commit -m "fix(ui): resolve UI thread freeze via async dispatch + JS reentry guard" `
#            -m "P1 (main_webview.py): wrap blocking calls in QThreadPool worker; UI" `
#            -m "    thread no longer freezes during PDF parse / DB write." `
#            -m "P2 (ollama_manager.py): make health-check + model load asynchronous;" `
#            -m "    add timeout + cancellable future so cold-start cannot block UI." `
#            -m "P3 (engine_modules/database.py): switch to short-lived connections" `
#            -m "    + WAL mode; eliminates lock contention with worker threads." `
#            -m "" `
#            -m "Verification: 1차 (정합성), 2차 (P1/P2/P3/Q1/DOCS 분할 감사)," `
#            -m "    3차 (Syntax / P1 / P3 통합 / Compliance / Docs)," `
#            -m "    4차 (P1 fix verify + stress), 5차 (HOLISTIC) 모두 통과." `
#            -m "" `
#            -m "CRITICAL (3차 발견): JS->Python bridge 재진입(recursion) 가드 누락." `
#            -m "    main_webview.py 에 _bridge_busy 플래그 + try/finally 가드 추가." `
#            -m "    재현 조건(빠른 더블클릭) 시 dead-loop 발생 -> 패치로 차단." `
#            -m "" `
#            -m "Refs: SQM_PATCH_FINAL_REPORT_2026-05-06.md," `
#            -m "      SQM_WORK_ORDER_2026-05-06.md," `
#            -m "      MANUAL_SMOKE_CHECKLIST.md" `
#            -m "" `
#            -m "Pre-patch baseline: pre-async-patch-20260506"

# --- (H) 원격에 push ---
# git push origin main

# --- (I) annotated tag 생성 + push ---
# git tag -a post-async-patch-20260506 -m "SQM Async UI Thread Patch - Post deploy" `
#                                       -m "P1: UI thread async dispatch (main_webview.py)" `
#                                       -m "P2: Ollama manager async health-check (ollama_manager.py)" `
#                                       -m "P3: DB short-lived connection + WAL (database.py)" `
#                                       -m "Critical fix (3차): JS bridge reentry guard" `
#                                       -m "Verified: 1차/2차/3차/4차/5차 pass" `
#                                       -m "Baseline tag: pre-async-patch-20260506"
# git push origin post-async-patch-20260506

# =============================================================================
# 사후 검증 (push 끝나면 자동으로 실행해도 안전)
# =============================================================================

# Write-Host ""
# Write-Host "=== POST-DEPLOY VERIFICATION ===" -ForegroundColor Green
# Write-Host ""
# Write-Host "[1] 최근 커밋 3개 (방금 만든 commit 이 최상단이어야 함)" -ForegroundColor Yellow
# git log --oneline -3
#
# Write-Host ""
# Write-Host "[2] post-async tag 목록" -ForegroundColor Yellow
# git tag --list "post-async-*"
#
# Write-Host ""
# Write-Host "[3] 원격(origin)과 동기화 상태" -ForegroundColor Yellow
# git status -sb
#
# Write-Host ""
# Write-Host "[4] tag 가 원격에도 올라갔는지" -ForegroundColor Yellow
# git ls-remote --tags origin "post-async-patch-20260506"
#
# Write-Host ""
# Write-Host "[5] pre <-> post 사이 변경 파일 수" -ForegroundColor Yellow
# git diff --stat pre-async-patch-20260506..post-async-patch-20260506 | Select-Object -Last 1
#
# Write-Host ""
# Write-Host "=== DEPLOY 완료 ===" -ForegroundColor Green
