"""Diagnóstico privilegiado de alternativas. No es un baseline online.

El snapshot de la sesión copia listas de cajas, puntos extremos, peso y
empaquetados. No guarda el sufijo ni el problema. Las cajas y los puntos se
comparten por referencia con el estado vivo en el momento de la copia.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Callable

class WallClockExceeded(BaseException):
    """El reloj global venció. No es una etiqueta ni un retorno 0."""

    def __init__(self, message: str = "wall_clock", partial: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.partial = partial


MAX_STATES_PER_ORDER = 5
MAX_ALTERNATIVES = 4
MAX_STATES = 100
MAX_CONTINUATIONS = 400
CONTINUATION_TIMEOUT_SECONDS = 60
FULL_WALL_CLOCK_SECONDS = 4 * 3600
PREFLIGHT_WALL_CLOCK_SECONDS = 15 * 60


def static_operation_estimate(
    *,
    n_orders: int = 20,
    max_states_per_order: int = MAX_STATES_PER_ORDER,
    max_alternatives: int = MAX_ALTERNATIVES,
) -> dict[str, Any]:
    states = min(MAX_STATES, n_orders * max_states_per_order)
    continuations = min(MAX_CONTINUATIONS, states * max_alternatives)
    return {
        "n_orders": n_orders,
        "max_states_per_order": max_states_per_order,
        "max_alternatives": max_alternatives,
        "upper_bound_states": states,
        "upper_bound_continuations": continuations,
        "per_continuation": [
            "restaurar la copia de la sesión",
            "reponer el sufijo guardado fuera de la sesión",
            "aplicar una candidata",
            "continuar con GreedyBestFit hasta la parada contractual",
            "capturar el plan",
            "auditar geometría y contrastar la entrada",
        ],
        "continuation_timeout_seconds": CONTINUATION_TIMEOUT_SECONDS,
        "full_wall_clock_seconds": FULL_WALL_CLOCK_SECONDS,
        "preflight_wall_clock_seconds": PREFLIGHT_WALL_CLOCK_SECONDS,
        "packing_executed_for_this_estimate": False,
        "uncertainty": (
            "La cota cuenta operaciones, no segundos medidos. "
            "Una continuación repite el sufijo y la auditoría puede dominar el coste."
        ),
    }


def candidate_key(candidate: Any) -> tuple[Any, ...]:
    return (
        int(candidate.bin_index),
        float(candidate.position.x),
        float(candidate.position.y),
        float(candidate.position.z),
        float(candidate.dimensions.length),
        float(candidate.dimensions.width),
        float(candidate.dimensions.height),
    )


def _chebyshev(left: Any, right: Any) -> float:
    return max(
        abs(float(left.position.x) - float(right.position.x)),
        abs(float(left.position.y) - float(right.position.y)),
        abs(float(left.position.z) - float(right.position.z)),
    )


def select_alternatives(options: list[Any], greedy: Any, *, limit: int = MAX_ALTERNATIVES) -> list[Any]:
    """Incluye la acción Greedy y completa con diversidad de orientación y posición.

    El orden de la lista legal es el de partida. No consulta retornos.
    """

    if greedy is None or limit < 1:
        return []
    greedy_key = candidate_key(greedy.candidate)
    chosen = [greedy]
    rest = [option for option in options if candidate_key(option.candidate) != greedy_key]
    while len(chosen) < limit and rest:
        best_index = 0
        best_key = None
        for index, option in enumerate(rest):
            orientation = (
                float(option.candidate.dimensions.length),
                float(option.candidate.dimensions.width),
                float(option.candidate.dimensions.height),
            )
            known = {
                (
                    float(item.candidate.dimensions.length),
                    float(item.candidate.dimensions.width),
                    float(item.candidate.dimensions.height),
                )
                for item in chosen
            }
            new_orientation = 1 if orientation not in known else 0
            distance = min(_chebyshev(option.candidate, item.candidate) for item in chosen)
            key = (new_orientation, distance, -index)
            if best_key is None or key > best_key:
                best_key = key
                best_index = index
        chosen.append(rest.pop(best_index))
    return chosen


def _geometry(session: Any) -> tuple[Any, ...]:
    rows = []
    for state in session.states:
        placed = tuple(
            (
                tuple(box.min_corner),
                tuple(box.max_corner),
            )
            for box in state.placed
        )
        points = tuple((point.x, point.y, point.z) for point in state.extreme_points)
        rows.append((placed, points, float(state.loaded_weight)))
    packed = tuple(
        (
            item.item_id,
            item.position.x,
            item.position.y,
            item.position.z,
            item.orientation.length,
            item.orientation.width,
            item.orientation.height,
        )
        for item in session.packed
    )
    return tuple(rows), packed


def capture_checkpoint(session: Any, remaining: list[Any]) -> dict[str, Any]:
    """Copia profunda: el snapshot del motor comparte cajas y puntos por referencia."""

    return {
        "session": copy.deepcopy(session.snapshot()),
        "remaining_ids": tuple(item.id for item in remaining),
        "geometry": _geometry(session),
    }


def restore_checkpoint(session: Any, problem_items: dict[str, Any], checkpoint: dict[str, Any]) -> list[Any]:
    session.restore(checkpoint["session"])
    return [problem_items[item_id] for item_id in checkpoint["remaining_ids"]]


def _legal_options(session: Any, current: Any, constraints: Any, mask: Any) -> list[Any]:
    from packing_services.online.types import StepOption

    options = []
    for candidate in session.candidates(current, constraints):
        if mask.allows(candidate, current, session, constraints):
            options.append(StepOption(item=current, candidate=candidate, buffer_index=0))
    return options


def _setup(problem: Any) -> tuple[Any, Any, Any, Any, list[Any]]:
    from compact_study import COMPACT_FLAGS, CompactError
    from pilot_problems import prepare_imports

    prepare_imports()
    from packing_services.algorithms._constructive import order_items
    from packing_services.domain.enums import SortStrategy
    from packing_services.online.budget import InformationBudget
    from packing_services.online.mask import ValidatorMask
    from packing_services.online.params import resolve_selection, support_threshold
    from packing_services.online.policies import GreedyBestFitPolicy
    from packing_services.online.session import ExtremePointOnlineSession

    observed = {key: getattr(problem.constraints, key) for key in COMPACT_FLAGS}
    if observed != COMPACT_FLAGS:
        raise CompactError("las restricciones no son las del contrato compacto")
    params = dict(problem.algorithm.parameters)
    budget = InformationBudget.from_parameters(params)
    session = ExtremePointOnlineSession(problem.containers, selection=resolve_selection(params))
    mask = ValidatorMask(problem, min_support_ratio=support_threshold(params, problem.constraints.basic_stability))
    remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)
    return session, mask, GreedyBestFitPolicy(), budget, remaining


def _stop_unpacked(remaining: list[Any]) -> list[Any]:
    from compact_study import SUFFIX_REASON, TERMINAL_REASON
    from packing_services.domain.models import UnpackedItem

    if not remaining:
        return []
    rows = [UnpackedItem(item_id=remaining[0].id, reason=TERMINAL_REASON)]
    rows.extend(UnpackedItem(item_id=item.id, reason=SUFFIX_REASON) for item in remaining[1:])
    return rows


def _finalize(problem: Any, session: Any, unpacked: list[Any]) -> Any:
    from packing_services.algorithms.base import build_solution
    from packing_services.algorithms.online_3d_bpp_heuristic import METADATA

    metadata = METADATA.model_copy(
        update={
            "name": problem.algorithm.name,
            "display_name": "Continuación GreedyBestFit del diagnóstico contrafactual",
            "description": "Una acción fijada y después GreedyBestFit. No es una política aprendida.",
        }
    )
    return build_solution(
        problem=problem,
        metadata=metadata,
        packed_items=session.packed,
        unpacked_items=unpacked,
        execution_time_seconds=0.0,
    )


def greedy_reference(problem: Any) -> Any:
    """Recorre el pedido solo con GreedyBestFit y la parada contractual."""

    session, mask, policy, budget, remaining = _setup(problem)
    constraints = problem.constraints
    while remaining:
        select_s, observe_p = budget.window(len(remaining))
        if select_s != 1 or observe_p != 1:
            raise RuntimeError("la ventana dejó de ser un ítem")
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
        if chosen is None:
            return _finalize(problem, session, _stop_unpacked(remaining))
        session.commit(chosen.candidate, chosen.item)
        remaining = [item for item in remaining if item.id != chosen.item.id]
    return _finalize(problem, session, [])


def collect_states(
    problem: Any,
    *,
    max_states: int = MAX_STATES_PER_ORDER,
    alternative_limit: int = MAX_ALTERNATIVES,
    deadline: float | None = None,
    now: Callable[[], float] | None = None,
) -> list[dict[str, Any]]:
    clock = now or time.perf_counter
    if deadline is not None and clock() > deadline:
        raise WallClockExceeded("wall_clock")
    session, mask, policy, budget, remaining = _setup(problem)
    constraints = problem.constraints
    found = []
    while remaining and len(found) < max_states:
        if deadline is not None and clock() > deadline:
            raise WallClockExceeded("wall_clock")
        select_s, observe_p = budget.window(len(remaining))
        if select_s != 1 or observe_p != 1:
            raise RuntimeError("la ventana dejó de ser un ítem")
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
        saved_geometry = None
        if len(options) >= 2 and chosen is not None:
            alternatives = select_alternatives(options, chosen, limit=alternative_limit)
            found.append(
                {
                    "checkpoint": capture_checkpoint(session, remaining),
                    "current_item_id": current.id,
                    "n_legal": len(options),
                    "alternatives": [candidate_key(option.candidate) for option in alternatives],
                    "greedy_key": candidate_key(chosen.candidate),
                    "orientations": [
                        [
                            float(option.candidate.dimensions.length),
                            float(option.candidate.dimensions.width),
                            float(option.candidate.dimensions.height),
                        ]
                        for option in alternatives
                    ],
                    "positions": [
                        [
                            float(option.candidate.position.x),
                            float(option.candidate.position.y),
                            float(option.candidate.position.z),
                        ]
                        for option in alternatives
                    ],
                }
            )
            saved_geometry = found[-1]["checkpoint"]["geometry"]
        if chosen is None:
            break
        before = _geometry(session)
        session.commit(chosen.candidate, chosen.item)
        if saved_geometry is not None and saved_geometry != before:
            raise RuntimeError("guardar el estado alteró la geometría ya registrada")
        remaining = [item for item in remaining if item.id != chosen.item.id]
    return found


def _resolve(options: list[Any], key: tuple[Any, ...]) -> Any | None:
    for option in options:
        if candidate_key(option.candidate) == key:
            return option
    return None


def _plan_rows(solution: Any) -> list[tuple[Any, ...]]:
    return [
        (
            item.item_id,
            item.position.x,
            item.position.y,
            item.position.z,
            item.orientation.length,
            item.orientation.width,
            item.orientation.height,
        )
        for item in solution.packed_items
    ]


def continue_from(
    problem: Any,
    checkpoint: dict[str, Any],
    action_key: tuple[Any, ...],
    *,
    deadline: float | None = None,
    now: Callable[[], float] | None = None,
) -> dict[str, Any]:
    clock = now or time.perf_counter
    if deadline is not None and clock() > deadline:
        return {"status": "timeout", "solution": None, "reason": "timeout"}
    session, mask, policy, budget, _remaining = _setup(problem)
    items = {item.id: item for item in problem.items}
    suffix_before = tuple(checkpoint["remaining_ids"])
    remaining = restore_checkpoint(session, items, checkpoint)
    if tuple(item.id for item in remaining) != suffix_before:
        return {"status": "restore_mismatch", "solution": None, "reason": "el sufijo restaurado no coincide"}
    if _geometry(session) != checkpoint["geometry"]:
        return {"status": "restore_mismatch", "solution": None, "reason": "la geometría restaurada no coincide"}
    if not remaining:
        return {"status": "restore_mismatch", "solution": None, "reason": "no queda ítem actual"}
    current = remaining[0]
    options = _legal_options(session, current, problem.constraints, mask)
    chosen = _resolve(options, action_key)
    if chosen is None:
        return {"status": "restore_mismatch", "solution": None, "reason": "la candidata no reaparece tras restaurar"}
    session.commit(chosen.candidate, chosen.item)
    remaining = remaining[1:]
    while remaining:
        if deadline is not None and clock() > deadline:
            return {"status": "timeout", "solution": None, "reason": "timeout"}
        select_s, observe_p = budget.window(len(remaining))
        if select_s != 1 or observe_p != 1:
            raise RuntimeError("la ventana dejó de ser un ítem")
        current = remaining[0]
        options = _legal_options(session, current, problem.constraints, mask)
        nxt = policy.decide(
            options,
            preview=remaining[:observe_p],
            remaining_count=0,
            session=session,
            constraints=problem.constraints,
            mask=mask,
        )
        if nxt is None:
            return {"status": "ok", "solution": _finalize(problem, session, _stop_unpacked(remaining)), "reason": None}
        session.commit(nxt.candidate, nxt.item)
        remaining = [item for item in remaining if item.id != nxt.item.id]
    return {"status": "ok", "solution": _finalize(problem, session, []), "reason": None}


def score_solution(
    problem: Any,
    solution: Any,
    *,
    order_id: str,
    dataset: str,
    dataset_sha256: str,
    snapshot: dict[str, Any],
    deadline: float | None = None,
    now: Callable[[], float] | None = None,
) -> dict[str, Any]:
    from compact_study import capture_compact_case
    from pilot_metrics import evaluate_outcome

    clock = now or time.perf_counter
    if deadline is not None and clock() > deadline:
        return {
            "q_hat": None,
            "reason": "wall_clock",
            "capture": None,
            "audit_failure_types": [],
            "capture_seconds": None,
            "audit_seconds": None,
        }
    capture_started = clock()
    capture = capture_compact_case(
        problem,
        solution,
        order_id=order_id,
        dataset=dataset,
        dataset_sha256=dataset_sha256,
    )
    capture_seconds = clock() - capture_started
    if deadline is not None and clock() > deadline:
        return {
            "q_hat": None,
            "reason": "wall_clock",
            "capture": capture,
            "audit_failure_types": [],
            "capture_seconds": capture_seconds,
            "audit_seconds": None,
        }
    audit_started = clock()
    container = snapshot["containers"][0]
    scored = evaluate_outcome(
        {"status": "ok", "capture": capture, "attempts": 1, "duration_seconds": 0.0},
        order_id=order_id,
        method="greedy",
        target=str(snapshot.get("target") or "euro-pallet"),
        container_volume_mm3=float(container["volume_mm3"]),
        run_id="counterfactual-diagnostic",
        snapshot=snapshot,
    )
    audit_seconds = clock() - audit_started
    if deadline is not None and clock() > deadline:
        return {
            "q_hat": None,
            "reason": "wall_clock",
            "capture": capture,
            "audit_failure_types": ["wall_clock"],
            "capture_seconds": capture_seconds,
            "audit_seconds": audit_seconds,
        }
    if scored.get("failure_types"):
        return {
            "q_hat": None,
            "reason": ",".join(scored["failure_types"]),
            "capture": capture,
            "audit_failure_types": scored["failure_types"],
            "capture_seconds": capture_seconds,
            "audit_seconds": audit_seconds,
        }
    return {
        "q_hat": float(scored["effective_u_geom"]),
        "reason": None,
        "capture": capture,
        "audit_failure_types": [],
        "capture_seconds": capture_seconds,
        "audit_seconds": audit_seconds,
    }


def _pack_evaluation(state: dict[str, Any], rows: list[dict[str, Any]], *, keep_captures: bool) -> dict[str, Any]:
    greedy_row = next((row for row in rows if row["is_greedy"]), None)
    greedy_q = None if greedy_row is None else greedy_row["q_hat"]
    complete = all(row["q_hat"] is not None for row in rows) and greedy_q is not None and len(rows) == len(state["alternatives"])
    labels = []
    if complete:
        for row in rows:
            labels.append(
                {
                    "action": row["action"],
                    "is_greedy": row["is_greedy"],
                    "q_hat": row["q_hat"],
                    "a_hat": float(row["q_hat"]) - float(greedy_q),
                }
            )
    public = []
    for row in rows:
        item = {key: value for key, value in row.items() if key != "capture"}
        if keep_captures:
            item["capture"] = row.get("capture")
        public.append(item)
    return {
        "current_item_id": state["current_item_id"],
        "n_legal": state["n_legal"],
        "complete": complete,
        "alternatives": public,
        "labels": labels,
        "orientations": state["orientations"],
        "positions": state["positions"],
    }


def evaluate_state(
    problem: Any,
    state: dict[str, Any],
    *,
    order_id: str,
    dataset: str,
    dataset_sha256: str,
    snapshot: dict[str, Any],
    timeout_seconds: float = CONTINUATION_TIMEOUT_SECONDS,
    now: Callable[[], float] | None = None,
    global_deadline: float | None = None,
    keep_captures: bool = False,
) -> dict[str, Any]:
    clock = now or time.perf_counter
    rows = []

    def _unknown(reason: str, *, is_greedy: bool, action: tuple[Any, ...], continuation_seconds: float | None) -> dict[str, Any]:
        return {
            "action": list(action),
            "is_greedy": is_greedy,
            "q_hat": None,
            "reason": reason,
            "audited": False,
            "audit_failure_types": [],
            "continuation_seconds": continuation_seconds,
            "capture_seconds": None,
            "audit_seconds": None,
        }

    try:
        for key in state["alternatives"]:
            action = tuple(key)
            is_greedy = action == tuple(state["greedy_key"])
            if global_deadline is not None and clock() > global_deadline:
                rows.append(_unknown("wall_clock", is_greedy=is_greedy, action=action, continuation_seconds=None))
                continue
            started = clock()
            deadline = started + timeout_seconds
            if global_deadline is not None:
                deadline = min(deadline, global_deadline)
            try:
                outcome = continue_from(problem, state["checkpoint"], action, deadline=deadline, now=clock)
            except WallClockExceeded as exc:
                rows.append(_unknown("wall_clock", is_greedy=is_greedy, action=action, continuation_seconds=clock() - started))
                exc.partial = _pack_evaluation(state, rows, keep_captures=keep_captures)
                raise
            except Exception as exc:
                outcome = {"status": "crash", "solution": None, "reason": f"{type(exc).__name__}: {exc}"}
            continuation_seconds = clock() - started
            if outcome["status"] != "ok" or outcome["solution"] is None:
                reason = outcome.get("reason") or outcome["status"]
                if reason == "timeout" and global_deadline is not None and clock() >= global_deadline:
                    reason = "wall_clock"
                rows.append(_unknown(reason, is_greedy=is_greedy, action=action, continuation_seconds=continuation_seconds))
                continue
            if global_deadline is not None and clock() > global_deadline:
                rows.append(_unknown("wall_clock", is_greedy=is_greedy, action=action, continuation_seconds=continuation_seconds))
                continue
            try:
                scored = score_solution(
                    problem,
                    outcome["solution"],
                    order_id=order_id,
                    dataset=dataset,
                    dataset_sha256=dataset_sha256,
                    snapshot=snapshot,
                    deadline=global_deadline,
                    now=clock,
                )
            except WallClockExceeded as exc:
                rows.append(_unknown("wall_clock", is_greedy=is_greedy, action=action, continuation_seconds=continuation_seconds))
                exc.partial = _pack_evaluation(state, rows, keep_captures=keep_captures)
                raise
            except Exception as exc:
                rows.append(
                    {
                        "action": list(action),
                        "is_greedy": is_greedy,
                        "q_hat": None,
                        "reason": f"audit_exception: {type(exc).__name__}: {exc}",
                        "audited": False,
                        "audit_failure_types": ["audit_exception"],
                        "continuation_seconds": continuation_seconds,
                        "capture_seconds": None,
                        "audit_seconds": None,
                    }
                )
                continue
            audited = scored["capture"] is not None and scored.get("audit_seconds") is not None
            rows.append(
                {
                    "action": list(action),
                    "is_greedy": is_greedy,
                    "q_hat": scored["q_hat"],
                    "reason": scored["reason"],
                    "audited": audited,
                    "audit_failure_types": list(scored["audit_failure_types"]),
                    "continuation_seconds": continuation_seconds,
                    "capture_seconds": scored.get("capture_seconds"),
                    "audit_seconds": scored.get("audit_seconds"),
                    "capture": scored["capture"],
                }
            )
    except WallClockExceeded as exc:
        if exc.partial is None:
            exc.partial = _pack_evaluation(state, rows, keep_captures=keep_captures)
        raise
    return _pack_evaluation(state, rows, keep_captures=keep_captures)


def accept_scored_capture(capture: dict[str, Any], snapshot: dict[str, Any], *, order_id: str) -> str | None:
    if capture.get("order_id") != order_id:
        return "order_id incompatible"
    observed = capture.get("input_items")
    expected = snapshot.get("items")
    if not isinstance(observed, list) or not isinstance(expected, list) or len(observed) != len(expected):
        return "entrada incompatible"
    for left, right in zip(observed, expected):
        for key in ("item_id", "length_mm", "width_mm", "height_mm", "weight_kg"):
            if left.get(key) != right.get(key):
                return f"entrada incompatible: {key}"
    return None
