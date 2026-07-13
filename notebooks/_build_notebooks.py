#!/usr/bin/env python3
"""Genera los notebooks didácticos de packing-services."""

from __future__ import annotations

import json
from pathlib import Path

NB_DIR = Path(__file__).resolve().parent

SETUP_CELL = """\
# Configuración del entorno (ejecutar primero)
%matplotlib inline

import sys
from pathlib import Path
import matplotlib.pyplot as plt

_cwd = Path.cwd().resolve()
for _candidate in [_cwd, *_cwd.parents]:
    _nb = _candidate / "notebooks"
    if (_nb / "_shared" / "loaders.py").exists():
        if str(_nb) not in sys.path:
            sys.path.insert(0, str(_nb))
        break
else:
    raise RuntimeError("No se encontró notebooks/_shared. Abre el notebook desde packing-services/.")

from _shared.loaders import setup_paths
ROOT = setup_paths(_cwd)
from _shared import display, viz, runners

plt.rcParams.update({"figure.dpi": 110, "font.size": 11})
print(f"Proyecto: {ROOT}")
"""

SHOWCASE_NOTE = (
    "> **Catálogo homogéneo `showcase_master_catalog.json`** — mismos SKUs P1–P5 en 3D-BPP, "
    "Container Loading y Single Container. Cada tipo usa una **instancia showcase** compleja "
    "donde el benchmark **diferencia** los algoritmos del grupo."
)

SHOWCASE_TABLE = (
    "| Grupo benchmark | Instancia | Diferenciación esperada |",
    "|-----------------|-----------|-------------------------|",
    "| 3D-BPP | `showcase_3d_bpp_instance.json` | best_fit ~27 emp. vs extreme_points ~22 |",
    "| Híbrido (misma instancia 3D) | `showcase_3d_bpp_instance.json` | compaction/LS mueven 8–11 piezas |",
    "| Mejora 3D (misma instancia 3D) | `showcase_3d_bpp_instance.json` | relocation/swap/orientation/bin_reduction refinan layout |",
    "| Container Loading | `showcase_container_loading_instance.json` | weight_aware ~27 vs single_container ~17 |",
    "| Single Container | `showcase_single_container_instance.json` | best_fit ~13 (94% util) vs first_fit ~16 |",
    "| Cartonization | `showcase_cartonization_instance.json` | single-box vs multi_box |",
    "| Palletization | `showcase_palletization_instance.json` | layer_based vs stack_based |",
    "| Stacking-aware | `showcase_stacking_aware_instance.json` | stacking_aware vs stack_based |",
)

BENCHMARK_CELL = """\
from _shared.loaders import load_showcase_instance, problem_type_for_benchmark_group
group = '{group}'
instance = load_showcase_instance(problem_type_for_benchmark_group(group))
display.show_problem_overview(instance)
display.run_and_show_showcase_benchmark(group, instance)"""


def nb(cells: list) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def md(*lines: str) -> dict:
    import uuid

    return {
        "cell_type": "markdown",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "source": [l + "\n" for l in lines],
    }


def code(*lines: str) -> dict:
    import uuid

    return {
        "cell_type": "code",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "outputs": [],
        "source": [l + "\n" for l in lines],
        "execution_count": None,
    }


