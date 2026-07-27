from __future__ import annotations

import re
from typing import Any, Sequence


_ROUTE_TOPICS: dict[str, tuple[str, ...]] = {
    "result_interpretation": (
        "classification",
        "clinical_evaluation",
        "diagnosis",
        "clinical_limitations",
    ),
    "heatmap_location": (
        "clinical_evaluation",
        "diagnostic_testing",
        "clinical_limitations",
    ),
    "timeline_comparison": (
        "monitoring",
        "follow_up",
        "clinical_limitations",
    ),
    "quality_warning": (
        "clinical_evaluation",
        "diagnostic_testing",
        "clinical_limitations",
    ),
    "severity_question": (
        "classification",
        "fundus_features",
        "clinical_limitations",
    ),
    "reference_question": (
        "classification",
        "clinical_evaluation",
        "diagnosis",
        "monitoring",
        "clinical_limitations",
    ),
    "general": (
        "classification",
        "clinical_evaluation",
        "diagnosis",
        "monitoring",
        "clinical_limitations",
    ),
}


def route_question(question: str) -> str:
    text = question.strip().lower()
    if re.search(r"(علاج|دواء|جرعة|حقن|treat|drug|dose|medication|injection)", text):
        return "treatment_question"
    if re.search(r"(heatmap|خريطة|ركز|تركيز|إحداث|احداث|coordinate|where.*focus)", text):
        return "heatmap_location"
    if re.search(r"(شدة|مرحلة|متقدم|مبكر|severity|stage|wet|dry|رطب|جاف)", text):
        return "severity_question"
    if re.search(r"(سابق|تغير|مقارن|زيارة|trend|previous|change|timeline|follow.?up)", text):
        return "timeline_comparison"
    if re.search(r"(جودة|ضباب|وهج|blur|glare|quality|exposure|contrast)", text):
        return "quality_warning"
    if re.search(r"(مرجع|مراجع|مصدر|citation|reference|guideline|aao|nice)", text):
        return "reference_question"
    if re.search(r"(نتيجة|لخص|تفسير|ماذا تعني|result|summary|interpret)", text):
        return "result_interpretation"
    return "general"


def route_topics(route: str) -> tuple[str, ...]:
    return _ROUTE_TOPICS.get(route, _ROUTE_TOPICS["general"])


