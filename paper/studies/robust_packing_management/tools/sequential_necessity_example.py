#!/usr/bin/env python3
"""Enumeración sintética: ¿una regla local de protección puede ser insuficiente?

≤3 ítems, soporte finito de ε, expectativas exactas (no Monte Carlo), ≤60 s.
El sufijo NO entra en la política local; el ítem-2 solo aparece en el análisis
bajo un supuesto adicional de llegada.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import product
from typing import Iterable

# --- AABB mínimo ---


@dataclass(frozen=True)
class Box:
    flb: tuple[float, float, float]
    dims: tuple[float, float, float]

    @property
    def hi(self) -> tuple[float, float, float]:
        return (
            self.flb[0] + self.dims[0],
            self.flb[1] + self.dims[1],
            self.flb[2] + self.dims[2],
        )


def outside(box: Box, container: tuple[float, float, float], eps: float = 1e-9) -> bool:
    if any(a < -eps for a in box.flb):
        return True
    return any(h > c + eps for h, c in zip(box.hi, container))


def overlap(a: Box, b: Box, eps: float = 1e-9) -> bool:
    ox = min(a.hi[0], b.hi[0]) - max(a.flb[0], b.flb[0])
    oy = min(a.hi[1], b.hi[1]) - max(a.flb[1], b.flb[1])
    oz = min(a.hi[2], b.hi[2]) - max(a.flb[2], b.flb[2])
    return ox > eps and oy > eps and oz > eps


def geom_fail(box: Box, container: tuple[float, float, float], occupied: Iterable[Box]) -> bool:
    if outside(box, container):
        return True
    return any(overlap(box, o) for o in occupied)


# --- Error discreto (sensibilidad sintética; no calibración) ---
# Mismo ε en los tres ejes (dependencia perfecta entre ejes).
EPS_VALUES = (0.0, 0.25)
EPS_PROBS = (0.5, 0.5)

CONTAINER = (10.0, 8.0, 5.0)
N1 = (6.0, 5.0, 2.0)
# Ítem-2: cabe en banda +Y tras colocación LEFT; tras RIGHT solapa en X si y≥5.
N2 = (4.01, 1.5, 2.0)

M0 = (0.0, 0.0, 0.0)
MG = tuple(0.25 * n for n in N1)  # envelope = N(1+0.25) = soporte máx.

# Poses candidatas sintéticas (chooser finito, no EP industrial).
# FLB_RIGHT empuja hacia +X: con m=0 cabe el nominal, pero R grande sale.
# FLB_LEFT en el origen: admite envelope garantista.
FLB_RIGHT = (4.0, 0.0, 0.0)
FLB_LEFT = (0.0, 0.0, 0.0)


def realize(nominal: tuple[float, float, float], eps: float) -> tuple[float, float, float]:
    return tuple(max(1.0, n * (1.0 + eps)) for n in nominal)


def envelope(nominal: tuple[float, float, float], margin: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(n + m for n, m in zip(nominal, margin))


def candidates_for_margin(margin: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    env = envelope(N1, margin)
    return [flb for flb in (FLB_RIGHT, FLB_LEFT) if not geom_fail(Box(flb, env), CONTAINER, [])]


def choose_flb(margin: tuple[float, float, float]) -> tuple[float, float, float] | None:
    """Chooser sintético fijo: maximiza x (empaca a la derecha), luego min y,z."""
    cands = candidates_for_margin(margin)
    if not cands:
        return None
    return sorted(cands, key=lambda p: (-p[0], p[1], p[2]))[0]


def immediate_failure_prob(margin: tuple[float, float, float], flb: tuple[float, float, float]) -> float:
    p_fail = 0.0
    for eps, p in zip(EPS_VALUES, EPS_PROBS):
        if geom_fail(Box(flb, realize(N1, eps)), CONTAINER, []):
            p_fail += p
    return p_fail


def place_item1(margin: tuple[float, float, float], eps1: float) -> tuple[str, Box | None]:
    flb = choose_flb(margin)
    if flb is None:
        return "no_candidate", None
    r = realize(N1, eps1)
    if geom_fail(Box(flb, r), CONTAINER, []):
        return "geometric_failure", None
    return "ok", Box(flb, r)


def place_item2(occupied: list[Box], eps2: float) -> str:
    """Chooser fijo ítem-2: candidatas finitas; no forma parte de la política de m del ítem-1."""
    r = realize(N2, eps2)
    for flb in (
        (0.0, 5.0, 0.0),
        (0.0, 6.25, 0.0),
        (0.0, 6.5, 0.0),
        (6.0, 0.0, 0.0),
        (5.5, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (2.0, 5.0, 0.0),
    ):
        if not geom_fail(Box(flb, r), CONTAINER, occupied):
            return "ok"
    return "geometric_failure"


def episode_JB(margin: tuple[float, float, float], eps1: float, eps2: float) -> float:
    vol_c = CONTAINER[0] * CONTAINER[1] * CONTAINER[2]
    st, box1 = place_item1(margin, eps1)
    if st != "ok" or box1 is None:
        return 0.0  # geometric_failure o no_candidate sin colocaciones previas
    v = N1[0] * N1[1] * N1[2]
    if place_item2([box1], eps2) == "geometric_failure":
        return 0.0
    v += N2[0] * N2[1] * N2[2]
    return v / vol_c


def expected_JB(margin: tuple[float, float, float]) -> float:
    return sum(
        p1 * p2 * episode_JB(margin, e1, e2)
        for (e1, p1), (e2, p2) in product(zip(EPS_VALUES, EPS_PROBS), repeat=2)
    )


def local_rule(rho_max: float = 0.5) -> tuple[float, float, float]:
    """Referencia local (sin sufijo / sin modelo de llegadas):
    admisible si existe pose y Pr_imm ≤ rho_max; minimizar sum(m);
    desempate: pose con mayor x (mismo criterio del chooser).
    """
    best = None
    best_key = None
    for m in (M0, MG):
        flb = choose_flb(m)
        if flb is None:
            continue
        rho = immediate_failure_prob(m, flb)
        if rho > rho_max + 1e-12:
            continue
        key = (sum(m), -flb[0], flb[1], flb[2])
        if best_key is None or key < best_key:
            best_key = key
            best = m
    if best is None:
        raise RuntimeError("local rule empty")
    return best


def arrival_model_best() -> tuple[tuple[float, float, float], float]:
    """Análisis con supuesto adicional: el siguiente ítem es N2 ~ misma ley ε.
    No es observación de la política local.
    """
    best_m, best_v = None, -1.0
    for m in (M0, MG):
        if choose_flb(m) is None:
            continue
        v = expected_JB(m)
        if v > best_v:
            best_v, best_m = v, m
    assert best_m is not None
    return best_m, best_v


def immediate_expected_utility(margin: tuple[float, float, float]) -> float:
    """U_imm = E[V_nom del ítem-1 / Vol(C)] tras la decisión; 0 si falla o no_candidate."""
    vol_c = CONTAINER[0] * CONTAINER[1] * CONTAINER[2]
    v1 = N1[0] * N1[1] * N1[2]
    u = 0.0
    for eps, p in zip(EPS_VALUES, EPS_PROBS):
        st, _box = place_item1(margin, eps)
        if st == "ok":
            u += p * (v1 / vol_c)
    return u


def prefer_guarantee_if_admissible() -> tuple[float, float, float] | None:
    if choose_flb(MG) is not None:
        return MG
    if choose_flb(M0) is not None:
        return M0
    return None


def max_immediate_expected_utility_rule() -> tuple[float, float, float]:
    best = None
    best_key = None
    for m in (M0, MG):
        if choose_flb(m) is None:
            continue
        key = (-immediate_expected_utility(m), sum(m))
        if best_key is None or key < best_key:
            best_key = key
            best = m
    assert best is not None
    return best


def compare_analytical_baselines() -> dict:
    """Comparación por la misma enumeración (sin nuevas simulaciones)."""
    rows = {}
    for name, m in (
        ("local_L_rho_star_0.5_min_margin", local_rule(0.5)),
        ("prefer_guarantee_if_admissible", prefer_guarantee_if_admissible()),
        ("max_immediate_expected_utility", max_immediate_expected_utility_rule()),
        ("limited_search_E_JB_declared_N2", arrival_model_best()[0]),
    ):
        assert m is not None
        flb = choose_flb(m)
        rows[name] = {
            "margin": m,
            "flb": flb,
            "rho_imm": immediate_failure_prob(m, flb) if flb else None,
            "U_imm": immediate_expected_utility(m),
            "E_JB": expected_JB(m),
        }
    # ¿La “ventaja” secuencial desaparece frente a baselines analíticas fuertes?
    strong = {
        k: rows[k]["E_JB"]
        for k in (
            "prefer_guarantee_if_admissible",
            "max_immediate_expected_utility",
            "limited_search_E_JB_declared_N2",
        )
    }
    rows["meta"] = {
        "rho_star_of_L": 0.5,
        "L_accepts_half_failure_then_min_margin": True,
        "strong_baselines_agree_on_MG": all(
            rows[k]["margin"] == MG for k in strong
        ),
        "residual_of_strong_baselines_vs_menu_opt": 0.0,
        "chooser_is_synthetic_not_EP_engine": True,
        "not_evidence_about_production_EP_motor": True,
    }
    return rows


def run_check(time_limit_s: float = 60.0) -> dict:
    t0 = time.perf_counter()
    flb0, flbg = choose_flb(M0), choose_flb(MG)
    rho0 = immediate_failure_prob(M0, flb0) if flb0 else None
    rhog = immediate_failure_prob(MG, flbg) if flbg else None
    ej0, ejg = expected_JB(M0), expected_JB(MG)
    local_m = local_rule(0.5)
    oracle_m, oracle_ej = arrival_model_best()
    elapsed = time.perf_counter() - t0

    two_actions = flb0 is not None and flbg is not None and flb0 != flbg
    futures_differ = abs(ej0 - ejg) > 1e-12
    local_insufficient = local_m != oracle_m and expected_JB(local_m) + 1e-12 < oracle_ej

    return {
        "elapsed_s": elapsed,
        "within_60s": elapsed <= time_limit_s,
        "container": CONTAINER,
        "N1": N1,
        "N2_arrival_assumption_only": N2,
        "eps_support": list(EPS_VALUES),
        "eps_probs": list(EPS_PROBS),
        "axis_dependence": "same_eps_all_axes_within_item",
        "independence_across_items": True,
        "menu": {"M0": M0, "MG": MG},
        "candidates_M0": candidates_for_margin(M0),
        "candidates_MG": candidates_for_margin(MG),
        "chosen_flb_M0": flb0,
        "chosen_flb_MG": flbg,
        "rho_imm_M0": rho0,
        "rho_imm_MG": rhog,
        "E_JB_M0": ej0,
        "E_JB_MG": ejg,
        "local_rule_margin": local_m,
        "local_rule_flb": choose_flb(local_m),
        "local_rule_E_JB": expected_JB(local_m),
        "local_rule_rho_max": 0.5,
        "oracle_under_arrival_model_margin": oracle_m,
        "oracle_under_arrival_model_flb": choose_flb(oracle_m),
        "oracle_under_arrival_model_E_JB": oracle_ej,
        "checks": {
            "two_admissible_actions_different_layout": two_actions,
            "immediate_risk_known": rho0 is not None and rhog is not None,
            "future_consequences_differ": futures_differ,
            "local_rule_insufficient_vs_arrival_oracle": local_insufficient,
        },
        "nontrivial_example_found": bool(
            two_actions and rho0 is not None and rhog is not None and futures_differ and local_insufficient
        ),
        "baseline_comparison": compare_analytical_baselines(),
        "interpretation": (
            "nontrivial_example_found solo indica insuficiencia de L con rho_star=0.5 "
            "(acepta riesgo 0.5 y minimiza margen). prefer_guarantee / max U_imm / "
            "búsqueda limitada eligen MG y empatan el óptimo del menú: no hay residual "
            "que justifique RL. Chooser sintético (max x), no el motor EP de producción."
        ),
        "limits": [
            "No evidencia industrial, frecuencia BED-BPP ni novedad.",
            "Ítem-2 solo en el análisis (supuesto de llegada); no en la política local.",
            "Comparación vs L débil no implica residual vs reglas analíticas fuertes.",
            "Calcular m_g es directo; optimizar packing seguro futuro no queda resuelto "
            "en general solo por conocer m_g — pero este juguete no muestra residual "
            "tras preferir m_g admisible.",
            "Política óptima del menú puede ser determinista.",
        ],
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_check(), indent=2))
