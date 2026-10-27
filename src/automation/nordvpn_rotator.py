#!/usr/bin/env python3
"""NordVPN CLI Rotator for macOS.

Rotates VPN IP addresses by querying NordVPN's API for available locations,
downloading the optimal OpenVPN configuration, and reconnecting via OpenVPN CLI.
"""

import os
import sys
import time
import random
import json
import urllib.request
import subprocess
import platform
import shutil
import tempfile
from pathlib import Path

SYSTEM = platform.system()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AUTH_FILE = PROJECT_ROOT / ".nord_auth.txt"
OVPN_CACHE_DIR = PROJECT_ROOT / "ovpn_configs"

if SYSTEM == "Windows":
    TEMP_DIR = Path(tempfile.gettempdir())
    PID_FILE = str(TEMP_DIR / "nord_openvpn.pid")
    LOG_FILE = str(TEMP_DIR / "nord_openvpn.log")
else:
    PID_FILE = "/tmp/nord_openvpn.pid"
    LOG_FILE = "/tmp/nord_openvpn.log"



def get_openvpn_bin() -> str:
    """Locate the OpenVPN executable on macOS, Linux, or Windows."""
    if SYSTEM == "Darwin":
        for cand in ["/opt/homebrew/opt/openvpn/sbin/openvpn", "/usr/local/sbin/openvpn"]:
            if Path(cand).exists():
                return cand
        return shutil.which("openvpn") or "openvpn"
    elif SYSTEM == "Windows":
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates = [
            Path(prog_files) / "OpenVPN" / "bin" / "openvpn.exe",
            Path(prog_files_x86) / "OpenVPN" / "bin" / "openvpn.exe",
            Path(r"C:\Program Files\OpenVPN\bin\openvpn.exe"),
        ]
        for cand in candidates:
            if cand.exists():
                return str(cand)
        return shutil.which("openvpn.exe") or shutil.which("openvpn") or "openvpn.exe"
    else:  # Linux / Unix
        for cand in ["/usr/sbin/openvpn", "/usr/bin/openvpn", "/usr/local/sbin/openvpn"]:
            if Path(cand).exists():
                return cand
        return shutil.which("openvpn") or "openvpn"


OPENVPN_BIN = get_openvpn_bin()

# Default fallback credentials provided by user
DEFAULT_USER = "NnZb1qmmvz4iJf7y8EjWDjo8"
DEFAULT_PASS = "uwXH67Ynz64N3M85r9EuwQxa"


def ensure_auth_file():
    """Ensure the credentials file exists."""
    if not AUTH_FILE.exists():
        AUTH_FILE.write_text(f"{DEFAULT_USER}\n{DEFAULT_PASS}\n")
        AUTH_FILE.chmod(0o600)


def get_all_available_countries() -> list[dict]:
    """Fetch all active countries supported by NordVPN."""
    url = "https://api.nordvpn.com/v1/servers/countries"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            # Filter countries with active servers
            countries = [c for c in data if c.get("serverCount", 0) > 0]
            return countries
    except Exception as e:
        print(f"[!] Warning: Failed to fetch country list from API ({e}), using curated fallback list.")
        return [
            {"id": 227, "name": "United Kingdom", "code": "GB"},
            {"id": 228, "name": "United States", "code": "US"},
            {"id": 38, "name": "Canada", "code": "CA"},
            {"id": 81, "name": "Germany", "code": "DE"},
            {"id": 74, "name": "France", "code": "FR"},
            {"id": 108, "name": "Japan", "code": "JP"},
            {"id": 195, "name": "Singapore", "code": "SG"},
            {"id": 13, "name": "Australia", "code": "AU"},
            {"id": 153, "name": "Netherlands", "code": "NL"},
            {"id": 208, "name": "Switzerland", "code": "CH"},
            {"id": 206, "name": "Sweden", "code": "SE"},
            {"id": 200, "name": "Spain", "code": "ES"},
            {"id": 106, "name": "Italy", "code": "IT"},
        ]


def get_best_server_for_country(country_id: int) -> dict | None:
    """Find the optimal recommended server for a specific country."""
    url = f"https://api.nordvpn.com/v1/servers/recommendations?filters[country_id]={country_id}&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            servers = json.loads(resp.read().decode())
            if servers:
                return servers[0]
    except Exception as e:
        print(f"[!] Error fetching recommended server for country {country_id}: {e}")
    return None


def download_ovpn_config(hostname: str, proto: str = "udp") -> Path | None:
    """Download .ovpn configuration file for a given server hostname."""
    OVPN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target_file = OVPN_CACHE_DIR / f"{hostname}.{proto}.ovpn"
    if target_file.exists() and target_file.stat().st_size > 500:
        return target_file

    url = f"https://downloads.nordcdn.com/configs/files/ovpn_{proto}/servers/{hostname}.{proto}.ovpn"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            if len(content) > 500:
                target_file.write_bytes(content)
                return target_file
    except Exception as e:
        print(f"[!] Failed to download ovpn for {hostname} ({proto}): {e}")
        # Try fallback to TCP if UDP download fails
        if proto == "udp":
            return download_ovpn_config(hostname, proto="tcp")
    return None


