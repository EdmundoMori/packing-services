"""Puntuación y packing de desarrollo. Usa el encoder, la política y el bucle existentes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from ablation_aggregate import aggregate_development, expected_case_keys
from ablation_contract import ARMS, AblationError, load_contract, sha256_file
from ablation_train import configure_process_threads, load_research_checkpoint
from normalization_features import transform_rows
from pilot_common import REPO_ROOT, TIMEOUT_SECONDS, atomic_write_json
from pilot_problems import capture_document, prepare_imports, shared_config

PACKING_CODE_FILES = (
    "paper/tools/ablation_pack.py",
    "paper/tools/ablation_worker.py",
    "paper/tools/ablation_aggregate.py",
    "paper/tools/run_normalization_ablation.py",
)
TARGET_BOXES = {
    "euro-pallet": ("EURO_PALLET", 1200.0, 800.0, 2000.0),
    "rollcontainer": ("ROLLCONTAINER", 800.0, 700.0, 2000.0),
}
Worker = Callable[[dict[str, Any]], dict[str, Any]]

PROTOCOL_07 = Path(__file__).resolve().parents[1] / "protocols" / "07_independent_evaluation.json"


class AblationScoreBackend:
    """Aplica la transformación del artefacto una vez y puntúa en eval, sin gradientes."""

    def __init__(self, checkpoint: dict[str, Any]) -> None:
        configure_process_threads()
        prepare_imports()
        import torch
        from torch import nn
        from packing_services.online.features import FEATURE_DIM

        self.arm = checkpoint["arm"]
        self.stats = checkpoint["transform"]["statistics"]
        hidden = int(checkpoint["hidden_size"])
        model = nn.Sequential(
            nn.Linear(FEATURE_DIM, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        self._torch = torch
        self._model = model

    def score(self, rows: list[list[float]]) -> list[float]:
        if not rows:
            return []
        import numpy as np

        transformed = transform_rows(np.asarray(rows, dtype=np.float64), self.stats, arm=self.arm)
        self._model.eval()
        with self._torch.no_grad():
            tensor = self._torch.tensor(transformed, dtype=self._torch.float32)
            logits = self._model(tensor).squeeze(-1)
            if logits.ndim == 0:
                return [float(logits.item())]
            return [float(value) for value in logits.tolist()]


def build_case_plan(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """50 heurísticas compartidas y 500 actores. La heurística no se replica por semilla."""

    cases: list[dict[str, Any]] = []
    for order in contract["orders"]:
        cases.append(
            {
                "role": "heuristic",
                "seed": None,
                "arm": None,
                "order_id": order["order_id"],
                "target": order["target"],
            }
        )
    for seed in contract["seeds"]:
        for arm in ARMS:
            for order in contract["orders"]:
                cases.append(
                    {
                        "role": arm,
                        "seed": seed,
                        "arm": arm,
                        "order_id": order["order_id"],
                        "target": order["target"],
                        "checkpoint": f"models/{arm}_seed{seed}.pt",
                    }
                )
    heuristic = sum(1 for case in cases if case["role"] == "heuristic")
    actors = len(cases) - heuristic
    if heuristic != len(contract["orders"]) or actors != len(contract["seeds"]) * len(ARMS) * len(contract["orders"]):
        raise AblationError("el plan no tiene una heurística por pedido y diez pasadas de actor")
    return cases


def dataset_sha256_expected() -> str:
    document = json.loads(PROTOCOL_07.read_text(encoding="utf-8"))
    return str(document["orders"]["source_dataset_sha256"])


def _loop_arguments(problem: Any) -> dict[str, Any]:
    prepare_imports()
    from packing_services.online.budget import InformationBudget
    from packing_services.online.params import resolve_selection, support_threshold

    params = dict(problem.algorithm.parameters)
    return {
        "budget": InformationBudget.from_parameters(params),
        "selection": resolve_selection(params),
        "min_support_ratio": support_threshold(params, problem.constraints.basic_stability),
        "params": params,
    }


def run_actor_problem(problem: Any, checkpoint: dict[str, Any]) -> Any:
    """Política aprendida existente sobre el bucle existente. No usa el loader de producción."""

    prepare_imports()
    from packing_services.algorithms.base import build_solution
    from packing_services.algorithms.drl_policy_3d_bpp import METADATA
    from packing_services.online.learned.policy import LearnedPlacementPolicy
    from packing_services.online.loop import run_online_loop
    from packing_services.online.params import maybe_wrap_consolidating
    from packing_services.utils.timing import measure_time

    arguments = _loop_arguments(problem)
    policy = maybe_wrap_consolidating(
        LearnedPlacementPolicy(AblationScoreBackend(checkpoint)),
        problem,
        arguments["params"],
    )
    with measure_time() as elapsed:
        packed, unpacked = run_online_loop(
            problem,
            budget=arguments["budget"],
            selection=arguments["selection"],
            min_support_ratio=arguments["min_support_ratio"],
            policy=policy,
        )
    return build_solution(
        problem=problem,
        metadata=METADATA,
        packed_items=packed,
        unpacked_items=unpacked,
        execution_time_seconds=elapsed.seconds,
    )


def run_heuristic_problem(problem: Any) -> Any:
    prepare_imports()
    from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic

    return Online3DBPPHeuristic().run(problem)


def verify_research_artifacts(run_dir: Path, verification: dict[str, Any], statistics_sha: str) -> None:
    """Comprueba hash, brazo y semilla del contenido. Un nombre de archivo no basta."""

    run_path = run_dir.expanduser().resolve()
    models = verification.get("models") or []
    if len(models) != 10:
        raise AblationError("la verificación de entrenamiento no lista diez modelos")
    seen: set[tuple[str, int]] = set()
    for row in models:
        path = run_path / row["path"]
        if sha256_file(path) != row["sha256"]:
            raise AblationError(f"el hash del artefacto no coincide con la verificación: {row['path']}")
        loaded = load_research_checkpoint(path, expected_standardizer_sha256=statistics_sha)
        arm = loaded["arm"]
        seed = int(loaded["seed"])
        if arm != row["arm"] or seed != int(row["seed"]):
            raise AblationError(f"el contenido no coincide con brazo y semilla: {row['path']}")
        if (arm, seed) in seen:
            raise AblationError("artefacto repetido")
        seen.add((arm, seed))
    if seen != {(arm, seed) for arm in ARMS for seed in (42, 43, 44, 45, 46)}:
        raise AblationError("los artefactos no cubren los dos brazos y las cinco semillas")


def assert_geometric_equivalence(actor: dict[str, Any], heuristic: dict[str, Any]) -> None:
    if shared_config(actor) != shared_config(heuristic):
        raise AblationError("los métodos no reciben la misma geometría")
    if not actor.get("model_path") or heuristic.get("model_path") is not None:
        raise AblationError("la ruta de modelo no queda solo en el actor")


def snapshot_for_case(base: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Copia el snapshot geométrico y fija la ruta de modelo de ese caso."""

    snapshot = json.loads(json.dumps(base))
    if case["role"] == "heuristic":
        snapshot["model_path"] = None
        snapshot["algorithm"] = "online_3d_bpp_heuristic"
    else:
        snapshot["model_path"] = str(case["checkpoint"])
        snapshot["algorithm"] = "drl_policy_3d_bpp"
    return snapshot


