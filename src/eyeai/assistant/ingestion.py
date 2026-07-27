from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml


SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".docx"}


@dataclass(frozen=True)
class DocumentPage:
    source_path: str
    title: str
    page: int | None
    text: str


@dataclass(frozen=True)
class ReferenceSpec:
    source_id: str
    title: str
    organization: str | None
    file_name_patterns: tuple[str, ...]
    required: bool
    allowed_topics: tuple[str, ...]
    include_page_ranges: tuple[tuple[int, int], ...]
    include_heading_patterns: tuple[str, ...]
    exclude_heading_patterns: tuple[str, ...]


@dataclass(frozen=True)
class PageAuditRecord:
    source_id: str
    title: str
    organization: str | None
    source_path: str
    page: int | None
    selected: bool
    selection_reason: str
    matched_include_patterns: tuple[str, ...]
    matched_exclude_patterns: tuple[str, ...]
    probable_heading: str | None
    text_preview: str
    allowed_topics: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "organization": self.organization,
            "source_path": self.source_path,
            "page": self.page,
            "selected": self.selected,
            "selection_reason": self.selection_reason,
            "matched_include_patterns": list(self.matched_include_patterns),
            "matched_exclude_patterns": list(self.matched_exclude_patterns),
            "probable_heading": self.probable_heading,
            "text_preview": self.text_preview,
            "allowed_topics": list(self.allowed_topics),
        }


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    document_id: str
    source_id: str
    title: str
    organization: str | None
    source_path: str
    page: int | None
    section: str | None
    allowed_topics: tuple[str, ...]
    text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "title": self.title,
            "organization": self.organization,
            "source_path": self.source_path,
            "page": self.page,
            "section": self.section,
            "allowed_topics": list(self.allowed_topics),
            "text": self.text,
        }


def discover_documents(root: str | Path) -> list[Path]:
    directory = Path(root)
    if not directory.is_dir():
        raise FileNotFoundError(f"Knowledge-base directory was not found: {directory}")
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def read_document(path: Path, root: Path) -> list[DocumentPage]:
    suffix = path.suffix.lower()
    relative = str(path.relative_to(root))
    title = path.stem.replace("_", " ").replace("-", " ").strip()
    if suffix in {".txt", ".md"}:
        return [
            DocumentPage(
                source_path=relative,
                title=title,
                page=None,
                text=path.read_text(encoding="utf-8", errors="replace"),
            )
        ]
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Install pypdf to ingest PDF references.") from exc
        reader = PdfReader(str(path))
        return [
            DocumentPage(
                source_path=relative,
                title=title,
                page=index + 1,
                text=page.extract_text() or "",
            )
            for index, page in enumerate(reader.pages)
        ]
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("Install python-docx to ingest DOCX references.") from exc
        document = Document(str(path))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return [DocumentPage(relative, title, None, text)]
    raise ValueError(f"Unsupported document type: {path}")


def load_reference_manifest(path: str | Path) -> list[ReferenceSpec]:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Reference manifest was not found: {manifest_path}")
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("references"), list):
        raise TypeError("reference_manifest.yaml must contain a 'references' list.")
    specs: list[ReferenceSpec] = []
    for raw in payload["references"]:
        if not isinstance(raw, dict):
            raise TypeError("Each reference manifest entry must be a mapping.")
        source_id = str(raw.get("source_id") or "").strip()
        if not source_id:
            raise ValueError("Each reference entry requires source_id.")
        ranges: list[tuple[int, int]] = []
        for item in raw.get("include_page_ranges", []) or []:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError(f"Invalid page range for {source_id}: {item}")
            start, end = int(item[0]), int(item[1])
            if start <= 0 or end < start:
                raise ValueError(f"Invalid page range for {source_id}: {item}")
            ranges.append((start, end))
        specs.append(
            ReferenceSpec(
                source_id=source_id,
                title=str(raw.get("title") or source_id),
                organization=(str(raw["organization"]) if raw.get("organization") else None),
                file_name_patterns=tuple(
                    str(value) for value in raw.get("file_name_patterns", [])
                ),
                required=bool(raw.get("required", True)),
                allowed_topics=tuple(str(value) for value in raw.get("allowed_topics", [])),
                include_page_ranges=tuple(ranges),
                include_heading_patterns=tuple(
                    str(value) for value in raw.get("include_heading_patterns", [])
                ),
                exclude_heading_patterns=tuple(
                    str(value) for value in raw.get("exclude_heading_patterns", [])
                ),
            )
        )
    return specs


