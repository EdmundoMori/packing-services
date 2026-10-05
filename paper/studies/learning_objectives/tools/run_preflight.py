"""Ejecuta solo el preflight reducido. No entrena ni abre desarrollo/test."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path.insert(0, str(HERE))

from preflight import run_preflight  # noqa: E402


def main() -> int:
    protocol = json.loads((STUDY / "protocol_frozen.json").read_text(encoding="utf-8"))
    sample = json.loads((STUDY / "sample_manifest.json").read_text(encoding="utf-8"))
    output = STUDY / "preflight"
    verification = run_preflight(protocol, sample, output)
    print(json.dumps({
        "status": verification["status"],
        "states_used": verification["states_used"],
        "continuations_used": verification["continuations_used"],
        "unknown_returns": verification["unknown_returns"],
        "wall_seconds": verification["wall_seconds"],
        "ru_maxrss_kb": verification["memory"]["ru_maxrss_kb"],
    }, ensure_ascii=False))
    return 0 if verification["status"] == "completed" and verification["unknown_returns"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
