"""MLP mlp_v1 en NumPy si no hay torch en el entrenamiento."""

from __future__ import annotations

from typing import Any

import numpy as np

from packing_services.online.features import FEATURE_DIM

from config import HIDDEN_SIZE, SEED


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max()
    e = np.exp(z)
    return e / e.sum()


class NumpyMlpV1:
    def __init__(self, hidden_size: int = HIDDEN_SIZE, rng: np.random.Generator | None = None) -> None:
        rng = rng or np.random.default_rng(SEED)
        self.w1 = rng.normal(0.0, np.sqrt(2.0 / FEATURE_DIM), size=(FEATURE_DIM, hidden_size))
        self.b1 = np.zeros(hidden_size)
        self.w2 = rng.normal(0.0, np.sqrt(2.0 / hidden_size), size=(hidden_size, 1))
        self.b2 = np.zeros(1)
        self.hidden_size = hidden_size

    def logits(self, x: np.ndarray) -> np.ndarray:
        h = _relu(x @ self.w1 + self.b1)
        return (h @ self.w2 + self.b2).reshape(-1)

    def step(self, x: np.ndarray, label: int, lr: float, clip: float = 1.0) -> tuple[float, float]:
        h_pre = x @ self.w1 + self.b1
        h = _relu(h_pre)
        logits = (h @ self.w2 + self.b2).reshape(-1)
        probs = _softmax(logits)
        loss = float(-np.log(max(probs[label], 1e-12)))
        acc = float(int(np.argmax(logits) == label))
        delta = probs.copy()
        delta[label] -= 1.0
        g_w2 = h.T @ delta.reshape(-1, 1)
        g_b2 = delta.sum(keepdims=True)
        g_h = delta.reshape(-1, 1) @ self.w2.T
        g_h_pre = g_h * (h_pre > 0)
        g_w1 = x.T @ g_h_pre
        g_b1 = g_h_pre.sum(axis=0)
        for arr in (g_w1, g_b1, g_w2, g_b2):
            np.clip(arr, -clip, clip, out=arr)
        self.w1 -= lr * g_w1
        self.b1 -= lr * g_b1
        self.w2 -= lr * g_w2
        self.b2 -= lr * g_b2
        return loss, acc

    def state_arrays(self) -> dict[str, np.ndarray]:
        return {
            "0.weight": self.w1.T.astype(np.float32),
            "0.bias": self.b1.astype(np.float32),
            "2.weight": self.w2.T.astype(np.float32),
            "2.bias": self.b2.astype(np.float32),
        }


def fit_mlp_numpy(
    train_transitions: list[dict[str, Any]],
    val_transitions: list[dict[str, Any]] | None = None,
    *,
    hidden_size: int = HIDDEN_SIZE,
    epochs: int = 10,
    lr: float = 1e-3,
    seed: int = SEED,
    require_informative: bool = True,
    require_val: bool = True,
) -> dict[str, Any]:
    if require_informative:
        from methodology import assert_trainable_transitions

        assert_trainable_transitions(train_transitions, label="mlp_numpy/train")
    if require_val and not val_transitions:
        from methodology import MethodologyError

        raise MethodologyError(
            "fit_mlp_numpy sin val_transitions: no hay early stopping."
        )
    rng = np.random.default_rng(seed)
    model = NumpyMlpV1(hidden_size=hidden_size, rng=rng)
    history: list[dict[str, float]] = []
    best = None
    best_acc = -1.0
    best_loss = float("inf")
    best_epoch = 0

    def eval_split(rows: list[dict[str, Any]]) -> tuple[float, float]:
        loss_sum = 0.0
        acc_sum = 0.0
        for tr in rows:
            x = np.asarray(tr["features"], dtype=np.float64)
            logits = model.logits(x)
            probs = _softmax(logits)
            y = int(tr["label"])
            loss_sum += float(-np.log(max(probs[y], 1e-12)))
            acc_sum += float(int(np.argmax(logits) == y))
        n = max(len(rows), 1)
        return loss_sum / n, acc_sum / n

    for _epoch in range(epochs):
        order = np.arange(len(train_transitions))
        rng.shuffle(order)
        tr_loss = 0.0
        tr_acc = 0.0
        for i in order:
            tr = train_transitions[int(i)]
            x = np.asarray(tr["features"], dtype=np.float64)
            loss, acc = model.step(x, int(tr["label"]), lr=lr)
            tr_loss += loss
            tr_acc += acc
        n = max(len(train_transitions), 1)
        row: dict[str, float] = {
            "epoch": float(_epoch + 1),
            "train_loss": tr_loss / n,
            "train_acc": tr_acc / n,
        }
        if val_transitions:
            val_loss, val_acc = eval_split(val_transitions)
            row["val_loss"] = val_loss
            row["val_acc"] = val_acc
            if val_acc > best_acc + 1e-12 or (
                abs(val_acc - best_acc) <= 1e-12 and val_loss < best_loss
            ):
                best_acc = val_acc
                best_loss = val_loss
                best_epoch = _epoch + 1
                best = {k: v.copy() for k, v in model.state_arrays().items()}
        history.append(row)

    if best is not None:
        model.w1 = best["0.weight"].T.astype(np.float64)
        model.b1 = best["0.bias"].astype(np.float64)
        model.w2 = best["2.weight"].T.astype(np.float64)
        model.b2 = best["2.bias"].astype(np.float64)

    return {
        "model": model,
        "hidden_size": hidden_size,
        "history": history,
        "state_arrays": model.state_arrays(),
        "best_epoch": best_epoch,
        "best_val_acc": best_acc if best is not None else None,
    }


def arrays_to_torch_state(state_arrays: dict[str, np.ndarray]):
    import torch

    return {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in state_arrays.items()}
