from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

from eyeai.data.datasets import FundusBinaryDataset
from eyeai.data.samplers import build_training_sampler
from eyeai.data.transforms import build_eval_transforms, build_train_transforms
from eyeai.models.cnn_models import set_frozen_batchnorm_eval
from eyeai.inference.checkpoint_loader import load_trained_checkpoint
from eyeai.models.registry import (
    build_model,
    build_optimizer_groups,
    configure_trainability,
    count_trainable_parameters,
)
from eyeai.postprocessing.thresholds import optimize_binary_threshold
from eyeai.training.losses import build_ce_loss
from eyeai.utils.checkpoints import load_checkpoint, save_checkpoint, save_json
from eyeai.utils.metrics import binary_metrics


def _log(message: str):
    print(message, flush=True)


def _crop_cfg(data_cfg: dict):
    return {
        "crop_mode": data_cfg.get("crop_mode", "full"),
        "eval_crop_mode": data_cfg.get("eval_crop_mode", data_cfg.get("crop_mode", "full")),
        "center_crop_scale": float(data_cfg.get("center_crop_scale", 0.75)),
        "roi_specs": data_cfg.get("roi_specs", None),
        "black_fill_mode": data_cfg.get("black_fill_mode", "none"),
        "black_threshold": int(data_cfg.get("black_threshold", 8)),
        "avoid_black_roi": bool(data_cfg.get("avoid_black_roi", False)),
        "max_black_fraction": float(data_cfg.get("max_black_fraction", 0.015)),
        "min_roi_scale": float(data_cfg.get("min_roi_scale", 0.45)),
    }


def _model_preprocess_cfg(model_report: dict) -> dict:
    data_config = model_report.get("data_config", {}) or {}
    return {
        "mean": data_config.get("mean", [0.485, 0.456, 0.406]),
        "std": data_config.get("std", [0.229, 0.224, 0.225]),
        "interpolation": data_config.get("interpolation", "bilinear"),
    }