NOTEBOOKS = {
    "00_introduccion_y_vision.ipynb": [
        md(
            "# 00 — Introducción y visión del proyecto",
            "",
            "**Audiencia:** tutor de tesis / personas sin conocimiento previo de packing.",
            "",
            SHOWCASE_NOTE,
            "",
            *SHOWCASE_TABLE,
            "",
            "## ¿Qué problema resolvemos?",
            "",
            "Dado un **catálogo de piezas** (cajas con dimensiones y cantidades) y uno o más **contenedores**,",
            "hay que decidir **dónde colocar cada pieza** (posición y rotación) para:",
            "- Maximizar el aprovechamiento del espacio",
            "- Respetar peso máximo y no solapar piezas",
            "- Reportar qué piezas no cupieron",
            "",
            "Eso pertenece a la familia *Cutting and Packing*, con **cuatro formulaciones** en este proyecto:",
            "3D-BPP, Container Loading, Cartonization y Single Container Loading.",
            "",
            "## La brecha que identifiqué",
            "",
            "Existen muchos algoritmos, pero cada implementación usa **formatos distintos**.",
            "No se pueden comparar de forma justa ni integrar en un espacio de datos.",
            "",
            "## Mi propuesta",
            "",
            "Plataforma de **servicios** donde cada algoritmo implementado expone su propio endpoint "
            "``POST /api/v1/algorithms/{algorithm_name}/execute`` con entrada/salida JSON homogénea.",
            "El **benchmark** usa perfiles estándar (`constructive`, `hybrid`, `box_selection`, …) para comparar ≥2 motores sobre la misma instancia.",
        ),
        code(SETUP_CELL.strip()),
        code(
            "import subprocess, sys",
            "from _shared.loaders import load_showcase_instance, SHOWCASE_INSTANCES, BENCHMARK_GROUPS",
            "from packing_services import SERVICE_VERSION",
            "from packing_services.algorithms.registry import get_default_registry",
            "from packing_services.domain.enums import AlgorithmStatus",
            "",
            "display.show_problem_overview(load_showcase_instance('3D_BPP'))",
            "",
            "registry = get_default_registry()",
            "n_impl = len(registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED))",
            "test_run = subprocess.run(",
            "    [sys.executable, '-m', 'pytest', str(ROOT / 'tests'), '--collect-only', '-q',",
            "     '--ignore=tests/test_api.py'],",
            "    capture_output=True, text=True, cwd=ROOT,",
            ")",
            "n_tests = next((int(l.split()[0]) for l in test_run.stdout.splitlines() if 'tests collected' in l), '?')",
            "print(f'\\n=== packing-services v{SERVICE_VERSION} ===')",
            "n_algo_svc = len([s for s in runners.run_dataspace_catalog().services if s.service_name.endswith('Algorithm Service')])",
            "print(f'Algoritmos implementados: {n_impl} | Servicios por algoritmo: {n_algo_svc} | Tests: {n_tests}')",
            "print(f'Tipos de problema: {len(SHOWCASE_INSTANCES)} | Grupos de benchmark: {len(BENCHMARK_GROUPS)}')",
            "from _shared.loaders import SHOWCASE_DIFFERENTIATION",
            "import pandas as pd",
            "from IPython.display import display as ipy_display",
            "rows = [{'Grupo': g, 'Diferenciación esperada': SHOWCASE_DIFFERENTIATION.get(g, '—')} for g in BENCHMARK_GROUPS]",
            "ipy_display(pd.DataFrame(rows).style.hide(axis='index'))",
        ),
        code(
            "print('═══ Vista previa: benchmarks homogéneos (mismas instancias en todos los notebooks) ═══')",
            "for group in BENCHMARK_GROUPS:",
            "    display.run_and_show_showcase_benchmark(group, show_chart=False)",
        ),
        md(
            "## Puente: informe técnico → código",
            "",
            "| Decisión del informe | Evidencia en el repositorio |",
            "|----------------------|----------------------------|",
            "| Priorizar heurísticas constructivas | 4 heurísticas 3D-BPP + py3dbp opcional |",
            "| Mejora local reutilizable | `solution_compaction`, `constructive_plus_local_search` |",
            "| Validador geométrico propio | `PackingValidator` + tests |",
            "| Servicios independientes | 5 agregados + 1 endpoint por algoritmo |",
            "| Preparación espacio de datos | `GET /api/v1/services` + `GET /api/v1/algorithms/{name}` |",
            "",
            "**Siguiente:** `01_arquitectura_y_servicios.ipynb`",
        ),
    ],
    "01_arquitectura_y_servicios.ipynb": [
        md(
            "# 01 — Arquitectura y servicios",
            "",
            SHOWCASE_NOTE,
            "",
            *SHOWCASE_TABLE,
            "",
            "Cada algoritmo implementado es un **servicio** con endpoint propio y contrato JSON homogéneo.",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from IPython.display import Markdown, display as ipy_display",
            "from packing_services.services.metadata_service import MetadataService",
            "from packing_services.benchmark.profiles import list_profiles",
            "",
            "meta = MetadataService().get_metadata()",
            "ipy_display(Markdown(f'## **{meta.service_name}** (v{meta.service_version})\\n\\n{meta.description}'))",
            "for group in ('3D_BPP', '3D_HYBRID', 'CONTAINER_LOADING', 'CARTONIZATION', 'SINGLE_CONTAINER_LOADING'):",
            "    display.show_comparable_algorithms(group)",
        ),
        code(
            "import pandas as pd",
            "from IPython.display import display as ipy_display",
            "from packing_services.benchmark.profiles import list_profiles",
            "",
            "endpoints = [",
            "    ('Ejecutar algoritmo', 'POST /algorithms/{algorithm_name}/execute', 'Input normalizado por tipo; nombre en URL (A3)'),",
            "    ('3D Bin Packing (legacy)', 'POST /pack/3d-bpp', 'Empaquetar en contenedores'),",
            "    ('Benchmark', 'POST /benchmark', 'Comparar motores (perfil o engines explícitos)'),",
            "    ('Perfiles benchmark', 'GET /benchmark/profiles', 'Catálogo de perfiles estándar'),",
            "    ('Container Loading (legacy)', 'POST /pack/container-loading', 'Carga multi-contenedor + peso'),",
            "    ('Cartonization (legacy)', 'POST /pack/cartonization', 'Elegir caja + layout'),",
            "    ('Validation', 'POST /validate', 'Juez independiente'),",
            "    ('Dataspace', 'GET /services', 'Descriptores publicables'),",
            "]",
            "ipy_display(pd.DataFrame(endpoints, columns=['Servicio', 'Endpoint', 'Rol']).style.hide(axis='index'))",
            "profiles = list_profiles()",
            "print(f'Perfiles de benchmark disponibles: {len(profiles)}')",
            "ipy_display(pd.DataFrame([{'Tipo': p['problem_type'], 'Perfil': p['profile'], 'Motores': p['engines_count']} for p in profiles]).style.hide(axis='index'))",
            "from _shared.loaders import SHOWCASE_DIFFERENTIATION, SHOWCASE_INSTANCES, BENCHMARK_GROUPS",
            "showcase_rows = [{'Grupo': g, 'Instancia': SHOWCASE_INSTANCES.get(g, '—'), 'Diferenciación': SHOWCASE_DIFFERENTIATION.get(g, '—')} for g in BENCHMARK_GROUPS]",
            "ipy_display(pd.DataFrame(showcase_rows).style.hide(axis='index'))",
        ),
        code(
            "from _shared.loaders import build_algorithm_execute_input",
            "",
            "# Ejemplo: un algoritmo por URL, body sin campo \"algorithm\"",
            "algo = 'best_fit_decreasing_3d'",
            "payload = build_algorithm_execute_input(algo, problem_type='3D_BPP')",
            "print(f'POST /api/v1/algorithms/{algo}/execute')",
            "print('Campos del body:', sorted(payload.keys()))",
            "result = runners.run_algorithm_execute(algo, payload)",
            "display.show_execute_result(result)",
        ),
        md("**Siguiente:** demo visual 3D-BPP → `02_demo_3d_bin_packing.ipynb`"),
    ],
    "02_demo_3d_bin_packing.ipynb": [
        md(
            "# 02 — Demo: 3D Bin Packing (un algoritmo)",
            "",
            SHOWCASE_NOTE,
            "",
            "**Instancia:** `showcase_3d_bpp_instance.json` — 30 piezas P1–P5 en 2 contenedores.",
            "",
            "**Flujo:** 1) Presentar el problema → 2) `POST /algorithms/best_fit_decreasing_3d/execute` → 3) Ver la solución.",
            "",
            "Entrada: `PackAlgorithmInput` (sin campo `algorithm`). Salida: `AlgorithmExecuteResponse`.",
            "",
            "Usamos `best_fit_decreasing_3d` (ganador habitual en el benchmark de esta instancia).",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from _shared.loaders import load_showcase_instance, build_algorithm_execute_input",
            "from packing_services.domain.models import Container",
            "",
            "instance = load_showcase_instance('3D_BPP')",
            "display.show_problem_overview(instance)",
        ),
        code(
            "algo = 'best_fit_decreasing_3d'",
            "payload = build_algorithm_execute_input(algo, problem_type='3D_BPP')",
            "containers = [Container(**c) for c in payload['containers']]",
            "print(f'--- Solución (POST /algorithms/{algo}/execute) ---')",
            "result = runners.run_algorithm_execute(algo, payload)",
            "solution = display.show_execute_result(result)",
        ),
        code(
            "fig = viz.plot_all_container_views(solution, containers, title_prefix='Mejor algoritmo')",
            "if fig: plt.show()",
            "fig = viz.plot_utilization_bar(solution.metrics.volume_utilization, title='Aprovechamiento global')",
            "plt.show()",
        ),
        code(BENCHMARK_CELL.format(group="3D_BPP").strip()),
        md(
            "**Siguiente:** comparar en detalle → `03_comparacion_de_algoritmos.ipynb`",
        ),
    ],
    "03_comparacion_de_algoritmos.ipynb": [
        md(
            "# 03 — Comparación de algoritmos (Benchmark 3D-BPP)",
            "",
            SHOWCASE_NOTE,
            "",
            "**Instancia:** `showcase_3d_bpp_instance.json`",
            "",
            "## Flujo de este notebook",
            "",
            "1. **Problema** — qué hay que empacar y bajo qué reglas",
            "2. **Algoritmos** — 4 heurísticas internas + adaptador `py3dbp` (si está instalado)",
            "3. **Ejecución** — misma instancia, mismo validador, mismas métricas",
            "4. **Resultados** — quién empaca más y quién aprovecha mejor el espacio",
            "5. **Layouts** — comparación visual del mejor vs el peor",
            "",
            "En esta instancia se espera diferenciación clara: `best_fit` ~27 empacados vs `extreme_points` ~22.",
            "",
            "Cada motor del benchmark también es invocable individualmente vía `POST /algorithms/{name}/execute`.",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from _shared.loaders import load_showcase_instance",
            "",
            "instance = load_showcase_instance('3D_BPP')",
            "print('═══ 1. PROBLEMA A RESOLVER ═══')",
            "display.show_problem_overview(instance)",
        ),
        code(
            "print('═══ BENCHMARK HOMOGÉNEO (3D-BPP) ═══')",
            "response = display.run_and_show_showcase_benchmark('3D_BPP', instance)",
            "print(f'Ganador: {response.ranking[0]}')",
        ),
        code(
            "print('═══ 5. LAYOUTS: MEJOR vs PEOR ═══')",
            "from packing_services.domain.models import Container",
            "containers = [Container(**c) for c in instance['containers']]",
            "best = next(r for r in response.results if r.engine == response.ranking[0])",
            "worst = next(r for r in response.results if r.engine == response.ranking[-1])",
            "for label, result in [('MEJOR', best), ('PEOR', worst)]:",
            "    if result.solution:",
            "        print(f'--- {label}: {result.engine} ({result.metrics.items_packed} empacados, {result.metrics.volume_utilization*100:.1f}%) ---')",
            "        fig = viz.plot_all_container_views(result.solution, containers, title_prefix=label)",
            "        if fig: plt.show()",
        ),
        md(
            "**Mensaje clave:** misma entrada, distintas salidas — el benchmark cuantifica la brecha entre heurísticas.",
            "",
            "**Siguiente:** mejora local y otros tipos en `08_catalogo_algoritmos_y_futuro.ipynb`.",
            "",
            "Luego: `04_validacion_independiente.ipynb`",
        ),
    ],
    "04_validacion_independiente.ipynb": [
        md(
            "# 04 — Validación independiente",
            "",
            SHOWCASE_NOTE,
            "",
            "**Instancia:** `showcase_3d_bpp_instance.json`",
            "",
            "Validamos la solución del mejor algoritmo 3D-BPP y fabricamos",
            "un caso inválido moviendo dos piezas para que se solapen.",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from copy import deepcopy",
            "from _shared.loaders import load_showcase_instance, build_algorithm_execute_input",
            "",
            "instance = load_showcase_instance('3D_BPP')",
            "display.show_problem_overview(instance)",
            "algo = 'best_fit_decreasing_3d'",
            "result = runners.run_algorithm_execute(algo, build_algorithm_execute_input(algo, problem_type='3D_BPP'))",
            "solution = result.solution",
            "print(f'Solución a validar: {result.algorithm_name}, {solution.metrics.items_packed} piezas empacadas')",
        ),
        code(
            "valid_data = {",
            "    'problem_type': '3D_BPP',",
            "    'request_id': 'demo-valid',",
            "    'containers': instance['containers'],",
            "    'items': instance['items'],",
            "    'constraints': instance['constraints'],",
            "    'packed_items': [p.model_dump() for p in solution.packed_items],",
            "}",
            "valid_resp = runners.run_validate(valid_data)",
            "display.summarize_validation(valid_resp, 'Solución del mejor algoritmo')",
        ),
        code(
            "packed_bad = [p.model_dump() for p in solution.packed_items[:4]]",
            "packed_bad[1]['position']['x'] = packed_bad[0]['position']['x'] + 5",
            "packed_bad[1]['position']['y'] = packed_bad[0]['position']['y'] + 5",
            "invalid_data = {**valid_data, 'request_id': 'demo-invalid', 'packed_items': packed_bad}",
            "invalid_resp = runners.run_validate(invalid_data)",
            "display.summarize_validation(invalid_resp, 'Misma instancia, colocación errónea (solapamiento)')",
        ),
        code(
            "from packing_services.domain.models import Container, PackingSolution, ExecutionMetadata, SolutionStatus",
            "from packing_services.domain.enums import ProblemType",
            "from packing_services import SERVICE_VERSION",
            "from packing_services.schemas.requests import ValidateRequest",
            "",
            "containers = [Container(**c) for c in instance['containers']]",
            "meta = ExecutionMetadata(algorithm='validator', algorithm_family='validator', service_version=SERVICE_VERSION)",
            "sol_ok = PackingSolution(status=SolutionStatus.SUCCESS, problem_type=ProblemType.THREE_D_BPP,",
            "    algorithm_name='best_fit_decreasing_3d', packed_items=solution.packed_items,",
            "    validation_report=valid_resp.validation_report, execution_metadata=meta)",
            "fig = viz.plot_all_container_views(sol_ok, containers, title_prefix='Válida')",
            "if fig: plt.show()",
            "overlap_ids = set()",
            "for v in invalid_resp.validation_report.violations: overlap_ids.update(v.item_ids)",
            "sol_bad = PackingSolution(status=SolutionStatus.SUCCESS, problem_type=ProblemType.THREE_D_BPP,",
            "    algorithm_name='manual-bad', packed_items=ValidateRequest(**invalid_data).packed_items,",
            "    validation_report=invalid_resp.validation_report, execution_metadata=meta)",
            "fig = viz.plot_container_views(sol_bad, containers[0], container_id=containers[0].id,",
            "    title='Inválida — solapamiento', highlight_items=overlap_ids)",
            "plt.show()",
        ),
        md("**Siguiente:** `05_container_loading.ipynb`"),
    ],
    "05_container_loading.ipynb": [
        md(
            "# 05 — Container Loading (multi-contenedor + peso)",
            "",
            SHOWCASE_NOTE,
            "",
            "**Instancia:** `showcase_container_loading_instance.json` — catálogo homogéneo P1–P5 (30 uds) en C1/C2.",
            "",
            "El servicio prioriza **peso** y **distribución** entre contenedores.",
            "El benchmark (perfil `constructive`) contrasta tres estrategias:",
            "- `single_container_constructive` — densifica un contenedor (alta util, menos piezas)",
            "- `weight_aware_container_loading` — distribuye y empaca más piezas",
            "- `extreme_points_3d` — heurística geométrica multi-contenedor",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from _shared.loaders import load_showcase_instance, build_algorithm_execute_input",
            "",
            "instance = load_showcase_instance('CONTAINER_LOADING')",
            "algo = 'weight_aware_container_loading'",
            "payload = build_algorithm_execute_input(algo, problem_type='CONTAINER_LOADING')",
            "display.show_problem_overview(instance)",
            "print('Endpoint:', f'POST /algorithms/{algo}/execute')",
        ),
        code(
            "result = runners.run_algorithm_execute(algo, payload)",
            "solution = display.show_execute_result(",
            "    result, extra={'Peso cargado': f'{result.solution.metrics.loaded_weight:.0f} kg'})",
            "max_w = payload['containers'][0]['max_weight'] or 500",
            "fig = viz.plot_weight_bar(solution.metrics.loaded_weight, max_w * len(payload['containers']))",
            "plt.show()",
        ),
        code(
            "from packing_services.domain.models import Container",
            "containers = [Container(**c) for c in payload['containers']]",
            "fig = viz.plot_all_container_views(solution, containers, title_prefix='Container Loading')",
            "if fig: plt.show()",
        ),
        code(
            "print('═══ BENCHMARK HOMOGÉNEO (Container Loading) ═══')",
            "display.run_and_show_showcase_benchmark('CONTAINER_LOADING', instance)",
        ),
        md("**Siguiente:** `06_single_container_loading.ipynb`"),
    ],
    "06_single_container_loading.ipynb": [
        md(
            "# 06 — Demo: Single Container Loading (un camión)",
            "",
            SHOWCASE_NOTE,
            "",
            "**Instancia:** `showcase_single_container_instance.json` — catálogo P1–P5 (30 uds), **1 contenedor altura 70**.",
            "",
            "**Flujo:** 1) Presentar el problema → 2) Ejecutar un algoritmo → 3) Ver la solución → 4) Benchmark.",
            "",
            "A diferencia del Container Loading (NB05), aquí solo hay **un camión**. La altura reducida fuerza",
            "un trade-off visible: `best_fit` densifica (~13 piezas, 94% util) vs `first_fit` empaca más (~16, 89%).",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from _shared.loaders import load_showcase_instance, build_algorithm_execute_input",
            "from packing_services.domain.models import Container",
            "",
            "instance = load_showcase_instance('SINGLE_CONTAINER_LOADING')",
            "display.show_problem_overview(instance)",
        ),
        code(
            "algo = 'best_fit_decreasing_3d'",
            "payload = build_algorithm_execute_input(algo, problem_type='SINGLE_CONTAINER_LOADING')",
            "containers = [Container(**c) for c in payload['containers']]",
            "print(f'--- Solución (POST /algorithms/{algo}/execute) ---')",
            "result = runners.run_algorithm_execute(algo, payload)",
            "solution = display.show_execute_result(result)",
        ),
        code(
            "fig = viz.plot_all_container_views(solution, containers, title_prefix='Single Container')",
            "if fig: plt.show()",
            "fig = viz.plot_utilization_bar(solution.metrics.volume_utilization, title='Aprovechamiento del camión')",
            "plt.show()",
        ),
        code(
            "print('═══ BENCHMARK HOMOGÉNEO (Single Container) ═══')",
            "display.run_and_show_showcase_benchmark('SINGLE_CONTAINER_LOADING', instance)",
        ),
        md("**Siguiente:** `07_cartonization.ipynb`"),
    ],
    "07_cartonization.ipynb": [
        md(
            "# 07 — Cartonization (selección de caja)",
            "",
            SHOWCASE_NOTE,
            "",
            "**Instancia:** `showcase_cartonization_instance.json` — pedido de **6 cubos P5** (20×20×20)",
            "y catálogo de cajas **BOX_S / BOX_M / BOX_L**.",
            "",
            "El problema: elegir **una caja** donde quepa todo el pedido.",
            "El benchmark (perfil `box_selection`) compara 4 criterios de selección;",
            "`largest_feasible_box` elige BOX_L (mucho espacio vacío) frente a las estrategias minimalistas (BOX_M).",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from _shared.loaders import load_showcase_instance, build_algorithm_execute_input",
            "from packing_services.domain.models import Container",
            "",
            "instance = load_showcase_instance('CARTONIZATION')",
            "algo = 'smallest_feasible_box'",
            "payload = build_algorithm_execute_input(algo)",
            "print('═══ PROBLEMA: pedido + catálogo de cajas ═══')",
            "display.show_problem_overview(instance)",
            "print('Endpoint:', f'POST /algorithms/{algo}/execute')",
        ),
        code(
            "print('═══ SOLUCIÓN ═══')",
            "result = runners.run_algorithm_execute(algo, payload)",
            "solution = display.show_execute_result(result)",
            "fig = viz.plot_box_catalog(result.cartonization.evaluated_boxes, result.cartonization.selected_box_id)",
            "plt.show()",
        ),
        code(
            "from packing_services.schemas.requests import BoxOption",
            "box = next(BoxOption(**b) for b in payload['boxes'] if b['id'] == result.cartonization.selected_box_id)",
            "container = box.to_container()",
            "fig = viz.plot_container_views(solution, container, title=f'Layout en {result.cartonization.selected_box_id}')",
            "plt.show()",
        ),
        code(
            "print('═══ BENCHMARK HOMOGÉNEO (Cartonization) ═══')",
            "display.run_and_show_showcase_benchmark('CARTONIZATION', instance)",
        ),
        md("**Siguiente:** `08_catalogo_algoritmos_y_futuro.ipynb`"),
    ],
    "08_catalogo_algoritmos_y_futuro.ipynb": [
        md(
            "# 08 — Catálogo de algoritmos y evidencia comparativa",
            "",
            SHOWCASE_NOTE,
            "",
            *SHOWCASE_TABLE,
            "",
            "Catálogo de **29 algoritmos implementados**, cada uno con endpoint propio "
            "``POST /api/v1/algorithms/{name}/execute`` y **9 grupos de benchmark**. "
            "Adaptador ``py3dbp`` activo si la dependencia está instalada.",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from packing_services.algorithms.registry import get_default_registry",
            "from packing_services.domain.enums import AlgorithmStatus",
            "from _shared.loaders import BENCHMARK_GROUPS",
            "import pandas as pd",
            "from IPython.display import display as ipy_display",
            "",
            "registry = get_default_registry()",
            "from packing_services.services.algorithm_input_service import AlgorithmInputService",
            "input_svc = AlgorithmInputService(registry)",
            "impl = registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED)",
            "rows = [{'Algoritmo': m.name, 'Familia': m.algorithm_family.value,",
            "         'Problemas': ', '.join(p.value for p in m.problem_types),",
            "         'Input': input_svc.input_schema_for(m),",
            "         'Endpoint': input_svc.execution_endpoint(m.name)} for m in impl]",
            "ipy_display(pd.DataFrame(rows).style.hide(axis='index'))",
        ),
        code(
            "print('═══ Demo: ejecutar un algoritmo vía servicio propio ═══')",
            "from _shared.loaders import build_algorithm_execute_input",
            "demo_algo = 'extreme_points_3d'",
            "payload = build_algorithm_execute_input(demo_algo, problem_type='3D_BPP')",
            "print(f'POST /api/v1/algorithms/{demo_algo}/execute')",
            "display.show_execute_result(runners.run_algorithm_execute(demo_algo, payload))",
        ),
        code(
            "print('═══ Evidencia comparativa: 9 benchmarks homogéneos ═══')",
            "for group in BENCHMARK_GROUPS:",
            "    display.run_and_show_showcase_benchmark(group)",
        ),
        code(
            "by = {}",
            "for m in registry.list_metadata(): by[m.status.value] = by.get(m.status.value, 0) + 1",
            "fig = viz.plot_algorithm_catalog_counts(by.get('implemented', 0), by.get('adapter', 0), by.get('future', 0))",
            "plt.show()",
            "fig = viz.plot_roadmap_phases(); plt.show()",
        ),
        md("**Siguiente:** `09_preparacion_espacio_de_datos.ipynb`"),
    ],
    "09_preparacion_espacio_de_datos.ipynb": [
        md(
            "# 09 — Preparación para espacio de datos",
            "",
            SHOWCASE_NOTE,
            "",
            "Cada algoritmo implementado queda descrito como activo publicable con endpoint, esquemas de entrada/salida y tipos de problema soportados.",
        ),
        code(SETUP_CELL.strip()),
        code(
            "from _shared.loaders import SHOWCASE_INSTANCES, BENCHMARK_GROUPS, SHOWCASE_DIFFERENTIATION, load_master_catalog",
            "from packing_services.services.algorithm_input_service import AlgorithmInputService",
            "catalog = runners.run_dataspace_catalog()",
            "print('dataspace_ready:', catalog.dataspace_ready)",
            "master = load_master_catalog()",
            "print(f'Catálogo homogéneo: {master[\"catalog_version\"]} — {master[\"description\"]}')",
            "import pandas as pd",
            "from IPython.display import display as ipy_display",
            "agg = [s for s in catalog.services if not s.service_name.endswith('Algorithm Service')]",
            "rows = [{'Servicio': s.service_name, 'Problema': s.problem_type, 'Algoritmos': len(s.algorithms),",
            "         'Input': s.input_schema, 'Output': s.output_schema, 'Endpoint': s.execution_endpoint} for s in agg]",
            "ipy_display(pd.DataFrame(rows).style.hide(axis='index'))",
            "algo_rows = [{'Algoritmo': s.algorithms[0], 'Input': s.input_schema, 'Output': s.output_schema,",
            "              'Endpoint': s.execution_endpoint} for s in catalog.services if s.service_name.endswith('Algorithm Service')]",
            "print(f'Servicios por algoritmo: {len(algo_rows)}')",
            "ipy_display(pd.DataFrame(algo_rows).style.hide(axis='index'))",
            "bench_rows = [{'Grupo': g, 'Instancia': SHOWCASE_INSTANCES.get(g, '—'), 'Diferenciación': SHOWCASE_DIFFERENTIATION.get(g, '—')} for g in BENCHMARK_GROUPS]",
            "ipy_display(pd.DataFrame(bench_rows).style.hide(axis='index'))",
        ),
        code(
            "svc = AlgorithmInputService()",
            "example = svc.build_input_example('multi_box_cartonization')",
            "print('Ejemplo de entrada (CartonizationAlgorithmInput):', sorted(example.keys()))",
            "result = runners.run_algorithm_execute('multi_box_cartonization', example)",
            "display.show_execute_result(result)",
            "print('Cajas usadas:', result.cartonization.selected_box_ids if result.cartonization else '—')",
        ),
        md(
            "## Cierre del recorrido didáctico",
            "",
            "1. **Cuatro tipos de problema** con instancia showcase dedicada (`examples/showcase_*_instance.json`)",
            "2. **Veintidós algoritmos** implementados + adaptador ``py3dbp`` (si está instalado)",
            "3. **Ocho benchmarks** comparativos: 3D-BPP, híbrido, mejora 3D, CL, Cartonization, SCL, Palletization, Stacking-aware",
            "4. **Perfiles estándar** (`constructive`, `hybrid`, `box_selection`) para comparación reproducible",
            "5. **Validación independiente** y **descriptores** listos para espacio de datos (`GET /api/v1/services`)",
            "6. **Un endpoint por algoritmo** con salida `AlgorithmExecuteResponse` estandarizada",
            "",
            "Cada benchmark usa un caso diseñado para **diferenciar** estrategias del mismo grupo — evidencia cuantitativa del avance del proyecto.",
        ),
    ],
}


def main() -> None:
    expected = set(NOTEBOOKS.keys())
    for name, cells in NOTEBOOKS.items():
        path = NB_DIR / name
        path.write_text(json.dumps(nb(cells), ensure_ascii=False, indent=1), encoding="utf-8")
        print("Wrote", path.name)

    # Elimina notebooks obsoletos tras renumerar.
    for path in NB_DIR.glob("*.ipynb"):
        if path.name not in expected:
            path.unlink()
            print("Removed obsolete", path.name)


if __name__ == "__main__":
    main()
