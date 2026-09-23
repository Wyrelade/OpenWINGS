# Focus a window (by process name) and send key(s) via keybd_event scancodes.
# usage: sendkey.ps1 -Keys "ENTER,DOWN" [-Proc dosbox-x] [-HoldMs 80]
param([string]$Keys = "ENTER", [string]$Proc = "dosbox-x", [int]$HoldMs = 80)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class K {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
"@
$map = @{ ENTER=@(0x0D,0x1C,0); ESC=@(0x1B,0x01,0); UP=@(0x26,0x48,1); DOWN=@(0x28,0x50,1);
          LEFT=@(0x25,0x4B,1); RIGHT=@(0x27,0x4D,1); SPACE=@(0x20,0x39,0); F10=@(0x79,0x44,0);
          Y=@(0x59,0x15,0); N=@(0x4E,0x31,0) }
$p = Get-Process $Proc | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
[K]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 150
foreach ($k in $Keys.Split(',')) {
  $e = $map[$k.Trim()]
  $ext = 0; if ($e[2] -eq 1) { $ext = 1 }
  [K]::keybd_event([byte]$e[0], [byte]$e[1], [uint32]$ext, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds $HoldMs
  [K]::keybd_event([byte]$e[0], [byte]$e[1], [uint32]($ext -bor 2), [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 250
}
