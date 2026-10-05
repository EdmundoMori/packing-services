# 11 — Literatura y alcance

Fuentes primarias verificadas para el manuscrito. No es una revisión exhaustiva.
No se usan resúmenes de terceros para atribuir fórmulas.

## Referencias

### Mandi et al., ICML 2022 (decision-focused / learning to rank)
- URL: https://proceedings.mlr.press/v162/mandi22a.html
- PDF: https://proceedings.mlr.press/v162/mandi22a/mandi22a.pdf
- Datos: Jayanta Mandi, Víctor Bucarey, Maxime Mulamba Ke Tchomba, Tias Guns;
  PMLR 162:14935–14947, 2022.
- Pertinente: Section 4.3 “Regress on Pairwise Difference”, Equation (13).
- Afirmación respaldada: una pérdida de diferencias de retorno empareja gaps de
  score con gaps de valor de solución en un esquema predict-and-optimize / ranking.
- Diferencia con nosotros: Mandi opera sobre soluciones de un problema CO con
  costes predichos; aquí se adaptan gaps de `Q_hat` entre candidatas locales de
  packing. El denominador es el número de pares estrictos en `S`. No es
  reproducción exacta.

### Crainic, Perboli & Tadei, INFORMS JOC 2008 (extreme points)
- URL: https://pubsonline.informs.org/doi/10.1287/ijoc.1070.0250
- DOI: 10.1287/ijoc.1070.0250
- Datos: Teodor Gabriel Crainic, Guido Perboli, Roberto Tadei;
  *INFORMS Journal on Computing*, 2008 (extreme-point heuristics for 3D BPP).
- Pertinente: definición de Extreme Points como regla de colocación / generación
  de puntos candidatos (§3 del preprint CIRRELT / versión JOC).
- Afirmación respaldada: una familia clásica de candidatas geométricas se genera
  a partir de puntos extremos tras cada colocación.
- Diferencia: nuestro motor compacto usa su propia generación legal; no afirmamos
  identidad bit a bit con EP-FFD/EP-BFD. La referencia motiva el vocabulario de
  “candidatas geométricas”, no un baseline experimental EP.

### Zhao, Yu & Xu, ICLR 2022 (online packing aprendido / PCT)
- URL: https://openreview.net/forum?id=bfuGjlCwAq
- Datos: Hang Zhao, Yang Yu, Kai Xu; ICLR 2022;
  “Learning Efficient Online 3D Bin Packing on Packing Configuration Trees”.
- Pertinente: representación PCT y política DRL sobre hojas del árbol.
- Afirmación respaldada: el packing online aprendido es un problema activo; PCT
  es una línea DRL con representación jerárquica de estado/acción.
- Diferencia: **no** comparamos experimentalmente con PCT en esta campaña; no
  llamamos PCT a nuestro MLP ni a OnlineBPH. Nuestro estudio es supervisión
  local bajo contrato geométrico propio.

### Kagerer et al., IJRR 2023 (BED-BPP)
- URL dataset: https://floriankagerer.github.io/dataset/
- DOI: 10.1177/02783649231193048
- PDF institucional: https://robotik.informatik.uni-wuerzburg.de/telematics/download/ijrr2023.pdf
- Datos: Florian Kagerer, Maximilian Beinhofer, Stefan Stricker, Andreas Nüchter;
  *The International Journal of Robotics Research*, 42(11):1007–1014, 2023.
- Pertinente: definición del dataset BED-BPP y evaluación con chequeo de
  estabilidad por simulación de cuerpo rígido.
- Afirmación respaldada: BED-BPP provee instancias realistas y un protocolo de
  evaluación robótica con estabilidad simulada.
- Diferencia: usamos BED-BPP como **fuente de instancias**. Nuestro `U_geom`,
  orientaciones, restricciones inactivas de peso/estabilidad y parada en el
  primer ítem ilegal **no** reproducen el benchmark robótico oficial ni su
  chequeo físico. `physical_stability_verified=null`.

### Supervisión por continuación / rollout
No se encontró una referencia primaria de packing que defina exactamente
`Q_hat` = utilización de una continuación Greedy tras una acción local.
Referencias cercanas en RL/LLM (ROSS, WS-GRPO, etc.) pertenecen a otros
dominios y **no** se citan como fundamento de nuestra fórmula.
**Estado:** la motivación de etiquetar con un retorno de continuación se apoya
en la lógica decision-focused (Mandi) y en la ingeniería del piloto previo;
queda marcada como **adaptación propia**, no como reproducción de un paper de
rollout en packing.

## Separación de protocolos

| Protocolo | Rol en este estudio |
| --- | --- |
| Zhao / PCT | Contexto de packing online aprendido; **fuera** de la comparación experimental |
| Kagerer / BED-BPP | Fuente de pedidos; no se adopta su evaluación de estabilidad |
| Contrato geométrico compacto | Motor, métrica y parada de **esta** campaña |

## Brecha investigable (sin afirmar “nadie lo estudió”)

Comparar objetivos de supervisión (clasificación, preferencias, diferencias de
retorno) para **acciones locales** en packing online, con etiquetas de
continuación Greedy y evaluación en **episodios completos**, bajo un contrato
geométrico fijo, soporte `S` compartido y presupuesto acotado.

No se afirma novedad por usar un dataset distinto. Si existiera un estudio
prácticamente equivalente (mismos tres objetivos, mismas etiquetas de
continuación y el mismo contraste de episodio), faltaría documentarlo; con las
fuentes inspeccionadas, PCT y BED-BPP no ocupan esa celda exacta.
