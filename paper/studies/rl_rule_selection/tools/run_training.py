"""Ejecuta el piloto una vez. No evalúa desarrollo ni test."""

from __future__ import annotations

import json
import os
import resource
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import torch

from model import build_actor, build_critic, build_optimizer
from ppo_math import GLOBAL_WALL_SECONDS, SEED_WALL_SECONDS
from train_loop import iter_orders, run_budget, save_checkpoint

SEEDS = (101, 102, 103)
MAX_WORKERS = 2


def _append(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()


def execute_seed(task: dict[str, Any]) -> dict[str, Any]:
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    torch.set_num_threads(1)
    import sys

    tools = Path(__file__).resolve().parent
    paper = tools.parents[2]
    for entry in (str(paper / "tools"), str(paper / "studies" / "counterfactual_ranking" / "tools"), str(tools)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from audit_internal_solution import audit_document
    from compact_study import build_compact_problem
    from environment import RuleSelectionEnv

    output_dir = Path(task["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    history_path = output_dir / "history.jsonl"
    started = time.perf_counter()
    cpu_start = resource.getrusage(resource.RUSAGE_SELF)
    deadline = min(time.time() + SEED_WALL_SECONDS, float(task["global_deadline"]))
    orders = json.loads(Path(task["dataset"]).read_text(encoding="utf-8"))
    rows = task["train_rows"]
    forbidden = set(task["forbidden_ids"])
    by_id = {row["order_id"]: row for row in rows}
    if set(by_id) & forbidden:
        raise RuntimeError("un pedido de desarrollo está dentro de train")
    actor = build_actor()
    critic = build_critic()
    optimizer = build_optimizer(list(actor.parameters()) + list(critic.parameters()))
    save_checkpoint(
        output_dir / "checkpoint_initial.pt",
        actor,
        critic,
        optimizer,
        {"seed": task["seed"], "decisions": 0, "updates": 0, "adam_steps": 0, "status": "inicial"},
    )
    schedule = iter_orders(list(by_id), torch.Generator().manual_seed(int(task["seed"])))
    live: dict[str, Any] = {"env": None, "terminated": True}

    def start_episode() -> dict[str, Any]:
        order_id = next(schedule)
        if order_id in forbidden:
            raise RuntimeError("el calendario pidió un pedido de desarrollo")
        row = by_id[order_id]
        problem = build_compact_problem(orders, order_id)
        env = RuleSelectionEnv()
        observation, info = env.reset(problem)
        return {
            "env": env,
            "order_id": order_id,
            "target": row["target"],
            "n_items": row["n_items"],
            "observation": observation,
            "terminated": bool(info["terminated"]),
        }

    def on_episode(record: dict[str, Any]) -> None:
        record["elapsed_seconds"] = time.perf_counter() - started
        _append(history_path, record)

    def on_update(record: dict[str, Any]) -> None:
        record["elapsed_seconds"] = time.perf_counter() - started
        _append(history_path, record)

    def on_finished(state: dict[str, Any], cause: str) -> None:
        document = state["env"].capture(
            order_id=state["order_id"],
            orders_path=Path(task["dataset"]),
            orders_sha256=task["dataset_sha"],
            description=f"Último episodio completo de la semilla {task['seed']}. Causa: {cause}.",
        )
        (output_dir / "last_capture.json").write_text(
            json.dumps(document, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    summary = run_budget(
        seed=int(task["seed"]),
        actor=actor,
        critic=critic,
        optimizer=optimizer,
        live=live,
        start_episode=start_episode,
        deadline=deadline,
        clock=time.time,
        on_update=on_update,
        on_episode=on_episode,
        on_finished=on_finished,
        checkpoint_path=output_dir / "checkpoint_last.pt",
    )
    last = output_dir / "checkpoint_last.pt"
    final = output_dir / "checkpoint_final.pt"
    if last.is_file():
        final.write_bytes(last.read_bytes())
    else:
        final.write_bytes((output_dir / "checkpoint_initial.pt").read_bytes())
    audit_summary = None
    capture_path = output_dir / "last_capture.json"
    if capture_path.is_file():
        audit = audit_document(json.loads(capture_path.read_text(encoding="utf-8")))
        (output_dir / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        audit_summary = {
            "internal_geometry_valid": audit["internal_geometry_valid"],
            "n_overlap_pairs": audit["n_overlap_pairs"],
            "n_boxes_outside_bin": audit["n_boxes_outside_bin"],
            "physical_stability_verified": audit["physical_stability_verified"],
        }
    cpu_end = resource.getrusage(resource.RUSAGE_SELF)
    manifest = {
        **summary,
        "seed": task["seed"],
        "wall_seconds": time.perf_counter() - started,
        "cpu_user_seconds": cpu_end.ru_utime - cpu_start.ru_utime,
        "cpu_system_seconds": cpu_end.ru_stime - cpu_start.ru_stime,
        "ru_maxrss_kb": cpu_end.ru_maxrss,
        "torch_threads": 1,
        "audit": audit_summary,
        "reward_used_for_selection": False,
        "historical_checkpoint_loaded": False,
    }
    (output_dir / "seed_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def worker_main(task: dict[str, Any], result_queue: Any) -> None:
    try:
        result_queue.put({"kind": "seed", **execute_seed(task)})
    except Exception as exc:
        result_queue.put(
            {
                "kind": "seed",
                "seed": task["seed"],
                "status": "incompleta_error",
                "equal_budget": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )


HASHED_FILES = (
    "tools/ppo_math.py",
    "tools/model.py",
    "tools/train_loop.py",
    "tools/environment.py",
    "tools/observation.py",
    "tools/rules.py",
    "tools/sample_audit.py",
    "tools/run_training.py",
)
EXPECTED_HEAD = "c7191d5fc87b4125795cd168b49c4709bb95a9b8"
EXPECTED_BRANCH = "research/paper-online-packing"


def study_hashes(study: Path) -> dict[str, str]:
    import hashlib

    payload = {}
    for relative in HASHED_FILES:
        payload[relative] = hashlib.sha256((study / relative).read_bytes()).hexdigest()
    return payload


def _rss_kb(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except OSError:
        return 0
    return 0


def run_campaign(study: Path) -> dict[str, Any]:
    import hashlib
    import multiprocessing
    import queue

    protocol_path = study / "protocol_frozen.json"
    if not protocol_path.is_file():
        raise SystemExit("bloqueo: falta protocol_frozen.json")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    current = study_hashes(study)
    if current != protocol["code_hashes"]:
        raise SystemExit("bloqueo: el código no coincide con el protocolo congelado")
    training = study / "training"
    if training.exists() and any(training.iterdir()):
        raise SystemExit("bloqueo: training ya tiene contenido")
    development = json.loads((study / "development_manifest.json").read_text(encoding="utf-8"))
    train = json.loads((study / "train_manifest.json").read_text(encoding="utf-8"))
    train_rows = [row for rows in train["selected"].values() for row in rows]
    forbidden = [row["order_id"] for rows in development["selected"].values() for row in rows]
    if set(row["order_id"] for row in train_rows) & set(forbidden):
        raise SystemExit("bloqueo: desarrollo y train se solapan")
    if development.get("episodes_executed") or development.get("final_test_selected"):
        raise SystemExit("bloqueo: el manifiesto de desarrollo no está sin episodios")
    training.mkdir(parents=True)
    for seed in SEEDS:
        (training / f"seed_{seed}").mkdir()
    started = time.time()
    global_deadline = started + GLOBAL_WALL_SECONDS
    config = {
        "started_unix": started,
        "global_deadline_unix": global_deadline,
        "seeds": list(SEEDS),
        "decisions_per_seed": 6144,
        "rollouts_per_seed": 12,
        "seed_wall_seconds": SEED_WALL_SECONDS,
        "global_wall_seconds": GLOBAL_WALL_SECONDS,
        "max_workers": MAX_WORKERS,
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "code_hashes": current,
        "development_evaluated": False,
        "final_test_selected": False,
        "final_test_executed": False,
    }
    (training / "training_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    _append(training / "events.jsonl", {"kind": "campaign_start", "unix": started})
    paper = study.parents[1]
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [
            str(study / "tools"),
            str(paper / "tools"),
            str(paper / "studies" / "counterfactual_ranking" / "tools"),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    pending = list(SEEDS)
    running: dict[int, Any] = {}
    results: dict[int, dict[str, Any]] = {}
    samples: list[int] = []
    wall_started = time.perf_counter()

    def launch(seed: int) -> None:
        task = {
            "seed": seed,
            "output_dir": str(training / f"seed_{seed}"),
            "dataset": str(protocol["dataset_path"]),
            "dataset_sha": protocol["dataset_sha256"],
            "train_rows": train_rows,
            "forbidden_ids": forbidden,
            "global_deadline": global_deadline,
        }
        process = context.Process(target=worker_main, args=(task, result_queue))
        process.start()
        running[seed] = process
        _append(training / "events.jsonl", {"kind": "seed_start", "seed": seed, "unix": time.time()})

    while pending or running:
        while pending and len(running) < MAX_WORKERS and time.time() < global_deadline:
            launch(pending.pop(0))
        if time.time() > global_deadline + 60 and running:
            break
        try:
            message = result_queue.get(timeout=1.0)
        except queue.Empty:
            message = None
        if message is not None:
            results[int(message["seed"])] = message
            _append(training / "events.jsonl", {"kind": "seed_result", "seed": message["seed"], "status": message.get("status")})
        finished = [seed for seed, process in running.items() if not process.is_alive()]
        for seed in finished:
            process = running[seed]
            process.join(timeout=5)
            if seed not in results:
                try:
                    while True:
                        message = result_queue.get_nowait()
                        results[int(message["seed"])] = message
                        _append(
                            training / "events.jsonl",
                            {"kind": "seed_result", "seed": message["seed"], "status": message.get("status")},
                        )
                except queue.Empty:
                    pass
            if seed not in results:
                results[seed] = {
                    "seed": seed,
                    "status": "incompleta_proceso",
                    "equal_budget": False,
                    "error": f"salida {process.exitcode}",
                }
            del running[seed]
        if running:
            joint = _rss_kb(os.getpid()) + sum(_rss_kb(process.pid) for process in running.values() if process.pid)
            samples.append(joint)
        if not pending and not running:
            break
    for seed, process in list(running.items()):
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        if seed not in results:
            results[seed] = {
                "seed": seed,
                "status": "incompleta_proceso",
                "equal_budget": False,
                "error": "el worker no devolvió un manifiesto",
            }
    for seed in pending:
        results[seed] = {
            "seed": seed,
            "status": "incompleta_reloj_no_iniciada",
            "equal_budget": False,
            "decisions": 0,
            "updates": 0,
        }
    import resource

    memory = {
        "sampled_joint_rss_max_kb": max(samples) if samples else None,
        "sampled_joint_rss_n": len(samples),
        "sampled_joint_rss_note": "Máximo de la suma de VmRSS del padre y de los workers vivos. No es ru_maxrss.",
        "parent_ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "wall_seconds": time.perf_counter() - wall_started,
        "max_workers": MAX_WORKERS,
        "torch_threads_per_worker": 1,
    }
    (training / "memory.json").write_text(json.dumps(memory, indent=2) + "\n", encoding="utf-8")
    verification = _verification(study, training, results, memory, config)
    (study / "training_verification.json").write_text(
        json.dumps(verification, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return verification


def _verification(study, training, results, memory, config) -> dict[str, Any]:
    seeds = []
    for seed in SEEDS:
        row = dict(results.get(seed) or {"seed": seed, "status": "ausente", "equal_budget": False})
        history = training / f"seed_{seed}" / "history.jsonl"
        episodes = []
        nonfinite_tokens = 0
        if history.is_file():
            for line in history.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                if any(token in line for token in ("NaN", "Infinity", "null")):
                    if "NaN" in line or "Infinity" in line:
                        nonfinite_tokens += 1
                payload = json.loads(line)
                if payload.get("kind") == "episode":
                    episodes.append(
                        {
                            "order_id": payload["order_id"],
                            "n_items": payload["n_items"],
                            "step_calls": payload["step_calls"],
                            "termination": payload["termination"],
                        }
                    )
        row["episodes_recorded"] = len(episodes)
        row["episode_terminations"] = episodes
        row["history_nonfinite_tokens"] = nonfinite_tokens
        seeds.append(row)
    return {
        "status": "piloto_ejecutado",
        "comparison_as_equal_budget": all(row.get("equal_budget") for row in seeds),
        "development_evaluated": False,
        "final_test_selected": False,
        "final_test_executed": False,
        "checkpoint_selected_by_reward": False,
        "seed_selected_by_reward": False,
        "convergence_claimed": False,
        "publishable_claimed": False,
        "config": config,
        "memory": memory,
        "seeds": seeds,
    }


def main() -> int:
    import subprocess

    study = Path(__file__).resolve().parents[1]
    repo = study.parents[2]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, text=True).strip()
    if head != EXPECTED_HEAD or branch != EXPECTED_BRANCH:
        raise SystemExit(f"bloqueo: HEAD {head} rama {branch}")
    run_campaign(study)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

