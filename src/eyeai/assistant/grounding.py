from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from eyeai.assistant.interpretation import citation_numbers


_ARABIC_WARNING_LABELS = {
    "possible_blur": "احتمال وجود ضبابية في الصورة",
    "possible_glare": "احتمال وجود وهج في الصورة",
    "overexposed_image": "تعريض زائد محتمل",
    "underexposed_image": "إضاءة منخفضة محتملة",
    "low_contrast": "تباين منخفض محتمل",
    "low_resolution": "دقة صورة منخفضة",
    "high_tta_disagreement": "اختلاف مرتفع بين نسختي TTA",
}

_ENGLISH_WARNING_LABELS = {
    "possible_blur": "possible image blur",
    "possible_glare": "possible image glare",
    "overexposed_image": "possible overexposure",
    "underexposed_image": "possible underexposure",
    "low_contrast": "possible low contrast",
    "low_resolution": "low image resolution",
    "high_tta_disagreement": "high disagreement between TTA variants",
}

_TERMINOLOGY_REPLACEMENTS = (
    (r"مرض\s+التهاب\s+الشبكية\s*\(?AMD\)?", "التنكس البقعي المرتبط بالعمر (AMD)"),
    (r"التهاب\s+الشبكية\s*\(?AMD\)?", "التنكس البقعي المرتبط بالعمر (AMD)"),
    (r"التهاب\s+الشبكية", "التنكس البقعي المرتبط بالعمر"),
    (r"تنكس\s+شبكي\s+مرتبط\s+بالعمر", "التنكس البقعي المرتبط بالعمر"),
    (r"مرض\s+الشبكية\s+المتقدم\s*\(?AMD\)?", "التنكس البقعي المرتبط بالعمر (AMD)"),
    (r"age[- ]related macular inflammation", "age-related macular degeneration"),
    (r"AMD inflammation", "age-related macular degeneration (AMD)"),
)

_ALWAYS_UNSAFE_PATTERNS = (
    r"\b(prescribe|prescription|dosage|dose|medication regimen|treatment plan)\b",
    r"\b(confirmed diagnosis|definitive diagnosis|autonomous diagnosis)\b",
    r"\b(confirms?|proves?|demonstrates?)\s+(rapid\s+)?disease progression\b",
    r"\b(early|intermediate|advanced|severe)\s+AMD\b",
    r"\b(wet|dry|neovascular|atrophic)\s+AMD\b",
    r"\b(جرعة|وصفة دوائية|خطة علاج|تشخيص مؤكد|تشخيص نهائي|تأكيد التشخيص)\b",
    r"(?:يؤكد|يثبت|يدل بشكل قاطع على)\s+(?:تقدم|تطور)\s+المرض",
    r"(?:تنكس بقعي|AMD)\s+(?:متقدم|شديد|متوسط|مبكر|رطب|جاف)",
)

_NO_RAG_UNSUPPORTED_PATTERNS = (
    r"\b(family history|environmental factors?|previous treatments?|prior treatments?|other infections?|risk factors?|smoking|supplements?|anti-VEGF|fluorescein|optical coherence tomography|\bOCT\b)\b",
    r"\b(التاريخ العائلي|العوامل البيئية|العلاجات السابقة|التهابات أخرى|عوامل الخطورة|عوامل الخطر|التدخين|المكملات|حقن العين|التصوير المقطعي البصري)\b",
    r"\baccording to (the )?(guideline|literature|evidence|studies)\b",
    r"\bوفقًا (?:للإرشادات|للأدلة|للدراسات|للمراجع)\b",
)

_JSONISH_PATTERNS = (
    r"^\s*\{",
    r'"answer"\s*:',
    r'"suggested_review"\s*:',
    r"```(?:json|yaml)?",
)


