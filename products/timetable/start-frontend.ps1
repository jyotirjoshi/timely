param(
    [int]$Port = 5173,
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"
$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = (Resolve-Path (Join-Path $ProductRoot "..\..")).Path
$FrontendRoot = Join-Path $RepositoryRoot "app"

if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Pass a different -Port value."
}

$env:VITE_API_URL = "http://127.0.0.1:$BackendPort"
Set-Location $FrontendRoot
if (-not (Test-Path "node_modules/vite/bin/vite.js")) {
    npm install
}
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port $Port
