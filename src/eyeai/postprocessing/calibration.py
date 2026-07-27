from dataclasses import dataclass
import numpy as np
import torch
import torch.nn.functional as F


def _safe_logit(prob, eps: float = 1e-6):
    prob = np.asarray(prob, dtype=np.float64)
    prob = np.clip(prob, eps, 1.0 - eps)
    return np.log(prob / (1.0 - prob))


@dataclass
class TemperatureCalibrationResult:
    temperature: float
    nll_before: float
    nll_after: float


def fit_temperature_binary_logits(logits, labels, max_iter: int = 100, device: str = "cpu") -> TemperatureCalibrationResult:
    """Fit one temperature value for binary logits on validation data."""
    logits_t = torch.tensor(np.asarray(logits, dtype=np.float32), device=device).view(-1)
    labels_t = torch.tensor(np.asarray(labels, dtype=np.float32), device=device).view(-1)

    log_temperature = torch.zeros(1, device=device, requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.05, max_iter=max_iter)

    with torch.no_grad():
        nll_before = F.binary_cross_entropy_with_logits(logits_t, labels_t).item()

    def closure():
        optimizer.zero_grad()
        temperature = torch.exp(log_temperature).clamp(min=0.05, max=20.0)
        loss = F.binary_cross_entropy_with_logits(logits_t / temperature, labels_t)
        loss.backward()
        return loss

    optimizer.step(closure)

    with torch.no_grad():
        temperature = float(torch.exp(log_temperature).clamp(min=0.05, max=20.0).item())
        nll_after = F.binary_cross_entropy_with_logits(logits_t / temperature, labels_t).item()

    return TemperatureCalibrationResult(
        temperature=temperature,
        nll_before=float(nll_before),
        nll_after=float(nll_after),
    )


def apply_temperature_to_logits(logits, temperature: float):
    logits = np.asarray(logits, dtype=np.float64)
    return logits / float(temperature)


def apply_temperature_to_probabilities(probabilities, temperature: float):
    logits = _safe_logit(probabilities)
    calibrated_logits = apply_temperature_to_logits(logits, temperature)
    return 1.0 / (1.0 + np.exp(-calibrated_logits))
