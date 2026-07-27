# Run 09 + TTA Model Package V1

This patch freezes the current champion into a portable inference artifact without retraining.

## Added

- Model-package export configuration.
- Inference-only checkpoint extraction that removes optimizer and training state.
- Standalone Run 09 predictor with original + horizontal-flip TTA.
- Raw-image black-border preprocessing contract.
- Structured prediction JSON and quality warnings.
- Kaggle export notebook.
- Unit tests for the package contract.

## Output

```text
/kaggle/working/eyeai_model_package/run09_tta_v1
```

Save this directory as a Kaggle Dataset after the notebook succeeds. The next patch will build FastAPI around this frozen package.
