# FastAPI V2 — Explainability Update

## Purpose

This update extends the frozen Run 09 + horizontal-flip TTA service with a transformer explanation endpoint. No training or checkpoint modification occurs.

## New endpoint

```text
POST /predict-with-explanation
```

The endpoint returns the normal V1 prediction contract plus:

- Gradient-weighted patch attribution metadata.
- Original image URL.
- Processed full-fundus image URL.
- Heatmap URL.
- Overlay URL.
- Explanation metrics and warnings.
- Re-encoded metadata JSON.

## Explanation method

The implementation captures the final RETFound transformer block and computes gradient-weighted patch attribution for the predicted class. Original and horizontally flipped TTA maps are aligned to the original orientation and averaged. Attribution outside the processed fundus field is masked before rendering.

This is an interpretability aid, not lesion segmentation or independent clinical evidence.

## Quality checks for explanations

The response reports:

- Fundus attribution focus.
- Border attribution focus.
- TTA map similarity.
- Normalized attribution entropy.
- Peak attribution location.

Warnings can include low fundus focus, high border focus, low TTA consistency, diffuse attribution, or empty attribution.

## Artifact storage

Artifacts are written under the configured directory using one UUID directory per request. Uploaded images are decoded and re-encoded as PNG, so source EXIF metadata is not copied.

Default development structure:

```text
artifacts/explanations/<request-id>/
├── original.png
├── processed.png
├── heatmap.png
├── overlay.png
└── metadata.json
```

Production retention and access control are deferred to the deployment-hardening stage.

## Kaggle validation

Run:

```text
notebooks/11_fastapi_ai_engine_v2_explainability_kaggle.ipynb
```

The notebook compares `/predict` and `/predict-with-explanation`, verifies matching probabilities, downloads all generated artifacts through the API, displays them, and confirms invalid uploads remain rejected.
