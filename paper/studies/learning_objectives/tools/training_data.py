"""Carga de estados etiquetados para entrenamiento (normalización suministrada, sin refit)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch

from labeling_verify import load_orders_from_manifest, learning_rows_from_orders
from normalization import apply_normalization


def load_normalization_document(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("fit_on") != "train_rows_only":
        raise RuntimeError("normalización no es train-only")
    if doc.get("refit_on_development_or_test"):
        raise RuntimeError("normalización marca refit prohibido")
    if "mean" not in doc or "scale" not in doc:
        raise RuntimeError("normalización incompleta")
    return doc


def build_states_from_orders(
    orders: list[dict[str, Any]],
    *,
    split: str,
    normalization: dict[str, Any],
) -> list[dict[str, Any]]:
    """Un estado = tensores de features normalizadas y Q_hat; peso igual por estado."""

    stats = {"mean": normalization["mean"], "scale": normalization["scale"]}
    states: list[dict[str, Any]] = []
    for order in orders:
        if order.get("split") != split:
            continue
        for state in order.get("states") or []:
            if not state.get("eligible_for_learning"):
                continue
            alts = state.get("alternatives") or []
            if not alts:
                continue
            if any(alt.get("q_hat") is None for alt in alts):
                raise RuntimeError(
                    f"Q_hat desconocido en {order['order_id']}:{state.get('choice_index')}"
                )
            feature_rows = [apply_normalization(alt["features"], stats) for alt in alts]
            q_hats = [float(alt["q_hat"]) for alt in alts]
            states.append(
                {
                    "order_id": order["order_id"],
                    "target": order["target"],
                    "split": order["split"],
                    "choice_index": int(state["choice_index"]),
                    "features": torch.tensor(feature_rows, dtype=torch.float32),
                    "q_hats": torch.tensor(q_hats, dtype=torch.float32),
                    "q_float64": q_hats,
                }
            )
    return states


def load_train_states(
    *,
    labels_output: Path,
    manifest: dict[str, Any],
    normalization_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    normalization = load_normalization_document(normalization_path)
    orders, failures = load_orders_from_manifest(labels_output, manifest)
    if failures:
        raise RuntimeError(f"pedidos no cargables: {[f['order_id'] for f in failures[:5]]}")
    states = build_states_from_orders(orders, split="train", normalization=normalization)
    if not states:
        raise RuntimeError("sin estados train")
    meta = {
        "n_train_states": len(states),
        "n_train_orders": len({s["order_id"] for s in states}),
        "n_train_learning_rows": len(learning_rows_from_orders(orders, split="train")),
        "n_development_learning_rows": len(learning_rows_from_orders(orders, split="development")),
        "normalization_sha256": normalization.get("sha256"),
        "normalization_n_rows": normalization.get("n_rows"),
    }
    return states, normalization, meta
