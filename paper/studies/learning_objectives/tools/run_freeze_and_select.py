"""Selecciona muestras y congela el protocolo. No ejecuta packing de campaña."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path.insert(0, str(HERE))

from freeze_protocol import build_protocol, write_protocol  # noqa: E402
from preflight import file_sha256  # noqa: E402
from select_samples import DATASET, select_all  # noqa: E402


def main() -> int:
    orders = json.loads(DATASET.read_text(encoding="utf-8"))
    sample = select_all(orders)
    sample_path = STUDY / "sample_manifest.json"
    sample_path.write_text(json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    code_hashes = {relative: file_sha256(STUDY / relative) for relative in [
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
        "tools/freeze_protocol.py",
    ]}
    protocol = build_protocol(sample, code_hashes)
    protocol["sample_manifest_sha256"] = file_sha256(sample_path)
    protocol["code_files"] = list(code_hashes)
    digest = write_protocol(protocol, STUDY / "protocol_frozen.json")
    print(json.dumps({
        "sample_manifest": str(sample_path),
        "n_train": sample["n_train"],
        "n_development": sample["n_development"],
        "n_test": sample["n_test"],
        "preflight_orders": sample["preflight_orders"],
        "protocol_sha256": digest,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
