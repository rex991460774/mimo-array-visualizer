#!/usr/bin/env bash
# Build the web client into src/virtual_array/server/static (served by the API server).
set -euo pipefail
cd "$(dirname "$0")/../web"
if [ ! -d node_modules ]; then
  npm ci --no-audit --no-fund
fi
npm run build
echo "Web client built into src/virtual_array/server/static"
