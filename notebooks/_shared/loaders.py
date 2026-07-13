"""Carga de ejemplos JSON y resolución de rutas del proyecto."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Instancias showcase: un caso complejo por tipo de problema (notebooks didácticos).
SHOWCASE_MASTER_CATALOG = "showcase_master_catalog"

SHOWCASE_INSTANCES: dict[str, str] = {
    "3D_BPP": "showcase_3d_bpp_instance",
    "3D_HYBRID": "showcase_3d_bpp_instance",
    "CONTAINER_LOADING": "showcase_container_loading_instance",
    "CARTONIZATION": "showcase_cartonization_instance",
    "SINGLE_CONTAINER_LOADING": "showcase_single_container_instance",
}

# Grupo de benchmark asociado a cada notebook didáctico (01–09).
NOTEBOOK_BENCHMARK_GROUP: dict[str, str | None] = {
    "00_introduccion_y_vision": None,
    "01_arquitectura_y_servicios": None,
    "02_demo_3d_bin_packing": "3D_BPP",
    "03_comparacion_de_algoritmos": "3D_BPP",
    "04_validacion_independiente": "3D_BPP",
    "05_container_loading": "CONTAINER_LOADING",
    "06_single_container_loading": "SINGLE_CONTAINER_LOADING",
    "07_cartonization": "CARTONIZATION",
    "08_catalogo_algoritmos_y_futuro": None,
    "09_preparacion_espacio_de_datos": None,
}

# Notas de diferenciación esperada (referencia para la narrativa didáctica).
SHOWCASE_DIFFERENTIATION: dict[str, str] = {
    "3D_BPP": "best_fit ~27 emp. (85% util) vs extreme_points ~22 (66%)",
    "3D_HYBRID": "misma cantidad empacada; compaction/LS mueven 8–11 piezas",
    "CONTAINER_LOADING": "weight_aware ~27 emp. vs single_container ~17 (alta util) vs extreme_points ~22",
    "CARTONIZATION": "minimalistas → BOX_M (~49% util) vs largest_feasible → BOX_L (~21%)",
    "SINGLE_CONTAINER_LOADING": "best_fit/single ~13 emp. (94% util) vs first_fit ~16 (89%)",
}

# Alias retrocompatible (misma mercancía que showcase 3D-BPP).
DEMO_INSTANCE = "showcase_3d_bpp_instance"

# Heurísticas 3D-BPP implementadas y comparables entre sí (+ adaptador opcional).
COMPARABLE_3D_BPP_ENGINES: list[dict[str, Any]] = [
    {
        "name": "heuristic_3d_bpp_v1",
        "label": "Volume First Candidate Placement",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "first_fit_decreasing_3d",
        "label": "First Fit Decreasing 3D",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "extreme_points_3d",
        "label": "Extreme Points Heuristic",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "best_fit_decreasing_3d",
        "label": "Best Fit Decreasing 3D",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "py3dbp_adapter",
        "label": "py3dbp Adapter (baseline externo)",
        "parameters": {"bigger_first": True, "distribute_items": True},
        "optional": True,
    },
]

COMPARABLE_CONTAINER_LOADING_ENGINES: list[dict[str, Any]] = [
    {
        "name": "single_container_constructive",
        "label": "Single Container Constructive",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "weight_aware_container_loading",
        "label": "Weight-aware Container Loading",
        "parameters": {"sort_strategy": "weight_desc"},
    },
    {
        "name": "extreme_points_3d",
        "label": "Extreme Points (multi-contenedor)",
        "parameters": {"sort_strategy": "volume_desc"},
    },
]

COMPARABLE_CARTONIZATION_ENGINES: list[dict[str, Any]] = [
    {
        "name": "smallest_feasible_box",
        "label": "Smallest Feasible Box",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "best_box_volume_utilization",
        "label": "Best Box by Volume Utilization",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "first_fit_box",
        "label": "First Fit Box (orden catálogo)",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "largest_feasible_box",
        "label": "Largest Feasible Box",
        "parameters": {"sort_strategy": "volume_desc"},
    },
]

COMPARABLE_SINGLE_CONTAINER_ENGINES: list[dict[str, Any]] = [
    {
        "name": "single_container_constructive",
        "label": "Single Container Constructive",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "best_fit_decreasing_3d",
        "label": "Best Fit Decreasing 3D",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "first_fit_decreasing_3d",
        "label": "First Fit Decreasing 3D",
        "parameters": {"sort_strategy": "volume_desc"},
    },
]

COMPARABLE_3D_HYBRID_ENGINES: list[dict[str, Any]] = [
    {
        "name": "best_fit_decreasing_3d",
        "label": "Best Fit Decreasing 3D (baseline)",
        "parameters": {"sort_strategy": "volume_desc"},
    },
    {
        "name": "solution_compaction",
        "label": "Compaction (mejora local)",
        "parameters": {
            "base_algorithm": "best_fit_decreasing_3d",
            "compaction_passes": 3,
        },
    },
    {
        "name": "constructive_plus_local_search",
        "label": "Constructive + Local Improvement",
        "parameters": {
            "base_algorithm": "best_fit_decreasing_3d",
            "compaction_passes": 3,
            "relocation_pass": True,
        },
    },
]

BENCHMARK_GROUPS: dict[str, dict[str, Any]] = {
    "3D_BPP": {
        "title": "3D Bin Packing",
        "engines": COMPARABLE_3D_BPP_ENGINES,
        "example": "benchmark_request",
        "builder": "build_benchmark_3d_bpp_request",
    },
    "3D_HYBRID": {
        "title": "3D Bin Packing — Constructivo + mejora local",
        "engines": COMPARABLE_3D_HYBRID_ENGINES,
        "example": "benchmark_hybrid_request",
        "builder": "build_benchmark_hybrid_request",
    },
    "CONTAINER_LOADING": {
        "title": "Container Loading",
        "engines": COMPARABLE_CONTAINER_LOADING_ENGINES,
        "example": "benchmark_container_loading_request",
        "builder": "build_benchmark_container_loading_request",
    },
    "CARTONIZATION": {
        "title": "Cartonization",
        "engines": COMPARABLE_CARTONIZATION_ENGINES,
        "example": "benchmark_cartonization_request",
        "builder": "build_benchmark_cartonization_request",
        "profile": "box_selection",
    },
    "SINGLE_CONTAINER_LOADING": {
        "title": "Single Container Loading",
        "engines": COMPARABLE_SINGLE_CONTAINER_ENGINES,
        "example": "benchmark_single_container_request",
        "builder": "build_benchmark_single_container_request",
        "profile": "constructive",
    },
}


def find_project_root(start: Path | None = None) -> Path:
    """Localiza la raíz del proyecto (contiene ``src/`` y ``examples/``)."""

    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "src" / "packing_services").is_dir() and (
            candidate / "examples"
        ).is_dir():
            return candidate
    raise FileNotFoundError(
        "No se encontró la raíz de packing-services. "
        "Ejecuta el notebook desde la carpeta del proyecto o notebooks/."
    )


def setup_paths(start: Path | None = None) -> Path:
    """Añade ``src/`` y ``notebooks/`` al ``sys.path`` y devuelve la raíz."""

    import sys

    root = find_project_root(start)
    src = str(root / "src")
    notebooks = str(root / "notebooks")
    for path in (src, notebooks):
        if path not in sys.path:
            sys.path.insert(0, path)
    return root


def examples_dir(root: Path | None = None) -> Path:
    return (root or find_project_root()) / "examples"


def load_example(name: str, root: Path | None = None) -> dict[str, Any]:
    """Carga ``examples/<name>.json`` (sin extensión en ``name``)."""

    path = examples_dir(root) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"No existe el ejemplo: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_master_catalog(root: Path | None = None) -> dict[str, Any]:
    """Catálogo homogéneo P1–P5 compartido por 3D-BPP, CL y SCL."""

    return load_example(SHOWCASE_MASTER_CATALOG, root)


def load_showcase_instance(
    problem_type: str = "3D_BPP",
    root: Path | None = None,
) -> dict[str, Any]:
    """Instancia showcase del tipo indicado (problema, sin algoritmo)."""

    name = SHOWCASE_INSTANCES.get(problem_type)
    if not name:
        raise ValueError(
            f"Sin instancia showcase para {problem_type!r}. "
            f"Disponibles: {sorted(SHOWCASE_INSTANCES)}"
        )
    return load_example(name, root)


def load_demo_instance(root: Path | None = None) -> dict[str, Any]:
    """Alias: instancia showcase 3D-BPP (retrocompatible)."""

    return load_showcase_instance("3D_BPP", root)


def _problem_payload(instance: dict[str, Any]) -> dict[str, Any]:
    """Copia solo campos válidos para Pack/Benchmark/ContainerLoading requests."""

    return {
        k: instance[k]
        for k in (
            "problem_type",
            "request_id",
            "containers",
            "items",
            "boxes",
            "constraints",
            "objective",
        )
        if k in instance
    }


def filter_available_engines(
    engines: list[dict[str, Any]],
    *,
    registry=None,
) -> list[dict[str, Any]]:
    """Omite motores opcionales no instalados (p. ej. ``py3dbp_adapter``)."""

    if registry is None:
        from packing_services.algorithms.registry import get_default_registry

        registry = get_default_registry()

    available: list[dict[str, Any]] = []
    for engine in engines:
        if engine.get("optional") and not registry.is_executable(engine["name"]):
            continue
        available.append(engine)
    return available


def _engine_configs(engines: list[dict[str, Any]], *, registry=None) -> list[dict[str, Any]]:
    return [
        {"name": e["name"], "parameters": e["parameters"]}
        for e in filter_available_engines(engines, registry=registry)
    ]


def build_pack_request(
    algorithm_name: str,
    instance: dict[str, Any] | None = None,
    *,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construye un ``PackRequest`` JSON desde la instancia demo."""

    data = _problem_payload(instance or load_showcase_instance("3D_BPP"))
    data["algorithm"] = {
        "name": algorithm_name,
        "parameters": parameters or {"sort_strategy": "volume_desc"},
    }
    return data


