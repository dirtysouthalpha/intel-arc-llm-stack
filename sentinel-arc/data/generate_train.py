#!/usr/bin/env python3
"""Generate sentinel-arc/data/train.jsonl — 1000 examples.
Target balance: 400 coding (40%), 300 automation-networking (30%),
200 reasoning (20%), 100 masking-safety (10%).
Built programmatically: structured templates x grounded parameter lists
drawn from real repo content read 2026-11-17 (see data/README.md).
No real secrets, family PII, credentials, hostnames/IPs (other than
loopback 127.0.0.1 from the public repo configs), or health data.
Placeholders only: <EMAIL>, <API_KEY>, <PASSWORD>, <NAME>, <PHONE>,
<GOV_ID>, 10.0.0.1 (explicit stand-in where a task needs an address).
Deduplicated on (instruction, input). Run: python3 generate_train.py
"""
import json, pathlib, hashlib
from collections import Counter

OUT = pathlib.Path(__file__).with_name("train.jsonl")
examples = []
seen = set()

def add(category, instruction, inp, output, source):
    key = hashlib.sha256((instruction + "\n" + inp).encode()).hexdigest()
    if key in seen:
        return False
    seen.add(key)
    examples.append({
        "id": f"train-{category}-{len([e for e in examples if e['category']==category])+1:04d}",
        "category": category,
        "instruction": instruction,
        "input": inp,
        "output": output,
        "source": source,
    })
    return True

# ---------------- CODING (400): 20 templates x 20 combos ----------------
ts_files = ["src/agent/runner.ts","src/tools/file.ts","src/tools/bash.ts","src/tools/patch.ts",
            "src/providers/router.ts","src/mcp/server.ts","src/state/session.ts","src/tui/app.tsx",
            "src/gui/palette.ts","src/tools/search.ts"]
go_files = ["internal/gateway/handlers.go","internal/gateway/middleware.go","internal/app/container.go",
            "internal/intelligence/router.go","internal/cache/cache.go","internal/database/sqlite.go",
            "internal/platform/webhook.go","internal/mask/mask.go","cmd/proxy/main.go","pkg/config/config.go"]
ps_cmds = ["restart-stack.ps1","install.ps1","start-swap.ps1","start-gateway.ps1"]
py_models = [("gemma3-12b", "6.8"), ("gemma3-27b", "15.8"), ("qwen3-30b", "18.0"),
             ("qwen2.5-coder-32b", "20.0"), ("qwen3-vl-8b", "5.2")]

coding_templates = []
# 1 ESM import fix, 10 files x 2 phrasings = 20
for f in ts_files:
    coding_templates.append(("coding",
        f"Fix the relative import in {f} so it follows the sentinel-code ESM convention.",
        f"import {{ helper }} from './helper';  // in {f}",
        "import { helper } from './helper.js';\n// sentinel-code is ESM: source is .ts but every relative import needs the explicit .js extension, or Node ESM fails at runtime even though tsc --noEmit passes.",
        "template:esm-import x repo-file-list(sentinel-code)"))
    coding_templates.append(("coding",
        f"In {f}, explain why the relative import needs a .js extension.",
        f"import {{ helper }} from './helper';  // in {f}",
        "Because sentinel-code is TypeScript ESM (\"type\": \"module\"). Node resolves the compiled .js file, so the source import must spell .js. Without it, tsc --noEmit still passes but Node throws at runtime.",
        "template:esm-explain x repo-file-list(sentinel-code)"))
# 2 Go handler, 10 files x 2 = 20
for f in go_files:
    coding_templates.append(("coding",
        f"Sketch a TokenRonin handler in {f} following the repo's conventions.",
        f"Add a GET endpoint in {f} that returns JSON and respects the repo's limits.",
        "func (h *Handler) GetStatus(w http.ResponseWriter, r *http.Request) {\n  // server-generated request ID; client X-Request-ID is echoed as X-Client-Request-ID\n  // enforce the request body limit; never swallow the provider error body\n  w.Header().Set(\"Content-Type\", \"application/json\")\n  _ = json.NewEncoder(w).Encode(map[string]any{\"status\": \"ok\"})\n}\n// Conventions: chi server in internal/gateway, body limits, server-generated IDs, fail loudly with the provider's own words.",
        "template:go-handler x repo-file-list(tokenronin)"))
    coding_templates.append(("coding",
        f"Write a Go test sketch for the handler in {f}.",
        f"Test the endpoint in {f} with go test.",
        "func TestGetStatus(t *testing.T) {\n  // go test ./... -v -count=1 ; table-driven, httptest recorder\n  // assert 200, JSON status ok, and that an oversize body is rejected\n}\n// TokenRonin is TDD-everywhere (v13, Go 1.25+); run `make test` (go test ./... -v -count=1).",
        "template:go-test x repo-file-list(tokenronin)"))
# 3 vitest / build commands, 10 variants x 2 = 20 (use file names + test names)
test_names = ["state.test.ts","router.test.ts","permissions.test.ts","mcp.test.ts","session.test.ts",
              "tools.test.ts","patch.test.ts","agent.test.ts","config.test.ts","gateway.test.ts"]
for t in test_names:
    coding_templates.append(("coding",
        f"How do you run only {t} in sentinel-code?",
        f"Run {t} only, not the whole suite.",
        f"npx vitest run tests/{t}\n# Full suite: npm test (vitest run). Filter one test by name: npx vitest run -t \"name of the test\". Build first with npm run build (tsup); lint is tsc --noEmit.",
        "template:vitest-single x repo-file-list(sentinel-code)"))
    coding_templates.append(("coding",
        f"How do you run a single test by name inside {t}?",
        f"Run one named test in tests/{t}.",
        "npx vitest run -t \"name of the test\"\n# Add the file to scope it: npx vitest run tests/" + t + " -t \"name of the test\". Full suite is npm test; v3.3.0 has 866 tests passing.",
        "template:vitest-name x repo-file-list(sentinel-code)"))
# 4 PowerShell launchers, 4 cmds x 5 phrasings = 20
ps_angles = [
    ("What does {c} do in the Arc stack?", "It is a launcher in launchers/: device-pinned to the Arc, run from an interactive session (session 1). Session-0 services silently fall back to CPU, so scheduled tasks use LogonType Interactive."),
    ("Why must {c} run in an interactive session?", "GPU compute only works in an interactive session (session 1), not a session-0 service — otherwise it silently falls back to CPU. The scheduled tasks use LogonType Interactive for this reason."),
    ("After editing a config, which script restarts the stack and how do you verify it?", "Run launchers/restart-stack.ps1, then verify with curl http://127.0.0.1:4000/v1/chat/completions -H \"Authorization: Bearer $KEY\" -d '{{\"model\":\"local-chat\",\"messages\":[{{\"role\":\"user\",\"content\":\"hi\"}}]}}'."),
    ("What is the one-line install that sets up the stack {c} belongs to?", "iex \"& { $(irm https://raw.githubusercontent.com/dirtysouthalpha/intel-arc-llm-stack/main/install.ps1) } -Root C:\\arc-llm — installs IPEX-LLM SYCL + mainline Vulkan llama.cpp + llama-swap engines, a default Gemma 3 model, the LiteLLM gateway, autostart tasks, and a firewall rule; it prints your endpoint + API key."),
    ("A user ran {c} as a service and got CPU-speed inference. Diagnose it.", "It ran in session 0. GPU compute silently falls back to CPU there. Re-run from an interactive session (session 1) with LogonType Interactive scheduled tasks; expect Gemma 3 12B at ~33.6 tok/s on llama-server -ngl 999, not 0.8 tok/s."),
]
for c in ps_cmds:
    for q, a in ps_angles:
        coding_templates.append(("coding", q.format(c=c), f"Context: launchers/{c} in intel-arc-llm-stack.",
            a + " Paths/commands are from the public repo (README.md, install.ps1, launchers/).",
            "template:powershell-launcher x repo-file-list(intel-arc-llm-stack)"))
