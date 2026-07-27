from pathlib import Path
from typing import List

import pandas as pd
from PIL import Image
import torch
from tqdm.auto import tqdm

from eyeai.data.transforms import build_eval_transforms
from eyeai.inference.tta import build_tta_transforms


def _binary_logit_from_two_class_logits(logits: torch.Tensor) -> torch.Tensor:
    if logits.ndim == 2 and logits.size(1) == 2:
        return logits[:, 1] - logits[:, 0]
    return logits.view(-1)


def predict_dataframe(
    model,
    df: pd.DataFrame,
    image_size: int,
    device: torch.device,
    tta_variants: List[str] | None = None,
    batch_size: int = 1,
    image_col: str = "proc_image_path",
    image_root: str | Path | None = None,
    data_config: dict | None = None,
    model_report: dict | None = None,
) -> pd.DataFrame:
    del batch_size
    model.eval()
    rows = []
    data_config = data_config or {}
    model_data_config = (model_report or {}).get("data_config", {}) or {}
    mean = model_data_config.get("mean")
    std = model_data_config.get("std")
    interpolation = model_data_config.get("interpolation", "bilinear")

    crop_kwargs = {
        "crop_mode": data_config.get("crop_mode", "full"),
        "eval_crop_mode": data_config.get("eval_crop_mode", data_config.get("crop_mode", "full")),
        "center_crop_scale": float(data_config.get("center_crop_scale", 0.75)),
        "roi_specs": data_config.get("roi_specs"),
        "black_fill_mode": data_config.get("black_fill_mode", "none"),
        "black_threshold": int(data_config.get("black_threshold", 8)),
        "avoid_black_roi": bool(data_config.get("avoid_black_roi", False)),
        "max_black_fraction": float(data_config.get("max_black_fraction", 0.015)),
        "min_roi_scale": float(data_config.get("min_roi_scale", 0.45)),
        "mean": mean,
        "std": std,
        "interpolation": interpolation,
    }

    use_tta = bool(tta_variants)
    if use_tta and crop_kwargs["eval_crop_mode"] not in {"full", "none", "fundus"}:
        raise ValueError("TTA is only supported for full-fundus inference in the corrected pipeline.")

    eval_transform = build_eval_transforms(image_size, **crop_kwargs)
    tta_transform = (
        build_tta_transforms(
            image_size,
            tta_variants,
            mean=mean,
            std=std,
            interpolation=interpolation,
        )
        if use_tta
        else None
    )
    root = Path(image_root) if image_root is not None else None

    with torch.no_grad():
        for row in tqdm(df.itertuples(index=False), total=len(df), desc="Predict"):
            value = str(getattr(row, image_col))
            image_path = Path(value)
            if not image_path.is_absolute():
                if root is None:
                    raise RuntimeError(f"Relative image path requires image_root: {value}")
                image_path = root / image_path
            with Image.open(image_path) as opened:
                image = opened.convert("RGB")

            if use_tta:
                tensors = tta_transform(image)
                batch = torch.stack(tensors, dim=0).to(device)
                logits = model(batch)
                probabilities = torch.softmax(logits, dim=1)[:, 1]
                binary_logits = _binary_logit_from_two_class_logits(logits)
                probability_amd = float(probabilities.mean().detach().cpu().item())
                logit_amd = float(binary_logits.mean().detach().cpu().item())
            else:
                tensor = eval_transform(image)
                if tensor.ndim == 4:
                    logits = model(tensor.to(device))
                    probabilities = torch.softmax(logits, dim=1)[:, 1]
                    probability_amd = float(probabilities.mean().detach().cpu().item())
                    logit_amd = float(_binary_logit_from_two_class_logits(logits).mean().detach().cpu().item())
                else:
                    logits = model(tensor.unsqueeze(0).to(device))
                    probability_amd = float(torch.softmax(logits, dim=1)[0, 1].detach().cpu().item())
                    logit_amd = float(_binary_logit_from_two_class_logits(logits)[0].detach().cpu().item())

            rows.append({
                "image_id": getattr(row, "image_id", ""),
                "image_name": getattr(row, "image_name", image_path.name),
                "patient_id": str(getattr(row, "patient_id", "")),
                "eye": str(getattr(row, "eye", "")),
                "dataset_source": str(getattr(row, "dataset_source", "unknown")),
                "label": int(getattr(row, "label", -1)),
                "binary_label": int(getattr(row, "binary_label", -1)),
                "prob_amd": probability_amd,
                "logit_amd": logit_amd,
            })

    return pd.DataFrame(rows)
