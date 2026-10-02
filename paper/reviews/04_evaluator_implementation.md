# 04 — evaluador del piloto interno

Origen: `research/paper-online-packing` en `9bf669770b321d3f7686500c6dd1c2b7ef8045d7`. El piloto no se ejecutó. No hubo inferencia, entrenamiento, commit ni push.

## Qué queda implementado

El anexo `paper/protocols/04_evaluator_operational.md` fija el tiempo límite de 300 segundos por método y pedido, una sola tentativa, CPU, el actor sin muestreo y en evaluación según el loader existente, y el orden del manifiesto con el actor antes que la heurística. El tiempo queda como diagnóstico.

`paper/tools/run_internal_pilot.py` conserva el protocolo 03A. Llama a `DRLPolicy3DBPP.run` y a `Online3DBPPHeuristic.run` en procesos separados. La geometría la revisa el auditor interno. El peso colocado se compara con la entrada, y el acumulado con el máximo activo. `feasible` del motor no certifica la solución. `physical_stability_verified` permanece null.

Una solución parcial válida sigue en el resultado. Crash, timeout, geometría inválida o violación de peso dejan `U_geom` efectivo en 0 y permanecen en el denominador de 20. El agregado primario es la media aritmética de los 20 `delta_i`.

## Preflight real

Se ejecutó solo `--preflight-only` el 2026-10-02T16:20:20Z, desde `/tmp`, con rutas absolutas. El directorio de salida no se creó. El checkpoint se hasheó y no se deserializó.

- Dataset fuente y subconjunto de validación quedaron identificados por separado. Sus hashes coinciden con el protocolo, igual que el manifiesto y el checkpoint.
- Los 20 ids, su orden y sus targets coinciden. Hay 13 rollcontainer y 7 euro-pallet.
- La conversión produjo el mismo problema para ambos métodos en los 20 pedidos.

Los 41 tests de `paper/tests` pasaron, con workers simulados y datos sintéticos. `git diff --check` no reportó errores.

## Comando para una corrida posterior

Ese comando no se ha lanzado. El directorio de salida no existe y no debe existir de antemano:

```
/home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_internal_pilot.py --protocol /home/edmundo/packing-services/paper/protocols/03_internal_pilot.json --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --checkpoint /home/edmundo/packing-services/online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt --output-dir /home/edmundo/packing-services/paper/results/04_internal_pilot
```

## Lo que sigue fuera de este paso

La reserva confirmatoria no cambia. Los cuatro ids excluidos por precaución siguen fuera. Los 675 candidatos con exposición incierta no se declaran limpios. No se elige N. La estabilidad física sigue sin verificar. Este piloto, cuando se ejecute, describirá esta mezcla de 20 pedidos.
