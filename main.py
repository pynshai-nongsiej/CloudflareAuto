#!/usr/bin/env python3
"""TenBox Websurfer Auto-Registration & OTP Verification.

Supports two automation engines:
  1. browser-use: Agentic AI browser automation with registered TempMail tools.
  2. direct (Playwright): Deterministic, ultra-fast automation with zero LLM cost.

Run modes:
  - Single run (default): python main.py --mode direct --headed
  - Unlimited loop:       python main.py --mode direct --loop
  - Limited loop:         python main.py --mode direct --loop --count 10
"""

import argparse
import asyncio
import random
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# Windows compatibility: set event loop policy & configure UTF-8 output for emojis in CMD/PowerShell
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from src.automation.tempmail_client import TempMailClient
from src.automation.playwright_automation import register_and_verify, RateLimitError, cleanup_all_screenshots
from src.automation.browser_use_automation import create_browser_use_agent, get_default_llm


REFERRAL_PRESETS = {
    "1": {
        "url": "https://websurfer.1024tenbox.com/referral/XWUPKX2D",
        "email": "pn@gmail.com",
        "label": "pn@gmail.com (Linux / Primary)",
    },
    "2": {
        "url": "https://websurfer.1024tenbox.com/referral/XUMZDQ5R",
        "email": "dd@gmail.com",
        "label": "dd@gmail.com (Windows / Secondary)",
    },
    "3": {
        "url": "https://websurfer.1024tenbox.com/referral/75H3QGGK",
        "email": "jn@gmail.com",
        "label": "jn@gmail.com (Tertiary)",
    },
    "4": {
        "url": "https://websurfer.1024tenbox.com/referral/8PCCMJ33",
        "email": "dai@gmail.com",
        "label": "dai@gmail.com (Quaternary)",
    },
}

REFERRAL_ALIASES = {
    "pn": "1",
    "pn@gmail.com": "1",
    "dd": "2",
    "dd@gmail.com": "2",
    "jn": "3",
    "jn@gmail.com": "3",
    "dai": "4",
    "dai@gmail.com": "4",
}


def resolve_target_url(raw_val: str) -> tuple[str, str]:
    """Resolve preset ID ('1', '2', '3', '4'), alias ('pn', 'dd', 'jn', 'dai'), or full URL.
    Returns (url, email_label).
    """
    cleaned = (raw_val or "").strip()
    key = REFERRAL_ALIASES.get(cleaned.lower(), cleaned)
    if key in REFERRAL_PRESETS:
        preset = REFERRAL_PRESETS[key]
        return preset["url"], preset["email"]

    for preset in REFERRAL_PRESETS.values():
        if cleaned.rstrip("/") == preset["url"].rstrip("/"):
            return preset["url"], preset["email"]

    return cleaned, "Custom Account"


DEFAULT_TARGET_URL = (
    REFERRAL_PRESETS["2"]["url"]
    if sys.platform == "win32"
    else REFERRAL_PRESETS["1"]["url"]
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="TenBox Websurfer Auto-Registration & OTP Verification via TempMail"
    )
    parser.add_argument(
        "--mode",
        choices=["browser-use", "direct"],
        default="direct",
        help="Automation mode: 'browser-use' (agentic LLM) or 'direct' (fast Playwright)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser with visible UI (default is headless)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run in unlimited loop mode with random delays between runs",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of registrations to perform (0 = unlimited, requires --loop)",
    )
    parser.add_argument(
        "--delay-min",
        type=int,
        default=60,
        help="Minimum delay in seconds between loop runs (default: 60 = 1 min)",
    )
    parser.add_argument(
        "--delay-max",
        type=int,
        default=120,
        help="Maximum delay in seconds between loop runs (default: 120 = 2 min)",
    )
    default_referrer = "random" if sys.platform == "darwin" else "none"
    parser.add_argument(
        "--referrer",
        type=str,
        default=default_referrer,
        help="Simulated inbound referral platform (macOS only): instagram, telegram, facebook, youtube, twitter, reddit, random, or none",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "google", "gemini", "anthropic", "ollama"],
        default=None,
        help="LLM provider for browser-use (reads OPENAI_API_KEY, GEMINI_API_KEY, etc. by default)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Specific model identifier (e.g. gpt-4o, gemini-2.0-flash, claude-3-5-sonnet-latest)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Optional API key override for the chosen LLM provider",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Timeout in seconds when waiting for OTP code delivery (default: 90)",
    )
    parser.add_argument(
        "--keep-inbox",
        action="store_true",
        help="Do not delete the temporary inbox after verification completes",
    )
    parser.add_argument(
        "--target-url",
        type=str,
        default=DEFAULT_TARGET_URL,
        help="Target registration/referral URL or preset ('1', '2', '3', 'pn', 'dd', 'jn')",
    )
    args = parser.parse_args()
    resolved_url, resolved_email = resolve_target_url(args.target_url)
    args.target_url = resolved_url
    args.target_email = resolved_email
    return args


