#!/usr/bin/env bash
# ============================================================
#  launch_multi_linux.sh -- Launch CloudflareAuto sessions on Linux / Ubuntu
# ============================================================
#
#  Features:
#    - Supports Ubuntu Desktop (GNOME Terminal, xterm, Terminator, etc.)
#    - Supports Ubuntu Server / SSH / Headless via tmux (tiled grid)
#    - Supports Background worker mode with real-time log files
#    - Staggered startup delays (~30s apart) to avoid rate-limiting
#
#  Usage:
#    chmod +x launch_multi_linux.sh
#    ./launch_multi_linux.sh            # Launch 5 workers (auto-detect GUI / tmux / bg)
#    ./launch_multi_linux.sh stop       # Stop all running workers
#
#  Optional environment variables:
#    NUM_WINDOWS=5         Number of workers/terminals (default: 5)
#    MODE=direct           main.py mode: direct or browser-use (default: direct)
#    TARGET_URL=...        Custom referral/target URL
#    METHOD=auto           Launch method: auto | gui | tmux | bg (default: auto)
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKERS_PER_LINK="${WORKERS_PER_LINK:-3}"
NUM_WINDOWS="${NUM_WINDOWS:-}"
MODE="${MODE:-direct}"
DELAY_MIN="${DELAY_MIN:-0}"
DELAY_MAX="${DELAY_MAX:-0}"
METHOD="${METHOD:-auto}"
EXTRA_ARGS="${EXTRA_ARGS:-}"
TMPDIR_WORKERS="/tmp/cloudflare_auto_workers"
TMUX_SESSION="cloudflare-auto"

# Terminal window mode: default headed (visible terminal emulator windows)
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
    echo "  Stopping all CloudflareAuto workers on Linux..."
    echo "================================================================"
    
    # Kill tmux session if active
    if command -v tmux &>/dev/null && tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
        echo "  [+] Stopped tmux session: $TMUX_SESSION"
    fi

    # Kill background PIDs if recorded
    if [[ -f "$TMPDIR_WORKERS/pids.txt" ]]; then
        while read -r pid; do
            if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
            fi
        done < "$TMPDIR_WORKERS/pids.txt"
        rm -f "$TMPDIR_WORKERS/pids.txt"
        echo "  [+] Cleaned up background processes."
    fi

    # Terminate any remaining main.py instances
    pkill -f 'main.py' 2>/dev/null || true
    pkill -f 'worker_.*\.sh' 2>/dev/null || true
    rm -rf "$TMPDIR_WORKERS"
    rm -f /tmp/cloudflare_rate_limit_triggered.flag
    rm -rf /tmp/websurfer_screenshots "${TMPDIR:-/tmp}/websurfer_screenshots" 2>/dev/null || true
    echo "  [+] All workers stopped."
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
    TARGET_EMAIL="dd & jn (3 workers each = 6 total)"
    TARGET_URL="Distributed across dd & jn"
    NUM_WINDOWS="${NUM_WINDOWS:-6}"
elif [[ -n "${TARGET_URL:-}" && "${TARGET_URL:-}" != "$ACCOUNT_1_URL" ]]; then
    TARGET_EMAIL="Custom URL"
    NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