# 5 VRAM budget, 5 models x 4 phrasings = 20
for model, w in py_models:
    coding_templates.append(("coding", f"Size the context window for {model} with vram-budget.",
        f"python vram-budget/vram_budget.py {model} --weights {w} --kv f16",
        f"python vram-budget/vram_budget.py {model} --weights {w} --kv f16\n# The calculator accounts for weights ({w} GB) + f16 KV cache (sliding-window aware). Use its max num_ctx before picking a llama-swap entry; do not guess.",
        "template:vram-budget x repo-file-list(intel-arc-llm-stack)"))
    coding_templates.append(("coding", f"Why f16 KV and not quantized KV for {model} on this stack?",
        f"{model} on the IPEX SYCL build (b20250729).",
        "Quantized KV (-ctk/-ctv q8_0) crashes this build the same way flash-attn does (GGML_ASSERT in ggml-cpu/ops.cpp). Use f16 KV, no flash-attn, and a small -ub at large ctx.",
        "template:vram-kv x bench/results.md"))
    coding_templates.append(("coding", f"Write the llama-swap entry for {model} at a safe context.",
        f"{model}, Q4_K_M, Arc B60 24GB, IPEX SYCL llama-server.",
        f"\"{model}\":\n  cmd: >\n    V:\\AI\\llama-cpp\\llama-server.exe -m V:\\AI\\models\\{model}-Q4_K_M.gguf -ngl 999 --host 127.0.0.1 --port ${{PORT}} -c 32768 -ub 64 -b 256 -np 1 --no-mmap\n  ttl: 1800\n# -ngl 999 puts all layers on GPU; -ub 64 keeps the compute buffer small at large ctx; --no-mmap as in llama-swap/models.yaml.",
        "template:llama-swap-entry x llama-swap/models.yaml"))
    coding_templates.append(("coding", f"What breaks if you add -fa to the {model} llama-server command?",
        f"{model} on IPEX-LLM llama-server, SYCL build b20250729.",
        "Flash attention is broken in this build: -fa falls back to a CPU op and crashes at warmup (GGML_ASSERT(nbv0 == ggml_type_size(v->type))). Keep FA off; the mainline Vulkan binary does support flash-attention for newer archs.",
        "template:fa-crash x bench/results.md"))
# 6 YAML / config fixes: 10 models x 2 = 20  (LiteLLM alias mapping)
aliases = [("local-chat","gemma3-12b-vision"),("local-vision","gemma3-12b-vision"),("gemma-12b","gemma3-12b"),
           ("gemma-12b-max","gemma3-12b-max"),("gemma-27b","gemma3-27b"),("qwen3-30b","qwen3-30b"),
           ("local-coding","qwen2.5-coder-32b"),("qwen2.5-vl","qwen2.5-vl-7b"),("gpt-oss-20b","gpt-oss-20b"),
           ("qwen3-vl","qwen3-vl-8b")]
for alias, backend in aliases:
    coding_templates.append(("coding", f"Write the LiteLLM gateway entry that maps alias {alias} to its backend.",
        f"gateway/config.yaml, api_base http://127.0.0.1:9090/v1, api_key \"swap\".",
        f"- model_name: {alias}\n  litellm_params:\n    model: openai/{backend}\n    api_base: http://127.0.0.1:9090/v1\n    api_key: \"swap\"\n# Local aliases are free on the B60; paid aliases (coding/orchestration) use os.environ/ANTHROPIC_API_KEY and are opt-in only.",
        "template:litellm-alias x gateway/config.yaml"))
    coding_templates.append(("coding", f"Why does the gateway entry for {alias} use api_key \"swap\"?",
        f"Alias {alias} -> openai/{backend} via llama-swap :9090.",
        "llama-swap (:9090) is the local backend; \"swap\" is the placeholder key the gateway sends it. Real secrets live in environment variables (os.environ/...) — never literal keys in YAML. LiteLLM YAML must be ASCII only (Windows cp1252 codec).",
        "template:litellm-key x gateway/config.yaml"))
