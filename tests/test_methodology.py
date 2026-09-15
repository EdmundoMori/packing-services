"""Compuertas metodológicas: holdout, splits, colinealidad, sobreajuste, entrenamiento."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from packing_services.online.features import FEATURE_DIM, FEATURE_NAMES

REPO = Path(__file__).resolve().parents[1]
SRC_ML = REPO / "online_policy_ml" / "src_ml"
if str(SRC_ML) not in sys.path:
    sys.path.insert(0, str(SRC_ML))

from methodology import (  # noqa: E402
    GATE_DISTILL,
    GATE_PPO,
    TautologicalTeacherError,
    closed_form_index,
    MethodologyError,
    STRUCTURAL_COLLINEAR_PAIRS,
    assert_can_promote,
    interpret_teacher_gate,
    assert_collectable,
    assert_disjoint_splits,
    assert_holdout_excluded,
    assert_no_overfit,
    assert_split_integrity,
    assert_trainable_teacher,
    assert_trainable_transitions,
    diagnose_collinearity,
    diagnose_constant_features,
    diagnose_overfit,
)
from splits import split_order_ids, working_subset  # noqa: E402
from train_linear import fit_linear  # noqa: E402

IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}
HOLDOUT = ["00100001", "00100002", "00100003", "00100004", "00100408"]


def _blank(k: int, rng: np.random.Generator) -> np.ndarray:
    return rng.random((k, FEATURE_DIM))


def _rule_transition(k: int, rng: np.random.Generator) -> dict:
    features = _blank(k, rng)
    return {
        "features": features.tolist(),
        "label": int(closed_form_index(features)),
        "n_options": k,
        "order_id": "x",
    }


def _random_transition(k: int, rng: np.random.Generator, order_id: str = "x") -> dict:
    features = _blank(k, rng)
    return {
        "features": features.tolist(),
        "label": int(rng.integers(0, k)),
        "n_options": k,
        "order_id": order_id,
    }


# --------------------------------------------------------------------------- #
# Holdout y splits
# --------------------------------------------------------------------------- #

def test_holdout_cannot_enter_training_ids():
    with pytest.raises(MethodologyError, match="holdout"):
        assert_holdout_excluded(["00100090", "00100408"], role="train", holdout_ids=HOLDOUT)


def test_holdout_clean_set_passes():
    assert_holdout_excluded(["00100090", "00103244"], role="train", holdout_ids=HOLDOUT)


def test_overlapping_splits_are_rejected():
    with pytest.raises(MethodologyError, match="solape"):
        assert_disjoint_splits(
            {"train": ["a", "b"], "val": ["b", "c"], "test": ["d"]}
        )


def test_missing_test_split_is_rejected():
    with pytest.raises(MethodologyError, match="test"):
        assert_split_integrity({"train": ["a"], "val": ["b"]}, blocked=[])


def test_split_stratifies_by_target_and_keeps_holdout_out():
    orders = {
        f"e{i}": {"item_sequence": {"1": {}}, "properties": {"target": "euro-pallet"}}
        for i in range(20)
    }
    orders.update(
        {
            f"r{i}": {"item_sequence": {"1": {}}, "properties": {"target": "rollcontainer"}}
            for i in range(20)
        }
    )
    orders["00100408"] = {
        "item_sequence": {"1": {}},
        "properties": {"target": "euro-pallet"},
    }
    split = split_order_ids(orders.keys(), blocked=["00100408"], seed=0, orders=orders)
    assert "00100408" not in split["train"] + split["val"] + split["test"]
    assert set(split["train"]) & set(split["val"]) == set()
    # Cada split debe contener ambos destinos.
    def targets(ids):
        return {orders[i]["properties"]["target"] for i in ids}

    assert targets(split["train"]) == {"euro-pallet", "rollcontainer"}
    assert targets(split["val"]) == {"euro-pallet", "rollcontainer"}
    assert targets(split["test"]) == {"euro-pallet", "rollcontainer"}


def test_working_subset_random_is_not_the_shortest():
    orders = {f"{i:03d}": {"item_sequence": {str(j): {} for j in range(i + 1)}} for i in range(80)}
    full = {"train": sorted(orders)[:60], "val": sorted(orders)[60:70], "test": sorted(orders)[70:]}
    shortest = working_subset(full, orders, strategy="shortest")
    random_ids = working_subset(full, orders, strategy="random", seed=42)
    assert shortest["train"] != random_ids["train"]
    assert len(random_ids["train"]) == len(shortest["train"])


# --------------------------------------------------------------------------- #
# Maestro y entrenamiento
# --------------------------------------------------------------------------- #

def test_volume_teacher_is_not_collectable():
    with pytest.raises(MethodologyError, match="tautológico|no es entrenable"):
        assert_trainable_teacher("privileged_volume_ep")
    with pytest.raises(MethodologyError):
        assert_collectable(["00100090"], teacher="privileged_volume_ep")


def test_volume_teacher_allowed_only_as_diagnostic():
    assert_trainable_teacher("privileged_volume_ep", allow_diagnostic=True)
    assert_collectable(["00100090"], teacher="privileged_volume_ep", allow_diagnostic=True)


def test_receding_teacher_is_collectable():
    assert_collectable(["00100090"], teacher="receding_horizon_ep", holdout_ids=HOLDOUT)


def test_fit_linear_refuses_tautological_labels():
    rng = np.random.default_rng(1)
    transitions = [_rule_transition(8, rng) for _ in range(40)]
    val = [_rule_transition(8, rng) for _ in range(10)]
    with pytest.raises(TautologicalTeacherError):
        fit_linear(transitions, val_transitions=val)


def test_fit_linear_refuses_training_without_val():
    rng = np.random.default_rng(2)
    transitions = [_random_transition(6, rng) for _ in range(30)]
    with pytest.raises(MethodologyError, match="val_transitions"):
        fit_linear(transitions, require_informative=False)


def test_fit_linear_accepts_informative_labels_with_val():
    rng = np.random.default_rng(3)
    train = [_random_transition(6, rng, order_id="a") for _ in range(20)]
    val = [_random_transition(6, rng, order_id="b") for _ in range(8)]
    result = fit_linear(train, val_transitions=val, epochs=2, require_informative=True)
    assert len(result["weights"]) == FEATURE_DIM
    assert result["best_epoch"] >= 1


def test_assert_trainable_transitions_rejects_closed_form():
    rng = np.random.default_rng(4)
    with pytest.raises(TautologicalTeacherError):
        assert_trainable_transitions([_rule_transition(5, rng) for _ in range(50)])


# --------------------------------------------------------------------------- #
# Colinealidad y features constantes
# --------------------------------------------------------------------------- #

def test_constant_feature_is_flagged():
    rng = np.random.default_rng(5)
    transitions = []
    for _ in range(30):
        features = _blank(4, rng)
        features[:, IDX["bin_index_n"]] = 0.0
        transitions.append({"features": features.tolist(), "label": 0, "n_options": 4})
    constants = diagnose_constant_features(transitions)
    names = {row["feature"] for row in constants}
    assert "bin_index_n" in names


def test_structural_collinearity_pos_z_vs_rank_1():
    rng = np.random.default_rng(6)
    transitions = []
    for _ in range(80):
        features = _blank(5, rng)
        # rank_1 es z en mm; pos_z_n es z/H. Relación lineal exacta.
        z = rng.random(5)
        features[:, IDX["pos_z_n"]] = z
        features[:, IDX["rank_1"]] = z * 2000.0
        transitions.append({"features": features.tolist(), "label": 0, "n_options": 5})
    report = diagnose_collinearity(transitions, threshold=0.95)
    flagged = {(p["a"], p["b"]) for p in report["pairs"]}
    assert ("pos_z_n", "rank_1") in flagged or ("rank_1", "pos_z_n") in flagged
    confirmed = next(p for p in report["structural_confirmed"] if p["a"] == "pos_z_n")
    assert confirmed["corr"] is not None
    assert abs(confirmed["corr"]) >= 0.95


def test_structural_pairs_are_the_known_encoder_duplicates():
    assert STRUCTURAL_COLLINEAR_PAIRS == (
        ("pos_z_n", "rank_1"),
        ("pos_y_n", "rank_2"),
        ("pos_x_n", "rank_3"),
    )


# --------------------------------------------------------------------------- #
# Sobreajuste y promoción
# --------------------------------------------------------------------------- #

def test_overfit_gap_is_detected():
    report = diagnose_overfit(0.99, 0.70)
    assert report["overfit"] is True
    with pytest.raises(MethodologyError, match="hueco"):
        assert_no_overfit(0.99, 0.70, label="mlp")


def test_small_train_val_gap_is_accepted():
    report = diagnose_overfit(0.80, 0.78)
    assert report["overfit"] is False
    assert_no_overfit(0.80, 0.78)


def test_promotion_requires_significant_paired_difference():
    with pytest.raises(MethodologyError, match="no hay evidencia"):
        assert_can_promote(
            {
                "label_a": "nuevo",
                "label_b": "vigente",
                "mean_delta": 0.003,
                "ci_lo": -0.01,
                "ci_hi": 0.02,
                "n_paired": 8,
                "significant": False,
            }
        )


def test_significant_comparison_can_promote():
    assert_can_promote(
        {
            "label_a": "nuevo",
            "label_b": "vigente",
            "mean_delta": 0.04,
            "ci_lo": 0.01,
            "ci_hi": 0.07,
            "n_paired": 40,
            "significant": True,
        }
    )


def _util_rows(prefix: str, values: list[float]) -> list[dict]:
    return [
        {"order_id": f"{prefix}{i}", "volume_utilization": v}
        for i, v in enumerate(values)
    ]


def test_teacher_gate_distill_when_teacher_beats_heuristic():
    teacher = _util_rows("o", [0.80, 0.82, 0.79, 0.81, 0.83, 0.80, 0.82, 0.81])
    heuristic = _util_rows("o", [0.66, 0.67, 0.65, 0.68, 0.66, 0.67, 0.65, 0.66])
    mlp = _util_rows("o", [0.67, 0.66, 0.66, 0.67, 0.65, 0.66, 0.67, 0.66])
    gate = interpret_teacher_gate(teacher, heuristic, mlp)
    assert gate["decision"] == GATE_DISTILL
    assert gate["teacher_wins_heuristic"] is True


def test_teacher_gate_ppo_when_teacher_ties_heuristic():
    tied = [0.66, 0.67, 0.65, 0.68, 0.66, 0.67, 0.65, 0.66]
    teacher = _util_rows("o", tied)
    heuristic = _util_rows("o", tied)
    mlp = _util_rows("o", [v - 0.001 for v in tied])
    gate = interpret_teacher_gate(teacher, heuristic, mlp)
    assert gate["decision"] == GATE_PPO
    assert gate["teacher_wins_heuristic"] is False