def build_loaders(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    external_val_df: pd.DataFrame | None,
    image_size: int,
    batch_size: int,
    num_workers: int,
    data_cfg: dict,
    model_report: dict,
    augmentation_cfg: dict | None = None,
    sampling_cfg: dict | None = None,
    seed: int = 42,
):
    augmentation_cfg = augmentation_cfg or {}
    sampling_cfg = sampling_cfg or {}
    crop_cfg = _crop_cfg(data_cfg)
    preprocess_cfg = _model_preprocess_cfg(model_report)
    image_col = str(data_cfg.get("image_col", "proc_image_path"))
    image_root = data_cfg.get("resolved_dataset_root") or data_cfg.get("image_root")

    train_ds = FundusBinaryDataset(
        train_df,
        image_col=image_col,
        transform=build_train_transforms(
            image_size,
            crop_mode=crop_cfg["crop_mode"],
            center_crop_scale=crop_cfg["center_crop_scale"],
            roi_specs=crop_cfg.get("roi_specs"),
            black_fill_mode=crop_cfg.get("black_fill_mode", "none"),
            black_threshold=crop_cfg.get("black_threshold", 8),
            avoid_black_roi=crop_cfg.get("avoid_black_roi", False),
            max_black_fraction=crop_cfg.get("max_black_fraction", 0.015),
            min_roi_scale=crop_cfg.get("min_roi_scale", 0.45),
            **preprocess_cfg,
            **augmentation_cfg,
        ),
        image_root=image_root,
    )
    val_ds = FundusBinaryDataset(
        val_df,
        image_col=image_col,
        transform=build_eval_transforms(
            image_size,
            crop_mode=crop_cfg["crop_mode"],
            eval_crop_mode=crop_cfg["eval_crop_mode"],
            center_crop_scale=crop_cfg["center_crop_scale"],
            roi_specs=crop_cfg.get("roi_specs"),
            black_fill_mode=crop_cfg.get("black_fill_mode", "none"),
            black_threshold=crop_cfg.get("black_threshold", 8),
            avoid_black_roi=crop_cfg.get("avoid_black_roi", False),
            max_black_fraction=crop_cfg.get("max_black_fraction", 0.015),
            min_roi_scale=crop_cfg.get("min_roi_scale", 0.45),
            **preprocess_cfg,
        ),
        image_root=image_root,
    )

    external_val_ds = None
    if external_val_df is not None:
        external_val_ds = FundusBinaryDataset(
            external_val_df,
            image_col=image_col,
            transform=build_eval_transforms(
                image_size,
                crop_mode=crop_cfg["crop_mode"],
                eval_crop_mode=crop_cfg["eval_crop_mode"],
                center_crop_scale=crop_cfg["center_crop_scale"],
                roi_specs=crop_cfg.get("roi_specs"),
                black_fill_mode=crop_cfg.get("black_fill_mode", "none"),
                black_threshold=crop_cfg.get("black_threshold", 8),
                avoid_black_roi=crop_cfg.get("avoid_black_roi", False),
                max_black_fraction=crop_cfg.get("max_black_fraction", 0.015),
                min_roi_scale=crop_cfg.get("min_roi_scale", 0.45),
                **preprocess_cfg,
            ),
            image_root=image_root,
        )

    sampler, sampler_report = build_training_sampler(
        train_df,
        mode=sampling_cfg.get("mode", "none"),
        label_col=sampling_cfg.get("label_col", "binary_label"),
        source_col=sampling_cfg.get("source_col", "dataset_source"),
        positive_fraction=float(sampling_cfg.get("positive_fraction", 0.50)),
        external_positive_fraction=float(sampling_cfg.get("external_positive_fraction", 0.35)),
        external_sources=sampling_cfg.get("external_sources", ["armd_curated"]),
        num_samples=sampling_cfg.get("samples_per_epoch"),
        seed=seed,
    )

    loader_kwargs = {
        "batch_size": batch_size,
        "num_workers": num_workers,
        "pin_memory": torch.cuda.is_available(),
        "persistent_workers": num_workers > 0,
    }
    train_loader = DataLoader(
        train_ds,
        shuffle=sampler is None,
        sampler=sampler,
        **loader_kwargs,
    )
    val_loader = DataLoader(val_ds, shuffle=False, **loader_kwargs)
    external_val_loader = (
        DataLoader(external_val_ds, shuffle=False, **loader_kwargs)
        if external_val_ds is not None
        else None
    )
    return train_loader, val_loader, external_val_loader, sampler_report


def _binary_logit_from_two_class_logits(logits: torch.Tensor) -> torch.Tensor:
    if logits.ndim == 2 and logits.size(1) == 2:
        return logits[:, 1] - logits[:, 0]
    if logits.ndim == 1 or (logits.ndim == 2 and logits.size(1) == 1):
        return logits.view(-1)
    raise ValueError(f"Expected binary logits with shape [B, 2] or [B], got {tuple(logits.shape)}")


