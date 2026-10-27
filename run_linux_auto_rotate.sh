#!/usr/bin/env bash
# ==============================================================================
#  run_linux_auto_rotate.sh -- 24/7 Auto-Rotating Multi-Worker Runner for Linux
# ==============================================================================
#  Launches 10 workers distributed across dd and jn (5 workers each).
#  Browser runs headlessly with extended 120s OTP timeout.
#  Terminals run headed (visible) or tmux/bg on headless servers.
#  When a rate-limit is encountered or batch finishes:
#    1. Lets running sessions complete cleanly
#    2. Selects a fresh random server from NordVPN global locations
#    3. Reconnects via OpenVPN CLI
#    4. Launches 10 fresh workers in new windows
# ==============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Ensure sudo credentials are valid and kept alive for the session
if [[ $EUID -ne 0 ]]; then
    if ! sudo -n true 2>/dev/null; then
        echo "================================================================"
        echo "  CloudflareAuto requires sudo to manage OpenVPN on Linux."
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

chmod +x "$PROJECT_DIR/launch_multi_linux.sh"
chmod +x "$PROJECT_DIR/rotate_and_run_linux.py"

exec "$PYTHON" "$PROJECT_DIR/rotate_and_run_linux.py" "$@"

