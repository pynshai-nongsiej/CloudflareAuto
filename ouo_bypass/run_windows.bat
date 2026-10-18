@echo off
REM ─────────────────────────────────────────────────────────
REM OUO.io Link Bypass Bot — Windows Launch Script
REM ─────────────────────────────────────────────────────────
REM Usage:
REM   ouo_bypass\run_windows.bat                       headless continuous loop
REM   ouo_bypass\run_windows.bat --headed              visible browser
REM   ouo_bypass\run_windows.bat --headed --count 5    process 5 links, stop
REM ─────────────────────────────────────────────────────────

chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%\.."

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.8+ first.
    pause
    exit /b 1
)

REM Check Playwright
python -c "import playwright" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Playwright...
    pip install playwright
    python -m playwright install chromium
)

echo.
echo Starting OUO.io Bypass Bot...
echo.

cd /d "%PROJECT_ROOT%"
python ouo_bypass\main.py %*

pause
