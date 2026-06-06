# Plan: Fully utilize the Intel Arc Pro B60 (24GB) for all LLMs

## Context

HOMESERVER (`100.70.240.55`, Windows Server 2025, Ryzen 7 2700X, 32GB RAM) has an **Intel Arc Pro B60 (24GB VRAM, Battlemage/Xe2)** that is currently **completely idle for LLM work**. The existing stock Ollama 0.24.0 only supports CUDA/ROCm/Metal, so it runs on the secondary **NVIDIA RTX 2070 (8GB)** — too small for the models we want.

Goal: build the tooling to run **any LLM on the B60**, with three explicit priorities from the user:
1. **Maximize usable context length** ("max tokens possible") per model.
2. **Fully saturate the 24GB** — custom quantized models are welcome.
3. **Local-first cost policy** — route everyday inference (and the always-on Hermes desktop agent) to the **local B60/Gemma**, and spend **paid APIs (Claude/etc.) only on coding and orchestration** when actually needed.

Concrete targets: **Gemma-class 12B and ~27–35B** (note: current released line is Gemma 3 — 12B/27B; "Gemma 4"/35B not yet released, recipes will be templated for it). Gemma 3 is **multimodal**, which matters below.

### Primary integration target: Hermes
`C:\hermes-bridge` is the live service — a **FastAPI desktop-automation A2A agent** ("Hermes A2A Agent — Desktop Automation for PremierBot", port **8478**). It already speaks **OpenAI protocol via the `openai` SDK**, fully driven by `.env`: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_VISION_MODEL`. So wiring Gemma in is **config-only** (repoint base_url/model) — **no Hermes code changes**. Because Hermes also needs vision (it screenshots the desktop), and **Gemma 3 is multimodal**, a single Gemma 3 model serves both `LLM_MODEL` and `LLM_VISION_MODEL`, displacing paid vision calls on a high-volume workload.

Secondary integration: the **Sentinel** master-control dashboard, which already uses **LiteLLM** (`C:\Sentinel\venv`). Access also via **OpenAI-compatible API + Tailscale remote**.

Strategy approved by user: **phased — IPEX-LLM Ollama first, then vLLM**; **max-context precision** (4-bit weights + quantized KV cache); **B60 only** for LLMs (leave RTX 2070 alone).

### Verified environment facts
- GPU driver `32.0.101.8517` ✅ (IPEX-LLM needs ≥ 31.0.101.5522).
- Intel oneAPI Base Toolkit **2025.1** already installed.
- Docker 29.5.2 (WSL2 backend) + WSL2 **Ubuntu-24.04** running; `/dev/dxg` present, but **no Intel compute runtime in WSL yet** (`/dev/dri` empty) — needed for the WSL/vLLM path.
- Disk: **C: 1TB free**, **V: 452GB free**. Use **V:\AI** as the working root (large model files).
- **Both** an Intel Arc and an NVIDIA GPU are present → every launcher MUST force device selection to the Arc (`ONEAPI_DEVICE_SELECTOR=level_zero:0`) so inference never lands on the 2070.
- Stock Ollama already binds **:11434** → new engines use new ports to avoid conflict.

---

## Deliverables (the "tools")

All under a new repo **`V:\AI`** (git-init'd, with README):

1. **`vram-budget/`** — Python calculator: given model params (size, quant bits, layers, GQA kv-heads, head-dim) + KV-cache dtype, outputs the **max `num_ctx` that fits in 24GB** (with a safety margin). The core sizing tool for "max tokens."
2. **`recipes/`** — per-model recipe library: Ollama **Modelfiles** + vLLM **launch configs**, tuned for max context. Includes `gemma3-12b-max`, `gemma3-27b-max`, and a `TEMPLATE` for future Gemma 35B.
3. **`launchers/`** — PowerShell scripts to start each engine with correct Arc device env: `start-ipex-ollama.ps1`, `start-vllm.ps1`, `start-gateway.ps1`, plus `start-all.ps1`.
4. **`gateway/config.yaml`** — **LiteLLM** unified OpenAI-compatible proxy fronting all B60 engines (single `/v1`, model aliases, API key, bound to Tailscale IP).
5. **`bench/`** — benchmark + healthcheck scripts (tokens/sec, time-to-first-token, max-context needle test) producing a per-recipe report.
6. **Sentinel integration** — config change pointing Sentinel's LiteLLM at the B60 models.
7. **Autostart** — NSSM services / Scheduled Tasks so engines + gateway survive reboot.

---

## Phase 1 — Get the B60 serving (IPEX-LLM Ollama, Windows native)

Fastest path; keeps the existing Ollama UX and your model library, GPU-accelerated on the B60.

- Download **IPEX-LLM Ollama Portable Zip** (≥ 2.2.0b, includes Battlemage attention kernels; no conda/oneAPI install needed) → extract to `V:\AI\ipex-ollama\`.
- Launcher `start-ipex-ollama.ps1` sets: `ONEAPI_DEVICE_SELECTOR=level_zero:0`, `OLLAMA_HOST=0.0.0.0:11500` (new port), `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_MODELS=V:\AI\models`, then runs `start-ollama.bat`.
- Validate the **B60 (not the 2070)** is used: Task Manager GPU / `xpu-smi` shows Arc compute load during `ollama run`. (First run does a 2–5 min SYCL kernel compile — expected.)
- Pull Gemma 3 12B + 27B as the proof models.

## Phase 2 — Max-context custom recipes

For each target, compute the weight-quant + KV-cache-dtype + context that maximizes tokens in 24GB (using `vram-budget`), then encode it as a custom Modelfile.

- **Gemma 3 12B**: ~Q4_K_M weights (~7GB) → ~15GB free → with Q8 KV cache + flash attention, target the model's **full 128K context** (verify it fits).
- **Gemma 3 27B**: ~Q4_K_M weights (~16GB) → ~7GB free → Q8/Q4 KV cache + flash attention; push `num_ctx` to the calculated ceiling (likely ~32–64K) and document the context↔precision tradeoff.
- Custom **Modelfiles** set `PARAMETER num_ctx <max>`, `num_gpu 999` (all layers on GPU), and rely on the engine env for flash-attn + KV quant.
- The `vram-budget` tool prints the realistic ceiling so we never silently overflow to shared memory (which kills throughput).

## Phase 3 — vLLM power tier (max throughput + context, Docker/WSL XPU)

vLLM gives paged KV cache + FP8 KV-cache quant = the best context-saturation engine; Intel + vLLM officially support the Arc Pro B-series (`intel/vllm` Docker image).

- Install Intel client-GPU compute runtime **inside WSL2 Ubuntu-24.04** (level-zero for `/dev/dxg`) so the GPU is usable in Linux; verify with `sycl-ls`/`clinfo`.
- Run vLLM via the **`intel/vllm` XPU Docker image** (or native wheel in WSL if Docker GPU passthrough is fiddly), serving on **:8001**.
- Launch flags for max context: `--quantization awq` (4-bit), `--kv-cache-dtype fp8`, `--gpu-memory-utilization 0.92`, `--max-model-len <ceiling>`, `--enforce-eager` off.
- Fallback if WSL GPU passthrough underperforms: IPEX-LLM's own vLLM build, or stay on IPEX-Ollama/llama.cpp for the heavy model.

## Phase 4 — Unified gateway + local-first cost routing + Tailscale

- Stand up **LiteLLM proxy** (`gateway/config.yaml`) as the single OpenAI-compatible front door, routing model aliases → IPEX-Ollama (:11500) and vLLM (:8001). Add a master API key.
- **Cost-routing policy** (core to the user's goal): define aliases so callers pick intent, not vendor:
  - `local-chat`, `local-vision`, `gemma-12b-max`, `gemma-27b-max` → **B60** (default for everyday + Hermes + vision; $0).
  - `coding`, `orchestration` → **paid APIs** (Claude/etc.) — only hit when explicitly requested.
  - Set the local Gemma model as the **default** so anything unspecified stays free.
- Bind to the **Tailscale IP `100.70.240.55`** (already on Tailscale) so `nuke`/laptop reach it; document `tailscale serve` option for HTTPS.
- Result: one `https://100.70.240.55:<port>/v1` endpoint; everyday traffic is local, paid spend is opt-in.

