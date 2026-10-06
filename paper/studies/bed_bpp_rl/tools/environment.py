"""Entorno BED-BPP-RL (R02): interfaz reset/step/close con terminated y truncated.

Adapta la semántica de selección de reglas sin modificar
``rl_rule_selection/tools/environment.py`` (histórico).
"""

from __future__ import annotations

import math
import sys
import time
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_STUDY = _HERE.parent
_RULE_TOOLS = _STUDY.parent / "rl_rule_selection" / "tools"
_PAPER_TOOLS = _STUDY.parents[1] / "tools"
for _entry in (str(_PAPER_TOOLS), str(_RULE_TOOLS), str(_HERE)):
    if _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

from compact_study import (  # noqa: E402
    COMPACT_FLAGS,
    SUFFIX_REASON,
    TERMINAL_REASON,
    prepare_imports,
)
from observation_spec import OBS_DIM, RULE_NAMES, encode_observation  # noqa: E402
from rules import current_max_height, propose_rules, redundancy  # noqa: E402

ENGINE_MODULE = "src/packing_services/algorithms/_extreme_points.py"
ENGINE_REQUIRED_COMMIT = "a5fb46879c7bfbe16400eec2ab985dd23bf30385"
ENVIRONMENT_VERSION = "bed_bpp_rl_env_r02_v1+ep_c04"


class EnvironmentClosedError(RuntimeError):
    """step tras terminated/truncated o entorno sin reset activo."""


class InvalidActionError(ValueError):
    """Acción fuera de {0,1,2}."""


@dataclass
class EpisodeSummary:
    """Resumen explícito del episodio (incl. cero transiciones)."""

    n_transitions: int = 0
    n_placements: int = 0
    reward_sum: float = 0.0
    terminated: bool = False
    truncated: bool = False
    end_reason: str | None = None
    zero_transition_terminal: bool = False
    physical_stability_verified: None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_transitions": self.n_transitions,
            "n_placements": self.n_placements,
            "reward_sum": self.reward_sum,
            "terminated": self.terminated,
            "truncated": self.truncated,
            "end_reason": self.end_reason,
            "zero_transition_terminal": self.zero_transition_terminal,
            "physical_stability_verified": None,
            "notes": list(self.notes),
        }


