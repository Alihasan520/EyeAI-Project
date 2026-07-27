# EyeAI Results and Experiment Tracking

## Current project metadata

| Field | Value |
|---|---|
| Project | EyeAI / AMD3 |
| Team | AMD3 |
| Active task | Binary AMD detection |
| Target domain | HYAMD fundus images |
| External positive source | ARMD Curated Dataset 2023 |
| Current champion | Run 09 + horizontal-flip TTA — RETFound CFP, last 10 blocks unfrozen |
| Locked test policy | Not loaded by the training script |

---

## 1. Original severity-grading direction

### Task

| Label | Interpretation | Images |
|---:|---|---:|
| 0 | Non-AMD | 1,028 |
| 1 | Mild / transitional AMD | 108 |
| 2 | More evident AMD | 424 |

The original objective was an ordinal severity model. The middle class was too small and unstable. Direct multiclass, weighting, sampling, multi-task, and ordinal post-processing experiments either ignored class 1 or over-predicted it.

### Decision

```text
Binary competition task:
0 = Non-AMD
1 = AMD = original class 1 + class 2
```

A future ordinal model will start from the strongest binary encoder.

---

## 2. ADAM pre-adaptation

ADAM was used as an AMD-specific adaptation source for RETFound + LoRA.

| Class | Count |
|---|---:|
| Non-AMD | 311 |
| AMD | 89 |
| Total | 400 |

### Validation result after threshold tuning

| Metric | Value |
|---|---:|
| Best threshold | 0.32 |
| Accuracy | 0.7625 |
| Macro F1 | 0.6979 |
| Precision AMD | 0.4800 |
| Recall AMD | 0.6667 |
| F1 AMD | 0.5581 |

Confusion matrix:

```text
[[49, 13],
 [ 6, 12]]
```

Useful checkpoint:

```text
best_adam_retfound_lora_by_auc.pth
```

ADAM fovea coordinates, lesion masks, and optic-disc masks remain unused and may support a later true fovea-aware branch.

---

## 3. Baseline v1 binary ensemble

### Models

| Model | Image size | Role |
|---|---:|---|
| RETFound + LoRA | 224 | Retinal foundation-model branch |
| EfficientNetV2-S | 384 | High-resolution CNN branch |

Initial ensemble weights:

| Model | Weight |
|---|---:|
| RETFound + LoRA | 0.60 |
| EfficientNetV2-S | 0.40 |

Historical TTA:

```text
original
horizontal flip
rotate +7
rotate -7
```

### Test result of the historical baseline ensemble

| Metric | Image level | Patient-eye level |
|---|---:|---:|
| Accuracy | 0.7154 | 0.7162 |
| Macro F1 | 0.6633 | 0.6558 |
| F1 AMD | 0.5309 | 0.5116 |
| Precision AMD | 0.5972 | 0.7333 |
| Recall AMD | 0.4778 | 0.3929 |
| AUC | 0.7013 | 0.7547 |
| Specificity | 0.8362 | 0.9130 |

The historical test was inspected during development, so the current locked test split and future competition evaluation must be treated separately.

---

## 4. RETFound + LoRA binary baseline

Model:

```text
retfound_lora_224
```

| Parameter metric | Value |
|---|---:|
| Total parameters | 304,090,114 |
| Trainable parameters | 788,482 |
| Trainable percent | 0.2593% |
| LoRA blocks | 24 |

| Validation metric | Value |
|---|---:|
| Best epoch | 16 |
| Best threshold | 0.50 |
| Macro F1 | 0.6266 |
| Recall AMD | 0.7000 |
| Precision AMD | 0.4737 |

### Interpretation

The model was parameter-efficient and sensitive to AMD, but its adaptation budget was extremely small. This result does not establish that RETFound is weak; it mainly shows that LoRA-only adaptation was insufficient for the target domain.

---

## 5. EfficientNetV2-S original full-fundus baseline

Model:

```text
tf_efficientnetv2_s.in21k_ft_in1k
```

| Metric | Value |
|---|---:|
| Image size | 384 |
| Trainable percent | 100% |
| Best epoch | 15 |
| Best threshold | 0.98 |
| Macro F1 | 0.6907 |
| Recall AMD | 0.4667 |
| Precision AMD | 0.6885 |

### Overfitting

