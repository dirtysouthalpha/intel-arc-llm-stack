# Sentinel RAG sources

How Sentinel's retrieval layer is fed, so answers about the local stack,
TokenRonin, and Sentinel itself are grounded in the actual repos instead of
memory. No training is involved: this is config and docs only.

## Source repos

All three repos live under the `dirtysouthalpha` GitHub org and are cloned
locally before indexing. Only the paths listed here are indexed; anything
else is out of scope until it is verified and added below.

| Repo | What it covers | Paths to index |
|---|---|---|
| `dirtysouthalpha/intel-arc-llm-stack` | The local serving stack: llama-swap model serving, LiteLLM gateway, Sentinel docs and prompts | `README.md`, `MODELS.md`, `PLAN.md`, `STATUS.md`, `docs/`, `gateway/config.yaml`, `llama-swap/models.yaml` |
| `dirtysouthalpha/tokenronin` | The Go proxy: provider routing, A/B splits, model aliases, spend guards, PII masking | `README.md`, `docs/PRODUCTION.md`, `docs/masking-baseline.md`, `docs/masking-tiers.md`, `docs/masking-bench-delta.md`, `pkg/config/structs.go`, `pkg/config/testdata/config.yaml`, `internal/mask/` |
| `dirtysouthalpha/sentinel-code` | The Sentinel coding-agent engine (TypeScript) | `README.md` and the repo's own docs directory -- confirm the exact doc paths in that repo before indexing, do not guess them |

Notes on the paths above:

- `internal/mask/` in tokenronin is the native reversible PII masking
  implementation. Its config surface is `features.pii_masking` in
  `pkg/config/structs.go` (enabled by default, fail-closed; `mode: mask` or
  `detect_only`; `skip_local` defaults to true). Index the package docs and
  the masking docs under `docs/masking-*.md`, not generated files.
- `docs/sentinel-system-prompt.md` and `docs/sentinel-rag-sources.md` (this
  file) in intel-arc-llm-stack are themselves RAG sources: the prompt is the
  behavior contract, this file is the source manifest.
- Do not index secrets, `.env` files, API keys, or any file containing
  credentials. If a doc contains a real key, redact it before indexing.

## Chunking guidance

- **Chunk by section, not by fixed size.** Split Markdown on headings
  (`#`, `##`) and keep code blocks whole -- never split a YAML block or a
  `cmd:` stanza across chunks.
- **Target roughly 300-800 tokens per chunk.** A whole short file (for
  example `gateway/config.yaml` or `llama-swap/models.yaml`) is one chunk;
  long docs split at `##` headings.
- **Keep the source path in every chunk's metadata** (`repo`, `path`,
  `heading`). Retrieval answers must cite the file path, per the Sentinel
  system prompt.
- **Config files are ground truth for config questions.** When a question is
  about a model name, a route, a fallback, or a masking flag, the chunk from
  the YAML / Go struct wins over any prose summary.

## Embedding guidance

- Use a local embedding model served on the B60 where possible (same
  llama-swap pattern as the chat models); a remote embedding endpoint is a
  fallback, not the default.
- One embedding model for the whole corpus -- do not mix embedding models
  across repos, or similarity scores stop being comparable.
- Re-embed only the chunks whose source file changed (see Refresh below).

## Refresh

1. `git pull` each of the three repos (or re-clone if the local copy is stale).
2. Diff against the last indexed commit per repo. Re-chunk and re-embed only
   the files that changed; drop chunks whose source file was deleted.
3. Record the indexed commit SHA per repo in the index metadata so a stale
   answer can be traced to the exact source version.
4. Re-run refresh after any merged PR that touches `docs/`,
   `gateway/config.yaml`, `llama-swap/models.yaml`, `pkg/config/`, or
   `internal/mask/`. Config-only PRs (like the Sentinel-Arc routing work)
   are the most common trigger.
5. Never auto-index a new repo or a new path. Add it to the table above
   first, with the exact verified path, then index it.

## What is intentionally not indexed

- Model weight files (`V:\AI\models\*.gguf`) -- binaries, not text.
- Logs, caches, and databases (TokenRonin SQLite/Postgres, cache DBs).
- Anything under a private repo that has not been explicitly listed here.
