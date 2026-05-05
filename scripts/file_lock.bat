@echo off
setlocal

if "%~1"=="" goto :help

python "%~dp0file_lock_manager.py" %*
exit /b %errorlevel%

:help
echo Usage:
echo   scripts\file_lock.bat acquire --file frontend/js/sqm-tonbag.js --session S1
echo   scripts\file_lock.bat status  --file frontend/js/sqm-tonbag.js
echo   scripts\file_lock.bat release --file frontend/js/sqm-tonbag.js --session S1
echo   scripts\file_lock.bat list
exit /b 1

