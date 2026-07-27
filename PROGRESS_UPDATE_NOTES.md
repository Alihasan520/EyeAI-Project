# EyeAI Training Progress Visibility Update

This patch improves live output during Kaggle training.

## Replaced files

- `scripts/train_binary.py`
- `src/eyeai/training/train_binary.py`

## What changed

- Adds flushed startup logs before data loading and model building.
- Shows current working directory and config path.
- Handles accidental config paths ending with a dot, e.g. `yaml.`.
- Shows tqdm progress bars for training and validation/evaluation.
- Shows batch loss and running average loss inside the progress bar.
- Prints epoch metrics with `flush=True` behavior.
- Keeps all previous checkpoint, prediction, and history saving behavior.

## Recommended Kaggle command

Run with unbuffered Python:

```bash
python -u scripts/train_binary.py --config configs/train_efficientnetv2_binary_regularized.yaml
```

Do not add a dot after `.yaml`.
