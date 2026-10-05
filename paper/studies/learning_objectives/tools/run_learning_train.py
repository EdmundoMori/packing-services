#!/usr/bin/env python3
"""Campaña de entrenamiento emparejado learning_objectives (9 modelos).

No ejecuta episodios de desarrollo ni test. Presupuesto 1800 s sin ampliación.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_contracts import verify_frozen_artifacts  # noqa: E402
from labeling_io import atomic_write_json  # noqa: E402
from labeling_verify import VERIFIER_VERSION, verify_labeling_output  # noqa: E402
from model_spec import ARMS, TRAINING_CONFIG, configure_torch_runtime  # noqa: E402
from training_data import load_train_states  # noqa: E402
from training_loop import (  # noqa: E402
    TrainingBudgetExceeded,
    run_seed_arms,
)


TRAINING_WALL_SECONDS = 1800.0


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Entrenamiento emparejado learning_objectives")
    p.add_argument("--study-dir", type=Path, required=True)
    p.add_argument("--labels-output", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--wall-seconds", type=float, default=TRAINING_WALL_SECONDS)
    return p.parse_args(argv)


def runtime_document() -> dict[str, Any]:
    import torch

    configure_torch_runtime()
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "torch_version": torch.__version(),
        "dtype": TRAINING_CONFIG["dtype"],
        "device": TRAINING_CONFIG["device"],
        "torch_num_threads": TRAINING_CONFIG["torch_num_threads"],
        "torch_num_interop_threads": TRAINING_CONFIG["torch_num_interop_threads"],
        "training_config": TRAINING_CONFIG,
        "documented_before_fit": True,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study_dir = args.study_dir.resolve()
    labels = args.labels_output.resolve()
    output = args.output.resolve()
    wall = float(args.wall_seconds)
    if wall > TRAINING_WALL_SECONDS:
        print(json.dumps({"status": "refused", "reason": "wall_exceeds_frozen_budget"}))
        return 2

    if output.exists() and any(output.iterdir()):
        print(json.dumps({"status": "refused", "reason": "output_exists", "path": str(output)}))
        return 2

    # Contratos / hashes antes del primer ajuste (sin mutar el árbol de etiquetas)
    contracts = verify_frozen_artifacts(
        protocol_path=study_dir / "protocol_frozen.json",
        sample_path=study_dir / "sample_manifest.json",
        study_dir=study_dir,
    )
    protocol = contracts["protocol"]
    if float(protocol["budget"]["training_wall_seconds"]) != TRAINING_WALL_SECONDS:
        print(json.dumps({"status": "refused", "reason": "protocol_training_budget_mismatch"}))
        return 2

    summary = json.loads((labels / "labeling_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((labels / "execution_manifest.json").read_text(encoding="utf-8"))
    verification = verify_labeling_output(
        output=labels,
        manifest=manifest,
        summary=summary,
        protocol=protocol,
    )
    if not verification.get("ready_for_training"):
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reason": "labels_not_ready",
                    "verification": verification.get("status"),
                    "issues": verification.get("issues", [])[:20],
                },
                ensure_ascii=False,
            )
        )
        return 2

    output.mkdir(parents=True, exist_ok=True)
    for seed in TRAINING_CONFIG["seeds"]:
        for arm in ARMS:
            (output / f"seed_{seed}" / arm).mkdir(parents=True, exist_ok=True)

    runtime = runtime_document()
    pre_manifest = {
        "kind": "training_execution_manifest",
        "written_before_fit": True,
        "study_dir": str(study_dir),
        "labels_output": str(labels),
        "output": str(output),
        "protocol_file_sha256": file_sha256(study_dir / "protocol_frozen.json"),
        "labels_summary_status": summary.get("status"),
        "label_verification_status": verification.get("status"),
        "label_verifier_version": VERIFIER_VERSION,
        "normalization_path": str(labels / "normalization_train.json"),
        "normalization_sha256": verification.get("normalization", {}).get("sha256"),
        "arms": list(ARMS),
        "seeds": list(TRAINING_CONFIG["seeds"]),
        "epochs": TRAINING_CONFIG["epochs"],
        "optimizer_steps_per_model": TRAINING_CONFIG["epochs"],
        "wall_budget_seconds": wall,
        "runtime": runtime,
        "development_selection": False,
        "episodes_executed": False,
        "test_executed": False,
        "note_loss_scales": "magnitudes de pérdida no comparables entre brazos; menor pérdida ≠ mejor packing",
    }
    atomic_write_json(output / "training_manifest.json", pre_manifest)

    states, normalization, data_meta = load_train_states(
        labels_output=labels,
        manifest=manifest,
        normalization_path=labels / "normalization_train.json",
    )
    atomic_write_json(output / "data_meta.json", {**data_meta, "normalization_mean_head": normalization["mean"][:3]})

    deadline = time.perf_counter() + wall
    campaign: dict[str, Any] = {
        "status": "running",
        "started_unix": time.time(),
        "seeds": {},
        "wall_budget_seconds": wall,
    }
    atomic_write_json(output / "training_progress.json", campaign)

    try:
        for seed in TRAINING_CONFIG["seeds"]:
            if time.perf_counter() > deadline:
                raise TrainingBudgetExceeded("presupuesto agotado antes de semilla")
            seed_report = run_seed_arms(
                seed=int(seed),
                states=states,
                output_seed_dir=output / f"seed_{seed}",
                deadline=deadline,
            )
            campaign["seeds"][str(seed)] = seed_report
            atomic_write_json(output / "training_progress.json", campaign)
    except (TrainingBudgetExceeded, FloatingPointError, RuntimeError) as exc:
        campaign["status"] = "incomplete"
        campaign["error"] = str(exc)
        campaign["error_class"] = type(exc).__name__
        campaign["finished_unix"] = time.time()
        atomic_write_json(output / "training_summary.json", campaign)
        atomic_write_json(output / "training_progress.json", campaign)
        print(json.dumps({"status": "incomplete", "error": str(exc)}, ensure_ascii=False))
        return 1

    campaign["status"] = "completed"
    campaign["finished_unix"] = time.time()
    campaign["wall_seconds"] = campaign["finished_unix"] - campaign["started_unix"]
    campaign["n_models"] = len(TRAINING_CONFIG["seeds"]) * len(ARMS)
    campaign["episodes_executed"] = False
    campaign["test_executed"] = False
    campaign["development_gate_applied"] = False
    atomic_write_json(output / "training_summary.json", campaign)
    atomic_write_json(output / "training_progress.json", {**campaign, "status": "completed"})
    print(
        json.dumps(
            {
                "status": "completed",
                "output": str(output),
                "n_models": campaign["n_models"],
                "wall_seconds": campaign["wall_seconds"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
