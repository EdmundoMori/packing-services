"""Pruebas sintéticas del diagnóstico de conjuntos y de la primera divergencia."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from diagnose_policy_results import (  # noqa: E402
    FEATURE_NAMES,
    classify_pair,
    exclusive_sets,
    first_divergence,
    reconstruct_greedy_index,
    select_extremes,
    volume_gap_explained,
)
from packing_services.online.features import FEATURE_NAMES as SOURCE_FEATURES


def _box(item_id: str, lwh: tuple[float, float, float], flb: tuple[float, float, float], oriented=None):
    return {
        "item_id": item_id,
        "original_lwh_mm": list(lwh),
        "oriented_lwh_mm": list(oriented or lwh),
        "flb_mm": list(flb),
    }


def _zeros(**values: float) -> list[float]:
    row = [0.0] * len(FEATURE_NAMES)
    index = {name: position for position, name in enumerate(FEATURE_NAMES)}
    for name, value in values.items():
        row[index[name]] = value
    return row


class PlacementDiagnosisTests(unittest.TestCase):
    def test_feature_names_match_the_encoder(self):
        self.assertEqual(FEATURE_NAMES, SOURCE_FEATURES)

    def test_equal_plans_have_no_divergence(self):
        plan = [_box("a", (2, 2, 2), (0, 0, 0)), _box("b", (1, 1, 1), (2, 0, 0))]
        self.assertEqual(classify_pair(plan, plan), "planes_iguales")
        divergence = first_divergence(plan, plan)
        self.assertEqual(divergence["kind"], "ninguna")
        self.assertEqual(divergence["prefix_length"], 2)
        self.assertFalse(divergence["causal"])

    def test_same_set_with_different_position(self):
        actor = [_box("a", (2, 2, 2), (0, 0, 0))]
        heuristic = [_box("a", (2, 2, 2), (1, 0, 0))]
        self.assertEqual(classify_pair(actor, heuristic), "mismo_conjunto_geometria_distinta")
        divergence = first_divergence(actor, heuristic)
        self.assertEqual(divergence["kind"], "posicion")
        self.assertEqual(divergence["prefix_length"], 0)
        self.assertEqual(exclusive_sets(actor, heuristic)["actor_only"], {})

    def test_orientation_divergence_keeps_the_same_item(self):
        actor = [_box("a", (4, 2, 1), (0, 0, 0), (4, 2, 1))]
        heuristic = [_box("a", (4, 2, 1), (0, 0, 0), (2, 4, 1))]
        self.assertEqual(first_divergence(actor, heuristic)["kind"], "orientacion")
        self.assertEqual(classify_pair(actor, heuristic), "mismo_conjunto_geometria_distinta")

    def test_identity_divergence_and_exclusive_volume(self):
        actor = [_box("a", (2, 2, 2), (0, 0, 0)), _box("b", (3, 1, 1), (2, 0, 0))]
        heuristic = [_box("a", (2, 2, 2), (0, 0, 0)), _box("c", (1, 1, 1), (2, 0, 0))]
        self.assertEqual(first_divergence(actor, heuristic)["kind"], "identidad")
        self.assertEqual(first_divergence(actor, heuristic)["prefix_length"], 1)
        self.assertEqual(classify_pair(actor, heuristic), "conjunto_distinto")
        volumes = {"a": 8.0, "b": 3.0, "c": 1.0}
        gap = volume_gap_explained(actor, heuristic, volumes)
        self.assertTrue(gap["explained"])
        self.assertEqual(gap["exclusive_volume_gap_mm3"], 2.0)
        self.assertEqual(gap["packed_volume_gap_mm3"], 2.0)

    def test_missing_capture_is_insufficient(self):
        self.assertEqual(classify_pair(None, []), "evidencia_insuficiente")

    def test_extremes_break_ties_by_id_after_the_result(self):
        rows = [
            {"order_id": "b", "delta": 1.0},
            {"order_id": "a", "delta": 1.0},
            {"order_id": "c", "delta": -2.0},
            {"order_id": "d", "delta": -2.0},
        ]
        selected = select_extremes(rows, 2)
        self.assertTrue(selected["selected_after_results"])
        self.assertFalse(selected["confirmatory"])
        self.assertEqual([row["order_id"] for row in selected["improvements"]], ["a", "b"])
        self.assertEqual([row["order_id"] for row in selected["deteriorations"]], ["c", "d"])


class GreedyReconstructionTests(unittest.TestCase):
    def test_unique_rank_selects_the_smaller_key(self):
        rows = [_zeros(rank_0=1.0), _zeros(rank_0=-2.0)]
        found = reconstruct_greedy_index(rows)
        self.assertEqual(found["status"], "comprobable")
        self.assertEqual(found["index"], 1)

    def test_tie_keeps_the_first_saved_row(self):
        rows = [_zeros(rank_0=-1.0, rank_1=4.0), _zeros(rank_0=-1.0, rank_1=4.0)]
        self.assertEqual(reconstruct_greedy_index(rows)["index"], 0)

    def test_preview_or_extra_item_is_not_checkable(self):
        self.assertEqual(
            reconstruct_greedy_index([_zeros(), _zeros(preview_0_l_n=0.2)])["status"],
            "no_comprobable",
        )
        self.assertEqual(
            reconstruct_greedy_index([_zeros(item_l_n=0.1), _zeros(item_l_n=0.2)])["status"],
            "no_comprobable",
        )
        self.assertEqual(
            reconstruct_greedy_index([_zeros(buffer_index_n=0.2), _zeros()])["status"],
            "no_comprobable",
        )


if __name__ == "__main__":
    unittest.main()