async def run_browser_use(args):
    print("=" * 60)
    print("  Starting browser-use Agent for TenBox Websurfer")
    print(f"  Target: {args.target_url} ({args.target_email})")
    print("=" * 60)

    mail_client = TempMailClient()

    try:
        llm = get_default_llm(
            provider=args.provider,
            model_name=args.model,
            api_key=args.api_key,
        )
    except ValueError as e:
        print(f"\n[!] Configuration notice:\n{e}\n")
        print("[*] Tip: You can run directly without an LLM key using: python main.py --mode direct\n")
        sys.exit(1)

    agent = create_browser_use_agent(
        mail_client=mail_client,
        llm=llm,
        headed=args.headed,
        target_url=getattr(args, "target_url", DEFAULT_TARGET_URL),
        referrer=getattr(args, "referrer", "random"),
    )

    history = await agent.run()
    print("\n[+] browser-use execution completed.")
    print("Final result:\n", history.final_result())


async def run_direct_single(args) -> dict:
    """Run a single registration and return the result."""
    mail_client = TempMailClient()

    result = await register_and_verify(
        client=mail_client,
        headed=args.headed,
        timeout=args.timeout,
        cleanup_inbox=not args.keep_inbox,
        target_url=getattr(args, "target_url", None),
        referrer=getattr(args, "referrer", "random"),
    )

    return result


def print_result(result: dict, run_number: int = 0):
    """Pretty-print a single registration result."""
    prefix = f"Run #{run_number} " if run_number > 0 else ""
    print(f"\n{'=' * 60}")
    print(f"  {prefix}VERIFICATION SUCCESSFUL ✅")
    print(f"{'=' * 60}")
    print(f"  Email:    {result['email']}")
    print(f"  OTP:      {result['otp']}")
    print(f"  URL:      {result['url']}")
    if 'referrer' in result and result['referrer']:
        ref = result['referrer']
        print(f"  Referrer: 🌐 {ref.get('platform', 'N/A')} ({ref.get('url', 'N/A')[:55]}...)")
    print(f"  Cookies:  {len(result.get('cookies', []))} captured")
    if 'auth_storage' in result:
        local_keys = list(result['auth_storage'].get('localStorage', {}).keys())
        print(f"  Auth:     {local_keys}")
    if 'fingerprint' in result:
        fp = result['fingerprint']
        print(f"  UA:       {fp.get('user_agent', 'N/A')[:55]}...")
        print(f"  TZ:       {fp.get('timezone', 'N/A')}")
    print(f"{'=' * 60}")


