# Matriz de novedad — antecedentes verificados

**Alcance de la búsqueda:** fuentes primarias listadas por el protocolo más trabajos posteriores localizados por búsqueda.
**Regla:** si no se pudo leer el texto primario, se marca `no verificado`. No se afirma que un problema esté irresuelto solo porque no apareció en la búsqueda.

## Resumen de contraste de incertidumbre

| Trabajo | Tipo de incertidumbre | ¿Selecciona margen geométrico adaptativo como decisión de gestión? |
|---------|----------------------|---------------------------------------------------------------------|
| GOPT (Yang et al., arXiv 2409.05344v2) | Error de medición en robot real | Buffer fijo en experimento; no política RL de margen |
| BED-BPP (Kagerer et al., IJRR) | Tolerancias dimensionales en datos/evaluación | Dataset y protocolo; no solver de protección aprendida |
| Wang & Hauser (TRO 2021) | Error de modelo/pose en packing robótico | Margen δ determinista + replanning; no RL de gestión |
| Shuai et al. (IET CTA 2023) | Planificación, transformación, percepción, ejecución | Cumplimiento / contacto; no RL de margen geométrico de packing |
| AR2L (Pan et al., NeurIPS 2023) | Permutación adversaria de **secuencia** | Robustez de secuencia; **no** incertidumbre geométrica dimensional |
| Online BP with size estimates (arXiv 2505.09321) | Estimados de tamaño 1D | Análisis competitivo 1D; no packing 3D online BED-BPP + RL margen |
| ASAP (arXiv 2501.17377v2) | Shift de distribución de ítems | Adaptación de selección de colocación; no margen geométrico |
| Robust 1D BP branch-and-price (EJOR-style PDF) | Tamaños inciertos offline 1D | Optimización robusta exacta; no online 3D RL |

---

## 1. GOPT — Generalizable Online 3D Bin Packing (Transformer DRL)

**Fuente primaria:** https://arxiv.org/html/2409.05344v2 (verificado)

| Campo | Registro |
|-------|----------|
| Problema y observabilidad | Online 3D-BPP; ítem actual medido; heightmap/EMS; bins de tamaño variable |
| Incertidumbre | En §IV-E: errores de medición de cámara que provocan colisiones |
| Decisión controlada | Selección de orientación + EMS vía política Transformer/PPO |
| Método | PG + Packing Transformer + PPO |
| Evaluación | RS dataset simulado; generalización a bins; 20 pruebas robot reales |
| Limitación / futuro explícito | §IV-E: buffer 0.7 cm → 67.5% util.; buffer 0 → 2/20 fallos y 73.3% en éxitos; impulso a mejorar **fiabilidad y compactación**. §V: mejorar fiabilidad del sistema físico |
| Diferencia propuesta nuestra | Tratar la **protección geométrica** como decisión de gestión secuencial bajo riesgo declarado, sobre pedidos BED-BPP, con volumen nominal (no volumen de márgenes) |
| ¿Aparece ya esa diferencia? | El trade-off fijo sí; **no** aparece (en el texto leído) una política RL que elija margen/protección paso a paso bajo criterio de riesgo formalizado |

---

## 2. Kagerer et al. — BED-BPP

**Fuente primaria:** https://robotik.informatik.uni-wuerzburg.de/telematics/download/ijrr2023.pdf (verificado)

| Campo | Registro |
|-------|----------|
| Problema y observabilidad | Pedidos industriales reales (grocery); variantes online O3DBP-p-s; target en properties |
| Incertidumbre | Tolerancia de tamaño 2 cm en n-gram (redondeo a múltiplos de 20 mm); nota de que algoritmos deben considerar tolerancias y exactitud |
| Decisión controlada | Dataset + evaluación; no propone política de margen |
| Método | Dataset, KPIs `xkpi`, score Σalgo, chequeo de estabilidad en Blender |
| Evaluación | Varios solvers (PCT, heurística O3DBP-3-2, sisyphus, xflp) |
| Limitación / futuro (§6) | Extender sectores; stacking rules; estabilidad con colocación robótica continua; ML para online industrial |
| Diferencia propuesta nuestra | Usar BED-BPP como **fuente de secuencias nominales** + incertidumbre geométrica **sintética** y decisión de protección; no confundir Σalgo/xkpi con métricas propias |
| ¿Aparece ya? | BED-BPP no resuelve selección adaptativa de protección; deja el gap sim–realidad abierto |

**Advertencia metodológica propia:** las perturbaciones sintéticas **no** son mediciones reales de BED-BPP.

---

## 3. Wang y Hauser — Dense Robotic Packing (TRO)

**Fuente primaria:** preprint https://motion.cs.illinois.edu/papers/TRO2021-Wang-DenseRoboticPacking-preprint.pdf (verificado); DOI 10.1109/TRO.2021.3097261

