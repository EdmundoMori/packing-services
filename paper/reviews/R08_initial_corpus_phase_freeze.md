# R08 — Congelación de la fase del corpus inicial

Siete pruebas sintéticas correctas, incluida integración supervisada.
Muestra y dataset contrastados; 217 archivos de implementación hasheados.

## Alcance congelado
Solo corpus inicial: 16 pedidos train, cuatro políticas, 64 episodios.
600 segundos, ejecución serial, un intento por clave y sin reinicio automático.
PPO y evaluación no autorizados.
No se ejecutaron pedidos industriales durante esta preparación.

## Hashes
Archivo: bcbe18d24025431fb6547349ebce184e7f9806fbb2210e7695fdeb1913a57c04
Digest interno: 82e5881b365587a47020fcec5bef9c5df055015029183187942ef6bb570b2058

## Lectura del informe
protocol_frozen=false corresponde al informe de preparación de la campaña
completa. El archivo nuevo declara frozen_corpus_only y authorized_phase
initial_corpus. La validación del archivo, no ese campo heredado, determina
el alcance congelado.

## Límites
Presupuesto industrial todavía no demostrado.
AABB no verifica estabilidad física.
No se afirma mejora de política, novedad ni publicabilidad.
