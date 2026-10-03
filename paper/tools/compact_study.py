"""Contrato geométrico del paso 16. No modifica el bucle de producción.

El bucle publicado descarta el ítem sin candidata y sigue con el sufijo.
Este contrato termina el episodio en ese ítem. GreedyBestFit elige solo
entre candidatas ya legales del ítem actual. No es OnlineBPH ni PCT.
"""

from __future__ import annotations

import time
from typing import Any

from pilot_problems import capture_document, prepare_imports, problem_snapshot

PROTOCOL_10 = "paper/protocols/10_normalization_ablation.json"
ALGORITHM_NAME = "compact_greedy_best_fit"
TERMINAL_REASON = "el ítem actual no tiene candidata legal; el episodio termina"
SUFFIX_REASON = "el episodio terminó antes de este ítem"
COMPACT_FLAGS = {
    "non_overlap": True,
    "containment": True,
    "allow_rotation": True,
    "max_weight": False,
    "basic_stability": False,
    "load_bearing": False,
    "fragility": False,
    "unloading_sequence": False,
}
OBSERVATION_KEYS = ("current_item_id", "current_lwh_mm", "candidates")


class CompactError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def development_orders() -> list[dict[str, Any]]:
    import json
    from pathlib import Path

    from pilot_common import REPO_ROOT

    document = json.loads((REPO_ROOT / PROTOCOL_10).read_text(encoding="utf-8"))
    return list(document["development_sample"]["execution_items"])


def smoke_orders(items: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Tres primeros euro-pallet y dos primeros rollcontainer, en orden de posición.

    La regla solo mira target y posición. No mira utilizaciones.
    """

    rows = development_orders() if items is None else list(items)
    euro = [row for row in rows if row.get("target") == "euro-pallet"][:3]
    roll = [row for row in rows if row.get("target") == "rollcontainer"][:2]
    chosen = euro + roll
    if len(euro) != 3 or len(roll) != 2:
        raise CompactError("la muestra no tiene tres euro-pallet y dos rollcontainer")
    if len({row["order_id"] for row in chosen}) != 5:
        raise CompactError("la regla de smoke no produjo cinco pedidos distintos")
    return sorted(chosen, key=lambda row: int(row["position"]))


def propose_calibration_orders(
    train_ids: list[str],
    orders: dict[str, Any],
    excluded: set[str],
    *,
    per_target: int = 20,
) -> dict[str, list[str]]:
    """Primeros ids de full.train por target, en el orden del archivo, fuera de los excluidos."""

    selected = {"euro-pallet": [], "rollcontainer": []}
    for order_id in train_ids:
        if order_id in excluded or order_id in selected["euro-pallet"] or order_id in selected["rollcontainer"]:
            continue
        order = orders.get(order_id)
        if not isinstance(order, dict):
            continue
        target = str((order.get("properties") or {}).get("target") or "")
        bucket = selected.get(target)
        if bucket is None or len(bucket) >= per_target:
            continue
        bucket.append(order_id)
        if all(len(values) >= per_target for values in selected.values()):
            break
    return selected


def build_compact_problem(orders: dict[str, Any], order_id: str) -> Any:
    prepare_imports()
    from packing_services.domain.models import ConstraintFlags
    from problems import order_to_problem

    problem = order_to_problem(
        orders,
        order_id,
        lookahead_p=1,
        select_s=1,
        algorithm_name=ALGORITHM_NAME,
        model_path=None,
    )
    constraints = ConstraintFlags(**COMPACT_FLAGS)
    return problem.model_copy(update={"constraints": constraints})


def compact_selector_view(current: Any, options: list[Any]) -> dict[str, Any]:
    """Observación del selector futuro: el ítem actual y sus candidatas.

    No recibe la cola, remaining_count ni dimensiones de ítems posteriores.
    """

    return {
        "current_item_id": current.id,
        "current_lwh_mm": [float(current.length), float(current.width), float(current.height)],
        "candidates": [
            {
                "oriented_lwh_mm": [
                    float(option.candidate.dimensions.length),
                    float(option.candidate.dimensions.width),
                    float(option.candidate.dimensions.height),
                ],
                "position_mm": [
                    float(option.candidate.position.x),
                    float(option.candidate.position.y),
                    float(option.candidate.position.z),
                ],
                "support_ratio": float(option.candidate.support_ratio),
                "rank_key": list(option.candidate.rank_key),
            }
            for option in options
        ],
    }


def run_compact_episode(
    problem: Any,
    chooser: Any,
    *,
    algorithm_name: str,
    display_name: str,
    description: str,
    selector: str,
    coefficients: dict[str, float] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Coloca con el selector recibido y se detiene en el primer ítem sin candidata."""

    prepare_imports()
    from packing_services.algorithms.base import build_solution
    from packing_services.algorithms.online_3d_bpp_heuristic import METADATA
    from packing_services.algorithms._constructive import order_items
    from packing_services.domain.enums import SortStrategy
    from packing_services.domain.models import UnpackedItem
    from packing_services.online.budget import InformationBudget
    from packing_services.online.mask import ValidatorMask
    from packing_services.online.params import resolve_selection, support_threshold
    from packing_services.online.session import ExtremePointOnlineSession
    from packing_services.online.types import StepOption

    constraints = problem.constraints
    observed = {key: getattr(constraints, key) for key in COMPACT_FLAGS}
    if observed != COMPACT_FLAGS:
        raise CompactError("las restricciones no son las del contrato compacto")
    params = dict(problem.algorithm.parameters)
    if int(params.get("lookahead_p")) != 1 or int(params.get("select_s")) != 1:
        raise CompactError("el contrato compacto exige p=1 y s=1")
    if params.get("sort_strategy") != "input_order":
        raise CompactError("el contrato compacto exige la secuencia original")
    if len(problem.containers) != 1:
        raise CompactError("el contrato compacto exige un contenedor")

    budget = InformationBudget.from_parameters(params)
    session = ExtremePointOnlineSession(problem.containers, selection=resolve_selection(params))
    mask = ValidatorMask(problem, min_support_ratio=support_threshold(params, constraints.basic_stability))
    if problem.algorithm.name != algorithm_name:
        problem = problem.model_copy(
            update={"algorithm": problem.algorithm.model_copy(update={"name": algorithm_name})}
        )
    remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)
    unpacked: list[UnpackedItem] = []
    steps: list[dict[str, Any]] = []
    started = time.perf_counter()
    while remaining:
        select_s, observe_p = budget.window(len(remaining))
        if select_s != 1 or observe_p != 1:
            raise CompactError("la ventana dejó de ser un ítem")
        current = remaining[0]
        preview = remaining[:observe_p]
        options: list[StepOption] = []
        for candidate in session.candidates(current, constraints):
            if mask.allows(candidate, current, session, constraints):
                options.append(StepOption(item=current, candidate=candidate, buffer_index=0))
        view = compact_selector_view(current, options)
        if set(view) != set(OBSERVATION_KEYS):
            raise CompactError("la observación compacta cambió de claves")
        chosen = chooser.decide(
            options,
            preview=preview,
            remaining_count=0,
            session=session,
            constraints=constraints,
            mask=mask,
        )
        steps.append(
            {
                "item_id": current.id,
                "preview_ids": [item.id for item in preview],
                "n_candidates": len(options),
                "placed": chosen is not None,
            }
        )
        if chosen is None:
            unpacked.append(UnpackedItem(item_id=current.id, reason=TERMINAL_REASON))
            for pending in remaining[1:]:
                unpacked.append(UnpackedItem(item_id=pending.id, reason=SUFFIX_REASON))
            break
        if chosen.item.id != current.id:
            raise CompactError("GreedyBestFit eligió un ítem que no es el actual")
        session.commit(chosen.candidate, chosen.item)
        remaining = [item for item in remaining if item.id != chosen.item.id]
    loop_seconds = time.perf_counter() - started
    metadata = METADATA.model_copy(
        update={
            "name": algorithm_name,
            "display_name": display_name,
            "description": description,
        }
    )
    solution = build_solution(
        problem=problem,
        metadata=metadata,
        packed_items=session.packed,
        unpacked_items=unpacked,
        execution_time_seconds=loop_seconds,
    )
    return solution, {
        "packing_loop_seconds": loop_seconds,
        "steps": steps,
        "n_packed": len(session.packed),
        "n_unpacked": len(unpacked),
        "stopped_early": any(item.reason == TERMINAL_REASON for item in unpacked),
        "generator": "extreme_point",
        "selector": selector,
        "coefficients": coefficients,
        "physical_stability_verified": None,
    }


