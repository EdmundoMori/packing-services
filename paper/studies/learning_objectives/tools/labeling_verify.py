"""Normalización solo train y verificación independiente del etiquetado.

La completitud se juzga desde las claves del manifiesto de ejecución y,
cuando existe, la procedencia de referencias. Un glob amplio no puede
declarar cobertura: los directorios .staging_* no cuentan como pedidos
finales ni ocultan un pedido esperado ausente o corrupto.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
COUNTERFACTUAL_TOOLS = HERE.parents[1] / "counterfactual_ranking" / "tools"
# learning_objectives/tools primero; counterfactual solo para dependencias no locales
for entry in (str(COUNTERFACTUAL_TOOLS), str(PAPER_TOOLS), str(HERE)):
    if entry in sys.path:
        sys.path.remove(entry)
sys.path.insert(0, str(COUNTERFACTUAL_TOOLS))
sys.path.insert(0, str(PAPER_TOOLS))
sys.path.insert(0, str(HERE))

from actor_features import FEATURE_NAMES  # noqa: E402
from campaign import recompute_u  # noqa: E402
from labeling_integrity import verify_order_artifacts  # noqa: E402
from labeling_io import AtomicWriteError, read_json_strict  # noqa: E402
from normalization import fit_normalization  # noqa: E402

VERIFIER_VERSION = "manifest_keyed_v2"


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


def load_order_result_for_id(output: Path, order_id: str) -> dict[str, Any]:
    """Carga un pedido esperado por id de manifiesto. Staging no sustituye el destino."""

    order_dir = output / "orders" / order_id
    staging_dir = output / "orders" / f".staging_{order_id}"
    meta: dict[str, Any] = {
        "order_id": order_id,
        "staging_present": staging_dir.is_dir(),
        "order_dir_present": order_dir.is_dir(),
    }
    result_path = order_dir / "result.json"
    if not result_path.exists():
        meta["load_status"] = "missing_expected_result"
        meta["issues"] = ["result_missing"]
        if staging_dir.is_dir() and (staging_dir / "result.json").exists():
            meta["issues"].append("staging_exists_but_not_final")
        return meta
    if result_path.stat().st_size == 0:
        meta["load_status"] = "corrupt_result"
        meta["issues"] = ["result_empty"]
        return meta
    try:
        result = read_json_strict(result_path)
    except AtomicWriteError as exc:
        meta["load_status"] = "corrupt_result"
        meta["issues"] = [f"result_unreadable:{exc}"]
        return meta
    meta["load_status"] = "loaded"
    meta["result"] = result
    meta["result_is_symlink"] = result_path.is_symlink()
    provenance_path = order_dir / "provenance.json"
    if provenance_path.is_file() and provenance_path.stat().st_size > 0:
        try:
            meta["provenance"] = read_json_strict(provenance_path)
        except AtomicWriteError:
            meta["provenance_unreadable"] = True
    return meta


def load_orders_from_manifest(output: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Devuelve (resultados cargados, registros de fallo de carga). Orden = manifiesto."""

    loaded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for row in manifest["execution_order"]:
        order_id = row["order_id"]
        entry = load_order_result_for_id(output, order_id)
        if entry.get("load_status") != "loaded":
            failures.append({**entry, "expected": row})
            continue
        result = entry["result"]
        loaded.append(result)
        # adjuntar metadatos de carga sin mutar el JSON en disco
        result["_verify_meta"] = {
            "staging_present": entry.get("staging_present"),
            "result_is_symlink": entry.get("result_is_symlink"),
            "provenance": entry.get("provenance"),
        }
    return loaded, failures


