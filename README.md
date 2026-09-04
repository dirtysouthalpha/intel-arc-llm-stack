# intel-arc-llm-stack

**Run any LLM — Gemma, Qwen3 MoE, gpt-oss, vision *and* audio — locally on an Intel Arc GPU.**
One OpenAI-compatible endpoint, on-demand model swapping, a cost-routing gateway, and a one-line installer.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
Built and battle-tested on an **Intel Arc Pro B60 (24GB, Battlemage)** on Windows.

---

## Why this exists
The Intel Arc software stack for LLMs is young and full of sharp edges. This repo is the result of
working through every one of them so you don't have to — and packaging the result so anyone with an
Arc card gets a working multi-model server in one command.

## What you get
- 🧠 **MoE + dense reasoning** — Qwen3-30B-A3B, gpt-oss-20b, Gemma 3 12B/27B
- 👁️ **Vision** — Gemma 3, Qwen2.5-VL, Qwen3-VL (screenshots, OCR, visual Q&A)
- 🔊 **Audio** — Qwen2.5-Omni transcribes/understands speech
- 📜 **Huge context** — Gemma 3 12B at the **full 128K** window (needle-test verified)
- 💸 **Local-first cost routing** — everyday + vision stay free on the GPU; paid APIs are opt-in
- 🔌 **One OpenAI endpoint** — point any app/IDE/agent at it; models hot-swap on demand
- ♻️ **Autostart** — survives reboot via scheduled tasks

## Install (one command)
On a Windows box with an Intel Arc GPU + Python 3.10+ (run from an interactive session):
```powershell
iex "& { $(irm https://raw.githubusercontent.com/dirtysouthalpha/intel-arc-llm-stack/main/install.ps1) } -Root C:\arc-llm"
```
It downloads the engines (IPEX-LLM SYCL + mainline Vulkan llama.cpp + llama-swap), a default Gemma 3
model, sets up the LiteLLM gateway, registers autostart tasks, opens the firewall, and prints your
endpoint + API key.

## Use it
```bash
curl http://<host>:4000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"local-chat","messages":[{"role":"user","content":"hi"}]}'
```
Model aliases: `local-chat`, `local-vision`, `gemma-12b-max` (128K), `qwen3-30b` (MoE),
`gpt-oss-20b`, `qwen3-vl`, `omni` (audio), `local-coding`, and opt-in paid `coding`/`orchestration`.

## How it works
```
your apps ──> LiteLLM gateway (:4000, cost routing) ──> llama-swap (:9090, hot-swap)
                                                          ├─ llama-server (IPEX SYCL)  Gemma/Qwen2.5
                                                          └─ llama-server (Vulkan)     gpt-oss/Qwen3-VL/Omni
                                                                      └─ Intel Arc GPU
```

## The sharp edges (so you skip the pain) — see [docs/](docs) + [bench/results.md](bench/results.md)
1. **GPU compute only works in an interactive session** (session 1), not a session-0 service —
   otherwise it silently falls back to CPU. The scheduled tasks use `LogonType Interactive`.
2. **Use `llama-server -ngl 999`, not IPEX-LLM *ollama*** — ollama's scheduler keeps the KV cache on
   CPU on big models (0.8 tok/s vs 33 tok/s).
3. **Use mainline GGUFs** (ggml-org/unsloth) — ollama's GGUFs fail to load in the IPEX build.
4. **IPEX SYCL build:** no flash-attn / no KV-quant (both crash) → f16 KV + small `-ub` for long ctx.
5. **Newer archs (gpt-oss, Qwen3-VL, Omni):** use the **mainline Vulkan** binary (enumerates only the
   Arc). gpt-oss: drop `-fa`. Qwen3-VL: add `-fit off`.
6. **Deploy configs with SCP**, not inline base64-over-SSH (truncates >~2KB). LiteLLM YAML must be ASCII.

## Layout
- `install.ps1` — the one-line installer.
- `vram-budget/` — max-`num_ctx` calculator (KV-cache + sliding-window aware).
- `launchers/` — start scripts (device-pinned to the Arc) + `restart-stack.ps1`.
- `llama-swap/models.yaml` — model definitions. `gateway/config.yaml` — LiteLLM cost routing.
- `bench/` — throughput + long-context needle test + results.
- `docs/` — vLLM/Vulkan notes, Sentinel-style router integration.

## License
MIT — built to help everyone with these cards. PRs welcome (more models, more Arc SKUs, perf tuning).

---

## Support this project

Built and maintained by one person, in the open. If it saves you time or
money, you can throw something in the hat — entirely optional, and it changes
nothing about the license or what ships.

<a href="https://cash.app/$vladien"><img src="docs/assets/donate-cashapp.png" alt="Cash App donation QR code for $vladien" width="170" align="left" hspace="18" vspace="6"></a>

**Cash App — [$vladien](https://cash.app/$vladien)**

Scan the code, or follow the link.

No tiers, no paywalled features, no "pro" build.

<br clear="left">