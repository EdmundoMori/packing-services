# Revisión 02 — G1 integridad sintética

**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2`
**Rama:** `research/paper-online-packing`
**Alcance:** solo G1 sintético. Sin BED-BPP, PPO, G2, commit, push.

## Contrato de tres eventos

| Evento | Efecto |
|--------|--------|
| `no_candidate` | Fin; conserva \(V_{\mathrm{nom}}\) parcial; no es fallo geométrico |
| `envelope_exceeded` | Registro; **continúa** si no hay solape/salida; ocupación ← realizado |
| `geometric_failure` | Fin sin recovery; Obj-B = 0 |

## Implementación

- `tools/geometry_contract.py` — dims/margen/envelope/certificado
- `tools/info_separation.py` — `PolicyObservation` vs `SimulatorTruth`
- `tools/adapters.py` — candidatas por envolvente; commit de realizado; rebuild
- `tools/episode.py` — transición y \(J_B\)
- `tools/baselines.py` — cero / uniforme / por eje (suministrados)
- `tests/test_g1_synthetic_integrity.py`
- `results/g1_preflight.json`

## Ocupación

Tras éxito (con o sin exceso de reserva), se hace `commit` del AABB **realizado** (mismo FLB). Rebuild desde revelados verifica equivalencia; bloqueo si no reinserta (no se aproxima).

## Filtración

El chooser solo recibe `PolicyObservation` + `PolicySessionView`. No recibe `SimulatorTruth`. El realizado se consulta **después** de fijar la pose.

## Limitación documentada (no silenciosa)

Con FLB compartido e inflación solo en +ejes, un `envelope_exceeded` tras candidata de envolvente factible frente a revelados **raramente** produce solape con cajas previas en el generador EP (el protrusión cae en espacio libre +). El solape se cubre con prueba unitaria del validador; la salida de contenedor cubre fallo geométrico por exceso en integración.

## Pruebas y preflight

- Pytest: 27 passed
- Preflight: ver `results/g1_preflight.json` (límite 120 s)

## Decisión

**`integridad_sintetica_verificada_para_disenar_G2`**

No autoriza ejecutar G2, RL, muestreo, commit ni push.
