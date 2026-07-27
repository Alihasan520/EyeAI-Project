# EyeAI Clinical Frontend

Frontend application for the EyeAI Clinical Intelligence Platform.

## Included in this batch

- Original EyeAI retinal-aurora SVG identity and favicon.
- Responsive login experience.
- Live FastAPI health and authentication integration.
- Dynamic Cloudflare/API URL configuration stored in the browser.
- Optional preview mode for interface development without a running backend.
- Professional dashboard connected to `/api/v1/dashboard`.
- RETFound, Qwen, RAG, and public API service-status cards.
- Light, dark, and system appearance modes.
- Arabic and English switching with RTL/LTR layout synchronization.
- Responsive sidebar, mobile drawer, top navigation, command palette, and scroll-to-top control.
- Render Static Site Blueprint with SPA rewrite.
- Motion and loading states with reduced-motion accessibility support.

## Requirements

- Node.js 22.12 or later.
- EyeAI Product Backend V1.1.2 for live data.

## Local setup

```bash
cd Frontend
cp .env.example .env.local
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The default backend URL is:

```text
http://127.0.0.1:8000
```

You can change it from the login screen or the top navigation without rebuilding the frontend. This is useful while Cloudflare Quick Tunnel produces a different URL for each Kaggle session.

## Environment variables

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ENABLE_PREVIEW_MODE=true
```

For the final Render deployment:

```env
VITE_API_BASE_URL=https://api.your-fixed-domain.example
VITE_ENABLE_PREVIEW_MODE=false
```

Do not place private keys or clinical secrets in Vite environment variables. Vite values are included in the browser bundle.

## Backend endpoints used in Batch 01

```text
GET  /health
POST /api/v1/auth/login
GET  /api/v1/auth/me
GET  /api/v1/dashboard
GET  /api/v1/assistant/status
```

## Render deployment

### Manual Static Site setup

- Root Directory: `Frontend`
- Build Command: `npm install && npm run build`
- Publish Directory: `dist`
- Node Version: `22.16.0`

Add an SPA rewrite:

```text
Source:      /*
Destination: /index.html
Action:      Rewrite
```

You may also use `Frontend/render.yaml` as a Render Blueprint file.

## CORS reminder

After Render provides the final site URL, add it to the backend notebook's allowed origins:

```python
RENDER_FRONTEND_URL = "https://your-eyeai-site.onrender.com"
```

Then restart the Kaggle FastAPI server.

## Preview mode

Preview mode is intended only for interface development. It provides sample dashboard data and does not create clinical records or call the AI services.

Disable it for the final deployment:

```env
VITE_ENABLE_PREVIEW_MODE=false
```

## Batch 02 — Clinical records and protected access

Batch 02 adds the first-administrator setup flow, editable clinician profile and password, administrator-managed user accounts, patient registration, patient profiles, eye-specific visits, and a longitudinal clinical timeline.

The live features require Product Backend API version 3.2.0 or later. If the database is empty, the login page displays **Initialize EyeAI workspace** so the first administrator can choose their own name, email address, and password.

## Batch 03: live retinal analysis

The AI Analysis page now connects to the protected visit-analysis endpoint and displays the original image and model-influence overlay. The fullscreen viewer supports zoom, pan, and a local non-destructive annotation layer. See `FRONTEND_BATCH_03_UPDATE_NOTES.md` for the complete test flow.

## Batch 04: grounded Clinical Copilot and PDF reports

Batch 04 activates the Clinical Assistant and Reports modules. It requires Product Backend API version 3.3.0 or later.

The assistant supports patient-, eye-, and visit-scoped conversations, structured evidence panels, approved-reference metadata, and an animated multi-stage thinking indicator.

The reports workspace can generate an English A4 PDF containing the EyeAI identity, readable patient and visit references, model score and threshold, original fundus image, heatmap overlay, deterministic heatmap metrics, clinician notes, approved references, model version, page numbering, and clinical safety language.

Live endpoints added in this batch:

```text
GET  /api/v1/reports
POST /api/v1/visits/{visit_ref}/reports
POST /api/v1/visits/{visit_ref}/report-draft
POST /api/v1/patients/{patient_ref}/assistant/conversations
GET  /api/v1/patients/{patient_ref}/assistant/conversations
GET  /api/v1/assistant/conversations/{conversation_ref}/messages
POST /api/v1/assistant/conversations/{conversation_ref}/messages
```
