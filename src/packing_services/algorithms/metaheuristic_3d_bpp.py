"""Metaheurísticas 3D-BPP implementadas.

Optimizan el orden de colocación de ítems (permutación) decodificado mediante un
constructivo base configurable. Aplican a ``3D_BPP``; no son el enfoque típico
para cartonization, palletization ni stacking-aware.
"""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ._metaheuristic_core import run_metaheuristic_algorithm
from ._metaheuristic_searches import (
    run_aco,
    run_genetic_algorithm,
    run_grasp,
    run_lns,
    run_simulated_annealing,
    run_tabu_search,
    run_vns,
)
from .base import PackingAlgorithm
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

_META_CONSTRAINTS = [
    Constraint.CONTAINMENT,
    Constraint.NON_OVERLAP,
    Constraint.MAX_WEIGHT,
    Constraint.ORIENTATION,
]
_META_UNSUPPORTED = [
    Constraint.FRAGILITY,
    Constraint.CENTER_OF_GRAVITY,
    Constraint.LOAD_BEARING,
    Constraint.UNLOADING_SEQUENCE,
    Constraint.ADVANCED_STABILITY,
    Constraint.BASIC_STABILITY,
]
_BASE_PARAMS = {
    "random_seed": "Semilla aleatoria para reproducibilidad",
    "time_limit_seconds": "Tiempo máximo de ejecución",
    "iterations": "Número máximo de iteraciones",
    "base_algorithm": "Constructivo de decodificación (por defecto best_fit_decreasing_3d)",
}


def _meta_metadata(
    name: str,
    display_name: str,
    description: str,
    extra_params: dict[str, str] | None = None,
) -> AlgorithmMetadata:
    return AlgorithmMetadata(
        name=name,
        display_name=display_name,
        problem_types=[ProblemType.THREE_D_BPP],
        algorithm_family=AlgorithmFamily.METAHEURISTIC,
        status=AlgorithmStatus.IMPLEMENTED,
        description=description,
        deterministic=False,
        supports_random_seed=True,
        supports_time_limit=True,
        supports_rotation=True,
        supports_multi_container=True,
        supported_constraints=_META_CONSTRAINTS,
        unsupported_constraints=_META_UNSUPPORTED,
        parameters={**_BASE_PARAMS, **(extra_params or {})},
        metrics=DEFAULT_METRICS,
        limitations=[
            "Metaheurística estocástica; no garantiza optimalidad",
            "Optimiza el orden de colocación decodificado por un constructivo base",
            "El tiempo de ejecución crece con iteraciones y tamaño de instancia",
        ],
    )


class SimulatedAnnealing3DBPP(PackingAlgorithm):
    metadata = _meta_metadata(
        "simulated_annealing_3d_bpp",
        "Simulated Annealing 3D-BPP",
        "Recocido simulado sobre permutaciones del orden de colocación.",
        {
            "initial_temperature": "Temperatura inicial del recocido",
            "cooling_rate": "Factor de enfriamiento por iteración (0-1)",
        },
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return run_metaheuristic_algorithm(self.metadata, problem, run_simulated_annealing)


class GeneticAlgorithm3DBPP(PackingAlgorithm):
    metadata = _meta_metadata(
        "genetic_algorithm_3d_bpp",
        "Genetic Algorithm 3D-BPP",
        "Algoritmo genético con cruce OX y mutación por intercambio.",
        {
            "population_size": "Tamaño de la población",
            "mutation_rate": "Probabilidad de mutación por descendiente",
            "crossover_rate": "Probabilidad de cruce entre padres",
        },
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return run_metaheuristic_algorithm(self.metadata, problem, run_genetic_algorithm)


class Grasp3DBPP(PackingAlgorithm):
    metadata = _meta_metadata(
        "grasp_3d_bpp",
        "GRASP 3D-BPP",
        "Construcción aleatorizada con lista restringida de candidatos + mejora local.",
        {
            "alpha": "Grado de aleatoriedad en la RCL (0=greedy, 1=aleatorio)",
            "local_search_steps": "Pasos de mejora local tras cada construcción",
        },
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return run_metaheuristic_algorithm(self.metadata, problem, run_grasp)


class TabuSearch3DBPP(PackingAlgorithm):
    metadata = _meta_metadata(
        "tabu_search_3d_bpp",
        "Tabu Search 3D-BPP",
        "Búsqueda tabú por intercambios en el orden de colocación.",
        {"tabu_tenure": "Duración tabú de movimientos recientes"},
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return run_metaheuristic_algorithm(self.metadata, problem, run_tabu_search)


class Lns3DBPP(PackingAlgorithm):
    metadata = _meta_metadata(
        "lns_3d_bpp",
        "Large Neighborhood Search 3D-BPP",
        "Destruye y reconstruye subconjuntos del orden de colocación.",
        {"destroy_fraction": "Fracción de ítems removidos por iteración"},
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return run_metaheuristic_algorithm(self.metadata, problem, run_lns)


class Vns3DBPP(PackingAlgorithm):
    metadata = _meta_metadata(
        "vns_3d_bpp",
        "Variable Neighborhood Search 3D-BPP",
        "Explora vecindarios crecientes con shake + mejora local.",
        {
            "max_neighborhood": "Número máximo de estructuras de vecindario",
            "shake_intensity": "Intensidad del shake por vecindario",
        },
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return run_metaheuristic_algorithm(self.metadata, problem, run_vns)


class Aco3DBPP(PackingAlgorithm):
    metadata = _meta_metadata(
        "aco_3d_bpp",
        "Ant Colony Optimization 3D-BPP",
        "Colonia de hormigas sobre precedencias en el orden de colocación.",
        {
            "ants_count": "Hormigas por iteración",
            "evaporation": "Tasa de evaporación de feromonas",
            "alpha_pheromone": "Peso de feromonas",
            "beta_heuristic": "Peso de heurística (volumen)",
        },
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return run_metaheuristic_algorithm(self.metadata, problem, run_aco)


METAHEURISTIC_ALGORITHMS: list[PackingAlgorithm] = [
    SimulatedAnnealing3DBPP(),
    GeneticAlgorithm3DBPP(),
    Grasp3DBPP(),
    TabuSearch3DBPP(),
    Lns3DBPP(),
    Vns3DBPP(),
    Aco3DBPP(),
]