| Signal | Observation |
|---|---|
| Train AUC | Approximately 0.997 |
| Train Macro F1 | Approximately 0.97 |
| Validation AUC | Approximately 0.67–0.69 |
| Validation loss | Approximately 1.8–2.1 |

This was the strongest early single model, but it was unstable and poorly calibrated.

---

## 6. Run 02 — Regularized EfficientNetV2-S

Purpose:

```text
Reduce overfitting using stronger regularization and partial unfreezing.
```

| Setting | Value |
|---|---:|
| Image size | 384 |
| Dropout | 0.30 |
| Weight decay | 5e-4 |
| Label smoothing | 0.03 |
| Learning rate | 1e-5 |
| Head learning rate | 1e-4 |
| Freeze backbone | 2 epochs |
| Intended unfreeze | Last 30% |
| Actual trainable percent | 90.97% |

| Validation metric | Value |
|---|---:|
| Best epoch | 5 |
| Best threshold | 0.98 |
| Macro F1 | 0.6377 |
| AUC | 0.6752 |
| Precision AMD | 0.4915 |
| Recall AMD | 0.6444 |
| Specificity | 0.6610 |

### Interpretation

The intended last-30% strategy was implemented by stages rather than parameter budget and accidentally exposed almost the whole model. The run increased sensitivity but lost precision and is not a valid controlled partial-unfreeze experiment.

---

## 7. Run 03 — Fixed unfreeze + center crop

Model:

```text
efficientnetv2_s_384_macula_fixed_unfreeze
```

| Setting | Value |
|---|---:|
| Crop mode | Center crop |
| Center crop scale | 0.65 |
| Trainable percent | 31.53% |
| Dropout | 0.30 |
| Weight decay | 5e-4 |
| Label smoothing | 0.03 |
| Learning rate | 1e-5 |
| Head learning rate | 3e-5 |
| Class weight mode | Balanced capped |
| Max class weight | 2.0 |

| Validation metric | Value |
|---|---:|
| Best epoch | 12 |
| Best threshold | 0.985 |
| Macro F1 | 0.6448 |
| AUC | 0.6492 |
| Precision AMD | 0.5275 |
| Recall AMD | 0.5333 |
| Specificity | 0.7571 |
| TN / FP / FN / TP | 134 / 43 / 42 / 48 |

### Interpretation

The corrected unfreeze logic worked, but the geometric center was not a reliable fovea location. The crop removed useful context and did not improve discrimination.

---

## 8. Run 04 — Smart multi-ROI EfficientNetV2-S

Purpose:

```text
Replace one center crop with multiple center and peripheral ROI views.
```

Training used a randomly selected ROI, while validation averaged deterministic ROI probabilities. Artificial median fill was removed after it produced brown/red backgrounds. The final configuration used no artificial fill and rejected ROIs with excessive black pixels.

| Metric | Value |
|---|---:|
| Best epoch | 1 |
| Best threshold | 0.99 |
| Macro F1 | 0.5888 |
| Trainable percent | 41.50% |

### Interpretation

Run 04 was rejected. Positive image labels were assigned to peripheral crops that might not contain AMD lesions, creating weak-label noise. Multi-view averaging also diluted macular evidence, and rotation could reintroduce black corners after ROI validation.

---

## 9. Corrected binary pipeline

The pipeline was rebuilt before Runs 05–07.

### Data corrections

- Patient-level HYAMD splitting.
- Exact and high-confidence near-duplicate filtering.
- Portable relative image paths.
- Source-aware training manifests.
- No CLAHE, fixed gamma, artificial background fill, ROI crop, or color filtering.
- Locked test manifest excluded from training code.

### Training corrections

- Silent fallback to random CNN weights disabled.
- Frozen BatchNorm layers kept in evaluation mode.
- Model-specific normalization and interpolation used.
- Checkpoint selected by Average Precision rather than threshold-tuned F1 per epoch.
- Threshold tuned once after selecting the checkpoint.
- Ensemble predictions aligned by `image_id`.

### Corrected prepared split used by Runs 06–07

| Split | Images | Binary 0 | Binary 1 |
|---|---:|---:|---:|
| Train | 1,084 | 735 | 349 |
| Validation | 233 | 153 | 80 |
| Locked test | 243 | 140 | 103 |

ARMD Curated audit:

