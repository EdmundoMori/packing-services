#!/usr/bin/env python3
"""Escribe g2_protocol_frozen.json/.md ANTES de packing (hashes incluidos)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((STUDY / "sample_manifest.json").read_text(encoding="utf-8"))
    code_files = [
        "tools/error_model.py",
        "tools/methods_g2.py",
        "tools/run_g2_episode.py",
        "tools/bedbpp_episode.py",
        "tools/episode.py",
        "tools/adapters.py",
        "tools/geometry_contract.py",
        "tools/info_separation.py",
        "tools/baselines.py",
        "tools/freeze_g2_sample.py",
        "tools/run_g2_preflight.py",
        "tools/verify_g2_preflight.py",
    ]
    code_hashes = {rel: sha256_file(STUDY / rel) for rel in code_files if (STUDY / rel).exists()}

    protocol = {
        "protocol_id": "rpm-g2-frozen-v1",
        "frozen_at": "2026-10-05T20:55:00Z",
        "status": "frozen_before_packing",
        "packing_authorized": "preflight_only_8_episodes",
        "g2_full_authorized": False,
        "training_authorized": False,
        "head_expected": "74c878e1a7bc7e77a2182d92d72c8a76f39d6de2",
        "branch_expected": "research/paper-online-packing",
        "agents_md": "ausente_en_repositorio",
        "formulation": "B",
        "error_model": {
            "model_id": "b1_mult_expand_v1",
            "family": (
                "realized_axis = max(1.0, nominal_axis * (1+alpha)); "
                "independiente entre ítems; misma realización por ítem entre métodos; "
                "orientación permuta el mismo triplete realizado."
            ),
            "units": "mm",
            "scenarios": {
                "sens_low": {"alpha": 0.02, "uniform_ref_mm": 3.0},
                "sens_mid": {"alpha": 0.05, "uniform_ref_mm": 7.0},
                "sens_high": {"alpha": 0.10, "uniform_ref_mm": 12.0},
            },
            "realizations_per_order_scenario": 1,
            "uncertainty_level": (
                "Condiciones de sensibilidad propias (ingeniería), no calibración empírica "
                "sobre BED-BPP. No se usa el 2 cm del n-gram BED-BPP. Ancla de orden de "
                "magnitud del nivel medio: buffer GOPT 7 mm (no ley del dataset)."
            ),
            "risk_metric_scope": (
                "Con R=1, las tasas reportadas son frecuencias observadas en escenarios "
                "de sensibilidad. No permiten calibrar una restricción probabilística "
                "Pr(fallo)≤ε ni interpretar 0 fallos como garantía."
            ),
            "not_bedbpp_ngram_2cm": True,
            "seed_namespace": "rpm-g2-error|v1",
            "realization_rule": (
                "Determinista dado (order_id, scenario_id, alpha): expand_nominal(nominal, alpha). "
                "Sin muestreo adicional; no hay semilla aleatoria por repetición porque R=1."
            ),
        },
        "methods": {
            "M0": {
                "math": "m=(0,0,0); choice=argmin rank_key over EP envelope candidates",
                "comparison_kind": "method",
                "public_info_only": True,
            },
            "M1": {
                "math": "m=(u,u,u), u=uniform_ref_mm(scenario); same chooser",
                "comparison_kind": "protection_level_within_scenario",
                "note": "Comparación principal = nivel de protección uniforme vs M0/M2, no política distinta",
                "public_info_only": True,
            },
            "M2": {
                "math": "m_i = alpha * nominal_i for i in {L,W,H}; same chooser",
                "comparison_kind": "method",
                "public_info_only": True,
            },
            "M3": {
                "math": (
                    "menu M={m0,m1,m2}; risk_hat=0 if n_cand(m)>0 else 1; "
                    "select argmin (risk_hat, sum(m), best_cand.rank_key); "
                    "si todos risk=1 → no_candidate"
                ),
                "comparison_kind": "method",
                "public_info_only": True,
                "note": (
                    "Si M2/M3 dominan el menú sin residual material, RL puede ser innecesario "
                    "en el alcance examinado; eso se decide tras G2 completo, no en preflight."
                ),
            },
            "parameter_lock": "No ajuste de parámetros tras observar packing.",
            "chooser": "fixed_rank_chooser: menor rank_key; sin lookahead; sin realizados ocultos",
        },
        "what_g2_can_show": [
            "arnes_invalido",
            "sensibilidad_insuficiente_o_diseno_no_informativo",
            "baseline_analitico_suficiente_en_alcance_examinado",
            "compromiso_observado_que_justifica_disenar_diagnostico_adicional_de_seleccion_adaptativa",
        ],
        "what_g2_cannot_show": [
            "necesidad_de_RL_solo_por_diferencias_entre_margenes",
            "que_una_politica_online_identifica_el_mejor_metodo_por_pedido_elegido_post_hoc",
            "calibracion_probabilistica_con_R=1",
            "autorizacion_de_entrenamiento",
        ],
        "metrics": {
            "J_B": "V_nom/Vol(C) con V_nom nominal acumulado; 0 si geometric_failure",
            "geometric_failure": "salida o solape de AABB realizado",
            "envelope_exceeded": "realizado_orientado no ⊆ envelope; distinto de geometric_failure",
            "no_candidate": "sin candidata EP bajo envelope; distinto de fallo geométrico",
            "physical_stability_verified": None,
            "risk_volume_tradeoff": (
                "Compromiso riesgo–volumen = contraste emparejado entre métodos de "
                "(frecuencia_observada_geometric_failure, J_B, V_nom_before_failure) "
                "bajo los mismos pedidos×escenarios. No es residual de RL identificable "
                "sin contraste adicional de selección adaptativa."
            ),
            "observed_frequency_label": "frecuencia observada en escenarios",
        },
        "sample": {
            "manifest": "sample_manifest.json",
            "manifest_sha256": sha256_file(STUDY / "sample_manifest.json"),
            "n_development_max": 10,
            "preflight_orders": list(manifest["preflight_orders"]),
            "preflight_rule": manifest["preflight_rule"],
            "absolute_independence": False,
            "learning_objectives_test_not_used": True,
        },
        "budget": {
            "g2_max_episodes": 120,
            "g2_structure": "N<=10 × S=3 × M=4",
            "preflight_episodes_max": 8,
            "preflight_structure": "2 orders × 4 methods × 1 scenario (sens_mid)",
            "timeout_episode_s": 100.0,
            "wall_global_preflight_s": 900.0,
            "no_selective_retries": True,
            "ceiling_not_silently_expanded": True,
        },
        "preflight": {
            "scenario_id": "sens_mid",
            "orders": list(manifest["preflight_orders"]),
            "methods": ["M0", "M1", "M2", "M3"],
            "episodes_planned": 8,
            "reuse_in_g2_full": (
                "Solo si coinciden exactamente contrato, código pertinente, métodos, "
                "entradas y realizaciones; no por similitud de nombres. No autorizado aún."
            ),
            "do_not_use_to_retune_methods_or_orders": True,
        },
        "integrity_rules": {
            "src_unchanged": True,
            "realized_geometry_after_reveal": True,
            "envelope_exceeded_separated": True,
            "no_candidate_separated": True,
            "J_B_nominal_zero_on_geom_fail": True,
            "physical_stability_verified": None,
            "policy_no_current_realized_before_act": True,
            "paired_realizations_across_methods": True,
            "failed_attempt_preserved": True,
            "atomic_persist": True,
        },
        "hashes": {
            "dataset_sha256": manifest["dataset_sha256"],
            "sample_manifest_sha256": sha256_file(STUDY / "sample_manifest.json"),
            "code": code_hashes,
        },
    }

    # Write without self hash first
    out_json = STUDY / "g2_protocol_frozen.json"
    body = json.dumps(protocol, indent=2, ensure_ascii=False) + "\n"
    # provisional write for hashing content excluding self
    protocol["protocol_content_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    body2 = json.dumps(protocol, indent=2, ensure_ascii=False) + "\n"
    out_json.write_text(body2, encoding="utf-8")

    md = f"""# G2 — protocolo congelado (antes de packing)

