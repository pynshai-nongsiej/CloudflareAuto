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
NUM_WINDOWS="${NUM_WINDOWS:-5}"
MODE="${MODE:-direct}"
TARGET_URL="${TARGET_URL:-https://websurfer.1024tenbox.com/referral/XUMZDQ5R}"
METHOD="${METHOD:-auto}"
TMPDIR_WORKERS="/tmp/cloudflare_auto_workers"
TMUX_SESSION="cloudflare-auto"

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
    pkill -f 'main.py.*--loop' 2>/dev/null || true
    echo "  [+] All workers stopped."
    echo "================================================================"
    exit 0
fi

# ── Clean up old worker directory ────────────────────────────
rm -rf "$TMPDIR_WORKERS"
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

if [[ "$SELECTED_METHOD" == "auto" ]]; then
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

# ── Banner ───────────────────────────────────────────────────
echo "================================================================"
echo "   CloudflareAuto -- Linux / Ubuntu Multi-Session Launcher"
echo "================================================================"
echo "  Project   : $PROJECT_DIR"
echo "  Python    : $PYTHON"
echo "  Mode      : $MODE (--loop)"
echo "  Workers   : $NUM_WINDOWS"
echo "  Target URL: $TARGET_URL"
echo "  Backend   : $SELECTED_METHOD $([[ "$SELECTED_METHOD" == "gui" ]] && echo "($GUI_TERMINAL)" || true)"
echo "================================================================"
echo ""

# ── Generate Worker Scripts ──────────────────────────────────
for (( i=0; i<NUM_WINDOWS; i++ )); do
    NUM=$(printf '%02d' $((i+1)))
    LABEL="Worker-${NUM}"
    WORKER_SCRIPT="$TMPDIR_WORKERS/worker_${NUM}.sh"

    # Stagger launch start times: Worker 1: ~10s, Worker 2: ~40s, Worker 3: ~70s, Worker 4: ~100s, Worker 5: ~130s
    BASE_DELAY=$(( i * 30 ))
    DELAY=$(( BASE_DELAY + $(rand_between 5 15) ))

    cat > "$WORKER_SCRIPT" <<WORKER_EOF
#!/usr/bin/env bash
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
    "${PYTHON}" main.py --mode ${MODE} --loop --target-url "${TARGET_URL}"
    echo ""
    echo "[${LABEL}] Process exited -- restarting in 5s..."
    sleep 5
done
WORKER_EOF

    chmod +x "$WORKER_SCRIPT"
    echo "  [$LABEL] Generated worker script (delay: ${DELAY}s)"
done

echo ""

# ── Launch Execution ─────────────────────────────────────────

if [[ "$SELECTED_METHOD" == "gui" ]]; then
    echo "[*] Launching ${NUM_WINDOWS} terminal windows using ${GUI_TERMINAL}..."

    for (( i=0; i<NUM_WINDOWS; i++ )); do
        NUM=$(printf '%02d' $((i+1)))
        LABEL="Worker-${NUM}"
        WORKER_SCRIPT="$TMPDIR_WORKERS/worker_${NUM}.sh"

        case "$GUI_TERMINAL" in
            gnome-terminal)
                gnome-terminal --title="${LABEL}" -- bash "${WORKER_SCRIPT}" &
                ;;
            xfce4-terminal)
                xfce4-terminal --title="${LABEL}" -e "bash ${WORKER_SCRIPT}" &
                ;;
            terminator)
                terminator -T "${LABEL}" -e "bash ${WORKER_SCRIPT}" &
                ;;
            tilix)
                tilix -t "${LABEL}" -e "bash ${WORKER_SCRIPT}" &
                ;;
            konsole)
                konsole -p tabtitle="${LABEL}" -e bash "${WORKER_SCRIPT}" &
                ;;
            alacritty)
                alacritty --title "${LABEL}" -e bash "${WORKER_SCRIPT}" &
                ;;
            kitty)
                kitty --title "${LABEL}" bash "${WORKER_SCRIPT}" &
                ;;
            xterm|x-terminal-emulator)
                "$GUI_TERMINAL" -title "${LABEL}" -e bash "${WORKER_SCRIPT}" &
                ;;
            *)
                bash "${WORKER_SCRIPT}" &
                ;;
        esac
        sleep 0.3
    done

    echo ""
    echo "  [+] All ${NUM_WINDOWS} windows launched."
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
