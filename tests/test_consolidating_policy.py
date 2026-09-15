"""Disciplina de consolidación: agotar el pallet abierto antes de abrir otro."""

from __future__ import annotations

from packing_services.domain.models import ConstraintFlags, Container, Item
from packing_services.online.budget import InformationBudget
from packing_services.online.loop import run_online_loop
from packing_services.online.mask import ValidatorMask
from packing_services.online.policies import (
    ConsolidatingPolicy,
    GreedyBestFitPolicy,
    restrict_to_open_bin,
)
from packing_services.online.session import ExtremePointOnlineSession
from packing_services.online.types import StepOption
from packing_services.domain.models import AlgorithmConfig, PackingProblem

CONSTRAINTS = ConstraintFlags(
    non_overlap=True, containment=True, allow_rotation=True, max_weight=True
)


def _two_pallet_problem(n_items: int = 12, algorithm: str = "online_3d_bpp_heuristic"):
    """Doce cajas que caben de sobra en un solo contenedor de los dos ofrecidos."""

    containers = [
        Container(id="P1", length=100, width=100, height=100, max_weight=10_000),
        Container(id="P2", length=100, width=100, height=100, max_weight=10_000),
    ]
    items = [
        Item(
            id=f"I{index:02d}",
            length=25,
            width=25,
            height=25,
            weight=1,
            arrival_index=index,
        )
        for index in range(1, n_items + 1)
    ]
    return PackingProblem(
        problem_type="3D_BPP",
        containers=containers,
        items=items,
        constraints=CONSTRAINTS,
        algorithm=AlgorithmConfig(
            name=algorithm,
            parameters={"sort_strategy": "input_order", "lookahead_p": 1, "select_s": 1},
        ),
    )


def _session_and_options(problem, item):
    session = ExtremePointOnlineSession(problem.containers, selection="best_fit")
    mask = ValidatorMask(problem, min_support_ratio=0.0)
    options = [
        StepOption(item=item, candidate=cand, buffer_index=0)
        for cand in session.candidates(item, CONSTRAINTS)
        if mask.allows(cand, item, session, CONSTRAINTS)
    ]
    return session, mask, options


def test_restrict_opens_the_lowest_bin_when_nothing_is_open_yet():
    problem = _two_pallet_problem()
    session, _, options = _session_and_options(problem, problem.items[0])
    assert {o.candidate.bin_index for o in options} == {0, 1}

    allowed = restrict_to_open_bin(options, session)
    assert {o.candidate.bin_index for o in allowed} == {0}


def test_restrict_keeps_the_open_bin_and_hides_the_empty_one():
    problem = _two_pallet_problem()
    session, mask, options = _session_and_options(problem, problem.items[0])

    first = restrict_to_open_bin(options, session)[0]
    session.commit(first.candidate, problem.items[0])
    assert session.states[0].placed and not session.states[1].placed

    second_item = problem.items[1]
    options = [
        StepOption(item=second_item, candidate=cand, buffer_index=0)
        for cand in session.candidates(second_item, CONSTRAINTS)
        if mask.allows(cand, second_item, session, CONSTRAINTS)
    ]
    assert {o.candidate.bin_index for o in options} == {0, 1}

    allowed = restrict_to_open_bin(options, session)
    assert {o.candidate.bin_index for o in allowed} == {0}


def test_restrict_returns_empty_for_no_options():
    problem = _two_pallet_problem()
    session, _, _ = _session_and_options(problem, problem.items[0])
    assert restrict_to_open_bin([], session) == []


def test_wrapper_delegates_the_pose_to_the_inner_policy():
    """La envolvente recorta el menú; no elige la pose."""

    problem = _two_pallet_problem()
    session, mask, options = _session_and_options(problem, problem.items[0])
    inner = GreedyBestFitPolicy()

    seen: dict[str, int] = {}

    class Spy:
        def decide(self, opts, **kwargs):
            seen["n"] = len(opts)
            seen["bins"] = len({o.candidate.bin_index for o in opts})
            return inner.decide(opts, **kwargs)

    chosen = ConsolidatingPolicy(Spy()).decide(
        options,
        preview=[problem.items[0]],
        remaining_count=len(problem.items),
        session=session,
        constraints=CONSTRAINTS,
        mask=mask,
    )
    assert seen["bins"] == 1
    assert seen["n"] < len(options)
    assert chosen is not None
    assert chosen.candidate.bin_index == 0


def test_greedy_alone_splits_a_load_that_fits_in_one_pallet():
    """Baseline del defecto: el greedy libre abre el segundo pallet sin necesidad."""

    problem = _two_pallet_problem()
    packed, unpacked = run_online_loop(
        problem, budget=InformationBudget(1, 1), selection="best_fit"
    )
    assert not unpacked
    assert len({p.container_id for p in packed}) == 2


def test_consolidating_policy_keeps_the_load_in_one_pallet():
    problem = _two_pallet_problem()
    packed, unpacked = run_online_loop(
        problem,
        budget=InformationBudget(1, 1),
        selection="best_fit",
        policy=ConsolidatingPolicy(GreedyBestFitPolicy()),
    )
    assert not unpacked
    assert len(packed) == len(problem.items)
    assert {p.container_id for p in packed} == {"P1"}


def test_heuristic_execute_consolidates_by_default_with_two_pallets():
    """Paso B: sin enviar consolidate, 2+ contenedores activan first-fit."""

    from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic

    problem = _two_pallet_problem()
    assert "consolidate" not in problem.algorithm.parameters
    solution = Online3DBPPHeuristic().run(problem)
    assert solution.validation_report and solution.validation_report.is_valid
    assert solution.metrics.items_unpacked == 0
    assert solution.metrics.containers_used == 1


def test_heuristic_execute_keeps_the_split_when_consolidate_is_false():
    from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic

    problem = _two_pallet_problem()
    problem.algorithm.parameters["consolidate"] = False
    solution = Online3DBPPHeuristic().run(problem)
    assert solution.metrics.containers_used == 2


def test_heuristic_execute_still_opens_second_pallet_when_needed():
    from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic

    problem = _two_pallet_problem(n_items=80)
    solution = Online3DBPPHeuristic().run(problem)
    assert solution.metrics.items_packed == 80
    assert solution.metrics.containers_used == 2


def test_wants_consolidate_defaults_to_multi_container():
    from packing_services.online.params import wants_consolidate

    assert wants_consolidate({}, 1) is False
    assert wants_consolidate({}, 2) is True
    assert wants_consolidate({"consolidate": False}, 2) is False
    assert wants_consolidate({"consolidate": "true"}, 1) is True


def test_consolidating_policy_still_opens_the_second_pallet_when_needed():
    """La disciplina consolida, no bloquea: si el primero se llena, abre el otro."""

    # 100x100x100 caben 64 cubos de 25; con 80 hacen falta dos contenedores.
    problem = _two_pallet_problem(n_items=80)
    packed, unpacked = run_online_loop(
        problem,
        budget=InformationBudget(1, 1),
        selection="best_fit",
        policy=ConsolidatingPolicy(GreedyBestFitPolicy()),
    )
    assert len(packed) == 80
    assert not unpacked
    assert len({p.container_id for p in packed}) == 2
    # El primero debe quedar lleno antes de tocar el segundo.
    per_container = {}
    for item in packed:
        per_container[item.container_id] = per_container.get(item.container_id, 0) + 1
    assert per_container["P1"] == 64
    assert per_container["P2"] == 16
