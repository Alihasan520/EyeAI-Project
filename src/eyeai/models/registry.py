import torch

from eyeai.models.cnn_models import build_cnn_model, set_cnn_trainability
from eyeai.models.retfound_finetune import (
    build_retfound_finetune,
    build_retfound_optimizer_groups,
    set_retfound_trainability,
)
from eyeai.models.retfound_lora import build_retfound_lora


def build_model(model_config: dict, device: torch.device):
    model_type = model_config.get("type")
    if model_type == "retfound_lora":
        return build_retfound_lora(model_config, device)
    if model_type == "retfound_finetune":
        return build_retfound_finetune(model_config, device)
    if model_type in {"efficientnetv2_s", "efficientnet_b4", "convnext_tiny"}:
        return build_cnn_model(model_config, device)
    raise ValueError(f"Unsupported model type: {model_type}")


def configure_trainability(model, model_config: dict, train_config: dict, epoch: int | None = None):
    """Configure trainable layers for staged fine-tuning."""
    model_type = model_config.get("type")

    if model_type == "retfound_finetune":
        return set_retfound_trainability(
            model,
            unfreeze_last_blocks=int(model_config.get("unfreeze_last_blocks", 6)),
        )

    if model_type not in {"efficientnetv2_s", "efficientnet_b4", "convnext_tiny"}:
        return {"strategy": "default", "message": "trainability unchanged for this model type"}

    freeze_epochs = int(train_config.get("freeze_backbone_epochs", 0) or 0)
    unfreeze_strategy = train_config.get("unfreeze_strategy", "all")
    unfreeze_percent = float(train_config.get("unfreeze_percent", 0.30))

    if epoch is not None and freeze_epochs > 0 and epoch <= freeze_epochs:
        return set_cnn_trainability(model, strategy="head_only", unfreeze_percent=unfreeze_percent)

    if freeze_epochs > 0:
        return set_cnn_trainability(model, strategy=unfreeze_strategy, unfreeze_percent=unfreeze_percent)

    return set_cnn_trainability(
        model,
        strategy=train_config.get("trainability", "all"),
        unfreeze_percent=unfreeze_percent,
    )


def build_optimizer_groups(model, model_config: dict, train_config: dict):
    if model_config.get("type") == "retfound_finetune":
        return build_retfound_optimizer_groups(model, model_config, train_config)
    return None


def count_trainable_parameters(model):
    total = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    return {
        "total": total,
        "trainable": trainable,
        "trainable_percent": 100.0 * trainable / total if total else 0.0,
    }
