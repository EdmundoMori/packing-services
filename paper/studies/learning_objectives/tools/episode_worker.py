#!/usr/bin/env python3
"""Worker de un episodio development (Greedy o actor limitado a S).

Greedy no importa torch ni el actor. El actor carga torch solo en su rama.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
COUNTERFACTUAL_TOOLS = HERE.parents[1] / "counterfactual_ranking" / "tools"
for entry in (str(COUNTERFACTUAL_TOOLS), str(PAPER_TOOLS), str(HERE)):
    if entry in sys.path:
        sys.path.remove(entry)
sys.path.insert(0, str(COUNTERFACTUAL_TOOLS))
sys.path.insert(0, str(PAPER_TOOLS))
sys.path.insert(0, str(HERE))

from compact_study import ALGORITHM_NAME, run_compact_episode  # noqa: E402
from labeling_io import atomic_write_json  # noqa: E402
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


def _load_actor(path: Path, stats: dict[str, list[float]]) -> Any:
    import torch
    from actor_policy_s import SupportConstrainedActorPolicy
    from model_spec import build_actor

    blob = torch.load(path, map_location="cpu", weights_only=False)
    model = build_actor(0)
    model.load_state_dict(blob["state_dict"])
    return SupportConstrainedActorPolicy(model, stats)


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
    prepare_imports()
    process_started = time.perf_counter()
    support_meta: dict[str, Any] = {}
    if arm == "greedy":
        from packing_services.online.policies import GreedyBestFitPolicy

        chooser: Any = _TimedChooser(GreedyBestFitPolicy())
        display = "GreedyBestFit lista legal completa"
        description = "Best-fit sobre todas las candidatas legales; para en el primer ítem imposible."
        selector = "GreedyBestFitPolicy"
        decision = (
            "GreedyBestFitPolicy sobre la lista legal completa del ítem actual. "
            "Empate interno de la política greedy del runtime. "
            "Si no hay candidata, el episodio termina."
        )
        scores_all_legal = True
    else:
        if checkpoint_path is None or stats is None:
            raise RuntimeError("el actor necesita checkpoint y normalización")
        from training_loop import configure_training_runtime

        configure_training_runtime()
        actor = _load_actor(Path(checkpoint_path), stats)
        chooser = actor
        display = f"Actor {arm} sobre S"
        description = "Construye S (greedy+orientación+diversidad, ≤4) y argmax de logits en S."
        selector = "SupportConstrainedActorPolicy"
        decision = (
            "S vía greedy_plus_orientation_position_diversity_v1; "
            "argmax de scores en S; empate exacto → menor índice en S "
            "(select_logit_index). Sin sufijo ni Q_hat."
        )
        scores_all_legal = False
        support_meta = {
            "supports_only": True,
            "tie_break": "min_index_in_S",
        }
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
    document["recipe"]["scores_all_legal_candidates"] = scores_all_legal
    document["recipe"]["support_constrained"] = not scores_all_legal
    document["recipe"]["support_meta"] = support_meta
    document["recipe"]["actor_checkpoint"] = checkpoint_path
    document["physical_stability_verified"] = None
    finished = time.perf_counter()
    loop_seconds = float(diagnostics["packing_loop_seconds"])
    decision_seconds = float(getattr(chooser, "decision_seconds", 0.0))
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
            "decision_seconds": decision_seconds,
            "decision_seconds_included_in_packing_loop": True,
            "capture_build_seconds": finished - ready - loop_seconds,
            "max_legal_candidates": int(getattr(chooser, "max_candidates", 0)),
            "max_support": int(getattr(chooser, "max_support", 0) or 0),
            "normalization_calls": int(getattr(chooser, "normalization_calls", 0) or 0),
        },
        "returncode": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
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
