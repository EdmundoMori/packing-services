"""Pruebas sintéticas del contrato compacto. No ejecutan el smoke real."""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compact_study import (  # noqa: E402
    COMPACT_FLAGS,
    SUFFIX_REASON,
    TERMINAL_REASON,
    build_compact_problem,
    compact_selector_view,
    propose_calibration_orders,
    run_compact_greedy,
    smoke_orders,
)
from online_bph_case import FiniteSequenceCreator  # noqa: E402
from pilot_metrics import evaluate_outcome  # noqa: E402
from pilot_problems import prepare_imports, problem_snapshot  # noqa: E402
from compact_study import capture_compact_case  # noqa: E402


def _order(order_id: str, target: str, items: list[tuple[str, int, int, int]]) -> dict:
    sequence = {}
    for index, (name, length, width, height) in enumerate(items, start=1):
        sequence[str(index)] = {
            "sequence": index,
            "id": name,
            "length/mm": length,
            "width/mm": width,
            "height/mm": height,
            "weight/kg": 1,
        }
    return {order_id: {"properties": {"target": target}, "item_sequence": sequence}}


class CompactContractTests(unittest.TestCase):
    def test_episode_stops_at_the_first_impossible_item_and_leaves_the_suffix(self):
        orders = _order("S", "100,100,100", [("big", 300, 10, 10), ("small", 20, 20, 20)])
        problem = build_compact_problem(orders, "S")
        solution, diagnostics = run_compact_greedy(problem)
        self.assertEqual(solution.packed_items, [])
        self.assertEqual([item.reason for item in solution.unpacked_items], [TERMINAL_REASON, SUFFIX_REASON])
        self.assertEqual([step["item_id"] for step in diagnostics["steps"]], ["big#1"])
        self.assertEqual(diagnostics["steps"][0]["preview_ids"], ["big#1"])

    def test_suffix_is_not_packed_after_a_later_stop(self):
        orders = _order(
            "S",
            "100,100,100",
            [("fit", 40, 40, 40), ("block", 300, 10, 10), ("later", 10, 10, 10)],
        )
        problem = build_compact_problem(orders, "S")
        solution, diagnostics = run_compact_greedy(problem)
        self.assertEqual([item.item_id for item in solution.packed_items], ["fit#1"])
        self.assertEqual(
            [(item.item_id, item.reason) for item in solution.unpacked_items],
            [("block#2", TERMINAL_REASON), ("later#3", SUFFIX_REASON)],
        )
        self.assertNotIn("later#3", [step["item_id"] for step in diagnostics["steps"]])
        for step in diagnostics["steps"]:
            self.assertEqual(step["preview_ids"], [step["item_id"]])

    def test_oriented_dimensions_stay_a_permutation_and_six_axes_exist(self):
        prepare_imports()
        from packing_services.domain.geometry import unique_orientations
        from packing_services.domain.models import Dimensions

        orientations = unique_orientations(Dimensions(30, 40, 50), True)
        self.assertEqual(len(orientations), 6)
        orders = _order("S", "euro-pallet", [("box", 30, 40, 50)])
        problem = build_compact_problem(orders, "S")
        solution, _diagnostics = run_compact_greedy(problem)
        packed = solution.packed_items[0]
        oriented = sorted((packed.orientation.length, packed.orientation.width, packed.orientation.height))
        self.assertEqual(oriented, [30, 40, 50])
        session_count = len(problem.constraints.model_dump())
        self.assertGreater(session_count, 0)
        self.assertEqual(
            {tuple(sorted((item.length, item.width, item.height))) for item in orientations},
            {(30, 40, 50)},
        )

    def test_selector_view_has_no_future_information(self):
        signature = inspect.signature(compact_selector_view)
        self.assertNotIn("remaining_count", signature.parameters)
        self.assertNotIn("preview", signature.parameters)
        orders = _order("S", "euro-pallet", [("now", 30, 40, 50), ("later", 80, 20, 10)])
        problem = build_compact_problem(orders, "S")
        _solution, diagnostics = run_compact_greedy(problem)
        self.assertTrue(all(len(step["preview_ids"]) == 1 for step in diagnostics["steps"]))
        self.assertNotIn("later#2", diagnostics["steps"][0]["preview_ids"])
        prepare_imports()
        from packing_services.online.mask import ValidatorMask
        from packing_services.online.params import support_threshold
        from packing_services.online.session import ExtremePointOnlineSession
        from packing_services.online.types import StepOption

        current = problem.items[0]
        session = ExtremePointOnlineSession(problem.containers)
        mask = ValidatorMask(problem, min_support_ratio=support_threshold({}, problem.constraints.basic_stability))
        options = [
            StepOption(item=current, candidate=candidate, buffer_index=0)
            for candidate in session.candidates(current, problem.constraints)
            if mask.allows(candidate, current, session, problem.constraints)
        ]
        view = compact_selector_view(current, options)
        self.assertEqual(set(view), {"current_item_id", "current_lwh_mm", "candidates"})
        self.assertEqual(len({tuple(row["oriented_lwh_mm"]) for row in view["candidates"]}), 6)
        rendered = str(view)
        self.assertNotIn("later#2", rendered)
        self.assertNotIn("remaining_count", rendered)

    def test_auditor_checks_input_and_geometry(self):
        orders = _order("S", "euro-pallet", [("a", 200, 150, 100), ("b", 180, 120, 80)])
        problem = build_compact_problem(orders, "S")
        self.assertEqual(problem.constraints.model_dump(), COMPACT_FLAGS)
        solution, _diagnostics = run_compact_greedy(problem)
        snapshot = problem_snapshot(problem)
        capture = capture_compact_case(
            problem,
            solution,
            order_id="S",
            dataset="/tmp/sintetico.json",
            dataset_sha256="0" * 64,
        )
        row = evaluate_outcome(
            {"status": "ok", "capture": capture, "attempts": 1, "duration_seconds": 0.01},
            order_id="S",
            method="greedy",
            target="euro-pallet",
            container_volume_mm3=snapshot["containers"][0]["volume_mm3"],
            run_id="synthetic",
            snapshot=snapshot,
        )
        self.assertEqual(row["failure_types"], [])
        self.assertGreater(row["effective_u_geom"], 0)
        self.assertIsNone(row["physical_stability_verified"])
        self.assertFalse(row["input_mismatch"])
        self.assertFalse(row["geometry_invalid"])

    def test_smoke_rule_and_calibration_do_not_read_utilities(self):
        items = [
            {"order_id": "e1", "target": "euro-pallet", "position": 0},
            {"order_id": "r1", "target": "rollcontainer", "position": 1},
            {"order_id": "r2", "target": "rollcontainer", "position": 2},
            {"order_id": "e2", "target": "euro-pallet", "position": 3},
            {"order_id": "e3", "target": "euro-pallet", "position": 4},
            {"order_id": "e4", "target": "euro-pallet", "position": 5},
        ]
        chosen = smoke_orders(items)
        self.assertEqual([row["order_id"] for row in chosen], ["e1", "r1", "r2", "e2", "e3"])
        orders = {
            "a": {"properties": {"target": "euro-pallet"}},
            "b": {"properties": {"target": "rollcontainer"}},
            "c": {"properties": {"target": "euro-pallet"}},
        }
        selected = propose_calibration_orders(["a", "b", "c"], orders, {"b"}, per_target=1)
        self.assertEqual(selected["euro-pallet"], ["a"])
        self.assertEqual(selected["rollcontainer"], [])

    def test_finite_sequence_keeps_arrival_order_then_sentinel(self):
        creator = FiniteSequenceCreator([(2, 3, 4), (5, 6, 7)], (9, 9, 9))
        self.assertEqual(creator.preview(1), [(2, 3, 4)])
        creator.drop_box()
        creator.generate_box_size()
        self.assertEqual(creator.preview(1), [(5, 6, 7)])
        creator.drop_box()
        creator.generate_box_size()
        self.assertEqual(creator.preview(1), [(9, 9, 9)])


if __name__ == "__main__":
    unittest.main()
