# 12A — contrato del packing de la ablación

Corrección del 2026-10-03 sobre `6921fc0f528a7026f7c528fb602327f3d5109bcf`, rama `research/paper-online-packing`. Los diez modelos del paso 12 siguen publicados. Este paso no empaqueta, no entrena, no hace commit y no hace push.

El packing anterior corría los 550 casos dentro del proceso padre y detenía la etapa ante la primera excepción. El contrato corregido usa un proceso por caso.

## Timeout, continuidad y contraste

Cada caso llama a `invoke_worker` con un intento y un timeout de 300 segundos. El entorno del proceso deja `CUDA_VISIBLE_DEVICES` vacío. El worker fija `torch.set_num_threads(1)` y `torch.set_num_interop_threads(1)` una vez.

Un crash, un timeout, una salida distinta de cero o un JSON ilegible dejan una fila de fallo con `U_geom` efectivo 0 y el bucle sigue. No hay un segundo intento. Un error interno del evaluador —preflight, snapshot ausente, agregación o escritura del manifiesto— marca la corrida `incomplete`, conserva el mensaje y no lo convierte en un cero silencioso.

Antes de lanzar workers, el preflight compara los diez hashes con `training_verification.json`, lee brazo y semilla del contenido de cada artefacto, y comprueba protocolo, congelado y estadísticas. Construye un snapshot de entrada por pedido y exige que la heurística y el actor compartan la geometría. El nombre del archivo no sustituye esa lectura.

`evaluate_outcome` recibe ese snapshot. Una discrepancia de entrada, geometría o peso pone `U_geom` efectivo en 0. Las dimensiones orientadas, las identidades, los pesos y las restricciones salen de la captura. `yaw` y la bandera `feasible` del motor no certifican la solución. `physical_stability_verified` permanece `null`. Un empaquetado parcial válido, con ítems sin candidato legal, no es un fallo de método.

Por caso se guardan `input.json`, `worker.json`, `capture.json` cuando el worker entrega captura, `audit.json` y `result.json`.

## Agregación y procedencia

La regla de avance sigue siendo la congelada: media de normalizado menos raw mayor que cero, diferencia positiva en al menos cuatro semillas, y media de normalizado menos heurístico mayor que cero. Hacen falta exactamente 550 claves: 50 heurísticas y 500 casos de pedido, brazo y semilla. Una clave ajena, un duplicado o un valor no finito rechazan la agregación. Los fallos permanecen en el denominador. Las cinco semillas no se cuentan como pedidos distintos.

El manifiesto de entrenamiento conserva el hash del código que entrenó. El manifiesto de packing, cuando se ejecute, registrará por separado el hash del código corregido. Los hashes de los diez modelos no se reescriben. No se reentrena para igualarlos.

## Pruebas

`python -m unittest discover -s paper/tests -p 'test_*.py'` terminó con 93 pruebas en verde. `git diff --check` no reportó espacios finales en el diff rastreado.

Las pruebas nuevas usan workers simulados, un pedido sintético de dos ítems y checkpoints sintéticos. Comprueban timeout y continuación, crash, salida distinta de cero, JSON ilegible, snapshot discrepante, captura conservada, artefacto con hash, brazo o semilla incorrectos, las 550 claves y la presencia de los fallos en la media. Los hashes de los diez `.pt` publicados se comparan con la verificación sin cargarlos. No hay forward de esos modelos ni packing de los 50 pedidos.

## Comando futuro

No se ha lanzado. Cuando un paso lo autorice:

```bash
cd /home/edmundo/packing-services
CUDA_VISIBLE_DEVICES= /home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_normalization_ablation.py pack --protocol /home/edmundo/packing-services/paper/protocols/10_normalization_ablation.json --freeze /home/edmundo/packing-services/paper/results/10_normalization_freeze.json --run-dir /home/edmundo/packing-services/paper/results/11_normalization_ablation --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json
```
