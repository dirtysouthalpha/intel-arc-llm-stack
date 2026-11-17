"""YAML validity tests for llama-swap/models.yaml and gateway/config.yaml."""
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Engine binaries used in llama-swap/models.yaml. The installer extracts
# the SYCL engine to $Root\\llama-cpp-ipex, which is NOT a path used in
# models.yaml — that drift is documented in docs/troubleshooting.md and
# is deliberately not changed here without live-host verification.
SYCL_BINARY = "V:\\AI\\llama-cpp\\llama-server.exe"
VULKAN_BINARY = "V:\\AI\\llama-cpp-vulkan\\llama-server.exe"
SYCL_MODELS = {
    "gemma3-12b",
    "gemma3-12b-max",
    "gemma3-12b-vision",
    "gemma3-27b",
    "gemma3-27b-vision",
    "qwen3-30b",
    "qwen2.5-coder-32b",
    "qwen2.5-vl-7b",
}
VULKAN_MODELS = {"gpt-oss-20b", "qwen3-vl-8b", "qwen2.5-omni", "qwen3.8-27b"}


def _load(rel):
    with open(ROOT / rel, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _installer_text():
    return (ROOT / "install.ps1").read_text(encoding="utf-8")


def _here_strings(text, var):
    # PowerShell here-strings: $var = @"\n<content>\n"@
    return re.findall(r"\$" + var + r' = @"\n(.*?)\n"@', text, re.DOTALL)


def _model_file(cmd):
    match = re.search(r"-m\s+\S+\\([^\s\\]+\.gguf)", cmd)
    return match.group(1) if match else None


def _context(cmd):
    match = re.search(r"-c\s+(\d+)", cmd)
    return int(match.group(1)) if match else None


def test_models_yaml_structure():
    data = _load("llama-swap/models.yaml")
    assert set(data) == {"healthCheckTimeout", "models"}
    assert isinstance(data["healthCheckTimeout"], int)
    assert isinstance(data["models"], dict) and data["models"]
    for name, spec in data["models"].items():
        assert isinstance(spec.get("cmd"), str) and "${PORT}" in spec["cmd"], name
        assert isinstance(spec.get("ttl"), int) and spec["ttl"] > 0, name


def test_gateway_yaml_structure():
    data = _load("gateway/config.yaml")
    assert "model_list" in data and isinstance(data["model_list"], list)
    names = [m["model_name"] for m in data["model_list"]]
    assert len(names) == len(set(names)), "duplicate model_name in gateway config"
    for m in data["model_list"]:
        assert "model" in m["litellm_params"], m["model_name"]


def test_gateway_config_is_ascii():
    # LiteLLM on Windows reads the YAML with cp1252; keep it pure ASCII (see file header).
    raw = (ROOT / "gateway/config.yaml").read_bytes()
    assert raw.isascii()


def test_local_gateway_models_exist_in_llama_swap():
    swap = set(_load("llama-swap/models.yaml")["models"])
    gw = _load("gateway/config.yaml")
    for m in gw["model_list"]:
        model = m["litellm_params"]["model"]
        if model.startswith("openai/") and "127.0.0.1:9090" in m["litellm_params"].get("api_base", ""):
            assert model.split("/", 1)[1] in swap, f"{m['model_name']} -> {model} not in models.yaml"


def test_every_llama_swap_model_has_gateway_alias():
    # Reverse of the test above: a model in llama-swap with no gateway
    # alias can never be reached through the :4000 endpoint.
    swap = set(_load("llama-swap/models.yaml")["models"])
    gw = _load("gateway/config.yaml")
    reachable = set()
    for m in gw["model_list"]:
        model = m["litellm_params"]["model"]
        if model.startswith("openai/") and "127.0.0.1:9090" in m["litellm_params"].get("api_base", ""):
            reachable.add(model.split("/", 1)[1])
    missing = swap - reachable
    assert not missing, f"llama-swap models with no gateway alias: {sorted(missing)}"


def test_installer_minimal_yaml_matches_repo_yaml():
    # The installer writes a Minimal (Gemma-only) models.yaml. Its two
    # models must match the repo models.yaml on GGUF file, context, and
    # TTL. The gateway side is checked by name only: the installer's
    # local-chat points at openai/gemma3-12b while the repo gateway
    # points local-chat at openai/gemma3-12b-vision — a known drift,
    # so the test does not assert the target model matches.
    repo = _load("llama-swap/models.yaml")["models"]
    blocks = [_load_yaml_text(b) for b in _here_strings(_installer_text(), "swapYaml")]
    assert blocks, "no $swapYaml here-string found in install.ps1"
    minimal = [b for b in blocks if set(b["models"]) == {"gemma3-12b", "gemma3-12b-vision"}]
    assert len(minimal) == 1, "expected exactly one Minimal installer block with gemma3-12b + gemma3-12b-vision"
    for name, spec in minimal[0]["models"].items():
        assert name in repo, f"installer model {name} not in repo models.yaml"
        assert _model_file(spec["cmd"]) == _model_file(repo[name]["cmd"]), name
        assert _context(spec["cmd"]) == _context(repo[name]["cmd"]), name
        if name == "gemma3-12b-vision":
            # Known drift, not a failure: the repo keeps the vision model
            # resident with ttl 28800, the installer writes 1800.
            assert spec["ttl"] == 1800 and repo[name]["ttl"] == 28800, name
        else:
            assert spec["ttl"] == repo[name]["ttl"], name


def _load_yaml_text(text):
    return yaml.safe_load(text)


def test_installer_models_are_in_repo():
    # Every model the installer can write (Minimal and, if present, Full)
    # must exist in the repo models.yaml, and every gateway alias it can
    # write must exist in the repo gateway config.
    repo_models = set(_load("llama-swap/models.yaml")["models"])
    gw_names = {m["model_name"] for m in _load("gateway/config.yaml")["model_list"]}
    text = _installer_text()
    for block in _here_strings(text, "swapYaml"):
        data = yaml.safe_load(block)
        unknown = set(data["models"]) - repo_models
        assert not unknown, f"installer writes models not in repo: {sorted(unknown)}"
    for block in _here_strings(text, "gwYaml"):
        data = yaml.safe_load(block)
        unknown = {m["model_name"] for m in data["model_list"]} - gw_names
        assert not unknown, f"installer writes gateway aliases not in repo: {sorted(unknown)}"
        for m in data["model_list"]:
            model = m["litellm_params"]["model"]
            if model.startswith("openai/"):
                assert model.split("/", 1)[1] in repo_models, f"installer gateway {m['model_name']} -> {model} not in models.yaml"


def test_binary_paths_consistent():
    # Every llama-swap cmd must use exactly one of the two known engine
    # binaries, and the SYCL/Vulkan split must match the verified roster.
    # No cmd may use the installer's llama-cpp-ipex path.
    models = _load("llama-swap/models.yaml")["models"]
    sycl = set()
    vulkan = set()
    for name, spec in models.items():
        cmd = spec["cmd"]
        assert "llama-cpp-ipex" not in cmd, f"{name}: repo models.yaml must not use the installer path llama-cpp-ipex"
        match = re.search(r"([A-Za-z]:\\[^\s]*llama-server\.exe)", cmd)
        assert match, f"{name}: no llama-server.exe path in cmd"
        binary = match.group(1)
        assert binary in (SYCL_BINARY, VULKAN_BINARY), f"{name}: unexpected engine binary {binary}"
        if binary == SYCL_BINARY:
            sycl.add(name)
        else:
            vulkan.add(name)
    assert sycl == SYCL_MODELS, f"SYCL models changed: {sorted(sycl)}"
    assert vulkan == VULKAN_MODELS, f"Vulkan models changed: {sorted(vulkan)}"
    assert sycl | vulkan == set(models), "engine split does not cover all models"


def test_model_files_are_gguf_under_models_dir():
    models = _load("llama-swap/models.yaml")["models"]
    for name, spec in models.items():
        cmd = spec["cmd"]
        assert _model_file(cmd), f"{name}: no -m <file>.gguf in cmd"
        assert re.search(r"-m\s+V:\\AI\\models\\[^\s]+\.gguf", cmd), f"{name}: model file is not under V:\\AI\\models"
        mmproj = re.search(r"--mmproj\s+(\S+)", cmd)
        if mmproj:
            assert mmproj.group(1).startswith("V:\\AI\\models\\") and mmproj.group(1).endswith(".gguf"), f"{name}: mmproj is not a GGUF under V:\\AI\\models"
