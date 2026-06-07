' hidden-run.vbs <path-to-.ps1>
' Launches a PowerShell script with NO visible window (windowStyle 0), detached.
' Used as the scheduled-task action so nothing ever flashes a console.
Set sh = CreateObject("WScript.Shell")
ps = WScript.Arguments(0)
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps & """", 0, False
