@echo off
title CloudflareAuto - Windows Setup Wizard

echo ===============================================================================
echo                CloudflareAuto / TenBox Automation Setup
echo                              (Windows OS)
echo ===============================================================================
echo.

:: 1. Check for Python
echo [*] Checking for Python installation...
set "PY_CMD=python"
python --version >nul 2>&1
if not errorlevel 1 goto py_found

set "PY_CMD=py"
py --version >nul 2>&1
if not errorlevel 1 goto py_found

echo.
echo [X] Python was not found in your system PATH!
echo.
echo Please install Python 3.10 or higher from:
echo    https://www.python.org/downloads/
echo.
echo IMPORTANT: During Python installation, make sure to check:
echo    "Add python.exe to PATH"
echo.
pause
exit /b 1

:py_found
for /f "tokens=*" %%i in ('%PY_CMD% --version') do set "PY_VER=%%i"
echo [+] Found %PY_VER%
echo.

:: 2. Setup Virtual Environment
if exist ".venv\Scripts\activate.bat" goto venv_exists

echo [*] Creating virtual environment (.venv)...
%PY_CMD% -m venv .venv
if errorlevel 1 (
    echo [X] Failed to create virtual environment.
    pause
    exit /b 1
)
echo [+] Virtual environment created.
goto venv_ready

:venv_exists
echo [+] Existing virtual environment (.venv) found.

:venv_ready
echo.

:: 3. Activate Virtual Environment
echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [X] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [*] Upgrading pip...
python -m pip install --upgrade pip

:: 4. Install Python Dependencies
echo.
echo [*] Installing requirements from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo [X] Failed to install Python dependencies.
    pause
    exit /b 1
)
echo [+] Python dependencies installed successfully.
echo.

:: 5. Install Playwright Browsers
echo [*] Installing Playwright Chromium browser binary...
playwright install chromium
if errorlevel 1 (
    echo [*] Retrying with python -m playwright install chromium...
    python -m playwright install chromium
)
echo [+] Playwright Chromium ready.
echo.

:: 6. Setup .env file
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul 2>&1
        echo [+] Created .env file from template.
    )
)

:: 7. Check for Node.js (Optional, for Cloudflare worker)
echo [*] Checking for Node.js - optional for Cloudflare Worker...
node -v >nul 2>&1
if errorlevel 1 goto no_node

for /f "tokens=*" %%i in ('node -v') do set "NODE_VER=%%i"
echo [+] Node.js detected: %NODE_VER%
if not exist "node_modules" (
    echo [*] Installing Node.js packages with npm install...
    call npm install
) else (
    echo [+] Node modules already installed.
)
goto finish

:no_node
echo [!] Node.js not detected. Note that Python automation works 100 percent without Node.js.

:finish
echo.
echo ===============================================================================
echo                           SETUP COMPLETE!
echo ===============================================================================
echo.
echo You can now run the automation using:
echo.
echo    run_windows.bat
echo.
echo Or via Command Prompt / PowerShell:
echo    .venv\Scripts\activate
echo    python main.py --mode direct --headed
echo.
pause
