from pathlib import Path

import torch

from eyeai.inference.model_package import extract_model_state_dict, load_yaml


def test_extract_model_state_dict_removes_module_prefix():
    checkpoint = {
        "model_state_dict": {
            "module.layer.weight": torch.ones(2, 2),
            "module.layer.bias": torch.zeros(2),
        }
    }
    state = extract_model_state_dict(checkpoint)
    assert set(state) == {"layer.weight", "layer.bias"}


def test_run09_package_config_contract():
    repo_root = Path(__file__).resolve().parents[1]
    config = load_yaml(repo_root / "configs" / "model_packages" / "run09_tta_v1.yaml")
    assert config["model"]["image_size"] == 224
    assert config["inference"]["variants"] == ["original", "hflip"]
    assert config["inference"]["threshold"] == 0.335
    assert config["preprocessing"]["crop_black_border"] is True