def disconnect_vpn():
    """Disconnect any running OpenVPN process cleanly."""
    if SYSTEM == "Windows":
        subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # macOS or Linux
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        pkill_cmd = ["pkill", "-f", "openvpn"] if is_root else ["sudo", "-n", "pkill", "-f", "openvpn"]
        subprocess.run(pkill_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)


def get_current_ip_info() -> dict:
    """Fetch current external IP and location details."""
    try:
        req = urllib.request.Request("https://ipinfo.io/json", headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {"ip": "unknown", "city": "unknown", "country": "unknown"}


def connect_to_server(ovpn_path: Path) -> bool:
    """Start OpenVPN daemon with the specified config."""
    ensure_auth_file()
    disconnect_vpn()

    # Reset log file with world read/write permissions
    try:
        with open(LOG_FILE, "w") as f:
            f.write("")
        os.chmod(LOG_FILE, 0o666)
    except Exception:
        pass

    if SYSTEM == "Windows":
        cmd = [
            OPENVPN_BIN,
            "--config", str(ovpn_path),
            "--auth-user-pass", str(AUTH_FILE),
            "--log", LOG_FILE,
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            Path(PID_FILE).write_text(str(proc.pid))
        except Exception as e:
            print(f"[!] OpenVPN launch failed on Windows: {e}")
            return False
    else:
        cmd = []
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        if not is_root:
            cmd.extend(["sudo", "-n"])
        cmd.extend([
            OPENVPN_BIN,
            "--config", str(ovpn_path),
            "--auth-user-pass", str(AUTH_FILE),
            "--daemon",
            "--writepid", PID_FILE,
            "--log", LOG_FILE,
        ])
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            print(f"[!] OpenVPN launch exited with return code {res.returncode}")
            return False

    # Wait up to 18 seconds for connection initialization
    start_wait = time.time()
    connected = False
    while time.time() - start_wait < 18:
        time.sleep(1.5)
        if Path(LOG_FILE).exists():
            try:
                log_text = Path(LOG_FILE).read_text(errors="ignore")
                if "Initialization Sequence Completed" in log_text:
                    connected = True
                    break
                if "AUTH_FAILED" in log_text:
                    print("[!] OpenVPN Authentication Failed! Check credentials in .nord_auth.txt")
                    return False
            except Exception as e:
                print(f"[!] Warning reading log: {e}")

    return connected


def rotate_vpn(target_country_name: str = None) -> dict:
    """Choose an available location, connect via OpenVPN, and return verified IP info."""
    countries = get_all_available_countries()
    if not countries:
        raise RuntimeError("No countries available from NordVPN API.")

    chosen_country = None
    if target_country_name:
        for c in countries:
            if c["name"].lower() == target_country_name.lower() or c.get("code", "").lower() == target_country_name.lower():
                chosen_country = c
                break

    if not chosen_country:
        chosen_country = random.choice(countries)

    print(f"\n{'=' * 60}")
    print(f"  🌐 NORDVPN CLI ROTATION")
    print(f"  Target Country:  {chosen_country['name']} ({chosen_country.get('code', 'N/A')})")
    print(f"  Available Pools: {len(countries)} countries")
    print(f"{'=' * 60}")

    server = get_best_server_for_country(chosen_country["id"])
    if not server:
        # Fallback to general random server
        print(f"[!] No server found for {chosen_country['name']}, picking another country...")
        fallback = random.choice(countries)
        server = get_best_server_for_country(fallback["id"])
        chosen_country = fallback

    if not server:
        raise RuntimeError("Failed to resolve recommended NordVPN server.")

    hostname = server["hostname"]
    station_ip = server.get("station", "N/A")
    print(f"  Connecting to:   {server['name']} ({hostname} / {station_ip})...")

    ovpn_path = download_ovpn_config(hostname)
    if not ovpn_path:
        raise RuntimeError(f"Failed to obtain .ovpn configuration for {hostname}")

    success = connect_to_server(ovpn_path)
    if not success:
        print("[!] Connection did not complete within timeout. Retrying with a different country/server...")
        disconnect_vpn()
        fallback_countries = [c for c in countries if c["id"] != chosen_country["id"]]
        if fallback_countries:
            fallback = random.choice(fallback_countries)
            server2 = get_best_server_for_country(fallback["id"])
            if server2:
                ovpn_path2 = download_ovpn_config(server2["hostname"])
                if ovpn_path2:
                    print(f"  Retrying connection with: {server2['name']} ({server2['hostname']})...")
                    success = connect_to_server(ovpn_path2)

    if not success:
        raise RuntimeError("OpenVPN connection initialization failed.")

    # Verify IP
    ip_info = get_current_ip_info()
    print(f"\n  ✅ VPN CONNECTED SUCCESSFULLY")
    print(f"  New Public IP:   {ip_info.get('ip', 'N/A')}")
    print(f"  Location:        {ip_info.get('city', 'N/A')}, {ip_info.get('region', 'N/A')}, {ip_info.get('country', 'N/A')}")
    print(f"  ISP / Org:       {ip_info.get('org', 'N/A')}")
    print(f"{'=' * 60}\n")
    return ip_info


if __name__ == "__main__":
    country_arg = sys.argv[1] if len(sys.argv) > 1 else None
    rotate_vpn(country_arg)
