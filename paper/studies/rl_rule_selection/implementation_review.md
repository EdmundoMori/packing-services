# Revisión de implementación

Se inspeccionaron el motor, la máscara, el contrato compacto, el encoder del estudio cerrado, el entrenador PPO histórico y el adaptador OnlineBPH. No se modificó ninguno.

## Se reutiliza

- `paper/tools/compact_study.py`: banderas del contrato, `p = 1`, `s = 1`, secuencia original, un contenedor, parada en el primer ítem sin candidata y construcción del problema compacto. El archivo no se edita.
- `ExtremePointOnlineSession.candidates` y `ValidatorMask.allows`: la lista legal es la misma para las tres reglas.
- `GreedyBestFitPolicy`: con `p = 1` la ventana no aporta otros ítems, `look = 0` y la clave es `rank_key`. La acción 0 reproduce el plan de `run_compact_greedy` en la prueba sintética.
- `capture_document` y `audit_document`: la captura sintética pasa contención y no solape. `physical_stability_verified` queda `null`.
- `paper/tools/online_bph_case.py`: baseline externo ya aislado. Se usará más adelante bajo el contrato de captura del paso 16A. Este paso no lo ejecuta.

## No se traslada

El entrenador `online_policy_ml/src_ml/train_ppo.py` y su configuración no sirven como receta de esta campaña.

- Terminación: el bucle de producción descarta el ítem imposible y sigue. El contrato compacto se detiene y deja el sufijo sin colocar.
- Observabilidad: el encoder histórico tiene 35 dimensiones y el actor del estudio cerrado, 17. El crítico histórico usa cinco entradas, incluida la cantidad de ítems restantes. La observación nueva tiene 36 dimensiones, sin sufijo, sin identificadores y sin ese contador.
- Recompensa: la receta histórica suma volumen, soporte y penalización de altura, con coeficientes 0.15, más una penalización por ítem no colocado, y `gamma = 0.99`. Aquí la recompensa es solo volumen colocado sobre volumen del contenedor y `gamma = 1`.
- Crítico y retornos: el crítico histórico no se exporta y el objetivo incluye una KL hacia el actor de clonación de comportamiento. Aquí el crítico tiene parámetros propios y el retorno con `gamma = 1` es la suma de recompensas, igual a `U_geom`.
- Inicialización: no se carga ningún `.pt` histórico. El sesgo `[1, 0, 0]` de la última capa está fijado en el borrador.

`compact_selector_view` sigue siendo la vista de auditoría del selector compacto. No es la observación de esta política.

## Qué queda implementado

Propuestas de las tres reglas, observación, entorno con `reset` y `step`, captura auditable, pruebas sintéticas y el ejecutor de preflight. El ejecutor con pedidos reales termina con código 2 mientras el protocolo siga en borrador.

## Qué queda fuera

No hay muestra materializada, ni rollouts de pedidos BED-BPP, ni actualización PPO sobre esos pedidos, ni evaluación OnlineBPH, ni test final.
