"""Actor de despliegue: construye S y elige argmax solo dentro de S.

No usa sufijo ni Q_hat. Greedy determina el ancla de S; el actor no observa
la lista legal completa al puntuar.
"""

from __future__ import annotations

import time
from typing import Any, Sequence

import torch
from torch import nn

from actor_features import FEATURE_DIM, encode_candidate
from candidate_support import select_logit_index
from labeling_states import _action_from_option
from normalization import apply_normalization
from pipeline import labeling_select_support


class SupportConstrainedActorPolicy:
    def __init__(self, model: nn.Module, stats: dict[str, list[float]]) -> None:
        if len(stats["mean"]) != FEATURE_DIM or len(stats["scale"]) != FEATURE_DIM:
            raise ValueError("la normalización no tiene 17 columnas")
        from packing_services.online.policies import GreedyBestFitPolicy

        self.model = model
        self.model.eval()
        self.stats = stats
        self._greedy = GreedyBestFitPolicy()
        self.decision_seconds = 0.0
        self.max_candidates = 0
        self.max_support = 0
        self.normalization_calls = 0
        self.last_support_ids: list[list[Any]] | None = None
        self.last_chosen_index_in_s: int | None = None

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
        del remaining_count
        started = time.perf_counter()
        try:
            if not options:
                self.last_support_ids = []
                self.last_chosen_index_in_s = None
                return None
            greedy_choice = self._greedy.decide(
                options,
                preview=preview,
                remaining_count=0,
                session=session,
                constraints=constraints,
                mask=mask,
            )
            if greedy_choice is None:
                self.last_support_ids = []
                self.last_chosen_index_in_s = None
                return None
            support = labeling_select_support(options, greedy_choice)
            self.max_candidates = max(self.max_candidates, len(options))
            self.max_support = max(self.max_support, len(support))
            raw = [encode_candidate(session, option.item, option.candidate) for option in support]
            normalized = [apply_normalization(row, self.stats) for row in raw]
            self.normalization_calls += len(normalized)
            features = torch.tensor(normalized, dtype=torch.float32)
            with torch.no_grad():
                logits = self.model(features).reshape(-1).detach().cpu().tolist()
            index = select_logit_index(logits)
            self.last_chosen_index_in_s = index
            self.last_support_ids = [_action_from_option(opt) for opt in support]
            return support[index]
        finally:
            self.decision_seconds += time.perf_counter() - started
