# EyeAI FastAPI deployment

Mount the exported model package at `/models/run09_tta_v1`.

```bash
docker build -f deploy/fastapi/Dockerfile -t eyeai-api:1.0 .

docker run --rm -p 8000:8000 \
  -v /absolute/path/to/run09_tta_v1:/models/run09_tta_v1:ro \
  eyeai-api:1.0
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

The provided image is a CPU deployment baseline. GPU deployment requires a CUDA-compatible PyTorch image and runtime.
