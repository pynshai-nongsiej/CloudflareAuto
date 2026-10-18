# OUO.io Link Bypass Bot

Automated Playwright bot that reads `ouo.io` short links from a text file, visits them at random in a continuous loop, and navigates through every intermediate page (Cloudflare challenges, countdown timers, form submissions) until the final destination URL is reached.

## Features

- **Random link selection** — picks a different ouo.io link each cycle (avoids repeating the same link twice in a row)
- **Full bypass flow** — handles Cloudflare Turnstile challenges, countdown timers, multi-step form submissions
- **Anti-detection** — fresh randomized browser fingerprints each cycle (user agent, viewport, timezone, WebGL, platform)
- **Stealth mode** — navigator.webdriver flag masked, chrome runtime mocked, WebGL fingerprint spoofed
- **Popup handling** — automatically closes ad popups/new tabs and returns focus to the main page
- **Human-like behavior** — random delays, mouse movements, scrolling, and dwell time on destination pages
- **Continuous or limited mode** — run forever or process a specific number of links
- **Screenshot capture** — optional screenshots at each step for debugging
- **Cross-platform** — Works on macOS, Linux, and Windows

## Quick Start

### Prerequisites

- Python 3.8+
- Playwright (`pip install playwright && python -m playwright install chromium`)

### Run

```bash
# Headless continuous loop (default)
python ouo_bypass/main.py

# Visible browser, continuous loop
python ouo_bypass/main.py --headed

# Process 5 random links, then stop
python ouo_bypass/main.py --headed --count 5

# Custom links file
python ouo_bypass/main.py --links /path/to/mylinks.txt

# Or use the convenience script:
chmod +x ouo_bypass/run.sh
./ouo_bypass/run.sh --headed
```

### Windows

```cmd
ouo_bypass\run_windows.bat --headed
```

## CLI Options

| Flag                | Default      | Description                                    |
|---------------------|--------------|------------------------------------------------|
| `--links FILE`      | `ouolinks.txt` | Path to text file with ouo.io URLs           |
| `--headed`          | off          | Show browser window (default: headless)        |
| `--count N`         | 0            | Process N links then stop (0 = unlimited loop) |
| `--link-delay-min`  | 15           | Min seconds between links                      |
| `--link-delay-max`  | 45           | Max seconds between links                      |
| `--dwell-min`       | 5            | Min seconds to stay on destination page        |
| `--dwell-max`       | 15           | Max seconds to stay on destination page        |
| `--page-timeout`    | 60           | Page load timeout in seconds                   |
| `--no-screenshots`  | off          | Disable screenshot capture                     |
| `--screenshot-dir`  | `screenshots`| Directory for screenshots                      |

## How It Works

```
1. Load links from ouolinks.txt (67 ouo.io URLs)
2. Pick a random link from the pool
3. Generate fresh browser fingerprint (anti-detection)
4. Launch stealth Chromium browser
5. Navigate to ouo.io link
6. Handle flow:
   ├── Cloudflare challenge? → Wait for auto-solve
   ├── Countdown timer? → Wait for expiry
   ├── Form #form-go? → Click submit button
   ├── Continue/Get Link button? → Click it
   └── Redirect? → Follow it
7. Repeat steps 5-6 until reaching non-ouo.io destination
8. Dwell on destination (human-like scrolling + delay)
9. Close browser, wait random delay
10. Go to step 2 (loop)
```

## File Structure

```
ouo_bypass/
├── __init__.py          # Package marker
├── main.py              # CLI entry point
├── config.py            # Configuration defaults
├── run.sh               # Mac/Linux launcher
├── run_windows.bat      # Windows launcher
├── screenshots/         # Auto-created screenshot output
└── src/
    ├── __init__.py
    ├── fingerprint.py   # Browser fingerprint generation & stealth scripts
    ├── link_loader.py   # Load & randomly select ouo.io links from file
    └── ouo_engine.py    # Core bypass engine (Playwright automation)
```

## Links File Format

One URL per line in `ouolinks.txt`:

```
https://ouo.io/LUFtdB
https://ouo.io/Qp9pfI
https://ouo.io/Jecewpy
...
```
