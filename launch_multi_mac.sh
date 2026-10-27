#!/usr/bin/env bash
# ============================================================
#  launch_multi_mac.sh -- Launch CloudflareAuto sessions
#  macOS only  |  Uses AppleScript (osascript) + Terminal.app
# ============================================================
#
#  Layout: Arranged dynamically (default 5 windows in 3x2 grid)
#  Each terminal starts with a staggered delay (~30s apart:
#  Worker 1: ~10s, Worker 2: ~40s, Worker 3: ~70s, Worker 4: ~100s, Worker 5: ~130s)
#  to avoid rate-limiting.
#
#  Usage:
#    chmod +x launch_multi_mac.sh
#    ./launch_multi_mac.sh
#
#  Optional env vars:
#    NUM_WINDOWS=5    number of windows  (default 5)
#    MODE=direct      main.py --mode arg (default: direct)
# ============================================================

set -euo pipefail

# ── Config ───────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKERS_PER_LINK="${WORKERS_PER_LINK:-2}"
NUM_WINDOWS="${NUM_WINDOWS:-}"
MODE="${MODE:-direct}"
REFERRER="${REFERRER:-none}"
DELAY_MIN="${DELAY_MIN:-0}"
DELAY_MAX="${DELAY_MAX:-0}"
EXTRA_ARGS="${EXTRA_ARGS:-}"
TMPDIR_WORKERS="/tmp/cloudflare_auto_workers"
EXIT_CODE=""
WORKER_STATUS=""

# Terminal window mode: default headed (visible Terminal.app windows)
HEADLESS="${HEADLESS:-false}"

# Browser execution mode: default headless (no Chromium GUI popups)
BROWSER_HEADED="false"

# Parse flags for headless vs headed
for arg in "$@"; do
    if [[ "$arg" == "--headless" ]]; then
        HEADLESS="true"
    elif [[ "$arg" == "--headed" || "$arg" == "--gui" || "$arg" == "--windows" ]]; then
        HEADLESS="false"
    elif [[ "$arg" == "--browser-headed" || "$arg" == "--headed-browser" || "$arg" == "--show-browser" ]]; then
        BROWSER_HEADED="true"
    fi
done

if [[ "$BROWSER_HEADED" == "true" && "$EXTRA_ARGS" != *"--headed"* ]]; then
    EXTRA_ARGS="$EXTRA_ARGS --headed"
fi

# Referral Account Presets
ACCOUNT_1_URL="https://websurfer.1024tenbox.com/referral/XWUPKX2D"
ACCOUNT_1_EMAIL="pn@gmail.com"

ACCOUNT_2_URL="https://websurfer.1024tenbox.com/referral/XUMZDQ5R"
ACCOUNT_2_EMAIL="dd@gmail.com"

ACCOUNT_3_URL="https://websurfer.1024tenbox.com/referral/75H3QGGK"
ACCOUNT_3_EMAIL="jn@gmail.com"

ACCOUNT_4_URL="https://websurfer.1024tenbox.com/referral/8PCCMJ33"
ACCOUNT_4_EMAIL="dai@gmail.com"

# ── Stop Command ─────────────────────────────────────────────
if [[ "${1:-}" == "stop" ]]; then
    echo "================================================================"
    echo "  Stopping all CloudflareAuto workers on macOS..."
    echo "================================================================"
    pkill -f 'main.py' 2>/dev/null || true
    pkill -f 'worker_.*\.sh' 2>/dev/null || true
    rm -rf "$TMPDIR_WORKERS"
    rm -f /tmp/cloudflare_rate_limit_triggered.flag
    rm -rf /tmp/websurfer_screenshots "${TMPDIR:-/tmp}/websurfer_screenshots" 2>/dev/null || true
    echo "  [+] All CloudflareAuto workers stopped."
    echo "================================================================"
    exit 0
fi

# ── Account Selection ────────────────────────────────────────
ROUND_ROBIN=false
TARGET_URL=""
TARGET_EMAIL=""

# Check if passed as first argument
ARG1="${1:-}"
if [[ "$ARG1" =~ ^https?:// ]]; then
    TARGET_URL="$ARG1"
    TARGET_EMAIL="Custom Account"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$ARG1" == "1" || "$ARG1" == "pn" || "$ARG1" == "pn@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_1_URL"
    TARGET_EMAIL="$ACCOUNT_1_EMAIL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$ARG1" == "2" || "$ARG1" == "dd" || "$ARG1" == "dd@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_2_URL"
    TARGET_EMAIL="$ACCOUNT_2_EMAIL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$ARG1" == "3" || "$ARG1" == "jn" || "$ARG1" == "jn@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_3_URL"
    TARGET_EMAIL="$ACCOUNT_3_EMAIL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$ARG1" == "4" || "$ARG1" == "dai" || "$ARG1" == "dai@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_4_URL"
    TARGET_EMAIL="$ACCOUNT_4_EMAIL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$ARG1" == "5" || "$ARG1" == "all" || "$ARG1" == "distribute" || "$ARG1" == "round-robin" ]]; then
    ROUND_ROBIN=true
    TARGET_EMAIL="pn & dai (5 workers each = 10 total)"
    TARGET_URL="Distributed across pn & dai"
    NUM_WINDOWS="${NUM_WINDOWS:-10}"
