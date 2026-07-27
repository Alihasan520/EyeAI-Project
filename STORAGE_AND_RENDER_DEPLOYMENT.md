# EyeAI Storage and Render Deployment

## Current development architecture

- React frontend: local Vite server.
- AI and product API: Kaggle FastAPI through Cloudflare Tunnel.
- Structured records: SQLite inside the active Kaggle workspace.
- Images, explanations, and reports: files inside the active Kaggle workspace.
- Drawing annotations: browser localStorage.

Kaggle workspace storage is temporary. It is suitable for functional testing, not persistent clinical records.

## Why clinical data is not stored in browser localStorage

Browser localStorage is not an appropriate database for protected patient information. It is tied to one browser profile, easy to clear, has small capacity, lacks safe multi-user concurrency, and provides no reliable backup or server-side access control.

## Local persistent development

A fully local data store requires the Product API to run on the local computer. Its environment can use:

```env
EYEAI_DATABASE_URL=sqlite:///./storage/eyeai.db
EYEAI_EXPLANATION_OUTPUT_DIR=./storage/explanations
EYEAI_REPORTS_OUTPUT_DIR=./storage/reports
```

With the current combined Backend, running only the frontend locally does not move the server database from Kaggle to the computer.

## Recommended final architecture

1. Render Static Site
   - React/Vite frontend.
2. Render Product API Web Service
   - Authentication, patients, visits, alerts, conversations, and reports.
3. Render Postgres
   - Structured relational data.
4. File storage
   - Option A: Render persistent disk on a paid Web Service.
   - Option B: S3-compatible object storage such as Cloudflare R2 (recommended when minimizing cost).
5. Kaggle AI Engine through a fixed Cloudflare Named Tunnel
   - RETFound, Heatmap, Qwen, and RAG only.

The Product API sends the minimum required image/context to the AI Engine and stores the returned result persistently. This prevents loss of patients and reports when a Kaggle session ends.

## Render-only limitation

A Render Static Site cannot act as persistent file storage. Render services use an ephemeral filesystem unless a paid persistent disk is attached. Render Postgres should hold structured data, not large image and PDF files.
