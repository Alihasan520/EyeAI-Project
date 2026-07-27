from pathlib import Path
import os
import shutil
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from tqdm.auto import tqdm
from eyeai.preprocessing.fundus_crop import crop_dataframe_images

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def collect_hyamd_images(input_dir: str | Path) -> pd.DataFrame:
    input_dir = Path(input_dir)
    chunk_dirs = sorted([p for p in input_dir.iterdir() if p.is_dir() and p.name.startswith("images_chunk_")])
    records = []

    for chunk_dir in chunk_dirs:
        img_dir = chunk_dir / "HYAMD_raw" / "Images"
        imgs = sorted([p for p in img_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]) if img_dir.exists() else []
        for img_path in imgs:
            records.append({"chunk": chunk_dir.name, "source_path": str(img_path), "image_name": img_path.name})

    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError(f"No HYAMD images found under: {input_dir}")
    if df["image_name"].duplicated().any():
        raise RuntimeError("Duplicate HYAMD image names found.")
    return df


def link_images(source_df: pd.DataFrame, images_dir: str | Path) -> None:
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    for row in tqdm(source_df.itertuples(index=False), total=len(source_df), desc="Symlink/copy HYAMD images"):
        src = Path(row.source_path)
        dst = images_dir / row.image_name
        if dst.exists():
            continue
        try:
            os.symlink(src, dst)
        except Exception:
            shutil.copy2(src, dst)


def map_label_id_to_image_name(label_id: str, available_names: set[str]) -> str:
    label_id = str(label_id).strip()
    exts = [".png", ".jpg", ".jpeg", ".tif", ".tiff"]

    for ext in exts:
        if label_id + ext in available_names:
            return label_id + ext

    parts = label_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        base, idx = parts[0], int(parts[1])
        if idx == 1:
            candidates = [base + ext for ext in exts]
        else:
            candidates = [f"{base}_{idx - 1}_" + ext for ext in exts]
        for candidate in candidates:
            if candidate in available_names:
                return candidate

    return label_id + ".png"


def build_hyamd_dataframe(input_dir: str | Path, images_dir: str | Path, cropped_images_dir: str | Path) -> pd.DataFrame:
    input_dir = Path(input_dir)
    images_dir = Path(images_dir)
    cropped_images_dir = Path(cropped_images_dir)

    labels_path = input_dir / "labels.csv"
    if not labels_path.exists():
        raise FileNotFoundError(f"labels.csv not found: {labels_path}")

    labels = pd.read_csv(labels_path, dtype=str)
    required = ["image_id", "patient_id", "side", "AMD"]
    missing = [c for c in required if c not in labels.columns]
    if missing:
        raise RuntimeError(f"Missing HYAMD label columns: {missing}")

    available_names = {p.name for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS}

    df = labels.copy()
    df["image_id"] = df["image_id"].astype(str).str.strip()
    df["patient_id"] = df["patient_id"].astype(str).str.strip()
    df["eye"] = df["side"].astype(str).str.strip()
    df["sex"] = df["sex"].astype(str).str.strip() if "sex" in df.columns else "unknown"
    df["age"] = pd.to_numeric(df["age"], errors="coerce") if "age" in df.columns else np.nan
    df["label"] = pd.to_numeric(df["AMD"], errors="coerce").astype("Int64")
    df["image_name"] = df["image_id"].apply(lambda x: map_label_id_to_image_name(x, available_names))
    df["image_path"] = df["image_name"].apply(lambda x: str(images_dir / x))
    df["proc_image_path"] = df["image_name"].apply(lambda x: str(cropped_images_dir / x))

    df["image_exists"] = df["image_path"].apply(lambda x: Path(x).exists())
    if df["label"].isna().any():
        raise RuntimeError("Some HYAMD labels could not be converted to integers.")
    if (~df["image_exists"]).any():
        missing_df = df.loc[~df["image_exists"], ["image_id", "image_name", "image_path"]].head(20)
        raise RuntimeError(f"Some HYAMD images could not be matched:\n{missing_df}")

    df["label"] = df["label"].astype(int)
    df["binary_label"] = (df["label"] > 0).astype(int)

    keep = ["image_id", "image_name", "image_path", "proc_image_path", "patient_id", "eye", "sex", "age", "label", "binary_label"]
    return df[keep].copy()


def create_patient_splits(df: pd.DataFrame, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    patient_df = df.groupby("patient_id")["binary_label"].max().reset_index().rename(columns={"binary_label": "patient_label"})

    def safe_split(pdf, test_size, random_state):
        counts = pdf["patient_label"].value_counts()
        strat = pdf["patient_label"] if len(counts) > 1 and counts.min() >= 2 else None
        return train_test_split(pdf, test_size=test_size, random_state=random_state, stratify=strat)

    train_pat, temp_pat = safe_split(patient_df, 0.30, seed)
    val_pat, test_pat = safe_split(temp_pat, 0.50, seed)

    train_ids = set(train_pat.patient_id)
    val_ids = set(val_pat.patient_id)
    test_ids = set(test_pat.patient_id)

    if len(train_ids & val_ids) or len(train_ids & test_ids) or len(val_ids & test_ids):
        raise RuntimeError("Patient leakage detected.")

    train_df = df[df.patient_id.isin(train_ids)].copy()
    val_df = df[df.patient_id.isin(val_ids)].copy()
    test_df = df[df.patient_id.isin(test_ids)].copy()

    train_df["split"] = "train"
    val_df["split"] = "val"
    test_df["split"] = "test"

    all_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
    return train_df, val_df, test_df, all_df


def prepare_hyamd(input_dir: str | Path, work_dir: str | Path, seed: int = 42, force_recrop: bool = False, validate_existing_crops: bool = False, max_workers: int = 8):
    work_dir = Path(work_dir)
    raw_dir = work_dir / "HYAMD_raw"
    images_dir = raw_dir / "Images"
    cropped_dir = raw_dir / "Images_cropped"
    splits_dir = raw_dir / "splits"

    raw_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    cropped_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    source_df = collect_hyamd_images(input_dir)
    link_images(source_df, images_dir)
    source_df.to_csv(raw_dir / "hyamd_image_sources.csv", index=False)

    final_df = build_hyamd_dataframe(input_dir, images_dir, cropped_dir)
    crop_report = crop_dataframe_images(final_df, src_col="image_path", dst_col="proc_image_path", max_workers=max_workers, force=force_recrop, validate_existing=validate_existing_crops)
    if crop_report["failed"] > 0:
        pd.DataFrame(crop_report["bad_rows"]).to_csv(raw_dir / "bad_crop_images.csv", index=False)
        raise RuntimeError(f"Cropping failed for {crop_report['failed']} images.")

    train_df, val_df, test_df, all_df = create_patient_splits(final_df, seed=seed)

    final_df.to_csv(raw_dir / "final_hyamd_dataframe.csv", index=False)
    train_df.to_csv(splits_dir / "train.csv", index=False)
    val_df.to_csv(splits_dir / "val.csv", index=False)
    test_df.to_csv(splits_dir / "test.csv", index=False)
    all_df.to_csv(splits_dir / "all_splits.csv", index=False)

    return {
        "raw_dir": raw_dir,
        "images_dir": images_dir,
        "cropped_dir": cropped_dir,
        "splits_dir": splits_dir,
        "train_df": train_df,
        "val_df": val_df,
        "test_df": test_df,
        "all_df": all_df,
        "crop_report": crop_report,
    }
