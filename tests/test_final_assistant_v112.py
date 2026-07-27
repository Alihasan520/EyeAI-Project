from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
import torch

from eyeai.assistant.grounding import ground_assistant_output
from eyeai.assistant.ingestion import (
    audit_manifest_documents,
    chunk_manifest_documents,
    load_reference_manifest,
)
from eyeai.assistant.interpretation import heatmap_spatial_summary, route_question
from eyeai.inference.explainability import build_gradient_weighted_patch_attribution


def _context_with_heatmap() -> dict:
    metrics = {
        "heatmap_width": 224,
        "heatmap_height": 224,
        "peak_x_pixel": 119,
        "peak_y_pixel": 141,
        "peak_x_fraction": 119 / 223,
        "peak_y_fraction": 141 / 223,
        "centroid_x_pixel": 111,
        "centroid_y_pixel": 126,
        "centroid_x_fraction": 111 / 223,
        "centroid_y_fraction": 126 / 223,
        "dominant_region": "middle-center",
        "dominant_region_mass_fraction": 0.42,
        "tta_map_similarity": 0.84,
        "fundus_focus_fraction": 0.93,
        "border_focus_fraction": 0.04,
    }
    return {
        "selected_eye": "right",
        "current_visit": {
            "date": "2026-07-25",
            "prediction": "AMD",
            "probability": 0.8009,
            "threshold": 0.335,
            "quality_warnings": ["possible_blur"],
            "explanation_metrics": metrics,
        },
        "previous_same_eye_visits": [],
        "score_change": None,
        "heatmap_spatial": heatmap_spatial_summary(metrics),
    }


def test_truncated_json_output_never_reaches_user():
    grounded = ground_assistant_output(
        answer='{"answer": "نتيجة الفحص إيجابية", "suggested_review": "ي',
        suggested_review="",
        question="لخص نتيجة العين اليمنى.",
        context=_context_with_heatmap(),
        rag_enabled=False,
        references=[],
    )
    assert grounded.fallback_used is True
    assert "invalid_structured_output" in grounded.warnings
    assert not grounded.answer.lstrip().startswith("{")
    assert '"answer"' not in grounded.answer
    assert "التنكس البقعي المرتبط بالعمر" in grounded.answer
    assert "(119, 141)" in grounded.answer
    assert "الجزء الأوسط الأوسط" in grounded.answer


def test_reference_grounded_plain_text_keeps_inline_citations():
    references = [
        {"citation_number": 1, "title": "AAO AMD PPP", "section": "Clinical Evaluation"},
        {"citation_number": 2, "title": "NICE NG82", "section": "Diagnosis"},
    ]
    answer = (
        "تعطي النتيجة فحصًا إيجابيًا للتنكس البقعي المرتبط بالعمر. "
        "تتطلب المراجعة السريرية تقييم العلامات البقعية ولا تكفي درجة ثنائية لتحديد المرحلة [1][2]."
    )
    grounded = ground_assistant_output(
        answer=answer,
        suggested_review="",
        question="فسر النتيجة مع المراجع.",
        context=_context_with_heatmap(),
        rag_enabled=True,
        references=references,
    )
    assert grounded.fallback_used is False
    assert grounded.knowledge_scope == "patient_context_and_approved_rag"
    assert "[1][2]" in grounded.answer
    assert "[1][2]" in grounded.suggested_review


def test_gradient_attribution_contains_deterministic_spatial_metrics():
    activation = torch.zeros((2, 197, 4), dtype=torch.float32)
    gradient = torch.zeros_like(activation)
    # Strong activation in a patch near the lower centre.
    patch_index = 14 * 9 + 7
    activation[:, 1 + patch_index, :] = 2.0
    gradient[:, 1 + patch_index, :] = 1.0
    image = Image.new("RGB", (224, 224), (80, 40, 30))
    result = build_gradient_weighted_patch_attribution(
        activation=activation,
        gradient=gradient,
        grid_size=(14, 14),
        variants=("original", "hflip"),
        processed_image=image,
        target_class_index=1,
        target_label="AMD",
    )
    metrics = result.metrics
    for key in (
        "peak_x_pixel",
        "peak_y_pixel",
        "centroid_x_fraction",
        "centroid_y_fraction",
        "dominant_region",
        "focus_bbox_x_min_fraction",
        "focus_bbox_y_max_fraction",
    ):
        assert key in metrics
    assert metrics["heatmap_width"] == 224
    assert metrics["heatmap_height"] == 224


def test_reference_manifest_audit_and_chunking_select_allowed_content(tmp_path: Path):
    documents = tmp_path / "source_documents"
    documents.mkdir()
    (documents / "NICE_NG82_AMD.txt").write_text(
        "Diagnosis and referral\nAMD screening requires structured clinical assessment.\n" * 30,
        encoding="utf-8",
    )
    manifest = tmp_path / "reference_manifest.yaml"
    manifest.write_text(
        """
version: '1.0'
references:
  - source_id: NICE_NG82
    title: NICE AMD
    organization: NICE
    required: true
    file_name_patterns: ['(?i).*NICE_NG82_AMD.*']
    allowed_topics: [diagnosis, referral]
    include_page_ranges: []
    include_heading_patterns: ['(?i)diagnosis', '(?i)referral']
    exclude_heading_patterns: ['(?i)^treatment']
""",
        encoding="utf-8",
    )
    specs = load_reference_manifest(manifest)
    audit, matched = audit_manifest_documents(
        documents_root=documents,
        reference_specs=specs,
    )
    assert len(audit) == 1
    assert audit[0].selected is True
    chunks = chunk_manifest_documents(
        documents_root=documents,
        reference_specs=specs,
        audit_records=audit,
        matched_files=matched,
        chunk_characters=300,
        overlap_characters=40,
    )
    assert chunks
    assert all(chunk.source_id == "NICE_NG82" for chunk in chunks)
    assert all("diagnosis" in chunk.allowed_topics for chunk in chunks)


def test_question_router_is_deterministic():
    assert route_question("أين ركزت خريطة الحرارة؟") == "heatmap_location"
    assert route_question("هل الحالة متقدمة؟") == "severity_question"
    assert route_question("قارن مع الزيارة السابقة") == "timeline_comparison"
