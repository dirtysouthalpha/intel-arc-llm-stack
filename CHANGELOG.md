# Changelog

## Unreleased

- Installer (pending in PR #4, not in this PR): `-Full` mode will write the full 12-model roster and 14 local gateway aliases, including Qwen3.8-27B / `sentinel-local`, registers `B60-Swap` / `B60-Gateway`; Gemma-only remains the default `-Minimal` path. Driver preflight (minimum 31.0.101.5522) and download retries added.
- Live roster in main is now 12 models / 14 local aliases (Qwen3.8-27B added by PR #6, merged 2026-11-17); the MODELS.md Live now table in this PR is updated to match.
- Docs refresh (2026-11-17): STATUS.md dated and corrected, PLAN.md Phases 1 and 3 marked superseded/blocked, MODELS.md reconciled with a Live now table, `docs/troubleshooting.md` added, README Requirements / Upgrade / Uninstall sections added.

## 2026-11-01 — Polish

- README, test suite, and pinned CI polish (see `git log` for the 2026-11-01 sweep).
- Live roster at that date (see `llama-swap/models.yaml` / `gateway/config.yaml`):
  gemma3-12b, gemma3-12b-max, gemma3-12b-vision, gemma3-27b, gemma3-27b-vision,
  qwen3-30b, qwen2.5-coder-32b, qwen2.5-vl-7b, gpt-oss-20b, qwen3-vl-8b,
  qwen2.5-omni.
- Engine pins at that date: IPEX-LLM llama.cpp b20250729, mainline llama.cpp
  b9544 (Vulkan), llama-swap v223. LiteLLM is not pinned in the installer —
  no verified known-good version is recorded in the repo.

## Release / tagging — follow-up

No release or tag exists yet. The first release/tag (for example `v0.1.0`
or a date-based tag) is a follow-up decision: confirm the version scheme
first, then tag the commit that matches this changelog.
