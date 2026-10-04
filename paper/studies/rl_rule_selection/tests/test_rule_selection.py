"""Pruebas sintéticas del entorno de selección de reglas. No usan pedidos reales."""

from __future__ import annotations

import gc
import sys
import tempfile
import unittest
import weakref
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
TOOLS = STUDY / "tools"
PAPER_TOOLS = STUDY.parents[1] / "tools"
COUNTERFACTUAL = STUDY.parents[1] / "studies" / "counterfactual_ranking" / "tools"
for entry in (str(PAPER_TOOLS), str(COUNTERFACTUAL), str(TOOLS)):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

import torch  # noqa: E402
from audit_internal_solution import audit_document  # noqa: E402
from campaign import recompute_u  # noqa: E402
from compact_study import SUFFIX_REASON, TERMINAL_REASON, build_compact_problem, run_compact_greedy  # noqa: E402
from environment import RuleSelectionEnv  # noqa: E402
from model import GREEDY_LOGIT_BIAS, build_actor, build_critic, greedy_softmax_probability  # noqa: E402
from observation import FEATURE_NAMES, OBS_DIM  # noqa: E402
from preflight import measure_synthetic  # noqa: E402
from rules import current_max_height, propose_rules  # noqa: E402
from run_preflight import main  # noqa: E402


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


def _plan(solution) -> list[tuple]:
    rows = []
    for packed in solution.packed_items:
        rows.append(
            (
                packed.item_id,
                round(float(packed.position.x), 6),
                round(float(packed.position.y), 6),
                round(float(packed.position.z), 6),
                round(float(packed.orientation.length), 6),
                round(float(packed.orientation.width), 6),
                round(float(packed.orientation.height), 6),
            )
        )
    return rows


def _play(problem, action: int) -> RuleSelectionEnv:
    env = RuleSelectionEnv()
    _observation, info = env.reset(problem)
    guard = 0
    while not info["terminated"]:
        _observation, _reward, _terminated, info = env.step(action)
        guard += 1
        if guard > 20:
            raise AssertionError("el episodio no terminó")
    return env


