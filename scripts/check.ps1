$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
Push-Location $repoRoot
try {
    & $pythonPath -m pytest -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
    node --check apps/frontend-app/kiosk/static/app.js
    if ($LASTEXITCODE -ne 0) { throw 'Kiosk JavaScript check failed.' }
    node --check apps/frontend-web/admin/static/app.js
    if ($LASTEXITCODE -ne 0) { throw 'Admin JavaScript check failed.' }
} finally {
    Pop-Location
}
