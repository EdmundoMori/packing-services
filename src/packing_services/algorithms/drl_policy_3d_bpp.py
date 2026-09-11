"""Algoritmo ``drl_policy_3d_bpp`` — política aprendida sobre el bucle online.

Misma geometría, máscara y presupuesto p/s que ``online_3d_bpp_heuristic``.
La diferencia es la política: puntúa candidatas legales con un checkpoint
``packing-services-online-policy``.

El execute API rellena ``parameters.model_path`` con el MLP de producción
(p=1, s=1) si el cliente no envía ruta. ``run()`` directo sigue exigiendo
``model_path``; sin ruta no hay fallback silencioso al greedy.
No modifica algoritmos offline. No llama a un solver offline en inferencia.
"""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ..utils.errors import InvalidInputError
from ..utils.timing import measure_time
from .base import PackingAlgorithm, build_solution
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="drl_policy_3d_bpp",
    display_name="Deep Reinforcement Learning Policy",
    problem_types=[
        ProblemType.THREE_D_BPP,
        ProblemType.CONTAINER_LOADING,
        ProblemType.SINGLE_CONTAINER_LOADING,
        ProblemType.PALLETIZATION,
        ProblemType.STACKING_AWARE,
    ],
    algorithm_family=AlgorithmFamily.MACHINE_LEARNING,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Default de producción: mlp_v1_p1s1.pt (p=1, s=1). Cinta: "
        "mlp_v1_p3s2.pt (p=3, s=2). Linear: linear_v1.json. Política "
        "aprendida sobre el bucle online (candidatas legales EP + validador). "
        "El placeholder examples/online_policy_linear_v1.json es solo smoke."
    ),
    deterministic=True,
    supports_random_seed=False,
    supports_time_limit=False,
    supports_rotation=True,
    supports_multi_container=True,
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
        Constraint.MAX_WEIGHT,
        Constraint.ORIENTATION,
        Constraint.BASIC_STABILITY,
        Constraint.LOAD_BEARING,
    ],
    unsupported_constraints=[
        Constraint.FRAGILITY,
        Constraint.CENTER_OF_GRAVITY,
        Constraint.UNLOADING_SEQUENCE,
        Constraint.ADVANCED_STABILITY,
    ],
    parameters={
        "model_path": (
            "Ruta al checkpoint (JSON linear o torch mlp_v1). "
            "Default de API: mlp_v1_p1s1.pt. Vacío no ejecuta."
        ),
        "sort_strategy": "Siempre input_order (orden de llegada).",
        "lookahead_p": "Ítems próximos visibles (entero ≥ 1, default 1)",
        "select_s": "Buffer de selección (entero ≥ 1, default 1)",
        "selection": "Generador de candidatas: best_fit | blb (default best_fit)",
        "min_support_ratio": "Soporte mínimo si basic_stability (float, default 0.6)",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Sin model_path no ejecuta (no hay fallback silencioso al greedy)",
        "Los .pt requieren pip install 'packing-services[torch]'",
        "Pesos de otros repos (PCT/GOPT) no se cargan tal cual",
        "Colocaciones irrevocables; no reordena fuera de select_s",
    ],
)


class DRLPolicy3DBPP(PackingAlgorithm):
    """Execute de política aprendida: carga ``model_path`` y corre el bucle."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        from ..online.budget import InformationBudget
        from ..online.learned.policy import LearnedPlacementPolicy
        from ..online.loop import run_online_loop
        from ..online.params import resolve_selection, support_threshold

        params = problem.algorithm.parameters
        model_path = params.get("model_path") or params.get("weights_path")
        if not model_path:
            raise InvalidInputError(
                "drl_policy_3d_bpp requiere parameters.model_path "
                "(checkpoint packing-services-online-policy)."
            )
        policy = LearnedPlacementPolicy.from_path(model_path)
        budget = InformationBudget.from_parameters(params)
        selection = resolve_selection(params)
        min_support = support_threshold(params, problem.constraints.basic_stability)

        with measure_time() as elapsed:
            packed, unpacked = run_online_loop(
                problem,
                budget=budget,
                selection=selection,
                min_support_ratio=min_support,
                policy=policy,
            )

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