elif [[ -n "${TARGET_URL:-}" && "${TARGET_URL:-}" != "$ACCOUNT_1_URL" ]]; then
    TARGET_EMAIL="Custom URL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [ -t 0 ]; then
    echo "================================================================"
    echo "   CloudflareAuto -- Select Target Referral Account (macOS)"
    echo "================================================================"
    echo "  [1] pn@gmail.com   ->  $ACCOUNT_1_URL  (${WORKERS_PER_LINK} workers)"
    echo "  [2] dai@gmail.com  ->  $ACCOUNT_4_URL  (${WORKERS_PER_LINK} workers)"
    echo "  [3] dd@gmail.com   ->  $ACCOUNT_2_URL  (${WORKERS_PER_LINK} workers)"
    echo "  [4] jn@gmail.com   ->  $ACCOUNT_3_URL  (${WORKERS_PER_LINK} workers)"
    echo "  [5] pn & dai       ->  5 workers each (10 total - Default for macOS)"
    echo "  [6] Custom URL     ->  [Enter your own referral link]"
    echo "================================================================"
    read -r -p "Select option [1-6, Enter for default 5]: " USER_CHOICE
    USER_CHOICE="${USER_CHOICE:-5}"

    case "$USER_CHOICE" in
        1|pn)
            TARGET_URL="$ACCOUNT_1_URL"
            TARGET_EMAIL="$ACCOUNT_1_EMAIL"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        2|dai)
            TARGET_URL="$ACCOUNT_4_URL"
            TARGET_EMAIL="$ACCOUNT_4_EMAIL"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        3|dd)
            TARGET_URL="$ACCOUNT_2_URL"
            TARGET_EMAIL="$ACCOUNT_2_EMAIL"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        4|jn)
            TARGET_URL="$ACCOUNT_3_URL"
            TARGET_EMAIL="$ACCOUNT_3_EMAIL"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        5|all|distribute)
            ROUND_ROBIN=true
            TARGET_EMAIL="pn & dai (5 workers each = 10 total)"
            TARGET_URL="Distributed across pn & dai"
            NUM_WINDOWS="${NUM_WINDOWS:-10}"
            ;;
        6|custom)
            read -r -p "Enter custom referral URL: " CUSTOM_INPUT
            TARGET_URL="${CUSTOM_INPUT:-$ACCOUNT_1_URL}"
            TARGET_EMAIL="Custom Account"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        *)
            ROUND_ROBIN=true
            TARGET_EMAIL="pn & dai (5 workers each = 10 total)"
            TARGET_URL="Distributed across pn & dai"
            NUM_WINDOWS="${NUM_WINDOWS:-10}"
            ;;
    esac
else
    # Non-interactive fallback default: pn & dai distributed (10 workers)
    ROUND_ROBIN=true
    TARGET_EMAIL="pn & dai (5 workers each = 10 total)"
    TARGET_URL="Distributed across pn & dai"
    NUM_WINDOWS="${NUM_WINDOWS:-10}"
fi

# Clean up any old worker scripts and temporary screenshots
rm -rf "$TMPDIR_WORKERS"
rm -rf /tmp/websurfer_screenshots "${TMPDIR:-/tmp}/websurfer_screenshots" 2>/dev/null || true
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

if (( NUM_WINDOWS <= 2 )); then
    COLS=$NUM_WINDOWS
    ROWS=1
elif (( NUM_WINDOWS <= 4 )); then
    COLS=$NUM_WINDOWS
    ROWS=1
elif (( NUM_WINDOWS <= 6 )); then
    COLS=3
    ROWS=2
elif (( NUM_WINDOWS <= 8 )); then
    COLS=4
    ROWS=2
else
    COLS=5
    ROWS=2
fi
MARGIN=5
TITLE_BAR=28

WIN_W=$(( (SCREEN_W - (COLS + 1) * MARGIN) / COLS ))
WIN_H=$(( (SCREEN_H - (ROWS + 1) * MARGIN - TITLE_BAR) / ROWS ))

