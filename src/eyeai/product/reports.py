from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Line, Path as ShapePath, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Flowable,
    Image as PdfImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TEAL = colors.HexColor("#0F9488")
INDIGO = colors.HexColor("#5B5CE2")
NAVY = colors.HexColor("#0B172A")
SLATE = colors.HexColor("#58697A")
PALE = colors.HexColor("#F3F7FB")
PALE_TEAL = colors.HexColor("#E7F7F5")
PALE_INDIGO = colors.HexColor("#EFEEFF")
BORDER = colors.HexColor("#DCE6EE")
SUCCESS = colors.HexColor("#168A5B")
WARNING = colors.HexColor("#B96C00")
DANGER = colors.HexColor("#C83D5A")
WHITE = colors.white


class EyeAILogo(Flowable):
    def __init__(self, width: float = 82 * mm, height: float = 15 * mm) -> None:
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        center_y = self.height / 2
        icon_x = 9 * mm
        canvas.setLineWidth(1.7)
        canvas.setStrokeColor(TEAL)
        canvas.bezier(
            1 * mm,
            center_y,
            5 * mm,
            center_y + 6 * mm,
            13 * mm,
            center_y + 6 * mm,
            17 * mm,
            center_y,
        )
        canvas.bezier(
            1 * mm,
            center_y,
            5 * mm,
            center_y - 6 * mm,
            13 * mm,
            center_y - 6 * mm,
            17 * mm,
            center_y,
        )
        canvas.setFillColor(INDIGO)
        canvas.circle(icon_x, center_y, 2.5 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.circle(icon_x + 0.8 * mm, center_y + 0.8 * mm, 0.7 * mm, fill=1, stroke=0)

        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(22 * mm, center_y + 0.7 * mm, "EyeAI")
        canvas.setFillColor(SLATE)
        canvas.setFont("Helvetica", 7.2)
        canvas.drawString(22.2 * mm, center_y - 3.2 * mm, "CLINICAL INTELLIGENCE PLATFORM")
        canvas.restoreState()


class ScoreGauge(Flowable):
    def __init__(self, score: float, threshold: float, width: float = 150 * mm) -> None:
        super().__init__()
        self.width = width
        self.height = 17 * mm
        self.score = max(0.0, min(1.0, float(score)))
        self.threshold = max(0.0, min(1.0, float(threshold)))

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        bar_y = 7 * mm
        bar_h = 3.2 * mm
        canvas.setFillColor(colors.HexColor("#E6EEF4"))
        canvas.roundRect(0, bar_y, self.width, bar_h, 1.6 * mm, fill=1, stroke=0)
        canvas.setFillColor(PALE_TEAL)
        canvas.roundRect(0, bar_y, self.width * self.threshold, bar_h, 1.6 * mm, fill=1, stroke=0)
        if self.score > self.threshold:
            canvas.setFillColor(colors.HexColor("#F8DCE2"))
            canvas.rect(
                self.width * self.threshold,
                bar_y,
                self.width * (self.score - self.threshold),
                bar_h,
                fill=1,
                stroke=0,
            )
        threshold_x = self.width * self.threshold
        score_x = self.width * self.score
        canvas.setStrokeColor(WARNING)
        canvas.setLineWidth(1.2)
        canvas.line(threshold_x, bar_y - 2 * mm, threshold_x, bar_y + bar_h + 3 * mm)
        canvas.setFillColor(DANGER if self.score >= self.threshold else SUCCESS)
        canvas.circle(score_x, bar_y + bar_h / 2, 2.4 * mm, fill=1, stroke=0)

        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(SLATE)
        canvas.drawString(0, 2 * mm, "0.000")
        canvas.drawRightString(self.width, 2 * mm, "1.000")
        canvas.setFillColor(WARNING)
        canvas.drawCentredString(threshold_x, 12.8 * mm, f"Threshold {self.threshold:.3f}")
        canvas.setFillColor(DANGER if self.score >= self.threshold else SUCCESS)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawCentredString(score_x, 0.5 * mm, f"Score {self.score:.4f}")
        canvas.restoreState()


def generate_visit_report(
    *,
    output_dir: Path,
    patient: Any,
    visit: Any,
    prediction: Any,
    explanation_root: Path,
    report_reference: str,
    doctor_notes: list[Any] | None = None,
    clinical_summary: str | None = None,
    references: list[dict[str, Any]] | None = None,
    clinician_name: str | None = None,
) -> Path:
    """Generate a polished English A4 report for one analyzed eye visit."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report_reference.lower()}-eyeai-report.pdf"
    generated_at = datetime.now(timezone.utc)
    doctor_notes = doctor_notes or []
    references = references or []

    styles = _styles()
    explanation = _json_object(prediction.explanation_json)
    quality = _json_object(prediction.quality_json)
    tta = _json_object(prediction.tta_json)
    metrics = explanation.get("metrics") if isinstance(explanation.get("metrics"), dict) else {}
    artifacts = explanation.get("artifacts") if isinstance(explanation.get("artifacts"), dict) else {}

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=f"{report_reference} EyeAI AMD Screening Report",
        author="EyeAI Clinical Intelligence Platform",
        subject="AI-assisted AMD screening report",
    )

    story: list[Any] = []
    story.append(_header_table(report_reference, visit, prediction, generated_at, styles))
    story.append(Spacer(1, 5 * mm))
    story.append(_section_title("Patient & Visit", "Structured clinical context", styles))
    story.append(_patient_table(patient, visit, clinician_name, styles))
    story.append(Spacer(1, 5 * mm))

    story.append(_section_title("AI-Assisted Screening Result", "RETFound + horizontal-flip TTA", styles))
    story.append(_result_summary(prediction, quality, tta, styles))
    story.append(Spacer(1, 3 * mm))
    story.append(ScoreGauge(prediction.probability, prediction.threshold, width=159 * mm))
    story.append(Spacer(1, 5 * mm))

    image_section = _image_comparison(artifacts, explanation_root, visit, styles)
    if image_section:
        story.append(_section_title("Retinal Image Review", "Original image and model-influence overlay", styles))
        story.extend(image_section)
        story.append(Spacer(1, 5 * mm))

    story.append(_section_title("Heatmap Spatial & Technical Review", "Deterministic metrics calculated from attribution data", styles))
    story.append(_heatmap_table(metrics, explanation, styles))
    story.append(Spacer(1, 4 * mm))
    story.append(
        _notice(
            "The heatmap visualizes regions that influenced the model output. It is not lesion segmentation, anatomical localization, or independent clinical evidence.",
            styles,
            tone="indigo",
        )
    )

    if clinical_summary:
        story.append(Spacer(1, 5 * mm))
        story.append(_section_title("AI-Assisted Clinical Summary", "Grounded synthesis for clinician review", styles))
        story.append(Paragraph(_paragraph_text(clinical_summary), styles["Body"] ))

    if doctor_notes:
        story.append(Spacer(1, 5 * mm))
        story.append(_section_title("Clinician Notes", "Notes stored with the selected visit", styles))
        note_rows: list[list[Any]] = []
        for note in doctor_notes:
            created = _date_text(getattr(note, "created_at", None))
            note_rows.append([
                Paragraph(f"<b>{escape(str(getattr(note, 'display_id', 'Note')))}</b><br/><font color='#7D8C9C'>{escape(created)}</font>", styles["Small"]),
                Paragraph(_paragraph_text(getattr(note, "text", "")), styles["Body"]),
            ])
        note_table = Table(note_rows, colWidths=[34 * mm, 125 * mm], hAlign="LEFT")
        note_table.setStyle(_table_style(first_column_background=True))
        story.append(note_table)

    if references:
        story.append(Spacer(1, 5 * mm))
        story.append(_section_title("Approved Clinical References", "Citation metadata supplied by the RAG backend", styles))
        for index, reference in enumerate(references[:8], start=1):
            number = reference.get("citation_number") or index
            title = reference.get("title") or reference.get("source_id") or "Clinical reference"
            organization = reference.get("organization") or ""
            section = reference.get("section") or ""
            page_number = reference.get("page")
            details = " · ".join(
                item
                for item in [
                    str(organization).strip(),
                    f"Section: {section}" if section else "",
                    f"Page: {page_number}" if page_number not in {None, ""} else "",
                ]
                if item
            )
            story.append(
                KeepTogether(
                    [
                        Paragraph(f"<b>[{escape(str(number))}] {escape(str(title))}</b>", styles["Reference"]),
                        Paragraph(escape(details) if details else "Approved reference metadata", styles["ReferenceMeta"]),
                        Spacer(1, 2.2 * mm),
                    ]
                )
            )

    story.append(Spacer(1, 6 * mm))
    story.append(
        _notice(
            "Clinical safety notice: EyeAI is an AI-assisted screening prototype. The model score is not a disease-severity grade, and the result does not independently confirm AMD subtype, stage, progression, or diagnosis. Clinical examination and confirmatory assessment remain required.",
            styles,
            tone="warning",
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(_signature_table(clinician_name, generated_at, styles))

    document.build(
        story,
        onFirstPage=lambda canvas, doc: _page_footer(canvas, doc, report_reference, prediction.model_version),
        onLaterPages=lambda canvas, doc: _page_footer(canvas, doc, report_reference, prediction.model_version),
    )
    return path


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "EyeAITitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        ),
        "Subtitle": ParagraphStyle(
            "EyeAISubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=SLATE,
        ),
        "Section": ParagraphStyle(
            "EyeAISection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            textColor=NAVY,
        ),
        "SectionMeta": ParagraphStyle(
            "EyeAISectionMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=SLATE,
            alignment=TA_RIGHT,
        ),
        "Body": ParagraphStyle(
            "EyeAIBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=13,
            textColor=NAVY,
            spaceAfter=1.5 * mm,
        ),
        "Small": ParagraphStyle(
            "EyeAISmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=10,
            textColor=SLATE,
        ),
        "Label": ParagraphStyle(
            "EyeAILabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=10,
            textColor=SLATE,
        ),
        "Value": ParagraphStyle(
            "EyeAIValue",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=11,
            textColor=NAVY,
        ),
        "ImageCaption": ParagraphStyle(
            "EyeAIImageCaption",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "Reference": ParagraphStyle(
            "EyeAIReference",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=11,
            textColor=NAVY,
        ),
        "ReferenceMeta": ParagraphStyle(
            "EyeAIReferenceMeta",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.8,
            leading=9,
            textColor=SLATE,
        ),
    }


def _header_table(
    report_reference: str,
    visit: Any,
    prediction: Any,
    generated_at: datetime,
    styles: dict[str, ParagraphStyle],
) -> Table:
    metadata = Table(
        [
            [Paragraph("REPORT ID", styles["Label"]), Paragraph(escape(report_reference), styles["Value"])],
            [Paragraph("VISIT ID", styles["Label"]), Paragraph(escape(str(visit.display_id or visit.id)), styles["Value"])],
            [Paragraph("ANALYSIS ID", styles["Label"]), Paragraph(escape(str(prediction.display_id or prediction.id)), styles["Value"])],
            [Paragraph("GENERATED", styles["Label"]), Paragraph(escape(_date_text(generated_at)), styles["Value"])],
        ],
        colWidths=[25 * mm, 42 * mm],
    )
    metadata.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.35, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    title = [
        EyeAILogo(),
        Spacer(1, 2 * mm),
        Paragraph("AI-Assisted AMD Screening Report", styles["Title"]),
        Paragraph("Retinal fundus screening, explainability, and longitudinal review", styles["Subtitle"]),
    ]
    table = Table([[title, metadata]], colWidths=[93 * mm, 67 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -1), 1.1, TEAL),
            ]
        )
    )
    return table


def _section_title(title: str, meta: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table(
        [[Paragraph(escape(title), styles["Section"]), Paragraph(escape(meta), styles["SectionMeta"])]],
        colWidths=[82 * mm, 78 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("LINEBELOW", (0, 0), (-1, -1), 0.7, BORDER),
            ]
        )
    )
    return table


def _patient_table(patient: Any, visit: Any, clinician_name: str | None, styles: dict[str, ParagraphStyle]) -> Table:
    name = f"{patient.first_name} {patient.last_name}".strip()
    rows = [
        [_label_value("Patient", name, styles), _label_value("Patient ID", patient.display_id or patient.id, styles)],
        [_label_value("Medical Record Number", patient.medical_record_number, styles), _label_value("Date of Birth", _date_only(getattr(patient, "date_of_birth", None)), styles)],
        [_label_value("Sex", getattr(patient, "sex", None) or "Not specified", styles), _label_value("Eye", str(visit.eye).title(), styles)],
        [_label_value("Visit Date", _date_text(visit.visit_date), styles), _label_value("Clinician", clinician_name or "EyeAI authorized clinician", styles)],
    ]
    table = Table(rows, colWidths=[80 * mm, 80 * mm], hAlign="LEFT")
    table.setStyle(_table_style())
    return table


def _result_summary(prediction: Any, quality: dict[str, Any], tta: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    warnings = quality.get("warnings") if isinstance(quality.get("warnings"), list) else []
    disagreement = _number(tta.get("absolute_disagreement"))
    quality_text = prediction.quality_status.replace("_", " ").title()
    warning_text = ", ".join(str(item).replace("_", " ") for item in warnings) if warnings else "No image-quality warning returned"
    rows = [
        [_label_value("Screening Output", prediction.label, styles), _label_value("Decision", "Positive screen" if prediction.decision else "Negative screen", styles)],
        [_label_value("Model Score", f"{prediction.probability:.4f}", styles), _label_value("Decision Threshold", f"{prediction.threshold:.3f}", styles)],
        [_label_value("Technical Review Status", quality_text, styles), _label_value("TTA Disagreement", f"{disagreement:.4f}" if disagreement is not None else "Not available", styles)],
        [_label_value("Image Quality", warning_text, styles), _label_value("Model Version", prediction.model_version, styles)],
    ]
    table = Table(rows, colWidths=[80 * mm, 80 * mm], hAlign="LEFT")
    table.setStyle(_table_style())
    return table


def _image_comparison(
    artifacts: dict[str, Any],
    explanation_root: Path,
    visit: Any,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    cells: list[Any] = []
    for title, key in [("Original Fundus Image", "original"), ("Heatmap Overlay", "overlay")]:
        artifact = artifacts.get(key) if isinstance(artifacts.get(key), dict) else {}
        relative = artifact.get("relative_path")
        if not relative:
            cells.append(Paragraph(f"{title}<br/><font color='#7D8C9C'>Image artifact unavailable</font>", styles["ImageCaption"]))
            continue
        image_path = explanation_root / str(relative)
        if not image_path.is_file():
            cells.append(Paragraph(f"{title}<br/><font color='#7D8C9C'>Image artifact unavailable</font>", styles["ImageCaption"]))
            continue
        image = PdfImage(str(image_path))
        max_width = 75 * mm
        max_height = 52 * mm
        scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
        image.drawWidth = image.imageWidth * scale
        image.drawHeight = image.imageHeight * scale
        image.hAlign = "CENTER"
        cells.append(
            [
                image,
                Spacer(1, 2 * mm),
                Paragraph(f"{escape(title)} · {escape(str(visit.eye).title())} eye", styles["ImageCaption"]),
            ]
        )
    if not cells:
        return []
    table = Table([cells], colWidths=[80 * mm, 80 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFCFE")),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    return [table]


def _heatmap_table(metrics: dict[str, Any], explanation: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    peak = metrics.get("peak") if isinstance(metrics.get("peak"), dict) else {}
    centroid = metrics.get("centroid") if isinstance(metrics.get("centroid"), dict) else {}
    peak_pixel = peak.get("pixel") if isinstance(peak.get("pixel"), dict) else {}
    peak_normalized = peak.get("normalized") if isinstance(peak.get("normalized"), dict) else {}
    centroid_pixel = centroid.get("pixel") if isinstance(centroid.get("pixel"), dict) else {}
    map_similarity = _number(metrics.get("tta_map_similarity"))
    fundus_focus = _number(metrics.get("fundus_focus_fraction"))
    border_focus = _number(metrics.get("border_focus_fraction"))

    peak_xy = _coordinate(peak_pixel)
    normalized_xy = _percentage_coordinate(peak_normalized)
    centroid_xy = _coordinate(centroid_pixel)
    peak_region = peak.get("region") or "Not available"
    centroid_region = centroid.get("region") or "Not available"

    rows = [
        [_label_value("Peak Coordinate", peak_xy, styles), _label_value("Normalized Coordinate", normalized_xy, styles)],
        [_label_value("Peak Region", str(peak_region), styles), _label_value("Centroid", f"{centroid_xy} · {centroid_region}", styles)],
        [_label_value("TTA Heatmap Similarity", _format_number(map_similarity, 4), styles), _label_value("Attribution Inside Fundus", _format_percent(fundus_focus), styles)],
        [_label_value("Border Focus Fraction", _format_percent(border_focus), styles), _label_value("Explanation Target", explanation.get("target_label") or "Not available", styles)],
    ]
    table = Table(rows, colWidths=[80 * mm, 80 * mm], hAlign="LEFT")
    table.setStyle(_table_style())
    return table


def _notice(text: str, styles: dict[str, ParagraphStyle], tone: str) -> Table:
    background = PALE_INDIGO if tone == "indigo" else colors.HexColor("#FFF5E6")
    border_color = INDIGO if tone == "indigo" else WARNING
    table = Table([[Paragraph(_paragraph_text(text), styles["Body"])]], colWidths=[160 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, border_color),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )
    return table


def _signature_table(clinician_name: str | None, generated_at: datetime, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [Paragraph("<b>Clinician review</b><br/><font color='#7D8C9C'>Name / signature</font>", styles["Small"]), Paragraph("<b>Report generated</b><br/><font color='#7D8C9C'>" + escape(_date_text(generated_at)) + "</font>", styles["Small"])],
        [Paragraph(escape(clinician_name or "________________________________"), styles["Value"]), Paragraph("EyeAI Clinical Intelligence Platform", styles["Value"])],
    ]
    table = Table(rows, colWidths=[80 * mm, 80 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )
    return table


def _label_value(label: str, value: Any, styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [
        Paragraph(escape(label.upper()), styles["Label"]),
        Spacer(1, 1.2 * mm),
        Paragraph(_paragraph_text(value if value not in {None, ""} else "Not specified"), styles["Value"]),
    ]


def _table_style(first_column_background: bool = False) -> TableStyle:
    commands: list[tuple[Any, ...]] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFCFE")),
    ]
    if first_column_background:
        commands.append(("BACKGROUND", (0, 0), (0, -1), PALE))
    return TableStyle(commands)


def _page_footer(canvas: Any, document: Any, report_reference: str, model_version: str) -> None:
    canvas.saveState()
    width, _ = A4
    y = 10 * mm
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, y + 4 * mm, width - 18 * mm, y + 4 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(SLATE)
    canvas.drawString(18 * mm, y, "EyeAI Clinical Intelligence · AI-assisted screening prototype")
    canvas.drawCentredString(width / 2, y, f"{report_reference} · {model_version}")
    canvas.drawRightString(width - 18 * mm, y, f"Page {document.page}")
    canvas.restoreState()


def _json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _paragraph_text(value: Any) -> str:
    return escape(str(value)).replace("\n", "<br/>")


def _date_text(value: Any) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%d %b %Y · %H:%M UTC")


def _date_only(value: Any) -> str:
    if value is None:
        return "Not specified"
    return getattr(value, "isoformat", lambda: str(value))()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coordinate(value: dict[str, Any]) -> str:
    x = _number(value.get("x"))
    y = _number(value.get("y"))
    return f"({x:.0f}, {y:.0f})" if x is not None and y is not None else "Not available"


def _percentage_coordinate(value: dict[str, Any]) -> str:
    x = _number(value.get("x"))
    y = _number(value.get("y"))
    return f"({x * 100:.1f}%, {y * 100:.1f}%)" if x is not None and y is not None else "Not available"


def _format_number(value: float | None, digits: int) -> str:
    return f"{value:.{digits}f}" if value is not None else "Not available"


def _format_percent(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "Not available"
