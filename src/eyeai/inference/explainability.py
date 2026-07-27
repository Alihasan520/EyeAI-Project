from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from PIL import Image
import torch


@dataclass(frozen=True)
class AttributionResult:
    method: str
    target_class_index: int
    target_label: str
    heatmap: Image.Image
    overlay: Image.Image
    metrics: dict[str, Any]
    warnings: tuple[str, ...]

    def metadata(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "target_class_index": self.target_class_index,
            "target_label": self.target_label,
            "metrics": self.metrics,
            "warnings": list(self.warnings),
        }


class LastBlockActivationCapture:
    """Capture the final transformer block output as an attribution leaf tensor."""

    def __init__(self, block: torch.nn.Module) -> None:
        self.block = block
        self.activation: torch.Tensor | None = None
        self._handle: Any | None = None

    def __enter__(self) -> "LastBlockActivationCapture":
        def hook(_module: torch.nn.Module, _inputs: tuple[Any, ...], output: Any) -> Any:
            tensor = output[0] if isinstance(output, tuple) else output
            if not isinstance(tensor, torch.Tensor):
                raise TypeError("The final transformer block did not return a tensor.")
            tensor.requires_grad_(True)
            self.activation = tensor
            return output

        self._handle = self.block.register_forward_hook(hook)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if self._handle is not None:
            self._handle.remove()
        self._handle = None
        return False