elif [ -t 0 ]; then
    echo "================================================================"
    echo "   CloudflareAuto -- Select Target Referral Account (Linux)"
    echo "================================================================"
    echo "  [1] dd@gmail.com   ->  $ACCOUNT_2_URL  (${WORKERS_PER_LINK} workers)"
    echo "  [2] jn@gmail.com   ->  $ACCOUNT_3_URL  (${WORKERS_PER_LINK} workers)"
    echo "  [3] pn@gmail.com   ->  $ACCOUNT_1_URL  (${WORKERS_PER_LINK} workers)"
    echo "  [4] dai@gmail.com  ->  $ACCOUNT_4_URL  (${WORKERS_PER_LINK} workers)"
    echo "  [5] dd & jn        ->  3 workers each (6 total - Default for Linux)"
    echo "  [6] Custom URL     ->  [Enter your own referral link]"
    echo "================================================================"
    read -r -p "Select option [1-6, Enter for default 5]: " USER_CHOICE
    USER_CHOICE="${USER_CHOICE:-5}"

    case "$USER_CHOICE" in
        1|dd)
            TARGET_URL="$ACCOUNT_2_URL"
            TARGET_EMAIL="$ACCOUNT_2_EMAIL"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        2|jn)
            TARGET_URL="$ACCOUNT_3_URL"
            TARGET_EMAIL="$ACCOUNT_3_EMAIL"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        3|pn)
            TARGET_URL="$ACCOUNT_1_URL"
            TARGET_EMAIL="$ACCOUNT_1_EMAIL"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        4|dai)
            TARGET_URL="$ACCOUNT_4_URL"
            TARGET_EMAIL="$ACCOUNT_4_EMAIL"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        5|all|distribute)
            ROUND_ROBIN=true
            TARGET_EMAIL="dd & jn (3 workers each = 6 total)"
            TARGET_URL="Distributed across dd & jn"
            NUM_WINDOWS="${NUM_WINDOWS:-6}"
            ;;
        6|custom)
            read -r -p "Enter custom referral URL: " CUSTOM_INPUT
            TARGET_URL="${CUSTOM_INPUT:-$ACCOUNT_2_URL}"
            TARGET_EMAIL="Custom Account"
            NUM_WINDOWS="${NUM_WINDOWS:-$WORKERS_PER_LINK}"
            ;;
        *)
            ROUND_ROBIN=true
            TARGET_EMAIL="dd & jn (3 workers each = 6 total)"
            TARGET_URL="Distributed across dd & jn"
            NUM_WINDOWS="${NUM_WINDOWS:-6}"
            ;;
    esac
else
    # Non-interactive fallback default: dd & jn distributed (6 workers)
    ROUND_ROBIN=true
    TARGET_EMAIL="dd & jn (3 workers each = 6 total)"
    TARGET_URL="Distributed across dd & jn"
    NUM_WINDOWS="${NUM_WINDOWS:-6}"
fi

# ── Clean up old worker directory and screenshots ────────────
rm -rf "$TMPDIR_WORKERS"
rm -rf /tmp/websurfer_screenshots "${TMPDIR:-/tmp}/websurfer_screenshots" 2>/dev/null || true
mkdir -p "$TMPDIR_WORKERS"

