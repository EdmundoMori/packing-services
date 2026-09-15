"""Comparación vs PCT en el protocolo de Zhao et al., ICLR 2022.

Condiciones del paper (Table 1): online 3D-BPP, un bin cerrado, Uti. =
volumen empacado *dentro del bin* / volumen del bin, Num. = ítems
completamente contenidos. Una pila con hn > altura del bin no es solución
factible de ese problema.

Kagerer IJRR 2023 es cómo se *corrió* el código de PCT en BED-BPP (O3DBP,
europalé). El xkpi (ηutil, hn) documenta el packing publicado; no sustituye
Uti./Num. ni admite overflow como si fuera Zhao.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packing_services.domain.models import PackingProblem, PackingSolution

EURO_PALLET_MM = (1200.0, 800.0, 2000.0)
_EPS = 1e-6

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


def _inside(x: float, y: float, z: float, l: float, w: float, h: float, bin_lwh: tuple[float, float, float]) -> bool:
    L, W, H = bin_lwh
    return (
        x >= -_EPS
        and y >= -_EPS
        and z >= -_EPS
        and x + l <= L + _EPS
        and y + w <= W + _EPS
        and z + h <= H + _EPS
    )


def kpis_zhao(
    problem: PackingProblem,
    solution: PackingSolution,
    *,
    bin_lwh: tuple[float, float, float] = EURO_PALLET_MM,
) -> dict[str, Any]:
    """Uti. y Num. de Zhao Table 1 con contención del bin cerrado."""

    L, W, H = bin_lwh
    bin_volume = L * W * H
    vol = 0.0
    num = 0
    hn_mm = 0.0
    n_fuera = 0
    for p in solution.packed_items:
        l, w, h = p.orientation.length, p.orientation.width, p.orientation.height
        x, y, z = p.position.x, p.position.y, p.position.z
        hn_mm = max(hn_mm, z + h)
        if _inside(x, y, z, l, w, h, bin_lwh):
            vol += l * w * h
            num += 1
        else:
            n_fuera += 1
    n = int(solution.metrics.items_packed + solution.metrics.items_unpacked)
    feasible = n_fuera == 0 and hn_mm <= H + _EPS
    uti = vol / bin_volume if bin_volume > 0 else 0.0
    return {
        "uti": round(uti, 6),
        "num": num,
        "N": n,
        "nu": n - num,
        "hn_m": round(hn_mm / 1000.0, 6),
        "feasible": feasible,
        "n_fuera_bin": n_fuera,
        "packed_volume_in": round(vol, 6),
        "bin_volume": round(bin_volume, 6),
        "bin_mm": [L, W, H],
    }


def kpis_zhao_from_plan(
    actions: list[dict[str, Any]],
    *,
    n_order: int,
    bin_lwh: tuple[float, float, float] = EURO_PALLET_MM,
) -> dict[str, Any]:
    """Uti./Num. Zhao a partir de un packing plan BED-BPP (FLB + orientation 0/1)."""

    L, W, H = bin_lwh
    bin_volume = L * W * H
    vol = 0.0
    num = 0
    hn_mm = 0.0
    n_fuera = 0
    for act in actions:
        item = act["item"]
        l0, w0, h0 = float(item["length"]), float(item["width"]), float(item["height"])
        if int(act.get("orientation") or 0) == 1:
            l, w, h = w0, l0, h0
        else:
            l, w, h = l0, w0, h0
        x, y, z = (float(v) for v in act["flb_coordinates"])
        hn_mm = max(hn_mm, z + h)
        if _inside(x, y, z, l, w, h, bin_lwh):
            vol += l * w * h
            num += 1
        else:
            n_fuera += 1
    feasible = n_fuera == 0 and hn_mm <= H + _EPS
    uti = vol / bin_volume if bin_volume > 0 else 0.0
    return {
        "uti": round(uti, 6) if actions else 0.0,
        "num": num,
        "N": n_order,
        "nu": n_order - num,
        "hn_m": round(hn_mm / 1000.0, 6) if actions else 0.0,
        "feasible": feasible,
        "n_fuera_bin": n_fuera,
        "packed_volume_in": round(vol, 6),
        "bin_volume": round(bin_volume, 6),
        "bin_mm": [L, W, H],
    }


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
    bin_lwh: tuple[float, float, float] = EURO_PALLET_MM,
) -> dict[str, Any]:
    """PCT sin packing plan: solo lo publicado. hn > H ⇒ no factible en Zhao."""

    L, W, H = bin_lwh
    hn_mm = hn_m * 1000.0
    feasible = hn_mm <= H + _EPS and nu == 0
    num_pub = n_order - nu
    v_est = eta_util * L * W * hn_mm
    uti_si_overflow = v_est / (L * W * H) if L * W * H > 0 else 0.0
    return {
        "uti": round(uti_si_overflow, 6) if feasible else None,
        "num": num_pub if feasible else None,
        "N": n_order,
        "nu": nu,
        "hn_m": hn_m,
        "feasible": feasible,
        "n_fuera_bin": None if not feasible else 0,
        "uti_si_se_ignora_contencion": round(uti_si_overflow, 6),
        "num_publicado": num_pub,
        "eta_util": eta_util,
        "source": "Kagerer IJRR 2023 Table 2 (sin plan LFS)",
        "bin_mm": [L, W, H],
        "nota": (
            None
            if feasible
            else (
                f"hn={hn_m} m > {H/1000:.3f} m: el packing publicado no cumple "
                "la contención del bin cerrado de Zhao. Uti./Num. Zhao no se "
                "asignan a una solución fuera de bin."
            )
        ),
    }


def tabla_comparacion(nuestro: dict[str, Any], pct: dict[str, Any]) -> dict[str, Any]:
    """Qué se puede comparar con el JSON del 09 (antes del veredicto)."""

    uti_ambos = nuestro.get("uti") is not None and pct.get("uti") is not None
    filas = [
        {
            "columna": "tarea / pedido / bin",
            "nuestro": "O3DBP-1-1, 00100408, 1200×800×2000 mm",
            "pct": "O3DBP, 00100408, europalé (Kagerer corrió PCT aquí)",
            "comparable": True,
            "decide": False,
        },
        {
            "columna": "feasible (contención Zhao)",
            "nuestro": nuestro.get("feasible"),
            "pct": pct.get("feasible"),
            "comparable": True,
            "decide": True,
            "nota": "en Zhao una caja fuera del bin no es solución Table 1",
        },
        {
            "columna": "Uti. Zhao (V_dentro / V_bin)",
            "nuestro": nuestro.get("uti"),
            "pct": pct.get("uti"),
            "comparable": uti_ambos,
            "decide": bool(uti_ambos and nuestro.get("feasible") and pct.get("feasible")),
            "nota": None if uti_ambos else "PCT sin Uti. en bin cerrado (plan LFS o hn>2 m)",
        },
        {
            "columna": "Num. Zhao (ítems dentro)",
            "nuestro": nuestro.get("num"),
            "pct": pct.get("num"),
            "comparable": uti_ambos,
            "decide": False,
        },
        {
            "columna": "Uti. si se ignora contención",
            "nuestro": nuestro.get("uti"),
            "pct": pct.get("uti_si_se_ignora_contencion"),
            "comparable": True,
            "decide": False,
            "nota": "mismo volumen de 26 ítems ≈ empate; no es Zhao",
        },
        {
            "columna": "ηutil Kagerer",
            "nuestro": nuestro.get("eta_util"),
            "pct": pct.get("eta_util"),
            "comparable": True,
            "decide": False,
            "nota": "ortoedro A×hn; no es Uti. del paper",
        },
        {
            "columna": "hn (m)",
            "nuestro": nuestro.get("hn_m"),
            "pct": pct.get("hn_m"),
            "comparable": True,
            "decide": False,
        },
    ]
    return {
        "filas": filas,
        "columna_decisoria": "feasible",
        "uti_head_to_head": uti_ambos,
        "alcance": "un pedido; no ranking BED-BPP; no tablas ICLR 10×10×10",
    }


def veredicto_zhao(nuestro: dict[str, Any], pct: dict[str, Any]) -> dict[str, Any]:
    """Supera / empata / inferior en el problema de Zhao (bin cerrado, Uti. luego Num.)."""

    nf, pf = bool(nuestro.get("feasible")), bool(pct.get("feasible"))
    if nf and not pf:
        lado = "supera"
        detalle = (
            "nuestra solución es factible en el bin 1200×800×2000 mm; "
            "la de PCT publicada no (hn > 2 m). En el protocolo Zhao una "
            "colocación fuera del bin no es solución."
        )
    elif pf and not nf:
        lado = "es inferior a"
        detalle = "PCT es factible en el bin cerrado y la nuestra no."
    elif nf and pf:
        du = float(nuestro["uti"]) - float(pct["uti"])
        if abs(du) < 5e-7:
            dn = int(nuestro["num"]) - int(pct["num"])
            if dn > 0:
                lado, detalle = "supera", f"Uti. empate ({nuestro['uti']}); mayor Num. ({nuestro['num']} vs {pct['num']})."
            elif dn < 0:
                lado, detalle = "es inferior a", f"Uti. empate ({nuestro['uti']}); menor Num. ({nuestro['num']} vs {pct['num']})."
            else:
                lado, detalle = "empata con", f"Uti.={nuestro['uti']} y Num.={nuestro['num']} iguales."
        elif du > 0:
            lado, detalle = "supera", f"Uti. {nuestro['uti']} vs {pct['uti']} (Δ={du:+.6f})."
        else:
            lado, detalle = "es inferior a", f"Uti. {nuestro['uti']} vs {pct['uti']} (Δ={du:+.6f})."
    else:
        lado = "no compara"
        detalle = "ningún lado es factible en el bin cerrado."

    frase = (
        f"En el pedido homologado, O3DBP p=1 s=1, bin 1200×800×2000 mm "
        f"(Zhao ICLR 2022: Uti./Num., contención), `mlp_v1_p1s1_ppo.pt` "
        f"{lado} PCT. {detalle} No es ranking sobre BED-BPP ni Σalgo."
    )
    return {"lado": lado, "detalle": detalle, "frase": frase}


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
