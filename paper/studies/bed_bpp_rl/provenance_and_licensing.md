# Procedencia, reutilización de datos y licencias (R01)

## Qué no es una transición RL

| Artefacto histórico | Uso permitido en BED-BPP-RL | Motivo |
|---------------------|----------------------------|--------|
| Etiquetas `Q_hat` / learning_labels | Antecedente metodológico (continuaciones greedy) | No son `(s,a,r,s')` on-policy del entorno de reglas |
| Capturas `learning_development_eval*` | Antecedente de packing AABB | Actor sobre soporte \(S\); motor pre-C04; no corpus del recurso |
| Capturas `rl_rule_selection/development` | Antecedente del piloto cerrado | Evidencia de campaña; no corpus versionado regenerable bajo R01 |
| Pickle BC / teacher volume | Excluidos | Fuga / semántica distinta |
| Checkpoints PPO producto o piloto | Excluidos como pesos del recurso | MDP/observación/recompensa no transferidos |

## Qué puede servir como antecedente

- Contratos compactos y código de `RuleSelectionEnv` / observación / reglas.
- Hashes de dataset BED-BPP (`orders_sha256`) ya documentados en estudios previos,
  **sin redistribuir** el JSON fuente desde este repositorio.
- Pedidos **ya observados** en campañas cerradas: pueden informar un futuro
  manifiesto de **desarrollo** del recurso; **no** se presentan como test
  independiente. R01 **no** selecciona IDs ni abre el test cerrado.

## Experiencias a generar de nuevo

Toda transición del corpus BED-BPP-RL debe generarse bajo:

1. contrato draft R01 (o su freeze posterior);
2. motor EP post-C04;
3. esquema `corpus_schema_v1`;
4. políticas de comportamiento declaradas y semillas.

## Licencias (distinción obligatoria)

| Capa | Objeto | Nota R01 |
|------|--------|----------|
| Software packing-services | Código del repo | Sujeto a la licencia del repositorio; no se altera aquí |
| Dataset BED-BPP | Fuente externa Kagerer et al. | No redistribuir sin comprobar condiciones de la fuente; citar IJRR 2023 |
| Artefactos derivados | Corpus/experiencias generadas por este estudio | Derivados: su redistribución exige política explícita post-R01; R01 no publica blob de datos |

`physical_stability_verified` permanece `null` en el diseño del recurso.
