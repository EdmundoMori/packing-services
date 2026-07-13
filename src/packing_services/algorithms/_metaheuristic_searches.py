"""Implementaciones de búsqueda metaheurística sobre orden de colocación."""

from __future__ import annotations

import math

from ._metaheuristic_core import (
    MetaContext,
    SearchState,
    evaluate,
    insert_neighbor,
    item_ids,
    local_search_order,
    order_crossover,
    swap_neighbor,
    volume_baseline_order,
)


def _fitness_delta(current: SearchState, candidate: SearchState) -> float:
    """Delta escalar aproximado (desempate por utilización)."""

    return (
        (candidate.fitness[0] - current.fitness[0]) * 1000.0
        + (candidate.fitness[1] - current.fitness[1]) * 100.0
        + (candidate.fitness[2] - current.fitness[2])
    )


def run_simulated_annealing(ctx: MetaContext) -> tuple[SearchState, dict[str, object]]:
    order = volume_baseline_order(ctx.problem)
    current = evaluate(ctx, order)
    best = current
    temperature = float(ctx.params.get("initial_temperature", 1.0))
    cooling_rate = float(ctx.params.get("cooling_rate", 0.95))
    evaluations = 1
    accepted = 0

    for _ in range(ctx.iterations):
        if ctx.deadline.exceeded():
            break
        n = len(current.order)
        if n < 2:
            break
        i, j = ctx.rng.sample(range(n), 2)
        neighbor = evaluate(ctx, swap_neighbor(current.order, i, j))
        evaluations += 1
        delta = _fitness_delta(current, neighbor)
        if delta < 0 or ctx.rng.random() < math.exp(-delta / max(temperature, 1e-9)):
            current = neighbor
            accepted += 1
            if neighbor.fitness < best.fitness:
                best = neighbor
        temperature *= cooling_rate

    return best, {
        "metaheuristic": "simulated_annealing",
        "evaluations": evaluations,
        "accepted_moves": accepted,
        "final_temperature": temperature,
    }


def run_genetic_algorithm(ctx: MetaContext) -> tuple[SearchState, dict[str, object]]:
    ids = item_ids(ctx.problem)
    population_size = max(4, int(ctx.params.get("population_size", 12)))
    mutation_rate = float(ctx.params.get("mutation_rate", 0.15))
    crossover_rate = float(ctx.params.get("crossover_rate", 0.8))
    generations = ctx.iterations

    population = [volume_baseline_order(ctx.problem)]
    while len(population) < population_size:
        order = list(ids)
        ctx.rng.shuffle(order)
        population.append(order)

    states = [evaluate(ctx, order) for order in population]
    best = min(states, key=lambda s: s.fitness)
    evaluations = len(states)

    def tournament() -> SearchState:
        contenders = ctx.rng.sample(states, min(3, len(states)))
        return min(contenders, key=lambda s: s.fitness)

    for _ in range(generations):
        if ctx.deadline.exceeded():
            break
        next_states: list[SearchState] = [best]
        while len(next_states) < population_size:
            parent_a = tournament()
            parent_b = tournament()
            if ctx.rng.random() < crossover_rate:
                child_order = order_crossover(parent_a.order, parent_b.order, ctx.rng)
            else:
                child_order = list(parent_a.order)
            if len(child_order) >= 2 and ctx.rng.random() < mutation_rate:
                i, j = ctx.rng.sample(range(len(child_order)), 2)
                child_order = swap_neighbor(child_order, i, j)
            child = evaluate(ctx, child_order)
            evaluations += 1
            next_states.append(child)
            if child.fitness < best.fitness:
                best = child
        states = next_states

    return best, {
        "metaheuristic": "genetic_algorithm",
        "evaluations": evaluations,
        "population_size": population_size,
        "generations": generations,
    }


