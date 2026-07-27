from __future__ import annotations

import gc
import io
import threading
import time
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from eyeai.api.artifacts import ExplanationArtifactStore
from eyeai.api.config import ApiSettings
from eyeai.inference.image_quality import assess_fundus_image_quality
from eyeai.preprocessing.fundus_crop import crop_fundus_region


class PredictionService:
    def __init__(
        self,
        settings: ApiSettings,
        *,
        predictor_factory: Callable[..., Any] | None = None,
        shared_lock: threading.RLock | threading.Lock | None = None,
    ) -> None:
        self.settings = settings
        self.predictor_factory = predictor_factory or _default_predictor_factory
        self.predictor: Any | None = None
        self._lock = (
            shared_lock
            if shared_lock is not None
            else (threading.Lock() if settings.inference_lock else _NullLock())
        )
        self.artifact_store = (
            ExplanationArtifactStore(
                settings.explanation_output_dir,
                settings.artifacts_url_prefix,
            )
            if settings.explainability_enabled
            else None
        )

    @property
    def loaded(self) -> bool:
        return self.predictor is not None

    def load(self) -> None:
        package_dir = self.settings.model_package_dir
        if not package_dir.is_dir():
            raise FileNotFoundError(f"Model package was not found: {package_dir}")
        device = None if self.settings.device == "auto" else self.settings.device
        self.predictor = self.predictor_factory(package_dir, device=device)

    def model_info(self) -> dict[str, Any]:
        predictor = self._require_predictor()
        config = predictor.config
        validation = config.get("validation", {})
        package = config["package"]
        model = config["model"]
        inference = config["inference"]
        explainability = dict(self.settings.explainability or {})
        return {
            "model_version": str(package["model_version"]),
            "package_name": str(package["package_name"]),
            "architecture": str(model["architecture"]),
            "task": str(package.get("task", "binary_amd_screening")),
            "image_size": int(model["image_size"]),
            "threshold": float(inference["threshold"]),
            "variants": list(inference.get("variants", [])),
            "aggregation": str(inference.get("aggregation", "mean_probability")),
            "class_names": {
                str(key): str(value) for key, value in model["class_names"].items()
            },
            "device": str(predictor.device),
            "fixed_split_metrics": dict(validation.get("fixed_split_tta", {})),
            "robust_oof_reference": dict(
                validation.get("robust_oof_reference", {})
            ),
            "limitations": list(config.get("limitations", [])),
            "explainability": {
                "enabled": self.settings.explainability_enabled,
                "method": str(
                    explainability.get(
                        "method", "gradient_weighted_patch_attribution"
                    )
                ),
                "target": str(explainability.get("target", "predicted_class")),
                "artifacts_url_prefix": self.settings.artifacts_url_prefix,
            },
        }

    def predict_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str | None,
    ) -> dict[str, Any]:
        image = self._decode_image(data)
        processed = crop_fundus_region(image)
        quality = assess_fundus_image_quality(
            image,
            processed,
            self.settings.quality,
        )

        predictor = self._require_predictor()
        started = time.perf_counter()
        with self._lock:
            result = predictor.predict(image).to_dict()
        latency_ms = (time.perf_counter() - started) * 1000.0

        request_id = str(uuid4())
        quality_payload = self._merge_quality(quality.to_dict(), result)
        return self._prediction_payload(
            request_id=request_id,
            filename=filename,
            content_type=content_type,
            latency_ms=latency_ms,
            result=result,
            quality_payload=quality_payload,
        )

    def predict_with_explanation_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str | None,
    ) -> dict[str, Any]:
        if not self.settings.explainability_enabled or self.artifact_store is None:
            raise RuntimeError("Explainability is disabled in the active API configuration.")

        image = self._decode_image(data)
        processed_for_quality = crop_fundus_region(image)
        quality = assess_fundus_image_quality(
            image,
            processed_for_quality,
            self.settings.quality,
        )

        predictor = self._require_predictor()
        started = time.perf_counter()
        with self._lock:
            try:
                explained = predictor.predict_with_explanation(
                    image,
                    explanation_config=self.settings.explainability,
                )
            finally:
                if self.settings.release_cuda_cache_after_explanation:
                    _release_cuda_cache()
        total_latency_ms = (time.perf_counter() - started) * 1000.0

        result = explained.prediction.to_dict()
        quality_payload = self._merge_quality(quality.to_dict(), result)
        request_id = str(uuid4())
        explanation_warnings = list(explained.attribution.warnings)
        metadata = {
            "request_id": request_id,
            "filename": Path(filename or "upload").name,
            "content_type": content_type,
            "prediction": result,
            "quality": quality_payload,
            "explanation": explained.attribution.metadata(),
        }
        artifacts = self.artifact_store.save(
            request_id=request_id,
            original=explained.original_image,
            processed=explained.processed_image,
            heatmap=explained.attribution.heatmap,
            overlay=explained.attribution.overlay,
            metadata=metadata,
        )

        payload = self._prediction_payload(
            request_id=request_id,
            filename=filename,
            content_type=content_type,
            latency_ms=total_latency_ms,
            result=result,
            quality_payload=quality_payload,
        )
        payload["explanation"] = {
            "method": explained.attribution.method,
            "target_class_index": explained.attribution.target_class_index,
            "target_label": explained.attribution.target_label,
            "latency_ms": round(total_latency_ms, 3),
            "warnings": explanation_warnings,
            "metrics": explained.attribution.metrics,
            "artifacts": artifacts,
            "disclaimer": (
                "The heatmap shows regions that influenced the model output. "
                "It is not a lesion segmentation or independent clinical evidence."
            ),
        }
        return payload

    def _decode_image(self, data: bytes) -> Image.Image:
        if not data:
            raise ValueError("Uploaded image is empty.")
        if len(data) > self.settings.maximum_upload_bytes:
            raise ValueError(
                f"Uploaded image exceeds {self.settings.maximum_upload_bytes} bytes."
            )
        try:
            with Image.open(io.BytesIO(data)) as source:
                image = source.convert("RGB")
                image.load()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError("Uploaded file is not a readable image.") from exc
        return image

    def _merge_quality(
        self,
        quality_payload: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        predictor_warnings = list(result.get("quality", {}).get("warnings", []))
        tta_disagreement = float(result.get("tta", {}).get("absolute_disagreement", 0.0))
        if tta_disagreement > float(
            self.settings.quality.get("maximum_tta_disagreement", 0.15)
        ):
            predictor_warnings.append("high_tta_disagreement")

        quality_payload["warnings"] = list(
            dict.fromkeys(quality_payload["warnings"] + predictor_warnings)
        )
        quality_payload["status"] = (
            "acceptable" if not quality_payload["warnings"] else "review_required"
        )
        return quality_payload

    @staticmethod
    def _prediction_payload(
        *,
        request_id: str,
        filename: str,
        content_type: str | None,
        latency_ms: float,
        result: dict[str, Any],
        quality_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "request_id": request_id,
            "filename": Path(filename or "upload").name,
            "content_type": content_type,
            "latency_ms": round(latency_ms, 3),
            "label": result["label"],
            "probability": result["probability"],
            "threshold": result["threshold"],
            "decision": result["decision"],
            "tta": result["tta"],
            "model_version": result["model_version"],
            "quality": quality_payload,
            "disclaimer": result["disclaimer"],
        }

    def _require_predictor(self) -> Any:
        if self.predictor is None:
            raise RuntimeError("The model has not been loaded.")
        return self.predictor


class _NullLock:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        return False


def _default_predictor_factory(package_dir: Path, device: str | None = None) -> Any:
    from eyeai.inference.run09_predictor import Run09Predictor

    return Run09Predictor(package_dir, device=device)


def _release_cuda_cache() -> None:
    try:
        import torch
    except ImportError:
        return
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except RuntimeError:
            pass
