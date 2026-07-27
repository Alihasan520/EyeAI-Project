from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw
import torch

from eyeai.inference.explainability import (
    build_gradient_weighted_patch_attribution,
)


def _processed_fundus(size: int = 224) -> Image.Image:
    image = Image.new("RGB", (size, size), "black")
    draw = ImageDraw.Draw(image)
    draw.ellipse((15, 15, size - 15, size - 15), fill=(145, 60, 40))
    return image


def test_patch_attribution_creates_aligned_images_and_metrics():
    activation = torch.zeros(2, 197, 8)
    gradient = torch.zeros_like(activation)
    activation[:, -196:, :] = 1.0
    gradient[:, -196:, :] = 0.5
    gradient[0, -196 + 7 * 14 + 7, :] = 3.0
    gradient[1, -196 + 7 * 14 + 6, :] = 3.0

    result = build_gradient_weighted_patch_attribution(
        activation=activation,
        gradient=gradient,
        grid_size=(14, 14),
        variants=["original", "hflip"],
        processed_image=_processed_fundus(),
        target_class_index=1,
        target_label="AMD",
    )

    assert result.heatmap.size == (224, 224)
    assert result.overlay.size == (224, 224)
    assert result.method == "gradient_weighted_patch_attribution"
    assert 0.0 <= result.metrics["fundus_focus_fraction"] <= 1.0
    assert 0.0 <= result.metrics["border_focus_fraction"] <= 1.0
    assert -1.0 <= result.metrics["tta_map_similarity"] <= 1.0


def test_black_background_is_suppressed_in_heatmap():
    activation = torch.ones(1, 197, 4)
    gradient = torch.ones_like(activation)
    result = build_gradient_weighted_patch_attribution(
        activation=activation,
        gradient=gradient,
        grid_size=(14, 14),
        variants=["original"],
        processed_image=_processed_fundus(),
        target_class_index=1,
        target_label="AMD",
    )
    heatmap = np.asarray(result.heatmap)
    assert np.max(heatmap[0:5, 0:5]) == 0


def test_empty_attribution_is_reported():
    activation = torch.zeros(1, 197, 4)
    gradient = torch.zeros_like(activation)
    result = build_gradient_weighted_patch_attribution(
        activation=activation,
        gradient=gradient,
        grid_size=(14, 14),
        variants=["original"],
        processed_image=_processed_fundus(),
        target_class_index=0,
        target_label="Non-AMD",
    )
    assert "empty_attribution_original" in result.warnings


def test_last_block_capture_supports_gradient_with_frozen_model():
    from eyeai.inference.explainability import LastBlockActivationCapture

    class TinyBlock(torch.nn.Module):
        def forward(self, value):
            return value + 1.0

    class TinyModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.block = TinyBlock()
            self.head = torch.nn.Linear(3, 2, bias=False)
            for parameter in self.parameters():
                parameter.requires_grad_(False)

        def forward(self, value):
            tokens = self.block(value)
            return self.head(tokens.mean(dim=1))

    model = TinyModel()
    batch = torch.ones(2, 4, 3)
    with torch.enable_grad():
        with LastBlockActivationCapture(model.block) as capture:
            logits = model(batch)
            assert capture.activation is not None
            gradient = torch.autograd.grad(logits[:, 1].sum(), capture.activation)[0]
    assert gradient.shape == (2, 4, 3)
