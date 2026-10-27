#!/usr/bin/env python3
"""Auto-Rotating 10-Worker Runner & Live Dashboard for Windows with NordVPN OpenVPN.

Features:
  - 10 workers running in visible CMD windows arranged in a 5x2 desktop grid.
  - Workers distributed across the 4 referral accounts.
  - Chromium browser runs headlessly in the background (no popup windows).
  - Extended OTP timeout (120s / 2 minutes) for high delivery reliability.
  - Live console dashboard showing real-time successes, failures, speed, IP, location,
    per-account stats, and live event feed.
  - When batch completes or rate limit is hit:
    1. Cleanly finishes / terminates batch workers.
    2. Randomly selects a fresh location from NordVPN's global server pool.
    3. Reconnects via OpenVPN CLI and verifies the new external IP.
    4. Launches 10 fresh workers in tiled CMD windows.
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

TRIGGER_FLAG = Path(os.environ.get("TEMP", r"C:\Temp")) / "cloudflare_rate_limit_triggered.flag"
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
    platform_name="Windows",
    target_subtitle="Target Accounts: dd & jn (3 workers each)",
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Windows 6-Worker Runner with Live Dashboard & NordVPN Auto-Rotator"
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=6,
        help="Total number of workers distributed across accounts (default: 6)",
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
        default=True,
        help="Run CMD terminal windows hidden in background (default: True, headless)",
    )
    parser.add_argument(
        "--headed",
        dest="headless",
        action="store_false",
        help="Run CMD terminal windows visibly tiled across desktop",
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
    """Kill all main.py worker processes and close their CMD windows cleanly."""
    try:
        subprocess.run(["taskkill", "/F", "/T", "/FI", "WINDOWTITLE eq Worker-*"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    try:
        ps_cmd = (
            "Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*Worker-*' } | Stop-Process -Force -ErrorAction SilentlyContinue; "
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
            "Where-Object { ($_.Name -eq 'cmd.exe' -and ($_.CommandLine -like '*cloudflare_auto_workers*' -or $_.CommandLine -like '*worker_*.bat*')) -or ($_.Name -eq 'python.exe' -and $_.CommandLine -like '*main.py*') } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    """Return count of actively running main.py processes on Windows."""
    try:
        ps_cmd = (
            "@((Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" -ErrorAction SilentlyContinue) | "
            "Where-Object { $_.CommandLine -like '*main.py*' }).Count"
        )
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        val = res.stdout.strip()
        return int(val) if val.isdigit() else 0
    except Exception:
        return 0


def launch_workers(num_workers: int, mode: str, delay_min: int, delay_max: int, browser_headed: bool = False, headless: bool = False):
    """Launch workers in visible CMD windows arranged across desktop."""
    launcher = PROJECT_ROOT / "launch_multi_windows.ps1"
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(launcher),
        "-Account", "5",
        "-NumWindows", str(num_workers),
        "-Mode", mode,
        "-DelayMin", str(delay_min),
        "-DelayMax", str(delay_max),
    ]

    if headless:
        cmd.append("-Headless")
    if browser_headed:
        cmd.append("-BrowserHeaded")

    subprocess.run(cmd, cwd=str(PROJECT_ROOT))


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

            # 1. Close any existing worker processes and CMD windows
            render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="Rotating VPN...")
            close_all_terminals()
            clear_trigger_flag()

            # 2. Rotate NordVPN to random location via OpenVPN CLI
            try:
                country_target = args.country if args.country and cycle_count == 1 else None
                ip_info = rotate_vpn(country_target)
            except Exception as e:
                time.sleep(3)
                try:
                    ip_info = rotate_vpn()
                except Exception:
                    ip_info = get_current_ip_info()

            # 3. Launch workers in visible CMD windows
            mode_desc = "Headed CMD Windows" if not args.headless else "Headless Background"
            render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg=f"Launching {total_workers} Workers ({mode_desc})...")
            launch_workers(
                num_workers=total_workers,
                mode=args.mode,
                delay_min=args.delay_min,
                delay_max=args.delay_max,
                browser_headed=args.browser_headed,
                headless=args.headless,
            )

            # 4. Dashboard monitoring loop: allows all batch sessions to complete before rotating
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
        dashboard.stop()
        sys.stdout.write("  [*] Stopping all workers and closing CMD windows...\n")
        close_all_terminals()
        clear_trigger_flag()
        sys.stdout.write("  [*] Disconnecting OpenVPN...\n")
        disconnect_vpn()
        sys.stdout.write("  ✅ All workers stopped and VPN disconnected cleanly.\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
