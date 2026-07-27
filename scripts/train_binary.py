#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from eyeai.config import load_yaml
from eyeai.data.prepare_hyamd import prepare_hyamd
from eyeai.training.train_binary import train_binary_model
from eyeai.utils.seed import set_seed


def _log(message: str):
    print(message, flush=True)


def _resolve_config_path(config: str) -> Path:
    path = Path(config)
    if path.exists():
        return path
    if str(path).endswith("."):
        alternative = Path(str(path).rstrip("."))
        if alternative.exists():
            _log(f"Warning: config path ended with a dot. Using: {alternative}")
            return alternative
    raise FileNotFoundError(f"Config file not found: {path}")


def _format_fold_value(value, fold: int | None):
    if isinstance(value, str):
        return value.format(fold=fold) if "{fold}" in value else value
    if isinstance(value, dict):
        return {key: _format_fold_value(item, fold) for key, item in value.items()}
    if isinstance(value, list):
        return [_format_fold_value(item, fold) for item in value]
    return value


def _apply_fold_overrides(cfg: dict, fold: int | None) -> dict:
    if fold is None:
        return cfg
    cfg = _format_fold_value(cfg, fold)

    run_cfg = cfg.setdefault("run", {})
    run_cfg["fold"] = int(fold)
    run_cfg["seed"] = int(run_cfg.get("seed", 42)) + int(fold)
    fold_checkpoint = cfg.get("training", {}).get("initial_checkpoint_fold")
    if fold_checkpoint:
        cfg["training"]["initial_checkpoint"] = fold_checkpoint
    model_name = str(cfg["model"]["name"])
    if not model_name.endswith(f"_fold{fold}"):
        cfg["model"]["name"] = f"{model_name}_fold{fold}"

    for key in ["checkpoint_dir", "log_dir", "prediction_dir"]:
        base = Path(cfg["outputs"][key])
        if base.name != f"fold_{fold}":
            cfg["outputs"][key] = str(base / f"fold_{fold}")
    return cfg


def _resolve_dataset_root(data_cfg: dict, cli_root: str | None) -> Path:
    candidates = []
    if cli_root:
        candidates.append(Path(cli_root))
    if os.environ.get("EYEAI_DATASET_ROOT"):
        candidates.append(Path(os.environ["EYEAI_DATASET_ROOT"]))
    if data_cfg.get("prepared_dataset_dir"):
        candidates.append(Path(data_cfg["prepared_dataset_dir"]))
    for item in data_cfg.get("prepared_dataset_fallback_dirs", []) or []:
        candidates.append(Path(item))

    for candidate in candidates:
        if (candidate / "dataset_summary.json").exists() and (candidate / "manifests").exists():
            return candidate

    checked = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError(
        "Prepared EyeAI dataset root was not found. Checked:\n"
        f"{checked}\n"
        "Set --data-root or EYEAI_DATASET_ROOT."
    )


def _read_prepared_manifest(root: Path, relative_path: str) -> pd.DataFrame:
    path = root / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prepared manifest not found: {path}")
    dataframe = pd.read_csv(path, dtype={"patient_id": str, "image_id": str})
    required = {"relative_image_path", "binary_label", "patient_id", "dataset_source"}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        raise RuntimeError(f"Manifest {path} is missing columns: {missing}")

    missing_images = [
        value for value in dataframe["relative_image_path"].astype(str)
        if not (root / value).exists()
    ]
    if missing_images:
        raise RuntimeError(f"Manifest {path} references missing images. Examples: {missing_images[:10]}")
    return dataframe


def _validate_train_val(train_df: pd.DataFrame, val_df: pd.DataFrame):
    val_sources = set(val_df["dataset_source"].astype(str).str.lower())
    if val_sources != {"hyamd"}:
        raise RuntimeError(f"Primary validation must contain HYAMD only, found: {sorted(val_sources)}")

    external_val = val_df[val_df.get("is_external", False).astype(bool)] if "is_external" in val_df.columns else pd.DataFrame()
    if not external_val.empty:
        raise RuntimeError("External images were found in primary HYAMD validation.")

    train_hyamd = train_df[train_df["dataset_source"].astype(str).str.lower() == "hyamd"]
    train_patients = set(train_hyamd["patient_id"].astype(str))
    val_patients = set(val_df["patient_id"].astype(str))
    overlap = train_patients & val_patients
    if overlap:
        raise RuntimeError(f"Patient leakage detected between train and validation: {sorted(overlap)[:20]}")