def build_gradient_weighted_patch_attribution(
    *,
    activation: torch.Tensor,
    gradient: torch.Tensor,
    grid_size: tuple[int, int],
    variants: Sequence[str],
    processed_image: Image.Image,
    target_class_index: int,
    target_label: str,
    overlay_alpha: float = 0.45,
    black_threshold: int = 8,
    border_fraction: float = 0.10,
    minimum_fundus_focus: float = 0.75,
    maximum_border_focus: float = 0.35,
    minimum_tta_map_similarity: float = 0.15,
    maximum_normalized_entropy: float = 0.96,
) -> AttributionResult:
    if activation.ndim != 3 or gradient.ndim != 3:
        raise ValueError(
            "Expected transformer activations and gradients shaped [batch, tokens, channels]."
        )
    if activation.shape != gradient.shape:
        raise ValueError(
            f"Activation and gradient shapes differ: {activation.shape} vs {gradient.shape}."
        )
    if activation.shape[0] != len(variants):
        raise ValueError("The number of TTA variants does not match the attribution batch.")

    grid_height, grid_width = (int(grid_size[0]), int(grid_size[1]))
    patch_count = grid_height * grid_width
    if activation.shape[1] < patch_count:
        raise ValueError(
            f"The model produced {activation.shape[1]} tokens but {patch_count} patches are required."
        )

    patch_activation = activation[:, -patch_count:, :].detach().float()
    patch_gradient = gradient[:, -patch_count:, :].detach().float()
    channel_weights = patch_gradient.mean(dim=1, keepdim=True)
    patch_scores = torch.relu((patch_activation * channel_weights).sum(dim=-1))
    patch_scores = patch_scores.reshape(-1, grid_height, grid_width).cpu().numpy()

    aligned_maps: list[np.ndarray] = []
    warnings: list[str] = []
    for variant, patch_map in zip(variants, patch_scores):
        normalized, empty = _normalize_map(patch_map)
        if empty:
            warnings.append(f"empty_attribution_{variant}")
        resized = _resize_float_map(normalized, processed_image.size)
        if variant == "hflip":
            resized = np.fliplr(resized)
        elif variant != "original":
            warnings.append(f"unsupported_explanation_alignment_{variant}")
        aligned_maps.append(resized)

    raw_combined = np.mean(np.stack(aligned_maps, axis=0), axis=0)
    raw_combined, empty_combined = _normalize_map(raw_combined)
    if empty_combined:
        warnings.append("empty_combined_attribution")

    processed_rgb = np.asarray(processed_image.convert("RGB"), dtype=np.uint8)
    active_mask = np.mean(processed_rgb, axis=2) > float(black_threshold)

    total_raw = float(np.sum(raw_combined))
    fundus_focus = (
        float(np.sum(raw_combined[active_mask])) / total_raw if total_raw > 1e-12 else 0.0
    )
    border_mask = _border_mask(raw_combined.shape, border_fraction)
    border_focus = (
        float(np.sum(raw_combined[border_mask])) / total_raw if total_raw > 1e-12 else 0.0
    )

    masked = raw_combined * active_mask.astype(np.float32)
    masked, masked_empty = _normalize_map(masked)
    if masked_empty:
        warnings.append("attribution_removed_by_fundus_mask")

    tta_similarity = _mean_pairwise_similarity(aligned_maps)
    entropy = _normalized_entropy(masked)
    peak_y, peak_x = np.unravel_index(int(np.argmax(masked)), masked.shape)
    height, width = masked.shape
    centroid_x, centroid_y = _weighted_centroid(masked)
    dominant_region, dominant_region_mass = _dominant_spatial_region(masked)
    focus_bbox = _focus_bounding_box(masked, quantile=0.85)

    if fundus_focus < minimum_fundus_focus:
        warnings.append("low_fundus_attribution_focus")
    if border_focus > maximum_border_focus:
        warnings.append("high_border_attribution_focus")
    if len(aligned_maps) > 1 and tta_similarity < minimum_tta_map_similarity:
        warnings.append("low_tta_explanation_consistency")
    if entropy > maximum_normalized_entropy:
        warnings.append("diffuse_attribution")

    heatmap_rgb = _colorize_heatmap(masked)
    overlay_rgb = _blend_overlay(processed_rgb, heatmap_rgb, masked, overlay_alpha)

    metrics: dict[str, Any] = {
        "fundus_focus_fraction": round(fundus_focus, 6),
        "border_focus_fraction": round(border_focus, 6),
        "tta_map_similarity": round(tta_similarity, 6),
        "normalized_entropy": round(entropy, 6),
        "peak_x_pixel": int(peak_x),
        "peak_y_pixel": int(peak_y),
        "peak_x_fraction": round(float(peak_x) / max(width - 1, 1), 6),
        "peak_y_fraction": round(float(peak_y) / max(height - 1, 1), 6),
        "centroid_x_pixel": int(round(centroid_x)),
        "centroid_y_pixel": int(round(centroid_y)),
        "centroid_x_fraction": round(float(centroid_x) / max(width - 1, 1), 6),
        "centroid_y_fraction": round(float(centroid_y) / max(height - 1, 1), 6),
        "peak_region": _spatial_region(
            float(peak_x) / max(width - 1, 1),
            float(peak_y) / max(height - 1, 1),
        ),
        "centroid_region": _spatial_region(
            float(centroid_x) / max(width - 1, 1),
            float(centroid_y) / max(height - 1, 1),
        ),
        "dominant_region": dominant_region,
        "dominant_region_mass_fraction": round(dominant_region_mass, 6),
        "focus_bbox_x_min_fraction": round(focus_bbox[0], 6),
        "focus_bbox_y_min_fraction": round(focus_bbox[1], 6),
        "focus_bbox_x_max_fraction": round(focus_bbox[2], 6),
        "focus_bbox_y_max_fraction": round(focus_bbox[3], 6),
        "heatmap_width": int(width),
        "heatmap_height": int(height),
    }

    return AttributionResult(
        method="gradient_weighted_patch_attribution",
        target_class_index=int(target_class_index),
        target_label=str(target_label),
        heatmap=Image.fromarray(heatmap_rgb, mode="RGB"),
        overlay=Image.fromarray(overlay_rgb, mode="RGB"),
        metrics=metrics,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _normalize_map(values: np.ndarray) -> tuple[np.ndarray, bool]:
    array = np.asarray(values, dtype=np.float32)
    array = np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)
    minimum = float(np.min(array))
    maximum = float(np.max(array))
    if maximum - minimum <= 1e-12:
        return np.zeros_like(array, dtype=np.float32), True
    return (array - minimum) / (maximum - minimum), False


