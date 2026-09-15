"""Selección de checkpoint por utilización de empaquetado, no por imitación.

Motivo. El proceso original elegía el epoch por exactitud de imitación del
maestro. Con un maestro tautológico eso equivale a premiar al epoch que mejor
reproduce una ordenación lexicográfica, que no es el objetivo. Y aunque el
maestro sea informativo, imitar mejor no implica empaquetar mejor: en la fase 5
el candidato con más exactitud empeoró en la prueba corta.

Aquí el criterio es directo: se empaqueta con cada epoch y se elige el que más
volumen aprovecha, descalificando cualquiera que produzca una solución inválida.
Es más caro que leer una curva de accuracy, y es lo correcto.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from config import HIDDEN_SIZE
from evaluate import evaluate_orders
from export_ckpt import export_mlp_pt


def select_epoch_by_utilization(
    epoch_states: list[dict[str, Any]],
    orders: dict[str, Any],
    order_ids: list[str],
    *,
    lookahead_p: int,
    select_s: int,
    hidden_size: int = HIDDEN_SIZE,
    max_orders: int | None = None,
    workdir: Path | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Empaqueta con cada epoch y devuelve el mejor por utilización media.

    Un epoch que produzca alguna solución inválida queda descalificado, por
    mucha utilización que alcance.
    """

    if not epoch_states:
        raise ValueError("no hay epochs guardados; entrena con keep_epochs=True")
    from methodology import assert_selection_split

    assert_selection_split(order_ids, role="model_selection")

    tmp: tempfile.TemporaryDirectory | None = None
    if workdir is None:
        tmp = tempfile.TemporaryDirectory(prefix="epoch_select_")
        base = Path(tmp.name)
    else:
        base = Path(workdir)
        base.mkdir(parents=True, exist_ok=True)

    table: list[dict[str, Any]] = []
    rows_by_epoch: dict[int, list[dict[str, Any]]] = {}
    try:
        for entry in epoch_states:
            epoch = int(entry["epoch"])
            path = base / f"epoch_{epoch:02d}.pt"
            export_mlp_pt(entry["state_dict"], path, hidden_size=hidden_size)
            rows = evaluate_orders(
                orders,
                order_ids,
                engine="learned",
                lookahead_p=lookahead_p,
                select_s=select_s,
                model_path=str(path),
                max_orders=max_orders,
            )
            rows_by_epoch[epoch] = rows
            n = max(len(rows), 1)
            util = sum(float(r["volume_utilization"]) for r in rows) / n
            packed = sum(int(r["items_packed"]) for r in rows) / n
            all_valid = all(bool(r["is_valid"]) for r in rows)
            table.append(
                {
                    "epoch": epoch,
                    "utilization": round(util, 6),
                    "items_packed": round(packed, 3),
                    "all_valid": all_valid,
                    "n_orders": len(rows),
                }
            )
            if verbose:
                flag = "" if all_valid else "  <-- DESCALIFICADO: solución inválida"
                print(
                    f"  epoch {epoch:>2}: utilización {util:.4f}  "
                    f"empacados {packed:.2f}{flag}"
                )

        eligible = [row for row in table if row["all_valid"]]
        if not eligible:
            raise RuntimeError(
                "ningún epoch produjo soluciones válidas en todos los pedidos"
            )
        best = max(eligible, key=lambda row: (row["utilization"], -row["epoch"]))
        best_state = next(
            entry["state_dict"]
            for entry in epoch_states
            if int(entry["epoch"]) == best["epoch"]
        )
    finally:
        if tmp is not None:
            tmp.cleanup()

    return {
        "best_epoch": best["epoch"],
        "best_utilization": best["utilization"],
        "best_state_dict": best_state,
        "criterion": "val_utilization",
        "table": table,
        "rows_by_epoch": rows_by_epoch,
        "disqualified": [row["epoch"] for row in table if not row["all_valid"]],
    }
