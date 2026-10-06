# Errata — ``recipe.actor_eval_mode`` en ``learning_development_eval_full``

**Fecha:** 2026-10-06
**Campaña:** `paper/studies/learning_objectives/learning_development_eval_full/`
**HEAD de documentación:** `2859678a00dd13f0141462085389a0f9da29da2d`
**No reescribe:** capturas, manifiestos, resultados, checkpoints ni protocolos.

## Hallazgo confirmado

En las **216** capturas de brazos actor (no-greedy) el campo
`recipe.actor_eval_mode` vale **`false`** en el 100 % de los casos (también en
las 24 greedy). Total de capturas del directorio: 240.

## Valor registrado vs comportamiento respaldado por código

| Plano | Contenido |
|-------|-----------|
| Valor registrado | `actor_eval_mode: false` en las 216 capturas de actor |
| Construcción histórica del campo | `paper/tools/pilot_problems.py`: `"actor_eval_mode": method == "actor"` |
| Método usado por el ejecutor LO | `episode_worker.run_problem(..., method=arm)` con `arm` ∈ {`classification`, `preferences`, `return_difference`, `greedy`} — **nunca** la cadena `"actor"` |
| Comportamiento del código de política | `paper/studies/learning_objectives/tools/actor_policy_s.py`: `self.model.eval()` en `__init__` y `torch.no_grad()` en el forward de `decide` |

Mecanismo: el metadato se **infirió del nombre del método** (`method == "actor"`),
pensado para el piloto que usaba method="actor". El worker de development
pasa el **nombre del brazo** como `method`, de modo que el booleano queda
siempre en falso aunque la política cargada sea `SupportConstrainedActorPolicy`.

## Ausencia de reconstrucción de cada forward

Esta errata **no** reconstruye ni audita cada forward histórico episodio a
episodio. Afirma únicamente:

1. lo que quedó escrito en las capturas;
2. lo que el código de política vigente en la corrida declara hacer al
   construirse y al decidir;
3. el mecanismo de construcción del campo en `pilot_problems.capture_document`.

**No** se deduce que el entrenamiento o el packing fueran inválidos por este
metadato.

## Conservación

Las capturas y hashes de `episode_worker.py` / resultados permanecen intactos.
Para corridas futuras: `capture_actor_eval_metadata_v1.py` +
`episode_capture_metadata_c07.py` asignan el campo de forma **explícita** desde
el ejecutor/política (`model.training`, no el nombre del método).
