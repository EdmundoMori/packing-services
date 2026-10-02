#!/usr/bin/env python3
"""Evaluador del piloto interno 03A. --preflight-only no carga el checkpoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pilot_common import PilotError, dumps
from pilot_execute import execute_pilot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluador pareado del piloto interno.")
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--subset", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = execute_pilot(
            protocol_path=args.protocol,
            dataset_path=args.dataset,
            checkpoint_path=args.checkpoint,
            output_dir=args.output_dir,
            preflight_only=args.preflight_only,
            manifest_path=args.manifest,
            subset_path=args.subset,
        )
    except PilotError as exc:
        print(dumps({"ok": False, "code": exc.code, "error": str(exc), **exc.details}), end="")
        return exc.exit_code
    print(dumps(result["public"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
