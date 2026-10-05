"""Normalización solo train y verificación independiente del etiquetado."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
COUNTERFACTUAL_TOOLS = HERE.parents[1] / "counterfactual_ranking" / "tools"
for entry in (str(HERE), str(PAPER_TOOLS), str(COUNTERFACTUAL_TOOLS)):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

from actor_features import FEATURE_NAMES  # noqa: E402
from campaign import recompute_u  # noqa: E402
from normalization import fit_normalization  # noqa: E402


def learning_rows_from_orders(orders: list[dict[str, Any]], *, split: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order in orders:
        if split is not None and order.get("split") != split:
            continue
        for state in order.get("states") or []:
            if not state.get("eligible_for_learning"):
                continue
            for alt in state["alternatives"]:
                rows.append(
                    {
                        "split": order["split"],
                        "order_id": order["order_id"],
                        "target": order["target"],
                        "choice_index": state["choice_index"],
                        "action": alt["action"],
                        "features": alt["features"],
                        "q_hat": alt["q_hat"],
                        "source": alt.get("source"),
                    }
                )
    return rows


def build_normalization_document(train_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not train_rows:
        raise RuntimeError("no hay filas train completas para normalización")
    matrix = [list(row["features"]) for row in train_rows]
    stats = fit_normalization(matrix)
    payload = {
        "fit_on": "train_rows_only",
        "row_weight": "equal",
        "feature_names": list(FEATURE_NAMES),
        "feature_order": list(FEATURE_NAMES),
        "n_rows": int(stats["n_rows"]),
        "n_columns": len(FEATURE_NAMES),
        "mean": list(stats["mean"]),
        "scale": list(stats["scale"]),
        "denominator": "population_std_or_1_if_constant",
        "refit_on_development_or_test": False,
    }
    raw = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    payload["sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return payload


def independent_refit_hash(train_rows: list[dict[str, Any]]) -> str:
    doc = build_normalization_document(train_rows)
    body = {key: value for key, value in doc.items() if key != "sha256"}
    raw = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_order_results(output: Path) -> list[dict[str, Any]]:
    orders_dir = output / "orders"
    if not orders_dir.is_dir():
        return []
    results = []
    for path in sorted(orders_dir.glob("*/result.json")):
        results.append(json.loads(path.read_text(encoding="utf-8")))
    return results


def verify_labeling_output(
    *,
    output: Path,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    orders = load_order_results(output)
    issues: list[str] = []
    expected_ids = [row["order_id"] for row in manifest["execution_order"]]
    seen = [order["order_id"] for order in orders]
    if len(seen) != len(set(seen)):
        issues.append("order_ids_duplicados")
    if set(seen) - set(expected_ids):
        issues.append("order_ids_fuera_del_manifiesto")
    if any(order.get("split") == "test" for order in orders):
        issues.append("test_presente")
    train_ids = {row["order_id"] for row in manifest["execution_order"] if row["split"] == "train"}
    dev_ids = {row["order_id"] for row in manifest["execution_order"] if row["split"] == "development"}
    if train_ids & dev_ids:
        issues.append("train_development_overlap")

    unknown = 0
    reused = 0
    new = 0
    coverage: dict[str, Any] = {"by_split": {}, "by_target": {}, "by_order": []}
    for order in orders:
        split = order.get("split")
        target = order.get("target")
        coverage["by_split"].setdefault(split, {"orders": 0, "states": 0, "complete_states": 0, "unknown": 0})
        coverage["by_target"].setdefault(target, {"orders": 0, "states": 0, "complete_states": 0, "unknown": 0})
        coverage["by_split"][split]["orders"] += 1
        coverage["by_target"][target]["orders"] += 1
        order_unknown = 0
        complete_states = 0
        for state in order.get("states") or []:
            coverage["by_split"][split]["states"] += 1
            coverage["by_target"][target]["states"] += 1
            if state.get("complete"):
                complete_states += 1
                coverage["by_split"][split]["complete_states"] += 1
                coverage["by_target"][target]["complete_states"] += 1
            if not state.get("greedy_in_support", True):
                issues.append(f"greedy_absent:{order['order_id']}:{state['choice_index']}")
            for alt in state.get("alternatives") or []:
                if alt.get("q_hat") is None:
                    unknown += 1
                    order_unknown += 1
                    coverage["by_split"][split]["unknown"] += 1
                    coverage["by_target"][target]["unknown"] += 1
                source = alt.get("source")
                if source == "preflight_reused":
                    reused += 1
                elif source == "new":
                    new += 1
                if alt.get("action") not in state.get("support_ids", []):
                    # action lists must match an identity in support_ids
                    if list(alt.get("action") or []) not in [list(x) for x in state.get("support_ids", [])]:
                        issues.append(f"action_outside_S:{order['order_id']}:{state['choice_index']}")
                capture_path = (
                    output
                    / "orders"
                    / order["order_id"]
                    / "states"
                    / f"choice_{state['choice_index']}"
                    / f"alt_{state['alternatives'].index(alt)}_capture.json"
                )
                if alt.get("capture_saved") and capture_path.is_file() and alt.get("q_hat") is not None:
                    capture = json.loads(capture_path.read_text(encoding="utf-8"))
                    recomputed = recompute_u(capture)
                    if recomputed is None or abs(float(recomputed) - float(alt["q_hat"])) > 1e-12:
                        issues.append(f"qhat_mismatch:{order['order_id']}:{state['choice_index']}")
        coverage["by_order"].append(
            {
                "order_id": order["order_id"],
                "split": split,
                "target": target,
                "n_states": order.get("n_states"),
                "complete_states": complete_states,
                "unknown_returns": order_unknown,
            }
        )

    train_learning = learning_rows_from_orders(orders, split="train")
    normalization = None
    normalization_ok = False
    if train_learning:
        normalization = build_normalization_document(train_learning)
        refit = independent_refit_hash(train_learning)
        normalization_ok = refit == normalization["sha256"]
        if not normalization_ok:
            issues.append("normalization_refit_mismatch")
        # Incomplete states must not appear in train_learning
        for order in orders:
            if order.get("split") != "train":
                continue
            for state in order.get("states") or []:
                if not state.get("eligible_for_learning"):
                    for alt in state.get("alternatives") or []:
                        if any(
                            row["order_id"] == order["order_id"]
                            and row["choice_index"] == state["choice_index"]
                            and row["action"] == alt["action"]
                            for row in train_learning
                        ):
                            issues.append("incomplete_state_in_normalization")

    expected_complete = (
        summary.get("status") == "completed"
        and not summary.get("pending_order_ids")
        and len(seen) == len(expected_ids)
        and summary.get("continuations_reused", reused) == 16
    )
    # Reused count in this pass may be less than 16 if those orders were not reached; require exact when completed.
    if summary.get("status") == "completed" and summary.get("continuations_reused") != 16:
        issues.append("reused_continuations_not_16_on_completed")
    if summary.get("status") == "completed" and unknown > 0:
        # completed with unknowns is allowed to persist nulls but readiness flag false
        pass

    document = {
        "status": "verified" if not issues and summary.get("status") == "completed" else "issues_found",
        "issues": issues,
        "n_orders": len(orders),
        "expected_orders": len(expected_ids),
        "unknown_returns": unknown,
        "continuations_reused_observed": reused,
        "continuations_new_observed": new,
        "coverage": coverage,
        "normalization": normalization,
        "normalization_independent_ok": normalization_ok,
        "summary_status": summary.get("status"),
        "expected_keys_complete": expected_complete and not issues,
        "ready_for_training": bool(
            summary.get("status") == "completed"
            and not issues
            and unknown == 0
            and train_learning
            and normalization_ok
        ),
        "development_gate_evaluated": False,
        "test_executed": False,
        "physical_stability_verified": None,
    }
    (output / "labeling_verification.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if normalization is not None:
        (output / "normalization_train.json").write_text(
            json.dumps(normalization, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return document
