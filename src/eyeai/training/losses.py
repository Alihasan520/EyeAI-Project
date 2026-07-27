import numpy as np
import torch
import torch.nn as nn


def build_class_weights(labels, num_classes: int = 2, mode: str = "balanced_capped", max_weight: float = 2.0, device=None):
    labels = np.asarray(labels).astype(int)
    counts = np.bincount(labels, minlength=num_classes).astype(float)

    if mode in {None, "none"}:
        return None

    if mode == "balanced_capped":
        weights = len(labels) / (num_classes * np.maximum(counts, 1.0))
        weights = weights / weights.mean()
        weights = np.clip(weights, 0.0, max_weight)
    else:
        raise ValueError(f"Unsupported class weight mode: {mode}")

    return torch.tensor(weights, dtype=torch.float32, device=device)


def build_ce_loss(labels, num_classes: int, mode: str, max_weight: float, device, label_smoothing: float = 0.0):
    weights = build_class_weights(labels, num_classes=num_classes, mode=mode, max_weight=max_weight, device=device)
    return nn.CrossEntropyLoss(weight=weights, label_smoothing=float(label_smoothing)), weights
