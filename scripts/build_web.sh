#!/usr/bin/env bash
# Build the web client into src/virtual_array/server/static (served by the API server).
set -euo pipefail
cd "$(dirname "$0")/../web"
# Always reinstall from the lock file: after `git pull` an existing node_modules
# may lack newly added dependencies and the build would fail (or ship a stale client).
npm ci --no-audit --no-fund
npm run build
echo "Web client built into src/virtual_array/server/static"