@dataclass(frozen=True)
class GroundedAssistantResponse:
    answer: str
    suggested_review: str
    fallback_used: bool
    warnings: tuple[str, ...]
    knowledge_scope: str

    def metadata(self) -> dict[str, Any]:
        return {
            "fallback_used": self.fallback_used,
            "warnings": list(self.warnings),
            "knowledge_scope": self.knowledge_scope,
        }


def ground_assistant_output(
    *,
    answer: str,
    suggested_review: str,
    question: str,
    context: dict[str, Any],
    rag_enabled: bool,
    references: Sequence[Any],
    strict_without_rag: bool = True,
    require_inline_citations: bool = True,
) -> GroundedAssistantResponse:
    """Normalize terminology and replace malformed or unsupported output."""

    del suggested_review
    language_is_arabic = _looks_arabic(question)
    normalized_answer = _canonicalize_terminology(answer.strip())
    normalized_references = [_reference_dict(item, index + 1) for index, item in enumerate(references)]
    warnings = _detect_grounding_violations(
        normalized_answer,
        rag_enabled=rag_enabled,
        references=normalized_references,
    )

    if not normalized_answer:
        warnings.append("empty_answer")
    if _looks_like_structured_output(normalized_answer):
        warnings.append("invalid_structured_output")
    if _looks_truncated(normalized_answer):
        warnings.append("truncated_output")

    if rag_enabled and normalized_references and require_inline_citations:
        valid_markers = {f"[{item['citation_number']}]" for item in normalized_references}
        if not any(marker in normalized_answer for marker in valid_markers):
            warnings.append("missing_inline_citations")
        invented = _invented_citation_numbers(normalized_answer, valid_markers)
        if invented:
            warnings.append("invented_citation_number")

    fallback_required = bool(warnings)
    if strict_without_rag and not rag_enabled:
        fallback_required = fallback_required or _contains_unverifiable_expansion(normalized_answer)
        if fallback_required and "context_only_fallback" not in warnings:
            warnings.append("context_only_fallback")

    if fallback_required:
        normalized_answer = deterministic_context_answer(
            context,
            arabic=language_is_arabic,
            rag_enabled=rag_enabled,
            references=normalized_references,
        )

    review = deterministic_suggested_review(
        arabic=language_is_arabic,
        rag_enabled=rag_enabled,
        references=normalized_references,
    )
    scope = (
        "patient_context_and_approved_rag"
        if rag_enabled and normalized_references
        else "patient_context_only"
    )
    return GroundedAssistantResponse(
        answer=normalized_answer,
        suggested_review=review,
        fallback_used=fallback_required,
        warnings=tuple(dict.fromkeys(warnings)),
        knowledge_scope=scope,
    )