| Item | Count |
|---|---:|
| Discovered | 511 |
| Kept | 510 |
| Excluded | 1 |

---

## 10. Run 05 — Corrected HYAMD-only baseline

Run 05 was prepared but intentionally skipped to prioritize the competition path with external AMD data. No performance result is reported.

---

## 11. Run 06 — Corrected mixed HYAMD + ARMD training

Model:

```text
efficientnetv2_s_run06_mixed_external
```

### Data and sampling

| Item | Value |
|---|---:|
| Training rows | 1,594 |
| HYAMD training rows | 1,084 |
| ARMD Curated rows | 510 |
| HYAMD validation rows | 233 |
| Sampling negative fraction | 0.500 |
| Sampling HYAMD-positive fraction | 0.325 |
| Sampling external-positive fraction | 0.175 |

### Model settings

| Setting | Value |
|---|---:|
| Backbone | `tf_efficientnetv2_s.in21k_ft_in1k` |
| Image size | 384 |
| Crop | Full fundus |
| Dropout | 0.20 |
| Trainable tail | 36.51% |
| Selection metric | Average Precision |
| Threshold tuning | Once after checkpoint selection |

### Validation result

| Metric | Value |
|---|---:|
| Best epoch | 7 |
| Average Precision | **0.6350** |
| ROC-AUC | **0.7560** |
| Best threshold | 0.35 |
| Accuracy | 0.7725 |
| Balanced accuracy | 0.7433 |
| Macro F1 | **0.7454** |
| F1 AMD | 0.6624 |
| Precision AMD | 0.6753 |
| Recall AMD | 0.6500 |
| Specificity | 0.8366 |

Confusion matrix:

```text
[[128, 25],
 [ 28, 52]]
```

Original-class recall at the selected threshold:

| Original class | Count | Metric |
|---:|---:|---:|
| 0 | 153 | Specificity 0.8366 |
| 1 | 5 | Recall 0.4000 |
| 2 | 75 | Recall 0.6667 |

### Interpretation

Run 06 became the strongest EfficientNet branch and confirmed that source-aware external AMD training was beneficial. Overfitting appeared after epoch 7, and early stopping correctly restored the best checkpoint. It was later surpassed by the RETFound full fine-tuning branch.

---

## 12. Run 07 — HYAMD-only fine-tuning from Run 06

Model:

```text
efficientnetv2_s_run07_hyamd_finetuned
```

Run 07 loaded Run 06 epoch 7 strictly with no missing or unexpected keys, removed external images, and continued partial fine-tuning on HYAMD only.

| Metric | Run 06 | Run 07 |
|---|---:|---:|
| Average Precision | **0.6350** | 0.6237 |
| ROC-AUC | **0.7560** | 0.7461 |
| Macro F1 | **0.7454** | 0.6993 |
| Precision AMD | **0.6753** | 0.6216 |
| Recall AMD | **0.6500** | 0.5750 |
| Specificity | **0.8366** | 0.8170 |

Run 07 confusion matrix:

```text
[[125, 28],
 [ 34, 46]]
```

### Interpretation

Fine-tuning caused over-adaptation to the smaller HYAMD training set and partial forgetting of the diversity learned from external AMD images. Run 07 is preserved for analysis but is not the final model.

---

## 13. RETFound full fine-tuning setup — Runs 08–10

The official colour-fundus RETFound CFP ViT-Large/16 checkpoint was fine-tuned without LoRA.

### Prepared data used

| Split | Images | Composition |
|---|---:|---|
| Mixed training | 1,543 | 1,084 HYAMD + 459 ARMD Curated |
| Primary validation | 233 | HYAMD: 153 Non-AMD + 80 AMD |
| External positive validation | 51 | ARMD Curated AMD only |
| Locked test | 243 | HYAMD only; not loaded during training |

The 510 cleaned ARMD Curated images were divided by `split_group_id`:

| External split | Images | Fraction |
|---|---:|---:|
| Training | 459 | 90% |
| Positive-only validation | 51 | 10% |

This grouping prevents exact or grouped near-duplicate images from appearing in both external training and validation.

### Validation policy

The two validation sources were reported separately:

1. **HYAMD validation** contains both classes and controls checkpoint selection, early stopping, ROC-AUC, Average Precision, threshold tuning, Macro F1, sensitivity, and specificity.
2. **ARMD positive validation** contains AMD only and reports recall and probability statistics. It is not used to compute ROC-AUC or specificity.

