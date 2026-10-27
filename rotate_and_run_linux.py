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
        "id": "2",
        "email": "dd@gmail.com",
        "url": "https://websurfer.1024tenbox.com/referral/XUMZDQ5R",
    },
    {
        "id": "3",
        "email": "jn@gmail.com",
        "url": "https://websurfer.1024tenbox.com/referral/75H3QGGK",
    },
    {
        "id": "4",
        "email": "dai@gmail.com",
        "url": "https://websurfer.1024tenbox.com/referral/8PCCMJ33",
    },
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Linux 10-Worker Runner with Live Dashboard & NordVPN Auto-Rotator"
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=10,
        help="Total number of workers distributed across accounts (default: 10)",
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

    sys.stdout.write("\033[H\033[J")

    total_runs = stats['total_success'] + stats['total_failure']
    rate_pct = f"{(stats['total_success'] / max(total_runs, 1) * 100):.1f}%" if total_runs > 0 else "0.0%"
    speed_hr = f"{(stats['total_success'] / max(elapsed, 1) * 3600):.1f}/h"

    out = []
    out.append("╔═══════════════════════════════════════════════════════════════════════════════╗")
    out.append("║          🛡️  CLOUDFLARE AUTO -- 10-WORKER DASHBOARD & NORDVPN ROTATOR          ║")
    out.append("╠═══════════════════════════════════════════════════════════════════════════════╣")
    out.append(f"║  Cycle     : #{cycle:<4} | Uptime: {uptime_str:<8} | Status: {status_msg:<27}║")
    out.append(f"║  Public IP : {ip:<15} | Location: {city}, {country:<4} | ISP: {org:<22}║")
    out.append("╠═══════════════════════════════════════════════════════════════════════════════╣")
    out.append(f"║  SUCCESS: {stats['total_success']:<5} ✅ │ FAILED: {stats['total_failure']:<4} ❌ │ RATE: {rate_pct:<6} │ SPEED: {speed_hr:<8}   ║")
    out.append(f"║  ACTIVE WORKERS: {active_workers}/{total_workers:<2} 🚀 │ LIMITS: {stats['total_rate_limit']:<3} ⚠️ │ POLICY: Instant Auto-Rotation  ║")
    out.append("╠═══════════════════════════════════════════════════════════════════════════════╣")
    out.append("║  ACCOUNTS STATUS (Distributed across 4 referral accounts):                    ║")

    for idx, acc in enumerate(ACCOUNTS):
        acc_st = stats["accounts"].get(acc["email"], {"success": 0, "failure": 0, "rate_limit": 0})
        acc_runs = acc_st["success"] + acc_st["failure"]
        acc_rate = f"{(acc_st['success'] / max(acc_runs, 1) * 100):.0f}%" if acc_runs > 0 else "0%"
        assigned_w = 3 if idx in (0, 1) else 2
        out.append(
            f"║   [{idx+1}] {acc['email']:<15} : {acc_st['success']:<4} ✅ | {acc_st['failure']:<3} ❌ | {acc_rate:<4} rate | {assigned_w} workers       ║"
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
    out.append("  [Tip] Workers running in visible terminal windows. Press Ctrl+C to stop cleanly.")

    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def main():
    args = parse_args()
    total_workers = args.num_workers
    start_time = time.time()
    cycle_count = 0

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    clear_trigger_flag()

    ip_info = {"ip": "Connecting...", "country": "??", "city": "...", "org": "NordVPN"}

    try:
        while True:
            cycle_count += 1

            # 1. Close any existing worker processes and terminal windows
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
                        render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="⚠️ All batch sessions finished/limited! Rotating...")
                        time.sleep(2.5)
                        break
                else:
                    if active == 0 and batch_elapsed > 30:
                        render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="Batch Completed! Rotating to fresh location...")
                        time.sleep(2.5)
                        break
                    elif batch_elapsed >= max_batch_time:
                        render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg="Batch Time Complete. Cycling...")
                        time.sleep(2.5)
                        break
                    msg = f"Batch in progress ({active}/{total_workers} active sessions)"
                    render_dashboard(cycle_count, start_time, ip_info, total_workers, status_msg=msg)

    except KeyboardInterrupt:
        sys.stdout.write("\n\n  🛑 SUPERVISOR STOPPED BY USER (Ctrl+C)\n")
        sys.stdout.flush()
    finally:
        sys.stdout.write("  [*] Stopping all workers and closing terminal windows...\n")
        close_all_terminals()
        clear_trigger_flag()
        sys.stdout.write("  [*] Disconnecting OpenVPN...\n")
        disconnect_vpn()
        sys.stdout.write("  ✅ All workers stopped and VPN disconnected cleanly.\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
