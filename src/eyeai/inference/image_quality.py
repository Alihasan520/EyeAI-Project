from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class ImageQualityAssessment:
    processable: bool
    status: str
    warnings: tuple[str, ...]
    metrics: dict[str, float | int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "processable": self.processable,
            "status": self.status,
            "warnings": list(self.warnings),
            "metrics": self.metrics,
        }


def assess_fundus_image_quality(
    image: Image.Image,
    processed: Image.Image,
    thresholds: Mapping[str, float | int] | None = None,
) -> ImageQualityAssessment:
    cfg = dict(thresholds or {})
    width, height = image.size
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    processed_rgb = np.asarray(processed.convert("RGB"), dtype=np.float32)

    gray = _rgb_to_gray(rgb)
    processed_gray = _rgb_to_gray(processed_rgb)
    active_mask = processed_gray > 8.0
    active_fraction = float(np.mean(active_mask))
    black_fraction = 1.0 - active_fraction

    warnings: list[str] = []
    if width < int(cfg.get("minimum_width", 512)) or height < int(
        cfg.get("minimum_height", 512)
    ):
        warnings.append("low_input_resolution")

    if active_fraction < float(cfg.get("minimum_fundus_fraction", 0.45)):
        warnings.append("low_fundus_coverage")
    if black_fraction > float(cfg.get("maximum_black_fraction", 0.55)):
        warnings.append("high_black_fraction")

    if np.any(active_mask):
        active_gray = processed_gray[active_mask]
        active_rgb = processed_rgb[active_mask]
        brightness_mean = float(np.mean(active_gray))
        brightness_std = float(np.std(active_gray))
        overexposed_fraction = float(np.mean(active_gray >= 245.0))
        underexposed_fraction = float(np.mean(active_gray <= 20.0))
        saturation = _pixel_saturation(active_rgb)
        glare_fraction = float(
            np.mean((active_gray >= 235.0) & (saturation <= 0.15))
        )
    else:
        brightness_mean = 0.0
        brightness_std = 0.0
        overexposed_fraction = 0.0
        underexposed_fraction = 1.0
        glare_fraction = 0.0

    laplacian_variance = _laplacian_variance(processed_gray, active_mask)

    if overexposed_fraction > float(
        cfg.get("maximum_overexposed_fraction", 0.08)
    ):
        warnings.append("possible_overexposure")
    if glare_fraction > float(cfg.get("maximum_glare_fraction", 0.03)):
        warnings.append("possible_glare")
    if underexposed_fraction > float(
        cfg.get("maximum_underexposed_fraction", 0.30)
    ):
        warnings.append("possible_underexposure")
    if brightness_std < float(cfg.get("minimum_contrast_std", 20.0)):
        warnings.append("low_contrast")
    if laplacian_variance < float(
        cfg.get("minimum_laplacian_variance", 20.0)
    ):
        warnings.append("possible_blur")

    status = "acceptable" if not warnings else "review_required"
    metrics: dict[str, float | int] = {
        "input_width": int(width),
        "input_height": int(height),
        "input_megapixels": round((width * height) / 1_000_000.0, 4),
        "fundus_fraction": round(active_fraction, 6),
        "black_fraction": round(black_fraction, 6),
        "mean_brightness": round(brightness_mean, 4),
        "contrast_std": round(brightness_std, 4),
        "overexposed_fraction": round(overexposed_fraction, 6),
        "underexposed_fraction": round(underexposed_fraction, 6),
        "glare_fraction": round(glare_fraction, 6),
        "laplacian_variance": round(laplacian_variance, 4),
    }
    return ImageQualityAssessment(
        processable=True,
        status=status,
        warnings=tuple(dict.fromkeys(warnings)),
        metrics=metrics,
    )


def _rgb_to_gray(array: np.ndarray) -> np.ndarray:
    return (
        0.299 * array[..., 0]
        + 0.587 * array[..., 1]
        + 0.114 * array[..., 2]
    )


def _pixel_saturation(rgb_pixels: np.ndarray) -> np.ndarray:
    maximum = np.max(rgb_pixels, axis=1)
    minimum = np.min(rgb_pixels, axis=1)
    return (maximum - minimum) / np.maximum(maximum, 1.0)


def _laplacian_variance(gray: np.ndarray, mask: np.ndarray) -> float:
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    center = gray[1:-1, 1:-1]
    laplacian = (
        -4.0 * center
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )
    valid = (
        mask[1:-1, 1:-1]
        & mask[:-2, 1:-1]
        & mask[2:, 1:-1]
        & mask[1:-1, :-2]
        & mask[1:-1, 2:]
    )
    if not np.any(valid):
        return 0.0
    return float(np.var(laplacian[valid]))
