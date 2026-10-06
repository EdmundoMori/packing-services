"""Pruebas sintéticas del diagnóstico del teacher. No ejecutan los 50 pedidos."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pilot_metrics import evaluate_outcome  # noqa: E402
from pilot_problems import prepare_imports  # noqa: E402
from teacher_probe import (  # noqa: E402
    PACKING_DIR,
    ProbeError,
    assess_comparator,
    build_teacher_problem,
    capture_teacher_case,
    compare_teacher_to_heuristic,
    development_orders,
    execute_teacher_cases,
    run_teacher_rollout,
    teacher_decision,
)


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


class TeacherBehaviorTests(unittest.TestCase):
    def test_simulation_restores_and_commits_one_legal_candidate(self):
        prepare_imports()
        from packing_services.algorithms._constructive import order_items
        from packing_services.domain.enums import SortStrategy
        from packing_services.online.budget import InformationBudget
        from packing_services.online.mask import ValidatorMask
        from packing_services.online.params import resolve_selection, support_threshold
        from packing_services.online.session import ExtremePointOnlineSession
        from packing_services.online.types import StepOption
        from teacher_probe import _fingerprint

        orders = _order("S", "euro-pallet", [("a", 200, 150, 100), ("b", 180, 120, 80)])
        problem = build_teacher_problem(orders, "S")
        constraints = problem.constraints
        params = dict(problem.algorithm.parameters)
        session = ExtremePointOnlineSession(problem.containers, selection=resolve_selection(params))
        mask = ValidatorMask(problem, min_support_ratio=support_threshold(params, constraints.basic_stability))
        remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)
        options = []
        for buffer_index, item in enumerate(remaining[:1]):
            for candidate in session.candidates(item, constraints):
                if mask.allows(candidate, item, session, constraints):
                    options.append(StepOption(item=item, candidate=candidate, buffer_index=buffer_index))
        self.assertGreater(len(options), 1)
        before = _fingerprint(session)
        chosen, _fallback = teacher_decision(
            options,
            remaining=remaining,
            session=session,
            constraints=constraints,
            mask=mask,
        )
        self.assertEqual(_fingerprint(session), before)
        self.assertEqual(len(session.packed), 0)
        self.assertIsNotNone(chosen)
        self.assertIn(options[int(chosen)].candidate, [option.candidate for option in options])
        session.commit(options[int(chosen)].candidate, options[int(chosen)].item)
        self.assertEqual(len(session.packed), 1)
        self.assertEqual(session.packed[0].item_id, options[int(chosen)].item.id)
        solution, diagnostics = run_teacher_rollout(problem)
        self.assertEqual(diagnostics["decisions"], len(solution.packed_items))
        self.assertGreaterEqual(diagnostics["multi_candidate_steps"], 1)
        self.assertIsNone(diagnostics["physical_stability_verified"])

    def test_discard_drops_the_oldest_item_and_continues(self):
        orders = _order("S", "euro-pallet", [("huge", 3000, 3000, 3000), ("small", 100, 80, 60)])
        problem = build_teacher_problem(orders, "S")
        solution, diagnostics = run_teacher_rollout(problem)
        self.assertEqual(diagnostics["discards"], 1)
        self.assertEqual(len(solution.unpacked_items), 1)
        self.assertIn("huge", solution.unpacked_items[0].item_id)
        self.assertEqual(solution.unpacked_items[0].reason, "No hay colocación legal con el presupuesto de información actual")
        self.assertEqual(len(solution.packed_items), 1)
        self.assertIn("small", solution.packed_items[0].item_id)

    def test_fallback_is_recorded_without_keeping_the_simulation(self):
        orders = _order("S", "120,120,120", [("small", 50, 50, 50), ("big", 100, 100, 100)])
        problem = build_teacher_problem(orders, "S")
        solution, diagnostics = run_teacher_rollout(problem)
        self.assertGreaterEqual(diagnostics["fallback_steps"], 1)
        self.assertEqual([item.item_id for item in solution.packed_items][0].startswith("small"), True)
        self.assertIsNone(solution.execution_metadata.parameters.get("model_path"))

    def test_capture_matches_the_independent_snapshot(self):
        orders = _order("S", "euro-pallet", [("a", 200, 150, 100), ("b", 180, 120, 80)])
        dataset = Path("/tmp/teacher-probe-synthetic.json")
        snapshot, document, diagnostics = capture_teacher_case(orders, "S", dataset_path=dataset)
        self.assertIsNone(document["physical_stability_verified"])
        self.assertTrue(document["placements"])
        self.assertIn("oriented_lwh_mm", document["placements"][0])
        row = evaluate_outcome(
            {"status": "ok", "attempts": 1, "capture": document, "duration_seconds": 0.1, "diagnostics": diagnostics},
            order_id="S",
            method="teacher",
            target="euro-pallet",
            container_volume_mm3=snapshot["containers"][0]["volume_mm3"],
            run_id="synthetic",
            snapshot=snapshot,
        )
        self.assertNotIn("input_mismatch", row["failure_types"])
        self.assertIsNone(row["physical_stability_verified"])
        self.assertGreater(row["effective_u_geom"], 0)

    def test_timeout_continues_with_zero_utility(self):
        def worker(job):
            if job["order_id"] == "A":
                raise subprocess.TimeoutExpired(cmd="teacher", timeout=0.1)
            raise RuntimeError("caída")

        snapshot = {
            "containers": [{"volume_mm3": 1920000000.0}],
            "model_path": None,
            "algorithm": "teacher_receding_horizon_ep",
        }
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            rows = execute_teacher_cases(
                [
                    {"order_id": "A", "target": "euro-pallet", "dataset": "/tmp/none.json"},
                    {"order_id": "B", "target": "euro-pallet", "dataset": "/tmp/none.json"},
                ],
                {"A": snapshot, "B": snapshot},
                Path(folder),
                timeout_s=0.1,
                worker=worker,
            )
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["effective_u_geom"] == 0.0 for row in rows))
        self.assertEqual(rows[0]["worker_status"], "timeout")
        self.assertEqual(rows[1]["worker_status"], "crash")


_PAPER = Path(__file__).resolve().parents[1]
_PROTOCOL_14 = _PAPER / "protocols" / "14_teacher_probe.json"


class ComparatorTests(unittest.TestCase):
    def test_published_heuristic_results_can_be_reused(self):
        if not _PROTOCOL_14.is_file():
            raise FileNotFoundError(
                f"Protocolo histórico obligatorio ausente: {_PROTOCOL_14}"
            )
        if not PACKING_DIR.is_dir():
            raise FileNotFoundError(
                "Artefacto histórico obligatorio ausente (packing ablación 11): "
                f"{PACKING_DIR}"
            )
        protocol = json.loads(_PROTOCOL_14.read_text(encoding="utf-8"))
        report = assess_comparator(
            PACKING_DIR,
            development_orders(),
            expected_digest=protocol["comparator"]["digest"],
            expected_code=protocol["comparator"]["code_sha256"],
        )
        self.assertEqual(report["n"], 50)
        self.assertEqual(report["issues"], [])
        self.assertTrue(report["accepted"])
        self.assertEqual(protocol["comparator"]["reuse"], "accepted")
        self.assertFalse(protocol["executed"])

    def test_reuse_is_rejected_when_the_contract_differs(self):
        orders = [{"order_id": "00100084", "target": "euro-pallet"}]
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            root = Path(folder)
            source = PACKING_DIR / "cases" / "heuristic__00100084"
            case = root / "cases" / "heuristic__00100084"
            case.mkdir(parents=True)
            for name in ("result.json", "input.json", "audit.json", "capture.json"):
                (case / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
            (root / "manifest.json").write_text((PACKING_DIR / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
            snapshot = json.loads((case / "input.json").read_text(encoding="utf-8"))
            snapshot["algorithm"] = "otro"
            (case / "input.json").write_text(json.dumps(snapshot), encoding="utf-8")
            report = assess_comparator(root, orders)
            self.assertFalse(report["accepted"])
            self.assertTrue(any("GreedyBestFit" in issue for issue in report["issues"]))

    def test_mean_keeps_a_failure_in_the_denominator(self):
        orders = [
            {"order_id": "A", "target": "euro-pallet"},
            {"order_id": "B", "target": "rollcontainer"},
        ]
        teacher = [
            {"order_id": "A", "effective_u_geom": 0.4, "failure": False, "failure_types": [], "fallback_steps": 1, "multi_candidate_steps": 2},
            {"order_id": "B", "effective_u_geom": 0.0, "failure": True, "failure_types": ["method_failure"], "fallback_steps": 0, "multi_candidate_steps": 0},
        ]
        heuristic = [
            {"order_id": "A", "effective_u_geom": 0.2, "failure": False, "failure_types": []},
            {"order_id": "B", "effective_u_geom": 0.2, "failure": False, "failure_types": []},
        ]
        summary = compare_teacher_to_heuristic(teacher, heuristic, orders)
        self.assertAlmostEqual(summary["mean_teacher_minus_greedy"], 0.0)
        self.assertEqual(summary["wins"], 1)
        self.assertEqual(summary["losses"], 1)
        self.assertEqual(summary["orders_with_fallback"], 1)
        self.assertFalse(summary["confirmatory"])
        self.assertTrue(summary["not_upper_bound"])
        with self.assertRaises(ProbeError):
            compare_teacher_to_heuristic(teacher, heuristic, orders + [{"order_id": "C", "target": "euro-pallet"}])


if __name__ == "__main__":
    unittest.main()
