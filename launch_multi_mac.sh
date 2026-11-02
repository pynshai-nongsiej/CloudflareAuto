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
WORKERS_PER_LINK="${WORKERS_PER_LINK:-3}"
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

# Network mode: default unset (will prompt interactively or default to residential)
NETWORK_MODE="${NETWORK_MODE:-}"
SUPERVISOR_RUN="${SUPERVISOR_RUN:-0}"

# Parse flags and positional arguments
TARGET_ARG=""
for arg in "$@"; do
    if [[ "$arg" == "--headless" ]]; then
        HEADLESS="true"
    elif [[ "$arg" == "--headed" || "$arg" == "--gui" || "$arg" == "--windows" ]]; then
        HEADLESS="false"
    elif [[ "$arg" == "--browser-headed" || "$arg" == "--headed-browser" || "$arg" == "--show-browser" ]]; then
        BROWSER_HEADED="true"
    elif [[ "$arg" == "--residential" || "$arg" == "--proxy" ]]; then
        NETWORK_MODE="residential"
    elif [[ "$arg" == "--vpn" || "$arg" == "--nord" || "$arg" == "--nordvpn" ]]; then
        NETWORK_MODE="vpn"
    elif [[ "$arg" == "--standalone" || "$arg" == "--direct-vpn" || "$arg" == "--direct" ]]; then
        NETWORK_MODE="standalone"
    elif [[ "$arg" == "--scatter" || "$arg" == "--round-robin" || "$arg" == "--distribute" ]]; then
        TARGET_ARG="5"
    elif [[ "$arg" != "stop" && "$arg" != -* && -z "$TARGET_ARG" ]]; then
        TARGET_ARG="$arg"
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
if [[ "${1:-}" == "stop" || "${2:-}" == "stop" ]]; then
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

# ── Network Mode Selection ───────────────────────────────────
if [[ -z "$NETWORK_MODE" && "$SUPERVISOR_RUN" != "1" ]]; then
    if [ -t 0 ]; then
        echo "================================================================"
        echo "   CloudflareAuto -- Select Network Engine (macOS)"
        echo "================================================================"
        echo "  [1] Residential Proxy (DataImpulse) [Default]"
        echo "      • Dedicated rotating residential IP per worker/run"
        echo "      • Instant skip (<1s) on OTP maintenance (no waiting)"
        echo "      • Continuous auto-cleaning unlimited loop"
        echo "      • No device VPN disconnects or OS routing changes"
        echo ""
        echo "  [2] NordVPN Auto-Rotator (OpenVPN Supervisor)"
        echo "      • Full-device VPN tunnel across 7,100+ global servers"
        echo "      • 3x Change Email retry on OTP maintenance"
        echo "      • Live Rich dashboard & server auto-rotation on rate limit"
        echo ""
        echo "  [3] NordVPN Standalone (No Proxy, Direct Device Tunnel)"
        echo "      • Runs on your current VPN connection without supervisor"
        echo "      • 3x Change Email retry on OTP maintenance"
        echo "================================================================"
        read -r -p "Select network option [1-3, Enter for default 1]: " NET_CHOICE
        NET_CHOICE="${NET_CHOICE:-1}"
        case "$NET_CHOICE" in
            1|res|residential|proxy)
                NETWORK_MODE="residential"
                ;;
            2|vpn|nord|nordvpn|supervisor)
                NETWORK_MODE="vpn"
                ;;
            3|direct|standalone)
                NETWORK_MODE="standalone"
                ;;
            *)
                NETWORK_MODE="residential"
                ;;
        esac
    else
        NETWORK_MODE="residential"
    fi
fi

# If NordVPN supervisor is requested and not already under supervisor, hand off
if [[ "$NETWORK_MODE" == "vpn" && "$SUPERVISOR_RUN" != "1" ]]; then
    echo ""
    echo "================================================================"
    echo "  🚀 Starting NordVPN Auto-Rotating Supervisor for macOS..."
    echo "================================================================"
    echo "  • OpenVPN connection management"
    echo "  • Automatic location rotation on rate limit (exit 42)"
    echo "  • 3x Change Email retry on OTP maintenance"
    echo "  • Real-time Rich dashboard"
    echo "================================================================"
    echo ""
    exec "$PROJECT_DIR/run_mac_auto_rotate.sh" "$@"
fi

# ── Account Selection ────────────────────────────────────────
ROUND_ROBIN=false
TARGET_URL=""
TARGET_EMAIL=""

