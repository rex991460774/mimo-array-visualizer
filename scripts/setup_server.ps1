# Setup or upgrade (after `git pull`) on a Windows server: Python venv, dependencies, web client.
# Requires Python 3.10+ and Node.js 20+ on PATH.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Push-Location web
# Always reinstall from the lock file so an upgrade picks up new dependencies.
npm ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "web build failed" }
Pop-Location

Write-Host ""
Write-Host "Done. Start the server with:"
Write-Host "  .\scripts\run_server.ps1"
