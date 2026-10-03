"""Entrenamiento emparejado de la ablación. Reutiliza fit_mlp sin cambiar su algoritmo.

La instrumentación registra pesos iniciales y permutaciones. No reajusta estadísticas.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from ablation_contract import ARMS, AblationError, code_sha256, load_contract
from normalization_features import stats_sha256, transform_rows
from pilot_common import atomic_write_json
from pilot_problems import prepare_imports

_THREADS_CONFIGURED = False


def configure_process_threads() -> dict[str, int]:
    """Fija un hilo de cómputo y uno de interoperación una sola vez por proceso."""

    global _THREADS_CONFIGURED
    import torch

    torch.set_num_threads(1)
    if not _THREADS_CONFIGURED:
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError as exc:
            if torch.get_num_interop_threads() != 1:
                raise AblationError(
                    "los hilos de interoperación ya no pueden fijarse en 1"
                ) from exc
        _THREADS_CONFIGURED = True
    if torch.get_num_threads() != 1 or torch.get_num_interop_threads() != 1:
        raise AblationError("la configuración de hilos del proceso no es 1 y 1")
    return {"torch.set_num_threads": 1, "torch.set_num_interop_threads": 1}


def initial_state_sha256(state_dict: dict[str, Any]) -> str:
    """SHA256 de clave, forma, dtype y bytes contiguos, en orden de clave."""

    chunks: list[bytes] = []
    for key in sorted(state_dict):
        tensor = state_dict[key].detach().cpu().contiguous()
        header = f"{key}|{list(tensor.shape)}|{tensor.dtype}|".encode("utf-8")
        chunks.append(header)
        chunks.append(tensor.numpy().tobytes())
    return hashlib.sha256(b"".join(chunks)).hexdigest()


def permutation_sha256(indices: list[list[int]]) -> str:
    """SHA256 del JSON canónico de las permutaciones, sin espacios."""

    payload = json.dumps(indices, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def transitions_sha256(transitions: list[dict[str, Any]]) -> str:
    payload = []
    for transition in transitions:
        payload.append(
            {
                "order_id": transition["order_id"],
                "step": transition["step"],
                "label": int(transition["label"]),
                "n_options": int(transition["n_options"]),
                "features": np.asarray(transition["features"], dtype=np.float64).tolist(),
            }
        )
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def transform_transitions(
    transitions: list[dict[str, Any]],
    statistics: dict[str, Any],
    arm: str,
) -> list[dict[str, Any]]:
    """Copia cada transición. Conserva etiqueta, orden de candidatas y filas de una opción."""

    if arm not in ARMS:
        raise AblationError("brazo desconocido")
    transformed: list[dict[str, Any]] = []
    for transition in transitions:
        matrix = np.asarray(transition["features"], dtype=np.float64)
        values = transform_rows(matrix, statistics, arm=arm)
        copied: dict[str, Any] = {
            "order_id": transition["order_id"],
            "step": transition["step"],
            "features": values.tolist(),
            "label": int(transition["label"]),
            "n_options": int(transition["n_options"]),
        }
        if "label_volume" in transition:
            copied["label_volume"] = transition["label_volume"]
        if copied["label"] != int(transition["label"]):
            raise AblationError("cambió una etiqueta")
        if values.shape[0] != matrix.shape[0]:
            raise AblationError("cambió el número de candidatas")
        transformed.append(copied)
    if len(transformed) != len(transitions):
        raise AblationError("cambió el número de transiciones")
    return transformed


def assert_adam_matches_protocol(hyperparameters: dict[str, Any]) -> None:
    import torch

    signature = inspect.signature(torch.optim.Adam.__init__)
    betas = signature.parameters["betas"].default
    eps = signature.parameters["eps"].default
    amsgrad = signature.parameters["amsgrad"].default
    if betas != hyperparameters["betas"] or eps != hyperparameters["eps"] or amsgrad is not False:
        raise AblationError("los defaults de Adam no coinciden con el protocolo congelado")


def _states_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    import torch

    if set(left) != set(right):
        return False
    return all(torch.equal(left[key], right[key]) for key in left)


def fit_one_arm(
    train_transitions: list[dict[str, Any]],
    val_transitions: list[dict[str, Any]],
    *,
    seed: int,
    hyperparameters: dict[str, Any],
) -> dict[str, Any]:
    """Llama a fit_mlp. El envoltorio solo observa la inicialización, el orden y el dtype."""

    configure_process_threads()
    assert_adam_matches_protocol(hyperparameters)
    prepare_imports()
    import torch
    import train_mlp

    observed: dict[str, Any] = {"init": None, "perms": [], "dtypes": []}
    original_randperm = torch.randperm
    original_build = train_mlp.build_mlp_v1

    def record_randperm(n: int, *args: Any, **kwargs: Any):
        permutation = original_randperm(n, *args, **kwargs)
        observed["perms"].append([int(value) for value in permutation.detach().cpu().tolist()])
        return permutation

    def record_build(hidden_size: int = 64):
        model = original_build(hidden_size)
        if observed["init"] is None:
            observed["init"] = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        original_forward = model.forward

        def forward(inputs):
            observed["dtypes"].append(str(inputs.dtype))
            return original_forward(inputs)

        model.forward = forward
        return model

    torch.manual_seed(seed)
    torch.randperm = record_randperm
    train_mlp.build_mlp_v1 = record_build
    try:
        fitted = train_mlp.fit_mlp(
            train_transitions,
            val_transitions,
            hidden_size=hyperparameters["hidden_size"],
            epochs=hyperparameters["epochs"],
            lr=hyperparameters["lr"],
            seed=seed,
            clip_grad=hyperparameters["clip_grad"],
            weight_decay=hyperparameters["weight_decay"],
            select_best=hyperparameters["select_best"],
            keep_epochs=hyperparameters["keep_epochs"],
            require_informative=hyperparameters["require_informative"],
            require_val=hyperparameters["require_val"],
        )
    finally:
        torch.randperm = original_randperm
        train_mlp.build_mlp_v1 = original_build
    if observed["init"] is None or not observed["perms"]:
        raise AblationError("fit_mlp no pasó por la inicialización y las permutaciones")
    if any(dtype != "torch.float32" for dtype in observed["dtypes"]):
        raise AblationError("el modelo recibió características que no eran float32")
    return {"fitted": fitted, "init": observed["init"], "perms": observed["perms"]}


def fit_paired_seed(
    train_transitions: list[dict[str, Any]],
    val_transitions: list[dict[str, Any]],
    statistics: dict[str, Any],
    *,
    seed: int,
    hyperparameters: dict[str, Any],
) -> dict[str, Any]:
    """Ajusta los dos brazos con la misma semilla y comprueba el emparejamiento."""

    before = stats_sha256(statistics)
    arms: dict[str, Any] = {}
    for arm in ARMS:
        train_arm = transform_transitions(train_transitions, statistics, arm)
        val_arm = transform_transitions(val_transitions, statistics, arm)
        arms[arm] = fit_one_arm(
            train_arm,
            val_arm,
            seed=seed,
            hyperparameters=hyperparameters,
        )
    if stats_sha256(statistics) != before:
        raise AblationError("las estadísticas se reajustaron")
    init_equal = _states_equal(arms["raw"]["init"], arms["normalized"]["init"])
    permutations_equal = arms["raw"]["perms"] == arms["normalized"]["perms"]
    if not init_equal or not permutations_equal:
        raise AblationError(f"la semilla {seed} no quedó emparejada")
    init_hash = initial_state_sha256(arms["raw"]["init"])
    if init_hash != initial_state_sha256(arms["normalized"]["init"]):
        raise AblationError(f"el hash inicial de la semilla {seed} no coincide")
    permutation_hash = permutation_sha256(arms["raw"]["perms"])
    if permutation_hash != permutation_sha256(arms["normalized"]["perms"]):
        raise AblationError(f"el hash de permutaciones de la semilla {seed} no coincide")
    return {
        "seed": seed,
        "init_equal": True,
        "permutations_equal": True,
        "initial_state_sha256": init_hash,
        "permutation_sha256": permutation_hash,
        "permutation_indices": arms["raw"]["perms"],
        "float32": True,
        "arms": arms,
    }


def research_checkpoint(
    *,
    arm: str,
    seed: int,
    fitted: dict[str, Any],
    statistics: dict[str, Any],
    initial_state_sha256_value: str,
    permutation_hash: str,
    permutation_indices: list[list[int]],
    data_sha256: dict[str, str],
    protocol_sha256: str,
    freeze_sha256: str,
    code_hash: dict[str, str],
) -> dict[str, Any]:
    kind = "identity" if arm == "raw" else "train_population_standardize"
    canonical = json.dumps(statistics, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return {
        "format": "packing-services-research-normalization-ablation",
        "version": 1,
        "role": "research-normalization-ablation",
        "not_for_production_loader": True,
        "arm": arm,
        "seed": int(seed),
        "architecture": "mlp_v1",
        "hidden_size": int(fitted["hidden_size"]),
        "feature_names": list(statistics["feature_names"]),
        "state_dict": fitted["state_dict"],
        "transform": {
            "arm": arm,
            "kind": kind,
            "applied_at": "training_and_scoring",
            "statistics": statistics,
            "statistics_canonical": canonical,
            "standardizer_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        },
        "data_sha256": data_sha256,
        "protocol_sha256": protocol_sha256,
        "freeze_sha256": freeze_sha256,
        "code_sha256": code_hash,
        "select_best": fitted["select_best"],
        "selection_rule": "menor val_loss estricta; se conserva el primer mínimo",
        "best_epoch": int(fitted["best_epoch"]),
        "best_val_loss": fitted["best_val_loss"],
        "history": fitted["history"],
        "initial_state_sha256": initial_state_sha256_value,
        "permutation_sha256": permutation_hash,
        "permutation_indices": permutation_indices,
        "device": "cpu",
        "dtype": "float32",
    }


def save_research_checkpoint(path: Path, document: dict[str, Any]) -> None:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(document, path)


def load_research_checkpoint(path: Path, *, expected_standardizer_sha256: str | None = None) -> dict[str, Any]:
    """Carga en CPU con weights_only=True y rechaza un contrato incompatible."""

    import torch

    prepare_imports()
    from packing_services.online.features import FEATURE_NAMES as encoder_names

    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise AblationError(f"no se pudo cargar el artefacto de investigación: {exc}") from exc
    if not isinstance(payload, dict):
        raise AblationError("el artefacto no es un dict")
    if payload.get("format") == "packing-services-online-policy":
        raise AblationError("un checkpoint de producción no se carga como artefacto de esta ablación")
    if payload.get("format") != "packing-services-research-normalization-ablation":
        raise AblationError("formato de artefacto incompatible")
    if int(payload.get("version", 0)) != 1:
        raise AblationError("versión de artefacto incompatible")
    if payload.get("not_for_production_loader") is not True:
        raise AblationError("el artefacto no declara su separación del loader de producción")
    arm = payload.get("arm")
    if arm not in ARMS:
        raise AblationError("brazo incompatible")
    if payload.get("architecture") != "mlp_v1":
        raise AblationError("arquitectura incompatible")
    if list(payload.get("feature_names") or []) != list(encoder_names):
        raise AblationError("el orden de columnas del artefacto no es el del encoder")
    transform = payload.get("transform") or {}
    if transform.get("arm") != arm:
        raise AblationError("el brazo de la transformación no coincide")
    expected_kind = "identity" if arm == "raw" else "train_population_standardize"
    if transform.get("kind") != expected_kind:
        raise AblationError("la transformación no corresponde al brazo")
    canonical = transform.get("statistics_canonical")
    if not isinstance(canonical, str):
        raise AblationError("el artefacto no trae la serialización canónica de las estadísticas")
    recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if recomputed != transform.get("standardizer_sha256"):
        raise AblationError("el hash de estadísticas del artefacto no cuadra")
    statistics = json.loads(canonical)
    if not isinstance(statistics, dict):
        raise AblationError("las estadísticas canónicas no son un objeto")
    payload["transform"]["statistics"] = statistics
    if expected_standardizer_sha256 is not None and recomputed != expected_standardizer_sha256:
        raise AblationError("las estadísticas no son las del congelado")
    if payload.get("select_best") != "val_loss":
        raise AblationError("la regla de selección no es val_loss")
    state = payload.get("state_dict")
    if not isinstance(state, dict) or "0.weight" not in state or "2.weight" not in state:
        raise AblationError("state_dict incompatible con mlp_v1")
    return payload


def expected_best_epoch(history: list[dict[str, Any]]) -> int:
    """Primer epoch, en base 1, cuya val_loss es estrictamente menor que las anteriores."""

    best_loss = float("inf")
    best_epoch = 0
    for row in history:
        loss = float(row["val_loss"])
        epoch = int(row["epoch"])
        if loss < best_loss:
            best_loss = loss
            best_epoch = epoch
    return best_epoch


def load_audited_transitions(contract: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Lee los dos pickle BC solo cuando se ejecuta la etapa real."""

    import pickle

    prepare_imports()
    from paths import TRAIN_DIR, VAL_DIR

    expected = contract["freeze"]["transitions"]["sha256_before"]
    files = {"train": TRAIN_DIR / "transitions_p1s1.pkl", "val": VAL_DIR / "transitions_p1s1.pkl"}
    for split, path in files.items():
        if sha256_file_bytes(path) != expected[split]:
            raise AblationError(f"el hash de {split} no coincide con el congelado; no se abre")
    loaded: dict[str, list[dict[str, Any]]] = {}
    for split, path in files.items():
        with path.open("rb") as handle:
            payload = pickle.load(handle)
        loaded[split] = payload["transitions"]
        if sha256_file_bytes(path) != expected[split]:
            raise AblationError(f"el hash de {split} cambió durante la lectura")
    return loaded


