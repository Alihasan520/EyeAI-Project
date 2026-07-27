from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from eyeai.api.config import ApiSettings
from eyeai.api.main import create_app


class FakeResult:
    def to_dict(self):
        return {
            "label": "AMD",
            "probability": 0.8,
            "threshold": 0.335,
            "decision": True,
            "tta": {
                "original_probability": 0.78,
                "horizontal_flip_probability": 0.82,
                "absolute_disagreement": 0.04,
                "aggregation": "mean_probability",
            },
            "model_version": "retfound-run09-tta-v1",
            "quality": {"warnings": []},
            "disclaimer": "AI-assisted screening output; clinical confirmation is required.",
        }


class FakeAttribution:
    method = "gradient_weighted_patch_attribution"
    target_class_index = 1
    target_label = "AMD"
    warnings = ()
    metrics = {
        "fundus_focus_fraction": 0.95,
        "border_focus_fraction": 0.05,
        "tta_map_similarity": 0.8,
    }

    def __init__(self):
        self.heatmap = Image.new("RGB", (128, 128), "red")
        self.overlay = Image.new("RGB", (128, 128), (130, 50, 40))

    def metadata(self):
        return {
            "method": self.method,
            "target_class_index": self.target_class_index,
            "target_label": self.target_label,
            "warnings": [],
            "metrics": self.metrics,
        }


class FakePredictor:
    def __init__(self, package_dir, device=None):
        self.device = device or "cpu"
        self.config = {
            "package": {
                "model_version": "retfound-run09-tta-v1",
                "package_name": "eyeai_retfound_run09_tta_v1",
                "task": "binary_amd_screening",
            },
            "model": {
                "architecture": "RETFound CFP ViT-Large/16",
                "image_size": 224,
                "class_names": {0: "Non-AMD", 1: "AMD"},
            },
            "inference": {
                "threshold": 0.335,
                "variants": ["original", "hflip"],
                "aggregation": "mean_probability",
            },
            "validation": {
                "fixed_split_tta": {"macro_f1": 0.8138},
                "robust_oof_reference": {"macro_f1": 0.6986},
            },
            "limitations": ["Prototype only."],
        }

    def predict(self, image):
        return FakeResult()

    def predict_with_explanation(self, image, explanation_config=None):
        processed = image.convert("RGB").resize((128, 128))
        return SimpleNamespace(
            prediction=FakeResult(),
            original_image=image.convert("RGB"),
            processed_image=processed,
            attribution=FakeAttribution(),
        )


def _settings(tmp_path: Path, *, explainability: bool = False) -> ApiSettings:
    package = tmp_path / "package"
    package.mkdir()
    return ApiSettings(
        title="Test EyeAI",
        description="Test",
        version="2.0.0" if explainability else "1.0.0",
        host="127.0.0.1",
        port=8000,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        model_package_dir=package,
        device="cpu",
        preload_model=True,
        inference_lock=True,
        maximum_upload_bytes=1024 * 1024,
        allowed_content_types=("image/png",),
        allowed_suffixes=(".png",),
        allowed_origins=(),
        allow_credentials=True,
        allowed_methods=("GET", "POST"),
        allowed_headers=("*",),
        quality={},
        explainability_enabled=explainability,
        explanation_output_dir=tmp_path / "artifacts",
        artifacts_url_prefix="/artifacts",
        explainability={"enabled": explainability, "overlay_alpha": 0.45},
    )


def _png_bytes() -> bytes:
    image = Image.new("RGB", (768, 768), (120, 45, 35))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_and_model_info(tmp_path):
    app = create_app(_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["model_loaded"] is True

        model_info = client.get("/model-info")
        assert model_info.status_code == 200
        assert model_info.json()["threshold"] == 0.335
        assert model_info.json()["explainability"]["enabled"] is False


def test_predict_endpoint(tmp_path):
    app = create_app(_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"file": ("fundus.png", _png_bytes(), "image/png")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["label"] == "AMD"
        assert payload["probability"] == 0.8
        assert payload["quality"]["processable"] is True


def test_predict_with_explanation_and_artifacts(tmp_path):
    app = create_app(
        _settings(tmp_path, explainability=True),
        predictor_factory=FakePredictor,
    )
    with TestClient(app) as client:
        response = client.post(
            "/predict-with-explanation",
            files={"file": ("fundus.png", _png_bytes(), "image/png")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["explanation"]["method"] == "gradient_weighted_patch_attribution"
        assert payload["explanation"]["target_label"] == "AMD"

        for name in ["original", "processed", "heatmap", "overlay", "metadata"]:
            artifact = payload["explanation"]["artifacts"][name]
            artifact_response = client.get(artifact["url"])
            assert artifact_response.status_code == 200
            assert artifact["sha256"]
            assert artifact["size_bytes"] > 0


def test_explanation_endpoint_is_absent_when_disabled(tmp_path):
    app = create_app(_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        response = client.post(
            "/predict-with-explanation",
            files={"file": ("fundus.png", _png_bytes(), "image/png")},
        )
        assert response.status_code == 404


def test_rejects_unsupported_content_type(tmp_path):
    app = create_app(_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"file": ("fundus.txt", b"not an image", "text/plain")},
        )
        assert response.status_code == 415
