"""Evaluador histórico BED-BPP / contraste Zhao (esquema de salida v2).

Contrato de este módulo (no atribuye automáticamente las banderas al paper de Zhao):
comprobaciones locales bajo ``evaluator_contract``. La semántica histórica
(pre-C02) podía marcar ``feasible=true`` sin comprobar solapes y emitir
«supera»/«empata» sin protocolos homologados; ver
``paper/reviews/C02_feasibility_semantics_correction.md``.

``packing_plan_actions`` se conserva sin cambios en esta pasada (C03: yaw).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from packing_services.domain.models import PackingProblem, PackingSolution

EURO_PALLET_MM = (1200.0, 800.0, 2000.0)
_EPS = 1e-6

EVALUATOR_OUTPUT_SCHEMA_VERSION = 2
EVALUATOR_CONTRACT = (
    "bedbpp_eval_v2: AABB axis-aligned; face contact allowed; "
    "geometry_valid ≠ physical feasibility under Zhao/Kagerer; "
    "yaw 0/1 plan ≠ six internal permutations"
)

FEASIBLE_MEANING = (
    "Compatibilidad v2: feasible is True solo si geometry_valid is True "
    "(validez geométrica AABB bajo evaluator_contract: finitos, dims>0, "
    "contención, no solape de volumen con contacto de caras permitido, "
    "identidad, orientación según contrato). "
    "feasible is False si geometry_valid is False. "
    "feasible is None si geometry_valid is None (falta evidencia; null≠false). "
    "No exige all_items_packed. "
    "Quedan fuera: estabilidad física, peso, fragilidad, protocolo Zhao/ICLR "
    "completo, y cualquier restricción no comprobada explícitamente."
)

MIGRATION_NOTE = (
    "schema_version 1→2 (C02): feasible ya no significa «n_fuera==0 y hn≤H»; "
    "aparecen containment_valid, non_overlap_valid, orientation_valid, "
    "identity_valid, geometry_valid, all_items_packed, "
    "physical_stability_verified, comparison_valid; "
    "métricas de planes inválidos van en claves diagnostic_*; "
    "veredicto_zhao no emite superioridad: comparison_valid exige evidencia "
    "de contrato verificable aquí; banderas solas no bastan; KPI sin plan "
    "no autoriza «supera»."
)

MARCO_ZHAO = {
    "paper": (
        "Zhao, Yu, Xu. Learning Efficient Online 3D Bin Packing on "
        "Packing Configuration Trees. ICLR 2022."
    ),
    "problema": "online 3D-BPP; colocación irrevocable; un bin cerrado por episodio",
    "columnas": ["uti", "num"],
    "uti": "volumen de ítems contenidos en el bin / volumen del bin",
    "num": "ítems completamente contenidos en el bin",
    "contencion": "x,y,z ≥ 0 y la caja cabe en L×W×H del bin (aquí 1200×800×2000 mm)",
    "settings": {
        "1": "estabilidad al colocar; |O|=2 (yaw)",
        "2": "solo no-solape y contención; |O|=6 (default del código PCT)",
        "3": "setting 1 + densidad del ítem",
    },
    "prohibido": "copiar Uti./Num. de las tablas ICLR en bins 10×10×10",
    "nota_evaluador": (
        "Las banderas geometry_valid/feasible de este módulo son del contrato "
        f"{EVALUATOR_CONTRACT!r}, no una certificación automática del paper."
    ),
}


def packing_plan_actions(
    problem: PackingProblem, solution: PackingSolution
) -> list[dict[str, Any]]:
    by_id = {item.id: item for item in problem.items}
    actions: list[dict[str, Any]] = []
    for packed in solution.packed_items:
        item = by_id[packed.item_id]
        ori = packed.orientation
        pos = packed.position
        L0, W0, H0 = item.dimensions.length, item.dimensions.width, item.dimensions.height
        rotated = abs(ori.length - L0) > 1e-6 or abs(ori.width - W0) > 1e-6
        actions.append(
            {
                "item": {
                    "id": item.id,
                    "length": L0,
                    "width": W0,
                    "height": H0,
                    "weight": item.weight,
                },
                "orientation": 1 if rotated else 0,
                "flb_coordinates": [pos.x, pos.y, pos.z],
            }
        )
    return actions


# ---------------------------------------------------------------------------
# Geometría local (duplicada a propósito: no importar paper/tools congelados)
# ---------------------------------------------------------------------------


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"campo no numérico: {field}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"campo no finito: {field}")
    return number


def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return min(a1, b1) - max(a0, b0)


def _strict_overlap(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
    *,
    eps: float = _EPS,
) -> bool:
    """Solape de volumen positivo; contacto de caras (overlap==0) permitido."""

    ax, ay, az, al, aw, ah = a
    bx, by, bz, bl, bw, bh = b
    ox = _interval_overlap(ax, ax + al, bx, bx + bl)
    oy = _interval_overlap(ay, ay + aw, by, by + bw)
    oz = _interval_overlap(az, az + ah, bz, bz + bh)
    return ox > eps and oy > eps and oz > eps


def _inside(
    x: float, y: float, z: float, l: float, w: float, h: float, bin_lwh: tuple[float, float, float]
) -> bool:
    L, W, H = bin_lwh
    return (
        x >= -_EPS
        and y >= -_EPS
        and z >= -_EPS
        and x + l <= L + _EPS
        and y + w <= W + _EPS
        and z + h <= H + _EPS
    )


def _is_permutation(oriented: tuple[float, float, float], original: tuple[float, float, float]) -> bool:
    o = sorted(oriented)
    r = sorted(original)
    return all(abs(a - b) <= _EPS for a, b in zip(o, r))


def _oriented_from_yaw01(l0: float, w0: float, h0: float, orientation: int) -> tuple[float, float, float]:
    if orientation == 0:
        return l0, w0, h0
    if orientation == 1:
        return w0, l0, h0
    raise ValueError(f"orientación yaw no representable por 0/1: {orientation!r}")


def _validity_shell() -> dict[str, Any]:
    return {
        "schema_version": EVALUATOR_OUTPUT_SCHEMA_VERSION,
        "evaluator_contract": EVALUATOR_CONTRACT,
        "feasible_meaning": FEASIBLE_MEANING,
        "migration_note": MIGRATION_NOTE,
        "containment_valid": None,
        "non_overlap_valid": None,
        "orientation_valid": None,
        "identity_valid": None,
        "geometry_valid": None,
        "all_items_packed": None,
        "physical_stability_verified": None,
        "comparison_valid": None,
        "feasible": None,
    }


def _validate_bin_lwh(bin_lwh: tuple[float, float, float]) -> tuple[float, float, float]:
    if not isinstance(bin_lwh, (tuple, list)) or len(bin_lwh) != 3:
        raise ValueError("bin_lwh debe ser (L, W, H)")
    out: list[float] = []
    for i, name in enumerate(("L", "W", "H")):
        v = _finite(bin_lwh[i], f"bin_lwh.{name}")
        if v <= 0:
            raise ValueError(f"bin_lwh.{name} debe ser positivo")
        out.append(v)
    return (out[0], out[1], out[2])


def _dims_equal(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> bool:
    return all(abs(x - y) <= _EPS for x, y in zip(a, b))


def _orientation_matches_contract(
    oriented: tuple[float, float, float],
    original: tuple[float, float, float],
    *,
    allow_rotation: bool,
) -> bool:
    """Con rotación prohibida no basta una permutación: debe coincidir el original."""

    if allow_rotation:
        return _is_permutation(oriented, original)
    return _dims_equal(oriented, original)


def _feasible_from_geometry(geometry_valid: bool | None) -> bool | None:
    # Comparación explícita con True/False; no usar bool(geometry_valid).
    if geometry_valid is True:
        return True
    if geometry_valid is False:
        return False
    return None


def _tri_state(ok: bool | None, *, checked: bool) -> bool | None:
    """Propaga null: no convertir None en False vía bool()."""

    if not checked:
        return None
    if ok is True:
        return True
    if ok is False:
        return False
    return None


def _audit_boxes(
    boxes: list[dict[str, Any]],
    *,
    bin_lwh: tuple[float, float, float],
    n_order: int,
    orientation_checked: bool,
    orientation_ok: bool | None,
    unknown_ids: list[str] | None = None,
) -> dict[str, Any]:
    """boxes: id, l, w, h, x, y, z; dimensiones ya orientadas y finitas/positivas."""

    bin_lwh = _validate_bin_lwh(bin_lwh)
    parse_errors = [b for b in boxes if b.get("parse_error")]
    clean = [b for b in boxes if not b.get("parse_error")]
    unknown = sorted(set(unknown_ids or []))

    ids = [b["id"] for b in clean]
    id_counts: dict[str, int] = {}
    for item_id in ids:
        id_counts[item_id] = id_counts.get(item_id, 0) + 1
    duplicate_ids = sorted(i for i, c in id_counts.items() if c > 1)
    identity_valid = len(parse_errors) == 0 and not duplicate_ids and not unknown

    n_fuera = 0
    for b in clean:
        if not _inside(b["x"], b["y"], b["z"], b["l"], b["w"], b["h"], bin_lwh):
            n_fuera += 1
            b["outside_bin"] = True
        else:
            b["outside_bin"] = False
    containment_valid = len(parse_errors) == 0 and n_fuera == 0

    overlap_pairs: list[dict[str, Any]] = []
    for i in range(len(clean)):
        for j in range(i + 1, len(clean)):
            a, b = clean[i], clean[j]
            if a.get("container_id") != b.get("container_id"):
                continue
            aa = (a["x"], a["y"], a["z"], a["l"], a["w"], a["h"])
            bb = (b["x"], b["y"], b["z"], b["l"], b["w"], b["h"])
            if _strict_overlap(aa, bb):
                overlap_pairs.append({"id_i": a["id"], "id_j": b["id"], "i": i, "j": j})
    non_overlap_valid = len(parse_errors) == 0 and len(overlap_pairs) == 0

    orientation_valid = _tri_state(orientation_ok, checked=orientation_checked)

    geometry_valid = (
        len(parse_errors) == 0
        and containment_valid is True
        and non_overlap_valid is True
        and identity_valid is True
        and orientation_valid is not False
    )

    unique_packed = len(set(ids))
    all_items_packed = (
        unique_packed == n_order
        and n_order >= 0
        and len(parse_errors) == 0
        and not duplicate_ids
        and not unknown
    )

    hn_mm = max((b["z"] + b["h"] for b in clean), default=0.0)
    vol_in = 0.0
    num_in = 0
    for b in clean:
        if not b.get("outside_bin"):
            vol_in += b["l"] * b["w"] * b["h"]
            num_in += 1

    return {
        "parse_errors": [{"id": b.get("id"), "error": b.get("parse_error")} for b in parse_errors],
        "duplicate_ids": duplicate_ids,
        "unknown_ids": unknown,
        "n_fuera_bin": n_fuera if len(parse_errors) == 0 else None,
        "n_overlap_pairs": len(overlap_pairs),
        "overlap_pairs": overlap_pairs,
        "containment_valid": containment_valid if len(parse_errors) == 0 else False,
        "non_overlap_valid": non_overlap_valid if len(parse_errors) == 0 else False,
        "orientation_valid": orientation_valid,
        "identity_valid": identity_valid,
        "geometry_valid": geometry_valid,
        "all_items_packed": all_items_packed,
        "physical_stability_verified": None,
        "hn_mm": hn_mm,
        "num_inside": num_in,
        "volume_inside": vol_in,
        "n_placed": len(clean),
        "bin_lwh_mm": list(bin_lwh),
    }


def _metrics_block(
    *,
    audit: dict[str, Any],
    n_order: int,
    bin_lwh: tuple[float, float, float],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    L, W, H = bin_lwh
    bin_volume = L * W * H
    geometry_valid = audit["geometry_valid"]
    vol = float(audit["volume_inside"])
    num = int(audit["num_inside"])
    hn_mm = float(audit["hn_mm"])
    uti_raw = vol / bin_volume if bin_volume > 0 else 0.0

    out = _validity_shell()
    out.update(
        {
            "containment_valid": audit["containment_valid"],
            "non_overlap_valid": audit["non_overlap_valid"],
            "orientation_valid": audit["orientation_valid"],
            "identity_valid": audit["identity_valid"],
            "geometry_valid": geometry_valid,
            "all_items_packed": audit["all_items_packed"],
            "physical_stability_verified": None,
            "comparison_valid": None,
            "feasible": _feasible_from_geometry(geometry_valid),
            "N": n_order,
            "nu": max(0, int(n_order) - int(audit["n_placed"])),
            "num": num if geometry_valid else None,
            "hn_m": round(hn_mm / 1000.0, 6),
            "n_fuera_bin": audit["n_fuera_bin"],
            "n_overlap_pairs": audit["n_overlap_pairs"],
            "duplicate_ids": audit["duplicate_ids"],
            "unknown_ids": audit.get("unknown_ids", []),
            "parse_errors": audit["parse_errors"],
            "bin_volume": round(bin_volume, 6),
            "bin_mm": list(audit.get("bin_lwh_mm") or [L, W, H]),
            "yaw01_is_not_six_permutations": True,
            "orientation_model_note": (
                "PackingSolution usa hasta 6 permutaciones axis-aligned; "
                "packing plan exportado usa solo yaw 0/1 (no equivalentes)."
            ),
        }
    )
    if geometry_valid:
        out["uti"] = round(uti_raw, 6)
        out["packed_volume_in"] = round(vol, 6)
        out["metric_status"] = "validated_geometry"
    else:
        out["uti"] = None
        out["packed_volume_in"] = None
        out["diagnostic_uti"] = round(uti_raw, 6)
        out["diagnostic_packed_volume_in"] = round(vol, 6)
        out["diagnostic_num"] = num
        out["metric_status"] = "diagnostic_only_geometry_invalid_or_incomplete_evidence"
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------------------
# KPIs sobre solución interna / plan / publicación
# ---------------------------------------------------------------------------


def kpis_zhao(
    problem: PackingProblem,
    solution: PackingSolution,
    *,
    bin_lwh: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """KPIs bajo el contrato local del evaluador (no certificación Zhao).

    Contenedor: si ``bin_lwh`` es None se usan las dimensiones de
    ``problem.containers[0]`` (explícitas en la instancia). No se sustituye
    silenciosamente por EURO_PALLET cuando el problema declara otro bin.
    ``EURO_PALLET_MM`` solo aplica si el llamador lo pasa o en helpers de plan
    / publicación con default documentado.

    ``geometry_valid=true`` exige: números finitos, dims > 0, contención AABB,
    sin solapes de volumen (contacto de caras OK), IDs conocidos y únicos, y
    orientación acorde al contrato (si ``allow_rotation`` es falso, debe
    coincidir el original; no basta una permutación). No comprueba estabilidad
    física ni el protocolo ICLR completo.
    """

    if bin_lwh is None:
        container = problem.containers[0]
        resolved = (float(container.length), float(container.width), float(container.height))
        bin_source = "problem.containers[0]"
    else:
        resolved = bin_lwh
        bin_source = "caller_explicit"
    resolved = _validate_bin_lwh(resolved)

    by_id = {item.id: item for item in problem.items}
    n_order = len(problem.items)
    boxes: list[dict[str, Any]] = []
    unknown_ids: list[str] = []
    orientation_ok: bool | None = True
    orientation_checked = False
    allow_rot_global = bool(problem.constraints.allow_rotation)

    for p in solution.packed_items:
        orientation_checked = True
        try:
            l = _finite(p.orientation.length, "orientation.length")
            w = _finite(p.orientation.width, "orientation.width")
            h = _finite(p.orientation.height, "orientation.height")
            x = _finite(p.position.x, "position.x")
            y = _finite(p.position.y, "position.y")
            z = _finite(p.position.z, "position.z")
            if l <= 0 or w <= 0 or h <= 0:
                raise ValueError("dimensiones no positivas")
            item = by_id.get(p.item_id)
            if item is None:
                unknown_ids.append(p.item_id)
                # No se inventan dimensiones originales; la orientación queda
                # sin verificación contra original → fallo de identidad/contrato.
                orientation_ok = False
            else:
                orig = (float(item.length), float(item.width), float(item.height))
                allow_rot = allow_rot_global and item.allowed_orientations != "none"
                if not _orientation_matches_contract(
                    (l, w, h), orig, allow_rotation=allow_rot
                ):
                    orientation_ok = False
            boxes.append(
                {
                    "id": p.item_id,
                    "l": l,
                    "w": w,
                    "h": h,
                    "x": x,
                    "y": y,
                    "z": z,
                    "container_id": p.container_id,
                }
            )
        except ValueError as exc:
            boxes.append(
                {
                    "id": getattr(p, "item_id", None),
                    "parse_error": str(exc),
                    "container_id": getattr(p, "container_id", None),
                }
            )

    n_metrics = int(solution.metrics.items_packed + solution.metrics.items_unpacked)
    if n_metrics > 0:
        n_order = n_metrics

    audit = _audit_boxes(
        boxes,
        bin_lwh=resolved,
        n_order=n_order,
        orientation_checked=orientation_checked,
        orientation_ok=orientation_ok if orientation_checked else None,
        unknown_ids=unknown_ids,
    )

    return _metrics_block(
        audit=audit,
        n_order=n_order,
        bin_lwh=resolved,
        extra={
            "source": "PackingSolution.orientation (hasta 6 permutaciones internas; no flag yaw 0/1)",
            "bin_lwh_source": bin_source,
            "allow_rotation_contract": allow_rot_global,
        },
    )


def kpis_zhao_from_plan(
    actions: list[dict[str, Any]],
    *,
    n_order: int,
    bin_lwh: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """KPIs desde packing plan BED-BPP (FLB + orientation 0/1).

    El flag 0/1 **no** representa las seis permutaciones internas del motor.
    No se repara ni se reinterpreta silenciosamente un plan.
    No se inventan IDs ni dimensiones originales ausentes.

    Si ``bin_lwh`` es None se usa ``EURO_PALLET_MM`` con
    ``bin_lwh_source=default_EURO_PALLET_MM``. Para otro target hay que pasar
    el bin explícitamente.
    """

    if bin_lwh is None:
        resolved = _validate_bin_lwh(EURO_PALLET_MM)
        bin_source = "default_EURO_PALLET_MM"
    else:
        resolved = _validate_bin_lwh(bin_lwh)
        bin_source = "caller_explicit"

    boxes: list[dict[str, Any]] = []
    orientation_ok: bool | None = True
    orientation_checked = len(actions) > 0

    for index, act in enumerate(actions):
        try:
            if not isinstance(act, dict):
                raise ValueError("la acción no es un objeto")
            item = act.get("item")
            if not isinstance(item, dict):
                raise ValueError("falta item")
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("id de ítem ausente o vacío")
            l0 = _finite(item.get("length"), "item.length")
            w0 = _finite(item.get("width"), "item.width")
            h0 = _finite(item.get("height"), "item.height")
            if l0 <= 0 or w0 <= 0 or h0 <= 0:
                raise ValueError("dimensiones no positivas")
            ori_raw = act.get("orientation")
            if isinstance(ori_raw, bool) or not isinstance(ori_raw, int) or ori_raw not in (0, 1):
                orientation_ok = False
                raise ValueError(f"orientación yaw no representable por 0/1: {ori_raw!r}")
            l, w, h = _oriented_from_yaw01(l0, w0, h0, ori_raw)
            flb = act.get("flb_coordinates")
            if not isinstance(flb, (list, tuple)) or len(flb) != 3:
                raise ValueError("flb_coordinates debe tener 3 números")
            x = _finite(flb[0], "flb.x")
            y = _finite(flb[1], "flb.y")
            z = _finite(flb[2], "flb.z")
            boxes.append(
                {
                    "id": item_id,
                    "l": l,
                    "w": w,
                    "h": h,
                    "x": x,
                    "y": y,
                    "z": z,
                    "container_id": "plan",
                    "index": index,
                }
            )
        except ValueError as exc:
            boxes.append(
                {
                    "id": None,
                    "parse_error": str(exc),
                    "container_id": "plan",
                    "index": index,
                }
            )
            if "orientación yaw" in str(exc):
                orientation_ok = False

    audit = _audit_boxes(
        boxes,
        bin_lwh=resolved,
        n_order=n_order,
        orientation_checked=orientation_checked,
        orientation_ok=orientation_ok if orientation_checked else None,
    )
    # Plan vacío: geometría de colocados (ninguno) válida; completitud no.
    if len(actions) == 0:
        audit["containment_valid"] = True
        audit["non_overlap_valid"] = True
        audit["identity_valid"] = True
        audit["orientation_valid"] = None
        audit["geometry_valid"] = True
        audit["all_items_packed"] = n_order == 0
        audit["n_fuera_bin"] = 0
        audit["n_overlap_pairs"] = 0
        audit["volume_inside"] = 0.0
        audit["num_inside"] = 0
        audit["hn_mm"] = 0.0
        audit["n_placed"] = 0
        audit["unknown_ids"] = []
        audit["bin_lwh_mm"] = list(resolved)

    return _metrics_block(
        audit=audit,
        n_order=n_order,
        bin_lwh=resolved,
        extra={
            "source": "packing_plan yaw 0/1",
            "bin_lwh_source": bin_source,
            "orientation_scheme": {
                "0": "length, width, height del item del plan",
                "1": "intercambia length y width; height se conserva",
                "nota": "no equivale a |O|=6 del motor interno",
            },
        },
    )


def is_lfs_pointer(path: Path) -> bool:
    if not path.is_file():
        return True
    head = path.read_bytes()[:64]
    return head.startswith(b"version https://git-lfs")


def load_pct_plan(path: Path) -> dict[str, Any] | None:
    if is_lfs_pointer(path):
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pct_zhao_publicado(
    *,
    n_order: int,
    eta_util: float,
    hn_m: float,
    nu: int = 0,
    bin_lwh: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """PCT sin packing plan: solo magnitudes publicadas.

    ``nu`` informa completitud publicada (dentro de sus límites de evidencia),
    no validez geométrica. ``hn > H`` registra violación del límite de altura
    **impuesto por este evaluador**; no declara inválido el packing bajo el
    protocolo Kagerer. Sin geometría no se afirma contención ni no-solape.
    """

    if bin_lwh is None:
        resolved = _validate_bin_lwh(EURO_PALLET_MM)
        bin_source = "default_EURO_PALLET_MM"
    else:
        resolved = _validate_bin_lwh(bin_lwh)
        bin_source = "caller_explicit"
    L, W, H = resolved
    hn_mm = float(hn_m) * 1000.0
    height_exceeded = hn_mm > H + _EPS
    num_pub = n_order - nu
    v_est = float(eta_util) * L * W * hn_mm
    uti_diag = v_est / (L * W * H) if L * W * H > 0 else 0.0

    # Completitud publicada: nu==0 ⇒ all_items_packed True; no usa bool(None).
    all_packed: bool | None
    if isinstance(nu, bool) or not isinstance(nu, int):
        all_packed = None
    else:
        all_packed = nu == 0

    out = _validity_shell()
    out.update(
        {
            "containment_valid": None,
            "non_overlap_valid": None,
            "orientation_valid": None,
            "identity_valid": None,
            "geometry_valid": None,
            "all_items_packed": all_packed,
            "physical_stability_verified": None,
            "comparison_valid": None,
            "feasible": None,
            "uti": None,
            "num": None,
            "N": n_order,
            "nu": nu,
            "hn_m": hn_m,
            "n_fuera_bin": None,
            "packed_volume_in": None,
            "bin_volume": round(L * W * H, 6),
            "bin_mm": [L, W, H],
            "bin_lwh_source": bin_source,
            "num_publicado": num_pub,
            "eta_util": eta_util,
            "source": "Kagerer IJRR 2023 Table 2 (sin plan LFS)",
            "evaluator_height_limit_mm": H,
            "evaluator_height_limit_exceeded": height_exceeded,
            "metric_status": "published_scalars_without_plan",
            "diagnostic_uti_if_eta_hn_mapped_to_bin": round(uti_diag, 6),
            "estimated_volume_from_eta_hn": {
                "value_mm3": v_est,
                "formula": "eta_util * L * W * (hn_m*1000)",
                "estimated": True,
                "subject_to_published_rounding": True,
                "assumptions": [
                    "eta_util y hn son los publicados",
                    "ortoedro L×W×hn como en el juez de contexto",
                    "no implica contención en H ni ausencia de solapes",
                ],
            },
            "nota": (
                (
                    f"hn={hn_m} m supera el límite de altura H={H/1000:.3f} m "
                    "impuesto por este evaluador. Eso no invalida por sí solo el "
                    "packing bajo el protocolo Kagerer; sin plan no hay "
                    "geometry_valid."
                )
                if height_exceeded
                else (
                    f"hn={hn_m} m ≤ H={H/1000:.3f} m del evaluador no prueba "
                    "contención lateral completa ni no-solape; geometry_valid=null."
                )
            ),
            "yaw01_is_not_six_permutations": True,
        }
    )
    return out


def _both_geometry_validated(nuestro: dict[str, Any], pct: dict[str, Any]) -> bool:
    return nuestro.get("geometry_valid") is True and pct.get("geometry_valid") is True


def _validated_uti(row: dict[str, Any]) -> float | None:
    if row.get("geometry_valid") is not True:
        return None
    if row.get("metric_status") != "validated_geometry":
        return None
    uti = row.get("uti")
    if uti is None:
        return None
    return float(uti)


def comparison_evidence_requirements() -> dict[str, Any]:
    """Evidencia exigida para ``comparison_valid=true`` (no por defecto).

    Este módulo **no** puede verificar por sí solo secuencia/observabilidad,
    terminación del episodio original ni el protocolo ICLR a partir de dos
    dicts KPI. Por tanto ``veredicto_zhao`` deja ``comparison_valid=false``
    y no emite superioridad científica aunque se pasen banderas.
    """

    return {
        "required_contract_fields": [
            "container_lwh_mm",
            "item_sequence_observability",
            "orientation_model",
            "active_constraints",
            "termination_rule",
            "metric_definitions",
            "both_plans_geometry_validated",
        ],
        "verifiable_here": [
            "geometry_valid is True en ambos lados (comprobable en los KPI)",
            "uti con metric_status=validated_geometry en ambos",
            "bin_mm coherente si se declara container_lwh_mm",
        ],
        "not_verifiable_from_kpi_dicts_alone": [
            "identidad de secuencia / observabilidad del online packing",
            "terminación del episodio original",
            "restricciones activas en la corrida fuente",
            "equivalencia con el protocolo Zhao ICLR",
        ],
        "flags_insufficient": (
            "protocols_homologated=True o shared_metric_contract no vacío "
            "no bastan por sí solos; no autorizan comparison_valid."
        ),
        "published_without_plan": (
            "geometry_valid is not True (p. ej. pct_zhao_publicado) impide "
            "comparison_valid y cualquier «supera»."
        ),
        "default": "comparison_valid=false; lado=no_compara; sin «supera»/«empata»/«inferior»",
    }


def tabla_comparacion(nuestro: dict[str, Any], pct: dict[str, Any]) -> dict[str, Any]:
    """Tabla descriptiva; no autoriza por sí sola un veredicto de superioridad."""

    uti_n = _validated_uti(nuestro)
    uti_p = _validated_uti(pct)
    uti_ambos = uti_n is not None and uti_p is not None
    geom_ambos = _both_geometry_validated(nuestro, pct)

    filas = [
        {
            "columna": "tarea / pedido / bin",
            "nuestro": "O3DBP-1-1, pedido bajo contrato interno, 1200×800×2000 mm",
            "pct": "magnitudes publicadas y/o plan bajo su fuente",
            "comparable": True,
            "decide": False,
        },
        {
            "columna": "geometry_valid (contrato evaluador)",
            "nuestro": nuestro.get("geometry_valid"),
            "pct": pct.get("geometry_valid"),
            "comparable": True,
            "decide": False,
            "nota": "no es certificación automática del protocolo Zhao",
        },
        {
            "columna": "feasible (compatibilidad → geometry_valid)",
            "nuestro": nuestro.get("feasible"),
            "pct": pct.get("feasible"),
            "comparable": True,
            "decide": False,
            "nota": FEASIBLE_MEANING,
        },
        {
            "columna": "Uti. validada (V_dentro / V_bin)",
            "nuestro": uti_n,
            "pct": uti_p,
            "comparable": uti_ambos,
            "decide": False,
            "nota": None if uti_ambos else "falta uti validada en al menos un lado",
        },
        {
            "columna": "Uti. diagnóstica / estimada",
            "nuestro": nuestro.get("diagnostic_uti"),
            "pct": pct.get("diagnostic_uti_if_eta_hn_mapped_to_bin")
            or pct.get("uti_si_se_ignora_contencion"),
            "comparable": False,
            "decide": False,
            "nota": "no promocionar a métrica de comparación",
        },
        {
            "columna": "ηutil Kagerer",
            "nuestro": nuestro.get("eta_util"),
            "pct": pct.get("eta_util"),
            "comparable": True,
            "decide": False,
            "nota": "contexto; no es Uti. del paper",
        },
        {
            "columna": "hn (m)",
            "nuestro": nuestro.get("hn_m"),
            "pct": pct.get("hn_m"),
            "comparable": True,
            "decide": False,
        },
        {
            "columna": "evaluator_height_limit_exceeded (solo PCT publicado)",
            "nuestro": None,
            "pct": pct.get("evaluator_height_limit_exceeded"),
            "comparable": pct.get("evaluator_height_limit_exceeded") is not None,
            "decide": False,
            "nota": "límite H de este evaluador; no invalida Kagerer",
        },
    ]
    return {
        "schema_version": EVALUATOR_OUTPUT_SCHEMA_VERSION,
        "filas": filas,
        "columna_decisoria": None,
        "uti_head_to_head": uti_ambos and geom_ambos,
        "comparison_valid": False,
        "comparison_evidence_requirements": comparison_evidence_requirements(),
        "alcance": (
            "descripción bajo contrato interno del evaluador; "
            "no es reproducción automática de Zhao ni ranking BED-BPP"
        ),
    }


def veredicto_zhao(
    nuestro: dict[str, Any],
    pct: dict[str, Any],
    *,
    protocols_homologated: bool = False,
    shared_metric_contract: str | None = None,
    homologation_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Veredicto acotado. No emite superioridad científica desde este módulo.

    ``comparison_valid`` permanece False: la secuencia/observabilidad, la
    terminación y la equivalencia ICLR/Zhao no son comprobables aquí a partir
    de dicts KPI. ``protocols_homologated=True`` o un ``shared_metric_contract``
    no bastan. Un KPI publicado sin plan (``geometry_valid is not True``) nunca
    autoriza «supera».

    Si ambos lados tienen uti validada, se expone solo
    ``internal_uti_delta_diagnostic`` (informativo, no veredicto).
    """

    req = comparison_evidence_requirements()
    blocking: list[str] = [
        "secuencia/observabilidad, terminación y restricciones del episodio "
        "original no verificables desde KPI en este módulo"
    ]
    if protocols_homologated is True or (
        isinstance(shared_metric_contract, str) and shared_metric_contract.strip() != ""
    ):
        blocking.append(
            "flags protocols_homologated/shared_metric_contract insuficientes por sí solos"
        )
    if homologation_evidence is not None:
        blocking.append(
            "homologation_evidence aportada no puede validarse completamente aquí; "
            "no se promociona a comparison_valid"
        )
    if nuestro.get("geometry_valid") is not True:
        blocking.append("nuestro.geometry_valid is not True")
    if pct.get("geometry_valid") is not True:
        blocking.append("pct.geometry_valid is not True")

    uti_n = _validated_uti(nuestro)
    uti_p = _validated_uti(pct)
    delta = None
    if uti_n is not None and uti_p is not None:
        delta = float(uti_n) - float(uti_p)

    return {
        "schema_version": EVALUATOR_OUTPUT_SCHEMA_VERSION,
        "lado": "no_compara",
        "detalle": (
            "Comparación homologada no establecida. "
            + "; ".join(blocking)
            + ". No se emite supera/empata/inferior."
        ),
        "frase": (
            "Este evaluador no declara comparación ICLR/Zhao ni superioridad "
            "frente a PCT a partir de KPIs internos o publicados. "
            "comparison_valid=false. Un delta de uti validada, si existe, es "
            "solo diagnóstico interno."
        ),
        "comparison_valid": False,
        "internal_uti_delta_diagnostic": delta,
        "comparison_evidence_requirements": req,
        "blocking_reasons": blocking,
        "flags_attempted": {
            "protocols_homologated": protocols_homologated is True,
            "shared_metric_contract": shared_metric_contract,
            "homologation_evidence_provided": homologation_evidence is not None,
        },
    }


