# arc-b60-llm

Tooling to fully use an **Intel Arc Pro B60 (24GB, Battlemage)** for local LLMs —
maximum context, full 24GB utilization, and a local-first cost policy that keeps
everyday + vision inference on the GPU and reserves paid APIs for coding/orchestration.

Built for **HOMESERVER** (Windows Server 2025) and deployed to `V:\AI`, but intended
to help anyone with an Arc B-series card. See [PLAN.md](PLAN.md) and [MODELS.md](MODELS.md).

## Install (one command)
On a Windows box with an Intel Arc GPU + Python 3.10+:
```powershell
iex "& { $(irm https://raw.githubusercontent.com/REPLACE_ME/arc-b60-llm/main/install.ps1) } -Root C:\arc-llm"
```
This downloads the engines (IPEX-LLM SYCL + mainline Vulkan llama.cpp + llama-swap), a default
Gemma 3 model, sets up the LiteLLM gateway, registers autostart tasks, and opens the firewall.
When it finishes it prints your endpoint + API key. (Run from an interactive session - Arc GPU
compute is not available to background services.)

## Layout
- `vram-budget/` — `vram_budget.py`, the max-`num_ctx` calculator (KV-cache + sliding-window aware).
- `recipes/` — Ollama Modelfiles (and later vLLM configs) tuned for max context per model.
- `launchers/` — start scripts that pin the Arc (`ONEAPI_DEVICE_SELECTOR=level_zero:0`).
- `gateway/` — LiteLLM config: one OpenAI endpoint with local-first cost routing.
- `bench/` — throughput + long-context verification.

## Key gotchas learned (Arc on Windows) — the hard-won part
1. **Run the engine in an interactive session (session 1), not a session-0 service.**
   Intel GPU *compute* isn't reachable from session 0, so it silently falls back to CPU
   (3.4 tok/s, `100% CPU`). The scheduled tasks use `LogonType Interactive`.
2. **Pin the device** to `level_zero:0` so inference never lands on the secondary RTX 2070.
   (The Intel runtime only enumerates the Arc, so this also guarantees isolation.)
3. **Don't use IPEX-LLM *ollama* for big models.** Its scheduler misdetects Arc VRAM
   (reports ~4–13 GiB), logs `layers.offload=0`, and puts weights on the GPU but the
   **KV cache + compute graph on CPU** → constant PCIe thrash → **0.8 tok/s on Gemma 12B**.
   Forcing `num_gpu` doesn't override it. Use **IPEX-LLM `llama-server`** instead, where
   `-ngl 999` reliably offloads everything (weights + KV).
4. **ollama's GGUFs don't load in IPEX-LLM llama.cpp.** ollama writes Gemma 3 with its own
   metadata; mainline llama.cpp errors with
   `key not found in model: gemma3.attention.layer_norm_rms_epsilon`.
   Use **mainline GGUFs from HuggingFace** (ggml-org / unsloth / bartowski) instead.
5. The IPEX-LLM Ollama (kept for convenience/small models) runs on **port 11500**, separate
   from stock Ollama (`11434`, RTX 2070). `llama-server` for the heavy models runs on **8080**.

## Deploying config changes
Copy files to `V:\AI\...` with **SCP** (`Set-SCPItem`), not inline base64-over-SSH — the latter
truncates files larger than ~2KB at the Windows command-line limit (silently dropped our extra
model entries once). After a config change, restart cleanly with `launchers/restart-stack.ps1`
(stopping a scheduled task leaves its spawned child process running).

## Quick start (on HOMESERVER)
```powershell
# Engine is auto-started by the 'B60-IPEX-Ollama' scheduled task (interactive session).
ollama create gemma3-12b-max -f recipes/gemma3-12b-max.Modelfile
# then point clients at the LiteLLM gateway on :4000
```
