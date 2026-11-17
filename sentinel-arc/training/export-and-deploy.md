# Export and deploy sentinel-arc-27b-v1

Status: **not started.** This is the plan for after the training run
and the held-out eval pass. Do not deploy a model that has not passed
the ship gates in `../eval/README.md`.

## 1. Merge the LoRA adapter

On the rented pod (or any machine with the base weights and the
adapter), merge the adapter into the base model. With Axolotl:

```bash
# From the training checkout, after the run finishes:
accelerate launch -m axolotl.cli.merge_lora sentinel-arc/training/axolotl-qwen3.8-27b-lora.yml
# Output: a merged model directory (record the actual path, e.g. ./outputs/sentinel-arc-27b-v1/merged)
```

Keep the adapter checkpoints as well — the merged model is the
deployable artefact, the adapter is the auditable one. Record which
epoch checkpoint was merged (start with the final epoch; if it
underperforms, try the earlier epoch checkpoints before retraining).

## 2. Export to GGUF Q4_K_M

Convert the merged model to GGUF with llama.cpp's converter, then
quantise to Q4_K_M (the quantisation the B60 stack uses for 27B
models; Q4 ~17–18 GB, fits the 24 GB card with KV headroom):

```bash
# From a llama.cpp checkout (mainline — the same source as the Vulkan binary):
python3 convert_hf_to_gguf.py /path/to/merged-sentinel-arc-27b-v1 \
  --outfile sentinel-arc-27b-v1-f16.gguf --outtype f16
llama-quantize sentinel-arc-27b-v1-f16.gguf sentinel-arc-27b-v1-Q4_K_M.gguf Q4_K_M
ls -lh sentinel-arc-27b-v1-Q4_K_M.gguf   # expect ~17-18 GB; record the exact size
```

Verify the file loads before deploying it anywhere:

```bash
llama-cli -m sentinel-arc-27b-v1-Q4_K_M.gguf -p "Hello" -n 32
# Expect coherent text and no load errors. Do not skip this check.
```

## 3. Deploy on the B60 (llama-swap / LiteLLM / TokenRonin)

> **Do not edit `llama-swap/models.yaml` or `gateway/config.yaml` in
> this Phase A PR.** Another worker owns those files in Phase B.
> The steps below are the Phase B deployment plan, to be executed
> then — they are written here so the deploy is ready, not so it is
> done now.

1. Copy the GGUF to the models directory (the path used by the
   existing entries, e.g. `V:\AI\models\sentinel-arc-27b-v1-Q4_K_M.gguf`).
2. Add a llama-swap entry (Phase B, in `llama-swap/models.yaml`),
   following the existing pattern — IPEX SYCL `llama-server.exe`,
   `-ngl 999`, f16 KV, no flash-attn, no KV-quant, small `-ub` at
   large ctx:
   ```yaml
   "sentinel-arc-27b":
     cmd: >
       V:\AI\llama-cpp\llama-server.exe
       -m V:\AI\models\sentinel-arc-27b-v1-Q4_K_M.gguf
       -ngl 999 --host 127.0.0.1 --port ${PORT}
       -c 32768 -ub 64 -b 256 -np 1 --no-mmap
     ttl: 1800
   ```
   (If the Vulkan binary proves faster for this model in A/B testing,
   use the `llama-cpp-vulkan` binary instead and record the change;
   do not assume — measure.)
3. Add a LiteLLM alias (Phase B, in `gateway/config.yaml`):
   ```yaml
   - model_name: sentinel-arc
     litellm_params:
       model: openai/sentinel-arc-27b
       api_base: http://127.0.0.1:9090/v1
       api_key: "swap"
   ```
4. Restart and verify from an interactive session (session 1):
   ```powershell
   .\launchers\restart-stack.ps1
   ```
   ```bash
   curl http://127.0.0.1:4000/v1/chat/completions \
     -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
     -d '{"model":"sentinel-arc","messages":[{"role":"user","content":"hi"}]}'
   ```
5. TokenRonin: no config change is needed to try the model — point
   a provider at the gateway alias (`:4000`, model `sentinel-arc`)
   and use the existing routing, spend guards, and masking. Keep
   TokenRonin's masking (`internal/mask/`) in front of it regardless
   of the eval result.

## 4. A/B plan

Run the same 120 held-out tasks (`../eval/eval.jsonl`) against both
models on the B60, same quantisation (Q4_K_M), same context, same
decoding settings, same harness:

| Arm | Model (gateway alias) | Purpose |
|---|---|---|
| A (control) | Stock Qwen3.8-27B Q4_K_M | Baseline task success, coding, tok/s |
| B (candidate) | `sentinel-arc` (this model) | Same metrics, same tasks |

- Score per `../eval/README.md` (masking leak = automatic fail).
- Measure throughput at 8k ctx on the B60 for both arms.
- Ship only if **all** gates pass: ≥ +10% overall task success,
  no coding regression, ≥15 tok/s, masking leak 0.
- If B wins on task success but loses on throughput, do not ship —
  fix the serving config (context, `-ub`, binary choice) and re-run.

## 5. Rollback — keep the old aliases

- **Never delete the old aliases.** The stock model entries
  (`qwen3-30b`, `local-coding`, `gemma-27b`, etc.) and their
  llama-swap entries stay in place. The new alias is additive.
- Rollback is one config change: point the `sentinel-arc` alias (or
  any caller using it) back at the previous model, run
  `launchers/restart-stack.ps1`, and curl `:4000` to verify. No
  reinstall, no re-download.
- If the new GGUF misbehaves (load failure, degenerate output,
  masking leak in production), roll back immediately, keep the GGUF
  and the eval output for diagnosis, and do not re-deploy it until
  the cause is found.
- Keep the previous working GGUF on disk until the new model has run
  cleanly for a full working day.
