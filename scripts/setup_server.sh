#!/usr/bin/env bash
# Setup or upgrade (after `git pull`) on a Linux/macOS server: Python venv, dependencies, web client.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
scripts/build_web.sh
echo
echo "Done. Start the server with:"
echo "  .venv/bin/mimo-array-server --host 0.0.0.0 --port 8000 --data-dir ./data"
