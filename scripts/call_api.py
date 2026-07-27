#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one fundus image to the EyeAI API.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/predict")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    with image_path.open("rb") as handle:
        response = httpx.post(
            args.url,
            files={"file": (image_path.name, handle, _content_type(image_path))},
            timeout=args.timeout,
        )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(suffix, "application/octet-stream")


if __name__ == "__main__":
    main()
