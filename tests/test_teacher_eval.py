"""El maestro se puede ejecutar como packer sobre el mismo validador."""

from __future__ import annotations

import sys
from pathlib import Path

from packing_services.domain.models import (
    AlgorithmConfig,
    ConstraintFlags,
    Container,
    Item,
    PackingProblem,
)

REPO = Path(__file__).resolve().parents[1]
SRC_ML = REPO / "online_policy_ml" / "src_ml"
if str(SRC_ML) not in sys.path:
    sys.path.insert(0, str(SRC_ML))

from evaluate import run_teacher_solution  # noqa: E402


def test_teacher_packs_a_tiny_online_instance():
    items = [
        Item(id=f"I{i}", length=30, width=25, height=20, weight=1, arrival_index=i)
        for i in range(1, 9)
    ]
    problem = PackingProblem(
        problem_type="3D_BPP",
        containers=[Container(id="C1", length=100, width=100, height=100, max_weight=100000)],
        items=items,
        constraints=ConstraintFlags(),
        algorithm=AlgorithmConfig(
            name="online_3d_bpp_heuristic",
            parameters={"lookahead_p": 1, "select_s": 1, "selection": "best_fit"},
        ),
    )
    solution = run_teacher_solution(problem, lookahead_p=1, select_s=1)
    assert solution.validation_report is not None
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed >= 1
    assert solution.metrics.volume_utilization > 0