def build_pack_algorithm_input(
    instance: dict[str, Any] | None = None,
    *,
    problem_type: str = "3D_BPP",
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Entrada normalizada ``PackAlgorithmInput`` (sin campo ``algorithm``)."""

    data = _problem_payload(instance or load_showcase_instance(problem_type))
    data["problem_type"] = problem_type
    data["parameters"] = parameters or {"sort_strategy": "volume_desc"}
    return data


def build_cartonization_algorithm_input(
    instance: dict[str, Any] | None = None,
    *,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Entrada normalizada ``CartonizationAlgorithmInput`` (sin ``algorithm``)."""

    raw = instance or load_showcase_instance("CARTONIZATION")
    return {
        "request_id": raw.get("request_id"),
        "items": raw["items"],
        "boxes": raw["boxes"],
        "constraints": raw.get(
            "constraints",
            {
                "non_overlap": True,
                "containment": True,
                "allow_rotation": True,
                "max_weight": True,
            },
        ),
        "parameters": parameters or {"sort_strategy": "volume_desc"},
    }


def build_algorithm_execute_input(
    algorithm_name: str,
    instance: dict[str, Any] | None = None,
    *,
    problem_type: str | None = None,
    parameters: dict[str, Any] | None = None,
    registry=None,
) -> dict[str, Any]:
    """Construye el body para ``POST /api/v1/algorithms/{name}/execute``."""

    if registry is None:
        from packing_services.algorithms.registry import get_default_registry

        registry = get_default_registry()

    from packing_services.domain.enums import ProblemType

    meta = registry.get_metadata(algorithm_name)
    if meta.problem_types == [ProblemType.CARTONIZATION]:
        return build_cartonization_algorithm_input(instance, parameters=parameters)

    allowed = [pt for pt in meta.problem_types if pt != ProblemType.CARTONIZATION]
    if not allowed:
        raise ValueError(f"Algoritmo sin tipos pack compatibles: {algorithm_name}")

    resolved_type = problem_type
    if resolved_type is None:
        if len(allowed) == 1:
            resolved_type = allowed[0].value
        else:
            raise ValueError(
                f"El algoritmo '{algorithm_name}' admite varios problem_type. "
                f"Indica uno de: {[p.value for p in allowed]}"
            )

    return build_pack_algorithm_input(
        instance,
        problem_type=resolved_type,
        parameters=parameters,
    )


def build_benchmark_3d_bpp_request(
    instance: dict[str, Any] | None = None,
    *,
    registry=None,
) -> dict[str, Any]:
    """Benchmark 3D-BPP: 4 heurísticas internas + ``py3dbp_adapter`` si está instalado."""

    data = _problem_payload(instance or load_showcase_instance("3D_BPP"))
    data["problem_type"] = "3D_BPP"
    data["request_id"] = data.get("request_id", "showcase-3d-bpp-001").replace(
        "showcase-3d-bpp", "benchmark-3d"
    )
    data["engines"] = _engine_configs(COMPARABLE_3D_BPP_ENGINES, registry=registry)
    return data


def build_benchmark_container_loading_request(
    instance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Benchmark Container Loading sobre la instancia showcase CL."""

    data = _problem_payload(instance or load_showcase_instance("CONTAINER_LOADING"))
    data["problem_type"] = "CONTAINER_LOADING"
    data["request_id"] = data.get("request_id", "showcase-cl-001").replace(
        "showcase-cl", "benchmark-cl"
    )
    data["profile"] = "constructive"
    return data


def build_benchmark_hybrid_request(
    instance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Benchmark híbrido: baseline constructivo vs mejora local."""

    data = _problem_payload(instance or load_showcase_instance("3D_BPP"))
    data["problem_type"] = "3D_BPP"
    data["request_id"] = data.get("request_id", "showcase-3d-bpp-001").replace(
        "showcase-3d-bpp", "benchmark-hybrid"
    )
    data["engines"] = _engine_configs(COMPARABLE_3D_HYBRID_ENGINES)
    return data


def build_benchmark_cartonization_request(
    instance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Benchmark Cartonization con 4 estrategias de selección de caja."""

    data = _problem_payload(instance or load_showcase_instance("CARTONIZATION"))
    data["problem_type"] = "CARTONIZATION"
    data["request_id"] = data.get("request_id", "showcase-carton-001").replace(
        "showcase-carton", "benchmark-carton"
    )
    data["profile"] = "box_selection"
    return data


def build_benchmark_single_container_request(
    instance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Benchmark de carga en un único contenedor."""

    data = _problem_payload(instance or load_showcase_instance("SINGLE_CONTAINER_LOADING"))
    data["problem_type"] = "SINGLE_CONTAINER_LOADING"
    data["request_id"] = data.get("request_id", "showcase-scl-001").replace(
        "showcase-scl", "benchmark-scl"
    )
    data["profile"] = "constructive"
    return data


def build_benchmark_from_profile(
    problem_type: str,
    profile: str,
    instance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construye un benchmark usando un perfil estándar (recomendado)."""

    if problem_type == "CARTONIZATION":
        if profile == "box_selection":
            return build_benchmark_cartonization_request(instance)
        raise ValueError(f"Perfil cartonization no soportado en loader: {profile}")

    default_instance = instance or load_showcase_instance(problem_type)
    data = _problem_payload(default_instance)
    data["problem_type"] = problem_type
    data["profile"] = profile
    data["request_id"] = f"benchmark-{problem_type.lower()}-{profile}"
    return data


def build_benchmark_request(
    instance: dict[str, Any] | None = None,
    *,
    registry=None,
) -> dict[str, Any]:
    """Alias retrocompatible: benchmark 3D-BPP."""

    return build_benchmark_3d_bpp_request(instance, registry=registry)


def build_container_loading_request(
    instance: dict[str, Any] | None = None,
    algorithm_name: str = "weight_aware_container_loading",
) -> dict[str, Any]:
    """Instancia showcase CL, formulada como Container Loading."""

    data = _problem_payload(instance or load_showcase_instance("CONTAINER_LOADING"))
    data["problem_type"] = "CONTAINER_LOADING"
    data["algorithm"] = {
        "name": algorithm_name,
        "parameters": {"sort_strategy": "weight_desc"},
    }
    return data


def build_cartonization_request(instance: dict[str, Any] | None = None) -> dict[str, Any]:
    """Instancia showcase Cartonization (pedido P5×6 + catálogo de cajas)."""

    raw = instance or load_showcase_instance("CARTONIZATION")
    return {
        "request_id": raw.get("request_id"),
        "items": raw["items"],
        "boxes": raw["boxes"],
        "constraints": raw.get(
            "constraints",
            {
                "non_overlap": True,
                "containment": True,
                "allow_rotation": True,
                "max_weight": True,
            },
        ),
        "algorithm": {
            "name": "smallest_feasible_box",
            "parameters": {"sort_strategy": "volume_desc"},
        },
    }


def build_single_container_request(
    instance: dict[str, Any] | None = None,
    algorithm_name: str = "best_fit_decreasing_3d",
) -> dict[str, Any]:
    """Instancia showcase de un solo contenedor."""

    data = _problem_payload(instance or load_showcase_instance("SINGLE_CONTAINER_LOADING"))
    data["problem_type"] = "SINGLE_CONTAINER_LOADING"
    data["algorithm"] = {
        "name": algorithm_name,
        "parameters": {"sort_strategy": "volume_desc"},
    }
    return data


def problem_type_for_benchmark_group(group: str) -> str:
    """Tipo de problema asociado a un grupo de benchmark."""

    if group == "3D_HYBRID":
        return "3D_BPP"
    return group


def build_benchmark_for_group(
    group: str,
    instance: dict[str, Any] | None = None,
    *,
    registry=None,
) -> dict[str, Any]:
    """Construye el benchmark estándar de un grupo showcase."""

    builders = {
        "3D_BPP": build_benchmark_3d_bpp_request,
        "3D_HYBRID": build_benchmark_hybrid_request,
        "CONTAINER_LOADING": build_benchmark_container_loading_request,
        "CARTONIZATION": build_benchmark_cartonization_request,
        "SINGLE_CONTAINER_LOADING": build_benchmark_single_container_request,
    }
    if group not in builders:
        raise ValueError(f"Grupo de benchmark desconocido: {group}")
    builder = builders[group]
    if group == "3D_BPP":
        return builder(instance, registry=registry)
    return builder(instance)


def total_item_units(items: list[dict[str, Any]]) -> int:
    return sum(int(it.get("quantity", 1)) for it in items)
