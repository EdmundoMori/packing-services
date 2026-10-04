"""Entrena una vez las seis combinaciones. No empaqueta ni elige semilla."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import torch

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
STUDY = HERE.parent
for _entry in (str(PAPER_TOOLS), str(HERE)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from actor_features import FEATURE_NAMES  # noqa: E402
from campaign import directory_must_be_new, file_sha256  # noqa: E402
from model_spec import TRAINING_CONFIG, configure_torch_runtime  # noqa: E402
from pilot_common import REPO_ROOT, sha256_file  # noqa: E402
from train_loop import (  # noqa: E402
    PairingError,
    aggregate_regret,
    epoch_permutations,
    forward_logits,
    initialization_sha256,
    normalize_once,
    normalized_ranges,
    paired_start,
    permutation_sha256,
    ranking_rows,
    signal_summary,
    train_arm,
    weights_equal,
)

EXPECTED_PROTOCOL_SHA256 = "5fd74cc0a6fc52aaf248a977934d9e199919096aa82c3ae6b0309a03e6aa6946"
EXPECTED_HEAD = "83b5e1c59808bd761f4c6fc47234c7dc232468d1"
CODE_FILES = (
    "paper/studies/counterfactual_ranking/tools/actor_features.py",
    "paper/studies/counterfactual_ranking/tools/objectives.py",
    "paper/studies/counterfactual_ranking/tools/model_spec.py",
    "paper/studies/counterfactual_ranking/tools/train_loop.py",
    "paper/studies/counterfactual_ranking/tools/run_learning_training.py",
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_states(results: dict, stats: dict, execution_order: list[str]) -> list[dict[str, Any]]:
    catalog = {order["order_id"]: order for order in results["orders"]}
    states = []
    for order_id in execution_order:
        order = catalog[order_id]
        for state in sorted(order["states"], key=lambda item: item["choice_index"]):
            if not state.get("eligible_for_learning"):
                continue
            features = [row["features"] for row in state["alternatives"]]
            q_values = [float(row["q_hat"]) for row in state["alternatives"]]
            states.append(
                {
                    "split": order["split"],
                    "target": order["target"],
                    "order_id": order_id,
                    "choice_index": state["choice_index"],
                    "features": normalize_once(features, stats),
                    "q_hats": torch.tensor(q_values, dtype=torch.float64),
                    "q_float64": q_values,
                }
            )
    return states


def _require_counts(states: list[dict[str, Any]]) -> None:
    train = [state for state in states if state["split"] == "train"]
    development = [state for state in states if state["split"] == "development"]
    train_orders = {state["order_id"] for state in train}
    development_orders = {state["order_id"] for state in development}
    train_rows = sum(int(state["features"].shape[0]) for state in train)
    development_rows = sum(int(state["features"].shape[0]) for state in development)
    if (len(train_orders), len(development_orders), len(train), len(development), train_rows, development_rows) != (
        24,
        12,
        96,
        48,
        368,
        185,
    ):
        raise SystemExit("bloqueo: los conteos de estados o filas no son los de las etiquetas")


def _checkpoint(model: torch.nn.Module, *, arm: str, seed: int, stats: dict) -> dict:
    return {
        "arm": arm,
        "seed": seed,
        "epoch": 40,
        "contract": "counterfactual-actor-v1",
        "feature_names": list(FEATURE_NAMES),
        "normalization": stats,
        "state_dict": model.state_dict(),
        "effective_config": dict(TRAINING_CONFIG),
    }


def _subset(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen = []
    seen = set()
    for state in states:
        if state["split"] != "development" or state["order_id"] in seen:
            continue
        seen.add(state["order_id"])
        if state["choice_index"] == min(
            item["choice_index"] for item in states if item["order_id"] == state["order_id"]
        ):
            chosen.append(state)
    return chosen


def _logits_snapshot(model: torch.nn.Module, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    with torch.no_grad():
        for state in states:
            rows.append(
                {
                    "order_id": state["order_id"],
                    "choice_index": state["choice_index"],
                    "logits": forward_logits(model, state["features"]).detach().cpu().tolist(),
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--normalization", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    started = time.perf_counter()
    protocol_path = Path(args.protocol)
    protocol_sha = file_sha256(protocol_path)
    if protocol_sha != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit("bloqueo: el protocolo congelado cambió")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if list(protocol["features"]["kept_columns"]) != list(FEATURE_NAMES):
        raise SystemExit("bloqueo: el contrato de columnas no coincide")
    dataset_sha = sha256_file(Path(protocol["dataset"]["path"]))
    if dataset_sha != protocol["dataset"]["sha256"]:
        raise SystemExit("bloqueo: el dataset cambió")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    if head != EXPECTED_HEAD:
        raise SystemExit(f"bloqueo: HEAD es {head}")
    configure_torch_runtime()
    results = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    stats = json.loads(Path(args.normalization).read_text(encoding="utf-8"))
    states = _load_states(results, stats, protocol["execution_order"])
    _require_counts(states)
    directory_must_be_new(output)
    output.mkdir(parents=True, exist_ok=False)
    train_states = [state for state in states if state["split"] == "train"]
    development_states = [state for state in states if state["split"] == "development"]
    annex = STUDY / "training_operational_annex.md"
    manifest = {
        "role": "manifiesto_previo_al_ajuste",
        "training_started": False,
        "head": head,
        "protocol_sha256": protocol_sha,
        "labels_sha256": file_sha256(Path(args.labels)),
        "normalization_sha256": file_sha256(Path(args.normalization)),
        "dataset_sha256": dataset_sha,
        "annex_sha256": file_sha256(annex),
        "code_sha256": {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_FILES},
        "config": TRAINING_CONFIG,
        "environment": {
            "python": sys.version,
            "torch": torch.__version__,
            "platform": platform.platform(),
            "device": "cpu",
            "torch_num_threads": 1,
        },
        "seeds": [11, 23, 37],
        "packing_episodes_executed": False,
        "final_test_selected": False,
    }
    _write(output / "manifest.json", manifest)
    _write(
        output / "signal_diagnostic.json",
        {
            "role": "diagnostico_descriptivo_previo_al_ajuste",
            "pairs_are_not_independent_orders": True,
            "changed_losses_or_hyperparameters": False,
            "by_split_target": signal_summary(states),
            "normalized_ranges": normalized_ranges(states, list(FEATURE_NAMES)),
        },
    )
    manifest["training_started"] = True
    _write(output / "manifest.json", manifest)
    runs = []
    incomplete = False
    subset = _subset(development_states)
    for seed in (11, 23, 37):
        record: dict[str, Any] = {"seed": seed, "status": "pending"}
        try:
            classification, preferences, init_hash = paired_start(seed)
            permutations = epoch_permutations(len(train_states), 40, seed)
            perm_hash = permutation_sha256(permutations)
            if not weights_equal(classification, preferences):
                raise PairingError("los tensores iniciales dejaron de coincidir")
            record.update(
                {
                    "initialization_sha256": init_hash,
                    "permutation_sha256": perm_hash,
                    "permutations": permutations,
                }
            )
            _write(output / "pairings" / f"seed_{seed}.json", record)
            started_seed = time.perf_counter()
            for arm, model in (("classification", classification), ("preferences", preferences)):
                history = train_arm(model, train_states, permutations, arm)
                if len(history) != 40 or history[-1]["epoch"] != 40:
                    raise RuntimeError("el historial no termina en la época 40")
                if any(not torch.isfinite(torch.tensor(row["loss"])) for row in history):
                    raise FloatingPointError("el historial contiene una pérdida no finita")
                blob = _checkpoint(model, arm=arm, seed=seed, stats=stats)
                path = output / "checkpoints" / f"{arm}_seed_{seed}.pt"
                path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(blob, path)
                logits = _logits_snapshot(model, subset)
                _write(output / "histories" / f"{arm}_seed_{seed}.json", {"history": history, "subset_logits": logits})
                ranking = {
                    "train": aggregate_regret(ranking_rows(model, train_states)),
                    "development": aggregate_regret(ranking_rows(model, development_states)),
                }
                _write(output / "ranking" / f"{arm}_seed_{seed}.json", ranking)
                record.setdefault("arms", {})[arm] = {
                    "checkpoint": str(path.relative_to(output)),
                    "final_loss": history[-1]["loss"],
                    "seconds": None,
                    "development_regret": ranking["development"]["regret"],
                }
            record["status"] = "completed"
            record["seconds"] = time.perf_counter() - started_seed
        except (PairingError, FloatingPointError, RuntimeError, ValueError, OSError) as exc:
            record["status"] = "incomplete"
            record["error"] = f"{type(exc).__name__}: {exc}"
            incomplete = True
            _write(output / "pairings" / f"seed_{seed}.json", {key: value for key, value in record.items() if key != "permutations"})
        runs.append({key: value for key, value in record.items() if key != "permutations"})
        _write(output / "runs.json", {"incomplete": incomplete, "runs": runs, "elapsed_seconds": time.perf_counter() - started})
    _write(
        output / "campaign.json",
        {
            "status": "incomplete" if incomplete else "completed",
            "incomplete": incomplete,
            "elapsed_seconds": time.perf_counter() - started,
            "runs": runs,
            "packing_gate_applied": False,
            "seed_selected": False,
            "training": True,
            "packing_episodes_executed": False,
        },
    )
    checks = []
    for path in sorted((output / "checkpoints").glob("*.pt")) if (output / "checkpoints").is_dir() else []:
        blob = torch.load(path, map_location="cpu", weights_only=False)
        model = clone_from_checkpoint(blob)
        history_path = output / "histories" / f"{blob['arm']}_seed_{blob['seed']}.json"
        saved = json.loads(history_path.read_text(encoding="utf-8"))["subset_logits"]
        reproduced = _logits_snapshot(model, subset)
        matches = saved == reproduced
        checks.append(
            {
                "checkpoint": path.name,
                "sha256": file_sha256(path),
                "epoch": blob["epoch"],
                "arm": blob["arm"],
                "seed": blob["seed"],
                "logits_match": matches,
            }
        )
    verification = {
        "role": "verificacion_del_ajuste",
        "status": "incomplete" if incomplete or not checks or any(not row["logits_match"] for row in checks) else "completed",
        "packing_gate_applied": False,
        "seed_selected": False,
        "authorizes_packing_evaluation": False,
        "elapsed_seconds": time.perf_counter() - started,
        "checkpoints": checks,
        "runs": runs,
    }
    _write(STUDY / "training_verification.json", verification)
    print(verification["status"], time.perf_counter() - started)


def clone_from_checkpoint(blob: dict) -> torch.nn.Module:
    from model_spec import build_actor

    model = build_actor(0)
    model.load_state_dict(blob["state_dict"])
    return model


if __name__ == "__main__":
    main()
