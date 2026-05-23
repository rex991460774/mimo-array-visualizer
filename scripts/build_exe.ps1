$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Missing .venv. Run .\scripts\setup.ps1 first."
}

& $Python -m PyInstaller --noconfirm --clean .\MIMOArrayVisualizer.spec
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$BuildPath = Join-Path $Root "build"
if (Test-Path -LiteralPath $BuildPath) {
    $ResolvedBuildPath = (Resolve-Path -LiteralPath $BuildPath).Path
    if (-not $ResolvedBuildPath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove build path outside project: $ResolvedBuildPath"
    }
    Remove-Item -LiteralPath $ResolvedBuildPath -Recurse -Force
}

Write-Host "Built .\dist\MIMOArrayVisualizer\MIMOArrayVisualizer.exe"