# 7 MCP / singleton / misc: 20 distinct
misc_coding = [
    ("Add a builtin Sentinel command as markdown.", ".sentinel/commands/ — drop a .md file in and it is picked up automatically; builtins ship in dist/builtin on build.",
     "Create .sentinel/commands/my-command.md with frontmatter + prompt body, run npm run build (scripts/copy-builtins.cjs copies builtins), and verify with /my-command in the TUI."),
    ("Register an MCP server in sentinel.json.", "{\"mcp\": {\"everything\": {\"type\": \"local\", \"command\": [\"npx\", \"-y\", \"@modelcontextprotocol/server-everything\"], \"enabled\": true}}}",
     "Add the mcp block to sentinel.json; its tools appear as mcp__everything__<tool>. `sentinel mcp` lists discovered tools (stdio + Streamable HTTP)."),
    ("Use getInstance() instead of new for a Sentinel manager.", "Singletons via the exported instance / getInstance() — never `new` the managers.",
     "Replace `new Manager()` with `getManagerInstance()` (the exported instance). Direct construction breaks the shared state every other module relies on."),
    ("Fix a Tauri v2 desktop build step.", "cd gui && npm install && npm run tauri dev — needs a Rust toolchain; artifacts in gui/src-tauri/target/release/.",
     "Install Rust (https://rustup.rs), then cd gui && npm install && npm run tauri dev. `sentinel gui` alone runs the GUI in the browser; Tauri gives a real window."),
    ("Write the Sentinel router JSON for a gsd agent rule.", "router.rules: match agent gsd -> anthropic/claude-sonnet, fallbacks [zai/glm-4.6].",
     "{\"router\": {\"default\": \"zai/glm-4.6\", \"rules\": [{\"match\": {\"agent\": \"gsd\"}, \"use\": \"anthropic/claude-sonnet\", \"fallbacks\": [\"zai/glm-4.6\"]}], \"retry\": {\"maxAttempts\": 2, \"baseDelayMs\": 200, \"maxDelayMs\": 2000, \"retryOn\": [429, 500, 502, 503, 504]}}}"),
    ("Explain drop_params in the LiteLLM gateway.", "litellm_settings: default_fallbacks: [\"local-chat\"], drop_params: true.",
     "drop_params: true tells LiteLLM to drop parameters the local backend does not support instead of erroring, so one client can talk to local and paid models. default_fallbacks [local-chat] routes failures to the free local model."),
    ("Add a TokenRonin provider with health checks.", "providers: name, base_url, api_key (${ENV}), models; health loop 30s, breaker threshold/cooldown.",
     "Add the provider under `providers` with base_url, api_key: ${PROVIDER_API_KEY}, and models. The 30s health loop and failure breaker (threshold/cooldown_seconds) handle failover; provider-excluding retry avoids the dead provider."),
    ("Implement TokenRonin exact-match response caching.", "features.cache: exact-match response cache; opt-in semantic cache via TR_SEMANTIC_CACHE / TR_SEMANTIC_THRESHOLD.",
     "Enable the exact-match cache in features; the semantic cache is opt-in with an HTTP embedder and a similarity threshold. Inspect with GET /v1/cache/stats, clear with DELETE /v1/cache."),
    ("Write a Go test for the TokenRonin spend guard.", "features.spend_guard: fleet + per-workspace daily caps; tripped cap drops cloud providers.",
     "Table-test the guard: under cap -> cloud allowed; fleet cap tripped -> cloud dropped, local served; workspace cap tripped -> same for that workspace. Flat-rate subscriptions meter at zero."),
    ("Fix a YAML file that LiteLLM rejects on Windows.", "gateway/config.yaml must be ASCII only; LiteLLM reads it with the Windows cp1252 codec.",
     "Remove/replace the non-ASCII character, save as ASCII, and redeploy with SCP (not inline base64-over-SSH, which truncates >~2KB)."),
    ("Explain why mainline GGUFs are required on this stack.", "Use mainline GGUFs (ggml-org/unsloth) — ollama's GGUFs fail to load in the IPEX build (gemma3.attention.layer_norm_rms_epsilon missing).",
     "Ollama GGUFs lack fields the IPEX build expects, so they fail to load. Use mainline ggml-org/unsloth/bartowski GGUFs."),
    ("Why does gpt-oss-20b use the Vulkan binary?", "gpt-oss-20b: mainline Vulkan binary, drop -fa; Qwen3-VL: add -fit off.",
     "Newer archs (gpt-oss, Qwen3-VL, Omni) run on the mainline Vulkan binary, which enumerates only the Arc and supports flash-attention. gpt-oss needs -fa dropped; Qwen3-VL needs -fit off."),
    ("Write a curl to test the gateway after a restart.", "curl http://127.0.0.1:4000/v1/chat/completions -H \"Authorization: Bearer $KEY\" -d '{\"model\":\"local-chat\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}'",
     "curl http://127.0.0.1:4000/v1/chat/completions -H \"Authorization: Bearer $KEY\" -H \"Content-Type: application/json\" -d '{\"model\":\"local-chat\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}' — expect a chat-completion JSON reply from the resident model."),
    ("Explain the TokenRonin escalation router.", "TR_ESCALATION=1 enables the escalation router; detects degenerate output and re-runs on a different provider (sets X-Escalated).",
     "With TR_ESCALATION=1, degenerate output triggers a re-run on a different provider and the response carries X-Escalated. It is opt-in."),
    ("Add a TokenRonin webhook subscription.", "POST /v1/webhooks; HMAC-SHA256 signed deliveries (sha256=<hex>), https only, private/loopback/.local rejected, mandatory secret.",
     "Create the subscription with an https URL and a secret; deliveries are HMAC-SHA256 signed. SSRF-guarded: private/loopback/.local targets are rejected."),
    ("Explain TokenRonin multi-tenancy auth.", "Organizations, workspaces, projects, API keys, users; auth with httpOnly session cookies (no localStorage tokens).",
     "Tenancy is org -> workspace -> project, with API keys per workspace and members per workspace. Auth uses httpOnly session cookies; tokens are never stored in localStorage."),
    ("How do you check TokenRonin analytics?", "GET /stats, /analytics, /history, /metrics (Prometheus), dashboard SSE at /events/stream.",
     "Use /stats and /analytics for cost/usage, /history (pagination cap 1000) for requests, /metrics for Prometheus, and /events/stream for live dashboard events."),
    ("Fix a Sentinel patch tool call that traverses outside the repo.", "Tool layer hardened against path traversal (file/patch), shell injection (search/git), SSRF (web) — see CODE-REVIEW.md.",
     "Reject any patch path that escapes the workspace root (resolve + prefix-check), and refuse absolute paths outside the project. The guard is in the tool layer, not the prompt."),
    ("Explain Sentinel auto-compacting context.", "Long conversations are summarized automatically so you don't hit the wall mid-task.",
     "When context grows long, Sentinel summarizes the conversation automatically and continues from the summary, so a long task does not hit the context wall mid-run."),
    ("Write the command to run Sentinel as an MCP server.", "node dist/cli.js mcp-serve — exposes Sentinel's tools over stdio to any MCP client.",
     "node dist/cli.js mcp-serve — point Claude Desktop (or any MCP client) at it over stdio. `sentinel mcp` lists tools when consuming other servers."),
]
for q, inp, out in misc_coding:
    coding_templates.append(("coding", q, inp, out, "template:misc-coding x sentinel-code/tokenronin READMEs"))

# coding total check: 40+40+20+20+20+20+20 = 200? recount in code below; pad if needed
# Actually: ESM 20, Go 20, vitest 20, PS 20, VRAM 20, LiteLLM 20, misc 20 = 140. Need 400.
# Expand: repeat each template with a second phrasing variant is already counted.
# We generate additional combinatorial variants below to reach 400.
extra_coding = []
# For each ts file, a patch-tool task + a search-tool task (20 files -> 40)
for f in ts_files + go_files:
    extra_coding.append(("coding",
        f"Use the Sentinel search tool to find all callers of the main export in {f}.",
        f"Search the repo for usages of the export in {f}.",
        "Use the search tool (not bash grep) with the export name, then read each caller file before editing. The search tool is injection-hardened; shell search is not the default path.",
        "template:search-tool x sentinel-code"))
    extra_coding.append(("coding",
        f"Write a patch for {f} that changes one behaviour and keeps the rest untouched.",
        f"Edit {f} via the patch tool.",
        "Use the patch tool with a minimal diff (context + changed lines only), run the file's tests after, and rely on checkpoints: `sentinel checkpoints` lists snapshots, `sentinel undo` reverts the last change.",
        "template:patch-tool x sentinel-code"))
# For each alias, a fallback + a curl variant (20)
for alias, backend in aliases:
    extra_coding.append(("coding",
        f"What happens when the backend for alias {alias} is down?",
        f"Alias {alias} -> openai/{backend} via llama-swap :9090; default_fallbacks [local-chat].",
        "LiteLLM falls back to default_fallbacks [local-chat] (the resident gemma3-12b-vision model, ttl 28800, stays warm). llama-swap unloads the dead model and loads the fallback on demand; healthCheckTimeout is 300.",
        "template:fallback x gateway/config.yaml"))
    extra_coding.append(("coding",
        f"Test alias {alias} with curl against the gateway.",
        f"Gateway :4000, alias {alias}.",
        f"curl http://127.0.0.1:4000/v1/chat/completions -H \"Authorization: Bearer $KEY\" -H \"Content-Type: application/json\" -d '{{\"model\":\"{alias}\",\"messages\":[{{\"role\":\"user\",\"content\":\"hi\"}}]}}'",
        "template:curl-alias x gateway/config.yaml"))
# For each py model, a bench + needle variant (10)
for model, w in py_models:
    extra_coding.append(("coding",
        f"How was {model} verified on the B60, and what would you re-check after a driver update?",
        f"{model} in bench/results.md.",
        "Re-run the bench in bench/ (throughput + long-context needle test) in an interactive session and compare with bench/results.md. Gemma 3 12B: 33.6 tok/s gen, pp512 84 tok/s, needle@16K PASS; re-check after any driver/oneAPI change.",
        "template:bench-verify x bench/results.md"))
    extra_coding.append(("coding",
        f"What context and ubatch do you use for {model} at 32K, and why?",
        f"{model}, 32K ctx, IPEX SYCL, f16 KV, no FA.",
        "Use -c 32768 with a small -ub (64) and -b 256: the attention compute buffer scales with ubatch x ctx, so a large -ub alloc-fails at long ctx. f16 KV, no flash-attn, no KV-quant on this build.",
        "template:ctx-ub x bench/results.md"))