def run_grasp(ctx: MetaContext) -> tuple[SearchState, dict[str, object]]:
    alpha = float(ctx.params.get("alpha", 0.3))
    local_steps = int(ctx.params.get("local_search_steps", 5))
    ranked = volume_baseline_order(ctx.problem)
    by_id = {item.id: item for item in ctx.problem.items}
    volumes = {item_id: by_id[item_id].volume for item_id in ranked}

    best = evaluate(ctx, ranked)
    evaluations = 1

    for _ in range(ctx.iterations):
        if ctx.deadline.exceeded():
            break
        remaining = list(ranked)
        order: list[str] = []
        while remaining:
            vmax = max(volumes[item_id] for item_id in remaining)
            vmin = min(volumes[item_id] for item_id in remaining)
            threshold = vmax - alpha * (vmax - vmin) if vmax > vmin else vmax
            rcl = [item_id for item_id in remaining if volumes[item_id] >= threshold]
            pick = ctx.rng.choice(rcl)
            order.append(pick)
            remaining.remove(pick)
        candidate = local_search_order(ctx, order, max_steps=local_steps)
        evaluations += local_steps + 1
        if candidate.fitness < best.fitness:
            best = candidate

    return best, {
        "metaheuristic": "grasp",
        "evaluations": evaluations,
        "alpha": alpha,
    }


def run_tabu_search(ctx: MetaContext) -> tuple[SearchState, dict[str, object]]:
    tabu_tenure = int(ctx.params.get("tabu_tenure", 7))
    current = evaluate(ctx, volume_baseline_order(ctx.problem))
    best = current
    tabu: dict[tuple[int, int], int] = {}
    evaluations = 1

    for step in range(ctx.iterations):
        if ctx.deadline.exceeded():
            break
        n = len(current.order)
        if n < 2:
            break
        best_neighbor: SearchState | None = None
        samples = min(n * 3, 40)
        for _ in range(samples):
            i, j = ctx.rng.sample(range(n), 2)
            move = (min(i, j), max(i, j))
            if tabu.get(move, 0) > step:
                continue
            neighbor = evaluate(ctx, swap_neighbor(current.order, i, j))
            evaluations += 1
            if best_neighbor is None or neighbor.fitness < best_neighbor.fitness:
                best_neighbor = neighbor
                best_move = move
        if best_neighbor is None:
            i, j = ctx.rng.sample(range(n), 2)
            best_neighbor = evaluate(ctx, swap_neighbor(current.order, i, j))
            evaluations += 1
            best_move = (min(i, j), max(i, j))
        current = best_neighbor
        tabu[best_move] = step + tabu_tenure
        if current.fitness < best.fitness:
            best = current

    return best, {
        "metaheuristic": "tabu_search",
        "evaluations": evaluations,
        "tabu_tenure": tabu_tenure,
    }


def run_lns(ctx: MetaContext) -> tuple[SearchState, dict[str, object]]:
    destroy_fraction = float(ctx.params.get("destroy_fraction", 0.25))
    current = evaluate(ctx, volume_baseline_order(ctx.problem))
    best = current
    evaluations = 1

    for _ in range(ctx.iterations):
        if ctx.deadline.exceeded():
            break
        n = len(current.order)
        if n < 2:
            break
        destroy_count = max(1, int(n * destroy_fraction))
        removed_idx = sorted(ctx.rng.sample(range(n), destroy_count), reverse=True)
        order = list(current.order)
        removed: list[str] = []
        for idx in removed_idx:
            removed.append(order.pop(idx))
        ctx.rng.shuffle(removed)
        for item_id in removed:
            pos = ctx.rng.randrange(len(order) + 1)
            order.insert(pos, item_id)
        candidate = evaluate(ctx, order)
        evaluations += 1
        if candidate.fitness < current.fitness:
            current = candidate
            if candidate.fitness < best.fitness:
                best = candidate

    return best, {
        "metaheuristic": "lns",
        "evaluations": evaluations,
        "destroy_fraction": destroy_fraction,
    }