def audit_manifest_documents(
    *,
    documents_root: str | Path,
    reference_specs: Sequence[ReferenceSpec],
) -> tuple[list[PageAuditRecord], dict[str, Path]]:
    root = Path(documents_root)
    documents = [path for path in discover_documents(root) if path.name.lower() != "readme.md"]
    matched_files: dict[str, Path] = {}
    audit: list[PageAuditRecord] = []
    for spec in reference_specs:
        matches = [path for path in documents if _matches_reference_file(path, spec)]
        if len(matches) > 1:
            raise RuntimeError(
                f"Multiple files matched {spec.source_id}: " + ", ".join(str(path) for path in matches)
            )
        if not matches:
            if spec.required:
                raise FileNotFoundError(
                    f"Required reference {spec.source_id} was not found under {root}. "
                    f"Accepted filename patterns: {spec.file_name_patterns}"
                )
            continue
        path = matches[0]
        matched_files[spec.source_id] = path
        for page in read_document(path, root):
            cleaned = _clean_text(page.text)
            heading = _probable_heading(cleaned)
            heading_scope = (heading or cleaned[:700]).strip()
            include_matches = tuple(
                pattern
                for pattern in spec.include_heading_patterns
                if re.search(pattern, cleaned, flags=re.IGNORECASE | re.MULTILINE)
            )
            exclude_matches = tuple(
                pattern
                for pattern in spec.exclude_heading_patterns
                if re.search(pattern, heading_scope, flags=re.IGNORECASE | re.MULTILINE)
            )
            in_page_range = _page_in_ranges(page.page, spec.include_page_ranges)
            selected = bool(cleaned) and (in_page_range or bool(include_matches)) and not exclude_matches
            if not cleaned:
                reason = "empty_page"
            elif exclude_matches:
                reason = "excluded_heading"
            elif in_page_range:
                reason = "included_page_range"
            elif include_matches:
                reason = "included_topic_pattern"
            else:
                reason = "no_allowed_topic_match"
            audit.append(
                PageAuditRecord(
                    source_id=spec.source_id,
                    title=spec.title,
                    organization=spec.organization,
                    source_path=page.source_path,
                    page=page.page,
                    selected=selected,
                    selection_reason=reason,
                    matched_include_patterns=include_matches,
                    matched_exclude_patterns=exclude_matches,
                    probable_heading=heading,
                    text_preview=cleaned[:500],
                    allowed_topics=spec.allowed_topics,
                )
            )
    return audit, matched_files


def chunk_manifest_documents(
    *,
    documents_root: str | Path,
    reference_specs: Sequence[ReferenceSpec],
    audit_records: Sequence[PageAuditRecord],
    matched_files: dict[str, Path],
    chunk_characters: int = 1500,
    overlap_characters: int = 180,
) -> list[TextChunk]:
    if chunk_characters <= overlap_characters:
        raise ValueError("chunk_characters must be larger than overlap_characters.")
    root = Path(documents_root)
    selected_pages = {
        (record.source_id, record.page): record
        for record in audit_records
        if record.selected
    }
    chunks: list[TextChunk] = []
    for spec in reference_specs:
        path = matched_files.get(spec.source_id)
        if path is None:
            continue
        document_id = hashlib.sha256(spec.source_id.encode("utf-8")).hexdigest()[:16]
        for page in read_document(path, root):
            record = selected_pages.get((spec.source_id, page.page))
            if record is None:
                continue
            cleaned = _clean_text(page.text)
            if not cleaned:
                continue
            chunks.extend(
                _chunk_page(
                    cleaned,
                    document_id=document_id,
                    source_id=spec.source_id,
                    title=spec.title,
                    organization=spec.organization,
                    source_path=page.source_path,
                    page=page.page,
                    allowed_topics=spec.allowed_topics,
                    chunk_characters=chunk_characters,
                    overlap_characters=overlap_characters,
                )
            )
    return chunks


