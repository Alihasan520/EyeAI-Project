from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eyeai.product.database import Base


def _uuid() -> str:
    return str(uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReferenceCounter(Base):
    __tablename__ = "reference_counters"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="doctor")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    medical_record_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    visits: Mapped[list["Visit"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["AssistantConversation"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    clinician_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    eye: Mapped[str] = mapped_column(String(10))
    visit_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="visits")
    predictions: Mapped[list["StoredPrediction"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    doctor_notes: Mapped[list["DoctorNote"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )


class StoredPrediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(30))
    probability: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    decision: Mapped[bool] = mapped_column(Boolean)
    model_version: Mapped[str] = mapped_column(String(100))
    quality_status: Mapped[str] = mapped_column(String(40))
    quality_json: Mapped[str] = mapped_column(Text)
    tta_json: Mapped[str] = mapped_column(Text)
    explanation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    visit: Mapped[Visit] = relationship(back_populates="predictions")


class DoctorNote(Base):
    __tablename__ = "doctor_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    visit: Mapped[Visit] = relationship(back_populates="doctor_notes")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), index=True)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("visits.id"), index=True)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.id"), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    visit_id: Mapped[str | None] = mapped_column(ForeignKey("visits.id"), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    eye: Mapped[str] = mapped_column(String(10))
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider: Mapped[str] = mapped_column(String(60))
    model_name: Mapped[str] = mapped_column(String(200))
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    patient: Mapped[Patient] = relationship(back_populates="conversations")
    messages: Mapped[list["AssistantMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("assistant_conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    structured_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    references_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversation: Mapped[AssistantConversation] = relationship(back_populates="messages")
