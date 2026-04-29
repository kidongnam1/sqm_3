@echo off
REM ============================================================
REM  SQM v864.3 - Phase 0 Safety Net test runner
REM  Usage (from project root):
REM      scripts\run_tests.bat
REM  Exit code 0 only if pytest AND standalone smoke both pass.
REM ============================================================

setlocal EnableDelayedExpansion

REM Move to project root (parent of this script's directory)
pushd "%~dp0.."

echo.
echo ============================================================
echo  SQM v864.3 - Phase 0 test runner
echo ============================================================
echo.

REM -- Activate virtualenv if present (check venv\ first, then .venv\) --
if exist "venv\Scripts\activate.bat" (
    echo [env] Activating venv\
    call "venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
    echo [env] Activating .venv\
    call ".venv\Scripts\activate.bat"
) else (
    echo [env] No virtualenv found ^(venv\ or .venv\^) - using system Python
)

echo.
echo ------------------------------------------------------------
echo  Step 1/2 : pytest tests\ -v
echo ------------------------------------------------------------
pytest tests\ -v
set PYTEST_RC=!ERRORLEVEL!
echo.
echo [pytest] exit code: !PYTEST_RC!

echo.
echo ------------------------------------------------------------
echo  Step 2/2 : python scripts\smoke_test.py
echo ------------------------------------------------------------
python scripts\smoke_test.py
set SMOKE_RC=!ERRORLEVEL!
echo.
echo [smoke]  exit code: !SMOKE_RC!

echo.
echo ============================================================
echo  SUMMARY
echo ============================================================
if !PYTEST_RC! EQU 0 (
    echo   pytest : PASS
) else (
    echo   pytest : FAIL ^(exit !PYTEST_RC!^)
)
if !SMOKE_RC! EQU 0 (
    echo   smoke  : PASS
) else (
    echo   smoke  : FAIL ^(exit !SMOKE_RC!^)
)
echo ============================================================

popd

if !PYTEST_RC! NEQ 0 (
    exit /b 1
)
if !SMOKE_RC! NEQ 0 (
    exit /b 1
)
exit /b 0
