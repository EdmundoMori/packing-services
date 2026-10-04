"""Pérdidas del piloto. No entrenan.

Los dos brazos pesan igual cada estado. Sus objetivos y sus escalas no
coinciden: comparar las pérdidas no aísla el efecto de ponderar por |ΔQ|.
"""

from __future__ import annotations

import math

TIE_EPS = 1e-9
TIE_COEFFICIENT = 1.0


def classification_target(q_hats: list[float], *, eps: float = TIE_EPS) -> list[float]:
    """Uniforme sobre las candidatas a como máximo `eps` del máximo."""

    if not q_hats:
        raise ValueError("un estado sin candidatas no tiene objetivo")
    best = max(q_hats)
    selected = [1.0 if abs(value - best) <= eps else 0.0 for value in q_hats]
    total = sum(selected)
    if total <= 0:
        raise RuntimeError("el máximo no cae en su propia tolerancia")
    return [value / total for value in selected]


def softmax(logits: list[float]) -> list[float]:
    if not logits:
        raise ValueError("softmax sin logits")
    peak = max(logits)
    shifted = [math.exp(value - peak) for value in logits]
    total = sum(shifted)
    return [value / total for value in shifted]


def classification_loss(logits: list[float], q_hats: list[float], *, eps: float = TIE_EPS) -> float:
    """Entropía cruzada natural. Sin temperatura y sin usar Q_hat como probabilidad."""

    if len(logits) != len(q_hats):
        raise ValueError("logits y retornos no están alineados")
    target = classification_target(q_hats, eps=eps)
    probabilities = softmax(logits)
    loss = 0.0
    for mass, probability in zip(target, probabilities):
        if mass > 0.0:
            loss -= mass * math.log(probability)
    return loss


def _softplus(value: float) -> float:
    if value > 40.0:
        return value
    if value < -40.0:
        return math.exp(value)
    return math.log1p(math.exp(value))


def preference_loss(
    logits: list[float],
    q_hats: list[float],
    *,
    eps: float = TIE_EPS,
    tie_coefficient: float = TIE_COEFFICIENT,
) -> float:
    """Suma del término de pares ordenados y del término de empates.

    Un par no empatado se orienta del mayor Q_hat al menor. Su pérdida es
    softplus(-(logit_mayor - logit_menor)) y su peso es |ΔQ|, normalizado
    para que los pesos del estado sumen 1. Un empate aporta la media de
    (logit_i - logit_j)^2, multiplicada por el coeficiente. Si falta una
    clase de pares, ese término vale 0.
    """

    if len(logits) != len(q_hats):
        raise ValueError("logits y retornos no están alineados")
    weighted: list[tuple[float, float]] = []
    ties: list[float] = []
    for left in range(len(q_hats)):
        for right in range(left + 1, len(q_hats)):
            delta = q_hats[left] - q_hats[right]
            if abs(delta) <= eps:
                ties.append((logits[left] - logits[right]) ** 2)
                continue
            if delta > 0:
                high, low, magnitude = logits[left], logits[right], delta
            else:
                high, low, magnitude = logits[right], logits[left], -delta
            weighted.append((magnitude, _softplus(-(high - low))))
    pair_term = 0.0
    if weighted:
        total = sum(weight for weight, _loss in weighted)
        pair_term = sum(weight / total * loss for weight, loss in weighted)
    tie_term = 0.0
    if ties:
        tie_term = tie_coefficient * (sum(ties) / len(ties))
    return pair_term + tie_term


def mean_state_loss(state_losses: list[float]) -> float:
    """Cada estado pesa uno, con independencia de cuántas candidatas tenga."""

    if not state_losses:
        raise ValueError("no hay estados")
    return sum(state_losses) / len(state_losses)


def fit_normalization(rows: list[list[float]]) -> dict[str, list[float]]:
    """Media y desviación poblacional. Una columna constante usa denominador 1."""

    if not rows:
        raise ValueError("train no tiene filas")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("las filas no tienen la misma anchura")
    count = len(rows)
    means: list[float] = []
    scales: list[float] = []
    for column in range(width):
        values = [row[column] for row in rows]
        mean = sum(values) / count
        variance = sum((value - mean) ** 2 for value in values) / count
        deviation = math.sqrt(variance)
        means.append(mean)
        scales.append(1.0 if deviation == 0.0 else deviation)
    return {"mean": means, "scale": scales, "denominator": "population_std_or_1_if_constant", "n_rows": count}


def apply_normalization(row: list[float], stats: dict[str, list[float]]) -> list[float]:
    return [(value - mean) / scale for value, mean, scale in zip(row, stats["mean"], stats["scale"])]
