<#
.SYNOPSIS
  One-shot installer for a local LLM server on an Intel Arc GPU (Battlemage B-series, e.g. B60 24GB).
  Sets up: IPEX-LLM llama.cpp (SYCL) + mainline llama.cpp (Vulkan) + llama-swap + a LiteLLM gateway,
  a default Gemma 3 model, autostart scheduled tasks, and a firewall rule. OpenAI-compatible endpoint.

.DESCRIPTION
  Encodes the hard-won Arc-on-Windows lessons:
   - GPU compute only works in an INTERACTIVE session (tasks use LogonType Interactive).
   - llama-server with -ngl 999 (the IPEX *ollama* scheduler keeps KV on CPU -> unusably slow).
   - Mainline GGUFs (ollama's don't load in the IPEX build).
   - This IPEX SYCL build: no flash-attn / no KV-quant -> f16 KV + small -ub for long context.
   - Vulkan build (mainline) for newer archs (gpt-oss, Qwen3-VL); it enumerates only the Arc.

  Modes:
   - Default / -Minimal: Gemma 3 12B only, 2 llama-swap entries, 2 gateway aliases
     (local-chat, local-vision), tasks ArcLLM-Swap / ArcLLM-Gateway.
   - -Full: writes the full live roster — all 12 models from llama-swap/models.yaml
     and all 14 local gateway aliases from gateway/config.yaml — and registers
     the B60-Swap / B60-Gateway task names used in STATUS.md. Only the default
     model is downloaded; other models are configured and must be downloaded
     separately into $Root\models (see the model file names in the generated
     models.yaml). Paid aliases (coding / orchestration) are included in the
     gateway config but stay inert until ANTHROPIC_API_KEY is set in
     $Root\gateway\.env.

  Note on engine paths: this installer extracts the SYCL engine to
  $Root\llama-cpp-ipex and the Vulkan engine to $Root\llama-cpp-vulkan.
  The live host's llama-swap/models.yaml in the repo uses V:\AI\llama-cpp\
  for SYCL models — that path drift is documented in tests, not changed here
  without live-host verification.

.EXAMPLE
  # one-liner:
  #   iex "& { $(irm https://raw.githubusercontent.com/dirtysouthalpha/intel-arc-llm-stack/main/install.ps1) } -Root C:\arc-llm"
  .\install.ps1 -Root C:\arc-llm
  .\install.ps1 -Root C:\arc-llm -Full
#>
[CmdletBinding()]
param(
  [string]$Root = "C:\arc-llm",
  [string]$Model = "gemma-3-12b",            # default model to pull
  [int]$GatewayPort = 4000,
  [int]$SwapPort = 9090,
  [switch]$NoModel,                          # skip the (large) model download
  [switch]$SkipFirewall,
  [switch]$Full,                             # write the full 12-model roster + 14 local aliases
  [switch]$Minimal                           # explicit Gemma-only fast path (the default)
)
$ErrorActionPreference = "Stop"
function Say($m){ Write-Host "[arc-llm] $m" -ForegroundColor Cyan }

# --- 0. Preflight: Intel Arc present? ---
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "Intel.*Arc" }
if (-not $gpu) { throw "No Intel Arc GPU detected. This installer targets Intel Arc (Battlemage)." }
Say "GPU: $($gpu.Name)  driver $($gpu.DriverVersion)"
# Driver floor from PLAN.md: IPEX-LLM needs >= 31.0.101.5522.
$driverFloor = [Version]"31.0.101.5522"
try {
  $driverVer = [Version]$gpu.DriverVersion
  if ($driverVer -lt $driverFloor) { throw "GPU driver $($gpu.DriverVersion) is below the required $driverFloor. Update the Intel Arc driver and re-run." }
} catch {
  if ($_.Exception.Message -match "below the required") { throw }
  Say "WARNING: could not parse driver version '$($gpu.DriverVersion)'; continuing. Required minimum is $driverFloor."
}
$me = "$env:USERDOMAIN\$env:USERNAME"

# --- 1. Layout ---
foreach($d in "downloads","models","logs","llama-cpp-ipex","llama-cpp-vulkan","llama-swap","gateway","launchers"){
  New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}
Say "Root: $Root"
if ($Full) { Say "Mode: Full — writing all 12 models and 14 local gateway aliases" } else { Say "Mode: Minimal — Gemma 3 12B only (use -Full for the full roster)" }