**Estado:** congelado · packing autorizado solo para **preflight 8 episodios**
**HEAD esperado:** `{protocol["head_expected"]}`
**Rama:** `{protocol["branch_expected"]}`
**AGENTS.md:** ausente en el repositorio
**protocol_id:** `{protocol["protocol_id"]}`
**content_sha256:** `{protocol["protocol_content_sha256"]}`

## Modelo sintético (B1)

- `realized_axis = max(1.0, nominal_axis * (1+α))`, unidades mm.
- Escenarios de **sensibilidad** (no tres i.i.d. de una P empírica):

| ID | α | u uniforme (mm) |
|----|---|-----------------|
| sens_low | 0.02 | 3 |
| sens_mid | 0.05 | 7 |
| sens_high | 0.10 | 12 |

- **R=1** realización por pedido×escenario ⇒ métricas de riesgo = **frecuencia observada en escenarios**; no calibran Pr(fallo).
- 0 fallos ≠ garantía. No se usa el 2 cm n-gram de BED-BPP.
- Misma realización por ítem entre métodos; orientación permuta el mismo triplete.

## Métodos (misma info pública)

| ID | Definición | Tipo de comparación |
|----|------------|---------------------|
| M0 | m=(0,0,0); chooser rank_key | método |
| M1 | m=(u,u,u) | nivel de protección (dentro de escenario) |
| M2 | m_i=α·nominal_i | método |
| M3 | menú {{0, uniforme, eje}}; riesgo 0/1 por factibilidad; desempate suma(m), rank_key | método |

