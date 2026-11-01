"""Unit tests for vram-budget/vram_budget.py (pure math only; no GPU or system calls)."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vram_budget", ROOT / "vram-budget" / "vram_budget.py")
vb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vb)

GIB = 1024 ** 3


def test_dtype_bytes_ordering():
    assert vb.DTYPE_BYTES["f32"] == 4.0
    assert vb.DTYPE_BYTES["f16"] == 2.0
    assert vb.DTYPE_BYTES["f16"] > vb.DTYPE_BYTES["q8_0"] > vb.DTYPE_BYTES["q4_0"]


@pytest.mark.parametrize("name", list(vb.PRESETS))
def test_presets_have_required_fields(name):
    arch = vb.PRESETS[name]
    for key in ("n_layers", "n_kv_heads", "head_dim", "window", "local_ratio", "max_ctx"):
        assert key in arch, f"{name} missing {key}"
    assert arch["n_layers"] > 0 and arch["n_kv_heads"] > 0 and arch["head_dim"] > 0
    assert 0.0 <= arch["local_ratio"] <= 1.0


def test_kv_bytes_per_token_all_global_matches_formula():
    # 2 (K,V) * layers * kv_heads * head_dim * bytes_per_elem
    got = vb.kv_bytes_per_token(64, 8, 128, "f16", window=0, local_ratio=0)
    assert got == 2 * 64 * 8 * 128 * 2.0


def test_kv_bytes_per_token_ctx_unknown_is_conservative():
    # With n_ctx=None the sliding window must be ignored (all layers treated as global).
    arch = vb.PRESETS["gemma3-12b"]
    full = vb.kv_bytes_per_token(arch["n_layers"], arch["n_kv_heads"], arch["head_dim"], "f16")
    swa = vb.kv_bytes_per_token(arch["n_layers"], arch["n_kv_heads"], arch["head_dim"], "f16",
                                window=arch["window"], local_ratio=arch["local_ratio"], n_ctx=131072)
    assert swa < full


def test_sliding_window_has_no_effect_below_window():
    arch = vb.PRESETS["gemma3-12b"]
    args = (arch["n_layers"], arch["n_kv_heads"], arch["head_dim"], "f16")
    full = vb.kv_bytes_per_token(*args)
    small = vb.kv_bytes_per_token(*args, window=arch["window"], local_ratio=arch["local_ratio"], n_ctx=512)
    assert small == pytest.approx(full)


def test_gemma3_sliding_window_decomposition_at_128k():
    # Gemma 3: 48 layers, 5:1 local:global -> 8 global layers scale with ctx, 40 local cap at window.
    arch = vb.PRESETS["gemma3-12b"]
    n_ctx = 131072
    per_layer = 2 * arch["n_kv_heads"] * arch["head_dim"] * vb.DTYPE_BYTES["f16"]
    expected = (per_layer * 8 * n_ctx + per_layer * 40 * arch["window"]) / n_ctx
    got = vb.kv_bytes_per_token(arch["n_layers"], arch["n_kv_heads"], arch["head_dim"], "f16",
                                arch["window"], arch["local_ratio"], n_ctx)
    assert got == pytest.approx(expected)
    # Global part alone is 8 GiB at 128K; total stays well under the all-global 48 GiB.
    assert 8.0 < got * n_ctx / GIB < 9.0


def test_max_ctx_zero_when_no_budget():
    assert vb.max_ctx(24, 23, 2, vb.PRESETS["gemma3-12b"], "f16") == 0


def test_max_ctx_capped_at_arch_max():
    arch = vb.PRESETS["gemma3-12b"]
    assert vb.max_ctx(1000, 6.8, 2, arch, "f16") == arch["max_ctx"]


def test_max_ctx_fits_budget_for_dense_model():
    arch = vb.PRESETS["qwen2.5-32b"]
    vram, weights, overhead = 24.0, 20.0, 2.0
    ctx = vb.max_ctx(vram, weights, overhead, arch, "f16")
    assert 0 < ctx < arch["max_ctx"]
    bpt = vb.kv_bytes_per_token(arch["n_layers"], arch["n_kv_heads"], arch["head_dim"], "f16")
    # The returned context must fit in the budget (allow the 256-token convergence slack).
    assert bpt * ctx <= (vram - weights - overhead) * GIB + bpt * 256


def test_max_ctx_grows_with_smaller_kv_dtype():
    arch = vb.PRESETS["qwen2.5-32b"]
    assert vb.max_ctx(24, 20, 2, arch, "q4_0") > vb.max_ctx(24, 20, 2, arch, "f16")


def test_cli_reports_fits_for_small_ctx(capsys):
    import sys
    argv = sys.argv
    sys.argv = ["vram_budget.py", "gemma3-12b", "--weights", "6.8", "--kv", "f16", "--ctx", "8192"]
    try:
        vb.main()
    finally:
        sys.argv = argv
    out = capsys.readouterr().out
    assert "ctx=8,192" in out and "FITS" in out