def run_compact_greedy(problem: Any) -> tuple[Any, dict[str, Any]]:
    """GreedyBestFit del ítem actual. No usa los coeficientes del selector compacto."""

    prepare_imports()
    from packing_services.online.policies import GreedyBestFitPolicy

    return run_compact_episode(
        problem,
        GreedyBestFitPolicy(),
        algorithm_name=ALGORITHM_NAME,
        display_name="GreedyBestFit con terminación al primer ítem imposible",
        description="Mismo selector best-fit del ítem actual. El episodio termina si ese ítem no tiene candidata legal.",
        selector="GreedyBestFitPolicy",
    )


def run_compact_selector(problem: Any, a: float, b: float, c: float) -> tuple[Any, dict[str, Any]]:
    """Selector compacto. Los coeficientes no cambian el generador ni el terminal."""

    from compact_selector import FORMULA_VERSION, CompactScorePolicy

    return run_compact_episode(
        problem,
        CompactScorePolicy(a, b, c),
        algorithm_name="compact_selector",
        display_name=f"Selector compacto {FORMULA_VERSION}",
        description="Puntúa candidatas legales del ítem actual. No observa la cola futura.",
        selector="CompactScorePolicy",
        coefficients={"a": float(a), "b": float(b), "c": float(c)},
    )


