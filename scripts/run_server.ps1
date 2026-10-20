# Start the web workbench on this Windows machine.
# Other machines on the LAN can open http://<this-host>:8000/ when -Host 0.0.0.0
# is used and the Windows firewall allows the port.
param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [string]$DataDir = (Join-Path (Join-Path $PSScriptRoot "..") "data")
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
.\.venv\Scripts\mimo-array-server.exe --host $BindHost --port $Port --data-dir $DataDir
