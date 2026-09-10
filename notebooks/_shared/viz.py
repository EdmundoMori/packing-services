"""Gráficos didácticos para layouts de packing y comparaciones."""

from __future__ import annotations

from typing import Iterable

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from packing_services.domain.models import Container, PackedItem, PackingSolution
from packing_services.schemas.responses import BenchmarkResponse

# Paleta distinguible para tipos de ítem.
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


def _base_id(item_id: str) -> str:
    return item_id.split("#")[0]


def _color_map(item_ids: Iterable[str]) -> dict[str, str]:
    bases = sorted({_base_id(i) for i in item_ids})
    return {b: _COLORS[i % len(_COLORS)] for i, b in enumerate(bases)}


def _setup_ax(ax: Axes, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_aspect("equal")
    ax.grid(True, linestyle=":", alpha=0.4)


def plot_container_views(
    solution: PackingSolution,
    container: Container,
    *,
    container_id: str | None = None,
    title: str | None = None,
    highlight_items: set[str] | None = None,
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Vista superior (XY) y lateral (XZ) del layout."""

    cid = container_id or (solution.packed_items[0].container_id if solution.packed_items else container.id)
    items = [p for p in solution.packed_items if p.container_id == cid]
    colors = _color_map(p.item_id for p in items)

    fig, axes = plt.subplots(1, 2, figsize=figsize)
    main_title = title or f"Layout — {solution.algorithm_name}"
    fig.suptitle(main_title, fontsize=14, fontweight="bold")

    # Vista superior: X (length) × Y (width)
    ax = axes[0]
    _draw_container_frame(ax, container.length, container.width)
    for p in items:
        x, y = p.position.x, p.position.y
        w, h = p.orientation.length, p.orientation.width
        color = colors[_base_id(p.item_id)]
        edge = "#c62828" if highlight_items and p.item_id in highlight_items else "#333"
        lw = 2.5 if highlight_items and p.item_id in highlight_items else 1.2
        rect = mpatches.Rectangle((x, y), w, h, facecolor=color, edgecolor=edge, linewidth=lw, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, _base_id(p.item_id), ha="center", va="center", fontsize=8, color="white", fontweight="bold")
    _setup_ax(ax, "Vista superior (desde arriba)", "X — largo", "Y — ancho")
    ax.set_xlim(-2, container.length + 5)
    ax.set_ylim(-2, container.width + 5)

    # Vista lateral: X (length) × Z (height)
    ax = axes[1]
    _draw_container_frame(ax, container.length, container.height)
    for p in items:
        x, z = p.position.x, p.position.z
        w, h = p.orientation.length, p.orientation.height
        color = colors[_base_id(p.item_id)]
        edge = "#c62828" if highlight_items and p.item_id in highlight_items else "#333"
        lw = 2.5 if highlight_items and p.item_id in highlight_items else 1.2
        rect = mpatches.Rectangle((x, z), w, h, facecolor=color, edgecolor=edge, linewidth=lw, alpha=0.85)
        ax.add_patch(rect)
    _setup_ax(ax, "Vista lateral (perfil)", "X — largo", "Z — alto")
    ax.set_xlim(-2, container.length + 5)
    ax.set_ylim(-2, container.height + 5)

    # Leyenda por tipo
    handles = [
        mpatches.Patch(color=colors[b], label=b)
        for b in sorted(colors)
    ]
    fig.legend(handles=handles, loc="lower center", ncol=min(4, len(handles)), bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout()
    return fig


def _draw_container_frame(ax: Axes, width: float, height: float) -> None:
    frame = mpatches.Rectangle(
        (0, 0), width, height, fill=False, edgecolor="#424242", linewidth=2, linestyle="--"
    )
    ax.add_patch(frame)


def plot_all_container_views(
    solution: PackingSolution,
    containers: list[Container],
    *,
    title_prefix: str = "",
) -> Figure | None:
    """Vista superior por cada contenedor que tenga piezas colocadas."""

    used = [c for c in containers if any(p.container_id == c.id for p in solution.packed_items)]
    if not used:
        return None
    n = len(used)
    fig, axes = plt.subplots(1, n, figsize=(5.5 * n, 5))
    if n == 1:
        axes = [axes]
    prefix = f"{title_prefix} — " if title_prefix else ""
    fig.suptitle(f"{prefix}{solution.algorithm_name}", fontsize=13, fontweight="bold")
    for ax, container in zip(axes, used):
        items = [p for p in solution.packed_items if p.container_id == container.id]
        colors = _color_map(p.item_id for p in items)
        _draw_container_frame(ax, container.length, container.width)
        for p in items:
            x, y = p.position.x, p.position.y
            w, h = p.orientation.length, p.orientation.width
            rect = mpatches.Rectangle(
                (x, y), w, h, facecolor=colors[_base_id(p.item_id)], edgecolor="#333", alpha=0.85
            )
            ax.add_patch(rect)
        _setup_ax(ax, f"Contenedor {container.id} (vista superior)", "X", "Y")
        ax.set_xlim(-2, container.length + 5)
        ax.set_ylim(-2, container.width + 5)
    fig.tight_layout()
    return fig


def plot_utilization_bar(utilization: float, *, title: str = "Aprovechamiento del contenedor") -> Figure:
    fig, ax = plt.subplots(figsize=(6, 1.8))
    used = utilization
    waste = max(0.0, 1.0 - used)
    ax.barh(["Contenedor"], [used], color="#43a047", label="Usado")
    ax.barh(["Contenedor"], [waste], left=[used], color="#e0e0e0", label="Vacío")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Fracción del volumen")
    ax.set_title(f"{title}: {used * 100:.1f}%", fontweight="bold")
    ax.legend(loc="upper right")
    fig.tight_layout()
    return fig


def plot_benchmark_bars(response: BenchmarkResponse) -> Figure:
    """Comparación visual de algoritmos del benchmark."""

    engines = [r.engine.replace("_", " ") for r in response.results]
    utils = [r.metrics.volume_utilization * 100 for r in response.results]
    packed = [r.metrics.items_packed for r in response.results]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    colors = ["#4e79a7" if response.results[i].is_valid else "#bdbdbd" for i in range(len(engines))]

    axes[0].barh(engines, utils, color=colors)
    axes[0].set_xlabel("Utilización volumétrica (%)")
    axes[0].set_title("¿Cuánto espacio se aprovecha?", fontweight="bold")
    axes[0].set_xlim(0, 100)

    axes[1].barh(engines, packed, color=colors)
    axes[1].set_xlabel("Ítems empacados")
    axes[1].set_title("¿Cuántas piezas entraron?", fontweight="bold")

    # Marcar ganador
    if response.ranking:
        winner = response.ranking[0].replace("_", " ")
        for ax in axes:
            for label in ax.get_yticklabels():
                if label.get_text() == winner:
                    label.set_fontweight("bold")

    fig.suptitle("Comparación de algoritmos (misma instancia, mismo validador)", fontweight="bold")
    fig.tight_layout()
    return fig


def plot_weight_bar(loaded: float, max_weight: float, *, title: str = "Peso cargado") -> Figure:
    fig, ax = plt.subplots(figsize=(6, 2))
    pct = min(loaded / max_weight, 1.0) if max_weight > 0 else 0
    ax.barh(["Camión"], [pct], color="#1565c0", label="Cargado")
    ax.barh(["Camión"], [max(0, 1 - pct)], left=[pct], color="#e0e0e0", label="Margen")
    ax.set_xlim(0, 1)
    ax.set_title(f"{title}: {loaded:.0f} / {max_weight:.0f} kg ({pct * 100:.1f}%)", fontweight="bold")
    ax.set_xlabel("Fracción del peso máximo")
    fig.tight_layout()
    return fig


def plot_box_catalog(evaluated: list[dict], selected_id: str | None) -> Figure:
    """Tarjetas visuales de cajas candidatas en cartonization."""

    ids = [b["box_id"] for b in evaluated]
    utils = [b.get("volume_utilization", 0) * 100 for b in evaluated]
    fits = [b.get("fits_all", False) for b in evaluated]
    colors = []
    for b in evaluated:
        if b["box_id"] == selected_id:
            colors.append("#2e7d32")
        elif b.get("fits_all"):
            colors.append("#4e79a7")
        else:
            colors.append("#bdbdbd")

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(ids, utils, color=colors, edgecolor="#333")
    ax.set_ylabel("Utilización volumétrica (%)")
    ax.set_title("Evaluación de cajas candidatas", fontweight="bold")
    ax.set_ylim(0, max(utils + [10]) * 1.15)

    for bar, fit, box in zip(bars, fits, evaluated):
        label = "Cabe todo" if fit else f"{box.get('items_packed', 0)} piezas"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, label, ha="center", fontsize=9)

    if selected_id:
        ax.text(0.98, 0.95, f"Elegida: {selected_id}", transform=ax.transAxes, ha="right", va="top",
                fontsize=11, fontweight="bold", color="#2e7d32",
                bbox=dict(boxstyle="round", facecolor="#e8f5e9", edgecolor="#2e7d32"))

    fig.tight_layout()
    return fig


def plot_algorithm_catalog_counts(implemented: int, adapter: int, future: int) -> Figure:
    fig, ax = plt.subplots(figsize=(5, 5))
    sizes = [implemented, adapter, future]
    labels = [f"Implementados\n({implemented})", f"Adaptadores\n({adapter})", f"Futuros\n({future})"]
    colors = ["#43a047", "#fb8c00", "#bdbdbd"]
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.0f%%", startangle=90)
    ax.set_title(
        f"Catálogo de algoritmos ({implemented + adapter + future} en total)",
        fontweight="bold",
    )
    fig.tight_layout()
    return fig


def plot_roadmap_phases() -> Figure:
    phases = [
        ("Fase 0–11\nCore + API + CL", 1),
        ("Pallet +\nStacking", 1),
        ("Metaheurísticas\n3D-BPP", 1),
        ("BED-BPP +\nexperimento conjunto", 1),
        ("Online / DRL", 0),
        ("Adaptadores\nreales", 0),
        ("Espacio de datos\n(despriorizado)", 0),
    ]
    fig, ax = plt.subplots(figsize=(10, 2.5))
    for i, (name, done) in enumerate(phases):
        color = "#43a047" if done else "#e0e0e0"
        edge = "#2e7d32" if done else "#9e9e9e"
        ax.bar(i, 1, color=color, edgecolor=edge, linewidth=2)
        ax.text(i, 0.5, name, ha="center", va="center", fontsize=9, fontweight="bold" if done else "normal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Hoja de ruta: verde = completado, gris = pendiente", fontweight="bold")
    fig.tight_layout()
    return fig