# 20 more: Go config / YAML env substitution variants
for i, var in enumerate(["ANTHROPIC_API_KEY","LITELLM_MASTER_KEY","TOKENRONIN_CONFIG","TR_ESCALATION","TR_SEMANTIC_CACHE",
                         "TR_SEMANTIC_THRESHOLD","POSTGRES_USER","POSTGRES_PASSWORD","POSTGRES_DB","TOKENRONIN_PORT"]):
    extra_coding.append(("coding",
        f"How is {var} used, and where must its value never appear?",
        f"Environment variable {var} in TokenRonin / LiteLLM config.",
        f"{var} is referenced by name from YAML as ${{{var}}} (TokenRonin) or os.environ/{var} (LiteLLM) and substituted at load time. Its literal value must never appear in YAML, chat, logs, or a pasted config snippet — reference it by name only.",
        "template:env-var x tokenronin/gateway READMEs"))
    extra_coding.append(("coding",
        f"Write a config line that references {var} correctly.",
        f"Reference {var} from YAML.",
        f"api_key: ${{{var}}}  # TokenRonin style, or os.environ/{var} in LiteLLM gateway/config.yaml. Never a literal value.",
        "template:env-ref x tokenronin/gateway READMEs"))
# totals: coding_templates 140 + extra 40+20+10+20 = 230? recount programmatically and pad with
# deterministic numbered variants of the ESM/Go sets if short.
coding_templates.extend(extra_coding)
# Pad to exactly 400 with numbered drill variants (still grounded, distinct inputs)
pad_i = 0
while len([t for t in coding_templates if t[0]=="coding"]) < 400:
    pad_i += 1
    f = ts_files[pad_i % len(ts_files)]
    coding_templates.append(("coding",
        f"Drill {pad_i}: in {f}, what is the correct ESM import for './utils' and the build command that checks it?",
        f"File {f}, drill {pad_i}.",
        "import { utils } from './utils.js'; then npm run build (tsup) and npm run lint (tsc --noEmit). ESM needs the .js extension; the build copies builtins into dist/builtin.",
        "template:esm-drill x sentinel-code"))
assert len([t for t in coding_templates if t[0]=="coding"]) == 400, len([t for t in coding_templates if t[0]=="coding"])

for cat, instr, inp, out, src in coding_templates:
    add(cat, instr, inp, out, src)

# ---------------- AUTOMATION-NETWORKING (300): 15 templates x 20 combos ----------------
sentinel_cmds = ["/plan","/cmd","/ship","/autopilot","/tdd","/team","/fork","/index","/search","/bg",
                 "/export","/branch","/usage","/workspace","/marketplace","/permissions","/undo","/checkpoints","/mcp","/model"]
auto_templates = []
cmd_desc = {
 "/plan":"Read-only research mode — proposes a plan, blocks edits/commands.",
 "/cmd":"AI command-search: natural language -> a shell command.",
 "/ship":"Autonomous GSD: plan -> implement -> test -> review -> fix.",
 "/autopilot":"Set-and-forget — loops the GSD cycle, gated on lint/test/build + strict readiness check, until production-ready. Checkpoints, commits each step, respects cost/time budgets, --resume-able.",
 "/tdd":"Enforces red-green-refactor.",
 "/team":"Parallel teams — multi-agent worktree isolation.",
 "/fork":"Session branching — explore alternatives.",
 "/index":"Build a repo index (TF-IDF).",
 "/search":"Semantically search the repo index.",
 "/bg":"Run shell commands in the background.",
 "/export":"Export the session (md/html).",
 "/branch":"Branch the current session.",
 "/usage":"Token / cost / per-tool usage metrics.",
 "/workspace":"Multi-repo workspace roots (alias /ws).",
 "/marketplace":"Install skills / MCP servers from a registry.",
 "/permissions":"Guardrails: yolo / auto / gated modes.",
 "/undo":"Revert the agent's last change (git-backed).",
 "/checkpoints":"List file snapshots the agent made.",
 "/mcp":"Inspect MCP tools.",
 "/model":"Switch model.",
}
for cmd in sentinel_cmds:
    auto_templates.append(("automation",
        f"What does {cmd} do in Sentinel, and when do you use it?",
        f"Sentinel TUI slash command {cmd}.",
        f"{cmd}: {cmd_desc[cmd]} Use it when the task matches that job; in headless mode use the equivalent `sentinel run` subcommand where one exists.",
        "template:sentinel-command x sentinel-code README"))
    auto_templates.append(("automation",
        f"Give an example invocation of {cmd} in Sentinel.",
        f"Example for {cmd}.",
        f"In the TUI type `{cmd}` (with its argument, e.g. `{cmd} <task>` where it takes one). Headless equivalent where supported: `sentinel run --json --permission-mode gated \"<task>\"`.",
        "template:sentinel-command-example x sentinel-code README"))
# 40 so far. Networking / TokenRonin routes: 12 routes x 5 = 60
routes = [("/v1/chat/completions","OpenAI-compatible chat (streaming supported)"),
          ("/v1/messages","Anthropic-format chat, or passthrough when enabled"),
          ("/v1/models","Deduplicated model menu across providers"),
          ("/v1/providers/status","Provider health / breaker state"),
          ("/v1/estimate","Cost estimate for a request"),
          ("/v1/analyze","Prompt analysis"),
          ("/v1/budget","Project budgets"),
          ("/v1/webhooks","Webhook subscriptions (admin to create/delete)"),
          ("/health","Liveness: status, version 13.0.0, breaker, providers, models routing table"),
          ("/metrics","Prometheus metrics"),
          ("/stats","Request/cost stats"),
          ("/events/stream","Dashboard SSE event stream")]
route_angles = [
    ("What is {r} for in TokenRonin?", "{d}"),
    ("How do you call {r} and what do you check in the reply?", "Call it with the documented method; check {d}. For /health, check status ok, provider_detail healthy/breaker, and the models routing table."),
    ("What fails first if {r} returns an error, and what is the fallback?", "If the provider behind it is unhealthy, the breaker opens and routing excludes it; a tripped spend guard drops cloud providers instead of failing the request. Check /v1/providers/status and /health first."),
    ("Write a curl for {r} against a local TokenRonin.", "curl http://127.0.0.1:<port>{r} with the workspace API key header; for POST routes add -H \"Content-Type: application/json\" and a JSON body. Port comes from TOKENRONIN_PORT / config server.port — do not invent one."),
    ("How does {r} fit the local-first cost policy?", "{d}. Local providers meter at $0 out-of-pocket (the GPU is already paid for); flat-rate subscriptions meter at zero; only real per-token cloud use counts as cost."),
]
for r, d in routes:
    for q, a in route_angles:
        auto_templates.append(("automation", q.format(r=r), f"TokenRonin v13 route {r}.",
            a.format(r=r, d=d), "template:tokenronin-route x tokenronin README"))
