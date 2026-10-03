"""Puerta, preflight y reloj de la campaña. No empaqueta pedidos reales."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
TOOLS = STUDY / "tools"
PAPER_TOOLS = STUDY.parents[1] / "tools"
for entry in (str(PAPER_TOOLS), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from campaign import (  # noqa: E402
    Budget,
    admit_state,
    directory_must_be_new,
    evaluate_planned_actions,
    file_sha256,
    finalize_state,
    run_sequence,
    semantic_equivalence,
    summarize,
)
from diagnostic import WallClockExceeded, select_alternatives  # noqa: E402


def _protocol():
    return json.loads((STUDY / "protocol_frozen.json").read_text(encoding="utf-8"))


def _row(action, q_hat, *, greedy=False, audited=True):
    return {
        "action": list(action),
        "is_greedy": greedy,
        "q_hat": q_hat,
        "audited": audited and q_hat is not None,
        "capture_ok": q_hat is not None,
        "reason": None if q_hat is not None else "timeout",
        "source": "new",
    }


def _complete_order(order_id, target, advantages):
    labels_source = []
    alternatives = [_row((0,), 0.5, greedy=True)]
    for index, advantage in enumerate(advantages, start=1):
        alternatives.append(_row((index,), 0.5 + advantage))
    state = finalize_state([(0,)] + [(index,) for index in range(1, len(advantages) + 1)], alternatives)
    return {
        "order_id": order_id,
        "target": target,
        "inspected": True,
        "states": [state],
        "states_not_captured_budget": 0,
        "choice_states_found": 1,
    }


class CampaignTests(unittest.TestCase):
    def test_frozen_protocol_matches_the_draft_semantically(self) -> None:
        draft = json.loads((STUDY / "protocol_draft.json").read_text(encoding="utf-8"))
        frozen = _protocol()
        report = semantic_equivalence(draft, frozen)
        self.assertTrue(report["equivalent"])
        self.assertEqual(report["mismatches"], [])
        self.assertNotEqual(file_sha256(STUDY / "protocol_draft.json"), file_sha256(STUDY / "protocol_frozen.json"))
        self.assertIn("el presupuesto truncado se acepta solo en el congelado", report["operational_differences"])
        self.assertFalse(frozen["budget"]["worst_case_fits_in_wall"])
        self.assertEqual(frozen["gate"]["positive_eps"], 1e-9)
        self.assertEqual(frozen["gate"]["min_orders_with_complete_state"], 15)
        self.assertEqual(frozen["gate"]["min_complete_states"], 40)
        self.assertEqual(frozen["preflight_observed"]["continuations"], 4)
        review = (STUDY / "freeze_review.md").read_text(encoding="utf-8")
        self.assertIn(file_sha256(STUDY / "protocol_frozen.json"), review)

    def test_preflight_actions_are_reused_once(self) -> None:
        budget = Budget(_protocol(), preflight_states=2, preflight_continuations=4)
        calls = []

        def run_one(identity):
            calls.append(identity)
            return _row(identity, 0.4)

        reuse = {
            ("00109938", (0,)): {
                "q_hat": 0.67,
                "is_greedy": True,
                "audited": True,
                "capture_ok": True,
                "reason": None,
                "source": "preflight",
            }
        }
        rows = evaluate_planned_actions(
            [(0,), (1,)],
            reuse=reuse,
            order_id="00109938",
            budget=budget,
            now=lambda: 0.0,
            deadline=10.0,
            run_one=run_one,
            greedy_key=(0,),
        )
        self.assertEqual(calls, [(1,)])
        self.assertEqual(budget.continuations_used, 5)
        self.assertEqual(rows[0]["source"], "preflight")
        self.assertEqual(rows[0]["q_hat"], 0.67)
        state = finalize_state([(0,), (1,)], rows)
        self.assertTrue(state["complete"])
        self.assertEqual(len(state["labels"]), 2)

    def test_wall_keeps_partials_and_unknown_returns(self) -> None:
        budget = Budget(_protocol(), preflight_states=2, preflight_continuations=4)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results_partial.json"
            saved = []

            def emit(document):
                path.write_text(json.dumps(document), encoding="utf-8")
                saved.append(document["status"])

            def process(spec):
                if spec["order_id"] == "b":
                    exc = WallClockExceeded("wall_clock")
                    exc.partial = {"order_id": "b", "target": "rollcontainer", "inspected": True, "states": [], "states_not_captured_budget": 0}
                    raise exc
                return {"order_id": spec["order_id"], "target": "euro-pallet", "inspected": True, "states": [], "states_not_captured_budget": 0}

            document = run_sequence(
                [{"order_id": "a"}, {"order_id": "b"}, {"order_id": "c"}],
                process_order=process,
                budget=budget,
                deadline=100.0,
                now=lambda: 0.0,
                emit=emit,
            )
            self.assertEqual(document["status"], "wall_clock")
            self.assertEqual([order["order_id"] for order in document["orders"]], ["a", "b"])
            self.assertEqual(document["pending_order_ids"], ["c"])
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored["orders"][0]["order_id"], "a")
            self.assertTrue(path.is_file())
        output = Path(tempfile.mkdtemp()) / "diagnostic_results"
        output.mkdir()
        with self.assertRaises(FileExistsError):
            directory_must_be_new(output)

    def test_gate_denominators_and_classification(self) -> None:
        gate = _protocol()["gate"]
        orders = []
        for index in range(15):
            orders.append(_complete_order(f"e{index}", "euro-pallet", [0.02]))
        for index in range(25):
            orders.append(_complete_order(f"x{index}", "rollcontainer", [0.02]))
        orders.append(
            {
                "order_id": "absent",
                "target": "euro-pallet",
                "inspected": False,
                "states": [],
                "states_not_captured_budget": 0,
            }
        )
        summary = summarize(orders, wall_seconds=100.0, gate=gate)
        self.assertEqual(summary["evaluable_n"], 40)
        self.assertEqual(summary["complete_states"], 40)
        self.assertEqual(summary["mean_f"], 1.0)
        self.assertAlmostEqual(summary["mean_m"], 0.02)
        self.assertEqual(summary["classification"], "margen_suficiente_para_disenar_el_experimento_de_aprendizaje")
        self.assertFalse(summary["authorizes_training"])
        self.assertIn("absent", summary["orders_not_inspected"])
        self.assertNotIn("absent", [row["order_id"] for row in summary["per_order"] if row["evaluable"]])

        low = summarize([_complete_order(f"e{i}", "euro-pallet", [0.0]) for i in range(40)], wall_seconds=100, gate=gate)
        self.assertEqual(low["classification"], "no_avanzar")
        self.assertEqual(low["mean_f"], 0.0)
        self.assertEqual(low["mean_m"], 0.0)

        incomplete = _complete_order("e0", "euro-pallet", [0.2])
        incomplete["states"][0]["alternatives"].append(_row((9,), None))
        incomplete["states"][0]["complete"] = False
        incomplete["states"][0]["labels"] = []
        unknown = summarize([incomplete], wall_seconds=100, gate=gate)
        self.assertEqual(unknown["unknown_returns"], 1)
        self.assertEqual(unknown["programmed_continuations"], 3)
        self.assertEqual(unknown["classification"], "inconcluso")
        self.assertEqual(unknown["complete_states"], 0)

        boundary = finalize_state([(0,), (1,)], [_row((0,), 0.0, greedy=True), _row((1,), 1e-9)])
        self.assertEqual(boundary["labels"][1]["a_hat"], 1e-9)
        narrow = summarize([{"order_id": "n", "target": "euro-pallet", "inspected": True, "states": [boundary], "states_not_captured_budget": 0, "choice_states_found": 1}], wall_seconds=10, gate=gate)
        self.assertEqual(narrow["mean_m"], 0.0)
        self.assertEqual(narrow["a_hat_distribution"]["zero"], 2)

    def test_alternative_prefix_does_not_depend_on_later_slots(self) -> None:
        from compact_study import build_compact_problem

        sequence = {
            "1": {"sequence": 1, "id": "box", "length/mm": 30, "width/mm": 40, "height/mm": 50, "weight/kg": 1}
        }
        orders = {"S": {"properties": {"target": "euro-pallet"}, "item_sequence": sequence}}
        problem = build_compact_problem(orders, "S")
        from diagnostic import collect_states

        short = collect_states(problem, max_states=1, alternative_limit=2)
        long = collect_states(problem, max_states=1, alternative_limit=4)
        self.assertEqual(short[0]["alternatives"], long[0]["alternatives"][:2])
        self.assertEqual(short[0]["greedy_key"], long[0]["greedy_key"])
        self.assertLessEqual(len(select_alternatives([], None)), 0)

    def test_state_budget_does_not_count_a_reused_state_twice(self) -> None:
        budget = Budget(_protocol(), preflight_states=99, preflight_continuations=4)
        self.assertTrue(admit_state(budget, already_counted=True))
        self.assertEqual(budget.states_used, 99)
        self.assertTrue(admit_state(budget, already_counted=False))
        self.assertFalse(admit_state(budget, already_counted=False))


if __name__ == "__main__":
    unittest.main()
