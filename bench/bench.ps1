# bench.ps1 — measure throughput and verify long context actually works on the B60.
# Usage: powershell -File bench.ps1 -Model gemma3-12b-max [-Ctx 131072] [-Port 11500]
param(
  [string]$Model = "gemma3-12b-max",
  [int]$Ctx = 0,                       # 0 = use model default; else needle-test at this ctx
  [int]$Port = 11500,
  [string]$ApiHost = "127.0.0.1"
)
$base = "http://${ApiHost}:${Port}"

function Invoke-Gen($prompt, $num_ctx) {
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

Write-Host "== Throughput ($Model) =="
$g = Invoke-Gen "Explain how a transformer attention head works, in 120 words." 0
$g | Format-List tok_s, gen_tok, ttft_s, wall_s

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
