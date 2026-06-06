# restart-stack.ps1 - cleanly restart B60 services. Stopping a scheduled task leaves the
# spawned child (ollama/llama-server/litellm/python) running, so we kill children explicitly.
param([ValidateSet('Swap','Gateway','Hermes','All')][string]$Service='All')

function Restart-One($task, [string[]]$prefixes) {
  Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
  foreach ($p in $prefixes) {
    Get-Process -ErrorAction SilentlyContinue |
      Where-Object { $_.Path -and $_.Path.StartsWith($p) } |
      Stop-Process -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep 3
  Start-ScheduledTask -TaskName $task
  Write-Host "restarted $task"
}

if ($Service -in 'Swap','All')    { Restart-One 'B60-Swap'    @('V:\AI\llama-swap','V:\AI\llama-cpp') }
if ($Service -in 'Gateway','All') { Restart-One 'B60-Gateway' @('V:\AI\gateway\venv') }
if ($Service -in 'Hermes','All')  { Restart-One 'B60-Hermes'  @('C:\hermes-bridge\venv') }
