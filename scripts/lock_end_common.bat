@echo off
setlocal

set SESSION=%~1
if "%SESSION%"=="" set SESSION=DEFAULT

echo [LOCK END] session=%SESSION%
call "%~dp0file_lock.bat" release --file frontend/js/sqm-tonbag.js --session %SESSION%
call "%~dp0file_lock.bat" release --file frontend/css/v864-layout.css --session %SESSION%

echo [OK] common locks released (or no lock).
exit /b 0

