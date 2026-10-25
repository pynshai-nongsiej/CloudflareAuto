#!/usr/bin/env bash
# ===============================================================================
#  run_mac.sh -- TenBox Websurfer Automation Interactive Menu for macOS
#  Mirrors run_windows.bat with identical configuration, options, and workflows
# ===============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Locate virtual environment python
PYTHON="python3"
if [[ -f "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [[ -f "$PROJECT_DIR/venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"
fi

# Referral Accounts Presets
ACCOUNT_1_URL="https://websurfer.1024tenbox.com/referral/XWUPKX2D"
ACCOUNT_1_EMAIL="pn@gmail.com"

ACCOUNT_2_URL="https://websurfer.1024tenbox.com/referral/XUMZDQ5R"
ACCOUNT_2_EMAIL="dd@gmail.com"

ACCOUNT_3_URL="https://websurfer.1024tenbox.com/referral/75H3QGGK"
ACCOUNT_3_EMAIL="jn@gmail.com"

ACCOUNT_4_URL="https://websurfer.1024tenbox.com/referral/8PCCMJ33"
ACCOUNT_4_EMAIL="dai@gmail.com"

TARGET_URL="$ACCOUNT_1_URL"
TARGET_EMAIL="$ACCOUNT_1_EMAIL"

# If arguments were passed directly from command line, forward them
if [[ $# -gt 0 ]]; then
    "$PYTHON" main.py "$@"
    exit $?
fi

while true; do
    clear
    echo "==============================================================================="
    echo "               CloudflareAuto / TenBox Websurfer Automation (macOS)"
    echo "                          (All Options Headless)"
    echo "==============================================================================="
    echo "Target Account: $TARGET_EMAIL"
    echo "Target URL    : $TARGET_URL"
    echo "Python Engine : $PYTHON"
    echo "==============================================================================="
    echo ""
    echo "Select an option:"
    echo ""
    echo "  [1] Direct Mode - Single Run (Headless)"
    echo "  [2] Unlimited Loop - 1-2 min delay (Headless)"
    echo "  [3] Counted Loop - Run N registrations with 1-2 min delay (Headless)"
    echo "  [4] Multi-Window Grid Launcher (5 Tiled Workers with Staggered Delays)"
    echo "  [5] Stop All Running Workers"
    echo "  [6] AI Agent Mode - browser-use (Headless) [Requires API key in .env]"
    echo "  [7] Switch Target Referral Account (pn, dd, jn, dai, custom)"
    echo "  [8] Show Help / CLI Options"
    echo "  [0] Exit"
    echo ""
    echo "==============================================================================="
    read -r -p "Enter choice [1-8, 0]: " CHOICE

    case "$CHOICE" in
        1)
            echo ""
            echo "[*] Launching Direct Mode (Headless)..."
            "$PYTHON" main.py --mode direct --target-url "$TARGET_URL"
            read -r -p "Press Enter to return to menu..."
            ;;
        2)
            echo ""
            echo "[*] Starting Unlimited Loop Mode (Headless) - Press Ctrl+C to stop..."
            "$PYTHON" main.py --mode direct --loop --delay-min 60 --delay-max 120 --target-url "$TARGET_URL"
            read -r -p "Press Enter to return to menu..."
            ;;
        3)
            echo ""
            read -r -p "How many registrations to run? (e.g. 5, 10): " NUM_RUNS
            echo "[*] Running $NUM_RUNS registrations (Headless)..."
            "$PYTHON" main.py --mode direct --loop --count "$NUM_RUNS" --delay-min 60 --delay-max 120 --target-url "$TARGET_URL"
            read -r -p "Press Enter to return to menu..."
            ;;
        4)
            echo ""
            echo "[*] Launching Multi-Window Tiled Grid Launcher..."
            bash ./launch_multi_mac.sh "$TARGET_URL"
            read -r -p "Press Enter to return to menu..."
            ;;
        5)
            echo ""
            bash ./launch_multi_mac.sh stop
            read -r -p "Press Enter to return to menu..."
            ;;
        6)
            echo ""
            echo "[*] Starting browser-use Agent Mode (Headless)..."
            echo "[*] Ensure your API key is configured in .env"
            "$PYTHON" main.py --mode browser-use --target-url "$TARGET_URL"
            read -r -p "Press Enter to return to menu..."
            ;;
        7)
            clear
            echo "==============================================================================="
            echo "                  Select Target Referral Account"
            echo "==============================================================================="
            echo ""
            echo "  [1] $ACCOUNT_1_EMAIL  -> $ACCOUNT_1_URL (Primary / pn)"
            echo "  [2] $ACCOUNT_2_EMAIL  -> $ACCOUNT_2_URL (Secondary / dd)"
            echo "  [3] $ACCOUNT_3_EMAIL  -> $ACCOUNT_3_URL (Tertiary / jn)"
            echo "  [4] $ACCOUNT_4_EMAIL  -> $ACCOUNT_4_URL (Quaternary / dai)"
            echo "  [5] Custom URL"
            echo ""
            read -r -p "Select account [1-5, Enter to cancel]: " ACC_CHOICE
            case "$ACC_CHOICE" in
                1)
                    TARGET_URL="$ACCOUNT_1_URL"
                    TARGET_EMAIL="$ACCOUNT_1_EMAIL"
                    ;;
                2)
                    TARGET_URL="$ACCOUNT_2_URL"
                    TARGET_EMAIL="$ACCOUNT_2_EMAIL"
                    ;;
                3)
                    TARGET_URL="$ACCOUNT_3_URL"
                    TARGET_EMAIL="$ACCOUNT_3_EMAIL"
                    ;;
                4)
                    TARGET_URL="$ACCOUNT_4_URL"
                    TARGET_EMAIL="$ACCOUNT_4_EMAIL"
                    ;;
                5)
                    read -r -p "Enter custom referral URL: " CUSTOM_URL
                    if [[ -n "$CUSTOM_URL" ]]; then
                        TARGET_URL="$CUSTOM_URL"
                        TARGET_EMAIL="Custom Account"
                    fi
                    ;;
            esac
            ;;
        8)
            echo ""
            "$PYTHON" main.py --help
            read -r -p "Press Enter to return to menu..."
            ;;
        0|exit|q)
            echo "Exiting."
            exit 0
            ;;
        *)
            echo "[!] Invalid selection. Please choose 1-8 or 0."
            sleep 1.5
            ;;
    esac
done
