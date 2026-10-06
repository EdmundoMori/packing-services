# BED-BPP-RL

**Ejes:** BED-BPP + aprendizaje por refuerzo.

**Estado:** R03-preparación (contraste de artefactos + preflight diseñado).
Decisión:
`preflight_real_disenado_y_contraste_de_artefactos_verificado`.

El preflight con políticas fijas/aleatorias es validación **operativa previa**,
no el resultado final del artículo. La demostración PPO mínima en CPU
(experiencias nuevas, train/eval separados) queda **pendiente** tras ejecutar y
revisar el preflight real. No se abre entrenamiento ahora. Las pruebas del
exportador o heurísticas **no** sustituyen esa demostración.

## Capas del recurso

1. Entorno BED-BPP para interacción RL (`BedBppRlEnv`).
2. Corpus de transiciones verificable.
3. Demostración RL (PPO CPU) — pendiente.
4. Resultados/limitaciones comprobados hasta ahora (sintético + diseño).

## Comandos actuales

```bash
python3 -m pytest paper/studies/bed_bpp_rl/tools/test_r02_synthetic.py \
  paper/studies/bed_bpp_rl/tools/test_r02a_integrity.py \
  paper/studies/bed_bpp_rl/tools/test_r03_artifact_contrast.py \
  paper/studies/bed_bpp_rl/tools/test_r03_preflight_design.py -v

python3 paper/studies/bed_bpp_rl/tools/run_preflight_real.py --static-only \
  --protocol paper/studies/bed_bpp_rl/preflight_real_protocol.json
```

## Siguiente paso (aún no ejecutado aquí)

Preflight real cerrado y verificado: 16 episodios, 648 transiciones.
Ver `reviews/R03_real_preflight_closure.md`.
Siguiente: revisar `corpus_and_ppo_design_draft.md` e implementar los
ejecutores antes de generar el corpus o entrenar.
