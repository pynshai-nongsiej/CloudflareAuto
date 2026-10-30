#!/usr/bin/env python3
"""Auto-Rotating 10-Worker Runner & Live Dashboard for Linux / Ubuntu with NordVPN OpenVPN.

Features:
  - 10 workers running in visible terminal emulator windows (GNOME Terminal, xterm, etc.)
    or tmux/background on headless servers.
  - Workers distributed across the 4 referral accounts.
  - Chromium browser runs headlessly (no intrusive popup windows).
  - Extended OTP timeout (120s / 2 minutes) for high reliability.
  - Live console dashboard showing real-time successes, failures, speed, IP, location,
    per-account stats, and live event feed.
  - When batch completes or rate limit is hit:
    1. Cleanly finishes / terminates batch workers.
    2. Randomly selects a fresh location from NordVPN's global server pool.
    3. Reconnects via OpenVPN CLI and verifies the new external IP.
    4. Launches 10 fresh workers in new windows.
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
from src.automation.rich_dashboard import RichDashboard

TRIGGER_FLAG = Path("/tmp/cloudflare_rate_limit_triggered.flag")
EVENTS_FILE = PROJECT_ROOT / "logs" / "events.jsonl"
LOGS_DIR = PROJECT_ROOT / "logs"

ACCOUNTS = [
    {
        "id": "2",
        "email": "dd@gmail.com",
        "url": "https://websurfer.1024tenbox.com/referral/XUMZDQ5R",
    },
    {
        "id": "3",
        "email": "jn@gmail.com",
        "url": "https://websurfer.1024tenbox.com/referral/75H3QGGK",
    },
]

dashboard = RichDashboard(
    platform_name="Linux",
    target_subtitle="Target Accounts: dd & jn (3 workers each)",
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Linux 6-Worker Runner (3 per refer: dd & jn) with Live Dashboard & NordVPN Auto-Rotator"
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=6,
        help="Total number of workers distributed across accounts (default: 6, 3 for dd & 3 for jn)",
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
        help="Run workers in background/tmux without visible terminal windows (default: False, headed)",
    )
    parser.add_argument(
        "--browser-headed",
        action="store_true",
        default=False,
        help="Also run Chromium browser with visible UI (default: False, headless browser)",
    )
    parser.add_argument(
        "--country",
        type=str,
        default=None,
        help="Target country name or ISO code for NordVPN (e.g. 'Germany', 'US')",
    )
    parser.add_argument(
        "--cooldown-min",
        type=int,
        default=45,
        help="Minimum cooldown delay in seconds after batch/rate-limit before rotating (default: 45 / 45s)",
    )
    parser.add_argument(
        "--cooldown-max",
        type=int,
        default=60,
        help="Maximum cooldown delay in seconds after batch/rate-limit before rotating (default: 60 / 1 min)",
    )
    return parser.parse_args()


def close_all_terminals():
    """Kill all main.py worker processes and close their terminal windows cleanly."""
    subprocess.run(["pkill", "-f", "main.py"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", r"worker_.*\.sh"], stderr=subprocess.DEVNULL)

    # If wmctrl is installed, close GUI windows whose title begins with Worker-
    try:
        res = subprocess.run(["wmctrl", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "Worker-" in line:
                    parts = line.split()
                    if parts:
                        subprocess.run(["wmctrl", "-ic", parts[0]], stderr=subprocess.DEVNULL)
    except Exception:
        pass

    # If tmux session is active, stop it
    try:
        subprocess.run(["tmux", "kill-session", "-t", "cloudflare-auto"], stderr=subprocess.DEVNULL)
    except Exception:
        pass

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


def launch_workers(num_workers: int, mode: str, delay_min: int, delay_max: int, browser_headed: bool = False, headless: bool = False):
    """Launch workers in visible terminal windows across all 4 accounts."""
    env = os.environ.copy()
    env["NUM_WINDOWS"] = str(num_workers)
    env["MODE"] = mode
    env["DELAY_MIN"] = str(delay_min)
    env["DELAY_MAX"] = str(delay_max)
    env["HEADLESS"] = "true" if headless else "false"

    extra = ["--exit-on-rate-limit", "--timeout", "120"]
    if browser_headed:
        extra.append("--headed")
    env["EXTRA_ARGS"] = " ".join(extra)

    launcher = PROJECT_ROOT / "launch_multi_linux.sh"
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

        recent_events = recent_events[-8:]
    except Exception:
        pass

    return stats, recent_events


def render_dashboard(cycle: int, start_time: float, ip_info: dict, total_workers: int, status_msg: str = "Active"):
    """Render terminal dashboard cleanly via Rich."""
    stats, recent_events = read_events_stats()
    active_workers = count_active_workers()
    dashboard.render(
        cycle=cycle,
        start_time=start_time,
        ip_info=ip_info,
        total_workers=total_workers,
        active_workers=active_workers,
        stats=stats,
        recent_events=recent_events,
        accounts=ACCOUNTS,
        status_msg=status_msg,
    )


def main():
    args = parse_args()
    total_workers = args.num_workers
    start_time = time.time()
    cycle_count = 0

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    clear_trigger_flag()
    dashboard.start()

    ip_info = {"ip": "Connecting...", "country": "??", "city": "...", "org": "NordVPN"}

    try:
        while True:
            cycle_count += 1

            # 1. Close any existing worker processes and terminal windows
            render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="Rotating VPN...")
            close_all_terminals()
            clear_trigger_flag()

            # 2. Rotate NordVPN across 7,100+ servers with verified public IP change
            ip_info = None
            rot_attempt = 0
            while not ip_info and rot_attempt < 5:
                rot_attempt += 1
                try:
                    render_dashboard(
                        cycle_count,
                        start_time,
                        {"ip": "Rotating...", "country": "??", "city": "...", "org": "NordVPN"},
                        total_workers,
                        status_msg=f"Rotating VPN across 7,100+ pool (Attempt {rot_attempt}/5)...",
                    )
                    country_target = args.country if args.country and cycle_count == 1 else None
                    ip_info = rotate_vpn(country_target)
                except Exception as e:
                    render_dashboard(
                        cycle_count,
                        start_time,
                        {"ip": "Retrying...", "country": "??", "city": "...", "org": "NordVPN"},
                        total_workers,
                        status_msg=f"⚠️ VPN Rotation Error: {e}",
                    )
                    time.sleep(3)

            if not ip_info or ip_info.get("ip") in ("unknown", "Connecting...", "Retrying...", "Rotating..."):
                raise RuntimeError("Failed to verify IP change after VPN rotation. Aborting batch to protect local IP from rate limits.")

            # 3. Launch 10 workers in visible terminal windows
            mode_desc = "Headed Terminal Windows" if not args.headless else "Headless Background"
            render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg=f"Launching {total_workers} Workers ({mode_desc})...")
            launch_workers(
                num_workers=total_workers,
                mode=args.mode,
                delay_min=args.delay_min,
                delay_max=args.delay_max,
                browser_headed=args.browser_headed,
                headless=args.headless,
            )

            # 4. Dashboard monitoring loop: allows all 10 batch sessions to complete before rotating
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

            # 5. Cleanly close terminals and apply random 45s - 1 min cooldown before rotating
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
        dashboard.stop()
        sys.stdout.write("  [*] Stopping all workers and closing terminal windows...\n")
        close_all_terminals()
        clear_trigger_flag()
        sys.stdout.write("  [*] Disconnecting OpenVPN...\n")
        disconnect_vpn()
        sys.stdout.write("  ✅ All workers stopped and VPN disconnected cleanly.\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
