from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Tuple, List, Dict
import os
import numpy as np
from PIL import Image, ImageFile
from tqdm.auto import tqdm

ImageFile.LOAD_TRUNCATED_IMAGES = True


def crop_fundus_region(image: Image.Image, threshold: int = 8, pad_ratio: float = 0.03, make_square: bool = True) -> Image.Image:
    image = image.convert("RGB")
    arr = np.array(image)
    gray = arr.mean(axis=2)
    mask = gray > threshold

    if not mask.any():
        return image

    ys, xs = np.where(mask)
    y1, y2 = ys.min(), ys.max()
    x1, x2 = xs.min(), xs.max()

    h, w = arr.shape[:2]
    pad = int(max(y2 - y1 + 1, x2 - x1 + 1) * pad_ratio)

    y1 = max(0, y1 - pad)
    y2 = min(h - 1, y2 + pad)
    x1 = max(0, x1 - pad)
    x2 = min(w - 1, x2 + pad)

    cropped = image.crop((x1, y1, x2 + 1, y2 + 1))

    if make_square:
        cw, ch = cropped.size
        side = max(cw, ch)
        canvas = Image.new("RGB", (side, side), (0, 0, 0))
        canvas.paste(cropped, ((side - cw) // 2, (side - ch) // 2))
        cropped = canvas

    return cropped


def is_valid_image(path: str | Path, validate_pixels: bool = False) -> bool:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return False
    if not validate_pixels:
        return True
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def crop_one(src: str | Path, dst: str | Path, force: bool = False, validate_existing: bool = False) -> Tuple[str, str, str | None]:
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if (not force) and is_valid_image(dst, validate_pixels=validate_existing):
        return str(dst), "existing", None

    try:
        with Image.open(src) as img:
            cropped = crop_fundus_region(img)
            tmp_dst = dst.parent / f"{dst.stem}.tmp{dst.suffix}"
            cropped.save(tmp_dst)
            os.replace(tmp_dst, dst)
        return str(dst), "created", None
    except Exception as e:
        return str(dst), "failed", repr(e)


def crop_dataframe_images(df, src_col: str, dst_col: str, max_workers: int = 8, force: bool = False, validate_existing: bool = False):
    rows = list(df.itertuples(index=False))
    src_idx = df.columns.get_loc(src_col)
    dst_idx = df.columns.get_loc(dst_col)

    tasks = []
    for i, row in enumerate(rows):
        src = getattr(row, src_col)
        dst = getattr(row, dst_col)
        if (not force) and is_valid_image(dst, validate_pixels=validate_existing):
            continue
        tasks.append((i, src, dst))

    bad_rows: List[Dict] = []
    created = 0
    existing = len(rows) - len(tasks)

    if tasks:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(crop_one, src, dst, force, validate_existing): (i, src, dst) for i, src, dst in tasks}
            for future in tqdm(as_completed(futures), total=len(futures), desc=f"Crop missing images x{max_workers}"):
                i, src, dst = futures[future]
                path, status, err = future.result()
                if status == "created":
                    created += 1
                if err is not None:
                    bad_rows.append({"row_index": i, "src": src, "dst": dst, "error": err})

    return {"existing": existing, "created": created, "failed": len(bad_rows), "bad_rows": bad_rows}