async def run_loop(args):
    """Run the automation in an unlimited (or counted) loop with human pacing (1-2 min delays)."""
    max_runs = args.count if args.count > 0 else float('inf')
    delay_min = args.delay_min
    delay_max = args.delay_max
    referrer_mode = getattr(args, "referrer", "random")

    run_number = 0
    successes = 0
    failures = 0
    start_time = time.time()

    print("=" * 60)
    print("  🔄 TENBOX AUTOMATION LOOP -- HUMAN PACING")
    print("=" * 60)
    print(f"  Mode:         {args.mode}")
    print(f"  Max runs:     {'unlimited' if max_runs == float('inf') else max_runs}")
    delay_desc = f"{delay_min}-{delay_max}s ({delay_min//60}-{delay_max//60} min)" if delay_min >= 60 else f"{delay_min}-{delay_max}s"
    print(f"  Pacing:       {delay_desc} between runs")
    if sys.platform == "darwin":
        print(f"  Referrer:     {referrer_mode.upper() if referrer_mode else 'NONE'} (Instagram, Telegram, Facebook, YouTube, etc.)")
    print(f"  Target URL:   {args.target_url}")
    print(f"  Account:      {args.target_email}")
    print(f"  Headed:       {args.headed}")
    print(f"  Timeout:      {args.timeout}s")
    print("=" * 60)
    print("  Press Ctrl+C to stop at any time.\n")

    try:
        while run_number < max_runs:
            run_number += 1
            elapsed_total = time.time() - start_time
            elapsed_min = int(elapsed_total // 60)
            elapsed_sec = int(elapsed_total % 60)

            print(f"\n{'─' * 60}")
            print(f"  📋 Run #{run_number} | ✅ {successes} ok | ❌ {failures} fail | "
                  f"⏱ {elapsed_min}m{elapsed_sec}s total")
            print(f"{'─' * 60}")

            try:
                result = await run_direct_single(args)
                successes += 1
                print_result(result, run_number)

            except KeyboardInterrupt:
                raise
            except RateLimitError as rle:
                failures += 1
                wait_time = rle.wait_seconds if rle.wait_seconds > 0 else 900
                wait_time += 30  # safety buffer
                resume_time = time.strftime("%H:%M:%S", time.localtime(time.time() + wait_time))
                mins = int(wait_time // 60)
                secs = int(wait_time % 60)
                print(f"\n{'=' * 60}")
                print(f"  ⚠️ Run #{run_number} RATE LIMITED BY TENBOX")
                print(f"     Details:        {rle.message}")
                print(f"     Cooldown:       {wait_time}s (~{mins}m {secs}s)")
                print(f"     Target Resume:  {resume_time}")
                print(f"{'=' * 60}")
                # Periodic updates while waiting so user knows process is active
                remaining = wait_time
                while remaining > 0:
                    step = min(remaining, 60)
                    await asyncio.sleep(step)
                    remaining -= step
                    if remaining > 0:
                        rem_m = int(remaining // 60)
                        rem_s = int(remaining % 60)
                        print(f"  ⏳ [Cooldown] {rem_m}m {rem_s}s remaining (resumes at {resume_time})...")
                print(f"\n  ✅ Rate limit cooldown complete! Resuming automation loop...\n")
                continue
            except Exception as e:
                failures += 1
                print(f"\n  ❌ Run #{run_number} FAILED: {e}")
                print(f"     Pausing 15s before next attempt...")
                await asyncio.sleep(15)

            # Random delay before next run (skip if last run)
            if run_number < max_runs:
                delay = random.uniform(delay_min, delay_max)
                mins = int(delay // 60)
                secs = int(delay % 60)
                time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                print(f"\n  ⏳ Waiting {delay:.1f}s (~{time_str}) before next run...")
                await asyncio.sleep(delay)

    except KeyboardInterrupt:
        print(f"\n\n{'=' * 60}")
        print(f"  🛑 LOOP STOPPED BY USER (Ctrl+C)")
        print(f"{'=' * 60}")
    finally:
        elapsed_total = time.time() - start_time
        elapsed_min = int(elapsed_total // 60)
        elapsed_sec = int(elapsed_total % 60)

        print(f"\n{'=' * 60}")
        print(f"  📊 FINAL SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Total runs:    {run_number}")
        print(f"  Successful:    {successes}")
        print(f"  Failed:        {failures}")
        print(f"  Success rate:  {(successes / max(run_number, 1) * 100):.1f}%")
        print(f"  Total time:    {elapsed_min}m {elapsed_sec}s")
        print(f"{'=' * 60}")


async def run_direct(args):
    print("=" * 60)
    print("  Starting Direct Playwright Automation for TenBox Websurfer")
    print(f"  Target: {args.target_url} ({args.target_email})")
    print("=" * 60)

    result = await run_direct_single(args)
    print_result(result)


def main():
    args = parse_args()
    cleanup_all_screenshots()

    try:
        if args.loop:
            asyncio.run(run_loop(args))
        elif args.mode == "browser-use":
            asyncio.run(run_browser_use(args))
        else:
            asyncio.run(run_direct(args))
    finally:
        cleanup_all_screenshots()


if __name__ == "__main__":
    main()