@torch.no_grad()
def evaluate_model(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    y_true = []
    y_prob = []
    y_logit = []
    meta_rows = []

    pbar = tqdm(loader, desc="Evaluate", leave=True, dynamic_ncols=True, mininterval=1.0, file=sys.stdout)
    for images, labels, metas in pbar:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True).long()

        if images.ndim == 5:
            batch_size, num_views, channels, height, width = images.shape
            flat_images = images.view(batch_size * num_views, channels, height, width)
            flat_labels = labels.repeat_interleave(num_views)
            flat_logits = model(flat_images)
            loss = criterion(flat_logits, flat_labels)
            view_probs = torch.softmax(flat_logits, dim=1)[:, 1].view(batch_size, num_views)
            probs = view_probs.mean(dim=1).clamp(1e-6, 1.0 - 1e-6)
            binary_logits = torch.log(probs / (1.0 - probs))
        else:
            logits = model(images)
            loss = criterion(logits, labels)
            probs = torch.softmax(logits, dim=1)[:, 1]
            binary_logits = _binary_logit_from_two_class_logits(logits)

        total_loss += loss.item() * labels.size(0)
        current_avg_loss = total_loss / max(1, len(y_true) + labels.size(0))
        pbar.set_postfix(loss=f"{loss.item():.4f}", avg_loss=f"{current_avg_loss:.4f}")
        y_true.extend(labels.detach().cpu().numpy().tolist())
        y_prob.extend(probs.detach().cpu().numpy().tolist())
        y_logit.extend(binary_logits.detach().cpu().numpy().tolist())

        for index in range(labels.size(0)):
            meta_rows.append({
                "image_id": metas["image_id"][index],
                "image_name": metas["image_name"][index],
                "patient_id": metas["patient_id"][index],
                "eye": metas["eye"][index],
                "dataset_source": metas["dataset_source"][index],
                "label": int(metas["original_label"][index]),
                "binary_label": int(labels[index].detach().cpu().item()),
            })

    y_true_array = np.asarray(y_true)
    y_prob_array = np.asarray(y_prob)
    metrics = binary_metrics(y_true_array, y_prob_array, threshold=0.5)
    metrics["loss"] = total_loss / max(len(loader.dataset), 1)

    predictions = pd.DataFrame(meta_rows)
    predictions["prob_amd"] = y_prob_array
    predictions["logit_amd"] = np.asarray(y_logit, dtype=float)
    return metrics, predictions


def positive_only_metrics(predictions: pd.DataFrame, threshold: float = 0.5) -> dict:
    if predictions.empty:
        return {}
    probabilities = predictions["prob_amd"].astype(float).to_numpy()
    return {
        "count": int(len(probabilities)),
        "threshold": float(threshold),
        "recall_amd": float((probabilities >= float(threshold)).mean()),
        "mean_probability": float(np.mean(probabilities)),
        "median_probability": float(np.median(probabilities)),
        "min_probability": float(np.min(probabilities)),
        "max_probability": float(np.max(probabilities)),
    }


def train_one_epoch(
    model,
    loader,
    criterion,
    optimizer,
    scaler,
    device,
    use_amp: bool,
    freeze_frozen_batchnorm: bool,
    gradient_clip_norm: float | None,
    gradient_accumulation_steps: int,
    epoch: int,
    epochs: int,
):
    model.train()
    frozen_bn_count = set_frozen_batchnorm_eval(model) if freeze_frozen_batchnorm else 0
    total_loss = 0.0
    y_true = []
    y_prob = []

    gradient_accumulation_steps = max(1, int(gradient_accumulation_steps))
    optimizer.zero_grad(set_to_none=True)
    pbar = tqdm(loader, desc=f"Train {epoch}/{epochs}", leave=True, dynamic_ncols=True, mininterval=1.0, file=sys.stdout)
    for step, (images, labels, _) in enumerate(pbar, start=1):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True).long()

        with torch.amp.autocast(device_type=device.type, enabled=use_amp and device.type == "cuda"):
            logits = model(images)
            loss = criterion(logits, labels)
            backward_loss = loss / gradient_accumulation_steps

        scaler.scale(backward_loss).backward()
        should_step = step % gradient_accumulation_steps == 0 or step == len(loader)
        if should_step:
            if gradient_clip_norm is not None and gradient_clip_norm > 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=float(gradient_clip_norm))
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)

        probs = torch.softmax(logits.detach(), dim=1)[:, 1]
        total_loss += loss.item() * images.size(0)
        current_avg_loss = total_loss / max(1, len(y_true) + images.size(0))
        pbar.set_postfix(loss=f"{loss.item():.4f}", avg_loss=f"{current_avg_loss:.4f}")
        y_true.extend(labels.detach().cpu().numpy().tolist())
        y_prob.extend(probs.detach().cpu().numpy().tolist())

    metrics = binary_metrics(y_true, y_prob, threshold=0.5)
    metrics["loss"] = total_loss / max(len(loader.sampler), 1)
    metrics["frozen_batchnorm_layers"] = int(frozen_bn_count)
    metrics["gradient_accumulation_steps"] = int(gradient_accumulation_steps)
    return metrics


