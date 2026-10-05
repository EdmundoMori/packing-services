"""Pérdidas diferenciables sobre scores Tensor.

Conserva las fórmulas y constantes de losses.py (hash congelado).
No convierte scores a float ni los desvincula del grafo.
Q_hat es etiqueta constante (sin gradiente requerido).
"""

from __future__ import annotations

from typing import Sequence

import torch
from torch import Tensor

from losses import TIE_COEFFICIENT, TIE_EPS

ARMS = ("classification", "preferences", "return_difference")


def _validate_pair(scores: Tensor, q_hats: Tensor) -> tuple[Tensor, Tensor]:
    if not isinstance(scores, Tensor) or not isinstance(q_hats, Tensor):
        raise TypeError("scores y Q_hat deben ser Tensor")
    if scores.ndim != 1 or q_hats.ndim != 1:
        raise ValueError("scores y Q_hat deben ser vectores 1-D")
    if scores.shape[0] != q_hats.shape[0]:
        raise ValueError("scores y Q_hat desalineados")
    if scores.shape[0] == 0:
        raise ValueError("estado vacío")
    if not torch.isfinite(scores).all():
        raise ValueError("scores no finitos")
    if not torch.isfinite(q_hats).all():
        raise ValueError("Q_hat no finitos")
    # Q_hat no participa del grafo de scores.
    q = q_hats.detach().to(dtype=scores.dtype, device=scores.device)
    return scores, q


def classification_loss_torch(
    scores: Tensor,
    q_hats: Tensor,
    *,
    eps: float = TIE_EPS,
) -> Tensor:
    """CE con log_softmax. Masa uniforme sobre máximos de Q_hat (±eps). Sin temperatura."""

    scores, q = _validate_pair(scores, q_hats)
    best = torch.max(q)
    selected = torch.abs(q - best) <= eps
    target = selected.to(dtype=scores.dtype)
    target = target / torch.sum(target)
    log_probabilities = torch.log_softmax(scores, dim=0)
    return -torch.sum(target * log_probabilities)


def preference_loss_torch(
    scores: Tensor,
    q_hats: Tensor,
    *,
    eps: float = TIE_EPS,
    tie_coefficient: float = TIE_COEFFICIENT,
) -> Tensor:
    """Pares i<j: softplus(-(s_high−s_low)) con peso |ΔQ|; empates: media de gaps² × 1."""

    scores, q = _validate_pair(scores, q_hats)
    count = int(q.shape[0])
    weighted_losses: list[Tensor] = []
    weights: list[Tensor] = []
    ties: list[Tensor] = []
    for left in range(count):
        for right in range(left + 1, count):
            delta = q[left] - q[right]
            if torch.abs(delta) <= eps:
                ties.append((scores[left] - scores[right]) ** 2)
                continue
            if delta > 0:
                high, low, magnitude = scores[left], scores[right], delta
            else:
                high, low, magnitude = scores[right], scores[left], -delta
            weighted_losses.append(torch.nn.functional.softplus(-(high - low), threshold=40.0))
            weights.append(magnitude.to(dtype=scores.dtype))
    if weights:
        weight_tensor = torch.stack(weights)
        pair_term = torch.sum(weight_tensor / torch.sum(weight_tensor) * torch.stack(weighted_losses))
    else:
        # Una candidata o solo empates: término de pares = 0 conectado al grafo.
        pair_term = scores.sum() * 0.0
    if ties:
        tie_term = float(tie_coefficient) * torch.mean(torch.stack(ties))
    else:
        tie_term = scores.sum() * 0.0
    return pair_term + tie_term


def return_difference_loss_torch(
    scores: Tensor,
    q_hats: Tensor,
    *,
    eps: float = TIE_EPS,
) -> Tensor:
    """Media de ((s_h−s_l)−(Q_h−Q_l))² sobre pares estrictos. Sin pares: 0 con gradiente 0."""

    scores, q = _validate_pair(scores, q_hats)
    count = int(q.shape[0])
    terms: list[Tensor] = []
    for left in range(count):
        for right in range(count):
            if left == right:
                continue
            if q[left] > q[right] + eps:
                predicted = scores[left] - scores[right]
                target = q[left] - q[right]
                terms.append((predicted - target) ** 2)
    if not terms:
        return scores.sum() * 0.0
    return torch.stack(terms).mean()


def mean_state_loss_torch(state_losses: Sequence[Tensor]) -> Tensor:
    if not state_losses:
        raise ValueError("sin estados")
    stacked = torch.stack([loss.reshape(()) for loss in state_losses])
    return stacked.mean()


def loss_for_arm_torch(arm: str, scores: Tensor, q_hats: Tensor) -> Tensor:
    if arm == "classification":
        return classification_loss_torch(scores, q_hats)
    if arm == "preferences":
        return preference_loss_torch(scores, q_hats)
    if arm == "return_difference":
        return return_difference_loss_torch(scores, q_hats)
    raise ValueError(f"brazo desconocido: {arm}")
