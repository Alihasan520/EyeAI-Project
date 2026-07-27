from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from eyeai.api.config import ApiSettings, default_config_path
from eyeai.api.schemas import (
    ErrorResponse,
    HealthResponse,
    ModelInfoResponse,
    PredictionResponse,
    PredictionWithExplanationResponse,
)
from eyeai.api.service import PredictionService


def create_app(
    settings: ApiSettings | None = None,
    *,
    predictor_factory: Callable[..., Any] | None = None,
    assistant_provider_factory: Callable[..., Any] | None = None,
    rag_index_factory: Callable[..., Any] | None = None,
) -> FastAPI:
    resolved_settings = settings or ApiSettings.from_yaml(default_config_path())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        gpu_lock = threading.RLock() if resolved_settings.inference_lock else None
        service = PredictionService(
            resolved_settings,
            **({"predictor_factory": predictor_factory} if predictor_factory else {}),
            shared_lock=gpu_lock,
        )
        app.state.prediction_service = service
        app.state.settings = resolved_settings
        app.state.gpu_lock = gpu_lock

        if resolved_settings.product_enabled:
            from eyeai.assistant.factory import build_provider, build_rag_index
            from eyeai.assistant.service import AssistantService
            from eyeai.product.database import Database
            from eyeai.product.service import ProductService

            database = Database(resolved_settings.database_url)
            database.create_all()
            product_service = ProductService(
                database,
                reports_dir=resolved_settings.reports_output_dir,
                explanation_root=resolved_settings.explanation_output_dir,
                score_change_threshold=resolved_settings.score_change_threshold,
                high_score_threshold=resolved_settings.high_score_threshold,
            )
            product_service.backfill_display_ids()
            provider = (
                assistant_provider_factory(resolved_settings, gpu_lock)
                if assistant_provider_factory
                else build_provider(resolved_settings, gpu_lock)
            )
            rag_index = (
                rag_index_factory(resolved_settings)
                if rag_index_factory
                else build_rag_index(resolved_settings)
            )
            assistant_service = AssistantService(
                database,
                provider=provider,
                rag_index=rag_index,
                model_name=resolved_settings.assistant_model_name,
                rag_enabled=resolved_settings.rag_enabled,
                maximum_history_messages=resolved_settings.assistant_maximum_history_messages,
                maximum_notes_characters=resolved_settings.assistant_maximum_notes_characters,
                strict_without_rag=resolved_settings.assistant_strict_without_rag,
                maximum_chunks_per_source=resolved_settings.rag_maximum_chunks_per_source,
                require_inline_citations=resolved_settings.assistant_require_inline_citations,
            )
            app.state.database = database
            app.state.product_service = product_service
            app.state.assistant_service = assistant_service
            if resolved_settings.assistant_enabled and not resolved_settings.assistant_lazy_load:
                provider.load()

        if resolved_settings.preload_model:
            service.load()
        yield

    app = FastAPI(
        title=resolved_settings.title,
        description=resolved_settings.description,
        version=resolved_settings.version,
        docs_url=resolved_settings.docs_url,
        redoc_url=resolved_settings.redoc_url,
        openapi_url=resolved_settings.openapi_url,
        lifespan=lifespan,
    )

    if resolved_settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.allowed_origins),
            allow_credentials=resolved_settings.allow_credentials,
            allow_methods=list(resolved_settings.allowed_methods),
            allow_headers=list(resolved_settings.allowed_headers),
        )

    if resolved_settings.explainability_enabled:
        resolved_settings.explanation_output_dir.mkdir(parents=True, exist_ok=True)
        app.mount(
            resolved_settings.artifacts_url_prefix,
            StaticFiles(
                directory=str(resolved_settings.explanation_output_dir),
                check_dir=True,
            ),
            name="explanation-artifacts",
        )

    if resolved_settings.product_enabled:
        from eyeai.api.product_router import router as product_router

        app.include_router(product_router)

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health(request: Request) -> HealthResponse:
        service = _service(request)
        model_version = None
        device = None
        if service.loaded:
            info = service.model_info()
            model_version = str(info["model_version"])
            device = str(info["device"])
        return HealthResponse(
            status="ok" if service.loaded else "model_not_loaded",
            model_loaded=service.loaded,
            model_version=model_version,
            device=device,
        )

    @app.get("/model-info", response_model=ModelInfoResponse, tags=["Model"])
    async def model_info(request: Request) -> ModelInfoResponse:
        service = _service(request)
        if not service.loaded:
            service.load()
        return ModelInfoResponse(**service.model_info())

    @app.post(
        "/predict",
        response_model=PredictionResponse,
        responses=_inference_error_responses(),
        tags=["Inference"],
    )
    async def predict(
        request: Request,
        file: UploadFile = File(...),
    ) -> PredictionResponse:
        service = _service(request)
        data = await _read_upload(request, file)
        try:
            if not service.loaded:
                service.load()
            payload = service.predict_bytes(
                data,
                filename=file.filename or "upload",
                content_type=file.content_type,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        return PredictionResponse(**payload)

    if resolved_settings.explainability_enabled:

        @app.post(
            "/predict-with-explanation",
            response_model=PredictionWithExplanationResponse,
            responses=_inference_error_responses(),
            tags=["Inference", "Explainability"],
        )
        async def predict_with_explanation(
            request: Request,
            file: UploadFile = File(...),
        ) -> PredictionWithExplanationResponse:
            service = _service(request)
            data = await _read_upload(request, file)
            try:
                if not service.loaded:
                    service.load()
                payload = service.predict_with_explanation_bytes(
                    data,
                    filename=file.filename or "upload",
                    content_type=file.content_type,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc
            except (FileNotFoundError, RuntimeError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc
            return PredictionWithExplanationResponse(**payload)

    return app


def _service(request: Request) -> PredictionService:
    service = getattr(request.app.state, "prediction_service", None)
    if not isinstance(service, PredictionService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction service is unavailable.",
        )
    return service


async def _read_upload(request: Request, file: UploadFile) -> bytes:
    settings = request.app.state.settings
    _validate_upload_metadata(file, settings)

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            request_bytes = int(content_length)
        except ValueError:
            request_bytes = 0
        if request_bytes > settings.maximum_upload_bytes + 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Uploaded request is too large.",
            )

    data = await file.read(settings.maximum_upload_bytes + 1)
    if len(data) > settings.maximum_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Uploaded image exceeds the configured size limit.",
        )
    return data


def _validate_upload_metadata(file: UploadFile, settings: ApiSettings) -> None:
    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()

    if settings.allowed_content_types and content_type not in settings.allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image content type: {content_type or 'unknown'}.",
        )
    if settings.allowed_suffixes and suffix not in settings.allowed_suffixes:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image suffix: {suffix or 'missing'}.",
        )


def _inference_error_responses() -> dict[int, dict[str, Any]]:
    return {
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    }
