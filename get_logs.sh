#!/usr/bin/env bash
# ==============================================================================
#  get_logs.sh -- Stream, Inspect & Download CloudflareAuto Logs from Oracle Cloud
# ==============================================================================
set -euo pipefail

REMOTE_HOST="oracle"
REMOTE_LOG_DIR="/home/ubuntu/CloudflareAuto/logs"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_LOG_DIR="${LOCAL_DIR}/logs"

mkdir -p "$LOCAL_LOG_DIR"

show_help() {
    echo "================================================================"
    echo "  CloudflareAuto -- Cloud Log Monitor & Manager"
    echo "================================================================"
    echo "  Usage:"
    echo "    ./get_logs.sh             # Live-stream all worker logs in real time"
    echo "    ./get_logs.sh 1           # Live-stream Worker 1 log only"
    echo "    ./get_logs.sh 2           # Live-stream Worker 2 log only"
    echo "    ./get_logs.sh --status    # Check 24/7 service status, RAM, CPU & PID"
    echo "    ./get_logs.sh --download  # Download all remote logs to local logs/"
    echo "    ./get_logs.sh --restart   # Restart the 24/7 cloud service"
    echo "    ./get_logs.sh --stop      # Stop the 24/7 cloud service"
    echo "================================================================"
    exit 0
}

MODE="${1:-stream}"

case "$MODE" in
    -h|--help|help)
        show_help
        ;;
    -s|--status|status)
        echo "================================================================"
        echo "  Checking CloudflareAuto Service & VM Status on Oracle Cloud..."
        echo "================================================================"
        ssh "$REMOTE_HOST" "
            sudo systemctl status cloudflare-auto --no-pager || true
            echo ''
            echo '── System Resources ─────────────────────────────────────'
            free -h
            echo ''
            echo '── Active Automation Processes ──────────────────────────'
            ps aux | grep -E 'python.*main\.py|start_workers' | grep -v grep || echo 'No active worker processes found.'
        "
        ;;
    -d|--download|download)
        echo "================================================================"
        echo "  Downloading remote logs from Oracle Cloud to ${LOCAL_LOG_DIR}..."
        echo "================================================================"
        rsync -avz "${REMOTE_HOST}:${REMOTE_LOG_DIR}/" "${LOCAL_LOG_DIR}/"
        echo "  [+] Logs downloaded successfully to: ${LOCAL_LOG_DIR}"
        ls -lh "${LOCAL_LOG_DIR}"
        ;;
    --restart|restart)
        echo "================================================================"
        echo "  Restarting cloudflare-auto 24/7 service on Oracle Cloud..."
        echo "================================================================"
        ssh "$REMOTE_HOST" "sudo systemctl restart cloudflare-auto && sudo systemctl status cloudflare-auto --no-pager"
        echo "  [+] Service restarted successfully."
        ;;
    --stop|stop)
        echo "================================================================"
        echo "  Stopping cloudflare-auto 24/7 service on Oracle Cloud..."
        echo "================================================================"
        ssh "$REMOTE_HOST" "sudo systemctl stop cloudflare-auto && sudo systemctl status cloudflare-auto --no-pager || true"
        echo "  [+] Service stopped."
        ;;
    1|worker1|01)
        echo "================================================================"
        echo "  Streaming Worker 1 Logs (Ctrl+C to exit)..."
        echo "================================================================"
        ssh -t "$REMOTE_HOST" "tail -n 40 -f ${REMOTE_LOG_DIR}/worker_01.log 2>/dev/null || tail -n 40 -f /var/log/cloudflare-auto.log"
        ;;
    2|worker2|02)
        echo "================================================================"
        echo "  Streaming Worker 2 Logs (Ctrl+C to exit)..."
        echo "================================================================"
        ssh -t "$REMOTE_HOST" "tail -n 40 -f ${REMOTE_LOG_DIR}/worker_02.log 2>/dev/null"
        ;;
    *)
        echo "================================================================"
        echo "  Streaming All Worker Logs in Real Time (Ctrl+C to exit)..."
        echo "================================================================"
        ssh -t "$REMOTE_HOST" "tail -n 30 -f ${REMOTE_LOG_DIR}/worker_*.log 2>/dev/null || journalctl -u cloudflare-auto -f -n 40"
        ;;
esac
