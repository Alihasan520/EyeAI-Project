# EyeAI Frontend Batch 01

## Product direction

This batch establishes the EyeAI Retinal Aurora design system and the foundational clinical workspace shell.

## Delivered

- Vector EyeAI brand identity with transparent background.
- Responsive English/Arabic experience.
- RTL/LTR synchronization.
- Light, dark, and system modes.
- Live backend connection testing and runtime URL override.
- JWT login and current-user hydration.
- Preview mode for offline interface review.
- Clinical dashboard using the final backend dashboard contract.
- Service readiness for RETFound, Qwen, approved RAG, and Cloudflare.
- Responsive desktop sidebar and mobile drawer.
- Command palette using Ctrl/Cmd + K.
- Scroll-to-top control.
- Render Static Site configuration.

## Backend compatibility

Designed against EyeAI Product Backend V1.1.2 and its readable display IDs.

## Validation completed in the generation environment

- JSON and YAML parsing.
- TypeScript and TSX syntax transpilation for all source files.
- SVG XML parsing.
- Frontend file-tree and required-file checks.

A full npm build could not be executed in the generation environment because the npm registry was not reachable. Run `npm install && npm run build` locally before the first Git push; any package-resolution issue should be reported with the complete console output.
