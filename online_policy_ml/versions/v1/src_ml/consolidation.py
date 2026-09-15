"""Paso A: disciplina de consolidación sobre la política ya entrenada.

La Fase 1 mostró que con dos pallets disponibles los motores basados en puntos
extremos reparten la carga casi por mitad en lugar de llenar el primero. La
causa está en la puntuación de candidatas y en que el modelo v1 nunca vio
"pallet vacío con ítems ya colocados" durante el entrenamiento.

Este módulo mide cuánta de esa brecha se cierra **sin reentrenar nada**:
envuelve la política existente en ``ConsolidatingPolicy`` y compara cada brazo
contra su gemelo sin envolver. Mismo checkpoint, mismo encoder v1, mismo bucle,
mismo validador y mismas métricas; lo único que cambia es qué candidatas se
ponen sobre la mesa en cada paso.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from packing_services.algorithms.base import build_solution
from packing_services.algorithms.drl_policy_3d_bpp import METADATA as META_LEARNED
from packing_services.algorithms.online_3d_bpp_heuristic import (
    METADATA as META_GREEDY,
)
from packing_services.benchmark.holdout_offline_online import (
    load_envelope,
    replicate_containers,
)
from packing_services.datasets.bed_bpp import convert_order_to_pack_input
from packing_services.domain.models import AlgorithmConfig, PackingProblem
from packing_services.online.budget import InformationBudget
from packing_services.online.learned.policy import LearnedPlacementPolicy
from packing_services.online.learned.production import (
    CINTA_LOOKAHEAD_P,
    CINTA_MODEL_PATH,
    CINTA_SELECT_S,
    DEFAULT_LOOKAHEAD_P,
    DEFAULT_MODEL_PATH,
    DEFAULT_SELECT_S,
)
from packing_services.online.loop import run_online_loop
from packing_services.online.policies import ConsolidatingPolicy, GreedyBestFitPolicy
from packing_services.online.params import support_threshold
from packing_services.utils.timing import measure_time

from config import SELECTION

# Las tablas de Fase 0 y Fase 1 corrieron los brazos online como PALLETIZATION,
# así que aquí se mantiene para que el brazo "libre" reproduzca exactamente esos
# números y sirva de baseline. No es el 3D_BPP que usa el pipeline de
# entrenamiento; las restricciones resultantes son idénticas en ambos casos.
PROBLEM_TYPE = "PALLETIZATION"


@dataclass(frozen=True)
class OnlineArm:
    """Un brazo del experimento: presupuesto, checkpoint y disciplina."""

    label: str
    lookahead_p: int
    select_s: int
    model_path: str | None = None
    consolidate: bool = False

    @property
    def family(self) -> str:
        return "greedy" if self.model_path is None else "aprendida"

    @property
    def discipline(self) -> str:
        return "consolida" if self.consolidate else "libre"

    @property
    def pair_key(self) -> str:
        """Identifica al gemelo: mismo motor y presupuesto, otra disciplina."""

        return f"{self.family}#p{self.lookahead_p}s{self.select_s}"


# Diseño emparejado: cada brazo libre tiene su gemelo consolidado, de modo que
# la única diferencia entre los dos es la disciplina de contenedor.
# El greedy con lookahead p=3 queda fuera a propósito: en la Fase 0 tardó 95 s
# en un pedido de 26 ítems y más de 22 minutos en uno de 44.
PASO_A_ARMS: tuple[OnlineArm, ...] = (
    OnlineArm("greedy p1s1 libre", DEFAULT_LOOKAHEAD_P, DEFAULT_SELECT_S),
    OnlineArm(
        "greedy p1s1 consolida",
        DEFAULT_LOOKAHEAD_P,
        DEFAULT_SELECT_S,
        consolidate=True,
    ),
    OnlineArm(
        "mlp_p1s1 libre",
        DEFAULT_LOOKAHEAD_P,
        DEFAULT_SELECT_S,
        model_path=DEFAULT_MODEL_PATH,
    ),
    OnlineArm(
        "mlp_p1s1 consolida",
        DEFAULT_LOOKAHEAD_P,
        DEFAULT_SELECT_S,
        model_path=DEFAULT_MODEL_PATH,
        consolidate=True,
    ),
    OnlineArm(
        "mlp_p3s2 libre",
        CINTA_LOOKAHEAD_P,
        CINTA_SELECT_S,
        model_path=CINTA_MODEL_PATH,
    ),
    OnlineArm(
        "mlp_p3s2 consolida",
        CINTA_LOOKAHEAD_P,
        CINTA_SELECT_S,
        model_path=CINTA_MODEL_PATH,
        consolidate=True,
    ),
)


def build_problem(
    orders: dict[str, Any],
    order_id: str,
    arm: OnlineArm,
    *,
    containers: int,
    target: str | None = None,
) -> PackingProblem:
    """Misma entrada BED-BPP que el resto del proyecto, con ``containers`` pallets."""

    parameters: dict[str, Any] = {
        "sort_strategy": "input_order",
        "lookahead_p": arm.lookahead_p,
        "select_s": arm.select_s,
        "selection": SELECTION,
    }
    if arm.model_path:
        parameters["model_path"] = arm.model_path

    payload = convert_order_to_pack_input(
        orders,
        order_id,
        problem_type=PROBLEM_TYPE,
        parameters=parameters,
        request_id=f"pasoA-{order_id}-{arm.label.replace(' ', '_')}",
        target_override=target,
        packing_mode="online",
    )
    replicate_containers(payload, containers)
    algorithm = "drl_policy_3d_bpp" if arm.model_path else "online_3d_bpp_heuristic"
    return PackingProblem(
        problem_type=payload["problem_type"],
        request_id=payload.get("request_id"),
        containers=payload["containers"],
        items=payload["items"],
        constraints=payload["constraints"],
        objective=payload.get("objective", "maximize_volume_utilization"),
        algorithm=AlgorithmConfig(name=algorithm, parameters=parameters),
    )


def run_arm(
    orders: dict[str, Any],
    order_id: str,
    arm: OnlineArm,
    *,
    containers: int = 2,
    target: str | None = None,
) -> dict[str, Any]:
    """Corre un brazo sobre un pedido y devuelve un renglón de la tabla.

    El camino es el mismo que usa el execute de producción: ``run_online_loop``
    para colocar y ``build_solution`` para validar y calcular métricas. Lo
    único añadido es la envolvente de consolidación cuando el brazo la pide.
    """

    problem = build_problem(
        orders, order_id, arm, containers=containers, target=target
    )
    inner = (
        LearnedPlacementPolicy.from_path(arm.model_path)
        if arm.model_path
        else GreedyBestFitPolicy()
    )
    policy = ConsolidatingPolicy(inner) if arm.consolidate else inner

    with measure_time() as elapsed:
        packed, unpacked = run_online_loop(
            problem,
            budget=InformationBudget.from_parameters(problem.algorithm.parameters),
            selection=SELECTION,
            min_support_ratio=support_threshold(
                problem.algorithm.parameters, problem.constraints.basic_stability
            ),
            policy=policy,
        )

    solution = build_solution(
        problem=problem,
        metadata=META_LEARNED if arm.model_path else META_GREEDY,
        packed_items=packed,
        unpacked_items=unpacked,
        execution_time_seconds=elapsed.seconds,
    )
    metrics = solution.metrics
    spread = Counter(p.container_id for p in solution.packed_items)
    return {
        "order_id": order_id,
        "arm": arm.label,
        "family": arm.family,
        "discipline": arm.discipline,
        "pair_key": arm.pair_key,
        "lookahead_p": arm.lookahead_p,
        "select_s": arm.select_s,
        "model_path": arm.model_path,
        "containers_available": containers,
        "n_items": len(problem.items),
        "is_valid": bool(
            solution.validation_report and solution.validation_report.is_valid
        ),
        "constraint_violations": metrics.constraint_violations,
        "volume_utilization": metrics.volume_utilization,
        "items_packed": metrics.items_packed,
        "items_unpacked": metrics.items_unpacked,
        "containers_used": metrics.containers_used,
        "seconds": metrics.execution_time_seconds,
        "spread": dict(sorted(spread.items())),
        **load_envelope(problem, solution),
    }


def run_paso_a(
    orders: dict[str, Any],
    order_ids: list[str],
    *,
    arms: tuple[OnlineArm, ...] = PASO_A_ARMS,
    containers: int = 2,
    target: str | None = None,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    """Recorre pedidos × brazos y devuelve todos los renglones."""

    rows: list[dict[str, Any]] = []
    for order_id in order_ids:
        for arm in arms:
            row = run_arm(
                orders, order_id, arm, containers=containers, target=target
            )
            rows.append(row)
            if verbose:
                print(
                    f"{order_id} · {arm.label:<22} "
                    f"pallets={row['containers_used']} "
                    f"emp={row['items_packed']}/{row['n_items']} "
                    f"util={row['volume_utilization']:.1%} "
                    f"t={row['seconds']:.2f}s",
                    flush=True,
                )
    return rows


def pair_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compara cada brazo libre contra su gemelo consolidado, pedido a pedido.

    Es la lectura que decide el Paso A: si la disciplina no mueve pallets ni
    cubo, el problema no estaba en el espacio de acciones.
    """

    indexed = {(r["order_id"], r["pair_key"], r["discipline"]): r for r in rows}
    deltas: list[dict[str, Any]] = []
    for (order_id, pair_key, discipline), row in indexed.items():
        if discipline != "libre":
            continue
        other = indexed.get((order_id, pair_key, "consolida"))
        if other is None:
            continue
        deltas.append(
            {
                "order_id": order_id,
                "motor": pair_key,
                "n_items": row["n_items"],
                "pallets_libre": row["containers_used"],
                "pallets_consolida": other["containers_used"],
                "pallets_delta": other["containers_used"] - row["containers_used"],
                "util_libre": row["volume_utilization"],
                "util_consolida": other["volume_utilization"],
                "util_delta": other["volume_utilization"] - row["volume_utilization"],
                "fuera_libre": row["items_unpacked"],
                "fuera_consolida": other["items_unpacked"],
                "fuera_delta": other["items_unpacked"] - row["items_unpacked"],
                "valido_libre": row["is_valid"],
                "valido_consolida": other["is_valid"],
                "seg_libre": row["seconds"],
                "seg_consolida": other["seconds"],
            }
        )
    deltas.sort(key=lambda d: (d["motor"], d["order_id"]))
    return deltas