### Common training configuration

| Setting | Value |
|---|---:|
| Architecture | RETFound CFP ViT-Large/16 |
| Total Transformer blocks | 24 |
| Input size | 224 |
| Global pooling | Average |
| Drop path | 0.10 |
| Batch size | 4 |
| Gradient accumulation | 4 |
| Effective batch size | 16 |
| Backbone learning rate | 2e-5 |
| Head learning rate | 1e-4 |
| Layer-wise LR decay | 0.75 |
| Weight decay | 0.05 |
| Label smoothing | 0.05 |
| Scheduler | 2-epoch warmup + cosine |
| Gradient clipping | 1.0 |
| Selection metric | HYAMD Average Precision |
| Early stopping | Patience 5, min delta 0.003 |
| Threshold tuning | Once after checkpoint selection |

Sampling targets:

| Group | Target fraction |
|---|---:|
| HYAMD Non-AMD | 0.500 |
| HYAMD AMD | 0.325 |
| External AMD | 0.175 |

Augmentations:

- Full fundus.
- Horizontal flip.
- Mild brightness, contrast, and saturation.
- No rotation, ROI crop, CLAHE, fixed gamma, random erasing, MixUp, or CutMix.

### Checkpoint loading verification

The RETFound checkpoint contained 294 tensor keys. A total of 292 backbone tensors were loaded, representing a full compatible backbone load. The only expected missing model parameters were the new `fc_norm` and binary classification head parameters. There were no shape mismatches.

---

## 14. Run 08 — RETFound, last 6 blocks unfrozen

Model:

```text
retfound_cfp_run08_last6_mixed
```

### Trainability

| Metric | Value |
|---|---:|
| Unfrozen blocks | 18–23 |
| Unfrozen block count | 6 |
| Total parameters | 303,303,682 |
| Trainable parameters | 75,581,442 |
| Trainable percent | 24.92% |

### Best HYAMD validation result

| Metric | Value |
|---|---:|
| Best epoch | 11 |
| Average Precision | 0.8319 |
| ROC-AUC | 0.8839 |
| Best threshold | 0.295 |
| Accuracy | 0.8197 |
| Balanced accuracy | **0.8121** |
| Macro F1 | 0.8045 |
| F1 AMD | **0.7500** |
| Precision AMD | 0.7159 |
| Recall AMD | **0.7875** |
| Specificity | 0.8366 |

Confusion matrix:

```text
[[128, 25],
 [ 17, 63]]
```

Original-class performance:

| Original class | Count | Result |
|---:|---:|---:|
| 0 | 153 | Specificity 0.8366 |
| 1 | 5 | Recall 0.8000 |
| 2 | 75 | Recall 0.7867 |

External positive validation:

| Metric | Value |
|---|---:|
| Images | 51 |
| Recall at threshold 0.295 | 1.0000 |
| Recall at threshold 0.50 | 0.9804 |
| Mean AMD probability | 0.9649 |

### Interpretation

Run 08 provided the highest AMD sensitivity among Runs 08–10. It detected 63 of 80 HYAMD AMD cases, but generated more false positives than Run 09. It is the preferred sensitivity-oriented checkpoint and remains useful for a future ensemble.

Saved checkpoints:

```text
/kaggle/working/eyeai_binary_ensemble/runs/run08_retfound_last6/checkpoints/retfound_cfp_run08_last6_mixed_best.pth
/kaggle/working/eyeai_binary_ensemble/runs/run08_retfound_last6/checkpoints/retfound_cfp_run08_last6_mixed_last.pth
```

---

## 15. Run 09 — RETFound, last 10 blocks unfrozen

Model:

```text
retfound_cfp_run09_last10_mixed
```

### Trainability

| Metric | Value |
|---|---:|
| Unfrozen blocks | 14–23 |
| Unfrozen block count | 10 |
| Total parameters | 303,303,682 |
| Trainable parameters | 125,966,338 |
| Trainable percent | 41.53% |

### Best HYAMD validation result

