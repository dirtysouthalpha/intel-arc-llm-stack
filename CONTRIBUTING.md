# Contributing

This project exists to make Intel Arc a first-class citizen for local LLM inference, and
contributions that push that forward are genuinely welcome — **issues and PRs are open.**

## Especially useful
- **More Arc SKUs** — got an A770, A580, B580, or a different B60 config? Launch configs and
  tok/s numbers for your card help everyone.
- **More models** — working `llama-swap` / gateway entries for models not yet listed.
- **Perf tuning** — better `-ngl` / `-ub` / KV settings, Vulkan vs SYCL comparisons.
- **Sharp edges** — hit a new driver/stack gotcha and solved it? Add it to the README's list so
  the next person skips the pain.

## How
1. Open an issue describing the change (or the bug + your hardware) first — it saves duplicate work.
2. Keep PRs focused. Include your GPU model, driver, OS, and how you measured any numbers.
3. **Never fabricate benchmark numbers.** Real measured data only — that is the whole point.

## Questions
Open an issue. Hardware quirks, "does X model work on my card", and setup problems are all fair game.
