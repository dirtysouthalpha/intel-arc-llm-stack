# setup-services.ps1 - make every B60/dashboard service launch HIDDEN + add a watchdog monitor.
$ErrorActionPreference = "Stop"
$vbs  = "V:\AI\launchers\hidden-run.vbs"
$me   = "HOME\Administrator"
# Prompt at runtime — do NOT hardcode the admin password in a file on disk.
$cred = Get-Credential -UserName $me -Message "Admin password (for the session-0 B60-Watchdog task)"
$pw   = $cred.GetNetworkCredential().Password

function Reg-HiddenInteractive($name, $script, $triggers) {
  # Session-1 (GPU) services: run the .ps1 hidden via the VBS wrapper, interactive logon.
  $action    = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ("//B //Nologo `"$vbs`" `"$script`"")
  $principal = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Highest
  $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
  Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Force | Out-Null
}

$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $me

# 1) GPU/session-1 services -> hidden launch
Reg-HiddenInteractive "B60-Swap"   "V:\AI\launchers\start-swap.ps1"   $atLogon
Reg-HiddenInteractive "B60-Hermes" "V:\AI\launchers\start-hermes.ps1" $atLogon
# Warmup: at logon + every 15 min (idle-aware), hidden
$warmTriggers = @($atLogon, (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 15)))
Reg-HiddenInteractive "B60-Warmup" "V:\AI\launchers\start-warmup.ps1" $warmTriggers

# 2) Watchdog -> session 0 (inherently no window), AtStartup + every 2 min. First run +3 min so setup settles.
$wdAction  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File V:\AI\launchers\watchdog.ps1"
$wdTrig    = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(3) -RepetitionInterval (New-TimeSpan -Minutes 2)))
$wdSet     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "B60-Watchdog" -Action $wdAction -Trigger $wdTrig -Settings $wdSet -User $me -Password $pw -RunLevel Highest -Force | Out-Null

Write-Output "Registered hidden launchers + B60-Watchdog."

# 3) Apply hidden NOW: restart the session-1 GPU services via the new hidden tasks (brief blip).
foreach ($t in "B60-Swap", "B60-Hermes") {
  Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
}
Get-Process | Where-Object { $_.Path -and ($_.Path.StartsWith("V:\AI\llama-swap") -or $_.Path.StartsWith("V:\AI\llama-cpp") -or $_.Path.StartsWith("C:\hermes-bridge\venv")) } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 3
Start-ScheduledTask -TaskName "B60-Swap"
Start-ScheduledTask -TaskName "B60-Hermes"
# wait for swap, then warm
foreach ($i in 1..25) { Start-Sleep 2; try { Invoke-WebRequest "http://127.0.0.1:9090/v1/models" -TimeoutSec 3 -UseBasicParsing | Out-Null; break } catch {} }
Start-ScheduledTask -TaskName "B60-Warmup"

# 4) Status
Start-Sleep 5
Write-Output "--- task states ---"
Get-ScheduledTask -TaskName "B60-*","CommandCenter" | Select-Object TaskName, State | Sort-Object TaskName | ForEach-Object { "  {0,-16} {1}" -f $_.TaskName, $_.State }
