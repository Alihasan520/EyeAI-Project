from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import desc, select

from eyeai.assistant.context import (
    build_messages,
    deterministic_patient_evidence,
    fixed_limitations,
)
from eyeai.assistant.grounding import ground_assistant_output
from eyeai.assistant.interpretation import (
    deterministic_clinical_interpretation,
    heatmap_spatial_summary,
    route_question,
    route_topics,
    technical_review_profile,
)
from eyeai.assistant.provider import AssistantProvider
from eyeai.assistant.rag import DisabledRagIndex, RetrievedReference
from eyeai.assistant.safety import requires_safe_refusal, safe_refusal
from eyeai.product.database import Database
from eyeai.product.models import (
    Alert,
    AssistantConversation,
    AssistantMessage,
    DoctorNote,
    Patient,
    StoredPrediction,
    User,
    Visit,
)
from eyeai.product.references import allocate_model_reference, resolve_reference


class AssistantService:
    def __init__(
        self,
        database: Database,
        *,
        provider: AssistantProvider,
        rag_index: Any | None = None,
        model_name: str,
        rag_enabled: bool = False,
        maximum_history_messages: int = 8,
        maximum_notes_characters: int = 1600,
        strict_without_rag: bool = True,
        maximum_chunks_per_source: int = 1,
        require_inline_citations: bool = True,
    ) -> None:
        self.database = database
        self.provider = provider
        self.rag_index = rag_index or DisabledRagIndex()
        self.model_name = model_name
        self.rag_enabled = rag_enabled
        self.maximum_history_messages = maximum_history_messages
        self.maximum_notes_characters = maximum_notes_characters
        self.strict_without_rag = strict_without_rag
        self.maximum_chunks_per_source = maximum_chunks_per_source
        self.require_inline_citations = require_inline_citations

    def status(self) -> dict[str, Any]:
        rag_loaded = bool(getattr(self.rag_index, "loaded", False))
        memory_status = self.provider.memory_status()
        return {
            "enabled": self.provider.name != "disabled",
            "provider": self.provider.name,
            "model_name": self.model_name,
            "model_loaded": self.provider.loaded,
            "rag_enabled": self.rag_enabled,
            "rag_loaded": rag_loaded,
            "gpu_memory": memory_status,
        }

    def create_conversation(
        self,
        *,
        patient_ref: str,
        created_by_ref: str,
        eye: str,
        visit_ref: str | None = None,
        title: str | None = None,
    ) -> AssistantConversation:
        with self.database.session() as session:
            patient = resolve_reference(session, Patient, patient_ref)
            user = resolve_reference(session, User, created_by_ref)
            visit = resolve_reference(session, Visit, visit_ref) if visit_ref else None
            if not patient:
                raise LookupError("Patient was not found.")
            if not user:
                raise LookupError("User was not found.")
            if visit_ref and not visit:
                raise LookupError("Visit was not found.")
            if visit and (visit.patient_id != patient.id or visit.eye != eye):
                raise ValueError("The selected visit does not match the patient and eye.")
            conversation = AssistantConversation(
                display_id=allocate_model_reference(session, AssistantConversation, "conversation"),
                patient_id=patient.id,
                visit_id=visit.id if visit else None,
                created_by=user.id,
                eye=eye,
                title=(title or f"{eye.title()} eye clinical assistant")[:200],
                provider=self.provider.name,
                model_name=self.model_name,
                rag_enabled=self.rag_enabled,
            )
            session.add(conversation)
            session.flush()
            return conversation

    def list_conversations(self, patient_ref: str) -> list[AssistantConversation]:
        with self.database.session() as session:
            patient = resolve_reference(session, Patient, patient_ref)
            if not patient:
                return []
            return list(
                session.scalars(
                    select(AssistantConversation)
                    .where(AssistantConversation.patient_id == patient.id)
                    .order_by(desc(AssistantConversation.updated_at))
                )
            )

    def get_conversation(self, conversation_ref: str) -> AssistantConversation | None:
        with self.database.session() as session:
            return resolve_reference(session, AssistantConversation, conversation_ref)

    def list_messages(self, conversation_ref: str) -> list[AssistantMessage]:
        with self.database.session() as session:
            conversation = resolve_reference(session, AssistantConversation, conversation_ref)
            if not conversation:
                return []
            return list(
                session.scalars(
                    select(AssistantMessage)
                    .where(AssistantMessage.conversation_id == conversation.id)
                    .order_by(AssistantMessage.created_at)
                )
            )

    def send_message(
        self,
        *,
        conversation_ref: str,
        user_ref: str,
        question: str,
    ) -> tuple[AssistantMessage, AssistantMessage, dict[str, Any]]:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Assistant question cannot be empty.")

        with self.database.session() as session:
            conversation = resolve_reference(session, AssistantConversation, conversation_ref)
            user = resolve_reference(session, User, user_ref)
            if not conversation:
                raise LookupError("Assistant conversation was not found.")
            if not user:
                raise LookupError("User was not found.")
            patient = session.get(Patient, conversation.patient_id)
            redaction_tokens = _patient_redaction_tokens(patient)
            provider_question = _redact_text(clean_question, redaction_tokens)

            question_route = route_question(clean_question)
            context_snapshot = self._build_context(
                session, conversation, redaction_tokens=redaction_tokens
            )
            context_snapshot["question_route"] = question_route
            history = self._history(
                session, conversation.id, redaction_tokens=redaction_tokens
            )
            retrieved_references = self._retrieve(
                provider_question,
                context_snapshot,
                question_route=question_route,
            )
            references = [
                self._number_reference(item, index + 1)
                for index, item in enumerate(retrieved_references)
            ]

            user_message = AssistantMessage(
                display_id=allocate_model_reference(session, AssistantMessage, "message"),
                conversation_id=conversation.id,
                role="user",
                content=clean_question,
                context_snapshot_json=None,
                references_json=None,
            )
            session.add(user_message)
            session.flush()

            if requires_safe_refusal(clean_question):
                answer, suggested_review = safe_refusal(clean_question)
                grounding_metadata = {
                    "fallback_used": True,
                    "warnings": ["safe_refusal"],
                    "knowledge_scope": "patient_context_only",
                }
            else:
                messages = build_messages(
                    question=provider_question,
                    context=context_snapshot,
                    references=[self._reference_prompt_payload(item) for item in references],
                    history=history,
                    question_route=question_route,
                )
                raw_output = self.provider.generate(messages)
                grounded = ground_assistant_output(
                    answer=raw_output.strip(),
                    suggested_review="",
                    question=clean_question,
                    context=context_snapshot,
                    rag_enabled=self.rag_enabled,
                    references=references,
                    strict_without_rag=self.strict_without_rag,
                    require_inline_citations=self.require_inline_citations,
                )
                answer = grounded.answer
                suggested_review = grounded.suggested_review
                grounding_metadata = grounded.metadata()

            structured = {
                "answer": answer,
                "question_route": question_route,
                "clinical_interpretation": deterministic_clinical_interpretation(context_snapshot),
                "patient_evidence": deterministic_patient_evidence(context_snapshot),
                "heatmap_spatial": context_snapshot.get("heatmap_spatial"),
                "technical_review_profile": context_snapshot.get("technical_review_profile"),
                "references": [self._reference_public_payload(item) for item in references],
                "limitations": fixed_limitations(),
                "suggested_review": suggested_review,
                "grounding": grounding_metadata,
                "source_status": (
                    f"{len(references)} approved RAG reference excerpt(s) were used."
                    if references
                    else "RAG disabled or no approved reference excerpts were used."
                ),
            }
            assistant_message = AssistantMessage(
                display_id=allocate_model_reference(session, AssistantMessage, "message"),
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                structured_json=json.dumps(structured, ensure_ascii=False),
                context_snapshot_json=json.dumps(
                    context_snapshot, ensure_ascii=False, default=_json_default
                ),
                references_json=json.dumps(
                    [self._reference_public_payload(item) for item in references], ensure_ascii=False
                ),
            )
            session.add(assistant_message)
            conversation.updated_at = datetime.now(timezone.utc)
            session.flush()
            return user_message, assistant_message, structured

    def create_visit_summary(
        self,
        *,
        visit_ref: str,
        user_ref: str,
    ) -> tuple[AssistantConversation, dict[str, Any]]:
        with self.database.session() as session:
            visit = resolve_reference(session, Visit, visit_ref)
            if not visit:
                raise LookupError("Visit was not found.")
            patient = session.get(Patient, visit.patient_id)
        conversation = self.create_conversation(
            patient_ref=patient.id,
            created_by_ref=user_ref,
            eye=visit.eye,
            visit_ref=visit.id,
            title=f"Visit summary for {visit.display_id}",
        )
        _, _, structured = self.send_message(
            conversation_ref=conversation.id,
            user_ref=user_ref,
            question=(
                "Summarize this visit using only the EyeAI record. Highlight the model "
                "score, image-quality warnings, same-eye comparison, and limitations."
            ),
        )
        return conversation, structured

    def create_report_draft(
        self,
        *,
        visit_ref: str,
        user_ref: str,
    ) -> tuple[AssistantConversation, dict[str, Any]]:
        with self.database.session() as session:
            visit = resolve_reference(session, Visit, visit_ref)
            if not visit:
                raise LookupError("Visit was not found.")
            patient = session.get(Patient, visit.patient_id)
        conversation = self.create_conversation(
            patient_ref=patient.id,
            created_by_ref=user_ref,
            eye=visit.eye,
            visit_ref=visit.id,
            title=f"Report draft for {visit.display_id}",
        )
        _, _, structured = self.send_message(
            conversation_ref=conversation.id,
            user_ref=user_ref,
            question=(
                "Create a concise clinician-facing draft for this visit. Do not diagnose, "
                "prescribe, or claim confirmed progression."
            ),
        )
        return conversation, structured

    def _history(
        self,
        session: Any,
        conversation_id: str,
        *,
        redaction_tokens: list[str],
    ) -> list[dict[str, str]]:
        messages = list(
            session.scalars(
                select(AssistantMessage)
                .where(AssistantMessage.conversation_id == conversation_id)
                .order_by(desc(AssistantMessage.created_at))
                .limit(self.maximum_history_messages)
            )
        )
        messages.reverse()
        return [
            {
                "role": item.role,
                "content": _redact_text(item.content[:4000], redaction_tokens),
            }
            for item in messages
            if item.role in {"user", "assistant"}
        ]

    def _retrieve(
        self,
        question: str,
        context_snapshot: dict[str, Any],
        *,
        question_route: str,
    ) -> list[RetrievedReference]:
        if not self.rag_enabled:
            return []
        query = (
            f"{question}\nSelected eye: {context_snapshot.get('selected_eye')}\n"
            f"Question route: {question_route}\n"
            "Topic: age-related macular degeneration screening and clinical review"
        )
        try:
            return list(
                self.rag_index.search(
                    query,
                    allowed_topics=route_topics(question_route),
                    maximum_chunks_per_source=self.maximum_chunks_per_source,
                )
            )
        except TypeError:
            # Backward-compatible adapter for simple custom/test RAG providers.
            return list(self.rag_index.search(query))

    def _build_context(
        self,
        session: Any,
        conversation: AssistantConversation,
        *,
        redaction_tokens: list[str],
    ) -> dict[str, Any]:
        patient = session.get(Patient, conversation.patient_id)
        selected_visit = session.get(Visit, conversation.visit_id) if conversation.visit_id else None
        visit_query = (
            select(Visit)
            .where(
                Visit.patient_id == conversation.patient_id,
                Visit.eye == conversation.eye,
            )
            .order_by(Visit.visit_date)
        )
        visits = list(session.scalars(visit_query))
        if selected_visit is None and visits:
            selected_visit = visits[-1]

        visit_payloads: list[dict[str, Any]] = []
        current_payload: dict[str, Any] | None = None
        previous_score: float | None = None
        score_change: float | None = None
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
            alerts = list(
                session.scalars(
                    select(Alert)
                    .where(Alert.visit_id == visit.id)
                    .order_by(Alert.created_at)
                )
            )
            probability = prediction.probability if prediction else None
            item = {
                "visit_reference": visit.display_id,
                "date": visit.visit_date.date().isoformat(),
                "eye": visit.eye,
                "prediction": prediction.label if prediction else None,
                "probability": probability,
                "threshold": prediction.threshold if prediction else None,
                "tta": json.loads(prediction.tta_json) if prediction else {},
                "quality_warnings": (
                    json.loads(prediction.quality_json).get("warnings", [])
                    if prediction
                    else []
                ),
                "explanation_metrics": (
                    (json.loads(prediction.explanation_json) or {}).get("metrics", {})
                    if prediction and prediction.explanation_json
                    else {}
                ),
                "alerts": [alert.alert_type for alert in alerts],
                "doctor_notes_untrusted": [
                    _redact_text(
                        note.text[: self.maximum_notes_characters], redaction_tokens
                    )
                    for note in notes
                ],
            }
            visit_payloads.append(item)
            if selected_visit and visit.id == selected_visit.id:
                current_payload = item
                if probability is not None and previous_score is not None:
                    score_change = probability - previous_score
            if probability is not None:
                previous_score = probability

        current_index = (
            next(
                (index for index, item in enumerate(visit_payloads) if current_payload is item),
                len(visit_payloads) - 1,
            )
            if visit_payloads
            else -1
        )
        previous_visits = visit_payloads[:current_index] if current_index >= 0 else []
        context = {
            "patient_demographics": {
                "age_years": _age(patient.date_of_birth) if patient else None,
                "sex": patient.sex if patient else None,
            },
            "selected_eye": conversation.eye,
            "current_visit": current_payload,
            "previous_same_eye_visits": previous_visits[-5:],
            "score_change": score_change,
            "model_limitations": fixed_limitations(),
        }
        explanation_metrics = (current_payload or {}).get("explanation_metrics") or {}
        context["heatmap_spatial"] = heatmap_spatial_summary(explanation_metrics)
        context["technical_review_profile"] = technical_review_profile(context)
        return context

    @staticmethod
    def _number_reference(item: RetrievedReference, citation_number: int) -> dict[str, Any]:
        payload = item.citation_payload(citation_number=citation_number)
        payload["excerpt"] = item.text
        return payload


    @staticmethod
    def _reference_public_payload(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "excerpt"}

    @staticmethod
    def _reference_prompt_payload(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "citation_number": item["citation_number"],
            "source_id": item.get("source_id"),
            "title": item.get("title"),
            "organization": item.get("organization"),
            "section": item.get("section"),
            "page": item.get("page"),
            "allowed_topics": item.get("allowed_topics", []),
            "excerpt": item.get("excerpt", ""),
        }


def _patient_redaction_tokens(patient: Patient | None) -> list[str]:
    if patient is None:
        return []
    candidates = [
        patient.first_name,
        patient.last_name,
        f"{patient.first_name} {patient.last_name}",
        patient.medical_record_number,
        patient.phone,
        patient.date_of_birth.isoformat() if patient.date_of_birth else None,
    ]
    return sorted(
        {str(value).strip() for value in candidates if value and str(value).strip()},
        key=len,
        reverse=True,
    )


def _redact_text(text: str, tokens: list[str]) -> str:
    redacted = text
    for token in tokens:
        redacted = re.sub(re.escape(token), "[REDACTED]", redacted, flags=re.IGNORECASE)
    return redacted

def _age(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
