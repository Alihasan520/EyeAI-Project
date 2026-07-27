from __future__ import annotations

from pathlib import Path

from eyeai.api.config import ApiSettings
from eyeai.assistant.grounding import ground_assistant_output


def _context() -> dict:
    return {
        "selected_eye": "right",
        "current_visit": {
            "date": "2026-07-24",
            "eye": "right",
            "prediction": "AMD",
            "probability": 0.8008884191513062,
            "threshold": 0.335,
            "quality_warnings": ["possible_blur"],
        },
        "previous_same_eye_visits": [],
        "score_change": None,
    }


def test_unsupported_arabic_expansion_falls_back_to_context_only_answer():
    grounded = ground_assistant_output(
        answer=(
            "النتيجة تشير إلى مرض التهاب الشبكية (AMD). "
            "يجب مراجعة التاريخ العائلي والعوامل البيئية والعلاجات السابقة."
        ),
        suggested_review="راجع التهابات أخرى.",
        question="لخص النتيجة الحالية.",
        context=_context(),
        rag_enabled=False,
        references=[],
        strict_without_rag=True,
    )

    assert grounded.fallback_used is True
    assert grounded.knowledge_scope == "patient_context_only"
    assert "التنكس البقعي المرتبط بالعمر" in grounded.answer
    assert "التهاب الشبكية" not in grounded.answer
    assert "التاريخ العائلي" not in grounded.answer
    assert "العوامل البيئية" not in grounded.answer
    assert "العلاجات السابقة" not in grounded.answer
    assert "0.8009" in grounded.answer
    assert "0.335" in grounded.answer
    assert "لم تُستخدم مراجع RAG" in grounded.answer


def test_clean_context_only_answer_is_kept_and_review_is_deterministic():
    grounded = ground_assistant_output(
        answer=(
            "تعرض سجلات EyeAI نتيجة فحص إيجابية تخص التنكس البقعي المرتبط بالعمر "
            "بدرجة نموذج 0.8009، ولا توجد زيارة سابقة للعين نفسها."
        ),
        suggested_review="نص حر غير معتمد.",
        question="ما ملخص النتيجة؟",
        context=_context(),
        rag_enabled=False,
        references=[],
        strict_without_rag=True,
    )

    assert grounded.fallback_used is False
    assert "التنكس البقعي المرتبط بالعمر" in grounded.answer
    assert "اختصاصي العيون" in grounded.suggested_review
    assert "لم تُستخدم مراجع RAG" in grounded.suggested_review


def test_v111_resource_defaults_are_conservative(tmp_path: Path):
    package = tmp_path / "package"
    package.mkdir()
    config_path = tmp_path / "api.yaml"
    config_path.write_text(
        f"""
api:
  version: 3.1.1
runtime:
  model_package_dir: {package.as_posix()}
assistant:
  enabled: true
  provider: mock
rag:
  enabled: false
""",
        encoding="utf-8",
    )

    settings = ApiSettings.from_yaml(config_path)
    assert settings.assistant_maximum_gpu_memory_gib == 5
    assert settings.assistant_maximum_input_tokens == 3072
    assert settings.assistant_maximum_new_tokens == 256
    assert settings.assistant_temperature == 0.0
    assert settings.assistant_maximum_history_messages == 4
    assert settings.assistant_maximum_notes_characters == 1600
    assert settings.assistant_release_cuda_cache_after_generate is True
    assert settings.assistant_strict_without_rag is True
    assert settings.release_cuda_cache_after_explanation is True
