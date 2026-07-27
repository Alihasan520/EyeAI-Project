FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EYEAI_API_CONFIG=/app/configs/api/fastapi_v1.yaml \
    EYEAI_MODEL_PACKAGE_DIR=/models/run09_tta_v1 \
    EYEAI_DEVICE=cpu

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
COPY src ./src
COPY configs ./configs
COPY scripts ./scripts

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-u", "scripts/run_api.py", "--host", "0.0.0.0", "--port", "8000"]
