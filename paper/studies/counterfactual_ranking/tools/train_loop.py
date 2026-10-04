"""Ajuste emparejado de los dos brazos. No empaqueta pedidos nuevos.

Un paso de Adam por época acumula la media de todos los estados. El orden
de esa suma es una permutación determinista de la semilla, compartida por
los dos brazos. Los retornos se comparan en float64; los logits, en float32.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Callable

import torch
from torch import nn
from torch.nn.utils import clip_grad_norm_

from model_spec import TRAINING_CONFIG, adam_for, build_actor
from objectives import TIE_COEFFICIENT, TIE_EPS, apply_normalization

ARMS = ("classification", "preferences")


class PairingError(RuntimeError):
    """La pareja no comparte inicialización o permutaciones."""


def select_logit_index(logits: list[float]) -> int:
    """Máximo logit. Un empate exacto en float se resuelve por el menor índice."""

    if not logits:
        raise ValueError("no hay logits")
    best = max(logits)
    for index, value in enumerate(logits):
        if value == best:
            return index
    raise RuntimeError("el máximo no reaparece")


def epoch_permutations(n_states: int, epochs: int, seed: int) -> list[list[int]]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    permutations = []
    for _epoch in range(epochs):
        permutations.append(torch.randperm(n_states, generator=generator).tolist())
    return permutations


def permutation_sha256(permutations: list[list[int]]) -> str:
    raw = json.dumps(permutations, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def initialization_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def clone_initialized(model: nn.Module) -> nn.Module:
    cloned = copy.deepcopy(model)
    cloned.load_state_dict(copy.deepcopy(model.state_dict()))
    return cloned


def weights_equal(left: nn.Module, right: nn.Module) -> bool:
    left_state = left.state_dict()
    right_state = right.state_dict()
    if left_state.keys() != right_state.keys():
        return False
    return all(torch.equal(left_state[name], right_state[name]) for name in left_state)


def normalize_once(features: list[list[float]], stats: dict[str, list[float]]) -> torch.Tensor:
    rows = [apply_normalization(row, stats) for row in features]
    return torch.tensor(rows, dtype=torch.float32)


def _classification_loss(logits: torch.Tensor, q_hats: torch.Tensor) -> torch.Tensor:
    best = torch.max(q_hats)
    selected = torch.abs(q_hats - best) <= TIE_EPS
    target = selected.to(dtype=logits.dtype)
    target = target / torch.sum(target)
    log_probabilities = torch.log_softmax(logits, dim=0)
    return -torch.sum(target * log_probabilities)


def _preference_loss(logits: torch.Tensor, q_hats: torch.Tensor) -> torch.Tensor:
    weighted_losses = []
    weights = []
    ties = []
    count = int(q_hats.shape[0])
    for left in range(count):
        for right in range(left + 1, count):
            delta = q_hats[left] - q_hats[right]
            if torch.abs(delta) <= TIE_EPS:
                ties.append((logits[left] - logits[right]) ** 2)
                continue
            if delta > 0:
                high, low, magnitude = logits[left], logits[right], delta
            else:
                high, low, magnitude = logits[right], logits[left], -delta
            weighted_losses.append(torch.nn.functional.softplus(-(high - low), threshold=40.0))
            weights.append(magnitude.to(dtype=logits.dtype))
    if weights:
        weight_tensor = torch.stack(weights)
        pair_term = torch.sum(weight_tensor / torch.sum(weight_tensor) * torch.stack(weighted_losses))
    else:
        pair_term = logits.new_zeros(())
    if ties:
        tie_term = TIE_COEFFICIENT * torch.mean(torch.stack(ties))
    else:
        tie_term = logits.new_zeros(())
    return pair_term + tie_term


def state_loss(logits: torch.Tensor, q_hats: torch.Tensor, arm: str) -> torch.Tensor:
    if arm == "classification":
        return _classification_loss(logits, q_hats)
    if arm == "preferences":
        return _preference_loss(logits, q_hats)
    raise ValueError(f"brazo desconocido: {arm}")


def forward_logits(model: nn.Module, features: torch.Tensor) -> torch.Tensor:
    return model(features).reshape(-1)


def train_arm(
    model: nn.Module,
    states: list[dict[str, Any]],
    permutations: list[list[int]],
    arm: str,
    *,
    on_epoch: Callable[[int], None] | None = None,
) -> list[dict[str, float | int]]:
    """Cuarenta actualizaciones como máximo: una media por época y un paso de Adam."""

    optimizer = adam_for(model)
    history = []
    for epoch, permutation in enumerate(permutations, start=1):
        optimizer.zero_grad(set_to_none=True)
        losses = []
        for index in permutation:
            state = states[index]
            logits = forward_logits(model, state["features"])
            losses.append(state_loss(logits, state["q_hats"], arm))
        objective = torch.mean(torch.stack(losses))
        if not torch.isfinite(objective):
            raise FloatingPointError(f"pérdida no finita en la época {epoch}")
        objective.backward()
        grad_norm = clip_grad_norm_(
            model.parameters(),
            max_norm=float(TRAINING_CONFIG["grad_clip_max_norm"]),
            norm_type=float(TRAINING_CONFIG["grad_clip_norm_type"]),
            error_if_nonfinite=bool(TRAINING_CONFIG["grad_clip_error_if_nonfinite"]),
        )
        optimizer.step()
        history.append(
            {
                "epoch": epoch,
                "loss": float(objective.detach().cpu()),
                "grad_norm_before_clip": float(grad_norm),
            }
        )
        if on_epoch is not None:
            on_epoch(epoch)
    return history


def paired_start(seed: int) -> tuple[nn.Module, nn.Module, str]:
    source = build_actor(seed)
    classification = clone_initialized(source)
    preferences = clone_initialized(source)
    if not weights_equal(classification, preferences) or not weights_equal(classification, source):
        raise PairingError(f"la semilla {seed} no copió la inicialización")
    return classification, preferences, initialization_sha256(source)


def regret_of(q_hats: list[float], chosen: int) -> float:
    return max(q_hats) - q_hats[chosen]


def matches_maximum(q_hats: list[float], chosen: int, *, eps: float = TIE_EPS) -> bool:
    return abs(q_hats[chosen] - max(q_hats)) <= eps


def logit_tie(logits: list[float]) -> bool:
    best = max(logits)
    return sum(value == best for value in logits) > 1


def q_multi_max(q_hats: list[float], *, eps: float = TIE_EPS) -> bool:
    best = max(q_hats)
    return sum(abs(value - best) <= eps for value in q_hats) > 1


def ranking_rows(model: nn.Module, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    with torch.no_grad():
        for state in states:
            logits = forward_logits(model, state["features"]).detach().cpu().tolist()
            chosen = select_logit_index(logits)
            q_hats = [float(value) for value in state["q_float64"]]
            rows.append(
                {
                    "order_id": state["order_id"],
                    "target": state["target"],
                    "choice_index": state["choice_index"],
                    "chosen_index": chosen,
                    "regret": regret_of(q_hats, chosen),
                    "matches_maximum": matches_maximum(q_hats, chosen),
                    "logit_tie": logit_tie(logits),
                    "q_multi_max": q_multi_max(q_hats),
                    "logits": logits,
                }
            )
    return rows


def aggregate_regret(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Media de regret por pedido y después media con igual peso por pedido."""

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["order_id"], row["target"]), []).append(row)
    per_order = []
    for (order_id, target), items in grouped.items():
        per_order.append(
            {
                "order_id": order_id,
                "target": target,
                "n_states": len(items),
                "regret": sum(item["regret"] for item in items) / len(items),
                "match_rate": sum(1.0 if item["matches_maximum"] else 0.0 for item in items) / len(items),
                "logit_ties": sum(1 for item in items if item["logit_tie"]),
                "q_multi_max": sum(1 for item in items if item["q_multi_max"]),
            }
        )
    per_order.sort(key=lambda item: item["order_id"])

    def _mean(subset: list[dict[str, Any]]) -> float | None:
        if not subset:
            return None
        return sum(item["regret"] for item in subset) / len(subset)

    by_target = {}
    for target in ("euro-pallet", "rollcontainer"):
        subset = [item for item in per_order if item["target"] == target]
        by_target[target] = {"orders": len(subset), "regret": _mean(subset)}
    return {
        "per_order": per_order,
        "by_target": by_target,
        "regret": _mean(per_order),
        "states": len(rows),
        "matches_maximum": sum(1 for row in rows if row["matches_maximum"]),
        "logit_ties": sum(1 for row in rows if row["logit_tie"]),
        "q_multi_max_states": sum(1 for row in rows if row["q_multi_max"]),
    }


