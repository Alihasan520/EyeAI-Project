# Product Backend Core V1.1 Update Notes

## Added

- Readable display references while preserving UUID primary keys.
- API route resolution by UUID or readable reference.
- Local Qwen3 4B assistant provider with lazy 4-bit loading.
- Shared GPU serialization between RETFound and Qwen.
- De-identified same-eye patient context snapshots.
- Persistent assistant conversations and messages.
- Optional local FAISS RAG with approved references and deterministic citations.
- Visit summary and report-draft endpoints.
- Safe refusal for treatment, medication, and dosage requests.
- Qwen model preparation, RAG indexing, and integrated Kaggle smoke-test notebooks.

## Resource policy

- RETFound remains preloaded.
- Qwen loads only on the first chat request.
- Qwen is limited to 4-bit weights and a short context window.
- RAG query embeddings run on CPU.
- RETFound and Qwen GPU operations do not run concurrently.