def _is_head_parameter(name: str) -> bool:
    parts = name.split(".")
    return any(part in {"classifier", "head", "fc"} for part in parts)


def _make_optimizer(model, model_cfg: dict, train_cfg: dict):
    model_specific_groups = build_optimizer_groups(model, model_cfg, train_cfg)
    if model_specific_groups is not None:
        return torch.optim.AdamW(model_specific_groups)

    include_all = bool(train_cfg.get("optimizer_include_all_params", False))
    base_lr = float(train_cfg["lr"])
    head_lr = float(train_cfg.get("head_lr", base_lr))

    head_params = []
    backbone_params = []
    for name, parameter in model.named_parameters():
        if not include_all and not parameter.requires_grad:
            continue
        if _is_head_parameter(name):
            head_params.append(parameter)
        else:
            backbone_params.append(parameter)

    groups = []
    if backbone_params:
        groups.append({"params": backbone_params, "lr": base_lr, "initial_lr": base_lr, "group_name": "backbone"})
    if head_params:
        groups.append({"params": head_params, "lr": head_lr, "initial_lr": head_lr, "group_name": "head"})
    if not groups:
        raise RuntimeError("No trainable parameters found for optimizer.")

    optimizer = torch.optim.AdamW(groups, weight_decay=float(train_cfg["weight_decay"]))
    return optimizer


def _lr_scale(epoch: int, epochs: int, scheduler_cfg: dict) -> float:
    mode = (scheduler_cfg.get("mode", "cosine") or "none").lower()
    if mode in {"none", "constant"}:
        return 1.0

    warmup_epochs = int(scheduler_cfg.get("warmup_epochs", 0) or 0)
    min_ratio = float(scheduler_cfg.get("min_lr_ratio", 0.10))
    if warmup_epochs > 0 and epoch <= warmup_epochs:
        return max(epoch / warmup_epochs, 1e-6)

    progress_denominator = max(epochs - warmup_epochs - 1, 1)
    progress = min(max((epoch - warmup_epochs - 1) / progress_denominator, 0.0), 1.0)
    if mode == "cosine":
        return min_ratio + (1.0 - min_ratio) * 0.5 * (1.0 + math.cos(math.pi * progress))
    raise ValueError(f"Unsupported scheduler mode: {mode}")


def _apply_lr_scale(optimizer, scale: float):
    for group in optimizer.param_groups:
        group["lr"] = float(group.get("initial_lr", group["lr"])) * float(scale)


def _threshold_config(config: dict):
    threshold_cfg = config.get("threshold", {}) or {}
    return {
        "metric": threshold_cfg.get("metric", "macro_f1"),
        "grid_step": float(threshold_cfg.get("grid_step", 0.005)),
        "mode": threshold_cfg.get("mode", "balanced"),
        "min_recall": threshold_cfg.get("min_recall", None),
        "min_precision": threshold_cfg.get("min_precision", None),
        "min_specificity": threshold_cfg.get("min_specificity", None),
    }


def _selection_config(config: dict):
    selection_cfg = config.get("selection", {}) or {}
    return {
        "metric": selection_cfg.get("metric", "average_precision"),
        "mode": selection_cfg.get("mode", "max"),
        "min_delta": float(selection_cfg.get("min_delta", config.get("training", {}).get("min_delta", 0.0))),
    }


def _selection_value(metrics: dict, selection_cfg: dict) -> float:
    metric = selection_cfg["metric"]
    if metric not in metrics:
        raise KeyError(f"Selection metric is not available: {metric}")
    value = float(metrics[metric])
    if not np.isfinite(value):
        raise RuntimeError(f"Selection metric is not finite: {metric}={value}")
    return value if selection_cfg["mode"] == "max" else -value


def _load_initial_weights(model, train_cfg: dict, device) -> dict:
    path_value = train_cfg.get("initial_checkpoint")
    if not path_value:
        return {"loaded": False}

    _, report = load_trained_checkpoint(
        model,
        checkpoint_path=Path(path_value),
        map_location=device,
        strict=bool(train_cfg.get("initial_checkpoint_strict", True)),
    )
    return report


