# bench.ps1 -- measure throughput and verify long context actually works on the B60.
# Default path is the live gateway: LiteLLM on :4000, OpenAI-compatible
# /v1/chat/completions, model local-chat. The old Ollama path
# (port 11500, /api/generate) is kept only with -Ollama -- the IPEX-Ollama
# service is disabled on the live stack (STATUS.md) and is not the default.
# Usage:
#   powershell -File bench.ps1 -Model local-chat
#   powershell -File bench.ps1 -Model gemma3-12b-max -Ctx 16384
#   powershell -File bench.ps1 -Ollama -Model gemma3-12b-max -Port 11500
param(
  [string]$Model = "local-chat",
  [int]$Ctx = 0,                       # 0 = no needle test; else needle-test at this ctx
  [int]$Port = 0,                      # 0 = default: 4000 gateway, 11500 with -Ollama
  [string]$ApiHost = "127.0.0.1",
  [switch]$Ollama,
  [string]$ApiKey = $env:LITELLM_MASTER_KEY
)
if ($Port -eq 0) { $Port = if ($Ollama) { 11500 } else { 4000 } }
$base = "http://${ApiHost}:${Port}"

function Invoke-GatewayGen($prompt) {
  $headers = @{ "Content-Type" = "application/json" }
  if ($ApiKey) { $headers["Authorization"] = "Bearer $ApiKey" }
  $body = @{ model = $Model; messages = @(@{ role = "user"; content = $prompt }); temperature = 0; stream = $false } | ConvertTo-Json -Depth 6
  $t0 = Get-Date
  $r = Invoke-RestMethod "$base/v1/chat/completions" -Method Post -Headers $headers -Body $body -TimeoutSec 1800
  $wall = ((Get-Date) - $t0).TotalSeconds
  $content = $r.choices[0].message.content
  $genTok = [int]$r.usage.completion_tokens
  [PSCustomObject]@{
    response   = $content
    tok_s      = if ($genTok -gt 0 -and $wall -gt 0) { [math]::Round($genTok / $wall, 1) } else { 0 }
    prompt_tok = [int]$r.usage.prompt_tokens
    gen_tok    = $genTok
    ttft_s     = 0
    wall_s     = [math]::Round($wall, 1)
  }
}

function Invoke-OllamaGen($prompt, $num_ctx) {
  $opts = @{ temperature = 0 }
  if ($num_ctx -gt 0) { $opts.num_ctx = $num_ctx }
  $body = @{ model = $Model; prompt = $prompt; stream = $false; options = $opts } | ConvertTo-Json -Depth 6
  $t0 = Get-Date
  $r = Invoke-RestMethod "$base/api/generate" -Method Post -Body $body -TimeoutSec 1800
  $wall = ((Get-Date) - $t0).TotalSeconds
  [PSCustomObject]@{
    response   = $r.response
    tok_s      = if ($r.eval_count) { [math]::Round($r.eval_count / ($r.eval_duration / 1e9), 1) } else { 0 }
    prompt_tok = $r.prompt_eval_count
    gen_tok    = $r.eval_count
    ttft_s     = if ($r.prompt_eval_duration) { [math]::Round($r.prompt_eval_duration / 1e9, 2) } else { 0 }
    wall_s     = [math]::Round($wall, 1)
  }
}

function Invoke-Gen($prompt, $num_ctx) {
  if ($Ollama) { return Invoke-OllamaGen $prompt $num_ctx }
  return Invoke-GatewayGen $prompt
}

if ($Ollama) {
  Write-Host "== Throughput ($Model) via Ollama :$Port =="
} else {
  Write-Host "== Throughput ($Model) via gateway :$Port =="
}
$g = Invoke-Gen "Explain how a transformer attention head works, in 120 words." 0
$g | Format-List tok_s, gen_tok, ttft_s, wall_s
if (-not $Ollama) { Write-Host "Note: ttft_s is 0 on the gateway path -- the chat API does not report prompt-eval time; tok/s is completion tokens / wall time." }

if ($Ctx -gt 0) {
  Write-Host "`n== Long-context needle test @ $Ctx tokens =="
  # Build filler ~ Ctx tokens (~4 chars/token), hide a secret in the middle.
  $secret = "The launch code is TANGERINE-42."
  $line = "The quick brown fox jumps over the lazy dog. "
  $fillerChars = [int]($Ctx * 3.5)
  $half = ("$line" * [int]($fillerChars / $line.Length / 2))
  $prompt = "$half`n$secret`n$half`nQuestion: What is the launch code? Answer with only the code."
  $n = Invoke-Gen $prompt $Ctx
  $pass = $n.response -match "TANGERINE-42"
  Write-Host ("prompt_tokens={0}  ttft={1}s  tok/s={2}  -> {3}" -f $n.prompt_tok, $n.ttft_s, $n.tok_s, $(if($pass){"PASS (found needle)"}else{"FAIL: $($n.response)"}))
}
