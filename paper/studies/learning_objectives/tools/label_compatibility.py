"""Compatibilidad de etiquetas publicadas con el contrato único de S.

Solo lee metadatos e identidades guardadas. No regenera candidatas ni
continúa packing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from candidate_support import SUPPORT_LIMIT, geometric_id_from_mapping


def inspect_labeled_state(state: dict[str, Any]) -> dict[str, Any]:
    alternatives = list(state.get("alternatives") or [])
    actions = [tuple(row["action"]) for row in alternatives]
    greedy = tuple(state.get("greedy_key") or [])
    n_legal = state.get("n_legal")
    problems = []
    if not alternatives:
        problems.append("sin_alternativas")
    if len(alternatives) > SUPPORT_LIMIT:
        problems.append("mas_de_cuatro_alternativas")
    if len(actions) != len(set(actions)):
        problems.append("acciones_duplicadas")
    if greedy and greedy not in actions:
        problems.append("greedy_ausente_en_alternativas")
    if not any(row.get("is_greedy") for row in alternatives):
        problems.append("sin_flag_is_greedy")
    if isinstance(n_legal, int) and n_legal > len(alternatives):
        # El piloto antiguo desplegó sobre la lista completa; ese soporte no
        # puede validarse aquí y es incompatible con desplegar solo en S.
        problems.append("n_legal_mayor_que_alternativas_etiquetadas")
    unknown = [row for row in alternatives if row.get("q_hat") is None]
    if unknown:
        problems.append("q_hat_desconocido")
    return {
        "choice_index": state.get("choice_index"),
        "n_legal": n_legal,
        "n_alternatives": len(alternatives),
        "greedy_in_alternatives": greedy in actions if greedy else False,
        "unique_actions": len(set(actions)),
        "problems": problems,
        "full_legal_list_persisted": False,
        "can_replay_build_candidate_support": False,
    }


def inspect_labels_dir(orders_dir: Path) -> dict[str, Any]:
    order_paths = sorted(orders_dir.glob("*.json"))
    state_reports = []
    problem_counts: dict[str, int] = {}
    for path in order_paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        for state in document.get("states") or []:
            report = inspect_labeled_state(state)
            report["order_id"] = document.get("order_id")
            report["split"] = document.get("split")
            state_reports.append(report)
            for problem in report["problems"]:
                problem_counts[problem] = problem_counts.get(problem, 0) + 1
    reusable = (
        not problem_counts.get("greedy_ausente_en_alternativas")
        and not problem_counts.get("mas_de_cuatro_alternativas")
        and not problem_counts.get("acciones_duplicadas")
        and not problem_counts.get("q_hat_desconocido")
        and problem_counts.get("n_legal_mayor_que_alternativas_etiquetadas", 0) == 0
        and all(item["can_replay_build_candidate_support"] for item in state_reports)
    )
    return {
        "orders": len(order_paths),
        "states": len(state_reports),
        "problem_counts": problem_counts,
        "states_with_n_legal_gt_alternatives": problem_counts.get(
            "n_legal_mayor_que_alternativas_etiquetadas", 0
        ),
        "compatibility": "no_comprobada_para_reutilizacion_bajo_contrato_unico",
        "reusable_under_new_support_contract": reusable,
        "reasons": [
            "Las listas legales completas no están persistidas; no se puede "
            "reproducir build_candidate_support desde metadatos.",
            "Cuando n_legal supera a las alternativas etiquetadas, el piloto "
            "antiguo desplegó fuera de S; eso es incompatible con el contrato "
            "único aunque Greedy esté entre las etiquetas.",
        ],
        "geometric_id_helper": geometric_id_from_mapping.__name__,
    }


def default_counterfactual_labels_report(repo_root: Path) -> dict[str, Any]:
    orders = (
        repo_root
        / "paper"
        / "studies"
        / "counterfactual_ranking"
        / "learning_labels"
        / "orders"
    )
    report = inspect_labels_dir(orders)
    report["source"] = str(orders.relative_to(repo_root))
    return report
