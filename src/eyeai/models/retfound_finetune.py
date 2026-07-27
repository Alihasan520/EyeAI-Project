from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
import timm


_HEAD_PREFIXES = ("head.",)
_DECODER_MARKERS = ("decoder", "mask_token")


def _load_torch_checkpoint(path: Path):
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def _checkpoint_state_dict(checkpoint) -> Dict[str, torch.Tensor]:
    if isinstance(checkpoint, dict):
        for key in ("model", "model_state_dict", "state_dict"):
            if key in checkpoint and isinstance(checkpoint[key], dict):
                checkpoint = checkpoint[key]
                break

    if not isinstance(checkpoint, dict):
        raise TypeError("RETFound checkpoint does not contain a state dictionary.")

    cleaned: Dict[str, torch.Tensor] = {}
    for name, value in checkpoint.items():
        if not torch.is_tensor(value):
            continue
        clean_name = str(name)
        for prefix in ("module.", "backbone.", "encoder."):
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):]
        if any(marker in clean_name for marker in _DECODER_MARKERS):
            continue
        cleaned[clean_name] = value
    return cleaned


def _resolve_checkpoint(config: dict) -> Path:
    candidates: list[Path] = []
    configured = config.get("retfound_checkpoint_path")
    if configured:
        candidates.append(Path(configured))
    for value in config.get("retfound_checkpoint_fallbacks", []) or []:
        candidates.append(Path(value))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    checked = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError(
        "RETFound CFP checkpoint was not found. Checked:\n"
        f"{checked}\n"
        "Attach the RETFound checkpoint Kaggle Dataset or update the config path."
    )


def interpolate_position_embedding(model: nn.Module, state_dict: Dict[str, torch.Tensor]) -> bool:
    if "pos_embed" not in state_dict or not hasattr(model, "pos_embed"):
        return False

    source = state_dict["pos_embed"]
    target = model.pos_embed
    if source.shape == target.shape:
        return False
    if source.ndim != 3 or target.ndim != 3 or source.shape[-1] != target.shape[-1]:
        raise RuntimeError(
            f"Cannot interpolate positional embedding from {tuple(source.shape)} to {tuple(target.shape)}."
        )

    target_patches = int(model.patch_embed.num_patches)
    target_extra = int(target.shape[1] - target_patches)
    source_extra = target_extra
    source_patches = int(source.shape[1] - source_extra)
    source_side = int(round(math.sqrt(source_patches)))
    target_side = int(round(math.sqrt(target_patches)))
    if source_side * source_side != source_patches or target_side * target_side != target_patches:
        raise RuntimeError("RETFound positional embeddings are not square grids.")

    extra_tokens = source[:, :source_extra]
    patch_tokens = source[:, source_extra:]
    patch_tokens = patch_tokens.reshape(1, source_side, source_side, source.shape[-1]).permute(0, 3, 1, 2)
    patch_tokens = F.interpolate(
        patch_tokens,
        size=(target_side, target_side),
        mode="bicubic",
        align_corners=False,
    )
    patch_tokens = patch_tokens.permute(0, 2, 3, 1).reshape(1, target_side * target_side, source.shape[-1])
    state_dict["pos_embed"] = torch.cat((extra_tokens, patch_tokens), dim=1)
    return True


def _load_retfound_weights(model: nn.Module, checkpoint_path: Path, min_loaded_fraction: float) -> dict:
    checkpoint = _load_torch_checkpoint(checkpoint_path)
    source_state = _checkpoint_state_dict(checkpoint)
    target_state = model.state_dict()

    for key in list(_HEAD_PREFIXES):
        weight_key = f"{key}weight" if key.endswith(".") else f"{key}.weight"
        bias_key = f"{key}bias" if key.endswith(".") else f"{key}.bias"
        for candidate in (weight_key, bias_key):
            if candidate in source_state and (
                candidate not in target_state or source_state[candidate].shape != target_state[candidate].shape
            ):
                source_state.pop(candidate)

    position_interpolated = interpolate_position_embedding(model, source_state)

    compatible: Dict[str, torch.Tensor] = {}
    skipped_shape: list[str] = []
    unexpected_source: list[str] = []
    for key, value in source_state.items():
        if key not in target_state:
            unexpected_source.append(key)
            continue
        if target_state[key].shape != value.shape:
            skipped_shape.append(key)
            continue
        compatible[key] = value

    incompatible = model.load_state_dict(compatible, strict=False)

    excluded_target_prefixes = ("head.", "fc_norm.")
    expected_backbone_numel = sum(
        tensor.numel()
        for key, tensor in target_state.items()
        if not key.startswith(excluded_target_prefixes)
    )
    loaded_backbone_numel = sum(
        tensor.numel()
        for key, tensor in compatible.items()
        if not key.startswith(excluded_target_prefixes)
    )
    loaded_fraction = loaded_backbone_numel / max(expected_backbone_numel, 1)
    if loaded_fraction < float(min_loaded_fraction):
        raise RuntimeError(
            "RETFound checkpoint loading coverage is too low: "
            f"{loaded_fraction:.4f} < {float(min_loaded_fraction):.4f}."
        )

    allowed_missing = {"head.weight", "head.bias", "fc_norm.weight", "fc_norm.bias"}
    unexpected_missing = sorted(set(incompatible.missing_keys) - allowed_missing)
    if unexpected_missing:
        raise RuntimeError(
            "Unexpected missing RETFound keys after checkpoint loading: "
            f"{unexpected_missing[:30]}"
        )

    return {
        "checkpoint_path": str(checkpoint_path),
        "source_tensor_keys": int(len(source_state)),
        "loaded_tensor_keys": int(len(compatible)),
        "loaded_backbone_fraction": float(loaded_fraction),
        "position_embedding_interpolated": bool(position_interpolated),
        "missing_keys": sorted(incompatible.missing_keys),
        "unexpected_model_keys": sorted(incompatible.unexpected_keys),
        "unexpected_source_keys": sorted(unexpected_source)[:50],
        "shape_mismatch_keys": sorted(skipped_shape)[:50],
    }


