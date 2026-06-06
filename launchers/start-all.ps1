# start-all.ps1 — bring up the whole B60 stack (idempotent; engines are scheduled tasks).
# Engines run in the interactive session (session 1) so the Arc is reachable for compute.
Start-ScheduledTask -TaskName 'B60-IPEX-Ollama' -ErrorAction SilentlyContinue
# Gateway (LiteLLM) — registered as its own task in Phase 4.
Start-ScheduledTask -TaskName 'B60-Gateway' -ErrorAction SilentlyContinue

foreach ($svc in @(@{n='Ollama (B60)'; u='http://127.0.0.1:11500/api/version'}, @{n='Gateway'; u='http://127.0.0.1:4000/health'})) {
  $up = $false
  try { Invoke-RestMethod $svc.u -TimeoutSec 3 | Out-Null; $up = $true } catch {}
  Write-Host ("{0,-16} {1}" -f $svc.n, $(if ($up) { 'UP' } else { 'down' }))
}
