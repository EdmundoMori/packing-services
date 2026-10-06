"""Comprobación expresa del motor EP post-C04."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from environment import ENGINE_MODULE, ENGINE_REQUIRED_COMMIT

REPO_ROOT = Path(__file__).resolve().parents[4]


def engine_path() -> Path:
    return REPO_ROOT / ENGINE_MODULE


def verify_post_c04_engine() -> dict:
    path = engine_path()
    if not path.is_file():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    markers = (
        "área positiva",
        "overlap_x > 0",
        "overlap_y > 0",
        "franja",
        "EPS",
    )
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise RuntimeError(f"motor no parece post-C04; faltan marcadores: {missing}")

    # El blob actual debe proceder del commit C04 o un ancestro que lo contenga.
    probe = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", ENGINE_REQUIRED_COMMIT, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise RuntimeError(
            f"HEAD no contiene el commit requerido post-C04 {ENGINE_REQUIRED_COMMIT}"
        )

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "module": ENGINE_MODULE,
        "required_commit": ENGINE_REQUIRED_COMMIT,
        "path": str(path.relative_to(REPO_ROOT)),
        "sha256": digest,
        "post_c04_markers_ok": True,
        "ancestor_of_head": True,
    }
