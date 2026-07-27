from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image
import torch
import timm

from eyeai.data.transforms import build_eval_transforms
from eyeai.inference.explainability import (
    AttributionResult,
    LastBlockActivationCapture,
    build_gradient_weighted_patch_attribution,
)
from eyeai.inference.model_package import load_torch_checkpoint, load_yaml
from eyeai.inference.tta import apply_tta_variant
from eyeai.preprocessing.fundus_crop import crop_fundus_region


@dataclass(frozen=True)
class PredictionResult:
    label: str
    probability: float
    threshold: float
    decision: bool
    original_probability: float
    horizontal_flip_probability: float
    model_version: str
    warnings: list[str]
    input_width: int
    input_height: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "probability": self.probability,
            "threshold": self.threshold,
            "decision": self.decision,
            "tta": {
                "original_probability": self.original_probability,
                "horizontal_flip_probability": self.horizontal_flip_probability,
                "absolute_disagreement": abs(
                    self.original_probability - self.horizontal_flip_probability
                ),
                "aggregation": "mean_probability",
            },
            "model_version": self.model_version,
            "quality": {
                "warnings": self.warnings,
                "input_width": self.input_width,
                "input_height": self.input_height,
            },
            "disclaimer": "AI-assisted screening output; clinical confirmation is required.",
        }


@dataclass(frozen=True)
class ExplainedPrediction:
    prediction: PredictionResult
    original_image: Image.Image
    processed_image: Image.Image
    attribution: AttributionResult


