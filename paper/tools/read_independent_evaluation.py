"""Lee la evaluación 07 ya escrita y aplica bootstrap_primary. No ejecuta políticas."""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from independent_analysis import bootstrap_primary

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "paper/protocols/07_independent_evaluation.json"
OUT = REPO / "paper/results/07_independent_evaluation"
ANALYSIS = OUT / "independent_analysis.json"
TIE_EPS = 1e-9
FROZEN_LIST = "dcb312188127239b70a0b4422fef8b03fc489817b9e504f180278d812a2d2227"
RUN_ID = "09d052b75a534728"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    items = protocol["orders"]["items"]
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    paired = json.loads((OUT / "paired_results.json").read_text(encoding="utf-8"))
    results = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    pairs = paired["pairs"]
    rows = results["rows"]

    issues: list[str] = []
    if manifest.get("status") != "complete" or summary.get("status") != "complete":
        issues.append("estado distinto de complete")
    if manifest.get("complete") is not True or summary.get("complete") is not True:
        issues.append("complete no es true")
    if results.get("complete") is not True or paired.get("complete") is not True:
        issues.append("results o paired sin complete")

    row_keys = [(row["order_id"], row["method"]) for row in rows]
    if len(rows) != 400 or len(set(row_keys)) != 400:
        issues.append(f"filas únicas {len(set(row_keys))} de {len(rows)}")
    pair_ids = [pair["order_id"] for pair in pairs]
    if len(pairs) != 200 or len(set(pair_ids)) != 200:
        issues.append(f"pares únicos {len(set(pair_ids))} de {len(pairs)}")

    protocol_ids = [item["order_id"] for item in items]
    protocol_targets = [item["target"] for item in items]
    if protocol_ids != pair_ids or protocol_targets != [pair["target"] for pair in pairs]:
        issues.append("ids, orden o targets de los pares no coinciden con el protocolo")
    expected_row_keys = [(item["order_id"], method) for item in items for method in ("actor", "heuristic")]
    if row_keys != expected_row_keys:
        issues.append("filas distintas del orden actor-heurística del protocolo")
    if [item["order_id"] for item in items] != sorted(protocol_ids):
        issues.append("el protocolo no está en orden de id ascendente")
    joined = "\n".join(protocol_ids) + "\n"
    frozen = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    if frozen != FROZEN_LIST or protocol["orders"]["frozen_list_sha256"] != FROZEN_LIST:
        issues.append("hash de la lista congelada distinto")

    counts = Counter(protocol_targets)
    if counts["euro-pallet"] != 91 or counts["rollcontainer"] != 109:
        issues.append(f"cuotas {dict(counts)}")

    run_ids = {
        "manifest": manifest.get("run_id"),
        "summary": summary.get("run_id"),
        "paired": paired.get("run_id"),
        "results": results.get("run_id"),
    }
    row_run_ids = {row.get("run_id") for row in rows}
    nested_run_ids = {side.get("run_id") for pair in pairs for side in (pair["actor"], pair["heuristic"])}
    if set(run_ids.values()) != {RUN_ID} or row_run_ids != {RUN_ID} or nested_run_ids != {RUN_ID}:
        issues.append(f"run_id incoherente {run_ids} filas={row_run_ids} lados={nested_run_ids}")

    stability = []
    for row in rows:
        if row.get("physical_stability_verified") is not None:
            stability.append(("row", row["order_id"], row["method"]))
    if summary.get("physical_stability_verified") is not None:
        stability.append(("summary",))
    for pair in pairs:
        for side_name in ("actor", "heuristic"):
            if pair[side_name].get("physical_stability_verified") is not None:
                stability.append(("pair", pair["order_id"], side_name))
    if stability:
        issues.append(f"physical_stability_verified no null en {len(stability)} sitios")

    failure_rows = [row for row in rows if row.get("method_failure") or row.get("failure_types")]
    if summary.get("n") != 200 or paired.get("n_pairs") != 200 or results.get("n_rows") != 400:
        issues.append("el denominador guardado no es 200 pares y 400 filas")
    if len(pairs) != protocol["orders"]["n"]:
        issues.append("hay pares fuera del denominador del protocolo")

    missing_capture = []
    missing_audit = []
    capture_stability = []
    capture_present = 0
    for item in items:
        for method in ("actor", "heuristic"):
            case_dir = OUT / "cases" / item["order_id"] / method
            audit_path = case_dir / "audit.json"
            capture_path = case_dir / "capture.json"
            worker_path = case_dir / "worker.json"
            if not audit_path.is_file():
                missing_audit.append(f"{item['order_id']}/{method}")
            if not worker_path.is_file():
                issues.append(f"sin worker.json {item['order_id']}/{method}")
                continue
            worker = json.loads(worker_path.read_text(encoding="utf-8"))
            produced = worker.get("status") == "ok"
            if produced and not capture_path.is_file():
                missing_capture.append(f"{item['order_id']}/{method}")
            if capture_path.is_file():
                capture_present += 1
                capture = json.loads(capture_path.read_text(encoding="utf-8"))
                if capture.get("physical_stability_verified") is not None:
                    capture_stability.append(f"{item['order_id']}/{method}")
    if missing_capture:
        issues.append(f"capturas ausentes donde el worker terminó ok: {len(missing_capture)}")
    if missing_audit:
        issues.append(f"auditorías ausentes: {len(missing_audit)}")
    if capture_stability:
        issues.append(f"capturas con estabilidad física no null: {len(capture_stability)}")

    recomputed = []
    delta_gaps = []
    for pair in pairs:
        delta = float(pair["actor"]["effective_u_geom"]) - float(pair["heuristic"]["effective_u_geom"])
        recomputed.append(delta)
        delta_gaps.append(abs(delta - float(pair["delta"])))
    max_delta_gap = max(delta_gaps) if delta_gaps else None
    if max_delta_gap is not None and max_delta_gap > 1e-12:
        issues.append(f"delta guardado distinto del recálculo, máximo {max_delta_gap}")

    mean_delta = statistics.fmean(recomputed)
    median_delta = statistics.median(recomputed)
    wins = sum(1 for value in recomputed if value > TIE_EPS)
    ties = sum(1 for value in recomputed if abs(value) <= TIE_EPS)
    losses = sum(1 for value in recomputed if value < -TIE_EPS)
    contrasts = {
        "mean_delta": abs(mean_delta - float(summary["mean_delta"])),
        "median_delta": abs(median_delta - float(summary["median_delta"])),
        "wins": wins != summary["wins"],
        "ties": ties != summary["ties"],
        "losses": losses != summary["losses"],
    }
    if contrasts["mean_delta"] > 1e-12 or contrasts["median_delta"] > 1e-12 or any(
        contrasts[key] for key in ("wins", "ties", "losses")
    ):
        issues.append(f"resumen distinto del recálculo {contrasts}")

    by_target = {}
    for target in ("euro-pallet", "rollcontainer"):
        values = [delta for delta, pair in zip(recomputed, pairs) if pair["target"] == target]
        actor_failures = sum(1 for pair in pairs if pair["target"] == target and pair["actor_failure"])
        heuristic_failures = sum(1 for pair in pairs if pair["target"] == target and pair["heuristic_failure"])
        stats = {
            "n": len(values),
            "mean_delta": statistics.fmean(values),
            "median_delta": statistics.median(values),
            "wins": sum(1 for value in values if value > TIE_EPS),
            "ties": sum(1 for value in values if abs(value) <= TIE_EPS),
            "losses": sum(1 for value in values if value < -TIE_EPS),
            "actor_failures": actor_failures,
            "heuristic_failures": heuristic_failures,
        }
        saved = summary["by_target"][target]
        for key in ("n", "wins", "ties", "losses", "actor_failures", "heuristic_failures"):
            if stats[key] != saved[key]:
                issues.append(f"{target} {key} {stats[key]} != {saved[key]}")
        for key in ("mean_delta", "median_delta"):
            if abs(stats[key] - float(saved[key])) > 1e-12:
                issues.append(f"{target} {key} difiere")
        by_target[target] = stats

    failure_types: dict[str, Counter] = {"actor": Counter(), "heuristic": Counter()}
    worker_status: dict[str, Counter] = {"actor": Counter(), "heuristic": Counter()}
    unpacked = Counter()
    for row in rows:
        worker_status[row["method"]][row.get("worker_status")] += 1
        for name in row.get("failure_types") or []:
            failure_types[row["method"]][name] += 1
        if row.get("n_unpacked_no_candidate"):
            unpacked[row["method"]] += 1

    euro = [
        delta
        for delta, item in sorted(
            ((delta, item) for delta, item in zip(recomputed, items) if item["target"] == "euro-pallet"),
            key=lambda pair: pair[1]["position"],
        )
    ]
    roll = [
        delta
        for delta, item in sorted(
            ((delta, item) for delta, item in zip(recomputed, items) if item["target"] == "rollcontainer"),
            key=lambda pair: pair[1]["position"],
        )
    ]
    analysis = bootstrap_primary(euro, roll, n_replicates=20000, seed=20261002)
    payload = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "protocol_sha256": sha256_file(PROTOCOL),
        "paired_results_sha256": sha256_file(OUT / "paired_results.json"),
        "within_target_order": "protocol_position",
        "mean_delta": analysis["mean_delta"],
        "ci_low": analysis["ci_low"],
        "ci_high": analysis["ci_high"],
        "interpretation": analysis["interpretation"],
        "replicates": analysis["replicates"],
        "seed": analysis["seed"],
        "percentile_method": analysis["percentile_method"],
        "n": analysis["n"],
        "n_euro_pallet": analysis["n_euro_pallet"],
        "n_rollcontainer": analysis["n_rollcontainer"],
        "equality_demonstrated": analysis["equality_demonstrated"],
        "by_target_role": analysis["by_target_role"],
        "interval_is_approximate": analysis["interval_is_approximate"],
    }
    ANALYSIS.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "issues": issues,
        "n_rows": len(rows),
        "n_pairs": len(pairs),
        "counts": dict(counts),
        "run_id": RUN_ID,
        "max_delta_gap": max_delta_gap,
        "mean_delta": mean_delta,
        "median_delta": median_delta,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "by_target": by_target,
        "actor_failures": summary["actor_failures"],
        "heuristic_failures": summary["heuristic_failures"],
        "failure_rows": len(failure_rows),
        "failure_types": {method: dict(counter) for method, counter in failure_types.items()},
        "worker_status": {method: dict(counter) for method, counter in worker_status.items()},
        "rows_with_unpacked_no_candidate": dict(unpacked),
        "capture_present": capture_present,
        "analysis": payload,
    }
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
