from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from eyeai.product.reports import generate_visit_report
from eyeai.product.schemas import ReportCreateRequest, ReportListItem, ReportResponse


def _image(path: Path, *, overlay: bool) -> None:
    image = Image.new("RGB", (640, 640), (4, 10, 18))
    draw = ImageDraw.Draw(image)
    draw.ellipse((45, 45, 595, 595), fill=(128, 62, 38), outline=(232, 161, 98), width=6)
    if overlay:
        draw.ellipse((300, 270, 490, 460), outline=(255, 40, 40), width=22)
        draw.ellipse((330, 300, 460, 430), outline=(255, 210, 40), width=18)
    image.save(path)


def test_report_request_and_list_schema() -> None:
    request = ReportCreateRequest(
        clinical_summary="Clinician-facing summary.",
        references=[{"source_id": "NICE_NG82", "page": 5}],
    )
    assert request.references[0]["source_id"] == "NICE_NG82"

    report = ReportResponse(
        id="report-id",
        display_id="REP-20260726-000001",
        patient_id="patient-id",
        visit_id="visit-id",
        prediction_id="prediction-id",
        download_url="/api/v1/reports/REP-20260726-000001/download",
        created_at=datetime.now(timezone.utc),
    )
    item = ReportListItem(
        report=report,
        patient_display_id="PAT-000001",
        patient_name="Demo Patient",
        visit_display_id="VIS-20260726-000001",
        eye="right",
        visit_date=datetime.now(timezone.utc),
    )
    assert item.eye == "right"


def test_professional_report_contains_images_and_metadata(tmp_path: Path) -> None:
    explanation_root = tmp_path / "explanations"
    artifact_dir = explanation_root / "case"
    artifact_dir.mkdir(parents=True)
    _image(artifact_dir / "original.png", overlay=False)
    _image(artifact_dir / "overlay.png", overlay=True)

    patient = SimpleNamespace(
        id="patient-id",
        display_id="PAT-000001",
        medical_record_number="MRN-1024",
        first_name="Demo",
        last_name="Patient",
        date_of_birth=date(1958, 4, 16),
        sex="female",
    )
    visit = SimpleNamespace(
        id="visit-id",
        display_id="VIS-20260726-000001",
        eye="right",
        visit_date=datetime.now(timezone.utc),
    )
    explanation = {
        "artifacts": {
            "original": {"relative_path": "case/original.png"},
            "overlay": {"relative_path": "case/overlay.png"},
        },
        "metrics": {
            "peak": {
                "pixel": {"x": 320, "y": 355},
                "normalized": {"x": 0.50, "y": 0.55},
                "region": "middle-center",
            },
            "centroid": {"pixel": {"x": 315, "y": 350}, "region": "middle-center"},
            "tta_map_similarity": 0.9632,
            "fundus_focus_fraction": 0.8653,
            "border_focus_fraction": 0.1433,
        },
        "target_label": "AMD",
    }
    prediction = SimpleNamespace(
        id="prediction-id",
        display_id="ANA-20260726-000001",
        label="AMD",
        probability=0.8009,
        threshold=0.335,
        decision=True,
        model_version="retfound-run09-tta-v1",
        quality_status="review_required",
        quality_json=json.dumps({"warnings": ["possible_blur"]}),
        tta_json=json.dumps({"absolute_disagreement": 0.018}),
        explanation_json=json.dumps(explanation),
    )
    notes = [
        SimpleNamespace(
            display_id="NTE-20260726-000001",
            created_at=datetime.now(timezone.utc),
            text="Review image quality before final interpretation.",
        )
    ]

    report_path = generate_visit_report(
        output_dir=tmp_path / "reports",
        patient=patient,
        visit=visit,
        prediction=prediction,
        explanation_root=explanation_root,
        report_reference="REP-20260726-000001",
        doctor_notes=notes,
        clinical_summary=(
            "The current screening output supports clinician review but does not "
            "determine AMD stage or subtype."
        ),
        references=[
            {
                "citation_number": 1,
                "source_id": "AAO_AMD_PPP",
                "title": "Age-Related Macular Degeneration Preferred Practice Pattern",
                "organization": "American Academy of Ophthalmology",
                "section": "Clinical Evaluation",
                "page": 57,
            }
        ],
        clinician_name="Dr. EyeAI",
    )

    payload = report_path.read_bytes()
    assert payload.startswith(b"%PDF")
    assert len(payload) > 10_000
    assert report_path.name == "rep-20260726-000001-eyeai-report.pdf"