| Metric | Value |
|---|---:|
| Best epoch | 11 |
| Average Precision | 0.8395 |
| ROC-AUC | 0.8873 |
| Best threshold | 0.33 |
| Accuracy | **0.8283** |
| Balanced accuracy | 0.8067 |
| Macro F1 | **0.8085** |
| F1 AMD | 0.7468 |
| Precision AMD | **0.7564** |
| Recall AMD | 0.7375 |
| Specificity | **0.8758** |

Confusion matrix:

```text
[[134, 19],
 [ 21, 59]]
```

Metrics at the default threshold 0.50:

| Metric | Value |
|---|---:|
| Macro F1 | 0.7796 |
| Precision AMD | 0.8136 |
| Recall AMD | 0.6000 |
| Specificity | 0.9281 |
| TN / FP / FN / TP | 142 / 11 / 32 / 48 |

Original-class performance at threshold 0.33:

| Original class | Count | Result |
|---:|---:|---:|
| 0 | 153 | Specificity 0.8758 |
| 1 | 5 | Recall 0.8000 |
| 2 | 75 | Recall 0.7333 |

External positive validation:

| Metric | Value |
|---|---:|
| Images | 51 |
| Recall at threshold 0.33 | 1.0000 |
| Recall at threshold 0.50 | 0.9804 |
| Mean AMD probability | 0.9656 |

### Training behavior and overfitting

At the selected epoch, training performance was higher than validation performance:

```text
Train AP ≈ 0.954
Validation AP = 0.8395
Train AUC ≈ 0.948
Validation AUC = 0.8873
```

After epoch 11, training metrics continued to improve while validation AP declined or fluctuated. This indicates moderate overfitting, but early stopping protected the selected checkpoint by restoring epoch 11.

### Interpretation

Run 09 offers the best overall balance. Compared with Run 08, it sacrifices four true positives but removes six false positives, increasing precision, specificity, accuracy, and Macro F1. It is the current competition champion and the checkpoint selected for the next development stage.

Saved checkpoints:

```text
/kaggle/working/eyeai_binary_ensemble/runs/run09_retfound_last10/checkpoints/retfound_cfp_run09_last10_mixed_best.pth
/kaggle/working/eyeai_binary_ensemble/runs/run09_retfound_last10/checkpoints/retfound_cfp_run09_last10_mixed_last.pth
```

---

## 16. Run 10 — RETFound, last 12 blocks unfrozen

Model:

```text
retfound_cfp_run10_last12_mixed
```

### Trainability

| Metric | Value |
|---|---:|
| Unfrozen blocks | 12–23 |
| Unfrozen block count | 12 |
| Total parameters | 303,303,682 |
| Trainable parameters | 151,158,786 |
| Trainable percent | 49.84% |

### Best HYAMD validation result

| Metric | Value |
|---|---:|
| Best epoch | 11 |
| Average Precision | **0.8399** |
| ROC-AUC | **0.8880** |
| Best threshold | 0.33 |
| Accuracy | 0.8240 |
| Balanced accuracy | 0.8034 |
| Macro F1 | 0.8043 |
| F1 AMD | 0.7421 |
| Precision AMD | 0.7468 |
| Recall AMD | 0.7375 |
| Specificity | 0.8693 |

Confusion matrix:

```text
[[133, 20],
 [ 21, 59]]
```

External positive validation:

| Metric | Value |
|---|---:|
| Images | 51 |
| Recall at threshold 0.33 | 1.0000 |
| Recall at threshold 0.50 | 0.9804 |
| Mean AMD probability | 0.9660 |

### Interpretation

Run 10 achieved numerically higher AP and AUC than Run 09 by less than 0.001, while its Macro F1, accuracy, precision, and specificity were slightly lower. The additional trainable blocks did not provide a meaningful practical gain. Further unfreezing is not currently justified.

Saved checkpoints:

```text
/kaggle/working/eyeai_binary_ensemble/runs/run10_retfound_last12/checkpoints/retfound_cfp_run10_last12_mixed_best.pth
/kaggle/working/eyeai_binary_ensemble/runs/run10_retfound_last12/checkpoints/retfound_cfp_run10_last12_mixed_last.pth
```

---

## 17. RETFound comparison and decision

