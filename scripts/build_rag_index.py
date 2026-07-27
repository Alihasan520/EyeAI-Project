from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from eyeai.assistant.ingestion import (
    audit_manifest_documents,
    chunk_documents,
    chunk_manifest_documents,
    discover_documents,
    load_reference_manifest,
    write_audit,
    write_chunks,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the local EyeAI FAISS RAG index.")
    parser.add_argument("--documents-root", type=Path, required=True)
    parser.add_argument("--embedding-model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--chunk-characters", type=int, default=1500)
    parser.add_argument("--overlap-characters", type=int, default=180)
    parser.add_argument("--batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    selected_documents: list[Path]
    audit_payload: list[dict] = []
    if args.reference_manifest:
        specs = load_reference_manifest(args.reference_manifest)
        audit, matched_files = audit_manifest_documents(
            documents_root=args.documents_root,
            reference_specs=specs,
        )
        write_audit(audit, args.output_dir / "reference_audit.json")
        _write_audit_csv(audit, args.output_dir / "reference_audit.csv")
        audit_payload = [item.to_dict() for item in audit]
        selected_documents = sorted(set(matched_files.values()))
        selected_counts = {
            spec.source_id: sum(1 for item in audit if item.source_id == spec.source_id and item.selected)
            for spec in specs
        }
        required_without_pages = [
            spec.source_id
            for spec in specs
            if spec.required and selected_counts.get(spec.source_id, 0) == 0
        ]
        if required_without_pages:
            raise RuntimeError(
                "No approved pages were selected for required references: "
                + ", ".join(required_without_pages)
                + ". Review reference_audit.csv and adjust reference_manifest.yaml."
            )
        if args.audit_only:
            summary = {
                "audit_only": True,
                "reference_count": len(selected_documents),
                "selected_page_count": sum(1 for item in audit if item.selected),
                "excluded_page_count": sum(1 for item in audit if not item.selected),
                "audit_json": str(args.output_dir / "reference_audit.json"),
                "audit_csv": str(args.output_dir / "reference_audit.csv"),
            }
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return
        chunks = chunk_manifest_documents(
            documents_root=args.documents_root,
            reference_specs=specs,
            audit_records=audit,
            matched_files=matched_files,
            chunk_characters=args.chunk_characters,
            overlap_characters=args.overlap_characters,
        )
    else:
        selected_documents = [
            path
            for path in discover_documents(args.documents_root)
            if path.name.lower() != "readme.md"
        ]
        if not selected_documents:
            raise FileNotFoundError(
                f"No approved reference documents were found under {args.documents_root}."
            )
        chunks = chunk_documents(
            selected_documents,
            root=args.documents_root,
            chunk_characters=args.chunk_characters,
            overlap_characters=args.overlap_characters,
        )

    if not chunks:
        raise RuntimeError("No text chunks were produced from the approved reference sections.")

    try:
        import faiss
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Install requirements-assistant-kaggle.txt before building the RAG index."
        ) from exc

    model = SentenceTransformer(
        str(args.embedding_model),
        device=args.device,
        local_files_only=True,
    )
    passages = [chunk.text for chunk in chunks]
    embeddings = model.encode(
        passages,
        batch_size=args.batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    ).astype(np.float32)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, str(args.output_dir / "index.faiss"))
    write_chunks(chunks, args.output_dir / "chunks.json")
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "documents_root": str(args.documents_root),
        "reference_manifest": str(args.reference_manifest) if args.reference_manifest else None,
        "document_count": len(selected_documents),
        "selected_page_count": sum(1 for item in audit_payload if item.get("selected")),
        "chunk_count": len(chunks),
        "embedding_model_dir": str(args.embedding_model),
        "embedding_dimension": int(embeddings.shape[1]),
        "index_type": "faiss.IndexFlatIP",
        "normalized_embeddings": True,
        "source_ids": sorted({chunk.source_id for chunk in chunks}),
        "documents_sha256": {
            str(path.relative_to(args.documents_root)): _sha256(path)
            for path in selected_documents
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


def _write_audit_csv(audit, path: Path) -> None:
    rows = [item.to_dict() for item in audit]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["matched_include_patterns"] = " | ".join(row["matched_include_patterns"])
            row["matched_exclude_patterns"] = " | ".join(row["matched_exclude_patterns"])
            row["allowed_topics"] = " | ".join(row["allowed_topics"])
            writer.writerow(row)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
