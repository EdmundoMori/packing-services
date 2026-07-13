"""Presentación resumida de resultados (sin ruido técnico)."""

from __future__ import annotations

import html
from typing import Any

import matplotlib.pyplot as plt
from IPython.display import HTML, display as ipy_display

from packing_services.domain.models import Container, Metrics, PackingSolution
from packing_services.schemas.responses import BenchmarkResponse, ValidateResponse


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def show_problem_overview(data: dict[str, Any]) -> None:
    """Presenta el **problema** (entrada) antes de mostrar cualquier solución."""

    import pandas as pd

    from .loaders import total_item_units

    desc = data.get("description", "")
    objective = data.get("objective", "maximize_volume_utilization")
    problem_type = data.get("problem_type", "3D_BPP")
    n_units = total_item_units(data.get("items", []))

    intro = f"""
    <div style="background:#e3f2fd;border-left:6px solid #1565c0;padding:16px;margin:12px 0;border-radius:4px;color:#212121;">
      <h3 style="margin:0 0 8px 0;color:#0d47a1;">Problema a resolver ({problem_type})</h3>
      <p style="margin:6px 0;color:#212121;"><b>Objetivo:</b> {html.escape(objective.replace('_', ' '))}</p>
      {f'<p style="margin:6px 0;color:#424242;">{html.escape(desc)}</p>' if desc else ''}
      <p style="margin:6px 0;color:#212121;"><b>Total de piezas a colocar:</b> {n_units}</p>
    </div>
    """
    ipy_display(HTML(intro))

    if data.get("containers"):
        print("Contenedores disponibles:")
        c_rows = [
            {
                "ID": c["id"],
                "Largo": c["length"],
                "Ancho": c["width"],
                "Alto": c["height"],
                "Peso máx": c.get("max_weight", "—"),
                "Volumen": c["length"] * c["width"] * c["height"],
            }
            for c in data.get("containers", [])
        ]
        ipy_display(pd.DataFrame(c_rows).style.hide(axis="index"))

    if data.get("boxes"):
        print("Catálogo de cajas candidatas:")
        b_rows = [
            {
                "Caja": b["id"],
                "Largo": b["length"],
                "Ancho": b["width"],
                "Alto": b["height"],
                "Peso máx": b.get("max_weight", "—"),
                "Volumen": b["length"] * b["width"] * b["height"],
            }
            for b in data.get("boxes", [])
        ]
        ipy_display(pd.DataFrame(b_rows).style.hide(axis="index"))

    print("Catálogo de piezas (ítems):")
    i_rows = [
        {
            "Tipo": it["id"],
            "Largo": it["length"],
            "Ancho": it["width"],
            "Alto": it["height"],
            "Peso": it.get("weight", 0),
            "Cantidad": it.get("quantity", 1),
        }
        for it in data.get("items", [])
    ]
    ipy_display(pd.DataFrame(i_rows).style.hide(axis="index"))

    constraints = data.get("constraints", {})
    active = [k for k, v in constraints.items() if v]
    print("Restricciones activas:", ", ".join(active) if active else "ninguna")


def show_comparable_algorithms(group: str = "3D_BPP") -> None:
    """Tabla de motores comparables para un grupo de benchmark."""

    import pandas as pd

    from .loaders import BENCHMARK_GROUPS, filter_available_engines

    meta = BENCHMARK_GROUPS[group]
    engines = filter_available_engines(meta["engines"])
    rows = [
        {
            "#": i + 1,
            "Algoritmo": e["name"],
            "Nombre": e["label"],
            "Opcional": "Sí" if e.get("optional") else "No",
        }
        for i, e in enumerate(engines)
    ]
    print(f"Motores comparables — {meta['title']}:")
    ipy_display(pd.DataFrame(rows).style.hide(axis="index"))


