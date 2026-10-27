@echo off
setlocal EnableDelayedExpansion
title CloudflareAuto - 10-Worker Auto-Rotator & Dashboard
chcp 65001 >nul 2>&1

cd /d "%~dp0"

:: Check if virtual environment exists
set "PYTHON=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON=%~dp0venv\Scripts\python.exe"
)

:: Run Windows auto rotator
"%PYTHON%" "%~dp0rotate_and_run_windows.py" %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Auto-rotator exited with error code %ERRORLEVEL%.
    pause
)
