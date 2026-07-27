#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send one fundus image to the EyeAI explanation endpoint."
    )
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--url", default="http://127.0.0.1:8000/predict-with-explanation"
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    with httpx.Client(timeout=args.timeout) as client:
        with image_path.open("rb") as handle:
            response = client.post(
                args.url,
                files={"file": (image_path.name, handle, _content_type(image_path))},
            )
        response.raise_for_status()
        payload = response.json()
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            base_url = args.url.split("/predict-with-explanation", 1)[0]
            for name, artifact in payload["explanation"]["artifacts"].items():
                if name == "metadata":
                    continue
                artifact_response = client.get(base_url + artifact["url"])
                artifact_response.raise_for_status()
                suffix = Path(artifact["relative_path"]).suffix
                (output_dir / f"{name}{suffix}").write_bytes(artifact_response.content)


def _content_type(path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(path.suffix.lower(), "application/octet-stream")


if __name__ == "__main__":
    main()
