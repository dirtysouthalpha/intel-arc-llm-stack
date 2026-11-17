# Sentinel-Arc training data

`train.jsonl` — 1,000 examples for LoRA fine-tuning of Qwen3.8-27B into
sentinel-arc-27b-v1. One JSON object per line:

| Field | Meaning |
|---|---|
| `id` | `train-<category>-<NNNN>` |
| `category` | `coding` \| `automation` \| `reasoning` \| `masking` |
| `instruction` | What the model is asked to do |
| `input` | Context (command, config, snippet, or scenario) |
| `output` | The target response |
| `source` | Provenance tag: `template:<name> x <grounding>` |

## Counts (exact, verified)

| Category | Count | Share | Target |
|---|---|---|---|
| coding | 400 | 40% | 40% |
| automation | 300 | 30% | 30% |
| reasoning | 200 | 20% | 20% |
| masking | 100 | 10% | 10% |
| **Total** | **1,000** | **100%** | — |

Verified by counting `train.jsonl`: 1,000 lines, 1,000 unique ids,
1,000 unique (instruction, input) pairs after dedup, and **zero
(instruction, input) overlap with `../eval/eval.jsonl`** (the held-out
set was never used as training input).

## How it was built

Programmatically, with `generate_train.py` in this directory — not
hand-written one by one. Structured templates × grounded parameter
lists, then deduplication on (instruction, input). The generator
asserts the exact per-category counts before writing the file.

### Provenance per example type

| Example type | Grounding (read 2026-11-17) | How examples vary |
|---|---|---|
| TypeScript ESM / build / vitest | `sentinel-code` v3.3.0 `README.md`, `package.json` (ESM `.js` imports, tsup build, `vitest run`, 866 tests, Node ≥ 20) | Real `src/*.ts` file names × task angles (fix, explain, test-first) |
| Go handlers / tests / config | `tokenronin` v13.0.0 `README.md` (`internal/gateway` chi, `internal/app`, `internal/mask`, `cmd/proxy`, `pkg/config`; Go 1.25+, `make test`) | Real `internal/*.go` paths × handler/test/guard angles |
| PowerShell launchers | `intel-arc-llm-stack` `README.md`, `install.ps1`, `launchers/` (`restart-stack.ps1`, `start-swap.ps1`, `start-gateway.ps1`; session-1 / `LogonType Interactive`) | 4 launchers × 5 diagnostic angles |
| VRAM / llama-swap / LiteLLM | `llama-swap/models.yaml`, `gateway/config.yaml`, `bench/results.md` @ `182f00d0` (weights, `-ngl 999`, `-c`/`-ub`/`-b`, ttl, aliases, f16 KV, no FA) | Real model names, weights, aliases × sizing/fix/route angles |
| Sentinel commands | `sentinel-code` README slash-command table (`/plan`, `/ship`, `/autopilot`, `/tdd`, `/team`, `/fork`, `/index`, `/search`, `/bg`, `/export`, `/branch`, `/usage`, `/workspace`, `/marketplace`, `/permissions`, `/undo`, `/checkpoints`, `/mcp`, `/model`) | 20 commands × what-it-does / example-invocation |
| TokenRonin routes | `tokenronin` README API table (`/v1/chat/completions`, `/v1/messages`, `/v1/models`, `/v1/providers/status`, `/v1/estimate`, `/v1/analyze`, `/v1/budget`, `/v1/webhooks`, `/health`, `/metrics`, `/stats`, `/events/stream`) | 12 routes × 5 angles (purpose, call, failure, curl, cost) |
| Reasoning / planning / incidents | `bench/results.md` (0.8 vs 33.6 tok/s, FA/KV-quant crashes, ollama-GGUF failure), gateway cost policy (local-free, paid opt-in), router/breaker rules | Model/ctx choices, cost-routing classes, 10 incidents × 4 angles, 10 plans × 4 angles |
| Masking / safety | `tokenronin` `internal/mask/` (reversible PII masking, per task brief) + `${ENV_VAR}`-by-name rule from the TokenRonin/LiteLLM READMEs | PII types × mask/before-use, 10 env vars × safe/rotate, 10 safety scenarios × 4 angles |

### What is NOT in the data

- No real secrets, credentials, API keys, or passwords. Secrets appear
  only as placeholders (`<EMAIL>`, `<API_KEY>`, `<PASSWORD>`, `<NAME>`,
  `<PHONE>`, `<GOV_ID>`) or as `${ENV_VAR}` / `os.environ/...`
  references **by name**.
- No family PII, no health data, no real hostnames or internal IPs.
  The only addresses are loopback values from the public repo configs
  (`http://127.0.0.1:9090/v1`, `:4000`). No non-loopback stand-in
  address was needed, so none (including `10.0.0.1`) appears in the
  file; if a future task genuinely needs an address stand-in, use
  `10.0.0.1` and flag it as a stand-in in the text.
- No eval tasks. The held-out set is separate and was never used here.

## Regenerating

```bash
python3 generate_train.py
```

The script asserts the exact counts (400/300/200/100), id uniqueness,
and dedup before writing `train.jsonl`. If you extend a template,
re-run it and re-verify the counts — do not hand-edit `train.jsonl`
without regenerating, or the counts in this README will drift from the
file. Token counts are not recorded here; measure them at launch time
by tokenizing the file with the base model's tokenizer and record the
number in the training run log.
