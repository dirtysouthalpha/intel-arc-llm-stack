# Benchmark results — Intel Arc Pro B60 (24GB)

Hardware: HOMESERVER, Arc Pro B60 24GB (Battlemage), driver 32.0.101.8517, oneAPI 2025.1.
All numbers in the **interactive session (session 1)**; engine pinned to `level_zero:0`.

## Engine comparison — Gemma 3 12B (Q4_K_M, ~6.8GB)

| Engine | Config | Generation | Notes |
|---|---|---|---|
| IPEX-LLM **ollama** | num_gpu=999 | **0.8 tok/s** | Scheduler misdetects VRAM → KV+compute on CPU; weights on GPU → PCIe thrash. Unusable for big models. |
| IPEX-LLM **llama-server** | `-ngl 999`, ctx 8192 | **33.6 tok/s** | Full 49/49 layers on GPU (`SYCL0 buffer 6.95GB`). 42× faster. **This is the engine.** |

llama-bench (same model): prompt processing `pp512 = 84 tok/s` (SYCL).

## Decisions
- **Heavy models → `llama-server`** (IPEX-LLM llama.cpp portable), one model per process,
  orchestrated by **llama-swap** for multi-model behind one OpenAI port.
- **Use mainline GGUFs** (ggml-org/unsloth/bartowski) — ollama's GGUFs fail to load
  (`gemma3.attention.layer_norm_rms_epsilon` missing).
- **Port 8088** for llama-server (8080 collides with qBittorrent's WebUI API).
- Keep IPEX-LLM **ollama on 11500** only for quick small-model convenience.
