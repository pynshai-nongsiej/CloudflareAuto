#!/usr/bin/env bash
# ============================================================
#  launch_multi_mac.sh — Launch 10 CloudflareAuto sessions
#  macOS only  |  Uses AppleScript (osascript) + Terminal.app
# ============================================================
#
#  Layout: 5 columns x 2 rows  (each window ~380x380 px)
#  Each terminal starts with a random delay of 5-20 seconds
#  so sessions are staggered and don't hammer the server together.
#
#  Usage:
#    chmod +x launch_multi_mac.sh
#    ./launch_multi_mac.sh
#
#  Options (env vars):
#    NUM_WINDOWS=10  -- number of windows  (default 10)
#    MODE=direct     -- main.py --mode     (default: direct)
# ============================================================

set -euo pipefail

# -- Config --------------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NUM_WINDOWS="${NUM_WINDOWS:-10}"
MODE="${MODE:-direct}"

# Virtual-env detection (prefer .venv, then venv)
PYTHON="python3"
if [[ -f "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [[ -f "$PROJECT_DIR/venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"
fi

# -- Grid geometry -------------------------------------------
# Detect screen size using osascript
SCREEN_INFO=$(osascript -e 'tell application "Finder" to get bounds of window of desktop' 2>/dev/null || echo "0, 0, 1920, 1080")
SCREEN_W=$(echo "$SCREEN_INFO" | awk -F', ' '{print $3}')
SCREEN_H=$(echo "$SCREEN_INFO" | awk -F', ' '{print $4}')

COLS=5
ROWS=2
MARGIN=5
TITLE_BAR=28   # macOS menu bar + title bar offset

WIN_W=$(( (SCREEN_W - (COLS + 1) * MARGIN) / COLS ))
WIN_H=$(( (SCREEN_H - (ROWS + 1) * MARGIN - TITLE_BAR) / ROWS ))

echo "================================================================"
echo "   CloudflareAuto -- 10-Window macOS Launcher"
echo "================================================================"
echo "  Project : $PROJECT_DIR"
echo "  Python  : $PYTHON"
echo "  Mode    : $MODE (--loop)"
echo "  Windows : $NUM_WINDOWS  (${COLS}x${ROWS} grid)"
echo "  Screen  : ${SCREEN_W}x${SCREEN_H}  -> each win ${WIN_W}x${WIN_H}"
echo "================================================================"
echo ""

# -- Helper: random integer in [lo, hi] ----------------------
rand_between() {
    echo $(( RANDOM % ($2 - $1 + 1) + $1 ))
}

# -- Open each terminal window --------------------------------
for (( i=0; i<NUM_WINDOWS; i++ )); do

    # Grid position
    COL=$(( i % COLS ))
    ROW=$(( i / COLS ))

    X=$(( MARGIN + COL * (WIN_W + MARGIN) ))
    Y=$(( TITLE_BAR + MARGIN + ROW * (WIN_H + MARGIN) ))

    # Right/bottom edge for AppleScript bounds
    X2=$(( X + WIN_W ))
    Y2=$(( Y + WIN_H ))

    # Random start delay per window (5-20 s)
    DELAY=$(rand_between 5 20)

    # Label shown in the terminal title
    LABEL="Worker-$(printf '%02d' $((i+1)))"

    echo "  [$LABEL]  col=$COL row=$ROW  pos=(${X},${Y})  size=${WIN_W}x${WIN_H}  delay=${DELAY}s"

    # Shell snippet that runs INSIDE the Terminal window
    read -r -d '' INNER_CMD <<INNER || true
printf '\\033]0;${LABEL}\\007'; cd '${PROJECT_DIR}'; echo ''; echo '=== ${LABEL} : starting in ${DELAY}s ==='; sleep ${DELAY}; echo ''; echo '[${LABEL}] Launching loop...'; echo ''; while true; do '${PYTHON}' main.py --mode ${MODE} --loop; echo '[${LABEL}] Exited -- restarting in 5s...'; sleep 5; done
INNER

    # Escape single-quotes for AppleScript string
    ESCAPED_CMD="${INNER_CMD//\'/\'}"

    # AppleScript: open new Terminal window, run the command, then resize it
    osascript <<APPLESCRIPT
tell application "Terminal"
    activate
    set newWin to do script "${INNER_CMD}"
    delay 0.5
    set bounds of window 1 to {${X}, ${Y}, ${X2}, ${Y2}}
end tell
APPLESCRIPT

    # Brief pause so Terminal can open the window cleanly
    sleep 0.7

done

echo ""
echo "All $NUM_WINDOWS windows launched and arranged."
echo ""
echo "To stop ALL workers at once, run:"
echo "  pkill -f 'main.py'"
