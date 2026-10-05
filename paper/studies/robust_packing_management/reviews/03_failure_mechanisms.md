# Revisión 03 — mecanismos de fallo y alcanzabilidad (G2 diseño)

**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2`
**Contrato:** envolvente = `nominal_oriented + margin_oriented`; mismo FLB; crecimiento del realizado solo en +ejes; ocupación revelada = AABB realizados; sin error de posición.

No se convierte “poco frecuente en búsqueda” en “imposible” sin prueba formal.
No se añade error de posición para fabricar dificultad.

---

## 1. Razonamiento geométrico

Sea la envolvente el AABB \(E=[p,\,p+e]\) y el realizado \(R=[p,\,p+r]\) con \(r\ge e\) componente a componente (mismo FLB). Entonces \(R\setminus E\) es la cáscara en la que al menos un eje supera \(e_i\).

- **`envelope_exceeded` + salida:** ocurre si \(\exists i:\; p_i+r_i > C_i\) mientras \(p_i+e_i\le C_i\).
  **Alcanzable bajo EP:** sí (G1: contenedor 55, nominal 50, realizado 60, margen 0).

- **`envelope_exceeded` + solape con caja previa \(B\):** requiere \(B\cap E=\emptyset\) (sin volumen; contacto de caras OK) y \(B\cap R\) con volumen > 0, i.e. \(B\) intersecta la cáscara.
  **Ejemplo abstracto alcanzable (ocupación manual, no EP):**
  \(E=[0,10]^3\), \(r=(15,10,10)\), \(B=[12,15]\times[2,6]\times[2,6]\).
  Envolvente factible; realizado solapa \(B\).

- **Bajo el generador EP de este repo (online, EP inicial solo origen, nuevos EP en caras/proyecciones de cajas colocadas):** una búsqueda discreta pequeña de episodios 2-ítem **no encontró** `geometric_failure` con `envelope_exceeded` por solape (0 hits). Las colocaciones típicas en caras hacen que el vecino soporte quede en un semiespacio “atrás” del FLB, de modo que crecer en +ejes produce **contacto**, no volumen de solape, con ese vecino.
  **Delimitación:** no se demuestra imposibilidad global para todos los layouts EP multi-ítem; se delimita que el solape-por-exceso es **geométricamente posible en abstracto** pero **no observado / difícil** bajo EP cara-a-cara en búsquedas pequeñas. El fallo dominante observable en integración es **salida** (y `no_candidate` por márgenes grandes).

## 2. Papel del margen más allá de la aceptación

| Efecto | ¿Ocurre? | Ejemplo |
|--------|----------|---------|
| Cambia el conjunto de candidatas (aceptación) | Sí | Margen 10 en bin 45 con nominal 40 → `no_candidate`; margen 0 → `placed` |
| Puede cambiar orientación elegida | Sí (cuando el ranking/feasible set cambia) | Menú de orientaciones distinto al filtrar por envolvente |
| Puede cambiar FLB elegida | Sí (si el mejor `rank_key` factible cambia) | Contenedores/ocupaciones donde la holgura elimina el EP óptimo nominal |
| Remuestrea el realizado | **No** | Misma realización por ítem/escenario; orientación solo permuta |

## 3. Candidata rechazada con margen vs realización válida

Una pose/orientación puede ser ilegal bajo envolvente grande y, con margen 0, admitir la misma realización (si \(r\le\) nominal o cabe).
Ejemplo sintético: bin \(45^3\), nominal \(40^3\), realizado \(=\) nominal; margen 10 → `no_candidate`; margen 0 → éxito.
Consecuencia: el margen no solo “asegura”; también **descarta huecos** que habrían sido válidos para el realizado verdadero.

## 4. Tabla de mecanismos

| Evento | Condición | Ejemplo alcanzable | Consecuencia para RL |
|--------|-----------|--------------------|----------------------|
| `no_candidate` | \(\mathcal{C}(m)=\emptyset\) | Margen uniforme grande vs bin justo | Trade-off volumen/riesgo vía early-stop; regla analítica de holgura libre puede bastar |
| `envelope_exceeded` (sin fallo) | \(r\not\le e\) pero \(R\) cabe y no solapa | Nominal 20, realizado 25, bin 100, \(m=0\) (G1) | Actualiza ocupación con realizado; no es fallo; RL no “arregla” el pasado |
| `geometric_failure` por **salida** | \(p+r\) fuera; \(p+e\) dentro | Bin 55, nom 50, real 60 (G1) | Riesgo inmediato ≈ función de holgura a paredes vs ley de \(r\); baseline local calculable |
| `geometric_failure` por **solape** vía exceso | \(B\) en cáscara \(R\setminus E\) | Abstracto shell; EP: no hallado en búsqueda pequeña | Si EP lo hace raro, el valor de políticas complejas por solape disminuye bajo este motor |
| Fallo sin exceso | \(r\le e\) pero bug/auditoría | No esperado si certificado aplica | Integridad G1; no es señal de aprendizaje |

## 5. Implicación científica (sin ejecutar G2)

La oportunidad de gestión, bajo este motor, se concentra en:

1. elegir \(m\) / pose para no salir (clearance a paredes + ley pública de error);
2. no asfixiar demasiado y provocar `no_candidate`;
3. efectos de layout futuro (chooser + holgura cambia poses).

Eso favorece **baselines analíticos locales** de clearance. RL solo tendría sentido si G2 muestra residual tras esas reglas — no se asume aquí.
