"""Contabilidad de presupuesto de etiquetado entre intentos.

Regla documentada (no reinicia al crear un proceso nuevo):

  accounted_for_deadline =
      max(registered_order_walls_attempt01, launcher_span_attempt01)
      + operational_reserve_120s
      + max(registered_order_walls_attempt02_new_orders, launcher_span_attempt02)

Justificación del max en intento 02: registered_02 y span_02 miden el mismo
trabajo sucesivo (pedidos nuevos). Usar solo la suma de fases cuando es menor
que el span subestimaría deliberadamente el tiempo ya consumido. Se toma el
máximo; no se suman ambos (evitar doble conteo).

Los spans son aproximaciones entre mtimes de artefactos, no tiempos exactos
de pared recuperados del proceso. No se presentan como medidas exactas.

Preflight 35.121554053999716 s permanece separado y ya contabilizado una vez.
No amplía el cupo 13500 s ni el total global 28800 s.
"""

from __future__ import annotations

from typing import Any

PUBLISHED_PREFLIGHT_WALL_SECONDS = 35.121554053999716
LABELING_WALL_BUDGET_SECONDS = 13500.0

# Intento 01
REGISTERED_ORDER_WALL_SUM_ATTEMPT01 = 214.80055754699697
LAUNCHER_ARTIFACT_SPAN_ATTEMPT01 = 216.745745165
OPERATIONAL_RESERVE_SECONDS = 120.0

# Intento 02 (pedidos nuevos; no incluye referenciados del 01)
REGISTERED_NEW_ORDER_WALL_SUM_ATTEMPT02 = 1108.0330003329998
LAUNCHER_ARTIFACT_SPAN_ATTEMPT02 = 1115.8956439495087


def budget_ledger() -> dict[str, Any]:
    base01 = max(REGISTERED_ORDER_WALL_SUM_ATTEMPT01, LAUNCHER_ARTIFACT_SPAN_ATTEMPT01)
    prior_before_02 = base01 + OPERATIONAL_RESERVE_SECONDS
    base02 = max(REGISTERED_NEW_ORDER_WALL_SUM_ATTEMPT02, LAUNCHER_ARTIFACT_SPAN_ATTEMPT02)
    accounted = prior_before_02 + base02
    remaining = LABELING_WALL_BUDGET_SECONDS - accounted
    return {
        "labeling_wall_budget_seconds": LABELING_WALL_BUDGET_SECONDS,
        "preflight_wall_seconds_separate": PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "preflight_already_accounted_once": True,
        "attempt01": {
            "registered_order_wall_sum_seconds": REGISTERED_ORDER_WALL_SUM_ATTEMPT01,
            "launcher_artifact_span_seconds": LAUNCHER_ARTIFACT_SPAN_ATTEMPT01,
            "spans_are_approximate": True,
            "spans_not_exact_wall_clock": True,
            "operational_reserve_seconds": OPERATIONAL_RESERVE_SECONDS,
            "accounted_component_seconds": prior_before_02,
        },
        "attempt02": {
            "registered_new_order_wall_sum_seconds": REGISTERED_NEW_ORDER_WALL_SUM_ATTEMPT02,
            "launcher_artifact_span_seconds": LAUNCHER_ARTIFACT_SPAN_ATTEMPT02,
            "spans_are_approximate": True,
            "spans_not_exact_wall_clock": True,
            "accounted_component_seconds": base02,
            "rule_component": "max(registered_02_new, span_02); no sumar ambos",
            "note": (
                "mismo trabajo sucesivo: max evita subestimar frente a span; "
                "no se suma registered+span (doble conteo)"
            ),
        },
        "prior_wall_accounted_for_next_deadline_seconds": accounted,
        "remaining_labeling_wall_seconds": remaining,
        "clock_resets_on_new_process": False,
        "includes_load_capture_audit_write_in_order_walls": True,
        "rule": (
            "accounted = max(reg01, span01) + reserve120 + max(reg02_new, span02); "
            "preflight separate once; no budget expansion; spans approximate only"
        ),
    }
