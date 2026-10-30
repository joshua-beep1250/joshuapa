@echo off
setlocal
title WING Stock - Run
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
echo WING Stock - Windows fix v2
echo.
if not exist "pyproject.toml" goto not_unpacked
if not exist ".venv\Scripts\python.exe" goto needs_setup
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto needs_setup

echo Opening WING in a browser. Keep this window open for instructions.
echo.
if exist "config.local.json" (
  ".venv\Scripts\python.exe" -m wing_stock.cli --config "config.local.json"
) else (
  ".venv\Scripts\python.exe" -m wing_stock.cli
)
set "WING_RUN_RESULT=%ERRORLEVEL%"
if not "%WING_RUN_RESULT%"=="0" goto failed
echo.
echo [OK] Report complete. See the output folder.
pause
exit /b %WING_RUN_RESULT%

:not_unpacked
echo [ERROR] Extract ALL files from the ZIP before running this program.
goto finish_error

:needs_setup
echo [ERROR] Python environment is missing or invalid.
echo Open setup_windows.bat first and wait for Installation complete.
goto finish_error

:failed
echo.
echo [ERROR] The program stopped. Read the error above before closing.
echo If a browser or package is missing, run setup_windows.bat again.

:finish_error
echo Pressing a key closes this window; it does not retry the program.
pause
exit /b 1
