$ErrorActionPreference = "Stop"
$ProductRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = (Resolve-Path (Join-Path $ProductRoot "..\..")).Path

Push-Location (Join-Path $RepositoryRoot "app\backend")
try {
    python -m pytest -q tests/test_timetable_standalone.py tests/test_tenant_access.py tests/test_department_calendars.py tests/test_academic_rosters.py tests/test_workload_allocation.py tests/test_activity_expansion.py tests/test_solve_preflight.py tests/test_multi_calendar_solver.py tests/test_solver.py
}
finally {
    Pop-Location
}

Push-Location (Join-Path $RepositoryRoot "app")
try {
    npm run build
}
finally {
    Pop-Location
}
