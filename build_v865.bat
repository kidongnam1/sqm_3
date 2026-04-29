@echo off
chcp 65001 > nul
title SQM v865 - EXE 빌드
cd /d "%~dp0"

echo.
echo ====================================================
echo  SQM Inventory v865 - EXE 빌드 시작
echo  %date% %time%
echo ====================================================
echo.

REM ── 1. 회귀 테스트 Gate ──────────────────────────────
echo [1/5] 회귀 테스트 실행 (Gate Check)...
python -m pytest tests/test_phase5_parity.py -q --tb=line 2>&1
if errorlevel 1 (
    echo.
    echo [FAIL] 회귀 테스트 실패 - 빌드를 중단합니다.
    echo        tests/test_phase5_parity.py 오류를 먼저 수정하세요.
    pause
    exit /b 1
)
echo [PASS] 회귀 테스트 통과
echo.

REM ── 2. 기존 빌드 캐시 정리 ───────────────────────────
echo [2/5] 이전 빌드 정리...
if exist dist\SQM_v865.exe (
    del /f dist\SQM_v865.exe
    echo   dist\SQM_v865.exe 삭제 완료
)
if exist build\SQM_v865 (
    rmdir /s /q build\SQM_v865
    echo   build\SQM_v865\ 삭제 완료
)
echo.

REM ── 3. PyInstaller 설치 확인 ─────────────────────────
echo [3/5] PyInstaller 확인...
python -m PyInstaller --version > nul 2>&1
if errorlevel 1 (
    echo   PyInstaller 미설치 - 설치 중...
    pip install pyinstaller==6.2.0
)
python -m PyInstaller --version
echo.

REM ── 4. EXE 빌드 ──────────────────────────────────────
echo [4/5] EXE 빌드 시작...
echo   spec: SQM_v865.spec
echo   모드: onefile / no console
echo   예상 소요 시간: 2~5분
echo.
python -m PyInstaller SQM_v865.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [FAIL] 빌드 실패. 위 오류를 확인하세요.
    pause
    exit /b 1
)
echo.

REM ── 5. 빌드 결과 검증 ────────────────────────────────
echo [5/5] 빌드 결과 확인...
if exist dist\SQM_v865.exe (
    for %%A in (dist\SQM_v865.exe) do (
        set SIZE=%%~zA
        echo.
        echo ====================================================
        echo  [SUCCESS] 빌드 성공!
        echo  파일: dist\SQM_v865.exe
        echo  크기: %%~zA bytes
        echo  날짜: %%~tA
        echo ====================================================
    )
    echo.
    echo  다음 단계:
    echo  1. dist\SQM_v865.exe 더블클릭으로 실행 테스트
    echo  2. sqm_debug.log 로 정상 기동 확인
    echo  3. 메뉴/탭 기본 동작 확인 후 GY Logis 배포
    echo.
) else (
    echo [FAIL] dist\SQM_v865.exe 파일이 없습니다.
    pause
    exit /b 1
)

pause
