#!/usr/bin/env python3
"""Ejecutor completo de etiquetado learning_objectives.

Uso futuro (NO lanzar en el paso de implementación):

  /home/edmundo/packing-services/.venv/bin/python \
    /home/edmundo/packing-services/paper/studies/learning_objectives/tools/run_learning_labels.py \
    --study-dir /home/edmundo/packing-services/paper/studies/learning_objectives \
    --output /home/edmundo/packing-services/paper/studies/learning_objectives/learning_labels

No entrena. No ejecuta development packing ni test.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_campaign import run_labeling_campaign  # noqa: E402
from labeling_contracts import static_preflight  # noqa: E402
from labeling_reuse import PreflightReuseIndex  # noqa: E402
from labeling_verify import verify_labeling_output  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Etiquetado learning_objectives (train+development)")
    parser.add_argument(
        "--study-dir",
        type=Path,
        required=True,
        help="Ruta absoluta a paper/studies/learning_objectives",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Carpeta de salida nueva (se rechaza si existe)",
    )
    parser.add_argument(
        "--preflight-dir",
        type=Path,
        default=None,
        help="Evidencia de preflight publicada (por defecto study-dir/preflight)",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Solo valida contratos y escribe el manifiesto; no empaqueta",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study_dir = args.study_dir.resolve()
    output = args.output.resolve()
    preflight_dir = args.preflight_dir.resolve() if args.preflight_dir else None
    started = time.perf_counter()
    static = static_preflight(study_dir=study_dir, output=output, preflight_dir=preflight_dir)
    if args.static_only:
        print(
            json.dumps(
                {
                    "status": "static_preflight_ok",
                    "output": str(output),
                    "n_orders": static["manifest"]["n_orders"],
                    "wall_seconds": time.perf_counter() - started,
                },
                ensure_ascii=False,
            )
        )
        return 0
    protocol = static["protocol"]
    reuse = PreflightReuseIndex(
        static["preflight_dir"],
        protocol=protocol,
        study_dir=study_dir,
    )
    dataset = Path(static["contracts"]["dataset"])
    orders_blob = json.loads(dataset.read_text(encoding="utf-8"))
    summary = run_labeling_campaign(
        protocol=protocol,
        ordered=static["ordered"],
        orders_blob=orders_blob,
        dataset=str(dataset),
        dataset_sha256=static["contracts"]["dataset_sha256"],
        output=output,
        reuse=reuse,
    )
    verification = verify_labeling_output(
        output=output,
        manifest=static["manifest"],
        summary=summary,
        protocol=protocol,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "verification": verification["status"],
                "ready_for_training": verification["ready_for_training"],
                "continuations_reused": summary["continuations_reused"],
                "continuations_new": summary["continuations_new"],
                "continuations_unknown": summary["continuations_unknown"],
                "labeling_wall_seconds": summary["labeling_wall_seconds"],
                "preflight_wall_seconds_accounted_once": summary["preflight_wall_seconds_accounted_once"],
                "global_accounted_wall_seconds": summary["global_accounted_wall_seconds"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    if summary["status"] != "completed" or verification["status"] != "verified":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
