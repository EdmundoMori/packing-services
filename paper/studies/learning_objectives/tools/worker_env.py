"""Entorno de workers: conserva identidad de la venv al invocar el intérprete.

No usar Path.resolve() sobre .venv/bin/python: sigue el symlink al Python base
y pierde site-packages de la venv (p. ej. torch).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
REPO_DEFAULT = HERE.parents[3]
PAPER_TOOLS = HERE.parents[2] / "tools"
COUNTERFACTUAL_TOOLS = HERE.parents[1] / "counterfactual_ranking" / "tools"


def venv_python(repo: Path) -> Path:
    """Ruta absoluta de invocación del Python de la venv (sin seguir symlinks)."""

    path = repo / ".venv" / "bin" / "python"
    if not path.exists():
        raise FileNotFoundError(f"intérprete venv ausente: {path}")
    return path.absolute()


def preserve_executable(path: str | Path) -> str:
    """Absoluta sin resolve(); conserva identidad de ejecutables enlazados."""

    p = Path(path)
    if not p.is_absolute():
        p = (Path.cwd() / p).absolute()
    else:
        p = p.absolute()
    return str(p)


def probe_worker_interpreter(
    python: str | Path,
    *,
    cwd: Path | None = None,
    extra_imports: Sequence[str] | None = None,
    tools_dir: Path = HERE,
    counterfactual_tools: Path = COUNTERFACTUAL_TOOLS,
    paper_tools: Path = PAPER_TOOLS,
) -> dict[str, Any]:
    """Subprocess real: sys.executable/prefix + torch (+ imports opcionales)."""

    imports = list(extra_imports or ())
    script = (
        "import json,sys\n"
        f"sys.path.insert(0,{str(counterfactual_tools)!r})\n"
        f"sys.path.insert(0,{str(paper_tools)!r})\n"
        f"sys.path.insert(0,{str(tools_dir)!r})\n"
        "out={"
        "'sys_executable':sys.executable,"
        "'sys_prefix':sys.prefix,"
        "'sys_base_prefix':sys.base_prefix,"
        "'in_venv':sys.prefix!=sys.base_prefix,"
        "'imports':{}"
        "}\n"
        "try:\n"
        " import torch\n"
        " out['torch_ok']=True\n"
        " out['torch_version']=getattr(torch,'__version__',None)\n"
        " out['imports']['torch']=True\n"
        "except Exception as exc:\n"
        " out['torch_ok']=False\n"
        " out['torch_error']=f'{type(exc).__name__}: {exc}'\n"
        " out['imports']['torch']=False\n"
    )
    for name in imports:
        if name == "torch":
            continue
        script += (
            f"try:\n import {name}\n out['imports'][{name!r}]=True\n"
            f"except Exception as exc:\n out['imports'][{name!r}]=False\n"
            f" out.setdefault('import_errors',[])\n"
            f" out['import_errors'].append(f'{name}: {{type(exc).__name__}}: {{exc}}')\n"
        )
    script += (
        "out['ok']=bool(out.get('torch_ok') and out.get('in_venv') and all(out['imports'].values()))\n"
        "print(json.dumps(out))\n"
    )
    invoked = preserve_executable(python)
    completed = subprocess.run(
        [invoked, "-c", script],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1"},
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "returncode": completed.returncode,
            "stderr": (completed.stderr or "")[:2000],
            "stdout": (completed.stdout or "")[:2000],
            "invoked_python": invoked,
            "in_venv": False,
            "imports": {},
        }
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    payload["invoked_python"] = invoked
    payload["returncode"] = 0
    return payload


def environment_preflight(repo: Path, *, require_actor_imports: bool = True) -> dict[str, Any]:
    """Preflight de entorno vía subprocess real. No basta torch en el padre."""

    python = venv_python(repo)
    absolute = Path(preserve_executable(python))
    # Detectar si la ruta cae fuera de la venv del repo (p. ej. mock a /usr/bin/python3.10)
    under_repo_venv = ".venv" in absolute.parts and str(repo.resolve()) in str(absolute)
    resolved = absolute.resolve()
    extras = ["torch", "actor_policy_s", "actor_features", "audit_internal_solution"] if require_actor_imports else ["torch"]
    interp = probe_worker_interpreter(absolute, cwd=repo, extra_imports=extras)
    parent_torch = False
    parent_version = None
    try:
        import torch

        parent_torch = True
        parent_version = getattr(torch, "__version__", None)
    except Exception as exc:  # noqa: BLE001
        parent_torch = False
        parent_version = f"{type(exc).__name__}: {exc}"

    ok = bool(under_repo_venv and interp.get("ok"))
    reason = None
    if not under_repo_venv:
        reason = "python_not_under_repo_venv"
    elif not interp.get("ok"):
        reason = "worker_environment_preflight_failed"
    return {
        "ok": ok,
        "reason": reason,
        "harness_failure": not ok,
        "gate_applicable": ok,
        "python_absolute": str(absolute),
        "python_resolve_would_be": str(resolved),
        "resolve_differs_from_absolute": str(resolved) != str(absolute),
        "under_repo_venv": under_repo_venv,
        "parent_has_torch": parent_torch,
        "parent_torch_version": parent_version,
        "subprocess_interpreter": interp,
        "note": "parent torch alone is insufficient; workers must pass subprocess probe",
        "harness_failure_if_not_ok": True,
    }
