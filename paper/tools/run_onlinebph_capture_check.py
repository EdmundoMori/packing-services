"""Verificación nueva del contrato de captura de OnlineBPH. No recalifica el smoke anterior."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compact_study import build_compact_problem  # noqa: E402
from pilot_common import REPO_ROOT, TIMEOUT_SECONDS, atomic_write_json, sha256_file  # noqa: E402
from pilot_execute import invoke_worker  # noqa: E402
from pilot_metrics import evaluate_outcome  # noqa: E402
from pilot_problems import prepare_imports, problem_snapshot  # noqa: E402


ORDER_IDS = ("00100084", "00100101", "00100802", "00100909", "00101315")
PREVIOUS_SMOKE = REPO_ROOT / "paper/results/16_baseline_smoke"
CODE_FILES = (
    "paper/tools/compact_study.py",
    "paper/tools/online_bph_case.py",
    "paper/tools/online_bph_worker.py",
    "paper/tools/run_onlinebph_capture_check.py",
)
REASON = (
    "El smoke 16 escribió status ok sin captura y invoke_worker lo rechazó. "
    "Esta corrida comprueba el worker corregido sobre los mismos cinco pedidos, "
    "sin sustituir esos method_failure."
)


def _external_commit(repo: Path) -> str | None:
    git_dir = repo / ".git"
    head = git_dir / "HEAD"
    if not head.is_file():
        return None
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref:"):
        ref = git_dir / value.split(" ", 1)[1]
        if ref.is_file():
            return ref.read_text(encoding="utf-8").strip()
    return value


def _snapshot_for(snapshot: dict) -> dict:
    copied = dict(snapshot)
    copied["algorithm"] = "online_bph"
    copied["selection"] = "online_bph_first_feasible_ems"
    return copied


def _previous_hashes() -> dict[str, str]:
    found = {}
    for order_id in ORDER_IDS:
        path = PREVIOUS_SMOKE / "cases" / order_id / "online_bph" / "result.json"
        if not path.is_file():
            raise RuntimeError(f"falta el resultado anterior {path}")
        found[order_id] = sha256_file(path)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica la captura de OnlineBPH en cinco pedidos.")
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--external", type=Path, default=REPO_ROOT / "paper/external/pct")
    parser.add_argument("--external-python", type=Path, default=None)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        print("la carpeta de salida ya existe", file=sys.stderr)
        return 2
    protocol_path = args.protocol.expanduser().resolve()
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expected = [row["order_id"] for row in protocol["smoke"]["orders"]]
    if expected != list(ORDER_IDS):
        print("los pedidos del protocolo no son los cinco del smoke", file=sys.stderr)
        return 2
    dataset = args.dataset.expanduser().resolve()
    dataset_sha = sha256_file(dataset)
    if dataset_sha != protocol["dataset_sha256"]:
        print("el hash del dataset no coincide", file=sys.stderr)
        return 2
    external = args.external.expanduser().resolve()
    commit = _external_commit(external)
    if commit != protocol["external"]["commit"]:
        print("el commit externo no coincide con el protocolo", file=sys.stderr)
        return 2
    external_python = args.external_python or (external / ".venv" / "bin" / "python")
    if not external_python.is_file():
        print("no existe el intérprete aislado", file=sys.stderr)
        return 2
    previous = _previous_hashes()
    code = {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_FILES}
    output.mkdir(parents=True)
    atomic_write_json(
        output / "preflight.json",
        {
            "status": "registrado_antes_de_ejecutar",
            "reason": REASON,
            "previous_smoke": str(PREVIOUS_SMOKE),
            "previous_online_bph_result_sha256": previous,
            "replaces_previous_scores": False,
            "protocol": str(protocol_path),
            "protocol_sha256": sha256_file(protocol_path),
            "orders": protocol["smoke"]["orders"],
            "order_ids": list(ORDER_IDS),
            "dataset": str(dataset),
            "dataset_sha256": dataset_sha,
            "code_sha256": code,
            "external_commit": commit,
            "external_python": str(external_python),
            "timeout_seconds": TIMEOUT_SECONDS,
            "attempts": 1,
            "device": "cpu",
            "methods": ["online_bph"],
            "greedy_rerun": False,
            "confirmatory": False,
            "physical_stability_verified": None,
        },
    )
    prepare_imports()
    from splits import load_orders

    loaded = load_orders(dataset)
    by_id = {row["order_id"]: row for row in protocol["smoke"]["orders"]}
    rows = []
    for order_id in ORDER_IDS:
        order = by_id[order_id]
        snapshot = problem_snapshot(build_compact_problem(loaded, order_id))
        case_root = output / "cases" / order_id
        atomic_write_json(case_root / "input.json", snapshot)
        case_dir = case_root / "online_bph"
        job = {
            "order_id": order_id,
            "target": order["target"],
            "dataset": str(dataset),
            "dataset_sha256": dataset_sha,
            "external_repo": str(external),
            "attempts": 1,
            "snapshot": snapshot,
        }
        outcome = invoke_worker(
            job,
            case_dir=case_dir,
            timeout_s=TIMEOUT_SECONDS,
            command=[
                str(external_python),
                str(TOOLS / "online_bph_worker.py"),
                "--job",
                str(case_dir / "job.json"),
                "--result",
                str(case_dir / "worker_result.partial"),
            ],
        )
        audit_started = time.perf_counter()
        volume = float(snapshot["containers"][0]["volume_mm3"])
        row = evaluate_outcome(
            outcome,
            order_id=order_id,
            method="online_bph",
            target=order["target"],
            container_volume_mm3=volume,
            run_id="16a-onlinebph-capture",
            snapshot=_snapshot_for(snapshot),
        )
        timings = dict(outcome.get("timings") or {}) if isinstance(outcome.get("timings"), dict) else {}
        timings["process_wall_seconds"] = outcome.get("duration_seconds")
        recipe = (outcome.get("capture") or {}).get("recipe") if isinstance(outcome.get("capture"), dict) else {}
        if isinstance(recipe, dict) and recipe.get("input_changed") is True:
            row["failure_types"] = list(dict.fromkeys([*(row.get("failure_types") or []), "input_changed"]))
            row["effective_u_geom"] = 0.0
        row["physical_stability_verified"] = None
        if row.get("failure_types"):
            row["effective_u_geom"] = 0.0
        audit = row.pop("audits", {"status": outcome.get("status"), "error": outcome.get("error")})
        atomic_write_json(case_dir / "worker.json", {key: value for key, value in outcome.items() if key != "capture"})
        if isinstance(outcome.get("capture"), dict):
            atomic_write_json(case_dir / "capture.json", outcome["capture"])
        atomic_write_json(case_dir / "audit.json", audit)
        atomic_write_json(case_dir / "result.json", row)
        timings["audit_and_write_seconds"] = time.perf_counter() - audit_started
        atomic_write_json(case_dir / "timings.json", timings)
        rows.append(
            {
                "order_id": order_id,
                "target": order["target"],
                "worker_status": row.get("worker_status"),
                "capture_present": isinstance(outcome.get("capture"), dict),
                "input_mismatch": row.get("input_mismatch"),
                "geometry_invalid": row.get("geometry_invalid"),
                "effective_u_geom": row.get("effective_u_geom"),
                "failure_types": row.get("failure_types"),
                "timings": timings,
            }
        )
    unchanged = _previous_hashes() == previous
    atomic_write_json(
        output / "manifest.json",
        {
            "status": "complete",
            "confirmatory": False,
            "n_orders": len(ORDER_IDS),
            "methods_executed": ["online_bph"],
            "cases": rows,
            "previous_results_unchanged": unchanged,
            "physical_stability_verified": None,
            "superiority_claimed": False,
            "statistical_comparison": False,
        },
    )
    if not unchanged:
        print("los resultados anteriores cambiaron", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
