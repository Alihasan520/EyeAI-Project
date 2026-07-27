from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"Expected a YAML mapping: {path}")
    return data


def write_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_torch_checkpoint(path: str | Path, map_location: str | torch.device = "cpu") -> dict[str, Any]:
    path = Path(path)
    try:
        checkpoint = torch.load(path, map_location=map_location, weights_only=False)
    except TypeError:
        checkpoint = torch.load(path, map_location=map_location)
    if not isinstance(checkpoint, dict):
        raise TypeError(f"Checkpoint is not a dictionary: {path}")
    return checkpoint


def extract_model_state_dict(checkpoint: dict[str, Any]) -> dict[str, torch.Tensor]:
    for key in ("model_state_dict", "model", "state_dict"):
        value = checkpoint.get(key)
        if isinstance(value, dict) and value:
            state_dict = value
            break
    else:
        state_dict = checkpoint

    cleaned: dict[str, torch.Tensor] = {}
    for name, value in state_dict.items():
        if not torch.is_tensor(value):
            continue
        clean_name = str(name)
        if clean_name.startswith("module."):
            clean_name = clean_name[len("module."):]
        cleaned[clean_name] = value.detach().cpu().contiguous()

    if not cleaned:
        raise RuntimeError("No tensors were found in the trained checkpoint.")
    return cleaned


