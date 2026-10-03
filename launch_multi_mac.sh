#!/usr/bin/env bash
# ============================================================
#  launch_multi_mac.sh -- Launch 10 CloudflareAuto sessions
#  macOS only  |  Uses AppleScript (osascript) + Terminal.app
# ============================================================
#
#  Layout: 5 columns x 2 rows
#  Each terminal starts with a RANDOM delay of 5-20 seconds
#  so sessions are staggered.
#
#  Usage:
#    chmod +x launch_multi_mac.sh
#    ./launch_multi_mac.sh
#
#  Optional env vars:
#    NUM_WINDOWS=10   number of windows  (default 10)
#    MODE=direct      main.py --mode arg (default: direct)
# ============================================================

set -euo pipefail

# ── Config ───────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NUM_WINDOWS="${NUM_WINDOWS:-10}"
MODE="${MODE:-direct}"
TMPDIR_WORKERS="/tmp/cloudflare_auto_workers"

# Clean up any old worker scripts
rm -rf "$TMPDIR_WORKERS"
mkdir -p "$TMPDIR_WORKERS"

# Virtual-env detection (prefer .venv, then venv)
PYTHON="python3"
if [[ -f "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [[ -f "$PROJECT_DIR/venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"
fi

# ── Grid geometry ────────────────────────────────────────────
SCREEN_INFO=$(osascript -e 'tell application "Finder" to get bounds of window of desktop' 2>/dev/null || echo "0, 0, 1920, 1080")
SCREEN_W=$(echo "$SCREEN_INFO" | awk -F', ' '{print $3}')
SCREEN_H=$(echo "$SCREEN_INFO" | awk -F', ' '{print $4}')

COLS=5
ROWS=2
MARGIN=5
TITLE_BAR=28

WIN_W=$(( (SCREEN_W - (COLS + 1) * MARGIN) / COLS ))
WIN_H=$(( (SCREEN_H - (ROWS + 1) * MARGIN - TITLE_BAR) / ROWS ))

echo "================================================================"
echo "   CloudflareAuto -- 10-Window macOS Launcher"
echo "================================================================"
echo "  Project : $PROJECT_DIR"
echo "  Python  : $PYTHON"
echo "  Mode    : $MODE (--loop)"
echo "  Windows : $NUM_WINDOWS  (${COLS}x${ROWS} grid)"
echo "  Screen  : ${SCREEN_W}x${SCREEN_H}  ->  each win ${WIN_W}x${WIN_H}"
echo "================================================================"
echo ""

# ── Helper: random integer in [lo, hi] ──────────────────────
rand_between() {
    echo $(( RANDOM % ($2 - $1 + 1) + $1 ))
}

# ── Launch each window ───────────────────────────────────────
for (( i=0; i<NUM_WINDOWS; i++ )); do

    COL=$(( i % COLS ))
    ROW=$(( i / COLS ))

    X=$(( MARGIN + COL * (WIN_W + MARGIN) ))
    Y=$(( TITLE_BAR + MARGIN + ROW * (WIN_H + MARGIN) ))
    X2=$(( X + WIN_W ))
    Y2=$(( Y + WIN_H ))

    DELAY=$(rand_between 5 20)
    NUM=$(printf '%02d' $((i+1)))
    LABEL="Worker-${NUM}"
    WORKER_SCRIPT="$TMPDIR_WORKERS/worker_${NUM}.sh"

    echo "  [$LABEL]  grid=(${COL},${ROW})  pos=(${X},${Y})  size=${WIN_W}x${WIN_H}  delay=${DELAY}s"

    # ── Write a standalone bash script for this worker ───────
    # Avoid ANY special-char quoting issues with AppleScript by
    # running a plain file path instead of an inline command.
    cat > "$WORKER_SCRIPT" <<WORKER_EOF
#!/usr/bin/env bash
# Set terminal title
printf '\033]0;${LABEL}\007'

cd "${PROJECT_DIR}"

echo ""
echo "============================================="
echo "  ${LABEL} -- waiting ${DELAY}s before start"
echo "============================================="
sleep ${DELAY}

echo ""
echo "[${LABEL}] Starting automation loop (mode=${MODE})..."
echo ""

while true; do
    "${PYTHON}" main.py --mode ${MODE} --loop
    echo ""
    echo "[${LABEL}] Process exited -- restarting in 5s..."
    sleep 5
done
WORKER_EOF

    chmod +x "$WORKER_SCRIPT"

    # ── AppleScript: open Terminal, run the worker file, resize ─
    osascript - "$WORKER_SCRIPT" "$X" "$Y" "$X2" "$Y2" <<'APPLESCRIPT'
on run argv
    set workerScript to item 1 of argv
    set xPos  to (item 2 of argv) as integer
    set yPos  to (item 3 of argv) as integer
    set xPos2 to (item 4 of argv) as integer
    set yPos2 to (item 5 of argv) as integer

    tell application "Terminal"
        activate
        do script "exec bash " & quoted form of workerScript
        delay 0.6
        set bounds of window 1 to {xPos, yPos, xPos2, yPos2}
    end tell
end run
APPLESCRIPT

    sleep 0.5

done

echo ""
echo "All ${NUM_WINDOWS} windows launched and arranged in a ${COLS}x${ROWS} grid."
echo ""
echo "Worker scripts are in: $TMPDIR_WORKERS"
echo ""
echo "To stop ALL workers at once, run:"
echo "  pkill -f 'main.py'"
