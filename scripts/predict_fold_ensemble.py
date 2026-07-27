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
from eyeai.inference.ensemble import weighted_average_predictions
from eyeai.inference.predict import predict_dataframe
from eyeai.models.registry import build_model
from eyeai.utils.metrics import binary_metrics


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


def _find_single(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {pattern} under {directory}, found {len(matches)}: {matches}")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description="Predict an unseen manifest with the mean of RETFound fold models.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--threshold-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fold-count", type=int, default=3)
    parser.add_argument("--tta", default="")
    args = parser.parse_args()

    config = load_yaml(Path(args.config))
    run_root = Path(args.run_root)
    data_root = Path(args.data_root)
    manifest_path = data_root / args.manifest
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataframe = pd.read_csv(manifest_path, dtype={"image_id": str, "patient_id": str})
    threshold = float(json.loads(Path(args.threshold_json).read_text(encoding="utf-8"))["threshold"])
    tta_variants = [value.strip() for value in args.tta.split(",") if value.strip()] or None

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("CUDA is required for RETFound fold inference.")

    prediction_frames = []
    checkpoint_reports = []
    for fold in range(args.fold_count):
        checkpoint_dir = run_root / "checkpoints" / f"fold_{fold}"
        checkpoint_path = _find_single(checkpoint_dir, "*_best.pth")
        model, model_report = build_model(config["model"], device)
        checkpoint, load_report = load_trained_checkpoint(
            model,
            checkpoint_path,
            map_location=device,
            strict=True,
        )
        predictions = predict_dataframe(
            model=model,
            df=dataframe,
            image_size=int(config["data"]["image_size"]),
            device=device,
            tta_variants=tta_variants,
            image_col="relative_image_path",
            image_root=data_root,
            data_config=config["data"],
            model_report=checkpoint.get("model_report", model_report),
        )
        predictions.to_csv(output_dir / f"fold_{fold}_predictions.csv", index=False)
        prediction_frames.append(predictions)
        checkpoint_reports.append(load_report)
        del model
        torch.cuda.empty_cache()

    ensemble = weighted_average_predictions(
        prediction_frames,
        [1.0] * len(prediction_frames),
    )
    ensemble["predicted_binary_label"] = (ensemble["prob_amd"].astype(float) >= threshold).astype(int)
    ensemble.to_csv(output_dir / "fold_ensemble_predictions.csv", index=False)

    summary = {
        "manifest": args.manifest,
        "count": int(len(ensemble)),
        "fold_count": int(args.fold_count),
        "threshold": threshold,
        "tta_variants": tta_variants or [],
        "checkpoint_reports": checkpoint_reports,
    }
    if "binary_label" in ensemble.columns and set(ensemble["binary_label"].astype(int).unique()).issubset({0, 1}):
        summary["metrics"] = binary_metrics(
            ensemble["binary_label"].astype(int).to_numpy(),
            ensemble["prob_amd"].astype(float).to_numpy(),
            threshold=threshold,
        )

    (output_dir / "fold_ensemble_summary.json").write_text(
        json.dumps(_json_ready(summary), indent=2),
        encoding="utf-8",
    )
    print(json.dumps(_json_ready(summary), indent=2))


if __name__ == "__main__":
    main()
