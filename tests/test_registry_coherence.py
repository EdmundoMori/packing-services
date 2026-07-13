"""Coherencia global del catálogo: unicidad, conteos y alineación benchmark."""

from __future__ import annotations

from packing_services.algorithms.registry import get_default_registry
from packing_services.benchmark.profiles import list_profiles, profile_engine_defs
from packing_services.domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    ProblemType,
)

_META_NAMES = {
    "simulated_annealing_3d_bpp",
    "genetic_algorithm_3d_bpp",
    "grasp_3d_bpp",
    "tabu_search_3d_bpp",
    "lns_3d_bpp",
    "vns_3d_bpp",
    "aco_3d_bpp",
}


def test_registry_total_counts():
    registry = get_default_registry()
    all_meta = registry.list_metadata()
    assert len(all_meta) == 52
    assert len(registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED)) == 29
    assert len(registry.list_metadata(status=AlgorithmStatus.ADAPTER)) == 6
    assert len(registry.list_metadata(status=AlgorithmStatus.FUTURE)) == 17


def test_registry_unique_names():
    registry = get_default_registry()
    names = registry.list_names()
    assert len(names) == len(set(names))


def test_metaheuristics_implemented_not_future():
    registry = get_default_registry()
    for name in _META_NAMES:
        meta = registry.get_metadata(name)
        assert meta.status == AlgorithmStatus.IMPLEMENTED
        assert meta.algorithm_family == AlgorithmFamily.METAHEURISTIC
        assert registry.is_executable(name)
    future_meta = [
        m.name
        for m in registry.list_metadata(
            family=AlgorithmFamily.METAHEURISTIC, status=AlgorithmStatus.FUTURE
        )
    ]
    assert future_meta == []


def test_benchmark_profiles_include_metaheuristic():
    profiles = list_profiles(ProblemType.THREE_D_BPP)
    profile_names = {p["profile"] for p in profiles}
    assert "metaheuristic" in profile_names
    assert "constructive" in profile_names
    assert "hybrid" in profile_names
    assert "improvement" in profile_names
    engines = profile_engine_defs(ProblemType.THREE_D_BPP, "metaheuristic")
    names = {e["name"] for e in engines}
    assert "simulated_annealing_3d_bpp" in names
    assert len(engines) >= 3


def test_benchmark_groups_align_with_profiles():
    profiles = list_profiles()
    assert len(profiles) >= 9
    for entry in profiles:
        engines = profile_engine_defs(entry["problem_type"], entry["profile"])
        assert len(engines) >= 2


def test_implemented_algorithms_are_executable():
    registry = get_default_registry()
    for meta in registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED):
        assert registry.is_executable(meta.name), meta.name
