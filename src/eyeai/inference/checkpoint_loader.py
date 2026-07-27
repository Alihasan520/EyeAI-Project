from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

from eyeai.models.retfound_finetune import interpolate_position_embedding
from eyeai.utils.checkpoints import load_checkpoint


def load_trained_checkpoint(
    model: torch.nn.Module,
    checkpoint_path: str | Path,
    map_location: str | torch.device = "cpu",
    strict: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a trained checkpoint and adapt ViT positional embeddings when needed."""
    checkpoint_path = Path(checkpoint_path)
    checkpoint = load_checkpoint(checkpoint_path, map_location=map_location)
    raw_state = checkpoint.get("model_state_dict", checkpoint)
    if not isinstance(raw_state, dict):
        raise TypeError(f"Checkpoint does not contain a model state dictionary: {checkpoint_path}")

    state_dict = dict(raw_state)
    position_embedding_interpolated = interpolate_position_embedding(model, state_dict)
    incompatible = model.load_state_dict(state_dict, strict=strict)

    report = {
        "loaded": True,
        "path": str(checkpoint_path),
        "strict": bool(strict),
        "position_embedding_interpolated": bool(position_embedding_interpolated),
        "missing_keys": list(getattr(incompatible, "missing_keys", [])),
        "unexpected_keys": list(getattr(incompatible, "unexpected_keys", [])),
        "source_epoch": checkpoint.get("epoch"),
        "source_image_size": checkpoint.get("image_size"),
        "source_selection_metric": checkpoint.get("selection_metric"),
        "source_selection_score": checkpoint.get("selection_score"),
        "source_best_threshold": checkpoint.get("best_threshold"),
    }
    return checkpoint, report
