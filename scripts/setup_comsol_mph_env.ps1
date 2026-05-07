$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envRoot = Join-Path $repoRoot ".venv-comsol311"
$pythonExe = Join-Path $envRoot "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Host "Creating Python 3.11 venv at $envRoot"
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Python launcher 'py' was not found."
    }
    py -3.11 -m venv $envRoot
}

Write-Host "Installing mph + JPype + MCP helpers in $envRoot"
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install mph jpype1==1.5.2 numpy mcp pillow

Write-Host "Done."
