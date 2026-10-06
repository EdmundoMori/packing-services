"""Metadato explícito ``actor_eval_mode`` para capturas futuras (C07/C08).

No modifica ``pilot_problems.py`` ni ``episode_worker.py`` históricos
(hasheados / reutilizados). No reescribe capturas existentes.
No afirma integración en todas las rutas de captura: es helper para uso futuro.

El valor se asigna desde el ejecutor/política, no se infiere del nombre
del método/brazo (el defecto histórico ``method == "actor"`` marcó
``false`` en las 216 capturas de actor de ``learning_development_eval_full``
aunque ``SupportConstrainedActorPolicy`` llama ``model.eval()`` y
``torch.no_grad()``).

Triestado de ``actor_eval_mode`` (C08):
- ``True``: eval observado (``model.training is False``);
- ``False``: training observado (``model.training is True``) o brazo no-actor;
- ``None``: evidencia insuficiente (sin modelo, sin atributo ``training``,
  o tipo no admitido). No usar ``bool(None)``.
"""

from __future__ import annotations

from typing import Any


METADATA_VERSION = "capture_actor_eval_metadata_v1"
SOURCE = "executor_explicit_c07"


def _coerce_training_flag(raw: Any) -> tuple[bool | None, str]:
    """Devuelve (training, nota). Solo acepta bool estrictos.

    No convierte ``None`` con ``bool(None)``. Enteros u otros tipos → desconocido.
    """

    if raw is None:
        return None, "training_attr_missing_or_none"
    if isinstance(raw, bool):
        return raw, "training_attr_bool"
    return None, f"training_attr_unsupported_type:{type(raw).__name__}"


def actor_eval_mode_evidence_from_policy(policy: Any) -> dict[str, Any]:
    """Lee evidencia observable de la política (sin reconstruir forwards)."""

    has_model_attr = hasattr(policy, "model")
    model = getattr(policy, "model", None) if has_model_attr else None
    actor_present = has_model_attr and model is not None

    training: bool | None = None
    training_note = "no_model"
    has_training_attr = False
    if actor_present:
        has_training_attr = hasattr(model, "training")
        if has_training_attr:
            training, training_note = _coerce_training_flag(getattr(model, "training"))
        else:
            training, training_note = None, "model_without_training_attr"

    if training is False:
        eval_mode: bool | None = True
        assignment = "eval_observed"
    elif training is True:
        eval_mode = False
        assignment = "training_observed"
    else:
        eval_mode = None
        assignment = "insufficient_evidence"

    return {
        "policy_class": type(policy).__name__,
        "is_actor_arm": None,
        "actor_model_present": actor_present,
        "has_model_attr": has_model_attr,
        "model_is_none": has_model_attr and model is None,
        "has_training_attr": has_training_attr if actor_present else False,
        "model_training": training,
        "model_training_note": training_note,
        "actor_eval_mode": eval_mode,
        "assignment": assignment,
        "code_path_notes": {
            "SupportConstrainedActorPolicy.__init__": "self.model.eval()",
            "SupportConstrainedActorPolicy.decide": "torch.no_grad() alrededor del forward",
        },
        "does_not_reconstruct_each_historical_forward": True,
        "not_integrated_into_all_capture_paths": True,
        "scope_note": (
            "Helper futuro: distingue ausencia de actor/modelo, estado del "
            "modelo y desconocimiento; no certifica cada forward histórico."
        ),
    }


def attach_actor_eval_mode(
    document: dict[str, Any],
    *,
    actor_eval_mode: bool | None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Asigna ``recipe.actor_eval_mode`` (True / False / None). Mutación in-place.

    ``None`` significa evidencia insuficiente; no se convierte con ``bool()``.
    """

    if actor_eval_mode is not None and not isinstance(actor_eval_mode, bool):
        raise TypeError(
            "actor_eval_mode debe ser True, False o None; "
            f"recibido {type(actor_eval_mode).__name__}"
        )

    recipe = document.setdefault("recipe", {})
    recipe["actor_eval_mode"] = actor_eval_mode
    recipe["actor_eval_mode_source"] = SOURCE
    recipe["actor_eval_mode_metadata_version"] = METADATA_VERSION
    recipe["actor_eval_mode_evidence"] = dict(evidence or {})
    recipe["actor_eval_mode_errata"] = (
        "paper/reviews/errata_actor_eval_mode_learning_development_eval.md"
    )
    return document


def attach_from_policy(
    document: dict[str, Any],
    policy: Any,
    *,
    is_actor_arm: bool,
) -> dict[str, Any]:
    """Brazo no-actor → False; actor → True/False/None según evidencia del modelo."""

    if not is_actor_arm:
        return attach_actor_eval_mode(
            document,
            actor_eval_mode=False,
            evidence={
                "policy_class": type(policy).__name__,
                "is_actor_arm": False,
                "actor_model_present": False,
                "assignment": "non_actor_arm",
                "actor_eval_mode": False,
                "does_not_reconstruct_each_historical_forward": True,
                "not_integrated_into_all_capture_paths": True,
            },
        )
    evidence = actor_eval_mode_evidence_from_policy(policy)
    evidence["is_actor_arm"] = True
    return attach_actor_eval_mode(
        document,
        actor_eval_mode=evidence["actor_eval_mode"],
        evidence=evidence,
    )