def _effective_configuration(snapshot: dict[str, Any], target: str) -> None:
    if snapshot.get("lookahead_p") != 1 or snapshot.get("select_s") != 1:
        raise AblationError("p o s efectivos distintos del protocolo")
    if snapshot.get("sort_strategy") != "input_order" or snapshot.get("selection") != "best_fit":
        raise AblationError("el orden o la selección efectivos no son los del protocolo")
    if snapshot.get("problem_type") != "3D_BPP" or snapshot.get("n_containers") != 1:
        raise AblationError("el tipo o el número de contenedores no son los del protocolo")
    flags = snapshot.get("constraints") or {}
    expected_flags = {
        "non_overlap": True,
        "containment": True,
        "allow_rotation": True,
        "max_weight": True,
        "basic_stability": False,
        "load_bearing": False,
        "fragility": False,
        "unloading_sequence": False,
    }
    for key, value in expected_flags.items():
        if flags.get(key) is not value:
            raise AblationError(f"la restricción efectiva {key} no es la del protocolo")
    container = snapshot["containers"][0]
    identity, length, width, height = TARGET_BOXES[target]
    if container["id"] != identity or container["max_weight_kg"] != 1500.0:
        raise AblationError("el contenedor efectivo no es el del target")
    if (container["length_mm"], container["width_mm"], container["height_mm"]) != (length, width, height):
        raise AblationError("las dimensiones efectivas no son las del target")