class RuleSelectionTests(unittest.TestCase):
    def test_greedy_matches_current_chooser(self) -> None:
        problem = build_compact_problem(
            _order("G", [("one", 300, 200, 150), ("two", 180, 120, 80), ("three", 90, 70, 40)]),
            "G",
        )
        greedy_solution, _extra = run_compact_greedy(problem)
        env = _play(problem, 0)
        chosen = env.solution(
            algorithm_name="rl_rule_selection",
            display_name="prueba",
            description="prueba",
        )
        self.assertEqual(_plan(chosen), _plan(greedy_solution))

    def test_heights_use_oriented_dimensions(self) -> None:
        problem = build_compact_problem(_order("H", [("tall", 100, 100, 400), ("next", 80, 70, 60)]), "H")
        env = RuleSelectionEnv()
        env.reset(problem)
        item = env._remaining[0]
        options = env._legal(item)
        proposals = propose_rules(options, env.session)
        chosen = proposals[1]["option"].candidate
        tops = [
            float(option.candidate.position.z) + float(option.candidate.dimensions.height)
            for option in options
        ]
        self.assertEqual(float(item.height), 400.0)
        self.assertEqual(float(chosen.dimensions.height), 100.0)
        self.assertEqual(float(chosen.position.z) + float(chosen.dimensions.height), min(tops))
        env.step(2)
        skyline = current_max_height(env.session)
        options = env._legal(env._remaining[0])
        proposals = propose_rules(options, env.session)
        chosen = proposals[2]["option"].candidate
        increases = []
        for option in options:
            top = float(option.candidate.position.z) + float(option.candidate.dimensions.height)
            increases.append(max(skyline, top) - skyline)
        chosen_top = float(chosen.position.z) + float(chosen.dimensions.height)
        self.assertAlmostEqual(max(skyline, chosen_top) - skyline, min(increases))

    def test_rules_share_candidates_and_keep_duplicate_actions(self) -> None:
        problem = build_compact_problem(_order("C", [("cube", 200, 200, 200)]), "C")
        env = RuleSelectionEnv()
        _observation, info = env.reset(problem)
        options = env._legal(env._remaining[0])
        proposals = propose_rules(options, env.session)
        identities = {id(option.candidate) for option in options}
        self.assertEqual([row["action"] for row in proposals], [0, 1, 2])
        self.assertEqual(len(proposals), 3)
        for row in proposals:
            self.assertIn(id(row["option"].candidate), identities)
        self.assertTrue(info["redundancy"]["all_three"])
        geometries = {row["geometry"] for row in info["proposals"]}
        self.assertEqual(len(geometries), 1)
        plans = [
            _plan(
                _play(problem, action).solution(
                    algorithm_name="rl_rule_selection",
                    display_name="p",
                    description="p",
                )
            )
            for action in (0, 1, 2)
        ]
        self.assertEqual(plans[0], plans[1])
        self.assertEqual(plans[0], plans[2])

    def test_observation_ignores_future_and_remaining_count(self) -> None:
        joined = " ".join(FEATURE_NAMES)
        self.assertNotIn("remaining", joined)
        self.assertNotIn("future", joined)
        self.assertEqual(len(FEATURE_NAMES), OBS_DIM)
        short = build_compact_problem(
            _order("S", [("same", 120, 80, 60), ("tail", 50, 50, 50)]),
            "S",
        )
        longer = build_compact_problem(
            _order(
                "L",
                [("same", 120, 80, 60), ("other", 90, 40, 30), ("more", 70, 70, 20), ("last", 30, 30, 30)],
            ),
            "L",
        )
        first, _info = RuleSelectionEnv().reset(short)
        second, _info = RuleSelectionEnv().reset(longer)
        self.assertEqual(first, second)
        self.assertEqual(len(first), OBS_DIM)

    def test_reward_sum_equals_geometric_utilization(self) -> None:
        problem = build_compact_problem(
            _order("U", [("one", 250, 200, 100), ("two", 120, 100, 80)]),
            "U",
        )
        env = RuleSelectionEnv()
        _observation, info = env.reset(problem)
        rewards = []
        while not info["terminated"]:
            _observation, reward, _terminated, info = env.step(0)
            rewards.append(reward)
        capture = env.capture(order_id="U", orders_path=Path("synthetic.json"), orders_sha256="0")
        self.assertAlmostEqual(sum(rewards), env.geometric_utilization())
        self.assertAlmostEqual(sum(rewards), recompute_u(capture))
        self.assertIsNone(capture["physical_stability_verified"])

    def test_stop_and_clean_reset(self) -> None:
        problem = build_compact_problem(
            _order("T", [("fit", 100, 100, 100), ("blocked", 2100, 2100, 2100), ("tail", 50, 50, 50)]),
            "T",
        )
        env = RuleSelectionEnv()
        _observation, info = env.reset(problem)
        self.assertFalse(info["terminated"])
        _observation, reward, terminated, info = env.step(0)
        self.assertGreater(reward, 0)
        self.assertFalse(terminated)
        _observation, reward, terminated, info = env.step(0)
        self.assertEqual(reward, 0.0)
        self.assertTrue(terminated)
        reasons = {item.item_id: item.reason for item in env._unpacked}
        self.assertEqual(reasons["blocked#2"], TERMINAL_REASON)
        self.assertEqual(reasons["tail#3"], SUFFIX_REASON)
        held = weakref.ref(env.session)
        other = build_compact_problem(_order("R", [("only", 80, 80, 80)]), "R")
        env.reset(other)
        gc.collect()
        self.assertIsNone(held())
        self.assertGreaterEqual(env.released_sessions(), 1)
        self.assertEqual(len(env.session.packed), 0)

    def test_capture_is_auditable(self) -> None:
        problem = build_compact_problem(_order("A", [("box", 200, 150, 100), ("next", 80, 60, 40)]), "A")
        env = _play(problem, 1)
        with tempfile.TemporaryDirectory() as directory:
            capture = env.capture(
                order_id="A",
                orders_path=Path(directory) / "orders.json",
                orders_sha256="abc",
            )
        audit = audit_document(capture)
        self.assertTrue(audit["internal_geometry_valid"])
        self.assertEqual(audit["n_overlap_pairs"], 0)
        self.assertEqual(audit["n_boxes_outside_bin"], 0)
        self.assertIsNone(audit["physical_stability_verified"])

    def test_initialization_prefers_greedy_without_historical_weights(self) -> None:
        actor = build_actor()
        critic = build_critic()
        actor_ids = {id(parameter) for parameter in actor.parameters()}
        critic_ids = {id(parameter) for parameter in critic.parameters()}
        self.assertTrue(actor_ids.isdisjoint(critic_ids))
        observation = torch.randn(4, OBS_DIM)
        logits = actor(observation)
        expected = torch.tensor([GREEDY_LOGIT_BIAS, 0.0, 0.0])
        self.assertTrue(torch.allclose(logits, expected.expand_as(logits)))
        self.assertEqual(int(torch.argmax(logits[0]).item()), 0)
        probability = torch.softmax(logits[0], dim=0)[0].item()
        self.assertAlmostEqual(probability, greedy_softmax_probability())

    def test_synthetic_preflight_does_not_pack_real_orders(self) -> None:
        report = measure_synthetic()
        self.assertFalse(report["real_orders_packed"])
        self.assertFalse(report["training_executed"])
        self.assertEqual(len(report["seconds_per_episode"]), 3)
        self.assertGreater(sum(report["decisions_per_episode"]), 0)
        self.assertGreater(report["tracemalloc_peak_bytes"], 0)
        self.assertGreater(report["ppo_update_seconds"], 0)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "preflight.json"
            self.assertEqual(main(["--synthetic", "--output", str(output)]), 0)
            self.assertTrue(output.is_file())
            self.assertEqual(main(["--orders", str(output)]), 2)

    def test_rules_two_and_three_diverge_after_a_tall_placement(self) -> None:
        problem = build_compact_problem(
            _order("D", [("tower", 100, 100, 1500), ("flat", 200, 150, 100)]),
            "D",
        )
        env = RuleSelectionEnv()
        _observation, info = env.reset(problem)
        self.assertEqual(info["proposals"][1]["geometry"], info["proposals"][2]["geometry"])
        env.step(0)
        options = env._legal(env._remaining[0])
        proposals = propose_rules(options, env.session)
        self.assertNotEqual(proposals[1]["geometry"], proposals[2]["geometry"])
        self.assertLess(proposals[2]["candidate_index"], proposals[1]["candidate_index"])
        self.assertEqual(proposals[1]["geometry"][6], 100.0)
        self.assertEqual(proposals[2]["geometry"][6], 150.0)
        self.assertEqual(env.candidate_generations, 2)

    def test_observation_uses_container_scale_and_packed_count(self) -> None:
        from observation import PACKED_SCALE, encode_observation

        class _Weight:
            weight = 1.0

        class _Session:
            packed = [_Weight() for _index in range(60)]

        class _Dims:
            length = 1200.0
            width = 800.0
            height = 2000.0

        class _Container:
            dimensions = _Dims()

        proposals = [{"action": index, "option": None} for index in range(3)]
        observation = encode_observation(
            container=_Container(),
            item=None,
            session=_Session(),
            proposals=proposals,
            skyline=0.0,
            orientations=[],
        )
        self.assertEqual(observation[FEATURE_NAMES.index("n_packed_n")], 60 / PACKED_SCALE)
        self.assertNotEqual(observation[FEATURE_NAMES.index("n_packed_n")], 1.0)
        problem = build_compact_problem(_order("N", [("alpha", 200, 100, 80)]), "N")
        other = build_compact_problem(_order("M", [("beta", 200, 100, 80)]), "M")
        first, info = RuleSelectionEnv().reset(problem)
        second, _info = RuleSelectionEnv().reset(other)
        self.assertEqual(first, second)
        geometry = info["proposals"][0]["geometry"]
        length = float(problem.containers[0].dimensions.length)
        height = float(problem.containers[0].dimensions.height)
        self.assertAlmostEqual(first[FEATURE_NAMES.index("greedy_best_fit_pos_x_n")] * length, geometry[1])
        self.assertAlmostEqual(first[FEATURE_NAMES.index("greedy_best_fit_ori_h_n")] * height, geometry[6])
        self.assertGreater(geometry[6], 0)


if __name__ == "__main__":
    unittest.main()
