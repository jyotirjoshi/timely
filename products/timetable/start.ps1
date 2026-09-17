param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = (Resolve-Path (Join-Path $ProductRoot "..\..")).Path
$BackendRoot = Join-Path $RepositoryRoot "app\backend"

if (Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue) {
    throw "Backend port $BackendPort is already in use."
}
if (Get-NetTCPConnection -LocalPort $FrontendPort -State Listen -ErrorAction SilentlyContinue) {
    throw "Frontend port $FrontendPort is already in use."
}

if (-not $env:SECRET_KEY) {
    $env:SECRET_KEY = "local-timetable-demo-change-before-production"
}
$env:DATABASE_URL = "sqlite:///./timely-timetable-standalone.db"
if (-not $env:AI_PROVIDER) {
    $env:AI_PROVIDER = "none"
}
if (-not $env:SOLVER_WORKERS) {
    $env:SOLVER_WORKERS = "8"
}
$env:FRONTEND_URL = "http://127.0.0.1:$FrontendPort"

Set-Location $BackendRoot
python -c "import fastapi, uvicorn, sqlalchemy, ortools" 2>$null
if ($LASTEXITCODE -ne 0) {
    python -m pip install -r requirements.txt
}

$Backend = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "app.timetable_main:app", "--host", "127.0.0.1", "--port", $BackendPort `
    -WorkingDirectory $BackendRoot -WindowStyle Hidden -PassThru

try {
    Start-Sleep -Seconds 2
    & (Join-Path $ProductRoot "start-frontend.ps1") -Port $FrontendPort -BackendPort $BackendPort
}
finally {
    if ($Backend -and -not $Backend.HasExited) {
        Stop-Process -Id $Backend.Id
    }
}
