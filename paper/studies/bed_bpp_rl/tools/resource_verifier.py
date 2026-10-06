"""Verificador independiente del recurso BED-BPP-RL (R02).

No valida el retorno únicamente re-sumando los mismos rewards almacenados:
recompone el volumen colocado desde la captura / solución del simulador.
"""

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

from corpus_contract import OBS_DIM, N_ACTIONS, validate_transition  # noqa: E402
from environment import BedBppRlEnv  # noqa: E402
from observation_spec import FEATURE_NAMES  # noqa: E402


class VerificationError(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def verify_episode_document(
    document: dict[str, Any],
    *,
    env: BedBppRlEnv | None = None,
    problem: Any | None = None,
    tol: float = 1e-9,
) -> dict[str, Any]:
    """Comprueba continuidad, máscaras, cierres, geometría y volumen auditado."""

    _require(document.get("kind") == "bed_bpp_rl_episode_r02", "kind inválido")
    transitions = document.get("transitions") or []
    for row in transitions:
        validate_transition(row)

    # Continuidad observation_next[t] == observation[t+1]
    for index in range(len(transitions) - 1):
        cur = transitions[index]
        nxt = transitions[index + 1]
        _require(cur["episode_id"] == nxt["episode_id"], "episode_id inconsistente")
        _require(cur["step_index"] + 1 == nxt["step_index"], "step_index no contiguo")
        _require(
            cur["observation_next"] == nxt["observation"],
            f"discontinuidad obs en step {index}",
        )
        _require(
            cur["action_mask_next"] == nxt["action_mask"],
            f"discontinuidad máscara en step {index}",
        )
        _require(not cur["terminated"] and not cur["truncated"], "cierre prematuro")

    if transitions:
        last = transitions[-1]
        _require(
            last["terminated"] ^ last["truncated"],
            "última transición debe cerrar con terminated XOR truncated",
        )
        _require(
            last.get("end_reason") == document.get("end_reason"),
            "end_reason documento vs última transición",
        )
        for earlier in transitions[:-1]:
            _require(
                earlier.get("end_reason") is None,
                "end_reason solo en la última transición",
            )
            _require(
                earlier["terminated"] is False and earlier["truncated"] is False,
                "cierre prematuro en transición intermedia",
            )

    # Cierre documento
    _require(
        bool(document.get("terminated")) ^ bool(document.get("truncated"))
        or document.get("n_transitions") == 0,
        "documento: terminated XOR truncated (o cero transiciones)",
    )
    if document.get("n_transitions") == 0:
        _require(
            document.get("summary", {}).get("zero_transition_terminal")
            or document.get("truncated")
            or document.get("terminated"),
            "cero transiciones sin resumen de cierre",
        )

    report: dict[str, Any] = {
        "n_transitions": len(transitions),
        "terminated": document.get("terminated"),
        "truncated": document.get("truncated"),
        "end_reason": document.get("end_reason"),
        "continuity_ok": True,
        "masks_ok": True,
        "physical_stability_verified": None,
    }

    # Acciones y máscaras
    for row in transitions:
        _require(0 <= row["action"] < N_ACTIONS, "acción fuera de dominio")
        _require(row["action_mask"][row["action"]] is True, "acción ilegal según máscara")
        _require(len(row["observation"]) == OBS_DIM, "dim observación")
        _require(len(FEATURE_NAMES) == OBS_DIM, "spec features")

    # Identidad del placement: chosen_geometry ∈ propuestas del step
    for row in transitions:
        proposals = row.get("rule_proposals") or []
        action = row["action"]
        if proposals and 0 <= action < len(proposals):
            expected = proposals[action].get("geometry")
            _require(
                row.get("chosen_geometry") == expected,
                "chosen_geometry no coincide con la regla seleccionada",
            )

    # Auditoría geométrica y volumen recompuesto (no re-suma ciega de rewards)
    if env is not None and problem is not None and transitions:
        audit = _audit_capture(env, problem, document, tol=tol)
        report.update(audit)
    elif env is not None and problem is not None and not transitions:
        report["volume_audit"] = {
            "placed_volume_mm3": 0.0,
            "reward_sum_stored": 0.0,
            "u_geom_from_capture": 0.0,
            "match": True,
            "note": "episodio sin placements",
        }
        report["containment_valid"] = True
        report["non_overlap_valid"] = True

    if document.get("truncated"):
        report["observed_return_kind"] = "partial"
        report["note"] = (
            "Retorno parcial observado; no presentar bootstrap estimado como retorno."
        )
    elif document.get("terminated") and transitions:
        report["observed_return_kind"] = "complete_u_geom"
    else:
        report["observed_return_kind"] = "zero_or_empty"

    report["ok"] = True
    return report


def _audit_capture(
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
        description="Auditoría R02",
    )
    kpis = kpis_zhao(problem, solution)
    _require(kpis.get("physical_stability_verified") is None, "estabilidad debe ser null")
    containment = kpis.get("containment_valid")
    non_overlap = kpis.get("non_overlap_valid")
    _require(containment is True, f"contención falló: {containment}")
    _require(non_overlap is True, f"no-solape falló: {non_overlap}")

    dims = problem.containers[0].dimensions
    bin_volume = float(dims.length) * float(dims.width) * float(dims.height)
    placed_volume = 0.0
    for packed in solution.packed_items:
        placed_volume += (
            float(packed.orientation.length)
            * float(packed.orientation.width)
            * float(packed.orientation.height)
        )
    u_geom = placed_volume / bin_volume if bin_volume > 0 else math.nan
    reward_sum = float(sum(row["reward"] for row in document["transitions"]))
    # Independencia: también comparar con volumen de captura, no solo reward_sum
    _require(math.isfinite(u_geom), "U_geom no finita")
    _require(abs(reward_sum - u_geom) <= tol, f"reward_sum={reward_sum} != U_geom={u_geom}")

    if document.get("terminated") and not document.get("truncated"):
        _require(
            abs(reward_sum - float(document["summary"]["reward_sum"])) <= tol,
            "summary.reward_sum inconsistente",
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
            "method": "recompose_packed_AABB_volumes_via_kpis_zhao",
        },
        "physical_stability_verified": None,
    }


def verify_resource_bundle(
    *,
    episode_path: Path,
    manifest_path: Path,
    env: BedBppRlEnv | None = None,
    problem: Any | None = None,
) -> dict[str, Any]:
    import json

    from corpus_loader import load_episode

    document = load_episode(episode_path, manifest_path=manifest_path)
    return verify_episode_document(document, env=env, problem=problem)
