#!/usr/bin/env python
import argparse
from pathlib import Path
import pandas as pd

from eyeai.config import load_yaml, ensure_dir
from eyeai.inference.ensemble import weighted_average_predictions
from eyeai.postprocessing.thresholds import optimize_binary_threshold
from eyeai.postprocessing.aggregation import aggregate_predictions
from eyeai.utils.metrics import binary_metrics
from eyeai.utils.checkpoints import save_json


def _prediction_files_from_config(cfg):
    files = []
    for model_cfg in cfg.get("models", []):
        path = model_cfg.get("prediction_file")
        if path:
            files.append(path)
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="configs/ensemble.yaml")
    parser.add_argument("--prediction-files", nargs="+", default=None)
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    output_dir = ensure_dir(cfg["paths"]["output_dir"])

    model_cfgs = cfg["models"]
    weights = [float(m["weight"]) for m in model_cfgs]
    prediction_files = args.prediction_files or _prediction_files_from_config(cfg)

    if len(prediction_files) != len(model_cfgs):
        raise ValueError(
            "Prediction files must be passed with --prediction-files or provided as prediction_file in configs/ensemble*.yaml."
        )

    pred_dfs = [pd.read_csv(p) for p in prediction_files]
    ensemble_df = weighted_average_predictions(pred_dfs, weights)

    threshold_cfg = cfg.get("threshold", {}) or {}
    threshold_result = optimize_binary_threshold(
        ensemble_df["binary_label"].values,
        ensemble_df["prob_amd"].values,
        metric=threshold_cfg.get("metric", "macro_f1"),
        grid_step=float(threshold_cfg.get("grid_step", 0.005)),
        mode=threshold_cfg.get("mode", "balanced"),
        min_recall=threshold_cfg.get("min_recall", None),
        min_precision=threshold_cfg.get("min_precision", None),
        min_specificity=threshold_cfg.get("min_specificity", None),
    )

    threshold = threshold_result["threshold"]
    image_metrics = binary_metrics(ensemble_df["binary_label"].values, ensemble_df["prob_amd"].values, threshold)
    ensemble_df["pred_binary"] = (ensemble_df["prob_amd"] >= threshold).astype(int)
    ensemble_df.to_csv(output_dir / "ensemble_image_predictions.csv", index=False)

    group_cols = cfg.get("aggregation", {}).get("group_by", ["patient_id", "eye"])
    agg_df = aggregate_predictions(ensemble_df, group_cols=group_cols)
    agg_metrics = binary_metrics(agg_df["binary_label"].values, agg_df["prob_amd"].values, threshold)
    agg_df["pred_binary"] = (agg_df["prob_amd"] >= threshold).astype(int)
    agg_df.to_csv(output_dir / "ensemble_patient_eye_predictions.csv", index=False)

    summary = {
        "weights": weights,
        "prediction_files": prediction_files,
        "threshold": threshold,
        "threshold_result": threshold_result,
        "image_level_metrics": image_metrics,
        "patient_eye_level_metrics": agg_metrics,
    }
    save_json(output_dir / "ensemble_summary.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
