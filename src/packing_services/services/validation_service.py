"""Packing Validation Service: valida soluciones de cualquier motor."""

from __future__ import annotations

from ..domain.models import UnpackedItem
from ..metrics.metrics import compute_metrics
from ..schemas.requests import ValidateRequest
from ..schemas.responses import ValidateResponse
from ..validation.validator import PackingValidator


class ValidationService:
    """Valida una solución y recalcula sus métricas de forma independiente."""

    def __init__(self, validator: PackingValidator | None = None) -> None:
        self.validator = validator or PackingValidator()

    def validate(self, request: ValidateRequest) -> ValidateResponse:
        items = request.expanded_items()

        report = self.validator.validate(
            containers=request.containers,
            items=items,
            packed_items=request.packed_items,
            constraints=request.constraints,
        )

        # Todo ítem de la instancia que no aparezca empacado se considera no
        # empacado a efectos de recalcular métricas.
        packed_ids = {p.item_id for p in request.packed_items}
        unpacked_items = [
            UnpackedItem(item_id=it.id) for it in items if it.id not in packed_ids
        ]

        metrics = compute_metrics(
            containers=request.containers,
            items=items,
            packed_items=request.packed_items,
            unpacked_items=unpacked_items,
            constraint_violations=report.error_count,
        )

        return ValidateResponse(
            request_id=request.request_id,
            validation_report=report,
            recomputed_metrics=metrics,
        )
