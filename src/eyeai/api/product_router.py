from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from eyeai.product.models import AssistantMessage, User
from eyeai.product.schemas import (
    AlertResponse,
    AssistantConversationCreate,
    AssistantConversationResponse,
    AssistantGeneratedDocumentResponse,
    AssistantMessageCreate,
    AssistantMessageResponse,
    AssistantStatusResponse,
    AssistantTurnResponse,
    AdminPasswordResetRequest,
    AdminUserCreate,
    AdminUserUpdate,
    BootstrapRequest,
    BootstrapStatusResponse,
    ChangePasswordRequest,
    DashboardResponse,
    DoctorNoteCreate,
    DoctorNoteResponse,
    LoginRequest,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    ReportCreateRequest,
    ReportListItem,
    ReportResponse,
    StoredPredictionResponse,
    TimelineEntry,
    TokenResponse,
    UserProfileUpdate,
    UserResponse,
    VisitCreate,
    VisitListItem,
    VisitResponse,
)
from eyeai.product.security import create_access_token, decode_access_token

router = APIRouter(prefix="/api/v1")
bearer = HTTPBearer(auto_error=False)


def _product(request: Request):
    return request.app.state.product_service


def _assistant(request: Request):
    service = getattr(request.app.state, "assistant_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Clinical assistant is unavailable.")
    return service


def _settings(request: Request):
    return request.app.state.settings