def heatmap_spatial_summary(metrics: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metrics:
        return None
    required = ("heatmap_width", "heatmap_height", "peak_x_fraction", "peak_y_fraction")
    if any(metrics.get(key) is None for key in required):
        return None

    width = int(metrics["heatmap_width"])
    height = int(metrics["heatmap_height"])
    peak_x_fraction = float(metrics["peak_x_fraction"])
    peak_y_fraction = float(metrics["peak_y_fraction"])
    centroid_x_fraction = float(metrics.get("centroid_x_fraction", peak_x_fraction))
    centroid_y_fraction = float(metrics.get("centroid_y_fraction", peak_y_fraction))
    peak_x = int(metrics.get("peak_x_pixel", round(peak_x_fraction * max(width - 1, 1))))
    peak_y = int(metrics.get("peak_y_pixel", round(peak_y_fraction * max(height - 1, 1))))
    centroid_x = int(
        metrics.get("centroid_x_pixel", round(centroid_x_fraction * max(width - 1, 1)))
    )
    centroid_y = int(
        metrics.get("centroid_y_pixel", round(centroid_y_fraction * max(height - 1, 1)))
    )

    peak_region = str(metrics.get("peak_region") or spatial_region(peak_x_fraction, peak_y_fraction))
    centroid_region = str(
        metrics.get("centroid_region")
        or spatial_region(centroid_x_fraction, centroid_y_fraction)
    )
    dominant_region = str(metrics.get("dominant_region") or centroid_region)

    return {
        "coordinate_system": "processed_image_top_left_origin",
        "image_size": {"width": width, "height": height},
        "peak": {
            "pixel": {"x": peak_x, "y": peak_y},
            "normalized": {
                "x": round(peak_x_fraction, 4),
                "y": round(peak_y_fraction, 4),
            },
            "region": peak_region,
            "region_ar": spatial_region_ar(peak_region),
            "region_en": spatial_region_en(peak_region),
        },
        "centroid": {
            "pixel": {"x": centroid_x, "y": centroid_y},
            "normalized": {
                "x": round(centroid_x_fraction, 4),
                "y": round(centroid_y_fraction, 4),
            },
            "region": centroid_region,
            "region_ar": spatial_region_ar(centroid_region),
            "region_en": spatial_region_en(centroid_region),
        },
        "dominant_region": {
            "region": dominant_region,
            "region_ar": spatial_region_ar(dominant_region),
            "region_en": spatial_region_en(dominant_region),
            "mass_fraction": _optional_float(metrics.get("dominant_region_mass_fraction")),
        },
        "focus_bbox_normalized": {
            "x_min": _optional_float(metrics.get("focus_bbox_x_min_fraction")),
            "y_min": _optional_float(metrics.get("focus_bbox_y_min_fraction")),
            "x_max": _optional_float(metrics.get("focus_bbox_x_max_fraction")),
            "y_max": _optional_float(metrics.get("focus_bbox_y_max_fraction")),
        },
        "tta_map_similarity": _optional_float(metrics.get("tta_map_similarity")),
        "fundus_focus_fraction": _optional_float(metrics.get("fundus_focus_fraction")),
        "border_focus_fraction": _optional_float(metrics.get("border_focus_fraction")),
        "disclaimer": (
            "Coordinates describe model-influence concentration in the processed image; "
            "they do not identify a confirmed lesion or anatomical structure."
        ),
    }


def technical_review_profile(context: dict[str, Any]) -> dict[str, Any]:
    current = context.get("current_visit") or {}
    probability = current.get("probability")
    threshold = current.get("threshold")
    warnings = [str(item) for item in current.get("quality_warnings") or []]
    tta = current.get("tta") or {}
    explanation = current.get("explanation_metrics") or {}

    reasons: list[str] = []
    attention_flags: list[str] = []
    if probability is not None and threshold is not None:
        margin = float(probability) - float(threshold)
        reasons.append(f"Model score margin from threshold: {margin:+.4f}")
    else:
        margin = None
        attention_flags.append("missing_model_result")

    if warnings:
        attention_flags.extend(warnings)
        reasons.append("Image-quality review flags are present.")
    else:
        reasons.append("No image-quality warning is recorded.")

    disagreement = tta.get("absolute_disagreement")
    if disagreement is not None:
        disagreement = float(disagreement)
        reasons.append(f"TTA probability disagreement: {disagreement:.4f}")
        if disagreement >= 0.15:
            attention_flags.append("high_tta_disagreement")

    tta_map_similarity = explanation.get("tta_map_similarity")
    if tta_map_similarity is not None:
        tta_map_similarity = float(tta_map_similarity)
        reasons.append(f"TTA heatmap similarity: {tta_map_similarity:.4f}")
        if tta_map_similarity < 0.15:
            attention_flags.append("low_tta_explanation_consistency")

    fundus_focus = explanation.get("fundus_focus_fraction")
    if fundus_focus is not None:
        fundus_focus = float(fundus_focus)
        reasons.append(f"Heatmap influence inside fundus: {fundus_focus:.4f}")
        if fundus_focus < 0.75:
            attention_flags.append("low_fundus_attribution_focus")

    if attention_flags:
        label = "review_required"
    elif margin is None:
        label = "insufficient_technical_data"
    else:
        label = "technically_consistent"

    return {
        "label": label,
        "reasons": reasons,
        "attention_flags": list(dict.fromkeys(attention_flags)),
        "not_clinical_confidence": True,
    }


def deterministic_clinical_interpretation(context: dict[str, Any]) -> list[str]:
    current = context.get("current_visit") or {}
    items: list[str] = []
    probability = current.get("probability")
    threshold = current.get("threshold")
    prediction = str(current.get("prediction") or "")
    if probability is not None and threshold is not None:
        positive = prediction.upper() == "AMD" or float(probability) >= float(threshold)
        items.append("Positive AMD screening output" if positive else "Negative AMD screening output")
        items.append(
            f"Model score {float(probability):.4f} versus decision threshold {float(threshold):.3f}"
        )
    warnings = current.get("quality_warnings") or []
    if warnings:
        items.append("Image quality requires review: " + ", ".join(map(str, warnings)))
    spatial = context.get("heatmap_spatial")
    if spatial:
        dominant = spatial["dominant_region"]
        items.append(
            "Model influence is concentrated in the processed-image region: "
            f"{dominant['region_en']} ({dominant['region']})"
        )
    else:
        items.append("Heatmap spatial metrics are unavailable for this analysis")
    if context.get("score_change") is None:
        items.append("No prior same-eye model score is available for longitudinal comparison")
    else:
        items.append(
            f"Same-eye model-score change: {float(context['score_change']):+.4f}; "
            "this is not confirmed disease progression"
        )
    items.append("AMD severity and subtype are not determined by this binary model")
    return items


def spatial_region(x_fraction: float, y_fraction: float) -> str:
    horizontal = "left" if x_fraction < 1 / 3 else "center" if x_fraction < 2 / 3 else "right"
    vertical = "upper" if y_fraction < 1 / 3 else "middle" if y_fraction < 2 / 3 else "lower"
    return f"{vertical}-{horizontal}"


def spatial_region_ar(region: str) -> str:
    vertical, _, horizontal = region.partition("-")
    vertical_ar = {"upper": "العلوي", "middle": "الأوسط", "lower": "السفلي"}.get(
        vertical, vertical
    )
    horizontal_ar = {"left": "الأيسر", "center": "الأوسط", "right": "الأيمن"}.get(
        horizontal, horizontal
    )
    return f"الجزء {vertical_ar} {horizontal_ar} من الصورة"


def spatial_region_en(region: str) -> str:
    vertical, _, horizontal = region.partition("-")
    return f"{vertical} {horizontal} portion of the image"


def citation_numbers(references: Sequence[dict[str, Any]]) -> str:
    numbers = [str(item.get("citation_number")) for item in references if item.get("citation_number")]
    return "".join(f"[{number}]" for number in numbers)


def _optional_float(value: Any) -> float | None:
    return round(float(value), 6) if value is not None else None
