# Model Card (draft) — sentinel-arc-27b-v1

> **Draft.** Fill in the bracketed fields after the training run and
> the held-out eval. Do not publish this card with unmeasured numbers.

## Model details

| Field | Value |
|---|---|
| Model name | sentinel-arc-27b-v1 |
| Base model | Qwen3.8-27B (open-weight, Apache-2.0) — exact Hugging Face repo id: [to be recorded at launch] |
| Fine-tuning method | LoRA, rank 32, 3 epochs, 4k context (see `train-qwen3.8-27b-lora.md` and `axolotl-qwen3.8-27b-lora.yml`) |
| Training data | `sentinel-arc/data/train.jsonl` — 1,000 examples (400 coding / 300 automation-networking / 200 reasoning / 100 masking-safety), built programmatically from public repo content; no real secrets, PII, credentials, hostnames, or health data |
| Eval data | `sentinel-arc/eval/eval.jsonl` — 120 held-out tasks (48 automation / 36 coding / 24 reasoning / 12 masking); **never trained on** |
| Licence | Apache-2.0 (base model licence; the LoRA adapter and this card follow the base licence) |
| Intended hardware | Intel Arc Pro B60 24 GB, Windows, llama.cpp (Vulkan/SYCL) via llama-swap :9090 + LiteLLM gateway :4000 |
| Quantisation (deployed) | GGUF Q4_K_M (~17–18 GB) — see `export-and-deploy.md` |
| Version | v1 (first LoRA run) |
| Training cost | [to be recorded: provider, GPU, hours, total $ — cap $60 for the first run] |
| Training date | [to be recorded] |

## Intended use

Sentinel automation, coding, and networking assistance on the local
Arc stack: driving Sentinel (`sentinel-code` v3.3.0) tool use, writing
and reviewing TypeScript / Go / PowerShell / Python for the
`intel-arc-llm-stack`, `sentinel-code`, and `tokenronin` repos,
operating llama-swap / LiteLLM / TokenRonin, sizing VRAM and context,
and masking PII/secrets before text leaves the trusted side
(TokenRonin `internal/mask/`).

## Out-of-scope / limitations

- **Not a general-purpose replacement for the base model.** It is
  tuned for Sentinel/Arc-stack tasks; performance outside that domain
  was not measured and should not be assumed.
- **No Qwen4.** Qwen4-Max is API-only; there is no open small Qwen4.
  This model is built on the latest open Qwen available (Qwen3.8-27B).
- **Knowledge is frozen at the base model's cutoff** plus the training
  data's grounding (repo content as read 2026-11-17). It does not know
  later repo changes, driver versions, or prices — re-check those live.
- **Masking is a behaviour, not a guarantee.** The model is trained to
  mask PII/secrets, but the ship gate requires a measured masking leak
  of 0 on the held-out set, and TokenRonin's reversible masking
  (`internal/mask/`) remains the enforcement point — do not rely on
  the model alone.
- **Throughput is hardware-dependent.** The ≥15 tok/s gate is measured
  on the B60 at 8k ctx with Q4_K_M; other cards, contexts, and
  quantisations will differ.
- **English only** (training and eval are English). Other languages
  were not evaluated.
- **No safety evaluation beyond the eval set.** The 12 masking/safety
  tasks cover PII/secret handling, not general jailbreak robustness.

## Eval results (to be filled after the run)

| Metric | Stock Qwen3.8-27B (baseline) | sentinel-arc-27b-v1 | Delta |
|---|---|---|---|
| Overall task success (120 tasks) | [ ] | [ ] | [ ] |
| Automation (48) | [ ] | [ ] | [ ] |
| Coding (36) | [ ] | [ ] | [ ] |
| Reasoning (24) | [ ] | [ ] | [ ] |
| Masking (12) | [ ] | [ ] | [ ] |
| Masking leaks | [ ] | [ ] (must be 0) | — |
| Throughput, B60, 8k ctx | [ ] tok/s | [ ] tok/s (must be ≥15) | — |

**Ship threshold (all must hold):** ≥ +10% overall task success vs
stock, no coding regression, ≥15 tok/s on the B60 at 8k ctx, masking
leak 0. See `../eval/README.md`. No benchmark numbers, tok/s figures,
or training results are claimed in this draft — the table above is
empty until the eval is actually run.

## Data provenance (summary)

Training examples were generated programmatically
(`../data/generate_train.py`) from structured templates grounded in
public repo content: `intel-arc-llm-stack` @ `182f00d0`
(`README.md`, `llama-swap/models.yaml`, `gateway/config.yaml`,
`bench/results.md`), `sentinel-code` v3.3.0 (`README.md`,
`package.json`), and `tokenronin` v13.0.0 (`README.md`). Full
provenance per example type is in `../data/README.md`. No real
secrets, family PII, credentials, hostnames/IPs, or health data are in
the training data; placeholders (`<EMAIL>`, `<API_KEY>`, etc.) and
`${ENV_VAR}` references by name only.

## Ethical / safety notes

- The masking training teaches the model to replace PII/secrets with
  placeholders and to refuse to reproduce literal secrets. This is a
  defence-in-depth behaviour; the proxy-side masking in TokenRonin is
  the control that must hold.
- Do not use the model to generate or repeat real credentials,
  personal data, or internal network details. The eval's masking tasks
  treat any such leak as an automatic fail.
