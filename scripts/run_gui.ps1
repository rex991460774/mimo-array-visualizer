$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "Missing .venv. Run .\scripts\setup.ps1 first."
}

.\.venv\Scripts\python.exe -m virtual_array.gui

