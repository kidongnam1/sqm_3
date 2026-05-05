@echo off
setlocal

set SESSION=%~1
if "%SESSION%"=="" set SESSION=DEFAULT

echo [LOCK START] session=%SESSION%
call "%~dp0file_lock.bat" acquire --file frontend/js/sqm-tonbag.js --session %SESSION%
if errorlevel 1 (
  echo [FAILED] frontend/js/sqm-tonbag.js
  exit /b 1
)

call "%~dp0file_lock.bat" acquire --file frontend/css/v864-layout.css --session %SESSION%
if errorlevel 1 (
  echo [FAILED] frontend/css/v864-layout.css
  echo [ROLLBACK] releasing previously acquired lock...
  call "%~dp0file_lock.bat" release --file frontend/js/sqm-tonbag.js --session %SESSION%
  exit /b 1
)

echo [OK] common locks acquired.
exit /b 0

