# Protocolo congelado del piloto de aprendizaje

Este protocolo queda congelado para generar etiquetas. No entrena. El borrador `learning_protocol_draft.json` se conserva como antecedente. El hash de este archivo es `5fd74cc0a6fc52aaf248a977934d9e199919096aa82c3ae6b0309a03e6aa6946`, calculado el 2026-10-03T19:17:02Z, antes de las continuaciones nuevas.

## Pregunta y alcance

¿Aprender diferencias de retorno entre candidatas mejora el packing frente a aprender solo la identidad de la mejor candidata, con los mismos datos, la misma observabilidad, la misma arquitectura y el mismo motor?

Es un piloto de desarrollo: 24 pedidos de train y 12 de desarrollo, ambos targets equilibrados. El test final no se selecciona ni se consulta. Los 20 pedidos del diagnóstico no entran.

## Entradas

El contrato `counterfactual-actor-v1` tiene 17 columnas, calculadas solo desde el contenedor, el estado ya colocado, el ítem actual y la candidata. El orden y las fórmulas están en el JSON. La altura orientada es la arista vertical de la candidata partida por la altura del contenedor. La altura usada es la máxima z ya ocupada y no incluye la candidata que se puntúa.

Quedan fuera el sufijo, el identificador del pedido, el retorno, la acción Greedy, el conteo de ítems futuros y cualquier rasgo del resultado. El encoder histórico de 35 columnas no se modifica.

La normalización usa la media y la desviación poblacional de las filas candidatas de los estados completos de train. Una columna constante tiene denominador 1. Los dos brazos reciben la misma transformación. Esas medias se calculan después de las etiquetas y no se escriben de vuelta en este protocolo.

## Arquitectura y ajuste, sin ejecutarlo

`Linear(17, 64) → ReLU → Linear(64, 1)`, compartida por candidata. Semillas 11, 23 y 37. 40 épocas. Adam con tasa 0.001, betas 0.9 y 0.999, eps 1e-8, weight decay 1e-4 acoplado al gradiente, sin la variante desacoplada. Clip de gradiente 1.0 en norma 2, y un gradiente no finito aborta esa corrida. CPU, un hilo de Torch y un hilo de interoperación. La primera capa usa la inicialización de `torch.nn.Linear` bajo la semilla; la última capa, peso y sesgo, queda a cero. Un paso por época, sin barajar, con la media aritmética de los estados de train en el orden congelado. El checkpoint es el de la última época. No hay búsqueda ni elección de semilla.

## Pérdidas

La tolerancia de empate es 1e-9. El brazo A reparte el objetivo uniforme entre las candidatas empatadas con el máximo y aplica entropía cruzada contra el softmax, sin temperatura. El brazo B ordena cada par no empatado, aplica `softplus(-(logit mayor − logit menor))`, pondera por el valor absoluto de la diferencia y normaliza esos pesos dentro del estado. Los empates suman la media de la diferencia de logits al cuadrado, con coeficiente 1. Si falta una clase de pares, su término vale 0. La pérdida del estado es la suma. Los dos brazos dan el mismo peso a cada estado.

Esos objetivos no comparten escala. Su comparación no demuestra que toda diferencia se deba solo a la ponderación por magnitud.

## Estados

La trayectoria es Greedy bajo el contrato del estudio. Entre los estados con al menos dos candidatas se toman como máximo cuatro cuantiles, con el redondeo `floor(i*(N-1)/3 + 1/2)` y sin rellenar duplicados. Las candidatas siguen la regla determinista del diagnóstico, con Greedy incluida, y no se añaden después de ver `Q_hat`. Solo un estado con todas las alternativas válidas puede entrenar o evaluar ranking. Un retorno desconocido queda null.

## Puerta

No se aplica ahora, porque no hay actores entrenados. El delta es el `U_geom` del episodio completo, el mismo pedido y la misma semilla, con igual peso por pedido y después por semilla. Se avanza con esta configuración solo si la media de preferencias menos clasificación es al menos 0.005, esa diferencia es positiva en al menos dos semillas, la media de preferencias menos Greedy es al menos 0.01, esa diferencia no es negativa en ningún target, y el evaluador tiene integridad y cobertura. Incumplirla significa no avanzar con esta configuración. No refuta en general el aprendizaje de preferencias. Los umbrales son criterios de ingeniería, no significación ni una prueba de publicación.

## Presupuesto de etiquetas

Como máximo 144 estados y 576 continuaciones. La pared es 14400 segundos e incluye la adquisición de trayectorias, la captura, la auditoría y la escritura. Cada caso tiene 60 segundos para restaurar y continuar y otros 60 para capturar y auditar, subordinados al reloj que quede. El peor caso de esos plazos no cabe en la pared. Si el reloj se agota, se detiene el trabajo nuevo y se registra lo pendiente.

## Límites que se mantienen

Los estados salen de trayectorias Greedy. Solo se examinan hasta cuatro candidatas. El retorno usa el futuro real. El máximo por estado no es el rendimiento de una política. Euro-pallet permanece en los dos splits.
