from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ApiSettings:
    title: str
    description: str
    version: str
    host: str
    port: int
    docs_url: str | None
    redoc_url: str | None
    openapi_url: str | None
    model_package_dir: Path
    device: str
    preload_model: bool
    inference_lock: bool
    maximum_upload_bytes: int
    allowed_content_types: tuple[str, ...]
    allowed_suffixes: tuple[str, ...]
    allowed_origins: tuple[str, ...]
    allow_credentials: bool
    allowed_methods: tuple[str, ...]
    allowed_headers: tuple[str, ...]
    quality: dict[str, float | int]
    release_cuda_cache_after_explanation: bool = True
    explainability_enabled: bool = False
    explanation_output_dir: Path = Path("artifacts/explanations")
    artifacts_url_prefix: str = "/artifacts"
    explainability: dict[str, float | int | str | bool] | None = None
    product_enabled: bool = False
    database_url: str = "sqlite:///artifacts/product/eyeai.db"
    reports_output_dir: Path = Path("artifacts/reports")
    jwt_secret: str = "development-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    bootstrap_enabled: bool = True
    score_change_threshold: float = 0.20
    high_score_threshold: float = 0.90
    assistant_enabled: bool = False
    assistant_provider: str = "disabled"
    assistant_model_name: str = "Qwen/Qwen3-4B-Instruct-2507"
    assistant_model_dir: Path | None = None
    assistant_load_in_4bit: bool = True
    assistant_lazy_load: bool = True
    assistant_local_files_only: bool = True
    assistant_maximum_gpu_memory_gib: int = 5
    assistant_maximum_input_tokens: int = 3072
    assistant_maximum_new_tokens: int = 256
    assistant_temperature: float = 0.0
    assistant_top_p: float = 0.8
    assistant_top_k: int = 20
    assistant_maximum_history_messages: int = 4
    assistant_maximum_notes_characters: int = 1600
    assistant_use_cache: bool = True
    assistant_release_cuda_cache_after_generate: bool = True
    assistant_strict_without_rag: bool = True
    assistant_require_inline_citations: bool = True
    rag_enabled: bool = False
    rag_index_dir: Path | None = None
    rag_embedding_model_dir: Path | None = None
    rag_embedding_device: str = "cpu"
    rag_top_k: int = 3
    rag_minimum_score: float = 0.20
    rag_maximum_chunk_characters: int = 1800
    rag_maximum_chunks_per_source: int = 1

    @classmethod
    def from_yaml(
        cls,
        config_path: str | Path,
        *,
        model_package_override: str | Path | None = None,
        device_override: str | None = None,
        assistant_model_override: str | Path | None = None,
        rag_index_override: str | Path | None = None,
        embedding_model_override: str | Path | None = None,
    ) -> "ApiSettings":
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"API config was not found: {path}")

        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise TypeError(f"Expected a YAML mapping: {path}")

        api = _mapping(payload, "api")
        runtime = _mapping(payload, "runtime")
        upload = _mapping(payload, "upload")
        cors = _mapping(payload, "cors")
        quality = dict(_mapping(payload, "quality"))
        explainability = dict(_mapping(payload, "explainability"))
        product = dict(_mapping(payload, "product"))
        database = dict(_mapping(payload, "database"))
        authentication = dict(_mapping(payload, "authentication"))
        reports = dict(_mapping(payload, "reports"))
        alerts = dict(_mapping(payload, "alerts"))
        assistant = dict(_mapping(payload, "assistant"))
        rag = dict(_mapping(payload, "rag"))

        configured_package = model_package_override or os.getenv(
            "EYEAI_MODEL_PACKAGE_DIR"
        ) or runtime.get("model_package_dir")
        if not configured_package:
            raise ValueError(
                "Model package path is required. Set EYEAI_MODEL_PACKAGE_DIR or "
                "runtime.model_package_dir."
            )

        device = device_override or os.getenv("EYEAI_DEVICE") or runtime.get(
            "device", "auto"
        )
        assistant_enabled = _env_bool(
            "EYEAI_ASSISTANT_ENABLED", bool(assistant.get("enabled", False))
        )
        rag_enabled = _env_bool("EYEAI_RAG_ENABLED", bool(rag.get("enabled", False)))
        assistant_model_dir = (
            assistant_model_override
            or os.getenv("EYEAI_ASSISTANT_MODEL_DIR")
            or assistant.get("model_dir")
        )
        rag_index_dir = (
            rag_index_override
            or os.getenv("EYEAI_RAG_INDEX_DIR")
            or rag.get("index_dir")
        )
        embedding_model_dir = (
            embedding_model_override
            or os.getenv("EYEAI_RAG_EMBEDDING_MODEL_DIR")
            or rag.get("embedding_model_dir")
        )

        return cls(
            title=str(api.get("title", "EyeAI API")),
            description=str(api.get("description", "")),
            version=str(api.get("version", "1.0.0")),
            host=str(os.getenv("EYEAI_HOST", api.get("host", "0.0.0.0"))),
            port=int(os.getenv("EYEAI_PORT", api.get("port", 8000))),
            docs_url=_optional_path(api.get("docs_url", "/docs")),
            redoc_url=_optional_path(api.get("redoc_url", "/redoc")),
            openapi_url=_optional_path(api.get("openapi_url", "/openapi.json")),
            model_package_dir=Path(configured_package),
            device=str(device),
            preload_model=bool(runtime.get("preload_model", True)),
            inference_lock=bool(runtime.get("inference_lock", True)),
            release_cuda_cache_after_explanation=bool(
                runtime.get("release_cuda_cache_after_explanation", True)
            ),
            maximum_upload_bytes=int(upload.get("maximum_bytes", 25 * 1024 * 1024)),
            allowed_content_types=tuple(
                str(value) for value in upload.get("allowed_content_types", [])
            ),
            allowed_suffixes=tuple(
                str(value).lower() for value in upload.get("allowed_suffixes", [])
            ),
            allowed_origins=_env_csv_tuple(
                "EYEAI_ALLOWED_ORIGINS",
                tuple(str(value) for value in cors.get("allowed_origins", [])),
            ),
            allow_credentials=bool(cors.get("allow_credentials", True)),
            allowed_methods=tuple(
                str(value) for value in cors.get("allowed_methods", ["GET", "POST"])
            ),
            allowed_headers=tuple(
                str(value) for value in cors.get("allowed_headers", ["*"])
            ),
            quality=quality,
            explainability_enabled=bool(explainability.get("enabled", False)),
            explanation_output_dir=Path(
                os.getenv("EYEAI_EXPLANATION_OUTPUT_DIR")
                or explainability.get("output_dir", "artifacts/explanations")
            ),
            artifacts_url_prefix=_normalized_url_prefix(
                explainability.get("artifacts_url_prefix", "/artifacts")
            ),
            explainability=explainability,
            product_enabled=bool(product.get("enabled", False)),
            database_url=str(
                os.getenv("EYEAI_DATABASE_URL")
                or database.get("url", "sqlite:///artifacts/product/eyeai.db")
            ),
            reports_output_dir=Path(
                os.getenv("EYEAI_REPORTS_OUTPUT_DIR")
                or reports.get("output_dir", "artifacts/reports")
            ),
            jwt_secret=str(
                os.getenv("EYEAI_JWT_SECRET")
                or authentication.get("jwt_secret", "development-secret-change-me")
            ),
            jwt_algorithm=str(authentication.get("algorithm", "HS256")),
            access_token_minutes=int(authentication.get("access_token_minutes", 480)),
            bootstrap_enabled=bool(authentication.get("bootstrap_enabled", True)),
            score_change_threshold=float(alerts.get("score_change_threshold", 0.20)),
            high_score_threshold=float(alerts.get("high_score_threshold", 0.90)),
            assistant_enabled=assistant_enabled,
            assistant_provider=str(assistant.get("provider", "qwen_transformers" if assistant_enabled else "disabled")),
            assistant_model_name=str(assistant.get("model_name", "Qwen/Qwen3-4B-Instruct-2507")),
            assistant_model_dir=Path(assistant_model_dir) if assistant_model_dir else None,
            assistant_load_in_4bit=bool(assistant.get("load_in_4bit", True)),
            assistant_lazy_load=bool(assistant.get("lazy_load", True)),
            assistant_local_files_only=bool(assistant.get("local_files_only", True)),
            assistant_maximum_gpu_memory_gib=int(assistant.get("maximum_gpu_memory_gib", 5)),
            assistant_maximum_input_tokens=int(assistant.get("maximum_input_tokens", 3072)),
            assistant_maximum_new_tokens=int(assistant.get("maximum_new_tokens", 256)),
            assistant_temperature=float(assistant.get("temperature", 0.0)),
            assistant_top_p=float(assistant.get("top_p", 0.8)),
            assistant_top_k=int(assistant.get("top_k", 20)),
            assistant_maximum_history_messages=int(assistant.get("maximum_history_messages", 4)),
            assistant_maximum_notes_characters=int(assistant.get("maximum_notes_characters", 1600)),
            assistant_use_cache=bool(assistant.get("use_cache", True)),
            assistant_release_cuda_cache_after_generate=bool(
                assistant.get("release_cuda_cache_after_generate", True)
            ),
            assistant_strict_without_rag=bool(assistant.get("strict_without_rag", True)),
            assistant_require_inline_citations=bool(
                assistant.get("require_inline_citations", True)
            ),
            rag_enabled=rag_enabled,
            rag_index_dir=Path(rag_index_dir) if rag_index_dir else None,
            rag_embedding_model_dir=Path(embedding_model_dir) if embedding_model_dir else None,
            rag_embedding_device=str(rag.get("embedding_device", "cpu")),
            rag_top_k=int(rag.get("top_k", 3)),
            rag_minimum_score=float(rag.get("minimum_score", 0.20)),
            rag_maximum_chunk_characters=int(rag.get("maximum_chunk_characters", 1800)),
            rag_maximum_chunks_per_source=int(rag.get("maximum_chunks_per_source", 1)),
        )


def default_config_path() -> Path:
    env_path = os.getenv("EYEAI_API_CONFIG")
    if env_path:
        return Path(env_path)
    return Path("configs/api/fastapi_v1.yaml")


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise TypeError(f"Expected '{key}' to be a mapping.")
    return value


def _optional_path(value: Any) -> str | None:
    if value in (None, "", False):
        return None
    return str(value)


def _normalized_url_prefix(value: Any) -> str:
    prefix = "/" + str(value or "artifacts").strip("/")
    return prefix if prefix != "/" else "/artifacts"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _env_csv_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())

