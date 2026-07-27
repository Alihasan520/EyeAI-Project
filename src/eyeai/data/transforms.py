import random
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

import numpy as np
from PIL import Image
import torch
from torchvision import transforms as T
from torchvision.transforms import InterpolationMode

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def _interpolation_mode(value: str | InterpolationMode | None) -> InterpolationMode:
    if isinstance(value, InterpolationMode):
        return value
    mapping = {
        "nearest": InterpolationMode.NEAREST,
        "bilinear": InterpolationMode.BILINEAR,
        "bicubic": InterpolationMode.BICUBIC,
        "lanczos": InterpolationMode.LANCZOS,
    }
    return mapping.get(str(value or "bilinear").lower(), InterpolationMode.BILINEAR)


@dataclass
class ROISpec:
    name: str
    cx: float
    cy: float
    scale: float


def _normalize_roi_specs(roi_specs: Iterable[Dict[str, Any]] | None) -> List[ROISpec]:
    if not roi_specs:
        roi_specs = [
            {"name": "center_065", "cx": 0.50, "cy": 0.50, "scale": 0.65},
            {"name": "center_055", "cx": 0.50, "cy": 0.50, "scale": 0.55},
            {"name": "left_055", "cx": 0.43, "cy": 0.50, "scale": 0.55},
            {"name": "right_055", "cx": 0.57, "cy": 0.50, "scale": 0.55},
            {"name": "upper_055", "cx": 0.50, "cy": 0.43, "scale": 0.55},
            {"name": "lower_055", "cx": 0.50, "cy": 0.57, "scale": 0.55},
        ]

    specs = []
    for index, spec in enumerate(roi_specs):
        name = str(spec.get("name", f"roi_{index}"))
        cx = min(1.0, max(0.0, float(spec.get("cx", 0.5))))
        cy = min(1.0, max(0.0, float(spec.get("cy", 0.5))))
        scale = float(spec.get("scale", 1.0))
        if scale <= 0 or scale > 1:
            raise ValueError(f"ROI scale must be in (0, 1], got {scale} for {name}")
        specs.append(ROISpec(name=name, cx=cx, cy=cy, scale=scale))
    return specs


def _black_fraction(image: Image.Image, threshold: int = 8) -> float:
    arr = np.asarray(image.convert("RGB"))
    gray = arr.mean(axis=2)
    return float((gray <= int(threshold)).mean())


