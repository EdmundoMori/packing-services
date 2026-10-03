#!/usr/bin/env python3
"""Ejecutor de las dos etapas de la ablación. Este módulo no se lanza en el paso 11.

Entrenamiento:
  CUDA_VISIBLE_DEVICES= .venv/bin/python paper/tools/run_normalization_ablation.py train \\
    --protocol paper/protocols/10_normalization_ablation.json \\
    --freeze paper/results/10_normalization_freeze.json \\
    --output paper/results/11_normalization_ablation

Packing, después de un entrenamiento completo:
  CUDA_VISIBLE_DEVICES= .venv/bin/python paper/tools/run_normalization_ablation.py pack \\
    --protocol paper/protocols/10_normalization_ablation.json \\
    --freeze paper/results/10_normalization_freeze.json \\
    --run-dir paper/results/11_normalization_ablation \\
    --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ablation_contract import AblationError  # noqa: E402
from ablation_pack import run_packing_stage  # noqa: E402
from ablation_train import run_training_stage  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ablación de normalización, en dos etapas.")
    subparsers = parser.add_subparsers(dest="stage", required=True)
    train = subparsers.add_parser("train")
    train.add_argument("--protocol", required=True, type=Path)
    train.add_argument("--freeze", required=True, type=Path)
    train.add_argument("--output", required=True, type=Path)
    pack = subparsers.add_parser("pack")
    pack.add_argument("--protocol", required=True, type=Path)
    pack.add_argument("--freeze", required=True, type=Path)
    pack.add_argument("--run-dir", required=True, type=Path)
    pack.add_argument("--dataset", required=True, type=Path)
    args = parser.parse_args(argv)
    command = [sys.executable, str(Path(__file__).resolve()), *list(argv if argv is not None else sys.argv[1:])]
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    try:
        if args.stage == "train":
            run_training_stage(
                protocol_path=args.protocol,
                freeze_path=args.freeze,
                output_dir=args.output,
                command=command,
            )
        else:
            run_packing_stage(
                protocol_path=args.protocol,
                freeze_path=args.freeze,
                run_dir=args.run_dir,
                dataset_path=args.dataset,
                command=command,
            )
    except AblationError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