# Check if passed as argument
if [[ "$TARGET_ARG" =~ ^https?:// ]]; then
    TARGET_URL="$TARGET_ARG"
    TARGET_EMAIL="Custom Account"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$TARGET_ARG" == "1" || "$TARGET_ARG" == "pn" || "$TARGET_ARG" == "pn@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_1_URL"
    TARGET_EMAIL="$ACCOUNT_1_EMAIL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$TARGET_ARG" == "2" || "$TARGET_ARG" == "dai" || "$TARGET_ARG" == "dai@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_4_URL"
    TARGET_EMAIL="$ACCOUNT_4_EMAIL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$TARGET_ARG" == "3" || "$TARGET_ARG" == "dd" || "$TARGET_ARG" == "dd@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_2_URL"
    TARGET_EMAIL="$ACCOUNT_2_EMAIL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$TARGET_ARG" == "4" || "$TARGET_ARG" == "jn" || "$TARGET_ARG" == "jn@gmail.com" ]]; then
    TARGET_URL="$ACCOUNT_3_URL"
    TARGET_EMAIL="$ACCOUNT_3_EMAIL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [[ "$TARGET_ARG" == "5" || "$TARGET_ARG" == "all" || "$TARGET_ARG" == "distribute" || "$TARGET_ARG" == "both" || "$TARGET_ARG" == "round-robin" ]]; then
    ROUND_ROBIN=true
    TARGET_EMAIL="pn & dai (3 workers each = 6 total)"
    TARGET_URL="Distributed across pn & dai"
    NUM_WINDOWS="${NUM_WINDOWS:-6}"
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
    echo "  [5] pn & dai       ->  3 workers each (6 total - Default for macOS)"
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
        5|all|distribute|both)
            ROUND_ROBIN=true
            TARGET_EMAIL="pn & dai (3 workers each = 6 total)"
            TARGET_URL="Distributed across pn & dai"
            NUM_WINDOWS="${NUM_WINDOWS:-6}"
            ;;
        6|custom)
            read -r -p "Enter custom referral URL: " CUSTOM_INPUT
            TARGET_URL="${CUSTOM_INPUT:-$ACCOUNT_1_URL}"
            TARGET_EMAIL="Custom Account"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        *)
            ROUND_ROBIN=true
            TARGET_EMAIL="pn & dai (3 workers each = 6 total)"
            TARGET_URL="Distributed across pn & dai"
            NUM_WINDOWS="${NUM_WINDOWS:-6}"
            ;;
    esac
else
    # Non-interactive fallback default: pn & dai distributed (6 workers)
    ROUND_ROBIN=true
    TARGET_EMAIL="pn & dai (3 workers each = 6 total)"
    TARGET_URL="Distributed across pn & dai"
    NUM_WINDOWS="${NUM_WINDOWS:-6}"
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
    COLS=2
    ROWS=2
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
echo "  Network : $([[ "$NETWORK_MODE" == "residential" ]] && echo "Residential Proxy (DataImpulse - Dynamic sticky IP per run)" || echo "NordVPN / Direct (Host Network)")"
echo "  Workers : $NUM_WINDOWS (${WORKERS_PER_LINK} per refer link, ${COLS}x${ROWS} grid)"
echo "  Screen  : ${SCREEN_W}x${SCREEN_H}  ->  each win ${WIN_W}x${WIN_H}"
if (( DELAY_MAX > 0 )); then
    echo "  Pacing  : ${DELAY_MIN}-${DELAY_MAX}s between runs"
elif [[ "$NETWORK_MODE" == "residential" ]]; then
    echo "  Pacing  : 1 minute (60s) cooldown after each run"
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

    echo "  [$LABEL]  grid=(${COL},${ROW})  account=${WORKER_ACCOUNT}"

    # ── Write a standalone bash script for this worker ───────
    if [[ "$NETWORK_MODE" == "vpn" ]]; then
        cat > "$WORKER_SCRIPT" <<WORKER_EOF
#!/usr/bin/env bash
export PYTHONUNBUFFERED=1
export WORKER_ID="${LABEL}"
export NETWORK_MODE="vpn"
export USE_PROXY="false"

# Set terminal title if running in a window
printf '\033]0;${LABEL}\007' 2>/dev/null || true

cd "${PROJECT_DIR}"

echo ""
echo "============================================="
echo "  ${LABEL} (${WORKER_ACCOUNT}) [NordVPN Mode]"
echo "  Target URL : ${WORKER_URL}"
echo "  Network    : NordVPN Host Tunnel (No Proxy)"
echo "  OTP Maint. : 3x Change Email Retry Enabled"
echo "============================================="
echo ""
echo "[${LABEL}] Starting 1 registration via NordVPN..."
echo ""

"${PYTHON}" -u main.py --mode ${MODE} --loop --count 1 --worker-id "${LABEL}" --target-url "${WORKER_URL}" --delay-min 0 --delay-max 0 --timeout 120 --no-proxy ${EXTRA_ARGS}
WORKER_STATUS=\$?

if [[ \$WORKER_STATUS -eq 0 ]]; then
    echo ""
    echo "[${LABEL}] ✅ Registration completed successfully on NordVPN. Done."
    exit 0
elif [[ \$WORKER_STATUS -eq 42 ]]; then
    echo ""
    echo "[${LABEL}] ⚠️ Rate limited (exit 42) -- finishing session for VPN rotation."
    exit 42
else
    echo ""
    echo "[${LABEL}] ⏭️ Process finished with code \$WORKER_STATUS."
    exit \$WORKER_STATUS
