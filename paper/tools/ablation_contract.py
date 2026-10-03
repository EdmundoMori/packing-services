"""Lee el protocolo y el congelado del paso 10. No abre pickle ni entrena."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from freeze_normalization_sample import frozen_list_sha256
from normalization_features import FEATURE_NAMES, stats_sha256
from pilot_common import REPO_ROOT

RESEARCH_FORMAT = "packing-services-research-normalization-ablation"
PRODUCTION_FORMAT = "packing-services-online-policy"
ARMS = ("raw", "normalized")
EXPECTED_SEEDS = [42, 43, 44, 45, 46]
CODE_FILES = (
    "paper/tools/ablation_contract.py",
    "paper/tools/ablation_train.py",
    "paper/tools/ablation_pack.py",
    "paper/tools/ablation_aggregate.py",
    "paper/tools/run_normalization_ablation.py",
    "paper/tools/normalization_features.py",
)


class AblationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_sha256(root: Path | None = None) -> dict[str, str]:
    base = root or REPO_ROOT
    return {relative: sha256_file(base / relative) for relative in CODE_FILES}


def _load_json(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise AblationError(f"no está el archivo {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AblationError(f"{resolved} no es un objeto JSON")
    return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AblationError(message)


def hyperparameters_from_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    block = protocol["hyperparameters"]
    explicit = block["explicit_notebook_03"]
    defaults = block["fit_mlp_defaults_not_passed"]
    optimizer = block["optimizer"]
    threads = block["threads"]["shared_control"]
    _require(explicit["hidden_size"] == 64, "hidden_size distinto del protocolo")
    _require(explicit["epochs"] == 10, "epochs distinto del protocolo")
    _require(explicit["lr"] == 0.001, "lr distinto del protocolo")
    _require(defaults["clip_grad"] == 1.0, "clip_grad distinto del protocolo")
    _require(defaults["weight_decay"] == 0.0001, "weight_decay distinto del protocolo")
    _require(defaults["select_best"] == "val_loss", "la selección no es val_loss")
    _require(defaults["keep_epochs"] is False, "keep_epochs distinto del protocolo")
    _require(defaults["require_informative"] is True, "require_informative distinto del protocolo")
    _require(defaults["require_val"] is True, "require_val distinto del protocolo")
    _require(block["seeds"] == EXPECTED_SEEDS, "las semillas no son 42, 43, 44, 45 y 46")
    _require(optimizer["betas"] == [0.9, 0.999], "betas de Adam distintas del protocolo")
    _require(optimizer["eps"] == 1e-8, "eps de Adam distinto del protocolo")
    _require(optimizer["amsgrad"] is False, "amsgrad distinto del protocolo")
    _require(threads["torch.set_num_threads"] == 1, "el número de hilos no es 1")
    _require(threads["torch.set_num_interop_threads"] == 1, "los hilos de interoperación no son 1")
    _require("best_seed" not in block, "el protocolo no admite elegir la mejor semilla")
    return {
        "hidden_size": 64,
        "epochs": 10,
        "lr": 0.001,
        "weight_decay": 0.0001,
        "clip_grad": 1.0,
        "select_best": "val_loss",
        "keep_epochs": False,
        "require_informative": True,
        "require_val": True,
        "seeds": list(EXPECTED_SEEDS),
        "betas": (0.9, 0.999),
        "eps": 1e-8,
        "amsgrad": False,
        "num_threads": 1,
        "num_interop_threads": 1,
    }


def _encoder_names() -> tuple[str, ...]:
    from pilot_problems import prepare_imports

    prepare_imports()
    from packing_services.online.features import FEATURE_NAMES as encoder_names

    return tuple(encoder_names)


def load_contract(protocol_path: Path, freeze_path: Path) -> dict[str, Any]:
    protocol_file = protocol_path.expanduser().resolve()
    freeze_file = freeze_path.expanduser().resolve()
    protocol = _load_json(protocol_file)
    freeze = _load_json(freeze_file)
    _require(protocol.get("training_executed") is False, "el protocolo figura como entrenado")
    _require(protocol.get("packing_executed") is False, "el protocolo figura como empaquetado")
    _require(freeze.get("training_executed") is False, "el congelado figura como entrenado")
    _require(freeze.get("packing_executed") is False, "el congelado figura como empaquetado")
    encoder_names = _encoder_names()
    _require(tuple(FEATURE_NAMES) == encoder_names, "FEATURE_NAMES no coincide con el encoder")
    _require(len(encoder_names) == 35, "el encoder no tiene 35 columnas")
    statistics = freeze["standardizer"]
    _require(list(statistics["feature_names"]) == list(encoder_names), "el orden congelado no es el del encoder")
    recomputed_stats = stats_sha256(statistics)
    _require(recomputed_stats == freeze["standardizer_sha256"], "el hash de estadísticas no cuadra con el congelado")
    _require(
        recomputed_stats == protocol["transform"]["standardizer_sha256"],
        "el hash de estadísticas no cuadra con el protocolo",
    )
    orders = protocol["development_sample"]["execution_items"]
    order_ids = [row["order_id"] for row in orders]
    recomputed_list = frozen_list_sha256(order_ids)
    _require(
        recomputed_list == protocol["development_sample"]["frozen_list_sha256"],
        "el hash de la lista no cuadra con el protocolo",
    )
    _require(
        recomputed_list == freeze["development_sample"]["frozen_list_sha256"],
        "el hash de la lista no cuadra con el congelado",
    )
    _require(order_ids == sorted(order_ids), "el orden de ejecución no es el id ascendente")
    counts = {"euro-pallet": 0, "rollcontainer": 0}
    for row in orders:
        _require(row["target"] in counts, "target desconocido en la muestra")
        counts[row["target"]] += 1
    _require(counts == {"euro-pallet": 25, "rollcontainer": 25}, "la muestra no tiene 25 pedidos por target")
    constants = freeze["constant_columns"]["train"]
    _require(constants == freeze["constant_columns"]["train_plus_val"], "train y train+val no comparten constantes")
    _require(len(constants) == 15, "no hay quince columnas constantes")
    names = statistics["feature_names"]
    for name in constants:
        index = names.index(name)
        _require(statistics["population_std"][index] == 0, f"{name} no tiene desviación 0")
        _require(statistics["denominator"][index] == 1, f"{name} no conserva denominador 1")
    hyperparameters = hyperparameters_from_protocol(protocol)
    return {
        "protocol": protocol,
        "freeze": freeze,
        "protocol_path": str(protocol_file),
        "freeze_path": str(freeze_file),
        "protocol_sha256": sha256_file(protocol_file),
        "freeze_sha256": sha256_file(freeze_file),
        "statistics": statistics,
        "standardizer_sha256": recomputed_stats,
        "orders": orders,
        "hyperparameters": hyperparameters,
        "seeds": list(hyperparameters["seeds"]),
    }