| Metric | Run 08: last 6 | Run 09: last 10 | Run 10: last 12 |
|---|---:|---:|---:|
| Trainable percent | 24.92% | 41.53% | 49.84% |
| Best epoch | 11 | 11 | 11 |
| Average Precision | 0.8319 | 0.8395 | **0.8399** |
| ROC-AUC | 0.8839 | 0.8873 | **0.8880** |
| Accuracy | 0.8197 | **0.8283** | 0.8240 |
| Balanced accuracy | **0.8121** | 0.8067 | 0.8034 |
| Macro F1 | 0.8045 | **0.8085** | 0.8043 |
| F1 AMD | **0.7500** | 0.7468 | 0.7421 |
| Precision AMD | 0.7159 | **0.7564** | 0.7468 |
| Recall AMD | **0.7875** | 0.7375 | 0.7375 |
| Specificity | 0.8366 | **0.8758** | 0.8693 |

Decision:

```text
Current champion: Run 09 + horizontal-flip TTA.
Base checkpoint: Run 09 — RETFound CFP, last 10 blocks unfrozen.
Sensitivity checkpoint: Run 08 — RETFound CFP, last 6 blocks unfrozen.
Run 10 is retained but does not replace Run 09.
```

Run 09 remains the strongest base checkpoint. Horizontal-flip TTA is adopted because it improved the fixed-split Macro F1 and AMD recall without increasing false positives. The result remains provisional because repeated model selection used the same 233-image HYAMD validation split.

---

## 18. Current limitations

1. The primary validation contains 233 images and only five original class-1 images.
2. Runs 06–10 and threshold selection used the same primary validation split.
3. ARMD external validation is positive-only and cannot measure external false-positive behavior.
4. The selected threshold is optimized on the current HYAMD validation split and is not yet calibrated using out-of-fold predictions.
5. Input resolution 224 may miss subtle small drusen or pigmentary changes.
6. Moderate overfitting appears after the selected epoch.

---

## 19. Current development decision

### Completed — Limited TTA on Run 09

No retraining was required.

```text
Prediction = mean(
    original image probability,
    horizontal-flip probability
)
```

Rotational and ROI TTA remain excluded.

### Completed — Run 11 patient-level 3-fold cross-validation

Three independent RETFound models were trained from the official CFP checkpoint using the Run 09 architecture at 224 resolution. Each fold used patient-disjoint HYAMD training and validation partitions, while external ARMD positives remained training-only except for the fixed positive-only external validation set.

The experiment produced a robust OOF estimate over all 1,317 HYAMD development images. Its performance was materially lower than the fixed 233-image validation result, showing that the original Run 09 split was comparatively favorable and that split-selection bias must be reported explicitly.

### Deferred — Re-training Run 11

The saved Run 11 outputs were lost when the Kaggle session ended without saving output. Re-training the three folds is not currently prioritized because:

- The OOF estimate was already recorded.
- The fold models did not outperform Run 09.
- Repeating three expensive training runs would mainly reproduce the same robustness result.
- The current competition priority has shifted to productization.

### Deferred — Progressive 336 fine-tuning

Run 12 remains available as a future experiment, but it is not part of the immediate plan. The likely gain is small and not guaranteed, while the product value of packaging and deploying the current champion is higher.

### Active next stage — Productization

```text
Run 09 best checkpoint
+ horizontal-flip TTA
+ threshold 0.335
→ versioned model package
→ standalone inference engine
→ FastAPI service
```

The locked test remains untouched.

---

## 20. Artifacts to preserve

```text
run08_retfound_last6/checkpoints/retfound_cfp_run08_last6_mixed_best.pth
run09_retfound_last10/checkpoints/retfound_cfp_run09_last10_mixed_best.pth
run10_retfound_last12/checkpoints/retfound_cfp_run10_last12_mixed_best.pth
```

The complete Kaggle output root is:

```text
/kaggle/working/eyeai_binary_ensemble
```

A Quick Save with output preserves this directory in the saved Kaggle notebook version, but the files should also be attached or exported before future sessions that require checkpoint loading.

## 21. Prepared champion-optimization pipeline

The project now includes a controlled implementation of the next four stages.

### TTA evaluation

Script:

```text
scripts/evaluate_binary_tta.py
```

The saved Run 09 checkpoint is evaluated twice on HYAMD validation:

```text
original only
original + horizontal flip
```

No model weights are updated. The report stores metrics at the original Run 09 threshold and at a separately tuned TTA development threshold.

### Run 11 — Run 09 architecture with 3-fold patient-level cross-validation

