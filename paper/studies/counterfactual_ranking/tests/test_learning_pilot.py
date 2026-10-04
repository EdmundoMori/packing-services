"""Pruebas del piloto de aprendizaje. No leen el test final ni entrenan."""

from __future__ import annotations

import hashlib
import json
import math
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

from actor_features import FEATURE_DIM, FEATURE_NAMES, encode_candidate  # noqa: E402
from compact_study import build_compact_problem  # noqa: E402
from diagnostic import WallClockExceeded, _legal_options, _setup  # noqa: E402
from label_campaign import (  # noqa: E402
    LabelBudget,
    complete_state,
    learning_rows,
    run_label_sequence,
)
from label_sampling import quantile_indices, unique_preserving_order  # noqa: E402
from model_spec import TRAINING_CONFIG, adam_for, build_actor  # noqa: E402
from objectives import (  # noqa: E402
    apply_normalization,
    classification_loss,
    classification_target,
    fit_normalization,
    mean_state_loss,
    preference_loss,
)
from campaign import recompute_u  # noqa: E402
from label_campaign import label_selected_states, collect_choice_states  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402


def _order(order_id: str, items: list[tuple[str, int, int, int]]) -> dict:
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
    return {order_id: {"properties": {"target": "euro-pallet"}, "item_sequence": sequence}}


