from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from eyeai.assistant.provider import DisabledProvider, MockProvider, TransformersQwenProvider
from eyeai.assistant.rag import DisabledRagIndex, FaissRagIndex


def build_provider(settings: Any, shared_lock: threading.RLock | threading.Lock | None = None) -> Any:
    if not settings.assistant_enabled:
        return DisabledProvider()
    provider_name = settings.assistant_provider.lower()
    if provider_name == "mock":
        return MockProvider()
    if provider_name != "qwen_transformers":
        raise ValueError(f"Unsupported assistant provider: {settings.assistant_provider}")
    if settings.assistant_model_dir is None:
        raise ValueError(
            "Assistant model directory is required when qwen_transformers is enabled."
        )
    return TransformersQwenProvider(
        model_path=Path(settings.assistant_model_dir),
        lock=shared_lock,
        load_in_4bit=settings.assistant_load_in_4bit,
        maximum_gpu_memory_gib=settings.assistant_maximum_gpu_memory_gib,
        maximum_input_tokens=settings.assistant_maximum_input_tokens,
        maximum_new_tokens=settings.assistant_maximum_new_tokens,
        temperature=settings.assistant_temperature,
        top_p=settings.assistant_top_p,
        top_k=settings.assistant_top_k,
        local_files_only=settings.assistant_local_files_only,
        use_cache=settings.assistant_use_cache,
        release_cuda_cache_after_generate=settings.assistant_release_cuda_cache_after_generate,
    )


def build_rag_index(settings: Any) -> Any:
    if not settings.rag_enabled:
        return DisabledRagIndex()
    if settings.rag_index_dir is None or settings.rag_embedding_model_dir is None:
        raise ValueError(
            "RAG index and embedding model directories are required when RAG is enabled."
        )
    return FaissRagIndex(
        index_dir=settings.rag_index_dir,
        embedding_model_path=settings.rag_embedding_model_dir,
        top_k=settings.rag_top_k,
        minimum_score=settings.rag_minimum_score,
        maximum_chunk_characters=settings.rag_maximum_chunk_characters,
        maximum_chunks_per_source=settings.rag_maximum_chunks_per_source,
        device=settings.rag_embedding_device,
        local_files_only=True,
    )