def build_order_snapshots(
    orders: dict[str, Any],
    order_id: str,
    target: str,
    checkpoint_path: Path,
) -> dict[str, dict[str, Any]]:
    prepare_imports()
    from problems import order_to_problem
    from pilot_problems import problem_snapshot

    source_target = str((orders[order_id].get("properties") or {}).get("target") or "")
    if source_target != target:
        raise AblationError(f"el target del dataset no coincide con la muestra: {order_id}")
    actor = problem_snapshot(
        order_to_problem(
            orders,
            order_id,
            lookahead_p=1,
            select_s=1,
            algorithm_name="drl_policy_3d_bpp",
            model_path=str(checkpoint_path),
        )
    )
    heuristic = problem_snapshot(
        order_to_problem(
            orders,
            order_id,
            lookahead_p=1,
            select_s=1,
            algorithm_name="online_3d_bpp_heuristic",
            model_path=None,
        )
    )
    assert_geometric_equivalence(actor, heuristic)
    _effective_configuration(actor, target)
    _effective_configuration(heuristic, target)
    return {"actor": actor, "heuristic": heuristic}


def packing_provenance(run_dir: Path) -> dict[str, Any]:
    """Separa el código que entrenó del código que empaquetará. No reescribe el entrenamiento."""

    training = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    verification = json.loads((run_dir / "training_verification.json").read_text(encoding="utf-8"))
    return {
        "training_code_sha256": training.get("code_sha256"),
        "training_commit": verification.get("executed_commit"),
        "model_sha256": {row["path"]: row["sha256"] for row in verification["models"]},
        "packing_code_sha256": {name: sha256_file(REPO_ROOT / name) for name in PACKING_CODE_FILES},
    }


def preflight_packing(
    contract: dict[str, Any],
    run_dir: Path,
    orders: dict[str, Any],
) -> dict[str, Any]:
    verification_path = run_dir / "training_verification.json"
    if not verification_path.is_file():
        raise AblationError("falta training_verification.json")
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if verification.get("training_status") != "complete" or verification.get("discrepancies"):
        raise AblationError("la verificación de entrenamiento no está limpia")
    if verification.get("protocol_sha256") != contract["protocol_sha256"]:
        raise AblationError("el protocolo no es el del entrenamiento")
    if verification.get("freeze_sha256") != contract["freeze_sha256"]:
        raise AblationError("el congelado no es el del entrenamiento")
    if verification.get("standardizer_sha256") != contract["standardizer_sha256"]:
        raise AblationError("las estadísticas no son las del entrenamiento")
    verify_research_artifacts(run_dir, verification, contract["standardizer_sha256"])
    order_ids = [row["order_id"] for row in contract["orders"]]
    if order_ids != sorted(order_ids) or len(order_ids) != 50:
        raise AblationError("la muestra no conserva los 50 ids en orden")
    reference = run_dir / verification["models"][0]["path"]
    snapshots: dict[str, dict[str, Any]] = {}
    for row in contract["orders"]:
        if row["order_id"] not in orders:
            raise AblationError(f"el pedido no está en el dataset: {row['order_id']}")
        snapshots[row["order_id"]] = build_order_snapshots(orders, row["order_id"], row["target"], reference)
    if len(expected_case_keys(contract["orders"], contract["seeds"])) != 550:
        raise AblationError("el plan no tiene 550 claves")
    return {"snapshots": snapshots, "provenance": packing_provenance(run_dir)}


