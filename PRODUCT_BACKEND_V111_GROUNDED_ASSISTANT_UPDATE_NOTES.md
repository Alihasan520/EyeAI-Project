# Product Backend Core V1.1.1 Update Notes

## Clinical grounding fixes

- Added a canonical AMD terminology contract for Arabic and English.
- Corrected the Arabic expansion to `التنكس البقعي المرتبط بالعمر`.
- Added a post-generation grounding validator.
- Added a deterministic context-only fallback for unsupported output.
- Prevented no-RAG responses from adding family history, environmental factors, prior treatments, unrelated infections, risk factors, tests, or therapies from model memory.
- Replaced model-generated review recommendations with a fixed safe review statement.
- Added grounding metadata and explicit source status to every assistant response.
- Added the limitation that a probability is not a disease-severity score.

## Kaggle GPU memory improvements

- Reduced Qwen GPU placement cap from 6 GiB to 5 GiB.
- Reduced maximum input context from 4096 to 3072 tokens.
- Reduced maximum answer length from 384 to 256 tokens.
- Reduced stored prompt history from eight to four messages.
- Reduced doctor-note context from 3000 to 1600 characters.
- Switched generation to deterministic decoding with temperature `0.0`.
- Added explicit generation tensor cleanup and CUDA cache release.
- Added CUDA cache release after explanation requests.
- Added expandable CUDA allocator segments in Notebook 15.
- Added GPU allocation, reservation, and peak-memory fields to assistant status.

## Notebook improvements

- RAG remains disabled by default.
- The embedding model and RAG index are no longer required when RAG is disabled.
- Model discovery supports both Notebook Outputs and Kaggle Datasets.
- The smoke test rejects the previously observed unsupported Arabic phrases.
- The smoke test verifies context-only grounding and reports peak CUDA memory.

## Verification

- Python and notebook syntax validation completed.
- Full integrated test suite: `22 passed`.
