"""Contraste completo de artefactos persistidos (R03-preparación).

No declara orientation_ok=True sin comprobarlo. Si falta un dato necesario,
reporta la propiedad como no comprobada (no inventa aceptación).
AABB ≠ estabilidad física.
"""

from __future__ import annotations

import math
from typing import Any

from episode_validation import has_sufficient_artifacts


class ArtifactContrastError(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactContrastError(message)


def _finite_positive(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArtifactContrastError(f"{name} no numérico")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ArtifactContrastError(f"{name} debe ser finito y > 0")
    return number


def _dims_equal(
    a: tuple[float, float, float], b: tuple[float, float, float], *, tol: float
) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _is_permutation(
    oriented: tuple[float, float, float],
    original: tuple[float, float, float],
    *,
    tol: float,
) -> bool:
    return all(
        abs(x - y) <= tol for x, y in zip(sorted(oriented), sorted(original))
    )


def orientation_allowed(
    oriented: tuple[float, float, float],
    original: tuple[float, float, float],
    *,
    allow_rotation: bool | None,
    allowed_orientations: str | None,
    tol: float,
) -> tuple[bool | None, str]:
    """Devuelve (ok, status). ok=None si no se pudo comprobar."""

    if allow_rotation is None:
        return None, "no_comprobada: falta allow_rotation en artifacts"
    if allowed_orientations is None:
        return None, "no_comprobada: falta allowed_orientations del ítem"
    item_allows = allowed_orientations != "none"
    effective = bool(allow_rotation) and item_allows
    if effective:
        ok = _is_permutation(oriented, original, tol=tol)
        return ok, "comprobada_permutacion" if ok else "orientacion_no_permitida"
    ok = _dims_equal(oriented, original, tol=tol)
    return ok, "comprobada_sin_rotacion" if ok else "orientacion_no_permitida"


def contrast_artifacts(
    document: dict[str, Any], *, tol: float = 1e-9
) -> dict[str, Any]:
    """Contraste identidad/orientación/placements/rewards/cierre desde snapshot."""

    if not has_sufficient_artifacts(document):
        return {
            "level": "artifact_contrast",
            "ok": False,
            "audit_performed": False,
            "status": "auditoria_no_realizada",
            "reason": "snapshot insuficiente (bin_lwh_mm, input_items, placements)",
            "properties": {},
            "physical_stability_verified": None,
        }

    artifacts = document["artifacts"]
    bin_lwh = tuple(_finite_positive(x, name=f"bin[{i}]") for i, x in enumerate(artifacts["bin_lwh_mm"]))
    bin_volume = bin_lwh[0] * bin_lwh[1] * bin_lwh[2]
    input_items = artifacts["input_items"]
    placements = artifacts["placements"]
    transitions = document.get("transitions") or []
    properties: dict[str, Any] = {}

    # --- IDs únicos y dimensiones originales ---
    ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(input_items):
        if not isinstance(item, dict):
            raise ArtifactContrastError(f"input_items[{index}] no es objeto")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ArtifactContrastError(f"input_items[{index}].id inválido")
        if item_id in by_id:
            raise ArtifactContrastError(f"ID duplicado en snapshot: {item_id}")
        length = _finite_positive(item.get("length"), name=f"{item_id}.length")
        width = _finite_positive(item.get("width"), name=f"{item_id}.width")
        height = _finite_positive(item.get("height"), name=f"{item_id}.height")
        ids.append(item_id)
        by_id[item_id] = {
            **item,
            "length": length,
            "width": width,
            "height": height,
            "sequence_index": item.get("sequence_index", index),
        }
    properties["input_ids_unique"] = {"checked": True, "ok": True, "n": len(ids)}
    properties["input_dims_finite_positive"] = {"checked": True, "ok": True}

    allow_rotation = artifacts.get("allow_rotation")
    if allow_rotation is not None and type(allow_rotation) is not bool:
        raise ArtifactContrastError("allow_rotation debe ser bool estricto o ausente")

    container_id = artifacts.get("container_id")
    expected_container = container_id if isinstance(container_id, str) and container_id else None
    if expected_container is None:
        properties["container_id"] = {
            "checked": False,
            "status": "no_comprobada: falta container_id en artifacts",
        }

    # --- Placements como prefijo de la secuencia (orden estricto) ---
    _require(isinstance(placements, list), "placements debe ser lista")
    n_placed = len(placements)
    _require(n_placed <= len(ids), "más placements que ítems de entrada")
    expected_prefix = ids[:n_placed]
    placed_ids = []
    for index, row in enumerate(placements):
        if not isinstance(row, dict):
            raise ArtifactContrastError(f"placements[{index}] no es objeto")
        pid = row.get("item_id")
        if not isinstance(pid, str) or not pid:
            raise ArtifactContrastError(f"placements[{index}].item_id inválido")
        if pid not in by_id:
            raise ArtifactContrastError(f"placement con ID desconocido: {pid}")
        placed_ids.append(pid)
        if expected_container is not None:
            cid = row.get("container_id")
            _require(cid == expected_container, f"container_id placement != snapshot ({cid})")
    if placed_ids != expected_prefix:
        raise ArtifactContrastError(
            "placements ausentes/adicionales/duplicados/reordenados respecto de la secuencia: "
            f"got={placed_ids} expected_prefix={expected_prefix}"
        )
    properties["placement_sequence_prefix"] = {"checked": True, "ok": True, "n_placed": n_placed}

    # --- Correspondencia 1:1 transición ↔ placement ---
    _require(
        len(transitions) == n_placed,
        f"len(transitions)={len(transitions)} != len(placements)={n_placed}",
    )
    orientation_results: list[dict[str, Any]] = []
    reward_checks: list[dict[str, Any]] = []
    placed_volume = 0.0
    for index, (row, tr) in enumerate(zip(placements, transitions)):
        item = by_id[row["item_id"]]
        original = (item["length"], item["width"], item["height"])
        oriented = (
            _finite_positive(row.get("l"), name=f"placement[{index}].l"),
            _finite_positive(row.get("w"), name=f"placement[{index}].w"),
            _finite_positive(row.get("h"), name=f"placement[{index}].h"),
        )
        x = float(row["x"])
        y = float(row["y"])
        z = float(row["z"])
        for name, value in (("x", x), ("y", y), ("z", z)):
            if not math.isfinite(value):
                raise ArtifactContrastError(f"placement[{index}].{name} no finito")

        ori_ok, ori_status = orientation_allowed(
            oriented,
            original,
            allow_rotation=allow_rotation,
            allowed_orientations=item.get("allowed_orientations"),
            tol=tol,
        )
        if ori_ok is None:
            orientation_results.append(
                {"index": index, "checked": False, "status": ori_status}
            )
        elif ori_ok is False:
            raise ArtifactContrastError(
                f"orientación no permitida en placement[{index}] id={row['item_id']}"
            )
        else:
            orientation_results.append(
                {"index": index, "checked": True, "ok": True, "status": ori_status}
            )

        geometry = tr.get("chosen_geometry")
        _require(
            isinstance(geometry, (list, tuple)) and len(geometry) >= 7,
            f"chosen_geometry insuficiente en transición {index}",
        )
        # geometry_key: bin_index, x, y, z, l, w, h
        g_pos = (float(geometry[1]), float(geometry[2]), float(geometry[3]))
        g_dims = (float(geometry[4]), float(geometry[5]), float(geometry[6]))
        _require(
            abs(g_pos[0] - x) <= tol
            and abs(g_pos[1] - y) <= tol
            and abs(g_pos[2] - z) <= tol,
            f"posición transición[{index}] != placement",
        )
        _require(
            _dims_equal(g_dims, oriented, tol=tol),
            f"dims orientadas transición[{index}] != placement",
        )

        vol = oriented[0] * oriented[1] * oriented[2]
        nominal = original[0] * original[1] * original[2]
        _require(abs(vol - nominal) <= tol, "volumen orientado != volumen nominal del ítem")
        placed_volume += vol
        expected_reward = vol / bin_volume
        reward = float(tr["reward"])
        if not math.isfinite(reward):
            raise ArtifactContrastError(f"reward[{index}] no finito")
        if abs(reward - expected_reward) > tol:
            raise ArtifactContrastError(
                f"reward[{index}]={reward} != V_item/V_bin={expected_reward}"
            )
        reward_checks.append(
            {
                "index": index,
                "checked": True,
                "ok": True,
                "reward": reward,
                "expected": expected_reward,
            }
        )

    if any(not row["checked"] for row in orientation_results):
        properties["orientations"] = {
            "checked": False,
            "status": "parcialmente_no_comprobada",
            "details": orientation_results,
        }
    else:
        properties["orientations"] = {
            "checked": True,
            "ok": True,
            "details": orientation_results,
        }
    properties["transition_placement_correspondence"] = {"checked": True, "ok": True}
    properties["per_step_reward_vs_nominal_volume"] = {
        "checked": True,
        "ok": True,
        "details": reward_checks,
    }

    reward_sum = float(sum(float(tr["reward"]) for tr in transitions))
    u_geom = placed_volume / bin_volume
    _require(abs(reward_sum - u_geom) <= tol, f"suma rewards={reward_sum} != U_geom={u_geom}")
    properties["accumulated_volume_return"] = {
        "checked": True,
        "ok": True,
        "placed_volume_mm3": placed_volume,
        "bin_volume_mm3": bin_volume,
        "u_geom": u_geom,
        "reward_sum": reward_sum,
    }

    # --- Cierre y no colocados ---
    unpacked = artifacts.get("unpacked")
    end_reason = document.get("end_reason")
    terminated = document.get("terminated")
    truncated = document.get("truncated")
    remaining_ids = ids[n_placed:]
    if unpacked is None:
        properties["unpacked_closure"] = {
            "checked": False,
            "status": "no_comprobada: falta artifacts.unpacked",
        }
    else:
        if not isinstance(unpacked, list):
            raise ArtifactContrastError("unpacked debe ser lista")
        unpacked_ids = []
        for index, row in enumerate(unpacked):
            if not isinstance(row, dict):
                raise ArtifactContrastError(f"unpacked[{index}] no es objeto")
            uid = row.get("item_id")
            if not isinstance(uid, str) or not uid:
                raise ArtifactContrastError(f"unpacked[{index}].item_id inválido")
            if uid not in by_id:
                raise ArtifactContrastError(f"unpacked ID desconocido: {uid}")
            if uid in placed_ids:
                raise ArtifactContrastError(f"ítem colocado y unpacked: {uid}")
            unpacked_ids.append(uid)
            reason = row.get("reason")
            if not isinstance(reason, str) or not reason:
                raise ArtifactContrastError(f"unpacked[{index}] sin reason")
        if terminated and not truncated:
            if end_reason == "all_items_placed":
                _require(n_placed == len(ids), "all_items_placed con ítems pendientes")
                _require(unpacked_ids == [], "all_items_placed con unpacked no vacío")
            elif end_reason in (
                "no_legal_candidate_on_reset",
                "no_legal_candidate_after_placement",
                "no_legal_candidate",
            ):
                _require(
                    unpacked_ids == remaining_ids,
                    f"unpacked != sufijo esperado: {unpacked_ids} vs {remaining_ids}",
                )
            else:
                properties["unpacked_end_reason"] = {
                    "checked": False,
                    "status": f"no_comprobada: end_reason no tipificado ({end_reason!r})",
                }
        elif truncated:
            # Truncación: los no colocados pueden quedar fuera de unpacked o listados;
            # exigimos al menos que no haya IDs inventados (ya comprobado) y que
            # unpacked ⊆ remaining.
            _require(
                all(uid in remaining_ids for uid in unpacked_ids),
                "unpacked en truncación fuera del sufijo",
            )
        properties["unpacked_closure"] = {
            "checked": True,
            "ok": True,
            "n_unpacked": len(unpacked_ids),
            "end_reason": end_reason,
        }

    # AABB contención / no solape (sin fingir orientación ya cubierta arriba)
    from bedbpp_eval import _audit_boxes
    from pilot_problems import prepare_imports

    prepare_imports()
    boxes = [
        {
            "id": row["item_id"],
            "l": float(row["l"]),
            "w": float(row["w"]),
            "h": float(row["h"]),
            "x": float(row["x"]),
            "y": float(row["y"]),
            "z": float(row["z"]),
            "container_id": row.get("container_id", expected_container or "bin"),
            "index": index,
        }
        for index, row in enumerate(placements)
    ]
    orientation_checked = len(placements) > 0
    orientation_ok = True
    if orientation_results and any(not r["checked"] for r in orientation_results):
        orientation_ok = None  # type: ignore[assignment]
    elif orientation_results and any(r.get("ok") is False for r in orientation_results):
        orientation_ok = False
    audit = _audit_boxes(
        boxes,
        bin_lwh=bin_lwh,
        n_order=len(ids),
        orientation_checked=orientation_checked,
        orientation_ok=orientation_ok,
        expected_container_id=expected_container,
        mono_container_overlap=True,
        problem_item_ids=ids,
    )
    _require(audit.get("physical_stability_verified") is None, "estabilidad debe ser null")
    _require(audit.get("containment_valid") is True, "contención falló")
    _require(audit.get("non_overlap_valid") is True, "no-solape falló")
    properties["aabb_containment"] = {"checked": True, "ok": True}
    properties["aabb_non_overlap"] = {"checked": True, "ok": True}
    properties["physical_stability"] = {
        "checked": True,
        "ok": None,
        "value": None,
        "note": "AABB no implica estabilidad física",
    }

    unchecked = [
        key
        for key, value in properties.items()
        if isinstance(value, dict) and value.get("checked") is False
    ]
    return {
        "level": "artifact_contrast",
        "ok": True,
        "audit_performed": True,
        "complete_contrast": len(unchecked) == 0,
        "unchecked_properties": unchecked,
        "properties": properties,
        "containment_valid": True,
        "non_overlap_valid": True,
        "volume_audit": {
            "placed_volume_mm3": placed_volume,
            "bin_volume_mm3": bin_volume,
            "u_geom_from_artifacts": u_geom,
            "reward_sum_stored": reward_sum,
            "match": True,
            "method": "per_step_nominal_volume_and_prefix_identity_contrast",
        },
        "observed_return_kind": (
            "partial"
            if document.get("truncated")
            else (
                "complete_u_geom"
                if document.get("terminated") and transitions
                else "zero_or_empty"
            )
        ),
        "physical_stability_verified": None,
        "note": "AABB no implica estabilidad física",
    }
