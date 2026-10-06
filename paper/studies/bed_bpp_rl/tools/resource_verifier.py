"""Verificador del recurso: estructural / geométrico / volumen / completo (R02A)."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PAPER_TOOLS = _HERE.parents[2] / "tools"
_ML = _HERE.parents[3] / "online_policy_ml" / "src_ml"
for _entry in (str(_PAPER_TOOLS), str(_ML), str(_HERE)):
    if _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

from corpus_writer import CorpusStore  # noqa: E402
from corpus_loader import load_episode_from_store  # noqa: E402
from episode_validation import (  # noqa: E402
    EpisodeValidationError,
    has_sufficient_artifacts,
    validate_episode_document,
)
from environment import BedBppRlEnv  # noqa: E402


class VerificationError(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def validate_structural(document: dict[str, Any]) -> dict[str, Any]:
    """Solo validación estructural común."""

    validated = validate_episode_document(document)
    return {
        "level": "structural",
        "ok": True,
        "n_transitions": validated["n_transitions"],
        "terminated": validated["terminated"],
        "truncated": validated["truncated"],
        "end_reason": validated.get("end_reason"),
        "physical_stability_verified": None,
        "validated": validated,
    }


def audit_geometry_from_artifacts(document: dict[str, Any]) -> dict[str, Any]:
    """Auditoría AABB desde artefactos persistidos (sin env vivo)."""

    if not has_sufficient_artifacts(document):
        return {
            "level": "geometry",
            "ok": False,
            "audit_performed": False,
            "status": "auditoria_no_realizada",
            "reason": "faltan artifacts independientes suficientes (bin, input_items, placements)",
            "physical_stability_verified": None,
        }

    from bedbpp_eval import _audit_boxes
    from pilot_problems import prepare_imports

    prepare_imports()
    artifacts = document["artifacts"]
    bin_lwh = tuple(float(x) for x in artifacts["bin_lwh_mm"])
    placements = artifacts["placements"]
    input_items = artifacts["input_items"]
    boxes = []
    for index, row in enumerate(placements):
        boxes.append(
            {
                "id": row["item_id"],
                "l": float(row["l"]),
                "w": float(row["w"]),
                "h": float(row["h"]),
                "x": float(row["x"]),
                "y": float(row["y"]),
                "z": float(row["z"]),
                "container_id": row.get("container_id", "bin"),
                "index": index,
            }
        )
    audit = _audit_boxes(
        boxes,
        bin_lwh=bin_lwh,
        n_order=len(input_items),
        orientation_checked=True,
        orientation_ok=True,
        expected_container_id=None,
        mono_container_overlap=True,
        problem_item_ids=None,
    )
    _require(audit.get("physical_stability_verified") is None, "estabilidad debe ser null")
    containment = audit.get("containment_valid")
    non_overlap = audit.get("non_overlap_valid")
    _require(containment is True, f"contención falló: {containment}")
    _require(non_overlap is True, f"no-solape falló: {non_overlap}")
    return {
        "level": "geometry",
        "ok": True,
        "audit_performed": True,
        "containment_valid": True,
        "non_overlap_valid": True,
        "geometry_valid": audit.get("geometry_valid"),
        "physical_stability_verified": None,
        "note": "AABB no implica estabilidad física",
    }


def check_volume_return_from_artifacts(
    document: dict[str, Any], *, tol: float = 1e-9
) -> dict[str, Any]:
    if not has_sufficient_artifacts(document):
        return {
            "level": "volume_return",
            "ok": False,
            "audit_performed": False,
            "status": "auditoria_no_realizada",
            "reason": "faltan artifacts para recomponer volumen",
            "physical_stability_verified": None,
        }
    artifacts = document["artifacts"]
    bin_lwh = [float(x) for x in artifacts["bin_lwh_mm"]]
    bin_volume = bin_lwh[0] * bin_lwh[1] * bin_lwh[2]
    placed_volume = 0.0
    for row in artifacts["placements"]:
        placed_volume += float(row["l"]) * float(row["w"]) * float(row["h"])
    u_geom = placed_volume / bin_volume if bin_volume > 0 else math.nan
    reward_sum = float(sum(row["reward"] for row in document.get("transitions", [])))
    _require(math.isfinite(u_geom), "U_geom no finita")
    _require(abs(reward_sum - u_geom) <= tol, f"reward_sum={reward_sum} != U_geom={u_geom}")

    # Contraste con geometrías elegidas en transiciones (sin re-sumar a ciegas solo).
    if document.get("transitions"):
        geom_volume = 0.0
        for row in document["transitions"]:
            geometry = row.get("chosen_geometry")
            _require(
                isinstance(geometry, (list, tuple)) and len(geometry) >= 7,
                "chosen_geometry insuficiente para volumen",
            )
            # geometry_key: bin_index, x,y,z,l,w,h
            geom_volume += float(geometry[4]) * float(geometry[5]) * float(geometry[6])
        _require(
            abs(geom_volume - placed_volume) <= tol,
            "volumen de placements != volumen de chosen_geometry",
        )

    kind = "partial" if document.get("truncated") else (
        "complete_u_geom" if document.get("terminated") and document.get("transitions") else "zero_or_empty"
    )
    return {
        "level": "volume_return",
        "ok": True,
        "audit_performed": True,
        "observed_return_kind": kind,
        "volume_audit": {
            "placed_volume_mm3": placed_volume,
            "bin_volume_mm3": bin_volume,
            "u_geom_from_artifacts": u_geom,
            "reward_sum_stored": reward_sum,
            "match": True,
            "method": "recompose_AABB_from_persisted_placements_and_geometries",
        },
        "physical_stability_verified": None,
        "note": (
            "Retorno parcial observado en truncación; no presentar bootstrap "
            "estimado como retorno."
            if kind == "partial"
            else None
        ),
    }


def verify_complete_from_artifacts(document: dict[str, Any], *, tol: float = 1e-9) -> dict[str, Any]:
    """Verificación completa solo si hay artefactos suficientes."""

    structural = validate_structural(document)
    if not has_sufficient_artifacts(document):
        return {
            "level": "complete",
            "ok": False,
            "complete_verification": False,
            "status": "auditoria_no_realizada",
            "reason": (
                "sin captura/snapshot independientes suficientes no hay "
                "verificación completa"
            ),
            "structural": structural,
            "physical_stability_verified": None,
        }
    geometry = audit_geometry_from_artifacts(document)
    volume = check_volume_return_from_artifacts(document, tol=tol)
    _require(geometry.get("ok") is True, "falló auditoría geométrica")
    _require(volume.get("ok") is True, "falló comprobación de volumen/retorno")
    return {
        "level": "complete",
        "ok": True,
        "complete_verification": True,
        "structural": {k: v for k, v in structural.items() if k != "validated"},
        "geometry": geometry,
        "volume_return": volume,
        "observed_return_kind": volume.get("observed_return_kind"),
        "physical_stability_verified": None,
    }


def verify_episode_document(
    document: dict[str, Any],
    *,
    env: BedBppRlEnv | None = None,
    problem: Any | None = None,
    tol: float = 1e-9,
    require_complete: bool = False,
) -> dict[str, Any]:
    """API compatible R02: estructural siempre; completa si hay artefacts o env+problem."""

    structural = validate_structural(document)
    report: dict[str, Any] = {
        "n_transitions": structural["n_transitions"],
        "terminated": structural["terminated"],
        "truncated": structural["truncated"],
        "end_reason": structural["end_reason"],
        "continuity_ok": True,
        "masks_ok": True,
        "physical_stability_verified": None,
        "structural_ok": True,
    }
    validated = structural["validated"]

    if has_sufficient_artifacts(validated):
        complete = verify_complete_from_artifacts(validated, tol=tol)
        report.update(
            {
                "ok": complete["ok"],
                "complete_verification": complete.get("complete_verification", False),
                "containment_valid": complete.get("geometry", {}).get("containment_valid"),
                "non_overlap_valid": complete.get("geometry", {}).get("non_overlap_valid"),
                "volume_audit": complete.get("volume_return", {}).get("volume_audit"),
                "observed_return_kind": complete.get("observed_return_kind"),
            }
        )
        if not complete["ok"]:
            raise VerificationError(complete.get("reason") or "verificación completa falló")
        return report

    # Sin artefactos: opcionalmente auditar con env vivo (legado R02).
    if env is not None and problem is not None:
        live = _audit_live(env, problem, validated, tol=tol)
        report.update(live)
        report["ok"] = True
        report["complete_verification"] = True
        report["observed_return_kind"] = live.get("observed_return_kind")
        return report

    report["ok"] = True
    report["complete_verification"] = False
    report["status"] = "auditoria_no_realizada"
    report["note"] = (
        "Validación estructural OK; auditoría geométrica/volumen no realizada "
        "sin artifacts o env+problem."
    )
    if validated.get("truncated"):
        report["observed_return_kind"] = "partial"
    elif validated.get("terminated") and validated.get("transitions"):
        report["observed_return_kind"] = "complete_u_geom_unverified"
    else:
        report["observed_return_kind"] = "zero_or_empty"
    if require_complete:
        raise VerificationError("auditoria_no_realizada: no hay verificación completa")
    return report


def _audit_live(
    env: BedBppRlEnv,
    problem: Any,
    document: dict[str, Any],
    *,
    tol: float,
) -> dict[str, Any]:
    from bedbpp_eval import kpis_zhao
    from pilot_problems import prepare_imports

    prepare_imports()
    solution = env.solution(
        algorithm_name="bed_bpp_rl_verify",
        display_name="BED-BPP-RL verify",
        description="Auditoría R02A live",
    )
    kpis = kpis_zhao(problem, solution)
    _require(kpis.get("physical_stability_verified") is None, "estabilidad debe ser null")
    _require(kpis.get("containment_valid") is True, "contención falló")
    _require(kpis.get("non_overlap_valid") is True, "no-solape falló")
    dims = problem.containers[0].dimensions
    bin_volume = float(dims.length) * float(dims.width) * float(dims.height)
    placed_volume = 0.0
    for packed in solution.packed_items:
        placed_volume += (
            float(packed.orientation.length)
            * float(packed.orientation.width)
            * float(packed.orientation.height)
        )
    u_geom = placed_volume / bin_volume
    reward_sum = float(sum(row["reward"] for row in document["transitions"]))
    _require(abs(reward_sum - u_geom) <= tol, f"reward_sum={reward_sum} != U_geom={u_geom}")
    kind = "partial" if document.get("truncated") else (
        "complete_u_geom" if document.get("terminated") and document["transitions"] else "zero_or_empty"
    )
    return {
        "containment_valid": True,
        "non_overlap_valid": True,
        "geometry_valid": kpis.get("geometry_valid"),
        "volume_audit": {
            "placed_volume_mm3": placed_volume,
            "bin_volume_mm3": bin_volume,
            "u_geom_from_capture": u_geom,
            "reward_sum_stored": reward_sum,
            "match": True,
            "method": "recompose_packed_AABB_volumes_via_kpis_zhao_live",
        },
        "observed_return_kind": kind,
        "physical_stability_verified": None,
    }


def verify_published_episode(
    store: CorpusStore, relpath: str, *, tol: float = 1e-9, require_complete: bool = True
) -> dict[str, Any]:
    """Verifica un episodio publicado solo desde artefactos del corpus."""

    document = load_episode_from_store(store, relpath)
    return verify_episode_document(
        document, tol=tol, require_complete=require_complete
    )


# Alias usados por pruebas R02
def verify_resource_bundle(
    *,
    episode_path: Path,
    manifest_path: Path,
    env: BedBppRlEnv | None = None,
    problem: Any | None = None,
) -> dict[str, Any]:
    from corpus_loader import load_episode

    document = load_episode(episode_path, manifest_path=manifest_path)
    return verify_episode_document(document, env=env, problem=problem)
