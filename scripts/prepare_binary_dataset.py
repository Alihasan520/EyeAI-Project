#!/usr/bin/env python
import argparse
from pathlib import Path

from eyeai.config import load_yaml
from eyeai.data.prepare_binary_dataset import prepare_hyamd_armd_binary_dataset
from eyeai.utils.seed import set_seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = load_yaml(config_path)
    preparation_config = config.get("preparation", config)
    set_seed(int(preparation_config.get("seed", 42)))
    summary = prepare_hyamd_armd_binary_dataset(preparation_config)
    print("Prepared dataset summary:", flush=True)
    print(summary, flush=True)


if __name__ == "__main__":
    main()
