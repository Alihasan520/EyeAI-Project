# RETFound Runs 08–10 Update

## Data preparation

- Reserves 10% of cleaned ARMD Curated images as positive-only external validation.
- Splits external data by `split_group_id` after exact and near-duplicate filtering.
- Keeps HYAMD validation as the primary checkpoint-selection set.
- Adds `manifests/armd_curated_train.csv` and `manifests/armd_curated_val_positive.csv`.
- Adds a notebook cell showing three random images before and after preprocessing.

The preparation notebook must be re-run and the Kaggle Dataset must be saved as a new version before RETFound training.

## RETFound model branch

- Adds official CFP ViT-Large/16 checkpoint loading with coverage validation.
- Uses global average pooling and strict expected-key checks.
- Adds last-6, last-10, and last-12 Transformer block unfreezing.
- Adds layer-wise learning-rate decay.
- Adds gradient accumulation for an effective batch size of 16.
- Reports ARMD positive-only validation recall separately from HYAMD metrics.

## Run order

1. Run 08: last 6 blocks.
2. Run 09: last 10 blocks only if Run 08 underfits.
3. Run 10: last 12 blocks only if Run 09 improves reliably.

Do not enable all three runs at the same time.
