"""Pérdidas del diseño revisado. Mayor score = mejor candidata.

No entrenan modelos reales. Las fórmulas de clasificación y preferencias
reproducen el piloto counterfactual. La de diferencias de retorno adapta
Mandi et al. (2022), §4.3, Eq. (13), al ranking de candidatas con Q_hat.
"""

from __future__ import annotations

import math
from typing import Sequence

TIE_EPS = 1e-9
TIE_COEFFICIENT = 1.0


def _softplus(value: float) -> float:
    if value > 40.0:
        return value
    if value < -40.0:
        return math.exp(value)
    return math.log1p(math.exp(value))


def classification_target(q_hats: Sequence[float], *, eps: float = TIE_EPS) -> list[float]:
    if not q_hats:
        raise ValueError("estado vacío")
    best = max(q_hats)
    selected = [1.0 if abs(value - best) <= eps else 0.0 for value in q_hats]
    total = sum(selected)
    return [value / total for value in selected]


def softmax(logits: Sequence[float]) -> list[float]:
    peak = max(logits)
    shifted = [math.exp(value - peak) for value in logits]
    total = sum(shifted)
    return [value / total for value in shifted]


def classification_loss(logits: Sequence[float], q_hats: Sequence[float], *, eps: float = TIE_EPS) -> float:
    """CE natural. Empates de máximo: masa uniforme. Sin temperatura."""

    if len(logits) != len(q_hats):
        raise ValueError("desalineado")
    target = classification_target(q_hats, eps=eps)
    probabilities = softmax(logits)
    loss = 0.0
    for mass, probability in zip(target, probabilities):
        if mass > 0.0:
            loss -= mass * math.log(probability)
    return loss


def preference_loss(
    logits: Sequence[float],
    q_hats: Sequence[float],
    *,
    eps: float = TIE_EPS,
    tie_coefficient: float = TIE_COEFFICIENT,
) -> float:
    """Pares no empatados con peso |ΔQ| renormalizado + penalización de empates."""

    if len(logits) != len(q_hats):
        raise ValueError("desalineado")
    weighted: list[tuple[float, float]] = []
    ties: list[float] = []
    for left in range(len(q_hats)):
        for right in range(left + 1, len(q_hats)):
            delta = float(q_hats[left]) - float(q_hats[right])
            if abs(delta) <= eps:
                ties.append((float(logits[left]) - float(logits[right])) ** 2)
                continue
            if delta > 0:
                high, low, magnitude = float(logits[left]), float(logits[right]), delta
            else:
                high, low, magnitude = float(logits[right]), float(logits[left]), -delta
            weighted.append((magnitude, _softplus(-(high - low))))
    pair_term = 0.0
    if weighted:
        total = sum(weight for weight, _loss in weighted)
        pair_term = sum(weight / total * loss for weight, loss in weighted)
    tie_term = 0.0
    if ties:
        tie_term = tie_coefficient * (sum(ties) / len(ties))
    return pair_term + tie_term


def ordered_pairs_by_return(q_hats: Sequence[float], *, eps: float = TIE_EPS) -> list[tuple[int, int]]:
    """Pares (mejor, peor) con Q_p > Q_q + eps. Todos los pares estrictos."""

    pairs = []
    for left in range(len(q_hats)):
        for right in range(len(q_hats)):
            if left == right:
                continue
            if float(q_hats[left]) > float(q_hats[right]) + eps:
                pairs.append((left, right))
    return pairs


def return_difference_loss(logits: Sequence[float], q_hats: Sequence[float], *, eps: float = TIE_EPS) -> float:
    """Adaptación de Mandi et al. (2022), §4.3, Eq. (13).

    Sustituye f(v, c) por Q_hat y f(v, ĉ) por el score del modelo.
    Denominador: número de pares ordenados estrictos en S.
    Si no hay pares (todas empatan), la pérdida es 0.
    Pendiente de congelar: ninguno adicional aquí; lr y épocas siguen abiertos.
    """

    if len(logits) != len(q_hats):
        raise ValueError("desalineado")
    pairs = ordered_pairs_by_return(q_hats, eps=eps)
    if not pairs:
        return 0.0
    total = 0.0
    for high, low in pairs:
        predicted = float(logits[high]) - float(logits[low])
        target = float(q_hats[high]) - float(q_hats[low])
        total += (predicted - target) ** 2
    return total / len(pairs)


def mean_state_loss(state_losses: Sequence[float]) -> float:
    if not state_losses:
        raise ValueError("sin estados")
    return float(sum(state_losses) / len(state_losses))
