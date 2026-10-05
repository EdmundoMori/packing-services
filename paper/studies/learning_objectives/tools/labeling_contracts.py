"""Contratos y preflight estático del etiquetado learning_objectives.

No empaqueta. No modifica el protocolo ni el manifiesto congelados.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_PROTOCOL_FILE_SHA256 = "385f25c60e92dc936c02363b7152031d20b2728db13c2f9d4911446930b83b05"
EXPECTED_PROTOCOL_INTERNAL_DIGEST = "a5959cb602ee00dfcb56b531de02d6e9d1dd618c42a54b7aa1e0d2214e6ad155"
EXPECTED_SAMPLE_MANIFEST_SHA256 = "782eb3abe10163270db8dec9594d099ea936e4491747278bee1b06a73accda62"
PUBLISHED_PREFLIGHT_WALL_SECONDS = 35.121554053999716
PREFLIGHT_REUSE_ORDER_IDS = ("00105883", "00104801")
SPLITS = ("train", "development")
CONTINUATION_TIMEOUT_SECONDS = 60.0
AUDIT_TIMEOUT_SECONDS = 60.0


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_internal_digest(protocol: dict[str, Any]) -> str:
    body = {key: value for key, value in protocol.items() if key != "sha256"}
    raw = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_frozen_artifacts(
    *,
    protocol_path: Path,
    sample_path: Path,
    study_dir: Path,
) -> dict[str, Any]:
    protocol_bytes = protocol_path.read_bytes()
    sample_bytes = sample_path.read_bytes()
    file_digest = hashlib.sha256(protocol_bytes).hexdigest()
    sample_digest = hashlib.sha256(sample_bytes).hexdigest()
    protocol = json.loads(protocol_bytes.decode("utf-8"))
    internal = protocol_internal_digest(protocol)
    if file_digest != EXPECTED_PROTOCOL_FILE_SHA256:
        raise RuntimeError(f"SHA256 completo del protocolo distinto: {file_digest}")
    if internal != EXPECTED_PROTOCOL_INTERNAL_DIGEST:
        raise RuntimeError(f"digest interno del protocolo distinto: {internal}")
    if protocol.get("sha256") != EXPECTED_PROTOCOL_INTERNAL_DIGEST:
        raise RuntimeError("campo sha256 del protocolo distinto del digest interno esperado")
    if sample_digest != EXPECTED_SAMPLE_MANIFEST_SHA256:
        raise RuntimeError(f"SHA256 de sample_manifest distinto: {sample_digest}")
    dataset = Path(protocol["dataset"])
    if not dataset.is_file():
        raise RuntimeError(f"dataset ausente: {dataset}")
    dataset_sha = file_sha256(dataset)
    if dataset_sha != protocol["dataset_sha256"]:
        raise RuntimeError("dataset SHA256 distinto del protocolo")
    code_mismatches = []
    for relative, expected in protocol["code_hashes"].items():
        path = study_dir / relative
        if not path.is_file():
            code_mismatches.append({"path": relative, "error": "missing"})
            continue
        current = file_sha256(path)
        if current != expected:
            code_mismatches.append({"path": relative, "expected": expected, "actual": current})
    if code_mismatches:
        raise RuntimeError(f"hashes de código incongruentes: {code_mismatches[:5]}")
    if protocol.get("authorizes_labeling") is True:
        # El protocolo congelado no autoriza; la autorización operativa es externa.
        pass
    return {
        "protocol": protocol,
        "protocol_file_sha256": file_digest,
        "protocol_internal_digest": internal,
        "sample_manifest_sha256": sample_digest,
        "dataset_sha256": dataset_sha,
        "dataset": str(dataset),
    }


def directory_must_be_absent_or_empty(path: Path) -> None:
    if path.exists():
        if any(path.iterdir()):
            raise RuntimeError(f"carpeta de salida existente no vacía: {path}")
        raise RuntimeError(f"carpeta de salida ya existe: {path}")


def execution_order(sample: dict[str, Any]) -> list[dict[str, Any]]:
    """Orden congelado: train luego development; dentro, selection_hash y order_id."""

    ordered: list[dict[str, Any]] = []
    for split in SPLITS:
        rows: list[dict[str, Any]] = []
        for target, items in sample[split].items():
            for row in items:
                rows.append({**row, "split": split, "target": row.get("target") or target})
        rows.sort(key=lambda item: (item["selection_hash"], item["order_id"]))
        ordered.extend(rows)
    test_ids = {row["order_id"] for rows in sample.get("test", {}).values() for row in rows}
    for row in ordered:
        if row["order_id"] in test_ids and row["split"] != "test":
            continue
        if row["split"] == "test":
            raise RuntimeError("el orden de ejecución no puede incluir test")
    if any(row["split"] == "test" for row in ordered):
        raise RuntimeError("test filtrado incorrectamente")
    return ordered


def assert_no_test_execution(ordered: list[dict[str, Any]], sample: dict[str, Any]) -> None:
    test_ids = {row["order_id"] for rows in sample.get("test", {}).values() for row in rows}
    for row in ordered:
        if row["split"] == "test":
            raise RuntimeError("bloqueo: se intentó ejecutar test")
        if row["order_id"] in test_ids and row["split"] not in SPLITS:
            raise RuntimeError("bloqueo: id de test fuera de train/development")


def build_execution_manifest(
    *,
    protocol: dict[str, Any],
    sample: dict[str, Any],
    contracts: dict[str, Any],
    output: Path,
    preflight_dir: Path,
    study_dir: Path,
) -> dict[str, Any]:
    ordered = execution_order(sample)
    assert_no_test_execution(ordered, sample)
    return {
        "study": "learning_objectives",
        "stage": "labeling",
        "status": "manifest_written_before_first_continuation",
        "authorizes_training": False,
        "test_executed": False,
        "development_evaluated": False,
        "labels_campaign_executed": False,
        "output": str(output),
        "protocol_path": str(study_dir / "protocol_frozen.json"),
        "protocol_file_sha256": contracts["protocol_file_sha256"],
        "protocol_internal_digest": contracts["protocol_internal_digest"],
        "sample_manifest_sha256": contracts["sample_manifest_sha256"],
        "dataset": contracts["dataset"],
        "dataset_sha256": contracts["dataset_sha256"],
        "preflight_dir": str(preflight_dir),
        "preflight_wall_seconds_accounted": PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "preflight_wall_phase": "preflight",
        "labeling_wall_budget_seconds": float(protocol["budget"]["labeling_wall_seconds"]),
        "global_wall_budget_seconds": float(protocol["budget"]["total_wall_seconds"]),
        "execution_order": [
            {
                "order_id": row["order_id"],
                "split": row["split"],
                "target": row["target"],
                "selection_hash": row["selection_hash"],
                "signature": row["signature"],
            }
            for row in ordered
        ],
        "n_orders": len(ordered),
        "splits": list(SPLITS),
        "support_contract": protocol["support_contract"]["name"],
        "states_per_order_max": int(protocol["labeling"]["states_per_order_max"]),
        "train_max_states": int(protocol["labeling"]["train_max_states"]),
        "train_max_continuations": int(protocol["labeling"]["train_max_continuations"]),
        "development_max_states": int(protocol["labeling"]["development_max_states"]),
        "development_max_continuations": int(protocol["labeling"]["development_max_continuations"]),
        "incomplete_states_kept": True,
        "no_training_on_partial_labels": True,
        "physical_stability_verified": None,
    }


def static_preflight(
    *,
    study_dir: Path,
    output: Path,
    preflight_dir: Path | None = None,
) -> dict[str, Any]:
    """Valida contratos y escribe el manifiesto sin packing."""

    directory_must_be_absent_or_empty(output)
    protocol_path = study_dir / "protocol_frozen.json"
    sample_path = study_dir / "sample_manifest.json"
    contracts = verify_frozen_artifacts(
        protocol_path=protocol_path,
        sample_path=sample_path,
        study_dir=study_dir,
    )
    protocol = contracts["protocol"]
    sample = load_json(sample_path)
    if sample["n_train"] != 48 or sample["n_development"] != 24 or sample["n_test"] != 100:
        raise RuntimeError("tamaños de muestra distintos del protocolo")
    resolved_preflight = preflight_dir or (study_dir / "preflight")
    if not resolved_preflight.is_dir():
        raise RuntimeError(f"preflight publicado ausente: {resolved_preflight}")
    verification_path = resolved_preflight / "preflight_verification.json"
    if not verification_path.is_file():
        raise RuntimeError("falta preflight_verification.json")
    verification = load_json(verification_path)
    if abs(float(verification["wall_seconds"]) - PUBLISHED_PREFLIGHT_WALL_SECONDS) > 1e-12:
        raise RuntimeError("wall del preflight publicado distinto del valor congelado")
    if verification.get("protocol_sha256") != EXPECTED_PROTOCOL_INTERNAL_DIGEST:
        raise RuntimeError("preflight.protocol_sha256 incongruente")
    if int(verification.get("continuations_used", -1)) != 16:
        raise RuntimeError("preflight no tiene exactamente 16 continuaciones")
    output.mkdir(parents=True, exist_ok=False)
    manifest = build_execution_manifest(
        protocol=protocol,
        sample=sample,
        contracts=contracts,
        output=output,
        preflight_dir=resolved_preflight,
        study_dir=study_dir,
    )
    (output / "execution_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "protocol": protocol,
        "sample": sample,
        "contracts": contracts,
        "manifest": manifest,
        "preflight_dir": resolved_preflight,
        "preflight_verification": verification,
        "ordered": execution_order(sample),
    }
