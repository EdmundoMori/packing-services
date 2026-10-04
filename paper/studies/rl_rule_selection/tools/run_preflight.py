"""Ejecutor futuro del preflight.

Con --synthetic mide episodios artificiales. Con cualquier ruta de pedidos
reales termina sin empaquetar: el borrador no autoriza esa corrida.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
PAPER_TOOLS = STUDY.parents[1] / "tools"
for entry in (str(PAPER_TOOLS), str(STUDY / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from preflight import measure_synthetic  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--orders", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.orders is not None or not args.synthetic:
        print(
            "El borrador no autoriza empaquetar pedidos reales. Use --synthetic.",
            file=sys.stderr,
        )
        return 2
    report = measure_synthetic()
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
