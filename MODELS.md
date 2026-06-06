# Model Strategy — Intel Arc Pro B60 (24GB)

Goal: a roster of **Claude/GPT-grade**, **tool-using**, **multimodal** models that run on a single 24GB Arc B60 — favoring **MoE** (fast + high quality) and pushing toward **audio/video**. Everything here is chosen for *Arc compatibility today or with modest dev work*, because the Intel LLM ecosystem is young — which is also our opportunity to build tools others can use.

> Quick myth-bust: **Gemma 3 is dense, not MoE.** What you love about it (speed + quality) is exactly what real MoE models like gpt-oss and Qwen3-30B-A3B do even better. So our flagship picks lean MoE.

VRAM math assumes 24GB total, ~1–2GB reserved, rest split between weights + KV cache. "Fits" = comfortably with usable context.

---

## Tier 1 — Flagship reasoning + tool use (MoE, daily driver)

| Model | Type | Active/Total | Modality | Tools | Arc status | Fit @ 24GB |
|---|---|---|---|---|---|---|
| **gpt-oss-20b** | MoE | 3.6B / 21B | text | excellent (harmony) | ✅ Intel LLM-Scaler vLLM | MXFP4 ~13GB → lots of KV room |
| **Qwen3-30B-A3B** | MoE | 3B / 30B | text | excellent | ✅ (you already run it) | Q4 ~18GB |

- **gpt-oss-20b** is the closest open thing to GPT-style quality + tool-calling at this size, and it's natively MXFP4 so it leaves huge context headroom. **Top pick for the "smart default."**
- **Qwen3-30B-A3B** = your current favorite class; keep as alternate reasoning brain.

## Tier 2 — Vision + tools (VLM)

| Model | Type | Modality | Arc status | Fit @ 24GB |
|---|---|---|---|---|
| **Qwen3-VL** (incl. 30B-A3B MoE VL) | MoE/dense | text+image (+video frames) | ✅ Intel LLM-Scaler enables Qwen3-VL on B-series | Q4 fits |
| **Qwen2.5-VL-32B-Instruct** | dense | text+image+video | ✅ IPEX-LLM/vLLM | Q4 ~18GB |
| **Mistral-Small-3.2-24B** | dense | text+image, strong tools | ✅ vLLM/llama.cpp | Q4 ~14GB |

- **Qwen3-VL** is the headline vision pick — multimodal + tools + already targeted by Intel's B-series vLLM.
- This tier covers **Hermes' vision needs** (desktop screenshots) on local hardware.

## Tier 3 — Omni: text + image + **audio + video** (the frontier)

| Model | Size | Modality | Arc status | Notes |
|---|---|---|---|---|
| **Qwen2.5-Omni-7B** | 7B | image+audio+video → text+**speech** | llama.cpp support landed; `ipex-llm[xpu]` example exists | true any-to-text/speech |
| **MiniCPM-o 2.6** | 8B | streaming video+audio, real-time speech | GGUF/int4 + llama.cpp + ipex-llm | fast tokenization, great on Arc |

- These give you **audio + video** understanding and **speech out** — the "more the merrier" goal. Expect this to need the most hands-on dev (the tools we'll build & share).

## Tier 4 — Local coding (cut paid coding spend too)

| Model | Size | Arc status | Fit |
|---|---|---|---|
| **Qwen2.5-Coder-32B-Instruct** | 32B | ✅ vLLM/llama.cpp | Q4 ~18GB |

- Strong enough to handle a lot of coding locally, reserving paid APIs for the hardest tasks/orchestration.

## Tier 5 — RAG infrastructure (tiny, always-on)

- **bge-m3** (multilingual, multi-vector embeddings) + **bge-reranker-v2-m3**. Run on the B60 or CPU; powers retrieval for everything above.

---

## Recommended starting roster (fits the B60, covers all needs)
1. **gpt-oss-20b** — smart default (reasoning + tools, MoE, $0).
2. **Qwen3-VL** (or Qwen2.5-VL-32B) — vision + tools; serves Hermes' eyes.
3. **Qwen2.5-Omni-7B** — audio + video + speech.
4. **Qwen2.5-Coder-32B** — local coding.
5. **bge-m3** — embeddings/RAG.

Each gets a tuned recipe (weights quant + KV-cache dtype + max `num_ctx`) via the `vram-budget` tool. Only one big model is resident at a time; the gateway swaps by alias.

## Serving engine per model
- **Ollama (IPEX-LLM)** — GGUF chat/vision models (Gemma 3, Qwen-VL, MiniCPM-o): easiest, what we stood up first.
- **Intel LLM-Scaler vLLM** (Arc B-series container) — gpt-oss, Qwen3-VL, max throughput/context.
- **llama.cpp (IPEX-LLM) / transformers+ipex-llm[xpu]** — omni audio/video models that need custom plumbing.

## "Tools that help everyone with these cards" (open-source roadmap)
The Arc LLM ecosystem is immature; we'll publish what we build:
1. **`arc-b60-llm`** repo: recipes, launchers, `vram-budget` calculator, benchmark suite.
2. **Arc model compatibility matrix** — what runs, at what context, how fast (real numbers).
3. **Omni-on-XPU wrappers** — make Qwen2.5-Omni / MiniCPM-o audio+video work cleanly on Arc; upstream fixes to llama.cpp SYCL & IPEX-LLM where needed.
4. **One-command installer** so anyone with a B60/B-series can replicate the stack.
