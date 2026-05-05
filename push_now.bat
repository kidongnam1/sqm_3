@echo off
cd /d "D:\program\SQM_inventory\SQM_v865_CLEAN"
if exist ".git\index.lock" del /f /q ".git\index.lock"
if exist ".git\HEAD.lock" del /f /q ".git\HEAD.lock"
if exist ".git\refs\heads\main.lock" del /f /q ".git\refs\heads\main.lock"
git log --oneline -3
git push origin main
pause
