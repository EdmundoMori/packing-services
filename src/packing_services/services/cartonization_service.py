"""Cartonization / Order Packing Service.

Selecciona la mejor caja del catálogo para un pedido usando los algoritmos de
cartonization del registro. Devuelve la caja elegida, el layout, las métricas y
un resumen de la evaluación de todas las cajas candidatas.
"""

from __future__ import annotations

from ..algorithms.cartonization import _evaluate_boxes  # noqa: PLC2701 (uso interno)
from ..algorithms.heuristic_3d_bpp import _resolve_sort_strategy
from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..schemas.requests import CartonizationRequest
from ..schemas.responses import CartonizationResponse
from ..utils.logging import get_logger

logger = get_logger(__name__)


class CartonizationService:
    """Orquesta la selección de caja para un pedido."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()

    def cartonize(self, request: CartonizationRequest) -> CartonizationResponse:
        problem = request.to_problem()
        algorithm_name = problem.algorithm.name
        logger.info(
            "cartonization request_id=%s algorithm=%s items=%d boxes=%d",
            problem.request_id,
            algorithm_name,
            len(problem.items),
            len(problem.containers),
        )

        solution = self.registry.execute(algorithm_name, problem)

        # La caja elegida es el contenedor donde se colocaron los ítems.
        selected_box_id = (
            solution.packed_items[0].container_id if solution.packed_items else None
        )

        return CartonizationResponse(
            request_id=request.request_id,
            status=solution.status.value,
            selected_box_id=selected_box_id,
            algorithm_name=algorithm_name,
            solution=solution,
            evaluated_boxes=self._evaluation_summary(problem),
        )

    def _evaluation_summary(self, problem) -> list[dict]:
        """Resumen por caja candidata (para explicar la decisión)."""

        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
        )
        summary = []
        for box, packed, unpacked, fits_all in _evaluate_boxes(problem, sort_strategy):
            packed_volume = sum(
                p.orientation.length * p.orientation.width * p.orientation.height
                for p in packed
            )
            summary.append(
                {
                    "box_id": box.id,
                    "box_volume": round(box.volume, 6),
                    "fits_all": fits_all,
                    "items_packed": len(packed),
                    "items_unpacked": len(unpacked),
                    "volume_utilization": round(packed_volume / box.volume, 6)
                    if box.volume > 0
                    else 0.0,
                }
            )
        return summary
