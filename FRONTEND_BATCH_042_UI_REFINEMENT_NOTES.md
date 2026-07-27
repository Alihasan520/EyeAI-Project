# EyeAI Frontend Batch 04.2 — UI Refinement

This update focuses on three clinician-facing refinements:

1. The Clinical Copilot receives substantially more horizontal and vertical space on common laptop screens. The evidence workspace moves below the conversation until very wide screens are available.
2. Arabic typography uses Noto Sans Arabic with local fallbacks, and assistant/user messages use automatic text direction for mixed Arabic and English content.
3. The clinical image viewer is replaced by a simpler internal viewer. It fetches protected files as authenticated blobs, displays them through a normal image element, and adds a lightweight SVG annotation layer with zoom, pan, pen, undo, clear, fullscreen, retry, and annotated PNG download.

No external image editor is used. Annotations remain a browser-local review layer and do not modify the clinical source image.
