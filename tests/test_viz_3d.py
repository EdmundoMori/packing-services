"""Validación end-to-end del visualizador 3D adaptado de D-Wave.

Inventario de funcionalidades del visualizador en
``dwave-examples/3d-bin-packing`` (utils.py) y comprobación una a una
de su implementación/adaptación en packing-services
(``notebooks/_shared/viz_3d.py`` + ``web-demo/.../layout-viz-3d.js``).

Referencia D-Wave (Apache-2.0):
  - _cuboid_data / _get_all_cuboids / _plot_cuboids / plot_cuboids
  - color_coded, bin boundaries, aspectmode=data
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from packing_services.domain.enums import AlgorithmFamily, ProblemType, SolutionStatus
from packing_services.domain.models import (
    Container,
    ExecutionMetadata,
    Orientation,
    PackedItem,
    PackingSolution,
    Point3D,
)

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"
sys.path.insert(0, str(NB_DIR))

from _shared.viz_3d import (  # noqa: E402
    base_id,
    build_container_traces,
    color_map,
    container_dims,
    cuboid_vertices,
    extract_cuboids,
    plot_container_3d,
    plot_solution_3d,
)

plotly = pytest.importorskip("plotly")
np = pytest.importorskip("numpy")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _packed(item_id, container_id, x, y, z, l, w, h, weight=1.0):
    return PackedItem(
        item_id=item_id,
        container_id=container_id,
        position=Point3D(x=x, y=y, z=z),
        orientation=Orientation(length=l, width=w, height=h),
        weight=weight,
    )


def _solution(packed_items, algorithm_name="test_algo"):
    return PackingSolution(
        status=SolutionStatus.SUCCESS if packed_items else SolutionStatus.FAILED,
        problem_type=ProblemType.THREE_D_BPP,
        algorithm_name=algorithm_name,
        packed_items=list(packed_items),
        execution_metadata=ExecutionMetadata(
            algorithm=algorithm_name,
            algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
            service_version="0.1.0",
        ),
    )


@pytest.fixture
def two_item_solution():
    """Equivalente conceptual al test_data_1 de D-Wave (2 cases en 1 bin)."""
    return _solution(
        [
            _packed("P1#0", "C1", 0, 0, 0, 2, 2, 2),
            _packed("P2#0", "C1", 2, 0, 0, 3, 3, 3),
        ]
    )


@pytest.fixture
def multi_container_solution():
    return _solution(
        [
            _packed("P1#0", "C1", 0, 0, 0, 10, 10, 10),
            _packed("P1#1", "C1", 10, 0, 0, 10, 10, 10),
            _packed("P2#0", "C2", 0, 0, 0, 5, 5, 5),
        ]
    )


# ===========================================================================
# F1 — Geometría de cuboide (_cuboid_data → cuboid_vertices)
# ===========================================================================


class TestF1CuboidGeometry:
    """D-Wave ``_cuboid_data``: 6 caras × 4 vértices desde origin+size."""

    def test_shape_six_faces_four_vertices(self):
        verts = cuboid_vertices((0, 0, 0), (1, 1, 1))
        assert verts.shape == (6, 4, 3)

    def test_origin_and_extent(self):
        verts = cuboid_vertices((10, 20, 30), (4, 5, 6))
        assert verts.min(axis=(0, 1)).tolist() == pytest.approx([10, 20, 30])
        assert verts.max(axis=(0, 1)).tolist() == pytest.approx([14, 25, 36])

    def test_unit_cube_has_eight_unique_corners(self):
        verts = cuboid_vertices((0, 0, 0), (1, 1, 1))
        unique = np.unique(np.vstack(verts), axis=0)
        assert len(unique) == 8

    def test_matches_dwave_face_layout(self):
        """Misma definición de caras que D-Wave utils._cuboid_data."""
        faces = [
            [[0, 1, 0], [0, 0, 0], [1, 0, 0], [1, 1, 0]],
            [[0, 0, 0], [0, 0, 1], [1, 0, 1], [1, 0, 0]],
            [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]],
            [[0, 0, 1], [0, 0, 0], [0, 1, 0], [0, 1, 1]],
            [[0, 1, 0], [0, 1, 1], [1, 1, 1], [1, 1, 0]],
            [[0, 1, 1], [0, 0, 1], [1, 0, 1], [1, 1, 1]],
        ]
        expected = np.array(faces, dtype=float)
        for i in range(3):
            expected[:, :, i] *= [2.0, 3.0, 4.0][i]
        expected += np.array([1.0, 1.0, 1.0])
        actual = cuboid_vertices((1, 1, 1), (2, 3, 4))
        np.testing.assert_allclose(actual, expected)


# ===========================================================================
# F2 — Extracción posición/tamaño desde solución (reemplaza SampleSet CQM)
# ===========================================================================


class TestF2SolutionToCuboids:
    """Adaptación de plot_cuboids: PackingSolution → positions/sizes."""

    def test_uses_position_and_orientation(self, two_item_solution):
        cuboids = extract_cuboids(two_item_solution.packed_items, "C1")
        assert cuboids[0]["position"] == (0.0, 0.0, 0.0)
        assert cuboids[0]["size"] == (2.0, 2.0, 2.0)
        assert cuboids[1]["position"] == (2.0, 0.0, 0.0)
        assert cuboids[1]["size"] == (3.0, 3.0, 3.0)

    def test_orientation_acts_as_effective_dimensions(self):
        """En D-Wave dx,dy,dz vienen de orientación; aquí de orientation.*."""
        item = _packed("A#0", "C1", 1, 2, 3, 30, 10, 20)  # rotado
        cuboids = extract_cuboids([item], "C1")
        assert cuboids[0]["size"] == (30.0, 10.0, 20.0)

    def test_filters_by_container_id(self, multi_container_solution):
        c1 = extract_cuboids(multi_container_solution.packed_items, "C1")
        c2 = extract_cuboids(multi_container_solution.packed_items, "C2")
        assert len(c1) == 2
        assert len(c2) == 1
        assert all(c["item_id"].startswith("P1") for c in c1)


# ===========================================================================
# F3 — Mesh3d por pieza (_get_all_cuboids)
# ===========================================================================


class TestF3Mesh3dTraces:
    """D-Wave Mesh3d: alphahull=0, flatshading, showlegend, name case_id."""

    def test_one_mesh_per_item_plus_wireframe(self, two_item_solution):
        cuboids = extract_cuboids(two_item_solution.packed_items, "C1")
        traces = build_container_traces(cuboids, 30, 40, 50)
        meshes = [t for t in traces if t.type == "mesh3d"]
        lines = [t for t in traces if t.type == "scatter3d"]
        assert len(meshes) == 2
        assert len(lines) == 1

    def test_mesh_has_dwave_style_props(self, two_item_solution):
        cuboids = extract_cuboids(two_item_solution.packed_items, "C1")
        meshes = [t for t in build_container_traces(cuboids, 30, 40, 50) if t.type == "mesh3d"]
        for m in meshes:
            assert m.alphahull == 0
            assert m.flatshading is True
            assert m.showlegend is True
            assert m.name  # case/item id

    def test_mesh_vertices_cover_cuboid_bbox(self):
        cuboids = [
            {
                "item_id": "X",
                "sku": "X",
                "position": (1.0, 2.0, 3.0),
                "size": (4.0, 5.0, 6.0),
            }
        ]
        mesh = [t for t in build_container_traces(cuboids, 20, 20, 20) if t.type == "mesh3d"][0]
        assert min(mesh.x) == pytest.approx(1.0)
        assert max(mesh.x) == pytest.approx(5.0)
        assert min(mesh.y) == pytest.approx(2.0)
        assert max(mesh.y) == pytest.approx(7.0)
        assert min(mesh.z) == pytest.approx(3.0)
        assert max(mesh.z) == pytest.approx(9.0)


# ===========================================================================
# F4 — Color coding (color_coded / SKU palette)
# ===========================================================================


class TestF4ColorCoding:
    """D-Wave: color_coded + Rainbow por case_id. PS: paleta discreta por SKU."""

    def test_sku_base_id(self):
        assert base_id("P1#3") == "P1"

    def test_same_sku_same_color(self):
        colors = color_map(["P1#0", "P1#1", "P2#0"])
        assert colors["P1"] == colors["P1"]
        assert colors["P1"] != colors["P2"]

    def test_color_coded_true_assigns_sku_colors(self, two_item_solution):
        cuboids = extract_cuboids(two_item_solution.packed_items, "C1")
        meshes = [t for t in build_container_traces(cuboids, 30, 40, 50, color_coded=True) if t.type == "mesh3d"]
        assert meshes[0].color != meshes[1].color  # P1 vs P2

    def test_color_coded_false_uses_uniform_color(self, two_item_solution):
        """Equivalente a D-Wave color_coded=False (sin escala Rainbow)."""
        cuboids = extract_cuboids(two_item_solution.packed_items, "C1")
        meshes = [
            t
            for t in build_container_traces(cuboids, 30, 40, 50, color_coded=False)
            if t.type == "mesh3d"
        ]
        assert meshes[0].color == meshes[1].color == "#4e79a7"


# ===========================================================================
# F5 — Contorno del contenedor (bin boundaries)
# ===========================================================================


class TestF5ContainerBoundary:
    """D-Wave: 3 Scatter3d rojos por bin. PS: wireframe completo 12 aristas."""

    def test_wireframe_is_scatter3d_red_lines(self):
        cuboids = [{"item_id": "A", "sku": "A", "position": (0, 0, 0), "size": (1, 1, 1)}]
        wire = [t for t in build_container_traces(cuboids, 10, 20, 30) if t.type == "scatter3d"][0]
        assert wire.mode == "lines"
        assert wire.line.color == "#b91c1c"
        assert wire.line.width == 5

    def test_wireframe_has_twelve_edges(self):
        cuboids = [{"item_id": "A", "sku": "A", "position": (0, 0, 0), "size": (1, 1, 1)}]
        wire = [t for t in build_container_traces(cuboids, 10, 20, 30) if t.type == "scatter3d"][0]
        # cada arista: 2 puntos + None → 3 entradas; 12 aristas → 36
        assert len(wire.x) == 36
        assert wire.x.count(None) == 12

    def test_wireframe_spans_container_dims(self):
        cuboids = [{"item_id": "A", "sku": "A", "position": (0, 0, 0), "size": (1, 1, 1)}]
        wire = [t for t in build_container_traces(cuboids, 10, 20, 30) if t.type == "scatter3d"][0]
        xs = [v for v in wire.x if v is not None]
        ys = [v for v in wire.y if v is not None]
        zs = [v for v in wire.z if v is not None]
        assert max(xs) == pytest.approx(10)
        assert max(ys) == pytest.approx(20)
        assert max(zs) == pytest.approx(30)


# ===========================================================================
# F6 — Figura Plotly: ejes, aspectmode, márgenes (_plot_cuboids + plot_cuboids)
# ===========================================================================


class TestF6FigureLayout:
    def test_scene_aspectmode_data(self, two_item_solution):
        container = Container(id="C1", length=30, width=40, height=50)
        fig = plot_container_3d(two_item_solution, container)
        assert fig.layout.scene.aspectmode == "data"

    def test_axis_ranges_use_container_dims_with_margin(self, two_item_solution):
        container = Container(id="C1", length=30, width=40, height=50)
        fig = plot_container_3d(two_item_solution, container)
        assert fig.layout.scene.xaxis.range[0] == pytest.approx(0)
        assert fig.layout.scene.xaxis.range[1] == pytest.approx(30 * 1.05)
        assert fig.layout.scene.yaxis.range[1] == pytest.approx(40 * 1.05)
        assert fig.layout.scene.zaxis.range[1] == pytest.approx(50 * 1.05)

    def test_trace_count_like_dwave_test(self, two_item_solution):
        """D-Wave test_plot_cuboids: n_cases + boundaries. Aquí: 2 meshes + 1 wireframe."""
        container = Container(id="C1", length=30, width=40, height=50)
        fig = plot_container_3d(two_item_solution, container)
        assert len(fig.data) == 2 + 1

    def test_empty_container_returns_none(self):
        sol = _solution([_packed("P1#0", "C2", 0, 0, 0, 1, 1, 1)])
        fig = plot_container_3d(sol, Container(id="C1", length=10, width=10, height=10))
        assert fig is None

    def test_no_packed_items_returns_none(self):
        fig = plot_container_3d(
            _solution([]),
            Container(id="C1", length=10, width=10, height=10),
        )
        assert fig is None


# ===========================================================================
# F7 — Multi-contenedor (adaptación: 1 figura por contenedor, no concat en X)
# ===========================================================================


class TestF7MultiContainerAdaptation:
    def test_one_figure_per_occupied_container(self, multi_container_solution):
        containers = [
            Container(id="C1", length=100, width=80, height=80),
            Container(id="C2", length=50, width=50, height=50),
        ]
        figs = plot_solution_3d(multi_container_solution, containers)
        assert len(figs) == 2

    def test_figures_sorted_by_container_id(self, multi_container_solution):
        containers = [
            Container(id="C2", length=50, width=50, height=50),
            Container(id="C1", length=100, width=80, height=80),
        ]
        figs = plot_solution_3d(multi_container_solution, containers, title_prefix="T")
        assert "C1" in figs[0].layout.title.text
        assert "C2" in figs[1].layout.title.text

    def test_fallback_dims_without_container_model(self, multi_container_solution):
        """Si no se pasan containers, dimensiones desde bbox de cuboides."""
        figs = plot_solution_3d(multi_container_solution, containers=None)
        assert len(figs) == 2
        # C1: ítems hasta x=20
        assert figs[0].layout.scene.xaxis.range[1] == pytest.approx(20 * 1.05)


# ===========================================================================
# F8 — Dimensiones de contenedor / boxes (cartonization)
# ===========================================================================


class TestF8ContainerAndBoxDims:
    def test_container_dims_from_model(self):
        c = Container(id="BOX_M", length=40, width=30, height=25)
        assert container_dims(c, []) == (40.0, 30.0, 25.0)

    def test_container_dims_fallback(self):
        cuboids = [{"position": (0, 0, 0), "size": (8, 6, 4)}]
        assert container_dims(None, cuboids) == (8.0, 6.0, 4.0)

    def test_plot_with_box_as_container(self):
        """Cartonization: la caja seleccionada actúa como contenedor."""
        sol = _solution([_packed("SKU#0", "BOX_M", 0, 0, 0, 5, 5, 5)])
        box = Container(id="BOX_M", length=40, width=30, height=25)
        fig = plot_container_3d(sol, box)
        assert fig is not None
        assert fig.layout.scene.xaxis.range[1] == pytest.approx(40 * 1.05)


# ===========================================================================
# F9 — Export HTML (capacidad Plotly, usada en D-Wave packing3d.py)
# ===========================================================================


class TestF9HtmlExport:
    def test_figure_can_write_html(self, two_item_solution, tmp_path):
        container = Container(id="C1", length=30, width=40, height=50)
        fig = plot_container_3d(two_item_solution, container)
        out = tmp_path / "layout3d.html"
        fig.write_html(str(out), include_plotlyjs="cdn")
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        assert "plotly" in text.lower()
        assert "mesh3d" in text.lower() or "Mesh3d" in text


# ===========================================================================
# F10 — End-to-end: algoritmo real → PackingSolution → figura 3D
# ===========================================================================


class TestF10EndToEndAlgorithmToViz:
    def test_best_fit_solution_renders_3d(self):
        from packing_services.services.algorithm_input_service import AlgorithmInputService
        from packing_services.services.algorithm_execution_service import AlgorithmExecutionService

        payload = AlgorithmInputService().build_input_example(
            "best_fit_decreasing_3d", problem_type=ProblemType.THREE_D_BPP
        )
        response = AlgorithmExecutionService().execute("best_fit_decreasing_3d", payload)
        solution = response.solution
        assert solution is not None
        assert solution.packed_items

        containers = [Container(**c) for c in payload["containers"]]
        figs = plot_solution_3d(solution, containers, title_prefix="E2E")
        assert figs
        total_meshes = 0
        for fig in figs:
            meshes = [t for t in fig.data if t.type == "mesh3d"]
            wires = [t for t in fig.data if t.type == "scatter3d"]
            assert len(meshes) >= 1
            assert len(wires) == 1
            assert fig.layout.scene.aspectmode == "data"
            total_meshes += len(meshes)
        assert total_meshes == len(solution.packed_items)


# ===========================================================================
# F11 — Paridad JS (layout-viz-3d.js) con geometría Python
# ===========================================================================


class TestF11JsGeometryParity:
    """Valida helpers de layout-viz-3d.js vía Node (sin browser)."""

    def test_js_cuboid_mesh_and_wireframe(self):
        js_path = ROOT / "web-demo" / "static" / "assets" / "js" / "layout-viz-3d.js"
        assert js_path.exists()
        script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync({json.dumps(str(js_path))}, 'utf8');
const ctx = {{ console, LayoutViz: {{ pickBestWorstByUtilization: () => null }} }};
vm.createContext(ctx);
vm.runInContext(code, ctx);
const L = ctx.LayoutViz3D;
const mesh = L.cuboidMesh([1, 2, 3], [4, 5, 6]);
if (mesh.x.length !== 8) throw new Error('expected 8 corners, got ' + mesh.x.length);
if (mesh.i.length !== 12) throw new Error('expected 12 triangles');
const minX = Math.min(...mesh.x), maxX = Math.max(...mesh.x);
if (minX !== 1 || maxX !== 5) throw new Error('x bbox');
const wire = L.wireframeTrace(10, 20, 30);
const xs = wire.x.filter(v => v !== null);
if (Math.max(...xs) !== 10) throw new Error('wire x');
if (wire.x.filter(v => v === null).length !== 12) throw new Error('12 edges');
const colors = L.colorMap(['P1#0', 'P1#1', 'P2#0']);
if (colors.P1 === colors.P2) throw new Error('sku colors');
const dims = L.dimsFor('C1', [{{id:'C1', length:100, width:80, height:60}}], []);
if (dims.length !== 100 || dims.width !== 80 || dims.height !== 60) throw new Error('dims');
console.log(JSON.stringify({{ ok: true, corners: mesh.x.length, edges: 12 }}));
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["ok"] is True

    def test_web_demo_pages_include_plotly_and_layout_viz_3d(self):
        for page in ("execute.html", "benchmark.html"):
            html = (ROOT / "web-demo" / "static" / page).read_text(encoding="utf-8")
            assert "plotly" in html.lower()
            assert "layout-viz-3d.js" in html
            assert "result-layout-3d" in html or "benchmark-layout-3d" in html


# ===========================================================================
# F12 — Checklist de cobertura funcional (meta-test documentado)
# ===========================================================================


class TestF12FeatureChecklist:
    """Asegura que el inventario D-Wave → PS está cubierto por esta suite."""

    FEATURES = {
        "F1_cuboid_geometry": TestF1CuboidGeometry,
        "F2_solution_mapping": TestF2SolutionToCuboids,
        "F3_mesh3d_traces": TestF3Mesh3dTraces,
        "F4_color_coding": TestF4ColorCoding,
        "F5_container_boundary": TestF5ContainerBoundary,
        "F6_figure_layout": TestF6FigureLayout,
        "F7_multi_container": TestF7MultiContainerAdaptation,
        "F8_box_dims": TestF8ContainerAndBoxDims,
        "F9_html_export": TestF9HtmlExport,
        "F10_e2e_algorithm": TestF10EndToEndAlgorithmToViz,
        "F11_js_parity": TestF11JsGeometryParity,
    }

    def test_all_feature_groups_present(self):
        assert len(self.FEATURES) == 11
        for name, cls in self.FEATURES.items():
            methods = [m for m in dir(cls) if m.startswith("test_")]
            assert methods, f"{name} sin tests"
