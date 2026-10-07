# R07 — Adaptador del corpus inicial: comprobación sintética

## Procedencia
HEAD de ejecución: 37d3840e2c518af30fa8fea2f8eb9cc0193daa13.
Siete pruebas sintéticas comunicadas: todas correctas.

## Generación y lectura posterior
Dos pedidos sintéticos, cuatro políticas por pedido.
8 episodios, 16 transiciones, 8 terminaciones, 0 truncaciones.
Verificación posterior desde disco: verified, con las mismas cifras.
Auditoría de identidad, orientación, volumen, contención y no solape.
physical_stability_verified permanece null.

## Recursos registrados
Pared de generación y comprobación: 0.47573242300040874 segundos.
ru_maxrss: 30740 KB, máximo del proceso completo en Linux/WSL;
no memoria incremental ni estimación industrial.
Evidencia: 27 archivos, 159935 bytes, sin temporales.

## Contrato
Tres reglas fijas y selección uniforme reproducible.
Semilla uniforme derivada del ID y la semilla base mediante SHA256.
Registro confirmado con rutas relativas, tamaños y hashes.
Las experiencias de estas políticas no son entrenamiento PPO.

## Límites y decisión
Solo ejecución sintética; entrenamiento y pedidos industriales no ejecutados.
El adaptador bloquea explícitamente ejecución industrial.
Timeout cooperativo: supervisor externo todavía pendiente de integración.
Adaptador sintético verificado para continuar la implementación.
Protocolo industrial sigue sin congelar.
