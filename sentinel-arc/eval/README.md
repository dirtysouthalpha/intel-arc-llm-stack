# Sentinel-Arc eval — held-out set

> **HELD OUT — DO NOT TRAIN ON THIS FILE.**
> `eval.jsonl` is the held-out evaluation set for sentinel-arc-27b-v1.
> It must never be included in training data, fine-tuning, prompt
> selection, or checkpoint selection. Training on it invalidates every
> result in this directory. The training set (`../data/train.jsonl`) was
> checked to have **zero (instruction, input) overlap** with this file.

## What it is

120 tasks, each a single JSON object per line in `eval.jsonl`:

| Field | Meaning |
|---|---|
| `id` | `eval-<category>-<NNN>` |
| `category` | `automation` \| `coding` \| `reasoning` \| `masking` |
| `instruction` | What the model is asked to do |
| `input` | Context the task is grounded in (command, config, snippet) |
| `expected_outcome` | What a correct answer must contain |
| `rubric` | Scoring points for the judge |
| `pass_criteria` | The bar for a pass on this task |
| `held_out` | Always `true` |

## Counts (exact)

| Category | Count | What it covers |
|---|---|---|
| automation | 48 | Sentinel commands (`sentinel run --json`, `loop`, `/tdd`, `/ship`, `/autopilot`, `/team`, `/plan`, MCP, model router, permissions/undo), llama-swap hot-swap, LiteLLM gateway routing (`:4000`), `restart-stack.ps1`, `install.ps1`, `vram-budget`, TokenRonin routes (`/health`, `/v1/*`), SIGHUP reload |
| coding | 36 | TypeScript ESM (`.js` imports), tsup build, vitest, singleton `getInstance()`, MCP SDK, Go chi handlers, SIGHUP reload, HMAC webhooks + SSRF guard, spend guard, PowerShell launchers, `vram_budget.py`, LiteLLM YAML (ASCII-only) |
| reasoning | 24 | Model/context choice for the B60 24 GB, VRAM sizing (`-ub` vs ctx, f16 KV, no FA), cost routing (local-free vs paid opt-in), fallback-chain design, slow-inference diagnosis, eval design, incident triage |
| masking | 12 | Reversible PII/secret masking; **any unmasked original value in the output is an automatic FAIL for the whole task** |
| **Total** | **120** | |

## Grounding

Tasks are grounded in real repo content read 2026-11-17:

- `dirtysouthalpha/intel-arc-llm-stack` @ `182f00d0` — `README.md`,
  `llama-swap/models.yaml`, `gateway/config.yaml`, `bench/results.md`
- `dirtysouthalpha/sentinel-code` v3.3.0 — `README.md`, `package.json`
  (866 tests, Node ≥ 20, ESM, tsup, vitest, Tauri v2)
- `dirtysouthalpha/tokenronin` v13.0.0 — `README.md`
  (Go, chi, `/health`, `/v1/*`, spend guards, webhooks, SIGHUP reload)

No invented file paths, flags, ports, hostnames, or IPs appear in the
tasks. The only addresses used are loopback values from the public repo
configs (`http://127.0.0.1:9090/v1`, `:4000`). Secrets appear only as
placeholders (`<EMAIL>`, `<API_KEY>`, `<PASSWORD>`, `<NAME>`, `<PHONE>`,
`<GOV_ID>`) or `${ENV_VAR}` references by name.

## Scoring rubric

Score each task **pass / fail** against its `pass_criteria`, using its
`rubric` as the checklist. Task success rate per category is:

```
task_success(category) = passed_tasks(category) / total_tasks(category)
overall_task_success   = passed_tasks(all) / 120
```

- **Masking:** leak = automatic fail for that task, regardless of other
  rubric points. A partially shown value (e.g. last 4 characters) is
  still a leak. Report the masking leak count separately; it must be 0.
- **Coding:** the code must be valid under the repo's toolchain
  (Node ≥ 20 / Go 1.25+ / PowerShell / Python 3.10+) and use only real
  APIs, imports, and paths from the repos above.
- **Automation / reasoning:** answers must use only documented numbers
  and behaviours. No invented benchmarks, prices, or throughput figures.
  A correct answer that cites a made-up number fails.

Run the same 120 tasks, in the same order, against both models:

1. **Baseline:** stock Qwen3.8-27B (Q4_K_M, same quantisation and
   context as the candidate, served the same way on the B60).
2. **Candidate:** sentinel-arc-27b-v1 (LoRA-merged, Q4_K_M).

Same prompts, same decoding settings, same harness. Report per-category
and overall rates for both, plus the delta.

## Ship threshold (all must hold)

| Gate | Threshold |
|---|---|
| Task success vs stock Qwen3.8-27B | **≥ +10% overall** (candidate − baseline ≥ 0.10) |
| Coding regression | **None** — coding task success must not drop below baseline |
| Throughput on B60 at 8k ctx | **≥ 15 tok/s** (generation, Q4_K_M) |
| Masking leak | **0** — any leak blocks ship, even if the other gates pass |

If any gate fails, do not ship. Diagnose, fix, and re-run the full
120-task set — do not cherry-pick a passing subset.

## Regenerating

`generate_eval.py` (in this directory) regenerates `eval.jsonl`
deterministically and asserts the exact counts (48/36/24/12, 120 total,
unique ids). If you change a task, regenerate and re-verify the counts
before using the set. Never add eval tasks to training data.
