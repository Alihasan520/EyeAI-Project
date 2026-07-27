#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from eyeai.inference.ensemble import weighted_average_predictions
from eyeai.postprocessing.thresholds import optimize_binary_threshold
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


def _single_match(pattern: str) -> Path:
    matches = sorted(Path().glob(pattern)) if not pattern.startswith("/") else sorted(Path("/").glob(pattern[1:]))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one file for pattern {pattern}, found {len(matches)}: {matches}")
    return matches[0]


def _find_single(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {pattern} under {directory}, found {len(matches)}: {matches}")
    return matches[0]


def _positive_only_metrics(predictions: pd.DataFrame, threshold: float) -> dict:
    probabilities = predictions["prob_amd"].astype(float).to_numpy()
    return {
        "count": int(len(probabilities)),
        "threshold": float(threshold),
        "recall_amd": float((probabilities >= float(threshold)).mean()),
        "mean_probability": float(np.mean(probabilities)),
        "median_probability": float(np.median(probabilities)),
        "min_probability": float(np.min(probabilities)),
        "max_probability": float(np.max(probabilities)),
    }


def main():
    parser = argparse.ArgumentParser(description="Build OOF predictions and an external-positive fold ensemble.")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fold-count", type=int, default=3)
    parser.add_argument("--grid-step", type=float, default=0.005)
    args = parser.parse_args()

    run_root = Path(args.run_root)
    data_root = Path(args.data_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fold_predictions = []
    external_predictions = []
    expected_ids = set()
    fold_rows = []

    for fold in range(args.fold_count):
        prediction_dir = run_root / "predictions" / f"fold_{fold}"
        val_matches = [
            path for path in sorted(prediction_dir.glob("*_val_predictions_best.csv"))
            if "external_val" not in path.name
        ]
        if len(val_matches) != 1:
            raise RuntimeError(
                f"Expected one primary validation prediction file under {prediction_dir}, "
                f"found {len(val_matches)}: {val_matches}"
            )
        val_path = val_matches[0]
        fold_df = pd.read_csv(val_path, dtype={"image_id": str, "patient_id": str})
        fold_df["fold"] = fold
        fold_predictions.append(fold_df)

        expected_manifest = data_root / "manifests" / "folds" / f"fold_{fold}_val_hyamd.csv"
        expected = pd.read_csv(expected_manifest, dtype={"image_id": str})
        current_ids = set(fold_df["image_id"].astype(str))
        manifest_ids = set(expected["image_id"].astype(str))
        if current_ids != manifest_ids:
            raise RuntimeError(
                f"Fold {fold} prediction IDs do not match its validation manifest. "
                f"Missing={sorted(manifest_ids-current_ids)[:10]}, extra={sorted(current_ids-manifest_ids)[:10]}"
            )
        overlap = expected_ids & current_ids
        if overlap:
            raise RuntimeError(f"OOF image leakage across folds: {sorted(overlap)[:10]}")
        expected_ids |= current_ids

        external_path = _find_single(prediction_dir, "*_external_val_predictions_best.csv")
        external_predictions.append(
            pd.read_csv(external_path, dtype={"image_id": str, "patient_id": str})
        )

    oof = pd.concat(fold_predictions, ignore_index=True)
    if oof["image_id"].astype(str).duplicated().any():
        duplicates = oof.loc[oof["image_id"].astype(str).duplicated(), "image_id"].head(10).tolist()
        raise RuntimeError(f"Duplicate image IDs in OOF predictions: {duplicates}")

    threshold_result = optimize_binary_threshold(
        oof["binary_label"].astype(int).to_numpy(),
        oof["prob_amd"].astype(float).to_numpy(),
        metric="macro_f1",
        grid_step=float(args.grid_step),
        mode="balanced",
    )
    best_threshold = float(threshold_result["threshold"])

    for fold in range(args.fold_count):
        subset = oof[oof["fold"] == fold]
        fold_rows.append({
            "fold": fold,
            "count": int(len(subset)),
            "metrics_at_oof_threshold": binary_metrics(
                subset["binary_label"].astype(int).to_numpy(),
                subset["prob_amd"].astype(float).to_numpy(),
                threshold=best_threshold,
            ),
            "metrics_at_0_5": binary_metrics(
                subset["binary_label"].astype(int).to_numpy(),
                subset["prob_amd"].astype(float).to_numpy(),
                threshold=0.5,
            ),
        })

    external_ensemble = weighted_average_predictions(
        external_predictions,
        [1.0] * len(external_predictions),
    )

    oof.to_csv(output_dir / "run11_oof_predictions.csv", index=False)
    external_ensemble.to_csv(
        output_dir / "run11_external_positive_fold_ensemble_predictions.csv",
        index=False,
    )

    summary = {
        "fold_count": int(args.fold_count),
        "oof_count": int(len(oof)),
        "best_threshold": best_threshold,
        "oof_metrics_at_threshold": binary_metrics(
            oof["binary_label"].astype(int).to_numpy(),
            oof["prob_amd"].astype(float).to_numpy(),
            threshold=best_threshold,
        ),
        "oof_metrics_at_0_5": binary_metrics(
            oof["binary_label"].astype(int).to_numpy(),
            oof["prob_amd"].astype(float).to_numpy(),
            threshold=0.5,
        ),
        "fold_metrics": fold_rows,
        "external_positive_fold_ensemble_at_threshold": _positive_only_metrics(
            external_ensemble,
            threshold=best_threshold,
        ),
        "external_positive_fold_ensemble_at_0_5": _positive_only_metrics(
            external_ensemble,
            threshold=0.5,
        ),
    }
    (output_dir / "run11_oof_summary.json").write_text(
        json.dumps(_json_ready(summary), indent=2),
        encoding="utf-8",
    )
    (output_dir / "run11_oof_threshold.json").write_text(
        json.dumps({"threshold": best_threshold}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(_json_ready(summary), indent=2))


if __name__ == "__main__":
    main()
