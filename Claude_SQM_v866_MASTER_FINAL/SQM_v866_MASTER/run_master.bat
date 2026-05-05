@echo off
chcp 949 > nul
cd /d D:\program\SQM_inventory\SQM_v866_CLEAN

set MAX_RETRY=5
set COUNT=0
set PYTHONPATH=%CD%

echo.
echo ============================================
echo   SQM v866 Sub-Agent Team Auto-Retry
echo   Ruby 2026-05-01 / 목표 완수율 97%
echo ============================================
echo.

if not exist env_check_done.txt (
    echo [PRE] env_check.bat 를 먼저 실행하세요.
    choice /C YN /M "지금 실행? Y=예 N=아니오"
    if errorlevel 2 goto END
    call env_check.bat
    echo. > env_check_done.txt
)

python scripts\telegram_notify.py start
echo [TG] 시작 알림 전송 완료
echo.

:LOOP
set /a COUNT+=1
echo [%DATE% %TIME%] ===== 실행 %COUNT%회차 =====

if exist DONE.md (
    echo [OK] DONE.md 확인 - 작업 완료!
    python scripts\telegram_notify.py done
    type DONE.md
    goto END
)

if exist SUMMARY.md (
    echo [CTX] SUMMARY.md 존재 - Agent에게 전달
)

if exist progress.txt (
    echo [RESUME] 마지막 완료 지점:
    type progress.txt
    echo.
)

echo [RUN] Sub-Agent Team 시작...
claude "SQM_v866_MASTER_FINAL.md 를 읽어라. CLAUDE.md 를 읽어라. docs/handoff/ 3개 JSON을 읽어라. SUMMARY.md 가 있으면 읽어라. progress.txt 가 있으면 읽어서 마지막 DONE 다음 TASK 부터 시작해라. MASTER Agent 로서 Agent A(프론트JS) Agent B(백엔드API) Agent C(버그수정) Agent D(검증ZIP) 팀을 이끌어라. 각 SYNC 포인트마다 python scripts\telegram_notify.py 를 호출해라. 에러 발생 시 RETRY PROTOCOL 3회 후 STOP. 판단 불가 에러(OperationalError, ModuleNotFoundError, node not found) 즉시 STOP."

echo.
echo [CHECK] 결과 확인 중...

if exist DONE.md (
    python scripts\telegram_notify.py done
    type DONE.md
    goto END
)

if exist error_report.md (
    echo [FAIL] 자동 수정 불가 에러 발생
    python scripts\telegram_notify.py blocked "자동수정불가" "error_report.md 참고"
    type error_report.md
    goto END
)

if %COUNT% GEQ %MAX_RETRY% (
    echo [WARN] 최대 재시도 초과
    python scripts\telegram_notify.py blocked "최대재시도초과" "%COUNT%회 실패"
    goto END
)

echo [WAIT] 10초 후 재시도 (%COUNT%/%MAX_RETRY%)...
timeout /t 10 /nobreak > nul
goto LOOP

:END
echo.
echo [END] 총 %COUNT%회 실행
pause
