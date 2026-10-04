# Revisión del ajuste de los dos brazos

Campaña única en `learning_training/`. Estado: `completed`. Tiempo de pared: 12.080205690996081 s. HEAD `83b5e1c59808bd761f4c6fc47234c7dc232468d1`. Protocolo congelado `5fd74cc0a6fc52aaf248a977934d9e199919096aa82c3ae6b0309a03e6aa6946`.

El ranking describe la elección entre candidatas ya etiquetadas. No es una mejora de episodios completos ni una verificación de estabilidad física. `physical_stability_verified` sigue `null`. La puerta de packing no se aplicó. Ninguna semilla queda elegida como representante. Las pérdidas de los dos brazos tienen definición y escala distintas; no se comparan entre sí.

Una carpeta anterior, `learning_training_aborted_missing_checkpoint_dir/`, se detuvo antes de guardar modelos. No forma parte de esta campaña y no se reintentó.

## Integridad y señal

Las entradas no cambiaron respecto del manifiesto. Etiquetas `results.json`: `a24af62fbe3bcb4bc6ba0e87b19a9f5b4124673fb53bbf38878cf91b2ab9beb3`. Normalización: `9b8302649364dc7b2e3f3e73d19ac648d625754e7286a8230d7e8596c30897e3`. Dataset: `6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc`.

Conteos: 24 pedidos de train y 12 de development; 96 y 48 estados; 368 y 185 filas candidatas. Todos los estados están completos. No hay claves duplicadas ni `Q_hat` desconocidos. Las medias y escalas salen de las 368 filas de train y se aplicaron una sola vez.

El diagnóstico descriptivo está en `learning_training/signal_diagnostic.json`. Pares y filas no son pedidos independientes. Esas cifras no modificaron pérdidas, datos ni hiperparámetros.

| Split y target | Estados | Todos los Q_hat empatados | Algún par no empatado | Pares empatados | Pares no empatados | Varias candidatas en el máximo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train euro-pallet | 48 | 29 | 19 | 201 | 74 | 36 |
| train rollcontainer | 48 | 14 | 34 | 124 | 134 | 31 |
| development euro-pallet | 24 | 15 | 9 | 103 | 35 | 20 |
| development rollcontainer | 24 | 5 | 19 | 56 | 75 | 13 |

Tras la normalización, `item_can_rotate` y `bin_index_n` quedan constantes en 0 en train y en development. El resto de las 17 columnas varía. Las dos constantes se conservaron.

## Configuración efectiva

El anexo `training_operational_annex.md` (`ec86bf0f8948caeef59daea33b2291f6cace243e6d6b39670d398721a0e732f8`) fija, sin reescribir el protocolo, lo que el protocolo dejaba sin separar del emparejamiento: un paso de Adam por época, media aritmética de las pérdidas de los 96 estados de train, y el orden de esa suma dado por 40 permutaciones de `torch.randperm` con un generador de CPU inicializado en la semilla. La permutación solo ordena la suma.

Adam: `lr=0.001`, `weight_decay=1e-4` acoplado, `betas=(0.9, 0.999)`, `eps=1e-8`, `amsgrad=false`, `foreach=false`, `fused=false`, `maximize=false`, `capturable=false`, `differentiable=false`. Recorte de gradiente: norma 2, máximo 1.0, error si no es finito. CPU, un hilo de Torch y uno de interoperación. Red `Linear(17, 64) → ReLU → Linear(64, 1)`, última capa a cero. 40 épocas, sin early stopping. El checkpoint es la época 40. La validación no elige época, semilla ni configuración.

## Los seis ajustes

Los seis terminaron. No hubo valores no finitos en pérdidas ni en normas de gradiente. Cada historial tiene las épocas 1 a 40. El tiempo se registra por semilla, con los dos brazos seguidos; el campo por brazo queda vacío.

| Semilla | Segundos | Inicialización | Permutaciones |
| --- | ---: | --- | --- |
| 11 | 5.28765314300108 | `c4326a66218dd60ce82e33f2b7c4e1a133b0a4c71b228f5fcceb5732c9d55986` | `584124bb6002f76fd9936a0858637ac2b69530b48f054fe3c2848ebf63c6f3a3` |
| 23 | 3.385094621000462 | `21bbf716a5921206b75445ca2c4910ecdca7223d53ff8c5f85997601fc3a199d` | `cf6c3533f89a6f260564297d2f9a3cc4bb6d1e7631261da3cc06f4ebce7a7a54` |
| 37 | 3.2515199250046862 | `f0c759532d7cd33d62e5c2b57cc66bf42d49e2da5e6fabdc25c0b9943c3ebce7` | `26536b7bd868e1228e027cda9d0183a6410b05629f963eec0d877f30ec2ca8ae` |