# ── Virtual environment detection ───────────────────────────
PYTHON="python3"
if [[ -f "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [[ -f "$PROJECT_DIR/venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"
fi

# ── Helper: Random integer in range [min, max] ───────────────
rand_between() {
    echo $(( RANDOM % ($2 - $1 + 1) + $1 ))
}

# ── Helper: Detect screen resolution ─────────────────────────
get_screen_geometry() {
    local w="" h="" res=""
    if command -v xdotool &>/dev/null; then
        read -r w h < <(xdotool getdisplaygeometry 2>/dev/null || true)
    fi
    if [[ -z "$w" || -z "$h" ]] && command -v xrandr &>/dev/null; then
        res=$(xrandr 2>/dev/null | grep '\*' | awk '{print $1}' | head -n1 || true)
        if [[ -n "$res" && "$res" =~ ^([0-9]+)x([0-9]+)$ ]]; then
            w="${BASH_REMATCH[1]}"
            h="${BASH_REMATCH[2]}"
        fi
    fi
    if [[ -z "$w" || -z "$h" ]] && command -v xdpyinfo &>/dev/null; then
        res=$(xdpyinfo 2>/dev/null | awk '/dimensions:/ {print $2}' || true)
        if [[ -n "$res" && "$res" =~ ^([0-9]+)x([0-9]+)$ ]]; then
            w="${BASH_REMATCH[1]}"
            h="${BASH_REMATCH[2]}"
        fi
    fi
    echo "${w:-1920} ${h:-1080}"
}

# ── Helper: Arrange / tile GUI terminal window ───────────────
arrange_window() {
    local label="$1" x="$2" y="$3" w="$4" h="$5"
    (
        for (( attempt=1; attempt<=15; attempt++ )); do
            if command -v wmctrl &>/dev/null; then
                if wmctrl -l 2>/dev/null | grep -F -q "$label"; then
                    wmctrl -r "$label" -e "0,$x,$y,$w,$h" 2>/dev/null || true
                    exit 0
                fi
            elif command -v xdotool &>/dev/null; then
                local wid=""
                wid=$(xdotool search --onlyvisible --name "$label" 2>/dev/null | tail -n1 || true)
                if [[ -n "$wid" ]]; then
                    xdotool windowmove "$wid" "$x" "$y" 2>/dev/null || true
                    xdotool windowsize "$wid" "$w" "$h" 2>/dev/null || true
                    exit 0
                fi
            else
                exit 0
            fi
            sleep 0.2
        done
    ) &
}

# ── Helper: Detect available GUI terminal emulator ───────────
detect_gui_terminal() {
    if command -v gnome-terminal &>/dev/null; then
        echo "gnome-terminal"
    elif command -v x-terminal-emulator &>/dev/null; then
        echo "x-terminal-emulator"
    elif command -v xfce4-terminal &>/dev/null; then
        echo "xfce4-terminal"
    elif command -v terminator &>/dev/null; then
        echo "terminator"
    elif command -v tilix &>/dev/null; then
        echo "tilix"
    elif command -v konsole &>/dev/null; then
        echo "konsole"
    elif command -v alacritty &>/dev/null; then
        echo "alacritty"
    elif command -v kitty &>/dev/null; then
        echo "kitty"
    elif command -v xterm &>/dev/null; then
        echo "xterm"
    else
        echo "none"
    fi
}

# ── Determine Execution Method ───────────────────────────────
SELECTED_METHOD="$METHOD"
GUI_TERMINAL="none"

if [[ "$HEADLESS" == "true" ]]; then
    if [[ "$SELECTED_METHOD" == "auto" ]]; then
        if command -v tmux &>/dev/null; then
            SELECTED_METHOD="tmux"
        else
            SELECTED_METHOD="bg"
        fi
    fi
elif [[ "$SELECTED_METHOD" == "auto" ]]; then
    # Auto-detect local display if unset (e.g. running via SSH on a desktop machine)
    if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
        if [[ -S /tmp/.X11-unix/X0 ]]; then
            export DISPLAY=":0"
        elif [[ -S /tmp/.X11-unix/X1 ]]; then
            export DISPLAY=":1"
        fi
    fi
    if [[ -z "${XAUTHORITY:-}" && -f "$HOME/.Xauthority" ]]; then
        export XAUTHORITY="$HOME/.Xauthority"
    fi

    HAS_DISPLAY=false
    if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
        HAS_DISPLAY=true
        GUI_TERMINAL=$(detect_gui_terminal)
    fi

    if [[ "$HAS_DISPLAY" == true && "$GUI_TERMINAL" != "none" ]]; then
        SELECTED_METHOD="gui"
    elif command -v tmux &>/dev/null; then
        SELECTED_METHOD="tmux"
    else
        SELECTED_METHOD="bg"
    fi
elif [[ "$SELECTED_METHOD" == "gui" ]]; then
    GUI_TERMINAL=$(detect_gui_terminal)
    if [[ "$GUI_TERMINAL" == "none" ]]; then
        echo "[!] No GUI terminal emulator detected. Falling back to tmux/background."
        if command -v tmux &>/dev/null; then
            SELECTED_METHOD="tmux"
        else
            SELECTED_METHOD="bg"
        fi
    fi
fi

# ── Grid Geometry Calculation ────────────────────────────────
read -r SCREEN_W SCREEN_H < <(get_screen_geometry)
SCREEN_W="${SCREEN_W:-1920}"
SCREEN_H="${SCREEN_H:-1080}"

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
    ROWS=$(( (NUM_WINDOWS + COLS - 1) / COLS ))
fi

MARGIN=8
TASKBAR_OFFSET=32

USABLE_W=$(( SCREEN_W - (COLS + 1) * MARGIN ))
USABLE_H=$(( SCREEN_H - TASKBAR_OFFSET - (ROWS + 1) * MARGIN ))

WIN_W=$(( USABLE_W / COLS ))
WIN_H=$(( USABLE_H / ROWS ))

# Character cell approximations for terminal geometry (standard ~9x18px)
CHAR_W=9
CHAR_H=18
COLS_CHAR=$(( (WIN_W - 20) / CHAR_W ))
if (( COLS_CHAR < 30 )); then COLS_CHAR=30; fi
ROWS_CHAR=$(( (WIN_H - 40) / CHAR_H ))
if (( ROWS_CHAR < 10 )); then ROWS_CHAR=10; fi

# ── Banner ───────────────────────────────────────────────────
echo "================================================================"
echo "   CloudflareAuto -- Linux / Ubuntu Multi-Session Launcher"
echo "================================================================"
echo "  Project   : $PROJECT_DIR"
echo "  Python    : $PYTHON"
echo "  Mode      : $MODE (--loop)"
echo "  Workers   : $NUM_WINDOWS (arranged in ${COLS}x${ROWS} grid)"
if [[ "$SELECTED_METHOD" == "gui" ]]; then
echo "  Screen    : ${SCREEN_W}x${SCREEN_H}  ->  each win ${WIN_W}x${WIN_H}"
fi
if (( DELAY_MAX > 0 )); then
    echo "  Pacing    : ${DELAY_MIN}-${DELAY_MAX}s between runs"
else
    echo "  Pacing    : No cooldown (continuous)"
fi
echo "  Target    : $TARGET_EMAIL"
if [[ "$ROUND_ROBIN" != "true" ]]; then
    echo "  URL       : $TARGET_URL"
fi
echo "  Backend   : $SELECTED_METHOD $([[ "$SELECTED_METHOD" == "gui" ]] && echo "($GUI_TERMINAL)" || true)"
echo "  Browser   : $([[ "$BROWSER_HEADED" == "true" ]] && echo "Headed (UI visible)" || echo "Headless")"
echo "================================================================"
echo ""

# ── Generate Worker Scripts ──────────────────────────────────
for (( i=0; i<NUM_WINDOWS; i++ )); do
    NUM=$(printf '%02d' $((i+1)))
    LABEL="Worker-${NUM}"
    WORKER_SCRIPT="$TMPDIR_WORKERS/worker_${NUM}.sh"

    COL=$(( i % COLS ))
    ROW=$(( i / COLS ))
    X=$(( MARGIN + COL * (WIN_W + MARGIN) ))
    Y=$(( TASKBAR_OFFSET + MARGIN + ROW * (WIN_H + MARGIN) ))

    if [[ "$ROUND_ROBIN" == "true" ]]; then
        ACCOUNTS=("$ACCOUNT_2_URL" "$ACCOUNT_3_URL")
        EMAILS=("$ACCOUNT_2_EMAIL" "$ACCOUNT_3_EMAIL")
        IDX=$(( (i / 3) % ${#ACCOUNTS[@]} ))
        WORKER_URL="${ACCOUNTS[$IDX]}"
        WORKER_ACCOUNT="${EMAILS[$IDX]}"
    else
        WORKER_URL="$TARGET_URL"
        WORKER_ACCOUNT="$TARGET_EMAIL"
    fi

    cat > "$WORKER_SCRIPT" <<WORKER_EOF
#!/usr/bin/env bash
printf '\033]0;${LABEL}\007'
cd "${PROJECT_DIR}"

echo ""
echo "============================================="
echo "  ${LABEL} (${WORKER_ACCOUNT})"
echo "  Target URL : ${WORKER_URL}"
echo "============================================="

echo ""
echo "[${LABEL}] Starting automation loop (mode=${MODE})..."
echo "[${LABEL}] Referral Account: ${WORKER_ACCOUNT}"
echo ""

while true; do
    "${PYTHON}" main.py --mode ${MODE} --loop --target-url "${WORKER_URL}" --delay-min ${DELAY_MIN} --delay-max ${DELAY_MAX} --worker-id "${LABEL}" --timeout 120 ${EXTRA_ARGS}
    EXIT_CODE=\$?
    if [[ \$EXIT_CODE -eq 42 ]]; then
        echo "[${LABEL}] Rate limit exit triggered (code 42) -- finishing batch for VPN rotation."
        exit 42
    fi
    echo ""
    echo "[${LABEL}] Process exited -- restarting in 5s..."
    sleep 5
done
WORKER_EOF

    chmod +x "$WORKER_SCRIPT"
    echo "  [$LABEL]  grid=(${COL},${ROW})  account=${WORKER_ACCOUNT}"
done

echo ""

# ── Launch Execution ─────────────────────────────────────────

if [[ "$SELECTED_METHOD" == "gui" ]]; then
    echo "[*] Launching ${NUM_WINDOWS} terminal windows arranged in a ${COLS}x${ROWS} grid using ${GUI_TERMINAL}..."

    if ! command -v wmctrl &>/dev/null && ! command -v xdotool &>/dev/null; then
        echo "  ℹ️  Tip: For precise pixel window snapping on GNOME/Ubuntu, install wmctrl:"
        echo "     sudo apt-get install -y wmctrl"
    fi

    for (( i=0; i<NUM_WINDOWS; i++ )); do
        NUM=$(printf '%02d' $((i+1)))
        LABEL="Worker-${NUM}"
        WORKER_SCRIPT="$TMPDIR_WORKERS/worker_${NUM}.sh"

        COL=$(( i % COLS ))
        ROW=$(( i / COLS ))
        X=$(( MARGIN + COL * (WIN_W + MARGIN) ))
        Y=$(( TASKBAR_OFFSET + MARGIN + ROW * (WIN_H + MARGIN) ))

        case "$GUI_TERMINAL" in
            gnome-terminal)
                gnome-terminal --title="${LABEL}" --geometry="${COLS_CHAR}x${ROWS_CHAR}+${X}+${Y}" -- bash "${WORKER_SCRIPT}" &
                ;;
            xfce4-terminal)
                xfce4-terminal --title="${LABEL}" --geometry="${COLS_CHAR}x${ROWS_CHAR}+${X}+${Y}" -e "bash ${WORKER_SCRIPT}" &
                ;;
            terminator)
                terminator -T "${LABEL}" --geometry="${WIN_W}x${WIN_H}+${X}+${Y}" -e "bash ${WORKER_SCRIPT}" &
                ;;
            tilix)
                tilix -t "${LABEL}" --geometry="${COLS_CHAR}x${ROWS_CHAR}+${X}+${Y}" -e "bash ${WORKER_SCRIPT}" &
                ;;
            konsole)
                konsole -p tabtitle="${LABEL}" --geometry="${WIN_W}x${WIN_H}+${X}+${Y}" -e bash "${WORKER_SCRIPT}" &
                ;;
            alacritty)
                alacritty --title "${LABEL}" --geometry "${COLS_CHAR}x${ROWS_CHAR}" --position "${X}" "${Y}" -e bash "${WORKER_SCRIPT}" &
                ;;
            kitty)
                kitty --title "${LABEL}" -o "initial_window_width=${WIN_W}" -o "initial_window_height=${WIN_H}" bash "${WORKER_SCRIPT}" &
                ;;
            xterm|x-terminal-emulator)
                "$GUI_TERMINAL" -title "${LABEL}" -geometry "${COLS_CHAR}x${ROWS_CHAR}+${X}+${Y}" -e bash "${WORKER_SCRIPT}" &
                ;;
            *)
                bash "${WORKER_SCRIPT}" &
                ;;
        esac

        # Asynchronously align window with wmctrl/xdotool once spawned
        arrange_window "$LABEL" "$X" "$Y" "$WIN_W" "$WIN_H"

        sleep 0.4
    done

    # Final pass to ensure all windows are firmly snapped into the grid
    if command -v wmctrl &>/dev/null || command -v xdotool &>/dev/null; then
        sleep 1
        for (( i=0; i<NUM_WINDOWS; i++ )); do
            NUM=$(printf '%02d' $((i+1)))
            LABEL="Worker-${NUM}"
            COL=$(( i % COLS ))
            ROW=$(( i / COLS ))
            X=$(( MARGIN + COL * (WIN_W + MARGIN) ))
            Y=$(( TASKBAR_OFFSET + MARGIN + ROW * (WIN_H + MARGIN) ))
            if command -v wmctrl &>/dev/null; then
                wmctrl -r "$LABEL" -e "0,$X,$Y,$WIN_W,$WIN_H" 2>/dev/null || true
            elif command -v xdotool &>/dev/null; then
                wid=$(xdotool search --onlyvisible --name "$LABEL" 2>/dev/null | tail -n1 || true)
                if [[ -n "$wid" ]]; then
                    xdotool windowmove "$wid" "$X" "$Y" 2>/dev/null || true
                    xdotool windowsize "$wid" "$WIN_W" "$WIN_H" 2>/dev/null || true
                fi
            fi
        done
    fi

    echo ""
    echo "  [+] All ${NUM_WINDOWS} windows launched and arranged in a ${COLS}x${ROWS} grid."
    echo "  👉 To stop all workers at any time, run:"
    echo "     ./launch_multi_linux.sh stop  (or pkill -f 'main.py')"

