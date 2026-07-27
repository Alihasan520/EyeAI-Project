# EyeAI Frontend Batch 03 — Retinal Analysis Workspace

Version: `0.3.0`

This batch activates the live AI Analysis module against the existing EyeAI Product Backend API 3.2.0. It does not change model weights, RAG assets, or the Kaggle server notebook.

## Added

- Patient and eye selection for retinal analysis.
- Existing-visit selection or automatic creation of a new visit.
- Drag-and-drop JPEG/PNG/WebP fundus upload with local preview and validation.
- Live call to `POST /api/v1/visits/{visit_ref}/analyze?explanation=true`.
- Animated, staged processing UI for validation, quality review, RETFound inference, TTA aggregation, heatmap generation, and result storage.
- Full analysis workspace with:
  - AMD label, model score, threshold, quality state, model version, and TTA disagreement.
  - Original image and heatmap overlay side by side.
  - Peak coordinates, normalized location, dominant region, TTA heatmap similarity, fundus focus, and border focus.
  - Technical review profile and explainability disclaimer.
- Interactive fullscreen image viewer:
  - Zoom, pan, fit/reset, and fullscreen.
  - Freehand annotation layer with color and brush-size controls.
  - Undo, redo, clear, and annotated PNG download.
  - Annotations remain non-destructive and are persisted locally per analysis image.
- Arabic and English translations for the full analysis workflow.
- Responsive light/dark UI for desktop, tablet, and mobile.

## Backend requirements

The already-installed Product Backend API 3.2.0 must expose:

- `GET /api/v1/patients`
- `GET /api/v1/visits`
- `POST /api/v1/patients/{patient_ref}/visits`
- `POST /api/v1/visits/{visit_ref}/analyze?explanation=true`
- `GET /api/v1/patients/{patient_ref}/timeline`
- `/artifacts/{request_id}/original.png`
- `/artifacts/{request_id}/overlay.png`

No new Python backend files are required for this batch.

## Test flow

1. Run the Kaggle demo server and keep the Cloudflare tunnel active.
2. Start the frontend with `npm run dev`.
3. Sign in to the live workspace, not Preview Mode.
4. Create a patient if needed.
5. Open **AI Analysis**.
6. Select a patient and eye.
7. Create a new visit or select an existing visit.
8. Upload a fundus image and run the analysis.
9. Verify original and overlay images, metrics, and technical review profile.
10. Open each image, test zoom/pan, draw annotations, undo/redo, and download the annotated PNG.

## Validation performed

- TypeScript and TSX syntax transpilation for every source file.
- Relative import resolution.
- Translation-key coverage for all new UI copy.
- JSON validation for `package.json`.
- Package version updated to `0.3.0`.

Run `npm run build` locally before committing to verify the full production bundle with installed dependencies.