Antes de cada pareja se copió una inicialización común y se exigió igualdad exacta de los tensores. Si esa copia falla, esa semilla no empieza y la campaña queda incompleta. Aquí las tres parejas arrancaron. Los archivos `pairings/seed_*.json` guardan el registro previo al primer paso de esa semilla: hash, permutaciones y el estado `pending` de ese momento. El cierre de cada pareja está en `campaign.json` y `runs.json`. Los pesos finales no tienen por qué coincidir.

## Ranking de development

Regret medio primero dentro de cada pedido y después con igual peso por pedido. La candidata es la de mayor logit. Un empate exacto de logits se resuelve por el menor índice original. En estos seis modelos no hubo empates de logit. 33 de los 48 estados de development tienen varias candidatas que comparten el máximo de `Q_hat`.

| Brazo | Semilla | Regret | Euro-pallet | Rollcontainer | Coincide con algún máximo |
| --- | ---: | ---: | ---: | ---: | ---: |
| classification | 11 | 0.015052534412202381 | 0.004867643229166667 | 0.025237425595238092 | 33/48 |
| classification | 23 | 0.017719938926091267 | 0.0068592230902777785 | 0.02858065476190476 | 31/48 |
| classification | 37 | 0.013933372085813493 | 0.006045203993055558 | 0.021821540178571425 | 33/48 |
| preferences | 11 | 0.01693572668650794 | 0.006237152777777782 | 0.027634300595238095 | 32/48 |
| preferences | 23 | 0.016673668464781747 | 0.004053624131944447 | 0.029293712797619043 | 32/48 |
| preferences | 37 | 0.01949079086061508 | 0.005510525173611114 | 0.033471056547619046 | 29/48 |

Cada target aporta 6 pedidos. Estas cifras no autorizan episodios nuevos.

## Hashes de los checkpoints

Cada archivo es la época 40, contrato `counterfactual-actor-v1`, con la normalización de train. Recargar el estado y evaluar el primer estado etiquetado de cada pedido de development reproduce los logits guardados en el historial.

| Checkpoint | SHA256 |
| --- | --- |
| `classification_seed_11.pt` | `6a5181fc303867c396048a66d5e84e290bd7926acb89a2a52db9e9a26bf7f647` |
| `classification_seed_23.pt` | `a7bc0e0e237d10587e9dd0bb6657aabd756975b665db27357b9d8a6e141de282` |
| `classification_seed_37.pt` | `169c2494ad124681aff2332b0872529b6b5e8c2812ead76fb37acdc93b558dbb` |
| `preferences_seed_11.pt` | `101ceaead264699be75283bef9e7ef62c4a8ae139316be370c2d4463975da617` |
| `preferences_seed_23.pt` | `3e646e889446ee00592816c895d39c7f48bba1318fc046bc578a958149b9db62` |
| `preferences_seed_37.pt` | `94c532b5dd57e936d9b797b1f5e10bd0bfd4f37964898b03f88f31f7ef2c0223` |

El código del ajuste coincide con el manifiesto: `actor_features.py` `a4350efa432efbc1a5059398a643a4e25e4be7bdd7e6de5c0938514ffd875291`, `objectives.py` `ec738b4925fcf02eac0b7cf314a94e332efb179d28df28d0ff56441a21e5dc73`, `model_spec.py` `a027b4f4a1324523cbc0db1296beba2c1a8b33ca50eb55d658967f9b3a735d2a`, `train_loop.py` `60b782aa6fa6505a5de3cd4f3f128ed4d0bedfa6dc9d8a64d92d00f50b10b31b`, `run_learning_training.py` `69245378470b83dbc5d6f8eb58113c7d2fa2e750bf87e994aca7a4f3aec21950`.

## Pruebas

`paper/tests`: 122 pruebas, OK. `paper/studies/counterfactual_ranking/tests`: 45 pruebas, OK. La segunda suite avisa al convertir un tensor con gradiente en `test_learning_pilot.py`. Las pruebas sintéticas cubren pérdidas y gradientes finitos, empates, dirección de la preferencia, peso por estado, igualdad inicial, permutaciones, normalización aplicada una vez, época 40, rechazo de un directorio de salida ya existente y reproducción de logits al cargar un checkpoint. No usan los pedidos reales para cambiar el ajuste.
