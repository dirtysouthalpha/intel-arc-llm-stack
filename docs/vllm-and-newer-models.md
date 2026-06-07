# vLLM / gpt-oss / Qwen3-VL on the B60 - status & path

## vLLM via WSL2: BLOCKED (Battlemage driver immaturity)
- WSL2 Ubuntu-24.04 has `/dev/dxg` (GPU paravirt) but Intel's apt "client" channel for noble
  installs compute-runtime **24.39** (`intel-opencl-icd 24.39.31294`, `libze-intel-gpu1 24.39`).
- `clinfo -l` returns **no devices** -> 24.39 doesn't recognize the Arc **B60 (Battlemage)**.
  BMG support needs compute-runtime **25.x**, not yet in that channel.
- Conclusion: vLLM XPU / Intel LLM-Scaler in WSL is not viable until newer runtime `.deb`s are
  hand-installed (igc + level-zero + compute-runtime version-matched) or the channel updates.

## Why the IPEX llama.cpp build can't run gpt-oss / Qwen3-VL
- The IPEX-LLM llama.cpp portable is pinned to **b20250729**, which predates gpt-oss (Aug 2025)
  and Qwen3-VL llama.cpp support.

## Recommended path: newer MAINLINE llama.cpp Windows SYCL build
- Mainline llama.cpp now supports gpt-oss and Qwen3-VL and ships Windows **SYCL** release zips.
- We have **oneAPI 2025.1** installed natively, so a mainline SYCL build should run on the B60
  using the same session-1 + llama-swap pattern (just a second llama-server binary for the
  newer-arch models, registered as extra llama-swap entries).
- Trade-off: mainline SYCL lacks IPEX's Battlemage-tuned kernels, so expect somewhat lower
  throughput than the IPEX build gets on Gemma/Qwen2.5 - acceptable for unlocking new models.

## RESULT: mainline Vulkan works - gpt-oss-20b is live
- Downloaded `llama-b9544-bin-win-vulkan-x64.zip` -> `V:\AI\llama-cpp-vulkan`.
- `llama-server --list-devices` enumerates **only** `Vulkan0: Intel Arc Pro B60 (24380 MiB)`
  (the RTX 2070 doesn't appear) -> device selection is automatic and safe.
- **gpt-oss-20b (MXFP4, ~12GB) loads and generates on the B60 via Vulkan** (`-ngl 999 -c 16384 --jinja`).
  Gotcha: drop `-fa` (Vulkan flash-attn + gpt-oss MoE crashed llama-swap's spawn).
- So newer archs use the Vulkan binary; Gemma/Qwen2.5 stay on the IPEX SYCL binary (Battlemage-tuned).
- vLLM/WSL is NOT needed for these models. (vLLM would still help for high-concurrency serving later.)

## Qwen3-VL + Qwen2.5-Omni (Vulkan) - DONE
- **Qwen3-VL-8B**: works on Vulkan, but ONLY with **`-fit off`** (the new auto memory-fit step
  crashes with `EXITCODE -1` during "fitting params to device memory" on this build). With it off:
  loads + answers image queries ("Red circle.", 12s).
- **Qwen2.5-Omni-7B**: text + image + **audio** + video. Loads on Vulkan; vision verified.
  Audio via OpenAI `input_audio` content type (base64 wav) through llama-server's mtmd.
- Download latest `llama-*-bin-win-sycl-x64.zip` from llama.cpp releases -> `V:\AI\llama-cpp-main`.
- Smoke-test on the B60 (ONEAPI_DEVICE_SELECTOR=level_zero:0, session 1).
- If good: pull gpt-oss-20b GGUF + Qwen3-VL GGUF, add llama-swap entries using the mainline binary.