def run_vns(ctx: MetaContext) -> tuple[SearchState, dict[str, object]]:
    max_neighborhood = int(ctx.params.get("max_neighborhood", 4))
    shake_intensity = int(ctx.params.get("shake_intensity", 3))
    current = evaluate(ctx, volume_baseline_order(ctx.problem))
    best = current
    evaluations = 1
    k = 1

    while k <= max_neighborhood and not ctx.deadline.exceeded():
        shaken = list(current.order)
        n = len(shaken)
        if n < 2:
            break
        for _ in range(shake_intensity * k):
            op = k % 3
            i, j = ctx.rng.sample(range(n), 2)
            if op == 0:
                shaken = swap_neighbor(shaken, i, j)
            elif op == 1:
                shaken = insert_neighbor(shaken, i, j)
            else:
                block = min(3, n)
                start = ctx.rng.randrange(0, max(1, n - block + 1))
                segment = shaken[start : start + block]
                ctx.rng.shuffle(segment)
                shaken = shaken[:start] + segment + shaken[start + block :]
        shaken_state = local_search_order(ctx, shaken, max_steps=4)
        evaluations += shake_intensity * k + 4
        if shaken_state.fitness < current.fitness:
            current = shaken_state
            k = 1
            if current.fitness < best.fitness:
                best = current
        else:
            k += 1

    return best, {
        "metaheuristic": "vns",
        "evaluations": evaluations,
        "max_neighborhood": max_neighborhood,
    }


def run_aco(ctx: MetaContext) -> tuple[SearchState, dict[str, object]]:
    ids = item_ids(ctx.problem)
    n = len(ids)
    if n == 0:
        empty = evaluate(ctx, [])
        return empty, {"metaheuristic": "aco", "evaluations": 0}

    by_id = {item.id: item for item in ctx.problem.items}
    heuristic = {
        (a, b): 1.0 / max(by_id[b].volume, 1e-6) for a in ids for b in ids if a != b
    }
    pheromone = {key: 1.0 for key in heuristic}
    evaporation = float(ctx.params.get("evaporation", 0.1))
    alpha = float(ctx.params.get("alpha_pheromone", 1.0))
    beta = float(ctx.params.get("beta_heuristic", 2.0))
    ants = max(2, int(ctx.params.get("ants_count", 8)))

    best = evaluate(ctx, volume_baseline_order(ctx.problem))
    evaluations = 1

    for _ in range(ctx.iterations):
        if ctx.deadline.exceeded():
            break
        iteration_best: SearchState | None = None
        for _ in range(ants):
            unvisited = set(ids)
            start = ctx.rng.choice(ids)
            tour = [start]
            unvisited.remove(start)
            while unvisited:
                current_id = tour[-1]
                candidates = list(unvisited)
                weights = []
                for nxt in candidates:
                    key = (current_id, nxt)
                    weights.append(
                        (pheromone[key] ** alpha) * (heuristic[key] ** beta)
                    )
                total = sum(weights)
                if total <= 0:
                    nxt = ctx.rng.choice(candidates)
                else:
                    pick = ctx.rng.random() * total
                    acc = 0.0
                    nxt = candidates[-1]
                    for candidate, weight in zip(candidates, weights):
                        acc += weight
                        if pick <= acc:
                            nxt = candidate
                            break
                tour.append(nxt)
                unvisited.remove(nxt)
            state = evaluate(ctx, tour)
            evaluations += 1
            if iteration_best is None or state.fitness < iteration_best.fitness:
                iteration_best = state
            if state.fitness < best.fitness:
                best = state

        for key in pheromone:
            pheromone[key] *= 1.0 - evaporation
        if iteration_best is not None:
            deposit = 1.0 / max(
                1.0,
                iteration_best.fitness[0] + 1,
                -iteration_best.fitness[1] * 100,
            )
            tour = iteration_best.order
            for i in range(len(tour) - 1):
                key = (tour[i], tour[i + 1])
                pheromone[key] += deposit

    return best, {
        "metaheuristic": "aco",
        "evaluations": evaluations,
        "ants_count": ants,
    }
