#!/usr/bin/env python3
"""Audita manifiestos de splits ya escritos. No carga transiciones .pkl."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FOCUS_ORDER = "00100408"

SPLIT_FILES = {
    "report_01_working": ("artifacts/reports/01_splits.json", ("working_ids",)),
    "report_01_scale": ("artifacts/reports/01_splits.json", ("scale_ids",)),
    "manifest_working": ("data/splits/working_split.json", ()),
    "manifest_scale": ("data/splits/scale_split.json", ()),
    "manifest_full": ("data/splits/full_split.json", ()),
    "dir_working_train": ("data/train/order_ids.json", ()),
    "dir_working_val": ("data/val/order_ids.json", ()),
    "dir_working_test": ("data/test/order_ids.json", ()),
    "dir_scale_train": ("data/scale/train/order_ids.json", ()),
    "dir_scale_val": ("data/scale/val/order_ids.json", ()),
    "dir_scale_test": ("data/scale/test/order_ids.json", ()),
}

FLAT_ID_FILES = {
    "blocked_demo": "data/splits/blocked_demo_ids.json",
    "holdout_producto": "data/holdout_producto/order_ids.json",
    "report_01_blocked": "artifacts/reports/01_splits.json",
}


def _as_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"identificador no textual: {value!r}")
    return str(value)


def _id_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("se esperaba una lista de identificadores")
    return [_as_id(item) for item in value]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def split_lists(payload: Any, nested: tuple[str, ...]) -> dict[str, list[str]]:
    node = payload
    for key in nested:
        if not isinstance(node, dict) or key not in node:
            raise ValueError(f"falta la clave {key}")
        node = node[key]
    if isinstance(node, list):
        return {"ids": _id_list(node)}
    if not isinstance(node, dict):
        raise ValueError("el manifiesto no es un objeto de splits")
    return {str(name): _id_list(ids) for name, ids in node.items()}


def flat_ids(payload: Any, *, blocked_key: bool) -> list[str]:
    if isinstance(payload, list):
        return _id_list(payload)
    if isinstance(payload, dict) and "order_ids" in payload:
        return _id_list(payload["order_ids"])
    if blocked_key and isinstance(payload, dict) and "blocked_demo_ids" in payload:
        return _id_list(payload["blocked_demo_ids"])
    raise ValueError("no hay una lista de identificadores reconocible")


def duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    repeated: list[str] = []
    for item in ids:
        if item in seen and item not in repeated:
            repeated.append(item)
        seen.add(item)
    return repeated


def intersection(left: list[str], right: list[str]) -> list[str]:
    right_set = set(right)
    return sorted({item for item in left if item in right_set})


PARTITION_FAMILIES = ("manifest_working", "manifest_scale", "manifest_full")
PARTITION_CUTS = ("train", "val", "test")


def partition_names() -> list[str]:
    return [f"{family}.{cut}" for family in PARTITION_FAMILIES for cut in PARTITION_CUTS]


def _partition_parts(name: str) -> tuple[str, str]:
    family, cut = name.split(".", 1)
    return family, cut


def pair_kind(left: str, right: str) -> str:
    family_left, cut_left = _partition_parts(left)
    family_right, cut_right = _partition_parts(right)
    if cut_left != cut_right:
        return "cortes_distintos"
    if "manifest_full" in (family_left, family_right) and family_left != family_right:
        return "subconjunto_y_full_mismo_corte"
    return "subconjuntos_mismo_corte"


def partition_cross_audit(lists: dict[str, list[str] | None]) -> dict[str, Any]:
    """Cruza las nueve particiones. Una lista ausente no es un conjunto vacío."""

    names = partition_names()
    pairs: dict[str, Any] = {}
    problematic: list[dict[str, Any]] = []
    outside_full: list[dict[str, Any]] = []
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            key = f"{left} ∩ {right}"
            kind = pair_kind(left, right)
            if lists.get(left) is None or lists.get(right) is None:
                pairs[key] = {
                    "kind": kind,
                    "evidence": "faltante",
                    "status": "evidencia_faltante",
                    "n": None,
                    "ids": None,
                }
                continue
            shared = intersection(lists[left] or [], lists[right] or [])
            record: dict[str, Any] = {
                "kind": kind,
                "evidence": "presente",
                "n": len(shared),
            }
            if kind == "cortes_distintos":
                record["ids"] = shared
                record["status"] = "requiere_investigar" if shared else "sin_cruce_observado"
                if shared:
                    problematic.append({"pair": key, "n": len(shared), "ids": shared})
            elif kind == "subconjunto_y_full_mismo_corte":
                subset_name = left if "manifest_full" not in left else right
                full_name = right if subset_name == left else left
                outside = sorted(set(lists[subset_name] or []) - set(lists[full_name] or []))
                record["status"] = "solapamiento_esperado"
                record["subset_contained_in_full"] = not outside
                record["ids_outside_full"] = outside
                if outside:
                    outside_full.append({"pair": key, "ids": outside})
            else:
                record["status"] = "mismo_corte_entre_subconjuntos"
                record["ids"] = shared
            pairs[key] = record
    return {
        "partitions_requested": names,
        "missing_partitions": [name for name in names if lists.get(name) is None],
        "n_pairs": len(pairs),
        "pairs": pairs,
        "problematic_crosses": problematic,
        "ids_outside_full": outside_full,
        "note": (
            "Un archivo ausente queda como evidencia faltante y no como intersección vacía. "
            "Sin cruce observado no demuestra que un pedido no se haya usado fuera de estos manifiestos."
        ),
    }


def load_partition_lists(ml_root: Path) -> dict[str, list[str] | None]:
    files = {
        "manifest_working": ml_root / "data/splits/working_split.json",
        "manifest_scale": ml_root / "data/splits/scale_split.json",
        "manifest_full": ml_root / "data/splits/full_split.json",
    }
    loaded: dict[str, list[str] | None] = {}
    for family, path in files.items():
        payload = None
        if path.is_file():
            raw = load_json(path)
            payload = raw if isinstance(raw, dict) else None
        for cut in PARTITION_CUTS:
            name = f"{family}.{cut}"
            if payload is None or cut not in payload:
                loaded[name] = None
            else:
                loaded[name] = _id_list(payload[cut])
    return loaded


def row_order_ids(rows: object) -> list[str]:
    if not isinstance(rows, list):
        return []
    found: list[str] = []
    for row in rows:
        if isinstance(row, dict) and "order_id" in row:
            found.append(_as_id(row["order_id"]))
    return found


def audit(ml_root: Path) -> dict[str, Any]:
    """Lee JSON existentes bajo el árbol de online_policy_ml."""

    missing: list[str] = []
    lists: dict[str, list[str]] = {}
    errors: list[str] = []

    for name, (relative, nested) in SPLIT_FILES.items():
        path = ml_root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        try:
            parts = split_lists(load_json(path), nested)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
            continue
        if "ids" in parts and len(parts) == 1:
            lists[name] = parts["ids"]
        else:
            for split_name, ids in parts.items():
                lists[f"{name}.{split_name}"] = ids

    for name, relative in FLAT_ID_FILES.items():
        path = ml_root / relative
        if not path.is_file():
            if relative not in missing:
                missing.append(relative)
            continue
        try:
            lists[name] = flat_ids(load_json(path), blocked_key=name.startswith("report_01"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")

    comparisons: dict[str, Any] = {}
    for label, relative, extractor in (
        ("05_rows", "artifacts/reports/05_rl_ppo.json", lambda doc: row_order_ids(doc.get("rows"))),
        ("06_holdout", "artifacts/reports/06_evaluar_holdout.json", lambda doc: _id_list((doc.get("holdout") or {}).get("order_ids") or [])),
        ("06_scale_val", "artifacts/reports/06_evaluar_holdout.json", lambda doc: _id_list((doc.get("scale_val") or {}).get("order_ids") or [])),
        ("09_orders", "artifacts/reports/09_homologar_pct.json", lambda doc: _id_list(doc.get("order_ids") or [])),
        ("10_shared", "artifacts/reports/10_comparar_pct.json", lambda doc: _id_list(doc.get("shared") or [])),
    ):
        path = ml_root / relative
        if not path.is_file():
            missing.append(relative)
            comparisons[label] = {"evidence": "ausente", "ids": []}
            continue
        try:
            ids = extractor(load_json(path))
        except (OSError, json.JSONDecodeError, ValueError, AttributeError) as exc:
            errors.append(f"{relative}: {exc}")
            comparisons[label] = {"evidence": "ilegible", "ids": []}
            continue
        lists[label] = ids
        comparisons[label] = {"evidence": "presente", "n": len(ids), "n_unique": len(set(ids))}

    split_lists_only = {
        name: ids
        for name, ids in lists.items()
        if name not in {"05_rows", "06_holdout", "06_scale_val", "09_orders", "10_shared"}
    }
    duplicate_report = {name: duplicates(ids) for name, ids in split_lists_only.items()}
    duplicate_report = {name: found for name, found in duplicate_report.items() if found}

    named_pairs = (
        ("manifest_working.train", "manifest_scale.train"),
        ("manifest_working.val", "manifest_scale.val"),
        ("manifest_working.test", "manifest_scale.test"),
        ("manifest_working.train", "manifest_full.train"),
        ("manifest_scale.train", "manifest_full.train"),
        ("manifest_scale.val", "manifest_full.val"),
        ("manifest_scale.test", "manifest_full.test"),
        ("report_01_working.train", "manifest_working.train"),
        ("report_01_scale.val", "manifest_scale.val"),
        ("dir_scale_val", "manifest_scale.val"),
        ("05_rows", "manifest_scale.val"),
        ("05_rows", "manifest_working.val"),
        ("06_scale_val", "manifest_scale.val"),
        ("blocked_demo", "manifest_full.train"),
        ("blocked_demo", "manifest_scale.train"),
        ("blocked_demo", "manifest_working.train"),
        ("holdout_producto", "06_holdout"),
        ("09_orders", "10_shared"),
    )
    intersections: dict[str, Any] = {}
    for left, right in named_pairs:
        if left not in lists or right not in lists:
            intersections[f"{left} ∩ {right}"] = {"evidence": "faltante"}
            continue
        shared = intersection(lists[left], lists[right])
        intersections[f"{left} ∩ {right}"] = {
            "n": len(shared),
            "ids": shared if len(shared) <= 30 else shared[:30],
            "truncated": len(shared) > 30,
            "equal_as_sets": set(lists[left]) == set(lists[right]),
        }

    scale_inside_full = {}
    for part in ("train", "val", "test"):
        scale_key = f"manifest_scale.{part}"
        full_key = f"manifest_full.{part}"
        if scale_key not in lists or full_key not in lists:
            scale_inside_full[part] = "no comprobado"
            continue
        scale_inside_full[part] = set(lists[scale_key]).issubset(set(lists[full_key]))

    working_inside_full = {}
    for part in ("train", "val", "test"):
        working_key = f"manifest_working.{part}"
        full_key = f"manifest_full.{part}"
        if working_key not in lists or full_key not in lists:
            working_inside_full[part] = "no comprobado"
            continue
        working_inside_full[part] = set(lists[working_key]).issubset(set(lists[full_key]))

    prefix = {}
    for part in ("train", "val", "test"):
        scale_key = f"manifest_scale.{part}"
        full_key = f"manifest_full.{part}"
        if scale_key not in lists or full_key not in lists:
            prefix[part] = "no comprobado"
            continue
        prefix[part] = lists[full_key][: len(lists[scale_key])] == lists[scale_key]

    locations = sorted(name for name, ids in lists.items() if FOCUS_ORDER in ids)
    five_rows_unique = sorted(set(lists.get("05_rows", [])))
    scale_val = lists.get("manifest_scale.val", [])

    return {
        "ml_root": str(ml_root),
        "loaded_lists": {name: {"n": len(ids), "n_unique": len(set(ids))} for name, ids in sorted(lists.items())},
        "missing_files": sorted(set(missing)),
        "read_errors": errors,
        "duplicates_within_splits": duplicate_report,
        "comparison_row_repeats": {
            "05_rows": "cada pedido aparece una vez por motor en rows; no es un duplicado de split"
            if lists.get("05_rows") and len(lists["05_rows"]) != len(set(lists["05_rows"]))
            else "no comprobado"
        },
        "intersections": intersections,
        "working_subset_of_full": working_inside_full,
        "scale_subset_of_full": scale_inside_full,
        "scale_is_prefix_of_full": prefix,
        "comparisons": comparisons,
        "vs_heuristic_matches_scale_val": (
            set(five_rows_unique) == set(scale_val) if "05_rows" in lists and "manifest_scale.val" in lists else "no comprobado"
        ),
        "vs_heuristic_matches_working_val": (
            set(five_rows_unique) == set(lists["manifest_working.val"])
            if "05_rows" in lists and "manifest_working.val" in lists
            else "no comprobado"
        ),
        "focus_order_id": FOCUS_ORDER,
        "focus_locations": locations,
        "exposure": classify_focus(lists),
        "note": (
            "La ausencia en un manifiesto no demuestra que un pedido no se haya usado. "
            "No se leyeron transiciones .pkl ni checkpoints."
        ),
    }


def classify_focus(lists: dict[str, list[str]]) -> dict[str, Any]:
    """Clasifica 00100408 con la evidencia presente. No inventa independencia."""

    def present(name: str) -> bool:
        return FOCUS_ORDER in lists.get(name, [])

    training_names = [name for name in lists if name.endswith(".train") or name.endswith("_train")]
    selection_names = [
        "manifest_scale.val",
        "report_01_scale.val",
        "dir_scale_val",
        "05_rows",
        "06_scale_val",
        "manifest_working.val",
        "report_01_working.val",
        "dir_working_val",
    ]
    later_names = ["holdout_producto", "blocked_demo", "report_01_blocked", "06_holdout", "09_orders", "10_shared"]
    a_hits = [name for name in training_names if present(name)]
    b_hits = [name for name in selection_names if name in lists and present(name)]
    c_hits = [name for name in later_names if name in lists and present(name)]
    inspected_later = [name for name in ("06_holdout", "09_orders", "10_shared") if present(name)]
    return {
        "A_pertenencia_entrenamiento": {
            "observado_en": a_hits,
            "ausente_de_manifiestos_train_leidos": [name for name in training_names if not present(name)],
            "conclusion": (
                "aparece en un manifiesto de entrenamiento"
                if a_hits
                else "no aparece en los manifiestos de entrenamiento leídos; eso no demuestra que nunca se usara"
            ),
        },
        "B_validacion_o_seleccion": {
            "observado_en": b_hits,
            "conclusion": (
                "aparece en un manifiesto de validación o en la comparación guardada de selección"
                if b_hits
                else "no aparece en los manifiestos de validación ni en las filas de 05 leídas"
            ),
        },
        "C_evaluacion_posterior_registrada": {
            "observado_en": c_hits,
            "inspeccionado_en_evaluaciones_guardadas": inspected_later,
            "conclusion": (
                "hay evaluación o bloqueo de producto registrado; no es un test confirmatorio sin inspeccionar"
                if c_hits
                else "no hay evaluación posterior en los informes leídos"
            ),
        },
        "D_exposicion_desconocida": {
            "pkl_no_leidos": True,
            "checkpoints_no_deserializados": True,
            "conclusion": "queda exposición no registrada fuera de estos JSON",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audita exposición de splits en JSON existentes.")
    parser.add_argument("--ml-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--cross-output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.output is None and args.cross_output is None:
        parser.error("indica --output, --cross-output o ambos")
    root = args.ml_root.expanduser().resolve()
    if args.output is not None:
        payload = audit(root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.cross_output is not None:
        cross = partition_cross_audit(load_partition_lists(root))
        args.cross_output.parent.mkdir(parents=True, exist_ok=True)
        args.cross_output.write_text(json.dumps(cross, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
