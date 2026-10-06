# Evaluación de publicabilidad (sin promesas)

Distingue tres planos que **no** deben confundirse:

## (a) Coherencia técnica del manuscrito

El borrador describe de forma auditable la pregunta, el protocolo congelado, el
encoder de 17 features, el soporte $S$, las pérdidas ejecutadas, el entrenamiento
(40 pasos Adam full-batch, sin selección de época/semilla/brazo por resultados) y
la evaluación **development** (240 episodios). Los incidentes de arnés están en
reproducibilidad, no como explicación causal del contraste algorítmico.

## (b) Alcance de las afirmaciones respaldadas

Sí, para afirmaciones **limitadas a esta configuración development**:

- preferencias no supera a clasificación en el contraste primario (media ≈ −0.00808);
- ambos brazos aprendidos quedan por debajo de GreedyBestFit en $U_{\mathrm{geom}}$
  de episodio en development (dato descriptivo; la puerta congelada
  **no** exige superar a Greedy);
- la puerta de continuity **no** autorizó abrir el test de este protocolo.

No, para superioridad general, comparación con PCT, ni generalización fuera del
conjunto development. La geometría AABB válida **no** implica estabilidad física;
si el manuscrito solo reporta $U_{\mathrm{geom}}$ bajo contrato compacto, no hace
falta “demostrar estabilidad física” como requisito de esas afirmaciones.

## (c) Novedad, relevancia y adecuación a un venue

**Todavía no establecidas.** Un informe empírico controlado (incluido un resultado
negativo o no concluyente en development) puede ser técnicamente coherente sin
estar listo para un venue concreto. Superar una heurística, obtener un margen
positivo o ejecutar un test adicional **no** son requisitos universales de
publicación; son condiciones de *otras* afirmaciones o de *este* protocolo de
continuidad experimental.

El test permanece **cerrado** conforme al protocolo y a la puerta. No se propone
abrirlo para “rescatar” la publicación. Ampliar afirmaciones de generalización
exigiría una evaluación independiente **autorizada**; eso no autoriza
experimentación nueva en este cierre.

**No se garantiza publicación en revista.** Este documento archiva el alcance;
no lanza otra campaña.
