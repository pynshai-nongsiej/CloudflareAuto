#!/usr/bin/env bash
# ==============================================================================
# start_workers.sh -- 24/7 Production Runner for CloudflareAuto on Oracle Cloud
# ==============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

PYTHON="$PROJECT_DIR/.venv/bin/python"
if [[ ! -f "$PYTHON" ]]; then
    PYTHON="python3"
fi

# Ensure Python flushes logs immediately in real time
export PYTHONUNBUFFERED=1

# Recommended configuration for Oracle Cloud Free Tier (1GB RAM + 3GB Swap)
# 2 workers with 60-120s staggered pacing prevents memory thrashing
NUM_WORKERS="${NUM_WORKERS:-2}"
DELAY_MIN="${DELAY_MIN:-0}"
DELAY_MAX="${DELAY_MAX:-0}"

# Target Referral Account (Default: Account 1 - pn@gmail.com)
TARGET_URL="${TARGET_URL:-https://websurfer.1024tenbox.com/referral/XWUPKX2D}"

echo "================================================================"
echo "  CloudflareAuto 24/7 Production Supervisor"
echo "  Started at : $(date)"
echo "  Workers    : ${NUM_WORKERS}"
echo "  Pacing     : ${DELAY_MIN}-${DELAY_MAX}s"
echo "  Target URL : ${TARGET_URL}"
echo "  Logs Dir   : ${PROJECT_DIR}/logs"
echo "================================================================"

# Trap termination signals to stop child workers cleanly
PIDS=()
cleanup() {
    echo "[*] Supervisor received shutdown signal. Stopping child workers..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    pkill -P $$ 2>/dev/null || true
    pkill -f 'main.py.*--loop' 2>/dev/null || true
    echo "[*] All workers stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM SIGHUP

# Launch each worker
for (( i=1; i<=NUM_WORKERS; i++ )); do
    NUM=$(printf '%02d' "$i")
    LOG_FILE="$PROJECT_DIR/logs/worker_${NUM}.log"

    (
        echo "=== [Worker-${NUM}] Starting at $(date) ===" > "$LOG_FILE"
        while true; do
            echo "[Worker-${NUM}] $(date '+%Y-%m-%d %H:%M:%S') - Launching registration cycle..." >> "$LOG_FILE"
            "$PYTHON" -u main.py --mode direct --loop --target-url "$TARGET_URL" --delay-min "$DELAY_MIN" --delay-max "$DELAY_MAX" >> "$LOG_FILE" 2>&1 || true
            echo "[Worker-${NUM}] $(date '+%Y-%m-%d %H:%M:%S') - Worker exited. Restarting in 5s..." >> "$LOG_FILE"
            sleep 5
        done
    ) &
    PIDS+=($!)
    echo "  [+] Worker-${NUM} started (PID: ${PIDS[-1]}) -> ${LOG_FILE}"
done

echo ""
echo "[*] All workers active. Monitoring..."

# Keep supervisor alive while child workers run
wait
