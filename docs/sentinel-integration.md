# Sentinel integration (B60 gateway)

Sentinel's model-router (`C:\Sentinel\optimization\model-router\`) currently routes:
- **tier1/tier2 (local)** -> stock ollama on `http://localhost:11434` = the **8GB RTX 2070** (small).
- **tier3 (complex)** -> z.ai **glm-5** (paid).
- **vision** -> `llava` on the 2070.

Goal: move local tiers to the **24GB B60** and cut paid spend, without breaking Sentinel.

## How the router dispatches (so we pick the safe path)
- Local tiers use `OllamaAdapter` -> ollama native API (`/api/chat`). Our B60 stack speaks **OpenAI /v1**, not ollama's API, so we CANNOT just change `base_url` for the ollama tiers.
- API tiers go through **litellm**: `router.py` builds `model = f"{provider}/{model}"` and calls `litellm.completion(...)`. tier3 uses `provider: zai`.

So the clean, low-risk integration is to add **OpenAI-provider tiers that point at the B60 gateway** (litellm path), leaving the ollama adapter untouched.

## Steps (reversible; back up config.yaml first)
1. Back up: copy `optimization\model-router\config.yaml` -> `config.yaml.bak`.
2. Give Sentinel's process these env vars (so litellm's openai provider targets the gateway):
   ```
   OPENAI_API_BASE=http://127.0.0.1:4000/v1
   OPENAI_API_KEY=<LITELLM_MASTER_KEY from V:\AI\gateway\.env>
   ```
   (Set in Sentinel's launcher / `start_all.bat` env, NOT globally, to avoid affecting other openai calls.)
3. Repoint tiers in `config.yaml` to B60 models via the openai provider:
   - tier2 (moderate): `provider: openai`, `model: qwen3-30b` (MoE, free, B60).
   - tier3 (complex): `provider: openai`, `model: gemma-27b` (free, B60) instead of paid glm-5 -
     or keep glm-5 as a tier3 fallback if you still want a paid escalation.
   - vision: `provider: openai`, `model: local-vision` (gemma3-12b-vision) or `qwen2.5-vl`.
   Remove the `base_url` field on these tiers (they now go through litellm, not the ollama adapter).
4. Verify `_build_completion_args` passes api_base/api_key. It currently only sets `model`. If litellm
   doesn't pick up `OPENAI_API_BASE` env for the `openai/` prefix, add to that tier branch:
   ```python
   args["api_base"] = tier.get("api_base")
   args["api_key"]  = tier.get("api_key")
   ```
   and put `api_base`/`api_key` in each B60 tier. (Small, contained change.)
5. Restart Sentinel; send a moderate query -> confirm it routes to qwen3-30b on the B60 (xpu load),
   and a complex query -> gemma-27b, with `$0` cost in the routing log.

## Why not just modify it now
Sentinel is a live system with circuit breakers, health checks, and its own routing logic. The change
above is safe and reversible but should be applied with your sign-off and a Sentinel restart you control.