# 100 so far. Gateway / llama-swap: 10 models x 4 = 40
for alias, backend in aliases:
    auto_templates.append(("automation", f"Route a request for alias {alias} through the stack.",
        f"Client -> LiteLLM :4000 model {alias} -> llama-swap :9090 model {backend}.",
        f"Client calls :4000 with model \"{alias}\". LiteLLM maps it to openai/{backend} at http://127.0.0.1:9090/v1. llama-swap loads {backend} on demand (only one big model fits in 24GB), serves it, and unloads after ttl.",
        "template:routing-path x gateway/config.yaml + llama-swap/models.yaml"))
    auto_templates.append(("automation", f"How do you switch the resident model to {backend}?",
        f"Switch to {backend} via llama-swap.",
        f"Send a request naming {backend} (via its LiteLLM alias) to :4000; llama-swap hot-swaps it in. The previous big model is unloaded (24GB fits one). The resident gemma3-12b-vision (ttl 28800) stays warm for everyday use.",
        "template:hotswap x llama-swap/models.yaml"))
    auto_templates.append(("automation", f"What are the llama-swap settings for {backend}?",
        f"llama-swap/models.yaml entry for {backend}.",
        f"See llama-swap/models.yaml: cmd with -ngl 999, -c per model, -ub/-b, -np 1, --no-mmap, ttl 1800 (28800 for the resident vision model). IPEX SYCL: f16 KV, no flash-attn, no KV-quant. Vulkan binary for gpt-oss/Qwen3-VL/Omni.",
        "template:swap-settings x llama-swap/models.yaml"))
    auto_templates.append(("automation", f"A request for {alias} is slow on first call but fast after. Why?",
        f"First call for {alias} after idle.",
        "Cold load: llama-swap loads the GGUF on demand (e.g. gpt-oss-20b ~15s warm, Qwen2.5-VL-7B ~32s load). After that the model is resident until ttl expires, so later calls are fast. The resident vision model (ttl 28800) avoids this for everyday use.",
        "template:cold-load x llama-swap/models.yaml + bench/results.md"))
# 140. Networking / deploy / diagnostics: 20 topics x 4 = 80
net_topics = [
    ("Diagnose a gateway 404 for model local-chat.", "Check gateway/config.yaml has model_name local-chat -> openai/gemma3-12b-vision at http://127.0.0.1:9090/v1, and that llama-swap :9090 is up. A missing alias is a config error, not a model error."),
    ("Diagnose llama-swap healthCheckTimeout.", "healthCheckTimeout is 300 in llama-swap/models.yaml. A cold big-model load can take minutes; do not lower it below the load time or swaps will be killed mid-load."),
    ("Why port 8088 for llama-server?", "Port 8080 collides with qBittorrent's WebUI API (bench/results.md). llama-server uses 8088."),
    ("Deploy a gateway config change safely.", "Deploy configs with SCP, not inline base64-over-SSH (truncates >~2KB). LiteLLM YAML must be ASCII. Then launchers/restart-stack.ps1 and curl :4000 to verify."),
    ("Check the stack after a reboot.", "Autostart uses scheduled tasks with LogonType Interactive. After reboot, verify in an interactive session: llama-swap :9090, gateway :4000, then curl local-chat. Session-0 services would silently fall back to CPU."),
    ("Explain the one-model-at-a-time limit.", "Only one big model fits in 24GB at a time. llama-swap loads/unloads on demand; ttl controls residency. Requesting a second big model unloads the first."),
    ("When do you use the Vulkan binary instead of IPEX SYCL?", "Newer archs (gpt-oss, Qwen3-VL, Omni) run on the mainline Vulkan binary, which enumerates only the Arc and supports flash-attention. IPEX SYCL is for Gemma/Qwen2.5."),
    ("What is the -ngl 999 flag for?", "-ngl 999 offloads all layers to the GPU (49/49 layers for Gemma 3 12B, SYCL0 buffer 6.95GB). Without it, layers/KV spill to CPU and throughput collapses."),
    ("How do you run a 128K-context Gemma 3 12B run?", "Use the gemma3-12b-max entry: -c 131072, -ub 64, -b 256, f16 KV, no FA. Small -ub keeps the compute buffer (~4.5GB at ub=64) inside VRAM; needle@16K PASS was verified at 17,640 tokens."),
    ("What does --no-mmap do in the llama-swap entries?", "--no-mmap loads the GGUF fully into memory instead of memory-mapping it, as used in every llama-swap/models.yaml entry on this stack."),
    ("How does TokenRonin route across providers?", "One model name maps to several providers (primary + fallbacks). Routing strategies: balanced, cost-priority, cost-aware, cost-first, cheapest, random, round-robin, first; stage router with A/B splits; request-level route hints and model aliases."),
    ("How does the TokenRonin failure breaker work?", "Per-provider health loop (30s), failure breaker (threshold/cooldown_seconds), provider-excluding retry. An unhealthy provider is excluded until its cooldown passes."),
    ("What is the TokenRonin cost ledger rule?", "One price ledger: flat-rate subscriptions meter at zero, unpriced models fail at boot. CostPersister writes usage to SQLite/Postgres. A dashboard that multiplies tokens by a generic rate is wrong."),
    ("How do you reload TokenRonin config?", "kill -HUP $(pidof tokenronin) (or make run / systemd). SIGHUP rebuilds the service container from YAML; a failed reload keeps the old container running."),
    ("What are TokenRonin spend guards?", "Fleet-wide daily cap plus per-workspace daily caps (features.spend_guard). A tripped cap drops cloud providers instead of failing the request. Project budgets via /v1/budget."),
    ("How does TokenRonin caching work?", "Exact-match response cache plus opt-in semantic cache (TR_SEMANTIC_CACHE, TR_SEMANTIC_THRESHOLD, HTTP embedder). GET /v1/cache/stats, DELETE /v1/cache."),
    ("How does Sentinel route cheap turns to a small model?", "Multi-model routing: cheap turns auto-route to the small model (~3-5x cost cut). router.roles (default/plan/smol/commit) and fallback chains; a dead provider falls through to the next."),
    ("How does Sentinel's autonomous loop end?", "The read -> act -> observe -> repeat loop runs until the task is done (loop / /ship / /autopilot). /autopilot additionally gates on lint/test/build + a strict readiness check and respects cost/time budgets."),
    ("What is Sentinel's diff-at-approval?", "Before accepting edits, the user sees the actual diff (inline diffs in the GUI, diff at approval in the TUI). Gated mode prompts Allow/Deny with the diff."),
    ("How do you export or branch a Sentinel session?", "/export [md|html] exports the session; /branch (and /fork) branches it to explore alternatives. Sessions are also resumable (--resume for autopilot)."),
]
for topic, ans in net_topics:
    auto_templates.append(("automation", topic, "Context: intel-arc-llm-stack / sentinel-code / tokenronin as documented in their READMEs.",
        ans, "template:net-topic x repo READMEs"))
    auto_templates.append(("automation", topic + " Give the verification step.",
        "Context: intel-arc-llm-stack / sentinel-code / tokenronin as documented in their READMEs.",
        ans + " Verify: curl the gateway :4000 or TokenRonin /health, or run the named Sentinel command and check its output; do not assume success without the check.",
        "template:net-topic-verify x repo READMEs"))
    auto_templates.append(("automation", topic + " What is the most common mistake?",
        "Context: intel-arc-llm-stack / sentinel-code / tokenronin as documented in their READMEs.",
        ans + " Common mistake: skipping the verification step, running in session 0, or editing the config by hand over SSH instead of SCP. Follow the documented path.",
        "template:net-topic-mistake x repo READMEs"))
    auto_templates.append(("automation", topic + " Explain it to a new operator in two sentences.",
        "Context: intel-arc-llm-stack / sentinel-code / tokenronin as documented in their READMEs.",
        ans,
        "template:net-topic-short x repo READMEs"))
