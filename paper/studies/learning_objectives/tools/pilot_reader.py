"""Lee resultados publicados del piloto counterfactual. No empaqueta ni entrena."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SEEDS: tuple[int, ...] = (11, 23, 37)
ARMS: tuple[str, ...] = ("classification", "preferences", "greedy")
EXPECTED_CASES = 84
EXPECTED_ORDERS = 12
EXPECTED_PER_TARGET = 6


class PilotIntegrityError(ValueError):
    """Claves, pedidos o valores incompatibles con el protocolo publicado."""


def case_key(order_id: str, arm: str, seed: int | None) -> str:
    if arm == "greedy":
        return f"greedy|{order_id}"
    return f"{arm}|{seed}|{order_id}"


def load_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_results(cases_root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(cases_root.glob("*/*/result.json")):
        row = load_result(path)
        row["_path"] = str(path)
        rows.append(row)
    return rows


def _finite(value: Any, *, label: str) -> float:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PilotIntegrityError(f"{label}: valor no numérico ({value!r})")
    number = float(value)
    if not math.isfinite(number):
        raise PilotIntegrityError(f"{label}: no finito ({number})")
    return number


def index_pilot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != EXPECTED_CASES:
        raise PilotIntegrityError(f"se esperaban {EXPECTED_CASES} resultados, hay {len(rows)}")
    keys = [row["key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise PilotIntegrityError("hay claves duplicadas")
    catalog: dict[tuple[str, str, int | None], dict[str, Any]] = {}
    orders: dict[str, str] = {}
    for row in rows:
        order_id = str(row["order_id"])
        arm = str(row["arm"])
        seed = row.get("seed")
        if arm == "greedy":
            seed = None
        elif seed not in SEEDS:
            raise PilotIntegrityError(f"semilla inesperada: {seed}")
        expected = case_key(order_id, arm, seed)
        if row["key"] != expected:
            raise PilotIntegrityError(f"clave {row['key']} no coincide con {expected}")
        if (order_id, arm, seed) in catalog:
            raise PilotIntegrityError(f"duplicado {(order_id, arm, seed)}")
        if not row.get("in_denominator", False):
            raise PilotIntegrityError(f"{expected}: fuera del denominador")
        u = _finite(row.get("effective_u_geom"), label=expected)
        catalog[(order_id, arm, seed)] = {**row, "effective_u_geom": u}
        target = str(row["target"])
        if order_id in orders and orders[order_id] != target:
            raise PilotIntegrityError(f"target inconsistente en {order_id}")
        orders[order_id] = target
    if len(orders) != EXPECTED_ORDERS:
        raise PilotIntegrityError(f"se esperaban {EXPECTED_ORDERS} pedidos, hay {len(orders)}")
    by_target: dict[str, list[str]] = {"euro-pallet": [], "rollcontainer": []}
    for order_id, target in sorted(orders.items()):
        if target not in by_target:
            raise PilotIntegrityError(f"target desconocido: {target}")
        by_target[target].append(order_id)
    for target, ids in by_target.items():
        if len(ids) != EXPECTED_PER_TARGET:
            raise PilotIntegrityError(f"{target}: se esperaban {EXPECTED_PER_TARGET}, hay {len(ids)}")
    missing = []
    for order_id in orders:
        for arm in ARMS:
            if arm == "greedy":
                if (order_id, arm, None) not in catalog:
                    missing.append(case_key(order_id, arm, None))
            else:
                for seed in SEEDS:
                    if (order_id, arm, seed) not in catalog:
                        missing.append(case_key(order_id, arm, seed))
    if missing:
        raise PilotIntegrityError(f"faltan claves: {missing[:8]}")
    return {
        "catalog": catalog,
        "orders": [{"order_id": order_id, "target": orders[order_id]} for order_id in sorted(orders)],
        "by_target": by_target,
        "seeds": list(SEEDS),
    }


def load_published_pilot(study_root: Path) -> dict[str, Any]:
    cases_root = study_root / "learning_packing" / "cases"
    if not cases_root.is_dir():
        raise PilotIntegrityError(f"no existe {cases_root}")
    return index_pilot(discover_results(cases_root))
