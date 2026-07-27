from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str | None = None
    device: str | None = None


class ModelInfoResponse(BaseModel):
    model_version: str
    package_name: str
    architecture: str
    task: str
    image_size: int
    threshold: float
    variants: list[str]
    aggregation: str
    class_names: dict[str, str]
    device: str
    fixed_split_metrics: dict[str, Any]
    robust_oof_reference: dict[str, Any]
    limitations: list[str]
    explainability: dict[str, Any] = Field(default_factory=dict)


class TtaResponse(BaseModel):
    original_probability: float
    horizontal_flip_probability: float
    absolute_disagreement: float
    aggregation: str


class QualityResponse(BaseModel):
    processable: bool
    status: str
    warnings: list[str]
    metrics: dict[str, float | int]


class PredictionResponse(BaseModel):
    request_id: str
    filename: str
    content_type: str | None
    latency_ms: float = Field(ge=0)
    label: str
    probability: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    decision: bool
    tta: TtaResponse
    model_version: str
    quality: QualityResponse
    disclaimer: str


class ArtifactFileResponse(BaseModel):
    url: str
    relative_path: str
    sha256: str
    size_bytes: int = Field(ge=0)


class ExplanationResponse(BaseModel):
    method: str
    target_class_index: int
    target_label: str
    latency_ms: float = Field(ge=0)
    warnings: list[str]
    metrics: dict[str, float | int]
    artifacts: dict[str, ArtifactFileResponse]
    disclaimer: str


class PredictionWithExplanationResponse(PredictionResponse):
    explanation: ExplanationResponse


class ErrorResponse(BaseModel):
    detail: str
