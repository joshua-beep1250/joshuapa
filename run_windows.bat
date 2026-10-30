@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo 먼저 setup_windows.bat 를 실행하세요.
  pause
  exit /b 1
)
if exist config.local.json (
  .venv\Scripts\python.exe -m wing_stock.cli --config config.local.json
) else (
  .venv\Scripts\python.exe -m wing_stock.cli
)
set "WING_RUN_RESULT=%ERRORLEVEL%"
pause
exit /b %WING_RUN_RESULT%
