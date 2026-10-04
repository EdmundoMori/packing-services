"""Selector del actor sobre todas las candidatas legales del ítem actual.

No consulta el sufijo, Q_hat, el identificador del pedido ni la acción Greedy.
La normalización guardada se aplica una vez a cada vector.
"""

from __future__ import annotations

import time
from typing import Any, Sequence

import torch
from torch import nn

from actor_features import FEATURE_DIM, encode_candidate
from objectives import apply_normalization
from train_loop import select_logit_index


class ActorPolicy:
    """Puntúa cada candidata legal y elige el mayor logit."""

    def __init__(self, model: nn.Module, stats: dict[str, list[float]]) -> None:
        if len(stats["mean"]) != FEATURE_DIM or len(stats["scale"]) != FEATURE_DIM:
            raise ValueError("la normalización no tiene 17 columnas")
        self.model = model
        self.model.eval()
        self.stats = stats
        self.decision_seconds = 0.0
        self.max_candidates = 0
        self.normalization_calls = 0

    def decide(
        self,
        options: Sequence[Any],
        *,
        preview: Sequence[Any],
        remaining_count: int,
        session: Any,
        constraints: Any,
        mask: Any,
    ) -> Any | None:
        del preview, remaining_count, constraints, mask
        started = time.perf_counter()
        try:
            if not options:
                return None
            raw = [encode_candidate(session, option.item, option.candidate) for option in options]
            normalized = [apply_normalization(row, self.stats) for row in raw]
            self.normalization_calls += len(normalized)
            features = torch.tensor(normalized, dtype=torch.float32)
            with torch.no_grad():
                logits = self.model(features).reshape(-1).detach().cpu().tolist()
            chosen = options[select_logit_index(logits)]
            self.max_candidates = max(self.max_candidates, len(options))
            return chosen
        finally:
            self.decision_seconds += time.perf_counter() - started