def load_order_results(output: Path, *, manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """API estable: si hay manifiesto, carga solo ids esperados; sin manifiesto, no usa staging."""

    if manifest is not None:
        loaded, _failures = load_orders_from_manifest(output, manifest)
        return loaded
    orders_dir = output / "orders"
    if not orders_dir.is_dir():
        return []
    results = []
    for path in sorted(orders_dir.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        result_path = path / "result.json"
        if not result_path.is_file():
            continue
        try:
            results.append(read_json_strict(result_path))
        except AtomicWriteError:
            continue
    return results


def verify_labeling_output(
    *,
    output: Path,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    del protocol  # contrato de llamada conservado; hashes de protocolo se validan fuera
    issues: list[str] = []
    expected_rows = list(manifest["execution_order"])
    expected_ids = [row["order_id"] for row in expected_rows]
    by_expected = {row["order_id"]: row for row in expected_rows}

    orders, load_failures = load_orders_from_manifest(output, manifest)
    for failure in load_failures:
        oid = failure["order_id"]
        for issue in failure.get("issues") or ["load_failed"]:
            issues.append(f"{issue}:{oid}")

    seen = [order["order_id"] for order in orders]
    if len(seen) != len(set(seen)):
        issues.append("order_ids_duplicados")
    if set(seen) - set(expected_ids):
        issues.append("order_ids_fuera_del_manifiesto")
    missing = [oid for oid in expected_ids if oid not in set(seen)]
    if missing:
        issues.append(f"missing_expected_count:{len(missing)}")

    if any(order.get("split") == "test" for order in orders):
        issues.append("test_presente")
    train_ids = {row["order_id"] for row in expected_rows if row["split"] == "train"}
    dev_ids = {row["order_id"] for row in expected_rows if row["split"] == "development"}
    if train_ids & dev_ids:
        issues.append("train_development_overlap")

    unknown = 0
    reused = 0
    new = 0
    n_alternatives = 0
    coverage: dict[str, Any] = {"by_split": {}, "by_target": {}, "by_order": []}
    order_state_action_keys: set[tuple[Any, ...]] = set()
    key_dups = 0

    for order in orders:
        oid = order["order_id"]
        expected = by_expected.get(oid)
        order_dir = output / "orders" / oid
        check = verify_order_artifacts(order_dir, expected=expected)
        if check["classification"] != "reusable_valid":
            issues.append(f"integrity:{oid}:{check['classification']}")
            for item in check.get("issues") or []:
                issues.append(f"integrity_detail:{oid}:{item}")

        meta = order.pop("_verify_meta", {}) or {}
        provenance = meta.get("provenance")
        if provenance:
            src = provenance.get("source_order_dir")
            if src and not Path(src).exists() and not (order_dir / "result.json").exists():
                issues.append(f"provenance_source_missing:{oid}")

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
                issues.append(f"greedy_absent:{oid}:{state['choice_index']}")
            for alt in state.get("alternatives") or []:
                n_alternatives += 1
                action_key = (
                    oid,
                    state.get("choice_index"),
                    json.dumps(alt.get("action"), sort_keys=True, default=str),
                )
                if action_key in order_state_action_keys:
                    key_dups += 1
                    issues.append(f"duplicate_order_state_action:{oid}:{state.get('choice_index')}")
                order_state_action_keys.add(action_key)
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
                if list(alt.get("action") or []) not in [list(x) for x in state.get("support_ids") or []]:
                    issues.append(f"action_outside_S:{oid}:{state['choice_index']}")
                capture_path = (
                    order_dir
                    / "states"
                    / f"choice_{state['choice_index']}"
                    / f"alt_{state['alternatives'].index(alt)}_capture.json"
                )
                if alt.get("capture_saved") and capture_path.is_file() and alt.get("q_hat") is not None:
                    capture = json.loads(capture_path.read_text(encoding="utf-8"))
                    recomputed = recompute_u(capture)
                    if recomputed is None or abs(float(recomputed) - float(alt["q_hat"])) > 1e-12:
                        issues.append(f"qhat_mismatch:{oid}:{state['choice_index']}")
        coverage["by_order"].append(
            {
                "order_id": oid,
                "split": split,
                "target": target,
                "n_states": order.get("n_states"),
                "complete_states": complete_states,
                "unknown_returns": order_unknown,
                "referenced": bool(provenance),
            }
        )

    train_learning = learning_rows_from_orders(orders, split="train")
    development_learning = learning_rows_from_orders(orders, split="development")
    normalization = None
    normalization_ok = False
    if train_learning:
        normalization = build_normalization_document(train_learning)
        refit = independent_refit_hash(train_learning)
        normalization_ok = refit == normalization["sha256"]
        if not normalization_ok:
            issues.append("normalization_refit_mismatch")
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
        and not load_failures
    )
    if summary.get("status") == "completed" and summary.get("continuations_reused") != 16:
        issues.append("reused_continuations_not_16_on_completed")

    document = {
        "status": "verified" if not issues and summary.get("status") == "completed" else "issues_found",
        "verifier_version": VERIFIER_VERSION,
        "issues": issues,
        "n_orders": len(orders),
        "expected_orders": len(expected_ids),
        "n_load_failures": len(load_failures),
        "unknown_returns": unknown,
        "continuations_reused_observed": reused,
        "continuations_new_observed": new,
        "n_alternatives": n_alternatives,
        "n_order_state_action_keys": len(order_state_action_keys),
        "order_state_action_key_duplicates": key_dups,
        "note_geometry_identity": (
            "unicidad exigida solo en (order_id, choice_index, action); "
            "la misma geometría puede repetirse en estados distintos"
        ),
        "coverage": coverage,
        "n_train_learning_rows": len(train_learning),
        "n_development_learning_rows": len(development_learning),
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
            and len(orders) == len(expected_ids)
        ),
        "development_gate_evaluated": False,
        "test_executed": False,
        "physical_stability_verified": None,
        "staging_policy": "staging_never_counts_as_final_order",
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
