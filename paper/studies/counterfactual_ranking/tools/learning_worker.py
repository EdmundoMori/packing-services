"""Un episodio aislado del contrato compacto. No entrena."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
for entry in (str(PAPER_TOOLS), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from actor_policy import ActorPolicy  # noqa: E402
from compact_study import ALGORITHM_NAME, run_compact_episode  # noqa: E402
from model_spec import build_actor, configure_torch_runtime  # noqa: E402
from pilot_common import atomic_write_json  # noqa: E402
from pilot_problems import capture_document, prepare_imports  # noqa: E402


class _TimedChooser:
    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.decision_seconds = 0.0
        self.max_candidates = 0

    def decide(self, options: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            chosen = self.inner.decide(options, **kwargs)
            self.max_candidates = max(self.max_candidates, len(options))
            return chosen
        finally:
            self.decision_seconds += time.perf_counter() - started


def _load_actor(path: Path, stats: dict[str, list[float]]) -> ActorPolicy:
    import torch

    blob = torch.load(path, map_location="cpu", weights_only=False)
    if list(blob["normalization"]["mean"]) != list(stats["mean"]) or list(blob["normalization"]["scale"]) != list(stats["scale"]):
        raise RuntimeError("el checkpoint no trae la normalización de train")
    model = build_actor(int(blob["seed"]))
    model.load_state_dict(blob["state_dict"])
    return ActorPolicy(model, stats)


def run_problem(
    problem: Any,
    *,
    arm: str,
    order_id: str,
    dataset: str,
    dataset_sha256: str,
    checkpoint_path: str | None,
    stats: dict[str, list[float]] | None,
) -> dict[str, Any]:
    """Ejecuta un episodio. El reloj de decisión está contenido en el del bucle."""

    prepare_imports()
    process_started = time.perf_counter()
    if arm == "greedy":
        from packing_services.online.policies import GreedyBestFitPolicy

        chooser: Any = _TimedChooser(GreedyBestFitPolicy())
        display = "GreedyBestFit con terminación al primer ítem imposible"
        description = "Mismo selector best-fit del ítem actual. El episodio termina si ese ítem no tiene candidata legal."
        selector = "GreedyBestFitPolicy"
        decision = (
            "GreedyBestFitPolicy sobre las candidatas legales del ítem actual. "
            "Si no hay ninguna, el episodio termina y el sufijo no se coloca."
        )
    else:
        if checkpoint_path is None or stats is None:
            raise RuntimeError("el actor necesita checkpoint y normalización")
        chooser = _load_actor(Path(checkpoint_path), stats)
        display = f"Actor {arm}"
        description = "Puntúa todas las candidatas legales del ítem actual. No observa el sufijo."
        selector = "ActorPolicy"
        decision = (
            "Mayor logit entre todas las candidatas legales. "
            "Un empate exacto de logits se resuelve por el menor índice original. "
            "No consulta el sufijo, Q_hat, el identificador del pedido ni la acción Greedy."
        )
    ready = time.perf_counter()
    solution, diagnostics = run_compact_episode(
        problem,
        chooser,
        algorithm_name=ALGORITHM_NAME,
        display_name=display,
        description=description,
        selector=selector,
    )
    document = capture_document(
        problem,
        solution,
        method=arm,
        order_id=order_id,
        orders_path=Path(dataset),
        orders_sha256=dataset_sha256,
        checkpoint_path=Path(checkpoint_path) if checkpoint_path else Path("."),
    )
    document["recipe"]["decision"] = decision
    document["recipe"]["terminal"] = "stop_at_first_impossible_item"
    document["recipe"]["observes_future_item_dimensions"] = False
    document["recipe"]["passes_remaining_count"] = False
    document["recipe"]["scores_all_legal_candidates"] = arm != "greedy"
    document["recipe"]["candidate_cap"] = None
    document["recipe"]["checkpoint_path"] = None
    document["recipe"]["actor_checkpoint"] = checkpoint_path
    document["physical_stability_verified"] = None
    finished = time.perf_counter()
    loop_seconds = float(diagnostics["packing_loop_seconds"])
    return {
        "status": "ok",
        "error": None,
        "attempts": 1,
        "timeout_seconds": 300,
        "capture": document,
        "diagnostics": diagnostics,
        "timings": {
            "startup_seconds": ready - process_started,
            "packing_loop_seconds": loop_seconds,
            "decision_seconds": float(chooser.decision_seconds),
            "decision_seconds_included_in_packing_loop": True,
            "candidate_generation_seconds": None,
            "candidate_generation_note": "La generación de candidatas queda dentro de packing_loop_seconds; el bucle congelado no la separa.",
            "capture_build_seconds": finished - ready - loop_seconds,
            "max_legal_candidates": int(chooser.max_candidates),
        },
        "returncode": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    configure_torch_runtime()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    prepare_imports()
    from compact_study import build_compact_problem
    from splits import load_orders

    orders = load_orders(Path(job["dataset"]))
    problem = build_compact_problem(orders, job["order_id"])
    document = run_problem(
        problem,
        arm=job["arm"],
        order_id=job["order_id"],
        dataset=job["dataset"],
        dataset_sha256=job["dataset_sha256"],
        checkpoint_path=job.get("checkpoint"),
        stats=job.get("normalization"),
    )
    atomic_write_json(args.result, document)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        destination = Path(sys.argv[sys.argv.index("--result") + 1])
        atomic_write_json(
            destination,
            {
                "status": "crash",
                "error": f"{type(exc).__name__}: {exc}",
                "worker_failure": "crash",
                "attempts": 1,
                "capture": None,
                "diagnostics": None,
                "returncode": 0,
            },
        )
        raise SystemExit(0)