def _prediction(request: Request):
    return request.app.state.prediction_service


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication is required.")
    settings = _settings(request)
    try:
        payload = decode_access_token(
            credentials.credentials,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.") from exc
    user = _product(request).get_user(str(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable.")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user


@router.get(
    "/auth/bootstrap-status",
    response_model=BootstrapStatusResponse,
    tags=["Authentication"],
)
def bootstrap_status(request: Request) -> BootstrapStatusResponse:
    enabled = bool(_settings(request).bootstrap_enabled)
    return BootstrapStatusResponse(
        available=enabled and _product(request).bootstrap_available(),
        bootstrap_enabled=enabled,
    )


@router.post("/auth/bootstrap", response_model=UserResponse, tags=["Authentication"])
def bootstrap(request: Request, payload: BootstrapRequest) -> UserResponse:
    settings = _settings(request)
    if not settings.bootstrap_enabled:
        raise HTTPException(status_code=403, detail="Bootstrap is disabled.")
    try:
        user = _product(request).bootstrap_user(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserResponse.model_validate(user)


@router.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
def login(request: Request, payload: LoginRequest) -> TokenResponse:
    service = _product(request)
    settings = _settings(request)
    user = service.authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(
        subject=user.id,
        role=user.role,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        minutes=settings.access_token_minutes,
    )
    return TokenResponse(
        access_token=token,
        expires_in_seconds=settings.access_token_minutes * 60,
    )


@router.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
def me(user: Annotated[User, Depends(current_user)]) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/auth/me", response_model=UserResponse, tags=["Authentication"])
def update_me(
    request: Request,
    payload: UserProfileUpdate,
    user: Annotated[User, Depends(current_user)],
) -> UserResponse:
    try:
        updated = _product(request).update_user_profile(
            user.id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="User was not found.")
    return UserResponse.model_validate(updated)


@router.post("/auth/change-password", status_code=204, tags=["Authentication"])
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user: Annotated[User, Depends(current_user)],
) -> None:
    changed = _product(request).change_password(
        user.id, payload.current_password, payload.new_password
    )
    if not changed:
        raise HTTPException(status_code=400, detail="Current password is incorrect.")


@router.get("/users", response_model=list[UserResponse], tags=["Users & Access"])
def list_users(
    request: Request,
    user: Annotated[User, Depends(admin_user)],
) -> list[UserResponse]:
    del user
    return [UserResponse.model_validate(item) for item in _product(request).list_users()]


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
    tags=["Users & Access"],
)
def create_user(
    request: Request,
    payload: AdminUserCreate,
    user: Annotated[User, Depends(admin_user)],
) -> UserResponse:
    del user
    try:
        created = _product(request).create_user(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserResponse.model_validate(created)


@router.patch("/users/{user_ref}", response_model=UserResponse, tags=["Users & Access"])
def update_user(
    user_ref: str,
    request: Request,
    payload: AdminUserUpdate,
    user: Annotated[User, Depends(admin_user)],
) -> UserResponse:
    target = _product(request).get_user(user_ref)
    if target is None:
        raise HTTPException(status_code=404, detail="User was not found.")
    if target.id == user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot disable your own account.")
    if target.id == user.id and payload.role is not None and payload.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot remove your own administrator role.")
    try:
        updated = _product(request).update_user(
            user_ref, payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="User was not found.")
    return UserResponse.model_validate(updated)


@router.post(
    "/users/{user_ref}/reset-password",
    response_model=UserResponse,
    tags=["Users & Access"],
)
def reset_user_password(
    user_ref: str,
    request: Request,
    payload: AdminPasswordResetRequest,
    user: Annotated[User, Depends(admin_user)],
) -> UserResponse:
    del user
    updated = _product(request).reset_user_password(user_ref, payload.new_password)
    if updated is None:
        raise HTTPException(status_code=404, detail="User was not found.")
    return UserResponse.model_validate(updated)


@router.post("/patients", response_model=PatientResponse, status_code=201, tags=["Patients"])
def create_patient(
    request: Request,
    payload: PatientCreate,
    user: Annotated[User, Depends(current_user)],
) -> PatientResponse:
    del user
    try:
        patient = _product(request).create_patient(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PatientResponse.model_validate(patient)


@router.get("/patients", response_model=list[PatientResponse], tags=["Patients"])
def list_patients(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    search: str | None = Query(default=None, max_length=100),
) -> list[PatientResponse]:
    del user
    return [PatientResponse.model_validate(item) for item in _product(request).list_patients(search)]


@router.get("/patients/{patient_ref}", response_model=PatientResponse, tags=["Patients"])
def get_patient(
    patient_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> PatientResponse:
    del user
    patient = _product(request).get_patient(patient_ref)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient was not found.")
    return PatientResponse.model_validate(patient)


@router.patch("/patients/{patient_ref}", response_model=PatientResponse, tags=["Patients"])
def update_patient(
    patient_ref: str,
    request: Request,
    payload: PatientUpdate,
    user: Annotated[User, Depends(current_user)],
) -> PatientResponse:
    del user
    patient = _product(request).update_patient(
        patient_ref, payload.model_dump(exclude_unset=True)
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient was not found.")
    return PatientResponse.model_validate(patient)


@router.post(
    "/patients/{patient_ref}/visits",
    response_model=VisitResponse,
    status_code=201,
    tags=["Visits"],
)
def create_visit(
    patient_ref: str,
    request: Request,
    payload: VisitCreate,
    user: Annotated[User, Depends(current_user)],
) -> VisitResponse:
    data = payload.model_dump()
    if data["visit_date"] is None:
        data["visit_date"] = datetime.now(timezone.utc)
    try:
        visit = _product(request).create_visit(patient_ref, user.id, data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VisitResponse.model_validate(visit)


@router.get("/visits", response_model=list[VisitListItem], tags=["Visits"])
def list_visits(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    patient_id: str | None = None,
    eye: Literal["left", "right"] | None = None,
) -> list[VisitListItem]:
    del user
    return [
        VisitListItem.model_validate(item)
        for item in _product(request).list_visits(patient_id, eye)
    ]


@router.get("/visits/{visit_ref}", response_model=VisitResponse, tags=["Visits"])
def get_visit(
    visit_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> VisitResponse:
    del user
    visit = _product(request).get_visit(visit_ref)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit was not found.")
    return VisitResponse.model_validate(visit)


@router.post(
    "/visits/{visit_ref}/notes",
    response_model=DoctorNoteResponse,
    status_code=201,
    tags=["Visits"],
)
def add_note(
    visit_ref: str,
    request: Request,
    payload: DoctorNoteCreate,
    user: Annotated[User, Depends(current_user)],
) -> DoctorNoteResponse:
    try:
        note = _product(request).add_note(visit_ref, user.id, payload.text)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DoctorNoteResponse.model_validate(note)


@router.post(
    "/visits/{visit_ref}/analyze",
    response_model=StoredPredictionResponse,
    status_code=201,
    tags=["Visits", "Inference"],
)
async def analyze_visit(
    visit_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    file: UploadFile = File(...),
    explanation: bool = Query(default=True),
) -> StoredPredictionResponse:
    del user
    if _product(request).get_visit(visit_ref) is None:
        raise HTTPException(status_code=404, detail="Visit was not found.")
    data = await file.read()
    prediction_service = _prediction(request)
    try:
        if not prediction_service.loaded:
            prediction_service.load()
        if explanation and _settings(request).explainability_enabled:
            payload = prediction_service.predict_with_explanation_bytes(
                data,
                filename=file.filename or "upload",
                content_type=file.content_type,
            )
        else:
            payload = prediction_service.predict_bytes(
                data,
                filename=file.filename or "upload",
                content_type=file.content_type,
            )
        stored = _product(request).store_prediction(visit_ref, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return StoredPredictionResponse(**_product(request).prediction_payload(stored))


@router.get(
    "/patients/{patient_ref}/timeline",
    response_model=list[TimelineEntry],
    tags=["Timeline"],
)
def patient_timeline(
    patient_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    eye: Literal["left", "right"] | None = None,
) -> list[TimelineEntry]:
    del user
    if _product(request).get_patient(patient_ref) is None:
        raise HTTPException(status_code=404, detail="Patient was not found.")
    return [TimelineEntry.model_validate(item) for item in _product(request).timeline(patient_ref, eye)]


@router.get("/alerts", response_model=list[AlertResponse], tags=["Alerts"])
def list_alerts(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    patient_id: str | None = None,
) -> list[AlertResponse]:
    del user
    return [AlertResponse.model_validate(item) for item in _product(request).list_alerts(patient_id)]


@router.post("/alerts/{alert_ref}/acknowledge", response_model=AlertResponse, tags=["Alerts"])
def acknowledge_alert(
    alert_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> AlertResponse:
    del user
    alert = _product(request).acknowledge_alert(alert_ref)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert was not found.")
    return AlertResponse.model_validate(alert)


@router.get("/reports", response_model=list[ReportListItem], tags=["Reports"])
def list_reports(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    patient_id: str | None = None,
) -> list[ReportListItem]:
    del user
    items = []
    for item in _product(request).list_reports(patient_id):
        report = item["report"]
        items.append(
            ReportListItem(
                report=ReportResponse(
                    id=report.id,
                    display_id=report.display_id,
                    patient_id=report.patient_id,
                    visit_id=report.visit_id,
                    prediction_id=report.prediction_id,
                    download_url=f"/api/v1/reports/{report.display_id}/download",
                    created_at=report.created_at,
                ),
                patient_display_id=item["patient_display_id"],
                patient_name=item["patient_name"],
                visit_display_id=item["visit_display_id"],
                eye=item["eye"],
                visit_date=item["visit_date"],
            )
        )
    return items


@router.post("/visits/{visit_ref}/reports", response_model=ReportResponse, status_code=201, tags=["Reports"])
def create_report(
    visit_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
    payload: ReportCreateRequest | None = None,
) -> ReportResponse:
    payload = payload or ReportCreateRequest()
    try:
        report = _product(request).create_report(
            visit_ref,
            clinical_summary=payload.clinical_summary,
            references=payload.references,
            clinician_name=user.full_name,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReportResponse(
        id=report.id,
        display_id=report.display_id,
        patient_id=report.patient_id,
        visit_id=report.visit_id,
        prediction_id=report.prediction_id,
        download_url=f"/api/v1/reports/{report.display_id}/download",
        created_at=report.created_at,
    )


@router.get("/reports/{report_ref}/download", tags=["Reports"])
def download_report(
    report_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> FileResponse:
    del user
    report = _product(request).get_report(report_ref)
    if report is None or not Path(report.file_path).is_file():
        raise HTTPException(status_code=404, detail="Report was not found.")
    return FileResponse(report.file_path, media_type="application/pdf", filename=Path(report.file_path).name)


@router.get("/dashboard", response_model=DashboardResponse, tags=["Dashboard"])
def dashboard(
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> DashboardResponse:
    del user
    return DashboardResponse.model_validate(_product(request).dashboard())


@router.get("/assistant/status", response_model=AssistantStatusResponse, tags=["Clinical Assistant"])
def assistant_status(
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> AssistantStatusResponse:
    del user
    return AssistantStatusResponse.model_validate(_assistant(request).status())


@router.post(
    "/patients/{patient_ref}/assistant/conversations",
    response_model=AssistantConversationResponse,
    status_code=201,
    tags=["Clinical Assistant"],
)
def create_assistant_conversation(
    patient_ref: str,
    request: Request,
    payload: AssistantConversationCreate,
    user: Annotated[User, Depends(current_user)],
) -> AssistantConversationResponse:
    try:
        conversation = _assistant(request).create_conversation(
            patient_ref=patient_ref,
            created_by_ref=user.id,
            eye=payload.eye,
            visit_ref=payload.visit_id,
            title=payload.title,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AssistantConversationResponse.model_validate(conversation)


@router.get(
    "/patients/{patient_ref}/assistant/conversations",
    response_model=list[AssistantConversationResponse],
    tags=["Clinical Assistant"],
)
def list_assistant_conversations(
    patient_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> list[AssistantConversationResponse]:
    del user
    if _product(request).get_patient(patient_ref) is None:
        raise HTTPException(status_code=404, detail="Patient was not found.")
    return [
        AssistantConversationResponse.model_validate(item)
        for item in _assistant(request).list_conversations(patient_ref)
    ]


@router.get(
    "/assistant/conversations/{conversation_ref}",
    response_model=AssistantConversationResponse,
    tags=["Clinical Assistant"],
)
def get_assistant_conversation(
    conversation_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> AssistantConversationResponse:
    del user
    conversation = _assistant(request).get_conversation(conversation_ref)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Assistant conversation was not found.")
    return AssistantConversationResponse.model_validate(conversation)


@router.get(
    "/assistant/conversations/{conversation_ref}/messages",
    response_model=list[AssistantMessageResponse],
    tags=["Clinical Assistant"],
)
def list_assistant_messages(
    conversation_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> list[AssistantMessageResponse]:
    del user
    if _assistant(request).get_conversation(conversation_ref) is None:
        raise HTTPException(status_code=404, detail="Assistant conversation was not found.")
    return [_message_response(item) for item in _assistant(request).list_messages(conversation_ref)]


@router.post(
    "/assistant/conversations/{conversation_ref}/messages",
    response_model=AssistantTurnResponse,
    status_code=201,
    tags=["Clinical Assistant"],
)
def send_assistant_message(
    conversation_ref: str,
    request: Request,
    payload: AssistantMessageCreate,
    user: Annotated[User, Depends(current_user)],
) -> AssistantTurnResponse:
    if not _settings(request).assistant_enabled:
        raise HTTPException(status_code=503, detail="Clinical assistant is disabled.")
    try:
        user_message, assistant_message, result = _assistant(request).send_message(
            conversation_ref=conversation_ref,
            user_ref=user.id,
            question=payload.content,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AssistantTurnResponse(
        user_message=_message_response(user_message),
        assistant_message=_message_response(assistant_message),
        result=result,
    )


@router.post(
    "/visits/{visit_ref}/assistant-summary",
    response_model=AssistantGeneratedDocumentResponse,
    status_code=201,
    tags=["Clinical Assistant"],
)
def generate_visit_summary(
    visit_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> AssistantGeneratedDocumentResponse:
    if not _settings(request).assistant_enabled:
        raise HTTPException(status_code=503, detail="Clinical assistant is disabled.")
    try:
        conversation, result = _assistant(request).create_visit_summary(
            visit_ref=visit_ref,
            user_ref=user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AssistantGeneratedDocumentResponse(
        conversation=AssistantConversationResponse.model_validate(conversation),
        result=result,
    )


@router.post(
    "/visits/{visit_ref}/report-draft",
    response_model=AssistantGeneratedDocumentResponse,
    status_code=201,
    tags=["Clinical Assistant"],
)
def generate_report_draft(
    visit_ref: str,
    request: Request,
    user: Annotated[User, Depends(current_user)],
) -> AssistantGeneratedDocumentResponse:
    if not _settings(request).assistant_enabled:
        raise HTTPException(status_code=503, detail="Clinical assistant is disabled.")
    try:
        conversation, result = _assistant(request).create_report_draft(
            visit_ref=visit_ref,
            user_ref=user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AssistantGeneratedDocumentResponse(
        conversation=AssistantConversationResponse.model_validate(conversation),
        result=result,
    )


def _message_response(message: AssistantMessage) -> AssistantMessageResponse:
    structured = json.loads(message.structured_json) if message.structured_json else None
    references = json.loads(message.references_json) if message.references_json else []
    return AssistantMessageResponse(
        id=message.id,
        display_id=message.display_id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        structured=structured,
        references=references,
        created_at=message.created_at,
    )
