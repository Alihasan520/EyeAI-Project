from typing import Dict

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def binary_metrics(y_true, y_prob, threshold: float = 0.5) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob).astype(float)
    y_pred = (y_prob >= threshold).astype(int)

    metrics = {
        "threshold": float(threshold),
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_amd": f1_score(y_true, y_pred, pos_label=1, zero_division=0),
        "precision_amd": precision_score(y_true, y_pred, pos_label=1, zero_division=0),
        "recall_amd": recall_score(y_true, y_pred, pos_label=1, zero_division=0),
    }

    try:
        metrics["auc"] = roc_auc_score(y_true, y_prob)
    except Exception:
        metrics["auc"] = float("nan")

    try:
        metrics["average_precision"] = average_precision_score(y_true, y_prob)
    except Exception:
        metrics["average_precision"] = float("nan")

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
        metrics["specificity"] = tn / max(tn + fp, 1)
        metrics["sensitivity"] = tp / max(tp + fn, 1)
        metrics["tn"] = int(tn)
        metrics["fp"] = int(fp)
        metrics["fn"] = int(fn)
        metrics["tp"] = int(tp)

    return metrics
