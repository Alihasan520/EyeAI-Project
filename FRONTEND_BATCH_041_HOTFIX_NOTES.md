# EyeAI Frontend Batch 04.1 Hotfix

## Fixes

- Activates the real Clinical Copilot and Reports routes in the consolidated frontend.
- Adds the complete Clinical Alerts page with filtering, acknowledgement, and direct navigation to the linked analysis.
- Fixes the image review modal that could remain on `Loading clinical image...`.
  - Clinical images are now fetched as authenticated Blob objects.
  - Cross-origin canvas restrictions no longer block zoom, drawing, or PNG export.
  - A 30-second failure state replaces an indefinite loading state.
- Adds a frontend version marker (`0.4.1`) under System and a verification command:

```bash
npm run verify:batch
```

## Required installation behavior

This is a consolidated replacement package. Extract it at the repository root and overwrite the existing `Frontend` files. Restart Vite with `--force` and hard-refresh the browser.

## Storage note

This hotfix does not move clinical records into browser localStorage. Browser localStorage remains limited to UI preferences, the active API URL, the access token, and temporary annotation strokes. Patient data, visits, analyses, conversations, and reports remain server-side.

See `STORAGE_AND_RENDER_DEPLOYMENT.md` for the safe local and Render architecture.
