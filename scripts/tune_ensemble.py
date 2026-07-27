#!/usr/bin/env python
import argparse
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


def _evaluate_df(df, threshold_cfg):
    threshold_result = optimize_binary_threshold(
        df["binary_label"].values,
        df["prob_amd"].values,
        metric=threshold_cfg.get("metric", "macro_f1"),
        grid_step=float(threshold_cfg.get("grid_step", 0.005)),
        mode=threshold_cfg.get("mode", "balanced"),
        min_recall=threshold_cfg.get("min_recall", None),
        min_precision=threshold_cfg.get("min_precision", None),
        min_specificity=threshold_cfg.get("min_specificity", None),
    )
    metrics = threshold_result["metrics"]
    return {
        "score": float(metrics[threshold_cfg.get("metric", "macro_f1")]),
        "threshold": float(threshold_result["threshold"]),
        "macro_f1": float(metrics["macro_f1"]),
        "auc": float(metrics.get("auc", float("nan"))),
        "precision_amd": float(metrics["precision_amd"]),
        "recall_amd": float(metrics["recall_amd"]),
        "specificity": float(metrics.get("specificity", float("nan"))),
        "threshold_result": threshold_result,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="configs/ensemble_tuned.yaml")
    parser.add_argument("--prediction-files", nargs="+", default=None)
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    output_dir = ensure_dir(cfg["paths"]["output_dir"])
    threshold_cfg = cfg.get("threshold", {}) or {}
    tuning_cfg = cfg.get("ensemble_tuning", {}) or {}

    model_cfgs = cfg["models"]
    prediction_files = args.prediction_files or _prediction_files_from_config(cfg)
    if len(model_cfgs) != 2 or len(prediction_files) != 2:
        raise ValueError("This tuner currently supports exactly two prediction files/models.")

    df_a = pd.read_csv(prediction_files[0])
    df_b = pd.read_csv(prediction_files[1])
    grid_step = float(tuning_cfg.get("weight_grid_step", 0.05))

    rows = []
    best = None
    w = 0.0
    while w <= 1.000001:
        weights = [round(w, 6), round(1.0 - w, 6)]
        combined = weighted_average_predictions([df_a, df_b], weights)
        result = _evaluate_df(combined, threshold_cfg)
        row = {
            "weight_0": weights[0],
            "weight_1": weights[1],
            "model_0": model_cfgs[0]["name"],
            "model_1": model_cfgs[1]["name"],
            **{k: v for k, v in result.items() if k != "threshold_result"},
        }
        rows.append(row)

        if best is None or result["score"] > best["score"]:
            best = {"weights": weights, "result": result, "combined": combined}

        w += grid_step

    grid_df = pd.DataFrame(rows)
    grid_df.to_csv(output_dir / "ensemble_weight_grid_search.csv", index=False)

    best_df = best["combined"].copy()
    best_threshold = best["result"]["threshold"]
    best_df["pred_binary"] = (best_df["prob_amd"] >= best_threshold).astype(int)
    best_df.to_csv(output_dir / "ensemble_tuned_image_predictions.csv", index=False)

    group_cols = cfg.get("aggregation", {}).get("group_by", ["patient_id", "eye"])
    agg_df = aggregate_predictions(best_df, group_cols=group_cols)
    agg_metrics = binary_metrics(agg_df["binary_label"].values, agg_df["prob_amd"].values, best_threshold)
    agg_df["pred_binary"] = (agg_df["prob_amd"] >= best_threshold).astype(int)
    agg_df.to_csv(output_dir / "ensemble_tuned_patient_eye_predictions.csv", index=False)

    summary = {
        "models": [m["name"] for m in model_cfgs],
        "prediction_files": prediction_files,
        "best_weights": best["weights"],
        "best_image_level": {k: v for k, v in best["result"].items() if k != "threshold_result"},
        "best_threshold_result": best["result"]["threshold_result"],
        "patient_eye_level_metrics": agg_metrics,
    }
    save_json(output_dir / "ensemble_tuning_summary.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
