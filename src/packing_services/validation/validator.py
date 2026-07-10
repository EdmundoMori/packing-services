"""Packing Validation Service propio.

Valida que una solución de packing (venga de un motor interno o externo) sea
geométricamente factible. Es independiente del algoritmo que la generó, lo que
permite auditar y comparar resultados de forma homogénea.

Comprobaciones implementadas en la primera versión:

1. Contención: cada ítem empacado dentro de los límites de su contenedor.
2. No solapamiento entre ítems del mismo contenedor.
3. Peso máximo por contenedor no excedido.
4. Orientación válida respecto a las dimensiones originales del ítem.
5. Ítems duplicados (mismo item_id colocado más de una vez).
6. Ítems no empacados reportados de forma coherente (sin faltantes ni sobras).
7. (Opcional) Estabilidad básica por superficie de soporte, si se activa.

Las métricas pueden recalcularse aparte con ``metrics.compute_metrics``, lo que
cubre el requisito de "métricas recalculables desde la solución".
"""

from __future__ import annotations

from collections import defaultdict

from ..domain.geometry import (
    AABB,
    Dimensions,
    Position,
    fits_within,
    is_same_box,
    overlaps,
    supported_area_ratio,
)
from ..domain.models import (
    Container,
    ConstraintFlags,
    Item,
    PackedItem,
    ValidationReport,
    Violation,
)
from .violations import ViolationType, make_violation


