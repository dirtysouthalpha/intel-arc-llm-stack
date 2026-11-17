# Train sentinel-arc-27b-v1 — LoRA on Qwen3.8-27B

Status: **READY TO LAUNCH — no training run has been started, nothing
has been charged.** This document is the launch checklist. Do not run
anything here without reading the cost section first.

## Goal

LoRA-fine-tune open-weight **Qwen3.8-27B** (Apache-2.0, Q4 ~17–18 GB,
fits the Arc Pro B60 24 GB) on `sentinel-arc/data/train.jsonl`
(1,000 examples) so the resulting model beats stock Qwen3.8-27B on the
held-out eval (`sentinel-arc/eval/eval.jsonl`, 120 tasks) for Sentinel
automation / coding / networking on the Arc stack.

Do **not** wait for Qwen4 — Qwen4-Max is API-only and there is no open
small Qwen4 to train. Do **not** use IPEX-LLM for training or serving:
it is dead for this stack; serving is llama.cpp Vulkan/SYCL.

## Config

| Setting | Value |
|---|---|
| Base model | Qwen3.8-27B, open-weight, Apache-2.0 (see "Base model id" below) |
| Method | LoRA (adapters only; base weights frozen) |
| LoRA rank (`r`) | **32** |
| LoRA alpha | 64 (alpha = 2 × rank) |
| LoRA dropout | 0.05 |
| LoRA target modules | `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj` |
| Epochs | **3** |
| Context (training) | **4,096 tokens** (`max_seq_len: 4096`) |
| Batch | micro-batch 1, gradient accumulation 8 (effective batch 8); lower if OOM |
| Learning rate | 1e-4, cosine schedule, warmup 3% |
| Optimiser | adamw_torch_fused; bf16, gradient checkpointing on |
| Checkpointing | **Save at the end of every epoch** (`save_steps` = steps-per-epoch; keep all 3) |
| Eval during training | None on the held-out set — the held-out eval is run only after training, on the merged model (see `export-and-deploy.md`). Use a small slice of the training file for sanity loss only. |
| Data | `sentinel-arc/data/train.jsonl` — 1,000 examples (400 coding / 300 automation / 200 reasoning / 100 masking). **Never add `eval/eval.jsonl`.** |
| Spend cap, first run | **$60 hard cap** (see Cost below) |

Full machine-readable config: `axolotl-qwen3.8-27b-lora.yml` in this
directory (Axolotl). Record the exact Axolotl / PyTorch / CUDA versions
installed at launch in the run log — they are not pinned here because
they must match whatever the rented image ships.

## Base model id — verify before launch

This document does **not** invent a Hugging Face repo id. Before
launch, confirm the exact repo id for the open Qwen3.8-27B weights on
huggingface.co, check its licence is Apache-2.0, and write the id into
`base_model:` in `axolotl-qwen3.8-27b-lora.yml`. If the id cannot be
confirmed, stop — do not guess a repo id and do not train a different
model. (The task brief names the model "Qwen3.8-27B"; if the Hub lists
it under a different exact name, record the Hub name and use that.)

## Provider and prices (verified 2026-11-17)

Prices checked by web search on 2026-11-17. They move with supply —
re-check the provider's own pricing page at launch before creating
the pod.

| Provider | 1× H100, on-demand | Source / date |
|---|---|---|
| **RunPod Secure Cloud, H100 PCIe 80 GB** | **$2.89/hr** | runpod.io, checked 17 Nov 2026 |
| RunPod Secure Cloud, H100 SXM 80 GB | $4.39/hr | runpod.io, checked 17 Nov 2026 |
| RunPod Community Cloud, H100 PCIe | from $1.99/hr | runpod.io, checked 17 Nov 2026 |
| RunPod Community Cloud, H100 SXM | from $2.69/hr | runpod.io, checked 17 Nov 2026 |
| Vast.ai, H100 SXM (cheapest on-demand) | ~$1.53–$1.67/hr; median ~$2.33–$2.40/hr | marketplace listings, 17 Nov 2026 |
| Lambda, H100 PCIe 1× | $3.79/hr (new tariff effective 16 Nov 2026) | lambda.ai/pricing via usagepricing.com, 16 Nov 2026 |
| Lambda, H100 SXM 1× / 8× | $4.89 / $4.59 per GPU/hr | same, effective 16 Nov 2026 |

**Recommended provider: RunPod Secure Cloud, 1× H100 PCIe 80 GB at
$2.89/hr.** It is the cheapest reliable (non-marketplace) option
verified, billed per second, and the Secure tier avoids the variable
reliability of community/marketplace hosts. Vast.ai is cheaper on the
cheapest listing but host reliability varies — use it only if you
accept marketplace risk. Lambda is more expensive for a single GPU.

## Cost estimate (arithmetic from the verified $2.89/hr rate)

