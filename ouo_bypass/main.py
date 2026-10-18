#!/usr/bin/env python3
"""OUO.io Link Bypass Bot — CLI Entry Point.

Reads ouo.io short links from ouolinks.txt, picks them at random, and
navigates through all intermediate pages (Cloudflare challenges, countdown
timers, form submissions) until reaching the final destination URL.

Usage:
  python ouo_bypass/main.py                          # headless continuous loop
  python ouo_bypass/main.py --headed                 # visible browser
  python ouo_bypass/main.py --headed --count 5       # run 5 links then stop
  python ouo_bypass/main.py --links /path/to/file    # custom links file
"""

import argparse
import asyncio
import logging
import os
import signal
import sys

# Ensure project root and local packages can be resolved
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Windows compatibility
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

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

from config import OUOConfig
from src.link_loader import load_links
from src.ouo_engine import OUOBypassEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("OUOBypass")


def parse_args():
    parser = argparse.ArgumentParser(
        description="OUO.io Link Bypass Bot — navigate through ouo.io shortener pages to final destinations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python ouo_bypass/main.py                        Headless continuous loop (default)
  python ouo_bypass/main.py --headed               Visible browser, continuous loop
  python ouo_bypass/main.py --headed --count 5     Process 5 random links, then stop
  python ouo_bypass/main.py --links mylinks.txt    Use a custom links file
        """,
    )

    parser.add_argument(
        "--links",
        type=str,
        default=None,
        help=f"Path to text file with ouo.io links (default: ../ouolinks.txt)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser with visible UI (default: headless)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of links to process (0 = unlimited continuous loop, default: 0)",
    )
    parser.add_argument(
        "--link-delay-min",
        type=float,
        default=15.0,
        help="Minimum delay in seconds between links (default: 15)",
    )
    parser.add_argument(
        "--link-delay-max",
        type=float,
        default=45.0,
        help="Maximum delay in seconds between links (default: 45)",
    )
    parser.add_argument(
        "--dwell-min",
        type=float,
        default=7.0,
        help="Minimum dwell time on destination page in seconds (at least 7s, default: 7)",
    )
    parser.add_argument(
        "--dwell-max",
        type=float,
        default=15.0,
        help="Maximum dwell time on destination page in seconds (default: 15)",
    )
    parser.add_argument(
        "--page-timeout",
        type=int,
        default=60,
        help="Page load timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--no-screenshots",
        action="store_true",
        help="Disable screenshot capture (default: screenshots enabled)",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=str,
        default="screenshots",
        help="Directory to save screenshots (default: screenshots)",
    )

    parser.add_argument(
        "--driver",
        type=str,
        default="uc",
        choices=["uc", "undetected-chromedriver", "nodriver", "playwright"],
        help="Automation engine: 'uc' (undetected-chromedriver, recommended for Cloudflare), 'nodriver' (CDP-free anti-detect), or 'playwright' (default: uc)",
    )

    return parser.parse_args()


async def run_limited(engine: OUOBypassEngine, links, count, link_delay_min, link_delay_max):
    """Run a limited number of links, then stop."""
    import random
    import time
    from src.link_loader import pick_random_link

    successes = 0
    failures = 0
    last_url = None
    start_time = time.time()

    engine._log("=" * 65)
    engine._log(f"  🎯 OUO.io BYPASS — LIMITED RUN ({count} links)")
    engine._log("=" * 65)
    engine._log(f"  Links pool:     {len(links)} URLs loaded")
    engine._log(f"  Processing:     {count} random links")
    engine._log(f"  Driver:         {engine.engine_type.upper()}")
    engine._log(f"  Headless:       {engine.headless}")
    engine._log("=" * 65)
    engine._log("")

    if engine.engine_type in ("uc", "undetected", "undetected-chromedriver"):
        for i in range(1, count + 1):
            url = pick_random_link(links, exclude=last_url)
            last_url = url

            elapsed = time.time() - start_time
            elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

            engine._log(f"\n{'─' * 65}")
            engine._log(
                f"  📋 Link {i}/{count} (Undetected-Chromedriver) | ✅ {successes} ok | ❌ {failures} fail | "
                f"⏱ {elapsed_m}m{elapsed_s}s"
            )
            engine._log(f"{'─' * 65}")

            session_id = f"ouo_uc_l{i}_{int(time.time())}"

            try:
                result = await asyncio.to_thread(engine.bypass_single_link_uc, url, session_id)

                if result["status"] == "success":
                    successes += 1
                    engine._log(f"  ✅ SUCCESS — Destination: {result['destination_url']}")
                else:
                    failures += 1
                    engine._log(f"  ❌ FAILED — Status: {result['status']} | Error: {result.get('error', 'N/A')}")

                engine._log(f"  ⏱ Duration: {result['duration']}s | Steps: {len(result['steps'])}")

            except Exception as e:
                failures += 1
                engine._log(f"  ❌ Link {i} EXCEPTION: {e}")

            if i < count:
                delay = random.uniform(link_delay_min, link_delay_max)
                engine._log(f"\n  ⏳ Waiting {delay:.1f}s before next link...")
                await asyncio.sleep(delay)

    elif engine.engine_type == "nodriver":
        for i in range(1, count + 1):
            url = pick_random_link(links, exclude=last_url)
            last_url = url

            elapsed = time.time() - start_time
            elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

            engine._log(f"\n{'─' * 65}")
            engine._log(
                f"  📋 Link {i}/{count} (Nodriver) | ✅ {successes} ok | ❌ {failures} fail | "
                f"⏱ {elapsed_m}m{elapsed_s}s"
            )
            engine._log(f"{'─' * 65}")

            session_id = f"ouo_nd_l{i}_{int(time.time())}"

            try:
                result = await engine.bypass_single_link_nodriver(url, session_id)

                if result["status"] == "success":
                    successes += 1
                    engine._log(f"  ✅ SUCCESS — Destination: {result['destination_url']}")
                else:
                    failures += 1
                    engine._log(f"  ❌ FAILED — Status: {result['status']} | Error: {result.get('error', 'N/A')}")

                engine._log(f"  ⏱ Duration: {result['duration']}s | Steps: {len(result['steps'])}")

            except Exception as e:
                failures += 1
                engine._log(f"  ❌ Link {i} EXCEPTION: {e}")

            if i < count:
                delay = random.uniform(link_delay_min, link_delay_max)
                engine._log(f"\n  ⏳ Waiting {delay:.1f}s before next link...")
                await asyncio.sleep(delay)
    else:
        from src.fingerprint import generate_fingerprint, get_context_options, get_launch_args, get_stealth_script
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            for i in range(1, count + 1):
                url = pick_random_link(links, exclude=last_url)
                last_url = url

                elapsed = time.time() - start_time
                elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

                engine._log(f"\n{'─' * 65}")
                engine._log(
                    f"  📋 Link {i}/{count} | ✅ {successes} ok | ❌ {failures} fail | "
                    f"⏱ {elapsed_m}m{elapsed_s}s"
                )
                engine._log(f"{'─' * 65}")

                fingerprint = generate_fingerprint()
                context_opts = get_context_options(fingerprint)
                launch_args = get_launch_args()
                stealth_script = get_stealth_script(fingerprint)

                engine._log(f"  🎭 Fingerprint: {fingerprint.platform} | "
                             f"{fingerprint.viewport_width}x{fingerprint.viewport_height} | "
                             f"{fingerprint.timezone}")

                browser = await p.chromium.launch(
                    headless=engine.headless,
                    args=launch_args,
                )
                context = await browser.new_context(**context_opts)
                await context.add_init_script(stealth_script)

                session_id = f"ouo_l{i}_{int(time.time())}"

                try:
                    result = await engine.bypass_single_link(url, context, session_id)

                    if result["status"] == "success":
                        successes += 1
                        engine._log(f"  ✅ SUCCESS — Destination: {result['destination_url']}")
                    else:
                        failures += 1
                        engine._log(f"  ❌ FAILED — Status: {result['status']} | Error: {result.get('error', 'N/A')}")

                    engine._log(f"  ⏱ Duration: {result['duration']}s | Steps: {len(result['steps'])}")

                except Exception as e:
                    failures += 1
                    engine._log(f"  ❌ Link {i} EXCEPTION: {e}")
                finally:
                    await context.close()
                    await browser.close()

                # Delay between links (skip after last)
                if i < count:
                    delay = random.uniform(link_delay_min, link_delay_max)
                    engine._log(f"\n  ⏳ Waiting {delay:.1f}s before next link...")
                    await asyncio.sleep(delay)


    elapsed = time.time() - start_time
    elapsed_m, elapsed_s = int(elapsed // 60), int(elapsed % 60)

    engine._log(f"\n{'=' * 65}")
    engine._log(f"  📊 FINAL SUMMARY")
    engine._log(f"{'=' * 65}")
    engine._log(f"  Total processed: {count}")
    engine._log(f"  Successful:      {successes}")
    engine._log(f"  Failed:          {failures}")
    rate = (successes / max(count, 1)) * 100
    engine._log(f"  Success rate:    {rate:.1f}%")
    engine._log(f"  Total time:      {elapsed_m}m {elapsed_s}s")
    engine._log(f"{'=' * 65}")


async def main():
    args = parse_args()

    # Resolve links file
    config = OUOConfig()
    links_file = args.links or config.links_file
    if not os.path.isabs(links_file):
        links_file = os.path.join(PROJECT_ROOT, links_file)

    # Load links
    print("=" * 65)
    print("  🌐 OUO.io Link Bypass Bot")
    print("=" * 65)
    print(f"  Links file: {links_file}")

    try:
        links = load_links(links_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  ❌ Error: {e}")
        print(f"  Make sure {links_file} exists and contains valid URLs.\n")
        sys.exit(1)

    print(f"  Links loaded: {len(links)}")
    print(f"  Mode: {'Limited (' + str(args.count) + ' links)' if args.count > 0 else 'Unlimited continuous loop'}")
    print(f"  Browser: {'Headed (visible)' if args.headed else 'Headless'}")
    print(f"  Screenshots: {'Disabled' if args.no_screenshots else args.screenshot_dir}")
    print("=" * 65)

    # Build the engine
    screenshot_dir = os.path.join(SCRIPT_DIR, args.screenshot_dir)
    engine = OUOBypassEngine(
        headless=not args.headed,
        engine_type=args.driver,
        page_load_timeout=args.page_timeout,
        destination_dwell_min=args.dwell_min,
        destination_dwell_max=args.dwell_max,
        screenshot_dir=screenshot_dir,
        take_screenshots=not args.no_screenshots,
    )


    if args.count > 0:
        # Limited run
        await run_limited(
            engine=engine,
            links=links,
            count=args.count,
            link_delay_min=args.link_delay_min,
            link_delay_max=args.link_delay_max,
        )
    else:
        # Unlimited continuous loop
        await engine.run_continuous(
            links=links,
            link_delay_min=args.link_delay_min,
            link_delay_max=args.link_delay_max,
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Exiting cleanly.")
