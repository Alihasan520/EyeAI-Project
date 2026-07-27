# Render Frontend Deployment Notes

Render is suitable for the EyeAI frontend.

## Recommended setup

Deploy a React/Vite frontend as a Render **Static Site**. It does not need a GPU and can
call the temporary Kaggle API URL or a future persistent backend URL through HTTPS.

For a full Next.js app that uses server-side rendering or API routes, use a Render
**Web Service** instead. A static export can still use a Static Site.

## Required frontend environment variable

```text
VITE_API_BASE_URL=https://your-eyeai-api.example
```

The backend must include the Render frontend domain in:

```text
EYEAI_ALLOWED_ORIGINS=https://your-frontend.onrender.com
```

## Important separation

- Render frontend: appropriate.
- RETFound + Qwen backend on a free Render service: not appropriate because this stack
  requires a CUDA GPU and large model files.
- Kaggle can remain a temporary demonstration backend, but its session and public tunnel
  URL are temporary.

## Persistence

Do not store patient images, SQLite data, generated reports, or explanations on an
unattached Render web-service filesystem. Use persistent object storage and PostgreSQL
when moving beyond the competition demo.
