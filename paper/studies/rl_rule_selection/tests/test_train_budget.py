"""Pruebas del presupuesto reducido. No usan pedidos reales ni el test final."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import torch

STUDY = Path(__file__).resolve().parents[1]
TOOLS = STUDY / "tools"
for entry in (str(TOOLS),):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

from model import build_actor, build_critic, build_optimizer  # noqa: E402
from observation import OBS_DIM  # noqa: E402
from ppo_math import (  # noqa: E402
    DECISIONS_PER_SEED,
    EPOCHS,
    MINIBATCH,
    ROLLOUT_DECISIONS,
    ROLLOUTS_PER_SEED,
    VALUE_CLIPPING,
)
from train_loop import (  # noqa: E402
    apply_update,
    collect_rollout,
    iter_orders,
    load_actor,
    logits_of,
    rollout_tensors,
    run_budget,
    save_checkpoint,
)


class FixedValue(torch.nn.Module):
    def forward(self, observation: torch.Tensor) -> torch.Tensor:
        return torch.full((observation.shape[0], 1), 0.4)


class ScriptedEnv:
    def __init__(self, length: int, *, distinct: bool = True) -> None:
        self.length = length
        self.left = length
        self.calls = 0

    def step(self, action: int):
        self.calls += 1
        self.left -= 1
        terminated = self.left == 0
        placed = not terminated
        return (
            [0.0] * OBS_DIM,
            0.1,
            terminated,
            {"placed": placed, "decision_redundancy": {"all_three": False}},
        )


class BudgetTests(unittest.TestCase):
    def test_exactly_twelve_rollouts_and_6144_decisions(self) -> None:
        actor = build_actor()
        critic = build_critic()
        optimizer = build_optimizer(list(actor.parameters()) + list(critic.parameters()))
        self.assertEqual(logits_of(actor, [0.0] * OBS_DIM), [1.0, 0.0, 0.0])
        holder = {"env": None}

        def start_episode() -> dict:
            env = ScriptedEnv(4)
            holder["env"] = env
            return {
                "env": env,
                "order_id": "00000001",
                "target": "euro-pallet",
                "n_items": 4,
                "observation": [0.0] * OBS_DIM,
                "terminated": False,
            }

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint_last.pt"
            summary = run_budget(
                seed=101,
                actor=actor,
                critic=critic,
                optimizer=optimizer,
                live={"env": None, "terminated": True},
                start_episode=start_episode,
                deadline=1e18,
                clock=lambda: 0.0,
                on_update=lambda record: None,
                on_episode=lambda record: None,
                checkpoint_path=path,
            )
            self.assertEqual(summary["decisions"], DECISIONS_PER_SEED)
            self.assertEqual(summary["decisions"], 6144)
            self.assertEqual(summary["updates"], ROLLOUTS_PER_SEED)
            self.assertEqual(summary["updates"], 12)
            self.assertEqual(summary["adam_steps"], 12 * EPOCHS * (ROLLOUT_DECISIONS // MINIBATCH))
            self.assertEqual(summary["adam_steps"], 192)
            self.assertEqual(summary["status"], "completa")
            self.assertTrue(summary["equal_budget"])
            self.assertEqual(summary["distinct_proposal_decisions"], 4608)
            loaded = load_actor(path)
            self.assertEqual(logits_of(loaded, [0.1] * OBS_DIM), logits_of(actor, [0.1] * OBS_DIM))

    def test_one_update_counts_sixteen_minibatches(self) -> None:
        actor = build_actor()
        critic = build_critic()
        optimizer = build_optimizer(list(actor.parameters()) + list(critic.parameters()))
        count = ROLLOUT_DECISIONS
        batch = {
            "observation": torch.zeros(count, OBS_DIM),
            "action": torch.zeros(count, dtype=torch.long),
            "reward": torch.zeros(count),
            "old_log_prob": torch.full((count,), -0.5),
            "value": torch.zeros(count),
            "returns": torch.zeros(count),
            "advantage": torch.zeros(count),
        }
        metrics = apply_update(actor, critic, optimizer, batch, torch.Generator().manual_seed(101))
        self.assertEqual(metrics["adam_steps"], EPOCHS * (ROLLOUT_DECISIONS // MINIBATCH))
        self.assertEqual(metrics["minibatches"], 16)
        self.assertFalse(VALUE_CLIPPING)
        with self.assertRaises(ValueError):
            short = {key: value[:511] for key, value in batch.items()}
            apply_update(actor, critic, optimizer, short, torch.Generator().manual_seed(1))

    def test_order_calendar_is_a_reproducible_permutation(self) -> None:
        ids = [f"{index:08d}" for index in (8, 1, 3, 7, 2, 5, 4, 6)]
        lengths = {order_id: index for index, order_id in enumerate(reversed(ids))}
        first_generator = torch.Generator().manual_seed(101)
        second_generator = torch.Generator().manual_seed(101)
        first_schedule = iter_orders(ids, first_generator)
        second_schedule = iter_orders(ids, second_generator)
        cycle = [next(first_schedule) for _index in range(8)]
        again = [next(second_schedule) for _index in range(8)]
        self.assertEqual(cycle, again)
        self.assertEqual(sorted(cycle), sorted(ids))
        self.assertNotEqual(cycle, sorted(ids, key=lambda order_id: (lengths[order_id], order_id)))
        self.assertNotEqual(cycle, sorted(ids, key=lambda order_id: lengths[order_id]))

    def test_bootstrap_and_episode_continuity(self) -> None:
        env = ScriptedEnv(30)
        actor = build_actor()
        critic = FixedValue()
        live = {
            "env": env,
            "order_id": "00000009",
            "target": "rollcontainer",
            "n_items": 30,
            "observation": [0.0] * OBS_DIM,
            "terminated": False,
            "episode_steps": 0,
            "episode_placed": 0,
            "episode_distinct": 0,
        }

        def start_episode():
            raise AssertionError("el episodio abierto no debe reiniciarse")

        first = collect_rollout(
            live,
            actor,
            critic,
            torch.Generator().manual_seed(101),
            n_steps=10,
            deadline=1e18,
            clock=lambda: 0.0,
            start_episode=start_episode,
        )
        self.assertTrue(first["complete"])
        self.assertTrue(first["rows"][-1]["truncated"])
        self.assertFalse(first["rows"][-1]["terminated"])
        self.assertIs(live["env"], env)
        self.assertEqual(env.left, 20)
        self.assertEqual(live["order_id"], "00000009")
        batch = rollout_tensors(actor, critic, first["rows"], live)
        self.assertAlmostEqual(float(batch["returns"][-1]), 0.5)
        second = collect_rollout(
            live,
            actor,
            critic,
            torch.Generator().manual_seed(101),
            n_steps=10,
            deadline=1e18,
            clock=lambda: 0.0,
            start_episode=start_episode,
        )
        self.assertIs(second and live["env"], env)
        self.assertEqual(env.left, 10)
        finished = ScriptedEnv(2)
        done = {
            "env": finished,
            "order_id": "00000009",
            "target": "rollcontainer",
            "n_items": 2,
            "observation": [0.0] * OBS_DIM,
            "terminated": False,
            "episode_steps": 0,
            "episode_placed": 0,
            "episode_distinct": 0,
        }
        closed = collect_rollout(
            done,
            actor,
            critic,
            torch.Generator().manual_seed(7),
            n_steps=2,
            deadline=1e18,
            clock=lambda: 0.0,
            start_episode=start_episode,
        )
        self.assertTrue(closed["rows"][-1]["terminated"])
        self.assertFalse(closed["rows"][-1]["truncated"])
        closed_batch = rollout_tensors(actor, critic, closed["rows"], done)
        self.assertAlmostEqual(float(closed_batch["returns"][-1]), 0.1)
        self.assertAlmostEqual(float(closed_batch["returns"][0]), 0.2)

    def test_clock_cutoff_keeps_partial_without_update(self) -> None:
        actor = build_actor()
        critic = build_critic()
        optimizer = build_optimizer(list(actor.parameters()) + list(critic.parameters()))
        calls = {"n": 0}
        episodes = []

        def clock() -> float:
            return calls["n"]

        def start_episode() -> dict:
            return {
                "env": ScriptedEnv(1000),
                "order_id": "00000002",
                "target": "euro-pallet",
                "n_items": 1000,
                "observation": [0.0] * OBS_DIM,
                "terminated": False,
            }

        real_step = ScriptedEnv.step

        def counting_step(self, action):
            calls["n"] += 1
            return real_step(self, action)

        ScriptedEnv.step = counting_step
        try:
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "checkpoint_last.pt"
                summary = run_budget(
                    seed=102,
                    actor=actor,
                    critic=critic,
                    optimizer=optimizer,
                    live={"env": None, "terminated": True},
                    start_episode=start_episode,
                    deadline=3,
                    clock=clock,
                    on_update=lambda record: episodes.append("update"),
                    on_episode=episodes.append,
                    checkpoint_path=path,
                )
                self.assertFalse(path.exists())
        finally:
            ScriptedEnv.step = real_step
        self.assertEqual(summary["updates"], 0)
        self.assertEqual(summary["adam_steps"], 0)
        self.assertGreater(summary["decisions"], 0)
        self.assertLess(summary["decisions"], ROLLOUT_DECISIONS)
        self.assertEqual(summary["status"], "incompleta_reloj")
        self.assertFalse(summary["equal_budget"])
        self.assertNotIn("update", episodes)
        self.assertEqual(episodes[-1]["termination"], "corte_de_presupuesto")

    def test_checkpoint_roundtrip_reproduces_logits(self) -> None:
        actor = build_actor()
        critic = build_critic()
        optimizer = build_optimizer(list(actor.parameters()) + list(critic.parameters()))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint_initial.pt"
            save_checkpoint(path, actor, critic, optimizer, {"status": "inicial"})
            self.assertEqual(logits_of(load_actor(path), [0.0] * OBS_DIM), [1.0, 0.0, 0.0])

    def test_development_manifest_excludes_train_and_runs_nothing(self) -> None:
        development = json.loads((STUDY / "development_manifest.json").read_text(encoding="utf-8"))
        train = json.loads((STUDY / "train_manifest.json").read_text(encoding="utf-8"))
        protocol = json.loads((STUDY / "protocol_frozen.json").read_text(encoding="utf-8"))
        dev_ids = [row["order_id"] for rows in development["selected"].values() for row in rows]
        train_ids = {row["order_id"] for rows in train["selected"].values() for row in rows}
        dev_signatures = {row["signature"] for rows in development["selected"].values() for row in rows}
        train_signatures = {row["signature"] for rows in train["selected"].values() for row in rows}
        self.assertEqual(len(dev_ids), 40)
        self.assertEqual(len(set(dev_ids)), 40)
        self.assertEqual(len(development["selected"]["euro-pallet"]), 20)
        self.assertEqual(len(development["selected"]["rollcontainer"]), 20)
        self.assertFalse(set(dev_ids) & train_ids)
        self.assertFalse(dev_signatures & train_signatures)
        self.assertFalse(development["episodes_executed"])
        self.assertFalse(development["statistics_built"])
        self.assertFalse(development["final_test_selected"])
        self.assertFalse(development["final_test_consulted"])
        self.assertFalse(protocol["development_gate"]["applied"])
        self.assertEqual(protocol["budget"]["decisions_per_seed"], 6144)
        self.assertNotIn("final_test_ids", development)


if __name__ == "__main__":
    unittest.main()