| Campo | Registro |
|-------|----------|
| Problema y observabilidad | Packing robótico offline/constructivo de objetos irregulares; sensors para closed-loop |
| Incertidumbre | Errores de modelo/pose/percepción en ejecución |
| Decisión controlada | Planificación de pose; δ de holgura; replanificación closed-loop |
| Método | Heightmap-Minimization; **robust planning** con umbral δ; si falla, δ decrece linealmente hasta 0; visión closed-loop |
| Evaluación | Simulación Monte-Carlo + plataforma física; V1–V4 |
| Limitación / futuro | Modelos pobres de geometría/masa/fricción siguen siendo problema; (texto de limitaciones del preprint) |
| Diferencia propuesta nuestra | Online p=s=1 sobre cuboides BED-BPP; comparar RL frente a márgenes fijos **y** frente a margen calculado / adaptativo determinista (análogo conceptual a δ); volumen nominal |
| ¿Aparece ya? | **Sí aparece** margen conservador adaptativo **determinista** (δ fijo + reducción). Nuestra diferencia RL no está demostrada como necesaria frente a esa familia |

---

## 4. Shuai et al. — Compliant-based robotic 3D bin packing

**Fuente primaria:** abstract/HTML de IET (digital-library.theiet.org) + texto agregado vía fuente secundaria de biblioteca (exa); **PDF epdf bloqueado por Cloudflare** → partes del PDF completo: **parcialmente verificado** (abstract + cuerpo disponible en espejo de texto). DOI: 10.1049/cth2.12432

| Campo | Registro |
|-------|----------|
| Problema y observabilidad | R-3dBPP online con robot; percepción de caja actual; contenedor sin vallas |
| Incertidumbre | Explicitan cuatro tipos: planning, transforming, perceiving (tamaño/posición), executing |
| Decisión controlada | Algoritmo online de apilado por contacto + motion planning compliante |
| Método | Principios de proximidad y path safety; end-effector blando; no RL de margen |
| Evaluación | Simulación y experimentos físicos; util. sim >70% reportada en abstract |
| Limitación | Enfoque en ejecución/contacto bajo incertidumbre no eliminable; no formaliza MDP de protección geométrica |
| Diferencia propuesta nuestra | Gestión geométrica de holgura en el **planificador de packing** (contención/no solape), separada de trayectoria robótica y compliance |
| ¿Aparece ya? | Mitigación por hardware/compliance **sí**; selección RL de protección geométrica en el sentido propuesto **no** en el texto verificado |

---

## 5. AR2L — Adjustable Robust RL for Online 3D Bin Packing (NeurIPS 2023)

**Fuente primaria:** PDF NeurIPS https://proceedings.neurips.cc/paper_files/paper/2023/file/a345ed605675c7c484e740a8ceaa6b45-Paper-Conference.pdf (verificado)

| Campo | Registro |
|-------|----------|
| Problema y observabilidad | Online 3D-BPP; secuencia observable parcialmente; política de packing (PCT+PPO) |
| Incertidumbre | **Secuencia**: atacante por permutación de ítems observables; dinámica nominal vs adversaria |
| Decisión controlada | Colocación; robustez ajustable α entre retorno esperado y peor caso |
| Método | AR2L exacto/aproximado; mixture dynamics; **no** modela error dimensional |
| Evaluación | Robustez frente a permutaciones adversarias |
| Limitación implícita | Distinta clase de incertidumbre: secuencia ≠ geometría |
| Diferencia propuesta nuestra | Incertidumbre **geométrica** (dimensiones/colocación efectiva), no reordenación |
| ¿Aparece ya? | Robust RL online 3D **sí**, pero sobre secuencia; **no** sustituye el problema geométrico |

---

## 6. Trabajos posteriores localizados (verificación primaria parcial)

### Online Bin Packing with Item Size Estimates (arXiv 2505.09321)

**Fuente:** https://arxiv.org/html/2505.09321v1 (verificado). Problema **1D** online con estimados de tamaño y error δ; ratios competitivos. **No** es 3D online BED-BPP ni RL de margen.

### ASAP — Adaptive Selection After Proposal (arXiv 2501.17377v2)

**Fuente:** HTML arXiv (verificado). Adaptación a shift de distribución de instancias vía fine-tune de selección. **No** trata margen geométrico bajo incertidumbre dimensional.

### Online 3D Bin Packing with Fast Stability Validation… (arXiv 2507.09123v1)

**Fuente:** HTML arXiv (verificado). Incertidumbre de centro de gravedad acotada; chequeos de sensibilidad a variación de tamaño en contactos. Relacionado con robustez geométrica, pero **no** RL de selección de protección como acción de gestión bajo el contrato BED-BPP p=s=1 aquí planteado.

### Patente / case “dynamic margin adjustment” (eureka.patsnap…)

**no verificado** como paper científico primario; no se usa como evidencia de gap académico.

---

## Lectura de novedad (provisional, no demostrada)

**Problema explícito en literatura que motiva la línea:** el compromiso fiabilidad/compactación bajo error de medición (GOPT §IV-E) y la planificación conservadora con holgura (Wang & Hauser) frente a pedidos industriales (BED-BPP), **sin** confundir robustez de secuencia (AR2L).

**Diferencia candidata nuestra:** política que elige protección geométrica online, evaluada por volumen **nominal** colocado bajo riesgo declarado, con baselines de margen fijo, margen derivado de la incertidumbre y adaptativo determinista.

**Novedad aún sin comprobar:** (i) que esa diferencia no esté ya cubierta por alguna variante no leída; (ii) que RL aporte algo que no resuelva el margen directo (A) o un adaptativo determinista tipo δ (Wang).
