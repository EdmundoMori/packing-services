#!/usr/bin/env python3
"""Ejecuta todos los notebooks didácticos y reporta errores."""

from __future__ import annotations

import sys
from pathlib import Path

NB_DIR = Path(__file__).resolve().parent
ROOT = NB_DIR.parent


def notebook_order() -> list[Path]:
    return sorted(NB_DIR.glob("[0-9][0-9]_*.ipynb"), key=lambda p: p.name)


def main() -> int:
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError:
        print("Instala dependencias: pip install -e '.[notebooks]' nbclient nbformat", file=sys.stderr)
        return 1

    notebooks = notebook_order()
    if not notebooks:
        print("No se encontraron notebooks en", NB_DIR, file=sys.stderr)
        return 1

    failures: list[tuple[str, str]] = []
    for path in notebooks:
        print(f"\n{'=' * 60}\nEjecutando: {path.name}\n{'=' * 60}")
        nb = nbformat.read(path, as_version=4)
        client = NotebookClient(
            nb,
            timeout=600,
            kernel_name="python3",
            resources={"metadata": {"path": str(NB_DIR)}},
            allow_errors=False,
        )
        try:
            client.execute(cwd=str(NB_DIR))
            nbformat.write(nb, path)
            print(f"OK: {path.name}")
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            print(f"FAIL: {path.name} — {msg}", file=sys.stderr)
            failures.append((path.name, msg))

    print(f"\n{'=' * 60}")
    if failures:
        print(f"Fallaron {len(failures)}/{len(notebooks)} notebooks:")
        for name, err in failures:
            print(f"  - {name}: {err}")
        return 1

    print(f"Todos los notebooks ejecutados correctamente ({len(notebooks)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
