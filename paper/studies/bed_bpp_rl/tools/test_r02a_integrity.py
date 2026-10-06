"""Pruebas sintéticas R02A — integridad del recurso (sin pedidos reales)."""

from __future__ import annotations

import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from corpus_contract import POLICY_PUBLIC_FIELDS
from corpus_loader import agent_batch_from_store, load_episode_from_store
from corpus_writer import CorpusStore, CorpusWriteError
from environment import BedBppRlEnv, InvalidActionError
from episode_export import fixed_action, publish_episode, run_and_record
from episode_validation import EpisodeValidationError, validate_episode_document
from resource_verifier import (
    VerificationError,
    audit_geometry_from_artifacts,
    validate_structural,
    verify_complete_from_artifacts,
    verify_episode_document,
    verify_published_episode,
)
from synthetic_problems import scenario_catalog


@pytest.fixture
def scenarios():
    return scenario_catalog()


def _recorded(scenarios, key="two_fit", **kwargs):
    problem = scenarios[key]
    defaults = dict(
        episode_id="ep-r02a",
        order_id=problem.items[0].id if False else "syn",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=0,
        policy=fixed_action(0),
    )
    defaults.update(kwargs)
    if "order_id" not in kwargs:
        defaults["order_id"] = {
            "all_fit": "syn-all-fit",
            "two_fit": "syn-two-fit",
            "first_impossible": "syn-first-imp",
            "next_impossible": "syn-next-imp",
        }.get(key, "syn")
    return run_and_record(problem, **defaults)


def test_reject_contradictory_counts_ids_indices_closures(scenarios):
    document, env, _ = _recorded(scenarios, "two_fit")
    env.close()
    bad = deepcopy(document)
    bad["n_transitions"] = 99
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)
    bad = deepcopy(document)
    bad["transitions"][0]["episode_id"] = "other"
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)
    bad = deepcopy(document)
    bad["transitions"][0]["step_index"] = 7
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)
    bad = deepcopy(document)
    bad["terminated"] = False
    bad["truncated"] = False
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)
    bad = deepcopy(document)
    bad["summary"]["terminated"] = False
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)


def test_reject_missing_or_incompatible_proposals(scenarios):
    document, env, _ = _recorded(scenarios, "two_fit")
    env.close()
    bad = deepcopy(document)
    bad["transitions"][0]["rule_proposals"] = None
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)
    bad = deepcopy(document)
    bad["transitions"][0]["rule_proposals"] = bad["transitions"][0]["rule_proposals"][:2]
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)
    bad = deepcopy(document)
    bad["transitions"][0]["chosen_geometry"] = [0, 0, 0, 0, 1, 1, 1]
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)
    bad = deepcopy(document)
    bad["transitions"][0]["rule_proposals"][0]["rule"] = "wrong"
    with pytest.raises(EpisodeValidationError):
        validate_episode_document(bad)


def test_structural_vs_complete_audit_distinction(scenarios):
    document, env, _ = _recorded(scenarios, "two_fit")
    env.close()
    structural = validate_structural(document)
    assert structural["ok"] is True
    stripped = deepcopy(document)
    stripped["artifacts"] = None
    structural2 = validate_structural(stripped)
    assert structural2["ok"] is True
    complete = verify_complete_from_artifacts(stripped)
    assert complete["ok"] is False
    assert complete["status"] == "auditoria_no_realizada"
    assert complete["complete_verification"] is False
    geom = audit_geometry_from_artifacts(stripped)
    assert geom["audit_performed"] is False
    full = verify_complete_from_artifacts(document)
    assert full["ok"] is True and full["complete_verification"] is True


def test_detect_post_confirmation_modification(tmp_path, scenarios):
    document, env, recorder = _recorded(scenarios, "two_fit", episode_id="ep-mod")
    store = CorpusStore(tmp_path)
    publish_episode(recorder, document, store=store, relpath="episodes/ep-mod.json")
    path = store.resolve_relpath("episodes/ep-mod.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["meta"]["notes"] = ["tampered"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256|tamaño"):
        load_episode_from_store(store, "episodes/ep-mod.json")
    env.close()


