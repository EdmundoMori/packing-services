"""Control de versiones de flujos: qué se corrió, con qué código y qué salió.

Un *flujo* es un experimento con identidad propia (por ejemplo
``eval_pasoA_consolidacion``). Cuando su notebook termina y sus comprobaciones
pasan, se **sella**: se copia el reporte a ``artifacts/runs/<flujo>/v<N>/``
junto a un manifiesto con el commit de git, la huella del notebook que lo
produjo y las métricas de cabecera, y se añade la entrada al índice
``artifacts/registry.json``.

Reglas:

- Una versión sellada no se reescribe nunca. Si vuelves a sellar, sale ``v2``.
- Si el código fuente y las métricas de cabecera son idénticos a la última
  versión, no se crea una nueva: se devuelve la existente. Así puedes
  reejecutar un notebook sin ensuciar el historial.
- El índice es la respuesta a "qué está hecho y qué falta", y el manifiesto
  es la respuesta a "de dónde salió este número".
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paths import ARTIFACTS_DIR, REPO_ROOT

REGISTRY_PATH = ARTIFACTS_DIR / "registry.json"
RUNS_DIR = ARTIFACTS_DIR / "runs"

STATUS_VALIDADO = "validado"
STATUS_EN_CURSO = "en_curso"
STATUS_DESCARTADO = "descartado"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def git_state() -> dict[str, Any]:
    """Commit y si el árbol tiene cambios sin confirmar al momento de sellar."""

    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return {
        "commit": commit,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status) if status is not None else None,
    }


def file_fingerprint(path: str | Path) -> str | None:
    """sha256 corto del archivo fuente, para atar el resultado a su código."""

    target = Path(path)
    if not target.is_file():
        return None
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return digest[:16]


def _environment() -> dict[str, Any]:
    env: dict[str, Any] = {"python": sys.version.split()[0]}
    try:
        import torch

        env["torch"] = torch.__version__
    except ImportError:
        env["torch"] = None
    try:
        from packing_services.online.features import FEATURE_DIM, FEATURE_VERSION

        env["feature_version"] = FEATURE_VERSION
        env["feature_dim"] = FEATURE_DIM
    except ImportError:
        pass
    return env


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        return {"schema": 1, "flows": {}}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save_registry(registry: dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def list_runs(flow_id: str | None = None) -> list[dict[str, Any]]:
    """Versiones selladas, de la más antigua a la más reciente."""

    flows = load_registry().get("flows", {})
    if flow_id is not None:
        return list(flows.get(flow_id, {}).get("runs", []))
    rows: list[dict[str, Any]] = []
    for fid, flow in flows.items():
        for run in flow.get("runs", []):
            rows.append({"flow_id": fid, **run})
    rows.sort(key=lambda r: (r.get("sealed_at") or "", r.get("version") or 0))
    return rows


def latest_run(flow_id: str) -> dict[str, Any] | None:
    runs = list_runs(flow_id)
    return runs[-1] if runs else None


def run_dir(flow_id: str, version: int) -> Path:
    return RUNS_DIR / flow_id / f"v{version}"


def load_sealed_report(flow_id: str, version: int | None = None) -> dict[str, Any]:
    """Lee el reporte de una versión sellada (por defecto la última)."""

    if version is None:
        run = latest_run(flow_id)
        if run is None:
            raise FileNotFoundError(f"el flujo {flow_id!r} no tiene versiones selladas")
        version = int(run["version"])
    path = run_dir(flow_id, version) / "report.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def seal_run(
    flow_id: str,
    *,
    title: str,
    source: str | Path,
    report: Any,
    headline: dict[str, Any],
    status: str = STATUS_VALIDADO,
    notes: str | None = None,
    skip_if_unchanged: bool = True,
) -> dict[str, Any]:
    """Sella un flujo terminado y devuelve la entrada del índice.

    ``source`` es el notebook o script que produjo el resultado; ``headline``
    son las dos o tres cifras por las que reconocerías esta corrida sin abrir
    el JSON completo.
    """

    source_path = Path(source)
    fingerprint = file_fingerprint(
        source_path if source_path.is_absolute() else REPO_ROOT / source_path
    )

    registry = load_registry()
    flows = registry.setdefault("flows", {})
    flow = flows.setdefault(flow_id, {"title": title, "runs": []})
    flow["title"] = title

    previous = flow["runs"][-1] if flow["runs"] else None
    if (
        skip_if_unchanged
        and previous is not None
        and previous.get("source_fingerprint") == fingerprint
        and previous.get("headline") == headline
        and previous.get("status") == status
    ):
        return previous

    version = (previous["version"] + 1) if previous else 1
    target = run_dir(flow_id, version)
    if target.exists():
        raise FileExistsError(f"{target} ya existe: una versión sellada no se reescribe")
    target.mkdir(parents=True)

    (target / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "flow_id": flow_id,
        "version": version,
        "title": title,
        "status": status,
        "sealed_at": _now(),
        "source": str(source_path),
        "source_fingerprint": fingerprint,
        "git": git_state(),
        "environment": _environment(),
        "headline": headline,
        "notes": notes,
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    entry = {
        "version": version,
        "status": status,
        "sealed_at": manifest["sealed_at"],
        "source": manifest["source"],
        "source_fingerprint": fingerprint,
        "git_commit": manifest["git"]["commit"],
        "git_dirty": manifest["git"]["dirty"],
        "headline": headline,
        "notes": notes,
        "path": str(target.relative_to(ARTIFACTS_DIR.parent)),
    }
    flow["runs"].append(entry)
    registry["updated_at"] = manifest["sealed_at"]
    _save_registry(registry)
    return entry


def registry_table() -> list[dict[str, Any]]:
    """Vista plana del índice: un renglón por flujo con su última versión."""

    rows: list[dict[str, Any]] = []
    for flow_id, flow in load_registry().get("flows", {}).items():
        runs = flow.get("runs", [])
        last = runs[-1] if runs else None
        rows.append(
            {
                "flujo": flow_id,
                "titulo": flow.get("title"),
                "versiones": len(runs),
                "ultima": f"v{last['version']}" if last else "-",
                "estado": last["status"] if last else "-",
                "sellado": (last["sealed_at"][:10] if last else "-"),
                "fuente": last["source"] if last else "-",
            }
        )
    rows.sort(key=lambda r: r["flujo"])
    return rows
