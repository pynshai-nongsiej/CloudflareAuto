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
NUM_WINDOWS="${NUM_WINDOWS:-5}"
MODE="${MODE:-direct}"
REFERRER="${REFERRER:-none}"
DELAY_MIN="${DELAY_MIN:-60}"
DELAY_MAX="${DELAY_MAX:-120}"
TMPDIR_WORKERS="/tmp/cloudflare_auto_workers"

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
    rm -rf "$TMPDIR_WORKERS"
    rm -rf /tmp/websurfer_screenshots "${TMPDIR:-/tmp}/websurfer_screenshots" 2>/dev/null || true
    echo "  [+] All CloudflareAuto workers stopped."
    echo "================================================================"
    exit 0
fi

# ── Account Selection ────────────────────────────────────────
TARGET_URL=""
TARGET_EMAIL=""

# Check if passed as first argument
ARG1="${1:-}"
if [[ "$ARG1" =~ ^https?:// ]]; then
    TARGET_URL="$ARG1"
    TARGET_EMAIL="Custom Account"
elif [[ "$ARG1" == "1" || "$ARG1" == "pn" || "$ARG1" == "pn@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_1_URL"
    TARGET_EMAIL="$ACCOUNT_1_EMAIL"
elif [[ "$ARG1" == "2" || "$ARG1" == "dd" || "$ARG1" == "dd@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_2_URL"
    TARGET_EMAIL="$ACCOUNT_2_EMAIL"
elif [[ "$ARG1" == "3" || "$ARG1" == "jn" || "$ARG1" == "jn@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_3_URL"
    TARGET_EMAIL="$ACCOUNT_3_EMAIL"
elif [[ "$ARG1" == "4" || "$ARG1" == "dai" || "$ARG1" == "dai@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_4_URL"
    TARGET_EMAIL="$ACCOUNT_4_EMAIL"
elif [[ -n "${TARGET_URL:-}" && "${TARGET_URL:-}" != "$ACCOUNT_1_URL" ]]; then
    TARGET_EMAIL="Custom URL"
elif [ -t 0 ]; then
    echo "================================================================"
    echo "   CloudflareAuto -- Select Target Referral Account"
    echo "================================================================"
    echo "  [1] pn@gmail.com   ->  $ACCOUNT_1_URL  (Default)"
    echo "  [2] dd@gmail.com   ->  $ACCOUNT_2_URL"
    echo "  [3] jn@gmail.com   ->  $ACCOUNT_3_URL"
    echo "  [4] dai@gmail.com  ->  $ACCOUNT_4_URL"
    echo "  [5] Custom URL     ->  [Enter your own referral link]"
    echo "================================================================"
    read -r -p "Select option [1-5, Enter for default 1]: " USER_CHOICE
    USER_CHOICE="${USER_CHOICE:-1}"

    case "$USER_CHOICE" in
        2|dd)
            TARGET_URL="$ACCOUNT_2_URL"
            TARGET_EMAIL="$ACCOUNT_2_EMAIL"
            ;;
        3|jn)
            TARGET_URL="$ACCOUNT_3_URL"
            TARGET_EMAIL="$ACCOUNT_3_EMAIL"
            ;;
        4|dai)
            TARGET_URL="$ACCOUNT_4_URL"
            TARGET_EMAIL="$ACCOUNT_4_EMAIL"
            ;;
        5|custom)
            read -r -p "Enter custom referral URL: " CUSTOM_INPUT
            TARGET_URL="${CUSTOM_INPUT:-$ACCOUNT_1_URL}"
            TARGET_EMAIL="Custom Account"
            ;;
        *)
            TARGET_URL="$ACCOUNT_1_URL"
            TARGET_EMAIL="$ACCOUNT_1_EMAIL"
            ;;
    esac
else
    # Non-interactive fallback default
    TARGET_URL="${TARGET_URL:-$ACCOUNT_1_URL}"
    TARGET_EMAIL="$ACCOUNT_1_EMAIL"
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

if (( NUM_WINDOWS <= 3 )); then
    COLS=$NUM_WINDOWS
    ROWS=1
elif (( NUM_WINDOWS <= 6 )); then
    COLS=3
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
echo "  Windows : $NUM_WINDOWS  (${COLS}x${ROWS} grid)"
echo "  Screen  : ${SCREEN_W}x${SCREEN_H}  ->  each win ${WIN_W}x${WIN_H}"
echo "  Pacing  : ${DELAY_MIN}-${DELAY_MAX}s (1-2 min) between runs"
echo "  Referrer: $REFERRER (Instagram, Telegram, Facebook, YouTube, etc.)"
echo "  Target  : $TARGET_EMAIL"
echo "  URL     : $TARGET_URL"
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

    # Stagger launch start times (~30s interval between workers so they don't hammer simultaneously)
    # Worker 1: ~10s, Worker 2: ~40s, Worker 3: ~70s, Worker 4: ~100s, Worker 5: ~130s
    BASE_DELAY=$(( i * 30 ))
    DELAY=$(( BASE_DELAY + $(rand_between 5 15) ))
    NUM=$(printf '%02d' $((i+1)))
    LABEL="Worker-${NUM}"
    WORKER_SCRIPT="$TMPDIR_WORKERS/worker_${NUM}.sh"

    WORKER_URL="$TARGET_URL"
    WORKER_ACCOUNT="$TARGET_EMAIL"

    echo "  [$LABEL]  grid=(${COL},${ROW})  account=${WORKER_ACCOUNT}  delay=${DELAY}s"

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
    "${PYTHON}" main.py --mode ${MODE} --loop --target-url "${WORKER_URL}" --delay-min ${DELAY_MIN} --delay-max ${DELAY_MAX}
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
