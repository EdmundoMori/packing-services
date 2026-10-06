"""Metadato explícito ``actor_eval_mode`` para capturas futuras (C07).

No modifica ``pilot_problems.py`` ni ``episode_worker.py`` históricos
(hasheados / reutilizados). No reescribe capturas existentes.

El valor se asigna desde el ejecutor/política, no se infiere del nombre
del método/brazo (el defecto histórico ``method == "actor"`` marcó
``false`` en las 216 capturas de actor de ``learning_development_eval_full``
aunque ``SupportConstrainedActorPolicy`` llama ``model.eval()`` y
``torch.no_grad()``).
"""

from __future__ import annotations

from typing import Any


METADATA_VERSION = "capture_actor_eval_metadata_v1"
SOURCE = "executor_explicit_c07"


def actor_eval_mode_evidence_from_policy(policy: Any) -> dict[str, Any]:
    """Lee evidencia observable de la política cargada (sin reconstruir forwards)."""

    model = getattr(policy, "model", None)
    training: bool | None
    if model is None:
        training = None
    else:
        training = bool(getattr(model, "training", True))
    return {
        "policy_class": type(policy).__name__,
        "has_model_attr": model is not None,
        "model_training": training,
        "model_eval_mode_inferred": (training is False) if training is not None else None,
        "code_path_notes": {
            "SupportConstrainedActorPolicy.__init__": "self.model.eval()",
            "SupportConstrainedActorPolicy.decide": "torch.no_grad() alrededor del forward",
        },
        "does_not_reconstruct_each_historical_forward": True,
    }


def attach_actor_eval_mode(
    document: dict[str, Any],
    *,
    actor_eval_mode: bool,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Asigna ``recipe.actor_eval_mode`` de forma explícita (mutación in-place).

    Devuelve el mismo dict. No altera capturas ya escritas en disco.
    """

    recipe = document.setdefault("recipe", {})
    recipe["actor_eval_mode"] = bool(actor_eval_mode)
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
    """Conveniencia: brazo greedy → False; actor → ``not model.training`` si hay modelo."""

    if not is_actor_arm:
        return attach_actor_eval_mode(
            document,
            actor_eval_mode=False,
            evidence={
                "policy_class": type(policy).__name__,
                "is_actor_arm": False,
                "does_not_reconstruct_each_historical_forward": True,
            },
        )
    evidence = actor_eval_mode_evidence_from_policy(policy)
    evidence["is_actor_arm"] = True
    mode = evidence.get("model_eval_mode_inferred")
    if mode is None:
        # Política actor sin atributo model: no afirmar eval; dejar False y documentar.
        return attach_actor_eval_mode(
            document,
            actor_eval_mode=False,
            evidence={**evidence, "assignment": "false_without_model_attr"},
        )
    return attach_actor_eval_mode(
        document,
        actor_eval_mode=bool(mode),
        evidence={**evidence, "assignment": "from_model.training"},
    )
