@echo off
REM Anthropic 키는 Windows 사용자/시스템 환경변수 ANTHROPIC_API_KEY 에 두면 됩니다.
REM (Python 프로세스가 상속받음 — CMD 에서 set 할 필요 없음)
chcp 949 > nul
cd /d D:\program\SQM_inventory\SQM_v866_CLEAN
set PYTHONPATH=%CD%

echo ============================================
echo   SQM v866 — run_master (Anthropic API)
echo   scripts\run_master_api.py
echo ============================================
python scripts\telegram_notify.py start 2>nul
echo.

echo [PHASE 1] Bug Fix...
if exist progress.txt (
    findstr /C:"DONE: PHASE1" progress.txt >nul 2>&1
    if not errorlevel 1 goto PHASE2
)
python scripts\run_master_api.py --phase 1
if errorlevel 1 goto API_FAIL
if exist error_report.md (
    echo [RECOVER] Phase1 error_report — API 복구 프롬프트
    python scripts\run_master_api.py --recover
    if errorlevel 1 goto API_FAIL
    del /q error_report.md 2>nul
)
python scripts\telegram_notify.py sync1 3 2>nul
echo DONE: PHASE1 >> progress.txt
timeout /t 30 /nobreak > nul

:PHASE2
echo.
echo [PHASE 2] Backend API...
if exist progress.txt (
    findstr /C:"DONE: PHASE2" progress.txt >nul 2>&1
    if not errorlevel 1 goto PHASE3
)
python scripts\run_master_api.py --phase 2
if errorlevel 1 goto API_FAIL
if exist error_report.md (
    echo [RECOVER] Phase2 error_report — API 복구 프롬프트
    python scripts\run_master_api.py --recover
    if errorlevel 1 goto API_FAIL
    del /q error_report.md 2>nul
)
python scripts\telegram_notify.py sync2 4 2>nul
echo DONE: PHASE2 >> progress.txt
timeout /t 30 /nobreak > nul

:PHASE3
echo.
echo [PHASE 3] Frontend JS...
if exist progress.txt (
    findstr /C:"DONE: PHASE3" progress.txt >nul 2>&1
    if not errorlevel 1 goto PHASE4
)
python scripts\run_master_api.py --phase 3
if errorlevel 1 goto API_FAIL
if exist error_report.md (
    echo [RECOVER] Phase3 error_report — API 복구 프롬프트
    python scripts\run_master_api.py --recover
    if errorlevel 1 goto API_FAIL
    del /q error_report.md 2>nul
)
python scripts\telegram_notify.py sync3 5 2>nul
echo DONE: PHASE3 >> progress.txt
timeout /t 30 /nobreak > nul

:PHASE4
echo.
echo [PHASE 4] QA and ZIP...
python scripts\run_master_api.py --phase 4
if errorlevel 1 goto API_FAIL
if exist error_report.md (
    echo [RECOVER] Phase4 error_report — API 복구 프롬프트
    python scripts\run_master_api.py --recover
    if errorlevel 1 goto API_FAIL
    del /q error_report.md 2>nul
)
if exist DONE.md goto SUCCESS
goto FAILED

:SUCCESS
echo.
echo [DONE] All phases API prompts complete. DONE.md 확인.
python scripts\telegram_notify.py done 2>nul
if exist DONE.md type DONE.md
goto END

:FAILED
echo.
echo [WARN] DONE.md 없음 — Phase4 체크리스트 수동 완료 필요
goto END

:API_FAIL
echo.
echo [FAIL] Anthropic API 호출 실패. REPORTS\run_master_last_api_response.txt 및 로그 확인.
exit /b 1

:END
echo.
echo [END] Finished
pause
exit /b 0
