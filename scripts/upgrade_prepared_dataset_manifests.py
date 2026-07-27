#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


def _resolve_source_root(dataset_mount: Path) -> Path:
    candidates = [dataset_mount, dataset_mount / "eyeai_prepared_binary_dataset"]
    for candidate in candidates:
        if (candidate / "dataset_summary.json").exists() and (candidate / "manifests").exists():
            return candidate
    valid = [
        path.parent
        for path in dataset_mount.rglob("dataset_summary.json")
        if (path.parent / "manifests" / "train_mixed.csv").exists()
    ]
    if len(valid) != 1:
        raise RuntimeError(f"Expected one prepared dataset root, found: {valid}")
    return valid[0]


def _external_manifest(manifest_dir: Path) -> Path:
    for name in ["armd_curated_all_clean.csv", "armd_curated_train_only.csv", "armd_curated_train.csv"]:
        path = manifest_dir / name
        if path.exists():
            return path
    raise FileNotFoundError("No ARMD Curated manifest was found.")


def main():
    parser = argparse.ArgumentParser(description="Create a writable manifest-only upgrade of the prepared EyeAI dataset.")
    parser.add_argument("--dataset-mount", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--external-val-fraction", type=float, default=0.10)
    args = parser.parse_args()

    dataset_mount = Path(args.dataset_mount)
    source_root = _resolve_source_root(dataset_mount)
    output_root = Path(args.output_root)

    already_upgraded = (
        (source_root / "manifests" / "armd_curated_train.csv").exists()
        and (source_root / "manifests" / "armd_curated_val_positive.csv").exists()
    )
    if already_upgraded:
        print(source_root)
        return

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    shutil.copy2(source_root / "dataset_summary.json", output_root / "dataset_summary.json")
    if (source_root / "README.md").exists():
        shutil.copy2(source_root / "README.md", output_root / "README.md")
    shutil.copytree(source_root / "manifests", output_root / "manifests")
    (output_root / "images").symlink_to(source_root / "images", target_is_directory=True)
    if (source_root / "audit").exists():
        (output_root / "audit").symlink_to(source_root / "audit", target_is_directory=True)

    manifest_dir = output_root / "manifests"
    external_all = pd.read_csv(_external_manifest(manifest_dir), dtype=str, keep_default_na=False)
    external_all["binary_label"] = pd.to_numeric(external_all["binary_label"], errors="raise").astype(int)

    group_column = next(
        (
            column
            for column in ["split_group_id", "duplicate_group", "duplicate_group_id", "sha256", "image_id"]
            if column in external_all.columns and external_all[column].astype(str).str.len().gt(0).all()
        ),
        None,
    )
    if group_column is None:
        raise RuntimeError("No safe external duplicate-group column was found.")
    external_all["split_group_id"] = external_all[group_column].astype(str)

    groups = external_all["split_group_id"].drop_duplicates().sort_values().to_numpy()
    rng = np.random.default_rng(args.seed)
    shuffled = rng.permutation(groups)
    val_count = max(1, int(round(len(shuffled) * args.external_val_fraction)))
    val_groups = set(shuffled[:val_count])

    external_val = external_all[external_all["split_group_id"].isin(val_groups)].copy()
    external_train = external_all[~external_all["split_group_id"].isin(val_groups)].copy()
    external_train["split"] = "train_external"
    external_val["split"] = "val_external_positive"

    for column in ["image_id", "sha256", "split_group_id"]:
        if column in external_all.columns:
            overlap = set(external_train[column].astype(str)) & set(external_val[column].astype(str))
            if overlap:
                raise RuntimeError(f"External leakage detected in {column}: {sorted(overlap)[:10]}")

    external_all.to_csv(manifest_dir / "armd_curated_all_clean.csv", index=False)
    external_train.to_csv(manifest_dir / "armd_curated_train.csv", index=False)
    external_val.to_csv(manifest_dir / "armd_curated_val_positive.csv", index=False)

    hyamd_train = pd.read_csv(manifest_dir / "hyamd_train.csv", dtype=str, keep_default_na=False)
    train_mixed = pd.concat([hyamd_train, external_train], ignore_index=True)
    train_mixed.to_csv(manifest_dir / "train_mixed.csv", index=False)

    fold_dir = manifest_dir / "folds"
    if fold_dir.exists():
        for train_path in sorted(fold_dir.glob("fold_*_train_hyamd.csv")):
            fold = int(train_path.stem.split("_")[1])
            fold_train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
            pd.concat([fold_train, external_train], ignore_index=True).to_csv(
                fold_dir / f"fold_{fold}_train_mixed.csv",
                index=False,
            )

    summary_path = output_root / "dataset_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update({
        "external_train": int(len(external_train)),
        "external_validation_positive": int(len(external_val)),
        "train_mixed": int(len(train_mixed)),
        "external_split_group_column": group_column,
        "external_validation_fraction": float(args.external_val_fraction),
        "notes": [
            "ARMD Curated is positive-only and split by duplicate group into training and positive-only validation.",
            "HYAMD validation remains the primary checkpoint-selection set.",
            "The locked HYAMD test manifest is never loaded during training.",
            "Images are reused without reprocessing.",
        ],
    })
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(output_root)


if __name__ == "__main__":
    main()
