"""Congela el protocolo y calcula su SHA256. No empaqueta."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]


def build_protocol(sample_manifest: dict, code_hashes: dict[str, str]) -> dict:
    return {
        "study": "learning_objectives",
        "status": "frozen",
        "authorizes_full_campaign": False,
        "authorizes_labeling": False,
        "authorizes_training": False,
        "head_at_freeze": "904038ff7f495510f1b8f3d398da3e4eb281a406",
        "branch_at_freeze": "research/paper-online-packing",
        "dataset": sample_manifest["dataset"],
        "dataset_sha256": sample_manifest["dataset_sha256"],
        "support_contract": {
            "name": "greedy_plus_orientation_position_diversity_v1",
            "limit": 4,
            "includes_greedy": True,
            "geometric_id": "(bin_index:int, x:float, y:float, z:float, length:float, width:float, height:float)",
            "numeric_comparison": "float() sobre coordenadas y aristas; igualdad exacta de tuplas tras float()",
            "chebyshev": "max(|dx|,|dy|,|dz|) entre posiciones presentes",
            "diversity_priority": "lexicográfico maximizar (nueva_orientacion, chebyshev_min_a_elegidos, -source_index)",
            "order_in_S": "Greedy primero; demás en orden de selección de diversidad",
            "source_of_truth": "tools/candidate_support.py::build_candidate_support",
            "call_sites": ["pipeline.labeling_select_support", "pipeline.deployment_select_action", "support_api.build_S"],
        },
        "geometry_contract": {
            "sequence": "input_order original",
            "containers": 1,
            "target": "propio del pedido",
            "p": 1,
            "s": 1,
            "orientations": "hasta seis permutaciones según conversion auditada compacta",
            "containment": True,
            "non_overlap": True,
            "max_weight": False,
            "basic_stability": False,
            "load_bearing": False,
            "stop": "primer ítem actual sin candidata legal",
            "U_geom": "volumen orientado colocado / volumen fijo del contenedor",
            "physical_stability_verified": None,
        },
        "q_hat": {
            "definition": "U_geom de continuación Greedy completa tras la acción, con sufijo real solo al etiquetar",
            "not": ["optimo_global", "upper_bound_global", "valor_de_la_politica_aprendida"],
        },
        "logit_tie_break": "mayor score; empate exacto -> menor índice en S",
        "arms": ["classification", "preferences", "return_difference"],
        "losses": {
            "score_sign": "mayor_es_mejor",
            "tie_eps": 1e-9,
            "preference_tie_coefficient": 1.0,
            "state_reduction": "media aritmética con peso uno por estado",
            "classification": "CE natural; masa uniforme sobre máximos empatados de Q_hat; sin temperatura",
            "preferences": "pares i<j; softplus(-(s_high-s_low)) con peso |dQ| renormalizado; empates: media de (si-sj)^2 * 1.0",
            "return_difference": "adaptación Mandi 2022 §4.3 Eq.13; media de ( (sp-sq)-(Qp-Qq) )^2 sobre pares estrictos; 0 si todos empatan",
        },
        "architecture": {
            "encoder": "17 features presentes sin sufijo",
            "mlp": "Linear(17,64)->ReLU->Linear(64,1)",
            "last_layer_init": "cero",
            "seeds": [11, 23, 37],
            "paired_initialization": True,
            "epochs": 40,
            "adam": {
                "lr": 0.001,
                "weight_decay": 1e-4,
                "betas": [0.9, 0.999],
                "eps": 1e-8,
                "amsgrad": False,
                "foreach": False,
                "fused": False,
            },
            "grad_clip": {"max_norm": 1.0, "norm_type": 2.0},
            "checkpoint": "epoch_40",
            "early_stopping": False,
            "seed_selection": False,
            "device": "cpu",
            "torch_num_threads": 1,
            "torch_num_interop_threads": 1,
            "shared_permutations_per_seed": True,
        },
        "normalization": {
            "fit_on": "train_rows_only",
            "row_weight": "equal",
            "scale": "population_std_or_1_if_constant",
            "refit_on_development_or_test": False,
        },
        "samples": {
            "train": {"n": 48, "per_target": 24, "pool": "full.val"},
            "development": {"n": 24, "per_target": 12, "pool": "full.val"},
            "test": {"n": 100, "per_target": 50, "pool": "full.test"},
            "selection_chain_template": sample_manifest["selection_chain_template"],
            "sizes_are_scope_not_power": True,
        },
        "labeling": {
            "states_per_order_max": 4,
            "quantile_rule": "floor(i*(N-1)/(limit-1)+0.5); duplicates dropped without refill",
            "train_max_states": 192,
            "train_max_continuations": 768,
            "development_max_states": 96,
            "development_max_continuations": 384,
            "incomplete_states_kept": True,
            "no_training_on_partial_labels": True,
            "reuse_old_labels": False,
        },
        "metrics": {
            "primary": "mean_i mean_seed (U_pref - U_class)",
            "secondary": [
                "return_difference vs other arms",
                "pref and class vs Greedy",
                "by_target",
                "R_S on labeled states",
                "failures_and_timings",
            ],
            "greedy_once_per_order": True,
            "test_bootstrap": {
                "replicas": 20000,
                "rng": "numpy.random.default_rng(20261005)",
                "unit": "order",
                "stratify_by_target": True,
                "keep_seeds_and_methods_together": True,
                "percentiles": [2.5, 97.5],
                "method": "linear",
            },
        },
        "gates": {
            "operational_before_campaign": [
                "support_inputs_restore_geometry_ok",
                "no_unknown_returns_in_preflight",
                "hashes_verifiable",
                "budget_estimate_compatible_with_uncertainty",
            ],
            "after_training": [
                "nine_complete_models",
                "pairing_checked",
                "data_and_normalization_ok",
                "no_nonfinite_values",
            ],
            "development": {
                "mean_pref_minus_class_ge": 0.005,
                "positive_mean_in_at_least_two_seeds": True,
                "aggregate_nonnegative_per_target": True,
                "complete_audited_evaluation": True,
                "remaining_budget_for_test": True,
                "does_not_require_beating_greedy": True,
                "engineering_gate_not_significance_test": True,
            },
        },
        "budget": {
            "total_wall_seconds": 28800,
            "preflight_wall_seconds": 900,
            "labeling_wall_seconds": 13500,
            "training_wall_seconds": 1800,
            "development_wall_seconds": 3600,
            "test_wall_seconds": 9000,
            "no_automatic_reallocation": True,
            "writing_time_separate": True,
        },
        "code_files": [
            "tools/candidate_support.py",
            "tools/support_api.py",
            "tools/pipeline.py",
            "tools/losses.py",
            "tools/support_metrics.py",
            "tools/quantile_sampling.py",
            "tools/model_spec.py",
            "tools/normalization.py",
            "tools/select_samples.py",
            "tools/preflight.py",
        ],
        "code_hashes": code_hashes,
        "sample_manifest_sha256": None,
    }


def write_protocol(protocol: dict, path: Path) -> str:
    raw = json.dumps(protocol, indent=2, ensure_ascii=False) + "\n"
    # hash without sha field
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    protocol = dict(protocol)
    protocol["sha256"] = digest
    path.write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return digest