def set_retfound_trainability(model: nn.Module, unfreeze_last_blocks: int) -> dict:
    if not hasattr(model, "blocks"):
        raise TypeError("RETFound model does not expose Transformer blocks.")

    block_count = len(model.blocks)
    unfreeze_last_blocks = int(unfreeze_last_blocks)
    if not 1 <= unfreeze_last_blocks <= block_count:
        raise ValueError(
            f"unfreeze_last_blocks must be between 1 and {block_count}, got {unfreeze_last_blocks}."
        )

    for parameter in model.parameters():
        parameter.requires_grad = False

    first_trainable_block = block_count - unfreeze_last_blocks
    for block in model.blocks[first_trainable_block:]:
        for parameter in block.parameters():
            parameter.requires_grad = True

    for module_name in ("fc_norm", "norm", "head"):
        module = getattr(model, module_name, None)
        if module is not None:
            for parameter in module.parameters():
                parameter.requires_grad = True

    return {
        "strategy": "retfound_last_blocks",
        "trainable_region": f"retfound_last_{unfreeze_last_blocks}_blocks",
        "total_blocks": int(block_count),
        "frozen_blocks": int(first_trainable_block),
        "unfrozen_blocks": int(unfreeze_last_blocks),
        "first_trainable_block": int(first_trainable_block),
        "trainable_block_indices": list(range(first_trainable_block, block_count)),
    }


def _layer_id_for_name(name: str, block_count: int) -> int:
    if name in {"cls_token", "pos_embed"} or name.startswith("patch_embed."):
        return 0
    if name.startswith("blocks."):
        parts = name.split(".")
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[1]) + 1
    return block_count + 1


def build_retfound_optimizer_groups(model: nn.Module, model_config: dict, train_config: dict) -> list[dict]:
    block_count = len(model.blocks)
    max_layer_id = block_count + 1
    layer_decay = float(train_config.get("layer_decay", 0.75))
    backbone_lr = float(train_config["lr"])
    head_lr = float(train_config.get("head_lr", backbone_lr))
    weight_decay = float(train_config.get("weight_decay", 0.05))

    groups: dict[tuple[int, bool, bool], dict] = {}
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue

        is_head = name.startswith("head.")
        layer_id = _layer_id_for_name(name, block_count)
        no_decay = (
            parameter.ndim == 1
            or name.endswith(".bias")
            or name in {"cls_token", "pos_embed"}
            or "norm" in name.lower()
        )
        key = (layer_id, no_decay, is_head)
        if key not in groups:
            if is_head:
                lr = head_lr
                group_name = "retfound_head"
            else:
                lr_scale = layer_decay ** (max_layer_id - layer_id)
                lr = backbone_lr * lr_scale
                group_name = f"retfound_layer_{layer_id}_{'no_decay' if no_decay else 'decay'}"
            groups[key] = {
                "params": [],
                "lr": float(lr),
                "initial_lr": float(lr),
                "weight_decay": 0.0 if no_decay else weight_decay,
                "group_name": group_name,
            }
        groups[key]["params"].append(parameter)

    result = list(groups.values())
    if not result:
        raise RuntimeError("No trainable RETFound parameters were found for the optimizer.")
    return result


def build_retfound_finetune(config: dict, device: torch.device) -> Tuple[nn.Module, dict]:
    timm_name = str(config.get("timm_name", "vit_large_patch16_224"))
    num_classes = int(config.get("num_classes", 2))
    input_size = int(config.get("input_size", 224))
    drop_path_rate = float(config.get("drop_path_rate", 0.10))
    global_pool = str(config.get("global_pool", "avg"))
    unfreeze_last_blocks = int(config.get("unfreeze_last_blocks", 6))

    model = timm.create_model(
        timm_name,
        pretrained=False,
        num_classes=num_classes,
        img_size=input_size,
        global_pool=global_pool,
        drop_path_rate=drop_path_rate,
    )
    if len(model.blocks) != 24:
        raise RuntimeError(f"Expected RETFound ViT-Large with 24 blocks, found {len(model.blocks)}.")

    checkpoint_path = _resolve_checkpoint(config)
    load_report = _load_retfound_weights(
        model,
        checkpoint_path=checkpoint_path,
        min_loaded_fraction=float(config.get("min_loaded_backbone_fraction", 0.95)),
    )

    if hasattr(model, "head") and isinstance(model.head, nn.Linear):
        nn.init.trunc_normal_(model.head.weight, std=2e-5)
        if model.head.bias is not None:
            nn.init.zeros_(model.head.bias)

    trainability_report = set_retfound_trainability(model, unfreeze_last_blocks)
    model = model.to(device)

    report = {
        "base_model": timm_name,
        "architecture": "RETFound CFP ViT-Large/16",
        "input_size": [3, input_size, input_size],
        "global_pool": global_pool,
        "drop_path_rate": drop_path_rate,
        "checkpoint_report": load_report,
        "trainability_report": trainability_report,
        "data_config": {
            "input_size": [3, input_size, input_size],
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
            "interpolation": "bicubic",
            "crop_pct": 1.0,
        },
    }
    return model, report
