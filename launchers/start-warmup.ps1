# start-warmup.ps1 - keep the primary model warm without thrashing.
# Loads the primary model ONLY when the GPU is idle (no llama-server running). If you're actively
# using another model, that model owns the GPU and we leave it alone; once it unloads (idle), the
# next run re-warms the primary. Run on boot + every ~15 min.
$primary = "gemma3-12b-vision"   # resident model for the dashboard (local-chat/local-vision)
$swap = "http://127.0.0.1:9090/v1/chat/completions"

# Is any model currently loaded? (llama-server child of either engine)
$busy = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -match 'llama-cpp' }
if ($busy) { return }   # something is loaded/active - don't disturb it

# GPU idle -> preload the primary so the next real request is instant.
try {
  $body = @{ model = $primary; messages = @(@{role='user'; content='warmup'}); max_tokens = 1 } | ConvertTo-Json -Depth 5
  Invoke-RestMethod $swap -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 240 | Out-Null
} catch {}
