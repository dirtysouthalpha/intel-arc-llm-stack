#!/usr/bin/env python3
"""
vram_budget.py - Max-context calculator for the Intel Arc Pro B60 (24GB).

Given a model's architecture + quantization, compute how large a context window
(num_ctx) fits in VRAM, and how much VRAM a target context needs. This is the
"max tokens possible" sizing tool for the B60.

KV-cache size (bytes) = 2 (K and V)
                      * n_layers
                      * n_ctx
                      * n_kv_heads          # grouped-query: KV heads, not Q heads
                      * head_dim
                      * bytes_per_elem(kv_dtype)

Notes:
- Some models (Gemma 3) interleave sliding-window "local" layers with "global"
  layers. Local layers cap their KV at the window size, which massively reduces
  KV cache at long context. Set --local-ratio / --window to model this.
- Weights size is taken from the on-disk quant (GGUF) you actually use.
"""
import argparse, sys

# bytes per element for common cache/weight dtypes (KV-cache quant adds a small
# per-block scale overhead; q8_0 ~= 8.5 bits, q4_0 ~= 4.5 bits).
DTYPE_BYTES = {
    "f32": 4.0, "f16": 2.0, "bf16": 2.0,
    "q8_0": 8.5 / 8, "q5_1": 6.0 / 8, "q5_0": 5.5 / 8,
    "q4_1": 5.0 / 8, "q4_0": 4.5 / 8,
}

# Architecture presets: (n_layers, n_kv_heads, head_dim, window, local_ratio)
# local_ratio = fraction of layers that are sliding-window "local" (0 = all global).
PRESETS = {
    # Gemma 3 (interleaved 5 local : 1 global, window 1024)
    "gemma3-12b": dict(n_layers=48, n_kv_heads=8,  head_dim=256, window=1024, local_ratio=5/6, max_ctx=131072),
    "gemma3-27b": dict(n_layers=62, n_kv_heads=16, head_dim=128, window=1024, local_ratio=5/6, max_ctx=131072),
    "gemma3-4b":  dict(n_layers=34, n_kv_heads=4,  head_dim=256, window=1024, local_ratio=5/6, max_ctx=131072),
    # Qwen2.5 / Qwen3 dense (all global attention)
    "qwen2.5-32b": dict(n_layers=64, n_kv_heads=8, head_dim=128, window=0, local_ratio=0, max_ctx=131072),
    "qwen2.5-coder-32b": dict(n_layers=64, n_kv_heads=8, head_dim=128, window=0, local_ratio=0, max_ctx=131072),
    # gpt-oss-20b (MoE)
    "gpt-oss-20b": dict(n_layers=24, n_kv_heads=8, head_dim=64, window=0, local_ratio=0, max_ctx=131072),
}

def kv_bytes_per_token(n_layers, n_kv_heads, head_dim, kv_dtype, window=0, local_ratio=0.0, n_ctx=None):
    """Average KV bytes per token across layers, accounting for sliding-window local layers."""
    be = DTYPE_BYTES[kv_dtype]
    per_layer_full = 2 * n_kv_heads * head_dim * be
    n_local = round(n_layers * local_ratio)
    n_global = n_layers - n_local
    if n_ctx is None or window == 0 or local_ratio == 0:
        # treat all layers as global (conservative) when ctx unknown
        return per_layer_full * n_layers
    # global layers scale with full ctx; local layers cap at window
    global_bytes = per_layer_full * n_global * n_ctx
    local_bytes = per_layer_full * n_local * min(n_ctx, window)
    return (global_bytes + local_bytes) / n_ctx  # amortized per token

def max_ctx(vram_gb, weights_gb, overhead_gb, arch, kv_dtype):
    budget = (vram_gb - weights_gb - overhead_gb) * (1024**3)
    if budget <= 0:
        return 0
    # iterate because local-window KV/token depends on ctx
    ctx = 1024
    for _ in range(64):
        bpt = kv_bytes_per_token(arch["n_layers"], arch["n_kv_heads"], arch["head_dim"],
                                 kv_dtype, arch.get("window", 0), arch.get("local_ratio", 0), ctx)
        new = int(budget / bpt)
        if abs(new - ctx) < 256:
            ctx = new; break
        ctx = (ctx + new) // 2
    return min(ctx, arch.get("max_ctx", ctx))

def main():
    p = argparse.ArgumentParser(description="Max-context (num_ctx) calculator for the Arc B60.")
    p.add_argument("model", choices=list(PRESETS) + ["custom"], help="architecture preset")
    p.add_argument("--vram", type=float, default=24.0, help="total VRAM GB (default 24)")
    p.add_argument("--weights", type=float, required=True, help="on-disk quant weights size in GB")
    p.add_argument("--overhead", type=float, default=2.0, help="reserve GB for activations/compute graph (default 2)")
    p.add_argument("--kv", default="q8_0", choices=list(DTYPE_BYTES), help="KV-cache dtype (default q8_0)")
    p.add_argument("--ctx", type=int, help="if set, report VRAM needed for this context instead")
    # custom arch
    for k, t in [("n_layers", int), ("n_kv_heads", int), ("head_dim", int), ("window", int)]:
        p.add_argument("--" + k, type=t)
    p.add_argument("--local-ratio", type=float, default=0.0)
    a = p.parse_args()

    if a.model == "custom":
        arch = dict(n_layers=a.n_layers, n_kv_heads=a.n_kv_heads, head_dim=a.head_dim,
                    window=a.window or 0, local_ratio=a.local_ratio, max_ctx=10**9)
        if not all([a.n_layers, a.n_kv_heads, a.head_dim]):
            p.error("custom requires --n_layers --n_kv_heads --head_dim")
    else:
        arch = PRESETS[a.model]

    print(f"Model: {a.model}  | VRAM {a.vram}GB  weights {a.weights}GB  overhead {a.overhead}GB  KV={a.kv}")
    if a.ctx:
        bpt = kv_bytes_per_token(arch["n_layers"], arch["n_kv_heads"], arch["head_dim"],
                                 a.kv, arch.get("window", 0), arch.get("local_ratio", 0), a.ctx)
        need = bpt * a.ctx / (1024**3)
        total = a.weights + a.overhead + need
        print(f"  ctx={a.ctx:,}  ->  KV cache {need:.2f}GB,  total {total:.2f}GB,  "
              f"{'FITS' if total <= a.vram else 'OVER by %.2fGB' % (total - a.vram)}")
    else:
        mc = max_ctx(a.vram, a.weights, a.overhead, arch, a.kv)
        print(f"  MAX num_ctx that fits: {mc:,} tokens")
        for c in [8192, 16384, 32768, 65536, 131072]:
            if c > arch.get("max_ctx", c): continue
            bpt = kv_bytes_per_token(arch["n_layers"], arch["n_kv_heads"], arch["head_dim"],
                                     a.kv, arch.get("window", 0), arch.get("local_ratio", 0), c)
            total = a.weights + a.overhead + bpt * c / (1024**3)
            tag = "FITS" if total <= a.vram else "over"
            print(f"    ctx={c:>7,}: total {total:5.1f}GB  [{tag}]")

if __name__ == "__main__":
    main()
