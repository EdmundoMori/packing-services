"""Diagnóstico exploratorio de capturas y transiciones ya guardadas.

No ejecuta políticas, no hace forward y no modifica los resultados del paso 08.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO / "paper/results/07_independent_evaluation"
PILOT_PAIRS = REPO / "paper/results/04_internal_pilot/paired_results.json"
PROTOCOL_07 = REPO / "paper/protocols/07_independent_evaluation.json"
PROTOCOL_03 = REPO / "paper/protocols/03_internal_pilot.json"
AUDIT_06A = REPO / "paper/results/06a_bc_transition_ids.json"
TRAIN_PKL = REPO / "online_policy_ml/data/train/transitions_p1s1.pkl"
VAL_PKL = REPO / "online_policy_ml/data/val/transitions_p1s1.pkl"
DIAGNOSTICS_PATH = REPO / "paper/results/09_policy_diagnostics.json"
EXPOSED_PATH = REPO / "paper/results/09_exposed_evaluation_ids.json"

VOLUME_TOL_MM3 = 1e-3
FEATURE_NAMES: tuple[str, ...] = (
    "item_l_n",
    "item_w_n",
    "item_h_n",
    "item_vol_n",
    "item_weight_n",
    "item_can_rotate",
    "pos_x_n",
    "pos_y_n",
    "pos_z_n",
    "ori_l_n",
    "ori_w_n",
    "ori_h_n",
    "support_ratio",
    "bin_index_n",
    "rank_0",
    "rank_1",
    "rank_2",
    "rank_3",
    "n_packed_n",
    "loaded_weight_n",
    "used_height_n",
    "remaining_n",
    "buffer_index_n",
    "preview_0_l_n",
    "preview_0_w_n",
    "preview_0_h_n",
    "preview_0_vol_n",
    "preview_1_l_n",
    "preview_1_w_n",
    "preview_1_h_n",
    "preview_1_vol_n",
    "preview_2_l_n",
    "preview_2_w_n",
    "preview_2_h_n",
    "preview_2_vol_n",
)
ITEM_FEATURES = ("item_l_n", "item_w_n", "item_h_n", "item_vol_n", "item_weight_n", "item_can_rotate")
RANK_FEATURES = ("rank_0", "rank_1", "rank_2", "rank_3")
PREVIEW_FEATURES = tuple(name for name in FEATURE_NAMES if name.startswith("preview_"))
INDEX = {name: position for position, name in enumerate(FEATURE_NAMES)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _volume(lwh: list[float] | tuple[float, ...]) -> float:
    return float(lwh[0]) * float(lwh[1]) * float(lwh[2])


def _placement_signature(placement: dict[str, Any]) -> tuple[Any, ...]:
    return (
        placement["item_id"],
        tuple(placement["flb_mm"]),
        tuple(placement["oriented_lwh_mm"]),
    )


def common_prefix_length(actor: list[dict[str, Any]], heuristic: list[dict[str, Any]]) -> int:
    length = 0
    for left, right in zip(actor, heuristic):
        if _placement_signature(left) != _placement_signature(right):
            break
        length += 1
    return length


def _brief(placement: dict[str, Any] | None) -> dict[str, Any] | None:
    if placement is None:
        return None
    return {
        "item_id": placement["item_id"],
        "original_lwh_mm": list(placement["original_lwh_mm"]),
        "oriented_lwh_mm": list(placement["oriented_lwh_mm"]),
        "flb_mm": list(placement["flb_mm"]),
    }


def first_divergence(actor: list[dict[str, Any]], heuristic: list[dict[str, Any]]) -> dict[str, Any]:
    """Primera diferencia observable. No es una causa del delta."""

    prefix = common_prefix_length(actor, heuristic)
    if prefix == len(actor) == len(heuristic):
        return {
            "kind": "ninguna",
            "prefix_length": prefix,
            "actor": None,
            "heuristic": None,
            "causal": False,
        }
    left = actor[prefix] if prefix < len(actor) else None
    right = heuristic[prefix] if prefix < len(heuristic) else None
    if left is None or right is None or left["item_id"] != right["item_id"]:
        kind = "identidad"
    elif list(left["flb_mm"]) != list(right["flb_mm"]):
        kind = "posicion"
    else:
        kind = "orientacion"
    return {
        "kind": kind,
        "prefix_length": prefix,
        "actor": _brief(left),
        "heuristic": _brief(right),
        "causal": False,
    }


def _counter(placements: list[dict[str, Any]]) -> Counter[str]:
    return Counter(placement["item_id"] for placement in placements)


def exclusive_sets(
    actor: list[dict[str, Any]],
    heuristic: list[dict[str, Any]],
) -> dict[str, Counter[str]]:
    actor_ids = _counter(actor)
    heuristic_ids = _counter(heuristic)
    return {
        "both": actor_ids & heuristic_ids,
        "actor_only": actor_ids - heuristic_ids,
        "heuristic_only": heuristic_ids - actor_ids,
    }


def _input_volumes(items: list[dict[str, Any]]) -> dict[str, float]:
    volumes: dict[str, float] = {}
    for item in items:
        volumes[item["item_id"]] = _volume((item["length_mm"], item["width_mm"], item["height_mm"]))
    return volumes


def _set_volume(counts: Counter[str], volumes: dict[str, float]) -> float | None:
    total = 0.0
    for item_id, count in counts.items():
        volume = volumes.get(item_id)
        if volume is None:
            return None
        total += volume * count
    return total


def packed_volume(placements: list[dict[str, Any]]) -> float:
    return sum(_volume(placement["oriented_lwh_mm"]) for placement in placements)


def volume_gap_explained(
    actor: list[dict[str, Any]],
    heuristic: list[dict[str, Any]],
    volumes: dict[str, float],
) -> dict[str, Any]:
    sets = exclusive_sets(actor, heuristic)
    actor_only = _set_volume(sets["actor_only"], volumes)
    heuristic_only = _set_volume(sets["heuristic_only"], volumes)
    if actor_only is None or heuristic_only is None:
        return {
            "explained": None,
            "reason": "un ítem colocado no está en la entrada",
            "exclusive_volume_gap_mm3": None,
            "packed_volume_gap_mm3": packed_volume(actor) - packed_volume(heuristic),
            "abs_residual_mm3": None,
        }
    exclusive_gap = actor_only - heuristic_only
    packed_gap = packed_volume(actor) - packed_volume(heuristic)
    residual = packed_gap - exclusive_gap
    explained = abs(residual) <= VOLUME_TOL_MM3
    return {
        "explained": explained,
        "reason": (
            "el volumen exclusivo coincide con la diferencia de volumen colocado"
            if explained
            else "el residual supera la tolerancia"
        ),
        "exclusive_volume_gap_mm3": exclusive_gap,
        "packed_volume_gap_mm3": packed_gap,
        "abs_residual_mm3": abs(residual),
    }


def final_height(placements: list[dict[str, Any]]) -> float | None:
    if not placements:
        return 0.0
    heights = []
    for placement in placements:
        flb = placement.get("flb_mm")
        oriented = placement.get("oriented_lwh_mm")
        if not isinstance(flb, list) or not isinstance(oriented, list) or len(flb) != 3 or len(oriented) != 3:
            return None
        heights.append(float(flb[2]) + float(oriented[2]))
    return max(heights) if heights else 0.0


def orientation_counts(placements: list[dict[str, Any]]) -> dict[str, int]:
    same = 0
    permuted = 0
    for placement in placements:
        if tuple(placement["oriented_lwh_mm"]) == tuple(placement["original_lwh_mm"]):
            same += 1
        else:
            permuted += 1
    return {"sin_cambio": same, "permutada": permuted}


def classify_pair(
    actor: list[dict[str, Any]] | None,
    heuristic: list[dict[str, Any]] | None,
) -> str:
    if actor is None or heuristic is None:
        return "evidencia_insuficiente"
    if [_placement_signature(item) for item in actor] == [_placement_signature(item) for item in heuristic]:
        return "planes_iguales"
    if _counter(actor) == _counter(heuristic):
        return "mismo_conjunto_geometria_distinta"
    return "conjunto_distinto"


def select_extremes(rows: list[dict[str, Any]], k: int = 5) -> dict[str, Any]:
    """Las mayores mejoras y deterioros, después de ver el delta. Desempata por id."""

    improvements = sorted(rows, key=lambda row: (-float(row["delta"]), row["order_id"]))[:k]
    deteriorations = sorted(rows, key=lambda row: (float(row["delta"]), row["order_id"]))[:k]
    return {
        "k": k,
        "selected_after_results": True,
        "tie_break": "order_id ascendente",
        "confirmatory": False,
        "improvements": improvements,
        "deteriorations": deteriorations,
    }


def _column(rows: list[list[float]], name: str) -> list[float]:
    position = INDEX[name]
    return [row[position] for row in rows]


def reconstruct_greedy_index(rows: list[list[float]]) -> dict[str, Any]:
    """Índice GreedyBestFit solo si los campos guardados fijan look=0 y rank_key completo.

    Con p=s=1 el buffer tiene un ítem, el lookahead de otros ítems es 0 y
    ``rank_0..rank_3`` son la clave best-fit de cuatro componentes. El desempate
    conservado es el primer mínimo, que es el orden de las filas guardadas.
    """

    if not rows:
        return {"status": "no_comprobable", "index": None, "reason": "sin candidatas"}
    width = {len(row) for row in rows}
    if width != {len(FEATURE_NAMES)}:
        return {"status": "no_comprobable", "index": None, "reason": "ancho de características distinto de 35"}
    if any(not math.isfinite(value) for row in rows for value in row):
        return {"status": "no_comprobable", "index": None, "reason": "hay un valor no finito"}
    if any(value != 0.0 for row in rows for value in _column(rows, "buffer_index_n")):
        return {"status": "no_comprobable", "index": None, "reason": "buffer_index_n no es 0"}
    if any(value != 0.0 for name in PREVIEW_FEATURES for value in _column(rows, name)):
        return {"status": "no_comprobable", "index": None, "reason": "la vista previa no está vacía"}
    for name in ITEM_FEATURES:
        values = _column(rows, name)
        if any(value != values[0] for value in values[1:]):
            return {"status": "no_comprobable", "index": None, "reason": "hay más de un ítem en las candidatas"}
    best = 0
    best_key: tuple[float, float, float, float] | None = None
    for index, row in enumerate(rows):
        key = tuple(row[INDEX[name]] for name in RANK_FEATURES)
        if best_key is None or key < best_key:
            best_key = key  # type: ignore[assignment]
            best = index
    return {
        "status": "comprobable",
        "index": best,
        "reason": "look nulo, un ítem, buffer 0 y rank_key de cuatro componentes",
    }


def _finite_stats(values: list[float]) -> dict[str, Any]:
    finite = [value for value in values if math.isfinite(value)]
    return {
        "n": len(values),
        "n_nonfinite": len(values) - len(finite),
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
        "n_equal_zero": sum(1 for value in finite if value == 0.0),
        "n_equal_one": sum(1 for value in finite if value == 1.0),
    }


def summarize_transitions(transitions: list[dict[str, Any]], *, split: str) -> dict[str, Any]:
    option_counts: Counter[int] = Counter()
    label_counts: Counter[int] = Counter()
    single = 0
    single_label_not_zero = 0
    multi = 0
    checkable = 0
    not_checkable = 0
    agree = 0
    disagree = 0
    reconstructed_index_zero = 0
    not_checkable_reasons: Counter[str] = Counter()
    volume_compared = 0
    volume_agree = 0
    reconstruction_matches_volume = 0
    reconstruction_mismatches_volume = 0
    columns: list[list[float]] = [[] for _ in FEATURE_NAMES]
    for transition in transitions:
        features = transition["features"]
        n_options = int(transition["n_options"])
        label = int(transition["label"])
        option_counts[n_options] += 1
        label_counts[label] += 1
        for row in features:
            for position, value in enumerate(row):
                columns[position].append(float(value))
        if n_options <= 1:
            single += 1
            if label != 0:
                single_label_not_zero += 1
            continue
        multi += 1
        reconstructed = reconstruct_greedy_index(features)
        if reconstructed["status"] != "comprobable":
            not_checkable += 1
            not_checkable_reasons[reconstructed["reason"]] += 1
            continue
        if "label_volume" in transition and int(transition["label_volume"]) != reconstructed["index"]:
            reconstruction_mismatches_volume += 1
            not_checkable += 1
            not_checkable_reasons["rank_key guardado no reproduce label_volume"] += 1
            continue
        checkable += 1
        if reconstructed["index"] == 0:
            reconstructed_index_zero += 1
        if "label_volume" in transition:
            volume_compared += 1
            reconstruction_matches_volume += 1
            if int(transition["label_volume"]) == label:
                volume_agree += 1
        if reconstructed["index"] == label:
            agree += 1
        else:
            disagree += 1
    counts = list(option_counts.elements())
    return {
        "split": split,
        "n_transitions": len(transitions),
        "n_options": {
            "min": min(option_counts) if option_counts else None,
            "max": max(option_counts) if option_counts else None,
            "mean": statistics.fmean(counts) if counts else None,
            "histogram": {str(key): option_counts[key] for key in sorted(option_counts)},
        },
        "label_histogram": {str(key): label_counts[key] for key in sorted(label_counts)},
        "single_candidate": {
            "n": single,
            "effective_choice": False,
            "label_not_zero": single_label_not_zero,
        },
        "multiple_candidates": {
            "n": multi,
            "checkable": checkable,
            "not_checkable": not_checkable,
            "not_checkable_reasons": dict(not_checkable_reasons),
            "greedy_agree": agree,
            "greedy_disagree": disagree,
            "agreement_denominator": checkable,
            "reconstructed_index_zero": reconstructed_index_zero,
        },
        "label_volume_on_checkable_multi": {
            "n": volume_compared,
            "teacher_equals_volume_index": volume_agree,
            "reconstructed_greedy_equals_volume_index": reconstruction_matches_volume,
            "reconstructed_greedy_differs_from_volume_index": reconstruction_mismatches_volume,
            "note": "label_volume es privileged_volume_ep, no una prueba automática del orden heurístico",
        },
        "features": {
            name: _finite_stats(columns[position]) for position, name in enumerate(FEATURE_NAMES)
        },
    }


def _audit_hashes() -> dict[str, str]:
    document = json.loads(AUDIT_06A.read_text(encoding="utf-8"))
    found: dict[str, list[str]] = {"train": [], "val": []}
    inspections = document["inspections"]
    for key, split in (("bc_working_train", "train"), ("bc_working_val", "val")):
        block = inspections[key]
        for moment in ("before", "after"):
            found[split].append(block[moment]["sha256"])
    if len(set(found["train"])) != 1 or len(set(found["val"])) != 1:
        raise RuntimeError("el resultado 06A no tiene un hash estable")
    return {"train": found["train"][0], "val": found["val"][0]}


def _read_transitions_payload() -> dict[str, Any]:
    expected = _audit_hashes()
    paths = {"train": TRAIN_PKL, "val": VAL_PKL}
    before = {split: sha256_file(path) for split, path in paths.items()}
    if before != expected:
        raise RuntimeError("el hash actual no coincide con el resultado 06A; no se leen los pickle")
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--read-transitions"],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    after = {split: sha256_file(path) for split, path in paths.items()}
    if after != expected:
        raise RuntimeError("el hash cambió durante la lectura")
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "la lectura de transiciones falló")
    payload = json.loads(completed.stdout)
    payload["sha256_before"] = before
    payload["sha256_after"] = after
    payload["sha256_matches_06a"] = True
    return payload


def _read_transitions_child() -> None:
    paths = {"train": TRAIN_PKL, "val": VAL_PKL}
    loaded: dict[str, Any] = {}
    for split, path in paths.items():
        with path.open("rb") as handle:
            import pickle

            loaded[split] = pickle.load(handle)
    summaries = {
        split: summarize_transitions(payload["transitions"], split=split) for split, payload in loaded.items()
    }
    combined = summarize_transitions(
        [*loaded["train"]["transitions"], *loaded["val"]["transitions"]],
        split="train_mas_val",
    )
    document = {
        "teacher_field": {split: payload.get("teacher") for split, payload in loaded.items()},
        "regime": {split: payload.get("regime") for split, payload in loaded.items()},
        "feature_names": {split: payload.get("feature_names") for split, payload in loaded.items()},
        "feature_version": {split: payload.get("feature_version") for split, payload in loaded.items()},
        "n_transitions_field": {split: payload.get("n_transitions") for split, payload in loaded.items()},
        "splits": summaries,
        "combined": combined,
    }
    json.dump(document, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def _placements(capture: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    if not isinstance(capture, dict) or not isinstance(capture.get("placements"), list):
        return None
    if not isinstance(capture.get("input_items"), list):
        return None
    return capture["placements"]


def _load_capture(order_id: str, method: str) -> dict[str, Any] | None:
    path = EVAL_DIR / "cases" / order_id / method / "capture.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def diagnose_order(pair: dict[str, Any]) -> dict[str, Any]:
    order_id = pair["order_id"]
    actor_capture = _load_capture(order_id, "actor")
    heuristic_capture = _load_capture(order_id, "heuristic")
    actor = _placements(actor_capture)
    heuristic = _placements(heuristic_capture)
    category = classify_pair(actor, heuristic)
    base = {
        "order_id": order_id,
        "target": pair["target"],
        "delta": pair["delta"],
        "category": category,
        "causal_claim_on_first_divergence": False,
    }
    if actor is None or heuristic is None or actor_capture is None or heuristic_capture is None:
        base.update(
            {
                "n_items": None,
                "requested_volume_mm3": None,
                "evidence": "evidencia_insuficiente",
            }
        )
        return base
    items = actor_capture["input_items"]
    volumes = _input_volumes(items)
    sets = exclusive_sets(actor, heuristic)
    both_volume = _set_volume(sets["both"], volumes)
    actor_only_volume = _set_volume(sets["actor_only"], volumes)
    heuristic_only_volume = _set_volume(sets["heuristic_only"], volumes)
    gap = volume_gap_explained(actor, heuristic, volumes)
    divergence = first_divergence(actor, heuristic)
    actor_height = final_height(actor)
    heuristic_height = final_height(heuristic)
    base.update(
        {
            "n_items": len(items),
            "requested_volume_mm3": sum(volumes.values()),
            "n_both": sum(sets["both"].values()),
            "n_actor_only": sum(sets["actor_only"].values()),
            "n_heuristic_only": sum(sets["heuristic_only"].values()),
            "volume_both_mm3": both_volume,
            "volume_actor_only_mm3": actor_only_volume,
            "volume_heuristic_only_mm3": heuristic_only_volume,
            "volume_gap": gap,
            "first_divergence": divergence,
            "prefix_length": divergence["prefix_length"],
            "final_height_mm": {"actor": actor_height, "heuristic": heuristic_height},
            "orientations": {"actor": orientation_counts(actor), "heuristic": orientation_counts(heuristic)},
            "actor_only_ids": sorted(sets["actor_only"]),
            "heuristic_only_ids": sorted(sets["heuristic_only"]),
        }
    )
    return base


def _detail_from_order(order: dict[str, Any]) -> dict[str, Any]:
    actor_capture = _load_capture(order["order_id"], "actor")
    heuristic_capture = _load_capture(order["order_id"], "heuristic")
    actor = _placements(actor_capture) or []
    heuristic = _placements(heuristic_capture) or []
    sets = exclusive_sets(actor, heuristic)

    def listed(placements: list[dict[str, Any]], counts: Counter[str]) -> list[dict[str, Any]]:
        remaining = Counter(counts)
        found = []
        for placement in placements:
            item_id = placement["item_id"]
            if remaining[item_id] <= 0:
                continue
            remaining[item_id] -= 1
            found.append(_brief(placement))
        return found

    return {
        "order_id": order["order_id"],
        "target": order["target"],
        "delta": order["delta"],
        "category": order["category"],
        "prefix_length": order.get("prefix_length"),
        "first_divergence": order.get("first_divergence"),
        "final_height_mm": order.get("final_height_mm"),
        "orientations": order.get("orientations"),
        "volume_gap": order.get("volume_gap"),
        "actor_only": listed(actor, sets["actor_only"]),
        "heuristic_only": listed(heuristic, sets["heuristic_only"]),
        "selection_after_results": True,
        "physical_stability_inferred": False,
    }


def _summary(orders: list[dict[str, Any]]) -> dict[str, Any]:
    categories = Counter(order["category"] for order in orders)
    divergence = Counter(
        (order.get("first_divergence") or {}).get("kind", "ausente") for order in orders
    )
    prefixes = [order["prefix_length"] for order in orders if isinstance(order.get("prefix_length"), int)]
    by_category = {}
    for category in (
        "planes_iguales",
        "mismo_conjunto_geometria_distinta",
        "conjunto_distinto",
        "evidencia_insuficiente",
    ):
        deltas = [float(order["delta"]) for order in orders if order["category"] == category]
        by_category[category] = {
            "n": len(deltas),
            "mean_delta": statistics.fmean(deltas) if deltas else None,
            "median_delta": statistics.median(deltas) if deltas else None,
        }
    residuals = [
        order["volume_gap"]["abs_residual_mm3"]
        for order in orders
        if isinstance(order.get("volume_gap"), dict) and order["volume_gap"]["abs_residual_mm3"] is not None
    ]
    explained = Counter(
        order["volume_gap"]["explained"]
        for order in orders
        if isinstance(order.get("volume_gap"), dict)
    )
    orientations = {
        "actor": Counter(),
        "heuristic": Counter(),
    }
    for order in orders:
        block = order.get("orientations") or {}
        for method in ("actor", "heuristic"):
            orientations[method].update(block.get(method) or {})
    heights = [
        (
            order["final_height_mm"]["actor"],
            order["final_height_mm"]["heuristic"],
        )
        for order in orders
        if isinstance(order.get("final_height_mm"), dict)
        and order["final_height_mm"]["actor"] is not None
        and order["final_height_mm"]["heuristic"] is not None
    ]
    return {
        "n_orders": len(orders),
        "categories": dict(categories),
        "by_category": by_category,
        "first_divergence": dict(divergence),
        "prefix_length": {
            "n": len(prefixes),
            "n_zero": sum(1 for value in prefixes if value == 0),
            "mean": statistics.fmean(prefixes) if prefixes else None,
            "median": statistics.median(prefixes) if prefixes else None,
            "min": min(prefixes) if prefixes else None,
            "max": max(prefixes) if prefixes else None,
        },
        "volume_explanation": {
            "n_true": explained.get(True, 0),
            "n_false": explained.get(False, 0),
            "n_unknown": explained.get(None, 0),
            "max_abs_residual_mm3": max(residuals) if residuals else None,
        },
        "orientations": {method: dict(counter) for method, counter in orientations.items()},
        "final_height_mm": {
            "n": len(heights),
            "actor_mean": statistics.fmean(pair[0] for pair in heights) if heights else None,
            "heuristic_mean": statistics.fmean(pair[1] for pair in heights) if heights else None,
        },
        "first_divergence_is_not_causal": True,
    }


def _exposed(order_ids: list[str]) -> dict[str, Any]:
    pilot = json.loads(PILOT_PAIRS.read_text(encoding="utf-8"))
    pilot_ids = [pair["order_id"] for pair in pilot["pairs"]]
    return {
        "schema_version": 1,
        "role": "pedidos ya observados por un diagnóstico posterior al resultado",
        "rewrites_historical_condition": False,
        "future_version_may_present_them_as_uninspected_confirmation": False,
        "sources": [
            {
                "name": "evaluacion_independiente",
                "n": len(order_ids),
                "run_id": "09d052b75a534728",
                "path": "paper/results/07_independent_evaluation/paired_results.json",
                "sha256": sha256_file(EVAL_DIR / "paired_results.json"),
                "protocol": "paper/protocols/07_independent_evaluation.json",
                "protocol_sha256": sha256_file(PROTOCOL_07),
                "order_ids": order_ids,
            },
            {
                "name": "piloto_interno",
                "n": len(pilot_ids),
                "run_id": pilot.get("run_id"),
                "path": "paper/results/04_internal_pilot/paired_results.json",
                "sha256": sha256_file(PILOT_PAIRS),
                "protocol": "paper/protocols/03_internal_pilot.json",
                "protocol_sha256": sha256_file(PROTOCOL_03),
                "order_ids": pilot_ids,
            },
        ],
    }


def build_diagnostics() -> dict[str, Any]:
    paired = json.loads((EVAL_DIR / "paired_results.json").read_text(encoding="utf-8"))
    orders = [diagnose_order(pair) for pair in paired["pairs"]]
    extremes = select_extremes(orders, 5)
    for group in ("improvements", "deteriorations"):
        extremes[group] = [_detail_from_order(order) for order in extremes[group]]
    transitions = _read_transitions_payload()
    return {
        "schema_version": 1,
        "exploratory": True,
        "confirmatory": False,
        "changes_step_08_conclusion": False,
        "run_id": paired.get("run_id"),
        "n_orders": len(orders),
        "summary": _summary(orders),
        "criterion": {
            "greedy_rank_key": "GreedyBestFit usa (-look, rank_key, buffer_index). best_fit guarda rank_key como (-contacto, z, y, x) en rank_0..rank_3.",
            "look": "look cuenta otros ítems de la vista previa con alguna candidata legal. No está guardado. Solo es 0 si la vista previa almacenada está vacía.",
            "teacher": "receding_horizon_ep simula el resto de la cola. Ese acceso no está en las 35 características del actor con p=1.",
            "label_is_not_heuristic_proof": True,
        },
        "transitions": transitions,
        "extremes": extremes,
        "orders": orders,
    }


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--read-transitions":
        _read_transitions_child()
        return
    diagnostics = build_diagnostics()
    exposed = _exposed([order["order_id"] for order in diagnostics["orders"]])
    DIAGNOSTICS_PATH.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    EXPOSED_PATH.write_text(json.dumps(exposed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
