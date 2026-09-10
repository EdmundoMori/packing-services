"""Visualización 3D de soluciones de packing (Plotly Mesh3d).

Adaptado del núcleo geométrico de dwave-examples/3d-bin-packing
(``utils._cuboid_data`` / ``_get_all_cuboids`` / ``_plot_cuboids``),
Apache License 2.0 — Copyright 2022 D-Wave Systems Inc.

Diferencias respecto al original:
- Entrada: ``PackingSolution`` + contenedores (no SampleSet CQM).
- Una escena por contenedor (no bins concatenados en el eje X).
- Wireframe completo del contenedor (12 aristas).
- Color por SKU base (``item_id`` sin sufijo ``#N``).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Sequence

from packing_services.domain.models import Container, PackedItem, PackingSolution

# Misma paleta que notebooks/_shared/viz.py y web-demo layout-viz.js
_COLORS = [
    "#4e79a7",
    "#f28e2b",
    "#e15759",
    "#76b7b2",
    "#59a14f",
    "#edc948",
    "#b07aa1",
    "#ff9da7",
    "#9c755f",
    "#bab0ac",
]


def base_id(item_id: str) -> str:
    return str(item_id).split("#")[0]


def color_map(item_ids: Iterable[str]) -> dict[str, str]:
    bases = sorted({base_id(i) for i in item_ids})
    return {b: _COLORS[i % len(_COLORS)] for i, b in enumerate(bases)}


def extract_cuboids(
    packed_items: Sequence[PackedItem],
    container_id: str,
) -> list[dict[str, Any]]:
    """Mapea ítems empacados de un contenedor a cuboides {item_id, position, size}.

    Función pura (sin Plotly) para tests y para alimentar el renderizado.
    """
    cuboids: list[dict[str, Any]] = []
    for p in packed_items:
        if p.container_id != container_id:
            continue
        cuboids.append(
            {
                "item_id": p.item_id,
                "sku": base_id(p.item_id),
                "position": (float(p.position.x), float(p.position.y), float(p.position.z)),
                "size": (
                    float(p.orientation.length),
                    float(p.orientation.width),
                    float(p.orientation.height),
                ),
            }
        )
    return cuboids


def container_dims(
    container: Container | None,
    cuboids: Sequence[dict[str, Any]],
) -> tuple[float, float, float]:
    if container is not None:
        return float(container.length), float(container.width), float(container.height)
    if not cuboids:
        return 100.0, 80.0, 80.0
    max_x = max(c["position"][0] + c["size"][0] for c in cuboids)
    max_y = max(c["position"][1] + c["size"][1] for c in cuboids)
    max_z = max(c["position"][2] + c["size"][2] for c in cuboids)
    return max_x or 100.0, max_y or 80.0, max_z or 80.0


def cuboid_vertices(origin: tuple[float, float, float], size: tuple[float, float, float]):
    """Vértices de las 6 caras de un cuboide (adaptado de D-Wave ``_cuboid_data``)."""
    import numpy as np

    faces = [
        [[0, 1, 0], [0, 0, 0], [1, 0, 0], [1, 1, 0]],
        [[0, 0, 0], [0, 0, 1], [1, 0, 1], [1, 0, 0]],
        [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]],
        [[0, 0, 1], [0, 0, 0], [0, 1, 0], [0, 1, 1]],
        [[0, 1, 0], [0, 1, 1], [1, 1, 1], [1, 1, 0]],
        [[0, 1, 1], [0, 0, 1], [1, 0, 1], [1, 1, 1]],
    ]
    X = np.array(faces, dtype=float)
    for i in range(3):
        X[:, :, i] *= size[i]
    X += np.array(origin, dtype=float)
    return X


def _mesh3d_from_cuboid(
    origin: tuple[float, float, float],
    size: tuple[float, float, float],
    *,
    name: str,
    color: str,
):
    import numpy as np
    import plotly.graph_objects as go

    case_points = cuboid_vertices(origin, size)
    x, y, z = np.unique(np.vstack(case_points), axis=0).T
    return go.Mesh3d(
        x=x,
        y=y,
        z=z,
        name=name,
        color=color,
        alphahull=0,
        flatshading=True,
        opacity=0.88,
        showlegend=True,
        hovertext=name,
        hoverinfo="text",
    )


def _container_wireframe(length: float, width: float, height: float):
    """12 aristas del contenedor como Scatter3d."""
    import plotly.graph_objects as go

    corners = [
        (0, 0, 0),
        (length, 0, 0),
        (length, width, 0),
        (0, width, 0),
        (0, 0, height),
        (length, 0, height),
        (length, width, height),
        (0, width, height),
    ]
    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    xs: list[float | None] = []
    ys: list[float | None] = []
    zs: list[float | None] = []
    for a, b in edges:
        xs.extend([corners[a][0], corners[b][0], None])
        ys.extend([corners[a][1], corners[b][1], None])
        zs.extend([corners[a][2], corners[b][2], None])
    return go.Scatter3d(
        x=xs,
        y=ys,
        z=zs,
        mode="lines",
        name="Contenedor",
        line=dict(color="#b91c1c", width=5),
        hoverinfo="skip",
        showlegend=True,
    )


def build_container_traces(
    cuboids: Sequence[dict[str, Any]],
    length: float,
    width: float,
    height: float,
    *,
    color_coded: bool = True,
) -> list:
    """Construye traces Mesh3d + wireframe (equivalente a D-Wave ``_get_all_cuboids`` + bordes)."""
    colors = color_map(c["item_id"] for c in cuboids) if color_coded else {}
    traces = []
    for c in cuboids:
        color = colors.get(c["sku"], "#4e79a7") if color_coded else "#4e79a7"
        traces.append(
            _mesh3d_from_cuboid(
                c["position"],
                c["size"],
                name=c["item_id"],
                color=color,
            )
        )
    traces.append(_container_wireframe(length, width, height))
    return traces


def plot_container_3d(
    solution: PackingSolution,
    container: Container | None,
    *,
    container_id: str | None = None,
    title: str | None = None,
    color_coded: bool = True,
):
    """Figura Plotly 3D de un contenedor con sus piezas empacadas.

    ``color_coded`` refleja el flag homónimo de D-Wave ``plot_cuboids``.
    """
    import plotly.graph_objects as go

    cid = container_id or (container.id if container else None)
    if cid is None and solution.packed_items:
        cid = solution.packed_items[0].container_id
    if cid is None:
        return None

    cuboids = extract_cuboids(solution.packed_items, cid)
    if not cuboids:
        return None

    length, width, height = container_dims(container, cuboids)
    traces = build_container_traces(
        cuboids, length, width, height, color_coded=color_coded
    )

    fig = go.Figure(data=traces)
    # Rangos con margen (~1.05; D-Wave usa 1.1 sobre bins concatenados).
    fig.update_layout(
        title=title or f"Layout 3D — {cid}",
        margin=dict(l=0, r=0, t=40, b=0),
        scene=dict(
            xaxis=dict(title="X (largo)", range=[0, length * 1.05]),
            yaxis=dict(title="Y (ancho)", range=[0, width * 1.05]),
            zaxis=dict(title="Z (alto)", range=[0, height * 1.05]),
            aspectmode="data",
        ),
        legend=dict(itemsizing="constant"),
    )
    return fig


def plot_solution_3d(
    solution: PackingSolution,
    containers: Sequence[Container] | None = None,
    *,
    title_prefix: str = "",
    color_coded: bool = True,
) -> list:
    """Una figura Plotly por cada contenedor con piezas empacadas."""
    by_id: dict[str, Container] = {c.id: c for c in (containers or [])}
    grouped: dict[str, list[PackedItem]] = defaultdict(list)
    for p in solution.packed_items:
        grouped[p.container_id].append(p)

    figures = []
    for cid in sorted(grouped):
        container = by_id.get(cid)
        prefix = f"{title_prefix} — " if title_prefix else ""
        fig = plot_container_3d(
            solution,
            container,
            container_id=cid,
            title=f"{prefix}{cid}",
            color_coded=color_coded,
        )
        if fig is not None:
            figures.append(fig)
    return figures