def show_kpis(
    metrics: Metrics,
    *,
    valid: bool | None = None,
    algorithm: str | None = None,
    extra: dict[str, str] | None = None,
) -> None:
    """Tarjetas KPI grandes para audiencia no técnica."""

    valid_html = ""
    if valid is not None:
        color = "#2e7d32" if valid else "#c62828"
        label = "Válida" if valid else "Inválida"
        valid_html = (
            f'<div style="flex:1;min-width:140px;background:{color};color:white;'
            f'padding:16px;border-radius:8px;text-align:center;">'
            f'<div style="font-size:13px;opacity:.9">Estado</div>'
            f'<div style="font-size:28px;font-weight:bold">{label}</div></div>'
        )

    algo_html = ""
    if algorithm:
        algo_html = (
            f'<div style="flex:1;min-width:180px;background:#1565c0;color:white;'
            f'padding:16px;border-radius:8px;text-align:center;">'
            f'<div style="font-size:13px;opacity:.9">Algoritmo</div>'
            f'<div style="font-size:16px;font-weight:bold">{algorithm}</div></div>'
        )

    extra_html = ""
    if extra:
        for key, val in extra.items():
            extra_html += (
                f'<div style="flex:1;min-width:140px;background:#5e35b1;color:white;'
                f'padding:16px;border-radius:8px;text-align:center;">'
                f'<div style="font-size:13px;opacity:.9">{key}</div>'
                f'<div style="font-size:24px;font-weight:bold">{val}</div></div>'
            )

    html = f"""
    <div style="display:flex;flex-wrap:wrap;gap:12px;margin:12px 0;">
      {algo_html}
      <div style="flex:1;min-width:140px;background:#ef6c00;color:white;padding:16px;border-radius:8px;text-align:center;">
        <div style="font-size:13px;opacity:.9">Utilización</div>
        <div style="font-size:32px;font-weight:bold">{_pct(metrics.volume_utilization)}</div>
      </div>
      <div style="flex:1;min-width:140px;background:#00838f;color:white;padding:16px;border-radius:8px;text-align:center;">
        <div style="font-size:13px;opacity:.9">Empacados</div>
        <div style="font-size:32px;font-weight:bold">{metrics.items_packed}</div>
      </div>
      <div style="flex:1;min-width:140px;background:#6d4c41;color:white;padding:16px;border-radius:8px;text-align:center;">
        <div style="font-size:13px;opacity:.9">Sin empacar</div>
        <div style="font-size:32px;font-weight:bold">{metrics.items_unpacked}</div>
      </div>
      {valid_html}
      {extra_html}
    </div>
    """
    ipy_display(HTML(html))


def show_weight_kpis(loaded: float, max_weight: float | None, valid: bool) -> None:
    max_label = f"{max_weight:.0f} kg" if max_weight else "sin límite"
    pct = (loaded / max_weight * 100) if max_weight and max_weight > 0 else 0
    show_kpis(
        Metrics(loaded_weight=loaded, volume_utilization=pct / 100),
        valid=valid,
        extra={"Peso cargado": f"{loaded:.0f} kg", "Máximo": max_label},
    )


def summarize_items_table(items: list) -> None:
    """Tabla simple de ítems de entrada (agrupa por tipo)."""

    import pandas as pd

    rows = []
    for it in items:
        rows.append(
            {
                "Tipo": it.id,
                "Largo": it.length,
                "Ancho": it.width,
                "Alto": it.height,
                "Peso": it.weight,
                "Cantidad": it.quantity,
            }
        )
    ipy_display(pd.DataFrame(rows))


def summarize_benchmark(response: BenchmarkResponse, *, title: str | None = None) -> None:
    import pandas as pd

    group = response.details.get("benchmark_group", "")
    profile = response.details.get("benchmark_profile", "")
    if title:
        print(title)
    elif group:
        suffix = f" (perfil: {profile})" if profile else ""
        print(f"Benchmark — {group.replace('_', ' ')}{suffix}")

    rows = []
    rank = {name: i + 1 for i, name in enumerate(response.ranking)}
    for r in response.results:
        row = {
            "Posición": rank.get(r.engine, "-"),
            "Algoritmo": r.engine,
            "Utilización": _pct(r.metrics.volume_utilization),
            "Empacados": r.metrics.items_packed,
            "Sin empacar": r.metrics.items_unpacked,
            "Válida": "Sí" if r.is_valid else "No",
            "Tiempo (s)": f"{r.metrics.execution_time_seconds:.4f}",
        }
        if r.details.get("selected_box_id"):
            row["Caja elegida"] = r.details["selected_box_id"]
        if r.solution and r.solution.execution_metadata.parameters.get("items_relocated") is not None:
            row["Piezas movidas"] = r.solution.execution_metadata.parameters["items_relocated"]
        if r.status == "error":
            row["Error"] = (r.error or "error")[:80]
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("Posición")
    ipy_display(df.style.hide(axis="index"))
    if response.ranking_explanation:
        print(response.ranking_explanation)


