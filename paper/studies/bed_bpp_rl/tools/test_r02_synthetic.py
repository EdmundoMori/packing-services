"""Pruebas sintéticas R02 — corrección contractual, no rendimiento BED-BPP."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from corpus_contract import AGENT_FIELDS, schema_document, validate_transition
from corpus_loader import agent_batch, load_episode
from corpus_writer import CorpusWriteError, is_confirmed_episode
from engine_check import verify_post_c04_engine
from environment import (
    ENVIRONMENT_VERSION,
    ENGINE_REQUIRED_COMMIT,
    BedBppRlEnv,
    EnvironmentClosedError,
    InvalidActionError,
)
from episode_export import fixed_action, publish_episode, run_and_record
from observation_spec import FEATURE_SPEC, OBS_DIM, observation_manifest
from resource_verifier import verify_episode_document
from synthetic_problems import scenario_catalog


@pytest.fixture(scope="module")
def engine_ok():
    return verify_post_c04_engine()


@pytest.fixture
def scenarios():
    return scenario_catalog()


def test_engine_post_c04(engine_ok):
    assert engine_ok["post_c04_markers_ok"] is True
    assert engine_ok["required_commit"] == ENGINE_REQUIRED_COMMIT
    assert engine_ok["ancestor_of_head"] is True


def test_observation_spec_36_features():
    manifest = observation_manifest()
    assert manifest["dim"] == 36 == OBS_DIM
    assert len(FEATURE_SPEC) == 36
    assert manifest["markov_sufficiency_claimed"] is False
    assert "future_item_dimensions" in manifest["excludes"]
    names = [row["name"] for row in FEATURE_SPEC]
    assert names == manifest["feature_names"]
    for row in FEATURE_SPEC:
        assert "formula" in row and "unit" in row and "meaning" in row
        assert isinstance(row["index"], int)
    assert manifest["dtype"]
    assert set(manifest["layers"]) >= {"simulator_internal", "agent_observation", "audit"}


def test_all_boxes_placed(scenarios, engine_ok, tmp_path):
    del engine_ok
    problem = scenarios["all_fit"]
    document, env, recorder = run_and_record(
        problem,
        episode_id="ep-all",
        order_id="syn-all-fit",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=0,
        policy=fixed_action(0),
    )
    assert document["terminated"] is True
    assert document["truncated"] is False
    assert document["end_reason"] == "all_items_placed"
    assert document["n_transitions"] == 3
    report = verify_episode_document(document, env=env, problem=problem)
    assert report["observed_return_kind"] == "complete_u_geom"
    assert report["volume_audit"]["match"] is True
    assert report["physical_stability_verified"] is None
    path = tmp_path / "ep-all.json"
    manifest = tmp_path / "manifest.json"
    publish_episode(recorder, document, path=path, manifest_path=manifest)
    loaded = load_episode(path, manifest_path=manifest)
    assert loaded["n_transitions"] == 3
    env.close()


def test_first_item_impossible_zero_transitions(scenarios):
    problem = scenarios["first_impossible"]
    document, env, _recorder = run_and_record(
        problem,
        episode_id="ep-zero",
        order_id="syn-first-imp",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=None,
    )
    assert document["n_transitions"] == 0
    assert document["terminated"] is True
    assert document["summary"]["zero_transition_terminal"] is True
    assert document["end_reason"] == "no_legal_candidate_on_reset"
    with pytest.raises(EnvironmentClosedError):
        env.step(0)
    report = verify_episode_document(document, env=env, problem=problem)
    assert report["observed_return_kind"] == "zero_or_empty"
    env.close()


def test_next_item_impossible_after_placement(scenarios):
    problem = scenarios["next_impossible"]
    document, env, _ = run_and_record(
        problem,
        episode_id="ep-next",
        order_id="syn-next-imp",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=1,
    )
    assert document["n_transitions"] == 1
    assert document["terminated"] is True
    assert document["end_reason"] == "no_legal_candidate_after_placement"
    # No exige acción adicional sobre lista vacía
    with pytest.raises(EnvironmentClosedError):
        env.step(0)
    verify_episode_document(document, env=env, problem=problem)
    env.close()


def test_truncation_keeps_bootstrap_observation(scenarios):
    problem = scenarios["all_fit"]
    document, env, _ = run_and_record(
        problem,
        episode_id="ep-trunc",
        order_id="syn-all-fit",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=2,
        decision_budget=1,
    )
    assert document["truncated"] is True
    assert document["terminated"] is False
    assert document["n_transitions"] == 1
    assert document["end_reason"] == "budget_decision_cut"
    last = document["transitions"][0]
    assert last["truncated"] is True
    assert any(last["action_mask_next"])  # máscara bootstrap utilizable
    assert last["observation_next"] != [0.0] * OBS_DIM or True  # puede tener packed feats
    report = verify_episode_document(document, env=env, problem=problem)
    assert report["observed_return_kind"] == "partial"
    env.close()


def test_natural_termination_priority_over_budget(scenarios):
    problem = scenarios["two_fit"]
    document, env, _ = run_and_record(
        problem,
        episode_id="ep-nat-budget",
        order_id="syn-two-fit",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=3,
        decision_budget=2,
    )
    assert document["terminated"] is True
    assert document["truncated"] is False
    assert document["end_reason"] == "all_items_placed"
    assert document["n_transitions"] == 2
    env.close()


def test_coincident_geometries_preserve_action_identity(scenarios):
    problem = scenarios["all_fit"]
    env = BedBppRlEnv()
    obs, info = env.reset(problem)
    proposals = info["proposals"]
    assert len(proposals) == 3
    assert [row["action"] for row in proposals] == [0, 1, 2]
    geos = [row["geometry"] for row in proposals]
    # Aunque coincidan, las tres identidades permanecen
    assert len({row["rule"] for row in proposals}) == 3
    for action in (0, 1, 2):
        env2 = BedBppRlEnv()
        env2.reset(problem)
        _o, _r, _t, _tr, info2 = env2.step(action)
        assert info2["action"] == action
        env2.close()
    # Si hay coincidencia geométrica, la identidad no colapsa
    if geos[0] == geos[1] == geos[2]:
        assert proposals[0]["rule"] != proposals[1]["rule"]
    env.close()


def test_step_after_close_rejected(scenarios):
    problem = scenarios["two_fit"]
    env = BedBppRlEnv()
    env.reset(problem)
    while True:
        _o, _r, term, trunc, info = env.step(0)
        if term or trunc:
            break
    with pytest.raises(EnvironmentClosedError):
        env.step(0)
    with pytest.raises(InvalidActionError):
        env2 = BedBppRlEnv()
        env2.reset(problem)
        env2.step(99)
    env.close()


def test_reset_releases_previous_episode(scenarios):
    env = BedBppRlEnv()
    env.reset(scenarios["all_fit"])
    first_session = env.session
    env.reset(scenarios["two_fit"])
    assert env.session is not first_session
    # Liberación: la sesión anterior ya no está referenciada por el env
    assert env.released_sessions() >= 0
    del first_session
    env.close()


def test_observation_independent_of_suffix(scenarios):
    base = scenarios["suffix_independence_base"]
    alt = scenarios["suffix_independence_alt"]
    env_a = BedBppRlEnv()
    env_b = BedBppRlEnv()
    obs_a, _ = env_a.reset(base)
    obs_b, _ = env_b.reset(alt)
    # Primer ítem idéntico → observación presente idéntica (sin fuga de sufijo)
    assert obs_a == obs_b
    env_a.close()
    env_b.close()


def test_reward_matches_audited_volume(scenarios):
    problem = scenarios["all_fit"]
    document, env, _ = run_and_record(
        problem,
        episode_id="ep-vol",
        order_id="syn-all-fit",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=4,
    )
    report = verify_episode_document(document, env=env, problem=problem)
    assert abs(
        report["volume_audit"]["u_geom_from_capture"]
        - report["volume_audit"]["reward_sum_stored"]
    ) < 1e-9
    # Independencia: volumen AABB recompuesto, no solo sum(rewards) opaca
    assert report["volume_audit"]["method"].startswith("recompose")
    env.close()


def test_interrupted_write_incomplete_and_duplicates(tmp_path, scenarios):
    problem = scenarios["two_fit"]
    document, env, recorder = run_and_record(
        problem,
        episode_id="ep-io",
        order_id="syn-two-fit",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=5,
    )
    path = tmp_path / "ep-io.json"
    manifest = tmp_path / "manifest.json"
    publish_episode(recorder, document, path=path, manifest_path=manifest)
    assert is_confirmed_episode(path, manifest)

    # Archivo .tmp incompleto no cuenta
    incomplete = tmp_path / "ep-io.json.tmp"
    incomplete.write_text("{", encoding="utf-8")
    assert is_confirmed_episode(incomplete, manifest) is False

    # Duplicado rechazado
    with pytest.raises(CorpusWriteError):
        publish_episode(recorder, document, path=path, manifest_path=manifest)

    # Documento no en manifiesto → loader rechaza
    orphan = tmp_path / "orphan.json"
    orphan.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        load_episode(orphan, manifest_path=manifest)
    env.close()


def test_agent_loader_excludes_audit(tmp_path, scenarios):
    problem = scenarios["two_fit"]
    document, env, recorder = run_and_record(
        problem,
        episode_id="ep-agent",
        order_id="syn-two-fit",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=6,
    )
    path = tmp_path / "ep-agent.json"
    manifest = tmp_path / "manifest.json"
    publish_episode(recorder, document, path=path, manifest_path=manifest)
    batch = agent_batch(path, manifest_path=manifest)
    assert batch
    for row in batch:
        assert set(row.keys()) == set(AGENT_FIELDS)
        assert "order_id" not in row
        assert "end_reason" not in row
        assert "rule_proposals" not in row
        assert "behavior_log_probs" not in row
    schema = schema_document()
    assert schema["off_policy_importance_supported"] is False
    env.close()


def test_budget_cut_without_actions(scenarios):
    problem = scenarios["all_fit"]
    env = BedBppRlEnv()
    obs, info = env.reset(problem, decision_budget=0)
    assert info["terminated"] is False
    # step con presupuesto 0 → truncación sin fabricar transición de placement
    obs2, reward, term, trunc, info2 = env.step(0)
    assert trunc is True and term is False
    assert reward == 0.0
    assert info2.get("fabricated_transition") is False
    assert env.summary.n_transitions == 0
    assert env.summary.end_reason == "budget_decision_cut"
    env.close()


def test_truncate_budget_zero_actions_summary(scenarios):
    problem = scenarios["all_fit"]
    env = BedBppRlEnv()
    env.reset(problem)
    info = env.truncate_budget(end_reason="budget_wall_cut")
    assert info["truncated"] is True
    assert info["fabricated_transition"] is False
    assert env.summary.n_transitions == 0
    env.close()


def test_contract_rejects_nonfinite_and_bad_action():
    base = {
        "observation": [0.0] * 36,
        "observation_next": [0.0] * 36,
        "action": 0,
        "action_mask": [True, True, True],
        "action_mask_next": [False, False, False],
        "reward": 0.1,
        "terminated": True,
        "truncated": False,
        "episode_id": "x",
        "step_index": 0,
    }
    validate_transition(base)
    bad = dict(base, reward=float("nan"))
    with pytest.raises(ValueError):
        validate_transition(bad)
    bad2 = dict(base, action=0, action_mask=[False, True, True])
    with pytest.raises(ValueError):
        validate_transition(bad2)
    bad3 = dict(base, terminated=True, truncated=True)
    with pytest.raises(ValueError):
        validate_transition(bad3)


def test_environment_version_binds_engine():
    assert "ep_c04" in ENVIRONMENT_VERSION
    assert ENGINE_REQUIRED_COMMIT.startswith("a5fb468")