echo "================================================================"
echo "   CloudflareAuto -- macOS Multi-Terminal Launcher"
echo "================================================================"
echo "  Project : $PROJECT_DIR"
echo "  Python  : $PYTHON"
echo "  Mode    : $MODE (--loop)"
echo "  Workers : $NUM_WINDOWS (${WORKERS_PER_LINK} per refer link, ${COLS}x${ROWS} grid)"
echo "  Screen  : ${SCREEN_W}x${SCREEN_H}  ->  each win ${WIN_W}x${WIN_H}"
if (( DELAY_MAX > 0 )); then
    echo "  Pacing  : ${DELAY_MIN}-${DELAY_MAX}s between runs"
else
    echo "  Pacing  : No cooldown (continuous)"
fi
echo "  Referrer: $REFERRER (Instagram, Telegram, Facebook, YouTube, etc.)"
echo "  Target  : $TARGET_EMAIL"
if [[ "$ROUND_ROBIN" != "true" ]]; then
    echo "  URL     : $TARGET_URL"
fi
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

    NUM=$(printf '%02d' $((i+1)))
    LABEL="Worker-${NUM}"
    WORKER_SCRIPT="$TMPDIR_WORKERS/worker_${NUM}.sh"

    if [[ "$ROUND_ROBIN" == "true" ]]; then
        ACCOUNTS=("$ACCOUNT_1_URL" "$ACCOUNT_4_URL")
        EMAILS=("$ACCOUNT_1_EMAIL" "$ACCOUNT_4_EMAIL")
        IDX=$(( (i / WORKERS_PER_LINK) % ${#ACCOUNTS[@]} ))
        WORKER_URL="${ACCOUNTS[$IDX]}"
        WORKER_ACCOUNT="${EMAILS[$IDX]}"
        ACC_GROUP=$IDX
    else
        WORKER_URL="$TARGET_URL"
        WORKER_ACCOUNT="$TARGET_EMAIL"
        ACC_GROUP=0
    fi

    # Delay is applied per 2 accounts (not every single worker)
    # 2s small offset between window opens so Terminal.app handles sizing cleanly
    BASE_DELAY=$(( ACC_GROUP * 30 ))
    OFFSET=$(( (i % (2 * WORKERS_PER_LINK)) * 2 ))
    DELAY=$(( BASE_DELAY + OFFSET ))

    echo "  [$LABEL]  grid=(${COL},${ROW})  account=${WORKER_ACCOUNT}  delay=${DELAY}s"

    # ── Write a standalone bash script for this worker ───────
    cat > "$WORKER_SCRIPT" <<WORKER_EOF
#!/usr/bin/env bash
export PYTHONUNBUFFERED=1
export WORKER_ID="${LABEL}"

# Set terminal title if running in a window
printf '\033]0;${LABEL}\007' 2>/dev/null || true

cd "${PROJECT_DIR}"

echo ""
echo "============================================="
echo "  ${LABEL} (${WORKER_ACCOUNT})"
echo "  Target URL : ${WORKER_URL}"
echo "  Waiting ${DELAY}s before start"
echo "============================================="
sleep ${DELAY}

echo ""
echo "[${LABEL}] Starting automation loop (mode=${MODE})..."
echo "[${LABEL}] Referral Account: ${WORKER_ACCOUNT}"
echo ""

while true; do
    "${PYTHON}" -u main.py --mode ${MODE} --loop --worker-id "${LABEL}" --target-url "${WORKER_URL}" --delay-min ${DELAY_MIN} --delay-max ${DELAY_MAX} --timeout 120 ${EXTRA_ARGS}
    WORKER_STATUS=\$?
    if [[ \$WORKER_STATUS -eq 42 ]]; then
        echo ""
        echo "[${LABEL}] Rate limited (exit 42) -- waiting for supervisor rotation..."
        sleep 60
    else
        echo ""
        echo "[${LABEL}] Process exited (code \$WORKER_STATUS) -- restarting in 5s..."
        sleep 5
    fi
done
WORKER_EOF

    chmod +x "$WORKER_SCRIPT"

    if [[ "$HEADLESS" == "true" ]]; then
        mkdir -p "$PROJECT_DIR/logs"
        LOG_FILE="$PROJECT_DIR/logs/worker_${NUM}.log"
        nohup bash "$WORKER_SCRIPT" > "$LOG_FILE" 2>&1 &
        WORKER_PID=$!
        echo "  [+] [$LABEL] Started in background (PID: $WORKER_PID) -> logs/worker_${NUM}.log"
    else
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
    fi

done

echo ""
if [[ "$HEADLESS" == "true" ]]; then
    echo "All ${NUM_WINDOWS} workers launched headlessly in the background."
    echo "Logs are streaming to: $PROJECT_DIR/logs/worker_*.log"
else
    echo "All ${NUM_WINDOWS} windows launched and arranged in a ${COLS}x${ROWS} grid."
fi
echo ""
echo "Worker scripts are in: $TMPDIR_WORKERS"
echo ""
echo "To stop ALL workers at once, run:"
echo "  ./launch_multi_mac.sh stop"
echo "  or: pkill -f 'main.py'"
