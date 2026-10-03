"""Puntuación y packing de desarrollo. Usa el encoder, la política y el bucle existentes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ablation_aggregate import aggregate_development
from ablation_contract import ARMS, AblationError, load_contract, sha256_file
from ablation_train import configure_process_threads, load_research_checkpoint
from normalization_features import transform_rows
from pilot_common import atomic_write_json
from pilot_problems import capture_document, prepare_imports

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


def pack_case(
    orders: dict[str, Any],
    case: dict[str, Any],
    *,
    dataset_path: Path,
    checkpoint: dict[str, Any] | None,
    lookahead_p: int = 1,
    select_s: int = 1,
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
) -> dict[str, Any]:
    """550 casos. Se detiene ante un fallo de ejecución y conserva lo ya escrito."""

    contract = load_contract(protocol_path, freeze_path)
    run_path = run_dir.expanduser().resolve()
    assert_training_ready(run_path, contract)
    dataset = dataset_path.expanduser().resolve()
    expected = dataset_sha256_expected()
    if sha256_file(dataset) != expected:
        raise AblationError("el hash del dataset no es el del protocolo geométrico")
    packing = run_path / "packing"
    packing.mkdir()
    manifest: dict[str, Any] = {
        "stage": "packing",
        "status": "running",
        "confirmatory": False,
        "command": command,
        "dataset_sha256": expected,
        "n_cases_expected": 550,
        "cases_written": 0,
    }
    atomic_write_json(packing / "manifest.json", manifest)
    try:
        prepare_imports()
        from splits import load_orders

        orders = load_orders(dataset)
        rows: list[dict[str, Any]] = []
        for case in build_case_plan(contract):
            name = _case_name(case)
            destination = packing / "cases" / name / "result.json"
            if destination.exists():
                raise AblationError(f"el caso {name} ya existe")
            checkpoint = None
            if case["role"] != "heuristic":
                checkpoint = load_research_checkpoint(
                    run_path / case["checkpoint"],
                    expected_standardizer_sha256=contract["standardizer_sha256"],
                )
            evaluated = pack_case(
                orders,
                case,
                dataset_path=dataset,
                checkpoint=checkpoint,
            )
            atomic_write_json(destination, evaluated)
            rows.append(evaluated)
            manifest["cases_written"] += 1
            atomic_write_json(packing / "manifest.json", manifest)
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