def capture_online_bph(
    snapshot: dict[str, Any],
    episode: dict[str, Any],
    *,
    order_id: str,
    dataset: str,
    dataset_sha256: str,
) -> dict[str, Any]:
    """Captura las cajas que devolvió el entorno externo, sin recalcular su selección."""

    items = snapshot["items"]
    container = snapshot["containers"][0]
    sentinel = episode.get("sentinel_lwh_mm")
    placed = []
    for placement in episode["placed"]:
        oriented = [float(value) for value in placement["oriented_lwh_mm"]]
        if isinstance(sentinel, list) and len(sentinel) == 3 and all(
            abs(oriented[index] - float(sentinel[index])) <= 1e-6 for index in range(3)
        ):
            continue
        placed.append(placement)
    input_changed = False
    placements = []
    for index, placement in enumerate(placed):
        if index >= len(items):
            input_changed = True
            break
        source = items[index]
        original = [float(source["length_mm"]), float(source["width_mm"]), float(source["height_mm"])]
        oriented = [float(value) for value in placement["oriented_lwh_mm"]]
        remaining = list(original)
        for value in oriented:
            match = next((pos for pos, item in enumerate(remaining) if abs(item - value) <= 1e-6), None)
            if match is None:
                input_changed = True
                break
            remaining.pop(match)
        if remaining:
            input_changed = True
        placements.append(
            {
                "packed_list_index": index,
                "item_id": source["item_id"],
                "container_id": container["id"],
                "flb_mm": [float(value) for value in placement["flb_mm"]],
                "original_lwh_mm": original,
                "oriented_lwh_mm": oriented,
                "weight_kg": source["weight_kg"],
            }
        )
    unpacked = []
    if len(placed) < len(items):
        unpacked.append({"item_id": items[len(placed)]["item_id"], "reason": TERMINAL_REASON})
        for source in items[len(placed) + 1 :]:
            unpacked.append({"item_id": source["item_id"], "reason": SUFFIX_REASON})
    return {
        "units": {"length": "mm", "volume": "mm3", "weight": "kg", "time": "s"},
        "order_id": order_id,
        "method": "online_bph",
        "recipe": {
            "method": "online_bph",
            "orders_path": dataset,
            "orders_sha256": dataset_sha256,
            "checkpoint_path": None,
            "lookahead_p": snapshot["lookahead_p"],
            "select_s": snapshot["select_s"],
            "selection": "online_bph_first_feasible_ems",
            "sort_strategy": snapshot["sort_strategy"],
            "packing_mode": "online",
            "problem_type": snapshot["problem_type"],
            "algorithm": "online_bph",
            "constraints": snapshot["constraints"],
            "min_support_ratio_effective": snapshot["min_support_ratio_effective"],
            "consolidate_effective": snapshot["consolidate_effective"],
            "n_containers": snapshot["n_containers"],
            "device": "cpu",
            "attempts": 1,
            "sampling": False,
            "terminal": "stop_at_first_impossible_item",
            "generator": "ems_of_Online-3D-BPP-PCT",
            "decision": (
                "OnlineBPH: EMS ordenados por (z, y, x) y la primera de seis orientaciones "
                "que drop_box_virtual acepta. El generador no se sustituye por puntos extremos."
            ),
            "setting": episode.get("setting"),
            "orientation": episode.get("orientation"),
            "input_changed": input_changed,
            "dimensions_rounded": False,
            "weight_used_by_selector": False,
            "stability_used_by_selector": False,
            "setting_2_skips_stability_check": episode.get("setting") == 2,
        },
        "containers": snapshot["containers"],
        "input_items": items,
        "placements": placements,
        "unpacked": unpacked,
        "physical_stability_verified": None,
    }


def capture_compact_case(
    problem: Any,
    solution: Any,
    *,
    order_id: str,
    dataset: str,
    dataset_sha256: str,
    coefficients: dict[str, float] | None = None,
) -> dict[str, Any]:
    from pathlib import Path

    from compact_selector import FORMULA, FORMULA_VERSION
    from pilot_common import REPO_ROOT

    method = "compact_selector" if coefficients is not None else "greedy"
    document = capture_document(
        problem,
        solution,
        method=method,
        order_id=order_id,
        orders_path=Path(dataset),
        orders_sha256=dataset_sha256,
        checkpoint_path=REPO_ROOT,
    )
    if coefficients is None:
        document["recipe"]["decision"] = (
            "GreedyBestFitPolicy sobre las candidatas legales del ítem actual. "
            "Si no hay ninguna, el episodio termina y el sufijo no se coloca."
        )
        document["recipe"]["coefficients"] = None
    else:
        document["recipe"]["decision"] = (
            "CompactScorePolicy sobre las candidatas legales del ítem actual. "
            "El contacto es -rank_key[0] normalizado por el área de las caras. "
            "No es una prueba de estabilidad. Si no hay candidata válida, el episodio termina."
        )
        document["recipe"]["coefficients"] = {
            "a": float(coefficients["a"]),
            "b": float(coefficients["b"]),
            "c": float(coefficients["c"]),
        }
        document["recipe"]["formula_version"] = FORMULA_VERSION
        document["recipe"]["formula"] = FORMULA
    document["recipe"]["terminal"] = "stop_at_first_impossible_item"
    document["recipe"]["observes_future_item_dimensions"] = False
    document["recipe"]["passes_remaining_count"] = False
    document["physical_stability_verified"] = None
    return document
