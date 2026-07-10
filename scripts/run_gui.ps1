$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Missing .venv. Run .\scripts\setup.ps1 first."
}

Push-Location $ProjectRoot
try {
    & $Python -m virtual_array.gui @args
}
finally {
    Pop-Location
}