def deterministic_context_answer(
    context: dict[str, Any],
    *,
    arabic: bool,
    rag_enabled: bool,
    references: Sequence[dict[str, Any]] | None = None,
) -> str:
    references = list(references or [])
    current = context.get("current_visit") or {}
    eye = str(context.get("selected_eye") or "unspecified")
    probability = current.get("probability")
    threshold = current.get("threshold")
    prediction = str(current.get("prediction") or "")
    visit_date = current.get("date")
    warnings = [str(item) for item in current.get("quality_warnings") or []]
    score_change = context.get("score_change")
    spatial = context.get("heatmap_spatial")

    if arabic:
        eye_label = {"right": "اليمنى", "left": "اليسرى"}.get(eye, eye)
        sentences = [f"هذا ملخص لسجل EyeAI المتاح للعين {eye_label} فقط."]
        if visit_date:
            sentences.append(f"تاريخ الزيارة الحالية هو {visit_date}.")
        if probability is not None and threshold is not None:
            positive = prediction.upper() == "AMD" or float(probability) >= float(threshold)
            decision_text = "إيجابية" if positive else "سلبية"
            sentences.append(
                "أعطى نموذج EyeAI نتيجة فحص "
                f"{decision_text} تخص التنكس البقعي المرتبط بالعمر (AMD)، "
                f"بدرجة نموذج {float(probability):.4f} مقارنة بعتبة قرار {float(threshold):.3f}."
            )
        elif probability is not None:
            sentences.append(f"درجة نموذج AMD الحالية هي {float(probability):.4f}.")
        else:
            sentences.append("لا توجد نتيجة تحليل صورة محفوظة لهذه الزيارة.")

        if warnings:
            labels = [_ARABIC_WARNING_LABELS.get(item, item) for item in warnings]
            sentences.append("تحذيرات جودة الصورة المسجلة: " + "، ".join(labels) + ".")
        else:
            sentences.append("لا توجد تحذيرات جودة صورة مسجلة في النتيجة الحالية.")

        if spatial:
            peak = spatial["peak"]
            centroid = spatial["centroid"]
            sentences.append(
                "بلغت ذروة تأثير الخريطة عند الإحداثيات "
                f"({peak['pixel']['x']}, {peak['pixel']['y']}) على صورة معالجة بحجم "
                f"{spatial['image_size']['width']}×{spatial['image_size']['height']}، "
                f"أي في {peak['region_ar']}. وكان مركز كتلة التأثير في {centroid['region_ar']}. "
                "هذه الإحداثيات تصف تأثير المودل ولا تحدد آفة أو بنية تشريحية مؤكدة."
            )
        else:
            sentences.append("لا تتوفر قياسات مكانية محفوظة لخريطة التأثير في هذا التحليل.")

        if score_change is None:
            sentences.append(
                "لا توجد نتيجة سابقة قابلة للمقارنة للعين نفسها، لذلك لا يمكن حساب تغير زمني في درجة النموذج."
            )
        else:
            sentences.append(
                f"التغير عن آخر نتيجة محفوظة للعين نفسها هو {float(score_change):+.4f}. "
                "هذا تغير في درجة النموذج ولا يثبت تقدم المرض."
            )

        if rag_enabled and references:
            markers = citation_numbers(references)
            sentences.append(
                "توضح المقاطع المعتمدة المسترجعة أن التقييم السريري والتصنيف يعتمدان على "
                f"مراجعة العلامات البقعية والفحوص المناسبة، ولا تكفي درجة تصنيف ثنائي وحدها لتحديد المرحلة أو النوع {markers}."
            )
        else:
            sentences.append("لم تُستخدم مراجع RAG معتمدة في هذا الرد.")
        sentences.append("النتيجة أداة مساعدة للفحص ولا تمثل تشخيصًا سريريًا مستقلاً.")
        return " ".join(sentences)

    sentences = [f"This summary uses only the available EyeAI record for the {eye} eye."]
    if visit_date:
        sentences.append(f"The current visit date is {visit_date}.")
    if probability is not None and threshold is not None:
        positive = prediction.upper() == "AMD" or float(probability) >= float(threshold)
        decision_text = "positive" if positive else "negative"
        sentences.append(
            "EyeAI produced a "
            f"{decision_text} screening output for age-related macular degeneration (AMD), "
            f"with a model score of {float(probability):.4f} and a decision threshold of {float(threshold):.3f}."
        )
    elif probability is not None:
        sentences.append(f"The current AMD model score is {float(probability):.4f}.")
    else:
        sentences.append("No stored image-analysis result is available for this visit.")

    if warnings:
        labels = [_ENGLISH_WARNING_LABELS.get(item, item) for item in warnings]
        sentences.append("Recorded image-quality warnings: " + ", ".join(labels) + ".")
    else:
        sentences.append("No image-quality warnings are recorded for the current result.")

    if spatial:
        peak = spatial["peak"]
        centroid = spatial["centroid"]
        sentences.append(
            "The heatmap peak is at "
            f"({peak['pixel']['x']}, {peak['pixel']['y']}) on the "
            f"{spatial['image_size']['width']}x{spatial['image_size']['height']} processed image, "
            f"in the {peak['region_en']}. The attribution centroid is in the {centroid['region_en']}. "
            "These coordinates describe model influence and do not localize a confirmed lesion or anatomical structure."
        )
    else:
        sentences.append("No stored spatial heatmap metrics are available for this analysis.")

    if score_change is None:
        sentences.append(
            "No comparable prior result is available for the same eye, so a longitudinal model-score change cannot be calculated."
        )
    else:
        sentences.append(
            f"The change from the previous stored score for the same eye is {float(score_change):+.4f}. "
            "This is a model-score change and does not establish disease progression."
        )

    if rag_enabled and references:
        markers = citation_numbers(references)
        sentences.append(
            "The retrieved approved excerpts indicate that clinical evaluation and classification require review of macular findings and appropriate testing; a binary model score alone does not determine stage or subtype "
            f"{markers}."
        )
    else:
        sentences.append("No approved RAG references were used in this response.")
    sentences.append(
        "The output is an AI-assisted screening result and is not an autonomous clinical diagnosis."
    )
    return " ".join(sentences)


