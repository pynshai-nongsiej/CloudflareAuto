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

:: Referral Accounts
set "ACCOUNT_1_URL=https://websurfer.1024tenbox.com/referral/XWUPKX2D"
set "ACCOUNT_1_EMAIL=pn@gmail.com"
set "ACCOUNT_2_URL=https://websurfer.1024tenbox.com/referral/XUMZDQ5R"
set "ACCOUNT_2_EMAIL=dd@gmail.com"
set "ACCOUNT_3_URL=https://websurfer.1024tenbox.com/referral/75H3QGGK"
set "ACCOUNT_3_EMAIL=jn@gmail.com"
set "ACCOUNT_4_URL=https://websurfer.1024tenbox.com/referral/8PCCMJ33"
set "ACCOUNT_4_EMAIL=dai@gmail.com"

set "TARGET_URL=%ACCOUNT_2_URL%"
set "TARGET_EMAIL=%ACCOUNT_2_EMAIL%"

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
echo Target Account: %TARGET_EMAIL%
echo Target URL    : %TARGET_URL%
echo ===============================================================================
echo.
echo Select an option:
echo.
echo   [1] Direct Mode - Single Run (Headless)
echo   [2] Unlimited Loop - 1-2 min delay (Headless)
echo   [3] Counted Loop - Run N registrations with 1-2 min delay (Headless)
echo   [4] Multi-Window Grid Launcher (5 Tiled Workers with Staggered Delays)
echo   [5] Stop All Running Workers
echo   [6] AI Agent Mode - browser-use (Headless) [Requires API key in .env]
echo   [7] Switch Target Referral Account (pn, dd, jn, dai, custom)
echo   [8] Show Help / CLI Options
echo   [0] Exit
echo.
echo ===============================================================================
set /p "CHOICE=Enter choice [1-8, 0]: "

if "%CHOICE%"=="1" goto opt_direct_single
if "%CHOICE%"=="2" goto opt_loop_unlimited
if "%CHOICE%"=="3" goto opt_loop_counted
if "%CHOICE%"=="4" goto opt_multi
if "%CHOICE%"=="5" goto opt_stop
if "%CHOICE%"=="6" goto opt_agent
if "%CHOICE%"=="7" goto opt_switch_account
if "%CHOICE%"=="8" goto opt_help
if "%CHOICE%"=="0" goto end

echo [!] Invalid selection. Please choose 1-7 or 0.
timeout /t 2 >nul
goto menu

:opt_direct_single
echo.
echo [*] Launching Direct Mode (Headless)...
python main.py --mode direct --target-url "%TARGET_URL%"
goto pause_and_menu

:opt_loop_unlimited
echo.
echo [*] Starting Unlimited Loop Mode (Headless) - Press Ctrl+C to stop...
python main.py --mode direct --loop --delay-min 0 --delay-max 0 --target-url "%TARGET_URL%"
goto pause_and_menu

:opt_loop_counted
echo.
set /p "NUM_RUNS=How many registrations to run? (e.g. 5, 10): "
echo [*] Running %NUM_RUNS% registrations (Headless)...
python main.py --mode direct --loop --count %NUM_RUNS% --delay-min 0 --delay-max 0 --target-url "%TARGET_URL%"
goto pause_and_menu

:opt_multi
echo.
echo [*] Launching Multi-Window Tiled Grid Launcher...
call launch_multi_windows.bat
goto pause_and_menu

:opt_stop
echo.
call launch_multi_windows.bat stop
goto pause_and_menu

:opt_agent
echo.
echo [*] Starting browser-use Agent Mode (Headless)...
echo [*] Ensure your API key is configured in .env
python main.py --mode browser-use --target-url "%TARGET_URL%"
goto pause_and_menu

:opt_switch_account
cls
echo ===============================================================================
echo                   Select Target Referral Account
echo ===============================================================================
echo.
echo   [1] %ACCOUNT_1_EMAIL%  -^> %ACCOUNT_1_URL%
echo   [2] %ACCOUNT_2_EMAIL%  -^> %ACCOUNT_2_URL% (Default Windows)
echo   [3] %ACCOUNT_3_EMAIL%  -^> %ACCOUNT_3_URL%
echo   [4] %ACCOUNT_4_EMAIL%  -^> %ACCOUNT_4_URL%
echo   [5] Custom URL
echo.
set /p "ACC_CHOICE=Select account [1-5, Enter to cancel]: "
if "%ACC_CHOICE%"=="1" (
    set "TARGET_URL=%ACCOUNT_1_URL%"
    set "TARGET_EMAIL=%ACCOUNT_1_EMAIL%"
)
if "%ACC_CHOICE%"=="2" (
    set "TARGET_URL=%ACCOUNT_2_URL%"
    set "TARGET_EMAIL=%ACCOUNT_2_EMAIL%"
)
if "%ACC_CHOICE%"=="3" (
    set "TARGET_URL=%ACCOUNT_3_URL%"
    set "TARGET_EMAIL=%ACCOUNT_3_EMAIL%"
)
if "%ACC_CHOICE%"=="4" (
    set "TARGET_URL=%ACCOUNT_4_URL%"
    set "TARGET_EMAIL=%ACCOUNT_4_EMAIL%"
)
if "%ACC_CHOICE%"=="5" (
    set /p "CUSTOM_URL=Enter custom referral URL: "
    if not "!CUSTOM_URL!"=="" (
        set "TARGET_URL=!CUSTOM_URL!"
        set "TARGET_EMAIL=Custom Account"
    )
)
goto menu

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
