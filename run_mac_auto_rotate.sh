#!/usr/bin/env bash
# ==============================================================================
#  run_mac_auto_rotate.sh -- 24/7 Auto-Rotating Multi-Worker Runner for macOS
# ==============================================================================
#  Launches 6 workers (3 for pn@gmail.com and 3 for dai@gmail.com).
#  When a rate-limit cooldown is hit:
#    1. Kills all worker processes & closes their terminal windows cleanly
#    2. Randomly selects a new location without duplicate in the same session
#    3. Switches VPN via OpenVPN CLI
#    4. Launches 6 fresh workers in new terminals
# ==============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Ensure sudo credentials are valid and kept alive for the session
if [[ $EUID -ne 0 ]]; then
    if ! sudo -n true 2>/dev/null; then
        echo "================================================================"
        echo "  CloudflareAuto requires sudo to manage OpenVPN on macOS."
        echo "  Please enter your sudo password:"
        echo "================================================================"
        sudo -v || exit 1
    fi
    # Keep sudo credentials active in background
    ( while true; do sudo -n true 2>/dev/null; sleep 50; done ) &
    SUDO_PID=$!
    trap "kill -9 $SUDO_PID 2>/dev/null || true" EXIT
fi

PYTHON="$PROJECT_DIR/.venv/bin/python"
if [[ ! -f "$PYTHON" ]]; then
    PYTHON="python3"
fi

chmod +x "$PROJECT_DIR/launch_multi_mac.sh"
chmod +x "$PROJECT_DIR/rotate_and_run_mac.py"

exec "$PYTHON" "$PROJECT_DIR/rotate_and_run_mac.py" "$@"