def signal_summary(states: list[dict[str, Any]]) -> dict[str, Any]:
    """Conteos de empates. Un par no es un pedido independiente."""

    buckets: dict[tuple[str, str], dict[str, int]] = {}
    for state in states:
        key = (state["split"], state["target"])
        bucket = buckets.setdefault(
            key,
            {
                "states": 0,
                "all_q_tied": 0,
                "has_untied_pair": 0,
                "tied_pairs": 0,
                "untied_pairs": 0,
                "multi_max": 0,
            },
        )
        q_hats = state["q_float64"]
        bucket["states"] += 1
        tied = untied = 0
        for left in range(len(q_hats)):
            for right in range(left + 1, len(q_hats)):
                if abs(q_hats[left] - q_hats[right]) <= TIE_EPS:
                    tied += 1
                else:
                    untied += 1
        bucket["tied_pairs"] += tied
        bucket["untied_pairs"] += untied
        if untied == 0:
            bucket["all_q_tied"] += 1
        else:
            bucket["has_untied_pair"] += 1
        if q_multi_max(q_hats):
            bucket["multi_max"] += 1
    return {f"{split}|{target}": value for (split, target), value in sorted(buckets.items())}


def normalized_ranges(states: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    grouped: dict[str, list[torch.Tensor]] = {}
    for state in states:
        grouped.setdefault(state["split"], []).append(state["features"])
    report = {}
    for split, tensors in grouped.items():
        matrix = torch.cat(tensors, dim=0)
        columns = []
        for index, name in enumerate(names):
            column = matrix[:, index]
            columns.append(
                {
                    "name": name,
                    "min": float(torch.min(column)),
                    "max": float(torch.max(column)),
                    "constant": bool(torch.max(column) == torch.min(column)),
                }
            )
        report[split] = columns
    return report
