#!/usr/bin/env python3
"""Copia instancias showcase canónicas de examples/ al demo web.

Fuente de verdad: examples/showcase_*_instance.json
Destino: web-demo/static/assets/data/

Uso:
    python scripts/sync_web_demo_showcase.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "examples"
DST = ROOT / "web-demo" / "static" / "assets" / "data"


def main() -> None:
    if not DST.is_dir():
        raise SystemExit(f"Destino no encontrado: {DST}")

    patterns = sorted(SRC.glob("showcase_*_instance.json"))
    if not patterns:
        raise SystemExit(f"No hay instancias showcase en {SRC}")

    for src in patterns:
        dst = DST / src.name
        shutil.copy2(src, dst)
        print(f"  {src.name} → {dst.relative_to(ROOT)}")

    print(f"\n{len(patterns)} instancias sincronizadas.")


if __name__ == "__main__":
    main()
