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
from src.automation.playwright_automation import register_and_verify
from src.automation.browser_use_automation import create_browser_use_agent, get_default_llm


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
        default=15,
        help="Minimum delay in seconds between loop runs (default: 15)",
    )
    parser.add_argument(
        "--delay-max",
        type=int,
        default=30,
        help="Maximum delay in seconds between loop runs (default: 30)",
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
    return parser.parse_args()


async def run_browser_use(args):
    print("=" * 60)
    print("  Starting browser-use Agent for TenBox Websurfer")
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
    """Run the automation in an unlimited (or counted) loop with random delays."""
    max_runs = args.count if args.count > 0 else float('inf')
    delay_min = args.delay_min
    delay_max = args.delay_max
    run_number = 0
    successes = 0
    failures = 0
    start_time = time.time()

    print("=" * 60)
    print("  🔄 UNLIMITED REGISTRATION LOOP")
    print("=" * 60)
    print(f"  Mode:      {args.mode}")
    print(f"  Max runs:  {'unlimited' if max_runs == float('inf') else max_runs}")
    print(f"  Delay:     {delay_min}-{delay_max}s between runs")
    print(f"  Headed:    {args.headed}")
    print(f"  Timeout:   {args.timeout}s")
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
            except Exception as e:
                failures += 1
                print(f"\n  ❌ Run #{run_number} FAILED: {e}")
                print(f"     Continuing to next run...")

            # Random delay before next run (skip if last run)
            if run_number < max_runs:
                delay = random.uniform(delay_min, delay_max)
                print(f"\n  ⏳ Waiting {delay:.1f}s before next run...")
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
    print("=" * 60)

    result = await run_direct_single(args)
    print_result(result)


def main():
    args = parse_args()

    if args.loop:
        asyncio.run(run_loop(args))
    elif args.mode == "browser-use":
        asyncio.run(run_browser_use(args))
    else:
        asyncio.run(run_direct(args))


if __name__ == "__main__":
    main()
