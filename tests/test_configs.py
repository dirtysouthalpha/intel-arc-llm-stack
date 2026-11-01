"""YAML validity tests for llama-swap/models.yaml and gateway/config.yaml."""
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(rel):
    with open(ROOT / rel, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


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
