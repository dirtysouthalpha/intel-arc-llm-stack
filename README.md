# arc-b60-llm

Tooling to fully use an **Intel Arc Pro B60 (24GB, Battlemage)** for local LLMs —
maximum context, full 24GB utilization, and a local-first cost policy that keeps
everyday + vision inference on the GPU and reserves paid APIs for coding/orchestration.

Built for **HOMESERVER** (Windows Server 2025) and deployed to `V:\AI`, but intended
to help anyone with an Arc B-series card. See [PLAN.md](PLAN.md) and [MODELS.md](MODELS.md).

## Layout
- `vram-budget/` — `vram_budget.py`, the max-`num_ctx` calculator (KV-cache + sliding-window aware).
- `recipes/` — Ollama Modelfiles (and later vLLM configs) tuned for max context per model.
- `launchers/` — start scripts that pin the Arc (`ONEAPI_DEVICE_SELECTOR=level_zero:0`).
- `gateway/` — LiteLLM config: one OpenAI endpoint with local-first cost routing.
- `bench/` — throughput + long-context verification.

## Key gotchas learned (Arc on Windows)
1. **Run the engine in an interactive session (session 1), not as a session-0 service** —
   Intel GPU *compute* isn't reachable from session 0, so it silently falls back to CPU.
   (The scheduled task uses `LogonType Interactive`.)
2. **Pin the device** to `level_zero:0` so inference never lands on the secondary RTX 2070.
3. The IPEX-LLM Ollama runs on **port 11500**, separate from stock Ollama (`11434`, RTX 2070).

## Quick start (on HOMESERVER)
```powershell
# Engine is auto-started by the 'B60-IPEX-Ollama' scheduled task (interactive session).
ollama create gemma3-12b-max -f recipes/gemma3-12b-max.Modelfile
# then point clients at the LiteLLM gateway on :4000
```
