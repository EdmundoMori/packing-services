"""Selección STEP: colocación congelada + elección de ítem del buffer.

Réplica de nikitasarawgi/step-bpp sobre el bucle y el encoder v1 de este repo.
No cambia ``run_online_loop`` ni el default de la API.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from packing_services.algorithms._constructive import order_items
from packing_services.algorithms.base import build_solution
from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic
from packing_services.domain.enums import SortStrategy
from packing_services.domain.models import UnpackedItem
from packing_services.online.budget import InformationBudget
from packing_services.online.features import encode_option
from packing_services.online.learned.policy import LearnedPlacementPolicy
from packing_services.online.mask import ValidatorMask
from packing_services.online.params import resolve_selection, support_threshold
from packing_services.online.session import ExtremePointOnlineSession
from packing_services.online.types import StepOption

from config import SELECTION


def collapse_best_pose_indices(
    options: Sequence[StepOption],
    scores: Sequence[float],
) -> list[int]:
    """Un superviviente por ítem: la pose con mayor score de colocación."""

    if not options:
        return []
    if len(options) != len(scores):
        raise ValueError("options y scores deben tener la misma longitud")
    best: dict[str, tuple[int, float]] = {}
    for i, opt in enumerate(options):
        score = float(scores[i])
        key = opt.item.id
        prev = best.get(key)
        if prev is None or score > prev[1]:
            best[key] = (i, score)
    return sorted((idx for idx, _ in best.values()), key=lambda i: options[i].buffer_index)


def decide_step(
    options: Sequence[StepOption],
    *,
    placement: LearnedPlacementPolicy,
    selection: LearnedPlacementPolicy,
    preview,
    remaining_count: int,
    session: ExtremePointOnlineSession,
) -> StepOption | None:
    if not options:
        return None
    place_rows = [
        encode_option(
            opt,
            session=session,
            preview=preview,
            remaining_count=remaining_count,
        )
        for opt in options
    ]
    place_scores = placement.backend.score(place_rows)
    survivors = [options[i] for i in collapse_best_pose_indices(options, place_scores)]
    sel_rows = [
        encode_option(
            opt,
            session=session,
            preview=preview,
            remaining_count=remaining_count,
        )
        for opt in survivors
    ]
    sel_scores = selection.backend.score(sel_rows)
    best_i = 0
    best_key = (sel_scores[0], -survivors[0].buffer_index)
    for i, score in enumerate(sel_scores[1:], start=1):
        key = (score, -survivors[i].buffer_index)
        if key > best_key:
            best_key = key
            best_i = i
    return survivors[best_i]


def run_step_solution(
    problem,
    *,
    placement_path: str,
    selection_path: str,
    lookahead_p: int,
    select_s: int,
):
    """Misma geometría y máscara que el execute; la política es STEP."""

    placement = LearnedPlacementPolicy.from_path(placement_path)
    selection = LearnedPlacementPolicy.from_path(selection_path)
    constraints = problem.constraints
    params = {
        **problem.algorithm.parameters,
        "lookahead_p": lookahead_p,
        "select_s": select_s,
    }
    budget = InformationBudget.from_parameters(params)
    sel = resolve_selection(params) or SELECTION
    min_support = support_threshold(params, constraints.basic_stability)
    session = ExtremePointOnlineSession(problem.containers, selection=sel)
    mask = ValidatorMask(problem, min_support_ratio=min_support)
    remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)
    unpacked: list[UnpackedItem] = []
    t0 = time.perf_counter()

    while remaining:
        select_s_now, observe_p = budget.window(len(remaining))
        selectable = remaining[:select_s_now]
        preview = remaining[:observe_p]
        options: list[StepOption] = []
        for buffer_index, item in enumerate(selectable):
            for cand in session.candidates(item, constraints):
                if mask.allows(cand, item, session, constraints):
                    options.append(
                        StepOption(item=item, candidate=cand, buffer_index=buffer_index)
                    )
        if not options:
            skipped = remaining.pop(0)
            unpacked.append(
                UnpackedItem(
                    item_id=skipped.id,
                    reason="No hay colocación legal con el presupuesto de información actual",
                )
            )
            continue
        chosen = decide_step(
            options,
            placement=placement,
            selection=selection,
            preview=preview,
            remaining_count=len(remaining),
            session=session,
        )
        if chosen is None:
            skipped = remaining.pop(0)
            unpacked.append(
                UnpackedItem(
                    item_id=skipped.id,
                    reason="STEP no eligió candidata",
                )
            )
            continue
        session.commit(chosen.candidate, chosen.item)
        remaining = [it for it in remaining if it.id != chosen.item.id]

    return build_solution(
        problem=problem,
        metadata=Online3DBPPHeuristic.metadata,
        packed_items=session.packed,
        unpacked_items=unpacked,
        execution_time_seconds=time.perf_counter() - t0,
    )
