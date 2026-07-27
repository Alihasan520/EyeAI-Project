# EyeAI Product Backend V1.1.2

The backend is ready to support a frontend MVP with patients, visits, image analysis,
explanations, alerts, PDF reports, readable IDs, and a grounded local clinical assistant.

## Assistant response contract

```json
{
  "answer": "Plain-language grounded answer with inline citations [1].",
  "question_route": "result_interpretation",
  "clinical_interpretation": [],
  "patient_evidence": [],
  "heatmap_spatial": {},
  "technical_review_profile": {},
  "references": [],
  "limitations": [],
  "suggested_review": "...",
  "grounding": {
    "fallback_used": false,
    "warnings": [],
    "knowledge_scope": "patient_context_and_approved_rag"
  },
  "source_status": "2 approved RAG reference excerpt(s) were used."
}
```

The LLM generates only the `answer` text. Every other field is calculated or assembled
by the backend.

## Heatmap coordinate system

- Origin: top-left of the processed image.
- `x` increases from left to right.
- `y` increases from top to bottom.
- Spatial descriptions use deterministic 3x3 image regions.
- No anatomical claim is produced from coordinates alone.

## RAG workflow

1. Put NICE and AAO PDFs in a private Kaggle Dataset.
2. Run Notebook 14.
3. Review `reference_audit.csv`.
4. Build and save `eyeai_rag_index/v2`.
5. Attach the index to Notebook 15 and enable RAG.

The reference manifest prevents treatment-focused pages from entering the index and
limits retrieval to approved classification, evaluation, diagnosis, monitoring, and
clinical-limitation topics.

## Frontend-facing environment variables

```text
EYEAI_ALLOWED_ORIGINS=https://your-frontend.onrender.com,http://localhost:5173
EYEAI_JWT_SECRET=<secure-secret>
EYEAI_DATABASE_URL=<persistent-database-url>
EYEAI_MODEL_PACKAGE_DIR=<run09-package-path>
EYEAI_ASSISTANT_MODEL_DIR=<qwen-model-path>
EYEAI_RAG_ENABLED=true
EYEAI_RAG_INDEX_DIR=<rag-index-path>
EYEAI_RAG_EMBEDDING_MODEL_DIR=<embedding-model-path>
```
