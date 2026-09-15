"""Evaluación packing_mode=online: modelo vs heurístico vs maestro vs placeholder."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from packing_services.algorithms._constructive import order_items
from packing_services.algorithms.base import build_solution
from packing_services.algorithms.drl_policy_3d_bpp import DRLPolicy3DBPP
from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic
from packing_services.domain.enums import SortStrategy
from packing_services.domain.models import UnpackedItem
from packing_services.online.budget import InformationBudget
from packing_services.online.learned.policy import LearnedPlacementPolicy
from packing_services.online.mask import ValidatorMask
from packing_services.online.params import resolve_selection, support_threshold
from packing_services.online.session import ExtremePointOnlineSession
from packing_services.online.types import StepOption

from config import SELECTION, TEACHER_NAME
from problems import order_to_problem
from step_select import run_step_solution
from teacher import label_index


def run_teacher_solution(
    problem,
    *,
    lookahead_p: int,
    select_s: int,
    teacher: str = TEACHER_NAME,
):
    """Empaqueta con el maestro P2O sobre el mismo bucle y el mismo validador.

    Vive aquí, no en el catálogo de producción: el execute no expone al maestro.
    ``remaining`` es la cola real (como en ``collect``), no una reconstrucción.
    """

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
    unpacked: list[UnpackedItem] = []
    t0 = time.perf_counter()

    while remaining:
        select_s_now, _observe_p = budget.window(len(remaining))
        selectable = remaining[:select_s_now]
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

        idx = label_index(
            options,
            teacher=teacher,
            remaining=remaining,
            session=session,
            constraints=constraints,
            mask=mask,
        )
        if idx is None:
            skipped = remaining.pop(0)
            unpacked.append(
                UnpackedItem(
                    item_id=skipped.id,
                    reason="El maestro no etiquetó ninguna candidata legal",
                )
            )
            continue

        chosen = options[idx]
        session.commit(chosen.candidate, chosen.item)
        remaining = [it for it in remaining if it.id != chosen.item.id]

    return build_solution(
        problem=problem,
        metadata=Online3DBPPHeuristic.metadata,
        packed_items=session.packed,
        unpacked_items=unpacked,
        execution_time_seconds=time.perf_counter() - t0,
    )


def run_engine(
    orders: dict[str, Any],
    order_id: str,
    *,
    engine: str,
    lookahead_p: int,
    select_s: int,
    model_path: str | None = None,
    teacher: str = TEACHER_NAME,
    placement_path: str | None = None,
) -> dict[str, Any]:
    if engine == "heuristic":
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name="online_3d_bpp_heuristic",
        )
        t0 = time.perf_counter()
        solution = Online3DBPPHeuristic().run(problem)
    elif engine == "learned":
        if not model_path:
            raise ValueError("learned requiere model_path")
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name="drl_policy_3d_bpp",
            model_path=model_path,
        )
        t0 = time.perf_counter()
        solution = DRLPolicy3DBPP().run(problem)
    elif engine == "step":
        if not model_path:
            raise ValueError("step requiere model_path (actor de selección)")
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name="drl_policy_3d_bpp",
            model_path=model_path,
        )
        t0 = time.perf_counter()
        solution = run_step_solution(
            problem,
            placement_path=placement_path or model_path,
            selection_path=model_path,
            lookahead_p=lookahead_p,
            select_s=select_s,
        )
    elif engine == "teacher":
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name="online_3d_bpp_heuristic",
        )
        t0 = time.perf_counter()
        solution = run_teacher_solution(
            problem,
            lookahead_p=lookahead_p,
            select_s=select_s,
            teacher=teacher,
        )
    else:
        raise ValueError(engine)

    report = solution.validation_report
    return {
        "order_id": order_id,
        "engine": (
            "ppo"
            if engine == "learned" and model_path and "ppo" in Path(model_path).name
            else engine
        ),
        "model_path": model_path,
        "teacher": teacher if engine == "teacher" else None,
        "lookahead_p": lookahead_p,
        "select_s": select_s,
        "volume_utilization": solution.metrics.volume_utilization,
        "items_packed": solution.metrics.items_packed,
        "items_unpacked": solution.metrics.items_unpacked,
        "is_valid": bool(report and report.is_valid),
        "seconds": time.perf_counter() - t0,
        "n_items": len(problem.items),
    }


def evaluate_orders(
    orders: dict[str, Any],
    order_ids: list[str],
    *,
    engine: str,
    lookahead_p: int,
    select_s: int,
    model_path: str | None = None,
    max_orders: int | None = None,
    teacher: str = TEACHER_NAME,
    placement_path: str | None = None,
) -> list[dict[str, Any]]:
    ids = order_ids[:max_orders] if max_orders else order_ids
    return [
        run_engine(
            orders,
            oid,
            engine=engine,
            lookahead_p=lookahead_p,
            select_s=select_s,
            model_path=model_path,
            teacher=teacher,
            placement_path=placement_path,
        )
        for oid in ids
    ]


def smoke_from_path(
    model_path: Path,
    orders: dict[str, Any],
    order_id: str,
    *,
    lookahead_p: int = 1,
    select_s: int = 1,
) -> dict[str, Any]:
    """Comprueba que el checkpoint carga y produce una solución válida.

    No es una métrica de calidad: un solo pedido no sostiene ninguna afirmación.
    El régimen (p, s) debe coincidir con el del checkpoint; el valor por
    defecto p=1, s=1 no sirve para evaluar ``mlp_v1_p3s2``.
    """

    LearnedPlacementPolicy.from_path(model_path)
    return run_engine(
        orders,
        order_id,
        engine="learned",
        lookahead_p=lookahead_p,
        select_s=select_s,
        model_path=str(model_path),
    )


def evaluate_fair(
    orders: dict[str, Any],
    order_ids: list[str],
    *,
    lookahead_p: int,
    select_s: int,
    engines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evalúa todos los motores sobre exactamente los mismos pedidos."""

    rows: list[dict[str, Any]] = []
    for spec in engines:
        rows.extend(
            evaluate_orders(
                orders,
                order_ids,
                engine=spec["engine"],
                lookahead_p=lookahead_p,
                select_s=select_s,
                model_path=spec.get("model_path"),
                teacher=spec.get("teacher", TEACHER_NAME),
            )
        )
    return rows


def write_report(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
