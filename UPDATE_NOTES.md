# EyeAI AMD3 — Next Experiment Updates

This patch adds the next experiment after Baseline v1.

## Main goal

Reduce EfficientNetV2-S overfitting and prepare a stronger ensemble workflow.

## New experiment

`efficientnetv2_s_384_binary_run02_regularized`

Key changes:

- freeze CNN backbone for the first 2 epochs
- train classifier head first
- unfreeze only the last 30% of CNN blocks after the freeze phase
- reduce learning rate to `1e-5`
- use stronger weight decay `5e-4`
- use dropout `0.30`
- use label smoothing `0.03`
- use early stopping with `patience=3` and `min_delta=0.005`
- add safer medical augmentations

## New/updated files

Copy the contents of this folder into the repository root `eyeai-team-AMD3/`.

Files to add:

- `configs/train_efficientnetv2_binary_regularized.yaml`
- `configs/ensemble_tuned.yaml`
- `src/eyeai/postprocessing/calibration.py`
- `scripts/tune_ensemble.py`
- `notebooks/03_hyamd_regularized_and_ensemble_kaggle.ipynb`

Files to overwrite:

- `src/eyeai/data/transforms.py`
- `src/eyeai/training/losses.py`
- `src/eyeai/models/cnn_models.py`
- `src/eyeai/models/registry.py`
- `src/eyeai/postprocessing/thresholds.py`
- `src/eyeai/training/train_binary.py`
- `src/eyeai/inference/predict.py`
- `src/eyeai/inference/ensemble.py`
- `scripts/evaluate_ensemble.py`

## Suggested run order on Kaggle

```bash
pip install -q -r requirements.txt
pip install -q -e .

python scripts/prepare_hyamd.py --config configs/train_efficientnetv2_binary_regularized.yaml
python scripts/train_binary.py --config configs/train_efficientnetv2_binary_regularized.yaml
```

After both RETFound and regularized EfficientNet validation prediction files are available:

```bash
python scripts/tune_ensemble.py --config configs/ensemble_tuned.yaml
```

## Git commands after copying

```bash
git status
git add configs scripts notebooks src/eyeai
git commit -m "Add regularized EfficientNet and ensemble tuning workflow"
git push origin main
```
