from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from eyeai.api.config import ApiSettings
from eyeai.api.main import create_app


def _settings(tmp_path: Path) -> ApiSettings:
    package = tmp_path / "package"
    package.mkdir()
    return ApiSettings(
        title="EyeAI Frontend Batch 02 Test",
        description="Test",
        version="3.2.0",
        host="127.0.0.1",
        port=8000,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        model_package_dir=package,
        device="cpu",
        preload_model=False,
        inference_lock=True,
        maximum_upload_bytes=1024 * 1024,
        allowed_content_types=("image/png",),
        allowed_suffixes=(".png",),
        allowed_origins=(),
        allow_credentials=True,
        allowed_methods=("GET", "POST", "PATCH"),
        allowed_headers=("*",),
        quality={},
        explainability_enabled=False,
        explanation_output_dir=tmp_path / "explanations",
        artifacts_url_prefix="/artifacts",
        explainability={"enabled": False},
        product_enabled=True,
        database_url=f"sqlite:///{tmp_path / 'product.db'}",
        reports_output_dir=tmp_path / "reports",
        jwt_secret="test-secret-that-is-long-enough-2026",
        jwt_algorithm="HS256",
        access_token_minutes=60,
        bootstrap_enabled=True,
        score_change_threshold=0.20,
        high_score_threshold=0.90,
        assistant_enabled=False,
        assistant_provider="disabled",
        assistant_model_name="disabled",
        rag_enabled=False,
    )


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_account_management_patients_and_visit_timeline(tmp_path: Path):
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        status = client.get("/api/v1/auth/bootstrap-status")
        assert status.status_code == 200
        assert status.json() == {"available": True, "bootstrap_enabled": True}

        bootstrap = client.post(
            "/api/v1/auth/bootstrap",
            json={
                "email": "admin@eyeai.local",
                "full_name": "Initial Administrator",
                "password": "initial-password",
            },
        )
        assert bootstrap.status_code == 200
        assert bootstrap.json()["display_id"] == "USR-000001"

        assert client.get("/api/v1/auth/bootstrap-status").json()["available"] is False
        admin_headers = _login(client, "admin@eyeai.local", "initial-password")

        profile = client.patch(
            "/api/v1/auth/me",
            headers=admin_headers,
            json={"full_name": "Dr. Updated Admin", "email": "updated@eyeai.local"},
        )
        assert profile.status_code == 200
        assert profile.json()["full_name"] == "Dr. Updated Admin"

        wrong_password = client.post(
            "/api/v1/auth/change-password",
            headers=admin_headers,
            json={"current_password": "wrong-password", "new_password": "new-secure-password"},
        )
        assert wrong_password.status_code == 400

        changed = client.post(
            "/api/v1/auth/change-password",
            headers=admin_headers,
            json={"current_password": "initial-password", "new_password": "new-secure-password"},
        )
        assert changed.status_code == 204
        admin_headers = _login(client, "updated@eyeai.local", "new-secure-password")

        clinician = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": "clinician@eyeai.local",
                "full_name": "Dr. Clinical User",
                "password": "clinician-password",
                "role": "clinician",
            },
        )
        assert clinician.status_code == 201
        assert clinician.json()["display_id"] == "USR-000002"

        users = client.get("/api/v1/users", headers=admin_headers)
        assert users.status_code == 200
        assert len(users.json()) == 2

        clinician_headers = _login(client, "clinician@eyeai.local", "clinician-password")
        assert client.get("/api/v1/users", headers=clinician_headers).status_code == 403

        patient = client.post(
            "/api/v1/patients",
            headers=clinician_headers,
            json={
                "medical_record_number": "MRN-0001",
                "first_name": "Demo",
                "last_name": "Patient",
                "sex": "female",
            },
        )
        assert patient.status_code == 201
        patient_ref = patient.json()["display_id"]

        visit = client.post(
            f"/api/v1/patients/{patient_ref}/visits",
            headers=clinician_headers,
            json={"eye": "right", "notes": "Initial right-eye visit."},
        )
        assert visit.status_code == 201

        visits = client.get("/api/v1/visits?eye=right", headers=clinician_headers)
        assert visits.status_code == 200
        assert visits.json()[0]["patient_display_id"] == patient_ref
        assert visits.json()[0]["patient_name"] == "Demo Patient"

        timeline = client.get(
            f"/api/v1/patients/{patient_ref}/timeline?eye=right",
            headers=clinician_headers,
        )
        assert timeline.status_code == 200
        assert len(timeline.json()) == 1
        assert timeline.json()[0]["visit"]["display_id"] == visit.json()["display_id"]

        disabled = client.patch(
            f"/api/v1/users/{clinician.json()['display_id']}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert disabled.status_code == 200
        assert disabled.json()["is_active"] is False