Config:

```text
configs/train_retfound_binary_run11_last10_cv.yaml
```

Outputs:

```text
/kaggle/working/eyeai_binary_ensemble/runs/run11_retfound_last10_cv/
```

Each fold uses a different seed (`42 + fold`) and saves independent `best.pth` and `last.pth` files. Automatic resume is enabled when a restored `last.pth` exists.

### OOF threshold and fold ensemble

Script:

```text
scripts/build_oof_ensemble.py
```

It verifies that every OOF image occurs once, matches the fold validation manifest, and has no overlap with another fold. It then saves:

```text
run11_oof_predictions.csv
run11_oof_summary.json
run11_oof_threshold.json
run11_external_positive_fold_ensemble_predictions.csv
```

The OOF threshold is intended for the final fold ensemble on unseen data.

### Run 12 — Progressive 336 fine-tuning

Config:

```text
configs/train_retfound_binary_run12_progressive336.yaml
```

Run 12 starts from the saved Run 09 best checkpoint, interpolates the learned positional embedding from 224 to 336, keeps the last 10 blocks trainable, and uses a lower learning rate with an effective batch size of 16.

Notebook:

```text
notebooks/08_retfound_run09_champion_optimization_kaggle.ipynb
```

The locked test fold-ensemble cell is disabled by default.

---

## 22. Run 09 horizontal-flip TTA evaluation

Run 09 was evaluated using the original image and a horizontal flip. The two AMD probabilities were averaged. No model weights were updated.

### Configuration

| Item | Value |
|---|---|
| Base checkpoint | `retfound_cfp_run09_last10_mixed_best.pth` |
| Source epoch | 11 |
| Image size | 224 |
| Variants | Original + horizontal flip |
| Aggregation | Mean probability |
| Stored Run 09 threshold | 0.33 |
| Tuned TTA threshold | 0.335 |

### Comparison on the 233-image HYAMD validation split

| Metric | Original Run 09 | Run 09 + TTA |
|---|---:|---:|
| Accuracy | 0.8283 | **0.8326** |
| Balanced accuracy | 0.8067 | **0.8129** |
| Macro F1 | 0.8085 | **0.8138** |
| F1 AMD | 0.7468 | **0.7547** |
| Precision AMD | 0.7564 | **0.7595** |
| Recall AMD | 0.7375 | **0.7500** |
| ROC-AUC | **0.8873** | 0.8872 |
| Average Precision | 0.8395 | **0.8400** |
| Specificity | 0.8758 | 0.8758 |
| TN / FP / FN / TP | 134 / 19 / 21 / 59 | **134 / 19 / 20 / 60** |

Probability change:

| Statistic | Value |
|---|---:|
| Mean absolute change | 0.0100 |
| Maximum absolute change | 0.0852 |

### Interpretation

Horizontal-flip TTA produced a small but useful improvement. It detected one additional AMD case without increasing false positives. Because it is inexpensive and requires no retraining, it is adopted as the current inference strategy.

```text
Current inference champion:
Run 09 + horizontal-flip TTA
Threshold = 0.335
```

---

## 23. Run 11 — 3-fold patient-level cross-validation

Run 11 used the same RETFound last-10-block architecture as Run 09 but trained three independent models from the official RETFound CFP checkpoint.

### Fold design

| Fold | HYAMD train | Mixed train | HYAMD validation |
|---:|---:|---:|---:|
| 0 | 889 | 1,348 | 428 |
| 1 | 836 | 1,295 | 481 |
| 2 | 909 | 1,368 | 408 |

The total OOF validation count was:

```text
428 + 481 + 408 = 1,317 images
```

Each OOF image was predicted by the single fold model that did not train on that image or its patient group.

### Fold-level ranking metrics

| Fold | Best epoch | Average Precision | ROC-AUC |
|---:|---:|---:|---:|
| 0 | 6 | 0.6462 | 0.7793 |
| 1 | 5 | 0.5944 | 0.7450 |
| 2 | 8 | 0.6312 | 0.7569 |

The fold results were consistently below the original Run 09 validation result, indicating that the fixed 233-image validation split was easier than the broader patient-level development distribution.

---

## 24. Run 11 OOF result

### OOF result at the tuned threshold

