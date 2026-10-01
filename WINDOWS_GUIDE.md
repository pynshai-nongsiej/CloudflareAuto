# Windows Setup and Usage Guide

Complete, step-by-step instructions for installing and running the **TenBox Websurfer Auto-Registration & Cloudflare Private TempMail** system on **Microsoft Windows (Windows 10 / Windows 11)**.

---

## 📋 System Prerequisites

Before starting, make sure you have the following installed on Windows:

### 1. Python 3.10 or higher
- Download from the official website: [python.org/downloads](https://www.python.org/downloads/)
- ⚠️ **CRITICAL STEP DURING INSTALLATION**:
  On the very first screen of the Python installer, make sure to check the box:
  > **☑️ Add python.exe to PATH**
  *(If you missed this, re-run the installer, choose "Modify", and check "Add Python to environment variables".)*

### 2. Git for Windows
- Download from: [git-scm.com/download/win](https://git-scm.com/download/win)
- Use standard default installation options.

### 3. (Optional) Node.js (v18+)
- Download from: [nodejs.org](https://nodejs.org/)
- *Only needed if you want to run or deploy the Cloudflare Worker locally. The Python auto-registration engine works 100% without Node.js.*

---

## 🚀 Quick Start (Automated One-Click Setup)

We have provided automated batch scripts designed specifically for Windows.

### Step 1: Open the Project Directory
Open the folder in **File Explorer** where you cloned or extracted this repository.

### Step 2: Run the Setup Script
Double-click `setup_windows.bat` (or run it in Command Prompt / Terminal):

```cmd
setup_windows.bat
```

**What this script does automatically:**
1. Verifies your Python installation.
2. Creates an isolated Python virtual environment (`.venv`).
3. Activates the virtual environment and upgrades `pip`.
4. Installs all required packages from `requirements.txt`.
5. Installs the Playwright Chromium browser binary (`playwright install chromium`).
6. Creates a `.env` file from `.env.example` if it doesn't already exist.
7. Checks for Node.js and installs worker dependencies (`npm install`) if Node is available.

---

## 🎮 Running the Automation on Windows

### Method A: One-Click Interactive Launcher (`run_windows.bat`)

Double-click `run_windows.bat` or run:
```cmd
run_windows.bat
```

This opens an interactive menu:
```text
===============================================================================
                CloudflareAuto / TenBox Websurfer Automation
===============================================================================

Select an option:

  [1] Direct Mode (Visible Browser GUI - Recommended for visual feedback)
  [2] Direct Mode (Headless - Fast background execution)
  [3] Unlimited Loop (Continuous runs with 1-2 min random delay)
  [4] Counted Loop (Run N registrations with 1-2 min random delay)
  [5] AI Agent Mode (browser-use, requires OPENAI_API_KEY / GEMINI_API_KEY)
  [6] Show Help / CLI Options
  [0] Exit
```
Simply type `1`, `2`, `3`, etc., and hit Enter!

---

### Method B: Using Windows Command Prompt (`cmd.exe`)

Open Command Prompt in the repository folder and run:

1. **Activate the virtual environment**:
   ```cmd
   .venv\Scripts\activate
   ```

2. **Run single registration with visible browser UI (headed)**:
   ```cmd
   python main.py --mode direct --headed
   ```

3. **Run fast headless registration**:
   ```cmd
   python main.py --mode direct
   ```

4. **Run unlimited continuous loop with random delays (1–2 minutes / 60–120 seconds)**:
   ```cmd
   python main.py --mode direct --headed --loop --delay-min 60 --delay-max 120
   ```

5. **Run a specific number of registrations (e.g. 10 runs with 1–2 min delay)**:
   ```cmd
   python main.py --mode direct --headed --loop --count 10 --delay-min 60 --delay-max 120
   ```

---

### Method C: Using Windows PowerShell (`powershell.exe`)

If you prefer PowerShell, you can use our built-in script `run_windows.ps1` or run Python directly:

```powershell
# Run using the PowerShell helper script:
.\run_windows.ps1 -Mode direct -Headed

# Run counted loop:
.\run_windows.ps1 -Mode direct -Headed -Loop -Count 5

# Or manually in PowerShell:
.\.venv\Scripts\Activate.ps1
python main.py --mode direct --headed
```

> **Note on PowerShell Execution Policy**:
> If PowerShell displays `File cannot be loaded because running scripts is disabled on this system`, run this once:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

---

## 🤖 Running AI Agent Mode (`browser-use`)

If you want the autonomous LLM agent mode:

1. Open `.env` in Notepad or your editor:
   ```cmd
   notepad .env
   ```
2. Insert your chosen API key:
   ```env
   # Example: Using OpenAI
   OPENAI_API_KEY=sk-...
   
   # Or using Google Gemini
   GEMINI_API_KEY=AIzaSy...
   ```
3. Run:
   ```cmd
   python main.py --mode browser-use --provider openai --headed
   ```
   *(Or `--provider gemini`)*

---

## ☁️ Running / Testing the Cloudflare Worker (Optional)

If you want to test the Cloudflare TempMail worker on Windows:

1. Install dependencies:
   ```cmd
   npm install
   ```
2. Run test suite:
   ```cmd
   npm test
   ```
3. Start local development worker:
   ```cmd
   npm run dev
   ```
4. Deploy to your Cloudflare account:
   ```cmd
   npm run deploy
   ```

---

## 🛠️ Windows Troubleshooting & FAQ

### Q1: `python` or `'py'` is not recognized as an internal or external command
- **Cause**: Python was installed without checking "Add python.exe to PATH".
- **Fix**: Re-download the installer from [python.org](https://www.python.org/), click "Modify", and check "Add Python to PATH", or manually add `C:\Users\<YourUser>\AppData\Local\Programs\Python\Python3xx\` to your Windows System PATH.

### Q2: Playwright says `Executable doesn't exist at ...` or browser fails to launch
- **Cause**: The Chromium browser binaries have not been downloaded yet.
- **Fix**: Run:
  ```cmd
  .venv\Scripts\activate
  playwright install chromium
  ```

### Q3: Console emojis look garbled or display question marks (`?`)
- **Cause**: Older Windows CMD or PowerShell codepage default (`cp1252` or `cp437`).
- **Fix**: The code automatically sets UTF-8 mode on Windows. In addition, you can run:
  ```cmd
  chcp 65001
  ```
  before starting, or use **Windows Terminal** (default in Windows 11), which has native full-color emoji support.

### Q4: How do I stop an unlimited loop?
- Simply press `Ctrl + C` in the console window. The script will catch the interrupt gracefully and display a summary of successful and failed runs.

### Q5: Where are debug screenshots stored on Windows?
- If an error or unexpected screen occurs during automation, screenshots are automatically saved to your Windows temporary directory under:
  ```text
  %TEMP%\websurfer_screenshots\
  (Usually C:\Users\<Username>\AppData\Local\Temp\websurfer_screenshots\)
  ```
