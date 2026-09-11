"""Backends de inferencia para el contrato packing-services-online-policy."""

from __future__ import annotations

from typing import Any, Protocol

from ...utils.errors import InvalidInputError
from ..features import FEATURE_DIM
from .checkpoint import load_checkpoint_document, resolve_model_path


class ScoreBackend(Protocol):
    def score(self, rows: list[list[float]]) -> list[float]:
        """Un logit por fila (candidata)."""


class LinearBackend:
    """score = w · x + b. Sin dependencias extra."""

    def __init__(self, weights: list[float], bias: float = 0.0) -> None:
        if len(weights) != FEATURE_DIM:
            raise InvalidInputError(
                f"weights tiene {len(weights)} valores; el encoder v1 espera {FEATURE_DIM}."
            )
        self.weights = [float(w) for w in weights]
        self.bias = float(bias)

    def score(self, rows: list[list[float]]) -> list[float]:
        out: list[float] = []
        for row in rows:
            if len(row) != FEATURE_DIM:
                raise InvalidInputError(
                    f"Fila de features con dim={len(row)}; se espera {FEATURE_DIM}."
                )
            acc = self.bias
            for w, x in zip(self.weights, row, strict=True):
                acc += w * x
            out.append(acc)
        return out


class TorchMlpV1Backend:
    """MLP feature_dim → hidden → 1. Requiere PyTorch y architecture=mlp_v1."""

    def __init__(self, payload: dict[str, Any]) -> None:
        try:
            import torch
            from torch import nn
        except ImportError as exc:
            raise InvalidInputError(
                "backend=torch requiere PyTorch "
                "(pip install 'packing-services[torch]')."
            ) from exc

        hidden = int(payload.get("hidden_size", 64))
        state = payload.get("state_dict")
        if not isinstance(state, dict):
            raise InvalidInputError(
                "checkpoint torch mlp_v1 requiere 'state_dict'. "
                "Guarde el dict del contrato con torch.save tras entrenar."
            )
        model = nn.Sequential(
            nn.Linear(FEATURE_DIM, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )
        try:
            model.load_state_dict(state)
        except Exception as exc:
            raise InvalidInputError(
                f"state_dict incompatible con mlp_v1 "
                f"(Linear({FEATURE_DIM},{hidden})→ReLU→Linear({hidden},1)): {exc}"
            ) from exc
        model.eval()
        self._torch = torch
        self._model = model

    def score(self, rows: list[list[float]]) -> list[float]:
        if not rows:
            return []
        with self._torch.no_grad():
            tensor = self._torch.tensor(rows, dtype=self._torch.float32)
            logits = self._model(tensor).squeeze(-1)
            if logits.ndim == 0:
                return [float(logits.item())]
            return [float(v) for v in logits.tolist()]


def load_backend(model_path: object) -> ScoreBackend:
    path = resolve_model_path(model_path)
    payload = load_checkpoint_document(path)
    backend = str(payload.get("backend", "linear")).lower()
    if backend == "linear":
        weights = payload.get("weights")
        if not isinstance(weights, list):
            raise InvalidInputError("checkpoint linear requiere lista 'weights'.")
        return LinearBackend(weights, bias=float(payload.get("bias", 0.0)))
    if backend == "torch":
        architecture = str(payload.get("architecture", "mlp_v1")).lower()
        if architecture != "mlp_v1":
            raise InvalidInputError(
                f"architecture={architecture!r} no soportada. Use mlp_v1 "
                f"(Linear {FEATURE_DIM}→H→1) o backend=linear."
            )
        return TorchMlpV1Backend(payload)
    raise InvalidInputError(
        f"backend={backend!r} no soportado. Use 'linear' o 'torch'."
    )
