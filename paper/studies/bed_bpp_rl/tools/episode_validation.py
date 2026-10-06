"""Validación estructural común del episodio (R02A).

Usada por escritor, cargador y verificador. Rechaza inconsistencias sin
normalizaciones silenciosas.
"""

from __future__ import annotations

import math
from typing import Any

from corpus_contract import N_ACTIONS, OBS_DIM, RULE_NAMES_EXPECTED, validate_transition

class EpisodeValidationError(ValueError):
    """Entrada de episodio inconsistente."""


def require_strict_int(value: Any, *, name: str, non_negative: bool = False) -> int:
    """Entero estricto: rechaza bool y floats (aunque sean 0.0 / 1.0)."""

    if isinstance(value, bool) or type(value) is not int:
        raise EpisodeValidationError(f"{name} debe ser int estricto, no {type(value).__name__}")
    if non_negative and value < 0:
        raise EpisodeValidationError(f"{name} debe ser >= 0")
    return value


def require_strict_bool(value: Any, *, name: str) -> bool:
    if type(value) is not bool:
        raise EpisodeValidationError(f"{name} debe ser bool estricto")
    return value


def require_action(value: Any) -> int:
    action = require_strict_int(value, name="action")
    if action not in (0, 1, 2):
        raise EpisodeValidationError("action fuera de {0,1,2}")
    return action


