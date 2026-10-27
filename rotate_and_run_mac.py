#!/usr/bin/env python3
"""Auto-Rotating 20-Worker Headless Runner & Dashboard for macOS with NordVPN CLI.

Features:
  - 20 workers run completely headlessly in the background (no popup windows).
  - 5 workers assigned to each of the 4 referral accounts.
  - Live console dashboard showing overall successes, failures, per-account stats,
    VPN IP, location, and real-time event feed.
  - As soon as any worker hits a rate limit / 15-minute cooldown:
    1. Kills all worker processes with `pkill`.
    2. Randomly chooses a new location from 150+ NordVPN countries.
    3. Reconnects via OpenVPN CLI and verifies the new IP.
    4. Relaunches 20 fresh headless workers.
"""

import os
import sys
import time
import json
import random
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.automation.nordvpn_rotator import rotate_vpn, disconnect_vpn, get_current_ip_info

TRIGGER_FLAG = Path("/tmp/cloudflare_rate_limit_triggered.flag")
EVENTS_FILE = PROJECT_ROOT / "logs" / "events.jsonl"
LOGS_DIR = PROJECT_ROOT / "logs"

ACCOUNTS = [
    {
        "id": "1",
        "email": "pn@gmail.com",
        "url": "https://websurfer.1024tenbox.com/referral/XWUPKX2D",
    },
    {
        "id": "4",
        "email": "dai@gmail.com",
        "url": "https://websurfer.1024tenbox.com/referral/8PCCMJ33",
    },
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="macOS 10-Worker Runner (pn & dai) with Live Dashboard & NordVPN Auto-Rotator"
    )
    parser.add_argument(
        "--workers-per-link",
        type=int,
        default=5,
        help="Number of workers per link (default: 5, total 10 across pn & dai)",
    )
    parser.add_argument(
        "--mode",
        choices=["direct", "browser-use"],
        default="direct",
        help="Automation mode: direct (fast deterministic) or browser-use",
    )
    parser.add_argument(
        "--delay-min",
        type=int,
        default=0,
        help="Minimum delay between runs per worker (default: 0)",
    )
    parser.add_argument(
        "--delay-max",
        type=int,
        default=0,
        help="Maximum delay between runs per worker (default: 0)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run workers headlessly in background without visible Terminal windows (default: False, headed)",
    )
    parser.add_argument(
        "--browser-headed",
        action="store_true",
        default=False,
        help="Also run Chromium browser with visible UI (default: False)",
    )
    parser.add_argument(
        "--cooldown-min",
        type=int,
        default=120,
        help="Minimum cooldown delay in seconds after batch/rate-limit before rotating (default: 120 / 2 min)",
    )
    parser.add_argument(
        "--cooldown-max",
        type=int,
        default=180,
        help="Maximum cooldown delay in seconds after batch/rate-limit before rotating (default: 180 / 3 min)",
    )
    return parser.parse_args()


