from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from PIL import Image, ImageFile
from sklearn.model_selection import StratifiedKFold, train_test_split
from tqdm.auto import tqdm

from eyeai.data.prepare_hyamd import IMAGE_EXTS, prepare_hyamd
from eyeai.preprocessing.fundus_crop import crop_fundus_region

ImageFile.LOAD_TRUNCATED_IMAGES = True


def _log(message: str):
    print(message, flush=True)


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _dhash(image: Image.Image, hash_size: int = 8) -> int:
    gray = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
    pixels = np.asarray(gray, dtype=np.int16)
    difference = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in difference.flatten():
        value = (value << 1) | int(bit)
    return int(value)


def _hamming_distance(left: int, right: int) -> int:
    return int((int(left) ^ int(right)).bit_count())


def _edge_feature(path: str | Path, size: int = 64) -> np.ndarray:
    with Image.open(path) as opened:
        gray = opened.convert("L").resize((size, size), Image.Resampling.BILINEAR)
        array = np.asarray(gray, dtype=np.float32) / 255.0
    gradients = np.concatenate([np.diff(array, axis=1).ravel(), np.diff(array, axis=0).ravel()])
    gradients = gradients - gradients.mean()
    norm = float(np.linalg.norm(gradients))
    return gradients / max(norm, 1e-8)


def _edge_similarity(left_path: str | Path, right_path: str | Path, cache: dict[str, np.ndarray]) -> float:
    left_key = str(left_path)
    right_key = str(right_path)
    if left_key not in cache:
        cache[left_key] = _edge_feature(left_key)
    if right_key not in cache:
        cache[right_key] = _edge_feature(right_key)
    return float(np.dot(cache[left_key], cache[right_key]))


def _image_statistics(path: Path) -> dict:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        resized = image.resize((128, 128), Image.Resampling.BILINEAR)
        array = np.asarray(resized, dtype=np.float32)
        gray = array.mean(axis=2)
        return {
            "width": int(width),
            "height": int(height),
            "aspect_ratio": float(width / max(height, 1)),
            "mean_brightness": float(gray.mean()),
            "contrast_std": float(gray.std()),
            "black_fraction": float((gray <= 8).mean()),
            "dhash": _dhash(image),
        }


def _audit_image(path: Path, dataset_source: str, min_dimension: int) -> dict:
    record = {
        "source_path": str(path),
        "image_name": path.name,
        "dataset_source": dataset_source,
        "status": "ok",
        "exclusion_reason": "",
    }
    try:
        record["sha256"] = _sha256_file(path)
        record.update(_image_statistics(path))
        if min(record["width"], record["height"]) < int(min_dimension):
            record["status"] = "excluded"
            record["exclusion_reason"] = "too_small"
        elif record["contrast_std"] < 4.0:
            record["status"] = "flagged"
            record["exclusion_reason"] = "very_low_contrast"
    except Exception as exc:
        record.update({
            "sha256": "",
            "width": 0,
            "height": 0,
            "aspect_ratio": 0.0,
            "mean_brightness": 0.0,
            "contrast_std": 0.0,
            "black_fraction": 1.0,
            "dhash": 0,
            "status": "excluded",
            "exclusion_reason": f"corrupt:{type(exc).__name__}",
        })
    return record


def resolve_input_dir(path_value: str | Path, search_hint: str | None = None) -> Path:
    path = Path(path_value)
    if path.exists():
        return path

    hint = (search_hint or path.name).lower()
    candidates = []
    kaggle_root = Path("/kaggle/input")
    if kaggle_root.exists():
        for candidate in kaggle_root.iterdir():
            if candidate.is_dir() and hint in candidate.name.lower():
                candidates.append(candidate)
        if not candidates:
            for candidate in kaggle_root.rglob("*"):
                if candidate.is_dir() and hint in candidate.name.lower():
                    candidates.append(candidate)
                    if len(candidates) >= 10:
                        break

    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise RuntimeError(f"Multiple input directories matched '{hint}': {candidates}")
    raise FileNotFoundError(f"Input directory not found: {path}")


