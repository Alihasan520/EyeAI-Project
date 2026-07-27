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
    metrics = {"fundus_focus_fraction": 0.95, "border_focus_fraction": 0.05}

    def __init__(self):
        self.heatmap = Image.new("RGB", (128, 128), "red")
        self.overlay = Image.new("RGB", (128, 128), (130, 50, 40))

    def metadata(self):
        return {
            "method": self.method,
            "target_class_index": 1,
            "target_label": "AMD",
            "warnings": [],
            "metrics": self.metrics,
        }


class FakePredictor:
    def __init__(self, package_dir, device=None):
        self.device = device or "cpu"
        self.config = {
            "package": {
                "model_version": "retfound-run09-tta-v1",
                "package_name": "test-package",
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
            "validation": {},
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


def _settings(tmp_path: Path) -> ApiSettings:
    package = tmp_path / "package"
    package.mkdir()
    return ApiSettings(
        title="EyeAI Product Test",
        description="Test",
        version="3.0.0",
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
        allowed_methods=("GET", "POST", "PATCH"),
        allowed_headers=("*",),
        quality={},
        explainability_enabled=True,
        explanation_output_dir=tmp_path / "explanations",
        artifacts_url_prefix="/artifacts",
        explainability={"enabled": True, "overlay_alpha": 0.45},
        product_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'product.db'}",
        reports_output_dir=tmp_path / "reports",
        jwt_secret="test-secret-that-is-long-enough-2026",
        jwt_algorithm="HS256",
        access_token_minutes=60,
        bootstrap_enabled=True,
        score_change_threshold=0.20,
        high_score_threshold=0.90,
    )


def _image_bytes() -> bytes:
    image = Image.new("RGB", (768, 768), (130, 50, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_complete_product_workflow(tmp_path):
    app = create_app(_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        bootstrap = client.post(
            "/api/v1/auth/bootstrap",
            json={
                "email": "doctor@example.com",
                "full_name": "Test Doctor",
                "password": "strong-password",
            },
        )
        assert bootstrap.status_code == 200

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "doctor@example.com", "password": "strong-password"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        patient = client.post(
            "/api/v1/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-001",
                "first_name": "Amina",
                "last_name": "Test",
            },
        )
        assert patient.status_code == 201
        patient_id = patient.json()["id"]

        visit = client.post(
            f"/api/v1/patients/{patient_id}/visits",
            headers=headers,
            json={"eye": "right", "notes": "Initial screening"},
        )
        assert visit.status_code == 201
        visit_id = visit.json()["id"]

        prediction = client.post(
            f"/api/v1/visits/{visit_id}/analyze?explanation=true",
            headers=headers,
            files={"file": ("fundus.png", _image_bytes(), "image/png")},
        )
        assert prediction.status_code == 201, prediction.text
        assert prediction.json()["label"] == "AMD"
        assert prediction.json()["explanation"] is not None

        note = client.post(
            f"/api/v1/visits/{visit_id}/notes",
            headers=headers,
            json={"text": "Refer for clinical confirmation."},
        )
        assert note.status_code == 201

        timeline = client.get(
            f"/api/v1/patients/{patient_id}/timeline?eye=right", headers=headers
        )
        assert timeline.status_code == 200
        assert timeline.json()[0]["trend"] == "first_measurement"

        alerts = client.get("/api/v1/alerts", headers=headers)
        assert alerts.status_code == 200
        assert any(item["alert_type"] == "positive_screening_result" for item in alerts.json())

        report = client.post(f"/api/v1/visits/{visit_id}/reports", headers=headers)
        assert report.status_code == 201, report.text
        download = client.get(report.json()["download_url"], headers=headers)
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/pdf"

        dashboard = client.get("/api/v1/dashboard", headers=headers)
        assert dashboard.status_code == 200
        assert dashboard.json()["patients"] == 1
        assert dashboard.json()["predictions"] == 1


def test_product_routes_require_authentication(tmp_path):
    app = create_app(_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        response = client.get("/api/v1/patients")
        assert response.status_code == 401
