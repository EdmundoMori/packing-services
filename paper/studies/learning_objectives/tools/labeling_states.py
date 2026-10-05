"""Generación de estados elegibles y S para etiquetado.

Reutiliza pipeline.labeling_select_support y quantile_sampling.
No usa Q_hat para elegir estados ni alternativas.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
COUNTERFACTUAL_TOOLS = HERE.parents[1] / "counterfactual_ranking" / "tools"
for entry in (str(HERE), str(PAPER_TOOLS), str(COUNTERFACTUAL_TOOLS)):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

from actor_features import FEATURE_NAMES, encode_candidate, feature_sha256  # noqa: E402
from diagnostic import WallClockExceeded, _geometry, _legal_options, _setup, capture_checkpoint  # noqa: E402
from pipeline import labeling_select_support  # noqa: E402
from quantile_sampling import quantile_indices  # noqa: E402
from support_api import CONTRACT_NAME, SUPPORT_LIMIT, build_S_from_options  # noqa: E402


def _action_from_option(option: Any) -> list[float | int]:
    cand = option.candidate
    return [
        int(cand.bin_index),
        float(cand.position.x),
        float(cand.position.y),
        float(cand.position.z),
        float(cand.dimensions.length),
        float(cand.dimensions.width),
        float(cand.dimensions.height),
    ]


def collect_choice_states(
    problem: Any,
    *,
    deadline: float,
    now: Callable[[], float],
) -> list[dict[str, Any]]:
    session, mask, policy, budget, remaining = _setup(problem)
    constraints = problem.constraints
    found: list[dict[str, Any]] = []
    while remaining:
        if now() > deadline:
            raise WallClockExceeded("wall_clock")
        select_s, observe_p = budget.window(len(remaining))
        if select_s != 1 or observe_p != 1:
            raise RuntimeError("ventana distinta de p=s=1")
        current = remaining[0]
        options = _legal_options(session, current, constraints, mask)
        chosen = policy.decide(
            options,
            preview=remaining[:observe_p],
            remaining_count=0,
            session=session,
            constraints=constraints,
            mask=mask,
        )
        if len(options) >= 2 and chosen is not None:
            legal_ids = []
            for index, option in enumerate(options):
                action = _action_from_option(option)
                legal_ids.append(action + [index])
            support = labeling_select_support(options, chosen, limit=SUPPORT_LIMIT)
            support_again = build_S_from_options(options, chosen, limit=SUPPORT_LIMIT)
            support_ids = [_action_from_option(opt) for opt in support]
            if support_ids != [_action_from_option(opt) for opt in support_again]:
                raise RuntimeError("S no es repetible sin Q_hat")
            greedy_key = _action_from_option(chosen)
            if support_ids[0] != greedy_key:
                raise RuntimeError("Greedy no es el primer elemento de S")
            alternatives = []
            for option in support:
                action = _action_from_option(option)
                features = encode_candidate(session, current, option.candidate)
                if len(features) != len(FEATURE_NAMES):
                    raise RuntimeError("encoder no produjo 17 columnas")
                alternatives.append(
                    {
                        "action": action,
                        "is_greedy": action == greedy_key,
                        "features": features,
                        "feature_sha256": feature_sha256(features),
                        "feature_names": list(FEATURE_NAMES),
                        "q_hat": None,
                        "reason": None,
                        "audited": False,
                        "source": "pending",
                    }
                )
            checkpoint = capture_checkpoint(session, remaining)
            found.append(
                {
                    "choice_index": len(found),
                    "current_item_id": current.id,
                    "n_legal": len(options),
                    "legal_ids": legal_ids,
                    "support_ids": support_ids,
                    "support_contract": CONTRACT_NAME,
                    "greedy_key": greedy_key,
                    "greedy_in_support": greedy_key in support_ids,
                    "checkpoint": checkpoint,
                    "alternatives": alternatives,
                }
            )
            saved_geometry = checkpoint["geometry"]
        else:
            saved_geometry = None
        if chosen is None:
            break
        before = _geometry(session)
        session.commit(chosen.candidate, chosen.item)
        if saved_geometry is not None and saved_geometry != before:
            raise RuntimeError("guardar el estado alteró la geometría ya registrada")
        remaining = [item for item in remaining if item.id != chosen.item.id]
    return found


def select_quantile_states(found: list[dict[str, Any]], *, limit: int = 4) -> tuple[list[int], list[dict[str, Any]]]:
    indices = quantile_indices(len(found), limit=limit)
    return indices, [found[index] for index in indices]
