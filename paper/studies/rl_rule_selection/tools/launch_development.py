"""Lanza la evaluación de desarrollo desde un archivo, para que spawn pueda importarlo."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
while str(TOOLS) in sys.path:
    sys.path.remove(str(TOOLS))
sys.path.insert(0, str(TOOLS))

from integrity_check import inspect_training  # noqa: E402
from run_development import run_development  # noqa: E402


def main() -> int:
    study = TOOLS.parent
    report = inspect_training(study)
    if not report["passed"]:
        raise SystemExit("integridad no superada")
    result = run_development(study, report)
    print("rows", len(result["rows"]), "wall", result["memory"]["wall_seconds"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