def chunk_documents(
    documents: Iterable[Path],
    *,
    root: Path,
    chunk_characters: int = 1800,
    overlap_characters: int = 240,
) -> list[TextChunk]:
    """Backward-compatible unrestricted chunking for local documents."""

    if chunk_characters <= overlap_characters:
        raise ValueError("chunk_characters must be larger than overlap_characters.")
    chunks: list[TextChunk] = []
    for path in documents:
        document_id = hashlib.sha256(str(path.relative_to(root)).encode("utf-8")).hexdigest()[:16]
        for page in read_document(path, root):
            cleaned = _clean_text(page.text)
            if not cleaned:
                continue
            chunks.extend(
                _chunk_page(
                    cleaned,
                    document_id=document_id,
                    source_id=document_id,
                    title=page.title,
                    organization=None,
                    source_path=page.source_path,
                    page=page.page,
                    allowed_topics=(),
                    chunk_characters=chunk_characters,
                    overlap_characters=overlap_characters,
                )
            )
    return chunks


def write_chunks(chunks: list[TextChunk], destination: Path) -> None:
    destination.write_text(
        json.dumps([chunk.to_dict() for chunk in chunks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_audit(audit: Sequence[PageAuditRecord], destination: Path) -> None:
    destination.write_text(
        json.dumps([item.to_dict() for item in audit], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _chunk_page(
    text: str,
    *,
    document_id: str,
    source_id: str,
    title: str,
    organization: str | None,
    source_path: str,
    page: int | None,
    allowed_topics: tuple[str, ...],
    chunk_characters: int,
    overlap_characters: int,
) -> list[TextChunk]:
    output: list[TextChunk] = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = min(start + chunk_characters, len(text))
        if end < len(text):
            sentence_break = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if sentence_break > start + chunk_characters // 2:
                end = sentence_break + 1
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunk_id = f"{source_id}-{page or 0:04d}-{chunk_index:04d}"
            output.append(
                TextChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    source_id=source_id,
                    title=title,
                    organization=organization,
                    source_path=source_path,
                    page=page,
                    section=_guess_section(chunk_text),
                    allowed_topics=allowed_topics,
                    text=chunk_text,
                )
            )
            chunk_index += 1
        if end >= len(text):
            break
        start = max(end - overlap_characters, start + 1)
    return output


def _matches_reference_file(path: Path, spec: ReferenceSpec) -> bool:
    if not spec.file_name_patterns:
        return spec.source_id.lower() in path.stem.lower()
    name = path.name
    return any(re.search(pattern, name, flags=re.IGNORECASE) for pattern in spec.file_name_patterns)


def _page_in_ranges(page: int | None, ranges: Sequence[tuple[int, int]]) -> bool:
    if page is None:
        return not ranges
    return any(start <= page <= end for start, end in ranges)


def _clean_text(text: str) -> str:
    normalized = text.replace("\x00", " ").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _guess_section(text: str) -> str | None:
    return _probable_heading(text)


def _probable_heading(text: str) -> str | None:
    for line in text.splitlines()[:12]:
        value = line.strip(" #\t")
        if 3 <= len(value) <= 140 and not value.endswith("."):
            if sum(character.isalpha() for character in value) >= 3:
                return value
    return None