def close_all_terminals():
    """Kill all main.py worker processes and close their Terminal windows cleanly."""
    subprocess.run(["pkill", "-f", "main.py"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", r"worker_.*\.sh"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "Worker-"], stderr=subprocess.DEVNULL)
    time.sleep(0.5)

    # Close Terminal.app windows whose title begins with Worker-
    ascript = """
    tell application "Terminal"
        repeat with w in (every window)
            try
                if name of w contains "Worker-" then
                    close w saving no
                end if
            end try
        end repeat
    end tell
    """
    subprocess.run(["osascript", "-e", ascript], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)


def clear_trigger_flag():
    """Remove rate limit trigger file."""
    try:
        if TRIGGER_FLAG.exists():
            TRIGGER_FLAG.unlink()
    except Exception:
        pass


def count_active_workers() -> int:
    """Return count of actively running main.py processes."""
    res = subprocess.run(
        ["pgrep", "-f", "main.py.*--worker-id"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    lines = [l.strip() for l in res.stdout.strip().split("\n") if l.strip()]
    if not lines:
        res2 = subprocess.run(
            ["pgrep", "-f", "main.py.*--mode"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        lines = [l.strip() for l in res2.stdout.strip().split("\n") if l.strip()]
    return len(lines)


def launch_workers(workers_per_link: int, mode: str, delay_min: int, delay_max: int, browser_headed: bool = False, headless: bool = False):
    """Launch workers in visible Terminal windows across all 4 accounts."""
    total_workers = workers_per_link * len(ACCOUNTS)
    env = os.environ.copy()
    env["WORKERS_PER_LINK"] = str(workers_per_link)
    env["NUM_WINDOWS"] = str(total_workers)
    env["MODE"] = mode
    env["DELAY_MIN"] = str(delay_min)
    env["DELAY_MAX"] = str(delay_max)
    env["HEADLESS"] = "true" if headless else "false"

    extra = ["--exit-on-rate-limit", "--timeout", "120"]
    if browser_headed:
        extra.append("--headed")
    env["EXTRA_ARGS"] = " ".join(extra)

    launcher = PROJECT_ROOT / "launch_multi_mac.sh"
    cmd = ["bash", str(launcher), "5"]
    if headless:
        cmd.append("--headless")
    else:
        cmd.append("--headed")
    if browser_headed:
        cmd.append("--browser-headed")

    subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)


def read_events_stats() -> tuple[dict, list]:
    """Parse events.jsonl to calculate cumulative stats and recent events."""
    stats = {
        "total_success": 0,
        "total_failure": 0,
        "total_rate_limit": 0,
        "accounts": {acc["email"]: {"success": 0, "failure": 0, "rate_limit": 0} for acc in ACCOUNTS},
    }
    recent_events = []

    if not EVENTS_FILE.exists():
        return stats, recent_events

    try:
        with open(EVENTS_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                ev_type = ev.get("event")
                acc_email = ev.get("account", "Unknown")

                if ev_type == "success":
                    stats["total_success"] += 1
                    if acc_email in stats["accounts"]:
                        stats["accounts"][acc_email]["success"] += 1
                elif ev_type == "rate_limit":
                    stats["total_rate_limit"] += 1
                    if acc_email in stats["accounts"]:
                        stats["accounts"][acc_email]["rate_limit"] += 1
                elif ev_type == "failure":
                    stats["total_failure"] += 1
                    if acc_email in stats["accounts"]:
                        stats["accounts"][acc_email]["failure"] += 1

                recent_events.append(ev)
            except Exception:
                pass

        # Keep last 8 recent events
        recent_events = recent_events[-8:]
    except Exception:
        pass

    return stats, recent_events


def render_dashboard(cycle: int, start_time: float, ip_info: dict, total_workers: int, status_msg: str = "Active"):
    """Render terminal dashboard."""
    stats, recent_events = read_events_stats()
    active_workers = count_active_workers()

    elapsed = int(time.time() - start_time)
    hours = elapsed // 3600
    mins = (elapsed % 3600) // 60
    secs = elapsed % 60
    uptime_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

    ip = ip_info.get("ip", "Checking...")
    country = ip_info.get("country", "??")
    city = ip_info.get("city", "N/A")
    org = ip_info.get("org", "NordVPN")[:32]

    # ANSI terminal clear and home
    sys.stdout.write("\033[H\033[J")

    total_runs = stats['total_success'] + stats['total_failure']
    rate_pct = f"{(stats['total_success'] / max(total_runs, 1) * 100):.1f}%" if total_runs > 0 else "0.0%"
    speed_hr = f"{(stats['total_success'] / max(elapsed, 1) * 3600):.1f}/h"

    out = []
    out.append("╔═══════════════════════════════════════════════════════════════════════════════╗")
    out.append("║      🛡️  CLOUDFLARE AUTO -- 10-WORKER DASHBOARD & NORDVPN ROTATOR (macOS)       ║")
    out.append("║                       Target Accounts: pn & dai (5 workers each)              ║")
    out.append("╠═══════════════════════════════════════════════════════════════════════════════╣")
    out.append(f"║  Cycle     : #{cycle:<4} | Uptime: {uptime_str:<8} | Status: {status_msg:<27}║")
    out.append(f"║  Public IP : {ip:<15} | Location: {city}, {country:<4} | ISP: {org:<22}║")
    out.append("╠═══════════════════════════════════════════════════════════════════════════════╣")
    out.append(f"║  SUCCESS: {stats['total_success']:<5} ✅ │ FAILED: {stats['total_failure']:<4} ❌ │ RATE: {rate_pct:<6} │ SPEED: {speed_hr:<8}   ║")
    out.append(f"║  ACTIVE WORKERS: {active_workers}/{total_workers:<2} 🚀 │ LIMITS: {stats['total_rate_limit']:<3} ⚠️ │ POLICY: Instant Auto-Rotation  ║")
    out.append("╠═══════════════════════════════════════════════════════════════════════════════╣")
    out.append("║  ACCOUNTS STATUS (5 Workers per referral link):                              ║")

    for idx, acc in enumerate(ACCOUNTS):
        acc_st = stats["accounts"].get(acc["email"], {"success": 0, "failure": 0, "rate_limit": 0})
        acc_runs = acc_st["success"] + acc_st["failure"]
        acc_rate = f"{(acc_st['success'] / max(acc_runs, 1) * 100):.0f}%" if acc_runs > 0 else "0%"
        out.append(
            f"║   [{idx+1}] {acc['email']:<15} : {acc_st['success']:<4} ✅ | {acc_st['failure']:<3} ❌ | {acc_rate:<4} rate | 5 workers       ║"
        )

    out.append("╠═══════════════════════════════════════════════════════════════════════════════╣")
    out.append("║  LIVE EVENTS FEED (Most Recent):                                              ║")

    if not recent_events:
        out.append("║   (Waiting for initial registration events...)                                ║")
    else:
        for ev in reversed(recent_events):
            ts = datetime.fromtimestamp(ev.get("timestamp", time.time())).strftime("%H:%M:%S")
            w_id = ev.get("worker_id", "Worker-??")
            ev_t = ev.get("event")
            acc_name = ev.get("account", "").split("@")[0]

            if ev_t == "success":
                icon = "✅"
                detail = f"Verified email: {ev.get('email', 'N/A')[:22]}"
            elif ev_t == "rate_limit":
                icon = "⚠️"
                detail = f"Rate limited -> rotation triggered"
            else:
                icon = "❌"
                detail = f"Failed: {ev.get('error', 'Error')[:28]}"

            line_str = f"║   • {ts} [{w_id}] {acc_name:<5} {icon} {detail:<42}║"
            out.append(line_str)

    out.append("╚═══════════════════════════════════════════════════════════════════════════════╝")
    out.append("  [Tip] Workers running in visible Terminal windows. Press Ctrl+C to stop cleanly.")

    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def main():
    args = parse_args()
    total_workers = args.workers_per_link * len(ACCOUNTS)
    start_time = time.time()
    cycle_count = 0

    # Ensure logs folder and clean trigger flag
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    clear_trigger_flag()

    ip_info = {"ip": "Connecting...", "country": "??", "city": "...", "org": "NordVPN"}

    try:
        while True:
            cycle_count += 1

            # 1. Close any existing worker processes and Terminal windows
            render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="Rotating VPN...")
            close_all_terminals()
            clear_trigger_flag()

            # 2. Rotate NordVPN to random location via OpenVPN CLI
            try:
                country_target = args.country if hasattr(args, "country") and args.country and cycle_count == 1 else None
                ip_info = rotate_vpn(country_target)
            except Exception as e:
                # Retry rotation once on error
                time.sleep(3)
                try:
                    ip_info = rotate_vpn()
                except Exception:
                    ip_info = get_current_ip_info()

            # 3. Launch 20 workers in visible Terminal windows
            mode_desc = "Headed Terminal Windows" if not args.headless else "Headless Background"
            render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg=f"Launching 20 Workers ({mode_desc})...")
            launch_workers(
                workers_per_link=args.workers_per_link,
                mode=args.mode,
                delay_min=args.delay_min,
                delay_max=args.delay_max,
                browser_headed=args.browser_headed,
                headless=args.headless,
            )

            # 4. Dashboard monitoring loop: allows all 20 batch sessions to complete before rotating
            cycle_start = time.time()
            max_batch_time = 180  # Up to 3 minutes for slow OTP delivery + initial stagger

            while True:
                time.sleep(1.5)
                active = count_active_workers()
                rate_limited = TRIGGER_FLAG.exists()
                batch_elapsed = time.time() - cycle_start

                if rate_limited:
                    if active > 0 and batch_elapsed < max_batch_time:
                        msg = f"⚠️ Rate limit hit on IP -- letting {active} ongoing sessions finish..."
                        render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg=msg)
                        continue
                    else:
                        render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="⚠️ All batch sessions finished/limited! Entering cooldown...")
                        break
                else:
                    if active == 0 and batch_elapsed > 30:
                        render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="Batch Completed! Entering cooldown...")
                        break
                    elif batch_elapsed >= max_batch_time:
                        render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="Batch Time Complete. Entering cooldown...")
                        break
                    msg = f"Batch in progress ({active}/{total_workers} active sessions)"
                    render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg=msg)

            # 5. Cleanly close terminals and apply random 2-3 minute cooldown before rotating
            close_all_terminals()
            clear_trigger_flag()

            cooldown_min = min(args.cooldown_min, args.cooldown_max)
            cooldown_max = max(args.cooldown_min, args.cooldown_max)
            cooldown_seconds = random.randint(cooldown_min, cooldown_max) if cooldown_max > 0 else 0

            if cooldown_seconds > 0:
                cooldown_end = time.time() + cooldown_seconds
                while time.time() < cooldown_end:
                    remaining = int(cooldown_end - time.time())
                    mins = remaining // 60
                    secs = remaining % 60
                    msg = f"⏳ Cooldown ({mins}m {secs:02d}s remaining) before rotating to next location..."
                    render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg=msg)
                    time.sleep(1.0)

    except KeyboardInterrupt:
        sys.stdout.write("\n\n  🛑 SUPERVISOR STOPPED BY USER (Ctrl+C)\n")
        sys.stdout.flush()
    finally:
        sys.stdout.write("  [*] Stopping all workers and closing Terminal windows...\n")
        close_all_terminals()
        clear_trigger_flag()
        sys.stdout.write("  [*] Disconnecting OpenVPN...\n")
        disconnect_vpn()
        sys.stdout.write("  ✅ All workers stopped and VPN disconnected cleanly.\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
