#!/usr/bin/env python3
"""Lanza el diagnóstico del teacher. Este paso no lo ejecuta sobre los 50 pedidos."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from teacher_probe import PACKING_DIR, ProbeError, run_probe_stage  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico teacher frente a GreedyBestFit.")
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--comparator", type=Path, default=PACKING_DIR)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    args = parser.parse_args(argv)
    protocol = json.loads(args.protocol.expanduser().resolve().read_text(encoding="utf-8"))
    run_probe_stage(
        protocol=protocol,
        comparator_dir=args.comparator,
        dataset_path=args.dataset,
        output_dir=args.output,
        command=[sys.executable, *argv] if argv is not None else sys.argv,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeError as exc:
        print(exc.message, file=sys.stderr)
        raise SystemExit(2)
