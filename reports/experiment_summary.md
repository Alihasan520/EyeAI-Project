# EyeAI Experiment Summary

## 1. HYAMD preparation and task definition

HYAMD contains three original severity labels:

| Label | Interpretation | Total images |
|---:|---|---:|
| 0 | Non-AMD | 1,028 |
| 1 | Mild / transitional AMD | 108 |
| 2 | More evident AMD | 424 |
| Total | — | 1,560 |

The initial goal was ordinal AMD severity estimation. Class 1 was too small and unstable: models either ignored it or over-predicted it after aggressive weighting. The active competition track was therefore changed to:

```text
0 = Non-AMD
1 = AMD = original class 1 + class 2
```

All HYAMD splits are patient-level. The locked test manifest is not loaded by the training script.

### Current corrected prepared split

| Split | Images | Binary 0 | Binary 1 |
|---|---:|---:|---:|
| Train | 1,084 | 735 | 349 |
| Validation | 233 | 153 | 80 |
| Locked test | 243 | 140 | 103 |
| Total | 1,560 | 1,028 | 532 |

ARMD Curated contributed 511 external AMD images. After quality and duplicate filtering, 510 remained in the first mixed-training dataset version.

## 2. ADAM adaptation

ADAM was used for AMD-aware RETFound + LoRA adaptation.

| Metric | Value |
|---|---:|
| Accuracy | 0.7625 |
| Macro F1 | 0.6979 |
| Precision AMD | 0.4800 |
| Recall AMD | 0.6667 |
| F1 AMD | 0.5581 |
| Best threshold | 0.32 |

Useful checkpoint:

```text
best_adam_retfound_lora_by_auc.pth
```

ADAM spatial information such as fovea coordinates and lesion masks has not yet been integrated into the production pipeline.

## 3. HYAMD severity experiments

Attempted methods included:

- RETFound + LoRA direct 3-class training.
- Class weights and weighted sampling.
- Multi-task binary + severity heads.
- Class-balanced losses.
- Ordinal thresholds and expected-severity post-processing.

Main finding:

```text
Original class 1 remained unstable because it was rare and visually difficult.
```

The severity track remains planned after a strong binary encoder is established.

## 4. Binary model progression

| Run | Main design | Best validation Macro F1 | Status |
|---|---|---:|---|
| Baseline RETFound + LoRA | 224, 0.2593% trainable | 0.6266 | Historical branch |
| Baseline EfficientNetV2-S | Full fundus 384, full fine-tuning | 0.6907 | Strong but overfit |
| Run 02 | Regularized EfficientNet | 0.6377 | Unfreeze bug: 90.97% trainable |
| Run 03 | Fixed unfreeze + center crop | 0.6448 | Engineering fix, weak crop |
| Run 04 | Smart multi-ROI | 0.5888 | Rejected |
| Run 05 | Corrected HYAMD-only baseline | Not run | Skipped for competition speed |
| Run 06 | Corrected mixed HYAMD + ARMD training | 0.7454 | Former EfficientNet champion |
| Run 07 | HYAMD-only fine-tuning from Run 06 | 0.6993 | Rejected as final model |
| Run 08 | RETFound, last 6 blocks | 0.8045 | Best sensitivity |
| Run 09 | RETFound, last 10 blocks | **0.8085** | Current champion |
| Run 10 | RETFound, last 12 blocks | 0.8043 | No meaningful gain over Run 09 |

## 5. Current champion — Run 09

Run 09 uses the official RETFound CFP ViT-Large/16 checkpoint with the last 10 of 24 Transformer blocks unfrozen.

### Data

| Split | Images | Composition |
|---|---:|---|
| Mixed training | 1,543 | 1,084 HYAMD + 459 ARMD Curated |
| Primary validation | 233 | HYAMD: 153 Non-AMD + 80 AMD |
| External positive validation | 51 | Held-out ARMD Curated AMD |
| Locked test | 243 | Not loaded during training |

