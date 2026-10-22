# Drive mGBA: start a ROM (or reuse the running instance), run steps, capture screens.
# Steps: "wait:SECONDS", "key:NAME[:COUNT]", "shot:NAME", "hold:NAME:MS"
param([string]$Rom, [string]$OutDir, [string[]]$Steps, [switch]$Keep, [switch]$Reuse)
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
$vk = @{ Enter=0x0D; A=0x41; Z=0x5A; Q=0x51; S=0x53; Space=0x20; Left=0x25; Up=0x26; Right=0x27; Down=0x28; Tab=0x09 }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$p = $null
if ($Reuse) { $p = Get-Process mGBA -ErrorAction SilentlyContinue | Select-Object -First 1 }
if (-not $p) { $p = Start-Process "C:\Program Files\mGBA\mGBA.exe" -ArgumentList "`"$Rom`"" -PassThru; Start-Sleep -Seconds 3 }
$p.Refresh(); $h = $p.MainWindowHandle
function Focus { [W]::SetForegroundWindow($h) | Out-Null; Start-Sleep -Milliseconds 150 }
function Press([string]$name, [int]$ms = 90) {
  Focus
  [W]::keybd_event([byte]$vk[$name], 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds $ms
  [W]::keybd_event([byte]$vk[$name], 0, 2, [UIntPtr]::Zero); Start-Sleep -Milliseconds 120
}
function Shot([string]$name) {
  Focus
  $r = New-Object W+RECT; [W]::GetWindowRect($h, [ref]$r) | Out-Null
  $w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
  $bmp = New-Object System.Drawing.Bitmap $w, $hh
  [System.Drawing.Graphics]::FromImage($bmp).CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
  $bmp.Save((Join-Path $OutDir "$name.png")); "shot $name"
}
foreach ($s in $Steps) {
  $parts = $s.Split(":")
  switch ($parts[0]) {
    "wait" { Start-Sleep -Milliseconds ([double]$parts[1] * 1000) }
    "key"  { $n = 1; if ($parts.Length -gt 2) { $n = [int]$parts[2] }; for ($i = 0; $i -lt $n; $i++) { Press $parts[1] } }
    "hold" { Press $parts[1] ([int]$parts[2]) }
    "shot" { Shot $parts[1] }
  }
}
if (-not $Keep) { Stop-Process -Id $p.Id }
