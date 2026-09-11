"""Tests del registro de algoritmos."""

from __future__ import annotations

import pytest

from packing_services.algorithms.registry import default_registry
from packing_services.domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from packing_services.domain.models import (
    AlgorithmConfig,
    Container,
    Item,
    PackingProblem,
)
from packing_services.utils.errors import (
    AdapterUnavailableError,
    AlgorithmNotExecutableError,
    AlgorithmNotFoundError,
)


def test_implemented_algorithms_present():
    names = default_registry.list_names()
    assert "heuristic_3d_bpp_v1" in names
    assert "first_fit_decreasing_3d" in names
    assert "solution_compaction" in names
    assert "constructive_plus_local_search" in names
    assert "maximal_spaces_3d" in names
    assert "relocation_improvement" in names
    assert "swap_improvement" in names
    assert "orientation_improvement" in names
    assert "bin_reduction" in names
    assert "first_fit_box" in names
    assert "largest_feasible_box" in names


def test_get_metadata():
    meta = default_registry.get_metadata("heuristic_3d_bpp_v1")
    assert meta.status == AlgorithmStatus.IMPLEMENTED
    assert ProblemType.THREE_D_BPP in meta.problem_types


def test_unknown_algorithm_raises():
    with pytest.raises(AlgorithmNotFoundError):
        default_registry.get_metadata("does_not_exist")


def test_future_algorithm_not_executable():
    problem = PackingProblem(
        problem_type="3D_BPP",
        containers=[Container(id="C1", length=10, width=10, height=10)],
        items=[Item(id="I1", length=5, width=5, height=5)],
        algorithm=AlgorithmConfig(name="mip_3d_bpp_reference"),
    )
    with pytest.raises(AlgorithmNotExecutableError):
        default_registry.execute("mip_3d_bpp_reference", problem)


def test_stub_adapter_raises_unavailable():
    problem = PackingProblem(
        problem_type="3D_BPP",
        containers=[Container(id="C1", length=10, width=10, height=10)],
        items=[Item(id="I1", length=5, width=5, height=5)],
        algorithm=AlgorithmConfig(name="skjolber_adapter"),
    )
    with pytest.raises(AdapterUnavailableError):
        default_registry.execute("skjolber_adapter", problem)


def test_filter_by_status():
    implemented = default_registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED)
    assert all(m.status == AlgorithmStatus.IMPLEMENTED for m in implemented)
    assert len(implemented) >= 2


def test_filter_by_family_and_constraint():
    metaheuristics = default_registry.list_metadata(
        family=AlgorithmFamily.METAHEURISTIC
    )
    assert all(m.algorithm_family == AlgorithmFamily.METAHEURISTIC for m in metaheuristics)
    assert len(metaheuristics) == 7
    assert all(m.status == AlgorithmStatus.IMPLEMENTED for m in metaheuristics)

    weight_aware = default_registry.list_metadata(
        supported_constraint=Constraint.MAX_WEIGHT
    )
    assert any(m.name == "heuristic_3d_bpp_v1" for m in weight_aware)


def test_adapters_registered():
    names = default_registry.list_names()
    for adapter in [
        "py3dbp_adapter",
        "skjolber_adapter",
        "boxpacker_adapter",
        "container_packing_adapter",
        "packingsolver_adapter",
        "dwave_adapter",
    ]:
        assert adapter in names
