"""Selector compacto: fórmulas, desempate y el recorrido real del worker."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compact_selector import (  # noqa: E402
    CompactScorePolicy,
    choose_top,
    engineering_gate,
    grid_configurations,
    mean_effective,
    score_components,
)
from compact_study import build_compact_problem, run_compact_greedy, run_compact_selector  # noqa: E402
from pilot_execute import invoke_worker  # noqa: E402
from pilot_metrics import evaluate_outcome  # noqa: E402
from pilot_problems import prepare_imports, problem_snapshot  # noqa: E402


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


class _Dims:
    def __init__(self, length: float, width: float, height: float) -> None:
        self.length = length
        self.width = width
        self.height = height


class _Pos:
    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


class _Candidate:
    def __init__(self, rank_key, support, dims, z, bin_index=0) -> None:
        self.rank_key = rank_key
        self.support_ratio = support
        self.dimensions = _Dims(*dims)
        self.position = _Pos(0, 0, z)
        self.bin_index = bin_index


class _Option:
    def __init__(self, candidate) -> None:
        self.candidate = candidate
        self.item = None


class _Box:
    def __init__(self, top: float) -> None:
        self.max_corner = (0.0, 0.0, top)


class _State:
    def __init__(self, height: float, tops: list[float]) -> None:
        self.container = type("C", (), {"dimensions": _Dims(100, 100, height)})()
        self.placed = [_Box(top) for top in tops]


class _Session:
    def __init__(self, height: float, tops: list[float]) -> None:
        self.states = [_State(height, tops)]


class CompactSelectorTests(unittest.TestCase):
    def test_formula_matches_hand_calculation(self) -> None:
        # Contacto 12, superficie 2*(2*3+2*4+3*4)=52, techo 7/10, incremento 2/10, apoyo 0.25.
        scored = score_components(
            rank_key=(-12, 3, 0, 0),
            oriented_lwh=(2, 3, 4),
            z_mm=3,
            support_ratio=0.25,
            bin_height_mm=10,
            current_height_mm=5,
            a=2,
            b=1,
            c=4,
        )
        self.assertIsNotNone(scored)
        self.assertAlmostEqual(scored["contacto_normalizado"], 12 / 52)
        self.assertAlmostEqual(scored["techo_normalizado"], 0.7)
        self.assertAlmostEqual(scored["incremento_altura_normalizado"], 0.2)
        self.assertAlmostEqual(scored["score"], 12 / 52 - 2 * 0.2 - 1 * 0.7 + 4 * 0.25)

    def test_normalization_is_unchanged_when_lengths_scale(self) -> None:
        base = score_components(
            rank_key=(-8, 1, 1, 1),
            oriented_lwh=(2, 3, 4),
            z_mm=1,
            support_ratio=0.5,
            bin_height_mm=20,
            current_height_mm=6,
            a=1,
            b=0.5,
            c=0.25,
        )
        scaled = score_components(
            rank_key=(-8 * 100, 10, 10, 10),
            oriented_lwh=(20, 30, 40),
            z_mm=10,
            support_ratio=0.5,
            bin_height_mm=200,
            current_height_mm=60,
            a=1,
            b=0.5,
            c=0.25,
        )
        self.assertAlmostEqual(base["score"], scaled["score"])

    def test_empty_bin_and_height_increase(self) -> None:
        empty = score_components(
            rank_key=(0, 0, 0, 0),
            oriented_lwh=(2, 2, 2),
            z_mm=0,
            support_ratio=1,
            bin_height_mm=10,
            current_height_mm=0,
            a=1,
            b=0,
            c=0,
        )
        self.assertAlmostEqual(empty["incremento_altura_normalizado"], 0.2)
        self.assertAlmostEqual(empty["techo_normalizado"], 0.2)
        flat = score_components(
            rank_key=(0, 0, 0, 0),
            oriented_lwh=(2, 2, 2),
            z_mm=1,
            support_ratio=1,
            bin_height_mm=10,
            current_height_mm=5,
            a=1,
            b=0,
            c=0,
        )
        self.assertAlmostEqual(flat["incremento_altura_normalizado"], 0.0)
        self.assertAlmostEqual(flat["techo_normalizado"], 0.3)

    def test_non_finite_or_non_positive_denominator_is_rejected(self) -> None:
        self.assertIsNone(
            score_components(
                rank_key=(0, 0, 0, 0),
                oriented_lwh=(0, 2, 2),
                z_mm=0,
                support_ratio=1,
                bin_height_mm=10,
                current_height_mm=0,
                a=0,
                b=0,
                c=0,
            )
        )
        self.assertIsNone(
            score_components(
                rank_key=(float("nan"), 0, 0, 0),
                oriented_lwh=(2, 2, 2),
                z_mm=0,
                support_ratio=1,
                bin_height_mm=10,
                current_height_mm=0,
                a=0,
                b=0,
                c=0,
            )
        )
        self.assertIsNone(
            score_components(
                rank_key=(0, 0, 0, 0),
                oriented_lwh=(2, 2, 2),
                z_mm=0,
                support_ratio=1,
                bin_height_mm=0,
                current_height_mm=0,
                a=0,
                b=0,
                c=0,
            )
        )

    def test_tie_keeps_smaller_rank_key_then_original_index(self) -> None:
        session = _Session(10, [])
        low = _Option(_Candidate((-4, 2, 0, 0), 0.0, (2, 2, 2), 0))
        high = _Option(_Candidate((-4, 0, 0, 0), 0.0, (2, 2, 2), 0))
        same = _Option(_Candidate((-4, 0, 0, 0), 0.0, (2, 2, 2), 0))
        policy = CompactScorePolicy(0, 0, 0)
        chosen = policy.decide([low, high, same], preview=[], remaining_count=99, session=session, constraints=None, mask=None)
        self.assertIs(chosen, high)
        worse = _Option(_Candidate((-3, 0, 0, 0), 1.0, (2, 2, 2), 0))
        self.assertIs(
            policy.decide([high, worse], preview=["futuro"], remaining_count=4, session=session, constraints=None, mask=None),
            high,
        )

    def test_zero_coefficients_match_greedy_and_stop_without_future_items(self) -> None:
        orders = _order(
            "S",
            "euro-pallet",
            [("a", 300, 200, 150), ("b", 280, 180, 120), ("c", 250, 160, 100), ("d", 5000, 10, 10), ("e", 40, 40, 40)],
        )
        problem = build_compact_problem(orders, "S")
        greedy, greedy_diag = run_compact_greedy(problem)
        selected, selected_diag = run_compact_selector(problem, 0, 0, 0)
        greedy_rows = [
            (item.item_id, item.position.x, item.position.y, item.position.z, item.orientation.length, item.orientation.width, item.orientation.height)
            for item in greedy.packed_items
        ]
        selected_rows = [
            (item.item_id, item.position.x, item.position.y, item.position.z, item.orientation.length, item.orientation.width, item.orientation.height)
            for item in selected.packed_items
        ]
        self.assertEqual(selected_rows, greedy_rows)
        self.assertEqual(
            [(item.item_id, item.reason) for item in selected.unpacked_items],
            [(item.item_id, item.reason) for item in greedy.unpacked_items],
        )
        self.assertTrue(selected_diag["stopped_early"])
        self.assertTrue(all(step["preview_ids"] == [step["item_id"]] for step in selected_diag["steps"]))
        self.assertNotIn("e#5", [step["item_id"] for step in selected_diag["steps"]])
        self.assertEqual(len(grid_configurations()), 32)

    def test_failures_remain_in_the_mean_and_top3_ties_are_stable(self) -> None:
        self.assertEqual(mean_effective([0.5, 0.0]), 0.25)
        rows = [
            {"a": 1, "b": 0, "c": 0, "mean_effective_u_geom": 0.4},
            {"a": 0, "b": 0, "c": 0.25, "mean_effective_u_geom": 0.4},
            {"a": 0, "b": 0, "c": 0, "mean_effective_u_geom": 0.2},
            {"a": 2, "b": 2, "c": 0.25, "mean_effective_u_geom": 0.4},
        ]
        top = choose_top(rows, 3)
        self.assertEqual([(row["a"], row["b"], row["c"]) for row in top], [(0, 0, 0.25), (1, 0, 0), (2, 2, 0.25)])
        gate = engineering_gate(0.004, 0.01, 0.01)
        self.assertFalse(gate["passed"])
        self.assertFalse(engineering_gate(0.005, 0.0, -0.001)["passed"])
        self.assertTrue(engineering_gate(0.005, 0.0, 0.0)["passed"])

    def test_real_worker_payload_is_accepted(self) -> None:
        orders = _order("S", "euro-pallet", [("box", 200, 150, 100), ("next", 180, 120, 80)])
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            dataset = root / "orders.json"
            dataset.write_text(json.dumps(orders), encoding="utf-8")
            outcome = invoke_worker(
                {
                    "order_id": "S",
                    "dataset": str(dataset),
                    "dataset_sha256": "0" * 64,
                    "coefficients": {"a": 0, "b": 0, "c": 0},
                },
                case_dir=root / "case",
                timeout_s=60,
                command=[
                    sys.executable,
                    str(TOOLS / "compact_worker.py"),
                    "--job",
                    str(root / "case" / "job.json"),
                    "--result",
                    str(root / "case" / "worker_result.partial"),
                ],
            )
        self.assertEqual(outcome["status"], "ok")
        capture = outcome["capture"]
        self.assertEqual(capture["method"], "compact_selector")
        self.assertEqual(capture["recipe"]["coefficients"], {"a": 0.0, "b": 0.0, "c": 0.0})
        self.assertEqual(capture["recipe"]["algorithm"], "compact_selector")
        self.assertIsNone(capture["physical_stability_verified"])
        self.assertFalse(capture["recipe"]["observes_future_item_dimensions"])
        prepare_imports()
        problem = build_compact_problem(orders, "S")
        snapshot = problem_snapshot(problem)
        snapshot["algorithm"] = "compact_selector"
        scored = evaluate_outcome(
            outcome,
            order_id="S",
            method="compact_selector",
            target="euro-pallet",
            container_volume_mm3=snapshot["containers"][0]["volume_mm3"],
            run_id="17-synthetic",
            snapshot=snapshot,
        )
        self.assertEqual(scored["failure_types"], [])
        self.assertGreater(scored["effective_u_geom"], 0)


if __name__ == "__main__":
    unittest.main()
