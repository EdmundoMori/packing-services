"""Ajuste linear_v1: softmax CE sobre candidatas legales del paso."""

from __future__ import annotations

from typing import Any

import numpy as np

from packing_services.online.features import FEATURE_DIM, FEATURE_NAMES
from packing_services.online.learned.checkpoint import greedy_like_linear_document


def _scaled_placeholder_init(transitions: list[dict[str, Any]]) -> tuple[np.ndarray, float]:
    doc = greedy_like_linear_document()
    weights = np.array(doc["weights"], dtype=np.float64)
    sample = transitions[: min(200, len(transitions))]
    if sample:
        stacked = np.concatenate(
            [np.asarray(tr["features"], dtype=np.float64) for tr in sample],
            axis=0,
        )
        rms = np.sqrt((stacked ** 2).mean(axis=0) + 1e-12)
        for i, name in enumerate(FEATURE_NAMES):
            if name.startswith("rank_") and rms[i] > 1.0:
                weights[i] = weights[i] / float(rms[i])
    return weights, float(doc["bias"])


def _softmax_ce_grad(features: np.ndarray, label: int, weights: np.ndarray, bias: float):
    logits = features @ weights + bias
    logits = logits - logits.max()
    exp = np.exp(logits)
    probs = exp / exp.sum()
    loss = float(-np.log(max(probs[label], 1e-12)))
    delta = probs.copy()
    delta[label] -= 1.0
    g_w = features.T @ delta
    g_b = float(delta.sum())
    return loss, g_w, g_b


def fit_linear(
    transitions: list[dict[str, Any]],
    *,
    val_transitions: list[dict[str, Any]] | None = None,
    epochs: int = 8,
    lr: float = 3e-4,
    l2: float = 1e-5,
    seed: int = 42,
    init: str = "zeros",
    require_informative: bool = True,
    require_val: bool = True,
) -> dict[str, Any]:
    """Ajuste lineal. Por defecto: init en ceros, early stopping en val.

    ``init='greedy'`` ancla los pesos a la heurística y contamina el
    aprendizaje: solo se admite como diagnóstico.
    """

    if require_informative:
        from methodology import assert_trainable_transitions

        assert_trainable_transitions(transitions, label="linear/train")
    if require_val and not val_transitions:
        from methodology import MethodologyError

        raise MethodologyError(
            "fit_linear sin val_transitions: no hay early stopping y el "
            "último epoch memoriza el train. Pasa el split de validación."
        )

    rng = np.random.default_rng(seed)
    if init == "greedy":
        weights, bias = _scaled_placeholder_init(transitions)
    elif init == "zeros":
        weights, bias = np.zeros(FEATURE_DIM, dtype=np.float64), 0.0
    else:
        raise ValueError(f"init desconocido: {init}")

    history: list[dict[str, float]] = []
    order = np.arange(len(transitions))
    best_weights = weights.copy()
    best_bias = float(bias)
    best_val_acc = -1.0
    best_val_loss = float("inf")
    best_epoch = 0
    for epoch in range(epochs):
        rng.shuffle(order)
        total_loss = 0.0
        total_acc = 0.0
        n = 0
        for idx in order:
            tr = transitions[int(idx)]
            features = np.asarray(tr["features"], dtype=np.float64)
            if features.ndim != 2 or features.shape[1] != FEATURE_DIM:
                raise ValueError(f"features con forma {features.shape}")
            label = int(tr["label"])
            loss, g_w, g_b = _softmax_ce_grad(features, label, weights, bias)
            weights -= lr * (g_w + l2 * weights)
            bias -= lr * g_b
            total_loss += loss
            total_acc += float(np.argmax(features @ weights + bias) == label)
            n += 1
        row: dict[str, float] = {
            "epoch": float(epoch + 1),
            "loss": total_loss / max(n, 1),
            "accuracy": total_acc / max(n, 1),
        }
        if val_transitions:
            val_acc = linear_accuracy(val_transitions, weights.tolist(), float(bias))
            val_loss = 0.0
            for tr in val_transitions:
                feats = np.asarray(tr["features"], dtype=np.float64)
                loss_v, _, _ = _softmax_ce_grad(feats, int(tr["label"]), weights, bias)
                val_loss += loss_v
            val_loss /= max(len(val_transitions), 1)
            row["val_loss"] = val_loss
            row["val_acc"] = val_acc
            if val_acc > best_val_acc + 1e-12 or (
                abs(val_acc - best_val_acc) <= 1e-12 and val_loss < best_val_loss
            ):
                best_val_acc = val_acc
                best_val_loss = val_loss
                best_epoch = epoch + 1
                best_weights = weights.copy()
                best_bias = float(bias)
        history.append(row)

    if val_transitions:
        weights = best_weights
        bias = best_bias
    return {
        "weights": weights.astype(float).tolist(),
        "bias": float(bias),
        "history": history,
        "best_epoch": best_epoch,
        "best_val_acc": best_val_acc if val_transitions else None,
        "init": init,
    }


def linear_accuracy(transitions: list[dict[str, Any]], weights: list[float], bias: float) -> float:
    w = np.asarray(weights, dtype=np.float64)
    b = float(bias)
    ok = 0
    for tr in transitions:
        features = np.asarray(tr["features"], dtype=np.float64)
        pred = int(np.argmax(features @ w + b))
        ok += int(pred == int(tr["label"]))
    return ok / max(len(transitions), 1)
