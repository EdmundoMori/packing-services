"""Tres reglas sobre la misma lista de candidatas legales.

El desempate común, después de la clave primaria, es el menor índice
original de esa lista. Las tres acciones se conservan aunque la geometría
coincida.
"""

from __future__ import annotations

from typing import Any

RULE_NAMES = ("greedy_best_fit", "lowest_top", "least_height_increase")


def geometry_key(candidate: Any) -> tuple:
    position = candidate.position
    dimensions = candidate.dimensions
    return (
        int(candidate.bin_index),
        round(float(position.x), 6),
        round(float(position.y), 6),
        round(float(position.z), 6),
        round(float(dimensions.length), 6),
        round(float(dimensions.width), 6),
        round(float(dimensions.height), 6),
    )


def current_max_height(session: Any) -> float:
    if len(session.states) != 1:
        raise ValueError("el contrato usa un contenedor")
    height = 0.0
    for packed in session.packed:
        top = float(packed.position.z) + float(packed.orientation.height)
        height = max(height, top)
    return height


def _argmin(options: list[Any], primary) -> tuple[int, Any]:
    best_index = 0
    best_key = None
    for index, option in enumerate(options):
        key = (primary(option), index)
        if best_key is None or key < best_key:
            best_key = key
            best_index = index
    return best_index, options[best_index]


def propose_rules(options: list[Any], session: Any) -> list[dict[str, Any]]:
    """Devuelve tres propuestas, una por regla, en orden fijo."""

    if not options:
        return [
            {"rule": name, "action": index, "option": None, "candidate_index": None, "geometry": None}
            for index, name in enumerate(RULE_NAMES)
        ]
    skyline = current_max_height(session)

    def top(option: Any) -> float:
        candidate = option.candidate
        return float(candidate.position.z) + float(candidate.dimensions.height)

    def increase(option: Any) -> float:
        return max(skyline, top(option)) - skyline

    choices = [
        _argmin(options, lambda option: option.candidate.rank_key),
        _argmin(options, top),
        _argmin(options, increase),
    ]
    proposals = []
    for action, (name, (candidate_index, option)) in enumerate(zip(RULE_NAMES, choices)):
        proposals.append(
            {
                "rule": name,
                "action": action,
                "option": option,
                "candidate_index": candidate_index,
                "geometry": geometry_key(option.candidate),
            }
        )
    return proposals


def redundancy(proposals: list[dict[str, Any]]) -> dict[str, bool | None]:
    geometries = [row["geometry"] for row in proposals]
    if any(geometry is None for geometry in geometries):
        return {
            "greedy_and_lowest_top": None,
            "greedy_and_least_height": None,
            "lowest_top_and_least_height": None,
            "all_three": None,
            "any_pair": None,
        }
    pairs = {
        "greedy_and_lowest_top": geometries[0] == geometries[1],
        "greedy_and_least_height": geometries[0] == geometries[2],
        "lowest_top_and_least_height": geometries[1] == geometries[2],
    }
    pairs["all_three"] = all(pairs.values())
    pairs["any_pair"] = any(pairs[key] for key in (
        "greedy_and_lowest_top",
        "greedy_and_least_height",
        "lowest_top_and_least_height",
    ))
    return pairs
