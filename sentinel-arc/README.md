# sentinel-arc — Phase A (ready-to-launch)

Fine-tune Qwen3.8-27B (open-weight, Apache-2.0) into
**sentinel-arc-27b-v1** for Sentinel automation / coding / networking
on the Intel Arc Pro B60 24 GB.

Phase A stops at ready-to-launch: **no training run has been started
and nothing has been charged.**

## Contents

| Path | What it is |
|---|---|
| `eval/eval.jsonl` + `eval/README.md` | **120 held-out tasks** (48 automation / 36 coding / 24 reasoning / 12 masking). **Do not train on this file.** Scoring rubric + ship threshold in the README. |
| `eval/generate_eval.py` | Regenerates the eval set; asserts the exact counts. |
| `data/train.jsonl` + `data/README.md` | **1,000 training examples** (400 coding / 300 automation / 200 reasoning / 100 masking), built programmatically from public repo content. Provenance per example type in the README. |
| `data/generate_train.py` | Regenerates the training set; asserts the exact counts and dedup. |
| `training/train-qwen3.8-27b-lora.md` | LoRA config (rank 32, 3 epochs, 4k ctx, 1× H100), exact launch command, verified GPU prices (2026-11-17), cost estimate, spend cap $60, failure playbook. |
| `training/axolotl-qwen3.8-27b-lora.yml` | Machine-readable Axolotl config for the run. |
| `training/model-card-draft.md` | Draft model card for sentinel-arc-27b-v1 (results to be filled after eval). |
| `training/export-and-deploy.md` | Merge → GGUF Q4_K_M export, llama-swap / LiteLLM / TokenRonin deploy, A/B plan, rollback. |

## Ship threshold (all must hold)

- Task success vs stock Qwen3.8-27B: **≥ +10%** on the 120-task held-out eval
- Coding regression: **none**
- Throughput on B60 at 8k ctx: **≥ 15 tok/s**
- Masking leak: **0**

## Launch status

**Ready-to-launch.** Provider: RunPod Secure Cloud, 1× H100 PCIe
80 GB at $2.89/hr (verified 17 Nov 2026). Planning window 8–12 h
($23.12–$34.68); $60 cap buys ~20.7 h. Exact command is in
`training/train-qwen3.8-27b-lora.md`. One pre-launch check remains:
confirm the exact Hugging Face repo id for the Qwen3.8-27B weights
before filling in `base_model:` — do not guess it.

## Notes

- Do not wait for Qwen4 (API-only, no open small model). IPEX-LLM is
  dead for this stack — serving is llama.cpp Vulkan/SYCL.
- `llama-swap/models.yaml` and `gateway/config.yaml` are **not**
  touched in this Phase A change (another worker owns them in Phase B).
