# Cierre de campaña: learning_objectives (configuración controlada)

**Decisión:** `no_avanzar_con_esta_configuracion`
**Test:** cerrado (no ejecutado)
**HEAD de cierre:** `ee9e0ec854c303d14d54b5be342558645777cb0a` (evaluación completa); commit de publicación pendiente en este paso.

## Pregunta

Bajo contrato geométrico fijo, encoder compartido de 17 características, soporte
$S$ compartido, etiquetas compartidas y presupuesto de optimización compartido,
¿cómo afectan la clasificación, las preferencias pareadas y la diferencia de
retorno a la utilización geométrica de episodios completos?

**Contraste principal (congelado):** media a nivel pedido (tras media de semillas
emparejadas) de preferencias−clasificación en $U_{\mathrm{geom}}$ de episodio.

## Protocolo e integridad

- Protocolo y muestra congelados; nueve modelos época 40 sin selección por development.
- Evaluación development autorizada: **240** claves únicas, **24** pedidos, **0** test.
- **8** claves reutilizadas una vez del smoke auditado; **232** ejecutadas en
  `dev_full_ee9e0ec854c3_20261005T174540Z`.
- **240/240** capturas con auditoría geométrica; **0** fallos de método, arnés o evaluador.
- $U_{\mathrm{geom}}$ recompuesto desde capturas coincide con resultados registrados.
- Agregación: media de semillas dentro del pedido, luego media igual entre pedidos.
- Empates W/T/L: tolerancia `1e-9` (`TIE_EPS`).

## Resultado algorítmico (cifras exactas, agg. pedido←semilla)

| Contraste | Media | Mediana |
|---|---:|---:|
| preferencias − clasificación | −0.008075238586102845 | −0.010981250000000015 |
| preferencias − Greedy | −0.05163430240368717 | −0.048369419642857125 |
| clasificación − Greedy | −0.04355906381758432 | −0.03153560267857145 |
| return_difference − clasificación | −0.0036117077701306286 | −0.005355175781250018 |
| return_difference − Greedy | −0.04717077158771495 | −0.037052083333333354 |

**Por target (pref−class):** euro-pallet −0.02995039966724537; rollcontainer +0.01379992249503968.

**Por semilla (pref−class, media pedido):** 11 → −0.026016768973214286; 23 → +0.013023960270957341; 37 → −0.011232907056051589.

Ambos brazos aprendidos quedan **por detrás de GreedyBestFit** en episodio completo
(pref−Greedy y class−Greedy negativos). El brazo secundario return_difference no
rescata la puerta.

## Puerta de development (no cumplida)

1. media pref−class ≥ 0.005 → **no**
2. positiva en ≥ 2 semillas → **no** (solo semilla 23)
3. agregado ≥ 0 por target → **no** (euro-pallet negativo)
4. evaluación completa y auditada → **sí**
5. saldo global de campaña ≥ 9000 s reservados para test → **sí** (~25828.43 s contabilizados; ver presupuesto)

No se abre test con esta configuración. No se elige semilla, brazo, pérdida nueva ni presupuesto adicional.

## Límites (sin causalidad atribuida)

- **Piloto exploratorio previo** (otro estudio, otro soporte/muestra): margen pref−class positivo aproximado **no reproducido** aquí.
- Muestras, soporte $S$ acotado, etiquetas sobre trayectorias greedy y **22** pedidos development distintos impiden atribuir el cambio a una sola causa (pérdida, target o pasos Adam).
- Presupuesto fijo de pared **no** demuestra convergencia comparable entre pérdidas.
- Contrato geométrico compacto; `physical_stability_verified=null`.
- **Sin evaluación test** independiente final: generalización fuera de development no establecida.

## Incidente operativo (no resultado científico)

El primer lanzamiento de 240 claves falló por intérprete venv (`Path.resolve`); artefacto
conservado en `learning_development_eval/` **excluido** de contrastes de packing.
Corregido antes del smoke y la evaluación íntegra.

## Artefactos reutilizables

| Artefacto | Uso |
|---|---|
| `learning_models/` | 9 checkpoints época 40 |
| `learning_development_eval_full/` | 240 episodios auditados |
| `learning_development_smoke_8/` | Procedencia de 8 claves reutilizadas |
| `learning_development_eval/` | Evidencia operativa fallida (no packing) |
| `forensics/campaign_closure_verification.json` | Verificación numérica final |
| `forensics/development_eval_full_independent_review.json` | Revisión independiente |

Nuevas campañas no autorizadas en este cierre.
