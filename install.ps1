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

.EXAMPLE
  # one-liner:
  #   iex "& { $(irm https://raw.githubusercontent.com/dirtysouthalpha/intel-arc-llm-stack/main/install.ps1) } -Root C:\arc-llm"
  .\install.ps1 -Root C:\arc-llm
#>
[CmdletBinding()]
param(
  [string]$Root = "C:\arc-llm",
  [string]$Model = "gemma-3-12b",            # default model to pull
  [int]$GatewayPort = 4000,
  [int]$SwapPort = 9090,
  [switch]$NoModel,                          # skip the (large) model download
  [switch]$SkipFirewall
)
$ErrorActionPreference = "Stop"
function Say($m){ Write-Host "[arc-llm] $m" -ForegroundColor Cyan }

# --- 0. Preflight: Intel Arc present? ---
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "Intel.*Arc" }
if (-not $gpu) { throw "No Intel Arc GPU detected. This installer targets Intel Arc (Battlemage)." }
Say "GPU: $($gpu.Name)  driver $($gpu.DriverVersion)"
$me = "$env:USERDOMAIN\$env:USERNAME"

# --- 1. Layout ---
foreach($d in "downloads","models","logs","llama-cpp-ipex","llama-cpp-vulkan","llama-swap","gateway","launchers"){
  New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}
Say "Root: $Root"

# --- 2. Engines (pinned, validated versions) ---
$ENGINES = @{
  "ipex"   = "https://github.com/ipex-llm/ipex-llm/releases/download/v2.3.0-nightly/llama-cpp-ipex-llm-2.3.0b20250729-win.zip"
  "vulkan" = "https://github.com/ggml-org/llama.cpp/releases/download/b9544/llama-b9544-bin-win-vulkan-x64.zip"
  "swap"   = "https://github.com/mostlygeek/llama-swap/releases/download/v223/llama-swap_223_windows_amd64.zip"
}
$ProgressPreference = "SilentlyContinue"
function Get-Zip($url,$dest){
  $zip = Join-Path $Root "downloads\$([IO.Path]::GetFileName($url))"
  if(-not (Test-Path $zip)){ Say "downloading $([IO.Path]::GetFileName($url))"; Invoke-WebRequest $url -OutFile $zip -UseBasicParsing }
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
[IO.File]::WriteAllText("$Root\llama-swap\models.yaml", $swapYaml, [Text.Encoding]::ASCII)

$key = "sk-arc-" + ([guid]::NewGuid().ToString("N").Substring(0,24))
$gwYaml = @"
model_list:
  - model_name: local-chat
    litellm_params: { model: openai/gemma3-12b, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
  - model_name: local-vision
    litellm_params: { model: openai/gemma3-12b-vision, api_base: http://127.0.0.1:$SwapPort/v1, api_key: "swap" }
litellm_settings: { default_fallbacks: ["local-chat"], drop_params: true }
general_settings: { master_key: os.environ/LITELLM_MASTER_KEY }
"@
[IO.File]::WriteAllText("$Root\gateway\config.yaml", $gwYaml, [Text.Encoding]::ASCII)
[IO.File]::WriteAllText("$Root\gateway\.env", "LITELLM_MASTER_KEY=$key`nANTHROPIC_API_KEY=`n", [Text.Encoding]::ASCII)

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
& "$Root\gateway\venv\Scripts\python.exe" -m pip install --quiet "litellm[proxy]"

# --- 7. Scheduled tasks (INTERACTIVE session = GPU works) ---
function Register-Svc($name,$file,[switch]$Startup){
  $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File $file"
  $p = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Highest
  $t = if($Startup){ New-ScheduledTaskTrigger -AtStartup } else { New-ScheduledTaskTrigger -AtLogOn -User $me }
  $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
  Register-ScheduledTask -TaskName $name -Action $a -Principal $p -Trigger $t -Settings $set -Force | Out-Null
  Start-ScheduledTask -TaskName $name
}
Register-Svc "ArcLLM-Swap"    "$Root\launchers\start-swap.ps1"
Register-Svc "ArcLLM-Gateway" "$Root\launchers\start-gateway.ps1"

# --- 8. Firewall ---
if(-not $SkipFirewall -and -not (Get-NetFirewallRule -DisplayName "Arc LLM Gateway" -ErrorAction SilentlyContinue)){
  New-NetFirewallRule -DisplayName "Arc LLM Gateway" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $GatewayPort | Out-Null
}

Say "DONE."
Say "Endpoint: http://<this-host>:$GatewayPort/v1   (model: local-chat / local-vision)"
Say "API key : $key"
Say "Test    : curl http://127.0.0.1:$GatewayPort/v1/chat/completions -H 'Authorization: Bearer $key' -d '{\"model\":\"local-chat\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}'"
