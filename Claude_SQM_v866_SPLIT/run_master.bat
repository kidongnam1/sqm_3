@echo off
chcp 949 > nul
cd /d D:\program\SQM_inventory\SQM_v866_CLEAN
set PYTHONPATH=%CD%
echo ============================================
echo   SQM v866 Sub-Agent Team 4-Phase Split
echo   Ruby 2026-05-01
echo ============================================
python scripts\telegram_notify.py start 2>nul
echo.
echo [PHASE 1] Bug Fix...
if exist progress.txt (
    findstr /C:"DONE: PHASE1" progress.txt >nul 2>&1
    if not errorlevel 1 goto PHASE2
)
claude --print "Read MASTER_P1.md and CLAUDE.md. Resume from last DONE in progress.txt. Run all Phase1 tasks. On error retry 3 times then write error_report.md and stop."
if exist error_report.md goto FAILED
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
claude --print "Read MASTER_P2.md and CLAUDE.md. Resume from last DONE in progress.txt. Run all Phase2 tasks. On error retry 3 times then write error_report.md and stop."
if exist error_report.md goto FAILED
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
claude --print "Read MASTER_P3.md and CLAUDE.md. Resume from last DONE in progress.txt. Run all Phase3 tasks. On error retry 3 times then write error_report.md and stop."
if exist error_report.md goto FAILED
python scripts\telegram_notify.py sync3 5 2>nul
echo DONE: PHASE3 >> progress.txt
timeout /t 30 /nobreak > nul
:PHASE4
echo.
echo [PHASE 4] QA and ZIP...
claude --print "Read MASTER_P4.md and CLAUDE.md. Run all verification tasks. Create Claude_SQM_v866_PATCH.zip. Create DONE.md when all checks pass."
if exist error_report.md goto FAILED
if exist DONE.md goto SUCCESS
goto FAILED
:SUCCESS
echo.
echo [DONE] All phases complete!
python scripts\telegram_notify.py done 2>nul
type DONE.md
goto END
:FAILED
echo.
echo [FAIL] Check error_report.md
python scripts\telegram_notify.py blocked AutoFixFailed SeeErrorReport 2>nul
if exist error_report.md type error_report.md
:END
echo.
echo [END] Finished
pause
