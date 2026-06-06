# start-llama-server.ps1 — IPEX-LLM llama.cpp server on the Arc B60 (OpenAI /v1 API).
# Reliable full-GPU offload via -ngl 999 (unlike the ollama scheduler).
# Must run in the interactive session (session 1) — Intel compute isn't reachable from session 0.
param(
  [string]$Model = "V:\AI\models\gemma-3-12b-it-Q4_K_M.gguf",
  [int]$Ctx = 131072,
  [int]$Port = 8088,            # 8080 collides with qBittorrent's WebUI
  [int]$Ngl = 999,
  [string]$KvType = "q8_0",
  # Flash attention with FP16 KV is REQUIRED for long context: without -fa the attention
  # compute buffer explodes (36GB+ at 128K) and load fails. With -fa it streams.
  # Do NOT add -ctk/-ctv KV quant: quantized V crashes this SYCL build
  # (GGML_ASSERT nbv0 == ggml_type_size in ggml-cpu/ops.cpp). f16 KV + -fa is the sweet spot.
  [switch]$QuantKv,            # opt-in; known-broken on this build, here for future testing
  [switch]$NoFlashAttn         # disable flash attention (only for tiny contexts)
)
$LL = "V:\AI\llama-cpp"
$env:ONEAPI_DEVICE_SELECTOR = "level_zero:0"   # pin Arc B60, never the RTX 2070
$env:ZES_ENABLE_SYSMAN      = "1"
$env:SYCL_CACHE_PERSISTENT  = "1"

$args = @("-m", $Model, "-ngl", $Ngl, "--host", "0.0.0.0", "--port", $Port,
          "-c", $Ctx, "-np", "1", "--no-mmap")
if (-not $NoFlashAttn) { $args += @("-fa") }                       # f16 KV + flash attention (default)
if ($QuantKv)          { $args += @("-ctk", $KvType, "-ctv", $KvType) }  # broken on this build

Set-Location $LL
Write-Host "llama-server: $Model  ctx=$Ctx  ngl=$Ngl  port=$Port  (Arc B60)"
$log = "V:\AI\logs\llama-server-$Port.log"
& "$LL\llama-server.exe" @args *> $log
