"""Episodio sintético G1: transición, eventos, J_B (sin reward PPO)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Sequence

from geometry_contract import (
    AABBBox,
    AxisTriple,
    OrientedSizes,
    certificate_realized_safe_if_subseteq_envelope,
    envelope_exceeded,
    geometric_violation,
    validate_margin,
)
from info_separation import (
    EpisodeSpec,
    PolicyObservation,
    RevealedBox,
    SimulatorTruth,
)
from adapters import (
    PolicySessionView,
    build_empty_session,
    capture_equivalence,
    commit_realized,
    rebuild_session_from_revealed,
    revealed_to_aabb,
)

EventCode = Literal[
    "placed",
    "envelope_exceeded",
    "no_candidate",
    "geometric_failure",
    "completed",
    "timeout",
]


@dataclass
class StepRecord:
    item_id: str
    margin_mm: tuple[float, float, float]
    event: EventCode
    envelope_exceeded_flag: bool = False
    flb_mm: tuple[float, float, float] | None = None
    orientation_order: tuple[int, int, int] | None = None
    nominal_oriented: tuple[float, float, float] | None = None
    envelope: tuple[float, float, float] | None = None
    realized_oriented: tuple[float, float, float] | None = None
    certificate: dict[str, object] | None = None
    n_candidates: int = 0


@dataclass
class EpisodeResult:
    termination: EventCode
    steps: list[StepRecord]
    placed_ids: list[str]
    V_nom_mm3: float
    V_nom_before_failure_mm3: float
    container_volume_mm3: float
    J_B: float
    n_envelope_exceeded: int
    geometric_failure: bool
    events: list[str]
    rebuild_ok: bool | None = None
    rebuild_note: str | None = None


MarginFn = Callable[[PolicyObservation], AxisTriple]
ChooserFn = Callable[[PolicyObservation, PolicySessionView], Any]


def fixed_rank_chooser(
    observation: PolicyObservation,
    view: PolicySessionView,
):
    """Chooser fijo: menor rank_key; sin lookahead; sin acceso a realizados ocultos."""
    cands = view.list_envelope_candidates(observation)
    if not cands:
        return None
    return cands[0]


class ProtectionEpisode:
    def __init__(
        self,
        spec: EpisodeSpec,
        *,
        margin_fn: MarginFn,
        chooser: ChooserFn = fixed_rank_chooser,
        use_rebuild_each_step: bool = False,
    ) -> None:
        self.spec = spec
        self.margin_fn = margin_fn
        self.chooser = chooser
        self.use_rebuild_each_step = use_rebuild_each_step
        self._truth = spec.truth()
        self._session = build_empty_session(spec.container_mm)
        self._revealed: list[RevealedBox] = []
        self._index = 0
        self._terminated = False
        self._termination: EventCode | None = None
        self._steps: list[StepRecord] = []
        self._V_nom = 0.0
        self._V_nom_before_failure = 0.0
        self._geom_fail = False
        self._n_env_ex = 0

    def reset(self) -> PolicyObservation:
        self._truth = self.spec.truth()
        self._session = build_empty_session(self.spec.container_mm)
        self._revealed = []
        self._index = 0
        self._terminated = False
        self._termination = None
        self._steps = []
        self._V_nom = 0.0
        self._V_nom_before_failure = 0.0
        self._geom_fail = False
        self._n_env_ex = 0
        return self.observe()

    def observe(self) -> PolicyObservation:
        if self._index >= len(self.spec.items):
            raise RuntimeError("episodio agotado")
        it = self.spec.items[self._index]
        # Separación: no se adjunta SimulatorTruth ni realizados actuales.
        return PolicyObservation(
            container_mm=self.spec.container_mm,
            current_item_id=it.item_id,
            current_nominal_mm=it.nominal_mm,
            margin_mm=AxisTriple(0.0, 0.0, 0.0),  # placeholder; step lo sustituye vía margin_fn
            revealed=tuple(self._revealed),
            remaining_count_including_current=len(self.spec.items) - self._index,
        )

    def _observation_with_margin(self, margin: AxisTriple) -> PolicyObservation:
        base = self.observe()
        return PolicyObservation(
            container_mm=base.container_mm,
            current_item_id=base.current_item_id,
            current_nominal_mm=base.current_nominal_mm,
            margin_mm=margin,
            revealed=base.revealed,
            remaining_count_including_current=base.remaining_count_including_current,
        )

    def step(self) -> StepRecord:
        if self._terminated:
            raise RuntimeError("episodio terminado")
        it = self.spec.items[self._index]
        margin = self.margin_fn(self._observation_with_margin(AxisTriple(0.0, 0.0, 0.0)))
        # Re-validate margin from fn (may ignore observation).
        margin = validate_margin(margin.as_tuple(), "margin")
        obs = self._observation_with_margin(margin)

        if self.use_rebuild_each_step:
            self._session = rebuild_session_from_revealed(
                self.spec.container_mm,
                self._revealed,
                allow_rotation=self.spec.allow_rotation,
            )

        view = PolicySessionView(self._session, allow_rotation=self.spec.allow_rotation)
        # El chooser solo recibe obs + view (sin truth).
        choice = self.chooser(obs, view)
        n_cand = len(view.list_envelope_candidates(obs))

        if choice is None:
            rec = StepRecord(
                item_id=it.item_id,
                margin_mm=margin.as_tuple(),
                event="no_candidate",
                n_candidates=n_cand,
            )
            self._steps.append(rec)
            self._V_nom_before_failure = self._V_nom
            self._terminated = True
            self._termination = "no_candidate"
            return rec

        # Tras fijar pose: el entorno consulta el realizado.
        realized = self._truth.peek_realized(it.item_id)
        sized = OrientedSizes.from_catalogue(
            it.nominal_mm, margin, choice.orientation_order, realized=realized
        )
        assert sized.realized_oriented is not None
        flb = choice.flb_mm
        exceeded = envelope_exceeded(sized.realized_oriented, sized.envelope)
        occupied = revealed_to_aabb(self._revealed)
        real_box = AABBBox(flb, sized.realized_oriented)
        geom = geometric_violation(real_box, self.spec.container_mm, occupied)
        cert = certificate_realized_safe_if_subseteq_envelope(
            flb=flb,
            envelope=sized.envelope,
            realized_oriented=sized.realized_oriented,
            container=self.spec.container_mm,
            occupied_revealed=occupied,
        )

        if geom["geometric_failure"]:
            rec = StepRecord(
                item_id=it.item_id,
                margin_mm=margin.as_tuple(),
                event="geometric_failure",
                envelope_exceeded_flag=exceeded,
                flb_mm=flb,
                orientation_order=choice.orientation_order,
                nominal_oriented=sized.nominal_oriented.as_tuple(),
                envelope=sized.envelope.as_tuple(),
                realized_oriented=sized.realized_oriented.as_tuple(),
                certificate=cert,
                n_candidates=n_cand,
            )
            self._steps.append(rec)
            self._V_nom_before_failure = self._V_nom
            self._geom_fail = True
            self._terminated = True
            self._termination = "geometric_failure"
            if exceeded:
                self._n_env_ex += 1
            return rec

        # Éxito geométrico (con o sin exceso de reserva).
        if exceeded:
            self._n_env_ex += 1
            event: EventCode = "envelope_exceeded"
        else:
            event = "placed"

        revealed = RevealedBox(
            item_id=it.item_id,
            flb_mm=flb,
            realized_oriented_mm=sized.realized_oriented,
            nominal_mm=it.nominal_mm,
            orientation_order=choice.orientation_order,
            envelope_mm=sized.envelope,
            envelope_exceeded=exceeded,
        )
        commit_realized(
            self._session,
            item_id=it.item_id,
            flb_mm=flb,
            realized_oriented=sized.realized_oriented,
            allow_rotation=self.spec.allow_rotation,
        )
        self._revealed.append(revealed)
        self._truth.mark_released(it.item_id)
        self._V_nom += it.nominal_mm.volume
        self._index += 1

        rec = StepRecord(
            item_id=it.item_id,
            margin_mm=margin.as_tuple(),
            event=event,
            envelope_exceeded_flag=exceeded,
            flb_mm=flb,
            orientation_order=choice.orientation_order,
            nominal_oriented=sized.nominal_oriented.as_tuple(),
            envelope=sized.envelope.as_tuple(),
            realized_oriented=sized.realized_oriented.as_tuple(),
            certificate=cert,
            n_candidates=n_cand,
        )
        self._steps.append(rec)

        if self._index >= len(self.spec.items):
            self._terminated = True
            self._termination = "completed"
            self._V_nom_before_failure = self._V_nom
        return rec

    def run(self) -> EpisodeResult:
        self.reset()
        while not self._terminated:
            self.step()
        assert self._termination is not None
        vol_c = self.spec.container_mm.volume
        j_b = 0.0 if self._geom_fail else (self._V_nom / vol_c if vol_c > 0 else 0.0)

        rebuild_ok = None
        rebuild_note = None
        try:
            rebuilt = rebuild_session_from_revealed(
                self.spec.container_mm,
                self._revealed,
                allow_rotation=self.spec.allow_rotation,
            )
            eq = capture_equivalence(rebuilt, self._revealed)
            rebuild_ok = bool(eq.get("matches"))
            if not rebuild_ok:
                rebuild_note = str(eq)
        except Exception as exc:  # noqa: BLE001 — registrar bloqueo
            rebuild_ok = False
            rebuild_note = f"bloqueo_rebuild: {exc}"

        return EpisodeResult(
            termination=self._termination,
            steps=self._steps,
            placed_ids=[r.item_id for r in self._revealed],
            V_nom_mm3=self._V_nom,
            V_nom_before_failure_mm3=self._V_nom_before_failure,
            container_volume_mm3=vol_c,
            J_B=j_b,
            n_envelope_exceeded=self._n_env_ex,
            geometric_failure=self._geom_fail,
            events=[s.event for s in self._steps],
            rebuild_ok=rebuild_ok,
            rebuild_note=rebuild_note,
        )

    def first_decision_signature(self, margin: AxisTriple) -> dict[str, Any]:
        """Firma de la primera decisión sin revelar realizados."""
        self.reset()
        margin = validate_margin(margin.as_tuple(), "margin")
        obs = self._observation_with_margin(margin)
        view = PolicySessionView(self._session, allow_rotation=self.spec.allow_rotation)
        choice = self.chooser(obs, view)
        # Intentar acceso indebido: el chooser no debe necesitar truth.
        if choice is None:
            return {"n_candidates": 0, "choice": None}
        return {
            "n_candidates": len(view.list_envelope_candidates(obs)),
            "choice": {
                "flb_mm": choice.flb_mm,
                "orientation_order": choice.orientation_order,
                "envelope": choice.envelope.as_tuple(),
            },
            "observation_public": obs.to_public_dict(),
        }