| Metric | Value |
|---|---:|
| OOF images | 1,317 |
| Best threshold | 0.60 |
| Accuracy | 0.7509 |
| Balanced accuracy | 0.6894 |
| Macro F1 | 0.6986 |
| F1 AMD | 0.5729 |
| Precision AMD | 0.6490 |
| Recall AMD | 0.5128 |
| ROC-AUC | 0.7525 |
| Average Precision | 0.6068 |
| Specificity | 0.8660 |
| TN / FP / FN / TP | 769 / 119 / 209 / 220 |

### OOF result at threshold 0.50

| Metric | Value |
|---|---:|
| Accuracy | 0.7320 |
| Balanced accuracy | 0.6934 |
| Macro F1 | 0.6940 |
| F1 AMD | 0.5862 |
| Precision AMD | 0.5896 |
| Recall AMD | 0.5828 |
| Specificity | 0.8041 |
| TN / FP / FN / TP | 714 / 174 / 179 / 250 |

### Threshold interpretation

The OOF Macro F1 difference between thresholds 0.60 and 0.50 was only approximately 0.0046. Threshold 0.60 increased precision and specificity but reduced AMD recall substantially.

```text
Threshold 0.60:
Higher precision and specificity
Lower AMD sensitivity

Threshold 0.50:
Higher AMD sensitivity
Slightly lower Macro F1
```

The OOF threshold is not adopted for the current Run 09 product package because the fold checkpoints were not retained and the product uses the saved Run 09 checkpoint with its validated TTA threshold.

### External positive fold ensemble

| Metric | Value |
|---|---:|
| External positive images | 51 |
| Recall at threshold 0.60 | 1.0000 |
| Recall at threshold 0.50 | 1.0000 |
| Mean AMD probability | 0.9682 |
| Minimum AMD probability | 0.6249 |

The external-positive set remained easy for all fold models. Because it contains no external negatives, it cannot estimate external specificity or source-related false positives.

### Interpretation

The OOF result is the most conservative robustness estimate obtained so far:

```text
Fixed-split Run 09 + TTA:
Macro F1 = 0.8138
AP = 0.8400
AUC = 0.8872

Patient-level OOF estimate:
Macro F1 = 0.6986
AP = 0.6068
AUC = 0.7525
```

The gap indicates split-selection bias and moderate domain/patient variability. It does not invalidate Run 09, but it prevents treating the fixed-split result as a guaranteed estimate for unseen populations.

---

## 25. Final model decision before productization

```text
Base checkpoint:
Run 09 — RETFound CFP, last 10 blocks unfrozen

Inference:
Original + horizontal flip TTA

Aggregation:
Mean AMD probability

Decision threshold:
0.335

Input size:
224 × 224
```

### Why Run 09 is retained

- It is the strongest saved checkpoint.
- TTA improved sensitivity without increasing false positives.
- Run 10 did not provide a meaningful practical improvement.
- Run 11 OOF exposed robustness limitations but did not produce a superior model.
- Re-training the three folds is not currently justified by the expected return.
- Progressive 336 fine-tuning is deferred.

### Product positioning

The current system is documented as:

```text
AI-assisted AMD screening and clinical workflow prototype
```

It is not documented as an autonomous clinical diagnosis system.

---

## 26. Model Package V1

The next project stage freezes Run 09 + TTA into a portable, versioned inference artifact.

Target output:

```text
/kaggle/working/eyeai_model_package/run09_tta_v1/
```

Expected contents:

```text
model.pth
model_config.yaml
preprocessing.json
threshold.json
labels.json
metrics.json
model_card.md
version.json
artifact_manifest.json
README.md
```

The package removes training-only state such as optimizer and AMP scaler data and preserves only the information required for inference, traceability, preprocessing, thresholding, metrics, and limitations.

### Package configuration

| Item | Value |
|---|---|
| Model version | `retfound-run09-tta-v1` |
| Architecture | RETFound CFP ViT-Large/16 |
| Input size | 224 |
| TTA | Original + horizontal flip |
| Aggregation | Mean |
| Threshold | 0.335 |
| Positive class | AMD |
| Negative class | Non-AMD |

### Next implementation stage

```text
Model Package V1
→ standalone Python predictor
→ FastAPI AI Engine
→ heatmap and overlay
→ patient and visit workflow
→ reports and frontend
```

No additional model training is required for Model Package V1.

