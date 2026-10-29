"""
rich_dashboard.py -- Clean, Static Terminal Dashboard for CloudflareAuto Rotators
================================================================================
Uses the Python 'rich' library to render a flicker-free, modern, beautifully styled
live terminal dashboard across macOS, Linux, and Windows.
"""

import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from rich.console import Console, Group
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class RichDashboard:
    """Flicker-free live terminal dashboard renderer using Rich."""

    def __init__(self, platform_name: str, target_subtitle: str):
        self.platform_name = platform_name
        self.target_subtitle = target_subtitle
        self.console = Console(highlight=False) if RICH_AVAILABLE else None
        self._live: Optional[Any] = None

    def start(self):
        """Start the Rich Live context if available."""
        if RICH_AVAILABLE and self._live is None:
            # screen=False keeps it in standard scrollback without full-screen buffer flicker
            self._live = Live(
                console=self.console,
                auto_refresh=False,
                screen=False,
                transient=False,
            )
            self._live.start()

    def stop(self):
        """Stop the Rich Live context cleanly."""
        if self._live is not None:
            try:
                self._live.stop()
            except Exception:
                pass
            self._live = None

    def _build_renderable(
        self,
        cycle: int,
        start_time: float,
        ip_info: Dict[str, Any],
        total_workers: int,
        active_workers: int,
        stats: Dict[str, Any],
        recent_events: List[Dict[str, Any]],
        accounts: List[Dict[str, Any]],
        status_msg: str,
    ):
        """Build the complete Rich Group of tables and panels."""
        elapsed = int(time.time() - start_time)
        hours = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        uptime_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

        ip = ip_info.get("ip", "Checking...")
        country = ip_info.get("country", "??")
        city = ip_info.get("city", "N/A")
        org = ip_info.get("org", "NordVPN")

        total_runs = stats.get("total_success", 0) + stats.get("total_failure", 0)
        rate_pct = f"{(stats.get('total_success', 0) / max(total_runs, 1) * 100):.1f}%" if total_runs > 0 else "0.0%"
        speed_hr = f"{(stats.get('total_success', 0) / max(elapsed, 1) * 3600):.1f}/h"

        # ── 1. Top Header Banner ────────────────────────────────────
        header_text = Text()
        header_text.append("🛡️  CLOUDFLARE AUTO ", style="bold bright_cyan")
        header_text.append("• ", style="bright_black")
        header_text.append(f"{self.platform_name.upper()} SUPERVISOR ", style="bold bright_white")
        header_text.append("• ", style="bright_black")
        header_text.append(f"{self.target_subtitle}", style="bold yellow")

        # ── 2. Network & Session Status Grid ───────────────────────
        net_table = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False, pad_edge=False)
        net_table.add_column("Cycle", style="bold white", justify="center")
        net_table.add_column("Uptime", style="bright_cyan", justify="center")
        net_table.add_column("Current Status", style="bold", justify="left")
        net_table.add_column("Public IP", style="bright_green", justify="center")
        net_table.add_column("Location", style="white", justify="left")
        net_table.add_column("Network / ISP", style="bright_blue", justify="left")

        # Style status message dynamically
        status_lower = status_msg.lower()
        if "rotating" in status_lower:
            styled_status = Text(f"🔄 {status_msg}", style="bold magenta")
        elif "cooldown" in status_lower or "waiting" in status_lower:
            styled_status = Text(f"⏳ {status_msg}", style="bold yellow")
        elif "rate limit" in status_lower:
            styled_status = Text(f"⚠️ {status_msg}", style="bold red")
        elif "launching" in status_lower:
            styled_status = Text(f"🚀 {status_msg}", style="bold cyan")
        elif "completed" in status_lower or "active" in status_lower or "progress" in status_lower:
            styled_status = Text(f"🟢 {status_msg}", style="bold green")
        else:
            styled_status = Text(status_msg, style="bold bright_white")

        loc_state = ip_info.get("state") or ip_info.get("region")
        if city != "N/A" and loc_state and loc_state != "N/A" and loc_state.lower() != city.lower():
            loc_str = f"{city}, {loc_state}, {country}"
        elif city != "N/A":
            loc_str = f"{city}, {country}"
        else:
            loc_str = country

        net_table.add_row(
            f"#{cycle}",
            uptime_str,
            styled_status,
            ip,
            loc_str[:32],
            org[:26],
        )

        # ── 3. Performance KPI Cards ────────────────────────────────
        kpi_table = Table(box=box.ROUNDED, expand=True, border_style="bright_blue", show_header=True)
        kpi_table.add_column("✅ Total Success", style="bold bright_green", justify="center")
        kpi_table.add_column("❌ Total Failed", style="bold bright_red", justify="center")
        kpi_table.add_column("⚠️ Rate Limits", style="bold yellow", justify="center")
        kpi_table.add_column("📈 Success Rate", style="bold bright_white", justify="center")
        kpi_table.add_column("⚡ Hourly Speed", style="bold bright_cyan", justify="center")
        kpi_table.add_column("👥 Active Workers", style="bold bright_magenta", justify="center")

        active_workers_str = f"{active_workers}/{total_workers}"
        kpi_table.add_row(
            str(stats.get("total_success", 0)),
            str(stats.get("total_failure", 0)),
            str(stats.get("total_rate_limit", 0)),
            rate_pct,
            speed_hr,
            active_workers_str,
        )

        # ── 4. Account Breakdown Table ──────────────────────────────
        acc_table = Table(
            title="🎯 Target Referral Accounts Breakdown",
            title_style="bold bright_white",
            box=box.SIMPLE_HEAVY,
            expand=True,
            show_header=True,
            header_style="bold bright_cyan",
        )
        acc_table.add_column("#", justify="center", width=4)
        acc_table.add_column("Account Email", justify="left", style="bold bright_white")
        acc_table.add_column("Success", justify="center", style="bold bright_green")
        acc_table.add_column("Failed", justify="center", style="bold bright_red")
        acc_table.add_column("Limits", justify="center", style="bold yellow")
        acc_table.add_column("Rate", justify="center", style="bright_cyan")
        acc_table.add_column("Allocated Workers", justify="center", style="bold bright_yellow")

        assigned_per_acc = total_workers // max(len(accounts), 1)
        for idx, acc in enumerate(accounts):
            acc_email = acc.get("email", "unknown")
            acc_st = stats.get("accounts", {}).get(acc_email, {"success": 0, "failure": 0, "rate_limit": 0})
            acc_runs = acc_st["success"] + acc_st["failure"]
            acc_rate = f"{(acc_st['success'] / max(acc_runs, 1) * 100):.0f}%" if acc_runs > 0 else "0%"
            acc_table.add_row(
                str(idx + 1),
                acc_email,
                f"{acc_st['success']} ✅",
                f"{acc_st['failure']} ❌",
                f"{acc_st.get('rate_limit', 0)} ⚠️",
                acc_rate,
                f"{assigned_per_acc} workers",
            )

        # ── 5. Live Events Feed ─────────────────────────────────────
        events_table = Table(
            title="📜 Live Registration Events Feed (Most Recent)",
            title_style="bold bright_white",
            box=box.SIMPLE_HEAVY,
            expand=True,
            show_header=True,
            header_style="bold bright_cyan",
        )
        events_table.add_column("Time", justify="center", width=10, style="bright_black")
        events_table.add_column("Worker", justify="center", width=12, style="bright_white")
        events_table.add_column("Target", justify="left", width=14, style="bright_yellow")
        events_table.add_column("Status", justify="center", width=10)
        events_table.add_column("Details", justify="left", style="white")

        if not recent_events:
            events_table.add_row("-", "-", "-", "[dim]WAITING[/dim]", "[dim]Waiting for initial registration events...[/dim]")
        else:
            for ev in reversed(recent_events[-6:]):
                ts = datetime.fromtimestamp(ev.get("timestamp", time.time())).strftime("%H:%M:%S")
                w_id = ev.get("worker_id", "Worker-??")
                ev_t = ev.get("event")
                acc_name = ev.get("account", "").split("@")[0]

                if ev_t == "success":
                    status_col = Text("SUCCESS", style="bold bright_green")
                    detail = f"Verified: {ev.get('email', 'N/A')}"
                elif ev_t == "rate_limit":
                    status_col = Text("LIMITED", style="bold yellow")
                    detail = "Rate limit hit -> supervisor rotation triggered"
                else:
                    status_col = Text("FAILED", style="bold bright_red")
                    detail = str(ev.get("error", "Registration error"))[:48]

                events_table.add_row(ts, w_id, acc_name, status_col, detail)

        footer_text = Text(
            "💡 Press Ctrl+C to stop all workers cleanly  •  Auto-rotates IP upon rate limits  •  Logs: logs/events.jsonl",
            style="dim italic",
            justify="center",
        )

        main_panel = Panel(
            Group(
                header_text,
                Text(""),
                net_table,
                Text(""),
                kpi_table,
                Text(""),
                acc_table,
                Text(""),
                events_table,
                Text(""),
                footer_text,
            ),
            box=box.ROUNDED,
            border_style="bright_cyan",
            padding=(1, 2),
        )

        return main_panel

    def render(
        self,
        cycle: int,
        start_time: float,
        ip_info: Dict[str, Any],
        total_workers: int,
        active_workers: int,
        stats: Dict[str, Any],
        recent_events: List[Dict[str, Any]],
        accounts: List[Dict[str, Any]],
        status_msg: str = "Active",
    ):
        """Render dashboard to console cleanly."""
        if not RICH_AVAILABLE or self.console is None:
            # Fallback for plain terminal without rich
            self._render_plain(cycle, start_time, ip_info, total_workers, active_workers, stats, recent_events, accounts, status_msg)
            return

        renderable = self._build_renderable(
            cycle, start_time, ip_info, total_workers, active_workers, stats, recent_events, accounts, status_msg
        )

        if self._live is not None:
            self._live.update(renderable, refresh=True)
        else:
            # Fallback if Live context not active: clear screen and print
            self.console.clear()
            self.console.print(renderable)

    def _render_plain(
        self,
        cycle: int,
        start_time: float,
        ip_info: Dict[str, Any],
        total_workers: int,
        active_workers: int,
        stats: Dict[str, Any],
        recent_events: List[Dict[str, Any]],
        accounts: List[Dict[str, Any]],
        status_msg: str,
    ):
        """Standard plain ANSI fallback if rich is unavailable."""
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
        total_runs = stats.get("total_success", 0) + stats.get("total_failure", 0)
        rate_pct = f"{(stats.get('total_success', 0) / max(total_runs, 1) * 100):.1f}%" if total_runs > 0 else "0.0%"
        speed_hr = f"{(stats.get('total_success', 0) / max(elapsed, 1) * 3600):.1f}/h"

        loc_state = ip_info.get("state") or ip_info.get("region")
        loc_str = f"{city}, {loc_state}, {country}" if (loc_state and loc_state != "N/A" and loc_state.lower() != city.lower()) else f"{city}, {country}"
        out = [
            f"╔═══════════════════════════════════════════════════════════════════════════════╗",
            f"║  🛡️  CLOUDFLARE AUTO -- {self.platform_name.upper()} SUPERVISOR DASHBOARD",
            f"║     {self.target_subtitle}",
            f"╠═══════════════════════════════════════════════════════════════════════════════╣",
            f"║  Cycle     : #{cycle:<4} | Uptime: {uptime_str:<8} | Status: {status_msg:<27}",
            f"║  Public IP : {ip:<15} | Location: {loc_str[:26]:<26} | ISP: {org:<22}",
            f"╠═══════════════════════════════════════════════════════════════════════════════╣",
            f"║  SUCCESS: {stats.get('total_success', 0):<5} ✅ │ FAILED: {stats.get('total_failure', 0):<4} ❌ │ RATE: {rate_pct:<6} │ SPEED: {speed_hr:<8}",
            f"║  ACTIVE WORKERS: {active_workers}/{total_workers:<2} 🚀 │ LIMITS: {stats.get('total_rate_limit', 0):<3} ⚠️",
            f"╠═══════════════════════════════════════════════════════════════════════════════╣",
        ]
        for idx, acc in enumerate(accounts):
            acc_email = acc.get("email", "")
            acc_st = stats.get("accounts", {}).get(acc_email, {"success": 0, "failure": 0})
            out.append(f"║   [{idx+1}] {acc_email:<16}: {acc_st['success']} ✅ | {acc_st['failure']} ❌")
        out.append(f"╚═══════════════════════════════════════════════════════════════════════════════╝")
        sys.stdout.write("\n".join(out) + "\n")
        sys.stdout.flush()
