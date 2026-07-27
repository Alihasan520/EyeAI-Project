# FastAPI AI Engine V1

This patch adds the first deployable API around the frozen Run 09 + horizontal-flip TTA model package.

## Endpoints

- `GET /health`
- `GET /model-info`
- `POST /predict`

## Prediction output

The API returns the AMD probability, threshold decision, original and horizontal-flip probabilities, model version, latency, quality warnings, and a clinical-review disclaimer.

## Initial quality checks

- Input resolution.
- Fundus-field coverage and black fraction.
- Possible overexposure and glare.
- Possible underexposure.
- Low contrast.
- Possible blur.
- TTA disagreement.

The quality checks are engineering heuristics and are not a validated medical image-quality model.

## Runtime

Set `EYEAI_MODEL_PACKAGE_DIR` to the exported `run09_tta_v1` directory, then run:

```bash
python -u scripts/run_api.py --config configs/api/fastapi_v1.yaml
```