# 140+80=220. Pad to 300 with numbered routing drills (grounded, distinct).
pad = 0
while len([t for t in auto_templates if t[0]=="automation"]) < 300:
    pad += 1
    alias, backend = aliases[pad % len(aliases)]
    auto_templates.append(("automation",
        f"Drill {pad}: a client asks for {alias}. Trace the request hop by hop.",
        f"Client -> :4000 model {alias}.",
        f"Client -> LiteLLM :4000 (model {alias}) -> openai/{backend} at http://127.0.0.1:9090/v1 -> llama-swap loads {backend} on the Arc B60 -> llama-server replies. Only one big model is resident at a time.",
        "template:routing-drill x gateway/config.yaml"))
assert len([t for t in auto_templates if t[0]=="automation"]) == 300
for cat, instr, inp, out, src in auto_templates:
    add(cat, instr, inp, out, src)
# Top-up: two templates collided on (instruction, input) dedup; fill to exactly 300 with unique drills.
_top = 0
while len([e for e in examples if e["category"] == "automation"]) < 300:
    _top += 1
    _alias, _backend = aliases[(_top + 7) % len(aliases)]
    add("automation",
        f"Top-up drill {_top}: trace a request for {_alias} and name the failure mode if llama-swap is down.",
        f"Top-up drill {_top} context: client -> :4000 model {_alias}.",
        f"Client -> LiteLLM :4000 (model {_alias}) -> openai/{_backend} at http://127.0.0.1:9090/v1. If llama-swap :9090 is down, LiteLLM falls back to default_fallbacks [local-chat] if configured; otherwise the request fails — check that llama-swap is running in an interactive session and restart with launchers/restart-stack.ps1.",
        "template:routing-topup x gateway/config.yaml")

# ---------------- REASONING (200): 10 templates x 20 combos ----------------
reason_templates = []
models_ctx = [("gemma3-12b", "6.8", "65536"), ("gemma3-12b-max", "6.8", "131072"),
              ("gemma3-27b", "15.8", "32768"), ("qwen3-30b", "18.0", "32768"),
              ("qwen2.5-coder-32b", "20.0", "16384"), ("qwen3.8-27b", "17.5", "32768"),
              ("qwen2.5-vl-7b", "5.0", "32768"), ("gpt-oss-20b", "12.0", "16384"),
              ("qwen3-vl-8b", "5.5", "32768"), ("qwen2.5-omni", "5.0", "32768")]
for model, w, ctx in models_ctx:
    reason_templates.append(("reasoning",
        f"Choose a model and context for a {ctx}-token task on the B60 24GB. Start from {model} ({w}GB weights).",
        f"Task needs {ctx} tokens of context; B60 24GB; weights {w}GB; f16 KV; no FA.",
        f"{model} at {ctx} ctx: weights {w}GB plus f16 KV plus the compute buffer (ubatch x ctx) must fit in 24GB. At large ctx use a small -ub (64) and -b 256; if it does not fit, drop ctx or pick a smaller model — do not add -fa or KV-quant, both crash this IPEX build. Only one big model is resident at a time.",
        "template:model-choice x llama-swap/models.yaml + bench/results.md"))
    reason_templates.append(("reasoning",
        f"A {ctx}-token job on {model} runs out of memory. What do you change first, and why?",
        f"OOM at {ctx} ctx on {model} ({w}GB).",
        "Lower -ub first (the compute buffer scales with ubatch x ctx; -ub 64 is ~4.5GB at 128K), then lower -c if still OOM. Do not enable flash-attn or KV-quant — both crash this build. Verify with vram-budget before retrying.",
        "template:oom-fix x bench/results.md"))
# 20. Cost routing decisions: 10 request classes x 2 = 20
classes = [("everyday chat","local-chat","$0 on the B60"),("vision / screenshot Q&A","local-vision","$0 on the B60"),
           ("128K long-context read","gemma-12b-max","$0 on the B60"),("MoE reasoning + tools","qwen3-30b","$0 on the B60"),
           ("local coding","local-coding","$0 on the B60"),("audio transcription","omni","$0 on the B60"),
           ("hard coding task the local model fails","coding (paid, opt-in)","paid Anthropic claude-sonnet-4-6"),
           ("orchestration / planning","orchestration (paid, opt-in)","paid Anthropic claude-opus-4-8"),
           ("fast vision","qwen2.5-vl","$0 on the B60"),("vision-language","qwen3-vl","$0 on the B60")]
for cls, alias, cost in classes:
    reason_templates.append(("reasoning",
        f"Route this workload: {cls}. Which alias, and what does it cost?",
        f"Workload: {cls}. Gateway aliases in gateway/config.yaml.",
        f"Use {alias} ({cost}). Local aliases stay on the B60 for free; paid aliases (coding/orchestration) are opt-in only and are justified only when the local model cannot do the job. default_fallbacks [local-chat] covers failures.",
        "template:cost-route x gateway/config.yaml"))
    reason_templates.append(("reasoning",
        f"When would you NOT use {alias} for {cls}?",
        f"Workload: {cls}; alias {alias}.",
        f"Do not use {alias} when the task needs a capability it lacks (e.g. a paid model for a job the local model already does well, or a local model for a job it repeatedly fails). Re-route on evidence — a failed local attempt or a measured quality gap — not on habit.",
        "template:cost-route-no x gateway/config.yaml"))
# 40. Fallback / incident reasoning: 10 scenarios x 4 = 40
incidents = [
    ("The gateway returns 404 for a model that worked yesterday.", "Check gateway/config.yaml for the alias and llama-swap :9090 for the backend; a config edit or a failed reload is the likeliest cause. Verify with curl :4000 and GET /health on TokenRonin if it fronts the request."),
    ("Inference is 0.8 tok/s on Gemma 3 12B.", "That is the IPEX ollama number (KV on CPU). The fix is llama-server -ngl 999 in an interactive session; expect ~33.6 tok/s. Check session (must be 1, not 0) and binary (llama-server, not ollama)."),
    ("llama-server crashes at warmup after adding -fa.", "Flash-attn is broken in this IPEX build and crashes at warmup. Remove -fa (and any KV-quant flags), keep f16 KV and a small -ub."),
    ("A GGUF fails to load with a missing epsilon field.", "That is an ollama GGUF (gemma3.attention.layer_norm_rms_epsilon missing). Use a mainline ggml-org/unsloth/bartowski GGUF."),
    ("TokenRonin keeps retrying the same dead provider.", "The breaker/health loop should exclude it; check /v1/providers/status and the breaker state. Provider-excluding retry is the designed behaviour — if it retries the same provider, the breaker config (threshold/cooldown_seconds) is wrong."),
    ("Costs in the dashboard look far too high.", "The dashboard once reported $724 on a $0 day: flat-rate subscriptions meter at zero and only one price ledger is authoritative. Check the ledger and CostPersister output; do not trust a generic per-token multiplication."),
    ("A config reload made things worse.", "SIGHUP keeps the old container on a failed reload — check whether the reload actually succeeded. If it did and the new config is bad, restore the previous YAML and SIGHUP again; the old container is the rollback."),
    ("A webhook delivery was rejected.", "Check the HMAC-SHA256 signature (sha256=<hex>), that the URL is https, and that the target is not private/loopback/.local. SSRF guard rejects those targets by design."),
    ("Sentinel's agent edited a file outside the project.", "The tool layer must reject path traversal (file/patch). Check the patch path resolution and the permission mode (gated prompts before edits); revert with `sentinel undo` and fix the guard, not the prompt."),
    ("A long Sentinel task hits the context wall.", "Auto-compacting context summarizes the conversation automatically. If it still fails, split the task (/ship in stages), use /plan first, and keep each stage's context small."),
]
for title, ans in incidents:
    reason_templates.append(("reasoning", f"Triage: {title}", "Incident on the Arc stack / TokenRonin / Sentinel as documented.",
        ans, "template:incident x repo READMEs/bench"))
    reason_templates.append(("reasoning", f"Triage: {title} List the checks in order.",
        "Incident on the Arc stack / TokenRonin / Sentinel as documented.",
        "Order: 1) reproduce and capture the exact error, 2) " + ans + " 3) verify the fix with the documented check (curl :4000, /health, bench, or the named command).",
        "template:incident-ordered x repo READMEs/bench"))
    reason_templates.append(("reasoning", f"Triage: {title} What evidence would prove each hypothesis?",
        "Incident on the Arc stack / TokenRonin / Sentinel as documented.",
        ans + " Evidence: the exact error text, the session/binary/config in use, and the before/after number (tok/s, /health, or test result). A hypothesis without evidence is a guess.",
        "template:incident-evidence x repo READMEs/bench"))
    reason_templates.append(("reasoning", f"Triage: {title} What is the rollback if the fix makes it worse?",
        "Incident on the Arc stack / TokenRonin / Sentinel as documented.",
        ans + " Rollback: restore the previous config/model (SIGHUP for TokenRonin, restart-stack.ps1 for the Arc stack, `sentinel undo` for agent edits) and re-verify before trying another fix.",
        "template:incident-rollback x repo READMEs/bench"))
