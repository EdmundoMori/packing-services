"""Ejecuta un notebook del flujo 01–10."""

from __future__ import annotations

import io
import os
import sys
import traceback
from pathlib import Path

import matplotlib
import nbformat
from nbformat.v4 import new_output

matplotlib.use("Agg")

NOTEBOOKS = Path(__file__).resolve().parent
NAMES = {
    "01": "01_datos_y_splits.ipynb",
    "02": "02_etiquetas_maestro.ipynb",
    "03": "03_imitacion.ipynb",
    "04": "04_compuerta_maestro.ipynb",
    "05": "05_rl_ppo.ipynb",
    "06": "06_evaluar_holdout.ipynb",
    "07": "07_multipallet_firstfit.ipynb",
    "08": "08_producto_execute.ipynb",
    "09": "09_homologar_pct.ipynb",
    "10": "10_comparar_pct.ipynb",
}
ORDER = tuple(NAMES)


def execute_notebook(path: Path) -> None:
    os.chdir(NOTEBOOKS)
    ml_root = NOTEBOOKS.parent
    repo = ml_root.parent
    for extra in (ml_root / "src_ml", repo / "src"):
        text = str(extra)
        if text not in sys.path:
            sys.path.insert(0, text)

    nb = nbformat.read(path, as_version=4)
    globs: dict = {"__name__": "__main__"}
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code" or not str(cell.source).strip():
            continue
        buf_out, buf_err = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = buf_out, buf_err
        try:
            exec(compile(cell.source, f"{path.name}:cell{i}", "exec"), globs)
            outs = []
            if buf_out.getvalue():
                outs.append(new_output("stream", name="stdout", text=buf_out.getvalue()))
            if buf_err.getvalue():
                outs.append(new_output("stream", name="stderr", text=buf_err.getvalue()))
            cell.outputs = outs
            cell.execution_count = i + 1
        except Exception as exc:
            tb = traceback.format_exc()
            cell.outputs = [
                new_output("stream", name="stderr", text=buf_err.getvalue() + tb)
            ]
            sys.stdout, sys.stderr = old_out, old_err
            nbformat.write(nb, path)
            raise RuntimeError(f"{path.name} falló en celda {i}: {exc}") from exc
        finally:
            sys.stdout, sys.stderr = old_out, old_err
    nbformat.write(nb, path)
    print(f"ok {path}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "uso: python _execute.py 01|02|…|10\n"
            "flujo: " + " → ".join(ORDER)
        )
    key = sys.argv[1]
    name = NAMES.get(key, key)
    path = NOTEBOOKS / name
    if not path.is_file():
        raise FileNotFoundError(path)
    print(f"==> ejecutando {path.name}", flush=True)
    execute_notebook(path)


if __name__ == "__main__":
    main()
