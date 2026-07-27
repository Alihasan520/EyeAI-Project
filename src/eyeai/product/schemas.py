from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BootstrapRequest(BaseModel):
    email: str
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str




class BootstrapStatusResponse(BaseModel):
    available: bool
    bootstrap_enabled: bool


class UserProfileUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    full_name: str | None = Field(default=None, min_length=2, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class AdminUserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    role: Literal["admin", "clinician"] = "clinician"


class AdminUserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    role: Literal["admin", "clinician"] | None = None
    is_active: bool | None = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class PatientCreate(BaseModel):
    medical_record_number: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date | None = None
    sex: str | None = None
    phone: str | None = None
    notes: str | None = None


class PatientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    sex: str | None = None
    phone: str | None = None
    notes: str | None = None


class PatientResponse(PatientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_id: str
    created_at: datetime
    updated_at: datetime


class VisitCreate(BaseModel):
    eye: Literal["left", "right"]
    visit_date: datetime | None = None
    notes: str | None = None


class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_id: str
    patient_id: str
    clinician_id: str | None
    eye: str
    visit_date: datetime
    notes: str | None
    created_at: datetime


class VisitListItem(BaseModel):
    visit: VisitResponse
    patient_display_id: str
    patient_name: str


class DoctorNoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class DoctorNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_id: str
    visit_id: str
    author_id: str
    text: str
    created_at: datetime


class StoredPredictionResponse(BaseModel):
    id: str
    display_id: str
    visit_id: str
    request_id: str
    label: str
    probability: float
    threshold: float
    decision: bool
    model_version: str
    quality_status: str
    quality: dict[str, Any]
    tta: dict[str, Any]
    explanation: dict[str, Any] | None
    created_at: datetime


class TimelineEntry(BaseModel):
    visit: VisitResponse
    prediction: StoredPredictionResponse | None
    score_delta: float | None
    trend: Literal["first_measurement", "stable", "increasing", "decreasing"]
    doctor_notes: list[DoctorNoteResponse]


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_id: str
    patient_id: str
    visit_id: str
    prediction_id: str
    alert_type: str
    severity: str
    message: str
    acknowledged: bool
    created_at: datetime


class ReportCreateRequest(BaseModel):
    clinical_summary: str | None = Field(default=None, max_length=12000)
    references: list[dict[str, Any]] = Field(default_factory=list, max_length=12)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_id: str
    patient_id: str
    visit_id: str
    prediction_id: str
    download_url: str
    created_at: datetime


class ReportListItem(BaseModel):
    report: ReportResponse
    patient_display_id: str
    patient_name: str
    visit_display_id: str
    eye: Literal["left", "right"]
    visit_date: datetime


class DashboardResponse(BaseModel):
    patients: int
    visits: int
    predictions: int
    unacknowledged_alerts: int
    recent_alerts: list[AlertResponse]


class AssistantStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model_name: str
    model_loaded: bool
    rag_enabled: bool
    rag_loaded: bool
    gpu_memory: dict[str, float] | None = None


class AssistantConversationCreate(BaseModel):
    eye: Literal["left", "right"]
    visit_id: str | None = None
    title: str | None = Field(default=None, max_length=200)


class AssistantConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_id: str
    patient_id: str
    visit_id: str | None
    created_by: str
    eye: str
    title: str | None
    provider: str
    model_name: str
    rag_enabled: bool
    created_at: datetime
    updated_at: datetime


class AssistantMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=12000)


class AssistantMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    structured: dict[str, Any] | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class AssistantTurnResponse(BaseModel):
    user_message: AssistantMessageResponse
    assistant_message: AssistantMessageResponse
    result: dict[str, Any]


class AssistantGeneratedDocumentResponse(BaseModel):
    conversation: AssistantConversationResponse
    result: dict[str, Any]