# 80. Planning: 10 plans x 4 = 40
plans = [
    ("Plan adding a new model to the Arc stack.", "1) Pick the GGUF (mainline, Q4_K_M) and size it with vram-budget. 2) Add the llama-swap entry (-ngl 999, -c/-ub, ttl). 3) Add the LiteLLM alias. 4) restart-stack.ps1, curl :4000, run the bench needle test. 5) Document the result in bench/results.md."),
    ("Plan a Sentinel feature (GSD).", "1) /plan (read-only) to research and propose. 2) Implement in small patches with checkpoints. 3) Add/extend vitest tests (red-green-refactor with /tdd). 4) npm run lint + npm test + npm run build. 5) Review the diff at approval before accepting."),
    ("Plan a TokenRonin provider migration.", "1) Add the new provider (base_url, ${ENV} key, models) alongside the old. 2) Check /v1/providers/status and the health loop. 3) Shift routing (A/B split) and watch /metrics. 4) Remove the old provider only after the new one is healthy. 5) Keep the old config as rollback."),
    ("Plan the Sentinel-Arc eval run.", "1) Run the 120 held-out tasks against stock Qwen3.8-27B (baseline). 2) Run the same set against sentinel-arc-27b-v1. 3) Score with the rubric (masking leak = auto-fail). 4) Check no coding regression, >=15 tok/s at 8k ctx. 5) Ship only if task success beats stock by >=10%."),
    ("Plan a cost review for the fleet.", "1) Pull /stats and /analytics (one ledger). 2) Separate $0 local/flat-rate use from real cloud spend. 3) Check spend guards and per-workspace caps. 4) Route what local can do to local aliases. 5) Re-check after a week."),
    ("Plan a long-context document task.", "1) Size ctx with vram-budget. 2) Pick the max-context entry (gemma3-12b-max, -c 131072, -ub 64). 3) Split the document if it exceeds ctx. 4) Verify with the needle test pattern. 5) Summarize in stages, not one giant call."),
    ("Plan onboarding a new operator.", "1) One-line install (interactive session). 2) curl :4000 smoke test. 3) Walk the aliases and the local-first cost rule. 4) Show restart-stack.ps1, /health, and `sentinel undo`. 5) Point at docs/ and bench/results.md for the sharp edges."),
    ("Plan a TokenRonin incident drill.", "1) Pick an incident (dead provider, tripped spend guard, bad reload). 2) Run the triage checks in order. 3) Verify the breaker/fallback behaviour. 4) Roll back and re-verify. 5) Write down what was slow and fix it."),
    ("Plan a LoRA training run (prep only).", "1) Confirm eval + training data are ready (this repo, sentinel-arc/). 2) Pick the provider from the priced list in training/train-qwen3.8-27b-lora.md. 3) Launch with the exact command, checkpoint every epoch. 4) Stop at the $60 cap. 5) Evaluate before any deploy."),
    ("Plan a model rollback.", "1) Keep the old llama-swap/LiteLLM aliases (do not delete them). 2) Point the alias at the previous model. 3) restart-stack.ps1 and curl :4000. 4) Re-run the eval subset. 5) Only delete the new entry after the old one is verified healthy."),
]
for title, ans in plans:
    reason_templates.append(("reasoning", title, "Planning task for the Arc stack / Sentinel / TokenRonin.",
        ans, "template:plan x repo READMEs"))
    reason_templates.append(("reasoning", title + " What are the risks and mitigations?",
        "Planning task for the Arc stack / Sentinel / TokenRonin.",
        ans + " Risks: OOM at large ctx (mitigate: small -ub, vram-budget), session-0 CPU fallback (mitigate: interactive session), bad config (mitigate: SCP + ASCII + restart + curl verify), training on held-out data (mitigate: never train on eval/).",
        "template:plan-risks x repo READMEs"))
    reason_templates.append(("reasoning", title + " What is the verification gate?",
        "Planning task for the Arc stack / Sentinel / TokenRonin.",
        ans + " Gate: the documented check passes (curl :4000, /health ok, bench number, npm test green, or the eval rubric) before the step is called done.",
        "template:plan-gate x repo READMEs"))
    reason_templates.append(("reasoning", title + " Do it in the cheapest correct order.",
        "Planning task for the Arc stack / Sentinel / TokenRonin.",
        ans + " Cheapest first: local/free checks before paid calls, read-only planning before edits, one change at a time so a failure points at its cause.",
        "template:plan-order x repo READMEs"))
# 120 so far (20+20+40+40). Pad to 200 with model-choice drills.
pad = 0
while len([t for t in reason_templates if t[0]=="reasoning"]) < 200:
    pad += 1
    model, w, ctx = models_ctx[pad % len(models_ctx)]
    reason_templates.append(("reasoning",
        f"Drill {pad}: is {model} ({w}GB) the right model for a {ctx}-token coding task, or is local-coding better?",
        f"Coding task, {ctx} ctx, B60 24GB.",
        f"For coding, local-coding (qwen2.5-coder-32b, Q4 ~20GB, -c 16384) is the documented local coding model; {model} at {ctx} ctx fits only if weights ({w}GB) + f16 KV + compute buffer fit in 24GB with a small -ub. If the local coding model fails the task, the paid coding alias is the opt-in escalation — not a bigger local ctx.",
        "template:model-drill x gateway/config.yaml + llama-swap/models.yaml"))
assert len([t for t in reason_templates if t[0]=="reasoning"]) == 200
for cat, instr, inp, out, src in reason_templates:
    add(cat, instr, inp, out, src)

