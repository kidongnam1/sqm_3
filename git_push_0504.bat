@echo off
chcp 65001 > nul
echo ===== SQM v866 Git Push 2026-05-04 =====
cd /d "D:\program\SQM_inventory\SQM_v866_CLEAN"

if exist ".git\index.lock" (
    del ".git\index.lock"
    echo index.lock removed
)

git add CLAUDE.md
git commit -m "docs: CLAUDE.md 2026-05-04 handoff - integrity check 16 files restored"
git push origin main

echo ===== DONE =====
pause
