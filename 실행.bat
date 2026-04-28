@echo off
chcp 65001 > nul
title SQM Inventory v8.6.5 - 광양창고
cd /d "%~dp0"
echo.
echo ====================================================
echo  SQM Inventory v8.6.5 - 광양창고
echo ====================================================
echo.
echo  진입점: main_webview.py
echo  포트  : http://127.0.0.1:8765
echo.
python main_webview.py
REM PyWebView는 정상 종료 시에도 exit code 1을 반환 (알려진 동작)
REM 실제 오류는 exit code 2 이상
if errorlevel 2 (
    echo.
    echo [ERROR] 실행 실패. 다음을 확인하세요:
    echo   1. Python 3.10+ 설치     ^(python --version^)
    echo   2. 의존성 설치           ^(pip install -r requirements_webview.txt^)
    pause
)
