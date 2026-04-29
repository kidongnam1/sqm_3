@echo off
REM ═══════════════════════════════════════════════════════════════════
REM SQM v864.3 — PyInstaller + Inno Setup 연쇄 빌드
REM 작성: Ruby, Tier 3 S2, 2026-04-21
REM
REM 실행:
REM   F:\program\SQM_inventory\Claude_SQM_v864_3>installer\build.bat
REM
REM 산출물:
REM   - build\dist\SQM_v864_3.exe        (PyInstaller 포터블)
REM   - installer\dist\SQM_v864_3_Setup.exe (Inno Setup 설치본)
REM ═══════════════════════════════════════════════════════════════════

setlocal
cd /d %~dp0..

echo [1/3] 이전 빌드 정리...
if exist build\dist rmdir /s /q build\dist
if exist installer\dist rmdir /s /q installer\dist

echo [2/3] PyInstaller 실행...
pyinstaller build\SQM_v864_3.spec --noconfirm
if errorlevel 1 (
    echo PyInstaller 실패 — 중단
    exit /b 1
)

echo [3/3] Inno Setup 실행...
REM Inno Setup 설치 경로 자동 탐지
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if %ISCC%=="" (
    echo [WARN] Inno Setup 미설치 — ZIP 포터블만 제공
    powershell -Command "Compress-Archive -Path 'build\dist\SQM_v864_3.exe' -DestinationPath 'build\dist\SQM_v864_3_portable.zip' -Force"
    echo Portable ZIP: build\dist\SQM_v864_3_portable.zip
    exit /b 0
)

%ISCC% installer\SQM_v864_3_Setup.iss
if errorlevel 1 (
    echo Inno Setup 실패
    exit /b 1
)

echo.
echo ════════════════════════════════════════════════════
echo 빌드 완료:
echo   - build\dist\SQM_v864_3.exe
echo   - installer\dist\SQM_v864_3_Setup.exe
echo ════════════════════════════════════════════════════
endlocal
