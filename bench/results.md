# Benchmark results — Intel Arc Pro B60 (24GB)

Hardware: HOMESERVER, Arc Pro B60 24GB (Battlemage), driver 32.0.101.8517, oneAPI 2025.1.
All numbers in the **interactive session (session 1)**; engine pinned to `level_zero:0`.

## Engine comparison — Gemma 3 12B (Q4_K_M, ~6.8GB)

| Engine | Config | Generation | Notes |
|---|---|---|---|
| IPEX-LLM **ollama** | num_gpu=999 | **0.8 tok/s** | Scheduler misdetects VRAM → KV+compute on CPU; weights on GPU → PCIe thrash. Unusable for big models. |
| IPEX-LLM **llama-server** | `-ngl 999`, ctx 8192 | **33.6 tok/s** | Full 49/49 layers on GPU (`SYCL0 buffer 6.95GB`). 42× faster. **This is the engine.** |

llama-bench (same model): prompt processing `pp512 = 84 tok/s` (SYCL).

## Long-context findings on this IPEX SYCL build (b20250729)
- **Flash attention is broken**: `-fa` (with or without KV quant) falls back to a CPU op and
  crashes at warmup — `GGML_ASSERT(nbv0 == ggml_type_size(v->type))` in `ggml-cpu/ops.cpp`.
  The SYCL backend has no FA kernel in this build. Keep FA **off**.
- **Quantized KV (`-ctk/-ctv q8_0`) also crashes** the same way. Use **f16 KV**.
- Without FA, the attention **compute buffer explodes with context**: ~36 GB at 128K / ub=512 →
  alloc fails. It scales with `ubatch × ctx`, so **lower `-ub`** to fit (e.g., `-ub 64` ≈ 4.5 GB).
- Gemma 3 KV stays modest via sliding-window: f16 KV @128K ≈ 9.8 GB (8.2 global + 1.6 SWA).
- Net recipe for max context on this build: **f16 KV, no FA, small `-ub`.**

## Verified models (llama-server on B60, via llama-swap/gateway)
| Model | Role | Verified |
|---|---|---|
| Gemma 3 12B | chat 64K / max 128K / vision | gen 33 tok/s; needle@16K PASS (17,640 tok) |
| Gemma 3 27B | larger chat 32K / vision | accurate gen |
| Qwen3-30B-A3B | **MoE** reasoning + tools | accurate gen |
| Qwen2.5-Coder-32B | local coding | correct code gen |
| Qwen2.5-VL-7B | fast vision | accurate image description (32s load) |

Long-context needle-in-haystack @ ~16K: **PASS** (retrieved hidden passcode).

## Decisions
- **Heavy models → `llama-server`** (IPEX-LLM llama.cpp portable), one model per process,
  orchestrated by **llama-swap** for multi-model behind one OpenAI port.
- **Use mainline GGUFs** (ggml-org/unsloth/bartowski) — ollama's GGUFs fail to load
  (`gemma3.attention.layer_norm_rms_epsilon` missing).
- **Port 8088** for llama-server (8080 collides with qBittorrent's WebUI API).
- Keep IPEX-LLM **ollama on 11500** only for quick small-model convenience.
