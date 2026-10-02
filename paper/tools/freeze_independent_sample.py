#!/usr/bin/env python3
"""Congela la muestra del paso 07. No ejecuta packing ni abre checkpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SELECTION_LABEL = "packing-study-eval-v1|20261002"
POOL_N = {"euro-pallet": 675, "rollcontainer": 815}
QUOTA_N = {"euro-pallet": 91, "rollcontainer": 109}
EXPECTED_EXCLUSIONS = {
    "euro-pallet": ("00101249", "00102764", "00108147", "00109619"),
    "rollcontainer": ("00100348", "00104068", "00108193", "00108237", "00109274"),
}
CONTAINERS = {
    "euro-pallet": ("EURO_PALLET", 1200.0, 800.0, 2000.0, 1920000000.0),
    "rollcontainer": ("ROLLCONTAINER", 800.0, 700.0, 2000.0, 1120000000.0),
}


class FreezeStopped(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def selection_token(target: str, order_id: str) -> str:
    return f"{SELECTION_LABEL}|{target}|{order_id}"


def selection_hash(target: str, order_id: str) -> str:
    return sha256_text(selection_token(target, order_id))


def frozen_list_sha256(order_ids: list[str]) -> str:
    return sha256_text("\n".join(order_ids) + "\n")


def rank_ids(order_ids: list[str], target: str) -> list[dict[str, Any]]:
    ranked = [
        {"order_id": order_id, "target": target, "selection_hash": selection_hash(target, order_id)}
        for order_id in order_ids
    ]
    ranked.sort(key=lambda row: (row["selection_hash"], row["order_id"]))
    for index, row in enumerate(ranked):
        row["selection_rank"] = index
    return ranked


def select_from_ranked(ranked: list[dict[str, Any]], quota: int) -> list[dict[str, Any]]:
    if len(ranked) < quota:
        raise FreezeStopped(f"el pool tiene {len(ranked)} ids y la cuota es {quota}")
    return [dict(row) for row in ranked[:quota]]


def execution_order(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(selected, key=lambda row: row["order_id"])
    for position, row in enumerate(ordered):
        row["position"] = position
    return ordered


def check_pools(pools: dict[str, list[str]], exclusions: dict[str, list[str]], full_test: set[str]) -> None:
    for target, expected in POOL_N.items():
        ids = pools.get(target)
        if ids is None or len(ids) != expected:
            found = None if ids is None else len(ids)
            raise FreezeStopped(
                f"el pool {target} tiene {found} ids; se esperaban {expected}. No se selecciona."
            )
        if len(set(ids)) != len(ids):
            raise FreezeStopped(f"el pool {target} tiene ids repetidos. No se selecciona.")
        outside = sorted(set(ids) - full_test)
        if outside:
            raise FreezeStopped(f"{target} tiene ids fuera de full.test. No se selecciona.")
        excluded = exclusions.get(target) or []
        expected_excluded = set(EXPECTED_EXCLUSIONS[target])
        if set(excluded) != expected_excluded:
            raise FreezeStopped(f"las exclusiones de {target} no coinciden con el registro 06A. No se selecciona.")
        overlap = sorted(set(ids) & set(excluded))
        if overlap:
            raise FreezeStopped(f"{target} mezcla candidatos y exclusiones. No se selecciona.")
        if not set(excluded) <= full_test:
            raise FreezeStopped(f"una exclusión de {target} no está en full.test. No se selecciona.")


def select_sample(pools: dict[str, list[str]], exclusions: dict[str, list[str]], full_test: set[str]) -> dict[str, Any]:
    check_pools(pools, exclusions, full_test)
    chosen: list[dict[str, Any]] = []
    ranked_selected: dict[str, list[dict[str, Any]]] = {}
    for target, quota in QUOTA_N.items():
        ranked = rank_ids(pools[target], target)
        picked = select_from_ranked(ranked, quota)
        ranked_selected[target] = picked
        chosen.extend(picked)
    ordered = execution_order(chosen)
    return {
        "by_target_rank": ranked_selected,
        "execution_items": ordered,
        "frozen_list_sha256": frozen_list_sha256([row["order_id"] for row in ordered]),
        "called_clean": False,
        "absolute_independence": False,
        "historical_file_identity": "no_comprobada",
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pools_from_exposure(payload: dict[str, Any]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    by_target = payload.get("by_target") or {}
    pools: dict[str, list[str]] = {}
    exclusions: dict[str, list[str]] = {}
    for target in POOL_N:
        block = by_target.get(target) or {}
        absent = (block.get("absent_from_inspected_sources") or {}).get("ids")
        excluded = (block.get("positive_exclusion") or {}).get("ids")
        if not isinstance(absent, list) or not isinstance(excluded, list):
            raise FreezeStopped(f"faltan listas de {target}. No se selecciona.")
        pools[target] = [str(item) for item in absent]
        exclusions[target] = [str(item) for item in excluded]
    return pools, exclusions


def dataset_targets_match(dataset: dict[str, Any], pools: dict[str, list[str]]) -> None:
    missing: list[str] = []
    mismatched: list[str] = []
    for target, ids in pools.items():
        for order_id in ids:
            order = dataset.get(order_id)
            if not isinstance(order, dict):
                missing.append(order_id)
                continue
            found = str((order.get("properties") or {}).get("target") or "")
            if found != target:
                mismatched.append(order_id)
    if missing or mismatched:
        raise FreezeStopped(
            f"hay {len(missing)} ids ausentes del dataset y {len(mismatched)} con otro target. No se selecciona."
        )


def protocol_items(selected: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for row in selected["execution_items"]:
        container_id, length, width, height, volume = CONTAINERS[row["target"]]
        items.append(
            {
                "position": row["position"],
                "order_id": row["order_id"],
                "target": row["target"],
                "target_source": row["target"],
                "targets_match": True,
                "selection_rank": row["selection_rank"],
                "selection_hash": row["selection_hash"],
                "container_id": container_id,
                "container_length_mm": length,
                "container_width_mm": width,
                "container_height_mm": height,
                "container_volume_mm3": volume,
                "max_weight_kg": 1500.0,
            }
        )
    return items


def build_freeze_document(
    *,
    pools: dict[str, list[str]],
    exclusions: dict[str, list[str]],
    selected: dict[str, Any],
    exposure_sha256: str,
    full_test_sha256: str,
    dataset_sha256: str,
    checkpoint_sha256: str,
) -> dict[str, Any]:
    return {
        "step": "07",
        "called_clean": False,
        "absolute_independence": False,
        "historical_file_identity": "no_comprobada",
        "absence_note": "Estos ids no aparecen en las fuentes inspeccionadas en 06A. La identidad histórica del archivo BC sigue no comprobada.",
        "selection_label": SELECTION_LABEL,
        "pool_n": {target: len(ids) for target, ids in pools.items()},
        "quota_n": dict(QUOTA_N),
        "candidates": pools,
        "positive_exclusions": exclusions,
        "selection_hashes": {
            target: [
                {"order_id": row["order_id"], "selection_rank": row["selection_rank"], "selection_hash": row["selection_hash"]}
                for row in rows
            ]
            for target, rows in selected["by_target_rank"].items()
        },
        "execution_ids": [row["order_id"] for row in selected["execution_items"]],
        "frozen_list_sha256": selected["frozen_list_sha256"],
        "frozen_list_rule": "SHA256 UTF-8 de los 200 ids en orden ascendente, unidos por salto de línea y con salto final",
        "exposure_sha256": exposure_sha256,
        "full_test_sha256": full_test_sha256,
        "source_dataset_sha256": dataset_sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "checkpoint_deserialized": False,
    }


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    exposure_path = repo / "paper/results/06a_candidate_exposure_by_target.json"
    full_path = repo / "online_policy_ml/data/splits/full_split.json"
    dataset_path = Path("/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json")
    checkpoint_path = repo / "online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt"
    pilot_protocol = _load(repo / "paper/protocols/03_internal_pilot.json")
    exposure = _load(exposure_path)
    full_split = _load(full_path)
    full_test = {str(item) for item in full_split.get("test") or []}
    pools, exclusions = pools_from_exposure(exposure)
    check_pools(pools, exclusions, full_test)
    dataset = _load(dataset_path)
    dataset_targets_match(dataset, pools)
    published = ((pilot_protocol.get("methods") or {}).get("A") or {}).get("sha256")
    checkpoint_sha = _sha256_file(checkpoint_path)
    if checkpoint_sha != published:
        raise FreezeStopped("el hash de bytes del checkpoint no coincide con el protocolo piloto. No se selecciona.")
    selected = select_sample(pools, exclusions, full_test)
    document = build_freeze_document(
        pools=pools,
        exclusions=exclusions,
        selected=selected,
        exposure_sha256=_sha256_file(exposure_path),
        full_test_sha256=_sha256_file(full_path),
        dataset_sha256=_sha256_file(dataset_path),
        checkpoint_sha256=checkpoint_sha,
    )
    out = repo / "paper/results/07_sample_freeze.json"
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    protocol = {
        "schema_version": 1,
        "protocol_id": "07_independent_evaluation",
        "status": "congelado, sin ejecutar",
        "evaluation_executed": False,
        "pilot_executed": False,
        "called_clean": False,
        "absolute_independence": False,
        "historical_file_identity": "no_comprobada",
        "compares_with_pct": False,
        "physical_stability_verified": None,
        "sample_role": "pedidos ausentes de las fuentes inspeccionadas en 06A",
        "not_scale_val": True,
        "question": "¿La política aprendida mejora la utilización geométrica frente a GreedyBestFit cuando ambas reciben las mismas candidatas y restricciones, en esta muestra congelada?",
        "methods": {
            "A": {
                "name": "actor con pesos BC conservados tras la selección PPO",
                "checkpoint": "online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt",
                "sha256": checkpoint_sha,
                "deserialized": False,
                "role": "Puntúa candidatas ya legales. Los tensores vigentes coinciden con el BC. best_epoch=0 no es una mejora obtenida mediante PPO.",
            },
            "B": {
                "name": "GreedyBestFitPolicy",
                "code": "src/packing_services/online/policies.py",
                "role": "Elige entre las mismas candidatas legales por rank_key. Con p=1 no hay otros ítems en la ventana.",
            },
        },
        "common_conditions": pilot_protocol["common_conditions"],
        "operational": {
            "device": "cpu",
            "timeout_seconds": 300,
            "attempts_per_method_order": 1,
            "capture": "completa, con contraste independiente",
            "failure_u_geom": 0,
            "failures_stay_in_denominator": True,
        },
        "orders": {
            "source_dataset": "/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json",
            "source_dataset_sha256": document["source_dataset_sha256"],
            "full_test_manifest": "online_policy_ml/data/splits/full_split.json",
            "full_test_sha256": document["full_test_sha256"],
            "exposure_file": "paper/results/06a_candidate_exposure_by_target.json",
            "exposure_sha256": document["exposure_sha256"],
            "freeze_file": "paper/results/07_sample_freeze.json",
            "freeze_sha256": _sha256_file(out),
            "n": 200,
            "n_euro_pallet": QUOTA_N["euro-pallet"],
            "n_rollcontainer": QUOTA_N["rollcontainer"],
            "pool_n": document["pool_n"],
            "execution_order": "id_ascendente",
            "selection_label": SELECTION_LABEL,
            "selection_rule": "Dentro de cada target, SHA256 de packing-study-eval-v1|20261002|TARGET|ID, orden por hash y después por id. Se toman los primeros 91 y 109.",
            "frozen_list_sha256": selected["frozen_list_sha256"],
            "frozen_list_rule": document["frozen_list_rule"],
            "positive_exclusion_ids": [order_id for target in QUOTA_N for order_id in exclusions[target]],
            "called_clean": False,
            "historical_file_identity": "no_comprobada",
            "items": protocol_items(selected),
        },
        "primary_metric": {
            "name": "U_geom",
            "definition": "U_geom del pedido es el volumen de los ítems colocados, con dimensiones verificadas contra la entrada, dividido por el volumen del contenedor de ese pedido",
            "paired_difference": "delta_i = U_geom(actor,i) - U_geom(heuristica,i)",
            "container_volume_by_target_mm3": {"euro-pallet": 1920000000.0, "rollcontainer": 1120000000.0},
        },
        "aggregate": {
            "primary": "media aritmética de los 200 delta_i, con el mismo peso por pedido",
            "n": 200,
            "n_rows": 400,
            "n_pairs": 200,
            "failures_stay_in_denominator": True,
            "invalid_u_geom": 0,
            "tie": "abs(delta) <= 1e-9",
            "by_target_required": True,
            "by_target_role": "secundario y descriptivo",
            "bootstrap": {
                "interval": "intervalo bootstrap percentil del 95 %",
                "replicates": 20000,
                "seed": 20261002,
                "generator": "numpy.random.default_rng(20261002)",
                "resample": "pedidos pareados dentro de cada target",
                "counts_per_replicate": {"euro-pallet": 91, "rollcontainer": 109},
                "methods_resampled_separately": False,
                "percentiles": [2.5, 97.5],
                "percentile_method": "linear",
                "scope": "aproximado; supone pedidos suficientemente independientes; no es garantía ni un intervalo sobre todas las instancias posibles",
            },
            "interpretation": {
                "above_zero": "evidencia de ventaja media bajo este protocolo",
                "below_zero": "evidencia de desventaja media bajo este protocolo",
                "includes_zero": "resultado no concluyente respecto al signo de la media",
                "inconclusive_is_not_equality": True,
            },
            "no_optional_stopping": True,
            "future_enlargement_needs_new_protocol": True,
            "frozen_before_execution": True,
            "executed": False,
            "values": None,
        },
        "future_output_dir": "paper/results/07_independent_evaluation/",
        "not_allowed": [
            "Superamos a PCT.",
            "Mejoramos el estado del arte.",
            "Demostramos estabilidad física.",
            "Estos pedidos son absolutamente limpios.",
            "Un intervalo que incluye 0 demuestra igualdad.",
            "La ventaja del piloto interno proviene de actualizaciones PPO.",
        ],
    }
    protocol_path = repo / "paper/protocols/07_independent_evaluation.json"
    protocol_path.write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "frozen_list_sha256": selected["frozen_list_sha256"],
        "n": len(selected["execution_items"]),
        "n_euro_pallet": sum(1 for row in selected["execution_items"] if row["target"] == "euro-pallet"),
        "n_rollcontainer": sum(1 for row in selected["execution_items"] if row["target"] == "rollcontainer"),
        "checkpoint_deserialized": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FreezeStopped as exc:
        print(exc.message)
        raise SystemExit(2)
