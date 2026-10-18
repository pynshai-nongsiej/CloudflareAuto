#!/bin/bash
# ─────────────────────────────────────────────────────────────
# OUO.io Link Bypass Bot — Mac/Linux Launch Script
# ─────────────────────────────────────────────────────────────
# Usage:
#   ./ouo_bypass/run.sh                    # headless continuous loop
#   ./ouo_bypass/run.sh --headed           # visible browser
#   ./ouo_bypass/run.sh --headed --count 5 # process 5 links then stop
# ─────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check Python
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "❌ Python not found. Please install Python 3.8+ first."
    exit 1
fi

# Check Playwright is installed
if ! $PYTHON -c "import playwright" 2>/dev/null; then
    echo "📦 Installing Playwright..."
    pip3 install playwright >/dev/null 2>&1 || pip install playwright >/dev/null 2>&1
    echo "📦 Installing Playwright browsers..."
    $PYTHON -m playwright install chromium
fi

echo ""
echo "🌐 Starting OUO.io Bypass Bot..."
echo ""

cd "$PROJECT_ROOT"
$PYTHON ouo_bypass/main.py "$@"
