# G2 — protocolo congelado (antes de packing)

**Estado:** congelado · packing autorizado solo para **preflight 8 episodios**
**HEAD esperado:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2`
**Rama:** `research/paper-online-packing`
**AGENTS.md:** ausente en el repositorio
**protocol_id:** `rpm-g2-frozen-v1`
**content_sha256:** `222601adb186ef53d1df814cc7641dbfb51b2e324ecf2248a50e73ad1e89c7eb`

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
| M3 | menú {0, uniforme, eje}; riesgo 0/1 por factibilidad; desempate suma(m), rank_key | método |

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

- Manifiesto: `sample_manifest.json` (sha256 `b71000ce8f60d435183b4c3c2319d1044391556ec10f9461ec0710e5396fa92f`).
- Preflight: pedidos `['00100030', '00100007']`, escenario `sens_mid`, métodos M0–M3 → **8** episodios.
- Techo: 100 s/episodio, 900 s global; sin reintentos selectivos.
- `absolute_independence=false`. Test de learning_objectives no usado.

## Presupuesto G2 completo

Máx. 120 episodios (10×3×4). Techo no ampliado en silencio. Coste pared: estimar tras preflight con incertidumbre explícita; no extrapolar desde G1 sintético.

## Hashes de código (pertinente)

- `tools/adapters.py`: `22070d6e9c3feb200d6fe8e0ec532eb03de08f1ece2015ae99ea288068ab3950`
- `tools/baselines.py`: `db35c364fa7ba4ab8b3f1a17f5daaf6711d87730e9759899b23c4b676a2f53ff`
- `tools/bedbpp_episode.py`: `8c227c6e1ccd31967b7493baadc415edd708fd5fecba0d34d893f442936b1d85`
- `tools/episode.py`: `285d1ef8a050100aa38bf3d4ec4d1b02523416aa3674a67c979013875b6dd588`
- `tools/error_model.py`: `8fab70835f00c58c7b3c4812f3d87cc277156b506f133841cb8649f602370c4b`
- `tools/freeze_g2_sample.py`: `ea8651a5047ad57e0fe08ba018b92b615704d0665577879adc7d5fb416953944`
- `tools/geometry_contract.py`: `8d2e3925a688e4ff45ccc6f2208b92b3983d77d23c81153daea4625a814f2176`
- `tools/info_separation.py`: `faacb798f8497222d5029dff92186e797a77b2953cc884a6abe3884785db6578`
- `tools/methods_g2.py`: `e3d203945ec63cacc0b7d19d18a002b7753596ce29a20be0af0bca64adafe85c`
- `tools/run_g2_episode.py`: `43da0c75a3c13319bc549c9e48f9602f74ae705f5ea8822160d80ae9e0f6e7db`
- `tools/run_g2_preflight.py`: `35319e6eb3581813ecccecc4012ee2eec4cef622c69e3f390266b81fe6a8fef0`
- `tools/verify_g2_preflight.py`: `5ffce7e7b806b29c23f9defc3ebc7a57e990fc2cf55f75e344c2f0e4ddd4781c`

Dataset sha256: `6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc`
