# watchdog.ps1 - health-checks every B60/dashboard service and relaunches any that are down.
# Runs hidden every ~2 min via the B60-Watchdog scheduled task. Also covers crash + post-reboot.
$ErrorActionPreference = "SilentlyContinue"
$logf = "V:\AI\logs\watchdog.log"
function Note($m) { "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m | Add-Content $logf }

# name = scheduled task to (re)start; url = health probe; kill = process path-prefixes to clear if stuck
$services = @(
  @{ name = "B60-Swap";      url = "http://127.0.0.1:9090/v1/models";         kill = @("V:\AI\llama-swap", "V:\AI\llama-cpp") },
  @{ name = "B60-Gateway";   url = "http://127.0.0.1:4000/health/liveliness"; kill = @("V:\AI\gateway\venv") },
  @{ name = "B60-Hermes";    url = "http://127.0.0.1:8478/health";            kill = @("C:\hermes-bridge\venv") },
  @{ name = "CommandCenter"; url = "http://127.0.0.1:3002/";                  kill = @("C:\builds\command-center") }
)

foreach ($s in $services) {
  $ok = $false
  try { Invoke-WebRequest $s.url -TimeoutSec 6 -UseBasicParsing | Out-Null; $ok = $true }
  catch { if ($_.Exception.Response) { $ok = $true } }   # any HTTP reply = process alive
  if (-not $ok) {
    foreach ($p in $s.kill) {
      Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($p) } | Stop-Process -Force
    }
    Start-Sleep 2
    Start-ScheduledTask -TaskName $s.name
    Note "restarted $($s.name) (was down: $($s.url))"
  }
}

# cloudflared tunnel (process-based, not an HTTP service)
if (-not (Get-Process cloudflared)) {
  Start-ScheduledTask -TaskName "Start Cloudflared Tunnel"
  Note "restarted cloudflared tunnel"
}
