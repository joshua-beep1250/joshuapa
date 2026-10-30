@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto fail
echo 설치 완료. run_windows.bat 를 실행하세요.
pause
exit /b 0
:fail
echo 설치 실패. Python 3.10 이상 설치 여부와 위 오류를 확인하세요.
pause
exit /b 1
