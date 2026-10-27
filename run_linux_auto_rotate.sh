#!/usr/bin/env bash
# ==============================================================================
#  run_linux_auto_rotate.sh -- 24/7 Auto-Rotating Multi-Worker Runner for Linux
# ==============================================================================
#  Launches 10 workers distributed across the 4 referral accounts.
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

PYTHON="$PROJECT_DIR/.venv/bin/python"
if [[ ! -f "$PYTHON" ]]; then
    PYTHON="python3"
fi

chmod +x "$PROJECT_DIR/launch_multi_linux.sh"
chmod +x "$PROJECT_DIR/rotate_and_run_linux.py"

exec "$PYTHON" "$PROJECT_DIR/rotate_and_run_linux.py" "$@"
