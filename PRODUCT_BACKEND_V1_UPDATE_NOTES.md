# EyeAI Product Backend Core V1

This patch extends FastAPI V2 into a persistent clinical-workflow prototype.

## Included

- SQLite development database with SQLAlchemy 2 and PostgreSQL-compatible models.
- One-time admin bootstrap, JWT login, and protected product endpoints.
- Patient records with medical-record-number uniqueness.
- Left/right-eye visits and doctor notes.
- Visit analysis using Run 09 + TTA and optional explainability.
- Persisted predictions, quality metadata, TTA values, and explanation artifacts.
- Patient timeline with model-score delta and neutral trend labels.
- Alerts for positive screening, image-quality review, and significant score increase.
- PDF visit reports containing model metadata and available original/overlay images.
- Dashboard counters and recent alerts.

## Product language

The timeline reports `model score` changes. It does not claim clinical disease progression.
The generated PDF and API responses retain the clinical-confirmation disclaimer.

## Main config

```text
configs/api/product_backend_v1.yaml
```

## Main smoke test

```text
notebooks/12_product_backend_core_v1_kaggle.ipynb
```

## Production note

SQLite is used for development and Kaggle smoke tests. Set `EYEAI_DATABASE_URL` to a
PostgreSQL URL for deployment. Set a strong `EYEAI_JWT_SECRET`; never use the development
secret in production.