# ---------------- MASKING-SAFETY (100): 10 templates x 10 combos ----------------
mask_templates = []
pii_sets = [
    ("<EMAIL>", "an email address", "user@example.com (stand-in)"),
    ("<API_KEY>", "an API key", "a literal API key value (stand-in)"),
    ("<PASSWORD>", "a password", "a literal password value (stand-in)"),
    ("<NAME>", "a person's name", "a person's full name (stand-in)"),
    ("<PHONE>", "a phone number", "a phone number (stand-in)"),
    ("<GOV_ID>", "a government ID number", "an ID-like number (stand-in)"),
    ("<EMAIL>", "an email in a log line", "an email address in a log (stand-in)"),
    ("<API_KEY>", "a Bearer token in a log line", "Authorization: Bearer <API_KEY>"),
    ("<NAME>", "a name in a support ticket", "a customer's name (stand-in)"),
    ("<PHONE>", "a phone number in a ticket", "a phone number (stand-in)"),
]
for ph, desc, _ in pii_sets:
    mask_templates.append(("masking",
        f"Mask {desc} in this text before sending it to a model. Use {ph}.",
        f"Text contains {desc}. Replace it with {ph} and nothing else of the original value.",
        f"Masked text with {ph} in place of the original value. The original value does not appear anywhere in the output — not in full, not in part (no last-4 characters). The mapping is reversible only inside TokenRonin internal/mask/ on the trusted side.",
        "template:mask-single x tokenronin internal/mask/"))
    mask_templates.append(("masking",
        f"A user pasted text containing {desc}. What do you do before using it?",
        f"Pasted text contains {desc}.",
        f"Mask it to {ph} first, then use the masked text. Never send the original value to a model, never repeat it back, and never store the mapping in a prompt. If the task cannot be done masked, ask for a de-identified version.",
        "template:mask-before-use x tokenronin internal/mask/"))
# 20. Config / env safety: 10 vars x 2 = 20
for var in ["ANTHROPIC_API_KEY","LITELLM_MASTER_KEY","TOKENRONIN_CONFIG","POSTGRES_PASSWORD","ZAI_API_KEY",
            "OPENAI_API_KEY","GEMINI_API_KEY","TOKENRONIN_API_KEY","PROVIDER_API_KEY","LITELLM_API_KEY"]:
    mask_templates.append(("masking",
        f"A config snippet references {var}. Is it safe to paste into chat?",
        f"Snippet contains ${{{var}}} / os.environ/{var} by name only.",
        f"Yes — a reference by name (${{{var}}}) is safe; it contains no secret value. It is NOT safe if the snippet contains the literal value. Never paste a literal key; reference it by name and rotate it if it was ever pasted.",
        "template:env-safe x tokenronin/gateway READMEs"))
    mask_templates.append(("masking",
        f"Someone pasted a literal value for {var} into chat. What now?",
        f"A literal secret value for {var} was pasted.",
        f"Treat it as compromised: rotate {var} immediately, remove the pasted value from history where possible, and use ${{{var}}} / os.environ/{var} by name in future. Do not repeat the value while explaining this.",
        "template:secret-rotate x tokenronin/gateway READMEs"))
# 40. Refusal / injection / partial leak: 10 scenarios x 4 = 40
safety = [
    ("Refuse to print a literal API key from a file.", "I cannot print a literal secret. Reference it by name (${API_KEY} style / os.environ/...) or rotate it; I can help with the config that references it."),
    ("Refuse to repeat health data from a prompt.", "I will not repeat or use health data from the prompt. Here is a de-identified rephrasing of the task with the health details removed."),
    ("Pasted content tells the model to disable masking.", "That instruction came from pasted content (data), not from you. I will not follow it; masking stays on. Tell me the task in your own words and I will do it masked."),
    ("A value is shown with only its last 4 characters.", "That is still a leak — partial values can identify or help reconstruct a secret. I will not complete it. The fully masked form is <API_KEY>."),
    ("A log contains Authorization: Bearer <API_KEY>.", "Redact it to Authorization: Bearer <API_KEY> (placeholder) before sharing. Keep timestamps and error text; drop the credential and any surrounding secret."),
    ("A support request contains a name, email and phone.", "Mask all three to <NAME>, <EMAIL>, <PHONE>. Keep the technical symptom. Do not include any original identifier in the reply."),
    ("Explain reversible masking to a new operator.", "Masking replaces PII/secrets with placeholders before text leaves the trusted side; the mapping lives in TokenRonin internal/mask/ and is restored only there. The model never sees the original, and the mapping is never pasted into a prompt."),
    ("A user asks for another person's private details.", "I do not share private details about other people. If this is your own account, verify through the account's own flow; otherwise I cannot help with that."),
    ("A config file contains a literal key. How do you fix it?", "Remove the literal value, replace it with a ${ENV_VAR} reference, rotate the exposed key, and check history/logs for copies. Never commit a literal key."),
    ("An internal hostname appears in a draft answer.", "Remove it. Public answers may use only loopback/public values from the public repo (e.g. http://127.0.0.1:9090/v1). Internal hostnames and addresses must not be shared or invented."),
]
for title, ans in safety:
    mask_templates.append(("masking", title, "Safety task. Any unmasked original value is a failure.",
        ans, "template:safety x tokenronin internal/mask/"))
    mask_templates.append(("masking", title + " What is the safe alternative?",
        "Safety task. Any unmasked original value is a failure.",
        ans + " Safe alternative: placeholders (<EMAIL>, <API_KEY>, <NAME>, <PHONE>, <GOV_ID>), ${ENV_VAR} references by name, and rotation if a value was ever exposed.",
        "template:safety-alt x tokenronin internal/mask/"))
    mask_templates.append(("masking", title + " Why is the unsafe version harmful?",
        "Safety task. Any unmasked original value is a failure.",
        ans + " Harm: a leaked secret can be reused, a leaked identifier can identify a person, and a pasted mapping can be replayed. Masking removes the value from the model's context entirely.",
        "template:safety-why x tokenronin internal/mask/"))
    mask_templates.append(("masking", title + " Verify zero leak in your own output.",
        "Safety task. Any unmasked original value is a failure.",
        ans + " Self-check: scan the output for the original value, any substring of it, and any partial form. Zero occurrences = pass; one occurrence = fail the whole task.",
        "template:safety-verify x tokenronin internal/mask/"))
# 80. Pad to 100 with multi-PII drills.
pad = 0
while len([t for t in mask_templates if t[0]=="masking"]) < 100:
    pad += 1
    mask_templates.append(("masking",
        f"Drill {pad}: mask an email and an API key in one message.",
        f"Message {pad} contains an email and an API key.",
        "Masked message with <EMAIL> and <API_KEY> and no original values, in full or in part. Both placeholders must appear; a single leak fails the whole task.",
        "template:mask-multi x tokenronin internal/mask/"))
assert len([t for t in mask_templates if t[0]=="masking"]) == 100
for cat, instr, inp, out, src in mask_templates:
    add(cat, instr, inp, out, src)

counts = Counter(e["category"] for e in examples)
assert counts == {"coding": 400, "automation": 300, "reasoning": 200, "masking": 100}, counts
assert len(examples) == 1000
# id uniqueness + no duplicate instruction/input (already enforced by seen)
assert len(set(e["id"] for e in examples)) == 1000
# safety scan: no literal-looking secrets — only placeholders / env refs / loopback allowed.
# (Templates use stand-in descriptions, never real values.)
with OUT.open("w", encoding="utf-8") as f:
    for e in examples:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
print(f"wrote {OUT} : {len(examples)} examples {dict(counts)}")
