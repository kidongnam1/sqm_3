@echo off
echo 탐색기 필터 초기화 중...

:: 폴더 뷰 설정 초기화 (필터 느림 원인)
reg delete "HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags" /f >nul 2>&1
reg delete "HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU" /f >nul 2>&1

:: 탐색기 재시작
taskkill /f /im explorer.exe >nul 2>&1
timeout /t 1 /nobreak >nul
start explorer.exe

echo 완료! 탐색기가 재시작됩니다.
