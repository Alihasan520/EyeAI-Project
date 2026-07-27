from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class RetrievedReference:
    chunk_id: str
    document_id: str
    title: str
    source_path: str
    page: int | None
    section: str | None
    text: str
    score: float
    source_id: str = ""
    organization: str | None = None
    allowed_topics: tuple[str, ...] = ()

    def citation_payload(self, citation_number: int | None = None) -> dict[str, Any]:
        payload = {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id or self.document_id,
            "title": self.title,
            "organization": self.organization,
            "page": self.page,
            "section": self.section,
            "allowed_topics": list(self.allowed_topics),
            "score": round(self.score, 6),
        }
        if citation_number is not None:
            payload["citation_number"] = int(citation_number)
        return payload


class DisabledRagIndex:
    enabled = False
    loaded = False

    def search(
        self,
        query: str,
        top_k: int | None = None,
        *,
        allowed_topics: Sequence[str] | None = None,
        maximum_chunks_per_source: int | None = None,
    ) -> list[RetrievedReference]:
        del query, top_k, allowed_topics, maximum_chunks_per_source
        return []


class FaissRagIndex:
    """Local FAISS index with a CPU embedding encoder for query retrieval."""

    enabled = True

    def __init__(
        self,
        *,
        index_dir: str | Path,
        embedding_model_path: str | Path,
        top_k: int = 3,
        minimum_score: float = 0.20,
        maximum_chunk_characters: int = 1800,
        maximum_chunks_per_source: int = 1,
        device: str = "cpu",
        local_files_only: bool = True,
    ) -> None:
        self.index_dir = Path(index_dir)
        self.embedding_model_path = Path(embedding_model_path)
        self.top_k = top_k
        self.minimum_score = minimum_score
        self.maximum_chunk_characters = maximum_chunk_characters
        self.maximum_chunks_per_source = maximum_chunks_per_source
        self.device = device
        self.local_files_only = local_files_only
        self.index: Any | None = None
        self.chunks: list[dict[str, Any]] = []
        self.encoder: Any | None = None

    @property
    def loaded(self) -> bool:
        return self.index is not None and bool(self.chunks)

    def load(self) -> None:
        if self.loaded:
            return
        required = [
            self.index_dir / "index.faiss",
            self.index_dir / "chunks.json",
            self.index_dir / "manifest.json",
        ]
        missing = [path for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "The configured RAG index is incomplete:\n"
                + "\n".join(f"- {path}" for path in missing)
            )
        if not self.embedding_model_path.is_dir():
            raise FileNotFoundError(
                f"Embedding model directory was not found: {self.embedding_model_path}"
            )
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError(
                "Install requirements-assistant-kaggle.txt before enabling RAG."
            ) from exc

        self.index = faiss.read_index(str(self.index_dir / "index.faiss"))
        self.chunks = json.loads(
            (self.index_dir / "chunks.json").read_text(encoding="utf-8")
        )
        if self.index.ntotal != len(self.chunks):
            raise RuntimeError("RAG index and chunks.json have different item counts.")

    def _load_encoder(self) -> None:
        if self.encoder is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Install requirements-assistant-kaggle.txt before enabling RAG."
            ) from exc
        self.encoder = SentenceTransformer(
            str(self.embedding_model_path),
            device=self.device,
            local_files_only=self.local_files_only,
        )

    def search(
        self,
        query: str,
        top_k: int | None = None,
        *,
        allowed_topics: Sequence[str] | None = None,
        maximum_chunks_per_source: int | None = None,
    ) -> list[RetrievedReference]:
        if not query.strip():
            return []
        if not self.loaded:
            self.load()
        self._load_encoder()
        assert self.index is not None
        assert self.encoder is not None

        instruction = (
            "Retrieve clinically relevant, evidence-based AMD guidance for the "
            "following clinician question: "
        )
        vector = self.encoder.encode(
            [instruction + query.strip()],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)

        requested = int(top_k or self.top_k)
        # Retrieve extra candidates because topic/source filtering happens after FAISS.
        search_count = min(max(requested * 8, requested), len(self.chunks))
        scores, indices = self.index.search(vector, search_count)
        allowed_topic_set = {str(topic) for topic in allowed_topics or []}
        per_source_limit = int(
            maximum_chunks_per_source
            if maximum_chunks_per_source is not None
            else self.maximum_chunks_per_source
        )
        per_source_counts: dict[str, int] = {}
        results: list[RetrievedReference] = []

        for score, index in zip(scores[0], indices[0]):
            if index < 0 or float(score) < self.minimum_score:
                continue
            item = self.chunks[int(index)]
            item_topics = tuple(str(value) for value in item.get("allowed_topics", []))
            if allowed_topic_set and item_topics and not (allowed_topic_set & set(item_topics)):
                continue
            source_id = str(item.get("source_id") or item.get("document_id"))
            if per_source_limit > 0 and per_source_counts.get(source_id, 0) >= per_source_limit:
                continue
            per_source_counts[source_id] = per_source_counts.get(source_id, 0) + 1
            results.append(
                RetrievedReference(
                    chunk_id=str(item["chunk_id"]),
                    document_id=str(item["document_id"]),
                    source_id=source_id,
                    title=str(item.get("title") or item["document_id"]),
                    organization=(
                        str(item["organization"]) if item.get("organization") else None
                    ),
                    source_path=str(item.get("source_path", "")),
                    page=int(item["page"]) if item.get("page") is not None else None,
                    section=str(item["section"]) if item.get("section") else None,
                    allowed_topics=item_topics,
                    text=str(item["text"])[: self.maximum_chunk_characters],
                    score=float(score),
                )
            )
            if len(results) >= requested:
                break
        return results
