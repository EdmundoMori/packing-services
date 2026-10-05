"""Contrato único del subconjunto S de candidatas.

Fuente de verdad para etiquetado, entrenamiento y despliegue. No empaqueta
pedidos reales y no consulta sufijo, Q_hat, etiquetas ni identificadores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

SUPPORT_LIMIT = 4
CONTRACT_NAME = "greedy_plus_orientation_position_diversity_v1"
CONTRACT_NOTES = (
    "Reutiliza la diversidad de orientación y Chebyshev del diagnóstico "
    "counterfactual (select_alternatives), con deduplicación geométrica "
    "explícita antes de completar S."
)


@dataclass(frozen=True)
class GeometryRecord:
    """Identidad geométrica presente. No incluye retorno ni futuro."""

    bin_index: int
    x: float
    y: float
    z: float
    length: float
    width: float
    height: float
    source_index: int

    @property
    def geometric_id(self) -> tuple[Any, ...]:
        return (
            int(self.bin_index),
            float(self.x),
            float(self.y),
            float(self.z),
            float(self.length),
            float(self.width),
            float(self.height),
        )

    @property
    def orientation(self) -> tuple[float, float, float]:
        return (float(self.length), float(self.width), float(self.height))

    @property
    def position(self) -> tuple[float, float, float]:
        return (float(self.x), float(self.y), float(self.z))


def geometric_id_from_mapping(row: Mapping[str, Any]) -> tuple[Any, ...]:
    if "geometric_id" in row:
        return tuple(row["geometric_id"])
    if "action" in row:
        return tuple(row["action"])
    return (
        int(row["bin_index"]),
        float(row["x"]),
        float(row["y"]),
        float(row["z"]),
        float(row["length"]),
        float(row["width"]),
        float(row["height"]),
    )


def record_from_candidate(candidate: Any, *, source_index: int) -> GeometryRecord:
    return GeometryRecord(
        bin_index=int(candidate.bin_index),
        x=float(candidate.position.x),
        y=float(candidate.position.y),
        z=float(candidate.position.z),
        length=float(candidate.dimensions.length),
        width=float(candidate.dimensions.width),
        height=float(candidate.dimensions.height),
        source_index=int(source_index),
    )


def records_from_options(options: Sequence[Any]) -> list[GeometryRecord]:
    """Convierte opciones del motor sin mutar la lista original."""

    return [record_from_candidate(option.candidate, source_index=index) for index, option in enumerate(options)]


def _chebyshev(left: GeometryRecord, right: GeometryRecord) -> float:
    return max(abs(left.x - right.x), abs(left.y - right.y), abs(left.z - right.z))


def dedupe_geometries(records: Sequence[GeometryRecord]) -> list[GeometryRecord]:
    """Conserva la primera aparición de cada geometric_id en el orden legal."""

    chosen: list[GeometryRecord] = []
    seen: set[tuple[Any, ...]] = set()
    for record in records:
        identity = record.geometric_id
        if identity in seen:
            continue
        seen.add(identity)
        chosen.append(record)
    return chosen


def build_candidate_support(
    legal: Sequence[GeometryRecord],
    greedy_id: Sequence[Any] | tuple[Any, ...],
    *,
    limit: int = SUPPORT_LIMIT,
) -> list[GeometryRecord]:
    """Construye S: Greedy más diversidad de orientación/posición, máx. `limit`.

    - Solo usa geometría presente.
    - No muta `legal`.
    - Elimina duplicados geométricos; orientaciones distintas permanecen distintas.
    - Empates de diversidad: mayor (nueva_orientación, distancia_chebyshev, -source_index).
    """

    if limit < 1:
        return []
    greedy_key = tuple(greedy_id)
    unique = dedupe_geometries(legal)
    greedy = next((row for row in unique if row.geometric_id == greedy_key), None)
    if greedy is None:
        raise ValueError("la propuesta Greedy no está entre las candidatas legales deduplicadas")
    chosen = [greedy]
    rest = [row for row in unique if row.geometric_id != greedy_key]
    while len(chosen) < limit and rest:
        best_index = 0
        best_key: tuple[Any, ...] | None = None
        known = {row.orientation for row in chosen}
        for index, option in enumerate(rest):
            new_orientation = 1 if option.orientation not in known else 0
            distance = min(_chebyshev(option, item) for item in chosen)
            key = (new_orientation, distance, -option.source_index)
            if best_key is None or key > best_key:
                best_key = key
                best_index = index
        chosen.append(rest.pop(best_index))
    return chosen


def build_candidate_support_from_options(
    options: Sequence[Any],
    greedy_option: Any,
    *,
    limit: int = SUPPORT_LIMIT,
) -> list[Any]:
    """Misma regla sobre opciones del motor. No muta `options`."""

    if greedy_option is None:
        return []
    records = records_from_options(options)
    greedy_record = record_from_candidate(greedy_option.candidate, source_index=-1)
    selected = build_candidate_support(records, greedy_record.geometric_id, limit=limit)
    by_id = {}
    for index, option in enumerate(options):
        identity = record_from_candidate(option.candidate, source_index=index).geometric_id
        by_id.setdefault(identity, option)
    return [by_id[row.geometric_id] for row in selected]


def support_identities(support: Sequence[GeometryRecord]) -> list[tuple[Any, ...]]:
    return [row.geometric_id for row in support]


def select_logit_index(logits: Sequence[float]) -> int:
    """Mayor score gana. Empate exacto en float: menor índice dentro de S."""

    if not logits:
        raise ValueError("no hay logits")
    best = max(logits)
    for index, value in enumerate(logits):
        if value == best:
            return index
    raise RuntimeError("el máximo no reaparece")


def select_within_support(
    support: Sequence[GeometryRecord],
    logits: Sequence[float],
) -> GeometryRecord:
    if len(support) != len(logits):
        raise ValueError("logits y S no están alineados")
    return support[select_logit_index(logits)]