def collect_images(input_dir: str | Path) -> list[Path]:
    input_dir = Path(input_dir)
    images = sorted(
        path for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )
    if not images:
        raise RuntimeError(f"No images found under: {input_dir}")
    return images


def _build_duplicate_reference(records: pd.DataFrame) -> tuple[dict[str, dict], list[dict]]:
    exact = {}
    near = []
    for row in records.itertuples(index=False):
        item = row._asdict()
        if item.get("status") == "excluded":
            continue
        exact.setdefault(str(item["sha256"]), item)
        near.append(item)
    return exact, near


def filter_external_duplicates(
    external_audit: pd.DataFrame,
    hyamd_audit: pd.DataFrame,
    near_duplicate_hamming_threshold: int = 4,
    near_duplicate_similarity_threshold: float = 0.985,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep HYAMD authoritative and remove only high-confidence duplicate copies."""
    hyamd_exact, hyamd_near = _build_duplicate_reference(hyamd_audit)
    kept_external = []
    exclusions = []
    external_exact = {}
    feature_cache: dict[str, np.ndarray] = {}

    for row in external_audit.sort_values("source_path").itertuples(index=False):
        item = row._asdict()
        reason = str(item.get("exclusion_reason", ""))
        match_source = ""
        match_path = ""
        distance = None
        similarity = None

        if item.get("status") == "excluded":
            exclusions.append({
                **item,
                "duplicate_match_source": match_source,
                "duplicate_match_path": match_path,
                "dhash_distance": distance,
                "edge_similarity": similarity,
            })
            continue

        exact_match = hyamd_exact.get(str(item["sha256"]))
        if exact_match is not None:
            reason = "exact_duplicate_of_hyamd"
            match_source = "hyamd"
            match_path = str(exact_match["source_path"])
        elif str(item["sha256"]) in external_exact:
            exact_match = external_exact[str(item["sha256"])]
            reason = "exact_duplicate_within_external"
            match_source = "armd_curated"
            match_path = str(exact_match["source_path"])
        else:
            best_match = None
            best_distance = 65
            best_similarity = -1.0
            references = hyamd_near + kept_external
            for reference in references:
                current_distance = _hamming_distance(item["dhash"], reference["dhash"])
                if current_distance > int(near_duplicate_hamming_threshold):
                    continue
                current_similarity = _edge_similarity(
                    item["source_path"],
                    reference["source_path"],
                    feature_cache,
                )
                if current_similarity > best_similarity:
                    best_similarity = current_similarity
                    best_distance = current_distance
                    best_match = reference

            if (
                best_match is not None
                and best_similarity >= float(near_duplicate_similarity_threshold)
            ):
                reason = "near_duplicate"
                match_source = str(best_match["dataset_source"])
                match_path = str(best_match["source_path"])
                distance = int(best_distance)
                similarity = float(best_similarity)

        if reason in {"exact_duplicate_of_hyamd", "exact_duplicate_within_external", "near_duplicate"}:
            item["status"] = "excluded"
            item["exclusion_reason"] = reason
            exclusions.append({
                **item,
                "duplicate_match_source": match_source,
                "duplicate_match_path": match_path,
                "dhash_distance": distance,
                "edge_similarity": similarity,
            })
            continue

        kept_external.append(item)
        external_exact[str(item["sha256"])] = item

    kept_columns = list(external_audit.columns)
    exclusion_columns = kept_columns + [
        "duplicate_match_source",
        "duplicate_match_path",
        "dhash_distance",
        "edge_similarity",
    ]
    return (
        pd.DataFrame(kept_external, columns=kept_columns),
        pd.DataFrame(exclusions, columns=exclusion_columns),
    )


def _save_standardized_image(source_path: Path, destination_path: Path, crop_black_border: bool = True):
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as opened:
        image = opened.convert("RGB")
        if crop_black_border:
            image = crop_fundus_region(image, threshold=8, pad_ratio=0.03, make_square=True)
        image.save(destination_path, format="JPEG", quality=95, subsampling=0, optimize=True)


def _standardized_name(prefix: str, sha256: str) -> str:
    return f"{prefix}_{sha256[:20]}.jpg"


def _assign_hyamd_split_groups(manifest: pd.DataFrame) -> pd.DataFrame:
    """Join patients connected by exact duplicate content into one split group."""
    dataframe = manifest.copy()
    patients = sorted(dataframe["patient_id"].astype(str).unique())
    parent = {patient: patient for patient in patients}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str):
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for _, group in dataframe.groupby("sha256"):
        group_patients = sorted(group["patient_id"].astype(str).unique())
        for patient in group_patients[1:]:
            union(group_patients[0], patient)

    roots = dataframe["patient_id"].astype(str).map(find)
    dataframe["split_group_id"] = roots.map(
        lambda value: "hyamd_group_" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    )
    return dataframe


def _prepare_hyamd_manifest(
    hyamd_df: pd.DataFrame,
    hyamd_audit: pd.DataFrame,
    output_dir: Path,
) -> pd.DataFrame:
    audit_by_path = hyamd_audit.set_index("source_path").to_dict(orient="index")
    rows = []
    for row in tqdm(hyamd_df.itertuples(index=False), total=len(hyamd_df), desc="Export HYAMD images"):
        source_path = Path(row.proc_image_path)
        audit = audit_by_path[str(source_path)]
        relative_path = Path("images") / "hyamd" / _standardized_name("hyamd", audit["sha256"])
        destination = output_dir / relative_path
        if not destination.exists():
            _save_standardized_image(source_path, destination, crop_black_border=False)
        rows.append({
            "image_id": str(row.image_id),
            "image_name": str(row.image_name),
            "relative_image_path": relative_path.as_posix(),
            "patient_id": str(row.patient_id),
            "eye": str(row.eye),
            "sex": str(row.sex),
            "age": row.age,
            "label": int(row.label),
            "binary_label": int(row.binary_label),
            "dataset_source": "hyamd",
            "is_external": False,
            "sha256": audit["sha256"],
            "dhash": int(audit["dhash"]),
        })
    return _assign_hyamd_split_groups(pd.DataFrame(rows))


def _prepare_external_manifest(external_kept: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    rows = []
    for row in tqdm(external_kept.itertuples(index=False), total=len(external_kept), desc="Export ARMD Curated images"):
        source_path = Path(row.source_path)
        relative_path = Path("images") / "armd_curated" / _standardized_name("armd", row.sha256)
        destination = output_dir / relative_path
        if not destination.exists():
            _save_standardized_image(source_path, destination, crop_black_border=True)
        rows.append({
            "image_id": f"armd_{row.sha256[:20]}",
            "image_name": str(row.image_name),
            "relative_image_path": relative_path.as_posix(),
            "patient_id": f"armd_{row.sha256[:20]}",
            "split_group_id": f"armd_{row.sha256[:20]}",
            "eye": "unknown",
            "sex": "unknown",
            "age": np.nan,
            "label": -1,
            "binary_label": 1,
            "dataset_source": "armd_curated",
            "is_external": True,
            "sha256": str(row.sha256),
            "dhash": int(row.dhash),
        })
    return pd.DataFrame(rows)



def _split_external_manifest(
    external_manifest: pd.DataFrame,
    validation_fraction: float,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a deterministic positive-only external validation split by duplicate group."""
    validation_fraction = float(validation_fraction)
    if validation_fraction <= 0:
        train_df = external_manifest.copy()
        train_df["split"] = "train_external"
        return train_df, external_manifest.iloc[0:0].copy()
    if not 0 < validation_fraction < 0.5:
        raise ValueError("external_validation_fraction must be in [0, 0.5).")

    group_table = external_manifest[["split_group_id"]].drop_duplicates().reset_index(drop=True)
    if len(group_table) < 2:
        raise RuntimeError("Not enough unique external groups to create validation data.")

    train_groups, val_groups = train_test_split(
        group_table,
        test_size=validation_fraction,
        random_state=int(seed),
        shuffle=True,
    )
    train_ids = set(train_groups["split_group_id"].astype(str))
    val_ids = set(val_groups["split_group_id"].astype(str))
    if train_ids & val_ids:
        raise RuntimeError("External duplicate-group leakage detected.")

    train_df = external_manifest[external_manifest["split_group_id"].astype(str).isin(train_ids)].copy()
    val_df = external_manifest[external_manifest["split_group_id"].astype(str).isin(val_ids)].copy()
    train_df["split"] = "train_external"
    val_df["split"] = "val_external_positive"

    if set(train_df["image_id"].astype(str)) & set(val_df["image_id"].astype(str)):
        raise RuntimeError("External image leakage detected after splitting.")
    if set(train_df["sha256"].astype(str)) & set(val_df["sha256"].astype(str)):
        raise RuntimeError("External exact-duplicate leakage detected after splitting.")
    return train_df, val_df

def _validate_split_frames(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame):
    for column in ["patient_id", "split_group_id"]:
        train_values = set(train_df[column].astype(str))
        val_values = set(val_df[column].astype(str))
        test_values = set(test_df[column].astype(str))
        if train_values & val_values or train_values & test_values or val_values & test_values:
            raise RuntimeError(f"Leakage detected in HYAMD fixed splits for grouping column: {column}")


def _create_group_splits(
    manifest: pd.DataFrame,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    group_table = (
        manifest.groupby("split_group_id", as_index=False)["binary_label"]
        .max()
        .rename(columns={"binary_label": "group_label"})
    )

    def safe_split(dataframe: pd.DataFrame, test_size: float, random_state: int):
        counts = dataframe["group_label"].value_counts()
        stratify = dataframe["group_label"] if len(counts) > 1 and counts.min() >= 2 else None
        return train_test_split(
            dataframe,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify,
        )

    train_groups, temporary_groups = safe_split(group_table, 0.30, seed)
    val_groups, test_groups = safe_split(temporary_groups, 0.50, seed)
    frames = []
    for name, groups in [("train", train_groups), ("val", val_groups), ("test", test_groups)]:
        group_ids = set(groups["split_group_id"].astype(str))
        frame = manifest[manifest["split_group_id"].astype(str).isin(group_ids)].copy()
        frame["split"] = name
        frames.append(frame)
    _validate_split_frames(*frames)
    return tuple(frames)


def _reuse_or_create_splits(
    manifest: pd.DataFrame,
    seed: int,
    existing_split_dir: str | Path | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if existing_split_dir:
        split_dir = Path(existing_split_dir)
        paths = {name: split_dir / f"{name}.csv" for name in ["train", "val", "test"]}
        if all(path.exists() for path in paths.values()):
            frames = {}
            for name, path in paths.items():
                old = pd.read_csv(path, dtype={"patient_id": str, "image_id": str})
                if "image_id" not in old.columns:
                    raise RuntimeError(f"Existing split is missing image_id: {path}")
                ids = set(old["image_id"].astype(str))
                frame = manifest[manifest["image_id"].astype(str).isin(ids)].copy()
                if len(frame) != len(ids):
                    missing = sorted(ids - set(frame["image_id"].astype(str)))[:20]
                    raise RuntimeError(f"Existing split contains unknown image IDs: {missing}")
                frame["split"] = name
                frames[name] = frame
            _validate_split_frames(frames["train"], frames["val"], frames["test"])
            return frames["train"], frames["val"], frames["test"]

    return _create_group_splits(manifest, seed=seed)


def _create_group_folds(development_df: pd.DataFrame, n_splits: int, seed: int):
    group_table = (
        development_df.groupby("split_group_id", as_index=False)["binary_label"]
        .max()
        .rename(columns={"binary_label": "group_label"})
    )
    splitter = StratifiedKFold(n_splits=int(n_splits), shuffle=True, random_state=int(seed))
    folds = []
    for fold, (train_indices, val_indices) in enumerate(
        splitter.split(group_table["split_group_id"], group_table["group_label"])
    ):
        train_groups = set(group_table.iloc[train_indices]["split_group_id"].astype(str))
        val_groups = set(group_table.iloc[val_indices]["split_group_id"].astype(str))
        train_df = development_df[development_df["split_group_id"].astype(str).isin(train_groups)].copy()
        val_df = development_df[development_df["split_group_id"].astype(str).isin(val_groups)].copy()
        if set(train_df["patient_id"].astype(str)) & set(val_df["patient_id"].astype(str)):
            raise RuntimeError(f"Patient leakage detected in fold {fold}.")
        if set(train_df["split_group_id"].astype(str)) & set(val_df["split_group_id"].astype(str)):
            raise RuntimeError(f"Duplicate-group leakage detected in fold {fold}.")
        folds.append((fold, train_df, val_df))
    return folds


def _write_manifest(dataframe: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False)


def prepare_hyamd_armd_binary_dataset(config: dict) -> dict:
    seed = int(config.get("seed", 42))
    output_dir = Path(config["output_dir"])
    intermediate_dir = Path(config.get("intermediate_dir", output_dir.parent / "eyeai_binary_build"))
    if bool(config.get("clean_output", True)) and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifests" / "folds").mkdir(parents=True, exist_ok=True)
    (output_dir / "audit").mkdir(parents=True, exist_ok=True)

    hyamd_input_dir = resolve_input_dir(config["hyamd_input_dir"], config.get("hyamd_search_hint", "hyamd"))
    external_input_dir = resolve_input_dir(
        config["external_input_dir"],
        config.get("external_search_hint", "armd-curated-dataset-2023"),
    )
    _log(f"HYAMD input: {hyamd_input_dir}")
    _log(f"ARMD Curated input: {external_input_dir}")

    hyamd_result = prepare_hyamd(
        input_dir=hyamd_input_dir,
        work_dir=intermediate_dir,
        seed=seed,
        force_recrop=bool(config.get("force_recrop", False)),
        validate_existing_crops=bool(config.get("validate_existing_crops", True)),
        max_workers=int(config.get("max_workers", 8)),
    )
    hyamd_source_df = hyamd_result["all_df"].copy()

    min_dimension = int(config.get("min_dimension", 200))
    hyamd_audit_records = [
        _audit_image(Path(path), "hyamd", min_dimension=min_dimension)
        for path in tqdm(hyamd_source_df["proc_image_path"], desc="Audit HYAMD")
    ]
    hyamd_audit = pd.DataFrame(hyamd_audit_records)
    if (hyamd_audit["status"] == "excluded").any():
        bad = hyamd_audit[hyamd_audit["status"] == "excluded"]
        bad.to_csv(output_dir / "audit" / "hyamd_excluded.csv", index=False)
        raise RuntimeError(f"HYAMD audit excluded {len(bad)} images. Review audit/hyamd_excluded.csv.")

    external_paths = collect_images(external_input_dir)
    external_audit = pd.DataFrame([
        _audit_image(path, "armd_curated", min_dimension=min_dimension)
        for path in tqdm(external_paths, desc="Audit ARMD Curated")
    ])
    external_kept, external_exclusions = filter_external_duplicates(
        external_audit=external_audit,
        hyamd_audit=hyamd_audit,
        near_duplicate_hamming_threshold=int(config.get("near_duplicate_hamming_threshold", 4)),
        near_duplicate_similarity_threshold=float(config.get("near_duplicate_similarity_threshold", 0.985)),
    )

    hyamd_manifest = _prepare_hyamd_manifest(hyamd_source_df, hyamd_audit, output_dir)
    external_manifest = _prepare_external_manifest(external_kept, output_dir)
    external_train, external_val = _split_external_manifest(
        external_manifest,
        validation_fraction=float(config.get("external_validation_fraction", 0.10)),
        seed=seed,
    )

    train_hyamd, val_hyamd, test_hyamd = _reuse_or_create_splits(
        hyamd_manifest,
        seed=seed,
        existing_split_dir=config.get("existing_split_dir"),
    )
    train_mixed = pd.concat([train_hyamd, external_train], ignore_index=True)

    _write_manifest(hyamd_manifest, output_dir / "manifests" / "hyamd_all.csv")
    _write_manifest(external_manifest, output_dir / "manifests" / "armd_curated_all_clean.csv")
    _write_manifest(external_train, output_dir / "manifests" / "armd_curated_train.csv")
    _write_manifest(external_val, output_dir / "manifests" / "armd_curated_val_positive.csv")
    _write_manifest(train_hyamd, output_dir / "manifests" / "hyamd_train.csv")
    _write_manifest(val_hyamd, output_dir / "manifests" / "hyamd_val.csv")
    _write_manifest(test_hyamd, output_dir / "manifests" / "hyamd_test_locked.csv")
    _write_manifest(train_mixed, output_dir / "manifests" / "train_mixed.csv")

    development = pd.concat([train_hyamd, val_hyamd], ignore_index=True)
    fold_summaries = []
    for fold, fold_train, fold_val in _create_group_folds(
        development,
        n_splits=int(config.get("n_splits", 3)),
        seed=seed,
    ):
        fold_train_mixed = pd.concat([fold_train, external_train], ignore_index=True)
        fold_dir = output_dir / "manifests" / "folds"
        _write_manifest(fold_train, fold_dir / f"fold_{fold}_train_hyamd.csv")
        _write_manifest(fold_train_mixed, fold_dir / f"fold_{fold}_train_mixed.csv")
        _write_manifest(fold_val, fold_dir / f"fold_{fold}_val_hyamd.csv")
        fold_summaries.append({
            "fold": fold,
            "train_hyamd": len(fold_train),
            "train_mixed": len(fold_train_mixed),
            "val_hyamd": len(fold_val),
            "train_distribution": fold_train["binary_label"].value_counts().sort_index().to_dict(),
            "val_distribution": fold_val["binary_label"].value_counts().sort_index().to_dict(),
        })

    combined_audit = pd.concat([hyamd_audit, external_audit], ignore_index=True)
    combined_audit.to_csv(output_dir / "audit" / "image_audit.csv", index=False)
    external_exclusions.to_csv(output_dir / "audit" / "external_exclusions.csv", index=False)

    summary = {
        "dataset_name": "EyeAI HYAMD + ARMD Curated Binary Training Dataset",
        "seed": seed,
        "hyamd_total": int(len(hyamd_manifest)),
        "hyamd_train": int(len(train_hyamd)),
        "hyamd_val": int(len(val_hyamd)),
        "hyamd_test_locked": int(len(test_hyamd)),
        "external_discovered": int(len(external_audit)),
        "external_kept": int(len(external_manifest)),
        "external_train": int(len(external_train)),
        "external_validation_positive": int(len(external_val)),
        "external_excluded": int(len(external_exclusions)),
        "train_mixed": int(len(train_mixed)),
        "train_hyamd_distribution": train_hyamd["binary_label"].value_counts().sort_index().to_dict(),
        "train_mixed_distribution": train_mixed["binary_label"].value_counts().sort_index().to_dict(),
        "validation_distribution": val_hyamd["binary_label"].value_counts().sort_index().to_dict(),
        "test_distribution": test_hyamd["binary_label"].value_counts().sort_index().to_dict(),
        "folds": fold_summaries,
        "notes": [
            "ARMD Curated is positive-only and split by duplicate_group into training and positive-only external validation.",
            "HYAMD validation remains the primary checkpoint-selection set.",
            "ARMD external validation is reported separately and never mixed into AUC or threshold selection.",
            "The locked test manifest contains HYAMD images only and is never loaded by training.",
            "External severity is unknown and stored as label=-1.",
            "Images are cropped only to remove outer black borders and saved without CLAHE or fixed gamma filters.",
        ],
    }
    with open(output_dir / "dataset_summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    readme = """# EyeAI Prepared Binary Dataset\n\nThis directory is a portable training artifact. All CSV paths are relative to this directory.\n\n- `images/hyamd`: HYAMD full-fundus images.\n- `images/armd_curated`: cleaned ARMD Curated positive images.\n- `manifests`: fixed HYAMD splits, mixed training, and positive-only ARMD validation manifests.\n- `manifests/folds`: patient-level 3-fold HYAMD development splits.\n- `audit`: quality and duplicate reports.\n- `dataset_summary.json`: counts and provenance summary.\n\nHYAMD validation is the primary selection set. ARMD validation is positive-only and reported separately.\n"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")
    return summary
