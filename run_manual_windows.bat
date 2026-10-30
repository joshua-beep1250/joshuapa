@echo off
setlocal
title WING Stock - Normal browser download
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
echo WING Stock - Browser update v3 - Manual download
echo This mode uses your normal browser. Log in and download the file yourself.
echo.
if not exist "pyproject.toml" goto not_unpacked
if not exist ".venv\Scripts\python.exe" goto needs_setup
if exist "config.local.json" (
  ".venv\Scripts\python.exe" -m wing_stock.cli --manual-download --config "config.local.json"
) else (
  ".venv\Scripts\python.exe" -m wing_stock.cli --manual-download
)
set "WING_RUN_RESULT=%ERRORLEVEL%"
if not "%WING_RUN_RESULT%"=="0" goto failed
echo [OK] Report complete. See the output folder.
pause
exit /b 0

:not_unpacked
echo [ERROR] Extract ALL files from the ZIP first.
goto finish_error

:needs_setup
echo [ERROR] Run setup_windows.bat first.
goto finish_error

:failed
echo [ERROR] Read the error above before closing.

:finish_error
pause
exit /b 1