class Run09Predictor:
    def __init__(self, package_dir: str | Path, device: str | torch.device | None = None):
        self.package_dir = Path(package_dir)
        self.config = load_yaml(self.package_dir / "model_config.yaml")
        self.device = torch.device(
            device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        )

        checkpoint_path = self.package_dir / self.config["package"].get(
            "checkpoint_output_name", "model.pth"
        )
        checkpoint = load_torch_checkpoint(checkpoint_path, map_location="cpu")
        state_dict = checkpoint.get("model_state_dict")
        if not isinstance(state_dict, dict):
            raise TypeError(f"Inference checkpoint has no model_state_dict: {checkpoint_path}")

        model_cfg = self.config["model"]
        self.model = timm.create_model(
            str(model_cfg["timm_name"]),
            pretrained=False,
            num_classes=int(model_cfg["num_classes"]),
            img_size=int(model_cfg["image_size"]),
            global_pool=str(model_cfg.get("global_pool", "avg")),
            drop_path_rate=0.0,
        )
        incompatible = self.model.load_state_dict(state_dict, strict=True)
        if incompatible.missing_keys or incompatible.unexpected_keys:
            raise RuntimeError(
                "Inference checkpoint is incompatible with the package architecture: "
                f"missing={incompatible.missing_keys}, unexpected={incompatible.unexpected_keys}"
            )
        self.model.to(self.device).eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)

        preprocessing = self.config["preprocessing"]
        self.eval_transform = build_eval_transforms(
            int(model_cfg["image_size"]),
            crop_mode="full",
            eval_crop_mode="full",
            mean=preprocessing["mean"],
            std=preprocessing["std"],
            interpolation=preprocessing["interpolation"],
        )

    def _open_and_process(
        self, image: str | Path | Image.Image
    ) -> tuple[Image.Image, Image.Image, list[str]]:
        if isinstance(image, Image.Image):
            opened = image.convert("RGB")
        else:
            with Image.open(Path(image)) as source:
                opened = source.convert("RGB")

        preprocessing = self.config["preprocessing"]
        processed = crop_fundus_region(
            opened,
            threshold=int(preprocessing.get("black_threshold", 8)),
            pad_ratio=float(preprocessing.get("crop_pad_ratio", 0.03)),
            make_square=bool(preprocessing.get("make_square", True)),
        )
        warnings = self._quality_warnings(opened, processed)
        return opened, processed, warnings

    def _quality_warnings(self, image: Image.Image, processed: Image.Image) -> list[str]:
        warnings: list[str] = []
        quality = self.config.get("quality", {})
        width, height = image.size
        if width < int(quality.get("minimum_width", 128)) or height < int(
            quality.get("minimum_height", 128)
        ):
            warnings.append("low_input_resolution")

        array = np.asarray(processed.convert("RGB"), dtype=np.uint8)
        black_fraction = float(np.mean(np.mean(array, axis=2) <= 8))
        if black_fraction > float(quality.get("maximum_black_fraction_warning", 0.45)):
            warnings.append("high_black_fraction")
        return warnings

    def _build_batch(
        self, processed: Image.Image
    ) -> tuple[list[str], torch.Tensor]:
        variants = list(self.config["inference"].get("variants", ["original", "hflip"]))
        tensors = [
            self.eval_transform(apply_tta_variant(processed, variant))
            for variant in variants
        ]
        return variants, torch.stack(tensors, dim=0).to(self.device)

    def _prediction_from_probabilities(
        self,
        *,
        probabilities: Mapping[str, float],
        warnings: list[str],
        input_width: int,
        input_height: int,
    ) -> PredictionResult:
        values = [float(value) for value in probabilities.values()]
        probability = float(np.mean(values))
        threshold = float(self.config["inference"]["threshold"])
        decision = probability >= threshold
        original_probability = float(probabilities.get("original", probability))
        hflip_probability = float(probabilities.get("hflip", probability))
        disagreement = abs(original_probability - hflip_probability)
        if disagreement > float(
            self.config.get("quality", {}).get("maximum_tta_disagreement_warning", 0.15)
        ):
            warnings.append("high_tta_disagreement")

        class_names = {
            int(key): value for key, value in self.config["model"]["class_names"].items()
        }
        return PredictionResult(
            label=str(class_names[1 if decision else 0]),
            probability=probability,
            threshold=threshold,
            decision=decision,
            original_probability=original_probability,
            horizontal_flip_probability=hflip_probability,
            model_version=str(self.config["package"]["model_version"]),
            warnings=list(dict.fromkeys(warnings)),
            input_width=input_width,
            input_height=input_height,
        )

    @torch.inference_mode()
    def predict(self, image: str | Path | Image.Image) -> PredictionResult:
        opened, processed, warnings = self._open_and_process(image)
        variants, batch = self._build_batch(processed)
        logits = self.model(batch)
        amd_probabilities = torch.softmax(logits, dim=1)[:, 1].detach().cpu().tolist()
        probabilities = {
            variant: float(probability)
            for variant, probability in zip(variants, amd_probabilities)
        }
        return self._prediction_from_probabilities(
            probabilities=probabilities,
            warnings=warnings,
            input_width=opened.width,
            input_height=opened.height,
        )

    def predict_with_explanation(
        self,
        image: str | Path | Image.Image,
        *,
        explanation_config: Mapping[str, float | int | str | bool] | None = None,
    ) -> ExplainedPrediction:
        opened, processed, warnings = self._open_and_process(image)
        variants, batch = self._build_batch(processed)
        config = dict(explanation_config or {})

        blocks = getattr(self.model, "blocks", None)
        if blocks is None or len(blocks) == 0:
            raise RuntimeError("The model does not expose transformer blocks for explanation.")

        with torch.enable_grad():
            with LastBlockActivationCapture(blocks[-1]) as capture:
                logits = self.model(batch)
                amd_probabilities = torch.softmax(logits, dim=1)[:, 1]
                probabilities = {
                    variant: float(probability.detach().cpu())
                    for variant, probability in zip(variants, amd_probabilities)
                }
                prediction = self._prediction_from_probabilities(
                    probabilities=probabilities,
                    warnings=warnings,
                    input_width=opened.width,
                    input_height=opened.height,
                )
                target_class_index = 1 if prediction.decision else 0
                target_score = logits[:, target_class_index].sum()
                activation = capture.activation
                if activation is None:
                    raise RuntimeError("Failed to capture the final transformer activation.")
                gradient = torch.autograd.grad(
                    target_score,
                    activation,
                    retain_graph=False,
                    create_graph=False,
                    allow_unused=False,
                )[0]

        grid_size = getattr(self.model.patch_embed, "grid_size", None)
        if grid_size is None:
            patch_count = int(getattr(self.model.patch_embed, "num_patches"))
            side = int(round(patch_count ** 0.5))
            grid_size = (side, side)
        elif isinstance(grid_size, int):
            grid_size = (grid_size, grid_size)
        else:
            grid_size = tuple(int(value) for value in grid_size)

        class_names = {
            int(key): str(value)
            for key, value in self.config["model"]["class_names"].items()
        }
        preprocessing = self.config["preprocessing"]
        attribution = build_gradient_weighted_patch_attribution(
            activation=activation,
            gradient=gradient,
            grid_size=(int(grid_size[0]), int(grid_size[1])),
            variants=variants,
            processed_image=processed,
            target_class_index=target_class_index,
            target_label=class_names[target_class_index],
            overlay_alpha=float(config.get("overlay_alpha", 0.45)),
            black_threshold=int(
                config.get("black_threshold", preprocessing.get("black_threshold", 8))
            ),
            border_fraction=float(config.get("border_fraction", 0.10)),
            minimum_fundus_focus=float(config.get("minimum_fundus_focus", 0.75)),
            maximum_border_focus=float(config.get("maximum_border_focus", 0.35)),
            minimum_tta_map_similarity=float(
                config.get("minimum_tta_map_similarity", 0.15)
            ),
            maximum_normalized_entropy=float(
                config.get("maximum_normalized_entropy", 0.96)
            ),
        )

        return ExplainedPrediction(
            prediction=prediction,
            original_image=opened,
            processed_image=processed,
            attribution=attribution,
        )

    def predict_to_json(self, image: str | Path | Image.Image) -> str:
        return json.dumps(self.predict(image).to_dict(), indent=2, ensure_ascii=False)
