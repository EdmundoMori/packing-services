"""Smoke de cinco pedidos. No selecciona coeficientes ni entrena."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compact_study import build_compact_problem, smoke_orders  # noqa: E402
from pilot_common import REPO_ROOT, TIMEOUT_SECONDS, atomic_write_json, sha256_file  # noqa: E402
from pilot_execute import invoke_worker  # noqa: E402
from pilot_metrics import evaluate_outcome  # noqa: E402
from pilot_problems import prepare_imports, problem_snapshot  # noqa: E402


CODE_FILES = (
    "paper/tools/compact_study.py",
    "paper/tools/compact_worker.py",
    "paper/tools/online_bph_case.py",
    "paper/tools/online_bph_worker.py",
    "paper/tools/run_compact_smoke.py",
    "src/packing_services/online/policies.py",
    "src/packing_services/online/session.py",
    "src/packing_services/online/loop.py",
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


def _snapshot_for(method: str, snapshot: dict) -> dict:
    copied = dict(snapshot)
    if method == "online_bph":
        copied["algorithm"] = "online_bph"
        copied["selection"] = "online_bph_first_feasible_ems"
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke geométrico de GreedyBestFit y OnlineBPH.")
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
    protocol = json.loads(args.protocol.expanduser().resolve().read_text(encoding="utf-8"))
    chosen = smoke_orders()
    expected = [row["order_id"] for row in protocol["smoke"]["orders"]]
    if [row["order_id"] for row in chosen] != expected:
        print("los pedidos de smoke no coinciden con el protocolo", file=sys.stderr)
        return 2
    dataset = args.dataset.expanduser().resolve()
    dataset_sha = sha256_file(dataset)
    if dataset_sha != protocol["dataset_sha256"]:
        print("el hash del dataset no coincide", file=sys.stderr)
        return 2
    external = args.external.expanduser().resolve()
    external_python = args.external_python or (external / ".venv" / "bin" / "python")
    code = {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_FILES}
    for relative, digest in protocol["code_sha256"].items():
        if code.get(relative) != digest:
            print(f"el código cambió después de congelar el protocolo: {relative}", file=sys.stderr)
            return 2
    commit = _external_commit(external)
    if commit != protocol["external"]["commit"]:
        print("el commit externo no coincide con el protocolo", file=sys.stderr)
        return 2
    output.mkdir(parents=True)
    atomic_write_json(
        output / "preflight.json",
        {
            "status": "registrado_antes_de_ejecutar",
            "orders": chosen,
            "dataset": str(dataset),
            "dataset_sha256": dataset_sha,
            "code_sha256": code,
            "external_commit": commit,
            "external_python": str(external_python),
            "external_python_exists": external_python.is_file(),
            "timeout_seconds": TIMEOUT_SECONDS,
            "attempts": 1,
            "device": "cpu",
            "confirmatory": False,
            "physical_stability_verified": None,
        },
    )
    prepare_imports()
    from splits import load_orders

    loaded = load_orders(dataset)
    snapshots = {}
    for row in chosen:
        snapshots[row["order_id"]] = problem_snapshot(build_compact_problem(loaded, row["order_id"]))
        atomic_write_json(output / "cases" / row["order_id"] / "input.json", snapshots[row["order_id"]])
    methods = [("greedy", [sys.executable, str(TOOLS / "compact_worker.py")])]
    if external_python.is_file():
        methods.append(("online_bph", [str(external_python), str(TOOLS / "online_bph_worker.py")]))
    else:
        atomic_write_json(
            output / "online_bph_blocked.json",
            {"blocked": True, "reason": "no existe el intérprete aislado de OnlineBPH"},
        )
    rows = []
    for order in chosen:
        for method, command in methods:
            case_dir = output / "cases" / order["order_id"] / method
            job = {
                "order_id": order["order_id"],
                "target": order["target"],
                "dataset": str(dataset),
                "dataset_sha256": dataset_sha,
                "external_repo": str(external),
                "attempts": 1,
            }
            if method == "online_bph":
                job["snapshot"] = snapshots[order["order_id"]]
            outcome = invoke_worker(
                job,
                case_dir=case_dir,
                timeout_s=TIMEOUT_SECONDS,
                command=[*command, "--job", str(case_dir / "job.json"), "--result", str(case_dir / "worker_result.partial")],
            )
            audit_started = time.perf_counter()
            volume = float(snapshots[order["order_id"]]["containers"][0]["volume_mm3"])
            row = evaluate_outcome(
                outcome,
                order_id=order["order_id"],
                method=method,
                target=order["target"],
                container_volume_mm3=volume,
                run_id="16-baseline-smoke",
                snapshot=_snapshot_for(method, snapshots[order["order_id"]]),
            )
            timings = dict(outcome.get("timings") or {}) if isinstance(outcome.get("timings"), dict) else {}
            timings["process_wall_seconds"] = outcome.get("duration_seconds")
            timings["startup_seconds"] = float(timings.get("startup_seconds") or 0) + float(timings.get("import_seconds") or 0)
            recipe = (outcome.get("capture") or {}).get("recipe") if isinstance(outcome.get("capture"), dict) else {}
            if isinstance(recipe, dict) and recipe.get("input_changed") is True:
                row["failure_types"] = list(dict.fromkeys([*(row.get("failure_types") or []), "input_changed"]))
                row["effective_u_geom"] = 0.0
                row["failure"] = True
            row["physical_stability_verified"] = None
            if row.get("failure"):
                row["effective_u_geom"] = 0.0
            audit = row.pop("audits", {"status": outcome.get("status"), "error": outcome.get("error")})
            atomic_write_json(case_dir / "worker.json", {key: value for key, value in outcome.items() if key != "capture"})
            if isinstance(outcome.get("capture"), dict):
                atomic_write_json(case_dir / "capture.json", outcome["capture"])
            atomic_write_json(case_dir / "audit.json", audit)
            atomic_write_json(case_dir / "result.json", row)
            timings["audit_and_write_seconds"] = time.perf_counter() - audit_started
            atomic_write_json(case_dir / "timings.json", timings)
            row["timings"] = timings
            rows.append(
                {
                    "order_id": order["order_id"],
                    "target": order["target"],
                    "method": method,
                    "worker_status": row.get("worker_status"),
                    "effective_u_geom": row.get("effective_u_geom"),
                    "failure_types": row.get("failure_types"),
                    "timings": timings,
                }
            )
    atomic_write_json(
        output / "manifest.json",
        {
            "status": "complete",
            "confirmatory": False,
            "n_orders": len(chosen),
            "methods_executed": [method for method, _command in methods],
            "cases": rows,
            "physical_stability_verified": None,
            "superiority_claimed": False,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
