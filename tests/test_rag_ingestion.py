from pathlib import Path

from eyeai.assistant.ingestion import chunk_documents, discover_documents


def test_markdown_ingestion_and_chunking(tmp_path: Path):
    source = tmp_path / "guidelines"
    source.mkdir()
    document = source / "amd-guideline.md"
    document.write_text(
        "# Review\n\nAMD screening outputs require clinical review. " * 80,
        encoding="utf-8",
    )
    documents = discover_documents(tmp_path)
    chunks = chunk_documents(
        documents,
        root=tmp_path,
        chunk_characters=500,
        overlap_characters=80,
    )
    assert documents == [document]
    assert len(chunks) > 1
    assert all(chunk.document_id for chunk in chunks)
    assert all(chunk.source_path == "guidelines/amd-guideline.md" for chunk in chunks)
