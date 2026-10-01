# CloudflareAuto & TenBox Websurfer Automation

> **Cross-Platform Auto-Registration, Disposable Email Engine & Private Cloudflare TempMail Worker**  
> Fully compatible with **Windows 10/11**, **macOS**, and **Linux**.

---

## 🌟 Overview

This repository contains an end-to-end automation suite for **TenBox Websurfer** registration and verification, coupled with a private **Cloudflare Workers** temporary email infrastructure.

It provides two core components:

1. **Python Automation Engine (`main.py`)**:
   - **Direct Mode (`playwright`)**: Ultra-fast, deterministic browser automation with zero LLM API costs.
   - **Agentic AI Mode (`browser-use`)**: Autonomous LLM agent controlling the browser with multi-provider support (OpenAI, Gemini, Anthropic, Ollama).
   - **TempMail Integration**: Integrates directly with [TempMail.Plus](https://tempmail.plus/) (and custom Cloudflare Worker inboxes) for instant disposable email generation and OTP retrieval.
   - **Anti-Detection Fingerprinting**: Fully randomized canvas, WebGL, AudioContext, User-Agent, platform, timezone, and viewport spoofing.
   - **Unlimited Loop Scheduler**: Automated batch registrations with randomized delays and live run statistics.

2. **Cloudflare Private Temp Mail Worker (`src/worker.js`)**:
   - A single-owner temporary email backend deployed on Cloudflare Workers + KV.
   - Parses incoming MIME messages, safely renders plain text, and extracts contextual numeric OTP codes.
   - Accessible via private bearer token API and web interface.

---

## 🪟 Windows Quick Start (Windows 10 / 11)

For detailed step-by-step instructions, see the dedicated [WINDOWS_GUIDE.md](file:///Users/pynshainongsiej/Desktop/CloudflareAuto/WINDOWS_GUIDE.md).

### 1. Prerequisites on Windows
- **Python 3.10+** (Ensure **"Add python.exe to PATH"** was checked during installation).
- **Git for Windows**.

### 2. Automated One-Click Setup
In the repository folder, double-click:
```cmd
setup_windows.bat
```
This automatically sets up your virtual environment (`.venv`), installs all dependencies, downloads the Playwright Chromium browser, and creates your `.env` configuration file.

### 3. Launch Automation
Double-click `run_windows.bat` or run in Command Prompt:
```cmd
run_windows.bat
```
An interactive menu lets you choose:
- Visible Browser UI (Headed)
- Headless (Background)
- Unlimited Loop with 15–30s random delays
- Counted loop (e.g. 10 runs)
- AI Agent mode

#### Or run via Command Prompt / PowerShell directly:
```cmd
.venv\Scripts\activate
python main.py --mode direct --headed
```

---

## 🍎 macOS & Linux Quick Start

### 1. Setup Virtual Environment & Dependencies
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 2. Run Automation
```bash
# Single run with visible browser
python3 main.py --mode direct --headed

# Fast headless run
python3 main.py --mode direct

# Continuous loop with random delay between 15-30 seconds
python3 main.py --mode direct --loop --delay-min 15 --delay-max 30
```

---

## ⚙️ Command-Line Options Reference

| Argument | Description | Default |
|---|---|---|
| `--mode` | Engine mode: `direct` (Playwright) or `browser-use` (AI Agent) | `direct` |
| `--headed` | Launch browser with visible GUI window | Headless |
| `--loop` | Run continuous registration loop | Disabled |
| `--count` | Number of loop runs (`0` = infinite / unlimited) | `0` |
| `--delay-min` | Minimum random delay between loop runs (seconds) | `15` |
| `--delay-max` | Maximum random delay between loop runs (seconds) | `30` |
| `--provider` | LLM provider: `openai`, `gemini`, `anthropic`, `ollama` | Auto-detect |
| `--model` | Specific LLM model name (e.g. `gpt-4o`, `gemini-2.0-flash`) | Provider default |
| `--api-key` | Provider API key override | Read from `.env` |
| `--timeout` | Timeout in seconds waiting for OTP arrival | `90` |
| `--keep-inbox` | Keep the temporary inbox active after verification | `False` (deletes inbox) |

---

## 🤖 AI Agent Mode (`browser-use`)

To use autonomous LLM agent mode:

1. Copy `.env.example` to `.env` and set your API key:
   ```env
   OPENAI_API_KEY="sk-..."
   # Or GEMINI_API_KEY="..."
   ```
2. Run with your provider:
   ```bash
   python main.py --mode browser-use --provider openai --headed
   # Or with Gemini
   python main.py --mode browser-use --provider gemini --model gemini-2.0-flash
   ```

---

## 🔄 Registration & OTP Flow

```text
+-----------------------------------------------------------------------------------+
| 1. Create temporary email address via TempMail.Plus / Cloudflare Worker           |
|    - Random pronounceable name (exact algorithm from TempMail.Plus index.js)      |
|    - Random domain selected from dropdown (@mailto.plus, @fexbox.org, etc.)       |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 2. Navigate to referral signup link                                               |
|    - Click "Get started free" CTA                                                 |
|    - Type randomized temporary email into the email field                         |
|    - Click "Send OTP"                                                             |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 3. Redirected to /otp page                                                        |
|    - Poll mailbox API until OTP arrives                                           |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 4. Verification & Dashboard Access                                                |
|    - Human-mimic input of 6-digit verification code into cells                    |
|    - Auto-submits / verifies with authentication endpoints                        |
|    - Reaches authenticated dashboard                                              |
|    - Extracts session cookies and authentication tokens (localStorage)            |
+-----------------------------------------------------------------------------------+
```

---

## ☁️ Cloudflare Worker (Private Temp Mail)

The repository also includes the private Cloudflare Worker temporary mail service:

### Local Preview
```bash
npm install
npm run dev
```

### Running Tests
```bash
npm test
```
All unit and integration tests run using Node.js's native test runner (`node --test`).

### Deployment
```bash
# 1. Authenticate Wrangler
npx wrangler login

# 2. Put admin token secret
npx wrangler secret put ADMIN_TOKEN

# 3. Deploy worker
npm run deploy
```

---

## 📁 Project Directory Structure

```text
├── .env.example                     # Environment template (API keys, secrets)
├── .gitignore                       # Multi-OS ignore rules (Windows/Mac/Linux/Python/Node)
├── AUTOMATION.md                    # Technical documentation for TenBox automation
├── WINDOWS_GUIDE.md                 # Dedicated Windows 10/11 user guide
├── README.md                        # Master documentation
├── main.py                          # Unified CLI entry point (loop scheduler & modes)
├── requirements.txt                 # Python dependencies
├── setup_windows.bat                # Windows one-click automated setup
├── run_windows.bat                  # Windows one-click interactive launcher
├── run_windows.ps1                  # Windows PowerShell launcher script
├── package.json                     # Node.js worker configuration & test runner
├── wrangler.jsonc                   # Cloudflare Worker deployment configuration
├── public/                          # Static frontend UI for private inbox
│   ├── app.js
│   ├── index.html
│   └── style.css
├── src/
│   ├── addresses.js                 # Address generator & validator
│   ├── codes.js                     # Contextual OTP extraction regex
│   ├── worker.js                    # Cloudflare Worker request handler
│   └── automation/
│       ├── __init__.py
│       ├── browser_use_automation.py # browser-use agent controller & tools
│       ├── fingerprint.py           # Stealth browser fingerprint randomizer
│       ├── playwright_automation.py # Direct Playwright high-speed automation
│       └── tempmail_client.py       # TempMail.Plus API client
└── test/
    ├── addresses.test.js            # Address generation & regex unit tests
    ├── codes.test.js                # OTP extraction unit tests
    └── worker.test.js               # Full worker lifecycle test suite
```

---

## 📜 License

MIT License. For educational and authorized testing purposes only.
