@echo off
setlocal EnableDelayedExpansion

title CloudflareAuto - TenBox Websurfer Launcher
chcp 65001 >nul 2>&1

:: Check if virtualenv exists
if not exist ".venv\Scripts\activate.bat" (
    echo [X] Virtual environment not found!
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
    goto :end
)

:menu
cls
echo ===============================================================================
echo                CloudflareAuto / TenBox Websurfer Automation
echo ===============================================================================
echo.
echo Select an option:
echo.
echo   [1] Direct Mode (Visible Browser GUI - Recommended for visual feedback)
echo   [2] Direct Mode (Headless - Fast background execution)
echo   [3] Unlimited Loop (Continuous runs with 40-45s random delay)
echo   [4] Counted Loop (Run N registrations with random delay)
echo   [5] AI Agent Mode (browser-use, requires OPENAI_API_KEY / GEMINI_API_KEY)
echo   [6] Show Help / CLI Options
echo   [0] Exit
echo.
echo ===============================================================================
set /p "CHOICE=Enter choice [1-6, 0]: "

if "%CHOICE%"=="1" (
    echo.
    echo [*] Launching Direct Mode in Headed Browser...
    python main.py --mode direct --headed
    goto :pause_and_menu
)

if "%CHOICE%"=="2" (
    echo.
    echo [*] Launching Direct Mode Headless...
    python main.py --mode direct
    goto :pause_and_menu
)

if "%CHOICE%"=="3" (
    echo.
    echo [*] Starting Unlimited Loop Mode (Press Ctrl+C to stop)...
    python main.py --mode direct --headed --loop --delay-min 40 --delay-max 45
    goto :pause_and_menu
)

if "%CHOICE%"=="4" (
    echo.
    set /p "NUM_RUNS=How many registrations to run? (e.g. 5, 10): "
    echo [*] Running !NUM_RUNS! registrations...
    python main.py --mode direct --headed --loop --count !NUM_RUNS! --delay-min 40 --delay-max 45
    goto :pause_and_menu
)

if "%CHOICE%"=="5" (
    echo.
    echo [*] Starting browser-use Agent Mode...
    echo [*] Note: Ensure your API key is in .env or your environment variables.
    python main.py --mode browser-use --headed
    goto :pause_and_menu
)

if "%CHOICE%"=="6" (
    echo.
    python main.py --help
    goto :pause_and_menu
)

if "%CHOICE%"=="0" (
    goto :end
)

echo [!] Invalid selection. Please choose 1-6 or 0.
timeout /t 2 >nul
goto :menu

:pause_and_menu
echo.
echo ===============================================================================
echo Execution finished. Press any key to return to menu...
pause >nul
goto :menu

:end