def sha256_file_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def environment_record() -> dict[str, Any]:
    import platform
    import sys
    import torch

    return {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "platform": platform.platform(),
        "device": "cpu",
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        "threads": configure_process_threads(),
    }


def run_training_stage(
    *,
    protocol_path: Path,
    freeze_path: Path,
    output_dir: Path,
    command: list[str],
    transitions: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Escribe los diez artefactos. Rechaza una carpeta ya existente."""

    output = output_dir.expanduser().resolve()
    if output.exists():
        raise AblationError("la carpeta de ejecución ya existe; no se reanuda ni se mezcla")
    contract = load_contract(protocol_path, freeze_path)
    output.mkdir(parents=True)
    manifest: dict[str, Any] = {
        "stage": "training",
        "status": "running",
        "confirmatory": False,
        "protocol_sha256": contract["protocol_sha256"],
        "freeze_sha256": contract["freeze_sha256"],
        "standardizer_sha256": contract["standardizer_sha256"],
        "code_sha256": code_sha256(),
        "command": command,
        "environment": None,
        "seeds": contract["seeds"],
        "models": [],
        "real_pickles_opened": transitions is None,
    }
    atomic_write_json(output / "manifest.json", manifest)
    try:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        manifest["environment"] = environment_record()
        if transitions is None:
            loaded = load_audited_transitions(contract)
            train_rows = loaded["train"]
            val_rows = loaded["val"]
            data_hash = {
                "source": "audited_p1s1",
                "train": contract["freeze"]["transitions"]["sha256_before"]["train"],
                "val": contract["freeze"]["transitions"]["sha256_before"]["val"],
            }
        else:
            train_rows = transitions["train"]
            val_rows = transitions["val"]
            data_hash = {
                "source": "caller",
                "train": transitions_sha256(train_rows),
                "val": transitions_sha256(val_rows),
            }
        statistics = contract["statistics"]
        stats_before = stats_sha256(statistics)
        for seed in contract["seeds"]:
            paired = fit_paired_seed(
                train_rows,
                val_rows,
                statistics,
                seed=seed,
                hyperparameters=contract["hyperparameters"],
            )
            atomic_write_json(
                output / "pairing" / f"seed_{seed}.json",
                {
                    "seed": seed,
                    "init_equal": paired["init_equal"],
                    "permutations_equal": paired["permutations_equal"],
                    "initial_state_sha256": paired["initial_state_sha256"],
                    "permutation_sha256": paired["permutation_sha256"],
                    "permutation_indices": paired["permutation_indices"],
                    "float32": paired["float32"],
                },
            )
            for arm in ARMS:
                fitted = paired["arms"][arm]["fitted"]
                if expected_best_epoch(fitted["history"]) != int(fitted["best_epoch"]):
                    raise AblationError("best_epoch no sigue la val_loss estricta")
                document = research_checkpoint(
                    arm=arm,
                    seed=seed,
                    fitted=fitted,
                    statistics=statistics,
                    initial_state_sha256_value=paired["initial_state_sha256"],
                    permutation_hash=paired["permutation_sha256"],
                    permutation_indices=paired["permutation_indices"],
                    data_sha256=data_hash,
                    protocol_sha256=contract["protocol_sha256"],
                    freeze_sha256=contract["freeze_sha256"],
                    code_hash=manifest["code_sha256"],
                )
                relative = f"models/{arm}_seed{seed}.pt"
                save_research_checkpoint(output / relative, document)
                manifest["models"].append(
                    {
                        "arm": arm,
                        "seed": seed,
                        "path": relative,
                        "best_epoch": document["best_epoch"],
                        "initial_state_sha256": paired["initial_state_sha256"],
                        "permutation_sha256": paired["permutation_sha256"],
                    }
                )
                atomic_write_json(output / "manifest.json", manifest)
        if stats_sha256(statistics) != stats_before:
            raise AblationError("las estadísticas cambiaron durante el entrenamiento")
        if len(manifest["models"]) != 10:
            raise AblationError("no quedaron los diez modelos")
        manifest["status"] = "complete"
    except Exception as exc:
        manifest["status"] = "incomplete"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        atomic_write_json(output / "manifest.json", manifest)
        raise
    atomic_write_json(output / "manifest.json", manifest)
    return manifest
