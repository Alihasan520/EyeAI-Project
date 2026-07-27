from pathlib import Path
import math
from typing import Dict, Tuple
import torch
import torch.nn as nn
import timm


class LoRAQKV(nn.Module):
    def __init__(self, original_qkv: nn.Linear, rank: int = 8, alpha: int = 16, dropout: float = 0.05):
        super().__init__()
        self.original_qkv = original_qkv
        self.scaling = alpha / rank
        self.lora_dropout = nn.Dropout(dropout)
        self.lora_A = nn.Linear(original_qkv.in_features, rank, bias=False)
        self.lora_B = nn.Linear(rank, original_qkv.out_features, bias=False)
        nn.init.kaiming_uniform_(self.lora_A.weight, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B.weight)
        for p in self.original_qkv.parameters():
            p.requires_grad = False

    def forward(self, x):
        base = self.original_qkv(x)
        delta = self.lora_B(self.lora_A(self.lora_dropout(x))) * self.scaling
        return base + delta


def freeze_all(model: nn.Module) -> None:
    for p in model.parameters():
        p.requires_grad = False


def inject_lora_qkv(model: nn.Module, rank: int, alpha: int, dropout: float) -> int:
    injected = 0
    for block in model.blocks:
        if hasattr(block, "attn") and hasattr(block.attn, "qkv"):
            if isinstance(block.attn.qkv, LoRAQKV):
                continue
            block.attn.qkv = LoRAQKV(block.attn.qkv, rank=rank, alpha=alpha, dropout=dropout)
            injected += 1
    return injected


def clean_checkpoint_state_dict(checkpoint) -> Dict[str, torch.Tensor]:
    if isinstance(checkpoint, dict):
        if "model" in checkpoint:
            state_dict = checkpoint["model"]
        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        elif "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        else:
            state_dict = checkpoint
    else:
        state_dict = checkpoint

    cleaned = {}
    for k, v in state_dict.items():
        if not torch.is_tensor(v):
            continue
        new_k = k
        for prefix in ["module.", "backbone.", "encoder."]:
            if new_k.startswith(prefix):
                new_k = new_k[len(prefix):]
        if new_k.startswith("decoder") or new_k.startswith("mask_token") or "decoder_" in new_k:
            continue
        cleaned[new_k] = v
    return cleaned


def load_compatible_state(model: nn.Module, checkpoint_path: str | Path) -> Dict[str, int]:
    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    try:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except TypeError:
        checkpoint = torch.load(checkpoint_path, map_location="cpu")

    state_dict = clean_checkpoint_state_dict(checkpoint)
    target = model.state_dict()
    compatible = {}
    skipped = []

    for k, v in state_dict.items():
        if k in target and target[k].shape == v.shape:
            compatible[k] = v
        else:
            skipped.append(k)

    missing, unexpected = model.load_state_dict(compatible, strict=False)
    return {
        "source_keys": len(state_dict),
        "loaded": len(compatible),
        "skipped": len(skipped),
        "missing": len(missing),
        "unexpected": len(unexpected),
    }


def find_adam_checkpoint(adam_output_dir: str | Path | None):
    if not adam_output_dir:
        return None
    root = Path(adam_output_dir)
    if not root.exists():
        return None
    preferred = sorted(root.rglob("best_adam_retfound_lora_by_auc.pth"))
    if preferred:
        return preferred[0]
    candidates = sorted([p for p in root.rglob("*.pth") if "adam" in p.name.lower() and "auc" in p.name.lower()])
    return candidates[0] if candidates else None


def build_retfound_lora(config: dict, device: torch.device) -> Tuple[nn.Module, Dict]:
    timm_name = config.get("timm_name", "vit_large_patch16_224")
    num_classes = int(config.get("num_classes", 2))
    lora_rank = int(config.get("lora_rank", 8))
    lora_alpha = int(config.get("lora_alpha", 16))
    lora_dropout = float(config.get("lora_dropout", 0.05))

    model = timm.create_model(timm_name, pretrained=False, num_classes=num_classes)
    report = {"base_model": timm_name, "loaded_from": None}

    adam_ckpt = find_adam_checkpoint(config.get("adam_output_dir")) if config.get("use_adam_init", False) else None

    if adam_ckpt is not None:
        freeze_all(model)
        injected = inject_lora_qkv(model, rank=lora_rank, alpha=lora_alpha, dropout=lora_dropout)
        for p in model.head.parameters():
            p.requires_grad = True
        load_report = load_compatible_state(model, adam_ckpt)
        report.update({"loaded_from": str(adam_ckpt), "load_report": load_report, "lora_blocks": injected})
    else:
        retfound_path = config.get("retfound_checkpoint_path")
        if retfound_path:
            load_report = load_compatible_state(model, retfound_path)
            report.update({"loaded_from": str(retfound_path), "load_report": load_report})
        freeze_all(model)
        injected = inject_lora_qkv(model, rank=lora_rank, alpha=lora_alpha, dropout=lora_dropout)
        for p in model.head.parameters():
            p.requires_grad = True
        report["lora_blocks"] = injected

    model = model.to(device)
    return model, report
