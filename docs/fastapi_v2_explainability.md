# EyeAI FastAPI V2 Explainability

## Run locally

```bash
export EYEAI_MODEL_PACKAGE_DIR="/path/to/run09_tta_v1"
export EYEAI_EXPLANATION_OUTPUT_DIR="/path/to/eyeai-artifacts"
python -u scripts/run_api.py --config configs/api/fastapi_v2.yaml
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Request an explanation

```bash
python scripts/call_explanation_api.py \
  --image "/path/to/fundus.jpg" \
  --output-dir "/path/to/downloaded-explanation"
```

## Interpretation contract

The heatmap identifies image regions that contributed to the selected model class under gradient-weighted patch attribution. It must not be described as a lesion mask, anatomical annotation, disease location ground truth, or proof of clinical causality.

## Artifact privacy

The prototype stores re-encoded images under UUID directories. Do not expose the artifact mount publicly without authentication, authorization, retention limits, encryption, and audit logging.