def row_from_outcome(
    outcome: dict[str, Any],
    case: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    from pilot_metrics import evaluate_outcome

    method = "heuristic" if case["role"] == "heuristic" else "actor"
    volume = float(snapshot["containers"][0]["volume_mm3"])
    evaluated = evaluate_outcome(
        outcome,
        order_id=case["order_id"],
        method=method,
        target=case["target"],
        container_volume_mm3=volume,
        run_id="normalization-ablation",
        snapshot=snapshot,
    )
    evaluated["role"] = case["role"]
    evaluated["seed"] = None if case["role"] == "heuristic" else int(case["seed"])
    evaluated["failure"] = bool(evaluated["failure_types"])
    evaluated["physical_stability_verified"] = None
    if evaluated["failure"]:
        evaluated["effective_u_geom"] = 0.0
    return evaluated


def execute_packing_cases(
    cases: list[dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    output_dir: Path,
    *,
    timeout_s: float = TIMEOUT_SECONDS,
    worker: Worker | None = None,
) -> list[dict[str, Any]]:
    """Un proceso por caso. Un fallo de worker continúa; un error del evaluador se propaga."""

    from pilot_execute import invoke_worker
    import subprocess

    rows: list[dict[str, Any]] = []
    worker_script = Path(__file__).resolve().parent / "ablation_worker.py"
    for case in cases:
        name = _case_name(case)
        case_dir = output_dir / "cases" / name
        if (case_dir / "result.json").exists():
            raise AblationError(f"el caso {name} ya existe; no hay reintento")
        case_dir.mkdir(parents=True, exist_ok=True)
        base = snapshots.get(case["order_id"])
        if base is None:
            raise AblationError(f"no hay snapshot independiente para {case['order_id']}")
        snapshot = snapshot_for_case(base["heuristic" if case["role"] == "heuristic" else "actor"], case)
        atomic_write_json(case_dir / "input.json", snapshot)
        job = {
            "role": case["role"],
            "arm": case.get("arm"),
            "seed": case.get("seed"),
            "order_id": case["order_id"],
            "target": case["target"],
            "dataset": case["dataset"],
            "checkpoint": case.get("checkpoint"),
            "lookahead_p": 1,
            "select_s": 1,
            "standardizer_sha256": case.get("standardizer_sha256"),
            "attempts": 1,
        }
        if worker is None:
            outcome = invoke_worker(
                job,
                case_dir=case_dir,
                timeout_s=timeout_s,
                command=[
                    sys.executable,
                    str(worker_script),
                    "--job",
                    str(case_dir / "job.json"),
                    "--result",
                    str(case_dir / "worker_result.partial"),
                ],
            )
        else:
            try:
                outcome = worker(job)
            except subprocess.TimeoutExpired:
                outcome = {
                    "status": "timeout",
                    "error": f"timeout de {timeout_s} segundos",
                    "worker_failure": "timeout",
                    "attempts": 1,
                    "duration_seconds": float(timeout_s),
                    "capture": None,
                }
            except Exception as exc:
                outcome = {
                    "status": "crash",
                    "error": f"{type(exc).__name__}: {exc}",
                    "worker_failure": "crash",
                    "attempts": 1,
                    "duration_seconds": None,
                    "capture": None,
                }
        if not isinstance(outcome, dict):
            raise AblationError("el evaluador recibió un resultado que no es un objeto")
        row = row_from_outcome(outcome, case, snapshot)
        audit = row.pop("audits", {"status": outcome.get("status"), "error": outcome.get("error")})
        atomic_write_json(case_dir / "worker.json", {key: value for key, value in outcome.items() if key != "capture"})
        if isinstance(outcome.get("capture"), dict):
            atomic_write_json(case_dir / "capture.json", outcome["capture"])
        atomic_write_json(case_dir / "audit.json", audit)
        atomic_write_json(case_dir / "result.json", row)
        rows.append(row)
    return rows


def pack_case(
    orders: dict[str, Any],
    case: dict[str, Any],
    *,
    dataset_path: Path,
    checkpoint: dict[str, Any] | None,
    lookahead_p: int = 1,
    select_s: int = 1,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convierte el pedido con el código de producción y captura con el evaluador anterior."""

    prepare_imports()
    from pilot_metrics import evaluate_outcome
    from problems import order_to_problem

    dataset = dataset_path.expanduser().resolve()
    order_id = case["order_id"]
    role = case["role"]
    if role == "heuristic":
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name="online_3d_bpp_heuristic",
            model_path=None,
        )
        solution = run_heuristic_problem(problem)
        method = "heuristic"
        checkpoint_path = dataset
    else:
        if checkpoint is None:
            raise AblationError("el actor no tiene artefacto")
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name="drl_policy_3d_bpp",
            model_path=str(case.get("checkpoint") or "research-artifact"),
        )
        solution = run_actor_problem(problem, checkpoint)
        method = "actor"
        checkpoint_path = Path(str(case.get("checkpoint") or "research-artifact"))
    document = capture_document(
        problem,
        solution,
        method=method,
        order_id=order_id,
        orders_path=dataset,
        orders_sha256=sha256_file(dataset) if dataset.is_file() else "",
        checkpoint_path=checkpoint_path,
    )
    container = problem.containers[0]
    volume = float(container.length) * float(container.width) * float(container.height)
    outcome = {
        "status": "ok",
        "error": None,
        "duration_seconds": solution.metrics.execution_time_seconds,
        "capture": document,
    }
    evaluated = evaluate_outcome(
        outcome,
        order_id=order_id,
        method=method,
        target=case["target"],
        container_volume_mm3=volume,
        run_id="normalization-ablation",
        snapshot=snapshot,
    )
    evaluated["role"] = role
    evaluated["seed"] = case.get("seed")
    evaluated["failure"] = bool(evaluated["failure_types"])
    if evaluated["failure"]:
        evaluated["effective_u_geom"] = 0.0
    return evaluated


def assert_training_ready(run_dir: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    run_path = run_dir.expanduser().resolve()
    manifest_path = run_path / "manifest.json"
    if not manifest_path.is_file():
        raise AblationError("no hay manifiesto de entrenamiento")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != "training" or manifest.get("status") != "complete":
        raise AblationError("el entrenamiento no está completo")
    if manifest.get("protocol_sha256") != contract["protocol_sha256"]:
        raise AblationError("el entrenamiento pertenece a otro protocolo")
    if manifest.get("standardizer_sha256") != contract["standardizer_sha256"]:
        raise AblationError("el entrenamiento no usa las estadísticas congeladas")
    models = manifest.get("models") or []
    if len(models) != 10:
        raise AblationError("el entrenamiento no tiene diez artefactos")
    seen: set[tuple[str, int]] = set()
    for row in models:
        key = (row["arm"], int(row["seed"]))
        if key in seen or row["arm"] not in ARMS or int(row["seed"]) not in contract["seeds"]:
            raise AblationError("los artefactos no cubren los dos brazos y las cinco semillas")
        seen.add(key)
        load_research_checkpoint(
            run_path / row["path"],
            expected_standardizer_sha256=contract["standardizer_sha256"],
        )
    if (run_path / "packing").exists():
        raise AblationError("la carpeta de packing ya existe; no se mezcla otra ejecución")
    return models


def run_packing_stage(
    *,
    protocol_path: Path,
    freeze_path: Path,
    run_dir: Path,
    dataset_path: Path,
    command: list[str],
    timeout_s: float = TIMEOUT_SECONDS,
    worker: Worker | None = None,
) -> dict[str, Any]:
    """550 casos, un proceso cada uno. Un fallo de worker continúa; un error interno queda incompleto."""

    contract = load_contract(protocol_path, freeze_path)
    run_path = run_dir.expanduser().resolve()
    assert_training_ready(run_path, contract)
    dataset = dataset_path.expanduser().resolve()
    expected = dataset_sha256_expected()
    if sha256_file(dataset) != expected:
        raise AblationError("el hash del dataset no es el del protocolo geométrico")
    prepare_imports()
    from splits import load_orders

    orders = load_orders(dataset)
    report = preflight_packing(contract, run_path, orders)
    packing = run_path / "packing"
    if packing.exists():
        raise AblationError("la carpeta de packing ya existe; no se mezcla otra ejecución")
    packing.mkdir()
    provenance = report["provenance"]
    manifest: dict[str, Any] = {
        "stage": "packing",
        "status": "running",
        "confirmatory": False,
        "command": command,
        "dataset_sha256": expected,
        "timeout_seconds": timeout_s,
        "attempts": 1,
        "device": "cpu",
        "cuda_visible_devices": "",
        "threads": {"torch.set_num_threads": 1, "torch.set_num_interop_threads": 1},
        "training_code_sha256": provenance["training_code_sha256"],
        "training_commit": provenance["training_commit"],
        "packing_code_sha256": provenance["packing_code_sha256"],
        "model_sha256": provenance["model_sha256"],
        "n_cases_expected": 550,
        "cases_written": 0,
    }
    atomic_write_json(packing / "manifest.json", manifest)
    try:
        cases: list[dict[str, Any]] = []
        for case in build_case_plan(contract):
            item = dict(case)
            item["dataset"] = str(dataset)
            item["standardizer_sha256"] = contract["standardizer_sha256"]
            if case["role"] != "heuristic":
                item["checkpoint"] = str((run_path / case["checkpoint"]).resolve())
            cases.append(item)
        rows = execute_packing_cases(
            cases,
            report["snapshots"],
            packing,
            timeout_s=timeout_s,
            worker=worker,
        )
        manifest["cases_written"] = len(rows)
        if len(rows) != 550:
            raise AblationError("la etapa no cerró las 550 claves")
        summary = aggregate_development(rows, contract["orders"], seeds=contract["seeds"])
        atomic_write_json(packing / "aggregate.json", summary)
        manifest["status"] = "complete"
        manifest["advance_continue"] = summary["advance"]["continue_with_this_configuration"]
    except Exception as exc:
        manifest["status"] = "incomplete"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        atomic_write_json(packing / "manifest.json", manifest)
        raise
    atomic_write_json(packing / "manifest.json", manifest)
    return manifest


def _case_name(case: dict[str, Any]) -> str:
    if case["role"] == "heuristic":
        return f"heuristic__{case['order_id']}"
    return f"{case['arm']}__seed{case['seed']}__{case['order_id']}"