Training runtime for this run is **not measured** — no run has happened
yet. Budget on a planning window, not a promised duration:

| Planning runtime | Cost at $2.89/hr (RunPod PCIe Secure) | Cost at $4.39/hr (RunPod SXM Secure) |
|---|---|---|
| 8 h | $23.12 | $35.12 |
| 12 h | $34.68 | $52.68 |
| 20 h | $57.80 | $87.80 (over cap) |
| 13.7 h | $39.59 | $60.00 (cap boundary) |

- **$60 cap buys ~20.7 h on the recommended PCIe instance**
  ($60 / $2.89) and ~13.7 h on SXM. A 1,000-example, 3-epoch LoRA run
  at 4k ctx on a 27B model is expected to fit comfortably inside the
  8–12 h planning window, but that is a planning assumption, not a
  measurement — the run log must record the actual start/stop times.
- The cap is enforced **by the operator**: set a timer, watch the run,
  and terminate the pod at $60. RunPod does not provide a hard
  auto-stop at a dollar amount in this flow — do not assume one exists.
  Because a checkpoint is saved every epoch, stopping at the cap loses
  at most the in-progress epoch.
- Extra costs: a small persistent volume (~100 GB) and any egress for
  the merged weights are billed separately and are small; check the
  pod summary before launching and record the total.

## Exact launch command

### 1. Create the pod (RunPod console)

- 1× H100 PCIe 80 GB, Secure Cloud, on-demand
- Image: a PyTorch CUDA image (e.g. RunPod's PyTorch image — pick the
  current one in the console and record its tag)
- Volume: 100 GB persistent volume
- No public ports needed; use the pod's web terminal / SSH

### 2. Inside the pod

```bash
git clone https://github.com/dirtysouthalpha/intel-arc-llm-stack.git
cd intel-arc-llm-stack
git checkout muse/sentinel-arc-phase-a-2026-11-17

# Install Axolotl per its own docs at launch time; record the version.
pip install axolotl
pip show axolotl | head -5   # record the version in the run log

# Fill in base_model in the config (verify the HF repo id first — see above).
# Then tokenize the data and record the token count:
python3 -c "import json; print(sum(1 for _ in open('sentinel-arc/data/train.jsonl')))"  # expect 1000

# Launch (3 epochs, checkpoint every epoch):
accelerate launch -m axolotl.cli.train sentinel-arc/training/axolotl-qwen3.8-27b-lora.yml
```

The config file sets `save_steps` to one epoch's worth of steps, so
checkpoints land in `outputs/sentinel-arc-27b-v1/checkpoint-epoch-*`
(or the Axolotl default `outputs/` layout — record the actual path).
Keep all 3 epoch checkpoints; evaluate the merged model from the
final one first (see `export-and-deploy.md`).

### 3. While it runs

- Watch loss: it should fall steadily; a flat or exploding loss in
  epoch 1 means stop and check the data/config, not the GPU.
- Watch the clock and the RunPod cost meter. Terminate the pod at $60
  even mid-epoch — the last epoch checkpoint is still usable.
- Record in the run log: start/stop time, pod id, image tag, Axolotl /
  PyTorch / CUDA versions, base-model HF id, token count, loss per
  epoch, checkpoint paths, total cost.

## If it fails

| Symptom | Do this |
|---|---|
| Pod unavailable / no H100 PCIe at $2.89 | Do not pay SXM prices silently. Re-check RunPod (try SXM only if the $60 cap still fits: ≤13.7 h), or Lambda PCIe 1× at $3.79/hr (≤15.8 h for $60), or Vast.ai cheapest listing. Record the switch and the new rate. |
| OOM on the H100 80 GB | Lower micro-batch to 1 (already), raise gradient accumulation, enable gradient checkpointing (already on), drop `max_seq_len` to 2048 only as a last resort and record it — do not silently change the config. |
| Loss explodes / NaN | Stop immediately. Check learning rate (1e-4), bf16, and that the data file is valid JSONL (1,000 lines). Do not restart the same broken config and burn the cap. |
| Run is slow (projected > 20 h on PCIe) | Stop at the $60 cap, keep the epoch checkpoints, and evaluate the best completed epoch. Do not extend the cap without a new decision. |
| Axolotl version mismatch / install fails | Install per Axolotl's current docs, record the version that worked, and update this document. Do not pin a version you have not verified. |
| Base-model id cannot be confirmed | Stop. Do not train a different model. Report the blocker. |
| Cost hits $60 | Terminate the pod. The epoch checkpoints are the deliverable; evaluate them before spending more. |

## After training — do not deploy yet

Merging, GGUF export, and deployment are in `export-and-deploy.md`.
The model card draft is `model-card-draft.md`. Nothing in this
document authorises a training run or any charge — the run is launched
only when Brandon says so, with the command above.
