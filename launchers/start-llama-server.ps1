# start-llama-server.ps1 — IPEX-LLM llama.cpp server on the Arc B60 (OpenAI /v1 API).
# Reliable full-GPU offload via -ngl 999 (unlike the ollama scheduler).
# Must run in the interactive session (session 1) — Intel compute isn't reachable from session 0.
param(
  [string]$Model = "V:\AI\models\gemma3-12b.gguf",
  [int]$Ctx = 131072,
  [int]$Port = 8080,
  [int]$Ngl = 999,
  [string]$KvType = "q8_0",     # quantized KV cache (requires flash attention)
  [switch]$NoFlashAttn
)
$LL = "V:\AI\llama-cpp"
$env:ONEAPI_DEVICE_SELECTOR = "level_zero:0"   # pin Arc B60, never the RTX 2070
$env:ZES_ENABLE_SYSMAN      = "1"
$env:SYCL_CACHE_PERSISTENT  = "1"

$args = @("-m", $Model, "-ngl", $Ngl, "--host", "0.0.0.0", "--port", $Port,
          "-c", $Ctx, "-np", "1", "--no-mmap")
if (-not $NoFlashAttn) { $args += @("-fa", "-ctk", $KvType, "-ctv", $KvType) }

Set-Location $LL
Write-Host "llama-server: $Model  ctx=$Ctx  ngl=$Ngl  port=$Port  (Arc B60)"
& "$LL\llama-server.exe" @args
