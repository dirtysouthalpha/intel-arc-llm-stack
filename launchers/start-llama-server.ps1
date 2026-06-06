# start-llama-server.ps1 — IPEX-LLM llama.cpp server on the Arc B60 (OpenAI /v1 API).
# Reliable full-GPU offload via -ngl 999 (unlike the ollama scheduler).
# Must run in the interactive session (session 1) — Intel compute isn't reachable from session 0.
param(
  [string]$Model = "V:\AI\models\gemma-3-12b-it-Q4_K_M.gguf",
  [int]$Ctx = 131072,
  [int]$Port = 8088,            # 8080 collides with qBittorrent's WebUI
  [int]$Ngl = 999,
  [string]$KvType = "q8_0",
  # Flash attention + quantized KV crashes this IPEX SYCL build
  # (GGML_ASSERT nbv0 == ggml_type_size in ggml-cpu/ops.cpp). Default OFF -> f16 KV.
  # Gemma 3's sliding-window attention keeps KV small even at 128K, so f16 is fine.
  [switch]$FlashAttn,
  [switch]$NoFlashAttn         # kept for back-compat; f16 KV is the default
)
$LL = "V:\AI\llama-cpp"
$env:ONEAPI_DEVICE_SELECTOR = "level_zero:0"   # pin Arc B60, never the RTX 2070
$env:ZES_ENABLE_SYSMAN      = "1"
$env:SYCL_CACHE_PERSISTENT  = "1"

$args = @("-m", $Model, "-ngl", $Ngl, "--host", "0.0.0.0", "--port", $Port,
          "-c", $Ctx, "-np", "1", "--no-mmap")
if ($FlashAttn) { $args += @("-fa", "-ctk", $KvType, "-ctv", $KvType) }  # opt-in only

Set-Location $LL
Write-Host "llama-server: $Model  ctx=$Ctx  ngl=$Ngl  port=$Port  (Arc B60)"
$log = "V:\AI\logs\llama-server-$Port.log"
& "$LL\llama-server.exe" @args *> $log