def require_decision_budget(value: Any) -> int | None:
    if value is None:
        return None
    return require_strict_int(value, name="decision_budget", non_negative=True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EpisodeValidationError(message)


def validate_rule_proposals(proposals: Any, *, action: int, chosen_geometry: Any) -> list[dict[str, Any]]:
    """Exige tres propuestas completas e identificadas; no acepta ausencia."""

    if not isinstance(proposals, list) or len(proposals) != N_ACTIONS:
        raise EpisodeValidationError(
            "rule_proposals debe ser una lista de exactamente 3 propuestas"
        )
    cleaned: list[dict[str, Any]] = []
    for index, row in enumerate(proposals):
        if not isinstance(row, dict):
            raise EpisodeValidationError(f"rule_proposals[{index}] no es objeto")
        if "action" not in row or "rule" not in row or "geometry" not in row:
            raise EpisodeValidationError(
                f"rule_proposals[{index}] incompleta (exige action, rule, geometry)"
            )
        row_action = require_strict_int(row["action"], name=f"rule_proposals[{index}].action")
        if row_action != index:
            raise EpisodeValidationError(
                f"rule_proposals[{index}].action debe coincidir con el índice ({index})"
            )
        rule = row["rule"]
        if not isinstance(rule, str) or rule != RULE_NAMES_EXPECTED[index]:
            raise EpisodeValidationError(
                f"rule_proposals[{index}].rule debe ser {RULE_NAMES_EXPECTED[index]!r}"
            )
        geometry = row["geometry"]
        if geometry is not None and not isinstance(geometry, (list, tuple)):
            raise EpisodeValidationError(f"rule_proposals[{index}].geometry inválida")
        cleaned.append(
            {
                "rule": rule,
                "action": row_action,
                "candidate_index": row.get("candidate_index"),
                "geometry": list(geometry) if isinstance(geometry, tuple) else geometry,
            }
        )
    expected = cleaned[action].get("geometry")
    chosen = list(chosen_geometry) if isinstance(chosen_geometry, tuple) else chosen_geometry
    if chosen != expected:
        raise EpisodeValidationError(
            "chosen_geometry debe igualar la geometría de la propuesta seleccionada"
        )
    return cleaned


def validate_episode_document(document: Any) -> dict[str, Any]:
    """Validación estructural completa. No muta el argumento; no repara campos."""

    if not isinstance(document, dict):
        raise EpisodeValidationError("el episodio debe ser un objeto")
    kind = document.get("kind")
    _require(
        kind in ("bed_bpp_rl_episode_r02", "bed_bpp_rl_episode_r02a"),
        "kind de episodio no reconocido",
    )
    episode_id = document.get("episode_id")
    if not isinstance(episode_id, str) or not episode_id:
        raise EpisodeValidationError("episode_id inválido")

    transitions_raw = document.get("transitions")
    if not isinstance(transitions_raw, list):
        raise EpisodeValidationError("transitions debe ser una lista")
    n_declared = document.get("n_transitions")
    n_declared = require_strict_int(n_declared, name="n_transitions", non_negative=True)
    _require(n_declared == len(transitions_raw), "n_transitions != len(transitions)")

    terminated = require_strict_bool(document.get("terminated"), name="terminated")
    truncated = require_strict_bool(document.get("truncated"), name="truncated")
    if terminated and truncated:
        raise EpisodeValidationError("documento: terminated y truncated excluyentes")
    if n_declared == 0:
        if not (terminated or truncated):
            raise EpisodeValidationError(
                "cero transiciones exige terminated o truncated en el documento"
            )
    else:
        if not (terminated ^ truncated):
            raise EpisodeValidationError(
                "con transiciones, el documento exige terminated XOR truncated"
            )

    summary = document.get("summary")
    if summary is None:
        summary = {}
    if not isinstance(summary, dict):
        raise EpisodeValidationError("summary debe ser un objeto")
    if "terminated" in summary:
        _require(
            require_strict_bool(summary["terminated"], name="summary.terminated") is terminated,
            "summary.terminated incoherente con documento",
        )
    if "truncated" in summary:
        _require(
            require_strict_bool(summary["truncated"], name="summary.truncated") is truncated,
            "summary.truncated incoherente con documento",
        )
    if n_declared == 0 and terminated:
        _require(
            summary.get("zero_transition_terminal") is True
            or document.get("end_reason") == "no_legal_candidate_on_reset"
            or truncated,
            "cero transiciones terminated sin cierre explícito en summary/end_reason",
        )

    validated_rows: list[dict[str, Any]] = []
    for index, row in enumerate(transitions_raw):
        cleaned = validate_transition(row)
        if cleaned["episode_id"] != episode_id:
            raise EpisodeValidationError(
                f"transitions[{index}].episode_id != document.episode_id"
            )
        if cleaned["step_index"] != index:
            raise EpisodeValidationError(
                f"transitions[{index}].step_index debe ser {index} (consecutivo desde 0)"
            )
        proposals = validate_rule_proposals(
            cleaned.get("rule_proposals"),
            action=cleaned["action"],
            chosen_geometry=cleaned.get("chosen_geometry"),
        )
        cleaned["rule_proposals"] = proposals
        # chosen_geometry normalizado a lista si venía como tupla en propuestas
        cleaned["chosen_geometry"] = proposals[cleaned["action"]]["geometry"]
        validated_rows.append(cleaned)

    for index in range(len(validated_rows) - 1):
        cur = validated_rows[index]
        nxt = validated_rows[index + 1]
        if cur["observation_next"] != nxt["observation"]:
            raise EpisodeValidationError(f"discontinuidad observation en step {index}")
        if cur["action_mask_next"] != nxt["action_mask"]:
            raise EpisodeValidationError(f"discontinuidad action_mask en step {index}")
        if cur["terminated"] or cur["truncated"]:
            raise EpisodeValidationError(f"cierre prematuro en step {index}")
        if cur.get("end_reason") is not None:
            raise EpisodeValidationError("end_reason solo en la última transición")

    if validated_rows:
        last = validated_rows[-1]
        if not (last["terminated"] ^ last["truncated"]):
            raise EpisodeValidationError(
                "última transición: terminated XOR truncated"
            )
        if last["terminated"] is not terminated or last["truncated"] is not truncated:
            raise EpisodeValidationError(
                "última transición incoherente con flags del documento"
            )
        if last.get("end_reason") != document.get("end_reason"):
            raise EpisodeValidationError("end_reason documento vs última transición")
        if last["terminated"]:
            if any(last["action_mask_next"]):
                raise EpisodeValidationError(
                    "en terminación natural, action_mask_next debe ser vacía (todo False)"
                )
        if last["truncated"]:
            if not any(last["action_mask_next"]):
                raise EpisodeValidationError(
                    "en truncación de estado abierto, action_mask_next debe ser utilizable"
                )

    # Devolver vista validada sin mutar el original: copia estructural.
    return {
        "schema_version": document.get("schema_version", 1),
        "kind": kind,
        "episode_id": episode_id,
        "n_transitions": n_declared,
        "terminated": terminated,
        "truncated": truncated,
        "end_reason": document.get("end_reason"),
        "summary": dict(summary),
        "transitions": validated_rows,
        "meta": dict(document.get("meta") or {}),
        "artifacts": document.get("artifacts"),
        "physical_stability_verified": None,
    }


def has_sufficient_artifacts(document: dict[str, Any]) -> bool:
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, dict):
        return False
    bin_lwh = artifacts.get("bin_lwh_mm")
    placements = artifacts.get("placements")
    input_items = artifacts.get("input_items")
    if not isinstance(bin_lwh, (list, tuple)) or len(bin_lwh) != 3:
        return False
    if not isinstance(placements, list):
        return False
    if not isinstance(input_items, list):
        return False
    for value in bin_lwh:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not math.isfinite(float(value)) or float(value) <= 0:
            return False
    return True
