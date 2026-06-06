# start-gateway.ps1 — LiteLLM unified OpenAI endpoint (local-first cost routing).
# Reachable over Tailscale at 100.70.240.55:4000.
$GW = "V:\AI\gateway"
if (Test-Path "$GW\.env") {
  Get-Content "$GW\.env" | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') { Set-Item -Path ("env:" + $matches[1].Trim()) -Value $matches[2].Trim() }
  }
}
Set-Location $GW
# litellm installed in its own venv (V:\AI\gateway\venv) to avoid clashing with Sentinel's
& "$GW\venv\Scripts\litellm.exe" --config "$GW\config.yaml" --host 0.0.0.0 --port 4000
