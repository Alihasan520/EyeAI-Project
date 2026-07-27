#!/usr/bin/env python
from __future__ import annotations

import argparse

import uvicorn

from eyeai.api.config import ApiSettings
from eyeai.api.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the EyeAI FastAPI inference engine.")
    parser.add_argument("--config", default="configs/api/fastapi_v1.yaml")
    parser.add_argument("--model-package", default=None)
    parser.add_argument("--device", default=None, choices=[None, "auto", "cpu", "cuda"])
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    settings = ApiSettings.from_yaml(
        args.config,
        model_package_override=args.model_package,
        device_override=args.device,
    )
    app = create_app(settings)
    uvicorn.run(
        app,
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
