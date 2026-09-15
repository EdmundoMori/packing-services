"""Algoritmo ``online_3d_bpp_heuristic`` — packing online con presupuesto p/s.

Los ítems se consideran en orden de llegada (``arrival_index`` / input). No se
reordena el resto del pedido. En cada paso se elige entre los primeros ``s``
de la cola, viendo una ventana de ``p`` ítems, se filtran candidatas legales
(puntos extremos + validador) y se compromete una colocación irrevocable.

``lookahead_p=1``, ``select_s=1`` es O3DBP estricto. ``p=3``, ``s=2`` es el
régimen típico de cinta / leaderboard BED-BPP. El mismo bucle sirve para
palletization, container loading y 3D-BPP.

No modifica algoritmos offline. No garantiza optimalidad.
"""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ..utils.timing import measure_time
from .base import PackingAlgorithm, build_solution
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="online_3d_bpp_heuristic",
    display_name="Online 3D-BPP Heuristic",
    problem_types=[
        ProblemType.THREE_D_BPP,
        ProblemType.CONTAINER_LOADING,
        ProblemType.SINGLE_CONTAINER_LOADING,
        ProblemType.PALLETIZATION,
        ProblemType.STACKING_AWARE,
    ],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Packing online generalizable: respeta arrival_index, no reordena, y "
        "coloca de forma irrevocable con presupuesto de información "
        "(lookahead_p / select_s). Candidatas por puntos extremos, máscara del "
        "validador propio y política greedy (best-fit o bottom-left-back)."
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
        "sort_strategy": "Siempre input_order (orden de llegada). Ignora otros valores.",
        "lookahead_p": "Ítems próximos visibles para la política (entero ≥ 1, default 1)",
        "select_s": "Ítems al frente de la cola entre los que se puede elegir (entero ≥ 1, default 1)",
        "selection": "Criterio de encaje: best_fit | blb (default best_fit)",
        "min_support_ratio": "Soporte mínimo si basic_stability (float, default 0.6)",
        "consolidate": (
            "Disciplina first-fit multi-pallet. Default: true si hay más de un "
            "contenedor. false restaura el reparto libre (defecto de Fase 1)."
        ),
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Colocaciones irrevocables; no reordena fuera del buffer select_s",
        "Heurístico; no garantiza optimalidad",
        "Candidatas = variante simplificada de Extreme Points (proyección vertical)",
        "Sin centro de gravedad ni estabilidad avanzada",
    ],
)


class Online3DBPPHeuristic(PackingAlgorithm):
    """Heurístico online ejecutable (O3DBP-p-s sobre el bucle general)."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        from ..online.budget import InformationBudget
        from ..online.loop import run_online_loop
        from ..online.params import (
            maybe_wrap_consolidating,
            resolve_selection,
            support_threshold,
        )
        from ..online.policies import GreedyBestFitPolicy

        params = problem.algorithm.parameters
        budget = InformationBudget.from_parameters(params)
        selection = resolve_selection(params)
        min_support = support_threshold(params, problem.constraints.basic_stability)
        policy = maybe_wrap_consolidating(GreedyBestFitPolicy(), problem, params)

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
