"""Control de integridad del piloto ya ejecutado. No empaqueta ni reentrena."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from model import build_actor
from observation import FEATURE_NAMES
from run_training import EXPECTED_BRANCH, EXPECTED_HEAD, HASHED_FILES, study_hashes
from train_loop import load_actor, logits_of

STUDY = Path(__file__).resolve().parents[1]
PROTOCOL_SHA = "61923d12ef9069cc0bdb95e547b22a89f05fe1db703f80182420bc79350b9c25"
FUTURE_MARKERS = ("remaining", "future", "suffix", "next_item")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tensor_report(initial: dict[str, torch.Tensor], final: dict[str, torch.Tensor]) -> dict[str, Any]:
    keys = sorted(set(initial) | set(final))
    max_abs = 0.0
    identical = True
    for key in keys:
        if key not in initial or key not in final or initial[key].shape != final[key].shape:
            identical = False
            max_abs = None
            break
        delta = float((final[key] - initial[key]).abs().max())
        max_abs = max(max_abs, delta)
        if delta != 0.0:
            identical = False
    return {
        "parameter_names": keys,
        "identical": identical,
        "max_abs_difference": max_abs,
        "initial_last_weight_is_zero": bool(torch.count_nonzero(initial["2.weight"]) == 0),
        "initial_last_bias": [float(value) for value in initial["2.bias"]],
        "final_last_bias": [float(value) for value in final["2.bias"]],
        "initial_deterministic_logits_on_zero_observation": logits_of(
            _actor_from(initial), [0.0] * initial["0.weight"].shape[1]
        ),
    }


def _actor_from(state: dict[str, torch.Tensor]):
    actor = build_actor()
    actor.load_state_dict(state)
    actor.eval()
    return actor


def inspect_training(study: Path = STUDY) -> dict[str, Any]:
    protocol_path = study / "protocol_frozen.json"
    protocol_sha = _sha(protocol_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    hashes = study_hashes(study)
    train = json.loads((study / "train_manifest.json").read_text(encoding="utf-8"))
    development = json.loads((study / "development_manifest.json").read_text(encoding="utf-8"))
    train_ids = {row["order_id"] for rows in train["selected"].values() for row in rows}
    development_ids = {row["order_id"] for rows in development["selected"].values() for row in rows}
    config = json.loads((study / "training" / "training_config.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    if protocol_sha != PROTOCOL_SHA:
        failures.append("el SHA256 del protocolo no coincide")
    if hashes != protocol["code_hashes"]:
        failures.append("el código ya no coincide con el hash congelado")
    if config["code_hashes"] != protocol["code_hashes"]:
        failures.append("la configuración de entrenamiento no usa los hashes congelados")
    if config["protocol_sha256"] != protocol_sha:
        failures.append("el entrenamiento no registró el SHA256 del protocolo")
    if set(FEATURE_NAMES) != set(protocol["observation_features"]):
        failures.append("las entradas de la observación no coinciden con el protocolo")
    if any(any(marker in name for marker in FUTURE_MARKERS) for name in FEATURE_NAMES):
        failures.append("la observación contiene una marca de futuro o de ítems restantes")
    if train_ids & development_ids:
        failures.append("train y desarrollo se solapan")
    if development.get("episodes_executed") or development.get("final_test_selected"):
        failures.append("el manifiesto de desarrollo ya no está sin episodios ni test")
    seeds = []
    tensor_rows = []
    for seed in (101, 102, 103):
        directory = study / "training" / f"seed_{seed}"
        manifest = json.loads((directory / "seed_manifest.json").read_text(encoding="utf-8"))
        lines = [
            json.loads(line)
            for line in (directory / "history.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        updates = [row for row in lines if row.get("kind") == "update"]
        episodes = [row for row in lines if row.get("kind") == "episode"]
        natural = {"sin_candidata", "secuencia_agotada"}
        partials = [row for row in episodes if row.get("termination") == "corte_de_presupuesto"]
        episode_ids = {row["order_id"] for row in episodes}
        initial = torch.load(directory / "checkpoint_initial.pt", map_location="cpu", weights_only=False)
        final = torch.load(directory / "checkpoint_final.pt", map_location="cpu", weights_only=False)
        last = torch.load(directory / "checkpoint_last.pt", map_location="cpu", weights_only=False)
        final_actor = load_actor(directory / "checkpoint_final.pt")
        last_actor = load_actor(directory / "checkpoint_last.pt")
        same_logits = logits_of(final_actor, [0.2] * 36) == logits_of(last_actor, [0.2] * 36)
        observation_fields = sum(1 for row in lines if "observation" in row)
        partial_returns = [
            row for row in partials if any(key in row for key in ("reward_sum", "reward_mean", "return", "u_geom"))
        ]
        checks = {
            "decisions": manifest.get("decisions") == 6144,
            "updates": manifest.get("updates") == 12 and len(updates) == 12,
            "adam_steps": manifest.get("adam_steps") == 192 and all(row.get("adam_steps") == 16 for row in updates),
            "decision_schedule": [row.get("decisions") for row in updates] == [512 * index for index in range(1, 13)],
            "checkpoint_payload": final["payload"].get("updates") == 12 and final["payload"].get("decisions") == 6144,
            "checkpoint_matches_last": same_logits and last["payload"].get("updates") == 12,
            "initial_before_updates": initial["payload"].get("updates") == 0 and initial["payload"].get("decisions") == 0,
            "train_only": episode_ids <= train_ids and not (episode_ids & development_ids),
            "partial_not_natural": len(partials) == 1 and partials[0]["termination"] not in natural,
            "partial_without_return": not partial_returns,
            "no_saved_observations": observation_fields == 0,
        }
        if not all(checks.values()):
            failures.append(f"semilla {seed}: " + ", ".join(key for key, ok in checks.items() if not ok))
        seeds.append(
            {
                "seed": seed,
                "status": manifest.get("status"),
                "checks": checks,
                "partial_episode": partials[0] if partials else None,
                "natural_episodes": sum(1 for row in episodes if row.get("termination") in natural),
                "history_has_observation_vectors": observation_fields,
            }
        )
        tensor_rows.append({"seed": seed, **_tensor_report(initial["actor"], final["actor"])})
    passed = not failures
    return {
        "passed": passed,
        "failures": failures,
        "protocol_sha256": protocol_sha,
        "protocol_sha256_expected": PROTOCOL_SHA,
        "head_expected": EXPECTED_HEAD,
        "branch_expected": EXPECTED_BRANCH,
        "code_hashes_match": hashes == protocol["code_hashes"],
        "hashed_files": list(HASHED_FILES),
        "code_hashes": hashes,
        "observation_features": list(FEATURE_NAMES),
        "future_access_in_feature_names": False,
        "development_ids_in_train": sorted(train_ids & development_ids),
        "on_policy_evidence": "El código congelado descarta el rollout tras cuatro épocas y comprueba que la log_prob antigua no cambia. El historial no guarda esas transiciones.",
        "advantage_evidence": "El código congelado normaliza las ventajas una vez sobre las 512 transiciones, antes de los minibatches de 128. Cada actualización guardada tiene 16 pasos de Adam.",
        "bootstrap_evidence": "Si el rollout corta un episodio, la última transición queda truncada y no terminada, y el retorno usa el valor del estado siguiente. El episodio abierto se registra como corte_de_presupuesto y no trae retorno.",
        "seeds": seeds,
        "policy_change": {
            "observations_saved": False,
            "sufficient_for_probability_or_action_comparison": False,
            "reconstruction_performed": False,
            "reason": "El historial guarda episodios y actualizaciones, no los vectores de observación. La última captura trae acciones de un episodio, sin la observación usada por el actor. No se reconstruye la trayectoria.",
            "kl_or_entropy_threshold_imposed": False,
            "tensors": tensor_rows,
            "proportion_of_decisions_different_from_initial_actor": None,
            "different_rule_versus_different_geometry": None,
        },
    }
