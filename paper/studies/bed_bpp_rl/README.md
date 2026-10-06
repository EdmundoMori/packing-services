# BED-BPP-RL

**Estado R03-preparación:** contraste de artefactos verificado + preflight real
diseñado (static-only). Decisión:
`preflight_real_disenado_y_contraste_de_artefactos_verificado`.

## Artefactos clave

| Ruta | Rol |
|------|-----|
| `tools/artifact_contrast.py` | Contraste identidad/orientación/rewards/cierre |
| `preflight_real_protocol.json` | Protocolo operativo (no ejecutado) |
| `tools/run_preflight_real.py` | Ejecutor (`--static-only` autorizado aquí) |
| `reviews/R03_preparation_preflight_and_artifact_contrast.md` | Revisión |

## Comandos

```bash
# Pruebas sintéticas
python3 -m pytest paper/studies/bed_bpp_rl/tools/test_r02_synthetic.py \
  paper/studies/bed_bpp_rl/tools/test_r02a_integrity.py \
  paper/studies/bed_bpp_rl/tools/test_r03_artifact_contrast.py \
  paper/studies/bed_bpp_rl/tools/test_r03_preflight_design.py -v

# Preflight static-only (no empaqueta pedidos reales)
python3 paper/studies/bed_bpp_rl/tools/run_preflight_real.py --static-only \
  --protocol paper/studies/bed_bpp_rl/preflight_real_protocol.json
```

## Preflight futuro (no autorizado en R03-prep)

```bash
python3 paper/studies/bed_bpp_rl/tools/run_preflight_real.py \
  --protocol paper/studies/bed_bpp_rl/preflight_real_protocol.json \
  --orders <BED_BPP_JSON> --out <CORPUS_DIR>
```
