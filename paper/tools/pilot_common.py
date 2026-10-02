"""Utilidades del evaluador piloto. No carga modelos ni ejecuta políticas."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_SECONDS = 300
TIE_EPS = 1e-9
EXPECTED_N = 20
METHODS = ("actor", "heuristic")
NO_CANDIDATE_REASON = "No hay colocación legal con el presupuesto de información actual"
MANIFEST_REL = Path("online_policy_ml/data/scale/val/order_ids.json")
SUBSET_REL = Path("online_policy_ml/data/scale/val/bed_bpp_orders.json")
ACTOR_ALGORITHM = "drl_policy_3d_bpp"
HEURISTIC_ALGORITHM = "online_3d_bpp_heuristic"
EVALUATOR_FILES = (
    "paper/protocols/03_internal_pilot.json",
    "paper/protocols/04_evaluator_operational.md",
    "paper/tools/run_internal_pilot.py",
    "paper/tools/pilot_common.py",
    "paper/tools/pilot_problems.py",
    "paper/tools/pilot_metrics.py",
    "paper/tools/pilot_preflight.py",
    "paper/tools/pilot_execute.py",
    "paper/tools/pilot_worker.py",
)


class PilotError(Exception):
    def __init__(self, message: str, *, code: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    @property
    def exit_code(self) -> int:
        return {"preflight": 2, "output_exists": 3}.get(self.code, 1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, dumps(payload))


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def git_snapshot() -> dict[str, Any]:
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    head = run("rev-parse", "HEAD")
    branch = run("branch", "--show-current")
    status = run("status", "--short")
    if head.returncode != 0 or branch.returncode != 0 or status.returncode != 0:
        raise PilotError("no se pudo leer el estado de git del repositorio", code="preflight")
    text = status.stdout
    lines = [line for line in text.splitlines() if line.strip()]
    return {
        "head": head.stdout.strip(),
        "branch": branch.stdout.strip(),
        "dirty": bool(lines),
        "status_short_count": len(lines),
        "status_short_sha256": sha256_text(text),
    }


def evaluator_hashes() -> dict[str, str]:
    found: dict[str, str] = {}
    missing: list[str] = []
    for relative in EVALUATOR_FILES:
        path = REPO_ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        found[relative] = sha256_file(path)
    if missing:
        raise PilotError(
            "faltan archivos del evaluador",
            code="preflight",
            details={"missing": missing},
        )
    return found


def format_delta(value: float) -> str:
    return format(float(value), ".12g")
