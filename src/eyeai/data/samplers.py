from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
import torch
from torch.utils.data import WeightedRandomSampler


def _normalized_target_weights(targets: dict[str, float]) -> dict[str, float]:
    clean = {str(k): float(v) for k, v in targets.items() if float(v) > 0}
    total = sum(clean.values())
    if total <= 0:
        raise ValueError("Sampler target weights must contain at least one positive value.")
    return {k: v / total for k, v in clean.items()}


def build_training_sampler(
    dataframe: pd.DataFrame,
    mode: str = "none",
    label_col: str = "binary_label",
    source_col: str = "dataset_source",
    positive_fraction: float = 0.50,
    external_positive_fraction: float = 0.35,
    external_sources: Iterable[str] = ("armd_curated",),
    num_samples: int | None = None,
    seed: int = 42,
):
    """Build a deterministic weighted sampler for class/source-aware training.

    Modes:
    - none: return None and let DataLoader shuffle normally.
    - class_balanced: target the requested positive/negative fractions.
    - source_aware: additionally control the external share within positive samples.
    """
    mode = (mode or "none").lower()
    if mode in {"none", "shuffle"}:
        return None, {"mode": "none"}

    if label_col not in dataframe.columns:
        raise KeyError(f"Missing sampler label column: {label_col}")

    df = dataframe.reset_index(drop=True).copy()
    labels = df[label_col].astype(int).to_numpy()
    if not set(np.unique(labels)).issubset({0, 1}):
        raise ValueError("Binary sampler requires labels in {0, 1}.")

    positive_fraction = float(positive_fraction)
    if not 0 < positive_fraction < 1:
        raise ValueError("positive_fraction must be in (0, 1).")

    group = np.full(len(df), "negative", dtype=object)
    group[labels == 1] = "positive_hyamd"

    targets = {
        "negative": 1.0 - positive_fraction,
        "positive_hyamd": positive_fraction,
    }

    if mode == "source_aware":
        if source_col not in df.columns:
            raise KeyError(f"Missing sampler source column: {source_col}")
        external_sources = {str(x).lower() for x in external_sources}
        sources = df[source_col].astype(str).str.lower().to_numpy()
        external_mask = (labels == 1) & np.isin(sources, list(external_sources))
        group[external_mask] = "positive_external"

        external_positive_fraction = float(external_positive_fraction)
        if not 0 <= external_positive_fraction < 1:
            raise ValueError("external_positive_fraction must be in [0, 1).")
        targets = {
            "negative": 1.0 - positive_fraction,
            "positive_hyamd": positive_fraction * (1.0 - external_positive_fraction),
            "positive_external": positive_fraction * external_positive_fraction,
        }
    elif mode != "class_balanced":
        raise ValueError(f"Unsupported sampling mode: {mode}")

    counts = {name: int((group == name).sum()) for name in sorted(set(group.tolist()))}
    targets = _normalized_target_weights(targets)

    missing_groups = [name for name, target in targets.items() if target > 0 and counts.get(name, 0) == 0]
    if missing_groups:
        raise RuntimeError(f"Sampler target groups are missing from the training data: {missing_groups}")

    sample_weights = np.zeros(len(df), dtype=np.float64)
    for name, target in targets.items():
        mask = group == name
        sample_weights[mask] = target / max(int(mask.sum()), 1)

    if (sample_weights <= 0).any():
        bad = sorted(set(group[sample_weights <= 0].tolist()))
        raise RuntimeError(f"Some training rows received non-positive sampler weights: {bad}")

    generator = torch.Generator()
    generator.manual_seed(int(seed))
    samples_per_epoch = int(num_samples) if num_samples else len(df)
    sampler = WeightedRandomSampler(
        weights=torch.as_tensor(sample_weights, dtype=torch.double),
        num_samples=samples_per_epoch,
        replacement=True,
        generator=generator,
    )

    report = {
        "mode": mode,
        "num_samples": samples_per_epoch,
        "group_counts": counts,
        "target_fractions": targets,
        "positive_fraction": positive_fraction,
        "external_positive_fraction": external_positive_fraction if mode == "source_aware" else 0.0,
    }
    return sampler, report
