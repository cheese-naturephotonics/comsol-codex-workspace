$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot ".venv-comsol311\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Missing $pythonExe. Run scripts/setup_comsol_mph_env.ps1 first."
}

& $pythonExe -c "from src.comsol_mph_helper import COMSOL_MPHCLIENT_EXE, COMSOL_SERVER_EXE; print({'client': str(COMSOL_MPHCLIENT_EXE), 'server': str(COMSOL_SERVER_EXE)})"
