# 15 — Publicación de la capa de recuperación

Publica código, pruebas, forense corregido y plan **antes** de ejecutar el intento 02.
No incluye `learning_labels/` ni resultados de recuperación.

Correcciones forenses: causa/exit desconocidos; no atribuir SIGKILL/sandbox/OOM;
214.80… s = tiempo registrado, no cota demostrada; reserva operativa 120 s;
span de artefactos ≈216.7 s.

`--execute-recovery` quedó rechazado de forma deliberada en el paso solo-plan;
ahora el CLI cablea `run_recovery_attempt`.