# --- 2. Engines (pinned, validated versions) ---
$ENGINES = @{
  "ipex"   = "https://github.com/ipex-llm/ipex-llm/releases/download/v2.3.0-nightly/llama-cpp-ipex-llm-2.3.0b20250729-win.zip"
  "vulkan" = "https://github.com/ggml-org/llama.cpp/releases/download/b9544/llama-b9544-bin-win-vulkan-x64.zip"
  "swap"   = "https://github.com/mostlygeek/llama-swap/releases/download/v223/llama-swap_223_windows_amd64.zip"
}
$ProgressPreference = "SilentlyContinue"
function Get-Zip($url,$dest){
  $zip = Join-Path $Root "downloads\$([IO.Path]::GetFileName($url))"
  if(-not (Test-Path $zip)){
    Say "downloading $([IO.Path]::GetFileName($url))"
    $attempt = 0
    while ($true) {
      $attempt++
      try { Invoke-WebRequest $url -OutFile $zip -UseBasicParsing; break } catch {
        if ($attempt -ge 3) { throw "Download failed after 3 attempts: $url — $_" }
        Say "download attempt $attempt failed, retrying in 5s..."
        Start-Sleep -Seconds 5
      }
    }
  }
  Expand-Archive $zip -DestinationPath $dest -Force
  # flatten single top-level dir
  $top = Get-ChildItem $dest
  if($top.Count -eq 1 -and $top[0].PSIsContainer){ Get-ChildItem $top[0].FullName | Move-Item -Destination $dest -Force }
}
Get-Zip $ENGINES.ipex   (Join-Path $Root "llama-cpp-ipex")
Get-Zip $ENGINES.vulkan (Join-Path $Root "llama-cpp-vulkan")
Get-Zip $ENGINES.swap   (Join-Path $Root "llama-swap")

# --- 3. Default model (mainline GGUF) ---
$MODELS = @{
  "gemma-3-12b" = @{
    weights = "https://huggingface.co/ggml-org/gemma-3-12b-it-GGUF/resolve/main/gemma-3-12b-it-Q4_K_M.gguf"
    mmproj  = "https://huggingface.co/ggml-org/gemma-3-12b-it-GGUF/resolve/main/mmproj-model-f16.gguf"
    file    = "gemma-3-12b-it-Q4_K_M.gguf"; proj = "gemma-3-12b-mmproj-f16.gguf"
  }
}
if(-not $NoModel){
  $m = $MODELS[$Model]; if(-not $m){ throw "Unknown model '$Model'." }
  foreach($pair in @(@($m.weights,$m.file), @($m.mmproj,$m.proj))){
    $out = Join-Path $Root "models\$($pair[1])"
    if(-not (Test-Path $out)){ Say "downloading model $($pair[1]) (large)"; & curl.exe -L --retry 3 -o $out $pair[0] }
  }
}