def _subgroup_recall(predictions: pd.DataFrame, threshold: float) -> dict:
    result = {}
    for original_label in [0, 1, 2]:
        subset = predictions[predictions["label"] == original_label]
        if subset.empty:
            continue
        predicted = (subset["prob_amd"].to_numpy() >= threshold).astype(int)
        if original_label == 0:
            result["specificity_original_class_0"] = float((predicted == 0).mean())
        else:
            result[f"recall_original_class_{original_label}"] = float((predicted == 1).mean())
        result[f"count_original_class_{original_label}"] = int(len(subset))
    return result


def train_binary_model(
    config: dict,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df=None,
    external_val_df: pd.DataFrame | None = None,
):
    del test_df
    device = torch.device(
        "cuda"
        if torch.cuda.is_available() and config.get("run", {}).get("device", "cuda") == "cuda"
        else "cpu"
    )
    run_cfg = config.get("run", {})
    data_cfg = config["data"]
    model_cfg = config["model"]
    train_cfg = config["training"]
    out_cfg = config["outputs"]
    augmentation_cfg = config.get("augmentation", {}) or {}
    sampling_cfg = config.get("sampling", {}) or {}
    scheduler_cfg = config.get("scheduler", {}) or {}
    selection_cfg = _selection_config(config)
    threshold_cfg = _threshold_config(config)

    checkpoint_dir = Path(out_cfg["checkpoint_dir"])
    log_dir = Path(out_cfg["log_dir"])
    pred_dir = Path(out_cfg["prediction_dir"])
    for directory in [checkpoint_dir, log_dir, pred_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    image_size = int(data_cfg["image_size"])
    batch_size = int(train_cfg["batch_size"])
    num_workers = int(data_cfg.get("num_workers", 2))
    crop_cfg = _crop_cfg(data_cfg)
    seed = int(run_cfg.get("seed", 42))

    _log("\n" + "=" * 90)
    _log(f"Starting binary training: {model_cfg.get('name', 'unknown_model')}")
    _log("=" * 90)
    _log(f"Device: {device}")
    _log(f"Image size: {image_size} | Batch size: {batch_size} | Num workers: {num_workers}")
    _log(f"Crop mode: {crop_cfg['crop_mode']} | eval_crop_mode={crop_cfg['eval_crop_mode']}")
    _log(f"Selection metric: {selection_cfg['metric']} ({selection_cfg['mode']})")
    _log("Train binary distribution:\n" + str(train_df["binary_label"].value_counts().sort_index()))
    _log("Validation binary distribution:\n" + str(val_df["binary_label"].value_counts().sort_index()))
    if "dataset_source" in train_df.columns:
        _log("Train source distribution:\n" + str(train_df["dataset_source"].value_counts()))
    if external_val_df is not None:
        _log(
            "External positive validation distribution:\n"
            + str(external_val_df["dataset_source"].value_counts())
        )

    _log("Building model...")
    model, model_report = build_model(model_cfg, device)
    initial_checkpoint_report = _load_initial_weights(model, train_cfg, device)
    _log(f"Model report: {model_report}")
    _log(f"Initial checkpoint report: {initial_checkpoint_report}")

    _log("Building data loaders...")
    train_loader, val_loader, external_val_loader, sampler_report = build_loaders(
        train_df=train_df,
        val_df=val_df,
        external_val_df=external_val_df,
        image_size=image_size,
        batch_size=batch_size,
        num_workers=num_workers,
        data_cfg=data_cfg,
        model_report=model_report,
        augmentation_cfg=augmentation_cfg,
        sampling_cfg=sampling_cfg,
        seed=seed,
    )
    _log(f"Sampler report: {sampler_report}")

    criterion, class_weights = build_ce_loss(
        train_df["binary_label"].values,
        num_classes=2,
        mode=train_cfg.get("class_weight_mode", "none"),
        max_weight=float(train_cfg.get("max_class_weight", 2.0)),
        device=device,
        label_smoothing=float(train_cfg.get("label_smoothing", 0.0)),
    )
    _log(f"Class weights: {class_weights.detach().cpu().tolist() if class_weights is not None else None}")

    epochs = int(train_cfg["epochs"])
    patience = int(train_cfg.get("patience", 5))
    use_amp = bool(train_cfg.get("use_amp", True))
    freeze_frozen_batchnorm = bool(train_cfg.get("freeze_frozen_batchnorm", True))
    gradient_clip_norm = train_cfg.get("gradient_clip_norm", 1.0)
    gradient_accumulation_steps = int(train_cfg.get("gradient_accumulation_steps", 1))
    _log(
        f"Gradient accumulation: {gradient_accumulation_steps} | "
        f"effective batch size: {batch_size * gradient_accumulation_steps}"
    )
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp and device.type == "cuda")

    optimizer = None
    current_phase = None
    best_selection_value = -float("inf")
    best_selection_raw = None
    best_loss = float("inf")
    best_epoch = -1
    early_best = -float("inf")
    early_counter = 0
    history = []

    model_name = model_cfg["name"]
    best_path = checkpoint_dir / f"{model_name}_best.pth"
    last_path = checkpoint_dir / f"{model_name}_last.pth"
    history_path = log_dir / f"{model_name}_history.csv"

    start_epoch = 1
    resume_payload = None
    if bool(train_cfg.get("auto_resume", False)) and last_path.exists():
        resume_payload = load_checkpoint(last_path, map_location=device)
        model.load_state_dict(resume_payload["model_state_dict"], strict=True)
        start_epoch = int(resume_payload.get("epoch", 0)) + 1
        best_selection_raw = resume_payload.get("best_selection_raw")
        best_epoch = int(resume_payload.get("best_epoch", -1))
        best_loss = float(resume_payload.get("best_loss", float("inf")))
        early_counter = int(resume_payload.get("early_counter", 0))
        early_best = float(resume_payload.get("early_best", -float("inf")))
        if best_selection_raw is not None:
            raw_value = float(best_selection_raw)
            best_selection_value = raw_value if selection_cfg["mode"] == "max" else -raw_value
        elif best_path.exists():
            existing_best = load_checkpoint(best_path, map_location="cpu")
            raw_value = float(existing_best.get("selection_score", -float("inf")))
            best_selection_raw = raw_value
            best_selection_value = raw_value if selection_cfg["mode"] == "max" else -raw_value
            best_epoch = int(existing_best.get("epoch", best_epoch))
            best_loss = float(
                (existing_best.get("validation_metrics_at_0_5") or {}).get("loss", best_loss)
            )
        if history_path.exists():
            history = pd.read_csv(history_path).to_dict("records")
        _log(f"Auto-resume loaded: {last_path} | next epoch={start_epoch}")

    for epoch in range(start_epoch, epochs + 1):
        trainability_report = configure_trainability(model, model_cfg, train_cfg, epoch=epoch)
        param_report = count_trainable_parameters(model)
        phase = trainability_report.get("trainable_region", trainability_report.get("strategy", "default"))

        if optimizer is None or phase != current_phase:
            optimizer = _make_optimizer(model, model_cfg, train_cfg)
            current_phase = phase
            _log(f"Optimizer rebuilt for phase '{phase}'.")
            if resume_payload is not None and epoch == start_epoch:
                optimizer_state = resume_payload.get("optimizer_state_dict")
                scaler_state = resume_payload.get("scaler_state_dict")
                if optimizer_state:
                    optimizer.load_state_dict(optimizer_state)
                if scaler_state:
                    scaler.load_state_dict(scaler_state)
                _log("Optimizer and AMP scaler state restored from last checkpoint.")

        lr_scale = _lr_scale(epoch, epochs, scheduler_cfg)
        _apply_lr_scale(optimizer, lr_scale)

        train_metrics = train_one_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion,
            optimizer=optimizer,
            scaler=scaler,
            device=device,
            use_amp=use_amp,
            freeze_frozen_batchnorm=freeze_frozen_batchnorm,
            gradient_clip_norm=gradient_clip_norm,
            gradient_accumulation_steps=gradient_accumulation_steps,
            epoch=epoch,
            epochs=epochs,
        )
        val_metrics, val_predictions = evaluate_model(model, val_loader, criterion, device)
        external_metrics = None
        external_predictions = None
        if external_val_loader is not None:
            _, external_predictions = evaluate_model(model, external_val_loader, criterion, device)
            external_metrics = positive_only_metrics(external_predictions, threshold=0.5)
        selection_value = _selection_value(val_metrics, selection_cfg)
        selection_raw = float(val_metrics[selection_cfg["metric"]])

        raw_improved = (
            selection_value > best_selection_value + 1e-12
            or (abs(selection_value - best_selection_value) <= 1e-12 and val_metrics["loss"] < best_loss)
        )
        early_improved = selection_value > early_best + selection_cfg["min_delta"]

        payload = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scaler_state_dict": scaler.state_dict(),
            "selection_metric": selection_cfg["metric"],
            "selection_score": selection_raw,
            "validation_metrics_at_0_5": val_metrics,
            "external_positive_validation_at_0_5": external_metrics,
            "model_config": model_cfg,
            "training_config": train_cfg,
            "data_config": data_cfg,
            "augmentation_config": augmentation_cfg,
            "sampling_config": sampling_cfg,
            "scheduler_config": scheduler_cfg,
            "model_report": model_report,
            "initial_checkpoint_report": initial_checkpoint_report,
            "param_report": param_report,
            "trainability_report": trainability_report,
            "sampler_report": sampler_report,
            "image_size": image_size,
            "best_selection_raw": best_selection_raw,
            "best_epoch": best_epoch,
            "best_loss": best_loss,
            "early_best": early_best,
            "early_counter": early_counter,
        }

        if raw_improved:
            best_selection_value = selection_value
            best_selection_raw = selection_raw
            best_loss = float(val_metrics["loss"])
            best_epoch = epoch
            save_checkpoint(best_path, payload)
            val_predictions.to_csv(pred_dir / f"{model_name}_val_predictions_candidate_best.csv", index=False)
            if external_predictions is not None:
                external_predictions.to_csv(
                    pred_dir / f"{model_name}_external_val_predictions_candidate_best.csv",
                    index=False,
                )

        if early_improved:
            early_best = selection_value
            early_counter = 0
        else:
            early_counter += 1

        payload.update({
            "best_selection_raw": best_selection_raw,
            "best_epoch": best_epoch,
            "best_loss": best_loss,
            "early_best": early_best,
            "early_counter": early_counter,
        })
        save_checkpoint(last_path, payload)

        row = {
            "epoch": epoch,
            "phase": phase,
            "is_best": raw_improved,
            "selection_metric": selection_cfg["metric"],
            "selection_score": selection_raw,
            "best_selection_score": best_selection_raw,
            "best_epoch": best_epoch,
            "early_counter": early_counter,
            "lr_scale": lr_scale,
            "trainable_parameters": param_report["trainable"],
            "trainable_percent": param_report["trainable_percent"],
        }
        for group in optimizer.param_groups:
            row[f"lr_{group.get('group_name', 'group')}"] = group["lr"]
        row.update({f"train_{key}": value for key, value in train_metrics.items()})
        row.update({f"val_{key}": value for key, value in val_metrics.items()})
        if external_metrics is not None:
            row.update({f"external_val_{key}": value for key, value in external_metrics.items()})
        history.append(row)
        pd.DataFrame(history).to_csv(history_path, index=False)

        _log("\n" + "=" * 90)
        _log(f"Epoch {epoch}/{epochs} | phase={phase} | trainable={param_report['trainable_percent']:.2f}%")
        _log(
            f"Train loss={train_metrics['loss']:.4f} AP={train_metrics['average_precision']:.4f} "
            f"AUC={train_metrics['auc']:.4f}"
        )
        _log(
            f"Val loss={val_metrics['loss']:.4f} AP={val_metrics['average_precision']:.4f} "
            f"AUC={val_metrics['auc']:.4f} MacroF1@0.5={val_metrics['macro_f1']:.4f}"
        )
        if external_metrics is not None:
            _log(
                f"External positive val recall@0.5={external_metrics['recall_amd']:.4f} "
                f"mean_prob={external_metrics['mean_probability']:.4f}"
            )
        _log(
            f"Best {selection_cfg['metric']}={best_selection_raw:.4f} at epoch={best_epoch} | "
            f"early={early_counter}/{patience}"
        )

        if early_counter >= patience:
            _log("Early stopping triggered.")
            break

    if best_epoch < 0 or not best_path.exists():
        raise RuntimeError("Training finished without a valid best checkpoint.")

    _log("Loading the selected checkpoint and tuning the threshold once...")
    best_checkpoint = load_checkpoint(best_path, map_location=device)
    model.load_state_dict(best_checkpoint["model_state_dict"], strict=True)
    final_val_metrics, final_val_predictions = evaluate_model(model, val_loader, criterion, device)
    threshold_result = optimize_binary_threshold(
        final_val_predictions["binary_label"].values,
        final_val_predictions["prob_amd"].values,
        metric=threshold_cfg["metric"],
        grid_step=threshold_cfg["grid_step"],
        mode=threshold_cfg["mode"],
        min_recall=threshold_cfg["min_recall"],
        min_precision=threshold_cfg["min_precision"],
        min_specificity=threshold_cfg["min_specificity"],
    )
    threshold = float(threshold_result["threshold"])
    subgroup_metrics = _subgroup_recall(final_val_predictions, threshold)
    final_external_metrics_at_threshold = None
    final_external_metrics_at_0_5 = None
    final_external_predictions = None
    if external_val_loader is not None:
        _, final_external_predictions = evaluate_model(model, external_val_loader, criterion, device)
        final_external_metrics_at_threshold = positive_only_metrics(
            final_external_predictions, threshold=threshold
        )
        final_external_metrics_at_0_5 = positive_only_metrics(
            final_external_predictions, threshold=0.5
        )

    best_checkpoint["best_threshold"] = threshold
    best_checkpoint["threshold_result"] = threshold_result
    best_checkpoint["final_validation_metrics_at_0_5"] = final_val_metrics
    best_checkpoint["original_class_metrics_at_threshold"] = subgroup_metrics
    best_checkpoint["external_positive_validation_at_threshold"] = final_external_metrics_at_threshold
    best_checkpoint["external_positive_validation_at_0_5"] = final_external_metrics_at_0_5
    save_checkpoint(best_path, best_checkpoint)
    final_val_predictions.to_csv(pred_dir / f"{model_name}_val_predictions_best.csv", index=False)
    if final_external_predictions is not None:
        final_external_predictions.to_csv(
            pred_dir / f"{model_name}_external_val_predictions_best.csv",
            index=False,
        )

    summary = {
        "model_name": model_name,
        "best_epoch": best_epoch,
        "selection_metric": selection_cfg["metric"],
        "best_selection_score": best_selection_raw,
        "best_threshold": threshold,
        "validation_metrics_at_threshold": threshold_result["metrics"],
        "validation_metrics_at_0_5": final_val_metrics,
        "original_class_metrics_at_threshold": subgroup_metrics,
        "external_positive_validation_at_threshold": final_external_metrics_at_threshold,
        "external_positive_validation_at_0_5": final_external_metrics_at_0_5,
        "best_checkpoint": str(best_path),
        "last_checkpoint": str(last_path),
        "model_report": model_report,
        "initial_checkpoint_report": initial_checkpoint_report,
        "sampler_report": sampler_report,
        "final_param_report": count_trainable_parameters(model),
        "selection_config": selection_cfg,
        "threshold_config": threshold_cfg,
        "crop_config": crop_cfg,
    }
    save_json(log_dir / f"{model_name}_summary.json", summary)
    _log("Training complete.")
    _log(str(summary))
    return summary
