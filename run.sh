#!/usr/bin/env bash
# Universal launcher for macOS and Linux
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$OSTYPE" == "darwin"* ]]; then
    exec bash "$PROJECT_DIR/run_mac.sh" "$@"
else
    exec bash "$PROJECT_DIR/run_linux.sh" "$@"
fi
