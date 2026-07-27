from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from eyeai.api.config import ApiSettings
from eyeai.api.main import create_app
from eyeai.assistant.provider import MockProvider
from eyeai.assistant.rag import RetrievedReference


class FakeResult:
    def to_dict(self):
        return {
            "label": "AMD",
            "probability": 0.72,
            "threshold": 0.335,
            "decision": True,
            "tta": {
                "original_probability": 0.70,
                "horizontal_flip_probability": 0.74,
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
        "tta_map_similarity": 0.82,
        "heatmap_width": 128,
        "heatmap_height": 128,
        "peak_x_pixel": 70,
        "peak_y_pixel": 80,
        "peak_x_fraction": 70 / 127,
        "peak_y_fraction": 80 / 127,
        "centroid_x_pixel": 64,
        "centroid_y_pixel": 70,
        "centroid_x_fraction": 64 / 127,
        "centroid_y_fraction": 70 / 127,
        "dominant_region": "middle-center",
        "dominant_region_mass_fraction": 0.41,
    }

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
        return SimpleNamespace(
            prediction=FakeResult(),
            original_image=image.convert("RGB"),
            processed_image=image.convert("RGB").resize((128, 128)),
            attribution=FakeAttribution(),
        )


class FakeRag:
    enabled = True
    loaded = True

    def search(self, query, top_k=None, **kwargs):
        return [
            RetrievedReference(
                chunk_id="guide-0001",
                document_id="guide",
                title="Approved AMD Guide",
                source_path="guidelines/amd.md",
                page=4,
                section="Clinical review",
                text="Model outputs require clinical review.",
                score=0.91,
            )
        ]


def _settings(tmp_path: Path, *, rag_enabled: bool = True) -> ApiSettings:
    package = tmp_path / "package"
    package.mkdir()
    return ApiSettings(
        title="EyeAI V1.1 Test",
        description="Test",
        version="3.1.0",
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
        assistant_enabled=True,
        assistant_provider="mock",
        assistant_model_name="mock-qwen",
        rag_enabled=rag_enabled,
    )


def _image_bytes() -> bytes:
    image = Image.new("RGB", (768, 768), (130, 50, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _login(client: TestClient) -> dict[str, str]:
    bootstrap = client.post(
        "/api/v1/auth/bootstrap",
        json={
            "email": "doctor@example.com",
            "full_name": "Test Doctor",
            "password": "strong-password",
        },
    )
    assert bootstrap.status_code == 200
    assert bootstrap.json()["display_id"] == "USR-000001"
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@example.com", "password": "strong-password"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_readable_references_and_context_aware_assistant(tmp_path):
    provider = MockProvider(
        {
            "answer": "The right-eye model score is positive and needs clinical review.",
            "suggested_review": "Compare the image with clinical findings.",
        }
    )
    app = create_app(
        _settings(tmp_path),
        predictor_factory=FakePredictor,
        assistant_provider_factory=lambda settings, lock: provider,
        rag_index_factory=lambda settings: FakeRag(),
    )
    with TestClient(app) as client:
        headers = _login(client)
        patient = client.post(
            "/api/v1/patients",
            headers=headers,
            json={
                "medical_record_number": "SECRET-MRN-001",
                "first_name": "Amina",
                "last_name": "Private",
                "phone": "+000000000",
            },
        ).json()
        assert patient["display_id"] == "PAT-000001"

        visit_response = client.post(
            f"/api/v1/patients/{patient['display_id']}/visits",
            headers=headers,
            json={"eye": "right"},
        )
        assert visit_response.status_code == 201
        visit = visit_response.json()
        assert visit["display_id"].startswith("VIS-")

        prediction = client.post(
            f"/api/v1/visits/{visit['display_id']}/analyze?explanation=true",
            headers=headers,
            files={"file": ("fundus.png", _image_bytes(), "image/png")},
        )
        assert prediction.status_code == 201
        assert prediction.json()["display_id"].startswith("ANA-")

        note_response = client.post(
            f"/api/v1/visits/{visit['display_id']}/notes",
            headers=headers,
            json={"text": "Amina Private has record SECRET-MRN-001 and phone +000000000."},
        )
        assert note_response.status_code == 201

        conversation_response = client.post(
            f"/api/v1/patients/{patient['display_id']}/assistant/conversations",
            headers=headers,
            json={"eye": "right", "visit_id": visit["display_id"]},
        )
        assert conversation_response.status_code == 201
        conversation = conversation_response.json()
        assert conversation["display_id"] == "CHT-000001"

        turn = client.post(
            f"/api/v1/assistant/conversations/{conversation['display_id']}/messages",
            headers=headers,
            json={"content": "هل تلخص نتيجة Amina الحالية؟"},
        )
        assert turn.status_code == 201, turn.text
        result = turn.json()["result"]
        assert result["references"][0]["title"] == "Approved AMD Guide"
        assert "excerpt" not in result["references"][0]
        assert result["heatmap_spatial"]["peak"]["pixel"] == {"x": 70, "y": 80}
        assert result["technical_review_profile"]["label"] in {
            "technically_consistent", "review_required"
        }
        assert "[1]" in result["answer"]
        assert result["limitations"]
        prompt = "\n".join(message["content"] for message in provider.last_messages)
        assert "Amina" not in prompt
        assert "Private" not in prompt
        assert "SECRET-MRN-001" not in prompt
        assert "+000000000" not in prompt
        assert "right" in prompt


def test_rag_can_be_disabled_and_treatment_question_is_refused(tmp_path):
    provider = MockProvider()
    app = create_app(
        _settings(tmp_path, rag_enabled=False),
        predictor_factory=FakePredictor,
        assistant_provider_factory=lambda settings, lock: provider,
    )
    with TestClient(app) as client:
        headers = _login(client)
        patient = client.post(
            "/api/v1/patients",
            headers=headers,
            json={
                "medical_record_number": "MRN-002",
                "first_name": "Demo",
                "last_name": "Patient",
            },
        ).json()
        conversation = client.post(
            f"/api/v1/patients/{patient['display_id']}/assistant/conversations",
            headers=headers,
            json={"eye": "left"},
        ).json()
        turn = client.post(
            f"/api/v1/assistant/conversations/{conversation['display_id']}/messages",
            headers=headers,
            json={"content": "ما جرعة الدواء التي يجب وصفها؟"},
        )
        assert turn.status_code == 201
        assert turn.json()["result"]["references"] == []
        assert "لا يستطيع" in turn.json()["result"]["answer"]
        assert provider.last_messages == []
