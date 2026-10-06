"""Verificador del recurso: estructural / contraste de artefactos / completo (R03)."""

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

from artifact_contrast import ArtifactContrastError, contrast_artifacts  # noqa: E402
from corpus_writer import CorpusStore  # noqa: E402
from corpus_loader import load_episode_from_store  # noqa: E402
from episode_validation import (  # noqa: E402
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


def audit_geometry_from_artifacts(document: dict[str, Any], *, tol: float = 1e-9) -> dict[str, Any]:
    """Auditoría geométrica + identidad/orientación (sin valores prefijados)."""

    try:
        return contrast_artifacts(document, tol=tol)
    except ArtifactContrastError as exc:
        raise VerificationError(str(exc)) from exc


def check_volume_return_from_artifacts(
    document: dict[str, Any], *, tol: float = 1e-9
) -> dict[str, Any]:
    """Compatibilidad: el contraste completo ya cubre volumen por paso y acumulado."""

    report = audit_geometry_from_artifacts(document, tol=tol)
    if not report.get("audit_performed"):
        return {
            "level": "volume_return",
            "ok": False,
            "audit_performed": False,
            "status": report.get("status"),
            "reason": report.get("reason"),
            "physical_stability_verified": None,
        }
    volume = report.get("volume_audit") or {}
    return {
        "level": "volume_return",
        "ok": True,
        "audit_performed": True,
        "observed_return_kind": report.get("observed_return_kind"),
        "volume_audit": volume,
        "physical_stability_verified": None,
        "note": report.get("note"),
    }


def verify_complete_from_artifacts(document: dict[str, Any], *, tol: float = 1e-9) -> dict[str, Any]:
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
    try:
        contrast = contrast_artifacts(document, tol=tol)
    except ArtifactContrastError as exc:
        raise VerificationError(str(exc)) from exc
    _require(contrast.get("ok") is True, "falló contraste de artefactos")
    return {
        "level": "complete",
        "ok": True,
        "complete_verification": True,
        "complete_contrast": contrast.get("complete_contrast"),
        "unchecked_properties": contrast.get("unchecked_properties"),
        "structural": {k: v for k, v in structural.items() if k != "validated"},
        "geometry": contrast,
        "volume_return": {
            "level": "volume_return",
            "ok": True,
            "observed_return_kind": contrast.get("observed_return_kind"),
            "volume_audit": contrast.get("volume_audit"),
        },
        "observed_return_kind": contrast.get("observed_return_kind"),
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
                "complete_contrast": complete.get("complete_contrast"),
                "unchecked_properties": complete.get("unchecked_properties"),
                "containment_valid": complete.get("geometry", {}).get("containment_valid"),
                "non_overlap_valid": complete.get("geometry", {}).get("non_overlap_valid"),
                "volume_audit": complete.get("volume_return", {}).get("volume_audit"),
                "observed_return_kind": complete.get("observed_return_kind"),
                "artifact_properties": complete.get("geometry", {}).get("properties"),
            }
        )
        if not complete["ok"]:
            raise VerificationError(complete.get("reason") or "verificación completa falló")
        return report

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
        "Validación estructural OK; contraste de artefactos no realizado "
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
        description="Auditoría R03 live",
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
    document = load_episode_from_store(store, relpath)
    return verify_episode_document(
        document, tol=tol, require_complete=require_complete
    )


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
