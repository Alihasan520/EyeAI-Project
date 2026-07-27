from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError

from eyeai.product.database import Database
from eyeai.product.models import (
    Alert,
    AssistantConversation,
    AssistantMessage,
    DoctorNote,
    Patient,
    Report,
    StoredPrediction,
    User,
    Visit,
)
from eyeai.product.references import allocate_model_reference, resolve_reference
from eyeai.product.reports import generate_visit_report
from eyeai.product.security import hash_password, verify_password


class ProductService:
    def __init__(
        self,
        database: Database,
        *,
        reports_dir: Path,
        explanation_root: Path,
        score_change_threshold: float = 0.20,
        high_score_threshold: float = 0.90,
    ) -> None:
        self.database = database
        self.reports_dir = reports_dir
        self.explanation_root = explanation_root
        self.score_change_threshold = score_change_threshold
        self.high_score_threshold = high_score_threshold

    def backfill_display_ids(self) -> None:
        mappings: list[tuple[type[Any], str, str]] = [
            (User, "user", "created_at"),
            (Patient, "patient", "created_at"),
            (Visit, "visit", "visit_date"),
            (StoredPrediction, "prediction", "created_at"),
            (DoctorNote, "note", "created_at"),
            (Alert, "alert", "created_at"),
            (Report, "report", "created_at"),
            (AssistantConversation, "conversation", "created_at"),
            (AssistantMessage, "message", "created_at"),
        ]
        with self.database.session() as session:
            for model, kind, timestamp_field in mappings:
                for entity in session.scalars(
                    select(model).where(model.display_id.is_(None)).order_by(getattr(model, timestamp_field))
                ):
                    entity.display_id = allocate_model_reference(
                        session,
                        model,
                        kind,
                        timestamp=getattr(entity, timestamp_field, None),
                    )
            session.flush()

    def bootstrap_user(self, email: str, full_name: str, password: str) -> User:
        with self.database.session() as session:
            if session.scalar(select(func.count(User.id))) > 0:
                raise ValueError("Bootstrap is disabled after the first user is created.")
            user = User(
                display_id=allocate_model_reference(session, User, "user"),
                email=email.strip().lower(),
                full_name=full_name.strip(),
                password_hash=hash_password(password),
                role="admin",
            )
            session.add(user)
            session.flush()
            return user

    def authenticate(self, email: str, password: str) -> User | None:
        with self.database.session() as session:
            user = session.scalar(select(User).where(User.email == email.strip().lower()))
            if not user or not user.is_active or not verify_password(password, user.password_hash):
                return None
            return user

    def get_user(self, user_ref: str) -> User | None:
        with self.database.session() as session:
            return resolve_reference(session, User, user_ref)

    def bootstrap_available(self) -> bool:
        with self.database.session() as session:
            return (session.scalar(select(func.count(User.id))) or 0) == 0

    def list_users(self) -> list[User]:
        with self.database.session() as session:
            return list(session.scalars(select(User).order_by(User.full_name, User.email)))

    def create_user(self, payload: dict[str, Any]) -> User:
        with self.database.session() as session:
            user = User(
                display_id=allocate_model_reference(session, User, "user"),
                email=str(payload["email"]).strip().lower(),
                full_name=str(payload["full_name"]).strip(),
                password_hash=hash_password(str(payload["password"])),
                role=str(payload.get("role") or "clinician"),
                is_active=True,
            )
            session.add(user)
            try:
                session.flush()
            except IntegrityError as exc:
                raise ValueError("Email address already exists.") from exc
            return user

    def update_user_profile(self, user_ref: str, payload: dict[str, Any]) -> User | None:
        with self.database.session() as session:
            user = resolve_reference(session, User, user_ref)
            if not user:
                return None
            if "email" in payload and payload["email"] is not None:
                user.email = str(payload["email"]).strip().lower()
            if "full_name" in payload and payload["full_name"] is not None:
                user.full_name = str(payload["full_name"]).strip()
            try:
                session.flush()
            except IntegrityError as exc:
                raise ValueError("Email address already exists.") from exc
            return user

    def change_password(
        self, user_ref: str, current_password: str, new_password: str
    ) -> bool:
        with self.database.session() as session:
            user = resolve_reference(session, User, user_ref)
            if not user or not verify_password(current_password, user.password_hash):
                return False
            user.password_hash = hash_password(new_password)
            session.flush()
            return True

    def update_user(self, user_ref: str, payload: dict[str, Any]) -> User | None:
        with self.database.session() as session:
            user = resolve_reference(session, User, user_ref)
            if not user:
                return None
            for key in ("email", "full_name", "role", "is_active"):
                if key in payload and payload[key] is not None:
                    value = payload[key]
                    if key == "email":
                        value = str(value).strip().lower()
                    elif key == "full_name":
                        value = str(value).strip()
                    setattr(user, key, value)
            try:
                session.flush()
            except IntegrityError as exc:
                raise ValueError("Email address already exists.") from exc
            return user

    def reset_user_password(self, user_ref: str, new_password: str) -> User | None:
        with self.database.session() as session:
            user = resolve_reference(session, User, user_ref)
            if not user:
                return None
            user.password_hash = hash_password(new_password)
            session.flush()
            return user

    def create_patient(self, payload: dict[str, Any]) -> Patient:
        with self.database.session() as session:
            patient = Patient(
                display_id=allocate_model_reference(session, Patient, "patient"),
                **payload,
            )
            session.add(patient)
            try:
                session.flush()
            except IntegrityError as exc:
                raise ValueError("Medical record number already exists.") from exc
            return patient

    def list_patients(self, search: str | None = None) -> list[Patient]:
        with self.database.session() as session:
            query = select(Patient).order_by(desc(Patient.created_at))
            if search:
                token = f"%{search.strip()}%"
                query = query.where(
                    Patient.display_id.ilike(token)
                    | Patient.medical_record_number.ilike(token)
                    | Patient.first_name.ilike(token)
                    | Patient.last_name.ilike(token)
                )
            return list(session.scalars(query))

    def get_patient(self, patient_ref: str) -> Patient | None:
        with self.database.session() as session:
            return resolve_reference(session, Patient, patient_ref)

    def update_patient(self, patient_ref: str, payload: dict[str, Any]) -> Patient | None:
        with self.database.session() as session:
            patient = resolve_reference(session, Patient, patient_ref)
            if not patient:
                return None
            for key, value in payload.items():
                setattr(patient, key, value)
            patient.updated_at = datetime.now(timezone.utc)
            session.flush()
            return patient

    def create_visit(self, patient_ref: str, clinician_ref: str, payload: dict[str, Any]) -> Visit:
        with self.database.session() as session:
            patient = resolve_reference(session, Patient, patient_ref)
            clinician = resolve_reference(session, User, clinician_ref)
            if not patient:
                raise LookupError("Patient was not found.")
            if not clinician:
                raise LookupError("Clinician was not found.")
            visit_date = payload.get("visit_date") or datetime.now(timezone.utc)
            visit = Visit(
                display_id=allocate_model_reference(session, Visit, "visit", timestamp=visit_date),
                patient_id=patient.id,
                clinician_id=clinician.id,
                **{**payload, "visit_date": visit_date},
            )
            session.add(visit)
            session.flush()
            return visit

    def get_visit(self, visit_ref: str) -> Visit | None:
        with self.database.session() as session:
            return resolve_reference(session, Visit, visit_ref)

    def list_visits(
        self, patient_ref: str | None = None, eye: str | None = None
    ) -> list[dict[str, Any]]:
        with self.database.session() as session:
            query = select(Visit, Patient).join(Patient, Visit.patient_id == Patient.id)
            if patient_ref:
                patient = resolve_reference(session, Patient, patient_ref)
                if not patient:
                    return []
                query = query.where(Visit.patient_id == patient.id)
            if eye:
                query = query.where(Visit.eye == eye)
            rows = session.execute(query.order_by(desc(Visit.visit_date))).all()
            return [
                {
                    "visit": visit,
                    "patient_display_id": patient.display_id,
                    "patient_name": f"{patient.first_name} {patient.last_name}".strip(),
                }
                for visit, patient in rows
            ]

    def add_note(self, visit_ref: str, author_ref: str, text_value: str) -> DoctorNote:
        with self.database.session() as session:
            visit = resolve_reference(session, Visit, visit_ref)
            author = resolve_reference(session, User, author_ref)
            if not visit:
                raise LookupError("Visit was not found.")
            if not author:
                raise LookupError("Author was not found.")
            note = DoctorNote(
                display_id=allocate_model_reference(session, DoctorNote, "note"),
                visit_id=visit.id,
                author_id=author.id,
                text=text_value,
            )
            session.add(note)
            session.flush()
            return note

    def store_prediction(self, visit_ref: str, payload: dict[str, Any]) -> StoredPrediction:
        with self.database.session() as session:
            visit = resolve_reference(session, Visit, visit_ref)
            if not visit:
                raise LookupError("Visit was not found.")
            prediction = StoredPrediction(
                display_id=allocate_model_reference(session, StoredPrediction, "prediction"),
                visit_id=visit.id,
                request_id=payload["request_id"],
                label=payload["label"],
                probability=float(payload["probability"]),
                threshold=float(payload["threshold"]),
                decision=bool(payload["decision"]),
                model_version=payload["model_version"],
                quality_status=payload["quality"]["status"],
                quality_json=json.dumps(payload["quality"], ensure_ascii=False),
                tta_json=json.dumps(payload["tta"], ensure_ascii=False),
                explanation_json=json.dumps(payload.get("explanation"), ensure_ascii=False)
                if payload.get("explanation")
                else None,
            )
            session.add(prediction)
            session.flush()
            self._create_alerts(session, visit, prediction)
            return prediction

    def prediction_payload(self, prediction: StoredPrediction) -> dict[str, Any]:
        return {
            "id": prediction.id,
            "display_id": prediction.display_id,
            "visit_id": prediction.visit_id,
            "request_id": prediction.request_id,
            "label": prediction.label,
            "probability": prediction.probability,
            "threshold": prediction.threshold,
            "decision": prediction.decision,
            "model_version": prediction.model_version,
            "quality_status": prediction.quality_status,
            "quality": json.loads(prediction.quality_json),
            "tta": json.loads(prediction.tta_json),
            "explanation": json.loads(prediction.explanation_json)
            if prediction.explanation_json
            else None,
            "created_at": prediction.created_at,
        }

    def timeline(self, patient_ref: str, eye: str | None = None) -> list[dict[str, Any]]:
        with self.database.session() as session:
            patient = resolve_reference(session, Patient, patient_ref)
            if not patient:
                return []
            query = select(Visit).where(Visit.patient_id == patient.id)
            if eye:
                query = query.where(Visit.eye == eye)
            visits = list(session.scalars(query.order_by(Visit.visit_date)))
            output: list[dict[str, Any]] = []
            previous_score: float | None = None
            for visit in visits:
                prediction = session.scalar(
                    select(StoredPrediction)
                    .where(StoredPrediction.visit_id == visit.id)
                    .order_by(desc(StoredPrediction.created_at))
                )
                notes = list(
                    session.scalars(
                        select(DoctorNote)
                        .where(DoctorNote.visit_id == visit.id)
                        .order_by(DoctorNote.created_at)
                    )
                )
                delta = None
                trend = "first_measurement"
                if prediction is not None:
                    if previous_score is not None:
                        delta = prediction.probability - previous_score
                        if abs(delta) < self.score_change_threshold:
                            trend = "stable"
                        else:
                            trend = "increasing" if delta > 0 else "decreasing"
                    previous_score = prediction.probability
                output.append(
                    {
                        "visit": visit,
                        "prediction": self.prediction_payload(prediction) if prediction else None,
                        "score_delta": delta,
                        "trend": trend,
                        "doctor_notes": notes,
                    }
                )
            return output

    def list_alerts(self, patient_ref: str | None = None) -> list[Alert]:
        with self.database.session() as session:
            query = select(Alert)
            if patient_ref:
                patient = resolve_reference(session, Patient, patient_ref)
                if not patient:
                    return []
                query = query.where(Alert.patient_id == patient.id)
            return list(session.scalars(query.order_by(desc(Alert.created_at))))

    def acknowledge_alert(self, alert_ref: str) -> Alert | None:
        with self.database.session() as session:
            alert = resolve_reference(session, Alert, alert_ref)
            if not alert:
                return None
            alert.acknowledged = True
            session.flush()
            return alert

    def create_report(
        self,
        visit_ref: str,
        *,
        clinical_summary: str | None = None,
        references: list[dict[str, Any]] | None = None,
        clinician_name: str | None = None,
    ) -> Report:
        with self.database.session() as session:
            visit = resolve_reference(session, Visit, visit_ref)
            if not visit:
                raise LookupError("Visit was not found.")
            patient = session.get(Patient, visit.patient_id)
            prediction = session.scalar(
                select(StoredPrediction)
                .where(StoredPrediction.visit_id == visit.id)
                .order_by(desc(StoredPrediction.created_at))
            )
            if not prediction:
                raise ValueError("The visit has no prediction to report.")
            doctor_notes = list(
                session.scalars(
                    select(DoctorNote)
                    .where(DoctorNote.visit_id == visit.id)
                    .order_by(DoctorNote.created_at)
                )
            )
            report_reference = allocate_model_reference(session, Report, "report")
            path = generate_visit_report(
                output_dir=self.reports_dir,
                patient=patient,
                visit=visit,
                prediction=prediction,
                explanation_root=self.explanation_root,
                report_reference=report_reference,
                doctor_notes=doctor_notes,
                clinical_summary=clinical_summary,
                references=references or [],
                clinician_name=clinician_name,
            )
            report = Report(
                display_id=report_reference,
                patient_id=patient.id,
                visit_id=visit.id,
                prediction_id=prediction.id,
                file_path=str(path),
            )
            session.add(report)
            session.flush()
            return report

    def list_reports(self, patient_ref: str | None = None) -> list[dict[str, Any]]:
        with self.database.session() as session:
            query = (
                select(Report, Patient, Visit)
                .join(Patient, Report.patient_id == Patient.id)
                .join(Visit, Report.visit_id == Visit.id)
            )
            if patient_ref:
                patient = resolve_reference(session, Patient, patient_ref)
                if not patient:
                    return []
                query = query.where(Report.patient_id == patient.id)
            rows = session.execute(query.order_by(desc(Report.created_at))).all()
            return [
                {
                    "report": report,
                    "patient_display_id": patient.display_id,
                    "patient_name": f"{patient.first_name} {patient.last_name}".strip(),
                    "visit_display_id": visit.display_id,
                    "eye": visit.eye,
                    "visit_date": visit.visit_date,
                }
                for report, patient, visit in rows
            ]

    def get_report(self, report_ref: str) -> Report | None:
        with self.database.session() as session:
            return resolve_reference(session, Report, report_ref)

    def dashboard(self) -> dict[str, Any]:
        with self.database.session() as session:
            alerts = list(
                session.scalars(
                    select(Alert)
                    .where(Alert.acknowledged.is_(False))
                    .order_by(desc(Alert.created_at))
                    .limit(10)
                )
            )
            return {
                "patients": session.scalar(select(func.count(Patient.id))) or 0,
                "visits": session.scalar(select(func.count(Visit.id))) or 0,
                "predictions": session.scalar(select(func.count(StoredPrediction.id))) or 0,
                "unacknowledged_alerts": session.scalar(
                    select(func.count(Alert.id)).where(Alert.acknowledged.is_(False))
                )
                or 0,
                "recent_alerts": alerts,
            }

    def _create_alerts(self, session: Any, visit: Visit, prediction: StoredPrediction) -> None:
        alerts: list[Alert] = []
        if prediction.decision:
            alerts.append(
                Alert(
                    display_id=allocate_model_reference(session, Alert, "alert"),
                    patient_id=visit.patient_id,
                    visit_id=visit.id,
                    prediction_id=prediction.id,
                    alert_type="positive_screening_result",
                    severity="high" if prediction.probability >= self.high_score_threshold else "medium",
                    message="AMD screening result is positive and requires clinical review.",
                )
            )
        if prediction.quality_status != "acceptable":
            alerts.append(
                Alert(
                    display_id=allocate_model_reference(session, Alert, "alert"),
                    patient_id=visit.patient_id,
                    visit_id=visit.id,
                    prediction_id=prediction.id,
                    alert_type="image_quality_review",
                    severity="medium",
                    message="Image-quality warnings require review before interpreting the score.",
                )
            )
        previous = session.scalar(
            select(StoredPrediction)
            .join(Visit, StoredPrediction.visit_id == Visit.id)
            .where(
                Visit.patient_id == visit.patient_id,
                Visit.eye == visit.eye,
                StoredPrediction.id != prediction.id,
            )
            .order_by(desc(Visit.visit_date), desc(StoredPrediction.created_at))
        )
        if previous is not None:
            delta = prediction.probability - previous.probability
            if delta >= self.score_change_threshold:
                alerts.append(
                    Alert(
                        display_id=allocate_model_reference(session, Alert, "alert"),
                        patient_id=visit.patient_id,
                        visit_id=visit.id,
                        prediction_id=prediction.id,
                        alert_type="model_score_increase",
                        severity="medium",
                        message=f"Model score increased by {delta:.3f} since the previous comparable visit.",
                    )
                )
        session.add_all(alerts)
