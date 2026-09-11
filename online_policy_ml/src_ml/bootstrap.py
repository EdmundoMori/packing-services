"""Arranque común del notebook: sys.path y carpetas."""

from __future__ import annotations

import sys
from pathlib import Path


def setup() -> Path:
    here = Path.cwd().resolve()
    if here.name == "notebooks":
        ml_root = here.parent
    elif (here / "src_ml").is_dir():
        ml_root = here
    else:
        ml_root = Path(__file__).resolve().parents[1]

    src_ml = str(ml_root / "src_ml")
    src_pkg = str(ml_root.parent / "src")
    if src_ml not in sys.path:
        sys.path.insert(0, src_ml)
    if src_pkg not in sys.path:
        sys.path.insert(0, src_pkg)

    from paths import ensure_dirs

    ensure_dirs()
    return ml_root
