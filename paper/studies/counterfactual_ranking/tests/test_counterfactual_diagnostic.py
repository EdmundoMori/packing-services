"""Pruebas sintéticas del diagnóstico. No leen pedidos reales."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

STUDY_TOOLS = Path(__file__).resolve().parents[1] / "tools"
PAPER_TOOLS = Path(__file__).resolve().parents[3] / "tools"
for entry in (str(PAPER_TOOLS), str(STUDY_TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from compact_study import COMPACT_FLAGS, SUFFIX_REASON, TERMINAL_REASON, build_compact_problem  # noqa: E402
from diagnostic import (  # noqa: E402
    accept_scored_capture,
    collect_states,
    continue_from,
    evaluate_state,
    greedy_reference,
    score_solution,
    select_alternatives,
    static_operation_estimate,
)
from pilot_problems import problem_snapshot  # noqa: E402
from run_preflight import (  # noqa: E402
    InvocationError,
    arm_wall_clock,
    declared_subset,
    disarm_wall_clock,
    require_declared_orders,
    require_hashes,
    run,
)
from select_sample import choose_orders, selection_hash  # noqa: E402


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


class CounterfactualDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orders = _order(
            "S",
            "euro-pallet",
            [("box", 30, 40, 50), ("next", 25, 35, 45), ("block", 3000, 10, 10), ("later", 10, 10, 10)],
        )
        self.problem = build_compact_problem(self.orders, "S")
        self.snapshot = problem_snapshot(self.problem)
        self.states = collect_states(self.problem)

    def test_static_estimate_does_not_pack(self) -> None:
        estimate = static_operation_estimate()
        self.assertFalse(estimate["packing_executed_for_this_estimate"])
        self.assertEqual(estimate["upper_bound_states"], 100)
        self.assertEqual(estimate["upper_bound_continuations"], 400)

    def test_restore_keeps_the_same_initial_state_and_suffix(self) -> None:
        state = self.states[0]
        before = copy.deepcopy(state["checkpoint"])
        first = continue_from(self.problem, state["checkpoint"], tuple(state["alternatives"][1]))
        second = continue_from(self.problem, state["checkpoint"], tuple(state["greedy_key"]))
        self.assertEqual(state["checkpoint"]["geometry"], before["geometry"])
        self.assertEqual(state["checkpoint"]["remaining_ids"], before["remaining_ids"])
        self.assertIsNotNone(first["solution"])
        self.assertIsNotNone(second["solution"])
        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")
        again = continue_from(self.problem, state["checkpoint"], tuple(state["greedy_key"]))
        self.assertEqual(
            [(item.item_id, item.position.x, item.position.y, item.position.z) for item in second["solution"].packed_items],
            [(item.item_id, item.position.x, item.position.y, item.position.z) for item in again["solution"].packed_items],
        )

    def test_orientation_can_change_height_and_greedy_is_included(self) -> None:
        state = self.states[0]
        self.assertEqual(state["alternatives"][0], state["greedy_key"])
        heights = {orientation[2] for orientation in state["orientations"]}
        self.assertGreaterEqual(len(heights), 2)
        self.assertIn(state["greedy_key"], [tuple(action) for action in state["alternatives"]])

    def test_later_state_examines_more_than_one_position(self) -> None:
        self.assertGreaterEqual(len(self.states), 2)
        positions = {tuple(position) for position in self.states[1]["positions"]}
        self.assertGreaterEqual(len(positions), 2)

    def test_greedy_alternative_matches_the_reference_continuation(self) -> None:
        reference = greedy_reference(self.problem)
        state = self.states[0]
        outcome = continue_from(self.problem, state["checkpoint"], tuple(state["greedy_key"]))
        self.assertEqual(
            [(item.item_id, item.reason) for item in outcome["solution"].unpacked_items],
            [(item.item_id, item.reason) for item in reference.unpacked_items],
        )
        self.assertEqual(
            [(item.item_id, item.orientation.height) for item in outcome["solution"].packed_items],
            [(item.item_id, item.orientation.height) for item in reference.packed_items],
        )

    def test_stop_keeps_the_suffix_without_discarding(self) -> None:
        reference = greedy_reference(self.problem)
        packed = [item.item_id for item in reference.packed_items]
        self.assertNotIn("later#4", packed)
        self.assertEqual(
            [(item.item_id, item.reason) for item in reference.unpacked_items],
            [("block#3", TERMINAL_REASON), ("later#4", SUFFIX_REASON)],
        )

    def test_original_checkpoint_survives_the_other_alternatives(self) -> None:
        state = self.states[0]
        saved = copy.deepcopy(state["checkpoint"]["geometry"])
        evaluate_state(
            self.problem,
            state,
            order_id="S",
            dataset="synthetic",
            dataset_sha256="0" * 64,
            snapshot=self.snapshot,
        )
        self.assertEqual(state["checkpoint"]["geometry"], saved)

    def test_each_successful_capture_is_audited(self) -> None:
        reference = greedy_reference(self.problem)
        scored = score_solution(
            self.problem,
            reference,
            order_id="S",
            dataset="synthetic",
            dataset_sha256="0" * 64,
            snapshot=self.snapshot,
        )
        self.assertIsNone(scored["reason"])
        self.assertEqual(scored["audit_failure_types"], [])
        self.assertIsNone(scored["capture"]["physical_stability_verified"])
        self.assertIsInstance(scored["q_hat"], float)
        self.assertIsNone(accept_scored_capture(scored["capture"], self.snapshot, order_id="S"))

    def test_timeout_is_unknown_and_incomplete_states_have_no_labels(self) -> None:
        state = self.states[0]
        ticks = {"value": 0.0}

        def now() -> float:
            ticks["value"] += 100.0
            return ticks["value"]

        result = evaluate_state(
            self.problem,
            state,
            order_id="S",
            dataset="synthetic",
            dataset_sha256="0" * 64,
            snapshot=self.snapshot,
            timeout_seconds=1,
            now=now,
        )
        self.assertEqual(result["labels"], [])
        self.assertFalse(result["complete"])
        self.assertTrue(result["alternatives"])
        for row in result["alternatives"]:
            self.assertIsNone(row["q_hat"])
            self.assertEqual(row["reason"], "timeout")
            self.assertNotEqual(row["q_hat"], 0)

    def test_partial_success_does_not_become_a_label(self) -> None:
        state = self.states[0]
        original = continue_from

        def mixed(problem, checkpoint, action_key, **kwargs):
            if tuple(action_key) == tuple(state["greedy_key"]):
                return original(problem, checkpoint, action_key, **kwargs)
            return {"status": "timeout", "solution": None, "reason": "timeout"}

        import diagnostic

        diagnostic.continue_from = mixed
        try:
            result = evaluate_state(
                self.problem,
                state,
                order_id="S",
                dataset="synthetic",
                dataset_sha256="0" * 64,
                snapshot=self.snapshot,
            )
        finally:
            diagnostic.continue_from = original
        self.assertEqual(result["labels"], [])
        self.assertFalse(result["complete"])
        greedy = next(row for row in result["alternatives"] if row["is_greedy"])
        self.assertIsInstance(greedy["q_hat"], float)
        self.assertTrue(any(row["q_hat"] is None for row in result["alternatives"]))

    def test_audit_exception_has_no_geometric_return(self) -> None:
        state = self.states[0]
        import diagnostic

        def boom(*args, **kwargs):
            raise RuntimeError("auditoría")

        original = diagnostic.score_solution
        diagnostic.score_solution = boom
        try:
            result = evaluate_state(
                self.problem,
                state,
                order_id="S",
                dataset="synthetic",
                dataset_sha256="0" * 64,
                snapshot=self.snapshot,
            )
        finally:
            diagnostic.score_solution = original
        self.assertEqual(result["labels"], [])
        for row in result["alternatives"]:
            self.assertIsNone(row["q_hat"])
            self.assertIn("audit_exception", row["reason"])

    def test_selection_is_deterministic(self) -> None:
        self.assertEqual(
            selection_hash("00100000"),
            hashlib.sha256(b"counterfactual-v1|20261003|00100000").hexdigest(),
        )
        state = self.states[0]
        again = collect_states(self.problem)
        self.assertEqual(state["alternatives"], again[0]["alternatives"])
        eligible = {"euro-pallet": ["b", "a", "c"], "rollcontainer": ["d", "e"]}

        def signature(order_id: str) -> str:
            return {"a": "same", "b": "same", "c": "other", "d": "roll", "e": "roll-2"}[order_id]

        first = choose_orders(eligible, signature, {"blocked": "excluded-1"}, per_target=2)
        second = choose_orders(eligible, signature, {"blocked": "excluded-1"}, per_target=2)
        self.assertEqual(first, second)
        euro = [row["order_id"] for row in first["selected"]["euro-pallet"]]
        ranked = sorted(["a", "b", "c"], key=selection_hash)
        expected = []
        for order_id in ranked:
            if len(expected) == 2:
                break
            if order_id in ("a", "b") and any(item in ("a", "b") for item in expected):
                continue
            expected.append(order_id)
        self.assertEqual(euro, expected)
        self.assertTrue(first["dropped_clones"])

    def test_incompatible_inputs_are_rejected(self) -> None:
        from packing_services.domain.models import ConstraintFlags

        flags = dict(COMPACT_FLAGS)
        flags["max_weight"] = True
        rejected = self.problem.model_copy(update={"constraints": ConstraintFlags(**flags)})
        with self.assertRaises(Exception):
            greedy_reference(rejected)
        altered = copy.deepcopy(self.snapshot)
        altered["items"][0]["length_mm"] = 1
        reference = greedy_reference(self.problem)
        scored = score_solution(
            self.problem,
            reference,
            order_id="S",
            dataset="synthetic",
            dataset_sha256="0" * 64,
            snapshot=altered,
        )
        self.assertIsNone(scored["q_hat"])
        self.assertIn("input_mismatch", scored["reason"])
        capture = score_solution(
            self.problem,
            reference,
            order_id="S",
            dataset="synthetic",
            dataset_sha256="0" * 64,
            snapshot=self.snapshot,
        )["capture"]
        self.assertEqual(
            accept_scored_capture(capture, altered, order_id="S"),
            "entrada incompatible: length_mm",
        )

    def test_preflight_subset_uses_the_registered_heads_and_cannot_reselect(self) -> None:
        subset = declared_subset(
            {
                "selected": {
                    "euro-pallet": [{"order_id": "e1", "target": "euro-pallet"}, {"order_id": "e2"}],
                    "rollcontainer": [{"order_id": "r1", "target": "rollcontainer"}],
                }
            }
        )
        self.assertEqual([row["order_id"] for row in subset["orders"]], ["e1", "r1"])
        self.assertEqual(subset["max_states_per_order"], 1)
        self.assertEqual(subset["max_alternatives"], 2)
        self.assertTrue(subset["counts_toward_sample"])
        self.assertTrue(subset["counts_toward_budget"])
        self.assertFalse(subset["may_reselect_sample"])
        with self.assertRaises(ValueError):
            declared_subset({"selected": {"euro-pallet": [], "rollcontainer": [{"order_id": "r1"}]}})

    def test_alternative_selection_does_not_read_returns(self) -> None:
        import inspect

        from diagnostic import select_alternatives as selector

        self.assertNotIn("q_hat", inspect.getsource(selector))
        options = self.states[0]
        self.assertLessEqual(len(options["alternatives"]), 4)

    def test_global_deadline_blocks_capture_and_audit(self) -> None:
        blocked = score_solution(
            self.problem,
            None,
            order_id="S",
            dataset="synthetic",
            dataset_sha256="0" * 64,
            snapshot=self.snapshot,
            deadline=0,
            now=lambda: 1.0,
        )
        self.assertIsNone(blocked["q_hat"])
        self.assertEqual(blocked["reason"], "wall_clock")
        self.assertIsNone(blocked["capture"])
        result = evaluate_state(
            self.problem,
            self.states[0],
            order_id="S",
            dataset="synthetic",
            dataset_sha256="0" * 64,
            snapshot=self.snapshot,
            global_deadline=0,
            now=lambda: 1.0,
        )
        self.assertEqual(result["labels"], [])
        self.assertFalse(result["complete"])
        self.assertTrue(result["alternatives"])
        for row in result["alternatives"]:
            self.assertIsNone(row["q_hat"])
            self.assertEqual(row["reason"], "wall_clock")

    def test_wall_clock_signal_interrupts_a_blocking_call(self) -> None:
        import time

        from diagnostic import WallClockExceeded

        arm_wall_clock(0.05)
        try:
            with self.assertRaises(WallClockExceeded):
                time.sleep(2)
        finally:
            disarm_wall_clock()

    def test_existing_output_directory_is_rejected(self) -> None:
        import tempfile

        manifest = {
            "selected": {
                "euro-pallet": [{"order_id": "00109938", "target": "euro-pallet"}],
                "rollcontainer": [{"order_id": "00105640", "target": "rollcontainer"}],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "preflight_results"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                run(manifest, {}, dataset="synthetic", dataset_sha256="0" * 64, output=output)

    def test_registered_orders_and_hash_mismatch_are_rejected(self) -> None:
        import tempfile

        from pilot_common import sha256_file

        study = Path(__file__).resolve().parents[1]
        protocol = json.loads((study / "protocol_draft.json").read_text(encoding="utf-8"))
        manifest = json.loads((study / "sample_manifest.json").read_text(encoding="utf-8"))
        subset = require_declared_orders(protocol, manifest)
        self.assertEqual([row["order_id"] for row in subset["orders"]], ["00109938", "00105640"])
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "data.json"
            dataset.write_text("[]", encoding="utf-8")
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")
            rejected = {
                "dataset_sha256": "0" * 64,
                "sample_manifest_sha256": sha256_file(manifest_path),
                "dataset": str(dataset),
            }
            with self.assertRaises(InvocationError):
                require_hashes(rejected, manifest_path, {"dataset_sha256": "0" * 64}, dataset)


if __name__ == "__main__":
    unittest.main()
