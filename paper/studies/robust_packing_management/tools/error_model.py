"""Modelo sintético B1 de sensibilidad dimensional (no calibrado en BED-BPP)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from geometry_contract import AxisTriple, validate_positive_dims

# Tres condiciones de sensibilidad (no son tres observaciones i.i.d. de una P empírica).
# Inspiración de orden de magnitud: GOPT buffer 7 mm como ancla de ingeniería para
# el nivel medio; NO se usa el 2 cm del n-gram de BED-BPP.
SCENARIOS: dict[str, dict[str, float]] = {
    "sens_low": {"alpha": 0.02, "uniform_ref_mm": 3.0},
    "sens_mid": {"alpha": 0.05, "uniform_ref_mm": 7.0},
    "sens_high": {"alpha": 0.10, "uniform_ref_mm": 12.0},
}

PREFLIGHT_SCENARIO = "sens_mid"
MODEL_ID = "b1_mult_expand_v1"
MODEL_SEED_NAMESPACE = "rpm-g2-error|v1"


@dataclass(frozen=True)
class PublicErrorModel:
    """Parámetros públicos compartidos por todos los métodos."""

    model_id: str
    scenario_id: str
    alpha: float
    uniform_ref_mm: float
    units: str = "mm"
    family: str = (
        "realized_axis = max(1.0, nominal_axis * (1+alpha)); "
        "alpha fijo por escenario de sensibilidad; independiente entre ítems; "
        "misma realización por ítem entre métodos; orientación permuta el mismo triplete."
    )
    probabilistic_calibration: bool = False
    note: str = (
        "Condiciones de sensibilidad propias, no ley medida sobre BED-BPP. "
        "Una realización por pedido×escenario ⇒ frecuencias observadas, no estimación "
        "fiable de Pr(fallo) ni garantía por 0 fallos."
    )

    @staticmethod
    def for_scenario(scenario_id: str) -> "PublicErrorModel":
        if scenario_id not in SCENARIOS:
            raise KeyError(scenario_id)
        cfg = SCENARIOS[scenario_id]
        return PublicErrorModel(
            model_id=MODEL_ID,
            scenario_id=scenario_id,
            alpha=float(cfg["alpha"]),
            uniform_ref_mm=float(cfg["uniform_ref_mm"]),
        )


def expand_nominal(nominal: AxisTriple, alpha: float) -> AxisTriple:
    return validate_positive_dims(
        (
            max(1.0, nominal.length * (1.0 + alpha)),
            max(1.0, nominal.width * (1.0 + alpha)),
            max(1.0, nominal.height * (1.0 + alpha)),
        ),
        "realized",
    )


def axis_margin_from_nominal(nominal: AxisTriple, alpha: float) -> AxisTriple:
    """M2: holgura por eje = alpha * nominal_axis (mm)."""
    return AxisTriple(
        max(0.0, nominal.length * alpha),
        max(0.0, nominal.width * alpha),
        max(0.0, nominal.height * alpha),
    )


def uniform_margin_mm(model: PublicErrorModel) -> AxisTriple:
    u = model.uniform_ref_mm
    return AxisTriple(u, u, u)


def model_public_dict(model: PublicErrorModel) -> dict:
    return {
        "model_id": model.model_id,
        "scenario_id": model.scenario_id,
        "alpha": model.alpha,
        "uniform_ref_mm": model.uniform_ref_mm,
        "units": model.units,
        "family": model.family,
        "probabilistic_calibration": model.probabilistic_calibration,
        "note": model.note,
        "seed_namespace": MODEL_SEED_NAMESPACE,
        "scenarios_all": SCENARIOS,
        "not_bedbpp_ngram_2cm": True,
    }
