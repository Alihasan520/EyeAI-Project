# Run 09 Champion Optimization Update

## Added stages

1. Original + horizontal-flip TTA evaluation without training.
2. Run 11: three patient-disjoint RETFound last-10-block folds at 224.
3. OOF prediction validation, OOF threshold selection, and external-positive fold ensemble.
4. Run 12: progressive 336 fine-tuning from the saved Run 09 best checkpoint.

## Safety controls

- Run 09 outputs are never overwritten.
- The locked test fold-ensemble cell is disabled by default.
- Fold validation predictions are checked against their manifests and must be unique across folds.
- Model predictions are aligned by `image_id` before averaging.
- Run 11 and Run 12 can resume from `last.pth` after outputs are restored.
- Positional embeddings are interpolated before strict 224-to-336 checkpoint loading.

## Main notebook

```text
notebooks/08_retfound_run09_champion_optimization_kaggle.ipynb
```
