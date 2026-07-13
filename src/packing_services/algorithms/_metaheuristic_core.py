"""Utilidades compartidas para metaheurísticas 3D-BPP.

Codifica la solución como una permutación del orden de colocación de ítems y
decodifica mediante un constructivo base con ``sort_strategy=input_order``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from ..domain.enums import SortStrategy
from ..domain.models import PackingProblem, PackingSolution
from ..utils.timing import Deadline, measure_time
from ._constructive import order_items
from ._constructive_runner import resolve_base_algorithm, run_constructive_base
from .base import PackingAlgorithm, build_solution
from .metadata import AlgorithmMetadata

Fitness = tuple[int, float, int]


@dataclass
class SearchState:
    """Estado de búsqueda: orden de ítems, solución decodificada y fitness."""

    order: list[str]
    solution: PackingSolution
    fitness: Fitness


@dataclass
class MetaContext:
    """Contexto de ejecución común a todas las metaheurísticas."""

    problem: PackingProblem
    base_name: str
    rng: random.Random
    deadline: Deadline
    iterations: int
    params: dict[str, object]
    seed: int


def build_context(problem: PackingProblem) -> MetaContext:
    """Construye el contexto de búsqueda a partir del problema normalizado."""

    params = problem.algorithm.parameters
    seed = problem.algorithm.random_seed
    if seed is None and params.get("random_seed") is not None:
        seed = int(params["random_seed"])
    if seed is None:
        seed = 42

    iterations = int(params.get("iterations", 50))
    time_limit = problem.algorithm.time_limit_seconds
    if time_limit is None and params.get("time_limit_seconds") is not None:
        time_limit = float(params["time_limit_seconds"])

    return MetaContext(
        problem=problem,
        base_name=resolve_base_algorithm(problem),
        rng=random.Random(seed),
        deadline=Deadline(time_limit),
        iterations=iterations,
        params=params,
        seed=seed,
    )


def solution_fitness(solution: PackingSolution) -> Fitness:
    """Menor es mejor: primero ítems sin empacar, luego utilización, luego bins."""

    return (
        solution.metrics.items_unpacked,
        -solution.metrics.volume_utilization,
        solution.metrics.containers_used,
    )


def item_ids(problem: PackingProblem) -> list[str]:
    return [item.id for item in problem.items]


def volume_baseline_order(problem: PackingProblem) -> list[str]:
    ordered = order_items(problem.items, SortStrategy.VOLUME_DESC)
    return [item.id for item in ordered]


def decode_permutation(
    problem: PackingProblem,
    order: list[str],
    base_name: str,
) -> PackingSolution:
    """Decodifica una permutación ejecutando el constructivo base."""

    by_id = {item.id: item for item in problem.items}
    ordered_items: list = []
    seen: set[str] = set()
    for item_id in order:
        if item_id in by_id and item_id not in seen:
            ordered_items.append(by_id[item_id])
            seen.add(item_id)
    for item in problem.items:
        if item.id not in seen:
            ordered_items.append(item)

    params = dict(problem.algorithm.parameters)
    params["sort_strategy"] = SortStrategy.INPUT_ORDER.value
    subproblem = problem.model_copy(
        update={
            "items": ordered_items,
            "algorithm": problem.algorithm.model_copy(update={"parameters": params}),
        }
    )
    return run_constructive_base(subproblem, base_name)


def evaluate(ctx: MetaContext, order: list[str]) -> SearchState:
    solution = decode_permutation(ctx.problem, order, ctx.base_name)
    return SearchState(order=list(order), solution=solution, fitness=solution_fitness(solution))


def swap_neighbor(order: list[str], i: int, j: int) -> list[str]:
    new_order = list(order)
    new_order[i], new_order[j] = new_order[j], new_order[i]
    return new_order


def insert_neighbor(order: list[str], i: int, j: int) -> list[str]:
    new_order = list(order)
    item = new_order.pop(i)
    new_order.insert(j, item)
    return new_order


def local_search_order(
    ctx: MetaContext,
    order: list[str],
    *,
    max_steps: int = 8,
) -> SearchState:
    """Mejora local por intercambios aleatorios en el orden."""

    state = evaluate(ctx, order)
    for _ in range(max_steps):
        if ctx.deadline.exceeded():
            break
        improved = False
        n = len(state.order)
        if n < 2:
            break
        attempts = min(n * 2, 30)
        for _ in range(attempts):
            i, j = ctx.rng.sample(range(n), 2)
            candidate = evaluate(ctx, swap_neighbor(state.order, i, j))
            if candidate.fitness < state.fitness:
                state = candidate
                improved = True
                break
        if not improved:
            break
    return state


def run_metaheuristic_algorithm(
    metadata: AlgorithmMetadata,
    problem: PackingProblem,
    search_fn: Callable[[MetaContext], tuple[SearchState, dict[str, object]]],
) -> PackingSolution:
    """Plantilla de ejecución: búsqueda + trazabilidad homogénea."""

    ctx = build_context(problem)
    with measure_time() as elapsed:
        best_state, trace = search_fn(ctx)

    solution = build_solution(
        problem=problem,
        metadata=metadata,
        packed_items=best_state.solution.packed_items,
        unpacked_items=best_state.solution.unpacked_items,
        execution_time_seconds=elapsed.seconds,
    )
    return solution.model_copy(
        update={
            "execution_metadata": solution.execution_metadata.model_copy(
                update={
                    "parameters": {
                        **solution.execution_metadata.parameters,
                        "base_algorithm_used": ctx.base_name,
                        "iterations_requested": ctx.iterations,
                        "random_seed_used": ctx.seed,
                        "best_items_packed": best_state.solution.metrics.items_packed,
                        "best_items_unpacked": best_state.solution.metrics.items_unpacked,
                        "best_volume_utilization": best_state.solution.metrics.volume_utilization,
                        **trace,
                    }
                }
            )
        }
    )


def order_crossover(
    parent_a: list[str],
    parent_b: list[str],
    rng: random.Random,
) -> list[str]:
    """Cruce OX sobre permutaciones de ids de ítem."""

    n = len(parent_a)
    if n < 2:
        return list(parent_a)
    i, j = sorted(rng.sample(range(n), 2))
    child = [""] * n
    child[i : j + 1] = parent_a[i : j + 1]
    fill = [x for x in parent_b if x not in child]
    idx = 0
    for pos in range(n):
        if not child[pos]:
            child[pos] = fill[idx]
            idx += 1
    return child
