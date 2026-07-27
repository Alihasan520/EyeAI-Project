from typing import Dict

import numpy as np

from eyeai.utils.metrics import binary_metrics


def _score_metrics(metrics: dict, metric: str) -> float:
    score = metrics.get(metric, None)
    if score is None:
        raise KeyError(f"Metric not found for threshold optimization: {metric}")
    return float(score)


def optimize_binary_threshold(
    y_true,
    y_prob,
    metric: str = "macro_f1",
    grid_step: float = 0.005,
    mode: str = "balanced",
    min_recall: float | None = None,
    min_precision: float | None = None,
    min_specificity: float | None = None,
) -> Dict:
    """Optimize one threshold after checkpoint selection.

    The training loop must select checkpoints with a threshold-free metric. This
    function is intentionally used only after the best checkpoint is fixed.
    """
    if grid_step <= 0 or grid_step > 1:
        raise ValueError("grid_step must be in (0, 1].")

    thresholds = np.arange(0.0, 1.0 + grid_step / 2.0, grid_step)
    mode = (mode or "balanced").lower()

    candidates = []
    all_results = []

    for threshold in thresholds:
        metrics = binary_metrics(y_true, y_prob, threshold=float(threshold))
        score = _score_metrics(metrics, metric)
        item = {"threshold": float(threshold), "score": score, "metrics": metrics}
        all_results.append(item)

        keep = True
        if mode == "screening" and min_recall is not None:
            keep = metrics.get("recall_amd", 0.0) >= float(min_recall)
        elif mode == "conservative":
            if min_precision is not None and metrics.get("precision_amd", 0.0) < float(min_precision):
                keep = False
            if min_specificity is not None and metrics.get("specificity", 0.0) < float(min_specificity):
                keep = False
        elif mode != "balanced":
            raise ValueError(f"Unsupported threshold mode: {mode}")

        if keep:
            candidates.append(item)

    fallback_used = False
    if not candidates:
        candidates = all_results
        fallback_used = True

    def sort_key(item):
        metrics = item["metrics"]
        threshold = item["threshold"]
        if mode == "screening":
            return (
                item["score"],
                metrics.get("recall_amd", 0.0),
                metrics.get("precision_amd", 0.0),
                -abs(threshold - 0.5),
            )
        if mode == "conservative":
            return (
                item["score"],
                metrics.get("precision_amd", 0.0),
                metrics.get("specificity", 0.0),
                -abs(threshold - 0.5),
            )
        return (
            item["score"],
            metrics.get("f1_amd", 0.0),
            metrics.get("balanced_accuracy", 0.0),
            -abs(threshold - 0.5),
        )

    best = dict(max(candidates, key=sort_key))
    best["mode"] = mode
    best["metric"] = metric
    best["fallback_used"] = fallback_used
    best["num_candidates"] = len(candidates)
    return best


def threshold_search_table(y_true, y_prob, grid_step: float = 0.005):
    return [
        binary_metrics(y_true, y_prob, threshold=float(threshold))
        for threshold in np.arange(0.0, 1.0 + grid_step / 2.0, grid_step)
    ]
