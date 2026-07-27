from typing import Tuple, Dict, List
import torch
import torch.nn as nn
import timm
from timm.data import resolve_model_data_config


def _try_create_timm_model(timm_name: str, pretrained: bool, num_classes: int, dropout: float):
    """Create a timm model. If a model does not accept drop_rate, retry without it."""
    try:
        return timm.create_model(
            timm_name,
            pretrained=pretrained,
            num_classes=num_classes,
            drop_rate=float(dropout),
        )
    except TypeError:
        return timm.create_model(timm_name, pretrained=pretrained, num_classes=num_classes)


def build_cnn_model(config: dict, device: torch.device) -> Tuple[nn.Module, Dict]:
    timm_name = config.get("timm_name", "tf_efficientnetv2_s.in21k_ft_in1k")
    fallback = config.get("fallback_timm_name", "efficientnetv2_rw_s")
    num_classes = int(config.get("num_classes", 2))
    pretrained = bool(config.get("pretrained", True))
    dropout = float(config.get("dropout", 0.0))

    report = {
        "requested_model": timm_name,
        "pretrained_requested": pretrained,
        "dropout": dropout,
    }

    require_pretrained = bool(config.get("require_pretrained", pretrained))
    allow_random_fallback = bool(config.get("allow_random_fallback", False))
    report["require_pretrained"] = require_pretrained

    try:
        model = _try_create_timm_model(timm_name, pretrained=pretrained, num_classes=num_classes, dropout=dropout)
        report["created_model"] = timm_name
        report["pretrained_used"] = pretrained
    except Exception as exc:
        report["creation_error"] = repr(exc)
        if require_pretrained or not allow_random_fallback:
            raise RuntimeError(
                f"Failed to create required pretrained model '{timm_name}'. "
                "The run was stopped to avoid silent random initialization."
            ) from exc
        model = _try_create_timm_model(fallback, pretrained=False, num_classes=num_classes, dropout=dropout)
        report["created_model"] = fallback
        report["pretrained_used"] = False
        report["fallback_reason"] = repr(exc)

    data_config = resolve_model_data_config(model)
    report["data_config"] = {
        "input_size": list(data_config.get("input_size", (3, 224, 224))),
        "mean": list(data_config.get("mean", (0.485, 0.456, 0.406))),
        "std": list(data_config.get("std", (0.229, 0.224, 0.225))),
        "interpolation": str(data_config.get("interpolation", "bilinear")),
        "crop_pct": float(data_config.get("crop_pct", 1.0)),
    }

    model = model.to(device)
    return model, report


def _set_requires_grad(module: nn.Module, requires_grad: bool) -> None:
    for p in module.parameters():
        p.requires_grad = requires_grad


def _param_count(module: nn.Module) -> int:
    return sum(p.numel() for p in module.parameters())


def _trainable_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def _total_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


def _mark_classifier_trainable(model: nn.Module) -> Dict:
    """Set common classifier/head modules trainable for timm CNN models."""
    names = []
    for name in ["classifier", "head", "fc"]:
        if hasattr(model, name):
            module = getattr(model, name)
            if isinstance(module, nn.Module):
                _set_requires_grad(module, True)
                names.append(name)
    return {"classifier_modules": names}


def _flatten_blocks(model: nn.Module) -> List[Tuple[str, nn.Module]]:
    """Flatten EfficientNet/ConvNeXt style blocks into smaller trainability units."""
    blocks = getattr(model, "blocks", None)
    if blocks is None or not hasattr(blocks, "__len__"):
        return []

    flattened = []
    for stage_idx, stage in enumerate(blocks):
        if isinstance(stage, nn.Sequential) and len(stage) > 0:
            for block_idx, block in enumerate(stage):
                flattened.append((f"blocks.{stage_idx}.{block_idx}", block))
        else:
            flattened.append((f"blocks.{stage_idx}", stage))
    return flattened


def _unfreeze_tail_by_param_percent(model: nn.Module, unfreeze_percent: float) -> Dict:
    """Unfreeze classifier plus tail blocks until the trainable parameter budget is reached."""
    total_params = _total_count(model)
    target_params = max(1, int(total_params * float(unfreeze_percent)))

    report = {
        "target_trainable_params": target_params,
        "target_trainable_percent": float(unfreeze_percent) * 100.0,
        "unfrozen_blocks": [],
    }

    # Keep the classification layer trainable.
    report.update(_mark_classifier_trainable(model))

    # Add final lightweight feature head modules when present.
    for name in ["conv_head", "bn2"]:
        if hasattr(model, name):
            module = getattr(model, name)
            if isinstance(module, nn.Module):
                _set_requires_grad(module, True)
                report.setdefault("extra_modules", []).append(name)

    candidates = _flatten_blocks(model)
    if not candidates:
        report["warning"] = "model.blocks not found; only classifier/head/final modules were unfrozen"
        return report

    for name, module in reversed(candidates):
        if _trainable_count(model) >= target_params:
            break
        _set_requires_grad(module, True)
        report["unfrozen_blocks"].append({
            "name": name,
            "params": _param_count(module),
        })

    report["actual_trainable_params"] = _trainable_count(model)
    report["actual_trainable_percent"] = 100.0 * _trainable_count(model) / max(1, total_params)
    return report


def set_cnn_trainability(model: nn.Module, strategy: str = "all", unfreeze_percent: float = 0.30) -> Dict:
    """
    Configure trainable layers for CNN-style timm models.

    Strategies:
    - all: train all parameters.
    - head_only: freeze backbone and train only classifier/head.
    - last_param_percent: train classifier + tail blocks up to a target parameter budget.
    - last_percent / last_blocks_only: kept for compatibility, now mapped to last_param_percent.
    """
    strategy = (strategy or "all").lower()
    report = {"strategy": strategy, "unfreeze_percent": float(unfreeze_percent)}

    if strategy == "all":
        _set_requires_grad(model, True)
        report["trainable_region"] = "all_parameters"
        return report

    _set_requires_grad(model, False)

    if strategy in {"head_only", "classifier_only"}:
        report.update(_mark_classifier_trainable(model))
        report["trainable_region"] = "classifier_head_only"
        return report

    if strategy in {"last_param_percent", "last_percent", "last_blocks_only", "last_30_percent"}:
        tail_report = _unfreeze_tail_by_param_percent(model, unfreeze_percent=unfreeze_percent)
        report.update(tail_report)
        report["trainable_region"] = "classifier_plus_tail_param_budget"
        return report

    raise ValueError(f"Unsupported CNN trainability strategy: {strategy}")


def set_frozen_batchnorm_eval(model: nn.Module) -> int:
    """Keep BatchNorm statistics fixed when the layer parameters are frozen."""
    frozen = 0
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm):
            direct_params = list(module.parameters(recurse=False))
            if direct_params and all(not parameter.requires_grad for parameter in direct_params):
                module.eval()
                frozen += 1
    return frozen
