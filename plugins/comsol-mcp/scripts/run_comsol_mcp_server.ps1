$ErrorActionPreference = "Stop"

$pluginRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = if ($env:COMSOL_MCP_PROJECT_ROOT) {
    $env:COMSOL_MCP_PROJECT_ROOT
}
else {
    (Resolve-Path (Join-Path $pluginRoot "..\..")).Path
}
$overridePython = $env:COMSOL_MCP_PYTHON
$localPython = Join-Path $projectRoot ".venv-comsol311\Scripts\python.exe"
$serverScript = Join-Path $pluginRoot "server.py"

function Test-ComsolPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe
    )

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        return $false
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $previousNativeErrorPreference = $PSNativeCommandUseErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $PSNativeCommandUseErrorActionPreference = $false
        & $PythonExe -c "import mcp, mph" *> $null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
    }
}

$pythonCandidates = @($overridePython, $localPython) | Where-Object { $_ }
$pythonExe = $pythonCandidates | Where-Object { Test-ComsolPython $_ } | Select-Object -First 1

if (-not $pythonExe) {
    throw "Could not find a COMSOL Python environment with the required 'mcp' and 'mph' packages. Run scripts/setup_comsol_mph_env.ps1 first or set COMSOL_MCP_PYTHON to a prepared Python executable."
}

Push-Location $projectRoot
try {
    & $pythonExe $serverScript
}
finally {
    Pop-Location
}
