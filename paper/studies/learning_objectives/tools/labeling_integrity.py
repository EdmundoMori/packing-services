"""Integridad por contenido y hashes; progress no es fuente de verdad."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_io import AtomicWriteError, read_json_strict  # noqa: E402

SUPPORT_CONTRACT = "greedy_plus_orientation_position_diversity_v1"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_order_artifacts(order_dir: Path, *, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verifica un pedido por archivos, no por progress."""

    issues: list[str] = []
    result_path = order_dir / "result.json"
    classification = "never_executed"
    result: dict[str, Any] | None = None
    if not result_path.exists():
        return {
            "order_id": order_dir.name,
            "classification": "never_executed",
            "issues": ["result_missing"],
            "result_sha256": None,
        }
    if result_path.stat().st_size == 0:
        return {
            "order_id": order_dir.name,
            "classification": "corrupt",
            "issues": ["result_empty"],
            "result_sha256": file_sha256(result_path),
            "partial_states": _scan_states(order_dir / "states"),
        }
    try:
        result = read_json_strict(result_path)
    except AtomicWriteError as exc:
        return {
            "order_id": order_dir.name,
            "classification": "corrupt",
            "issues": [f"result_unreadable:{exc}"],
            "result_sha256": file_sha256(result_path),
        }

    if expected is not None:
        for key in ("order_id", "split", "target", "selection_hash", "signature"):
            if expected.get(key) is not None and result.get(key) != expected.get(key):
                issues.append(f"mismatch:{key}")

    states = result.get("states") or []
    selected = list(result.get("selected_indices") or [])
    if result.get("status") == "ok" and selected and len(states) != len(selected):
        issues.append("state_count_mismatch")
    for state in states:
        choice = state.get("choice_index")
        state_dir = order_dir / "states" / f"choice_{choice}"
        state_path = state_dir / "state.json"
        if not state_path.is_file() or state_path.stat().st_size == 0:
            issues.append(f"state_missing_or_empty:{choice}")
            continue
        try:
            disk_state = read_json_strict(state_path)
        except AtomicWriteError:
            issues.append(f"state_unreadable:{choice}")
            continue
        if disk_state.get("support_contract") != SUPPORT_CONTRACT:
            issues.append(f"support_contract:{choice}")
        if not disk_state.get("greedy_in_support", True):
            issues.append(f"greedy_absent:{choice}")
        n_sup = int(disk_state.get("n_support") or len(disk_state.get("support_ids") or []))
        if n_sup > 4:
            issues.append(f"support_gt4:{choice}")
        alts = disk_state.get("alternatives") or []
        if len(alts) != n_sup:
            issues.append(f"alt_count:{choice}")
        for index, alt in enumerate(alts):
            cap = state_dir / f"alt_{index}_capture.json"
            if alt.get("capture_saved"):
                if not cap.is_file() or cap.stat().st_size == 0:
                    issues.append(f"capture_missing:{choice}:{index}")
                else:
                    try:
                        read_json_strict(cap)
                    except AtomicWriteError:
                        issues.append(f"capture_unreadable:{choice}:{index}")
            q = alt.get("q_hat")
            ru = alt.get("recomputed_u_geom")
            if q is not None and ru is not None and abs(float(q) - float(ru)) > 1e-12:
                issues.append(f"qhat_mismatch:{choice}:{index}")
            if list(alt.get("action") or []) not in [list(x) for x in disk_state.get("support_ids") or []]:
                issues.append(f"action_outside_S:{choice}:{index}")

    if result.get("status") == "ok" and not issues:
        classification = "reusable_valid"
    elif issues and any("empty" in i or "unreadable" in i or "missing" in i for i in issues):
        classification = "corrupt" if result.get("status") == "ok" else "insufficient"
    else:
        classification = "insufficient" if issues else "reusable_valid"

    # progress may claim ok; content wins
    if result.get("status") == "ok" and issues:
        classification = "corrupt_or_incomplete"
        issues.append("status_ok_but_content_invalid")

    return {
        "order_id": result.get("order_id") or order_dir.name,
        "classification": classification,
        "issues": issues,
        "result_sha256": file_sha256(result_path),
        "status_field": result.get("status"),
        "n_states": len(states),
        "split": result.get("split"),
        "target": result.get("target"),
        "wall_seconds": result.get("wall_seconds"),
    }


def _scan_states(states_dir: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not states_dir.is_dir():
        return out
    for choice_dir in sorted(states_dir.iterdir()):
        if not choice_dir.is_dir():
            continue
        files = {p.name: p.stat().st_size for p in choice_dir.iterdir() if p.is_file()}
        if not files:
            klass = "missing"
        elif all(size > 0 for size in files.values()):
            klass = "intact_files"
        elif all(size == 0 for size in files.values()):
            klass = "empty_files"
        else:
            klass = "mixed"
        out[choice_dir.name] = {"files": files, "class": klass}
    return out


def audit_labeling_tree(
    output: Path,
    *,
    manifest: dict[str, Any],
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected = {row["order_id"]: row for row in manifest["execution_order"]}
    orders_dir = output / "orders"
    present = {p.name for p in orders_dir.iterdir()} if orders_dir.is_dir() else set()
    by_class: dict[str, list[str]] = {
        "reusable_valid": [],
        "corrupt": [],
        "corrupt_or_incomplete": [],
        "insufficient": [],
        "never_executed": [],
    }
    details: list[dict[str, Any]] = []
    progress_ok_ids = set()
    if progress:
        progress_ok_ids = {
            item["order_id"]
            for item in progress.get("orders_done") or []
            if item.get("status") == "ok"
        }

    for order_id, row in expected.items():
        if row.get("split") == "test":
            continue
        order_dir = orders_dir / order_id
        if order_id not in present:
            item = {
                "order_id": order_id,
                "classification": "never_executed",
                "issues": ["no_order_dir"],
                "split": row["split"],
                "target": row["target"],
            }
        else:
            item = verify_order_artifacts(order_dir, expected=row)
        if order_id in progress_ok_ids and item["classification"] not in {"reusable_valid"}:
            item.setdefault("issues", []).append("progress_ok_but_content_not_reusable")
            item["progress_conflict"] = True
        by_class.setdefault(item["classification"], []).append(order_id)
        details.append(item)

    return {
        "kind": "content_integrity_audit",
        "progress_is_source_of_truth": False,
        "by_class": {key: sorted(vals) for key, vals in by_class.items()},
        "counts": {key: len(vals) for key, vals in by_class.items()},
        "details": details,
        "n_expected_non_test": sum(1 for row in manifest["execution_order"] if row.get("split") != "test"),
    }
