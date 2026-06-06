# start-swap.ps1 — llama-swap front: one OpenAI endpoint, swaps B60 models on demand.
# Children (llama-server) inherit the Arc env set here. Must run in session 1.
$env:ONEAPI_DEVICE_SELECTOR = "level_zero:0"   # pin Arc B60, never the RTX 2070
$env:ZES_ENABLE_SYSMAN      = "1"
$env:SYCL_CACHE_PERSISTENT  = "1"
$SW = "V:\AI\llama-swap"
Set-Location $SW
& "$SW\llama-swap.exe" --config "V:\AI\llama-swap\models.yaml" --listen 0.0.0.0:9090 *> "V:\AI\logs\llama-swap.log"
