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
echo ===============================================================================
echo.
echo Select an option:
echo.
echo   [1] Direct Mode - Visible Browser GUI [Recommended]
echo   [2] Direct Mode - Headless Background [Fast]
echo   [3] Unlimited Loop - Continuous runs with 1-2 min random delay
echo   [4] Counted Loop - Run N registrations with 1-2 min random delay
echo   [5] AI Agent Mode - browser-use [Requires API key in .env]
echo   [6] Show Help / CLI Options
echo   [0] Exit
echo.
echo ===============================================================================
set /p "CHOICE=Enter choice [1-6, 0]: "

if "%CHOICE%"=="1" goto opt_direct_headed
if "%CHOICE%"=="2" goto opt_direct_headless
if "%CHOICE%"=="3" goto opt_loop_unlimited
if "%CHOICE%"=="4" goto opt_loop_counted
if "%CHOICE%"=="5" goto opt_agent
if "%CHOICE%"=="6" goto opt_help
if "%CHOICE%"=="0" goto end

echo [!] Invalid selection. Please choose 1-6 or 0.
timeout /t 2 >nul
goto menu

:opt_direct_headed
echo.
echo [*] Launching Direct Mode in Headed Browser...
python main.py --mode direct --headed
goto pause_and_menu

:opt_direct_headless
echo.
echo [*] Launching Direct Mode Headless...
python main.py --mode direct
goto pause_and_menu

:opt_loop_unlimited
echo.
echo [*] Starting Unlimited Loop Mode - Press Ctrl+C to stop...
python main.py --mode direct --headed --loop --delay-min 60 --delay-max 120
goto pause_and_menu

:opt_loop_counted
echo.
set /p "NUM_RUNS=How many registrations to run? (e.g. 5, 10): "
echo [*] Running %NUM_RUNS% registrations...
python main.py --mode direct --headed --loop --count %NUM_RUNS% --delay-min 60 --delay-max 120
goto pause_and_menu

:opt_agent
echo.
echo [*] Starting browser-use Agent Mode...
echo [*] Ensure your API key is configured in .env
python main.py --mode browser-use --headed
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