def file_sha256(path: str | Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def directory_manifest(root: str | Path) -> list[dict[str, Any]]:
    root = Path(root)
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        records.append(
            {
                "path": str(path.relative_to(root)),
                "size_bytes": int(path.stat().st_size),
                "sha256": file_sha256(path),
            }
        )
    return records


def _copy_optional(source: str | Path | None, destination: Path) -> bool:
    if not source:
        return False
    source_path = Path(source)
    if not source_path.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    return True


def export_model_package(
    *,
    trained_checkpoint: str | Path,
    package_config_path: str | Path,
    output_dir: str | Path,
    tta_summary_path: str | Path | None = None,
    training_summary_path: str | Path | None = None,
    source_training_config_path: str | Path | None = None,
    source_git_commit: str | None = None,
) -> Path:
    trained_checkpoint = Path(trained_checkpoint)
    package_config_path = Path(package_config_path)
    output_dir = Path(output_dir)

    if not trained_checkpoint.is_file():
        raise FileNotFoundError(f"Trained checkpoint was not found: {trained_checkpoint}")
    if not package_config_path.is_file():
        raise FileNotFoundError(f"Package config was not found: {package_config_path}")

    package_config = load_yaml(package_config_path)
    checkpoint = load_torch_checkpoint(trained_checkpoint, map_location="cpu")
    state_dict = extract_model_state_dict(checkpoint)

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_name = str(package_config["package"].get("checkpoint_output_name", "model.pth"))
    inference_checkpoint_path = output_dir / checkpoint_name

    inference_checkpoint = {
        "format_version": 1,
        "model_state_dict": state_dict,
        "model_version": package_config["package"]["model_version"],
        "architecture": package_config["model"],
        "preprocessing": package_config["preprocessing"],
        "inference": package_config["inference"],
        "source": {
            "checkpoint_name": trained_checkpoint.name,
            "source_epoch": checkpoint.get("epoch"),
            "source_image_size": checkpoint.get("image_size", package_config["model"]["image_size"]),
            "source_selection_metric": checkpoint.get("selection_metric"),
            "source_selection_score": checkpoint.get("selection_score"),
            "source_best_threshold": checkpoint.get("best_threshold"),
        },
    }
    torch.save(inference_checkpoint, inference_checkpoint_path)

    shutil.copy2(package_config_path, output_dir / "model_config.yaml")
    write_json(output_dir / "preprocessing.json", package_config["preprocessing"])
    write_json(output_dir / "threshold.json", package_config["inference"])
    write_json(output_dir / "labels.json", package_config["model"]["class_names"])

    metrics = package_config.get("validation", {})
    if tta_summary_path and Path(tta_summary_path).is_file():
        metrics = dict(metrics)
        metrics["source_tta_summary"] = json.loads(Path(tta_summary_path).read_text(encoding="utf-8"))
    write_json(output_dir / "metrics.json", metrics)

    copied_sources: dict[str, bool] = {}
    copied_sources["tta_summary"] = _copy_optional(tta_summary_path, output_dir / "source_records" / "run09_tta_summary.json")
    copied_sources["training_summary"] = _copy_optional(
        training_summary_path,
        output_dir / "source_records" / "run09_training_summary.json",
    )
    copied_sources["training_config"] = _copy_optional(
        source_training_config_path,
        output_dir / "source_records" / "run09_training_config.yaml",
    )

    version_payload = {
        "package_name": package_config["package"]["package_name"],
        "model_version": package_config["package"]["model_version"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_git_commit": source_git_commit,
        "source_checkpoint": str(trained_checkpoint),
        "source_checkpoint_sha256": file_sha256(trained_checkpoint),
        "inference_checkpoint": checkpoint_name,
        "copied_source_records": copied_sources,
    }
    write_json(output_dir / "version.json", version_payload)

    limitations = package_config.get("limitations", [])
    fixed_metrics = package_config.get("validation", {}).get("fixed_split_tta", {})
    oof_metrics = package_config.get("validation", {}).get("robust_oof_reference", {})
    model_card = f"""# EyeAI RETFound Run 09 + TTA Model Card

## Model identity

- Version: `{package_config['package']['model_version']}`
- Architecture: {package_config['model']['architecture']}
- Task: Binary AMD screening support
- Input: RGB fundus image, resized to {package_config['model']['image_size']} × {package_config['model']['image_size']}
- Inference: Original image + horizontal flip; mean AMD probability
- Decision threshold: {package_config['inference']['threshold']}

## Fixed-split TTA validation

- Macro F1: {fixed_metrics.get('macro_f1')}
- Average Precision: {fixed_metrics.get('average_precision')}
- ROC-AUC: {fixed_metrics.get('auc')}
- AMD precision: {fixed_metrics.get('precision_amd')}
- AMD recall: {fixed_metrics.get('recall_amd')}
- Specificity: {fixed_metrics.get('specificity')}

## Robustness reference

- OOF count: {oof_metrics.get('count')}
- OOF Macro F1: {oof_metrics.get('macro_f1')}
- OOF Average Precision: {oof_metrics.get('average_precision')}
- OOF ROC-AUC: {oof_metrics.get('auc')}

## Preprocessing contract

Outer black borders are cropped, the image is square-padded with black pixels when needed, resized with bicubic interpolation, converted to RGB, and normalized with ImageNet mean and standard deviation. CLAHE, fixed gamma correction, and ROI crops are not used.

## Intended use

This package supports an AI-assisted AMD screening and workflow prototype. It is not a standalone diagnosis and requires clinical review.

## Known limitations

""" + "\n".join(f"- {item}" for item in limitations) + "\n"
    (output_dir / "model_card.md").write_text(model_card, encoding="utf-8")

    readme = """# EyeAI Model Package

This directory is the frozen Run 09 + horizontal-flip TTA inference artifact.

Required runtime files:

- `model.pth`: inference-only model state and architecture contract.
- `model_config.yaml`: complete package configuration.
- `preprocessing.json`: image preprocessing contract.
- `threshold.json`: TTA variants, aggregation, and decision threshold.
- `labels.json`: class mapping.
- `metrics.json`: fixed-split and robustness metrics.
- `model_card.md`: intended use and limitations.
- `version.json`: provenance and source hash.
- `artifact_manifest.json`: package file hashes.

Use `scripts/predict_model_package.py` for a standalone prediction smoke test.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    manifest = directory_manifest(output_dir)
    write_json(output_dir / "artifact_manifest.json", manifest)
    return output_dir
