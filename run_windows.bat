@echo off
setlocal EnableDelayedExpansion
title CloudflareAuto - TenBox Websurfer Launcher
chcp 65001 >nul 2>&1

:: Check if virtualenv exists
if not exist ".venv\Scripts\activate.bat" (
    echo [X] Virtual environment not found at .venv
    echo [*] Please run setup_windows.bat first to install all requirements.
    echo.
    pause
    exit /b 1
)

:: Activate virtualenv
call .venv\Scripts\activate.bat

:: If arguments were passed directly from command line, forward them
if not "%~1"=="" (
    python main.py %*
    goto end
)

:menu
cls
echo ===============================================================================
echo                CloudflareAuto / TenBox Websurfer Automation
echo                           (All Options Headless)
echo ===============================================================================
echo.
echo Select an option:
echo.
echo   [1] Direct Mode - Single Run (Headless)
echo   [2] Unlimited Loop - Continuous runs with 15-30s delay (Headless)
echo   [3] Counted Loop - Run N registrations with 15-30s delay (Headless)
echo   [4] AI Agent Mode - browser-use (Headless) [Requires API key in .env]
echo   [5] Show Help / CLI Options
echo   [0] Exit
echo.
echo ===============================================================================
set /p "CHOICE=Enter choice [1-5, 0]: "

if "%CHOICE%"=="1" goto opt_direct_single
if "%CHOICE%"=="2" goto opt_loop_unlimited
if "%CHOICE%"=="3" goto opt_loop_counted
if "%CHOICE%"=="4" goto opt_agent
if "%CHOICE%"=="5" goto opt_help
if "%CHOICE%"=="0" goto end

echo [!] Invalid selection. Please choose 1-5 or 0.
timeout /t 2 >nul
goto menu

:opt_direct_single
echo.
echo [*] Launching Direct Mode (Headless)...
python main.py --mode direct
goto pause_and_menu

:opt_loop_unlimited
echo.
echo [*] Starting Unlimited Loop Mode (Headless) - Press Ctrl+C to stop...
python main.py --mode direct --loop --delay-min 15 --delay-max 30
goto pause_and_menu

:opt_loop_counted
echo.
set /p "NUM_RUNS=How many registrations to run? (e.g. 5, 10): "
echo [*] Running %NUM_RUNS% registrations (Headless)...
python main.py --mode direct --loop --count %NUM_RUNS% --delay-min 15 --delay-max 30
goto pause_and_menu

:opt_agent
echo.
echo [*] Starting browser-use Agent Mode (Headless)...
echo [*] Ensure your API key is configured in .env
python main.py --mode browser-use
goto pause_and_menu

:opt_help
echo.
python main.py --help
goto pause_and_menu

:pause_and_menu
echo.
echo ===============================================================================
echo Execution finished. Press any key to return to menu...
pause >nul
goto menu

:end
