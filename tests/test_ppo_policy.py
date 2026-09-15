"""PPO: preset de plataforma, rollout mínimo y compuerta de promoción."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from packing_services.api.main import app
from packing_services.domain.models import (
    AlgorithmConfig,
    ConstraintFlags,
    Container,
    Item,
    PackingProblem,
)
from packing_services.online.learned.production import (
    DEFAULT_MODEL_PATH,
    PPO_MODEL_PATH,
    apply_policy_preset,
    rl_learned_parameters,
)
from packing_services.utils.errors import InvalidInputError

REPO = Path(__file__).resolve().parents[1]
SRC_ML = REPO / "online_policy_ml" / "src_ml"
if str(SRC_ML) not in sys.path:
    sys.path.insert(0, str(SRC_ML))

from export_ckpt import export_mlp_pt  # noqa: E402
from methodology import compare_paired  # noqa: E402
from train_mlp import build_mlp_v1  # noqa: E402
from step_select import collapse_best_pose_indices  # noqa: E402
from train_ppo import (  # noqa: E402
    STATE_DIM,
    build_critic,
    compare_ppo_to_baselines,
    load_actor_from_pt,
    place_reward,
    rollout_episode,
    terminal_reward,
)

client = TestClient(app)


def test_imitation_preset_is_rejected():
    with pytest.raises(InvalidInputError, match="imitation ya no está disponible"):
        apply_policy_preset({"policy": "imitation"})


def test_rl_is_the_default_learned_policy():
    out = apply_policy_preset({})
    assert out["policy"] == "rl"
    assert out["model_path"] == DEFAULT_MODEL_PATH
    assert out["lookahead_p"] == 1


def test_unknown_policy_is_rejected():
    with pytest.raises(InvalidInputError, match="policy"):
        apply_policy_preset({"policy": "dqn"})


def test_rl_preset_without_checkpoint_explains_notebook_05():
    repo_ppo = REPO / PPO_MODEL_PATH
    if repo_ppo.is_file():
        pytest.skip("el checkpoint PPO ya existe")
    with pytest.raises(InvalidInputError, match="policy=rl requiere"):
        apply_policy_preset({"policy": "rl"})


def test_rl_route_is_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/v1/online/rl/execute" in paths
    assert "/api/v1/online/learned/execute" in paths
    assert rl_learned_parameters()["policy"] == "rl"


def test_rl_execute_without_checkpoint_is_400():
    if (REPO / PPO_MODEL_PATH).is_file():
        pytest.skip("el checkpoint PPO ya existe")
    response = client.post(
        "/api/v1/online/rl/execute",
        json={
            "problem_type": "3D_BPP",
            "packing_mode": "online",
            "containers": [
                {"id": "C1", "length": 50, "width": 50, "height": 50, "max_weight": 1000}
            ],
            "items": [
                {"id": "I1", "length": 10, "width": 10, "height": 10, "weight": 1}
            ],
            "parameters": {"policy": "rl"},
        },
    )
    assert response.status_code == 422
    assert "05_ppo_finetune" in response.text or "PPO" in response.text


def test_ppo_rollout_on_tiny_instance(tmp_path):
    actor = build_mlp_v1(64)
    path = tmp_path / "actor.pt"
    export_mlp_pt(actor.state_dict(), path, hidden_size=64)
    loaded, hidden = load_actor_from_pt(path)
    assert hidden == 64
    critic = build_critic(hidden)
    problem = PackingProblem(
        problem_type="3D_BPP",
        containers=[Container(id="C1", length=50, width=50, height=50, max_weight=1000)],
        items=[
            Item(id="I1", length=10, width=10, height=10, weight=1, arrival_index=1),
            Item(id="I2", length=10, width=10, height=10, weight=1, arrival_index=2),
        ],
        constraints=ConstraintFlags(),
        algorithm=AlgorithmConfig(
            name="drl_policy_3d_bpp",
            parameters={"lookahead_p": 1, "select_s": 1, "selection": "best_fit"},
        ),
    )
    episode = rollout_episode(
        problem, loaded, critic, lookahead_p=1, select_s=1, deterministic=True
    )
    assert episode["is_valid"]
    assert episode["items_packed"] >= 1
    assert episode["steps"]
    assert all("reward" in step and "return" in step for step in episode["steps"])
    assert episode["reward"] > 0
    assert all("state" in step and step["state"].numel() == STATE_DIM for step in episode["steps"])
    assert terminal_reward(SimpleNamespace(metrics=SimpleNamespace(volume_utilization=0.5))) == 0.5


def test_step_collapse_keeps_one_pose_per_item():
    a0 = SimpleNamespace(item=SimpleNamespace(id="A"), buffer_index=0)
    a1 = SimpleNamespace(item=SimpleNamespace(id="A"), buffer_index=0)
    b0 = SimpleNamespace(item=SimpleNamespace(id="B"), buffer_index=1)
    assert collapse_best_pose_indices([a0, a1, b0], [0.1, 0.9, 0.4]) == [1, 2]


def test_place_reward_depends_on_height_and_support():
    item = SimpleNamespace(volume=1000.0)
    low = SimpleNamespace(support_ratio=0.9, position=SimpleNamespace(z=0.0))
    high = SimpleNamespace(support_ratio=0.2, position=SimpleNamespace(z=80.0))
    r_low = place_reward(item, 8000.0, candidate=low, container_height=100.0)
    r_high = place_reward(item, 8000.0, candidate=high, container_height=100.0)
    assert r_low > r_high


def test_ppo_does_not_promote_on_tie():
    rows = [{"order_id": str(i), "volume_utilization": 0.66} for i in range(8)]
    cmp = compare_ppo_to_baselines(rows, list(rows), list(rows))
    assert cmp["can_promote_over_heuristic"] is False
    assert cmp["can_promote_over_imitation"] is False
    tied = compare_paired(rows, list(rows), label_a="ppo", label_b="heuristic")
    assert tied["significant"] is False