def kpis_kagerer(problem: PackingProblem, solution: PackingSolution) -> dict[str, Any]:
    """ηutil / hn / νu como el juez de bed-bpp-env sin Blender (contexto, no veredicto Zhao)."""

    packed = list(solution.packed_items)
    n = int(solution.metrics.items_packed + solution.metrics.items_unpacked)
    nu = int(solution.metrics.items_unpacked)
    if not packed:
        return {
            "N": n,
            "nu": nu,
            "eta_util": 0.0,
            "hn_m": 0.0,
            "Asupp": None,
            "rinterl": None,
            "stable": None,
            "items_packed": 0,
        }

    by_cid = {c.id: c for c in problem.containers}
    tops: dict[str, float] = {}
    vol = 0.0
    for p in packed:
        l, w, h = p.orientation.length, p.orientation.width, p.orientation.height
        vol += l * w * h
        top = p.position.z + h
        tops[p.container_id] = max(tops.get(p.container_id, 0.0), top)

    cuboid = 0.0
    for cid, top in tops.items():
        container = by_cid.get(cid) or problem.containers[0]
        cuboid += float(container.length) * float(container.width) * max(top, 1e-9)

    hn_mm = max(tops.values())
    return {
        "N": n,
        "nu": nu,
        "eta_util": round(vol / cuboid, 6),
        "hn_m": round(hn_mm / 1000.0, 6),
        "Asupp": None,
        "rinterl": None,
        "stable": None,
        "items_packed": len(packed),
    }
