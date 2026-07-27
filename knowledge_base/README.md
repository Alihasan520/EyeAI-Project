# EyeAI Approved Medical Knowledge Base

The repository stores policies and ingestion code, not copyrighted source PDFs.

## Required PDF Dataset

Upload the downloaded documents to a private Kaggle Dataset. Supported names include:

```text
agerelated-macular-degeneration-pdf-1837691334853.pdf
Age-Related Macular Degeneration PPP.pdf
```

The optional Beckman classification paper can be added later.

## Build process

`notebooks/14_build_eyeai_rag_index_kaggle.ipynb` performs:

1. Filename matching from `reference_manifest.yaml`.
2. Page extraction.
3. Allowed-topic and excluded-heading audit.
4. Audit review files (`reference_audit.json` and `reference_audit.csv`).
5. Chunking of selected pages only.
6. CPU embeddings and FAISS index creation.
7. Retrieval smoke testing.

The final assistant never receives entire PDFs and never creates reference metadata.
Citation numbers, titles, sections, and pages come from the backend index.