# --- 4. Configs (ASCII; LiteLLM reads YAML as cp1252) ---
if ($Full) {
$swapYaml = @"
healthCheckTimeout: 300
models:
  "gemma3-12b":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\gemma-3-12b-it-Q4_K_M.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 65536 -ub 256 -b 1024 -np 1 --no-mmap
    ttl: 1800
  "gemma3-12b-max":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\gemma-3-12b-it-Q4_K_M.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 131072 -ub 64 -b 256 -np 1 --no-mmap
    ttl: 1800
  "gemma3-12b-vision":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\gemma-3-12b-it-Q4_K_M.gguf
      --mmproj $Root\models\gemma-3-12b-mmproj-f16.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 32768 -ub 256 -b 1024 -np 1 --no-mmap
    ttl: 28800
  "gemma3-27b":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\gemma-3-27b-it-Q4_K_M.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 32768 -ub 64 -b 256 -np 1 --no-mmap
    ttl: 1800
  "gemma3-27b-vision":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\gemma-3-27b-it-Q4_K_M.gguf
      --mmproj $Root\models\gemma-3-27b-mmproj-f16.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 16384 -ub 64 -b 256 -np 1 --no-mmap
    ttl: 1800
  "qwen3-30b":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 32768 -ub 256 -b 1024 -np 1 --no-mmap
    ttl: 1800
  "qwen2.5-coder-32b":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 16384 -ub 64 -b 256 -np 1 --no-mmap
    ttl: 1800
  "qwen2.5-vl-7b":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf
      --mmproj $Root\models\Qwen2.5-VL-7B-mmproj-F16.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 32768 -ub 256 -b 1024 -np 1 --no-mmap
    ttl: 1800
  "gpt-oss-20b":
    cmd: >
      $Root\llama-cpp-vulkan\llama-server.exe -m $Root\models\gpt-oss-20b-mxfp4.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 16384 --jinja -np 1 --no-mmap
    ttl: 1800
  "qwen3-vl-8b":
    cmd: >
      $Root\llama-cpp-vulkan\llama-server.exe -m $Root\models\Qwen3-VL-8B-Instruct-Q4_K_M.gguf
      --mmproj $Root\models\Qwen3-VL-8B-mmproj-F16.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 32768 -fit off -np 1 --no-mmap
    ttl: 1800
  "qwen2.5-omni":
    cmd: >
      $Root\llama-cpp-vulkan\llama-server.exe -m $Root\models\Qwen2.5-Omni-7B-Q4_K_M.gguf
      --mmproj $Root\models\Qwen2.5-Omni-7B-mmproj-f16.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 32768 -np 1 --no-mmap
    ttl: 1800
  # Qwen3.8-27B - latest open Qwen (Apache-2.0), Sentinel lane. Q4 ~17-18GB, fits the B60.
  # Mainline Vulkan binary, with --jinja like gpt-oss-20b. Text-only: no --mmproj line,
  # the mmproj filename for this model is NOT verified yet.
  "qwen3.8-27b":
    cmd: >
      $Root\llama-cpp-vulkan\llama-server.exe -m $Root\models\Qwen3.8-27B-Q4_K_M.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 16384 --jinja -np 1 --no-mmap
    ttl: 1800
"@
$gwYaml = @"
model_list:
  - model_name: local-chat
    litellm_params: { model: openai/gemma3-12b-vision, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: local-vision
    litellm_params: { model: openai/gemma3-12b-vision, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: gemma-12b
    litellm_params: { model: openai/gemma3-12b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: gemma-12b-max
    litellm_params: { model: openai/gemma3-12b-max, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: gemma-27b
    litellm_params: { model: openai/gemma3-27b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: gemma-27b-vision
    litellm_params: { model: openai/gemma3-27b-vision, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: qwen3-30b
    litellm_params: { model: openai/qwen3-30b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: local-coding
    litellm_params: { model: openai/qwen2.5-coder-32b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: qwen2.5-vl
    litellm_params: { model: openai/qwen2.5-vl-7b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: gpt-oss-20b
    litellm_params: { model: openai/gpt-oss-20b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: qwen3-vl
    litellm_params: { model: openai/qwen3-vl-8b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: omni
    litellm_params: { model: openai/qwen2.5-omni, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: qwen3.8-27b
    litellm_params: { model: openai/qwen3.8-27b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: sentinel-local
    litellm_params: { model: openai/qwen3.8-27b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: coding
    litellm_params: { model: anthropic/claude-sonnet-4-6, api_key: os.environ/ANTHROPIC_API_KEY }
  - model_name: orchestration
    litellm_params: { model: anthropic/claude-opus-4-8, api_key: os.environ/ANTHROPIC_API_KEY }
litellm_settings: { default_fallbacks: ["local-chat", "qwen3.8-27b"], drop_params: true }
general_settings: { master_key: os.environ/LITELLM_MASTER_KEY }
"@
} else {
$swapYaml = @"
healthCheckTimeout: 300
models:
  "gemma3-12b":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\gemma-3-12b-it-Q4_K_M.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 65536 -ub 256 -b 1024 -np 1 --no-mmap
    ttl: 1800
  "gemma3-12b-vision":
    cmd: >
      $Root\llama-cpp-ipex\llama-server.exe -m $Root\models\gemma-3-12b-it-Q4_K_M.gguf
      --mmproj $Root\models\gemma-3-12b-mmproj-f16.gguf
      -ngl 999 --host 127.0.0.1 --port `${PORT} -c 32768 -ub 256 -b 1024 -np 1 --no-mmap
    ttl: 1800
"@
$gwYaml = @"
model_list:
  - model_name: local-chat
    litellm_params: { model: openai/gemma3-12b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: local-vision
    litellm_params: { model: openai/gemma3-12b-vision, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
litellm_settings: { default_fallbacks: ["local-chat"], drop_params: true }
general_settings: { master_key: os.environ/LITELLM_MASTER_KEY }
"@
}
[IO.File]::WriteAllText("$Root\llama-swap\models.yaml", $swapYaml, [Text.Encoding]::ASCII)
[IO.File]::WriteAllText("$Root\gateway\config.yaml", $gwYaml, [Text.Encoding]::ASCII)

$key = "sk-arc-" + ([guid]::NewGuid().ToString("N").Substring(0,24))
[IO.File]::WriteAllText("$Root\gateway\.env", "LITELLM_MASTER_KEY=$key`nANTHROPIC_API_KEY=", [Text.Encoding]::ASCII)

# --- 5. Launchers ---
$swapLauncher = @"
`$env:ONEAPI_DEVICE_SELECTOR='level_zero:0'; `$env:ZES_ENABLE_SYSMAN='1'; `$env:SYCL_CACHE_PERSISTENT='1'
Set-Location '$Root\llama-swap'
& '$Root\llama-swap\llama-swap.exe' --config '$Root\llama-swap\models.yaml' --listen 0.0.0.0:$SwapPort *> '$Root\logs\llama-swap.log'
"@
[IO.File]::WriteAllText("$Root\launchers\start-swap.ps1", $swapLauncher, [Text.Encoding]::UTF8)
$gwLauncher = @"
Get-Content '$Root\gateway\.env' | ForEach-Object { if(`$_ -match '^\s*([^#=]+)=(.*)$'){ Set-Item -Path ('env:'+`$matches[1].Trim()) -Value `$matches[2].Trim() } }
& '$Root\gateway\venv\Scripts\litellm.exe' --config '$Root\gateway\config.yaml' --host 0.0.0.0 --port $GatewayPort
"@
[IO.File]::WriteAllText("$Root\launchers\start-gateway.ps1", $gwLauncher, [Text.Encoding]::UTF8)

# --- 6. Gateway venv + LiteLLM ---
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if(-not $py){ throw "Python not found on PATH. Install Python 3.10+ and re-run." }
Say "creating gateway venv + installing litellm (this takes a few minutes)"
& $py -m venv "$Root\gateway\venv"
& "$Root\gateway\venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
$pipAttempt = 0
while ($true) {
  $pipAttempt++
  & "$Root\gateway\venv\Scripts\python.exe" -m pip install --quiet "litellm[proxy]==1.108.11"
  if ($LASTEXITCODE -eq 0) { break }
  if ($pipAttempt -ge 3) { throw "pip install litellm[proxy]==1.108.11 failed after 3 attempts." }
  Say "pip install attempt $pipAttempt failed, retrying in 5s..."
  Start-Sleep -Seconds 5
}
# NOTE: LiteLLM is pinned to the 1.108.11 LTS release (Nov 17, 2026, per the
# official LiteLLM release notes). Not yet validated on the live B60 — bump
# the pin only after a version is confirmed working there. Engine zip SHA256
# checks are likewise not added here — no verified checksums are recorded
# in the repo.

# --- 7. Scheduled tasks (INTERACTIVE session = GPU works) ---
function Register-Svc($name,$file,[switch]$Startup){
  $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File $file"
  $p = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Highest
  $t = if($Startup){ New-ScheduledTaskTrigger -AtStartup } else { New-ScheduledTaskTrigger -AtLogOn -User $me }
  $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
  Register-ScheduledTask -TaskName $name -Action $a -Principal $p -Trigger $t -Settings $set -Force | Out-Null
  Start-ScheduledTask -TaskName $name
}
if ($Full) {
  Register-Svc "B60-Swap"    "$Root\launchers\start-swap.ps1"
  Register-Svc "B60-Gateway" "$Root\launchers\start-gateway.ps1" -Startup
} else {
  Register-Svc "ArcLLM-Swap"    "$Root\launchers\start-swap.ps1"
  Register-Svc "ArcLLM-Gateway" "$Root\launchers\start-gateway.ps1"
}

# --- 8. Firewall ---
if(-not $SkipFirewall -and -not (Get-NetFirewallRule -DisplayName "Arc LLM Gateway" -ErrorAction SilentlyContinue)){
  New-NetFirewallRule -DisplayName "Arc LLM Gateway" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $GatewayPort | Out-Null
}

Say "DONE."
if ($Full) {
  Say "Full roster installed: 12 models configured, 14 local gateway aliases. Only the default Gemma model was downloaded — download other model GGUFs into $Root\models before calling those aliases."
}
Say "Endpoint: http://<this-host>:$GatewayPort/v1   (model: local-chat / local-vision)"
Say "API key : $key"
Say "Test    : curl http://127.0.0.1:$GatewayPort/v1/chat/completions -H 'Authorization: Bearer $key' -d '{\"model\":\"local-chat\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}'"