## Phase 5 — Wire into Hermes (primary) + Sentinel (secondary)

- **Hermes** (`C:\hermes-bridge\.env`): set `LLM_BASE_URL` → gateway `/v1`, `LLM_MODEL` → `gemma-27b-max` (or `gemma-12b-max`), `LLM_VISION_MODEL` → the Gemma 3 multimodal alias, `LLM_API_KEY` → gateway key. **No code changes** — restart via `run.bat`. Confirm the desktop-automation loop (screenshot → vision → action) works on local Gemma 3 vision.
- **Sentinel**: read existing LiteLLM/model config under `C:\Sentinel` (+ `.env`); **reuse the existing LiteLLM integration**, register the B60 aliases, set local as preferred for on-prem inference.
- Validate request flow end-to-end for both: app → gateway → B60 → response.

## Phase 6 — Ops: autostart, monitoring, benchmarks

- Register IPEX-Ollama, vLLM, and the gateway as **NSSM services / Scheduled Tasks** (start on boot).
- `bench/` scripts: tokens/sec, TTFT, and a **needle-in-a-haystack test at max `num_ctx`** to prove long context actually works (not just loads). Output a markdown report per recipe.
- `xpu-smi` for live VRAM/utilization monitoring.

---

## Critical files / locations
- **New repo:** `V:\AI\` → `vram-budget/`, `recipes/`, `launchers/`, `gateway/config.yaml`, `bench/`, `models/`, `ipex-ollama/`, `README.md`.
- **Sentinel integration point:** `C:\Sentinel\` LiteLLM config + `.env` (exact file to be read during implementation; LiteLLM confirmed at `C:\Sentinel\venv\Lib\site-packages\litellm`).
- **Do not touch** stock Ollama on :11434 / the RTX 2070 path.

## Verification
1. `xpu-smi` shows **B60** compute + VRAM load (and 2070 idle) during inference.
2. Each Gemma recipe loads at its target `num_ctx` and **passes a long-context needle test** at that length.
3. `curl https://100.70.240.55/.../v1/chat/completions` from **nuke over Tailscale** returns a completion using `gemma-27b-max`.
4. **Hermes** runs its desktop-automation loop entirely on local Gemma 3 (text **and** vision) — verified via a screenshot→action task with `xpu-smi` showing B60 load and **no paid-API calls**.
5. **Sentinel dashboard** produces a response routed through the B60 end-to-end.
6. **Cost-routing**: `local-*` aliases hit the B60 ($0); `coding`/`orchestration` aliases reach paid APIs only when explicitly called.
7. Benchmark report committed: tokens/sec + verified max context per recipe.

## Risks / notes
- **Dual-vendor device selection** is the #1 footgun — every launcher pins `level_zero:0` (Arc).
- **vLLM-in-WSL GPU passthrough** is the least-certain step; Phase 1/2 (native IPEX) delivers value independent of it, and there are fallbacks.
- **Gemma 27B at very long context** may exceed 24GB even 4-bit; the `vram-budget` tool sets honest ceilings (no silent shared-memory spillover).
- **Gemma "4"/35B** isn't released; its recipe is a template — a real 35B at 4-bit (~20GB) leaves little KV room, so it'll need Q3/IQ3 or reduced context (documented when it ships).
