@echo off
setlocal EnableDelayedExpansion

title CloudflareAuto - Windows Setup Wizard
echo ===============================================================================
echo                CloudflareAuto / TenBox Automation Setup
echo                              (Windows OS)
echo ===============================================================================
echo.

:: 1. Check for Python
echo [*] Checking for Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    py --version >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [X] Python was not found in your system PATH!
        echo.
        echo Please install Python 3.10 or higher from:
        echo    https://www.python.org/downloads/
        echo.
        echo IMPORTANT: When installing, make sure to check:
        echo    [x] "Add python.exe to PATH"
        echo.
        pause
        exit /b 1
    ) else (
        set "PY_CMD=py"
    )
) else (
    set "PY_CMD=python"
)

for /f "tokens=*" %%i in ('%PY_CMD% --version') do set "PY_VER=%%i"
echo [+] Found %PY_VER%
echo.

:: 2. Setup Virtual Environment
if not exist ".venv" (
    echo [*] Creating virtual environment (.venv)...
    %PY_CMD% -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [X] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [+] Virtual environment created.
) else (
    echo [+] Existing .venv directory found.
)
echo.

:: 3. Activate Virtual Environment & Upgrade pip
echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
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
if %ERRORLEVEL% neq 0 (
    echo [X] Failed to install Python dependencies.
    pause
    exit /b 1
)
echo [+] Python dependencies installed successfully.
echo.

:: 5. Install Playwright Browsers
echo [*] Installing Playwright Chromium browser binary...
playwright install chromium
if %ERRORLEVEL% neq 0 (
    echo [!] Playwright install had a warning or error. Trying with python -m playwright...
    python -m playwright install chromium
)
echo [+] Playwright Chromium ready.
echo.

:: 6. Setup .env file
if not exist ".env" (
    if exist ".env.example" (
        echo [*] Creating .env file from .env.example...
        copy .env.example .env >nul
        echo [+] Created .env. You can add your API keys there if using AI mode.
    )
)

:: 7. Check for Node.js (Optional, for Cloudflare worker)
echo.
echo [*] Checking for Node.js (optional, for Cloudflare Worker)...
node -v >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=*" %%i in ('node -v') do set "NODE_VER=%%i"
    echo [+] Node.js detected: !NODE_VER!
    if not exist "node_modules" (
        echo [*] Installing Node.js packages with npm install...
        call npm install
    ) else (
        echo [+] Node modules already installed.
    )
) else (
    echo [!] Node.js not detected. (Only needed if modifying/deploying the Cloudflare Worker).
    echo     Python automation will work 100%% without Node.js!
)

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
