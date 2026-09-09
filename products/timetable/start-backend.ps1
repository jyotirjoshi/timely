param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = (Resolve-Path (Join-Path $ProductRoot "..\..")).Path
$BackendRoot = Join-Path $RepositoryRoot "app\backend"

if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Pass a different -Port value."
}

if (-not $env:SECRET_KEY) {
    $env:SECRET_KEY = "local-timetable-demo-change-before-production"
}
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "sqlite:///./timely-timetable-standalone.db"
}
if (-not $env:AI_PROVIDER) {
    $env:AI_PROVIDER = "none"
}
if (-not $env:SOLVER_WORKERS) {
    $env:SOLVER_WORKERS = "8"
}

Set-Location $BackendRoot
python -c "import fastapi, uvicorn, sqlalchemy, ortools" 2>$null
if ($LASTEXITCODE -ne 0) {
    python -m pip install -r requirements.txt
}
python -m uvicorn app.timetable_main:app --host 127.0.0.1 --port $Port
