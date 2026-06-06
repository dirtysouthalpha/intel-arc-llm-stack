# start-llama-server.ps1 — IPEX-LLM llama.cpp server on the Arc B60 (OpenAI /v1 API).
# Reliable full-GPU offload via -ngl 999 (unlike the ollama scheduler).
# Must run in the interactive session (session 1) — Intel compute isn't reachable from session 0.
param(
  [string]$Model = "V:\AI\models\gemma-3-12b-it-Q4_K_M.gguf",
  [int]$Ctx = 131072,
  [int]$Port = 8088,            # 8080 collides with qBittorrent's WebUI
  [int]$Ngl = 999,
  [string]$KvType = "q8_0",
  [int]$UBatch = 0,            # micro-batch; SMALL value shrinks the attention compute buffer
  [int]$Batch = 0,            # logical batch
  # This IPEX SYCL build has NO flash-attention kernel: -fa falls back to a CPU op that
  # crashes (GGML_ASSERT nbv0 == ggml_type_size in ggml-cpu/ops.cpp). So FA stays OFF and we
  # tame the (otherwise 36GB @128K) compute buffer by lowering -ub instead. f16 KV (no quant;
  # quantized V also crashes the same way).
  [switch]$FlashAttn,         # opt-in; known-broken on this build, kept for future builds
  [switch]$QuantKv            # opt-in; known-broken on this build
)
$LL = "V:\AI\llama-cpp"
$env:ONEAPI_DEVICE_SELECTOR = "level_zero:0"   # pin Arc B60, never the RTX 2070
$env:ZES_ENABLE_SYSMAN      = "1"
$env:SYCL_CACHE_PERSISTENT  = "1"

$args = @("-m", $Model, "-ngl", $Ngl, "--host", "0.0.0.0", "--port", $Port,
          "-c", $Ctx, "-np", "1", "--no-mmap")
if ($UBatch -gt 0) { $args += @("-ub", $UBatch) }
if ($Batch  -gt 0) { $args += @("-b",  $Batch) }
if ($FlashAttn)    { $args += @("-fa") }                              # broken on this build
if ($QuantKv)      { $args += @("-ctk", $KvType, "-ctv", $KvType) }   # broken on this build

Set-Location $LL
Write-Host "llama-server: $Model  ctx=$Ctx  ngl=$Ngl  port=$Port  (Arc B60)"
$log = "V:\AI\logs\llama-server-$Port.log"
& "$LL\llama-server.exe" @args *> $log
