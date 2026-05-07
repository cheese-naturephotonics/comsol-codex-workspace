param(
    [Parameter(Mandatory = $true)]
    [string]$ModelPath,

    [string]$ProcessName = "comsolmphclient"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ModelPath)) {
    throw "Model path does not exist: $ModelPath"
}

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class WindowFocus {
  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

$target = Get-Process |
    Where-Object { $_.ProcessName -eq $ProcessName -and $_.MainWindowHandle -ne 0 } |
    Sort-Object StartTime -Descending |
    Select-Object -First 1

if (-not $target) {
    throw "No visible process named '$ProcessName' was found."
}

[WindowFocus]::ShowWindowAsync($target.MainWindowHandle, 9) | Out-Null
Start-Sleep -Milliseconds 400

$shell = New-Object -ComObject WScript.Shell
if (-not $shell.AppActivate($target.Id)) {
    throw "Failed to activate COMSOL Desktop window."
}

[WindowFocus]::SetForegroundWindow($target.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 600

Set-Clipboard -Value $ModelPath
$shell.SendKeys("^o")
Start-Sleep -Milliseconds 1200
$shell.SendKeys("^v")
Start-Sleep -Milliseconds 250
$shell.SendKeys("{ENTER}")

[pscustomobject]@{
    processId = $target.Id
    title = $target.MainWindowTitle
    modelPath = $ModelPath
    triggeredAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
} | ConvertTo-Json -Compress