elif [[ "$SELECTED_METHOD" == "tmux" ]]; then
    echo "[*] Launching ${NUM_WINDOWS} workers in tmux session '${TMUX_SESSION}'..."

    # Kill any existing session with this name
    tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true

    # Start new detached tmux session running worker 1
    tmux new-session -d -s "$TMUX_SESSION" -n "workers" "bash ${TMPDIR_WORKERS}/worker_01.sh"

    # Split panes for workers 2 through NUM_WINDOWS
    for (( i=1; i<NUM_WINDOWS; i++ )); do
        NUM=$(printf '%02d' $((i+1)))
        tmux split-window -t "$TMUX_SESSION:workers" "bash ${TMPDIR_WORKERS}/worker_${NUM}.sh"
        tmux select-layout -t "$TMUX_SESSION:workers" tiled
    done

    # Ensure clean tiled grid layout
    tmux select-layout -t "$TMUX_SESSION:workers" tiled

    echo ""
    echo "  [+] tmux session '${TMUX_SESSION}' is running in the background with ${NUM_WINDOWS} panes."
    echo ""
    echo "  👉 To view all workers in real time, run:"
    echo "     tmux attach -t ${TMUX_SESSION}"
    echo ""
    echo "  👉 To detach from tmux: Press Ctrl+b, then d"
    echo "  👉 To stop all workers: ./launch_multi_linux.sh stop"

elif [[ "$SELECTED_METHOD" == "bg" ]]; then
    echo "[*] Launching ${NUM_WINDOWS} background workers with log files..."
    PID_FILE="$TMPDIR_WORKERS/pids.txt"
    > "$PID_FILE"

    for (( i=0; i<NUM_WINDOWS; i++ )); do
        NUM=$(printf '%02d' $((i+1)))
        LABEL="Worker-${NUM}"
        WORKER_SCRIPT="$TMPDIR_WORKERS/worker_${NUM}.sh"
        LOG_FILE="$TMPDIR_WORKERS/worker_${NUM}.log"

        bash "$WORKER_SCRIPT" > "$LOG_FILE" 2>&1 &
        PID=$!
        echo "$PID" >> "$PID_FILE"
        echo "  [$LABEL] Started (PID: $PID) -> Log: $LOG_FILE"
    done

    echo ""
    echo "  [+] All ${NUM_WINDOWS} workers running in background."
    echo ""
    echo "  👉 To monitor live logs from all workers, run:"
    echo "     tail -f ${TMPDIR_WORKERS}/worker_*.log"
    echo ""
    echo "  👉 To stop all workers: ./launch_multi_linux.sh stop"
fi

echo ""
