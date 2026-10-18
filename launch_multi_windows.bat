@echo off
setlocal EnableDelayedExpansion
title CloudflareAuto - Windows Multi-Session Launcher
chcp 65001 >nul 2>&1

:: Check if stop command requested
if /i "%~1"=="stop" (
    echo ================================================================
    echo   Stopping all CloudflareAuto workers on Windows...
    echo ================================================================
    taskkill /F /FI "WINDOWTITLE eq Worker-*" >nul 2>&1
    taskkill /F /IM python.exe >nul 2>&1
    echo   [+] All workers stopped.
    echo ================================================================
    exit /b 0
)

:: Check if virtual environment exists
if not exist "%~dp0.venv\Scripts\python.exe" (
    if not exist "%~dp0venv\Scripts\python.exe" (
        echo [!] Virtual environment not detected at .venv or venv.
        echo [*] Running setup_windows.bat to initialize environment...
        call "%~dp0setup_windows.bat"
    )
)

:: Forward all execution to launch_multi_windows.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_multi_windows.ps1" %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Launcher exited with error code %ERRORLEVEL%.
    pause
)
