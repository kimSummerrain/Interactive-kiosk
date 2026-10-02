$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install apps/backend/requirements.txt first. See README.md.'
}
Push-Location $repoRoot
try {
    & $pythonPath -m uvicorn app:app --app-dir apps/backend --host 127.0.0.1 --port 8000 --reload --reload-dir apps/backend
} finally {
    Pop-Location
}
