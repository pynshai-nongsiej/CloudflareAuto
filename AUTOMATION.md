# TenBox Websurfer Auto-Registration & OTP Verification

Automated registration and verification system for [TenBox Websurfer](https://websurfer.1024tenbox.com/) powered by **`playwright`** (deterministic stealth runner) and **`browser-use`** (Agentic AI), integrated with **[TempMail.Plus](https://tempmail.plus/en/#!)** disposable email service.

---

## Architecture & Flow

```
+-----------------------------------------------------------------------------------+
| 1. Create temporary email address via TempMail.Plus                               |
|    - Random pronounceable name (exact algorithm from TempMail.Plus index.js)      |
|    - Random domain selected from dropdown (@mailto.plus, @fexbox.org, etc.)       |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 2. Navigate to https://websurfer.1024tenbox.com/referral/J7V5V668                 |
|    - Click "Get started free" CTA                                                 |
|    - Input generated email into the email field                                   |
|    - Click "Send OTP"                                                             |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 3. Redirected to /otp page                                                        |
|    - Poll GET https://tempmail.plus/api/mails?email=... until OTP code arrives    |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 4. Verification & Dashboard Access                                                |
|    - Fill the 6-digit verification code into the numeric input cells              |
|    - Auto-submits / verifies with https://api.tenbox.app/api/v1/auth/verify-otp   |
|    - Lands on TenBox distributor dashboard (https://websurfer.1024tenbox.com/)    |
|    - Extracts session cookies and authentication tokens (localStorage)            |
+-----------------------------------------+-----------------------------------------+
```

---

## Prerequisites

Python packages:
```bash
pip install browser-use playwright
playwright install chromium
```

No external API keys or tokens are required for TempMail.Plus.

---

## Usage

### Option 1: AI Agent Mode (`browser-use`)

Uses the `browser-use` autonomous agent with custom tools registered on the `Controller` (`create_temporary_email` and `fetch_verification_otp`).

```bash
# Using OpenAI (requires OPENAI_API_KEY)
export OPENAI_API_KEY="sk-..."
python3 main.py --mode browser-use --provider openai

# Using Google Gemini (requires GEMINI_API_KEY)
export GEMINI_API_KEY="..."
python3 main.py --mode browser-use --provider gemini --model gemini-2.0-flash

# Using Anthropic Claude (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY="sk-ant-..."
python3 main.py --mode browser-use --provider anthropic

# With visible browser UI
python3 main.py --mode browser-use --provider openai --headed
```

### Option 2: Direct Playwright Mode (Fast & Zero LLM Cost)

Executes the verification flow deterministically within seconds without needing an LLM key:

```bash
# Headless run (default)
python3 main.py --mode direct

# Headed run (visible browser window)
python3 main.py --mode direct --headed

# Keep temporary inbox active after verification
python3 main.py --mode direct --keep-inbox
```

---

## Command-Line Options

| Argument | Description | Default |
|---|---|---|
| `--mode` | Engine mode: `browser-use` or `direct` | `browser-use` |
| `--headed` | Launch browser with visible GUI | Headless |
| `--provider` | LLM provider: `openai`, `gemini`, `anthropic`, `ollama` | Auto-detect |
| `--model` | Specific LLM model name | Provider default |
| `--api-key` | Provider API key override | Read from env |
| `--timeout` | Maximum seconds to wait for OTP email | `90` |
| `--keep-inbox` | Prevent temporary inbox deletion after verification | False (deletes inbox) |
| `--loop` | Run continuous loop (unlimited runs if `--count 0`) | False |
| `--count` | Number of loop runs (0 = infinite / unlimited) | `0` |
| `--delay-min` | Minimum random delay between runs (seconds) | `15.0` |
| `--delay-max` | Maximum random delay between runs (seconds) | `30.0` |
| `--target-url` | Target URL (defaults to referral link) | `https://websurfer.1024tenbox.com/referral/J7V5V668` |

---

### Option 3: Unlimited Automated Loop with Random Delays

Run unlimited automated registrations with randomized 15-30s delays and full fingerprint randomization:

```bash
# Unlimited loop with 15-30s delays (runs continuously until stopped with Ctrl+C)
python3 main.py --mode direct --loop

# Run exactly N registrations with 15-30s delays
python3 main.py --mode direct --loop --count 10 --delay-min 15 --delay-max 30

# Headed mode to visually inspect runs
python3 main.py --mode direct --headed --loop
```

---

## Key Features

1. **TempMail.Plus Provider**:
   - Random pronounceable name generated per signup via TempMail.Plus's native algorithm (`getRandomPre`).
   - Random domain ending selected per signup from the live dropdown list (`@mailto.plus`, `@fexpost.com`, `@fexbox.org`, `@mailbox.in.ua`, `@rover.info`, `@chitthi.in`, `@fextemp.com`, `@any.pink`, `@merepost.com`).
   - Direct API polling and instant OTP extraction without requiring external auth tokens.

2. **Full Fingerprint Randomization**:
   - Randomizes User-Agent, platform, viewport resolutions, device pixel ratio, timezone, locale, WebGL renderer & vendor, Canvas noise, and AudioContext fingerprints per run.

3. **Unlimited Loop Mode & Delay Randomization**:
   - Customizable random delay between cycles (default 15 to 30 seconds).
   - Real-time run counter and success/failure statistics.
   - Graceful interrupt handling with clean exit summaries.

---

## File Structure

- [main.py](file:///Users/pynshainongsiej/Desktop/CloudflareAuto/main.py): Unified CLI entry point with loop engine and random delay scheduler.
- [src/automation/fingerprint.py](file:///Users/pynshainongsiej/Desktop/CloudflareAuto/src/automation/fingerprint.py): Full randomized fingerprint generator & injection scripts.
- [src/automation/tempmail_client.py](file:///Users/pynshainongsiej/Desktop/CloudflareAuto/src/automation/tempmail_client.py): TempMail.Plus client supporting random names and dropdown domains per signup.
- [src/automation/browser_use_automation.py](file:///Users/pynshainongsiej/Desktop/CloudflareAuto/src/automation/browser_use_automation.py): `browser-use` Agent with registered TempMail actions.
- [src/automation/playwright_automation.py](file:///Users/pynshainongsiej/Desktop/CloudflareAuto/src/automation/playwright_automation.py): High-speed Playwright automation with stealth fingerprinting and OTP verification.