def _validate_external_validation(train_df: pd.DataFrame, external_val_df: pd.DataFrame):
    if external_val_df.empty:
        raise RuntimeError("External positive validation manifest is empty.")
    sources = set(external_val_df["dataset_source"].astype(str).str.lower())
    if sources != {"armd_curated"}:
        raise RuntimeError(f"Unexpected external validation sources: {sorted(sources)}")
    if set(external_val_df["binary_label"].astype(int)) != {1}:
        raise RuntimeError("ARMD external validation must contain positive labels only.")

    for column in ["image_id", "sha256", "split_group_id"]:
        if column not in train_df.columns or column not in external_val_df.columns:
            continue
        overlap = set(train_df[column].astype(str)) & set(external_val_df[column].astype(str))
        if overlap:
            raise RuntimeError(
                f"Leakage detected between training and external validation for {column}: "
                f"{sorted(overlap)[:20]}"
            )


def load_prepared_splits(cfg: dict, cli_root: str | None, fold: int | None):
    data_cfg = cfg["data"]
    root = _resolve_dataset_root(data_cfg, cli_root)

    if fold is None:
        train_manifest = data_cfg["train_manifest"]
        val_manifest = data_cfg["val_manifest"]
    else:
        train_manifest = data_cfg.get("fold_train_manifest", data_cfg["train_manifest"])
        val_manifest = data_cfg.get("fold_val_manifest", data_cfg["val_manifest"])

    train_df = _read_prepared_manifest(root, train_manifest)
    val_df = _read_prepared_manifest(root, val_manifest)
    _validate_train_val(train_df, val_df)

    external_val_df = None
    external_manifest = data_cfg.get("external_val_manifest")
    if external_manifest:
        external_path = root / external_manifest
        if external_path.exists():
            external_val_df = _read_prepared_manifest(root, external_manifest)
            _validate_external_validation(train_df, external_val_df)
        elif bool(data_cfg.get("require_external_validation", False)):
            raise FileNotFoundError(
                f"Required external validation manifest was not found: {external_path}. "
                "Re-run the preparation notebook and save a new dataset version."
            )

    cfg["data"]["resolved_dataset_root"] = str(root)
    cfg["data"]["image_col"] = "relative_image_path"
    _log(f"Prepared dataset root: {root}")
    _log(f"Train manifest: {train_manifest} ({len(train_df)} rows)")
    _log(f"Primary HYAMD validation manifest: {val_manifest} ({len(val_df)} rows)")
    if external_val_df is not None:
        _log(f"External positive validation manifest: {external_manifest} ({len(external_val_df)} rows)")
    return train_df, val_df, external_val_df


def load_or_prepare_legacy_splits(cfg: dict):
    data_cfg = cfg["data"]
    work_dir = Path(data_cfg["work_dir"])
    split_dir = work_dir / "HYAMD_raw" / "splits"
    train_csv = split_dir / "train.csv"
    val_csv = split_dir / "val.csv"

    if train_csv.exists() and val_csv.exists():
        train_df = pd.read_csv(train_csv, dtype={"patient_id": str})
        val_df = pd.read_csv(val_csv, dtype={"patient_id": str})
        return train_df, val_df

    result = prepare_hyamd(
        input_dir=data_cfg["input_dir"],
        work_dir=data_cfg["work_dir"],
        seed=cfg.get("run", {}).get("seed", 42),
        force_recrop=bool(data_cfg.get("force_recrop", False)),
        validate_existing_crops=bool(data_cfg.get("validate_existing_crops", False)),
        max_workers=8,
    )
    return result["train_df"], result["val_df"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--data-root", type=str, default=None)
    parser.add_argument("--fold", type=int, default=None)
    args = parser.parse_args()

    config_path = _resolve_config_path(args.config)
    cfg = load_yaml(config_path)
    cfg = _apply_fold_overrides(cfg, args.fold)
    set_seed(int(cfg.get("run", {}).get("seed", 42)))

    _log("=" * 90)
    _log("EyeAI binary training entrypoint")
    _log("=" * 90)
    _log(f"Current working directory: {Path.cwd()}")
    _log(f"Config path: {config_path}")
    _log(f"Fold: {args.fold}")

    if cfg.get("data", {}).get("prepared_dataset_dir") or args.data_root or os.environ.get("EYEAI_DATASET_ROOT"):
        train_df, val_df, external_val_df = load_prepared_splits(cfg, args.data_root, args.fold)
    else:
        train_df, val_df = load_or_prepare_legacy_splits(cfg)
        external_val_df = None

    summary = train_binary_model(
        cfg,
        train_df,
        val_df,
        test_df=None,
        external_val_df=external_val_df,
    )
    _log("Final summary:")
    _log(str(summary))


if __name__ == "__main__":
    main()
