"""Clasificación de algoritmos por modo de packing (offline / online).

Un solo contrato de entrada (``PackAlgorithmInput`` / BED-BPP). Lo que cambia
es qué puede hacer el solver con ``sequence`` / ``arrival_index``.
"""

from __future__ import annotations

from ..utils.errors import InvalidInputError
from .enums import AlgorithmFamily, PackingMode, ProblemType, SortStrategy

DEFAULT_PACKING_MODE = PackingMode.OFFLINE

# Heurístico online y DRL: aún no ejecutables; solo aparecen en modo online.
ONLINE_ONLY_NAMES = frozenset(
    {
        "online_3d_bpp_heuristic",
        "drl_policy_3d_bpp",
    }
)

# Ven el pedido completo: permutaciones, mejora local, exactos.
OFFLINE_ONLY_FAMILIES = frozenset(
    {
        AlgorithmFamily.METAHEURISTIC,
        AlgorithmFamily.IMPROVEMENT_HEURISTIC,
        AlgorithmFamily.HYBRID,
        AlgorithmFamily.EXACT,
    }
)

_ONLINE_SORT = SortStrategy.INPUT_ORDER.value


def parse_packing_mode(value: object | None) -> PackingMode:
    """``None`` / vacío → offline (subsistema cerrado por defecto)."""
    if value is None or value == "":
        return DEFAULT_PACKING_MODE
    if isinstance(value, PackingMode):
        return value
    try:
        return PackingMode(str(value).strip().lower())
    except ValueError as exc:
        allowed = ", ".join(m.value for m in PackingMode)
        raise InvalidInputError(
            f"packing_mode={value!r} no es válido. Use uno de: {allowed}."
        ) from exc


def modes_for_algorithm(
    name: str,
    family: AlgorithmFamily,
    problem_types: list[ProblemType],
) -> tuple[PackingMode, ...]:
    """Modos en los que un algoritmo puede figurar en el catálogo."""
    if name in ONLINE_ONLY_NAMES:
        return (PackingMode.ONLINE,)
    if family in OFFLINE_ONLY_FAMILIES:
        return (PackingMode.OFFLINE,)
    if problem_types and all(pt == ProblemType.CARTONIZATION for pt in problem_types):
        # Elegir caja requiere el pedido completo.
        return (PackingMode.OFFLINE,)
    return (PackingMode.OFFLINE, PackingMode.ONLINE)


def algorithm_supports_mode(
    name: str,
    family: AlgorithmFamily,
    problem_types: list[ProblemType],
    mode: PackingMode,
) -> bool:
    return mode in modes_for_algorithm(name, family, problem_types)


def ensure_algorithm_allowed(
    name: str,
    family: AlgorithmFamily,
    problem_types: list[ProblemType],
    mode: PackingMode,
) -> None:
    if algorithm_supports_mode(name, family, problem_types, mode):
        return
    allowed = ", ".join(
        m.value for m in modes_for_algorithm(name, family, problem_types)
    )
    extra = ""
    if mode == PackingMode.ONLINE:
        extra = (
            " El modo online no admite metaheurísticas, mejora local ni "
            "cartonization (miran o necesitan el pedido completo). "
            "Use un constructivo, o packing_mode=offline."
        )
    raise InvalidInputError(
        f"El algoritmo '{name}' no está disponible en packing_mode={mode.value}. "
        f"Modos de este algoritmo: {allowed}.{extra}"
    )


def default_sort_for_mode(mode: PackingMode) -> str:
    if mode == PackingMode.ONLINE:
        return _ONLINE_SORT
    return SortStrategy.VOLUME_DESC.value


def apply_mode_to_parameters(
    mode: PackingMode,
    user_parameters: dict | None,
    algorithm_defaults: dict | None,
) -> dict:
    """Defaults del algoritmo + usuario; online fuerza ``input_order``."""
    user = dict(user_parameters or {})
    if mode != PackingMode.ONLINE:
        return {**(algorithm_defaults or {}), **user}

    if "sort_strategy" in user and user["sort_strategy"] not in (None, _ONLINE_SORT):
        raise InvalidInputError(
            f"packing_mode=online no permite sort_strategy={user['sort_strategy']!r}. "
            "El orden de llegada es obligatorio (input_order)."
        )
    merged = {**(algorithm_defaults or {}), **user}
    merged["sort_strategy"] = _ONLINE_SORT
    return merged


def packing_modes_catalog() -> dict:
    """Descriptor para GET /packing-modes y metadatos del servicio."""
    return {
        "default": DEFAULT_PACKING_MODE.value,
        "same_input": True,
        "input": "PackAlgorithmInput o wrapper BED-BPP (mismo contrato en ambos modos)",
        "modes": [
            {
                "id": PackingMode.OFFLINE.value,
                "label": "Packing offline",
                "description": (
                    "El pedido completo se conoce de antemano. Se puede reordenar "
                    "(volume_desc / weight_desc) y usar metaheurísticas o mejora local."
                ),
                "status": "ready",
            },
            {
                "id": PackingMode.ONLINE.value,
                "label": "Packing online",
                "description": (
                    "Se respeta sequence/arrival_index; no se reordena. "
                    "Hoy: constructivos en orden de llegada. "
                    "Heurístico dedicado y DRL: capas siguientes."
                ),
                "status": "door_open",
            },
        ],
    }
