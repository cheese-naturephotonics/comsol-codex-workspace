param(
    [Parameter(Mandatory = $true)]
    [string]$OutPath,

    [string[]]$ProcessNames = @("comsolmphclient", "comsol")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing
$drawingAssembly = [System.Reflection.Assembly]::LoadWithPartialName("System.Drawing").Location

Add-Type -ReferencedAssemblies $drawingAssembly -TypeDefinition @"
using System;
using System.Drawing;
using System.Runtime.InteropServices;

public static class WindowCapture {
  [DllImport("user32.dll")]
  public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

  [DllImport("user32.dll")]
  public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, int nFlags);

  [StructLayout(LayoutKind.Sequential)]
  public struct RECT {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
  }

  public static bool Capture(IntPtr handle, string path, out int width, out int height) {
    RECT rect;
    if (!GetWindowRect(handle, out rect)) {
      width = 0;
      height = 0;
      return false;
    }

    width = rect.Right - rect.Left;
    height = rect.Bottom - rect.Top;

    using (var bitmap = new Bitmap(width, height)) {
      using (var graphics = Graphics.FromImage(bitmap)) {
        var hdc = graphics.GetHdc();
        try {
          bool ok = PrintWindow(handle, hdc, 0);
          if (!ok) {
            return false;
          }
        }
        finally {
          graphics.ReleaseHdc(hdc);
        }
      }

      bitmap.Save(path, System.Drawing.Imaging.ImageFormat.Png);
    }

    return true;
  }
}
"@

$target = Get-Process |
    Where-Object { ($ProcessNames -contains $_.ProcessName) -and $_.MainWindowHandle -ne 0 } |
    Sort-Object StartTime -Descending |
    Select-Object -First 1

if (-not $target) {
    throw "No visible COMSOL Desktop window was found."
}

$directory = Split-Path -Parent $OutPath
if ($directory -and -not (Test-Path $directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$width = 0
$height = 0
$ok = [WindowCapture]::Capture($target.MainWindowHandle, $OutPath, [ref]$width, [ref]$height)
if (-not $ok) {
    throw "PrintWindow failed for '$($target.MainWindowTitle)'."
}

[pscustomobject]@{
    processId = $target.Id
    title = $target.MainWindowTitle
    outPath = $OutPath
    width = $width
    height = $height
    capturedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
} | ConvertTo-Json -Compress
