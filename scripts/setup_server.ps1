# One-time setup on a Windows server: Python venv, dependencies, web client.
# Requires Python 3.10+ and Node.js 20+ on PATH.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Push-Location web
if (-not (Test-Path "node_modules")) {
    npm ci --no-audit --no-fund
}
npm run build
Pop-Location

Write-Host ""
Write-Host "Done. Start the server with:"
Write-Host "  .\scripts\run_server.ps1"