def deterministic_suggested_review(
    *,
    arabic: bool,
    rag_enabled: bool,
    references: Sequence[dict[str, Any]] | None = None,
) -> str:
    references = list(references or [])
    markers = citation_numbers(references)
    if arabic:
        text = (
            "راجع جودة صورة قاع العين ونتيجة المودل والعلامات البقعية مع اختصاصي العيون، "
            "واستخدم تقييمًا سريريًا تأكيديًا قبل أي قرار طبي."
        )
        if rag_enabled and references:
            text += f" تستند هذه الخطوة العامة إلى المقاطع المعتمدة المسترجعة {markers}."
        else:
            text += " لم تُستخدم مراجع RAG معتمدة في هذا التشغيل."
        return text
    text = (
        "Review the fundus image quality, model output, and macular findings with an ophthalmologist, "
        "and use confirmatory clinical assessment before any medical decision."
    )
    if rag_enabled and references:
        text += f" This general review step is supported by the retrieved approved excerpts {markers}."
    else:
        text += " No approved RAG references were used in this run."
    return text


def _canonicalize_terminology(text: str) -> str:
    normalized = text
    for pattern, replacement in _TERMINOLOGY_REPLACEMENTS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def _detect_grounding_violations(
    text: str,
    *,
    rag_enabled: bool,
    references: Sequence[Any],
) -> list[str]:
    violations: list[str] = []
    for pattern in _ALWAYS_UNSAFE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            violations.append("unsafe_or_unsupported_clinical_claim")
            break

    if not rag_enabled or not references:
        for pattern in _NO_RAG_UNSUPPORTED_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                violations.append("unsupported_external_medical_claim_without_rag")
                break
    return violations


def _contains_unverifiable_expansion(text: str) -> bool:
    patterns = (
        r"(?:يُنصح|يوصى|يجب)\s+(?:بفحص|بإجراء|بمراجعة)\s+(?:التاريخ|العوامل|العلاجات|الالتهابات)",
        r"(?:consider|assess|review)\s+(?:family history|risk factors|prior treatment|other infection)",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _looks_like_structured_output(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) for pattern in _JSONISH_PATTERNS)


def _looks_truncated(text: str) -> bool:
    if not text:
        return True
    stripped = text.rstrip()
    if stripped.count("{") != stripped.count("}") or stripped.count('"') % 2:
        return True
    return stripped.endswith(("\\", ":", "\"", "'", "، و", " and"))


def _invented_citation_numbers(text: str, valid_markers: set[str]) -> set[str]:
    found = set(re.findall(r"\[\d+\]", text))
    return found - valid_markers


def _reference_dict(item: Any, default_number: int) -> dict[str, Any]:
    if isinstance(item, dict):
        payload = dict(item)
    elif hasattr(item, "citation_payload"):
        payload = dict(item.citation_payload())
    else:
        payload = {"title": str(item)}
    payload.setdefault("citation_number", default_number)
    return payload


def _looks_arabic(text: str) -> bool:
    return any("\u0600" <= character <= "\u06ff" for character in text)
