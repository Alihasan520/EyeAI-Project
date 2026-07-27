# EyeAI AMD3 — Binary Pipeline V2 Update Notes

## Purpose

This update separates dataset preparation from training and rebuilds the binary pipeline around a portable prepared dataset.

## Dataset preparation

Run:

```bash
python -u scripts/prepare_binary_dataset.py --config configs/prepare_hyamd_armd_binary.yaml
```

The output directory is:

```text
/kaggle/working/eyeai_prepared_binary_dataset
```

It contains:

- HYAMD full-fundus images.
- Cleaned ARMD Curated positive images.
- Fixed HYAMD train/validation/locked-test manifests.
- Mixed training manifests.
- Three patient-level development folds.
- Image quality and duplicate reports.

No CLAHE, fixed gamma correction, sharpening, ROI crop, or artificial background fill is applied.

## Training order

### 1. Corrected HYAMD-only baseline

```bash
python -u scripts/train_binary.py \
  --config configs/train_efficientnetv2_binary_run05_hyamd_corrected.yaml \
  --data-root /kaggle/working/eyeai_prepared_binary_dataset
```

### 2. Mixed HYAMD + ARMD Curated training

```bash
python -u scripts/train_binary.py \
  --config configs/train_efficientnetv2_binary_run06_mixed_external.yaml \
  --data-root /kaggle/working/eyeai_prepared_binary_dataset
```

### 3. HYAMD-only fine-tuning

```bash
python -u scripts/train_binary.py \
  --config configs/train_efficientnetv2_binary_run07_hyamd_finetune.yaml \
  --data-root /kaggle/working/eyeai_prepared_binary_dataset
```

## Major corrections

- Pretrained model loading fails loudly instead of silently using random weights.
- Frozen BatchNorm statistics remain fixed.
- Model-specific timm normalization and interpolation are used.
- Checkpoint selection uses threshold-free average precision.
- Threshold tuning runs once after checkpoint selection.
- Test data is not loaded by the training loop.
- Source-aware sampling limits the share of external positives.
- External images remain training-only.
- Ensemble predictions align by `image_id`.
- Rotation augmentation is disabled in the corrected configs.
- Checkpoints include optimizer and scaler states for later continuation.

## Cross-validation

Use `--fold 0`, `--fold 1`, or `--fold 2` with the Run 06 and Run 07 configs. The fold manifests remain patient-disjoint and HYAMD-only for validation.