External ARMD images were separated by `split_group_id`, leaving 459 for training and 51 for positive-only validation.

### Configuration

- Input size: 224.
- Global average pooling.
- Last 10 Transformer blocks unfrozen.
- 125,966,338 trainable parameters, representing 41.53% of the model.
- Full fundus; no ROI, rotation, CLAHE, fixed gamma, MixUp, CutMix, or random erasing.
- Source-aware sampling.
- Layer-wise learning-rate decay.
- Effective batch size 16 using gradient accumulation.
- Checkpoint selection by HYAMD Average Precision.
- Threshold tuned once after checkpoint selection.

### Best result

| Metric | Value |
|---|---:|
| Best epoch | 11 |
| Average Precision | 0.8395 |
| ROC-AUC | 0.8873 |
| Best threshold | 0.33 |
| Accuracy | 0.8283 |
| Balanced accuracy | 0.8067 |
| Macro F1 | **0.8085** |
| F1 AMD | 0.7468 |
| Precision AMD | 0.7564 |
| Recall AMD | 0.7375 |
| Specificity | 0.8758 |

Confusion matrix:

```text
[[134, 19],
 [ 21, 59]]
```

External positive validation recall was 1.000 at threshold 0.33 and 0.9804 at threshold 0.50.

The selected checkpoint shows moderate but controlled overfitting. Training metrics continued improving after epoch 11 while validation AP declined or fluctuated, and early stopping restored the epoch-11 checkpoint.

Checkpoint:

```text
/kaggle/working/eyeai_binary_ensemble/runs/run09_retfound_last10/checkpoints/retfound_cfp_run09_last10_mixed_best.pth
```

## 6. RETFound comparison

| Metric | Run 08: last 6 | Run 09: last 10 | Run 10: last 12 |
|---|---:|---:|---:|
| Average Precision | 0.8319 | 0.8395 | **0.8399** |
| ROC-AUC | 0.8839 | 0.8873 | **0.8880** |
| Macro F1 | 0.8045 | **0.8085** | 0.8043 |
| Precision AMD | 0.7159 | **0.7564** | 0.7468 |
| Recall AMD | **0.7875** | 0.7375 | 0.7375 |
| Specificity | 0.8366 | **0.8758** | 0.8693 |

Run 08 is preserved as the sensitivity-oriented checkpoint. Run 10 added trainable parameters without a meaningful practical improvement. Run 09 is the accepted current champion.

## 7. Current decision and next work

```text
Current champion:
Run 09 — RETFound CFP, last 10 blocks unfrozen.

Next sequence:
1. Test original + horizontal-flip TTA without retraining.
2. Train Run 09 on three patient-level folds at 224.
3. Produce OOF predictions and an OOF-selected threshold.
4. Evaluate Run 08 + Run 09 and fold ensembles using OOF predictions.
5. Fine-tune the saved Run 09 checkpoint at 336 resolution as a separate experiment.
6. Freeze all choices before evaluating the locked test.
```

Run 09 is a strong provisional result on unseen validation images without direct patient leakage. Cross-validation is required next to measure split stability and reduce dependence on one repeatedly used validation partition.

## 8. Implemented next-stage pipeline

The following stages are now implemented but require execution before results can be reported:

| Stage | Training required | Output |
|---|---|---|
| Run 09 TTA | No | Original vs horizontal-flip validation comparison |
| Run 11 3-fold CV | Yes, three models | Fold checkpoints and patient-unseen OOF predictions |
| OOF threshold + fold ensemble | No | One OOF threshold and averaged fold predictions on unseen manifests |
| Run 12 progressive 336 | Yes | Separate 336 checkpoint initialized from Run 09 |

Run 11 and Run 12 use automatic resume from their own `last.pth` files when restored outputs are available. The current Run 09 checkpoint remains unchanged and is used only as an inference artifact for TTA and an initialization artifact for Run 12.
