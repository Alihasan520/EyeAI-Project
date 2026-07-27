from pathlib import Path

import pandas as pd
from PIL import Image
import torch
from torch.utils.data import Dataset


class FundusBinaryDataset(Dataset):
    def __init__(
        self,
        dataframe: pd.DataFrame,
        image_col: str = "proc_image_path",
        label_col: str = "binary_label",
        transform=None,
        image_root: str | Path | None = None,
    ):
        self.df = dataframe.reset_index(drop=True).copy()
        self.image_col = image_col
        self.label_col = label_col
        self.transform = transform
        self.image_root = Path(image_root) if image_root is not None else None

        if label_col not in self.df.columns:
            raise KeyError(f"Missing dataset label column: {label_col}")
        if image_col not in self.df.columns:
            raise KeyError(f"Missing dataset image column: {image_col}")

        self.df[label_col] = self.df[label_col].astype(int)
        self.df[image_col] = self.df[image_col].astype(str)

    def __len__(self):
        return len(self.df)

    def _resolve_image_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        if self.image_root is None:
            raise RuntimeError(f"Relative image path requires image_root: {value}")
        return self.image_root / path

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        image_path = self._resolve_image_path(str(row[self.image_col]))
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
        label = int(row[self.label_col])

        if self.transform is not None:
            image = self.transform(image)

        original_label = row.get("label", label)
        try:
            original_label = int(original_label)
        except (TypeError, ValueError):
            original_label = -1

        meta = {
            "image_id": str(row.get("image_id", "")),
            "image_name": str(row.get("image_name", image_path.name)),
            "patient_id": str(row.get("patient_id", "")),
            "eye": str(row.get("eye", "")),
            "dataset_source": str(row.get("dataset_source", "unknown")),
            "original_label": original_label,
        }
        return image, torch.tensor(label, dtype=torch.long), meta
