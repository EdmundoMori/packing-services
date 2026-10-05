"""Métodos M0–M3 congelados (misma información pública)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from adapters import PolicySessionView
from episode import fixed_rank_chooser
from error_model import (
    PublicErrorModel,
    axis_margin_from_nominal,
    uniform_margin_mm,
)
from geometry_contract import AxisTriple, validate_margin
from info_separation import PolicyObservation

MethodFn = Callable[[PolicyObservation, PolicySessionView], tuple[AxisTriple, Any]]


@dataclass(frozen=True)
class MethodSpec:
    method_id: str
    description: str
    comparison_kind: str  # "method" | "protection_level_within_scenario"


def m0_nominal(obs: PolicyObservation, view: PolicySessionView):
    margin = AxisTriple(0.0, 0.0, 0.0)
    obs_m = _with_margin(obs, margin)
    return margin, fixed_rank_chooser(obs_m, view)


def m1_uniform(model: PublicErrorModel):
    base = uniform_margin_mm(model)

    def _fn(obs: PolicyObservation, view: PolicySessionView):
        margin = validate_margin(base.as_tuple(), "m1")
        obs_m = _with_margin(obs, margin)
        return margin, fixed_rank_chooser(obs_m, view)

    return _fn


def m2_axis_from_public(model: PublicErrorModel):
    def _fn(obs: PolicyObservation, view: PolicySessionView):
        margin = axis_margin_from_nominal(obs.current_nominal_mm, model.alpha)
        margin = validate_margin(margin.as_tuple(), "m2")
        obs_m = _with_margin(obs, margin)
        return margin, fixed_rank_chooser(obs_m, view)

    return _fn


def m3_local_analytical(model: PublicErrorModel):
    """Selección local: menú {0, uniforme, eje}; elige el m con candidatas y mejor rank.

    Riesgo inmediato (modelo determinista de sensibilidad): 0 si existe candidata
    bajo m, 1 si no. Desempate: menor volumen de envolvente media proxy vía
    suma de márgenes, luego rank_key del mejor cand.
    """

    menu_builders = [
        ("m0", lambda obs: AxisTriple(0.0, 0.0, 0.0)),
        ("m1", lambda obs: uniform_margin_mm(model)),
        ("m2", lambda obs: axis_margin_from_nominal(obs.current_nominal_mm, model.alpha)),
    ]

    def _fn(obs: PolicyObservation, view: PolicySessionView):
        best = None
        best_key = None
        best_margin = None
        best_choice = None
        for _name, builder in menu_builders:
            margin = validate_margin(builder(obs).as_tuple(), "m3_menu")
            obs_m = _with_margin(obs, margin)
            cands = view.list_envelope_candidates(obs_m)
            if not cands:
                key = (1, 1e18, (1e18,))
                choice = None
            else:
                choice = cands[0]
                margin_sum = sum(margin.as_tuple())
                key = (0, margin_sum, choice.rank_key)
            if best_key is None or key < best_key:
                best_key = key
                best_margin = margin
                best_choice = choice
                best = _name
        assert best_margin is not None
        # Si ningún m tiene candidata, devolver margen m2 y choice None → no_candidate
        if best_choice is None:
            return best_margin, None
        return best_margin, best_choice

    return _fn


def _with_margin(obs: PolicyObservation, margin: AxisTriple) -> PolicyObservation:
    return PolicyObservation(
        container_mm=obs.container_mm,
        current_item_id=obs.current_item_id,
        current_nominal_mm=obs.current_nominal_mm,
        margin_mm=margin,
        revealed=obs.revealed,
        remaining_count_including_current=obs.remaining_count_including_current,
    )


def build_methods(model: PublicErrorModel) -> dict[str, MethodFn]:
    return {
        "M0": m0_nominal,
        "M1": m1_uniform(model),
        "M2": m2_axis_from_public(model),
        "M3": m3_local_analytical(model),
    }


METHOD_SPECS = {
    "M0": MethodSpec("M0", "nominal sin protección m=(0,0,0); chooser rank_key", "method"),
    "M1": MethodSpec(
        "M1",
        "margen uniforme (u,u,u) con u=uniform_ref_mm del escenario; chooser rank_key",
        "protection_level_within_scenario",
    ),
    "M2": MethodSpec(
        "M2",
        "margen por eje alpha*nominal_axis del modelo público; chooser rank_key",
        "method",
    ),
    "M3": MethodSpec(
        "M3",
        "selección local analítica sobre menú {0, uniforme, eje}; risk 0/1 por factibilidad",
        "method",
    ),
}