fi
WORKER_EOF

    elif [[ "$NETWORK_MODE" == "standalone" ]]; then
        cat > "$WORKER_SCRIPT" <<WORKER_EOF
#!/usr/bin/env bash
export PYTHONUNBUFFERED=1
export WORKER_ID="${LABEL}"
export NETWORK_MODE="vpn"
export USE_PROXY="false"

printf '\033]0;${LABEL}\007' 2>/dev/null || true
cd "${PROJECT_DIR}"

RUN_COUNT=0
SUCCESS_COUNT=0

while true; do
    RUN_COUNT=\$((RUN_COUNT + 1))

    clear 2>/dev/null || printf "\033[2J\033[3J\033[H"

    echo "============================================="
    echo "  ${LABEL} (${WORKER_ACCOUNT}) [NordVPN Standalone]"
    echo "  Target URL : ${WORKER_URL}"
    echo "  Total Runs : \$RUN_COUNT | ✅ Successes: \$SUCCESS_COUNT"
    echo "  OTP Maint. : 3x Change Email Retry Enabled"
    echo "============================================="
    echo ""
    echo "[${LABEL}] Starting registration #\$RUN_COUNT on device network (no proxy)..."
    echo ""

    "${PYTHON}" -u main.py --mode ${MODE} --loop --count 1 --worker-id "${LABEL}" --target-url "${WORKER_URL}" --delay-min 0 --delay-max 0 --timeout 120 --no-proxy ${EXTRA_ARGS}
    WORKER_STATUS=\$?

    if [[ \$WORKER_STATUS -eq 0 ]]; then
        SUCCESS_COUNT=\$((SUCCESS_COUNT + 1))
        echo ""
        echo "[${LABEL}] ✅ Run #\$RUN_COUNT successful! Restarting in 2s..."
    elif [[ \$WORKER_STATUS -eq 42 ]]; then
        echo ""
        echo "[${LABEL}] ⚠️ Rate limited (exit 42). Cooldown before retry..."
        sleep 60
    else
        echo ""
        echo "[${LABEL}] ⏭️ Run #\$RUN_COUNT finished (code \$WORKER_STATUS). Restarting in 2s..."
    fi

    rm -rf /tmp/playwright* /tmp/.org.chromium* /tmp/chromium* /tmp/websurfer_screenshots* 2>/dev/null || true
    sleep 1
done
WORKER_EOF

    else
        # Default: Residential Proxy Mode
        cat > "$WORKER_SCRIPT" <<WORKER_EOF
#!/usr/bin/env bash
export PYTHONUNBUFFERED=1
export WORKER_ID="${LABEL}"
export NETWORK_MODE="residential"
export USE_PROXY="true"

# Set terminal title if running in a window
printf '\033]0;${LABEL}\007' 2>/dev/null || true

cd "${PROJECT_DIR}"

RUN_COUNT=0
SUCCESS_COUNT=0

while true; do
    RUN_COUNT=\$((RUN_COUNT + 1))

    # Clear terminal screen and scrollback buffer to prevent memory bloat
    clear 2>/dev/null || printf "\033[2J\033[3J\033[H"

    echo "============================================="
    echo "  ${LABEL} (${WORKER_ACCOUNT}) [Residential Proxy Mode]"
    echo "  Target URL : ${WORKER_URL}"
    echo "  Total Runs : \$RUN_COUNT | ✅ Successes: \$SUCCESS_COUNT"
    echo "============================================="
    echo ""
    echo "[${LABEL}] Starting registration #\$RUN_COUNT on dedicated residential IP..."
    echo ""

    # Execute exactly 1 registration attempt per Python process, terminating directly on finish
    "${PYTHON}" -u main.py --mode ${MODE} --loop --count 1 --worker-id "${LABEL}" --target-url "${WORKER_URL}" --delay-min 0 --delay-max 0 --timeout 60 ${EXTRA_ARGS}
    WORKER_STATUS=\$?

    if [[ \$WORKER_STATUS -eq 0 ]]; then
        SUCCESS_COUNT=\$((SUCCESS_COUNT + 1))
        echo ""
        echo "[${LABEL}] ✅ Run #\$RUN_COUNT successful!"
    elif [[ \$WORKER_STATUS -eq 42 ]]; then
        echo ""
        echo "[${LABEL}] ⚠️ Rate limited (exit 42)."
    else
        echo ""
        echo "[${LABEL}] ⏭️ Run #\$RUN_COUNT finished (code \$WORKER_STATUS)."
    fi

    # Clean up temporary browser data, screenshots, and orphan chromium temp data
    rm -rf /tmp/playwright* /tmp/.org.chromium* /tmp/chromium* /tmp/websurfer_screenshots* 2>/dev/null || true

    echo ""
    echo "[${LABEL}] ⏳ Cooldown: 1 minute (60s) before next residential proxy registration..."
    for (( sec=60; sec>0; sec-- )); do
        printf "\r[${LABEL}] ⏳ Cooldown: %2ds remaining before starting run #\$((RUN_COUNT + 1))..." "\$sec"
        sleep 1
    done
    echo ""
done
WORKER_EOF
    fi

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
