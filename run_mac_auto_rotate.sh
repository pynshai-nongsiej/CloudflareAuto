#!/usr/bin/env bash
# ==============================================================================
#  run_mac_auto_rotate.sh -- 24/7 Auto-Rotating Multi-Worker Runner for macOS
# ==============================================================================
#  Launches 20 workers (5 for each of the 4 referral links).
#  When a 15-minute rate-limit cooldown is hit:
#    1. Kills all worker processes & closes their terminal windows with pkill
#    2. Randomly selects a new location from 150+ NordVPN countries
#    3. Switches VPN via OpenVPN CLI
#    4. Launches 20 fresh workers in new terminals
# ==============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON="$PROJECT_DIR/.venv/bin/python"
if [[ ! -f "$PYTHON" ]]; then
    PYTHON="python3"
fi

chmod +x "$PROJECT_DIR/launch_multi_mac.sh"
chmod +x "$PROJECT_DIR/rotate_and_run_mac.py"

exec "$PYTHON" "$PROJECT_DIR/rotate_and_run_mac.py" "$@"
