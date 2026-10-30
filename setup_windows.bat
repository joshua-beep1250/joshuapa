@echo off
setlocal
title WING Stock - Setup
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
if not exist "pyproject.toml" goto not_unpacked

echo WING Stock Setup - Browser update v3
echo.
set "WING_PYTHON=py -3"
%WING_PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 goto python_ready
set "WING_PYTHON=python"
%WING_PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto no_python

:python_ready
set "WING_SETUP_STEP=Creating Python environment"
echo [1/3] %WING_SETUP_STEP%...
%WING_PYTHON% -m venv ".venv"
if errorlevel 1 goto fail
set "WING_SETUP_STEP=Installing Python packages"
echo [2/3] %WING_SETUP_STEP%...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -e .
if errorlevel 1 goto fail
set "WING_SETUP_STEP=Installing Chromium browser"
echo [3/3] %WING_SETUP_STEP%...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto fail
echo.
echo [OK] Installation complete. Now open run_windows.bat.
pause
exit /b 0

:not_unpacked
echo [ERROR] Project files are missing.
echo Right-click the ZIP file and select Extract All first.
goto finish_error

:no_python
echo [ERROR] Python 3.10 or newer was not found.
echo Install Python from https://www.python.org/downloads/
echo Enable the Python launcher and Add python.exe to PATH.
echo Then close this window and open setup_windows.bat again.
goto finish_error

:fail
echo.
echo [ERROR] Setup failed: %WING_SETUP_STEP%.
echo Read the error above or take a screenshot before closing.

:finish_error
echo Pressing a key closes this window; it does not start the program.
pause
exit /b 1
