"""Construcción de ejemplos de entrada y contratos API por algoritmo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..algorithms.metadata import AlgorithmMetadata
from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.enums import PackingMode, ProblemType
from ..domain.packing_modes import DEFAULT_PACKING_MODE, apply_mode_to_parameters
from ..schemas.responses import AlgorithmDetailResponse
from ..utils.errors import AlgorithmNotFoundError, InvalidInputError

PACK_INPUT_SCHEMA = "PackAlgorithmInput"
CARTONIZATION_INPUT_SCHEMA = "CartonizationAlgorithmInput"
EXECUTE_OUTPUT_SCHEMA = "AlgorithmExecuteResponse"

_EXAMPLE_FILES: dict[ProblemType, str] = {
    ProblemType.THREE_D_BPP: "algorithm_execute_3d_bpp.json",
    ProblemType.CONTAINER_LOADING: "algorithm_execute_container_loading.json",
    ProblemType.SINGLE_CONTAINER_LOADING: "algorithm_execute_single_container.json",
    ProblemType.CARTONIZATION: "algorithm_execute_cartonization.json",
    ProblemType.PALLETIZATION: "algorithm_execute_palletization.json",
    ProblemType.STACKING_AWARE: "algorithm_execute_stacking_aware.json",
}

_IMPROVEMENT_ALGORITHMS = {
    "solution_compaction": {
        "base_algorithm": "best_fit_decreasing_3d",
        "compaction_passes": 3,
    },
    "constructive_plus_local_search": {
        "base_algorithm": "best_fit_decreasing_3d",
        "compaction_passes": 3,
        "relocation_pass": True,
    },
    "relocation_improvement": {
        "base_algorithm": "best_fit_decreasing_3d",
        "relocation_passes": 2,
        "compaction_passes": 1,
    },
    "swap_improvement": {
        "base_algorithm": "best_fit_decreasing_3d",
        "improvement_passes": 1,
    },
    "orientation_improvement": {
        "base_algorithm": "best_fit_decreasing_3d",
        "improvement_passes": 1,
    },
    "bin_reduction": {
        "base_algorithm": "best_fit_decreasing_3d",
        "improvement_passes": 1,
    },
}

_ALGORITHM_PARAMETERS: dict[str, dict[str, Any]] = {
    "weight_aware_container_loading": {"sort_strategy": "weight_desc"},
    "first_fit_decreasing_3d": {"sort_strategy": "volume_desc"},
    "maximal_spaces_3d": {"sort_strategy": "volume_desc", "selection": "best_fit"},
    "multi_box_cartonization": {
        "sort_strategy": "volume_desc",
        "box_selection": "smallest_first",
    },
    "layer_based_palletization": {"sort_strategy": "volume_desc"},
    "stack_based_palletization": {"sort_strategy": "volume_desc", "min_support_ratio": 0.6},
    "stacking_aware_constructive": {
        "sort_strategy": "weight_desc",
        "min_support_ratio": 0.6,
    },
    "py3dbp_adapter": {
        "bigger_first": True,
        "distribute_items": True,
        "number_of_decimals": 3,
    },
    "heuristic_3d_bpp_v1": {
        "sort_strategy": "volume_desc",
        "position_strategy": "bottom_left_back",
    },
}

# Defaults modestos: suficientes para demos sin saturar CPU/tiempo.
_METAHEURISTIC_DEFAULTS = {
    "base_algorithm": "best_fit_decreasing_3d",
    "iterations": 20,
    "random_seed": 42,
    "time_limit_seconds": 10,
}

for _meta_name in (
    "simulated_annealing_3d_bpp",
    "genetic_algorithm_3d_bpp",
    "grasp_3d_bpp",
    "tabu_search_3d_bpp",
    "lns_3d_bpp",
    "vns_3d_bpp",
    "aco_3d_bpp",
):
    _ALGORITHM_PARAMETERS[_meta_name] = dict(_METAHEURISTIC_DEFAULTS)


class AlgorithmInputService:
    """Resuelve esquemas y ejemplos de entrada por algoritmo."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()
        self._examples_dir = Path(__file__).resolve().parents[3] / "examples"

    @staticmethod
    def execution_endpoint(algorithm_name: str) -> str:
        return f"POST /api/v1/algorithms/{algorithm_name}/execute"

    def pack_compatible_types(self, meta: AlgorithmMetadata) -> list[ProblemType]:
        return [pt for pt in meta.problem_types if pt != ProblemType.CARTONIZATION]

    def supports_cartonization(self, meta: AlgorithmMetadata) -> bool:
        return ProblemType.CARTONIZATION in meta.problem_types

    def input_schema_for(self, meta: AlgorithmMetadata) -> str:
        pack_types = self.pack_compatible_types(meta)
        if self.supports_cartonization(meta) and not pack_types:
            return CARTONIZATION_INPUT_SCHEMA
        return PACK_INPUT_SCHEMA

    def default_problem_type(
        self, meta: AlgorithmMetadata, requested: ProblemType | None = None
    ) -> ProblemType:
        pack_types = self.pack_compatible_types(meta)
        if self.supports_cartonization(meta) and not pack_types:
            return ProblemType.CARTONIZATION
        if requested is not None:
            if requested == ProblemType.CARTONIZATION:
                if not self.supports_cartonization(meta):
                    raise InvalidInputError(
                        f"El algoritmo '{meta.name}' no soporta CARTONIZATION."
                    )
                return requested
            if requested not in pack_types:
                allowed = ", ".join(p.value for p in pack_types)
                raise InvalidInputError(
                    f"problem_type={requested.value} no es compatible con "
                    f"'{meta.name}'. Valores permitidos: {allowed}"
                )
            return requested
        if len(pack_types) == 1:
            return pack_types[0]
        if len(pack_types) > 1:
            raise InvalidInputError(
                f"El algoritmo '{meta.name}' admite varios problem_type. "
                f"Indica uno de: {', '.join(p.value for p in pack_types)}"
            )
        return ProblemType.CARTONIZATION

    def default_parameters(
        self,
        algorithm_name: str,
        packing_mode: PackingMode | None = None,
    ) -> dict[str, Any]:
        """Parámetros opcionales con valores seguros si el cliente no los envía."""
        if algorithm_name in _IMPROVEMENT_ALGORITHMS:
            base = dict(_IMPROVEMENT_ALGORITHMS[algorithm_name])
        else:
            base = dict(
                _ALGORITHM_PARAMETERS.get(algorithm_name, {"sort_strategy": "volume_desc"})
            )
        mode = packing_mode or DEFAULT_PACKING_MODE
        if mode == PackingMode.ONLINE:
            return apply_mode_to_parameters(mode, None, base)
        return base

    def merge_parameters(
        self,
        algorithm_name: str,
        user_parameters: dict[str, Any] | None,
        packing_mode: PackingMode | None = None,
    ) -> dict[str, Any]:
        """Defaults primero; lo enviado por el usuario sobrescribe; el modo puede forzar orden."""
        mode = packing_mode or DEFAULT_PACKING_MODE
        return apply_mode_to_parameters(
            mode,
            user_parameters,
            self.default_parameters(algorithm_name, packing_mode=DEFAULT_PACKING_MODE),
        )

    def enrich_metadata(
        self,
        name: str,
        packing_mode: PackingMode | None = None,
    ) -> AlgorithmDetailResponse:
        if not self.registry.has(name):
            raise AlgorithmNotFoundError(f"Algoritmo no encontrado: {name}")
        meta = self.registry.get_metadata(name)
        mode = packing_mode or DEFAULT_PACKING_MODE
        return AlgorithmDetailResponse(
            name=meta.name,
            display_name=meta.display_name,
            problem_types=[p.value for p in meta.problem_types],
            algorithm_family=meta.algorithm_family.value,
            status=meta.status.value,
            description=meta.description,
            deterministic=meta.deterministic,
            supports_random_seed=meta.supports_random_seed,
            supports_time_limit=meta.supports_time_limit,
            supports_rotation=meta.supports_rotation,
            supports_multi_container=meta.supports_multi_container,
            supported_constraints=[c.value for c in meta.supported_constraints],
            unsupported_constraints=[c.value for c in meta.unsupported_constraints],
            parameters=meta.parameters,
            default_parameters=self.default_parameters(name, packing_mode=mode),
            packing_modes=[m.value for m in meta.packing_modes],
            metrics=meta.metrics,
            limitations=meta.limitations,
            external_engine=meta.external_engine,
            external_language=meta.external_language,
            external_repository=meta.external_repository,
            execution_endpoint=self.execution_endpoint(name),
            input_schema=self.input_schema_for(meta),
            output_schema=EXECUTE_OUTPUT_SCHEMA,
            is_executable=self.registry.is_executable(name),
        )

    def _load_example_file(self, filename: str) -> dict[str, Any]:
        path = self._examples_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"No existe el ejemplo: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def build_input_example(
        self,
        algorithm_name: str,
        problem_type: ProblemType | None = None,
        packing_mode: PackingMode | None = None,
    ) -> dict[str, Any]:
        if not self.registry.has(algorithm_name):
            raise AlgorithmNotFoundError(f"Algoritmo no encontrado: {algorithm_name}")
        meta = self.registry.get_metadata(algorithm_name)
        resolved = self.default_problem_type(meta, problem_type)
        mode = packing_mode or DEFAULT_PACKING_MODE

        if resolved == ProblemType.CARTONIZATION:
            example = self._load_example_file(_EXAMPLE_FILES[ProblemType.CARTONIZATION])
        else:
            example = self._load_example_file(_EXAMPLE_FILES[resolved])
            example["problem_type"] = resolved.value

        example["packing_mode"] = mode.value
        example["parameters"] = self.default_parameters(algorithm_name, packing_mode=mode)
        return example