class PackingValidator:
    """Validador geométrico reutilizable por todos los servicios."""

    def __init__(self, support_surface_ratio: float = 0.6) -> None:
        # Umbral usado solo cuando se valida estabilidad básica.
        self.support_surface_ratio = support_surface_ratio

    def validate(
        self,
        containers: list[Container],
        items: list[Item],
        packed_items: list[PackedItem],
        constraints: ConstraintFlags | None = None,
        expected_unpacked_ids: list[str] | None = None,
    ) -> ValidationReport:
        """Valida una solución y devuelve un reporte estructurado."""

        constraints = constraints or ConstraintFlags()
        violations: list[Violation] = []

        container_by_id = {c.id: c for c in containers}
        item_by_id = {it.id: it for it in items}

        violations += self._check_references(packed_items, container_by_id, item_by_id)
        violations += self._check_duplicates(packed_items)

        if constraints.containment:
            violations += self._check_containment(packed_items, container_by_id)
        if constraints.allow_rotation is not None:
            violations += self._check_orientation(packed_items, item_by_id)
        if constraints.non_overlap:
            violations += self._check_overlaps(packed_items)
        if constraints.max_weight:
            violations += self._check_max_weight(packed_items, container_by_id)
        if expected_unpacked_ids is not None:
            violations += self._check_unpacked(
                packed_items, item_by_id, expected_unpacked_ids
            )
        if constraints.basic_stability:
            violations += self._check_basic_stability(packed_items, item_by_id)

        is_valid = all(v.severity != "error" for v in violations)
        return ValidationReport(is_valid=is_valid, violations=violations)

    # ------------------------------------------------------------------ #
    # Comprobaciones individuales
    # ------------------------------------------------------------------ #

    def _check_references(
        self,
        packed_items: list[PackedItem],
        container_by_id: dict[str, Container],
        item_by_id: dict[str, Item],
    ) -> list[Violation]:
        violations: list[Violation] = []
        for p in packed_items:
            if p.container_id not in container_by_id:
                violations.append(
                    make_violation(
                        ViolationType.UNKNOWN_CONTAINER,
                        f"El ítem {p.item_id} referencia un contenedor inexistente "
                        f"{p.container_id}",
                        container_id=p.container_id,
                        item_ids=[p.item_id],
                    )
                )
            if p.item_id not in item_by_id:
                violations.append(
                    make_violation(
                        ViolationType.UNKNOWN_ITEM,
                        f"El ítem empacado {p.item_id} no existe en la instancia",
                        item_ids=[p.item_id],
                    )
                )
        return violations

    def _check_duplicates(self, packed_items: list[PackedItem]) -> list[Violation]:
        counts: dict[str, int] = defaultdict(int)
        for p in packed_items:
            counts[p.item_id] += 1
        return [
            make_violation(
                ViolationType.DUPLICATE_ITEM,
                f"El ítem {item_id} aparece empacado {count} veces",
                item_ids=[item_id],
            )
            for item_id, count in counts.items()
            if count > 1
        ]

    def _check_containment(
        self,
        packed_items: list[PackedItem],
        container_by_id: dict[str, Container],
    ) -> list[Violation]:
        violations: list[Violation] = []
        for p in packed_items:
            container = container_by_id.get(p.container_id)
            if container is None:
                continue  # Ya reportado en referencias.
            box = _to_aabb(p)
            if not fits_within(box, container.dimensions):
                violations.append(
                    make_violation(
                        ViolationType.CONTAINMENT,
                        f"El ítem {p.item_id} sobresale del contenedor "
                        f"{p.container_id}",
                        container_id=p.container_id,
                        item_ids=[p.item_id],
                    )
                )
        return violations

    def _check_orientation(
        self,
        packed_items: list[PackedItem],
        item_by_id: dict[str, Item],
    ) -> list[Violation]:
        violations: list[Violation] = []
        for p in packed_items:
            item = item_by_id.get(p.item_id)
            if item is None:
                continue
            used = Dimensions(
                p.orientation.length, p.orientation.width, p.orientation.height
            )
            # La orientación debe ser una permutación de las dimensiones
            # originales. Si el ítem no permite rotación, además debe coincidir
            # exactamente con l/w/h.
            if not is_same_box(used, item.dimensions):
                violations.append(
                    make_violation(
                        ViolationType.INVALID_ORIENTATION,
                        f"El ítem {p.item_id} usa dimensiones "
                        f"{used.as_tuple()} incompatibles con las originales "
                        f"{item.dimensions.as_tuple()}",
                        container_id=p.container_id,
                        item_ids=[p.item_id],
                    )
                )
            elif not item.allow_rotation and used.as_tuple() != item.dimensions.as_tuple():
                violations.append(
                    make_violation(
                        ViolationType.INVALID_ORIENTATION,
                        f"El ítem {p.item_id} fue rotado pero no permite rotación",
                        container_id=p.container_id,
                        item_ids=[p.item_id],
                    )
                )
        return violations

    def _check_overlaps(self, packed_items: list[PackedItem]) -> list[Violation]:
        violations: list[Violation] = []
        by_container: dict[str, list[PackedItem]] = defaultdict(list)
        for p in packed_items:
            by_container[p.container_id].append(p)

        for container_id, group in by_container.items():
            boxes = [(p, _to_aabb(p)) for p in group]
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    if overlaps(boxes[i][1], boxes[j][1]):
                        violations.append(
                            make_violation(
                                ViolationType.OVERLAP,
                                f"Los ítems {boxes[i][0].item_id} y "
                                f"{boxes[j][0].item_id} se solapan en el "
                                f"contenedor {container_id}",
                                container_id=container_id,
                                item_ids=[boxes[i][0].item_id, boxes[j][0].item_id],
                            )
                        )
        return violations

    def _check_max_weight(
        self,
        packed_items: list[PackedItem],
        container_by_id: dict[str, Container],
    ) -> list[Violation]:
        violations: list[Violation] = []
        weight_by_container: dict[str, float] = defaultdict(float)
        for p in packed_items:
            weight_by_container[p.container_id] += p.weight

        for container_id, total in weight_by_container.items():
            container = container_by_id.get(container_id)
            if container is None or container.max_weight is None:
                continue
            if total > container.max_weight + 1e-6:
                violations.append(
                    make_violation(
                        ViolationType.MAX_WEIGHT,
                        f"El contenedor {container_id} excede su peso máximo: "
                        f"{total} > {container.max_weight}",
                        container_id=container_id,
                    )
                )
        return violations

    def _check_unpacked(
        self,
        packed_items: list[PackedItem],
        item_by_id: dict[str, Item],
        expected_unpacked_ids: list[str],
    ) -> list[Violation]:
        packed_ids = {p.item_id for p in packed_items}
        reported_unpacked = set(expected_unpacked_ids)
        all_ids = set(item_by_id.keys())

        violations: list[Violation] = []

        # Un ítem no puede estar a la vez empacado y reportado como no empacado.
        both = packed_ids & reported_unpacked
        for item_id in sorted(both):
            violations.append(
                make_violation(
                    ViolationType.UNPACKED_MISMATCH,
                    f"El ítem {item_id} está empacado y también reportado como "
                    f"no empacado",
                    item_ids=[item_id],
                )
            )

        # Todo ítem de la instancia debe estar empacado o reportado no empacado.
        missing = all_ids - packed_ids - reported_unpacked
        for item_id in sorted(missing):
            violations.append(
                make_violation(
                    ViolationType.UNPACKED_MISMATCH,
                    f"El ítem {item_id} no está empacado ni reportado como no "
                    f"empacado",
                    item_ids=[item_id],
                )
            )
        return violations

    def _check_basic_stability(
        self,
        packed_items: list[PackedItem],
        item_by_id: dict[str, Item],
    ) -> list[Violation]:
        violations: list[Violation] = []
        by_container: dict[str, list[PackedItem]] = defaultdict(list)
        for p in packed_items:
            by_container[p.container_id].append(p)

        for container_id, group in by_container.items():
            boxes = [_to_aabb(p) for p in group]
            for idx, p in enumerate(group):
                target = boxes[idx]
                supports = [b for k, b in enumerate(boxes) if k != idx]
                ratio = supported_area_ratio(target, supports)
                if ratio + 1e-9 < self.support_surface_ratio:
                    violations.append(
                        make_violation(
                            ViolationType.SUPPORT_SURFACE,
                            f"El ítem {p.item_id} tiene soporte insuficiente "
                            f"({ratio:.2f} < {self.support_surface_ratio:.2f})",
                            container_id=container_id,
                            item_ids=[p.item_id],
                            severity="warning",  # No invalida la solución.
                        )
                    )
        return violations


def _to_aabb(packed: PackedItem) -> AABB:
    """Convierte un ítem empacado en una caja AABB para cálculos geométricos."""

    return AABB(
        position=Position(packed.position.x, packed.position.y, packed.position.z),
        dimensions=Dimensions(
            packed.orientation.length,
            packed.orientation.width,
            packed.orientation.height,
        ),
    )