class BedBppRlEnv:
    """Interfaz pública: reset, step, close, truncate_budget.

    ``step`` → ``(observation, reward, terminated, truncated, info)``.
    """

    def __init__(self) -> None:
        self.problem: Any = None
        self.session: Any = None
        self._mask: Any = None
        self._constraints: Any = None
        self._remaining: list[Any] = []
        self._unpacked: list[Any] = []
        self._rewards: list[float] = []
        self._decisions: list[dict[str, Any]] = []
        self._terminated = True
        self._truncated = False
        self._bin_volume = 0.0
        self._closed_sessions: list[weakref.ReferenceType] = []
        self._cached: tuple[str, list[Any]] | None = None
        self.candidate_seconds = 0.0
        self.candidate_generations = 0
        self._decision_budget: int | None = None
        self._decisions_taken = 0
        self.summary = EpisodeSummary()
        self._last_info: dict[str, Any] = {}
        self._last_observation: list[float] = [0.0] * OBS_DIM

    def close(self) -> None:
        if self.session is not None:
            self._closed_sessions.append(weakref.ref(self.session))
        self.session = None
        self._mask = None
        self._remaining = []
        self.problem = None
        self._cached = None
        self._terminated = True

    def released_sessions(self) -> int:
        return sum(ref() is None for ref in self._closed_sessions)

    def reset(
        self,
        problem: Any,
        *,
        decision_budget: int | None = None,
    ) -> tuple[list[float], dict[str, Any]]:
        self.close()
        self._assert_contract(problem)
        prepare_imports()
        from packing_services.algorithms._constructive import order_items
        from packing_services.domain.enums import SortStrategy
        from packing_services.online.mask import ValidatorMask
        from packing_services.online.params import resolve_selection, support_threshold
        from packing_services.online.session import ExtremePointOnlineSession

        self.problem = problem
        self._constraints = problem.constraints
        params = dict(problem.algorithm.parameters)
        container = problem.containers[0]
        dims = container.dimensions
        self._bin_volume = float(dims.length) * float(dims.width) * float(dims.height)
        if not math.isfinite(self._bin_volume) or self._bin_volume <= 0:
            raise ValueError("volumen del bin inválido")
        self.session = ExtremePointOnlineSession(
            problem.containers,
            selection=resolve_selection(params),
        )
        self._mask = ValidatorMask(
            problem,
            min_support_ratio=support_threshold(params, self._constraints.basic_stability),
        )
        self._remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)
        self._unpacked = []
        self._rewards = []
        self._decisions = []
        self._terminated = False
        self._truncated = False
        self._cached = None
        self.candidate_seconds = 0.0
        self.candidate_generations = 0
        self._decision_budget = decision_budget
        self._decisions_taken = 0
        self.summary = EpisodeSummary()

        observation, info = self._view(action=None, reward=0.0, placed=False)
        if self._remaining and not self._legal(self._remaining[0]):
            self._stop_current(end_reason="no_legal_candidate_on_reset")
            observation, info = self._view(action=None, reward=0.0, placed=False)
            self.summary.terminated = True
            self.summary.end_reason = "no_legal_candidate_on_reset"
            self.summary.zero_transition_terminal = True
            self.summary.notes.append(
                "Primer ítem sin candidata: episodio terminado con cero transiciones; "
                "no se inventa acción ni reward."
            )
            info["episode_summary"] = self.summary.as_dict()
        self._last_observation = list(observation)
        self._last_info = info
        return observation, info

    def step(
        self, action: int
    ) -> tuple[list[float], float, bool, bool, dict[str, Any]]:
        if self._terminated or self._truncated:
            raise EnvironmentClosedError(
                "step rechazado: el episodio ya está terminado o truncado"
            )
        if self.session is None or self.problem is None:
            raise EnvironmentClosedError("step sin reset activo")
        if action not in (0, 1, 2):
            raise InvalidActionError("la acción debe ser 0, 1 o 2")

        # Límite de presupuesto: si queda 0 decisiones permitidas y el episodio
        # sigue abierto → truncar sin fabricar transición (solo si aún no se actuó
        # en este step). El presupuesto cuenta decisiones ya tomadas.
        if (
            self._decision_budget is not None
            and self._decisions_taken >= self._decision_budget
        ):
            return self._apply_truncation(end_reason="budget_decision_cut")

        current = self._remaining[0]
        options = self._legal(current)
        proposals = propose_rules(options, self.session)
        if not options:
            # No debería alcanzarse tras auto-terminación post-placement; defensa.
            self._stop_current(end_reason="no_legal_candidate")
            observation, info = self._view(action=action, reward=0.0, placed=False)
            self._finalize_terminated("no_legal_candidate")
            info["episode_summary"] = self.summary.as_dict()
            self._last_observation = list(observation)
            self._last_info = info
            return observation, 0.0, True, False, info

        chosen = proposals[action]["option"]
        candidate = chosen.candidate
        placed_volume = (
            float(candidate.dimensions.length)
            * float(candidate.dimensions.width)
            * float(candidate.dimensions.height)
        )
        reward = placed_volume / self._bin_volume
        if not math.isfinite(reward):
            raise RuntimeError("recompensa no finita")
        self.session.commit(candidate, chosen.item)
        self._cached = None
        self._rewards.append(reward)
        self._remaining = self._remaining[1:]
        self._decisions.append(
            {
                "action": action,
                "rule": proposals[action]["rule"],
                "redundancy": redundancy(proposals),
                "n_candidates": len(options),
                "geometry": proposals[action]["geometry"],
            }
        )
        self._decisions_taken += 1
        self.summary.n_placements += 1
        self.summary.n_transitions += 1
        self.summary.reward_sum += reward

        # Auto-terminación si no queda secuencia o el siguiente ítem es imposible.
        natural_end: str | None = None
        if not self._remaining:
            self._terminated = True
            natural_end = "all_items_placed"
        elif not self._legal(self._remaining[0]):
            self._stop_current(end_reason="no_legal_candidate_after_placement")
            natural_end = "no_legal_candidate_after_placement"

        # Si el límite coincide con terminación natural, prioridad a terminated.
        hit_budget = (
            self._decision_budget is not None
            and self._decisions_taken >= self._decision_budget
            and not self._terminated
        )
        truncated = False
        if natural_end is not None:
            self._finalize_terminated(natural_end)
            observation, info = self._view(action=action, reward=reward, placed=True)
        elif hit_budget:
            # Vista bootstrap con episodio aún abierto (máscara real utilizable).
            observation, info = self._view(action=action, reward=reward, placed=True)
            truncated = True
            self._truncated = True
            self.summary.truncated = True
            self.summary.end_reason = "budget_decision_cut"
            self.summary.notes.append(
                "Truncación con episodio abierto; observation/mask siguiente "
                "conservadas para bootstrap; no se inventa retorno completo."
            )
            info["truncated"] = True
            info["end_reason"] = "budget_decision_cut"
            info["bootstrap_observation"] = list(observation)
            info["bootstrap_action_mask"] = list(info["action_mask"])
        else:
            observation, info = self._view(action=action, reward=reward, placed=True)

        info["episode_summary"] = self.summary.as_dict()
        self._last_observation = list(observation)
        self._last_info = info
        return observation, reward, self._terminated, truncated, info

    def truncate_budget(self, *, end_reason: str = "budget_wall_cut") -> dict[str, Any]:
        """Corta el episodio abierto sin inventar transición si no hubo acciones."""

        if self._terminated or self._truncated:
            raise EnvironmentClosedError("truncate sobre episodio ya cerrado")
        if self._decisions_taken == 0:
            self._truncated = True
            self.summary.truncated = True
            self.summary.end_reason = end_reason
            self.summary.zero_transition_terminal = False
            self.summary.notes.append(
                "Corte de presupuesto sin ninguna acción: resumen sin transición fabricada."
            )
            observation, info = self._view(action=None, reward=0.0, placed=False)
            info["truncated"] = True
            info["end_reason"] = end_reason
            info["episode_summary"] = self.summary.as_dict()
            info["fabricated_transition"] = False
            self._last_observation = list(observation)
            self._last_info = info
            return info
        observation, _reward, _term, trunc, info = self._apply_truncation(end_reason=end_reason)
        del observation, trunc
        return info

    def geometric_utilization(self) -> float:
        return float(sum(self._rewards))

    def solution(self, *, algorithm_name: str, display_name: str, description: str) -> Any:
        prepare_imports()
        from packing_services.algorithms.base import build_solution
        from packing_services.algorithms.online_3d_bpp_heuristic import METADATA

        metadata = METADATA.model_copy(
            update={
                "name": algorithm_name,
                "display_name": display_name,
                "description": description,
            }
        )
        return build_solution(
            problem=self.problem,
            metadata=metadata,
            packed_items=list(self.session.packed),
            unpacked_items=list(self._unpacked),
            execution_time_seconds=0.0,
        )

    def capture(
        self,
        *,
        order_id: str,
        orders_path: Path,
        orders_sha256: str,
        description: str = "Episodio BED-BPP-RL (R02).",
    ) -> dict[str, Any]:
        from pilot_problems import capture_document

        document = capture_document(
            self.problem,
            self.solution(
                algorithm_name="bed_bpp_rl",
                display_name="BED-BPP-RL",
                description=description,
            ),
            method="bed_bpp_rl",
            order_id=order_id,
            orders_path=orders_path,
            orders_sha256=orders_sha256,
            checkpoint_path=orders_path,
        )
        document["physical_stability_verified"] = None
        document["reward_sum"] = self.geometric_utilization()
        document["decisions"] = list(self._decisions)
        document["episode_summary"] = self.summary.as_dict()
        document["environment_version"] = ENVIRONMENT_VERSION
        document["engine_module"] = ENGINE_MODULE
        document["engine_required_commit"] = ENGINE_REQUIRED_COMMIT
        return document

    def _apply_truncation(
        self, *, end_reason: str
    ) -> tuple[list[float], float, bool, bool, dict[str, Any]]:
        # Observación/máscara del estado abierto antes de marcar truncación.
        observation, info = self._view(action=None, reward=0.0, placed=False)
        self._truncated = True
        self.summary.truncated = True
        self.summary.end_reason = end_reason
        info["truncated"] = True
        info["terminated"] = False
        info["end_reason"] = end_reason
        info["bootstrap_observation"] = list(observation)
        info["bootstrap_action_mask"] = list(info["action_mask"])
        info["episode_summary"] = self.summary.as_dict()
        info["fabricated_transition"] = False
        self._last_observation = list(observation)
        self._last_info = info
        # No nueva transición: el llamador (corpus) debe marcar truncated en la
        # última transición ya registrada, o exportar solo resumen si n=0.
        return observation, 0.0, False, True, info

    def _finalize_terminated(self, end_reason: str) -> None:
        self._terminated = True
        self.summary.terminated = True
        self.summary.end_reason = end_reason

    def _assert_contract(self, problem: Any) -> None:
        observed = {key: getattr(problem.constraints, key) for key in COMPACT_FLAGS}
        if observed != COMPACT_FLAGS:
            raise ValueError("las restricciones no son las del contrato compacto")
        params = dict(problem.algorithm.parameters)
        if int(params.get("lookahead_p")) != 1 or int(params.get("select_s")) != 1:
            raise ValueError("el contrato exige p=1 y s=1")
        if params.get("sort_strategy") != "input_order":
            raise ValueError("el contrato exige la secuencia original")
        if len(problem.containers) != 1:
            raise ValueError("el contrato exige un contenedor")

    def _legal(self, item: Any) -> list[Any]:
        if self._cached is not None and self._cached[0] == item.id:
            return self._cached[1]
        prepare_imports()
        from packing_services.online.types import StepOption

        started = time.perf_counter()
        options = []
        for candidate in self.session.candidates(item, self._constraints):
            if self._mask.allows(candidate, item, self.session, self._constraints):
                options.append(StepOption(item=item, candidate=candidate, buffer_index=0))
        self.candidate_seconds += time.perf_counter() - started
        self.candidate_generations += 1
        self._cached = (item.id, options)
        return options

    def _stop_current(self, *, end_reason: str) -> None:
        prepare_imports()
        from packing_services.domain.models import UnpackedItem

        del end_reason  # registrado en summary por el llamador
        current = self._remaining[0]
        self._unpacked.append(UnpackedItem(item_id=current.id, reason=TERMINAL_REASON))
        for pending in self._remaining[1:]:
            self._unpacked.append(UnpackedItem(item_id=pending.id, reason=SUFFIX_REASON))
        self._remaining = []
        self._terminated = True
        self._cached = None

    def _action_mask(self, proposals: list[dict[str, Any]]) -> list[bool]:
        if self._terminated or self._truncated:
            return [False, False, False]
        # Identidades de regla siempre seleccionables si hay candidatas legales.
        if any(row.get("option") is not None for row in proposals):
            return [True, True, True]
        return [False, False, False]

    def _view(
        self, *, action: int | None, reward: float, placed: bool
    ) -> tuple[list[float], dict[str, Any]]:
        if self._terminated or not self._remaining:
            proposals = propose_rules([], self.session)
            observation = encode_observation(
                container=self.problem.containers[0],
                item=None,
                session=self.session,
                proposals=proposals,
                skyline=current_max_height(self.session),
                orientations=[],
            )
        else:
            current = self._remaining[0]
            options = self._legal(current)
            proposals = propose_rules(options, self.session)
            observation = encode_observation(
                container=self.problem.containers[0],
                item=current,
                session=self.session,
                proposals=proposals,
                skyline=current_max_height(self.session),
                orientations=self.session.orientations_for(current, self._constraints),
            )
        mask = self._action_mask(proposals)
        info = {
            "terminated": self._terminated,
            "truncated": self._truncated,
            "action": action,
            "reward": reward,
            "placed": placed,
            "action_mask": mask,
            "decision_redundancy": self._decisions[-1]["redundancy"] if self._decisions else None,
            "redundancy": redundancy(proposals),
            "proposals": [
                {
                    "rule": row["rule"],
                    "action": row["action"],
                    "candidate_index": row["candidate_index"],
                    "geometry": row["geometry"],
                }
                for row in proposals
            ],
            "physical_stability_verified": None,
            "environment_version": ENVIRONMENT_VERSION,
            "rules": list(RULE_NAMES),
            "end_reason": self.summary.end_reason,
        }
        return observation, info
