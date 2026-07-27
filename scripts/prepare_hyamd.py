#!/usr/bin/env python
from pathlib import Path
import argparse
from eyeai.config import load_yaml
from eyeai.data.prepare_hyamd import prepare_hyamd
from eyeai.utils.seed import set_seed


def _resolve_config_path(config: str) -> Path:
    path = Path(config)
    if path.exists():
        return path
    if str(path).endswith("."):
        alternative = Path(str(path).rstrip("."))
        if alternative.exists():
            print(f"Warning: config path ended with a dot. Using: {alternative}", flush=True)
            return alternative
    raise FileNotFoundError(f"Config file not found: {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="configs/train_retfound_binary.yaml")
    args = parser.parse_args()

    config_path = _resolve_config_path(args.config)
    print("EyeAI HYAMD preparation entrypoint", flush=True)
    print("Current working directory:", Path.cwd(), flush=True)
    print("Config path:", config_path, flush=True)

    cfg = load_yaml(config_path)
    set_seed(cfg.get("run", {}).get("seed", 42))

    data_cfg = cfg["data"]
    result = prepare_hyamd(
        input_dir=data_cfg["input_dir"],
        work_dir=data_cfg["work_dir"],
        seed=cfg.get("run", {}).get("seed", 42),
        force_recrop=bool(data_cfg.get("force_recrop", False)),
        validate_existing_crops=bool(data_cfg.get("validate_existing_crops", False)),
        max_workers=8,
    )

    print("Prepared HYAMD splits:", result["splits_dir"], flush=True)
    print("Train:", len(result["train_df"]), flush=True)
    print("Val:", len(result["val_df"]), flush=True)
    print("Test:", len(result["test_df"]), flush=True)


if __name__ == "__main__":
    main()
