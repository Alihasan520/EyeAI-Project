#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from eyeai.config import load_yaml
from eyeai.inference.checkpoint_loader import load_trained_checkpoint
from eyeai.inference.predict import predict_dataframe
from eyeai.models.registry import build_model
from eyeai.postprocessing.thresholds import optimize_binary_threshold
from eyeai.utils.metrics import binary_metrics
from eyeai.utils.seed import set_seed


def _json_ready(value: Any):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _read_manifest(dataset_root: Path, relative_path: str) -> pd.DataFrame:
    path = dataset_root / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    dataframe = pd.read_csv(path, dtype={"image_id": str, "patient_id": str})
    required = {"image_id", "relative_image_path", "binary_label"}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        raise RuntimeError(f"Manifest is missing required columns: {missing}")
    missing_images = [
        value
        for value in dataframe["relative_image_path"].astype(str)
        if not (dataset_root / value).exists()
    ]
    if missing_images:
        raise RuntimeError(f"Manifest references missing images: {missing_images[:10]}")
    return dataframe


def _metrics(dataframe: pd.DataFrame, threshold: float) -> dict:
    return binary_metrics(
        dataframe["binary_label"].astype(int).to_numpy(),
        dataframe["prob_amd"].astype(float).to_numpy(),
        threshold=float(threshold),
    )


def main():
    parser = argparse.ArgumentParser(description="Evaluate a trained binary model with original + horizontal-flip TTA.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--manifest", default="manifests/hyamd_val.csv")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--variants", default="original,hflip")
    parser.add_argument("--fixed-threshold", type=float, default=None)
    args = parser.parse_args()

    config = load_yaml(Path(args.config))
    set_seed(int(config.get("run", {}).get("seed", 42)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("CUDA is required for RETFound TTA evaluation.")

    dataset_root = Path(args.data_root)
    dataframe = _read_manifest(dataset_root, args.manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model, model_report = build_model(config["model"], device)
    checkpoint, checkpoint_report = load_trained_checkpoint(
        model,
        args.checkpoint,
        map_location=device,
        strict=True,
    )
    model.eval()

    checkpoint_threshold = args.fixed_threshold
    if checkpoint_threshold is None:
        checkpoint_threshold = checkpoint.get("best_threshold", 0.5)
    checkpoint_threshold = float(checkpoint_threshold)

    common_kwargs = {
        "model": model,
        "df": dataframe,
        "image_size": int(config["data"]["image_size"]),
        "device": device,
        "image_col": "relative_image_path",
        "image_root": dataset_root,
        "data_config": config["data"],
        "model_report": checkpoint.get("model_report", model_report),
    }

    original_predictions = predict_dataframe(tta_variants=None, **common_kwargs)
    variants = [value.strip() for value in args.variants.split(",") if value.strip()]
    if "original" not in variants:
        variants.insert(0, "original")
    tta_predictions = predict_dataframe(tta_variants=variants, **common_kwargs)

    original_predictions.to_csv(output_dir / "run09_original_predictions.csv", index=False)
    tta_predictions.to_csv(output_dir / "run09_tta_predictions.csv", index=False)

    threshold_result = optimize_binary_threshold(
        tta_predictions["binary_label"].astype(int).to_numpy(),
        tta_predictions["prob_amd"].astype(float).to_numpy(),
        metric=config.get("threshold", {}).get("metric", "macro_f1"),
        grid_step=float(config.get("threshold", {}).get("grid_step", 0.005)),
        mode=config.get("threshold", {}).get("mode", "balanced"),
        min_recall=config.get("threshold", {}).get("min_recall"),
        min_precision=config.get("threshold", {}).get("min_precision"),
        min_specificity=config.get("threshold", {}).get("min_specificity"),
    )
    tta_threshold = float(threshold_result["threshold"])

    summary = {
        "checkpoint": str(Path(args.checkpoint)),
        "checkpoint_report": checkpoint_report,
        "manifest": args.manifest,
        "count": int(len(dataframe)),
        "variants": variants,
        "checkpoint_threshold": checkpoint_threshold,
        "original_at_checkpoint_threshold": _metrics(original_predictions, checkpoint_threshold),
        "tta_at_checkpoint_threshold": _metrics(tta_predictions, checkpoint_threshold),
        "tta_best_threshold": tta_threshold,
        "tta_at_tuned_threshold": _metrics(tta_predictions, tta_threshold),
        "probability_change": {
            "mean_absolute": float(
                np.mean(
                    np.abs(
                        tta_predictions["prob_amd"].to_numpy()
                        - original_predictions["prob_amd"].to_numpy()
                    )
                )
            ),
            "max_absolute": float(
                np.max(
                    np.abs(
                        tta_predictions["prob_amd"].to_numpy()
                        - original_predictions["prob_amd"].to_numpy()
                    )
                )
            ),
        },
    }
    (output_dir / "run09_tta_summary.json").write_text(
        json.dumps(_json_ready(summary), indent=2),
        encoding="utf-8",
    )

    print(json.dumps(_json_ready(summary), indent=2))


if __name__ == "__main__":
    main()
