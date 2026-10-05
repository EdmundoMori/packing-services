# 12 — Alineación manuscrito ↔ código/protocolo

| Afirmación del manuscrito | Código / protocolo / fuente | Estado | Limitación |
| --- | --- | --- | --- |
| Pregunta: objetivos de supervisión con $S$ y contrato fijos | `protocol_frozen.json`, §§1–5 | Alineado | Resultados pendientes |
| Tres pérdidas con fórmulas y $\varepsilon=10^{-9}$ | `losses.py` + `torch_losses.py` | Alineado | Escalas no recalibradas |
| Preferencias ≠ Mandi Eq.\ 13; RD es adaptación | reviews 03, 10, 11 | Alineado | No reproducción exacta |
| BED-BPP = instancias; no eval robótica oficial | Kagerer 2023; contrato compacto | Alineado | Estabilidad null |
| PCT fuera de la comparación experimental | Zhao 2022; §2 y §5 | Alineado | — |
| Estados elegibles + cuantiles | `quantile_sampling.py`, `labeling_states.py` | Alineado | $N$ depende del pedido |
| Train 48 / dev 24 / test 100 | `sample_manifest.json` | Alineado | Alcance, no potencia |
| Contraste primario pref−class | protocolo `metrics.primary` | Alineado | Sin cifras nuevas |
| Puerta de desarrollo de ingeniería | protocolo `gates.development` | Alineado | No es test de significancia |
| Piloto exploratorio ≈0.031 / −0.020 / −0.051 | `results/02_…` | Alineado | No es esta campaña |
| Ejecutor listo; etiquetas no corridas | review 09; state.json | Alineado | Campaña no autorizada aquí |

No se detectó incoherencia sustantiva que bloquee la publicación del ejecutor y las pérdidas diferenciables.
