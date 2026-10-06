# C08 — Cierre final de mantenimiento, documentación y maquetación

**Fecha:** 2026-10-06
**HEAD de trabajo (pre-commit):** `3aa19b6d1acaa5806068c8bf52d9ab9ca796d66f`
**Rama:** `research/paper-online-packing`
**Decisión:** `mantenimiento_identificado_cerrado_con_limitaciones`

Sin entrenamiento, inferencia, packing real, notebooks ni campañas.
Sin abrir el test ni regenerar resultados históricos.

## Resumen C01–C08

| Paso | Defectos corregidos | Evidencia preservada | Verificación ejecutada |
|------|---------------------|----------------------|------------------------|
| C01 | Afirmaciones documentales vigentes | JSON/cierres históricos | Revisión documental |
| C02 | Semántica `feasible` / geometría AABB | Informes 09/10 no regenerados | Pruebas sintéticas evaluador |
| C03 | Export yaw estricto | Planes históricos intactos | Pruebas yaw |
| C04 | Intercepción EP `_support_z` | Campañas pre-C04 no reevaluadas | Pruebas proyección |
| C05 | Rutas portables / skips de verificación | Protocolos y resultados | Suites afectadas + doc entorno |
| C06 | Manuscritos ↔ evidencia LO/RPM | Protocolos/resultados | Compilación LaTeX |
| C07 | Moncontenedor, IDs, errata `actor_eval_mode` | Capturas/worker hasheado | 51 pruebas C02/C03/C07 |
| C08 | Metadato triestado; tiempo 742.826… s; Overfull; cobertura C05 | Idem | 55 pruebas; compilaciones |

Este cierre cubre los **hallazgos identificados** en la auditoría de mantenimiento.
**No** declara «todo el repositorio certificado» ni agota defectos posibles.

## Correcciones C08

1. **Metadato futuro C07/C08:** `actor_eval_mode` ∈ {True, False, None}
   (eval observado / training observado / evidencia insuficiente). No
   `bool(None)`. Helper no integrado en todas las rutas de captura.
2. **Cobertura portable (C05):** 412/0 es del entorno registrado; skips
   posibles de train transitions sin pickle locales; fixture teacher sintético
   = detector, no dump histórico.
3. **Tiempo development:** unificado a `742.8260259628296` s
   (≈ 743 s) según `campaign_closure_verification.json`; registro original
   intacto.
4. **Maquetación:** `\codepath`/`xurl`/`tabularx`; Overfull hbox eliminados en
   ambos manuscritos tras recompilación. PDF/aux fuera del índice.

## Límites explícitos (definitivos de este cierre)

- Resultados históricos anteriores a C04 (motor EP de episodios publicados).
- Campañas cerradas; **test no ejecutado**.
- Helper de metadatos **futuro** (no afirma integración universal).
- Dataset/artefactos externos y entornos históricos no reconstruidos.
- Geometría AABB ≠ estabilidad física.
- Motor EP simplificado; sin completitud demostrada frente a Crainic completo.
- Novedad y adecuación a venue **no establecidas**.

## Pruebas C08

`test_bedbpp_eval_feasibility` + `test_yaw_export_contract` +
`test_bedbpp_eval_contract_c07` (incluye casos triestado del helper):
**55 passed**.

## Compilación

- LO: pdfLaTeX + BibTeX + pasadas finales → `/tmp/c08_lo_build/main.pdf` (10 pág.);
  sin Overfull residual en el log final; bibliografía resuelta vía `references.bib`.
- RPM: pdfLaTeX → `/tmp/c08_rpm_build/main.pdf` (5 pág.); sin Overfull residual.
