# Revisión de la congelación

El borrador y el preflight quedan intactos. El protocolo operativo es `protocol_frozen.json`, SHA256 `e8fafb399a59863fc7a03f011b91f93e22af78f3a0d7aa78520c4a9e035717c1`. Ese hash se calculó antes de cualquier continuación nueva. El borrador conserva SHA256 `cda879555db890f9108e4fb495cfaa7d1881bd61fa4f3e18ce950f3ca5ca84a6`. No se exige igualdad literal.

## Equivalencia semántica

Coinciden la pregunta, el contrato geométrico, la observabilidad privilegiada, la muestra y su hash, el dataset `6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc`, la regla de selección, la definición de `Q_hat` y los límites de análisis.

Diferencias operativas, aceptadas:

- El borrador sigue diciendo que el preflight no se ha ejecutado, porque ese archivo no se reescribe. El congelado registra dos pedidos y cuatro retornos ya observados.
- El presupuesto del borrador estaba pendiente. El congelado acepta el presupuesto truncado: 14400 segundos con el preflight incluido, 60 segundos de continuación y 60 de captura y auditoría, sin afirmar que el peor caso quepa en ese reloj.
- La puerta que estaba propuesta se adopta con denominadores explícitos. Los umbrales son los anteriores al preflight.
- El estudio queda declarado como exploratorio de desarrollo. Cumplir la puerta no garantiza que el margen sea aprendible ni autoriza entrenar.

## Preflight

Archivo `preflight_results/preflight.json`, SHA256 `b0fb7cd9958202c8cec7e90170bbc9c6b177ed49b5ec03ed75abefd8c47e3dfd`.

El tiempo recuperable es `startup_seconds + work_wall_seconds` de ese JSON. Si faltara, la campaña reservaría 11 segundos y lo declararía incierto. El código de continuación que produjo esas cuatro capturas sigue siendo el de `diagnostic.py` `8d95f84c50b15a46dcf361a303889be18ba6b8487f605f28c850fa0012f9d4aa`. La campaña nueva vive en `campaign.py` y `run_diagnostic.py` y no sustituye ese código.

Antes de continuar, el ejecutor comprueba las capturas sin empaquetar y el estado vivo de `00109938` y `00105640`. Si el estado, el sufijo o las dos acciones ya evaluadas no coinciden, se detiene sin casos nuevos.
