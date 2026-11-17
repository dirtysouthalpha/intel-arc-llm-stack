# healthcheck.ps1 -- one-command health check for the live Arc stack.
# Checks the llama-swap endpoint, the LiteLLM gateway, and one real model
# response via the gateway. HTTP only, no GPU work, so it runs without a GPU.
# Usage:
#   powershell -File healthcheck.ps1
#   powershell -File healthcheck.ps1 -Model local-chat -GatewayPort 4000 -SwapPort 9090
# Exit code 0 = all checks passed, 1 = at least one check failed.
param(
  [int]$GatewayPort = 4000,
  [int]$SwapPort = 9090,
  [string]$Model = "local-chat",
  [string]$ApiHost = "127.0.0.1",
  [int]$TimeoutSec = 10,
  [string]$ApiKey = $env:LITELLM_MASTER_KEY
)
$failed = 0

function Test-Check($name, $scriptBlock) {
  try {
    $detail = & $scriptBlock
    Write-Host "PASS: $name -- $detail"
  } catch {
    Write-Host "FAIL: $name -- $($_.Exception.Message)"
    $script:failed++
  }
}

Test-Check "llama-swap models (http://${ApiHost}:${SwapPort}/v1/models)" {
  $r = Invoke-RestMethod "http://${ApiHost}:${SwapPort}/v1/models" -TimeoutSec $TimeoutSec
  $count = @($r.data).Count
  if ($count -eq 0) { throw "swap returned no models" }
  "$count model(s) listed"
}

Test-Check "gateway liveliness (http://${ApiHost}:${GatewayPort}/health/liveliness)" {
  Invoke-RestMethod "http://${ApiHost}:${GatewayPort}/health/liveliness" -TimeoutSec $TimeoutSec | Out-Null
  "gateway responded"
}

Test-Check "model response via gateway ($Model)" {
  $headers = @{ "Content-Type" = "application/json" }
  if ($ApiKey) { $headers["Authorization"] = "Bearer $ApiKey" }
  $body = @{ model = $Model; messages = @(@{ role = "user"; content = "Reply with exactly: OK" }); temperature = 0; max_tokens = 5; stream = $false } | ConvertTo-Json -Depth 6
  $r = Invoke-RestMethod "http://${ApiHost}:${GatewayPort}/v1/chat/completions" -Method Post -Headers $headers -Body $body -TimeoutSec 120
  $content = $r.choices[0].message.content
  if (-not $content) { throw "gateway returned an empty response" }
  "model answered: $($content.Trim())"
}

if ($failed -gt 0) {
  Write-Host "healthcheck: $failed check(s) FAILED"
  exit 1
}
Write-Host "healthcheck: all checks passed"
exit 0
