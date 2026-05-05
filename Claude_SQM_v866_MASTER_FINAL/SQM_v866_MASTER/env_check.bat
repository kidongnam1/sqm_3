@echo off
chcp 949 > nul
cd /d D:\program\SQM_inventory\Claude_SQM_v864_3

echo.
echo ============================================
echo   SQM v864.3 환경 사전 검증 (env_check)
echo   실행 전 반드시 이것 먼저 실행하세요
echo ============================================
echo.

set PASS=0
set FAIL=0

:: Python 버전
echo [1] Python 버전 확인...
python --version
if errorlevel 1 (
    echo [FAIL] Python 을 찾을 수 없습니다
    set /a FAIL+=1
) else (
    set /a PASS+=1
)

:: NiceGUI
echo.
echo [2] NiceGUI 설치 확인...
python -c "import nicegui; print('  nicegui:', nicegui.__version__)" 2>nul
if errorlevel 1 (
    echo [FAIL] nicegui 미설치 - 설치 중...
    pip install nicegui
    set /a FAIL+=1
) else (
    set /a PASS+=1
)

:: httpx
echo.
echo [3] httpx 설치 확인...
python -c "import httpx; print('  httpx:', httpx.__version__)" 2>nul
if errorlevel 1 (
    echo [FAIL] httpx 미설치 - 설치 중...
    pip install httpx
    set /a FAIL+=1
) else (
    set /a PASS+=1
)

:: FastAPI
echo.
echo [4] FastAPI 설치 확인...
python -c "import fastapi; print('  fastapi:', fastapi.__version__)" 2>nul
if errorlevel 1 (
    echo [FAIL] fastapi 미설치 - 설치 중...
    pip install fastapi uvicorn
    set /a FAIL+=1
) else (
    set /a PASS+=1
)

:: openpyxl
echo.
echo [5] openpyxl 설치 확인...
python -c "import openpyxl; print('  openpyxl:', openpyxl.__version__)" 2>nul
if errorlevel 1 (
    echo [FAIL] openpyxl 미설치 - 설치 중...
    pip install openpyxl
    set /a FAIL+=1
) else (
    set /a PASS+=1
)

:: 포트 8765 확인
echo.
echo [6] 포트 8765 사용 여부 확인...
netstat -an | findstr "8765" > nul
if not errorlevel 1 (
    echo [WARN] 포트 8765 이미 사용 중 - 충돌 가능
) else (
    echo [OK] 포트 8765 사용 가능
    set /a PASS+=1
)

:: DB 파일 확인
echo.
echo [7] DB 파일 존재 확인...
if exist sqm_inventory.db (
    echo [OK] sqm_inventory.db 존재 확인
    set /a PASS+=1
) else (
    echo [FAIL] sqm_inventory.db 없음 - 경로 확인 필요
    set /a FAIL+=1
)

:: config.py 확인
echo.
echo [8] config.py 확인...
if exist config.py (
    echo [OK] config.py 존재 확인
    set /a PASS+=1
) else (
    echo [FAIL] config.py 없음 - 프로젝트 경로 확인 필요
    set /a FAIL+=1
)

:: PYTHONPATH 설정
echo.
echo [9] PYTHONPATH 설정...
set PYTHONPATH=%CD%
echo [OK] PYTHONPATH=%CD%
set /a PASS+=1

echo.
echo ============================================
echo   검증 결과: 통과 %PASS%개 / 실패 %FAIL%개
echo ============================================

if %FAIL% GTR 0 (
    echo.
    echo [WARN] 실패 항목이 있습니다.
    echo        위 내용 확인 후 run_master.bat 실행하세요.
) else (
    echo.
    echo [OK] 환경 검증 완료 - run_master.bat 실행 가능합니다.
)

echo.
pause