Parámetros **bloqueados** antes de packing. M2/M3 pueden hacer RL innecesario en el alcance; el preflight **no** lo decide.

## Qué puede demostrar G2

1. arnés inválido
2. sensibilidad insuficiente / diseño no informativo
3. baseline analítico suficiente en el alcance examinado
4. compromiso riesgo–volumen observado que justifica **diseñar** un diagnóstico adicional de selección adaptativa (**no** autoriza entrenamiento)

**No** demuestra: necesidad de RL solo por diferencias de márgenes; que una política online identificaría el mejor método post-hoc por pedido.

## Compromiso riesgo–volumen

Contraste emparejado de `(frecuencia_observada_geometric_failure, J_B, V_nom_before_failure)` entre métodos bajo mismos pedidos×escenarios.

## Muestra y preflight

- Manifiesto: `sample_manifest.json` (sha256 `{protocol["sample"]["manifest_sha256"]}`).
- Preflight: pedidos `{protocol["preflight"]["orders"]}`, escenario `sens_mid`, métodos M0–M3 → **8** episodios.
- Techo: 100 s/episodio, 900 s global; sin reintentos selectivos.
- `absolute_independence=false`. Test de learning_objectives no usado.

## Presupuesto G2 completo

Máx. 120 episodios (10×3×4). Techo no ampliado en silencio. Coste pared: estimar tras preflight con incertidumbre explícita; no extrapolar desde G1 sintético.

## Hashes de código (pertinente)

"""
    for rel, h in sorted(code_hashes.items()):
        md += f"- `{rel}`: `{h}`\n"
    md += f"\nDataset sha256: `{manifest['dataset_sha256']}`\n"
    (STUDY / "g2_protocol_frozen.md").write_text(md, encoding="utf-8")
    print(json.dumps({"wrote": str(out_json), "content_sha": protocol["protocol_content_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