def _resize_float_map(values: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray(np.asarray(values * 255.0, dtype=np.uint8), mode="L")
    resized = image.resize(size, resample=Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.float32) / 255.0


def _border_mask(shape: tuple[int, int], border_fraction: float) -> np.ndarray:
    height, width = shape
    border_y = max(1, int(round(height * max(0.0, min(border_fraction, 0.49)))))
    border_x = max(1, int(round(width * max(0.0, min(border_fraction, 0.49)))))
    mask = np.zeros(shape, dtype=bool)
    mask[:border_y, :] = True
    mask[-border_y:, :] = True
    mask[:, :border_x] = True
    mask[:, -border_x:] = True
    return mask


def _mean_pairwise_similarity(maps: Sequence[np.ndarray]) -> float:
    if len(maps) < 2:
        return 1.0
    similarities: list[float] = []
    for index in range(len(maps) - 1):
        left = maps[index].astype(np.float64).ravel()
        right = maps[index + 1].astype(np.float64).ravel()
        left -= left.mean()
        right -= right.mean()
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        similarities.append(float(np.dot(left, right) / denominator) if denominator else 0.0)
    return float(np.mean(similarities))


def _normalized_entropy(values: np.ndarray) -> float:
    flat = np.asarray(values, dtype=np.float64).ravel()
    total = float(np.sum(flat))
    if total <= 1e-12 or flat.size <= 1:
        return 0.0
    probability = flat / total
    probability = probability[probability > 0]
    entropy = -float(np.sum(probability * np.log(probability)))
    return entropy / float(np.log(flat.size))


def _colorize_heatmap(values: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(values, dtype=np.float32), 0.0, 1.0)
    red = np.clip(1.5 - np.abs(4.0 * x - 3.0), 0.0, 1.0)
    green = np.clip(1.5 - np.abs(4.0 * x - 2.0), 0.0, 1.0)
    blue = np.clip(1.5 - np.abs(4.0 * x - 1.0), 0.0, 1.0)
    rgb = np.stack([red, green, blue], axis=-1)
    rgb *= x[..., None] > 0
    return np.asarray(np.round(rgb * 255.0), dtype=np.uint8)


def _blend_overlay(
    original_rgb: np.ndarray,
    heatmap_rgb: np.ndarray,
    intensity: np.ndarray,
    alpha: float,
) -> np.ndarray:
    original = original_rgb.astype(np.float32)
    heatmap = heatmap_rgb.astype(np.float32)
    alpha_map = np.clip(float(alpha), 0.0, 1.0) * np.clip(intensity, 0.0, 1.0)
    blended = original * (1.0 - alpha_map[..., None]) + heatmap * alpha_map[..., None]
    return np.asarray(np.clip(np.round(blended), 0, 255), dtype=np.uint8)

def _weighted_centroid(values: np.ndarray) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    total = float(array.sum())
    height, width = array.shape
    if total <= 1e-12:
        return (float(max(width - 1, 0)) / 2.0, float(max(height - 1, 0)) / 2.0)
    y_coordinates, x_coordinates = np.indices(array.shape, dtype=np.float64)
    centroid_x = float((x_coordinates * array).sum() / total)
    centroid_y = float((y_coordinates * array).sum() / total)
    return centroid_x, centroid_y


def _dominant_spatial_region(values: np.ndarray) -> tuple[str, float]:
    array = np.asarray(values, dtype=np.float64)
    height, width = array.shape
    row_edges = np.linspace(0, height, 4, dtype=int)
    column_edges = np.linspace(0, width, 4, dtype=int)
    masses = np.zeros((3, 3), dtype=np.float64)
    for row in range(3):
        for column in range(3):
            masses[row, column] = array[
                row_edges[row] : row_edges[row + 1],
                column_edges[column] : column_edges[column + 1],
            ].sum()
    total = float(masses.sum())
    row, column = np.unravel_index(int(np.argmax(masses)), masses.shape)
    vertical = ("upper", "middle", "lower")[row]
    horizontal = ("left", "center", "right")[column]
    fraction = float(masses[row, column] / total) if total > 1e-12 else 0.0
    return f"{vertical}-{horizontal}", fraction


def _focus_bounding_box(values: np.ndarray, quantile: float = 0.85) -> tuple[float, float, float, float]:
    array = np.asarray(values, dtype=np.float64)
    height, width = array.shape
    positive = array[array > 0]
    if positive.size == 0:
        return (0.0, 0.0, 1.0, 1.0)
    threshold = float(np.quantile(positive, min(max(quantile, 0.0), 1.0)))
    y_indices, x_indices = np.where(array >= threshold)
    if x_indices.size == 0:
        return (0.0, 0.0, 1.0, 1.0)
    return (
        float(x_indices.min()) / max(width - 1, 1),
        float(y_indices.min()) / max(height - 1, 1),
        float(x_indices.max()) / max(width - 1, 1),
        float(y_indices.max()) / max(height - 1, 1),
    )


def _spatial_region(x_fraction: float, y_fraction: float) -> str:
    horizontal = "left" if x_fraction < 1 / 3 else "center" if x_fraction < 2 / 3 else "right"
    vertical = "upper" if y_fraction < 1 / 3 else "middle" if y_fraction < 2 / 3 else "lower"
    return f"{vertical}-{horizontal}"