class LearningPilotTests(unittest.TestCase):
    def test_features_ignore_the_hidden_future(self) -> None:
        banned = {"remaining_count", "preview", "rank_key", "q_hat", "order_id", "buffer_index", "suffix"}
        self.assertTrue(banned.isdisjoint(encode_candidate.__code__.co_names))
        early = _order("A", [("box", 30, 40, 50), ("next", 20, 20, 20), ("tail", 10, 10, 10)])
        other = _order("B", [("box", 30, 40, 50), ("next", 80, 15, 90), ("tail", 70, 70, 12)])
        problem_a = build_compact_problem(early, "A")
        problem_b = build_compact_problem(other, "B")
        session_a, mask_a, _policy_a, _budget_a, remaining_a = _setup(problem_a)
        session_b, mask_b, _policy_b, _budget_b, remaining_b = _setup(problem_b)
        options_a = _legal_options(session_a, remaining_a[0], problem_a.constraints, mask_a)
        options_b = _legal_options(session_b, remaining_b[0], problem_b.constraints, mask_b)
        self.assertGreaterEqual(len(options_a), 1)
        self.assertEqual(len(options_a), len(options_b))
        for left, right in zip(options_a, options_b):
            self.assertEqual(
                encode_candidate(session_a, remaining_a[0], left.candidate),
                encode_candidate(session_b, remaining_b[0], right.candidate),
            )

    def test_orientation_and_used_height(self) -> None:
        problem = build_compact_problem(
            _order("H", [("box", 30, 40, 50), ("next", 30, 40, 50)]),
            "H",
        )
        session, mask, policy, budget, remaining = _setup(problem)
        current = remaining[0]
        options = _legal_options(session, current, problem.constraints, mask)
        container = session.states[0].container
        rotated = next(
            option for option in options if abs(option.candidate.dimensions.height - current.height) > 1e-6
        )
        vector = encode_candidate(session, current, rotated.candidate)
        by_name = dict(zip(FEATURE_NAMES, vector))
        self.assertEqual(len(vector), FEATURE_DIM)
        self.assertAlmostEqual(by_name["ori_h_n"], rotated.candidate.dimensions.height / container.height)
        self.assertAlmostEqual(by_name["ori_l_n"], rotated.candidate.dimensions.length / container.length)
        self.assertAlmostEqual(by_name["pos_z_n"], rotated.candidate.position.z / container.height)
        self.assertNotAlmostEqual(by_name["ori_h_n"], current.height / container.height)
        self.assertEqual(by_name["used_height_n"], 0.0)
        self.assertEqual(budget.window(2), (1, 1))
        chosen = policy.decide(
            options,
            preview=remaining[:1],
            remaining_count=0,
            session=session,
            constraints=problem.constraints,
            mask=mask,
        )
        session.commit(chosen.candidate, chosen.item)
        placed_height = max(float(box.max_corner[2]) for box in session.states[0].placed)
        later = _legal_options(session, remaining[1], problem.constraints, mask)[0]
        later_vector = encode_candidate(session, remaining[1], later.candidate)
        self.assertAlmostEqual(later_vector[FEATURE_NAMES.index("used_height_n")], placed_height / container.height)
        self.assertNotIn(budget.window(1), ())

    def test_classification_ties_are_uniform(self) -> None:
        self.assertEqual(classification_target([0.1, 0.2, 0.2]), [0.0, 0.5, 0.5])
        self.assertEqual(classification_target([0.0, 1e-9]), [0.5, 0.5])
        self.assertEqual(classification_target([0.0, 2e-9]), [0.0, 1.0])
        loss = classification_loss([0.0, 0.0, 0.0], [0.1, 0.2, 0.2])
        self.assertAlmostEqual(loss, -math.log(1.0 / 3.0))

    def test_preference_direction_weights_and_ties(self) -> None:
        self.assertAlmostEqual(preference_loss([0.0, 0.0], [0.2, 0.5]), math.log(2.0))
        self.assertAlmostEqual(preference_loss([1.0, 0.0], [0.2, 0.2]), 1.0)
        self.assertEqual(preference_loss([0.0], [0.4]), 0.0)
        mixed = preference_loss([0.0, 0.0, 0.0], [0.0, 0.0, 0.3])
        self.assertGreater(mixed, 0.0)
        self.assertLess(preference_loss([0.0, 1.0], [0.0, 1.0]), preference_loss([1.0, 0.0], [0.0, 1.0]))
        weighted = preference_loss([2.0, 0.0, 0.0], [0.0, 1.0, 3.0])
        softplus = math.log1p(math.exp(2.0))
        expected = (1.0 * softplus + 3.0 * softplus + 2.0 * math.log(2.0)) / 6.0
        self.assertAlmostEqual(weighted, expected)

    def test_states_have_equal_weight(self) -> None:
        self.assertEqual(mean_state_loss([1.0, 3.0]), 2.0)
        short = classification_loss([0.0, 0.0], [0.0, 1.0])
        long = classification_loss([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])
        self.assertNotEqual(len([0, 1]), len([0, 1, 2, 3]))
        self.assertEqual(mean_state_loss([short, long]), (short + long) / 2)

    def test_quantiles_drop_duplicates_without_replacement(self) -> None:
        self.assertEqual(quantile_indices(0), [])
        self.assertEqual(quantile_indices(3), [0, 1, 2])
        self.assertEqual(quantile_indices(4), [0, 1, 2, 3])
        self.assertEqual(quantile_indices(5), [0, 1, 3, 4])
        self.assertEqual(unique_preserving_order([0, 2, 2, 5]), [0, 2, 5])
        for count in range(0, 40):
            indices = quantile_indices(count)
            self.assertEqual(indices, list(dict.fromkeys(indices)))
            self.assertTrue(all(0 <= index < count for index in indices))

    def test_normalization_uses_only_train_rows(self) -> None:
        stats = fit_normalization([[0.0, 1.0], [0.0, 3.0]])
        self.assertEqual(stats["mean"], [0.0, 2.0])
        self.assertEqual(stats["scale"], [1.0, 1.0])
        self.assertEqual(apply_normalization([5.0, 3.0], stats), [5.0, 1.0])
        untouched = fit_normalization([[0.0, 1.0], [0.0, 3.0]])
        self.assertEqual(untouched["mean"], stats["mean"])

    def test_restore_capture_and_audit_on_a_synthetic_order(self) -> None:
        orders = _order("S", [("box", 30, 40, 50), ("next", 25, 35, 45), ("later", 20, 20, 20)])
        problem = build_compact_problem(orders, "S")
        snapshot = problem_snapshot(problem)
        found = collect_choice_states(problem, deadline=None, alternative_limit=2)
        self.assertGreaterEqual(len(found), 1)
        protocol = {
            "label_budget": {
                "max_states": 4,
                "max_continuations": 8,
                "continuation_timeout_seconds": 30,
                "capture_and_audit_timeout_seconds": 30,
                "wall_seconds": 60,
            }
        }
        budget = LabelBudget(protocol)
        states = label_selected_states(
            problem,
            snapshot,
            found[:1],
            dataset="synthetic",
            dataset_sha256="0" * 64,
            order_id="S",
            budget=budget,
            deadline=time_deadline(),
            now=time_now(),
        )
        self.assertTrue(states[0]["complete"])
        for row in states[0]["alternatives"]:
            recomputed = recompute_u(row["capture"])
            self.assertIsNotNone(recomputed)
            self.assertEqual(recomputed, row["q_hat"])
            self.assertIsNone(row["capture"].get("physical_stability_verified"))
            self.assertEqual(len(row["features"]), 17)
        self.assertNotIn("suffix_ids_not_an_actor_input", states[0]["alternatives"][0])

    def test_incomplete_states_are_excluded(self) -> None:
        order = {
            "split": "train",
            "order_id": "1",
            "target": "euro-pallet",
            "states": [
                {
                    "choice_index": 0,
                    "eligible_for_learning": False,
                    "complete": False,
                    "incomplete_reasons": ["timeout"],
                    "alternatives": [{"action": [0], "features": [0.0] * 17, "q_hat": None}],
                },
                {
                    "choice_index": 1,
                    "eligible_for_learning": True,
                    "complete": True,
                    "alternatives": [{"action": [1], "features": [1.0] * 17, "q_hat": 0.4}],
                },
            ],
        }
        rows = learning_rows([order], split="train")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["q_hat"], 0.4)
        self.assertFalse(complete_state(order["states"][0]["alternatives"]))

    def test_wall_clock_keeps_partials(self) -> None:
        protocol = {
            "label_budget": {
                "max_states": 144,
                "max_continuations": 576,
                "continuation_timeout_seconds": 60,
                "capture_and_audit_timeout_seconds": 60,
                "wall_seconds": 14400,
            }
        }
        budget = LabelBudget(protocol)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results_partial.json"

            def emit(document: dict) -> None:
                path.write_text(json.dumps(document), encoding="utf-8")

            def process(spec: dict) -> dict:
                if spec["order_id"] == "b":
                    exc = WallClockExceeded("wall_clock")
                    exc.partial = {"order_id": "b", "split": "train", "states": [{"complete": False}]}
                    raise exc
                return {"order_id": spec["order_id"], "split": "train", "states": []}

            document = run_label_sequence(
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
            self.assertTrue(path.is_file())

    def test_actor_init_is_shared_by_seed_and_does_not_train(self) -> None:
        left = build_actor(11)
        right = build_actor(11)
        other = build_actor(23)
        self.assertTrue(torch_equal(left[0].weight, right[0].weight))
        self.assertFalse(torch_equal(left[0].weight, other[0].weight))
        self.assertEqual(float(left[2].weight.abs().sum()), 0.0)
        self.assertEqual(float(left[2].bias.abs().sum()), 0.0)
        optimizer = adam_for(left)
        self.assertEqual(optimizer.defaults["lr"], 0.001)
        self.assertEqual(optimizer.defaults["weight_decay"], 1e-4)
        self.assertEqual(TRAINING_CONFIG["epochs"], 40)
        self.assertEqual(TRAINING_CONFIG["seeds"], [11, 23, 37])
        self.assertFalse(TRAINING_CONFIG["training_executed_by_this_module"])

    def test_frozen_protocol_keeps_the_selected_orders(self) -> None:
        protocol = json.loads((STUDY / "learning_protocol_frozen.json").read_text(encoding="utf-8"))
        draft = json.loads((STUDY / "learning_protocol_draft.json").read_text(encoding="utf-8"))
        diagnostic = json.loads((STUDY / "sample_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(protocol["status"], "congelado_para_generar_etiquetas")
        self.assertFalse(protocol["training"])
        self.assertFalse(protocol["authorizes_training"])
        self.assertNotIn("signo cambia", json.dumps(protocol, ensure_ascii=False))
        ids = []
        for split in ("train", "development"):
            for target in ("euro-pallet", "rollcontainer"):
                protocol_ids = [row["order_id"] for row in protocol["splits"][target][split]]
                draft_ids = [row["order_id"] for row in draft["splits"][target][split]]
                self.assertEqual(protocol_ids, draft_ids)
                for row in protocol["splits"][target][split]:
                    ids.append(row["order_id"])
                    digest = hashlib.sha256(f"counterfactual-learn-v1|20261003|{row['order_id']}".encode()).hexdigest()
                    self.assertEqual(digest, row["selection_hash"])
        self.assertEqual(len(ids), 36)
        self.assertTrue(set(ids).isdisjoint(diagnostic["execution_order"]))
        signatures = [row["signature"] for target in protocol["splits"].values() for split in target.values() for row in split]
        self.assertEqual(len(signatures), len(set(signatures)))


def time_now():
    import time

    return time.perf_counter


def time_deadline() -> float:
    import time

    return time.perf_counter() + 30.0


def torch_equal(left, right) -> bool:
    return bool((left == right).all())


if __name__ == "__main__":
    unittest.main()
