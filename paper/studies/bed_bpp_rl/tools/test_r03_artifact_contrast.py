"""Pruebas adversariales del contraste de artefactos (R03-preparación)."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from artifact_contrast import ArtifactContrastError, contrast_artifacts
from episode_export import fixed_action, run_and_record
from resource_verifier import VerificationError, verify_complete_from_artifacts
from synthetic_problems import scenario_catalog


@pytest.fixture
def complete_doc():
    document, env, _ = run_and_record(
        scenario_catalog()["two_fit"],
        episode_id="ep-adv",
        order_id="syn-two-fit",
        target_id="euro-pallet",
        behavior_policy="fixed_greedy_best_fit",
        behavior_seed=0,
        policy=fixed_action(0),
    )
    env.close()
    return document


def test_reject_unknown_placement_id(complete_doc):
    bad = deepcopy(complete_doc)
    bad["artifacts"]["placements"][0]["item_id"] = "unknown#9"
    with pytest.raises((ArtifactContrastError, VerificationError)):
        verify_complete_from_artifacts(bad)


def test_reject_disallowed_orientation(complete_doc):
    bad = deepcopy(complete_doc)
    bad["artifacts"]["allow_rotation"] = False
    place = bad["artifacts"]["placements"][0]
    place["l"], place["w"] = place["w"], place["l"]
    geom = list(bad["transitions"][0]["chosen_geometry"])
    geom[4], geom[5] = place["l"], place["w"]
    bad["transitions"][0]["chosen_geometry"] = geom
    # Mantener coherencia estructural de propuestas con la geometría elegida
    action = bad["transitions"][0]["action"]
    bad["transitions"][0]["rule_proposals"][action]["geometry"] = list(geom)
    with pytest.raises((ArtifactContrastError, VerificationError), match="orientación"):
        verify_complete_from_artifacts(bad)


def test_reject_position_change_preserving_volume(complete_doc):
    bad = deepcopy(complete_doc)
    place = bad["artifacts"]["placements"][0]
    place["x"] = float(place["x"]) + 50.0
    # volumen y dims iguales; geometría de transición aún con posición antigua
    with pytest.raises((ArtifactContrastError, VerificationError), match="posición"):
        verify_complete_from_artifacts(bad)


def test_reject_swapped_placements(complete_doc):
    bad = deepcopy(complete_doc)
    assert len(bad["artifacts"]["placements"]) >= 2
    bad["artifacts"]["placements"][0], bad["artifacts"]["placements"][1] = (
        bad["artifacts"]["placements"][1],
        bad["artifacts"]["placements"][0],
    )
    with pytest.raises(
        (ArtifactContrastError, VerificationError), match="reordenados|prefix|secuencia"
    ):
        verify_complete_from_artifacts(bad)


def test_reject_individual_reward_with_conserved_sum(complete_doc):
    bad = deepcopy(complete_doc)
    assert len(bad["transitions"]) >= 2
    r0 = bad["transitions"][0]["reward"]
    r1 = bad["transitions"][1]["reward"]
    bad["transitions"][0]["reward"] = r0 + 0.0001
    bad["transitions"][1]["reward"] = r1 - 0.0001
    # suma conservada aproximadamente; fallará el reward individual
    assert abs(
        sum(t["reward"] for t in bad["transitions"])
        - sum(t["reward"] for t in complete_doc["transitions"])
    ) < 1e-12
    with pytest.raises((ArtifactContrastError, VerificationError), match="reward"):
        verify_complete_from_artifacts(bad)


def test_insufficient_snapshot_not_preaccepted(complete_doc):
    bad = deepcopy(complete_doc)
    bad["artifacts"] = {"bin_lwh_mm": [1, 1, 1]}  # incompleto
    report = contrast_artifacts(bad)
    assert report["audit_performed"] is False
    assert report["status"] == "auditoria_no_realizada"
    complete = verify_complete_from_artifacts(bad)
    assert complete["ok"] is False
    assert complete["status"] == "auditoria_no_realizada"


def test_missing_allow_rotation_reported_not_preaccepted(complete_doc):
    bad = deepcopy(complete_doc)
    del bad["artifacts"]["allow_rotation"]
    report = contrast_artifacts(bad)
    assert report["ok"] is True  # contención puede pasar
    oris = report["properties"]["orientations"]
    assert oris["checked"] is False
    assert "no_comprobada" in oris["status"]
    assert report["complete_contrast"] is False
