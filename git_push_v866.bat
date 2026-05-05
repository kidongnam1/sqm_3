@echo off
cd /d D:\program\SQM_inventory\SQM_v866_CLEAN

if exist .git\index.lock del /f .git\index.lock

echo [1/4] 미커밋 변경사항 임시 보관 (stash)...
git stash
echo stash 완료 (변경사항 없으면 "No local changes" - 정상)

echo [2/4] Remote 동기화 (pull --rebase)...
git pull --rebase origin main
if errorlevel 1 (
    echo.
    echo [ERROR] pull --rebase 실패. 충돌 확인 필요.
    git stash pop
    pause
    exit /b 1
)

echo [3/4] stash 복원...
git stash pop
echo stash pop 완료 (stash 없으면 "No stash entries" - 정상)

echo [4/4] 스테이징 + 커밋 + Push...
git add CLAUDE.md
git add RELEASE_NOTES.md
git add backend\api\__init__.py
git add backend\api\inbound.py
git add parsers\document_parser_modular\ai_fallback.py
git add parsers\document_parser_modular\bl_mixin.py
git add utils\parse_alarm.py
git add tools\fix_carrier_rules_one.py
git add git_push_v866.bat

git commit -F COMMIT_MSG_866.txt
if errorlevel 1 (
    echo [INFO] 커밋할 새 변경사항 없음 - push 진행
)

git push origin main
if errorlevel 1 (
    echo.
    echo [ERROR] push 실패.
    pause
    exit /b 1
)

echo.
echo ==============================
echo   v8.6.6 GitHub push 완료!
echo ==============================
pause
