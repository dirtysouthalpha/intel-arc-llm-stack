# Live system status

The Arc B60 local-LLM stack is **operational on HOMESERVER** and reboot-persistent.

## Endpoints
- **Gateway (use this):** `http://100.70.240.55:4000/v1` — OpenAI-compatible, reachable over Tailscale.
  Auth: `Authorization: Bearer <LITELLM_MASTER_KEY>` (stored in `V:\AI\gateway\.env`).
- llama-swap (internal): `http://127.0.0.1:9090/v1` — model swapping on the B60.
- Hermes agent: `http://100.70.240.55:8478` (A2A: `/a2a/message`).

## Models (via the gateway)
| Alias | Backend | Notes |
|---|---|---|
| `local-chat` | gemma3-12b (64K) | default everyday brain, $0 |
| `local-vision` | gemma3-12b-vision (32K) | text + image (Hermes uses this) |
| `gemma-12b` | gemma3-12b (64K) | fast |
| `gemma-12b-max` | gemma3-12b (128K) | full context, slower long-prompt ingest |
| `coding` | claude-sonnet-4-6 | **paid**, needs ANTHROPIC_API_KEY |
| `orchestration` | claude-opus-4-8 | **paid**, needs ANTHROPIC_API_KEY |

Default fallback is `local-chat`, so unspecified traffic stays local + free.

## Throughput (Gemma 3 12B Q4 on the B60)
- Generation ~33 tok/s; full GPU offload (49/49 layers, SYCL0).
- 128K context loads and runs (~31 tok/s gen).

## Scheduled tasks (autostart)
- `B60-Swap` (session 1, AtLogon) — llama-swap front.
- `B60-Gateway` (session 0, AtStartup) — LiteLLM.
- `B60-Hermes` (session 1, AtLogon) — desktop agent on local Gemma.
- `B60-Job` — reusable session-1 job runner (benchmarks/ops).
- `B60-IPEX-Ollama`, `B60-LlamaServer` — disabled (superseded by llama-swap).

## To enable paid coding/orchestration routing
Put your key in `V:\AI\gateway\.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
then `Restart-ScheduledTask B60-Gateway`. Everyday/vision stays local; only `coding`/`orchestration` aliases spend.

## Quick test (from any Tailscale machine)
```bash
curl http://100.70.240.55:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"model":"local-chat","messages":[{"role":"user","content":"hi"}]}'
```

## Next steps
- Pull more models (27B, gpt-oss-20b, Qwen3-VL, Qwen2.5-Omni) — see MODELS.md; add to `llama-swap/models.yaml`.
- Wire Sentinel's LiteLLM at the same models (secondary).
- xpu-smi monitoring + needle-in-haystack long-context verification.
