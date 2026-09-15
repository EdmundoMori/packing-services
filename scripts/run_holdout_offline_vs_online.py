#!/usr/bin/env python3
"""Compara offline vs online sobre los cinco pedidos del holdout BED-BPP.

Los pedidos de ``examples/5_bed-bpp.json`` nunca se usaron para entrenar ni
para ajustar, de modo que la tabla resultante es la primera evidencia a nivel
de producto (hasta ahora sólo había validación corta y un smoke de un pedido).

Uso::

    PYTHONPATH=src python scripts/run_holdout_offline_vs_online.py
    PYTHONPATH=src python scripts/run_holdout_offline_vs_online.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from packing_services.benchmark.holdout_offline_online import (  # noqa: E402
    HOLDOUT_ENGINES,
    HOLDOUT_ORDER_IDS,
    run_holdout_offline_online,
    summarize_holdout,
)

# El lookahead del heurístico reevalúa la ventana en cada candidata, así que su
# coste crece con el cubo del número de ítems: minutos por pedido mediano.
EXPENSIVE = ("online_3d_bpp_heuristic", "p3s2")

ENGINE_WIDTH = 52


def _print_order(response) -> None:
    d = response.details
    available = d.get("containers_available", 1)
    print(
        f"Pedido {d['order_id']} · {d['n_items']} ítems · "
        f"target={d['target']} {d['container_size']} mm · "
        f"{available} contenedor(es) disponible(s)"
    )
    print(
        f"Válidos: {d['engines_valid']}/{d['engines_total']} · "
        f"errores: {d['engines_error']} · mejor: {d['best_engine']}"
    )
    header = (
        f"{'motor':<{ENGINE_WIDTH}} {'ok':>4} {'emp.':>5} {'no':>4} {'pal':>4} "
        f"{'util':>8} {'alto(mm)':>9} {'util@alto':>10} {'t(s)':>9}"
    )
    print(header)
    print("-" * len(header))
    by_engine = {r.engine: r for r in response.results}
    for name in response.ranking:
        r = by_engine[name]
        m = r.metrics
        print(
            f"{name:<{ENGINE_WIDTH}} {str(r.is_valid):>4} {m.items_packed:>5} "
            f"{m.items_unpacked:>4} {m.containers_used:>4} "
            f"{m.volume_utilization:>7.1%} "
            f"{r.details.get('load_height_mm', 0.0):>9.0f} "
            f"{r.details.get('envelope_utilization', 0.0):>9.1%} "
            f"{m.execution_time_seconds:>9.3f}"
        )
    for r in response.results:
        if r.error:
            print(f"  ! {r.engine}: {r.error}")
    print()


def _print_summary(summary: dict) -> None:
    print("=" * 96)
    print(
        f"Resumen sobre {summary['orders_total']} pedidos de holdout: "
        f"{', '.join(summary['orders'])}"
    )
    header = (
        f"{'motor':<{ENGINE_WIDTH}} {'val':>4} {'gana':>5} {'emp.':>5} "
        f"{'no':>4} {'pal':>4} {'util~':>8} {'alto~(mm)':>10} "
        f"{'util@alto~':>11} {'t~(s)':>9}"
    )
    print(header)
    print("-" * len(header))
    for row in summary["engines"]:
        print(
            f"{row['engine']:<{ENGINE_WIDTH}} "
            f"{row['orders_valid']:>4} {row['wins']:>5} "
            f"{row['items_packed']:>5} {row['items_unpacked']:>4} "
            f"{row['containers_used']:>4} "
            f"{row['mean_volume_utilization']:>7.1%} "
            f"{row['mean_load_height_mm']:>10.0f} "
            f"{row['mean_envelope_utilization']:>10.1%} "
            f"{row['mean_execution_time_seconds']:>9.3f}"
        )
    print()
    print("val = pedidos con solución válida · gana = veces primero en el ranking")
    print("pal = contenedores usados (total del holdout)")
    print("util = cubo sobre los contenedores usados (empata si todo el pedido cabe)")
    print("alto = altura de carga alcanzada · util@alto = cubo dentro de esa altura")
    print("util~, alto~ y t~ son promedios por pedido; emp./no/pal son totales")
    print()
    print(summary["ranking_explanation"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--order-id",
        action="append",
        dest="order_ids",
        help="Limitar a un pedido (repetible). Por defecto, los cinco del holdout.",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Ruta donde volcar la tabla completa en JSON.",
    )
    parser.add_argument(
        "--containers",
        type=int,
        default=1,
        help=(
            "Cuántos contenedores idénticos al destino del pedido se ponen a "
            "disposición. Con 2, cada motor decide si abre el segundo pallet."
        ),
    )
    parser.add_argument(
        "--skip-greedy-lookahead",
        action="store_true",
        help=(
            "Omitir online_3d_bpp_heuristic#p3s2. Su lookahead tarda minutos "
            "por pedido y deja a mlp_p3s2 sin baseline al mismo (p, s)."
        ),
    )
    args = parser.parse_args()

    sample = ROOT / "examples" / "5_bed-bpp.json"
    orders = json.loads(sample.read_text(encoding="utf-8"))
    order_ids = tuple(args.order_ids) if args.order_ids else HOLDOUT_ORDER_IDS
    engines = HOLDOUT_ENGINES
    if args.skip_greedy_lookahead:
        engines = tuple(
            e for e in engines if (e.algorithm, e.variant) != EXPENSIVE
        )

    if args.containers < 1:
        parser.error("--containers debe ser 1 o más")

    responses = run_holdout_offline_online(
        orders,
        order_ids=order_ids,
        engines=engines,
        containers=args.containers,
    )
    for response in responses:
        _print_order(response)

    summary = summarize_holdout(responses)
    _print_summary(summary)

    if args.json_path:
        payload = {
            "summary": summary,
            "orders": [
                {
                    "details": r.details,
                    "ranking": r.ranking,
                    "results": [
                        {
                            "engine": e.engine,
                            "status": e.status,
                            "is_valid": e.is_valid,
                            "error": e.error,
                            "details": e.details,
                            "metrics": e.metrics.model_dump(),
                        }
                        for e in r.results
                    ],
                }
                for r in responses
            ],
        }
        out = Path(args.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nJSON escrito en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
