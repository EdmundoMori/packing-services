"""Colecta transiciones con el bucle online del repo + maestro P2O."""

from __future__ import annotations

import pickle
import time
from pathlib import Path
from typing import Any

from packing_services.algorithms._constructive import order_items
from packing_services.domain.enums import SortStrategy
from packing_services.domain.models import PackingProblem
from packing_services.online.budget import InformationBudget
from packing_services.online.features import (
    FEATURE_DIM,
    FEATURE_NAMES,
    FEATURE_VERSION,
    encode_option,
)
from packing_services.online.mask import ValidatorMask
from packing_services.online.params import resolve_selection, support_threshold
from packing_services.online.session import ExtremePointOnlineSession
from packing_services.online.types import StepOption

from config import SEED, SELECTION, TEACHER_NAME
from problems import order_to_problem
from teacher import label_index, privileged_volume_ep_index


def collect_order_transitions(
    problem: PackingProblem,
    *,
    lookahead_p: int,
    select_s: int,
    teacher: str = TEACHER_NAME,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    constraints = problem.constraints
    params = {
        **problem.algorithm.parameters,
        "lookahead_p": lookahead_p,
        "select_s": select_s,
    }
    budget = InformationBudget.from_parameters(params)
    selection = resolve_selection(params) or SELECTION
    min_support = support_threshold(params, constraints.basic_stability)
    session = ExtremePointOnlineSession(problem.containers, selection=selection)
    mask = ValidatorMask(problem, min_support_ratio=min_support)
    remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)

    transitions: list[dict[str, Any]] = []
    skipped = 0
    labeled = 0
    unlabeled = 0
    step = 0
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
            remaining.pop(0)
            skipped += 1
            continue

        rows = [
            encode_option(
                opt,
                session=session,
                preview=preview,
                remaining_count=len(remaining),
            )
            for opt in options
        ]
        if any(len(row) != FEATURE_DIM for row in rows):
            raise RuntimeError("encode_option no respetó FEATURE_DIM")

        if teacher == "receding_horizon_ep":
            y = label_index(
                options,
                teacher=teacher,
                remaining=remaining,
                session=session,
                constraints=constraints,
                mask=mask,
            )
        else:
            y = label_index(options, teacher=teacher)

        if y is None:
            remaining.pop(0)
            unlabeled += 1
            skipped += 1
            continue

        row = {
            "order_id": problem.request_id,
            "step": step,
            "features": rows,
            "label": int(y),
            "n_options": len(options),
        }
        if teacher == "receding_horizon_ep":
            vol = privileged_volume_ep_index(options)
            if vol is not None:
                row["label_volume"] = int(vol)
        transitions.append(row)
        labeled += 1
        chosen = options[y]
        session.commit(chosen.candidate, chosen.item)
        remaining = [it for it in remaining if it.id != chosen.item.id]
        step += 1

    attempted = labeled + unlabeled
    stats = {
        "order_id": problem.request_id,
        "n_items": len(problem.items),
        "n_transitions": len(transitions),
        "n_skipped": skipped,
        "n_packed": len(session.packed),
        "label_rate": (labeled / attempted) if attempted else 0.0,
        "seconds": time.perf_counter() - t0,
        "lookahead_p": lookahead_p,
        "select_s": select_s,
        "teacher": teacher,
    }
    return transitions, stats


def collect_dataset(
    orders: dict[str, Any],
    order_ids: list[str],
    *,
    lookahead_p: int,
    select_s: int,
    teacher: str = TEACHER_NAME,
) -> dict[str, Any]:
    all_tr: list[dict[str, Any]] = []
    per_order: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for oid in order_ids:
        problem = order_to_problem(
            orders, oid, lookahead_p=lookahead_p, select_s=select_s
        )
        tr, stats = collect_order_transitions(
            problem,
            lookahead_p=lookahead_p,
            select_s=select_s,
            teacher=teacher,
        )
        for row in tr:
            row["order_id"] = oid
        all_tr.extend(tr)
        per_order.append(stats)
        n_done = len(per_order)
        if n_done == 1 or n_done == len(order_ids) or n_done % 10 == 0:
            print(
                f"    {n_done}/{len(order_ids)} {oid} "
                f"tr={stats['n_transitions']} packed={stats['n_packed']} "
                f"{stats['seconds']:.2f}s",
                flush=True,
            )

    n_ok = sum(1 for t in all_tr if 0 <= int(t["label"]) < int(t["n_options"]))
    return {
        "feature_version": FEATURE_VERSION,
        "feature_dim": FEATURE_DIM,
        "feature_names": list(FEATURE_NAMES),
        "regime": {"lookahead_p": lookahead_p, "select_s": select_s},
        "teacher": teacher,
        "seed": SEED,
        "order_ids": list(order_ids),
        "transitions": all_tr,
        "per_order": per_order,
        "n_transitions": len(all_tr),
        "label_rate": (n_ok / len(all_tr)) if all_tr else 0.0,
        "seconds": time.perf_counter() - t0,
    }


def save_transitions(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_transitions(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return pickle.load(handle)


def disagreement_vs_volume(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    """Tasa de desacuerdo receding vs volumen en el MISMO estado (trayectoria RH)."""

    n = 0
    disagree = 0
    for tr in transitions:
        if "label_volume" not in tr:
            continue
        n += 1
        if int(tr["label"]) != int(tr["label_volume"]):
            disagree += 1
    return {
        "n_compared": n,
        "n_disagree": disagree,
        "rate": (disagree / n) if n else None,
    }
