# Troubleshooting

## How to tell which GPU is actually loaded

Use `xpu-smi` while a request is running. It should show compute and VRAM
load on the Intel Arc B60, with the secondary NVIDIA RTX 2070 idle. If the
Arc shows no load, the request is not on the GPU — check the session and
device selection below before changing models or context sizes.

## Session-0 CPU fallback

GPU compute only works in an interactive session (session 1), not in a
session-0 service — otherwise it silently falls back to CPU. The scheduled
tasks use `LogonType Interactive`. If throughput suddenly drops to CPU-like
speeds, check that the swap task is running in session 1, not as a
session-0 service.

## `-ngl 999` vs ollama

Use `llama-server -ngl 999`, not IPEX-LLM ollama. Ollama's scheduler keeps
the KV cache on CPU on big models (0.8 tok/s vs about 33 tok/s with
llama-server on Gemma 3 12B). If you see very low tok/s with weights on
the GPU, you are probably on the ollama path.

## GGUF source

Use mainline GGUFs (ggml-org / unsloth). Ollama's GGUFs fail to load in
the IPEX build (for example, `gemma3.attention.layer_norm_rms_epsilon`
missing).

## Flash attention and KV quant crashes

On the IPEX SYCL build (b20250729), flash attention (`-fa`, with or
without KV quant) and quantized KV (`-ctk` / `-ctv q8_0`) crash at
warmup. Use f16 KV and keep flash attention off. Without flash
attention, the attention compute buffer grows with context — lower `-ub`
to fit (for example, `-ub 64` at 128K).

## Newer archs: gpt-oss, Qwen3-VL, Omni

Use the mainline Vulkan binary, which enumerates only the Arc.
gpt-oss: drop `-fa`. Qwen3-VL: add `-fit off`. These flags are already
in `llama-swap/models.yaml` for those models — if you copy a model
entry, keep them.

## Configs: SCP, not base64

Deploy configs with SCP, not inline base64-over-SSH — inline base64
truncates at about 2 KB. LiteLLM YAML must be ASCII; the repo tests
enforce that for `gateway/config.yaml`.

## Gateway / swap not responding

1. Check the scheduled tasks `B60-Swap` and `B60-Gateway` (or
   `ArcLLM-Swap` / `ArcLLM-Gateway` on a Minimal install) are running.
2. Check the logs under `$Root\logs` (default `C:\arc-llm\logs`).
3. Smoke-test the gateway directly:
   `curl http://127.0.0.1:4000/v1/chat/completions` with a `local-chat`
   request and the master key from `$Root\gateway\.env`.
4. If only one model fails, check its entry in
   `llama-swap/models.yaml` — model file name, mmproj file name, and
   engine binary path (`llama-cpp-ipex` for SYCL models,
   `llama-cpp-vulkan` for Vulkan models).

## Engine-path drift (known, unverified on the live host)

The repo's `llama-swap/models.yaml` uses `V:\AI\llama-cpp\llama-server.exe`
for SYCL models. The installer extracts the SYCL engine to
`$Root\llama-cpp-ipex`. That drift is documented, not changed here —
verify on the live host whether `V:\AI\llama-cpp\` exists separately
before changing either path.