def run_and_show_showcase_benchmark(
    group: str,
    instance: dict[str, Any] | None = None,
    *,
    title: str | None = None,
    show_chart: bool = True,
    note: str | None = None,
) -> BenchmarkResponse:
    """Ejecuta y presenta el benchmark homogéneo de un grupo showcase."""

    from . import viz
    from .loaders import (
        BENCHMARK_GROUPS,
        SHOWCASE_DIFFERENTIATION,
        build_benchmark_for_group,
        load_showcase_instance,
        problem_type_for_benchmark_group,
    )
    from .runners import run_benchmark

    meta = BENCHMARK_GROUPS[group]
    if instance is None:
        instance = load_showcase_instance(problem_type_for_benchmark_group(group))

    show_comparable_algorithms(group)
    if note or group in SHOWCASE_DIFFERENTIATION:
        print(f"Nota: {note or SHOWCASE_DIFFERENTIATION[group]}")

    response = run_benchmark(build_benchmark_for_group(group, instance))
    summarize_benchmark(response, title=title or f"Benchmark — {meta['title']}")
    if show_chart:
        fig = viz.plot_benchmark_bars(response)
        if fig:
            plt.show()
    return response


def summarize_validation(response: ValidateResponse, title: str) -> None:
    """Resumen legible del validador (alto contraste en temas claros y oscuros)."""

    report = response.validation_report
    valid = report.is_valid
    status = "Solución válida" if valid else "Solución inválida"
    status_icon = "✓" if valid else "✗"

    if valid:
        bg = "#e8f5e9"
        border = "#2e7d32"
        heading_color = "#1b5e20"
        badge_bg = "#2e7d32"
    else:
        bg = "#ffebee"
        border = "#c62828"
        heading_color = "#b71c1c"
        badge_bg = "#c62828"

    n_errors = report.error_count
    summary = (
        f"{n_errors} violación detectada" if n_errors == 1 else f"{n_errors} violaciones detectadas"
    )
    if valid:
        summary = "Sin violaciones geométricas ni de restricciones"

    violations_html = ""
    if report.violations:
        li_parts: list[str] = []
        for v in report.violations:
            item_note = ""
            if v.item_ids:
                item_note = (
                    f' <span style="color:#616161;">'
                    f"(ítems: {html.escape(', '.join(v.item_ids))})</span>"
                )
            li_parts.append(
                f"<li style='margin:6px 0;color:#212121;'>"
                f"<b style='color:{heading_color};'>{html.escape(v.type)}</b>: "
                f"{html.escape(v.message)}{item_note}</li>"
            )
        violations_html = (
            f"<ul style='margin:8px 0 0 18px;padding:0;color:#212121;'>"
            f"{''.join(li_parts)}</ul>"
        )

    html_block = f"""
    <div style="background:{bg};border-left:6px solid {border};padding:16px;margin:12px 0;border-radius:4px;color:#212121;">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px;">
        <span style="background:{badge_bg};color:#ffffff;font-weight:bold;font-size:18px;
          padding:6px 14px;border-radius:20px;">{status_icon} {status}</span>
        <h3 style="margin:0;color:{heading_color};font-size:18px;">{html.escape(title)}</h3>
      </div>
      <p style="margin:0;color:#424242;">{html.escape(summary)}</p>
      {violations_html}
    </div>
    """
    ipy_display(HTML(html_block))
    print(f"{title} — {status} ({summary})")


def solution_item_types(solution: PackingSolution) -> dict[str, int]:
    """Cuenta piezas empacadas por tipo base (sin sufijo #n)."""

    counts: dict[str, int] = {}
    for p in solution.packed_items:
        base = p.item_id.split("#")[0]
        counts[base] = counts.get(base, 0) + 1
    return counts


def container_by_id(containers: list[Container], container_id: str) -> Container:
    for c in containers:
        if c.id == container_id:
            return c
    return containers[0]