def test_load_corpus_after_directory_move(tmp_path, scenarios):
    document, env, recorder = _recorded(scenarios, "two_fit", episode_id="ep-move")
    src = tmp_path / "corpus_a"
    dst = tmp_path / "corpus_b"
    store = CorpusStore(src)
    publish_episode(recorder, document, store=store, relpath="episodes/ep-move.json")
    shutil.move(str(src), str(dst))
    moved = CorpusStore(dst)
    loaded = load_episode_from_store(moved, "episodes/ep-move.json")
    assert loaded["episode_id"] == "ep-move"
    report = verify_published_episode(moved, "episodes/ep-move.json")
    assert report["ok"] is True and report["complete_verification"] is True
    env.close()


def test_truncate_without_actions_bootstrap_mask(scenarios):
    problem = scenarios["all_fit"]
    env = BedBppRlEnv()
    obs, info = env.reset(problem)
    assert any(info["action_mask"])
    cut = env.truncate_budget()
    assert cut["fabricated_transition"] is False
    assert cut["bootstrap_observation"] == obs
    assert any(cut["bootstrap_action_mask"])
    assert cut["bootstrap_action_mask"] == info["action_mask"]
    env.close()


def test_policy_callback_cannot_access_audit(scenarios):
    seen = {}

    def sneaky(obs, mask, public):
        seen["keys"] = set(public.keys())
        seen["has_proposals"] = "proposals" in public
        seen["has_order"] = "order_id" in public
        assert "proposals" not in public
        assert set(public.keys()) <= set(POLICY_PUBLIC_FIELDS)
        return 0

    document, env, _ = run_and_record(
        scenarios["two_fit"],
        episode_id="ep-policy",
        order_id="syn-two-fit",
        target_id="euro-pallet",
        behavior_policy="sneaky",
        behavior_seed=0,
        policy=sneaky,
    )
    assert document["n_transitions"] >= 1
    assert seen["has_proposals"] is False
    assert seen["has_order"] is False
    # Auditoría sí quedó en el corpus por ruta separada
    assert document["transitions"][0]["rule_proposals"]
    env.close()


def test_reject_wrong_action_and_budget_types(scenarios):
    problem = scenarios["all_fit"]
    env = BedBppRlEnv()
    with pytest.raises(ValueError):
        env.reset(problem, decision_budget=1.0)
    with pytest.raises(ValueError):
        env.reset(problem, decision_budget=True)
    env.reset(problem)
    with pytest.raises(InvalidActionError):
        env.step(True)  # type: ignore[arg-type]
    with pytest.raises(InvalidActionError):
        env.step(0.0)  # type: ignore[arg-type]
    env.close()


def test_verify_geometry_and_return_from_files_without_live_env(tmp_path, scenarios):
    document, env, recorder = _recorded(scenarios, "all_fit", episode_id="ep-files")
    env.close()
    del env  # sin env vivo
    store = CorpusStore(tmp_path)
    publish_episode(recorder, document, store=store, relpath="episodes/ep-files.json")
    report = verify_published_episode(store, "episodes/ep-files.json")
    assert report["complete_verification"] is True
    assert report["containment_valid"] is True
    assert report["non_overlap_valid"] is True
    assert report["volume_audit"]["match"] is True
    assert report["physical_stability_verified"] is None
    batch = agent_batch_from_store(store, "episodes/ep-files.json")
    assert batch and "rule_proposals" not in batch[0]


def test_reject_path_outside_corpus_and_tmp(tmp_path, scenarios):
    document, env, recorder = _recorded(scenarios, "two_fit", episode_id="ep-path")
    store = CorpusStore(tmp_path)
    with pytest.raises(CorpusWriteError):
        publish_episode(recorder, document, store=store, relpath="../escape.json")
    with pytest.raises(CorpusWriteError):
        publish_episode(recorder, document, store=store, relpath="episodes/ep.tmp")
    env.close()


def test_zero_transition_closure_valid(scenarios):
    document, env, _ = _recorded(scenarios, "first_impossible", episode_id="ep-zero")
    assert document["n_transitions"] == 0
    validate_episode_document(document)
    structural = validate_structural(document)
    assert structural["ok"] is True
    env.close()