def _crop_square_once(image: Image.Image, cx: float, cy: float, scale: float) -> Image.Image:
    image = image.convert("RGB")
    width, height = image.size
    side = max(1, min(int(round(min(width, height) * scale)), width, height))
    center_x = int(round(width * cx))
    center_y = int(round(height * cy))
    left = max(0, min(center_x - side // 2, width - side))
    top = max(0, min(center_y - side // 2, height - side))
    return image.crop((left, top, left + side, top + side))


def crop_by_roi_spec(
    image: Image.Image,
    spec: ROISpec,
    black_fill_mode: str = "none",
    black_threshold: int = 8,
    avoid_black_roi: bool = False,
    max_black_fraction: float = 0.015,
    min_roi_scale: float = 0.45,
) -> Image.Image:
    """Crop one ROI without adding artificial background colors."""
    image = image.convert("RGB")
    mode = (black_fill_mode or "none").lower()
    if mode not in {"none", "off", "false", "no"}:
        raise ValueError("Artificial ROI fill modes are disabled because they create source artifacts.")

    scale = float(spec.scale)
    crop = _crop_square_once(image, spec.cx, spec.cy, scale)
    if not avoid_black_roi:
        return crop

    min_roi_scale = max(0.05, min(float(min_roi_scale), scale))
    max_black_fraction = max(0.0, float(max_black_fraction))
    while scale > min_roi_scale and _black_fraction(crop, threshold=black_threshold) > max_black_fraction:
        scale = max(min_roi_scale, scale * 0.92)
        crop = _crop_square_once(image, spec.cx, spec.cy, scale)
    return crop


class CenterCropByScale:
    def __init__(
        self,
        scale: float = 0.65,
        black_fill_mode: str = "none",
        black_threshold: int = 8,
        avoid_black_roi: bool = False,
        max_black_fraction: float = 0.015,
        min_roi_scale: float = 0.45,
    ):
        if scale <= 0 or scale > 1:
            raise ValueError(f"center crop scale must be in (0, 1], got {scale}")
        self.spec = ROISpec(name="center", cx=0.5, cy=0.5, scale=float(scale))
        self.kwargs = {
            "black_fill_mode": black_fill_mode,
            "black_threshold": int(black_threshold),
            "avoid_black_roi": bool(avoid_black_roi),
            "max_black_fraction": float(max_black_fraction),
            "min_roi_scale": float(min_roi_scale),
        }

    def __call__(self, image: Image.Image) -> Image.Image:
        return crop_by_roi_spec(image, self.spec, **self.kwargs)


class RandomROICrop:
    def __init__(
        self,
        roi_specs=None,
        black_fill_mode: str = "none",
        black_threshold: int = 8,
        avoid_black_roi: bool = False,
        max_black_fraction: float = 0.015,
        min_roi_scale: float = 0.45,
    ):
        self.roi_specs = _normalize_roi_specs(roi_specs)
        self.kwargs = {
            "black_fill_mode": black_fill_mode,
            "black_threshold": int(black_threshold),
            "avoid_black_roi": bool(avoid_black_roi),
            "max_black_fraction": float(max_black_fraction),
            "min_roi_scale": float(min_roi_scale),
        }

    def __call__(self, image: Image.Image) -> Image.Image:
        return crop_by_roi_spec(image, random.choice(self.roi_specs), **self.kwargs)


class MultiROIEvalTransform:
    def __init__(
        self,
        image_size: int,
        roi_specs=None,
        black_fill_mode: str = "none",
        black_threshold: int = 8,
        avoid_black_roi: bool = False,
        max_black_fraction: float = 0.015,
        min_roi_scale: float = 0.45,
        mean=None,
        std=None,
        interpolation: str | InterpolationMode = "bilinear",
    ):
        self.roi_specs = _normalize_roi_specs(roi_specs)
        self.kwargs = {
            "black_fill_mode": black_fill_mode,
            "black_threshold": int(black_threshold),
            "avoid_black_roi": bool(avoid_black_roi),
            "max_black_fraction": float(max_black_fraction),
            "min_roi_scale": float(min_roi_scale),
        }
        self.post = T.Compose([
            T.Resize((image_size, image_size), interpolation=_interpolation_mode(interpolation)),
            T.ToTensor(),
            T.Normalize(mean=mean or IMAGENET_MEAN, std=std or IMAGENET_STD),
        ])

    def __call__(self, image: Image.Image) -> torch.Tensor:
        image = image.convert("RGB")
        views = [self.post(crop_by_roi_spec(image, spec, **self.kwargs)) for spec in self.roi_specs]
        return torch.stack(views, dim=0)


def _pre_resize_transforms(
    crop_mode: str = "full",
    center_crop_scale: float = 0.65,
    roi_specs=None,
    black_fill_mode: str = "none",
    black_threshold: int = 8,
    avoid_black_roi: bool = False,
    max_black_fraction: float = 0.015,
    min_roi_scale: float = 0.45,
):
    mode = (crop_mode or "full").lower()
    common = {
        "black_fill_mode": black_fill_mode,
        "black_threshold": black_threshold,
        "avoid_black_roi": avoid_black_roi,
        "max_black_fraction": max_black_fraction,
        "min_roi_scale": min_roi_scale,
    }
    if mode in {"center", "center_crop", "center_macula", "macula", "macula_center"}:
        return [CenterCropByScale(scale=float(center_crop_scale), **common)]
    if mode in {"smart_roi_random", "random_roi", "multi_roi_random"}:
        return [RandomROICrop(roi_specs=roi_specs, **common)]
    if mode in {"full", "none", "fundus"}:
        return []
    raise ValueError(f"Unsupported crop_mode for single-image transform: {crop_mode}")


def build_train_transforms(
    image_size: int,
    rotation_degrees: float = 0,
    horizontal_flip_prob: float = 0.5,
    brightness: float = 0.06,
    contrast: float = 0.06,
    saturation: float = 0.03,
    gaussian_blur_prob: float = 0.0,
    crop_mode: str = "full",
    center_crop_scale: float = 0.65,
    roi_specs=None,
    black_fill_mode: str = "none",
    black_threshold: int = 8,
    avoid_black_roi: bool = False,
    max_black_fraction: float = 0.015,
    min_roi_scale: float = 0.45,
    mean=None,
    std=None,
    interpolation: str | InterpolationMode = "bilinear",
):
    """Build conservative full-fundus augmentations.

    Rotation is disabled in the corrected configs because rotating a cropped
    fundus creates new border pixels. It remains available for controlled tests.
    """
    interpolation_mode = _interpolation_mode(interpolation)
    transforms = _pre_resize_transforms(
        crop_mode=crop_mode,
        center_crop_scale=center_crop_scale,
        roi_specs=roi_specs,
        black_fill_mode=black_fill_mode,
        black_threshold=black_threshold,
        avoid_black_roi=avoid_black_roi,
        max_black_fraction=max_black_fraction,
        min_roi_scale=min_roi_scale,
    )
    transforms.append(T.Resize((image_size, image_size), interpolation=interpolation_mode))

    if horizontal_flip_prob and horizontal_flip_prob > 0:
        transforms.append(T.RandomHorizontalFlip(p=float(horizontal_flip_prob)))
    if rotation_degrees and rotation_degrees > 0:
        transforms.append(
            T.RandomRotation(
                degrees=float(rotation_degrees),
                interpolation=interpolation_mode,
                fill=0,
            )
        )
    if any(value and value > 0 for value in [brightness, contrast, saturation]):
        transforms.append(
            T.ColorJitter(
                brightness=float(brightness),
                contrast=float(contrast),
                saturation=float(saturation),
                hue=0.0,
            )
        )
    if gaussian_blur_prob and gaussian_blur_prob > 0:
        transforms.append(
            T.RandomApply([T.GaussianBlur(kernel_size=3, sigma=(0.1, 1.0))], p=float(gaussian_blur_prob))
        )

    transforms.extend([
        T.ToTensor(),
        T.Normalize(mean=mean or IMAGENET_MEAN, std=std or IMAGENET_STD),
    ])
    return T.Compose(transforms)


def build_eval_transforms(
    image_size: int,
    crop_mode: str = "full",
    center_crop_scale: float = 0.65,
    roi_specs=None,
    eval_crop_mode: str | None = None,
    black_fill_mode: str = "none",
    black_threshold: int = 8,
    avoid_black_roi: bool = False,
    max_black_fraction: float = 0.015,
    min_roi_scale: float = 0.45,
    mean=None,
    std=None,
    interpolation: str | InterpolationMode = "bilinear",
):
    mode = (eval_crop_mode or crop_mode or "full").lower()
    if mode in {"smart_multi_roi", "multi_roi", "multi_roi_eval"}:
        return MultiROIEvalTransform(
            image_size=image_size,
            roi_specs=roi_specs,
            black_fill_mode=black_fill_mode,
            black_threshold=black_threshold,
            avoid_black_roi=avoid_black_roi,
            max_black_fraction=max_black_fraction,
            min_roi_scale=min_roi_scale,
            mean=mean,
            std=std,
            interpolation=interpolation,
        )

    transforms = _pre_resize_transforms(
        crop_mode=mode,
        center_crop_scale=center_crop_scale,
        roi_specs=roi_specs,
        black_fill_mode=black_fill_mode,
        black_threshold=black_threshold,
        avoid_black_roi=avoid_black_roi,
        max_black_fraction=max_black_fraction,
        min_roi_scale=min_roi_scale,
    )
    transforms.extend([
        T.Resize((image_size, image_size), interpolation=_interpolation_mode(interpolation)),
        T.ToTensor(),
        T.Normalize(mean=mean or IMAGENET_MEAN, std=std or IMAGENET_STD),
    ])
    return T.Compose(transforms)
