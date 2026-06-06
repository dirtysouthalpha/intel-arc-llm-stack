# start-ipex-ollama.ps1
# IPEX-LLM Ollama serving on the Intel Arc Pro B60 (24GB).
# Runs on a SEPARATE port (11500) from stock Ollama (11434, which uses the RTX 2070).
$ROOT = "V:\AI\ipex-ollama"

# --- Device pinning: force the Arc B60 (the only Level-Zero device; never the RTX 2070) ---
$env:ONEAPI_DEVICE_SELECTOR = "level_zero:0"
$env:ZES_ENABLE_SYSMAN      = "1"
$env:SYCL_CACHE_PERSISTENT  = "1"   # persist compiled SYCL kernels (slow first run, fast after)

# --- Ollama service config ---
$env:OLLAMA_HOST            = "0.0.0.0:11500"   # reachable over LAN/Tailscale
$env:OLLAMA_MODELS          = "V:\AI\models"
$env:OLLAMA_NUM_GPU         = "999"             # put all layers on the GPU
$env:OLLAMA_KEEP_ALIVE      = "30m"
$env:OLLAMA_NUM_PARALLEL    = "1"               # 1 = give a single request the whole KV budget (max context)

# --- Max-context levers ---
$env:OLLAMA_FLASH_ATTENTION = "1"               # flash attention -> smaller KV footprint
$env:OLLAMA_KV_CACHE_TYPE   = "q8_0"            # quantized KV cache -> more tokens per GB (best-effort on SYCL)

$env:no_proxy = "localhost,127.0.0.1"

$env:OLLAMA_DEBUG = "INFO"
Set-Location $ROOT
Write-Host "Starting IPEX-LLM Ollama on the Arc B60 (level_zero:0) at $($env:OLLAMA_HOST) ..."
& "$ROOT\ollama.exe" serve *> "V:\AI\logs\serve.log"
