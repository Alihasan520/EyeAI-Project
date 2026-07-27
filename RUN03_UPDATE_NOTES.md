# EyeAI AMD3 — Run 03 Fixed Unfreeze + Center/Macula Crop

This patch adds the third experiment.

## Goal

Improve the previous regularized EfficientNetV2-S experiment by fixing the unfreeze behavior and adding a low-cost center/macula crop.

## Main changes

- Adds `configs/train_efficientnetv2_binary_macula_fixed_unfreeze.yaml`.
- Adds `crop_mode: center_macula` and `center_crop_scale: 0.65`.
- Fixes CNN unfreezing using `last_param_percent`, not block-count based unfreezing.
- Saves the raw best checkpoint whenever validation score improves, even if the improvement is smaller than `min_delta`.
- Keeps `min_delta` only for early stopping decisions.
- Reduces `head_lr` to `3e-5`.
- Keeps live tqdm output and robust config-path handling.
- Adds a new Kaggle notebook: `notebooks/04_hyamd_macula_fixed_unfreeze_kaggle.ipynb`.

## Files to add/overwrite

Copy this folder into the repository root.

New files:

- `configs/train_efficientnetv2_binary_macula_fixed_unfreeze.yaml`
- `notebooks/04_hyamd_macula_fixed_unfreeze_kaggle.ipynb`
- `RUN03_UPDATE_NOTES.md`

Overwrite files:

- `src/eyeai/data/transforms.py`
- `src/eyeai/models/cnn_models.py`
- `src/eyeai/training/train_binary.py`
- `scripts/train_binary.py`
- `scripts/prepare_hyamd.py`

## Kaggle command

```bash
python -u scripts/prepare_hyamd.py --config configs/train_efficientnetv2_binary_macula_fixed_unfreeze.yaml
python -u scripts/train_binary.py --config configs/train_efficientnetv2_binary_macula_fixed_unfreeze.yaml
```

Do not use the test set until validation confirms that this run improves over the previous baseline.
