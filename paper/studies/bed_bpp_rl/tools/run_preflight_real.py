#!/usr/bin/env python3
"""Ejecutor del preflight real BED-BPP-RL.

Por defecto / con ``--static-only``: valida el protocolo y ejercita la regla de
selección sobre un catálogo sintético de metadatos. **No** abre pedidos BED-BPP
reales ni entrena.

El modo real (sin --static-only) queda bloqueado en R03-preparación.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_STUDY = _HERE.parent
for _entry in (str(_HERE), str(_STUDY.parents[1] / "tools")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from preflight_selection import select_by_item_count_quantiles, synthetic_metadata_pool


PROTOCOL_REQUIRED = (
    "schema_version",
    "kind",
    "sample_design",
    "policies",
    "budgets_proposed_before_execution",
    "measurements",
)


def load_protocol(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    for key in PROTOCOL_REQUIRED:
        if key not in document:
            raise ValueError(f"protocolo incompleto: falta {key}")
    if document.get("kind") != "bed_bpp_rl_preflight_real_protocol_r03":
        raise ValueError("kind de protocolo inesperado")
    return document


def run_static_only(protocol: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    budgets = protocol["budgets_proposed_before_execution"]
    policies = protocol["policies"]
    sample = protocol["sample_design"]
    pool = synthetic_metadata_pool()
    # Simula exclusión de IDs reservados (catálogo sintético).
    excluded = {"E010", "R010"}
    selection = select_by_item_count_quantiles(
        pool,
        targets=tuple(sample["targets"]),
        excluded_ids=excluded,
    )
    max_episodes = int(policies["max_episodes"])
    n_policies = len(policies["fixed"]) + len(policies["stochastic"])
    planned_episodes = selection["n_orders"] * n_policies
    if planned_episodes > max_episodes:
        raise RuntimeError(
            f"episodios planificados {planned_episodes} > max_episodes {max_episodes}"
        )
    elapsed = time.perf_counter() - started
    return {
        "mode": "static_only",
        "real_orders_packed": False,
        "training_executed": False,
        "protocol_kind": protocol["kind"],
        "protocol_status": protocol.get("status"),
        "selection": selection,
        "planned_episodes": planned_episodes,
        "max_episodes": max_episodes,
        "budgets_proposed": {
            "timeout_seconds_per_episode": budgets["timeout_seconds_per_episode"],
            "global_wall_seconds": budgets["global_wall_seconds"],
            "rss_bytes_soft_ceiling": budgets["rss_bytes_soft_ceiling"],
            "concurrency": budgets["concurrency"],
            "attempts_per_key": budgets["attempts_per_key"],
        },
        "foundation_note": budgets["foundation"],
        "measurements_declared": protocol["measurements"],
        "static_only_wall_seconds": elapsed,
        "reopen_copied_corpus_supported_by_design": True,
        "physical_stability_verified": None,
        "decision_context": "preflight_real_disenado_y_contraste_de_artefactos_verificado",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=_STUDY / "preflight_real_protocol.json",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Valida diseño sin empaquetar pedidos reales (R03-preparación).",
    )
    parser.add_argument("--orders", type=Path, default=None, help="Reservado; no usar en R03.")
    parser.add_argument("--out", type=Path, default=None, help="Reservado; no usar en R03.")
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol.resolve())

    if not args.static_only:
        print(
            "R03-preparación no autoriza el preflight real. "
            "Use --static-only, o autorice un paso posterior.",
            file=sys.stderr,
        )
        return 2

    if args.orders is not None or args.out is not None:
        print(
            "--orders/--out no se usan en --static-only; no se abren pedidos reales.",
            file=sys.stderr,
        )

    report = run_static_only(protocol)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
