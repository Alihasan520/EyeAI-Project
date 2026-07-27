from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


class ExplanationArtifactStore:
    def __init__(self, root: str | Path, url_prefix: str = "/artifacts") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        prefix = "/" + str(url_prefix).strip("/")
        self.url_prefix = prefix if prefix != "/" else "/artifacts"

    def save(
        self,
        *,
        request_id: str,
        original: Image.Image,
        processed: Image.Image,
        heatmap: Image.Image,
        overlay: Image.Image,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if not request_id or any(character not in "0123456789abcdef-" for character in request_id.lower()):
            raise ValueError("Invalid explanation request identifier.")

        destination = self.root / request_id
        destination.mkdir(parents=True, exist_ok=False)

        image_payload = {
            "original": ("original.png", original.convert("RGB")),
            "processed": ("processed.png", processed.convert("RGB")),
            "heatmap": ("heatmap.png", heatmap.convert("RGB")),
            "overlay": ("overlay.png", overlay.convert("RGB")),
        }

        artifacts: dict[str, Any] = {}
        for key, (filename, image) in image_payload.items():
            path = destination / filename
            image.save(path, format="PNG", optimize=True)
            artifacts[key] = {
                "url": f"{self.url_prefix}/{request_id}/{filename}",
                "relative_path": f"{request_id}/{filename}",
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }

        metadata_path = destination / "metadata.json"
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False, default=_json_default),
            encoding="utf-8",
        )
        artifacts["metadata"] = {
            "url": f"{self.url_prefix}/{request_id}/metadata.json",
            "relative_path": f"{request_id}/metadata.json",
            "sha256": _sha256(metadata_path),
            "size_bytes": metadata_path.stat().st_size,
        }
        return artifacts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")
